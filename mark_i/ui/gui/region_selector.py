import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict, Any, Tuple
import time
import copy

import customtkinter as ctk
from PIL import ImageGrab, ImageTk, Image, ImageDraw

from mark_i.core.config_manager import ConfigManager
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.region_selector")

DEFAULT_NEW_REGION_X = 50
DEFAULT_NEW_REGION_Y = 50
DEFAULT_NEW_REGION_WIDTH = 200
DEFAULT_NEW_REGION_HEIGHT = 150


class RegionSelectorWindow(ctk.CTkToplevel):
    def __init__(self, master: Any, config_manager_context: ConfigManager, existing_region_data: Optional[Dict[str, Any]] = None, direct_image_input_pil: Optional[Image.Image] = None):
        super().__init__(master)

        self.transient(master)
        self.grab_set()
        self.attributes("-topmost", True)

        self.config_manager_context = config_manager_context
        self.original_existing_region_data = copy.deepcopy(existing_region_data) if existing_region_data else None
        self.is_editing_existing = bool(self.original_existing_region_data)

        edit_name_hint = self.original_existing_region_data.get("name", "") if self.is_editing_existing else ""
        self.title(f"Region Selector - {'Edit: ' + edit_name_hint if self.is_editing_existing and edit_name_hint else ('Edit Region' if self.is_editing_existing else 'Add New Region')}")

        self.image_source_pil: Optional[Image.Image] = None
        self.image_source_tk: Optional[ImageTk.PhotoImage] = None

        self.canvas_display_width: int = 0
        self.canvas_display_height: int = 0
        self.image_display_scale_factor: float = 1.0

        self.current_selection_rect_id: Optional[int] = None
        self.start_x_canvas: Optional[int] = None
        self.start_y_canvas: Optional[int] = None
        self.selected_coords_on_image: Optional[Tuple[int, int, int, int]] = None

        self.saved_region_info: Optional[Dict[str, Any]] = None
        self.changes_made: bool = False

        self._is_direct_image_input_mode = direct_image_input_pil is not None

        try:
            self._setup_canvas_and_image(direct_image_input_pil)
            if hasattr(self, "canvas") and self.canvas:
                self._setup_controls_and_bindings()
                if self.is_editing_existing and self.original_existing_region_data:
                    self._pre_draw_existing_region()
            else:
                raise RuntimeError("Canvas setup failed critically.")

            logger.info(f"RegionSelectorWindow initialized. Editing: {self.is_editing_existing}. Source: {'Provided Image' if direct_image_input_pil else 'Live Screen'}.")
            self.after(100, self._center_on_master_screen)
            self.focus_force()
        except Exception as e_init:
            logger.critical(f"Critical error during RegionSelectorWindow __init__: {e_init}", exc_info=True)
            messagebox.showerror("Region Selector Error", f"Failed to initialize Region Selector:\n{e_init}", parent=self.master if self.master else None)
            self.after(10, self.destroy_selector_immediately)

    def _setup_canvas_and_image(self, direct_image_input_pil: Optional[Image.Image]):
        screen_interaction_alpha = 0.25
        image_display_alpha = 1.0

        if self._is_direct_image_input_mode:
            if not direct_image_input_pil:
                logger.error("RegionSelector: Direct image input mode selected, but no PIL image provided.")
                raise ValueError("Direct image input mode selected, but no PIL image provided.")
            logger.debug("RegionSelector: Using direct PIL image input.")
            self.image_source_pil = direct_image_input_pil.copy()
            self.attributes("-alpha", image_display_alpha)
            self.configure(fg_color=self._get_appearance_mode_fg_color())
            self.overrideredirect(False)
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
                self.overrideredirect(True)
                self.lift()
            except Exception as e:
                logger.error(f"RegionSelector: Failed to capture full screen: {e}", exc_info=True)
                raise RuntimeError(f"Could not capture screen: {e}") from e

        if not self.image_source_pil:
            logger.error("RegionSelector: Image source is None after capture/input. Cannot proceed.")
            raise RuntimeError("Could not obtain image for region selection.")

        img_orig_w, img_orig_h = self.image_source_pil.size
        if img_orig_w <= 0 or img_orig_h <= 0:
            logger.error(f"RegionSelector: Image source has invalid dimensions ({img_orig_w}x{img_orig_h}). Cannot proceed.")
            raise RuntimeError(f"Image source has invalid dimensions ({img_orig_w}x{img_orig_h}).")

        if self._is_direct_image_input_mode:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            max_win_w = screen_w - 100
            max_win_h = screen_h - 150

            self.image_display_scale_factor = 1.0
            if img_orig_w > max_win_w or img_orig_h > max_win_h:
                self.image_display_scale_factor = min(max_win_w / img_orig_w, max_win_h / img_orig_h)
            if self.image_display_scale_factor <= 0:
                self.image_display_scale_factor = 1.0

            self.canvas_display_width = int(img_orig_w * self.image_display_scale_factor)
            self.canvas_display_height = int(img_orig_h * self.image_display_scale_factor)
            img_for_canvas_pil = self.image_source_pil.resize((max(1, self.canvas_display_width), max(1, self.canvas_display_height)), Image.Resampling.LANCZOS)
        else:
            self.image_display_scale_factor = 1.0
            self.canvas_display_width = img_orig_w
            self.canvas_display_height = img_orig_h
            img_for_canvas_pil = self.image_source_pil
            self.geometry(f"{img_orig_w}x{img_orig_h}+0+0")

        self.image_source_tk = ImageTk.PhotoImage(img_for_canvas_pil)

        self.canvas = ctk.CTkCanvas(self, width=self.canvas_display_width, height=self.canvas_display_height, highlightthickness=0, borderwidth=0, cursor="crosshair")
        self.canvas.create_image(0, 0, anchor="nw", image=self.image_source_tk)
        self.canvas.pack(side="top", fill="both", expand=True)

        if not self.overrideredirect():
            self.update_idletasks()
            controls_height_estimate = 60
            min_sensible_width = 400
            min_sensible_height = 300
            final_win_width = max(min_sensible_width, self.canvas_display_width + 20)
            final_win_height = max(min_sensible_height, self.canvas_display_height + controls_height_estimate + 20)
            self.geometry(f"{final_win_width}x{final_win_height}")

    def _get_appearance_mode_fg_color(self) -> str:
        try:
            if ctk.get_appearance_mode().lower() == "dark":
                return "gray20"
            return "gray85"
        except Exception:
            return "gray85"

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
            instruction_text = f"Editing '{self.original_existing_region_data.get('name', 'Region')}'. Redraw or press 'Enter' to use current coords, then confirm name."

        label_bg_color = ("gray80", "gray25")
        label_text_color = ("black", "white")

        self.instruction_label = ctk.CTkLabel(
            self, text=instruction_text, font=ctk.CTkFont(size=14, weight="bold"), fg_color=label_bg_color, text_color=label_text_color, corner_radius=6, padx=8, pady=4
        )

        if self.overrideredirect():
            self.instruction_label.place(in_=self.canvas, relx=0.5, y=20, anchor="n")
        else:
            instruction_frame = ctk.CTkFrame(self, fg_color="transparent")
            instruction_frame.pack(side="top", fill="x", pady=(5, 0), padx=10)
            self.instruction_label.pack(in_=instruction_frame)
            self.canvas.pack_configure(pady=(5, 0), padx=10, expand=False)

            controls_frame = ctk.CTkFrame(self, fg_color="transparent")
            controls_frame.pack(side="bottom", fill="x", pady=10, padx=10)
            controls_frame.grid_columnconfigure(0, weight=1)
            controls_frame.grid_columnconfigure(3, weight=1)
            self.btn_confirm_selection = ctk.CTkButton(controls_frame, text="Confirm Selection", command=self._trigger_confirmation_dialog, state="disabled")
            self.btn_confirm_selection.grid(row=0, column=2, padx=5)
            ctk.CTkButton(controls_frame, text="Cancel", command=self._cancel_selection).grid(row=0, column=1, padx=5)

        if not self.overrideredirect() and not hasattr(self, "btn_confirm_selection"):
            logger.error("Button 'btn_confirm_selection' was not initialized for non-overlay mode.")

    def _center_on_master_screen(self):
        self.update_idletasks()
        if self.overrideredirect():
            return

        if self.master and self.master.winfo_exists():
            master_x, master_y, master_w, master_h = self.master.winfo_x(), self.master.winfo_y(), self.master.winfo_width(), self.master.winfo_height()
            win_w, win_h = self.winfo_width(), self.winfo_height()
            x = master_x + (master_w // 2) - (win_w // 2)
            y = master_y + (master_h // 2) - (win_h // 2)
            self.geometry(f"{win_w}x{win_h}+{max(0,x)}+{max(0,y)}")
        elif not self.overrideredirect():
            self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        self.lift()

    def _pre_draw_existing_region(self):
        if not self.original_existing_region_data or not self.image_source_pil or not self.canvas:
            return
        x_orig = self.original_existing_region_data.get("x", DEFAULT_NEW_REGION_X)
        y_orig = self.original_existing_region_data.get("y", DEFAULT_NEW_REGION_Y)
        w_orig = self.original_existing_region_data.get("width", DEFAULT_NEW_REGION_WIDTH)
        h_orig = self.original_existing_region_data.get("height", DEFAULT_NEW_REGION_HEIGHT)

        if not all(isinstance(v, int) for v in [x_orig, y_orig, w_orig, h_orig]):
            logger.warning(f"Pre-draw: Existing region '{self.original_existing_region_data.get('name')}' has invalid coordinate/dimension types. Using defaults.")
            x_orig, y_orig, w_orig, h_orig = DEFAULT_NEW_REGION_X, DEFAULT_NEW_REGION_Y, DEFAULT_NEW_REGION_WIDTH, DEFAULT_NEW_REGION_HEIGHT
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

        self.current_selection_rect_id = self.canvas.create_rectangle(x1_canvas, y1_canvas, x2_canvas, y2_canvas, outline="lime green", width=3)

        self.selected_coords_on_image = (x_orig, y_orig, x_orig + w_orig, y_orig + h_orig)
        if hasattr(self, "btn_confirm_selection") and self.btn_confirm_selection:
            self.btn_confirm_selection.configure(state="normal")
        logger.info(
            f"RegionSelector: Pre-drew existing region '{self.original_existing_region_data.get('name')}' at canvas ({x1_canvas},{y1_canvas})-({x2_canvas},{y2_canvas}). Original image coords: {self.selected_coords_on_image}"
        )

    def _on_mouse_press(self, event):
        try:
            self.start_x_canvas, self.start_y_canvas = event.x, event.y
            if self.current_selection_rect_id:
                self.canvas.delete(self.current_selection_rect_id)
            self.current_selection_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2, dash=(5, 3))
            if hasattr(self, "btn_confirm_selection") and self.btn_confirm_selection:
                self.btn_confirm_selection.configure(state="disabled")
            if self.instruction_label and self.instruction_label.winfo_exists():
                self.instruction_label.configure(text="Dragging... Release mouse to finalize selection.")
        except Exception as e:
            logger.error(f"Error in _on_mouse_press: {e}", exc_info=True)
            messagebox.showerror("Selection Error", f"An error occurred while starting selection: {e}", parent=self)
            self.destroy_selector_immediately()

    def _on_mouse_drag(self, event):
        try:
            if self.start_x_canvas is None or self.current_selection_rect_id is None:
                return
            self.canvas.coords(self.current_selection_rect_id, self.start_x_canvas, self.start_y_canvas, event.x, event.y)
        except Exception as e:
            logger.error(f"Error in _on_mouse_drag: {e}", exc_info=True)

    def _on_mouse_release(self, event):
        try:
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
                    if hasattr(self, "btn_confirm_selection") and self.btn_confirm_selection:
                        self.btn_confirm_selection.configure(state="normal")
                    if self.instruction_label and self.instruction_label.winfo_exists():
                        self.instruction_label.configure(text=f"Selection: ({orig_x1},{orig_y1}) to ({orig_x2},{orig_y2}) on original. Press Enter or Confirm.")
                else:
                    self._reset_selection_state("Invalid selection (zero area on original). Redraw.")
            else:
                self._reset_selection_state("Invalid selection (zero area on canvas). Redraw.")
        except Exception as e:
            logger.error(f"Error in _on_mouse_release: {e}", exc_info=True)
            messagebox.showerror("Selection Error", f"An error occurred finalizing selection: {e}", parent=self)
            self.destroy_selector_immediately()

    def _reset_selection_state(self, instruction_text: str):
        self.selected_coords_on_image = None
        if self.current_selection_rect_id and self.canvas.winfo_exists():
            self.canvas.delete(self.current_selection_rect_id)
            self.current_selection_rect_id = None
        if hasattr(self, "btn_confirm_selection") and self.btn_confirm_selection:
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
        was_overrideredirect = self.overrideredirect()

        input_name_value_to_prefill = ""  # For CTkInputDialog, we can't prefill the entry easily.
        # The prompt text itself will suggest the name.

        default_name_suggestion = f"Region_{len(self.config_manager_context.get_regions()) + 1 if self.config_manager_context else 1}"
        if self.is_editing_existing and self.original_existing_region_data:
            default_name_suggestion = self.original_existing_region_data.get("name", default_name_suggestion)

        dialog_prompt_text = f"Enter unique name for this region (e.g., '{default_name_suggestion}'):\nCoords (on original): x={x1}, y={y1}, w={sel_w}, h={sel_h}"

        try:
            if was_overrideredirect:
                self.overrideredirect(False)
                self.attributes("-alpha", 1.0)
            self.attributes("-topmost", False)

            dialog = ctk.CTkInputDialog(
                text=dialog_prompt_text,
                title="Confirm Region Name",
                # CTkInputDialog does not take 'entry_text' or 'parent'
            )
            input_name = dialog.get_input()

        finally:
            if self.winfo_exists():
                if was_overrideredirect:
                    self.overrideredirect(True)
                    self.attributes("-alpha", initial_alpha)
                self.attributes("-topmost", was_topmost)
                self.lift()
                self.focus_force()

        if input_name and input_name.strip():
            final_name = input_name.strip()
            self.saved_region_info = {"name": final_name, "x": x1, "y": y1, "width": sel_w, "height": sel_h}
            if self.is_editing_existing and self.original_existing_region_data:
                self.saved_region_info["comment"] = self.original_existing_region_data.get("comment", f"Region edited: {final_name}")
            else:
                self.saved_region_info["comment"] = f"Newly defined region: {final_name}"

            self.changes_made = True
            logger.info(f"RegionSelector: Confirmed region '{final_name}' with coords {self.saved_region_info} (relative to source image).")
            self.destroy_selector_immediately()
        elif input_name is None:
            logger.info("RegionSelector: Name input dialog cancelled by user. Selection remains active.")
            if self.instruction_label and self.instruction_label.winfo_exists():
                self.instruction_label.configure(text=f"Naming cancelled. Selection active. Press Enter or Confirm.")
            if hasattr(self, "btn_confirm_selection") and self.btn_confirm_selection:
                self.btn_confirm_selection.configure(state="normal")
        else:
            logger.info("RegionSelector: Name input was empty. Selection remains active.")
            messagebox.showwarning("Name Required", "Region name cannot be empty. Please try again or cancel.", parent=self)
            if self.instruction_label and self.instruction_label.winfo_exists():
                self.instruction_label.configure(text=f"Naming aborted (empty name). Selection active. Press Enter or Confirm.")
            if hasattr(self, "btn_confirm_selection") and self.btn_confirm_selection:
                self.btn_confirm_selection.configure(state="normal")

    def _cancel_selection(self, event=None):
        logger.info("RegionSelector: User cancelled selection.")
        self.saved_region_info = None
        self.changes_made = False
        self.destroy_selector_immediately()

    def destroy_selector_immediately(self):
        logger.debug("RegionSelectorWindow: Attempting to destroy self.")
        if self.winfo_exists():
            if self.overrideredirect():
                self.overrideredirect(False)
            current_grab = self.grab_current()
            if current_grab == self:
                self.grab_release()
            elif current_grab:
                logger.warning(f"RegionSelector: Tried to release grab, but grab is held by {current_grab}, not self.")

            self.destroy()
            logger.debug("RegionSelectorWindow: Destroy call completed.")
        else:
            logger.debug("RegionSelectorWindow: Destroy called, but window no longer exists.")

    def get_selected_region_info(self) -> Optional[Dict[str, Any]]:
        return self.saved_region_info if self.changes_made and self.saved_region_info else None
