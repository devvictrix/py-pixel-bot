import pytest
from tkinter import messagebox, Tk
import tkinter as tk # Added import
from unittest.mock import patch, MagicMock

from mark_i.ui.gui.gui_utils import parse_bgr_string, validate_and_get_widget_value
import customtkinter as ctk

# --- Tests for parse_bgr_string ---
@pytest.fixture(scope="module")
def tk_root_for_messagebox():
    root = Tk()
    root.withdraw()
    yield root
    root.destroy()

def test_parse_bgr_string_valid(tk_root_for_messagebox):
    assert parse_bgr_string("255,0,128", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) == [255, 0, 128]
    assert parse_bgr_string(" 10 , 20 , 30 ", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) == [10, 20, 30]

def test_parse_bgr_string_invalid_format_not_enough_parts(tk_root_for_messagebox):
    with patch.object(messagebox, "showerror") as mock_showerror:
        assert parse_bgr_string("255,0", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None
        mock_showerror.assert_called_once()
        args, _ = mock_showerror.call_args
        assert "Invalid BGR format" in args[1]
        assert args[2] == tk_root_for_messagebox # Check parent passed

def test_parse_bgr_string_invalid_format_too_many_parts(tk_root_for_messagebox):
    with patch.object(messagebox, "showerror") as mock_showerror:
        assert parse_bgr_string("255,0,128,50", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None
        mock_showerror.assert_called_once()
        args, _ = mock_showerror.call_args
        assert "Invalid BGR format" in args[1]
        assert args[2] == tk_root_for_messagebox

def test_parse_bgr_string_non_numeric_parts(tk_root_for_messagebox):
    with patch.object(messagebox, "showerror") as mock_showerror:
        assert parse_bgr_string("255,abc,128", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None
        mock_showerror.assert_called_once()
        args, _ = mock_showerror.call_args
        assert "Invalid characters in BGR string" in args[1]
        assert args[2] == tk_root_for_messagebox

def test_parse_bgr_string_values_out_of_range(tk_root_for_messagebox):
    with patch.object(messagebox, "showerror") as mock_showerror:
        assert parse_bgr_string("256,0,128", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None
        mock_showerror.assert_called_once()
        args, _ = mock_showerror.call_args
        assert "Invalid BGR values" in args[1]
        assert args[2] == tk_root_for_messagebox

    mock_showerror.reset_mock() # Reset for next call
    with patch.object(messagebox, "showerror") as mock_showerror_neg: # Use new mock object for isolation
        assert parse_bgr_string("-10,0,128", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None
        mock_showerror_neg.assert_called_once()
        args_neg, _ = mock_showerror_neg.call_args
        assert "Invalid BGR values" in args_neg[1]
        assert args_neg[2] == tk_root_for_messagebox

def test_parse_bgr_string_empty_string(tk_root_for_messagebox):
    with patch.object(messagebox, "showerror") as mock_showerror:
        assert parse_bgr_string("", "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None
        mock_showerror.assert_called_once()
        args, _ = mock_showerror.call_args
        assert "Invalid BGR format" in args[1]
        assert args[2] == tk_root_for_messagebox

def test_parse_bgr_string_invalid_input_type(tk_root_for_messagebox):
    with patch.object(messagebox, "showerror") as mock_showerror:
        assert parse_bgr_string(123, "TestField", parent_widget_for_msgbox=tk_root_for_messagebox) is None # type: ignore
        mock_showerror.assert_called_once()
        args, _ = mock_showerror.call_args
        assert "Invalid input type for BGR string" in args[1]
        assert args[2] == tk_root_for_messagebox

# --- Tests for validate_and_get_widget_value ---
@pytest.fixture
def mock_ctk_entry():
    class MockEntry:
        _widget_name = 'CTkEntry' # For validate_and_get_widget_value to identify
        def __init__(self, text=""): self._text = text
        def get(self): return self._text
        def winfo_exists(self): return True
        def winfo_ismapped(self): return True
    return MockEntry

@pytest.fixture
def mock_ctk_textbox():
    class MockTextbox:
        _widget_name = 'CTkTextbox' # For validate_and_get_widget_value
        def __init__(self, text=""): self._text = text
        def get(self, start, end): return self._text
        def winfo_exists(self): return True
        def winfo_ismapped(self): return True
    return MockTextbox

def test_validate_get_value_entry_string_valid(mock_ctk_entry):
    entry = mock_ctk_entry("hello world")
    value, is_valid = validate_and_get_widget_value(entry, None, "String Field", str, "")
    assert value == "hello world"
    assert is_valid is True

def test_validate_get_value_entry_string_empty_not_required(mock_ctk_entry):
    entry = mock_ctk_entry("")
    value, is_valid = validate_and_get_widget_value(entry, None, "Optional String", str, "default", required=False)
    assert value == "default"
    assert is_valid is True

def test_validate_get_value_entry_string_empty_required_not_allowed(mock_ctk_entry, tk_root_for_messagebox):
    entry = mock_ctk_entry("")
    with patch.object(messagebox, "showerror") as mock_showerror:
        value, is_valid = validate_and_get_widget_value(entry, None, "Required String", str, "default_on_fail", required=True, allow_empty_string=False)
        assert value == "default_on_fail"
        assert is_valid is False
        mock_showerror.assert_called_once_with("Input Error", "'Required String' cannot be empty.", parent=entry)

def test_validate_get_value_entry_string_empty_required_allowed(mock_ctk_entry):
    entry = mock_ctk_entry("")
    value, is_valid = validate_and_get_widget_value(entry, None, "Required Empty String", str, "def", required=True, allow_empty_string=True)
    assert value == ""
    assert is_valid is True

def test_validate_get_value_entry_int_valid(mock_ctk_entry):
    entry = mock_ctk_entry("123")
    value, is_valid = validate_and_get_widget_value(entry, None, "Int Field", int, 0)
    assert value == 123
    assert is_valid is True

def test_validate_get_value_entry_int_invalid_format(mock_ctk_entry, tk_root_for_messagebox):
    entry = mock_ctk_entry("abc")
    with patch.object(messagebox, "showerror") as mock_showerror:
        value, is_valid = validate_and_get_widget_value(entry, None, "Int Field", int, 0)
        assert value == 0
        assert is_valid is False # is_valid should be False
        mock_showerror.assert_called_once() # messagebox should be shown

def test_validate_get_value_entry_int_with_float_string(mock_ctk_entry):
    entry = mock_ctk_entry("123.0")
    value, is_valid = validate_and_get_widget_value(entry, None, "Int Field from Float Str", int, 0)
    assert value == 123
    assert is_valid is True

def test_validate_get_value_entry_float_valid(mock_ctk_entry):
    entry = mock_ctk_entry("123.45")
    value, is_valid = validate_and_get_widget_value(entry, None, "Float Field", float, 0.0)
    assert value == 123.45
    assert is_valid is True

def test_validate_get_value_entry_bgr_string_valid(mock_ctk_entry, tk_root_for_messagebox):
    entry = mock_ctk_entry("10,20,30")
    with patch("mark_i.ui.gui.gui_utils.parse_bgr_string", return_value=[10, 20, 30]) as mock_parse_bgr:
        value, is_valid = validate_and_get_widget_value(entry, None, "BGR Field", "bgr_string", [0,0,0])
        assert value == [10, 20, 30]
        assert is_valid is True
        # The parent argument to parse_bgr_string should be the widget itself.
        mock_parse_bgr.assert_called_once_with("10,20,30", "BGR Field", parent_widget_for_msgbox=entry)

def test_validate_get_value_optionmenu_string(tk_root_for_messagebox):
    str_var = tk.StringVar(value="Option2")
    mock_optionmenu_widget = MagicMock(spec=ctk.CTkOptionMenu); mock_optionmenu_widget.winfo_exists.return_value = True
    value, is_valid = validate_and_get_widget_value(mock_optionmenu_widget, str_var, "Option Field", str, "DefaultOption")
    assert value == "Option2"; assert is_valid is True

def test_validate_get_value_checkbox_bool(tk_root_for_messagebox):
    bool_var = tk.BooleanVar(value=True)
    mock_checkbox_widget = MagicMock(spec=ctk.CTkCheckBox); mock_checkbox_widget.winfo_exists.return_value = True
    value, is_valid = validate_and_get_widget_value(mock_checkbox_widget, bool_var, "Checkbox Field", bool, False)
    assert value is True; assert is_valid is True

def test_validate_get_value_list_str_csv_valid(mock_ctk_entry):
    entry = mock_ctk_entry(" one ,two, three ")
    value, is_valid = validate_and_get_widget_value(entry, None, "CSV List Field", "list_str_csv", [])
    assert value == ["one", "two", "three"]; assert is_valid is True

def test_validate_get_value_list_str_csv_empty(mock_ctk_entry):
    entry = mock_ctk_entry("  ")
    value, is_valid = validate_and_get_widget_value(entry, None, "CSV List Field", "list_str_csv", ["default"])
    assert value == [] ; assert is_valid is True

def test_validate_get_value_entry_int_bounds_check(mock_ctk_entry, tk_root_for_messagebox):
    entry_low = mock_ctk_entry("5")
    with patch.object(messagebox, "showerror") as mock_showerror_low:
        value, is_valid = validate_and_get_widget_value(entry_low, None, "Bounded Int", int, 15, min_val=10, max_val=20)
        assert value == 15 # Returns default on failure
        assert is_valid is False # is_valid should be False
        mock_showerror_low.assert_called_once()
        assert "must be at least 10" in mock_showerror_low.call_args[0][1]

    entry_high = mock_ctk_entry("25")
    with patch.object(messagebox, "showerror") as mock_showerror_high:
        value, is_valid = validate_and_get_widget_value(entry_high, None, "Bounded Int", int, 15, min_val=10, max_val=20)
        assert value == 15 # Returns default on failure
        assert is_valid is False # is_valid should be False
        mock_showerror_high.assert_called_once()
        assert "must be no more than 20" in mock_showerror_high.call_args[0][1]

    entry_valid = mock_ctk_entry("15")
    value, is_valid = validate_and_get_widget_value(entry_valid, None, "Bounded Int", int, 0, min_val=10, max_val=20)
    assert value == 15; assert is_valid is True