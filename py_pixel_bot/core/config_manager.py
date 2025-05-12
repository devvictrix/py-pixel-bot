import json
import logging
import os
from typing import Dict, Any, Optional, List
import copy  # Added for deepcopy in create_if_missing

import dotenv

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_FILENAME = "default_profile.json"
PROFILES_DIR_NAME = "profiles"
TEMPLATES_SUBDIR_NAME = "templates"


def load_environment_variables():
    """
    Loads environment variables from a .env file in the project root.
    Key variable expected: APP_ENV (e.g., development, production).
    """
    # Simpler way to get project root assuming this file is two levels down from project root
    # py-pixel-bot/py_pixel_bot/core/config_manager.py
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    package_dir = os.path.dirname(current_file_dir)
    project_root = os.path.dirname(package_dir)

    dotenv_path = os.path.join(project_root, ".env")

    if os.path.exists(dotenv_path):
        loaded = dotenv.load_dotenv(dotenv_path, override=True)
        if loaded:
            logger.info(f"Environment variables loaded from: {dotenv_path}")
            app_env = os.getenv("APP_ENV")
            logger.info(f"APP_ENV set to: '{app_env if app_env else 'Not Set'}'")
        else:
            logger.warning(f".env file found at {dotenv_path}, but python-dotenv reported no " "variables loaded. This might be unexpected.")
    else:
        logger.warning(f".env file not found at {dotenv_path}. Application will use default " "settings or OS environment variables.")
        app_env = os.getenv("APP_ENV")
        if app_env:
            logger.info(f"APP_ENV read from OS environment: '{app_env}'")
        else:
            logger.warning("APP_ENV not found in .env or OS environment. Defaulting to 'production' " "for safety in logging, but this should be configured.")
            os.environ["APP_ENV"] = "production"


class ConfigManager:
    """
    Manages loading, accessing, and saving bot profile configurations (JSON files).
    Also handles path resolution for profiles and their associated assets like templates.
    """

    def __init__(self, profile_path_or_name: str, create_if_missing: bool = False):
        """
        Initializes the ConfigManager and loads the specified profile.
        """
        self.project_root = self._find_project_root()
        self.profiles_base_dir = os.path.join(self.project_root, PROFILES_DIR_NAME)
        logger.debug(f"ConfigManager: Project root is '{self.project_root}', " f"Profiles base directory is '{self.profiles_base_dir}'")

        self.profile_path: Optional[str] = self._resolve_profile_path(profile_path_or_name)
        self.profile_data: Dict[str, Any] = {}

        if self.profile_path and os.path.exists(self.profile_path):
            self._load_profile()
        elif create_if_missing:
            # Ensure this import path is correct or DEFAULT_PROFILE_STRUCTURE is defined here
            try:
                from py_pixel_bot.ui.gui.main_app_window import DEFAULT_PROFILE_STRUCTURE
            except ImportError:
                # Fallback if GUI components are not always available (e.g. pure CLI run)
                logger.warning("Could not import DEFAULT_PROFILE_STRUCTURE from main_app_window. Using internal default.")
                DEFAULT_PROFILE_STRUCTURE = {
                    "profile_description": "New Default Profile",
                    "settings": {"monitoring_interval_seconds": 1.0, "analysis_dominant_colors_k": 3},
                    "regions": [],
                    "templates": [],
                    "rules": [],
                }
            self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
            if self.profile_path:  # Path was resolved but file doesn't exist
                logger.info(f"Profile file '{self.profile_path}' not found. Initializing with default " "structure in memory (create_if_missing=True).")
            else:  # profile_path_or_name was perhaps just a name for a new profile
                self.profile_path = os.path.join(
                    self.profiles_base_dir, profile_path_or_name if profile_path_or_name.endswith(".json") else f"{profile_path_or_name}.json"  # Ensure .json extension for name-only
                )
                logger.info(f"No existing profile found for '{profile_path_or_name}'. Initializing " f"with default structure in memory. Target path: {self.profile_path}")

        elif self.profile_path:  # Path resolved but file not found and not create_if_missing
            logger.error(f"Profile file not found at '{self.profile_path}' and " "create_if_missing is False.")
            raise FileNotFoundError(f"Profile file not found: {self.profile_path}")
        else:  # Should not happen if _resolve_profile_path works
            logger.error(f"Could not resolve a valid profile path for '{profile_path_or_name}'.")
            raise ValueError(f"Invalid profile path or name: {profile_path_or_name}")

        logger.info(f"ConfigManager initialized for profile path: " f"'{self.profile_path if self.profile_path else 'In-memory New Profile'}'.")

    def _find_project_root(self) -> str:
        """Determines the project root directory (py-pixel-bot)."""
        # Assumes this file is: py-pixel-bot/py_pixel_bot/core/config_manager.py
        current_file_dir = os.path.dirname(os.path.abspath(__file__))  # .../py_pixel_bot/core
        package_dir = os.path.dirname(current_file_dir)  # .../py_pixel_bot (package directory)
        project_root_dir = os.path.dirname(package_dir)  # .../py-pixel-bot (project folder)

        # Basic heuristic check
        expected_package_dirname = "py_pixel_bot"
        profiles_dirname_check = "profiles"
        if (
            os.path.basename(project_root_dir) == "py-pixel-bot"
            and os.path.isdir(os.path.join(project_root_dir, expected_package_dirname))
            and os.path.isdir(os.path.join(project_root_dir, profiles_dirname_check))
        ):
            logger.debug(f"Project root determined by heuristic: {project_root_dir}")
            return project_root_dir
        else:
            # Fallback to direct calculation if heuristic fails, but log warning
            calculated_root = os.path.dirname(os.path.dirname(current_file_dir))
            logger.warning(
                f"Project root heuristic check failed. Current file: '{__file__}'. "
                f"Basename of calculated root: '{os.path.basename(calculated_root)}'. "
                f"Using calculated root: {calculated_root}. Ensure this is correct."
            )
            return calculated_root

    def _resolve_profile_path(self, profile_path_or_name: str) -> Optional[str]:
        """
        Resolves a profile name or path to an absolute file path.
        - If it's an absolute path and ends with .json, use it.
        - If it's a relative path (from project_root) and ends with .json, resolve it.
        - If it's just a name (no .json, no path seps), look in self.profiles_base_dir.
        """
        path_or_name = profile_path_or_name.strip()
        if not path_or_name:
            logger.warning("Empty profile path or name provided for resolution.")
            return None

        # Check if it's an absolute path
        if os.path.isabs(path_or_name):
            if path_or_name.endswith(".json"):
                logger.debug(f"Resolved '{path_or_name}' as an absolute path.")
                return path_or_name
            else:  # Absolute path but no .json extension
                resolved_path = f"{path_or_name}.json"
                logger.debug(f"Resolved '{path_or_name}' (absolute, no ext) to: {resolved_path}")
                return resolved_path

        # Check if it's a relative path from project_root or just a name
        # A relative path might contain os.sep or be intended to be directly in profiles_base_dir
        if os.sep in path_or_name or path_or_name.endswith(".json"):
            # If it's already relative to project root (e.g. "profiles/my.json")
            potential_path = os.path.join(self.project_root, path_or_name)
            if not potential_path.endswith(".json"):
                potential_path += ".json"
            logger.debug(f"Resolved '{path_or_name}' as a project-relative path to: {potential_path}")
            return os.path.abspath(potential_path)

        # Treat as a simple name, look in the default profiles directory
        filename = f"{path_or_name}.json"
        resolved_path = os.path.join(self.profiles_base_dir, filename)
        logger.debug(f"Resolved '{path_or_name}' as a profile name to: {resolved_path}")
        return os.path.abspath(resolved_path)

    def _load_profile(self):
        """Loads the JSON profile data from the resolved self.profile_path."""
        if not self.profile_path or not os.path.exists(self.profile_path):
            logger.error(f"Cannot load profile: Path '{self.profile_path}' is invalid or file does not exist.")
            raise FileNotFoundError(f"Profile file not found at {self.profile_path}")

        logger.info(f"Loading profile from: {self.profile_path}")
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                self.profile_data = json.load(f)
            logger.info(f"Profile '{os.path.basename(self.profile_path)}' loaded successfully.")
            self.profile_data.setdefault("settings", {})
            self.profile_data.setdefault("regions", [])
            self.profile_data.setdefault("templates", [])
            self.profile_data.setdefault("rules", [])

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from profile '{self.profile_path}': {e}", exc_info=True)
            raise ValueError(f"Invalid JSON in profile file: {self.profile_path}. Error: {e}")
        except Exception as e:
            logger.error(f"Failed to load profile '{self.profile_path}': {e}", exc_info=True)
            raise IOError(f"Could not read profile file: {self.profile_path}. Error: {e}")

    def get_profile_data(self) -> Dict[str, Any]:
        return self.profile_data

    def get_profile_path(self) -> Optional[str]:
        return self.profile_path

    def get_profile_base_path(self) -> Optional[str]:
        if self.profile_path:
            return os.path.dirname(self.profile_path)
        logger.warning("Requested profile base path, but current profile has no file path.")
        return None

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        return self.profile_data.get("settings", {}).get(key, default)

    def get_regions(self) -> List[Dict[str, Any]]:
        return self.profile_data.get("regions", [])

    def get_region_config(self, region_name: str) -> Optional[Dict[str, Any]]:
        for region in self.get_regions():
            if region.get("name") == region_name:
                return region
        logger.warning(f"Region named '{region_name}' not found in profile.")
        return None

    def get_templates(self) -> List[Dict[str, Any]]:
        return self.profile_data.get("templates", [])

    def get_rules(self) -> List[Dict[str, Any]]:
        return self.profile_data.get("rules", [])

    def get_all_region_configs(self) -> Dict[str, Dict[str, Any]]:
        return {region.get("name", ""): region for region in self.get_regions() if region.get("name")}

    @staticmethod
    def save_profile_data_to_path(filepath: str, data: Dict[str, Any]):
        logger.info(f"Attempting to save profile data to: {filepath}")
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info(f"Profile data successfully saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save profile data to '{filepath}': {e}", exc_info=True)
            raise IOError(f"Could not save profile to file: {filepath}. Error: {e}")

    def save_current_profile(self, new_path: Optional[str] = None):
        if new_path:
            # If new_path is just a name, _resolve_profile_path will place it in profiles_base_dir
            # If new_path is relative, it's from project_root
            # If new_path is absolute, it's used directly
            resolved_new_path = self._resolve_profile_path(new_path)
            if not resolved_new_path:
                logger.error(f"Cannot save profile: New path '{new_path}' could not be resolved.")
                raise ValueError(f"Invalid new path for saving profile: {new_path}")
            self.profile_path = resolved_new_path
            logger.info(f"Profile path updated to '{self.profile_path}' for saving.")

        if not self.profile_path:
            logger.error("Cannot save profile: No valid file path is set. Use 'save_as'.")
            raise ValueError("No file path set for saving the profile. Use Save As.")

        ConfigManager.save_profile_data_to_path(self.profile_path, self.profile_data)


if __name__ == "__main__":
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    load_environment_variables()
    logger.info("Testing ConfigManager...")

    # This test assumes it's run from the project root (py-pixel-bot)
    # or that the _find_project_root works correctly from wherever it's run.
    test_project_root = ConfigManager("dummy_for_root_finding").project_root  # Get calculated root
    test_profiles_dir = os.path.join(test_project_root, PROFILES_DIR_NAME)
    os.makedirs(test_profiles_dir, exist_ok=True)

    dummy_profile_name = "test_dummy_profile"
    # Path for creating the dummy file
    dummy_profile_disk_path = os.path.join(test_profiles_dir, f"{dummy_profile_name}.json")

    if not os.path.exists(dummy_profile_disk_path):
        logger.info(f"Creating dummy profile for testing at {dummy_profile_disk_path}")
        dummy_data = {"profile_description": "Test dummy", "settings": {"interval": 2.0}}
        with open(dummy_profile_disk_path, "w") as f:
            json.dump(dummy_data, f, indent=4)

    try:
        logger.info("\n--- Test 1: Loading by name (expects it in profiles_base_dir) ---")
        cm_name = ConfigManager(dummy_profile_name)  # Should find test_dummy_profile.json
        logger.info(f"Loaded by name: '{cm_name.get_profile_path()}'. Desc: {cm_name.get_profile_data().get('profile_description')}")
        assert cm_name.get_profile_path() == os.path.abspath(dummy_profile_disk_path)

        logger.info("\n--- Test 2: Loading by relative path (from project root) ---")
        # This path is relative to project_root where command is run
        relative_path_to_profile = os.path.join(PROFILES_DIR_NAME, f"{dummy_profile_name}.json")
        cm_rel_path = ConfigManager(relative_path_to_profile)
        logger.info(f"Loaded by relative path '{relative_path_to_profile}': '{cm_rel_path.get_profile_path()}'. Interval: {cm_rel_path.get_setting('interval')}")
        assert cm_rel_path.get_profile_path() == os.path.abspath(dummy_profile_disk_path)

        logger.info("\n--- Test 3: Loading by absolute path ---")
        cm_abs_path = ConfigManager(os.path.abspath(dummy_profile_disk_path))
        logger.info(f"Loaded by absolute path: '{cm_abs_path.get_profile_path()}'")
        assert cm_abs_path.get_profile_path() == os.path.abspath(dummy_profile_disk_path)

        logger.info("\n--- Test 4: Create if missing (memory only, then save) ---")
        new_profile_name = "new_nonexistent_profile"
        cm_new_mem = ConfigManager(new_profile_name, create_if_missing=True)
        logger.info(f"New in-memory profile target path: {cm_new_mem.get_profile_path()}")
        logger.info(f"New profile data desc: {cm_new_mem.get_profile_data()['profile_description']}")

        # Expected save path if saved by name
        expected_new_save_path = os.path.join(test_profiles_dir, f"{new_profile_name}.json")
        assert cm_new_mem.get_profile_path() == os.path.abspath(expected_new_save_path)

        cm_new_mem.profile_data["profile_description"] = "My Saved New Mem Profile"
        cm_new_mem.save_current_profile()  # Saves to its resolved self.profile_path

        if os.path.exists(expected_new_save_path):
            logger.info(f"New profile saved to: {expected_new_save_path}")
            cm_reloaded = ConfigManager(new_profile_name)
            assert cm_reloaded.get_profile_data()["profile_description"] == "My Saved New Mem Profile"
            os.remove(expected_new_save_path)
            logger.info(f"Cleaned up {expected_new_save_path}")
        else:
            logger.error(f"Failed to save new profile to {expected_new_save_path}")

        logger.info("\n--- Test 5: File not found (create_if_missing=False) ---")
        try:
            ConfigManager("another_nonexistent_profile_for_error", create_if_missing=False)
        except FileNotFoundError as e:
            logger.info(f"Correctly caught FileNotFoundError: {e}")

        if os.path.exists(dummy_profile_disk_path):
            os.remove(dummy_profile_disk_path)
            logger.info(f"Cleaned up dummy profile: {dummy_profile_disk_path}")
        logger.info("ConfigManager tests completed.")

    except Exception as e:
        logger.exception(f"Error during ConfigManager test: {e}")
