import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict, Any

import customtkinter as ctk
from PIL import ImageGrab, ImageTk, Image, ImageDraw # Added ImageDraw for drawing existing rect

# Assuming ConfigManager might be passed for context or saving path hint,
# but it should not directly save to the main app's profile during selection.
from mark_i.core.config_manager import ConfigManager

# Standardized logger
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.region_selector")

# Default values for region if creating a new one without specific initial coords
DEFAULT_NEW_REGION_X = 50
DEFAULT_NEW_REGION_Y = 50
DEFAULT_NEW_REGION_WIDTH = 200
DEFAULT_NEW_REGION_HEIGHT = 150


class RegionSelectorWindow(ctk.CTkToplevel):
    """
    A Toplevel window that overlays the screen (or a provided image) to allow
    the user to visually select a rectangular region by clicking and dragging.
    It prompts for a region name upon confirmation.

    If `existing_region_data` is provided, it pre-draws that region and allows adjustment.
    If `direct_image_input_pil` is provided, it uses that image as the canvas instead
    of taking a new full-screen screenshot. Coordinates returned are relative to this image.
    Otherwise, it takes a full virtual screen screenshot to draw upon, and coordinates
    are absolute screen coordinates.
    """
    def __init__(self, master: Any,
                 config_manager_for_saving_path_only: ConfigManager, # Used for default save path hints if ever needed by a caller
                 existing_region_data: Optional[Dict[str, Any]] = None,
                 direct_image_input_pil: Optional[Image.Image] = None): # New param for v5 wizard
        super().__init__(master)

        self.transient(master) # Stay on top of master
        self.grab_set()        # Make modal
        self.attributes("-topmost", True) # Ensure it's on top of everything

        self.config_manager_context = config_manager_for_saving_path_only # Store for context if needed
        self.original_existing_region_data = copy.deepcopy(existing_region_data) if existing_region_data else None
        self.is_editing_existing = bool(self.original_existing_region_data)
        
        edit_name_hint = self.original_existing_region_data.get("name", "") if self.is_editing_existing else ""
        self.title(f"Region Selector - {'Edit: ' + edit_name_hint if self.is_editing_existing else 'Add New Region'}")

        self.image_source_pil: Optional[Image.Image] = None # The PIL image being drawn upon
        self.image_source_tk: Optional[ImageTk.PhotoImage] = None # Tkinter-compatible version for canvas

        self.canvas_display_width: int = 0
        self.canvas_display_height: int = 0
        self.image_display_scale_factor: float = 1.0 # Scale factor if image is resized for display

        self.current_selection_rect_id: Optional[int] = None # ID of the rectangle on canvas
        # Coordinates of the selection relative to the *image_source_pil*
        self.selected_coords_on_image: Optional[Tuple[int, int, int, int]] = None # (x1, y1, x2, y2)
        
        # Final result to be retrieved by caller
        self.saved_region_info: Optional[Dict[str, Any]] = None # Format: {"name": str, "x": int, "y": int, "width": int, "height": int}
        self.changes_made: bool = False # True if user confirms a selection

        self._setup_canvas_and_image(direct_image_input_pil) # Setup canvas with image
        self._setup_controls_and_bindings()       # Setup drawing bindings and confirm/cancel buttons

        if self.is_editing_existing and self.original_existing_region_data:
            self._pre_draw_existing_region()
        
        logger.info(f"RegionSelectorWindow initialized. Editing: {self.is_editing_existing}. Source: {'Provided Image' if direct_image_input_pil else 'Live Screen'}.")
        self.after(100, self._center_on_master_screen) # Center after initial rendering
        self.focus_force()


    def _setup_canvas_and_image(self, direct_image_input_pil: Optional[Image.Image]):
        """Captures screen or uses provided image, then sets up the canvas."""
        screen_interaction_alpha = 0.25 # Alpha for live screen interaction
        image_display_alpha = 1.0    # Full alpha if displaying a provided image

        if direct_image_input_pil:
            logger.debug("RegionSelector: Using direct PIL image input.")
            self.image_source_pil = direct_image_input_pil.copy() # Use a copy
            self.attributes("-alpha", image_display_alpha)
            self.configure(fg_color="systemशंकरBackground") # Normal window bg
        else: # Capture live screen
            logger.debug("RegionSelector: Capturing live screen for selection.")
            try:
                self.attributes("-alpha", 0.0) # Hide self before capture
                self.lower()
                self.update_idletasks()
                time.sleep(0.15) # Short delay for window manager
                self.image_source_pil = ImageGrab.grab(all_screens=True)
                self.attributes("-alpha", screen_interaction_alpha) # Semi-transparent overlay
                self.configure(fg_color="black") # Darken background for overlay feel
                self.lift()
            except Exception as e:
                logger.error(f"RegionSelector: Failed to capture full screen: {e}", exc_info=True)
                # Fallback: destroy self and show error on master
                messagebox.showerror("Screen Capture Error", f"Could not capture screen: {e}\nRegion selection cannot proceed.", parent=self.master)
                self.destroy_selector_immediately(); return

        if not self.image_source_pil:
            logger.error("RegionSelector: Image source is None after capture/input. Cannot proceed.")
            messagebox.showerror("Image Error", "Could not obtain image for region selection.", parent=self.master)
            self.destroy_selector_immediately(); return

        # Determine canvas size and image scaling for display
        img_orig_w, img_orig_h = self.image_source_pil.size
        
        # Maximize window but leave some space for OS chrome if not overrideredirect
        # If overrideredirect is True (for screen capture mode), window can be screen size.
        if direct_image_input_pil:
            # For provided image, fit within a max sensible size, keeping aspect ratio
            max_display_w, max_display_h = min(img_orig_w, self.winfo_screenwidth() - 100), min(img_orig_h, self.winfo_screenheight() - 150)
            self.overrideredirect(False) # Normal window for provided image
            self.geometry("") # Reset geometry to allow natural sizing by content
        else: # Live screen capture, use full virtual screen size
            max_display_w, max_display_h = img_orig_w, img_orig_h
            self.overrideredirect(True) # Full overlay for screen capture
            self.geometry(f"{img_orig_w}x{img_orig_h}+0+0")

        if img_orig_w > max_display_w or img_orig_h > max_display_h:
            self.image_display_scale_factor = min(max_display_w / img_orig_w, max_display_h / img_orig_h)
            self.canvas_display_width = int(img_orig_w * self.image_display_scale_factor)
            self.canvas_display_height = int(img_orig_h * self.image_display_scale_factor)
            img_for_canvas_pil = self.image_source_pil.resize((self.canvas_display_width, self.canvas_display_height), Image.Resampling.LANCZOS)
        else:
            self.image_display_scale_factor = 1.0
            self.canvas_display_width = img_orig_w
            self.canvas_display_height = img_orig_h
            img_for_canvas_pil = self.image_source_pil
        
        self.image_source_tk = ImageTk.PhotoImage(img_for_canvas_pil)

        self.canvas = ctk.CTkCanvas(self, width=self.canvas_display_width, height=self.canvas_display_height,
                                    highlightthickness=0, borderwidth=0)
        self.canvas.create_image(0, 0, anchor="nw", image=self.image_source_tk)
        self.canvas.pack(side="top", fill="both", expand=True)


    def _setup_controls_and_bindings(self):
        """Sets up mouse bindings for drawing and control buttons."""
        if not hasattr(self, 'canvas') or not self.canvas: # Canvas setup failed
            return

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.bind("<Escape>", self._cancel_selection) # Bind Esc to window
        self.bind("<Return>", self._trigger_confirmation_dialog) # Bind Enter to window

        # Instruction Label (placed on top of canvas using .place or in a separate frame)
        instruction_text = "Click & Drag to draw selection. Press 'Enter' to Confirm, 'Esc' to Cancel."
        if self.is_editing_existing and self.original_existing_region_data:
            instruction_text = f"Editing '{self.original_existing_region_data.get('name')}'. Redraw or press 'Enter' to use current coords, then confirm name."
        
        self.instruction_label = ctk.CTkLabel(self, text=instruction_text, font=ctk.CTkFont(size=14, weight="bold"),
                                              fg_color=("#DBDBDB", "#2B2B2B"), text_color=("#101010", "#DCE4EE"),
                                              corner_radius=6, padx=8, pady=4)
        # Place label at top-center of the canvas area
        self.instruction_label.place(in_=self.canvas, relx=0.5, y=20, anchor="n")


        # Controls frame (Confirm/Cancel buttons) for direct_image_input_pil mode
        if self.image_source_pil and self.overrideredirect() is False: # If it's a normal window (not overlay)
            controls_frame = ctk.CTkFrame(self, fg_color="transparent")
            controls_frame.pack(side="bottom", fill="x", pady=10, padx=10)
            controls_frame.grid_columnconfigure(0, weight=1) # Spacer
            controls_frame.grid_columnconfigure(3, weight=1) # Spacer

            self.btn_confirm_selection = ctk.CTkButton(controls_frame, text="Confirm Selection", command=self._trigger_confirmation_dialog, state="disabled")
            self.btn_confirm_selection.grid(row=0, column=2, padx=5)
            
            ctk.CTkButton(controls_frame, text="Cancel", command=self._cancel_selection).grid(row=0, column=1, padx=5)
        else: # For overlay mode, confirm is via Enter key, cancel via Esc
            self.btn_confirm_selection = None # No visible button


    def _center_on_master_screen(self): # No change
        self.update_idletasks()
        if self.master and self.master.winfo_exists():
            master_x, master_y, master_w, master_h = self.master.winfo_x(), self.master.winfo_y(), self.master.winfo_width(), self.master.winfo_height()
            win_w, win_h = self.winfo_width(), self.winfo_height()
            x = master_x + (master_w // 2) - (win_w // 2)
            y = master_y + (master_h // 2) - (win_h // 2)
            self.geometry(f"{win_w}x{win_h}+{max(0,x)}+{max(0,y)}")
        else: # Fallback if master not available (e.g. testing standalone)
            self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        self.lift()

    def _pre_draw_existing_region(self):
        """If editing, draws the existing region's rectangle on the canvas."""
        if not self.original_existing_region_data or not self.image_source_pil: return

        # Coords are relative to the image_source_pil
        x_orig = self.original_existing_region_data.get("x", 0)
        y_orig = self.original_existing_region_data.get("y", 0)
        w_orig = self.original_existing_region_data.get("width", DEFAULT_NEW_REGION_WIDTH)
        h_orig = self.original_existing_region_data.get("height", DEFAULT_NEW_REGION_HEIGHT)

        if w_orig <= 0 or h_orig <= 0:
            logger.warning(f"Pre-draw: Existing region '{self.original_existing_region_data.get('name')}' has non-positive dimensions. Not drawing."); return

        # Scale these original image coordinates to canvas display coordinates
        x1_canvas = int(round(x_orig * self.image_display_scale_factor))
        y1_canvas = int(round(y_orig * self.image_display_scale_factor))
        x2_canvas = int(round((x_orig + w_orig) * self.image_display_scale_factor))
        y2_canvas = int(round((y_orig + h_orig) * self.image_display_scale_factor))
        
        # Clamp to canvas boundaries for safety if image was larger than canvas
        x1_canvas = max(0, x1_canvas); y1_canvas = max(0, y1_canvas)
        x2_canvas = min(self.canvas_display_width, x2_canvas); y2_canvas = min(self.canvas_display_height, y2_canvas)


        if self.current_selection_rect_id: self.canvas.delete(self.current_selection_rect_id)
        self.current_selection_rect_id = self.canvas.create_rectangle(
            x1_canvas, y1_canvas, x2_canvas, y2_canvas,
            outline="lime green", width=3, fill="green", stipple="gray25" # Use a distinct fill for existing
        )
        # Store the original image coordinates of this pre-drawn selection
        self.selected_coords_on_image = (x_orig, y_orig, x_orig + w_orig, y_orig + h_orig)
        if self.btn_confirm_selection: self.btn_confirm_selection.configure(state="normal")
        logger.info(f"RegionSelector: Pre-drew existing region '{self.original_existing_region_data.get('name')}' at canvas coords ({x1_canvas},{y1_canvas})-({x2_canvas},{y2_canvas}). Original image coords: {self.selected_coords_on_image}")


    def _on_mouse_press(self, event): # Unchanged
        self.start_x_canvas, self.start_y_canvas = event.x, event.y
        if self.current_selection_rect_id: self.canvas.delete(self.current_selection_rect_id)
        self.current_selection_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)
        if self.btn_confirm_selection: self.btn_confirm_selection.configure(state="disabled")
        self.instruction_label.configure(text="Dragging... Release mouse to finalize selection.")

    def _on_mouse_drag(self, event): # Unchanged
        if self.start_x_canvas is None or self.current_selection_rect_id is None: return
        self.canvas.coords(self.current_selection_rect_id, self.start_x_canvas, self.start_y_canvas, event.x, event.y)

    def _on_mouse_release(self, event): # Unchanged from previous SubImageSelector version
        if self.start_x_canvas is None or self.current_selection_rect_id is None: return
        x1_c = max(0, min(self.start_x_canvas, event.x)); y1_c = max(0, min(self.start_y_canvas, event.y))
        x2_c = min(self.canvas_display_width, max(self.start_x_canvas, event.x)); y2_c = min(self.canvas_display_height, max(self.start_y_canvas, event.y))
        w_c, h_c = x2_c - x1_c, y2_c - y1_c

        if w_c > 0 and h_c > 0:
            self.canvas.coords(self.current_selection_rect_id, x1_c, y1_c, x2_c, y2_c); self.canvas.itemconfig(self.current_selection_rect_id, outline="lime green", width=3)
            # Convert canvas coords to original image coords using scale factor
            orig_x1 = int(round(x1_c / self.image_display_scale_factor)); orig_y1 = int(round(y1_c / self.image_display_scale_factor))
            orig_x2 = int(round(x2_c / self.image_display_scale_factor)); orig_y2 = int(round(y2_c / self.image_display_scale_factor))
            # Ensure coords are within original image bounds
            img_w_orig, img_h_orig = self.image_source_pil.size
            orig_x1 = max(0, orig_x1); orig_y1 = max(0, orig_y1)
            orig_x2 = min(img_w_orig, orig_x2); orig_y2 = min(img_h_orig, orig_y2)
            if (orig_x2 - orig_x1) > 0 and (orig_y2 - orig_y1) > 0:
                self.selected_coords_on_image = (orig_x1, orig_y1, orig_x2, orig_y2) # Store as (x1,y1,x2,y2) on original image
                if self.btn_confirm_selection: self.btn_confirm_selection.configure(state="normal")
                self.instruction_label.configure(text=f"Selection: ({orig_x1},{orig_y1}) to ({orig_x2},{orig_y2}) on original. Press Enter or Confirm.")
            else: self.selected_coords_on_image = None; if self.btn_confirm_selection: self.btn_confirm_selection.configure(state="disabled"); self.instruction_label.configure(text="Invalid selection (zero area on original). Redraw.")
        else: self.selected_coords_on_image = None; if self.btn_confirm_selection: self.btn_confirm_selection.configure(state="disabled"); self.instruction_label.configure(text="Invalid selection (zero area on canvas). Redraw.")
        if self.selected_coords_on_image is None and self.current_selection_rect_id: self.canvas.delete(self.current_selection_rect_id); self.current_selection_rect_id = None

    def _trigger_confirmation_dialog(self, event=None): # Renamed from show_confirmation_dialog_on_enter
        if not self.selected_coords_on_image:
            messagebox.showwarning("No Region Selected", "Please draw or confirm a rectangular selection on the screen/image first.", parent=self); return

        x1, y1, x2, y2 = self.selected_coords_on_image # These are on original image
        sel_w, sel_h = x2 - x1, y2 - y1
        if sel_w <= 0 or sel_h <= 0: messagebox.showerror("Invalid Selection", "Selected region has zero width or height. Please redraw.", parent=self); return

        # Temporarily hide/lower overlay for dialog visibility if it's an overrideredirect window
        initial_alpha = self.attributes("-alpha")
        was_topmost = self.attributes("-topmost")
        if self.overrideredirect(): self.attributes("-alpha", 0.0); self.lower()
        self.attributes("-topmost", False) # Allow dialog to be on top

        default_name = f"Region_{len(self.config_manager_context.get_regions()) + 1}" # Default name suggestion
        if self.is_editing_existing and self.original_existing_region_data:
            default_name = self.original_existing_region_data.get("name", default_name)
        
        dialog = ctk.CTkInputDialog(
            text=f"Enter a unique name for this region:\nCoords (on original): x={x1}, y={y1}, w={sel_w}, h={sel_h}\n(Current name hint: '{default_name}')",
            title="Confirm Region Name"
        )
        input_name = dialog.get_input() # This blocks until dialog is closed

        # Restore selector window state
        if self.overrideredirect(): self.attributes("-alpha", initial_alpha)
        self.attributes("-topmost", was_topmost) # Restore topmost status
        self.lift(); self.focus_force() # Bring back to focus

        if input_name and input_name.strip():
            final_name = input_name.strip()
            # Check for name conflict within the ConfigManager's *current* profile data
            # This is tricky if this selector is used by AI Profile Creator on an in-memory draft.
            # The caller (e.g., AI Profile Creator Wizard) should handle name conflicts with its *draft*.
            # For now, this selector itself won't check against a live profile if it's just returning coords.
            # However, if it *were* to save directly (original design), conflict check is needed.
            # For now, we just store it and let the caller validate name uniqueness.
            
            self.saved_region_info = {"name": final_name, "x": x1, "y": y1, "width": sel_w, "height": sel_h}
            self.changes_made = True
            logger.info(f"RegionSelector: User confirmed region '{final_name}' with coords {self.saved_region_info} (relative to source image).")
            self.destroy_selector_immediately() # Close after successful naming
        else:
            logger.info("RegionSelector: Name input cancelled or empty. Selection remains on canvas.")
            self.instruction_label.configure(text=f"Naming cancelled. Selection active. Press Enter or Confirm.")
            if self.btn_confirm_selection: self.btn_confirm_selection.configure(state="normal") # Re-enable confirm

    def _cancel_selection(self, event=None): # Unchanged
        logger.info("RegionSelector: User cancelled selection via Esc or Cancel button.")
        self.saved_region_info = None; self.changes_made = False
        self.destroy_selector_immediately()

    def destroy_selector_immediately(self): # Renamed for clarity
        logger.debug("RegionSelectorWindow: Destroying self.")
        self.grab_release() # Release grab before destroying
        self.destroy()

    def get_selected_region_info(self) -> Optional[Dict[str, Any]]:
        """Called by the parent window after this Toplevel closes to get the result."""
        return self.saved_region_info if self.changes_made else None