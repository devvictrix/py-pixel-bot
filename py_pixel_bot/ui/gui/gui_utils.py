import logging
import tkinter as tk
from tkinter import messagebox
from typing import Any, Optional, List, Union, Tuple, Callable

import customtkinter as ctk

logger = logging.getLogger(__name__)


def parse_bgr_string(bgr_str: str, field_name_for_error: str) -> Optional[List[int]]:
    """Parses a 'B,G,R' string into a list of 3 integers. Returns None on failure."""
    try:
        parts = [int(p.strip()) for p in bgr_str.split(",")]
        if len(parts) == 3 and all(0 <= x <= 255 for x in parts):
            return parts
        else:
            messagebox.showerror("BGR Format Error", f"Invalid BGR format for '{field_name_for_error}'.\nExpected 3 numbers (0-255) separated by commas (e.g., '255,0,128').")
            return None
    except ValueError:
        messagebox.showerror("BGR Format Error", f"Invalid BGR values for '{field_name_for_error}'.\nNumbers must be integers between 0 and 255 (e.g., '255,0,128').")
        return None


def validate_and_get_widget_value(
    widget: Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox, None],
    tk_var: Optional[Union[tk.StringVar, tk.BooleanVar]],
    field_name_for_error: str,
    target_type_def: Union[type, str],
    default_val: Any,
    required: bool = False,
    allow_empty_string: bool = False,
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
) -> Tuple[Any, bool]:
    """
    Validates and retrieves value from a widget.
    For CTkOptionMenu and CTkCheckBox, their associated Tkinter variable must be passed in `tk_var`.
    Returns (value, is_valid_bool). Value will be default_val if validation fails.
    """
    val_str = ""
    is_valid = True
    actual_value = default_val

    if widget is None and tk_var is None:
        logger.error(f"Validation Error: Widget and tk_var for '{field_name_for_error}' are both None.")
        return default_val, not required

    try:
        if isinstance(widget, ctk.CTkTextbox):
            val_str = widget.get("0.0", "end-1c").strip()
        elif isinstance(widget, ctk.CTkEntry):
            val_str = widget.get().strip() # CTkEntry.get() takes no arguments
        elif isinstance(widget, ctk.CTkOptionMenu) and tk_var and isinstance(tk_var, tk.StringVar):
            val_str = tk_var.get()
        elif isinstance(widget, ctk.CTkCheckBox) and tk_var and isinstance(tk_var, tk.BooleanVar):
            actual_value = tk_var.get()
            return actual_value, True
        elif tk_var is not None:
            if isinstance(tk_var, tk.StringVar):
                val_str = tk_var.get()
            elif isinstance(tk_var, tk.BooleanVar):
                return tk_var.get(), True
        else:
            logger.warning(f"Could not get value for '{field_name_for_error}'. Widget type: {type(widget)}, TkVar type: {type(tk_var)}. Using default.")
            if target_type_def == bool:
                 return bool(default_val), True
            val_str = str(default_val)

        if not allow_empty_string and not val_str and required:
            messagebox.showerror("Input Error", f"'{field_name_for_error}' cannot be empty.")
            return default_val, False

        if not val_str and (allow_empty_string or not required):
            actual_value = "" if target_type_def == str and allow_empty_string else default_val
            if not required and not val_str:
                return default_val, True
            return actual_value, True

        if target_type_def == str:
            actual_value = val_str
        elif target_type_def == int:
            actual_value = int(val_str)
        elif target_type_def == float:
            actual_value = float(val_str)
        elif target_type_def == "bgr_string":
            parsed_bgr = parse_bgr_string(val_str, field_name_for_error)
            if parsed_bgr is None:
                return default_val, False
            actual_value = parsed_bgr

        if isinstance(actual_value, (int, float)):
            if min_val is not None and actual_value < min_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be at least {min_val}.")
                is_valid = False
            if max_val is not None and actual_value > max_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be no more than {max_val}.")
                is_valid = False

    except ValueError:
        expected_type_name = target_type_def.__name__ if isinstance(target_type_def, type) else str(target_type_def)
        messagebox.showerror("Input Error", f"Invalid format for '{field_name_for_error}'. Expected {expected_type_name}.")
        is_valid = False
    except TypeError as te: # Specifically catch TypeErrors like the one from CTkEntry.get() if logic was still wrong
        messagebox.showerror("Input Error", f"Type error validating '{field_name_for_error}': {te}")
        logger.error(f"Type error validating '{field_name_for_error}': {te}", exc_info=True)
        is_valid = False
    except Exception as e:
        messagebox.showerror("Input Error", f"Unexpected error validating '{field_name_for_error}': {e}")
        logger.error(f"Unexpected validation error for '{field_name_for_error}': {e}", exc_info=True)
        is_valid = False

    return actual_value if is_valid else default_val, is_valid


def create_clickable_list_item(parent_frame: ctk.CTkScrollableFrame, text: str, on_click_callback: Callable) -> ctk.CTkFrame:
    item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent", corner_radius=0)
    item_frame.pack(fill="x", pady=1, padx=1)
    label = ctk.CTkLabel(item_frame, text=text, anchor="w", cursor="hand2")
    label.pack(side="left", fill="x", expand=True, padx=5, pady=2)
    label.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
    item_frame.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
    return item_frame