import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict, Any
import copy # Added for deepcopy

import customtkinter as ctk
from PIL import ImageGrab, ImageTk

from py_pixel_bot.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class RegionSelectorWindow(ctk.CTkToplevel):
    def __init__(self, master: Any, config_manager: ConfigManager, existing_region_data: Optional[Dict[str, Any]] = None):
        super().__init__(master)

        self.config_manager = config_manager
        # Store a deep copy of the original data if editing, to know the original name
        self.original_existing_region_data = copy.deepcopy(existing_region_data) if existing_region_data else None
        
        self.profile_path_for_log = config_manager.get_profile_path() if config_manager else "UnknownProfile"

        logger.info(f"Initializing RegionSelectorWindow. Master: {master}, Profile: '{self.profile_path_for_log}'")
        is_editing = bool(self.original_existing_region_data)
        edit_name = self.original_existing_region_data.get("name", "") if is_editing else ""

        self.title(f"Region Selector - {'Edit Region: ' + edit_name if is_editing else 'Add New Region'}")
        
        self.screenshot_pil: Optional[ImageGrab.Image.Image] = None
        self.bg_image_tk: Optional[ImageTk.PhotoImage] = None

        canvas_width, canvas_height = 0, 0

        try:
            self.screenshot_pil = ImageGrab.grab(all_screens=True)
            if self.screenshot_pil:
                canvas_width, canvas_height = self.screenshot_pil.width, self.screenshot_pil.height
                logger.debug(f"Virtual desktop screenshot captured: {canvas_width}x{canvas_height}")
                
                self.geometry(f"{canvas_width}x{canvas_height}+0+0")
                self.overrideredirect(True) 
                self.attributes("-alpha", 0.3) 
                self.configure(fg_color="black")
            else:
                raise ValueError("ImageGrab.grab(all_screens=True) returned None.")

        except Exception as e:
            logger.error(f"Failed to capture full screen or set up overlay: {e}", exc_info=True)
            canvas_width = self.winfo_screenwidth()
            canvas_height = self.winfo_screenheight()
            self.attributes("-fullscreen", True) 
            self.attributes("-alpha", 0.3)
            self.configure(fg_color="black")
            # Ensure messagebox has a proper parent if self (Toplevel) is not fully ready.
            # However, by this point, self should be a valid Toplevel.
            messagebox.showwarning("Overlay Warning",
                                   f"Could not create full virtual desktop overlay: {e}\n"
                                   "Falling back to primary screen fullscreen. Selection might be limited.",
                                   parent=self if self.winfo_exists() else master) 

        self.start_x_abs: Optional[int] = None
        self.start_y_abs: Optional[int] = None
        self.rect_id: Optional[int] = None
        self.current_rect_coords_abs: Optional[tuple[int, int, int, int]] = None
        self.saved_region_info: Optional[Dict[str, Any]] = None 
        self.changes_made: bool = False

        self.canvas = tk.Canvas(self, width=canvas_width, height=canvas_height,
                                    highlightthickness=0, bg="black") 

        if self.screenshot_pil: 
            self.bg_image_tk = ImageTk.PhotoImage(image=self.screenshot_pil)
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image_tk)
            logger.debug("Screenshot set as tk.Canvas background.")
        else:
            logger.warning("No background image for RegionSelector canvas.")

        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        instruction_text = "Click & Drag to draw. Release. Press 'Enter' to Confirm, 'Esc' to Cancel."
        if is_editing:
            instruction_text = f"Editing '{edit_name}'. Redraw or press 'Enter' to keep coords, then confirm name."

        self.label_instructions = ctk.CTkLabel(
            self, text=instruction_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=("gray10", "gray90"), text_color=("white", "black"), corner_radius=5, padx=10, pady=5
        )
        self.label_instructions.place(relx=0.5, y=30, anchor="n")


        self.bind("<Escape>", self.cancel_selection)
        self.bind("<Return>", self.show_confirmation_dialog_on_enter)

        if self.original_existing_region_data:
            self._draw_existing_rectangle()

        logger.info("RegionSelectorWindow fully initialized and displayed.")
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True) 
        self.grab_set() # Makes the window modal

    def _draw_existing_rectangle(self):
        if self.original_existing_region_data:
            x_abs = self.original_existing_region_data.get("x", 0)
            y_abs = self.original_existing_region_data.get("y", 0)
            w = self.original_existing_region_data.get("width", 0)
            h = self.original_existing_region_data.get("height", 0)

            if w > 0 and h > 0:
                self.start_x_abs, self.start_y_abs = x_abs, y_abs 
                self.current_rect_coords_abs = (x_abs, y_abs, x_abs + w, y_abs + h)

                if self.rect_id: self.canvas.delete(self.rect_id)
                self.rect_id = self.canvas.create_rectangle(
                    self.current_rect_coords_abs,
                    outline="lime green", width=3, fill="green", stipple="gray50"
                )
                logger.info(f"Drew existing rectangle for region '{self.original_existing_region_data.get('name')}' at screen coords {self.current_rect_coords_abs}")
                if self.label_instructions:
                    self.label_instructions.configure(text=f"Editing '{self.original_existing_region_data.get('name')}'. Redraw or press 'Enter', then confirm name.")
            else:
                logger.warning(f"Existing region data for '{self.original_existing_region_data.get('name')}' has zero width/height. Not drawing.")


    def on_mouse_press(self, event):
        self.start_x_abs = event.x 
        self.start_y_abs = event.y

        if self.rect_id:
            self.canvas.delete(self.rect_id)

        self.rect_id = self.canvas.create_rectangle(
            self.start_x_abs, self.start_y_abs, self.start_x_abs, self.start_y_abs,
            outline="red", width=2 
        )
        logger.debug(f"Mouse pressed at canvas-relative ({event.x}, {event.y}). New rect ID: {self.rect_id}")
        if self.label_instructions: self.label_instructions.configure(text="Dragging... Release mouse, then press 'Enter' or 'Esc'.")


    def on_mouse_drag(self, event):
        if self.start_x_abs is None or self.start_y_abs is None or self.rect_id is None:
            return
        cur_x_abs = event.x 
        cur_y_abs = event.y

        self.canvas.coords(self.rect_id, self.start_x_abs, self.start_y_abs, cur_x_abs, cur_y_abs)

    def on_mouse_release(self, event):
        if self.start_x_abs is None or self.start_y_abs is None or self.rect_id is None:
            logger.warning("Mouse released but selection start/rect_id is None.")
            return

        end_x_abs = event.x 
        end_y_abs = event.y

        x1 = min(self.start_x_abs, end_x_abs)
        y1 = min(self.start_y_abs, end_y_abs)
        x2 = max(self.start_x_abs, end_x_abs)
        y2 = max(self.start_y_abs, end_y_abs)

        if (x2 - x1) > 0 and (y2 - y1) > 0:
            self.current_rect_coords_abs = (int(x1), int(y1), int(x2), int(y2))
            logger.info(f"Mouse released. Finalized rectangle at screen coordinates (x1,y1,x2,y2): {self.current_rect_coords_abs}")
            self.canvas.itemconfig(self.rect_id, outline="lime green", width=3, fill="green", stipple="gray50")
            if self.label_instructions: self.label_instructions.configure(text="Rectangle drawn. Press 'Enter' to confirm name, 'Esc' to cancel/redraw.")
        else:
            logger.warning(f"Mouse released, but drawn rectangle has no area. Coords: ({x1},{y1},{x2},{y2}). Resetting.")
            if self.rect_id: self.canvas.delete(self.rect_id)
            self.rect_id = None; self.current_rect_coords_abs = None
            if self.label_instructions: self.label_instructions.configure(text="Invalid rectangle (zero area). Click and drag again.")


    def show_confirmation_dialog_on_enter(self, event=None):
        if self.current_rect_coords_abs:
            logger.debug("Enter pressed with valid current_rect_coords_abs. Showing confirmation dialog.")
            self._show_name_and_confirm_dialog()
        else:
            logger.info("Enter pressed, but no valid rectangle drawn/selected yet.")
            if self.label_instructions: self.label_instructions.configure(text="No rectangle selected. Click and drag first, then press Enter.")


    def _show_name_and_confirm_dialog(self):
        if not self.current_rect_coords_abs:
            logger.warning("Confirmation dialog attempt, but no rectangle selected.")
            messagebox.showwarning("No Region", "Please draw or confirm a rectangle first.", parent=self)
            return

        x1, y1, x2, y2 = self.current_rect_coords_abs
        width = x2 - x1
        height = y2 - y1

        if width <= 0 or height <= 0:
            logger.error(f"Invalid rect dimensions before confirm: W={width}, H={height}")
            messagebox.showerror("Error", "Invalid rectangle dimensions. Please redraw.", parent=self)
            return

        initial_alpha = self.attributes("-alpha")
        self.attributes("-alpha", 0.0) 
        self.lower() 
        self.attributes("-topmost", False) # Ensure dialog can be on top

        default_name_prompt = self.original_existing_region_data.get("name", f"Region_{len(self.config_manager.get_regions()) + 1}") if self.original_existing_region_data else f"Region_{len(self.config_manager.get_regions()) + 1}"
        dialog_title = "Confirm Region Name"

        dialog = ctk.CTkInputDialog(
            text=f"Enter name for region:\nCoords: (x={x1}, y={y1}, w={width}, h={height})\nDefault: '{default_name_prompt}'",
            title=dialog_title
        )
        
        region_name_input = dialog.get_input() 
        
        self.attributes("-alpha", initial_alpha)
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)


        if region_name_input and region_name_input.strip():
            region_name_final = region_name_input.strip()
            logger.info(f"Region named '{region_name_final}' with Coords (x={x1}, y={y1}, w={width}, h={height}) confirmed by user.")
            self.save_region_to_profile(region_name_final, x1, y1, width, height)
            self.destroy_selector() 
        else:
            logger.info("Region name input cancelled or empty. Rectangle selection remains available.")
            if self.label_instructions: self.label_instructions.configure(text="Naming cancelled. Rectangle drawn. Press 'Enter' to name again, or 'Esc'.")

    def save_region_to_profile(self, name: str, x: int, y: int, width: int, height: int):
        new_region_data = {"name": name, "x": x, "y": y, "width": width, "height": height}
        logger.info(f"Preparing to save/update region: {new_region_data} to profile: '{self.profile_path_for_log}'")

        profile_data = self.config_manager.get_profile_data()
        regions: List[Dict[str, Any]] = profile_data.get("regions", [])
        
        original_name_if_editing = self.original_existing_region_data.get("name") if self.original_existing_region_data else None
        
        # Temporarily make window non-topmost for messagebox
        was_topmost = self.attributes("-topmost")
        self.attributes("-topmost", False)

        # Scenario 1: Editing an existing region
        if original_name_if_editing:
            found_original_slot_idx = -1
            for i, r_spec in enumerate(regions):
                if r_spec.get("name") == original_name_if_editing:
                    found_original_slot_idx = i
                    break
            
            if name != original_name_if_editing: # Name has changed
                # Check if the new name conflicts with another existing region
                conflict_idx = -1
                for i, r_spec in enumerate(regions):
                    if r_spec.get("name") == name: # New name conflicts
                        conflict_idx = i
                        break
                if conflict_idx != -1 and conflict_idx != found_original_slot_idx : # Conflict with a DIFFERENT region
                    if not messagebox.askyesno("Name Conflict", f"A region named '{name}' already exists. Overwrite it?", parent=self):
                        logger.info(f"User chose not to overwrite existing region named '{name}'. Save cancelled.")
                        self.attributes("-topmost", was_topmost)
                        return
                    else: # User chose to overwrite the OTHER region
                        logger.info(f"User chose to overwrite region at index {conflict_idx} (name '{name}') with data for original '{original_name_if_editing}'. The original slot of '{original_name_if_editing}' will effectively be deleted if it's not this conflicting one.")
                        regions.pop(conflict_idx)
                        # Re-check found_original_slot_idx if it was after the popped one
                        if found_original_slot_idx != -1 and found_original_slot_idx > conflict_idx:
                            found_original_slot_idx -=1
            
            if found_original_slot_idx != -1: # Update the original region's data (name might have changed)
                 logger.info(f"Updating region at index {found_original_slot_idx} (original name: '{original_name_if_editing}') with new data: {new_region_data}")
                 regions[found_original_slot_idx] = new_region_data
            else: # Original region not found (e.g., deleted/renamed elsewhere - unlikely but defensive)
                 logger.warning(f"Original region '{original_name_if_editing}' not found for update. Appending as new region '{name}'.")
                 regions.append(new_region_data)

        # Scenario 2: Adding a new region
        else:
            conflict_idx = -1
            for i, r_spec in enumerate(regions):
                if r_spec.get("name") == name:
                    conflict_idx = i
                    break
            if conflict_idx != -1: # New region's name conflicts
                if not messagebox.askyesno("Name Conflict", f"A region named '{name}' already exists. Overwrite it?", parent=self):
                    logger.info(f"User chose not to overwrite existing region named '{name}'. Save cancelled.")
                    self.attributes("-topmost", was_topmost)
                    return
                else: # User chose to overwrite
                    logger.info(f"Overwriting existing region '{name}' at index {conflict_idx} with new data.")
                    regions[conflict_idx] = new_region_data
            else: # No conflict, just append
                logger.info(f"Adding new region '{name}'.")
                regions.append(new_region_data)
        
        self.attributes("-topmost", was_topmost) # Restore topmost

        profile_data["regions"] = regions
        self.config_manager.profile_data = profile_data 

        try:
            self.config_manager.save_current_profile() 
            self.saved_region_info = new_region_data 
            self.changes_made = True
            logger.info(f"Region '{name}' (coords: x={x},y={y},w={width},h={height}) saved successfully to profile '{self.profile_path_for_log}'.")
        except Exception as e:
            logger.error(f"Failed to save profile after updating region '{name}': {e}", exc_info=True)
            self.attributes("-topmost", False)
            messagebox.showerror("Save Error", f"Could not save region '{name}'.\nError: {e}", parent=self)
            self.attributes("-topmost", was_topmost)
            self.saved_region_info = None 
            self.changes_made = False


    def cancel_selection(self, event=None):
        logger.info("Region selection cancelled by user.")
        self.saved_region_info = None 
        self.changes_made = False
        self.destroy_selector()

    def destroy_selector(self):
        logger.debug("RegionSelectorWindow destroy_selector called.")
        self.grab_release() 
        super().destroy()