import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict, Any, Tuple  # Added Tuple
import time  # For short delay before screen capture
import copy  # For deepcopy

import customtkinter as ctk
from PIL import ImageGrab, ImageTk, Image, ImageDraw

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

    def __init__(self, master: Any, config_manager_for_saving_path_only: ConfigManager, existing_region_data: Optional[Dict[str, Any]] = None, direct_image_input_pil: Optional[Image.Image] = None):
        super().__init__(master)

        self.transient(master)
        self.grab_set()
        self.attributes("-topmost", True)

        self.config_manager_context = config_manager_for_saving_path_only
        self.original_existing_region_data = copy.deepcopy(existing_region_data) if existing_region_data else None
        self.is_editing_existing = bool(self.original_existing_region_data)

        edit_name_hint = self.original_existing_region_data.get("name", "") if self.is_editing_existing else ""
        self.title(f"Region Selector - {'Edit: ' + edit_name_hint if self.is_editing_existing else 'Add New Region'}")

        self.image_source_pil: Optional[Image.Image] = None
        self.image_source_tk: Optional[ImageTk.PhotoImage] = None

        self.canvas_display_width: int = 0
        self.canvas_display_height: int = 0
        self.image_display_scale_factor: float = 1.0

        self.current_selection_rect_id: Optional[int] = None
        # Store canvas coordinates for drawing logic
        self.start_x_canvas: Optional[int] = None
        self.start_y_canvas: Optional[int] = None

        # Coordinates of the selection relative to the *image_source_pil* (x1, y1, x2, y2)
        self.selected_coords_on_image: Optional[Tuple[int, int, int, int]] = None

        self.saved_region_info: Optional[Dict[str, Any]] = None
        self.changes_made: bool = False

        self._setup_canvas_and_image(direct_image_input_pil)
        if hasattr(self, "canvas") and self.canvas:  # Proceed only if canvas setup was successful
            self._setup_controls_and_bindings()
            if self.is_editing_existing and self.original_existing_region_data:
                self._pre_draw_existing_region()

        logger.info(f"RegionSelectorWindow initialized. Editing: {self.is_editing_existing}. Source: {'Provided Image' if direct_image_input_pil else 'Live Screen'}.")
        self.after(100, self._center_on_master_screen)
        self.focus_force()

    def _setup_canvas_and_image(self, direct_image_input_pil: Optional[Image.Image]):
        screen_interaction_alpha = 0.25
        image_display_alpha = 1.0

        if direct_image_input_pil:
            logger.debug("RegionSelector: Using direct PIL image input.")
            self.image_source_pil = direct_image_input_pil.copy()
            self.attributes("-alpha", image_display_alpha)
            # Use system theme background for a normal window feel
            # self.configure(fg_color=ctk.ThemeManager.theme["CTkFrame"]["fg_color"]) # This might not be directly accessible or ideal
            self.configure(fg_color=self._get_appearance_mode_fg_color())  # Try to get a theme-aware color
        else:
            logger.debug("RegionSelector: Capturing live screen for selection.")
            try:
                self.attributes("-alpha", 0.0)
                self.lower()
                self.update_idletasks()
                time.sleep(0.15)
                self.image_source_pil = ImageGrab.grab(all_screens=True)
                self.attributes("-alpha", screen_interaction_alpha)
                self.configure(fg_color="black")
                self.lift()
            except Exception as e:
                logger.error(f"RegionSelector: Failed to capture full screen: {e}", exc_info=True)
                messagebox.showerror("Screen Capture Error", f"Could not capture screen: {e}\nRegion selection cannot proceed.", parent=self.master)
                self.destroy_selector_immediately()
                return

        if not self.image_source_pil:
            logger.error("RegionSelector: Image source is None after capture/input. Cannot proceed.")
            messagebox.showerror("Image Error", "Could not obtain image for region selection.", parent=self.master)
            self.destroy_selector_immediately()
            return

        img_orig_w, img_orig_h = self.image_source_pil.size

        if direct_image_input_pil:
            max_display_w = min(img_orig_w, self.winfo_screenwidth() - 100)
            max_display_h = min(img_orig_h, self.winfo_screenheight() - 150)
            self.overrideredirect(False)
            self.geometry("")
        else:
            max_display_w, max_display_h = img_orig_w, img_orig_h
            self.overrideredirect(True)
            self.geometry(f"{img_orig_w}x{img_orig_h}+0+0")
            # For overlay, ensure no window decorations interfere with coords
            self.wm_attributes("-fullscreen", True)  # Attempt true fullscreen for overlay

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

        self.canvas = ctk.CTkCanvas(self, width=self.canvas_display_width, height=self.canvas_display_height, highlightthickness=0, borderwidth=0, cursor="crosshair")  # Added crosshair
        self.canvas.create_image(0, 0, anchor="nw", image=self.image_source_tk)
        self.canvas.pack(side="top", fill="both", expand=True)

    def _get_appearance_mode_fg_color(self) -> str:
        """Helper to get a suitable background color based on theme."""
        try:
            # Accessing theme data directly can be fragile.
            # CustomTkinter might not expose this cleanly.
            if ctk.get_appearance_mode().lower() == "dark":
                return "gray20"
            return "gray85"
        except Exception:
            return "gray85"  # Fallback

    def _setup_controls_and_bindings(self):
        if not hasattr(self, "canvas") or not self.canvas:
            return

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)
        self.bind("<Escape>", self._cancel_selection)
        self.bind("<Return>", self._trigger_confirmation_dialog)

        instruction_text = "Click & Drag to draw selection. Press 'Enter' to Confirm, 'Esc' to Cancel."
        if self.is_editing_existing and self.original_existing_region_data:
            instruction_text = f"Editing '{self.original_existing_region_data.get('name')}'. Redraw or press 'Enter' to use current coords, then confirm name."

        # Make instruction label slightly transparent for better overlay feel
        label_fg_color_tuple = ("#E0E0E0", "#303030")  # Light gray, Dark gray (adjust as needed)
        label_text_color_tuple = ("#101010", "#DCE4EE")
        self.instruction_label = ctk.CTkLabel(
            self, text=instruction_text, font=ctk.CTkFont(size=14, weight="bold"), fg_color=label_fg_color_tuple, text_color=label_text_color_tuple, corner_radius=6, padx=8, pady=4
        )
        self.instruction_label.place(in_=self.canvas, relx=0.5, y=20, anchor="n")

        if self.overrideredirect() is False:  # Normal window (direct_image_input_pil mode)
            controls_frame = ctk.CTkFrame(self, fg_color="transparent")
            controls_frame.pack(side="bottom", fill="x", pady=10, padx=10)
            controls_frame.grid_columnconfigure(0, weight=1)
            controls_frame.grid_columnconfigure(3, weight=1)
            self.btn_confirm_selection = ctk.CTkButton(controls_frame, text="Confirm Selection", command=self._trigger_confirmation_dialog, state="disabled")
            self.btn_confirm_selection.grid(row=0, column=2, padx=5)
            ctk.CTkButton(controls_frame, text="Cancel", command=self._cancel_selection).grid(row=0, column=1, padx=5)
        else:
            self.btn_confirm_selection = None

    def _center_on_master_screen(self):
        self.update_idletasks()
        if self.master and self.master.winfo_exists():
            master_x, master_y, master_w, master_h = self.master.winfo_x(), self.master.winfo_y(), self.master.winfo_width(), self.master.winfo_height()
            win_w, win_h = self.winfo_width(), self.winfo_height()
            x = master_x + (master_w // 2) - (win_w // 2)
            y = master_y + (master_h // 2) - (win_h // 2)
            self.geometry(f"{win_w}x{win_h}+{max(0,x)}+{max(0,y)}")
        else:
            self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        self.lift()

    def _pre_draw_existing_region(self):
        if not self.original_existing_region_data or not self.image_source_pil or not self.canvas:
            return
        x_orig = self.original_existing_region_data.get("x", DEFAULT_NEW_REGION_X)
        y_orig = self.original_existing_region_data.get("y", DEFAULT_NEW_REGION_Y)
        w_orig = self.original_existing_region_data.get("width", DEFAULT_NEW_REGION_WIDTH)
        h_orig = self.original_existing_region_data.get("height", DEFAULT_NEW_REGION_HEIGHT)
        if w_orig <= 0 or h_orig <= 0:
            logger.warning(f"Pre-draw: Non-positive dims for '{self.original_existing_region_data.get('name')}'.")
            return

        x1_canvas = int(round(x_orig * self.image_display_scale_factor))
        y1_canvas = int(round(y_orig * self.image_display_scale_factor))
        x2_canvas = int(round((x_orig + w_orig) * self.image_display_scale_factor))
        y2_canvas = int(round((y_orig + h_orig) * self.image_display_scale_factor))
        x1_canvas = max(0, x1_canvas)
        y1_canvas = max(0, y1_canvas)
        x2_canvas = min(self.canvas_display_width, x2_canvas)
        y2_canvas = min(self.canvas_display_height, y2_canvas)

        if self.current_selection_rect_id:
            self.canvas.delete(self.current_selection_rect_id)
        self.current_selection_rect_id = self.canvas.create_rectangle(x1_canvas, y1_canvas, x2_canvas, y2_canvas, outline="lime green", width=3, fill="#00FF0030")  # Semi-transparent green
        self.selected_coords_on_image = (x_orig, y_orig, x_orig + w_orig, y_orig + h_orig)
        if self.btn_confirm_selection:
            self.btn_confirm_selection.configure(state="normal")
        logger.info(
            f"RegionSelector: Pre-drew existing region '{self.original_existing_region_data.get('name')}' at canvas ({x1_canvas},{y1_canvas})-({x2_canvas},{y2_canvas}). Original image coords: {self.selected_coords_on_image}"
        )

    def _on_mouse_press(self, event):
        self.start_x_canvas, self.start_y_canvas = event.x, event.y
        if self.current_selection_rect_id:
            self.canvas.delete(self.current_selection_rect_id)
        self.current_selection_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2, dash=(5, 3))
        if self.btn_confirm_selection:
            self.btn_confirm_selection.configure(state="disabled")
        self.instruction_label.configure(text="Dragging... Release mouse to finalize selection.")

    def _on_mouse_drag(self, event):
        if self.start_x_canvas is None or self.current_selection_rect_id is None:
            return
        self.canvas.coords(self.current_selection_rect_id, self.start_x_canvas, self.start_y_canvas, event.x, event.y)

    def _on_mouse_release(self, event):
        if self.start_x_canvas is None or self.current_selection_rect_id is None:
            return
        x1_c = max(0, min(self.start_x_canvas, event.x))
        y1_c = max(0, min(self.start_y_canvas, event.y))
        x2_c = min(self.canvas_display_width, max(self.start_x_canvas, event.x))
        y2_c = min(self.canvas_display_height, max(self.start_y_canvas, event.y))
        w_c, h_c = x2_c - x1_c, y2_c - y1_c

        if w_c > 0 and h_c > 0:
            self.canvas.coords(self.current_selection_rect_id, x1_c, y1_c, x2_c, y2_c)
            self.canvas.itemconfig(self.current_selection_rect_id, outline="lime green", width=3, dash=())
            orig_x1 = int(round(x1_c / self.image_display_scale_factor))
            orig_y1 = int(round(y1_c / self.image_display_scale_factor))
            orig_x2 = int(round(x2_c / self.image_display_scale_factor))
            orig_y2 = int(round(y2_c / self.image_display_scale_factor))
            img_w_orig, img_h_orig = self.image_source_pil.size
            orig_x1 = max(0, orig_x1)
            orig_y1 = max(0, orig_y1)
            orig_x2 = min(img_w_orig, orig_x2)
            orig_y2 = min(img_h_orig, orig_y2)
            if (orig_x2 - orig_x1) > 0 and (orig_y2 - orig_y1) > 0:
                self.selected_coords_on_image = (orig_x1, orig_y1, orig_x2, orig_y2)
                if self.btn_confirm_selection:
                    self.btn_confirm_selection.configure(state="normal")
                self.instruction_label.configure(text=f"Selection: ({orig_x1},{orig_y1}) to ({orig_x2},{orig_y2}) on original. Press Enter or Confirm.")
            else:
                self._reset_selection_state("Invalid selection (zero area on original). Redraw.")
        else:
            self._reset_selection_state("Invalid selection (zero area on canvas). Redraw.")

    def _reset_selection_state(self, instruction_text: str):
        self.selected_coords_on_image = None
        if self.current_selection_rect_id and self.canvas.winfo_exists():
            self.canvas.delete(self.current_selection_rect_id)
            self.current_selection_rect_id = None
        if self.btn_confirm_selection:
            self.btn_confirm_selection.configure(state="disabled")
        if self.instruction_label and self.instruction_label.winfo_exists():
            self.instruction_label.configure(text=instruction_text)

    def _trigger_confirmation_dialog(self, event=None):
        if not self.selected_coords_on_image:
            messagebox.showwarning("No Region Selected", "Please draw a rectangular selection first.", parent=self)
            return
        x1, y1, x2, y2 = self.selected_coords_on_image
        sel_w, sel_h = x2 - x1, y2 - y1
        if sel_w <= 0 or sel_h <= 0:
            messagebox.showerror("Invalid Selection", "Selected region has zero width or height. Please redraw.", parent=self)
            return

        initial_alpha = self.attributes("-alpha")
        was_topmost = self.attributes("-topmost")
        if self.overrideredirect():
            self.attributes("-alpha", 0.0)
            self.lower()
        self.attributes("-topmost", False)

        # Default name logic: use existing if editing, else suggest new
        default_name_suggestion = f"Region_{len(self.config_manager_context.get_regions()) + 1 if self.config_manager_context else 1}"
        if self.is_editing_existing and self.original_existing_region_data:
            default_name_suggestion = self.original_existing_region_data.get("name", default_name_suggestion)

        dialog = ctk.CTkInputDialog(
            text=f"Enter unique name for this region:\nCoords (on original): x={x1}, y={y1}, w={sel_w}, h={sel_h}", title="Confirm Region Name", entry_text=default_name_suggestion
        )
        input_name = dialog.get_input()

        if self.overrideredirect():
            self.attributes("-alpha", initial_alpha)
        self.attributes("-topmost", was_topmost)
        self.lift()
        self.focus_force()

        if input_name and input_name.strip():
            final_name = input_name.strip()
            self.saved_region_info = {"name": final_name, "x": x1, "y": y1, "width": sel_w, "height": sel_h}
            self.changes_made = True
            logger.info(f"RegionSelector: Confirmed region '{final_name}' with coords {self.saved_region_info} (relative to source image).")
            self.destroy_selector_immediately()
        else:
            logger.info("RegionSelector: Name input cancelled/empty. Selection remains.")
            self.instruction_label.configure(text=f"Naming cancelled. Selection active. Press Enter or Confirm.")
            if self.btn_confirm_selection:
                self.btn_confirm_selection.configure(state="normal")

    def _cancel_selection(self, event=None):
        logger.info("RegionSelector: User cancelled selection.")
        self.saved_region_info = None
        self.changes_made = False
        self.destroy_selector_immediately()

    def destroy_selector_immediately(self):
        logger.debug("RegionSelectorWindow: Destroying self.")
        self.grab_release()
        self.destroy()

    def get_selected_region_info(self) -> Optional[Dict[str, Any]]:
        return self.saved_region_info if self.changes_made else None
