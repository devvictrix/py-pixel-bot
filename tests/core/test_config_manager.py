import os
import pytest
import json
from unittest.mock import patch, mock_open  # Ensure mock_open is imported
import copy

from mark_i.core.config_manager import ConfigManager, PROFILES_DIR_NAME, TEMPLATES_SUBDIR_NAME
from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE  # For comparison

# Define a fixed project root for testing path resolution consistently
# For Windows, an absolute path starting with a drive letter is more robust for os.path.abspath comparisons
# Using os.path.join to construct it to be OS-agnostic as much as possible for the test definition itself.
TEST_PROJECT_ROOT_BASE = "C:\\" if os.name == "nt" else "/"  # Ensures C:\ for absolute paths
TEST_PROJECT_ROOT = os.path.join(TEST_PROJECT_ROOT_BASE, "test_project_root_dir_for_cm_tests")
EXPECTED_PROFILES_DIR_CM = os.path.join(TEST_PROJECT_ROOT, PROFILES_DIR_NAME)


@pytest.fixture
def mock_project_root_cm(monkeypatch):
    """Fixture to mock ConfigManager._find_project_root() for consistent path testing."""
    monkeypatch.setattr(ConfigManager, "_find_project_root", lambda self: TEST_PROJECT_ROOT)

    # Also mock os.makedirs as it's called in __init__ if profiles_base_dir needs creation.
    # Let it run or mock it to not fail if it's already mocked elsewhere.
    # For these tests, if _find_project_root is mocked, self.profiles_base_dir will be based on TEST_PROJECT_ROOT.
    # We can mock it to do nothing to avoid actual disk I/O for this specific part of __init__.
    def mock_makedirs(path, exist_ok=False):
        # Simulate makedirs without actual disk write, or log call
        # print(f"Mocked os.makedirs called with: {path}, exist_ok={exist_ok}")
        pass

    monkeypatch.setattr(os, "makedirs", mock_makedirs)


@pytest.fixture
def temp_profile_file(tmp_path_factory, mock_project_root_cm):  # Depends on mock_project_root for consistency
    """Creates a temporary valid profile file and returns its ConfigManager instance."""
    # This fixture now correctly uses tmp_path for the *actual* file,
    # while relying on mock_project_root_cm for ConfigManager's *internal* understanding of project root.
    # This separation is important. ConfigManager will think its base is EXPECTED_PROFILES_DIR_CM.
    # For loading a *specific file path*, we give it an absolute path created by tmp_path.

    profile_content = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
    profile_content["profile_description"] = "Test Profile Loaded"
    profile_content["settings"]["monitoring_interval_seconds"] = 5.0
    profile_content["regions"].append({"name": "region1", "x": 1, "y": 2, "width": 3, "height": 4, "comment": "c1"})

    # Create the test profile in a real temporary directory
    temp_dir_for_this_test = tmp_path_factory.mktemp("actual_profile_storage")
    file_path = temp_dir_for_this_test / "test_profile_to_load.json"
    with open(file_path, "w") as f:
        json.dump(profile_content, f)

    # When CM is initialized with an absolute path, it should use it directly.
    cm = ConfigManager(str(file_path))
    return cm, profile_content, str(file_path)


# --- Initialization Tests (Enhanced) ---


def test_config_manager_init_create_if_missing_no_path(mock_project_root_cm):
    cm = ConfigManager(profile_path_or_name=None, create_if_missing=True)
    assert cm.profile_path is None
    assert cm.get_profile_name() == "Unsaved Profile"
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]  # Check a key field


def test_config_manager_init_non_existent_profile_create_false(mock_project_root_cm, monkeypatch):
    non_existent_profile = "non_existent_profile_for_test.json"
    # Ensure expected_full_path_in_cm matches how ConfigManager resolves it
    expected_full_path_in_cm = os.path.abspath(os.path.join(EXPECTED_PROFILES_DIR_CM, non_existent_profile))

    # Mock os.path.exists to return False specifically for the path ConfigManager will try to access
    monkeypatch.setattr(os.path, "exists", lambda path_arg: path_arg != expected_full_path_in_cm)

    with pytest.raises(FileNotFoundError) as excinfo:
        ConfigManager(profile_path_or_name=non_existent_profile, create_if_missing=False)
    # The error message comes from the FileNotFoundError raised in __init__ by ConfigManager itself.
    assert str(excinfo.value).startswith(f"Profile file not found: {expected_full_path_in_cm}")


def test_config_manager_init_non_existent_profile_create_true(mock_project_root_cm, monkeypatch):
    non_existent_profile_name = "new_profile_to_create"
    # This is the path ConfigManager will construct internally and assign to self.profile_path
    expected_resolved_path_in_cm = os.path.abspath(os.path.join(EXPECTED_PROFILES_DIR_CM, f"{non_existent_profile_name}.json"))

    monkeypatch.setattr(os.path, "exists", lambda path_arg: False)  # Ensure it thinks no file exists
    cm = ConfigManager(profile_path_or_name=non_existent_profile_name, create_if_missing=True)

    # Normalize both paths for comparison to handle OS differences robustly
    assert os.path.normpath(cm.profile_path) == os.path.normpath(expected_resolved_path_in_cm)
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]


def test_config_manager_init_no_args(mock_project_root_cm):
    cm = ConfigManager()
    assert cm.profile_path is None
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]


# --- _resolve_profile_path Tests (Enhanced) ---


@pytest.mark.parametrize(
    "profile_input, expected_suffix_or_full_path_logic",
    [
        ("test_prof", lambda base_profiles_dir, base_project_dir: os.path.join(base_profiles_dir, "test_prof.json")),
        ("test_prof.json", lambda base_profiles_dir, base_project_dir: os.path.join(base_profiles_dir, "test_prof.json")),
        (os.path.join("subdir", "test_prof"), lambda base_profiles_dir, base_project_dir: os.path.join(base_project_dir, "subdir", "test_prof.json")),
        (os.path.join(TEST_PROJECT_ROOT, "abs_test.json"), lambda base_profiles_dir, base_project_dir: os.path.join(TEST_PROJECT_ROOT, "abs_test.json")),
    ],
)
def test_resolve_profile_path_variations(profile_input, expected_suffix_or_full_path_logic, monkeypatch, mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)  # CM instance for calling _resolve_profile_path

    # Determine if the input path is intended to be absolute for this test
    is_abs_input = os.path.isabs(profile_input)
    monkeypatch.setattr(os.path, "isabs", lambda path_arg: path_arg == profile_input if is_abs_input else False)

    # Mock os.path.exists: only for directory check if it's a relative path with separators
    def mock_exists_for_resolve(path_arg):
        if os.sep in profile_input or (os.altsep and os.altsep in profile_input):
            # If it's a relative path with separators, os.path.exists is called on its dirname
            # For this test, assume the directory of the project-relative path exists.
            expected_dir_to_check = os.path.dirname(os.path.abspath(os.path.join(TEST_PROJECT_ROOT, profile_input)))
            return path_arg == expected_dir_to_check
        return False  # For other calls (like file existence, which shouldn't block resolution)

    monkeypatch.setattr(os.path, "exists", mock_exists_for_resolve)

    # Calculate the expected path based on the logic provided
    expected_path = expected_suffix_or_full_path_logic(EXPECTED_PROFILES_DIR_CM, TEST_PROJECT_ROOT)

    # Ensure both resolved and expected paths are absolute and normalized for reliable comparison
    resolved_path_from_cm = cm._resolve_profile_path(profile_input)
    assert os.path.normpath(os.path.abspath(resolved_path_from_cm)) == os.path.normpath(os.path.abspath(expected_path))


# --- _load_profile Tests (Enhanced) ---


def test_load_profile_success(temp_profile_file):  # temp_profile_file already uses mock_project_root_cm implicitly
    cm, expected_content, _ = temp_profile_file
    assert cm.profile_data["profile_description"] == "Test Profile Loaded"
    assert cm.profile_data["settings"]["monitoring_interval_seconds"] == 5.0
    assert len(cm.profile_data["regions"]) == 1
    assert cm.profile_data["regions"][0]["name"] == "region1"


def test_load_profile_file_not_exist(mock_project_root_cm, monkeypatch):
    cm = ConfigManager(None, create_if_missing=True)  # Initialize an empty CM
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "non_existent_for_load.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: False)  # Mock that the file doesn't exist
    cm._load_profile()  # This should now initialize with default data due to the first check in _load_profile
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]


@patch("builtins.open", new_callable=mock_open, read_data='{"profile_description": "Partial", "settings": {"new_setting": true}}')
def test_load_profile_merges_with_defaults(mock_file_open_patch, mock_project_root_cm, monkeypatch):
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "partial_profile.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: True)  # Mock that the file exists
    cm._load_profile()
    assert cm.profile_data["profile_description"] == "Partial"
    assert cm.profile_data["settings"]["new_setting"] is True
    assert "monitoring_interval_seconds" in cm.profile_data["settings"]  # From default
    assert "rules" in cm.profile_data  # From default


@patch("builtins.open", new_callable=mock_open, read_data="This is not JSON")
def test_load_profile_invalid_json(mock_file_open_patch, mock_project_root_cm, monkeypatch):
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "invalid_json.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: True)
    with pytest.raises(ValueError, match="Invalid JSON in profile file"):
        cm._load_profile()
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]  # Should revert to default


@patch("builtins.open", side_effect=IOError("Test permission denied"))
def test_load_profile_io_error(mock_file_open_patch, mock_project_root_cm, monkeypatch):
    cm = ConfigManager(None, create_if_missing=True)
    cm.profile_path = os.path.join(EXPECTED_PROFILES_DIR_CM, "unreadable.json")
    monkeypatch.setattr(os.path, "exists", lambda path_arg: True)
    with pytest.raises(IOError, match="Could not read or process profile file"):  # Match OSError from re-raise
        cm._load_profile()
    assert cm.profile_data["profile_description"] == DEFAULT_PROFILE_STRUCTURE["profile_description"]


# --- save_profile_data_to_path and save_current_profile Tests (Enhanced) ---


def test_save_profile_data_to_path_success(tmp_path):  # Removed monkeypatch for os.makedirs
    save_dir = tmp_path / "save_test_profiles"
    # No need to mock os.makedirs, let the function create the directory
    file_to_save = save_dir / "saved_data.json"
    data_to_save = {"description": "Saved Test", "settings": {}}
    ConfigManager.save_profile_data_to_path(str(file_to_save), data_to_save)
    assert file_to_save.exists()
    with open(file_to_save, "r") as f:
        loaded_data = json.load(f)
    assert loaded_data == data_to_save


def test_save_profile_data_to_path_invalid_path(tmp_path):
    with pytest.raises(ValueError, match="Invalid filepath"):
        ConfigManager.save_profile_data_to_path("", {"data": 1})
    # Trying to save directly to tmp_path (which is a dir) with IOError:
    with pytest.raises(IOError):  # Changed from ValueError; open() would raise IOError if path is a directory.
        ConfigManager.save_profile_data_to_path(str(tmp_path), {"data": 1})


def test_save_current_profile_new_profile_requires_path(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)  # No profile_path set initially
    assert cm.save_current_profile() is False  # Should fail as path is None


@patch.object(ConfigManager, "save_profile_data_to_path")
def test_save_current_profile_existing_path(mock_static_save, mock_project_root_cm):
    # Initialize with a name, which sets self.profile_path
    cm = ConfigManager("existing_profile", create_if_missing=True)
    cm.profile_data = {"key": "value"}
    assert cm.save_current_profile() is True
    mock_static_save.assert_called_once_with(cm.profile_path, {"key": "value"})


@patch.object(ConfigManager, "save_profile_data_to_path")
def test_save_current_profile_with_new_path_save_as(mock_static_save, mock_project_root_cm):
    cm = ConfigManager("original_profile", create_if_missing=True)
    cm.profile_data = {"original": "data"}
    new_name = "saved_as_profile"
    expected_new_path = os.path.abspath(os.path.join(EXPECTED_PROFILES_DIR_CM, f"{new_name}.json"))

    assert cm.save_current_profile(new_path_or_name=new_name) is True
    assert os.path.normpath(cm.profile_path) == os.path.normpath(expected_new_path)
    mock_static_save.assert_called_once_with(expected_new_path, {"original": "data"})


# --- Getter method tests (Enhanced) ---


def test_get_template_image_path(temp_profile_file):
    cm, _, profile_file_path = temp_profile_file
    cm.profile_path = profile_file_path  # Ensure it's set from the temp file
    template_filename = "my_template.png"
    expected_path = os.path.join(os.path.dirname(profile_file_path), TEMPLATES_SUBDIR_NAME, template_filename)
    assert cm.get_template_image_path(template_filename) == expected_path


def test_get_template_image_path_profile_unsaved(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    assert cm.get_template_image_path("any.png") is None


def test_get_template_image_path_invalid_filename(temp_profile_file):
    cm, _, _ = temp_profile_file
    assert cm.get_template_image_path("") is None
    assert cm.get_template_image_path(None) is None  # type: ignore


def test_getters_return_copies_and_defaults(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    assert cm.get_setting("monitoring_interval_seconds") == DEFAULT_PROFILE_STRUCTURE["settings"]["monitoring_interval_seconds"]
    assert cm.get_setting("non_existent_setting", "default_val") == "default_val"

    regions_list = cm.get_regions()
    assert regions_list == []
    regions_list.append({"new_region": True})
    assert cm.get_regions() == []  # Should be a copy

    templates_list = cm.get_templates()
    assert templates_list == []
    templates_list.append({"new_template": True})
    assert cm.get_templates() == []

    rules_list = cm.get_rules()
    assert rules_list == []
    rules_list.append({"new_rule": True})
    assert cm.get_rules() == []


def test_update_profile_data_merges_correctly(mock_project_root_cm):
    cm = ConfigManager(None, create_if_missing=True)
    new_data_partial = {
        "profile_description": "Updated Description",
        "settings": {"monitoring_interval_seconds": 10.5, "custom_user_setting": "xyz"},
        "regions": [{"name": "r1"}],
        # templates and rules are missing, should default to empty lists
    }
    cm.update_profile_data(new_data_partial)

    # Check updated fields
    assert cm.profile_data["profile_description"] == "Updated Description"
    assert cm.profile_data["settings"]["monitoring_interval_seconds"] == 10.5
    assert cm.profile_data["settings"]["custom_user_setting"] == "xyz"
    assert len(cm.profile_data["regions"]) == 1
    assert cm.profile_data["regions"][0]["name"] == "r1"

    # Check fields from default structure that should still be present
    assert "analysis_dominant_colors_k" in cm.profile_data["settings"]
    assert "templates" in cm.profile_data and cm.profile_data["templates"] == []
    assert "rules" in cm.profile_data and cm.profile_data["rules"] == []