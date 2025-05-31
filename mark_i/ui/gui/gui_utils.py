import logging
import tkinter as tk
from tkinter import messagebox
from typing import Any, Optional, List, Union, Tuple, Callable

import customtkinter as ctk

# Use __name__ for module-level logger
logger = logging.getLogger(__name__)


def parse_bgr_string(bgr_str: str, field_name_for_error: str, parent_widget_for_msgbox: Optional[Any] = None) -> Optional[List[int]]:
    """
    Parses a 'B,G,R' string (e.g., "255,0,128") into a list of 3 integers.
    Returns None on failure and shows a messagebox.
    """
    if not isinstance(bgr_str, str):  # Basic type check
        messagebox.showerror(
            "BGR Format Error", f"Invalid input type for BGR string for '{field_name_for_error}'. Expected string.", parent=parent_widget_for_msgbox
        )
        return None
    try:
        parts_str = bgr_str.split(",")
        if len(parts_str) != 3:
            messagebox.showerror(
                "BGR Format Error",
                f"Invalid BGR format for '{field_name_for_error}'.\nExpected 3 numbers (0-255) separated by commas (e.g., '255,0,128'). Received: '{bgr_str}'",
                parent=parent_widget_for_msgbox,
            )
            return None

        parts_int = [int(p.strip()) for p in parts_str]
        if all(0 <= x <= 255 for x in parts_int):
            return parts_int
        else:
            messagebox.showerror(
                "BGR Value Error", f"Invalid BGR values for '{field_name_for_error}'.\nNumbers must be integers between 0 and 255. Received: {parts_int}", parent=parent_widget_for_msgbox
            )
            return None
    except ValueError:  # Handles int() conversion failure
        messagebox.showerror(
            "BGR Conversion Error",
            f"Invalid characters in BGR string for '{field_name_for_error}'.\nEnsure only numbers and commas are used (e.g., '255,0,128'). Received: '{bgr_str}'",
            parent=parent_widget_for_msgbox,
        )
        return None


def validate_and_get_widget_value(
    widget: Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox, None],
    tk_var: Optional[Union[tk.StringVar, tk.BooleanVar]],  # tk_var is primary for OptionMenu/CheckBox
    field_name_for_error: str,  # User-friendly name for error messages
    target_type_def: Union[type, str],  # Python type (int, float, str, bool) or custom string like "bgr_string", "list_str_csv"
    default_val: Any,  # Default value to return on validation failure or if not required and empty
    required: bool = False,
    allow_empty_string: bool = False,  # For str type, if "" is a valid value even if required=True
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
) -> Tuple[Any, bool]:
    """
    Validates and retrieves value from a CustomTkinter widget or its associated Tkinter variable.
    Returns (value, is_valid_bool). Value will be default_val if validation fails and required,
    or the successfully converted value. If not required and empty, returns default_val.
    Shows messageboxes on validation errors.
    """
    val_str_from_widget = ""  # For Entry/Textbox/OptionMenu string value
    is_valid = True
    final_value_to_return = default_val  # Start with default

    msg_box_parent = widget if widget and widget.winfo_exists() else messagebox.get_tk_parent()

    widget_class_name = ""
    if hasattr(widget, '_widget_name'): # For mocks like MockEntry
        widget_class_name = widget._widget_name
    elif isinstance(widget, ctk.CTkEntry):
        widget_class_name = "CTkEntry"
    elif isinstance(widget, ctk.CTkTextbox):
        widget_class_name = "CTkTextbox"
    # CTkOptionMenu and CTkCheckBox are typically handled by tk_var

    if widget_class_name == "CTkTextbox":
        val_str_from_widget = widget.get("0.0", "end-1c").strip() # type: ignore
    elif widget_class_name == "CTkEntry": # Handles mock_ctk_entry as well
        val_str_from_widget = widget.get().strip() # type: ignore
    elif isinstance(tk_var, tk.StringVar):  # Primarily for CTkOptionMenu
        val_str_from_widget = tk_var.get()  # OptionMenu value is string
    elif isinstance(tk_var, tk.BooleanVar):  # Primarily for CTkCheckBox
        final_value_to_return = tk_var.get()
        return final_value_to_return, True  # Boolean directly from var, always valid type-wise
    elif widget is None and tk_var is None:
        logger.error(f"Validation Error: Widget and tk_var for '{field_name_for_error}' are both None.")
        if required: return default_val, False
        return default_val, True
    else:
        logger.warning(f"Could not reliably get value for '{field_name_for_error}'. Widget type: {type(widget)}, TkVar type: {type(tk_var)}. Attempting str(default_val).")
        if target_type_def == bool: return bool(default_val), True
        val_str_from_widget = str(default_val)

    if target_type_def == "list_str_csv":
        if val_str_from_widget:
            final_value_to_return = [s.strip() for s in val_str_from_widget.split(",") if s.strip()]
        else:
            final_value_to_return = [] # Empty string for list_str_csv becomes empty list

        if required and not allow_empty_string and not final_value_to_return:
            messagebox.showerror("Input Error", f"'{field_name_for_error}' (as list) cannot be empty.", parent=msg_box_parent)
            return default_val, False
        return final_value_to_return, True

    if not val_str_from_widget:
        if required and not allow_empty_string:
            messagebox.showerror("Input Error", f"'{field_name_for_error}' cannot be empty.", parent=msg_box_parent)
            return default_val, False
        elif required and allow_empty_string:
            final_value_to_return = "" if target_type_def == str else default_val
            return final_value_to_return, True
        else:
            return default_val, True

    try:
        if target_type_def == str:
            final_value_to_return = val_str_from_widget
        elif target_type_def == int:
            final_value_to_return = int(float(val_str_from_widget))
        elif target_type_def == float:
            final_value_to_return = float(val_str_from_widget)
        elif target_type_def == "bgr_string":
            # Pass the widget itself as parent for messagebox
            parsed_bgr = parse_bgr_string(val_str_from_widget, field_name_for_error, parent_widget_for_msgbox=widget)
            if parsed_bgr is None:
                return default_val, False
            final_value_to_return = parsed_bgr
        elif target_type_def == bool:
            final_value_to_return = val_str_from_widget.lower() in ["true", "1", "yes", "on"]
        else:
            logger.error(f"Unknown target_type_def '{target_type_def}' for field '{field_name_for_error}'.")
            return default_val, False

        if isinstance(final_value_to_return, (int, float)):
            if min_val is not None and final_value_to_return < min_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be at least {min_val}. Value: {final_value_to_return}", parent=msg_box_parent)
                is_valid = False
            if max_val is not None and final_value_to_return > max_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be no more than {max_val}. Value: {final_value_to_return}", parent=msg_box_parent)
                is_valid = False
    except ValueError:
        expected_type_name = target_type_def.__name__ if isinstance(target_type_def, type) else str(target_type_def)
        messagebox.showerror("Input Error", f"Invalid format for '{field_name_for_error}'. Expected {expected_type_name}. Received: '{val_str_from_widget}'", parent=msg_box_parent)
        is_valid = False
    except Exception as e_unexpected:
        messagebox.showerror("Validation Error", f"Unexpected error validating '{field_name_for_error}': {e_unexpected}", parent=msg_box_parent)
        logger.error(f"Unexpected validation error for '{field_name_for_error}': {e_unexpected}", exc_info=True)
        is_valid = False

    return final_value_to_return if is_valid else default_val, is_valid


def create_clickable_list_item(parent_frame: ctk.CTkScrollableFrame, text: str, on_click_callback: Callable, text_color: Optional[str] = None) -> ctk.CTkFrame:
    """
    Creates a clickable item (a CTkFrame with a CTkLabel) for a list.
    The entire frame and the label within it are bound to the on_click_callback.
    """
    item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent", corner_radius=0)
    item_frame.pack(fill="x", pady=(1, 1), padx=(1, 1))

    label_fg_color = ("gray10", "gray90") if text_color is None else text_color

    label = ctk.CTkLabel(item_frame, text=text, anchor="w", cursor="hand2", text_color=label_fg_color)
    label.pack(side="left", fill="x", expand=True, padx=5, pady=2)

    label.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
    item_frame.bind("<Button-1>", lambda e, cb=on_click_callback: cb())

    return item_frame