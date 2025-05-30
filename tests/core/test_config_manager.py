import os
import pytest
import json
from unittest.mock import patch, mock_open # Ensure mock_open is imported
import copy

from mark_i.core.config_manager import ConfigManager, PROFILES_DIR_NAME, TEMPLATES_SUBDIR_NAME
from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE # For comparison

# Define a fixed project root for testing path resolution consistently
TEST_PROJECT_ROOT = "/test_project_root_dir_for_cm_tests" # Use a clearly distinct dummy path
EXPECTED_PROFILES_DIR_CM = os.path.join(TEST_PROJECT_ROOT, PROFILES_DIR_NAME)


@pytest.fixture
def mock_project_root_cm(monkeypatch):
    """Fixture to mock ConfigManager._find_project_root() for consistent path testing."""
    monkeypatch.setattr(ConfigManager, "_find_project_root", lambda self: TEST_PROJECT_ROOT)
    # Also mock os.makedirs as it's called in __init__
    monkeypatch.setattr(os, "makedirs", lambda path, exist_ok=False: None)


@pytest.fixture
def temp_profile_file(tmp_path_factory, mock_project_root_cm): # Depends on mock_project_root for consistency
    """Creates a temporary valid profile file and returns its ConfigManager instance."""
    profile_dir = tmp_path_factory.mktemp("profiles_temp")
    # Override where ConfigManager thinks the profiles dir is for this specific test context
    ConfigManager.profiles_base_dir = str(profile_dir) # type: ignore

    profile_content = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
    profile_content["profile_description"] = "Test Profile Loaded"
    profile_content["settings"]["monitoring_interval_seconds"] = 5.0
    profile_content["regions"].append({"name": "region1", "x":1, "y":2, "width":3, "height":4, "comment": "c1"})

    file_path = profile_dir / "test_profile_to_load.json"
    with open(file_path, "w") as f:
        json.dump(profile_content, f)

    original_find_project_root = ConfigManager._find_project_root
    ConfigManager._find_project_root = lambda self: str(tmp_path_factory.getbasetemp().parent) # type: ignore

    cm = ConfigManager(str(file_path))

    ConfigManager._find_project_root = original_find_project_root # type: ignore
    ConfigManager.profiles_base_dir = EXPECTED_PROFILES_DIR_CM 

    return cm, profile_content, str(file_path)


# --- Initialization Tests (Enhanced) ---

def test_config_manager_init_create_if_missing_no_path(mock_project_root_cm):
    cm = ConfigManager(profile_path_or_name=None, create_if_missing=True)
    assert cm.profile_path is None
    assert cm.get_profile_name() == "Unsaved Profile"
    assert cm.profile_data == DEFAULT_PROFILE_STRUCTURE

def test_config_manager_init_non_existent_profile_create_false(mock_project_root_cm, monkeypatch):
    non_existent_profile = "non_existent_profile_for_test.json"
    expected_full_path = os.path.join(EXPECTED_PROFILES_DIR_CM, non_existent_profile)
    monkeypatch.setattr(os.path, "exists", lambda path_arg: path_arg != expected_full_path)
    with pytest.raises(FileNotFoundError) as excinfo:
        ConfigManager(profile_path_or_name=non_existent_profile, create_if_missing=False)
    assert str(excinfo.value).startswith(f"Profile file not found: {expected_full_path}")

def test_config_manager_init_non_existent_profile_create_true(mock_project_root_cm, monkeypatch):
    non_existent_profile_name = "new_profile_to_create"
    expected_full_path = os.path.join(EXPECTED_PROFILES_DIR_CM, f"{non_existent_profile_name}.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: False)
    cm = ConfigManager(profile_path_or_name=non_existent_profile_name, create_if_missing=True)
    assert cm.profile_path == expected_full_path
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]

def test_config_manager_init_no_args(mock_project_root_cm):
    cm = ConfigManager()
    assert cm.profile_path is None
    assert cm.profile_data == DEFAULT_PROFILE_STRUCTURE

# --- _resolve_profile_path Tests (Enhanced) ---

@pytest.mark.parametrize("profile_input, expected_suffix", [
    ("test_prof", "test_prof.json"),
    ("test_prof.json", "test_prof.json"),
    (f"subdir{os.sep}test_prof", f"subdir{os.sep}test_prof.json"),
])
def test_resolve_profile_path_variations(profile_input, expected_suffix, monkeypatch, mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    monkeypatch.setattr(os.path, "isabs", lambda path_arg: False)
    expected_path = os.path.abspath(os.path.join(EXPECTED_PROFILES_DIR_CM, expected_suffix))
    if os.sep in profile_input or (os.altsep and os.altsep in profile_input):
        expected_dir_to_check = os.path.dirname(os.path.abspath(os.path.join(TEST_PROJECT_ROOT, expected_suffix)))
        monkeypatch.setattr(os.path, "exists", lambda path_arg: path_arg == expected_dir_to_check)
        expected_path = os.path.abspath(os.path.join(TEST_PROJECT_ROOT, expected_suffix))
    else:
        monkeypatch.setattr(os.path, "exists", lambda path_arg: False)
    assert cm._resolve_profile_path(profile_input) == expected_path


# --- _load_profile Tests (Enhanced) ---

def test_load_profile_success(temp_profile_file):
    cm, expected_content, _ = temp_profile_file
    assert cm.profile_data["profile_description"] == "Test Profile Loaded"
    assert cm.profile_data["settings"]["monitoring_interval_seconds"] == 5.0
    assert len(cm.profile_data["regions"]) == 1
    assert cm.profile_data["regions"][0]["name"] == "region1"

def test_load_profile_file_not_exist(mock_project_root_cm, monkeypatch):
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "non_existent_for_load.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: False)
    cm._load_profile()
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]

@patch("builtins.open", new_callable=mock_open, read_data='{"profile_description": "Partial", "settings": {"new_setting": true}}')
def test_load_profile_merges_with_defaults(mock_file_open_patch, mock_project_root_cm, monkeypatch): # Renamed fixture
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "partial_profile.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: True)
    cm._load_profile()
    assert cm.profile_data["profile_description"] == "Partial"
    assert cm.profile_data["settings"]["new_setting"] is True
    assert "monitoring_interval_seconds" in cm.profile_data["settings"]
    assert "rules" in cm.profile_data

@patch("builtins.open", new_callable=mock_open, read_data='This is not JSON')
def test_load_profile_invalid_json(mock_file_open_patch, mock_project_root_cm, monkeypatch): # Renamed fixture
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "invalid_json.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: True)
    with pytest.raises(ValueError, match="Invalid JSON in profile file"):
        cm._load_profile()
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]

@patch("builtins.open", side_effect=IOError("Test permission denied"))
def test_load_profile_io_error(mock_file_open_patch, mock_project_root_cm, monkeypatch): # Renamed fixture
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "unreadable.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: True)
    with pytest.raises(IOError, match="Could not read or process profile file"):
        cm._load_profile()
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]

# --- save_profile_data_to_path and save_current_profile Tests (Enhanced) ---

def test_save_profile_data_to_path_success(tmp_path, monkeypatch):
    save_dir = tmp_path / "save_test_profiles"
    monkeypatch.setattr(os, "makedirs", lambda path, exist_ok=False: None)
    file_to_save = save_dir / "saved_data.json"
    data_to_save = {"description": "Saved Test", "settings": {}}
    ConfigManager.save_profile_data_to_path(str(file_to_save), data_to_save)
    assert file_to_save.exists()
    with open(file_to_save, "r") as f:
        loaded_data = json.load(f)
    assert loaded_data == data_to_save

def test_save_profile_data_to_path_invalid_path(tmp_path):
    with pytest.raises(ValueError, match="Invalid filepath"):
        ConfigManager.save_profile_data_to_path("", {"data":1})
    with pytest.raises(IOError):
        ConfigManager.save_profile_data_to_path(str(tmp_path), {"data":1})

def test_save_current_profile_new_profile_requires_path(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    assert cm.save_current_profile() is False

@patch.object(ConfigManager, 'save_profile_data_to_path')
def test_save_current_profile_existing_path(mock_static_save, mock_project_root_cm):
    cm = ConfigManager("existing_profile", create_if_missing=True)
    cm.profile_data = {"key": "value"}
    assert cm.save_current_profile() is True
    mock_static_save.assert_called_once_with(cm.profile_path, {"key": "value"})

@patch.object(ConfigManager, 'save_profile_data_to_path')
def test_save_current_profile_with_new_path_save_as(mock_static_save, mock_project_root_cm):
    cm = ConfigManager("original_profile", create_if_missing=True)
    cm.profile_data = {"original": "data"}
    new_name = "saved_as_profile"
    expected_new_path = os.path.abspath(os.path.join(EXPECTED_PROFILES_DIR_CM, f"{new_name}.json"))
    assert cm.save_current_profile(new_path_or_name=new_name) is True
    assert cm.profile_path == expected_new_path
    mock_static_save.assert_called_once_with(expected_new_path, {"original": "data"})


# --- Getter method tests (Enhanced) ---

def test_get_template_image_path(temp_profile_file):
    cm, _, profile_file_path = temp_profile_file
    cm.profile_path = profile_file_path
    template_filename = "my_template.png"
    expected_path = os.path.join(os.path.dirname(profile_file_path), TEMPLATES_SUBDIR_NAME, template_filename)
    assert cm.get_template_image_path(template_filename) == expected_path

def test_get_template_image_path_profile_unsaved(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    assert cm.get_template_image_path("any.png") is None

def test_get_template_image_path_invalid_filename(temp_profile_file):
    cm, _, _ = temp_profile_file
    assert cm.get_template_image_path("") is None
    assert cm.get_template_image_path(None) is None # type: ignore

def test_getters_return_copies_and_defaults(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    assert cm.get_setting("monitoring_interval_seconds") == DEFAULT_PROFILE_STRUCTURE["settings"]["monitoring_interval_seconds"]
    assert cm.get_setting("non_existent_setting", "default_val") == "default_val"
    regions_list = cm.get_regions(); assert regions_list == []
    regions_list.append({"new_region": True}); assert cm.get_regions() == []
    templates_list = cm.get_templates(); assert templates_list == []
    templates_list.append({"new_template": True}); assert cm.get_templates() == []
    rules_list = cm.get_rules(); assert rules_list == []
    rules_list.append({"new_rule": True}); assert cm.get_rules() == []

def test_update_profile_data_merges_correctly(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    new_data_partial = {
        "profile_description": "Updated Description",
        "settings": {"monitoring_interval_seconds": 10.5, "custom_user_setting": "xyz"},
        "regions": [{"name": "r1"}]
    }
    cm.update_profile_data(new_data_partial)
    assert cm.profile_data["profile_description"] == "Updated Description"
    assert cm.profile_data["settings"]["monitoring_interval_seconds"] == 10.5
    assert cm.profile_data["settings"]["custom_user_setting"] == "xyz"
    assert "analysis_dominant_colors_k" in cm.profile_data["settings"]
    assert len(cm.profile_data["regions"]) == 1
    assert cm.profile_data["regions"][0]["name"] == "r1"
    assert "templates" in cm.profile_data and cm.profile_data["templates"] == []
    assert "rules" in cm.profile_data and cm.profile_data["rules"] == []