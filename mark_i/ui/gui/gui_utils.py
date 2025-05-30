import logging
import tkinter as tk
from tkinter import messagebox
from typing import Any, Optional, List, Union, Tuple, Callable

import customtkinter as ctk

# Use __name__ for module-level logger
logger = logging.getLogger(__name__)


def parse_bgr_string(bgr_str: str, field_name_for_error: str) -> Optional[List[int]]:
    """
    Parses a 'B,G,R' string (e.g., "255,0,128") into a list of 3 integers.
    Returns None on failure and shows a messagebox.
    """
    if not isinstance(bgr_str, str):  # Basic type check
        messagebox.showerror(
            "BGR Format Error", f"Invalid input type for BGR string for '{field_name_for_error}'. Expected string.", parent=messagebox.get_tk_parent()
        )  # Try to get parent for messagebox
        return None
    try:
        parts_str = bgr_str.split(",")
        if len(parts_str) != 3:
            messagebox.showerror(
                "BGR Format Error",
                f"Invalid BGR format for '{field_name_for_error}'.\nExpected 3 numbers (0-255) separated by commas (e.g., '255,0,128'). Received: '{bgr_str}'",
                parent=messagebox.get_tk_parent(),
            )
            return None

        parts_int = [int(p.strip()) for p in parts_str]
        if all(0 <= x <= 255 for x in parts_int):
            return parts_int
        else:
            messagebox.showerror(
                "BGR Value Error", f"Invalid BGR values for '{field_name_for_error}'.\nNumbers must be integers between 0 and 255. Received: {parts_int}", parent=messagebox.get_tk_parent()
            )
            return None
    except ValueError:  # Handles int() conversion failure
        messagebox.showerror(
            "BGR Conversion Error",
            f"Invalid characters in BGR string for '{field_name_for_error}'.\nEnsure only numbers and commas are used (e.g., '255,0,128'). Received: '{bgr_str}'",
            parent=messagebox.get_tk_parent(),
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

    # Attempt to get parent for messagebox if widget exists
    msg_box_parent = widget if widget and widget.winfo_exists() else messagebox.get_tk_parent()

    # 1. Get the raw value based on widget type or tk_var
    if isinstance(widget, ctk.CTkTextbox):
        val_str_from_widget = widget.get("0.0", "end-1c").strip()
    elif isinstance(widget, ctk.CTkEntry):
        val_str_from_widget = widget.get().strip()
    elif isinstance(tk_var, tk.StringVar):  # Primarily for CTkOptionMenu
        val_str_from_widget = tk_var.get()  # OptionMenu value is string
    elif isinstance(tk_var, tk.BooleanVar):  # Primarily for CTkCheckBox
        final_value_to_return = tk_var.get()
        return final_value_to_return, True  # Boolean directly from var, always valid type-wise
    elif widget is None and tk_var is None:  # Should not happen if UI config is correct
        logger.error(f"Validation Error: Widget and tk_var for '{field_name_for_error}' are both None.")
        if required:
            return default_val, False  # Invalid if required and no widget
        return default_val, True  # Not required, no widget, use default, consider valid
    else:  # Fallback if widget type not directly handled, or only widget was passed for OptionMenu/CheckBox
        logger.warning(f"Could not reliably get value for '{field_name_for_error}'. Widget type: {type(widget)}, TkVar type: {type(tk_var)}. Attempting str(default_val).")
        if target_type_def == bool:
            return bool(default_val), True  # Assume default is okay for bool
        val_str_from_widget = str(default_val)  # Fallback to string of default

    # 2. Handle empty string cases based on 'required' and 'allow_empty_string'
    if not val_str_from_widget:  # Empty string after stripping
        if required and not allow_empty_string:
            messagebox.showerror("Input Error", f"'{field_name_for_error}' cannot be empty.", parent=msg_box_parent)
            return default_val, False  # Invalid
        elif required and allow_empty_string:  # Required but empty string is allowed
            final_value_to_return = ""  # Return empty string
            return final_value_to_return, True  # Valid
        else:  # Not required and empty
            return default_val, True  # Valid, return default (could be "" or None based on type)

    # 3. Convert and validate non-empty string to target type
    try:
        if target_type_def == str:
            final_value_to_return = val_str_from_widget
        elif target_type_def == int:
            final_value_to_return = int(float(val_str_from_widget))  # int(float()) handles "10.0" -> 10
        elif target_type_def == float:
            final_value_to_return = float(val_str_from_widget)
        elif target_type_def == "bgr_string":
            parsed_bgr = parse_bgr_string(val_str_from_widget, field_name_for_error)
            if parsed_bgr is None:
                return default_val, False  # parse_bgr_string shows its own messagebox
            final_value_to_return = parsed_bgr
        elif target_type_def == "list_str_csv":  # Expects string from widget, converts to list
            if val_str_from_widget:  # Only split if not empty
                final_value_to_return = [s.strip() for s in val_str_from_widget.split(",") if s.strip()]
            else:  # Empty string for list_str_csv means empty list
                final_value_to_return = []
        elif target_type_def == bool:  # Should have been handled by BooleanVar path
            final_value_to_return = val_str_from_widget.lower() in ["true", "1", "yes", "on"]
        else:  # Unknown target type
            logger.error(f"Unknown target_type_def '{target_type_def}' for field '{field_name_for_error}'.")
            return default_val, False  # Invalid

        # Numeric bounds check (only if conversion succeeded and value is numeric)
        if isinstance(final_value_to_return, (int, float)):
            if min_val is not None and final_value_to_return < min_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be at least {min_val}. Value: {final_value_to_return}", parent=msg_box_parent)
                is_valid = False
            if max_val is not None and final_value_to_return > max_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be no more than {max_val}. Value: {final_value_to_return}", parent=msg_box_parent)
                is_valid = False

    except ValueError:  # Handles int()/float() conversion errors
        expected_type_name = target_type_def.__name__ if isinstance(target_type_def, type) else str(target_type_def)
        messagebox.showerror("Input Error", f"Invalid format for '{field_name_for_error}'. Expected {expected_type_name}. Received: '{val_str_from_widget}'", parent=msg_box_parent)
        is_valid = False
    except Exception as e_unexpected:  # Catch any other unexpected errors
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
    # Use pack for items within a CTkScrollableFrame
    item_frame.pack(fill="x", pady=(1, 1), padx=(1, 1))

    label_fg_color = ("gray10", "gray90") if text_color is None else text_color  # Default text colors

    label = ctk.CTkLabel(item_frame, text=text, anchor="w", cursor="hand2", text_color=label_fg_color)
    label.pack(side="left", fill="x", expand=True, padx=5, pady=2)

    # Make both the label and its containing frame clickable
    # Pass lambda e (event) to the callback if it expects it, otherwise call directly.
    # Assuming callback doesn't need the event object itself.
    label.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
    item_frame.bind("<Button-1>", lambda e, cb=on_click_callback: cb())

    return item_frame
