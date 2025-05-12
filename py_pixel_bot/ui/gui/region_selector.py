import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict, Any

import customtkinter as ctk
from PIL import ImageGrab, ImageTk

from py_pixel_bot.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class RegionSelectorWindow(ctk.CTkToplevel):
    def __init__(self, master: Any, config_manager: ConfigManager, existing_region_data: Optional[Dict[str, Any]] = None):
        super().__init__(master)

        self.config_manager = config_manager
        self.existing_region_data = existing_region_data
        self.profile_path_for_log = config_manager.get_profile_path() if config_manager else "UnknownProfile"

        logger.info(f"Initializing RegionSelectorWindow. Master: {master}, Profile: '{self.profile_path_for_log}'")

        self.title("Region Selector - Draw a rectangle, then press 'Enter' or 'Esc'")
        
        # --- Fullscreen and Overlay Setup ---
        self.screenshot_pil: Optional[ImageGrab.Image.Image] = None
        self.bg_image_tk: Optional[ImageTk.PhotoImage] = None
        
        canvas_width, canvas_height = 0, 0

        try:
            # Capture the entire virtual desktop
            self.screenshot_pil = ImageGrab.grab(all_screens=True)
            if self.screenshot_pil:
                canvas_width, canvas_height = self.screenshot_pil.width, self.screenshot_pil.height
                self.bg_image_tk = ImageTk.PhotoImage(image=self.screenshot_pil)
                logger.debug(f"Virtual desktop screenshot captured: {canvas_width}x{canvas_height}")
                
                # Set window geometry to cover the entire virtual desktop
                self.geometry(f"{canvas_width}x{canvas_height}+0+0")
                self.overrideredirect(True) # Remove window decorations for true overlay
                self.attributes("-alpha", 0.3) # Make it semi-transparent
                self.configure(fg_color="black") # Background color for transparency effect
            else:
                raise ValueError("ImageGrab.grab(all_screens=True) returned None.")

        except Exception as e:
            logger.error(f"Failed to capture full screen or set up overlay: {e}", exc_info=True)
            # Fallback to primary screen dimensions if full capture fails
            canvas_width = self.winfo_screenwidth()
            canvas_height = self.winfo_screenheight()
            self.attributes("-fullscreen", True) # Fallback to standard fullscreen
            self.attributes("-alpha", 0.3)
            self.configure(fg_color="black")
            messagebox.showwarning("Overlay Warning",
                                   f"Could not create full virtual desktop overlay: {e}\n"
                                   "Falling back to primary screen fullscreen. Selection might be limited.",
                                   parent=self)
        # --- End Fullscreen and Overlay Setup ---


        self.start_x_abs: Optional[int] = None
        self.start_y_abs: Optional[int] = None
        self.rect_id: Optional[int] = None
        self.current_rect_coords_abs: Optional[tuple[int, int, int, int]] = None
        self.saved_region_info: Optional[Dict[str, Any]] = None
        self.changes_made: bool = False

        self.canvas = ctk.CTkCanvas(self, width=canvas_width, height=canvas_height,
                                    highlightthickness=0, bg="black") # bg ensures transparency if alpha works

        if self.bg_image_tk:
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image_tk)
            logger.debug("Screenshot set as canvas background.")
        else:
            logger.warning("No background image for RegionSelector canvas.")

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
        # Place instructions relative to the actual canvas size (which is virtual desktop size)
        self.label_instructions.place(x=canvas_width/2, y=30, anchor="n")


        self.bind("<Escape>", self.cancel_selection)
        self.bind("<Return>", self.show_confirmation_dialog_on_enter)

        if self.existing_region_data:
            self._draw_existing_rectangle()

        logger.info("RegionSelectorWindow fully initialized and displayed.")
        self.lift()
        self.focus_force()
        self.grab_set()

    def _draw_existing_rectangle(self):
        if self.existing_region_data:
            x_abs = self.existing_region_data.get("x", 0)
            y_abs = self.existing_region_data.get("y", 0)
            w = self.existing_region_data.get("width", 0)
            h = self.existing_region_data.get("height", 0)

            if w > 0 and h > 0:
                self.start_x_abs, self.start_y_abs = x_abs, y_abs
                self.current_rect_coords_abs = (x_abs, y_abs, x_abs + w, y_abs + h)

                if self.rect_id: self.canvas.delete(self.rect_id)
                self.rect_id = self.canvas.create_rectangle(
                    self.current_rect_coords_abs,
                    outline="lime green", width=3, fill="green"
                )
                logger.info(f"Drew existing rectangle for region '{self.existing_region_data.get('name')}' at screen coords {self.current_rect_coords_abs}")
                self.label_instructions.configure(text=f"Editing '{self.existing_region_data.get('name')}'. Redraw or press 'Enter', then confirm name.")
            else:
                logger.warning(f"Existing region data for '{self.existing_region_data.get('name')}' has zero width/height. Not drawing.")


    def on_mouse_press(self, event):
        self.start_x_abs = event.x_root
        self.start_y_abs = event.y_root

        if self.rect_id:
            self.canvas.delete(self.rect_id)

        self.rect_id = self.canvas.create_rectangle(
            self.start_x_abs, self.start_y_abs, self.start_x_abs, self.start_y_abs,
            outline="red", width=2, fill="red" 
        )
        logger.debug(f"Mouse pressed at screen ({self.start_x_abs}, {self.start_y_abs}). New rect ID: {self.rect_id}")
        self.label_instructions.configure(text="Dragging... Release mouse, then press 'Enter' or 'Esc'.")


    def on_mouse_drag(self, event):
        if self.start_x_abs is None or self.start_y_abs is None or self.rect_id is None:
            return
        cur_x_abs = event.x_root
        cur_y_abs = event.y_root

        self.canvas.coords(self.rect_id, self.start_x_abs, self.start_y_abs, cur_x_abs, cur_y_abs)

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
            # Change fill to green after final selection to indicate it's 'set' before confirmation
            self.canvas.itemconfig(self.rect_id, fill="green", outline="lime green", width=3)
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

        initial_alpha = self.attributes("-alpha"); self.attributes("-alpha", 0.01) # Hide overlay temporarily
        self.grab_release() # Release grab for dialog interaction

        default_name_prompt = self.existing_region_data.get("name", "NewRegion") if self.existing_region_data else "MyRegion"
        dialog_title = "Confirm Region" if not self.existing_region_data else f"Confirm Edit: {default_name_prompt}"

        dialog = ctk.CTkInputDialog(
            text=f"Enter/Confirm name for this region:\nCoords: (x={x1}, y={y1}, w={width}, h={height})\nDefault was: '{default_name_prompt}'",
            title=dialog_title
        )
        region_name_input = dialog.get_input() # This blocks until dialog is closed

        self.attributes("-alpha", initial_alpha); self.grab_set(); self.focus_force() # Restore overlay

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

        profile_data = self.config_manager.get_profile_data()
        regions = profile_data.get("regions", [])

        found_existing_and_updated = False
        if self.existing_region_data and self.existing_region_data.get("name") == name:
            for i, r_spec in enumerate(regions):
                if r_spec.get("name") == self.existing_region_data.get("name"): 
                    logger.info(f"Updating existing region '{self.existing_region_data.get('name')}' (name unchanged) at index {i}.")
                    regions[i] = new_region_data
                    found_existing_and_updated = True
                    break
        
        if not found_existing_and_updated:
            existing_idx_for_new_name = -1
            original_name_if_editing = self.existing_region_data.get("name") if self.existing_region_data else None

            for i, r_spec in enumerate(regions):
                 if r_spec.get("name") == name: # Found a region with the target name
                    if original_name_if_editing and original_name_if_editing == name:
                        # This is the case where we are editing, and the name hasn't changed.
                        # It should have been caught by the `found_existing_and_updated` block above.
                        # This path implies something is off or it's a new region colliding.
                        pass
                    elif original_name_if_editing and original_name_if_editing != name:
                        # Editing, but name changed to collide with *another* existing region.
                        if messagebox.askyesno("Name Conflict", f"A region named '{name}' already exists. Overwrite the other region?", parent=self):
                            existing_idx_for_new_name = i
                        else:
                            logger.info(f"User chose not to overwrite existing region named '{name}'. Save cancelled.")
                            return 
                        break
                    elif not original_name_if_editing: # Adding new, but name collides.
                         if messagebox.askyesno("Name Conflict", f"A region named '{name}' already exists. Overwrite it?", parent=self):
                            existing_idx_for_new_name = i
                         else:
                            logger.info(f"User chose not to overwrite existing region named '{name}'. Save cancelled.")
                            return
                         break

            if existing_idx_for_new_name != -1: # Overwrite or update (if name changed to existing)
                logger.info(f"Region with name '{name}' will be updated/overwritten at index {existing_idx_for_new_name}.")
                regions[existing_idx_for_new_name] = new_region_data
            elif original_name_if_editing and not found_existing_and_updated: 
                # Editing, name changed, and no collision with *another* region. Find original slot.
                updated_original = False
                for i, r_spec in enumerate(regions):
                    if r_spec.get("name") == original_name_if_editing:
                        logger.info(f"Updating original region '{original_name_if_editing}' with new name '{name}' and data at index {i}.")
                        regions[i] = new_region_data
                        updated_original = True
                        break
                if not updated_original: # Should not happen if existing_region_data was valid
                    logger.error(f"Could not find original region '{original_name_if_editing}' to update. Appending as new.")
                    regions.append(new_region_data)
            else: # Truly a new region name, not an edit or collision overwrite.
                logger.info(f"Adding new region '{name}'.")
                regions.append(new_region_data)

        profile_data["regions"] = regions

        try:
            self.config_manager.save_current_profile()
            self.saved_region_info = new_region_data
            self.changes_made = True
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
        logger.debug("RegionSelectorWindow destroy called.")
        self.grab_release()
        super().destroy()