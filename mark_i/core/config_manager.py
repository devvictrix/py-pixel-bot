import json
import logging
import os
from typing import Dict, Any, Optional, List
import copy  # For deepcopy of default profile structure

import dotenv  # For loading .env files

# Use the application's root logger name, assuming it's defined and accessible.
# If logging_setup is guaranteed to run before this module is heavily used,
# this will work. Otherwise, direct __name__ is safer for module-level loggers.
# Let's stick to __name__ for module-level loggers for better encapsulation.
logger = logging.getLogger(__name__)

DEFAULT_PROFILE_FILENAME = "default_profile.json"  # Not currently used, profiles are named by user
PROFILES_DIR_NAME = "profiles"
TEMPLATES_SUBDIR_NAME = "templates"


def load_environment_variables():
    """
    Loads environment variables from a .env file located in the project root.
    Key variables expected:
        - APP_ENV (e.g., development, uat, production) for logging configuration.
        - GEMINI_API_KEY (for v4.0.0+ Gemini features).

    The project root is determined by navigating up from this file's location.
    This function should be called once at application startup.
    """
    try:
        # Determine project root: py-pixel-bot/mark_i/core/config_manager.py -> py-pixel-bot/
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        package_dir = os.path.dirname(current_file_dir)  # Should be .../mark_i/
        project_root = os.path.dirname(package_dir)  # Should be .../py-pixel-bot/

        dotenv_path = os.path.join(project_root, ".env")

        if os.path.exists(dotenv_path):
            loaded_count = dotenv.load_dotenv(dotenv_path, override=True)
            if loaded_count:  # python-dotenv returns True if .env was loaded, or number of vars
                logger.info(f"Successfully loaded environment variables from: {dotenv_path}")
            else:
                # This case might mean the .env file is empty or unreadable by dotenv
                logger.warning(f".env file found at {dotenv_path}, but python-dotenv reported no variables loaded. File might be empty or malformed.")
        else:
            logger.warning(f".env file not found at {dotenv_path}. Application will rely on OS-level environment variables or defaults.")

        # Log status of key environment variables
        app_env = os.getenv("APP_ENV")
        gemini_key = os.getenv("GEMINI_API_KEY")

        logger.info(f"APP_ENV after .env load: '{app_env if app_env else 'Not Set (will default in logging_setup)'}'")
        if gemini_key:
            logger.info(f"GEMINI_API_KEY after .env load: Loaded (length: {len(gemini_key)})")
        else:
            logger.warning("GEMINI_API_KEY after .env load: Not Set. Gemini features will be unavailable.")

    except Exception as e:
        # Fallback logging if the main logger isn't configured yet
        print(f"ERROR: Failed to load environment variables: {e}", file=os.sys.stderr)
        logger.error(f"Failed to load environment variables: {e}", exc_info=True)


class ConfigManager:
    """
    Manages loading, accessing, and saving bot profile configurations (JSON files).
    It also handles path resolution for profiles and their associated assets like templates.
    It ensures that basic profile structure keys exist when data is loaded or created.
    """

    def __init__(self, profile_path_or_name: Optional[str] = None, create_if_missing: bool = False):
        """
        Initializes the ConfigManager. If profile_path_or_name is provided,
        it attempts to load that profile. If create_if_missing is True and
        the profile doesn't exist (or no path is given), it initializes with
        a default profile structure in memory.

        Args:
            profile_path_or_name: The name of the profile (assumed to be in the
                                  default profiles directory, e.g., "my_bot") or a
                                  full/relative path to a .json profile file.
                                  If None and create_if_missing is True, prepares a new profile.
            create_if_missing: If True, and the specified profile doesn't exist,
                               a new default profile structure will be initialized in memory.
                               If False (default) and profile not found, an error is raised.
        """
        self.project_root = self._find_project_root()
        self.profiles_base_dir = os.path.join(self.project_root, PROFILES_DIR_NAME)
        os.makedirs(self.profiles_base_dir, exist_ok=True)  # Ensure base profiles dir exists

        self.profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = {}

        if profile_path_or_name:
            self.profile_path = self._resolve_profile_path(profile_path_or_name)
            if os.path.exists(self.profile_path):
                self._load_profile()
            elif create_if_missing:
                logger.info(f"Profile file '{self.profile_path}' not found. Initializing with default structure for new profile (create_if_missing=True).")
                self._initialize_default_profile_data()
            else:
                logger.error(f"Profile file not found at '{self.profile_path}' and create_if_missing is False.")
                raise FileNotFoundError(f"Profile file not found: {self.profile_path}")
        elif create_if_missing:  # No path/name given, but create_if_missing is true
            logger.info("No profile path/name provided, but create_if_missing is True. Initializing new default profile in memory.")
            self._initialize_default_profile_data()
            # profile_path remains None until first save_as
        else:
            # No path/name and not create_if_missing: This state means an empty ConfigManager,
            # useful perhaps if GUI wants to manage a "no profile loaded" state.
            # For CLI usage, a profile is usually expected for 'run'.
            logger.debug("ConfigManager initialized without a profile loaded or created (no path/name, create_if_missing=False).")
            self._initialize_default_profile_data()  # Still provide a default structure for consistency

        if profile_path_or_name or create_if_missing:
            logger.info(f"ConfigManager initialized. Target profile path: '{self.profile_path if self.profile_path else 'New Profile (unsaved)'}'.")

    def _initialize_default_profile_data(self):
        """Sets self.profile_data to a deep copy of the default structure."""
        # Import here to avoid circular dependency if gui_config imports this module indirectly
        from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE

        self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        # Ensure essential keys exist even in the default structure
        self.profile_data.setdefault("profile_description", "New Profile")
        self.profile_data.setdefault("settings", {})
        self.profile_data["settings"].setdefault("monitoring_interval_seconds", 1.0)
        self.profile_data["settings"].setdefault("analysis_dominant_colors_k", 3)
        self.profile_data["settings"].setdefault("gemini_default_model_name", "gemini-1.5-flash-latest")
        self.profile_data.setdefault("regions", [])
        self.profile_data.setdefault("templates", [])
        self.profile_data.setdefault("rules", [])

    def _find_project_root(self) -> str:
        """
        Determines the project root directory (assumed to be 'py-pixel-bot' or its equivalent).
        This method assumes a consistent directory structure: project_root/mark_i/core/this_file.py
        """
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        package_dir = os.path.dirname(current_file_dir)  # .../mark_i/
        project_root_dir = os.path.dirname(package_dir)  # .../py-pixel-bot/
        logger.debug(f"Project root determined: {project_root_dir} (based on location of config_manager.py)")
        return project_root_dir

    def _resolve_profile_path(self, profile_path_or_name: str) -> str:
        """
        Resolves a profile name or a partial/full path to an absolute .json file path.
        - If it's an absolute path ending with .json, use it.
        - If it's an absolute path not ending with .json, append .json.
        - If it's a relative path containing path separators, resolve it from project_root.
        - If it's just a name (no separators), assume it's in self.profiles_base_dir.
        Appends .json extension if not present.
        """
        path_or_name = profile_path_or_name.strip()
        if not path_or_name:
            # This case should ideally be handled before calling, but as a safeguard:
            logger.error("Cannot resolve empty profile path or name. Defaulting to 'untitled.json' in profiles directory.")
            return os.path.join(self.profiles_base_dir, "untitled.json")

        # Ensure .json extension
        if not path_or_name.lower().endswith(".json"):
            path_or_name_with_ext = f"{path_or_name}.json"
        else:
            path_or_name_with_ext = path_or_name

        if os.path.isabs(path_or_name_with_ext):
            logger.debug(f"Resolved '{profile_path_or_name}' as absolute path: '{path_or_name_with_ext}'")
            return path_or_name_with_ext

        # Check if it contains path separators (might be relative from project root or current dir)
        if os.sep in path_or_name_with_ext or ("/" in path_or_name_with_ext and os.altsep == "/"):
            # Try resolving relative to project root first
            project_relative_path = os.path.join(self.project_root, path_or_name_with_ext)
            if os.path.exists(os.path.dirname(project_relative_path)):  # Check if path appears valid relative to project root
                logger.debug(f"Resolved '{profile_path_or_name}' as project-relative path: '{os.path.abspath(project_relative_path)}'")
                return os.path.abspath(project_relative_path)
            # Fallback: resolve relative to current working directory if not clearly project-relative
            logger.debug(f"Resolved '{profile_path_or_name}' as CWD-relative path: '{os.path.abspath(path_or_name_with_ext)}'")
            return os.path.abspath(path_or_name_with_ext)

        # Treat as a simple name, look in the default profiles directory
        resolved_path = os.path.join(self.profiles_base_dir, path_or_name_with_ext)
        logger.debug(f"Resolved '{profile_path_or_name}' as profile name in default dir: '{os.path.abspath(resolved_path)}'")
        return os.path.abspath(resolved_path)

    def _load_profile(self):
        """Loads the JSON profile data from the resolved self.profile_path."""
        if not self.profile_path or not os.path.exists(self.profile_path):  # Should be guaranteed by caller if this is invoked
            logger.error(f"Cannot load profile: Path '{self.profile_path}' is invalid or file does not exist.")
            self._initialize_default_profile_data()  # Load default if file disappears
            # Raise error if strict loading is needed:
            # raise FileNotFoundError(f"Profile file not found at {self.profile_path}")
            return

        logger.info(f"Loading profile from: {self.profile_path}")
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)

            # Merge with default to ensure all top-level keys exist
            # This provides some backward compatibility if new top-level sections are added.
            from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE  # Local import

            merged_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)

            for key, default_value in DEFAULT_PROFILE_STRUCTURE.items():
                if key in loaded_data:
                    if isinstance(default_value, dict) and isinstance(loaded_data[key], dict):
                        # For 'settings', merge dictionaries to preserve existing and add new defaults
                        merged_data[key] = {**default_value, **loaded_data[key]}
                    else:
                        merged_data[key] = loaded_data[key]
                # If key from default is not in loaded, it remains as default from merged_data initialization

            self.profile_data = merged_data
            logger.info(f"Profile '{os.path.basename(self.profile_path)}' loaded and merged with defaults successfully.")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from profile '{self.profile_path}': {e}", exc_info=True)
            self._initialize_default_profile_data()  # Load default on parse error
            raise ValueError(f"Invalid JSON in profile file: {self.profile_path}. Error: {e}")
        except Exception as e:
            logger.error(f"Failed to load profile '{self.profile_path}': {e}", exc_info=True)
            self._initialize_default_profile_data()  # Load default on other errors
            raise IOError(f"Could not read profile file: {self.profile_path}. Error: {e}")

    def get_profile_data(self) -> Dict[str, Any]:
        """Returns a deep copy of the current profile data to prevent external modification."""
        return copy.deepcopy(self.profile_data)

    def update_profile_data(self, new_data: Dict[str, Any]):
        """
        Updates the in-memory profile data. Used by GUI before saving.
        Performs a merge to ensure all default top-level keys are present.
        """
        from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE  # Local import

        merged_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        for key, default_value in DEFAULT_PROFILE_STRUCTURE.items():
            if key in new_data:
                if isinstance(default_value, dict) and isinstance(new_data[key], dict):
                    merged_data[key] = {**default_value, **new_data[key]}
                else:
                    merged_data[key] = new_data[key]
        self.profile_data = merged_data
        logger.debug("In-memory profile data updated and merged with defaults.")

    def get_profile_path(self) -> Optional[str]:
        """Returns the absolute path of the currently loaded/target profile, if any."""
        return self.profile_path

    def get_profile_name(self) -> str:
        """Returns the filename of the current profile, or 'Unsaved Profile'."""
        if self.profile_path:
            return os.path.basename(self.profile_path)
        return "Unsaved Profile"

    def get_profile_base_path(self) -> Optional[str]:
        """Returns the directory of the current profile, if saved."""
        if self.profile_path:
            return os.path.dirname(self.profile_path)
        logger.warning("Requested profile base path, but current profile is unsaved or path is not set.")
        return None

    def get_template_image_path(self, template_filename: str) -> Optional[str]:
        """
        Constructs the full path to a template image file.

        Args:
            template_filename: The filename of the template (e.g., "icon.png").

        Returns:
            The absolute path to the template image, or None if the profile isn't saved
            (as the base path for templates would be unknown).
        """
        profile_base = self.get_profile_base_path()
        if not profile_base:
            logger.warning(f"Cannot get template path for '{template_filename}': Profile base path is unknown (profile may be unsaved).")
            return None
        return os.path.join(profile_base, TEMPLATES_SUBDIR_NAME, template_filename)

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        """Safely retrieves a value from the 'settings' dictionary in the profile."""
        return self.profile_data.get("settings", {}).get(key, default)

    def get_regions(self) -> List[Dict[str, Any]]:
        """Returns a list of region configurations."""
        return self.profile_data.get("regions", [])

    def get_region_config(self, region_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific region's configuration by its name."""
        for region in self.get_regions():
            if region.get("name") == region_name:
                return region
        logger.debug(f"Region named '{region_name}' not found in profile.")
        return None

    def get_templates(self) -> List[Dict[str, Any]]:
        """Returns a list of template configurations."""
        return self.profile_data.get("templates", [])

    def get_rules(self) -> List[Dict[str, Any]]:
        """Returns a list of rule configurations."""
        return self.profile_data.get("rules", [])

    def get_all_region_configs(self) -> Dict[str, Dict[str, Any]]:
        """Returns a dictionary of all region configurations, keyed by region name."""
        return {region.get("name", f"UnnamedRegion_{i}"): region for i, region in enumerate(self.get_regions())}

    @staticmethod
    def save_profile_data_to_path(filepath: str, data: Dict[str, Any]):
        """
        Static method to save provided profile data to a specified filepath.
        Ensures parent directory exists.
        """
        logger.info(f"Attempting to save profile data to: {filepath}")
        try:
            # Ensure the directory for the profile exists
            profile_dir = os.path.dirname(filepath)
            if profile_dir:  # If filepath includes a directory part
                os.makedirs(profile_dir, exist_ok=True)

            # Ensure the templates subdirectory exists next to the profile
            templates_dir = os.path.join(profile_dir if profile_dir else os.getcwd(), TEMPLATES_SUBDIR_NAME)
            os.makedirs(templates_dir, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Profile data successfully saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save profile data to '{filepath}': {e}", exc_info=True)
            # Re-raise as an IOError or a custom ConfigSaveError for callers to handle
            raise IOError(f"Could not save profile to file: {filepath}. Error: {e}")

    def save_current_profile(self, new_path_or_name: Optional[str] = None) -> bool:
        """
        Saves the current in-memory profile_data.
        If new_path_or_name is provided, it updates self.profile_path and saves to the new location (Save As).
        Otherwise, it saves to the existing self.profile_path (Save).

        Args:
            new_path_or_name: Optional. If provided, acts as a "Save As".
                              Can be a full path, relative path, or just a filename.

        Returns:
            True if save was successful, False otherwise.
        """
        if new_path_or_name:
            resolved_new_path = self._resolve_profile_path(new_path_or_name)
            if not resolved_new_path:  # Should not happen if _resolve_profile_path is robust
                logger.error(f"Cannot save profile: New path '{new_path_or_name}' could not be resolved.")
                return False  # Or raise ValueError
            self.profile_path = resolved_new_path
            logger.info(f"Profile path updated to '{self.profile_path}' for 'Save As' operation.")

        if not self.profile_path:
            logger.error("Cannot save profile: No valid file path is set. A 'Save As' operation (with a path/name) is required first for an unsaved profile.")
            # It's up to the caller (e.g., GUI) to prompt for a path if self.profile_path is None.
            # This method assumes self.profile_path is valid if new_path_or_name is not given.
            return False  # Or raise ValueError

        try:
            ConfigManager.save_profile_data_to_path(self.profile_path, self.profile_data)
            return True
        except IOError:  # Catch specific error from static method
            return False


if __name__ == "__main__":
    # This basic test assumes it can create a 'logs' and 'profiles' dir if not present.
    # For more robust testing, a dedicated test environment setup is better.

    # Ensure basic logging is available for the test itself
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s")

    load_environment_variables()  # For APP_ENV and GEMINI_API_KEY status logging

    logger.info("--- Running ConfigManager Self-Test ---")

    # Determine a base path for test profiles within the project structure
    try:
        test_cm_for_paths = ConfigManager()  # Initialize to get project_root and profiles_base_dir
        test_profiles_dir = test_cm_for_paths.profiles_base_dir
        logger.info(f"Test profiles will be managed in: {test_profiles_dir}")
    except Exception as e:
        logger.error(f"Failed to initialize ConfigManager for path determination: {e}")
        exit(1)

    test_profile_name = "cm_selftest_profile"
    # This path is where the file will actually be on disk
    test_profile_disk_path = os.path.join(test_profiles_dir, f"{test_profile_name}.json")

    # Clean up previous test file if it exists
    if os.path.exists(test_profile_disk_path):
        os.remove(test_profile_disk_path)
        logger.info(f"Removed existing test profile: {test_profile_disk_path}")

    try:
        logger.info("\n[Test 1: Initialize new profile in memory and save it by name]")
        cm1 = ConfigManager(test_profile_name, create_if_missing=True)
        cm1.profile_data["profile_description"] = "CM Test 1 Profile - Saved by Name"
        cm1.profile_data["settings"]["test_setting_1"] = "value1"
        save1_success = cm1.save_current_profile()  # Saves to resolved test_profile_disk_path
        assert save1_success, "Test 1: Failed to save new profile by name."
        assert os.path.exists(test_profile_disk_path), f"Test 1: File not created at {test_profile_disk_path}"
        logger.info(f"Test 1: New profile saved to '{cm1.get_profile_path()}' successfully.")

        logger.info("\n[Test 2: Load existing profile by name]")
        cm2 = ConfigManager(test_profile_name)  # Should load the file saved in Test 1
        assert cm2.get_profile_data().get("profile_description") == "CM Test 1 Profile - Saved by Name", "Test 2: Description mismatch."
        assert cm2.get_setting("test_setting_1") == "value1", "Test 2: Setting mismatch."
        logger.info(f"Test 2: Profile '{test_profile_name}' loaded successfully. Path: {cm2.get_profile_path()}")

        logger.info("\n[Test 3: Save As to a new name/path]")
        new_name_for_save_as = "cm_selftest_profile_saved_as"
        save_as_success = cm2.save_current_profile(new_name_for_save_as)  # Should save in profiles_base_dir
        assert save_as_success, "Test 3: Save As failed."
        expected_save_as_path = os.path.join(test_profiles_dir, f"{new_name_for_save_as}.json")
        assert cm2.get_profile_path() == expected_save_as_path, f"Test 3: Profile path not updated after Save As. Expected {expected_save_as_path}, got {cm2.get_profile_path()}"
        assert os.path.exists(expected_save_as_path), f"Test 3: File not created at Save As path {expected_save_as_path}"
        logger.info(f"Test 3: Profile successfully saved as '{new_name_for_save_as}' to path '{cm2.get_profile_path()}'")

        # Clean up the "saved_as" file
        if os.path.exists(expected_save_as_path):
            os.remove(expected_save_as_path)
            logger.info(f"Cleaned up Save As test profile: {expected_save_as_path}")

        logger.info("\n[Test 4: Initialize with full path and create_if_missing=True]")
        full_path_test_profile_name = "cm_selftest_fullpath_profile.json"
        full_path_test_profile_disk_path = os.path.join(test_profiles_dir, full_path_test_profile_name)
        if os.path.exists(full_path_test_profile_disk_path):
            os.remove(full_path_test_profile_disk_path)  # Clean if exists

        cm4 = ConfigManager(full_path_test_profile_disk_path, create_if_missing=True)
        assert cm4.get_profile_path() == full_path_test_profile_disk_path, "Test 4: Path mismatch for full path init."
        assert cm4.get_profile_data().get("profile_description") == "New Profile", "Test 4: Default data not initialized."
        cm4.profile_data["profile_description"] = "CM Test 4 Profile - Full Path"
        save4_success = cm4.save_current_profile()
        assert save4_success and os.path.exists(full_path_test_profile_disk_path), "Test 4: Failed to save full path profile."
        logger.info(f"Test 4: Profile with full path saved to '{cm4.get_profile_path()}' successfully.")

        if os.path.exists(full_path_test_profile_disk_path):  # Cleanup
            os.remove(full_path_test_profile_disk_path)
            logger.info(f"Cleaned up full path test profile: {full_path_test_profile_disk_path}")

        logger.info("\n[Test 5: Attempt to load non-existent profile with create_if_missing=False]")
        try:
            ConfigManager("non_existent_profile_for_error_test_123abc", create_if_missing=False)
            assert False, "Test 5: FileNotFoundError was not raised for non-existent profile."
        except FileNotFoundError:
            logger.info("Test 5: Correctly raised FileNotFoundError for non-existent profile.")
        except Exception as e:
            assert False, f"Test 5: Unexpected exception {type(e).__name__} raised: {e}"

        logger.info("\n[Test 6: Initialize with no path and create_if_missing=True (for new profile GUI state)]")
        cm6 = ConfigManager(None, create_if_missing=True)
        assert cm6.get_profile_path() is None, "Test 6: profile_path should be None for new, unsaved profile."
        assert cm6.get_profile_data().get("profile_description") == "New Profile", "Test 6: Default data not initialized for unsaved."
        logger.info(f"Test 6: New unsaved profile initialized. Description: '{cm6.get_profile_data()['profile_description']}'")
        # Attempting to save cm6 without a path should fail or be handled by GUI by calling save_as
        save6_success = cm6.save_current_profile()  # This should return False as path is None
        assert not save6_success, "Test 6: save_current_profile should fail or return False if path is None."
        logger.info("Test 6: Correctly handled save attempt on unsaved profile (returned False or raised error if not caught).")

        logger.info("\n--- ConfigManager Self-Test Completed ---")

    except AssertionError as e_assert:
        logger.error(f"ConfigManager Self-Test ASSERTION FAILED: {e_assert}", exc_info=True)
    except Exception as e_test:
        logger.error(f"ConfigManager Self-Test FAILED with unexpected error: {e_test}", exc_info=True)
    finally:
        # Final cleanup of the initial test file
        if os.path.exists(test_profile_disk_path):
            os.remove(test_profile_disk_path)
            logger.info(f"Final cleanup: Removed initial test profile: {test_profile_disk_path}")
