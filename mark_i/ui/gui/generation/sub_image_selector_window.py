import logging
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Tuple, Any

import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw

# Standardized logger
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.generation.sub_image_selector_window")


class SubImageSelectorWindow(ctk.CTkToplevel):
    """
    A modal Toplevel window that displays a provided PIL image and allows the user
    to select a rectangular sub-area by clicking and dragging.
    Returns the selected coordinates relative to the original input PIL image.
    """

    def __init__(self, master: Any, image_to_select_from_pil: Image.Image, title: str = "Select Sub-Image Area"):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)  # Handle window close button

        if not image_to_select_from_pil:
            logger.error("SubImageSelectorWindow: No image provided for selection.")
            messagebox.showerror("Error", "No image provided to select from.", parent=self)
            self.after(10, self.destroy)  # Schedule destroy as self might not be fully up
            return

        self.original_pil_image: Image.Image = image_to_select_from_pil.copy()  # Work with a copy
        self.display_pil_image: Optional[Image.Image] = None  # Scaled image for display
        self.display_tk_image: Optional[ImageTk.PhotoImage] = None  # Tkinter-compatible version for canvas

        self.canvas_display_width: int = 0
        self.canvas_display_height: int = 0
        self.image_display_scale_factor: float = 1.0  # Scale if image is larger than display area

        self.start_x_canvas: Optional[int] = None  # Canvas coordinate for mouse press
        self.start_y_canvas: Optional[int] = None  # Canvas coordinate for mouse press
        self.current_selection_rect_id: Optional[int] = None  # ID of the rectangle on canvas

        # Stores (x1, y1, x2, y2) relative to the original_pil_image
        self.final_selected_coords_on_original_image: Optional[Tuple[int, int, int, int]] = None

        self._setup_ui()
        self._prepare_display_image_and_canvas()

        self.after(100, self._center_on_master)  # Center after initial rendering
        self.focus_force()  # Ensure this window gets focus
        logger.info(f"SubImageSelectorWindow initialized for image size: {self.original_pil_image.size}")

    def _center_on_master(self):
        """Centers the window relative to its master or the screen."""
        self.update_idletasks()  # Ensure window dimensions are calculated
        if self.master and self.master.winfo_exists():
            master_x = self.master.winfo_x()
            master_y = self.master.winfo_y()
            master_w = self.master.winfo_width()
            master_h = self.master.winfo_height()
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            x_pos = master_x + (master_w // 2) - (win_w // 2)
            y_pos = master_y + (master_h // 2) - (win_h // 2)
            self.geometry(f"+{max(0, x_pos)}+{max(0, y_pos)}")
        else:  # Fallback to screen center if no master or master not visible
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            win_w = self.winfo_width()
            win_h = self.winfo_height()
            x_pos = (screen_w // 2) - (win_w // 2)
            y_pos = (screen_h // 2) - (win_h // 2)
            self.geometry(f"+{max(0, x_pos)}+{max(0, y_pos)}")
        self.lift()  # Ensure it's on top

    def _setup_ui(self):
        """Sets up the main canvas and control buttons."""
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.main_frame.grid_rowconfigure(1, weight=1)  # Canvas row expands
        self.main_frame.grid_columnconfigure(0, weight=1)  # Canvas column expands

        self.instruction_label = ctk.CTkLabel(self.main_frame, text="Click and drag on the image to select an area.", font=ctk.CTkFont(size=13))
        self.instruction_label.grid(row=0, column=0, pady=(0, 5), sticky="ew")

        # Canvas will be configured with actual size in _prepare_display_image_and_canvas
        self.canvas = ctk.CTkCanvas(self.main_frame, highlightthickness=0, borderwidth=0, background="gray50")  # Neutral bg
        self.canvas.grid(row=1, column=0, sticky="nsew")

        # Bind mouse events for drawing selection
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_release)

        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(10, 0), sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)  # Spacer left
        button_frame.grid_columnconfigure(3, weight=1)  # Spacer right

        self.btn_confirm = ctk.CTkButton(button_frame, text="Confirm Selection", command=self._on_confirm, state="disabled")
        self.btn_confirm.grid(row=0, column=2, padx=5)

        self.btn_cancel = ctk.CTkButton(button_frame, text="Cancel", command=self._on_cancel)
        self.btn_cancel.grid(row=0, column=1, padx=5)

    def _prepare_display_image_and_canvas(self):
        """Resizes the image if necessary to fit the screen and displays it on the canvas."""
        orig_w, orig_h = self.original_pil_image.size

        # Determine max display size based on master window or screen, leaving some margin
        if self.master and self.master.winfo_exists():
            max_w = self.master.winfo_width() - 100  # Leave some padding
            max_h = self.master.winfo_height() - 150  # More padding for title bar, buttons
        else:
            max_w = self.winfo_screenwidth() - 100
            max_h = self.winfo_screenheight() - 150

        max_w = max(300, max_w)  # Minimum sensible width
        max_h = max(200, max_h)  # Minimum sensible height

        self.image_display_scale_factor = 1.0
        if orig_w > max_w or orig_h > max_h:
            self.image_display_scale_factor = min(max_w / orig_w, max_h / orig_h)

        self.canvas_display_width = int(orig_w * self.image_display_scale_factor)
        self.canvas_display_height = int(orig_h * self.image_display_scale_factor)

        # Ensure dimensions are at least 1 pixel for resize
        if self.canvas_display_width < 1:
            self.canvas_display_width = 1
        if self.canvas_display_height < 1:
            self.canvas_display_height = 1

        self.display_pil_image = self.original_pil_image.resize((self.canvas_display_width, self.canvas_display_height), Image.Resampling.LANCZOS)  # Use LANCZOS for better quality downscaling
        self.display_tk_image = ImageTk.PhotoImage(self.display_pil_image)

        self.canvas.configure(width=self.canvas_display_width, height=self.canvas_display_height)
        self.canvas.create_image(0, 0, anchor="nw", image=self.display_tk_image)

        # Adjust window size to fit canvas and controls after canvas is configured
        self.update_idletasks()  # Ensure widgets report correct sizes
        instr_h = self.instruction_label.winfo_reqheight() if self.instruction_label.winfo_exists() else 20
        btn_h = self.btn_confirm.winfo_reqheight() if self.btn_confirm.winfo_exists() else 30

        req_w = self.canvas_display_width + 40  # Padding for main_frame and window borders
        req_h = self.canvas_display_height + instr_h + btn_h + 60  # Padding, instr label, button frame

        self.geometry(f"{max(400, req_w)}x{max(300, req_h)}")

    def _on_mouse_press(self, event):
        self.start_x_canvas, self.start_y_canvas = event.x, event.y
        if self.current_selection_rect_id:
            self.canvas.delete(self.current_selection_rect_id)
        # Create a new rectangle. Use a dashed outline or different color during drawing.
        self.current_selection_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2, dash=(4, 2))
        self.btn_confirm.configure(state="disabled")  # Disable confirm until selection is made
        self.instruction_label.configure(text="Dragging... Release mouse to finalize selection.")

    def _on_mouse_drag(self, event):
        if self.start_x_canvas is None or self.current_selection_rect_id is None:
            return
        # Update the coordinates of the rectangle as the mouse is dragged
        self.canvas.coords(self.current_selection_rect_id, self.start_x_canvas, self.start_y_canvas, event.x, event.y)

    def _on_mouse_release(self, event):
        if self.start_x_canvas is None or self.current_selection_rect_id is None:
            return

        # Final canvas coordinates, normalized (x1 < x2, y1 < y2)
        x1_c = max(0, min(self.start_x_canvas, event.x))
        y1_c = max(0, min(self.start_y_canvas, event.y))
        x2_c = min(self.canvas_display_width, max(self.start_x_canvas, event.x))
        y2_c = min(self.canvas_display_height, max(self.start_y_canvas, event.y))

        w_c = x2_c - x1_c
        h_c = y2_c - y1_c

        if w_c > 0 and h_c > 0:
            self.canvas.coords(self.current_selection_rect_id, x1_c, y1_c, x2_c, y2_c)
            self.canvas.itemconfig(self.current_selection_rect_id, outline="lime green", width=3, dash=())  # Solid line for confirmed selection

            # Convert canvas coordinates to original image coordinates using scale factor
            orig_x1 = int(round(x1_c / self.image_display_scale_factor))
            orig_y1 = int(round(y1_c / self.image_display_scale_factor))
            orig_x2 = int(round(x2_c / self.image_display_scale_factor))
            orig_y2 = int(round(y2_c / self.image_display_scale_factor))

            # Ensure coordinates are within original image bounds after scaling
            img_w_orig, img_h_orig = self.original_pil_image.size
            orig_x1 = max(0, orig_x1)
            orig_y1 = max(0, orig_y1)
            orig_x2 = min(img_w_orig, orig_x2)
            orig_y2 = min(img_h_orig, orig_y2)

            if (orig_x2 - orig_x1) > 0 and (orig_y2 - orig_y1) > 0:
                self.final_selected_coords_on_original_image = (orig_x1, orig_y1, orig_x2, orig_y2)
                self.btn_confirm.configure(state="normal")
                self.instruction_label.configure(text=f"Selection made. Original Coords (x1,y1,x2,y2): ({orig_x1},{orig_y1})-({orig_x2},{orig_y2}). Confirm or redraw.")
                logger.debug(f"SubImageSelector: Selection on canvas ({x1_c},{y1_c})-({x2_c},{y2_c}), maps to original ({orig_x1},{orig_y1})-({orig_x2},{orig_y2})")
            else:
                self._reset_selection_state("Invalid selection (zero area on original image after scaling). Please redraw.")
        else:  # Zero area on canvas
            self._reset_selection_state("Invalid selection (zero area on canvas). Please redraw.")

    def _reset_selection_state(self, instruction_text: str):
        """Resets selection state and updates UI."""
        self.final_selected_coords_on_original_image = None
        if self.current_selection_rect_id:
            self.canvas.delete(self.current_selection_rect_id)
            self.current_selection_rect_id = None
        self.btn_confirm.configure(state="disabled")
        self.instruction_label.configure(text=instruction_text)

    def _on_confirm(self):
        if self.final_selected_coords_on_original_image:
            logger.info(f"SubImageSelector: User confirmed selection. Coords (x1,y1,x2,y2) on original: {self.final_selected_coords_on_original_image}")
            self.grab_release()
            self.destroy()
        else:
            messagebox.showwarning("No Selection", "Please select an area on the image first.", parent=self)

    def _on_cancel(self, event=None):
        logger.info("SubImageSelector: User cancelled selection.")
        self.final_selected_coords_on_original_image = None  # Ensure no coords are returned
        self.grab_release()
        self.destroy()

    def get_selected_coords(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Called by the parent window after this Toplevel closes to get the result.
        Returns (x, y, width, height) relative to the original image if a selection
        was confirmed, otherwise None.
        """
        if self.final_selected_coords_on_original_image:
            x1, y1, x2, y2 = self.final_selected_coords_on_original_image
            return (x1, y1, x2 - x1, y2 - y1)  # Convert to x,y,w,h
        return None
