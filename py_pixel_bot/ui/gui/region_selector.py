import logging
import tkinter as tk # For basic Toplevel and event bindings if needed beyond CTk
from tkinter import messagebox # For showing errors if screenshot fails, etc.
from typing import Optional, Dict, Any

import customtkinter as ctk
from PIL import ImageGrab # For taking a screenshot of the entire screen for the overlay

from py_pixel_bot.core.config_manager import ConfigManager # To save the region

logger = logging.getLogger(__name__)

class RegionSelectorWindow(ctk.CTkToplevel):
    """
    A Toplevel window that provides a transparent overlay for selecting a screen region.
    Allows drawing a rectangle and confirming the selection with a name.
    The selected region (name and coordinates) is then saved to the provided ConfigManager's profile.
    """

    def __init__(self, master: Any, config_manager: ConfigManager, 
                 existing_region_data: Optional[Dict[str, Any]] = None):
        """
        Initializes the RegionSelectorWindow.

        Args:
            master: The master window (can be a CTk root or another Toplevel).
            config_manager: The ConfigManager instance for the profile to update.
            existing_region_data: Optional. If provided, pre-fills fields for editing a region.
                                   Expected keys: "name", "x", "y", "width", "height".
        """
        super().__init__(master)
        # If master is None (e.g. when called from CLI with no existing GUI root),
        # CTkToplevel will create its own hidden root.
        
        self.config_manager = config_manager
        self.existing_region_data = existing_region_data 
        self.profile_path_for_log = config_manager.get_profile_path() if config_manager else "UnknownProfile"

        logger.info(f"Initializing RegionSelectorWindow. Master: {master}, Profile: '{self.profile_path_for_log}'")
        
        self.title("Region Selector - Draw a rectangle, then press 'Enter' or 'Esc'")
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.3) 
        # self.attributes("-topmost", True) # Usually not needed if grab_set is used.
        self.configure(fg_color="black")

        self.start_x_abs: Optional[int] = None # Absolute screen coordinates for start
        self.start_y_abs: Optional[int] = None
        self.rect_id: Optional[int] = None 
        self.current_rect_coords_abs: Optional[tuple[int,int,int,int]] = None # (x1,y1,x2,y2) absolute screen
        self.saved_region_info: Optional[Dict[str, Any]] = None 
        self.changes_made: bool = False # Added to track if save occurred

        try:
            # Grab all screens to handle multi-monitor setups correctly.
            # The canvas will be sized to the combined virtual screen.
            self.screenshot = ImageGrab.grab(all_screens=True) 
            self.bg_image = ctk.CTkImage(light_image=self.screenshot, dark_image=self.screenshot, 
                                         size=(self.screenshot.width, self.screenshot.height))
            logger.debug(f"Screenshot captured for RegionSelector background. Virtual screen size: {self.screenshot.width}x{self.screenshot.height}")
            canvas_width, canvas_height = self.screenshot.width, self.screenshot.height
        except Exception as e:
            logger.error(f"Failed to capture screenshot for RegionSelector background: {e}", exc_info=True)
            self.screenshot = None
            self.bg_image = None
            # Fallback to primary screen dimensions if full grab fails
            canvas_width = self.winfo_screenwidth()
            canvas_height = self.winfo_screenheight()
            messagebox.showwarning("Screenshot Failed", 
                                   "Could not capture full screen for background overlay.\n"
                                   "Selection will still work on a transparent layer based on primary screen.", 
                                   parent=self) # Ensure parent is self for modality

        self.canvas = ctk.CTkCanvas(self, width=canvas_width, height=canvas_height,
                                    highlightthickness=0, bg="black") # Match window bg for transparency effect
        
        if self.bg_image:
            # The canvas origin (0,0) corresponds to the top-left of the virtual screen if all_screens=True worked.
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image)
            logger.debug("Screenshot set as canvas background.")
        
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        instruction_text = "Click & Drag to draw rectangle. Release. Press 'Enter' to Confirm, 'Esc' to Cancel."
        if self.existing_region_data:
            instruction_text = f"Editing '{self.existing_region_data.get('name')}'. Redraw or press 'Enter' to keep current selection, then confirm name."
        
        self.label_instructions = ctk.CTkLabel(
            self.canvas, text=instruction_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=("gray10", "gray90"), text_color=("white", "black"), corner_radius=5, padx=10, pady=5
        )
        # Place instructions on the primary screen, near top-center.
        # For multi-monitor, this is relative to the virtual screen's (0,0).
        # A more robust placement might consider the primary monitor's geometry.
        # For now, simple placement on the canvas assuming (0,0) is top-left of primary or virtual screen.
        self.label_instructions.place(x=canvas_width/2, y=30, anchor="n")

        self.bind("<Escape>", self.cancel_selection)
        self.bind("<Return>", self.show_confirmation_dialog_on_enter)

        if self.existing_region_data:
            self._draw_existing_rectangle()

        logger.info("RegionSelectorWindow fully initialized and displayed fullscreen.")
        self.lift() # Bring to front
        self.focus_force() # Grab keyboard focus
        self.grab_set() # Make this window modal over its master

    def _draw_existing_rectangle(self):
        if self.existing_region_data:
            # These are absolute screen coordinates from the profile
            x_abs = self.existing_region_data.get("x", 0)
            y_abs = self.existing_region_data.get("y", 0)
            w = self.existing_region_data.get("width", 0)
            h = self.existing_region_data.get("height", 0)

            if w > 0 and h > 0:
                # Store these as the initial selection
                self.start_x_abs, self.start_y_abs = x_abs, y_abs # For potential redraw start
                self.current_rect_coords_abs = (x_abs, y_abs, x_abs + w, y_abs + h)
                
                if self.rect_id: self.canvas.delete(self.rect_id)
                # Canvas coordinates are the same as screen coordinates if canvas covers the whole virtual screen
                self.rect_id = self.canvas.create_rectangle(
                    self.current_rect_coords_abs, 
                    outline="lime green", width=3, fill="green", stipple="gray50" # Different color for existing
                )
                logger.info(f"Drew existing rectangle for region '{self.existing_region_data.get('name')}' at screen coords {self.current_rect_coords_abs}")
                self.label_instructions.configure(text=f"Editing '{self.existing_region_data.get('name')}'. Redraw or press 'Enter', then confirm name.")
            else:
                logger.warning(f"Existing region data for '{self.existing_region_data.get('name')}' has zero width/height. Not drawing.")


    def on_mouse_press(self, event):
        # event.x_root, event.y_root are absolute screen coordinates
        self.start_x_abs = event.x_root
        self.start_y_abs = event.y_root
        
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        # Create rectangle using canvas coordinates, which should map 1:1 to screen if canvas is fullscreen
        # and screenshot is correctly placed at (0,0) of canvas.
        self.rect_id = self.canvas.create_rectangle(
            self.start_x_abs, self.start_y_abs, self.start_x_abs, self.start_y_abs, # Start as a point
            outline="red", width=2, fill="red", stipple="gray25" 
        )
        logger.debug(f"Mouse pressed at screen ({self.start_x_abs}, {self.start_y_abs}). New rect ID: {self.rect_id}")
        self.label_instructions.configure(text="Dragging... Release mouse, then press 'Enter' or 'Esc'.")


    def on_mouse_drag(self, event):
        if self.start_x_abs is None or self.start_y_abs is None or self.rect_id is None:
            return
        cur_x_abs = event.x_root
        cur_y_abs = event.y_root
        
        self.canvas.coords(self.rect_id, self.start_x_abs, self.start_y_abs, cur_x_abs, cur_y_abs)
        # logger.debug(f"Mouse dragged to screen ({cur_x_abs}, {cur_y_abs}).") # Too verbose

    def on_mouse_release(self, event):
        if self.start_x_abs is None or self.start_y_abs is None or self.rect_id is None:
            logger.warning("Mouse released but selection start/rect_id is None.")
            return

        end_x_abs = event.x_root
        end_y_abs = event.y_root

        x1 = min(self.start_x_abs, end_x_abs)
        y1 = min(self.start_y_abs, end_y_abs)
        x2 = max(self.start_x_abs, end_x_abs)
        y2 = max(self.start_y_abs, end_y_abs)
        
        if (x2 - x1) > 0 and (y2 - y1) > 0:
            self.current_rect_coords_abs = (int(x1), int(y1), int(x2), int(y2))
            logger.info(f"Mouse released. Finalized rectangle at screen coordinates (x1,y1,x2,y2): {self.current_rect_coords_abs}")
            self.label_instructions.configure(text="Rectangle drawn. Press 'Enter' to confirm name, 'Esc' to cancel/redraw.")
        else: 
            logger.warning(f"Mouse released, but drawn rectangle has no area. Coords: ({x1},{y1},{x2},{y2}). Resetting.")
            if self.rect_id: self.canvas.delete(self.rect_id)
            self.rect_id = None; self.current_rect_coords_abs = None
            self.label_instructions.configure(text="Invalid rectangle (zero area). Click and drag again.")
        

    def show_confirmation_dialog_on_enter(self, event=None):
        if self.current_rect_coords_abs:
            logger.debug("Enter pressed with valid current_rect_coords_abs. Showing confirmation dialog.")
            self._show_name_and_confirm_dialog()
        else:
            logger.info("Enter pressed, but no valid rectangle drawn/selected yet.")
            self.label_instructions.configure(text="No rectangle selected. Click and drag first, then press Enter.")


    def _show_name_and_confirm_dialog(self):
        if not self.current_rect_coords_abs:
            logger.warning("Confirmation dialog attempt, but no rectangle selected."); messagebox.showwarning("No Region", "Please draw or confirm a rectangle first.", parent=self); return

        x1, y1, x2, y2 = self.current_rect_coords_abs
        width = x2 - x1; height = y2 - y1

        if width <= 0 or height <= 0: 
            logger.error(f"Invalid rect dimensions before confirm: W={width}, H={height}"); messagebox.showerror("Error", "Invalid rectangle dimensions. Please redraw.", parent=self); return

        initial_alpha = self.attributes("-alpha"); self.attributes("-alpha", 0.01) # Make very faint
        self.grab_release() 

        default_name_prompt = self.existing_region_data.get("name", "NewRegion") if self.existing_region_data else "MyRegion"
        dialog_title = "Confirm Region" if not self.existing_region_data else f"Confirm Edit: {default_name_prompt}"
        
        # CTkInputDialog does not allow setting an initial value in the entry easily.
        # We'll have to ask the user to type it. A custom dialog would be better for editing.
        dialog = ctk.CTkInputDialog(
            text=f"Enter/Confirm name for this region:\nCoords: (x={x1}, y={y1}, w={width}, h={height})\nDefault was: '{default_name_prompt}'",
            title=dialog_title
        )
        region_name_input = dialog.get_input()

        self.attributes("-alpha", initial_alpha); self.grab_set(); self.focus_force()

        if region_name_input and region_name_input.strip():
            region_name = region_name_input.strip()
            logger.info(f"Region named '{region_name}' with Coords (x={x1}, y={y1}, w={width}, h={height}) confirmed by user.")
            self.save_region(region_name, x1, y1, width, height)
            self.destroy_selector() 
        else:
            logger.info("Region name input cancelled or empty. Rectangle selection remains.")
            self.label_instructions.configure(text="Naming cancelled. Rectangle remains. Press 'Enter' to name again, or 'Esc'.")


    def save_region(self, name: str, x: int, y: int, width: int, height: int):
        new_region_data = {"name": name, "x": x, "y": y, "width": width, "height": height}
        logger.info(f"Preparing to save region: {new_region_data} to profile: '{self.profile_path_for_log}'")
        
        # This method assumes ConfigManager handles the logic of updating or adding.
        # For a robust "edit" mode, ConfigManager would need a way to identify and update
        # an existing region if `self.existing_region_data` was provided and its name didn't change,
        # or handle name changes carefully (e.g. remove old, add new).
        # For simplicity now, it relies on name matching or appending.
        
        # Let MainAppWindow handle the actual update to its self.profile_data
        # and then saving. This dialog should just return the data.
        # For CLI's add-region, it saves directly.
        # This is a divergence. For now, let it save directly as it's also called by CLI.
        
        profile_data = self.config_manager.get_profile_data() # Get current data
        regions = profile_data.get("regions", [])
        
        found_existing_and_updated = False
        if self.existing_region_data and self.existing_region_data.get("name") == name: # Editing existing, name unchanged
            for i, r_spec in enumerate(regions):
                if r_spec.get("name") == name:
                    logger.info(f"Updating existing region '{name}' at index {i}.")
                    regions[i] = new_region_data
                    found_existing_and_updated = True
                    break
        if not found_existing_and_updated: # New region, or name changed (treat as new, old one might still exist if name changed)
             # If it's an edit and name changed, should we remove the old one?
             # For now, if name is new, it's an add. If name exists, it's an update.
            existing_idx_for_new_name = -1
            for i, r_spec in enumerate(regions):
                 if r_spec.get("name") == name:
                      existing_idx_for_new_name = i
                      break
            if existing_idx_for_new_name != -1:
                logger.info(f"Region with name '{name}' already exists. Updating it.")
                regions[existing_idx_for_new_name] = new_region_data
            else:
                logger.info(f"Adding new region '{name}'.")
                regions.append(new_region_data)
            
        profile_data["regions"] = regions
        
        try:
            self.config_manager.save_current_profile() # Saves the modified profile_data
            self.saved_region_info = new_region_data 
            self.changes_made = True # Signal that changes were made
            logger.info(f"Region '{name}' saved successfully to profile '{self.profile_path_for_log}'.")
        except Exception as e:
            logger.error(f"Failed to save profile after updating region '{name}': {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Could not save region '{name}'.\nError: {e}", parent=self)
            self.saved_region_info = None
            self.changes_made = False


    def cancel_selection(self, event=None):
        logger.info("Region selection cancelled.")
        self.saved_region_info = None 
        self.changes_made = False
        self.destroy_selector()

    def destroy_selector(self):
        """Safely destroys the window."""
        logger.debug("RegionSelectorWindow destroy called.")
        self.grab_release() # Important to release grab before destroying
        super().destroy()


if __name__ == '__main__': # (Same test setup as before)
    import os # Added for os.path.exists and os.remove
    # ... (Test code as in previous version, ensuring logging and ConfigManager can init) ...
    if not logging.getLogger("py_pixel_bot").hasHandlers(): logging.basicConfig(level=logging.DEBUG,format='%(asctime)s-%(name)s-%(levelname)s-%(message)s'); logger.info("RegionSelector standalone:Min logging.")
    try:
        root=ctk.CTk();root.title("Master Test");root.geometry("300x200"); test_profile_name="test_region_sel_profile"; dummy_cm=ConfigManager(test_profile_name,create_if_missing=True)
        def open_sel():
            logger.info("Opening RegionSelector...")
            sel=RegionSelectorWindow(master=root,config_manager=dummy_cm)
            root.wait_window(sel)
            # Check if sel.saved_region_info exists and has content
            if hasattr(sel, 'saved_region_info') and sel.saved_region_info: # Line 304 - Corrected
                logger.info(f"Test:Selector closed.Saved:{sel.saved_region_info}\nProfile data:{dummy_cm.get_profile_data()}")
            else:
                logger.info("Test:Selector closed,no save.")

        ctk.CTkButton(root,text="Open Region Selector",command=open_sel).pack(pady=20);ctk.CTkLabel(root,text="Close after test.").pack(pady=10);root.mainloop()
        if dummy_cm.get_profile_path() and os.path.exists(dummy_cm.get_profile_path()):logger.info(f"Cleaning up:{dummy_cm.get_profile_path()}");os.remove(dummy_cm.get_profile_path())
    except Exception as e:logger.exception(f"Error in RegionSelector standalone test:{e}")