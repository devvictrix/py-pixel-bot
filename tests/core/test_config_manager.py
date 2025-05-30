// File: tests/core/test_config_manager.py
import os
import pytest
import json
from unittest import mock # For more complex mocking if needed later

from mark_i.core.config_manager import ConfigManager
from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE # For comparison

# Define a fixed project root for testing path resolution consistently
TEST_PROJECT_ROOT = "/test_project_root_dir" # Use a clearly distinct dummy path
EXPECTED_PROFILES_DIR = os.path.join(TEST_PROJECT_ROOT, "profiles")


@pytest.fixture
def mock_project_root(monkeypatch):
    """Fixture to mock ConfigManager._find_project_root() for consistent path testing."""
    monkeypatch.setattr(ConfigManager, "_find_project_root", lambda self: TEST_PROJECT_ROOT)

@pytest.fixture
def mock_os_path_for_abs(monkeypatch):
    """Fixture to mock os.path.isabs for testing absolute path logic."""
    # This needs to be more nuanced if we test both abs and rel paths in one go
    # For now, let's assume a simple mock for a specific test.
    # A more robust way would be a callable mock.
    pass # Will apply specific os.path mocks within tests as needed

def test_config_manager_init_create_if_missing_no_path(mock_project_root):
    """Test ConfigManager initialization with create_if_missing=True and no path provided."""
    cm = ConfigManager(profile_path_or_name=None, create_if_missing=True)
    assert cm.profile_path is None, "Profile path should be None for a new, unsaved profile"
    assert cm.get_profile_name() == "Unsaved Profile", "Profile name should be 'Unsaved Profile'"
    # Check if the profile_data is initialized with the default structure
    # We need to be careful about comparing mutable defaults directly.
    # DEFAULT_PROFILE_STRUCTURE itself might be imported and used by ConfigManager.
    # For this test, we check that the structure is not empty and contains key elements.
    assert "profile_description" in cm.profile_data
    assert "settings" in cm.profile_data
    assert "regions" in cm.profile_data
    assert "templates" in cm.profile_data
    assert "rules" in cm.profile_data
    assert cm.profile_data["settings"]["monitoring_interval_seconds"] == DEFAULT_PROFILE_STRUCTURE["settings"]["monitoring_interval_seconds"]

def test_config_manager_init_with_non_existent_profile_and_create_false(mock_project_root, monkeypatch):
    """Test ConfigManager initialization with a non-existent profile path when create_if_missing is False."""
    non_existent_profile = "non_existent_profile_for_test.json"
    # Ensure os.path.exists returns False for this specific path resolution
    # The path will be resolved to TEST_PROJECT_ROOT/profiles/non_existent_profile_for_test.json
    expected_full_path = os.path.join(EXPECTED_PROFILES_DIR, non_existent_profile)
    monkeypatch.setattr(os.path, "exists", lambda path_arg: path_arg != expected_full_path)

    with pytest.raises(FileNotFoundError) as excinfo:
        ConfigManager(profile_path_or_name=non_existent_profile, create_if_missing=False)
    assert str(excinfo.value).startswith(f"Profile file not found: {expected_full_path}")

def test_config_manager_init_with_non_existent_profile_and_create_true(mock_project_root, monkeypatch):
    """Test ConfigManager initialization with a non-existent profile path when create_if_missing is True."""
    non_existent_profile_name = "new_profile_to_create"
    expected_full_path = os.path.join(EXPECTED_PROFILES_DIR, f"{non_existent_profile_name}.json")

    # Mock os.path.exists to always return False for the initial check
    monkeypatch.setattr(os.path, "exists", lambda path_arg: False)

    cm = ConfigManager(profile_path_or_name=non_existent_profile_name, create_if_missing=True)
    assert cm.profile_path == expected_full_path, "Profile path should be set to the resolved new path"
    assert "profile_description" in cm.profile_data, "Default data should be initialized"


# --- Tests for _resolve_profile_path ---
# These require more specific monkeypatching of os.path functions

def test_resolve_profile_path_simple_name(monkeypatch):
    """Test resolving a simple profile name (e.g., 'my_bot')."""
    cm = ConfigManager(None, create_if_missing=True) # Create an instance to call method
    monkeypatch.setattr(cm, "_find_project_root", lambda: TEST_PROJECT_ROOT) # Mock instance's root finder

    profile_name = "test_profile"
    expected_path = os.path.abspath(os.path.join(TEST_PROJECT_ROOT, "profiles", f"{profile_name}.json"))
    assert cm._resolve_profile_path(profile_name) == expected_path

def test_resolve_profile_path_simple_name_with_json_ext(monkeypatch):
    """Test resolving a simple profile name with .json extension."""
    cm = ConfigManager(None, create_if_missing=True)
    monkeypatch.setattr(cm, "_find_project_root", lambda: TEST_PROJECT_ROOT)

    profile_name = "test_profile.json"
    expected_path = os.path.abspath(os.path.join(TEST_PROJECT_ROOT, "profiles", profile_name))
    assert cm._resolve_profile_path(profile_name) == expected_path

def test_resolve_profile_path_absolute_unix_path(monkeypatch):
    """Test resolving an absolute Unix-like path."""
    cm = ConfigManager(None, create_if_missing=True)
    # No need to mock _find_project_root if os.path.isabs works as expected
    abs_path = "/an/absolute/path/profile.json"
    monkeypatch.setattr(os.path, "isabs", lambda path_arg: path_arg == abs_path) # Ensure isabs returns True only for this path
    # Ensure other path checks don't interfere by making them return False if they were to be called
    monkeypatch.setattr(os.path, "exists", lambda path_arg: False)

    assert cm._resolve_profile_path(abs_path) == abs_path

@pytest.mark.skipif(os.name != "nt", reason="Windows-specific path test")
def test_resolve_profile_path_absolute_windows_path(monkeypatch):
    """Test resolving an absolute Windows path (run only on Windows)."""
    cm = ConfigManager(None, create_if_missing=True)
    abs_path = "C:\\Users\\Test\\profile.json"
    # On Windows, os.path.isabs should correctly identify this.
    # We rely on the actual os.path.isabs for this OS-specific test.
    # For cross-platform testing of this logic, we'd mock isabs based on path format.
    assert cm._resolve_profile_path(abs_path) == os.path.abspath(abs_path)

def test_resolve_profile_path_relative_to_project_root(monkeypatch):
    """Test resolving a path relative to the project root."""
    cm = ConfigManager(None, create_if_missing=True)
    monkeypatch.setattr(cm, "_find_project_root", lambda: TEST_PROJECT_ROOT)

    relative_path_input = "data/subdir/my_profile.json"
    # Path that _resolve_profile_path will construct to check existence of parent dir
    # os.path.abspath here is important as _resolve_profile_path uses it.
    expected_dir_to_check = os.path.dirname(os.path.abspath(os.path.join(TEST_PROJECT_ROOT, relative_path_input)))

    # Mock os.path.exists to return True only for the specific directory it will check
    def mock_exists_for_rel_project(path_arg):
        return path_arg == expected_dir_to_check

    monkeypatch.setattr(os.path, "exists", mock_exists_for_rel_project)
    monkeypatch.setattr(os.path, "isabs", lambda path_arg: False) # Ensure it's not treated as absolute

    expected_resolved_path = os.path.abspath(os.path.join(TEST_PROJECT_ROOT, relative_path_input))
    assert cm._resolve_profile_path(relative_path_input) == expected_resolved_path

def test_resolve_profile_path_relative_to_cwd_fallback(monkeypatch):
    """Test resolving a path relative to CWD when project-relative fails."""
    cm = ConfigManager(None, create_if_missing=True)
    monkeypatch.setattr(cm, "_find_project_root", lambda: TEST_PROJECT_ROOT)

    relative_path_input = "cwd_data/my_profile.json"
    # Path for project-relative check (this should fail, os.path.exists returns False)
    project_relative_dir_to_check = os.path.dirname(os.path.abspath(os.path.join(TEST_PROJECT_ROOT, relative_path_input)))

    mock_cwd = "/test_current_working_dir"
    monkeypatch.setattr(os, "getcwd", lambda: mock_cwd)

    # Mock os.path.exists: False for project-relative, True for CWD-relative parent (if needed, but _resolve_profile_path doesn't check CWD parent existence explicitly)
    def mock_exists_for_cwd_fallback(path_arg):
        if path_arg == project_relative_dir_to_check:
            return False # Project-relative dir does NOT exist
        # For other paths, we might not care for this specific test's focus on CWD fallback logic itself
        return True # Default to True for other existence checks if any were made.

    monkeypatch.setattr(os.path, "exists", mock_exists_for_cwd_fallback)
    monkeypatch.setattr(os.path, "isabs", lambda path_arg: False)

    expected_resolved_path = os.path.abspath(os.path.join(mock_cwd, relative_path_input))
    assert cm._resolve_profile_path(relative_path_input) == expected_resolved_path

def test_resolve_profile_path_empty_input(monkeypatch):
    """Test _resolve_profile_path with empty string input."""
    cm = ConfigManager(None, create_if_missing=True)
    monkeypatch.setattr(cm, "_find_project_root", lambda: TEST_PROJECT_ROOT)
    expected_path = os.path.abspath(os.path.join(TEST_PROJECT_ROOT, "profiles", "untitled.json"))
    assert cm._resolve_profile_path("") == expected_path
    assert cm._resolve_profile_path("   ") == expected_path # Test with whitespace