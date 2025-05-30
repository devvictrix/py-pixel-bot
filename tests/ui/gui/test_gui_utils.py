import pytest
from unittest.mock import patch, MagicMock

# Import the function to be tested
from mark_i.ui.gui.gui_utils import parse_bgr_string, validate_and_get_widget_value # Added validate_and_get_widget_value

# --- Tests for parse_bgr_string (Enhanced) ---

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_valid_input(mock_showerror: MagicMock):
    """Test with valid BGR strings."""
    assert parse_bgr_string("255,0,128", "TestField") == [255, 0, 128]
    assert parse_bgr_string("0,0,0", "TestField") == [0, 0, 0]
    assert parse_bgr_string(" 10 , 20 , 30 ", "TestField") == [10, 20, 30]
    assert parse_bgr_string("255, 255, 255", "TestField") == [255, 255, 255]
    mock_showerror.assert_not_called()

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_invalid_format_parts_count(mock_showerror: MagicMock):
    """Test with BGR strings that don't have exactly 3 parts."""
    assert parse_bgr_string("255,0", "Field1") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR format" in mock_showerror.call_args[0][1] and "Field1" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("255,0,128,100", "Field2") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR format" in mock_showerror.call_args[0][1] and "Field2" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("255,,0", "Field3") is None # Empty part
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1] and "Field3" in mock_showerror.call_args[0][1] # int('') fails
    mock_showerror.reset_mock()

    assert parse_bgr_string(",255,0", "FieldLeadingComma") is None
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("255,0,", "FieldTrailingComma") is None
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("255, ,0", "FieldSpaceAsPart") is None # Space as a part
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_invalid_format_non_numeric(mock_showerror: MagicMock):
    """Test with BGR strings containing non-numeric parts."""
    assert parse_bgr_string("255,abc,128", "FieldAlpha") is None
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1] and "FieldAlpha" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("255,0.5,128", "FieldFloat") is None # int(float_string) would work, but int("0.5") fails
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1] and "FieldFloat" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_value_out_of_range(mock_showerror: MagicMock):
    """Test with BGR values out of the 0-255 range."""
    assert parse_bgr_string("256,0,128", "FieldHigh") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR values" in mock_showerror.call_args[0][1] and "FieldHigh" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("-10,0,128", "FieldLow") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR values" in mock_showerror.call_args[0][1] and "FieldLow" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("0,300,0", "FieldMidHigh") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR values" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_empty_string(mock_showerror: MagicMock):
    """Test with an empty BGR string."""
    assert parse_bgr_string("", "FieldEmpty") is None
    mock_showerror.assert_called_once()
    assert "Invalid characters" in mock_showerror.call_args[0][1] and "FieldEmpty" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_whitespace_string(mock_showerror: MagicMock):
    """Test with a whitespace-only BGR string."""
    assert parse_bgr_string("   ", "FieldWhitespace") is None
    mock_showerror.assert_called_once()
    # Depending on strip, this might lead to "Invalid characters" if int('') is attempted,
    # or "Invalid BGR format" if split results in e.g. ['   '] and int('   ') fails.
    # Current implementation: int('   ') raises ValueError -> "Invalid characters"
    assert "Invalid characters" in mock_showerror.call_args[0][1] and "FieldWhitespace" in mock_showerror.call_args[0][1]


@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_non_string_input(mock_showerror: MagicMock):
    """Test with non-string input types."""
    assert parse_bgr_string(None, "FieldNone") is None # type: ignore
    mock_showerror.assert_called_once_with("BGR Format Error", "Invalid input type for BGR string for 'FieldNone'. Expected string.", parent=None) # Assuming get_tk_parent returns None
    mock_showerror.reset_mock()

    assert parse_bgr_string(123, "FieldNumber") is None # type: ignore
    mock_showerror.assert_called_once_with("BGR Format Error", "Invalid input type for BGR string for 'FieldNumber'. Expected string.", parent=None)
    mock_showerror.reset_mock()

    assert parse_bgr_string([255,0,0], "FieldList") is None # type: ignore
    mock_showerror.assert_called_once_with("BGR Format Error", "Invalid input type for BGR string for 'FieldList'. Expected string.", parent=None)

# --- Placeholder for validate_and_get_widget_value tests (to be added later) ---
# These would require mocking CTk widgets and tk.StringVar/BooleanVar, which is more involved.
# For now, we assume parse_bgr_string is the main utility function from this file to test in isolation.

# @patch('tkinter.messagebox.showerror')
# class TestValidateAndGetWidgetValue:
#     # Example:
#     # def test_entry_valid_int(self, mock_showerror):
#     #     mock_entry = MagicMock(spec=ctk.CTkEntry)
#     #     mock_entry.get.return_value = "123"
#     #     value, is_valid = validate_and_get_widget_value(mock_entry, None, "Test Int", int, 0, required=True)
#     #     assert is_valid is True
#     #     assert value == 123
#     #     mock_showerror.assert_not_called()
#     pass