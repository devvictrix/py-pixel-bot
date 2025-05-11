import json
import logging
import os
from typing import Dict, Any, Optional, List

import dotenv

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_FILENAME = "default_profile.json" # Example, not actively used for auto-creation currently
PROFILES_DIR_NAME = "profiles"
TEMPLATES_SUBDIR_NAME = "templates"


def load_environment_variables():
    """
    Loads environment variables from a .env file in the project root.
    Key variable expected: APP_ENV (e.g., development, production).
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Should resolve to py-pixel-bot/
    dotenv_path = os.path.join(project_root, ".env")
    
    if os.path.exists(dotenv_path):
        loaded = dotenv.load_dotenv(dotenv_path, override=True)
        if loaded:
            logger.info(f"Environment variables loaded from: {dotenv_path}")
            app_env = os.getenv("APP_ENV")
            logger.info(f"APP_ENV set to: '{app_env if app_env else 'Not Set'}'")
        else:
            logger.warning(f".env file found at {dotenv_path}, but python-dotenv reported no variables loaded. This might be unexpected.")
    else:
        logger.warning(
            f".env file not found at {dotenv_path}. Application will use default settings or OS environment variables."
        )
        # It's crucial that APP_ENV can be set via OS if .env is missing for some deployments
        app_env = os.getenv("APP_ENV")
        if app_env:
            logger.info(f"APP_ENV read from OS environment: '{app_env}'")
        else:
            logger.warning("APP_ENV not found in .env or OS environment. Defaulting to 'production' for safety in logging, but this should be configured.")
            os.environ["APP_ENV"] = "production" # Default if not set anywhere, to ensure logging doesn't fail


class ConfigManager:
    """
    Manages loading, accessing, and saving bot profile configurations (JSON files).
    Also handles path resolution for profiles and their associated assets like templates.
    """

    def __init__(self, profile_path_or_name: str, create_if_missing: bool = False):
        """
        Initializes the ConfigManager and loads the specified profile.

        Args:
            profile_path_or_name: The name of the profile (e.g., "my_bot" will look for
                                  "profiles/my_bot.json") or a direct relative/absolute
                                  path to a .json profile file.
            create_if_missing: If True and the profile file does not exist,
                               a default empty profile structure will be used in memory
                               (but not saved to disk until explicitly requested).
                               If False (default) and file not found, an error is raised.
        """
        self.project_root = self._find_project_root()
        self.profiles_base_dir = os.path.join(self.project_root, PROFILES_DIR_NAME)
        
        self.profile_path: Optional[str] = self._resolve_profile_path(profile_path_or_name)
        self.profile_data: Dict[str, Any] = {}

        if self.profile_path and os.path.exists(self.profile_path):
            self._load_profile()
        elif create_if_missing:
            from py_pixel_bot.ui.gui.main_app_window import DEFAULT_PROFILE_STRUCTURE # Delayed import
            self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
            if self.profile_path: # Path was resolved but file doesn't exist
                 logger.info(f"Profile file '{self.profile_path}' not found. Initializing with default structure in memory (create_if_missing=True).")
            else: # profile_path_or_name was perhaps just a name for a new profile
                 self.profile_path = os.path.join(self.profiles_base_dir, profile_path_or_name if not profile_path_or_name.endswith(".json") else os.path.basename(profile_path_or_name))
                 if not self.profile_path.endswith(".json"): self.profile_path += ".json"
                 logger.info(f"No existing profile found for '{profile_path_or_name}'. Initializing with default structure in memory. Target path: {self.profile_path}")

        elif self.profile_path: # Path resolved but file not found and not create_if_missing
            logger.error(f"Profile file not found at '{self.profile_path}' and create_if_missing is False.")
            raise FileNotFoundError(f"Profile file not found: {self.profile_path}")
        else: # Should not happen if _resolve_profile_path works
            logger.error(f"Could not resolve a valid profile path for '{profile_path_or_name}'.")
            raise ValueError(f"Invalid profile path or name: {profile_path_or_name}")

        logger.info(f"ConfigManager initialized for profile path: '{self.profile_path if self.profile_path else 'In-memory New Profile'}'.")

    def _find_project_root(self) -> str:
        """Determines the project root directory (assumed to be parent of 'src')."""
        # Navigates up from the current file's location (core/config_manager.py)
        # src/py_pixel_bot/core/config_manager.py -> src/py_pixel_bot/core -> src/py_pixel_bot -> src -> project_root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))


    def _resolve_profile_path(self, profile_path_or_name: str) -> Optional[str]:
        """
        Resolves a profile name or path to an absolute file path.
        - If it's an absolute path and ends with .json, use it.
        - If it's a relative path and ends with .json, resolve it against project_root.
        - If it's just a name (no .json extension, no path separators), look in profiles_base_dir.
        """
        path_or_name = profile_path_or_name.strip()
        if not path_or_name:
            logger.warning("Empty profile path or name provided for resolution.")
            return None

        # Check if it's potentially an absolute path
        if os.path.isabs(path_or_name) and path_or_name.endswith(".json"):
            logger.debug(f"Resolved '{path_or_name}' as an absolute path.")
            return path_or_name
        
        # Check if it's a relative path (contains path separators or ends with .json but not absolute)
        # or if it's intended to be directly in the project root
        if os.sep in path_or_name or path_or_name.endswith(".json"):
            # If it doesn't end with .json, but looks like a path, something is wrong.
            # For now, assume if it has path sep, it's a path.
            # And if it ends with .json, it's a path.
            potential_path = os.path.join(self.project_root, path_or_name)
            if not potential_path.endswith(".json"): # User might provide dir/profile_name without .json
                potential_path += ".json"
            logger.debug(f"Resolved '{path_or_name}' as a relative path to: {potential_path}")
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
            # This state should ideally be caught by __init__ logic
            raise FileNotFoundError(f"Profile file not found at {self.profile_path}")
        
        logger.info(f"Loading profile from: {self.profile_path}")
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                self.profile_data = json.load(f)
            logger.info(f"Profile '{os.path.basename(self.profile_path)}' loaded successfully.")
            # Basic validation of top-level keys can be added here if needed
            # e.g., ensure "regions", "rules", "settings" exist, defaulting if not.
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
        """Returns the loaded profile data dictionary."""
        return self.profile_data

    def get_profile_path(self) -> Optional[str]:
        """Returns the absolute path to the loaded profile file, or None if in-memory only."""
        return self.profile_path

    def get_profile_base_path(self) -> Optional[str]:
        """
        Returns the directory path where the current profile is located.
        This is useful for resolving relative paths for assets like templates.
        Returns None if the profile hasn't been saved to a file yet.
        """
        if self.profile_path:
            return os.path.dirname(self.profile_path)
        logger.warning("Requested profile base path, but current profile has no file path (likely new and unsaved).")
        return None

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        """Gets a specific setting from the profile's 'settings' dictionary."""
        return self.profile_data.get("settings", {}).get(key, default)

    def get_regions(self) -> List[Dict[str, Any]]:
        """Returns the list of region specifications from the profile."""
        return self.profile_data.get("regions", [])
    
    def get_region_config(self, region_name: str) -> Optional[Dict[str, Any]]:
        """Gets the configuration for a specific region by its name."""
        for region in self.get_regions():
            if region.get("name") == region_name:
                return region
        logger.warning(f"Region named '{region_name}' not found in profile.")
        return None

    def get_templates(self) -> List[Dict[str, Any]]:
        """Returns the list of template specifications from the profile."""
        return self.profile_data.get("templates", [])

    def get_rules(self) -> List[Dict[str, Any]]:
        """Returns the list of rule specifications from the profile."""
        return self.profile_data.get("rules", [])

    def get_all_region_configs(self) -> Dict[str, Dict[str, Any]]:
        """Returns a dictionary mapping region names to their configs."""
        return {region.get("name", ""): region for region in self.get_regions() if region.get("name")}


    @staticmethod
    def save_profile_data_to_path(filepath: str, data: Dict[str, Any]):
        """
        Static method to save provided profile data to a specific filepath.
        Useful for the GUI editor when saving.
        """
        logger.info(f"Attempting to save profile data to: {filepath}")
        try:
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4) # Use indent for readability
            logger.info(f"Profile data successfully saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save profile data to '{filepath}': {e}", exc_info=True)
            # Re-raise or handle as needed by caller (e.g., GUI shows error message)
            raise IOError(f"Could not save profile to file: {filepath}. Error: {e}")

    def save_current_profile(self, new_path: Optional[str] = None):
        """
        Saves the current self.profile_data.
        If new_path is provided, updates self.profile_path and saves to the new location.
        Otherwise, saves to the existing self.profile_path.
        """
        if new_path:
            resolved_new_path = self._resolve_profile_path(new_path)
            if not resolved_new_path:
                logger.error(f"Cannot save profile: New path '{new_path}' could not be resolved.")
                raise ValueError(f"Invalid new path for saving profile: {new_path}")
            self.profile_path = resolved_new_path
            logger.info(f"Profile path updated to '{self.profile_path}' for saving.")

        if not self.profile_path:
            logger.error("Cannot save profile: No valid file path is set. Use 'save_as' functionality or provide a path.")
            raise ValueError("No file path set for saving the profile. Use Save As.")
        
        ConfigManager.save_profile_data_to_path(self.profile_path, self.profile_data)


# Ensure this runs only when the module is executed directly e.g. for testing it.
if __name__ == "__main__":
    # This basic test assumes a .env file and a profiles directory might exist
    # relative to where this script is if run directly.
    # For proper testing, run from project root with `python -m py_pixel_bot.core.config_manager`
    # or ensure PYTHONPATH is set.
    
    # Setup basic logging for standalone test
    if not logging.getLogger().hasHandlers(): # Avoid reconfiguring if already set by main app
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    load_environment_variables() # Load .env if present

    logger.info("Testing ConfigManager...")
    # Example: Create a dummy profiles directory and a test profile if they don't exist
    
    # Determine project root assuming this file is src/py_pixel_bot/core/config_manager.py
    test_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    test_profiles_dir = os.path.join(test_project_root, PROFILES_DIR_NAME)
    os.makedirs(test_profiles_dir, exist_ok=True)
    
    dummy_profile_name = "test_dummy_profile"
    dummy_profile_path = os.path.join(test_profiles_dir, f"{dummy_profile_name}.json")
    
    if not os.path.exists(dummy_profile_path):
        logger.info(f"Creating dummy profile for testing at {dummy_profile_path}")
        dummy_data = {"profile_description": "A test dummy profile", "settings": {"interval": 2.0}, "regions": [], "rules": []}
        with open(dummy_profile_path, "w") as f:
            json.dump(dummy_data, f, indent=4)

    try:
        logger.info("\n--- Test 1: Loading by name ---")
        cm_name = ConfigManager(dummy_profile_name)
        logger.info(f"Loaded profile by name: {cm_name.get_profile_path()}")
        logger.info(f"Profile description: {cm_name.get_profile_data().get('profile_description')}")

        logger.info("\n--- Test 2: Loading by relative path from project root ---")
        relative_path = os.path.join(PROFILES_DIR_NAME, f"{dummy_profile_name}.json")
        cm_rel_path = ConfigManager(relative_path)
        logger.info(f"Loaded profile by relative path: {cm_rel_path.get_profile_path()}")
        logger.info(f"Interval setting: {cm_rel_path.get_setting('interval')}")

        logger.info("\n--- Test 3: Loading by absolute path ---")
        cm_abs_path = ConfigManager(dummy_profile_path)
        logger.info(f"Loaded profile by absolute path: {cm_abs_path.get_profile_path()}")

        logger.info("\n--- Test 4: Create if missing (memory only) ---")
        cm_new_mem = ConfigManager("new_nonexistent_profile", create_if_missing=True)
        logger.info(f"New in-memory profile path (target): {cm_new_mem.get_profile_path()}")
        logger.info(f"New profile data (default): {cm_new_mem.get_profile_data()['profile_description']}")
        
        # Test saving this new profile
        new_profile_save_path = os.path.join(test_profiles_dir, "saved_new_profile.json")
        logger.info(f"\n--- Test 5: Saving new in-memory profile to {new_profile_save_path} ---")
        cm_new_mem.profile_data["profile_description"] = "My Saved New Profile"
        cm_new_mem.save_current_profile(new_profile_save_path) # This will set its path
        if os.path.exists(new_profile_save_path):
            logger.info("New profile saved successfully.")
            # Verify by loading it
            cm_reloaded = ConfigManager("saved_new_profile") # Load by name
            logger.info(f"Reloaded saved profile description: {cm_reloaded.get_profile_data()['profile_description']}")
            os.remove(new_profile_save_path) # Clean up
            logger.info(f"Cleaned up {new_profile_save_path}")
        else:
            logger.error("Failed to save new profile.")


        logger.info("\n--- Test 6: File not found (create_if_missing=False) ---")
        try:
            ConfigManager("another_nonexistent_profile", create_if_missing=False)
        except FileNotFoundError as e:
            logger.info(f"Correctly caught FileNotFoundError: {e}")
        
        logger.info("\n--- Test 7: Get profile base path ---")
        base_path = cm_abs_path.get_profile_base_path()
        logger.info(f"Base path for '{cm_abs_path.get_profile_path()}': {base_path}")
        if cm_new_mem.get_profile_path(): # Path is now set after save
            base_path_new_saved = cm_new_mem.get_profile_base_path()
            logger.info(f"Base path for new saved profile: {base_path_new_saved}")
        
        # Clean up dummy profile
        if os.path.exists(dummy_profile_path):
            os.remove(dummy_profile_path)
            logger.info(f"Cleaned up dummy profile: {dummy_profile_path}")

    except Exception as e:
        logger.exception(f"Error during ConfigManager test: {e}")