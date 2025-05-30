// File: tests/ui/gui/test_gui_utils.py
import pytest
from unittest.mock import patch, MagicMock

# Import the function to be tested
from mark_i.ui.gui.gui_utils import parse_bgr_string

# We need a way to get a parent for messagebox, or mock it effectively.
# For unit tests, it's best to mock messagebox entirely.

@patch('tkinter.messagebox.showerror') # Mock the showerror function
def test_parse_bgr_string_valid_input(mock_showerror: MagicMock):
    """Test with valid BGR strings."""
    assert parse_bgr_string("255,0,128", "TestField") == [255, 0, 128]
    assert parse_bgr_string("0,0,0", "TestField") == [0, 0, 0]
    assert parse_bgr_string(" 10 , 20 , 30 ", "TestField") == [10, 20, 30] # Test with spaces
    mock_showerror.assert_not_called()

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_invalid_format_not_enough_parts(mock_showerror: MagicMock):
    """Test with BGR strings that don't have exactly 3 parts."""
    assert parse_bgr_string("255,0", "TestField") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR format" in mock_showerror.call_args[0][1] # Check error message content
    mock_showerror.reset_mock()

    assert parse_bgr_string("255,0,128,100", "TestField") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR format" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_invalid_format_non_numeric(mock_showerror: MagicMock):
    """Test with BGR strings containing non-numeric parts."""
    assert parse_bgr_string("255,abc,128", "TestField") is None
    mock_showerror.assert_called_once()
    assert "Invalid characters in BGR string" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("255,0.5,128", "TestField") is None # Decimals should also fail int conversion here
    mock_showerror.assert_called_once()
    assert "Invalid characters in BGR string" in mock_showerror.call_args[0][1]


@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_value_out_of_range(mock_showerror: MagicMock):
    """Test with BGR values out of the 0-255 range."""
    assert parse_bgr_string("256,0,128", "TestField") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR values" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string("-10,0,128", "TestField") is None
    mock_showerror.assert_called_once()
    assert "Invalid BGR values" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_empty_string(mock_showerror: MagicMock):
    """Test with an empty BGR string."""
    # According to implementation, parse_bgr_string itself doesn't handle empty string check
    # before split. `split` on empty string results in `['']`.
    # `int('')` raises ValueError.
    assert parse_bgr_string("", "TestField") is None
    mock_showerror.assert_called_once()
    # The error message depends on how int('') is caught vs len(parts_str) != 3
    # In current impl, `int('')` fails:
    assert "Invalid characters in BGR string" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_non_string_input(mock_showerror: MagicMock):
    """Test with non-string input types."""
    assert parse_bgr_string(None, "TestField") is None # type: ignore
    mock_showerror.assert_called_once()
    assert "Invalid input type for BGR string" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string(123, "TestField") is None # type: ignore
    mock_showerror.assert_called_once()
    assert "Invalid input type for BGR string" in mock_showerror.call_args[0][1]
    mock_showerror.reset_mock()

    assert parse_bgr_string([255,0,0], "TestField") is None # type: ignore
    mock_showerror.assert_called_once()
    assert "Invalid input type for BGR string" in mock_showerror.call_args[0][1]

@patch('tkinter.messagebox.showerror')
def test_parse_bgr_string_field_name_in_error(mock_showerror: MagicMock):
    """Test that the field_name_for_error appears in the error message."""
    custom_field_name = "MyCustomBGRField"
    parse_bgr_string("invalid,string", custom_field_name)
    mock_showerror.assert_called_once()
    args, _ = mock_showerror.call_args
    # args[0] is title, args[1] is message
    assert custom_field_name in args[1], "Field name should be in the error message"