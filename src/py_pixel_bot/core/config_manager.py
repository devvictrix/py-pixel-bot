// File: src/py_pixel_bot/core/config_manager.py
import json
import logging
import os
from typing import Dict, Any, Optional, List, Set # Added Set for type hint consistency
import copy # For deepcopying default profile structure

import dotenv # For loading .env file

logger = logging.getLogger(__name__) # Corresponds to 'py_pixel_bot.core.config_manager'

DEFAULT_PROFILE_FILENAME = "default_profile.json" # Currently unused for auto-creation from this name
PROFILES_DIR_NAME = "profiles" # Default subdirectory for profiles relative to project root
TEMPLATES_SUBDIR_NAME = "templates" # Subdirectory for template images, relative to a profile's JSON file location

# Attempt to locate the project root for .env loading and default profiles directory.
# This assumes a structure like: project_root/src/py_pixel_bot/core/config_manager.py
# More robust methods might involve searching for a marker file (e.g., .git) or using package resources if distributed.
try:
    CONFIG_MANAGER_FILE_PATH = os.path.abspath(__file__)
    CORE_DIR = os.path.dirname(CONFIG_MANAGER_FILE_PATH)
    PY_PIXEL_BOT_DIR = os.path.dirname(CORE_DIR)
    SRC_DIR = os.path.dirname(PY_PIXEL_BOT_DIR)
    PROJECT_ROOT_FROM_CM = os.path.dirname(SRC_DIR) # Default assumption
except NameError: # __file__ might not be defined in some contexts (e.g. interactive, somefrozen apps)
    PROJECT_ROOT_FROM_CM = os.getcwd() # Fallback, might not be accurate
    logger.warning(f"__file__ not defined in ConfigManager, using CWD '{PROJECT_ROOT_FROM_CM}' as potential project root for .env. This might be incorrect.")


def load_environment_variables() -> None:
    """
    Loads environment variables from a .env file located in the project root.
    The primary variable expected is APP_ENV (e.g., development, production).
    This function should be called once at application startup, before logging setup.
    """
    # Use PROJECT_ROOT_FROM_CM determined at module load.
    dotenv_path = os.path.join(PROJECT_ROOT_FROM_CM, ".env")
    
    if os.path.exists(dotenv_path):
        loaded = dotenv.load_dotenv(dotenv_path, override=True) # Override OS env vars if present in .env
        if loaded:
            logger.info(f"Environment variables successfully loaded from: {dotenv_path}")
            app_env = os.getenv("APP_ENV")
            logger.info(f"APP_ENV (from .env or overridden OS): '{app_env if app_env else 'Not Set in .env/OS'}'")
        else:
            # This can happen if .env is empty or only has comments.
            logger.warning(f".env file found at '{dotenv_path}', but python-dotenv reported no variables were loaded. Check .env content.")
            # Check if APP_ENV was already in OS and not overridden
            app_env = os.getenv("APP_ENV")
            if app_env: logger.info(f"APP_ENV is present in OS environment: '{app_env}' (was not overridden by .env).")

    else:
        logger.warning(f".env file not found at '{dotenv_path}'. Application will rely on OS environment variables or defaults.")
    
    # Final check and default for APP_ENV if still not set (critical for logging)
    app_env = os.getenv("APP_ENV")
    if not app_env:
        logger.warning("APP_ENV not found in .env or OS environment. Defaulting APP_ENV to 'production' for logging safety.")
        os.environ["APP_ENV"] = "production" # Ensure it's set for logging_setup
    else:
        logger.info(f"Final APP_ENV for application session: '{app_env}'")


class ConfigManager:
    """
    Manages loading, accessing, and saving bot profile configurations (JSON files).
    Handles path resolution for profiles and their associated assets like templates.
    """

    def __init__(self, profile_path_or_name: str, create_if_missing: bool = False):
        """
        Initializes the ConfigManager and loads the specified profile.

        Args:
            profile_path_or_name: The name of the profile (e.g., "my_bot" will look for
                                  "profiles/my_bot.json" relative to project root) or a
                                  direct relative/absolute path to a .json profile file.
            create_if_missing: If True and the profile file does not exist after path resolution,
                               a default empty profile structure will be used in memory.
                               The file itself is NOT created on disk until an explicit save.
                               If False (default) and file not found, a FileNotFoundError is raised.
        """
        self.project_root: str = PROJECT_ROOT_FROM_CM # Use the module-level determined root
        self.profiles_base_dir: str = os.path.join(self.project_root, PROFILES_DIR_NAME)
        
        self.profile_path: Optional[str] = self._resolve_profile_path(profile_path_or_name)
        self.profile_data: Dict[str, Any] = {} # Will hold the loaded profile content

        logger.debug(f"ConfigManager trying to initialize with input: '{profile_path_or_name}', resolved to path: '{self.profile_path}'")

        if self.profile_path and os.path.exists(self.profile_path):
            self._load_profile()
        elif self.profile_path and create_if_missing: # Path resolved, file doesn't exist, but allowed to create in memory
            from py_pixel_bot.ui.gui.main_app_window import DEFAULT_PROFILE_STRUCTURE # Delayed to avoid circular import at module level
            self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
            # Update description if a name was given for the new profile
            base_name = os.path.splitext(os.path.basename(self.profile_path))[0]
            self.profile_data["profile_description"] = f"New Profile: {base_name}"
            logger.info(f"Profile file '{self.profile_path}' not found. Initialized new profile '{base_name}' in memory (create_if_missing=True).")
        elif self.profile_path: # Path resolved, file doesn't exist, and create_if_missing is False
            logger.error(f"Profile file not found at '{self.profile_path}' and 'create_if_missing' is False.")
            raise FileNotFoundError(f"Profile file not found: {self.profile_path}")
        else: # _resolve_profile_path returned None (e.g., empty input)
            logger.error(f"Could not resolve a valid profile file path for input '{profile_path_or_name}'.")
            raise ValueError(f"Invalid profile path or name provided: '{profile_path_or_name}'")

        logger.info(f"ConfigManager initialized. Effective profile path: '{self.profile_path}'. Profile description: '{self.profile_data.get('profile_description', 'N/A')}'")


    def _resolve_profile_path(self, profile_path_or_name: str) -> Optional[str]:
        """
        Resolves a profile name or path to an absolute file path.
        - If an absolute path ending with .json, it's used directly.
        - If a relative path (containing path separators or ending with .json), it's resolved against the project root.
        - If just a name (no separators, no .json), it's assumed to be in `self.profiles_base_dir`.
        """
        path_or_name = str(profile_path_or_name).strip() # Ensure string and strip whitespace
        if not path_or_name:
            logger.warning("Resolved profile path is None because input was empty.")
            return None

        # Check if it's an absolute path
        if os.path.isabs(path_or_name):
            if not path_or_name.endswith(".json"):
                resolved_path = f"{path_or_name}.json"
                logger.debug(f"Input '{path_or_name}' is absolute, appending .json: '{resolved_path}'")
            else:
                resolved_path = path_or_name
                logger.debug(f"Input '{path_or_name}' is absolute and ends with .json.")
            return os.path.normpath(resolved_path)
        
        # Check if it contains path separators (implying relative path from project root)
        # or if it already ends with .json (implying a file path, likely relative)
        if os.sep in path_or_name or "/" in path_or_name or path_or_name.endswith(".json"):
            # Assume relative to project_root if not absolute
            potential_path = os.path.join(self.project_root, path_or_name)
            if not potential_path.endswith(".json"):
                resolved_path = f"{potential_path}.json"
                logger.debug(f"Input '{path_or_name}' treated as relative, appending .json: '{resolved_path}'")
            else:
                resolved_path = potential_path
                logger.debug(f"Input '{path_or_name}' treated as relative and ends with .json.")
            return os.path.abspath(os.path.normpath(resolved_path))

        # Treat as a simple name, look in the default profiles directory
        filename_with_ext = f"{path_or_name}.json"
        resolved_path = os.path.join(self.profiles_base_dir, filename_with_ext)
        logger.debug(f"Input '{path_or_name}' treated as simple name, resolved to: '{resolved_path}'")
        return os.path.abspath(os.path.normpath(resolved_path))

    def _load_profile(self):
        """Loads the JSON profile data from the resolved self.profile_path."""
        if not self.profile_path or not os.path.exists(self.profile_path): # Should be caught by init
            logger.critical(f"Internal error: _load_profile called with invalid path '{self.profile_path}'.")
            raise FileNotFoundError(f"Profile file not found at invalid path: {self.profile_path}")
        
        logger.info(f"Loading profile from: {self.profile_path}")
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            
            # Ensure top-level keys exist, merging with defaults if necessary (more robust loading)
            from py_pixel_bot.ui.gui.main_app_window import DEFAULT_PROFILE_STRUCTURE # Delayed import
            default_copy = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
            
            # Merge settings: loaded takes precedence over default
            default_settings = default_copy.get("settings", {})
            loaded_settings = loaded_data.get("settings", {})
            default_settings.update(loaded_settings) # Update default with loaded values
            loaded_data["settings"] = default_settings

            # Ensure other top-level lists exist
            for key in ["regions", "templates", "rules"]:
                loaded_data.setdefault(key, default_copy.get(key, []))
            loaded_data.setdefault("profile_description", default_copy.get("profile_description", "Profile"))

            self.profile_data = loaded_data
            logger.info(f"Profile '{os.path.basename(self.profile_path)}' loaded and defaults ensured. Description: '{self.profile_data.get('profile_description')}'")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from profile '{self.profile_path}': {e}", exc_info=True)
            raise ValueError(f"Invalid JSON in profile file: {self.profile_path}. Error: {e}")
        except Exception as e:
            logger.error(f"Failed to load profile '{self.profile_path}': {e}", exc_info=True)
            raise IOError(f"Could not read profile file: {self.profile_path}. Error: {e}")

    def get_profile_data(self) -> Dict[str, Any]:
        """Returns the loaded (and potentially modified in-memory) profile data dictionary."""
        return self.profile_data

    def get_profile_path(self) -> Optional[str]:
        """Returns the absolute path to the loaded profile file, or None if in-memory only (new, unsaved)."""
        return self.profile_path

    def get_profile_base_path(self) -> Optional[str]:
        """
        Returns the absolute directory path where the current profile file is located.
        This is crucial for resolving relative paths for assets like template images.
        Returns None if the profile hasn't been saved to a file yet (i.e., `self.profile_path` is None).
        """
        if self.profile_path:
            return os.path.dirname(self.profile_path)
        logger.debug("get_profile_base_path: Current profile has no file path (likely new and unsaved). Returning None.")
        return None
    
    def get_template_image_abs_path(self, template_filename: str) -> Optional[str]:
        """
        Constructs the absolute path to a template image file.
        Assumes `template_filename` is relative to the profile's `templates/` subdirectory.
        """
        profile_base = self.get_profile_base_path()
        if not profile_base:
            logger.warning(f"Cannot get template path for '{template_filename}': Profile base path is unknown (profile likely unsaved).")
            return None
        if not template_filename or not isinstance(template_filename, str):
            logger.warning(f"Invalid template_filename provided: '{template_filename}'.")
            return None
            
        abs_path = os.path.join(profile_base, TEMPLATES_SUBDIR_NAME, template_filename)
        logger.debug(f"Resolved template '{template_filename}' to absolute path: {abs_path}")
        return os.path.normpath(abs_path)

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        return self.profile_data.get("settings", {}).get(key, default)

    def get_regions(self) -> List[Dict[str, Any]]:
        return self.profile_data.get("regions", [])
    
    def get_region_config(self, region_name: str) -> Optional[Dict[str, Any]]:
        for region in self.get_regions():
            if region.get("name") == region_name: return region
        logger.debug(f"Region named '{region_name}' not found in current profile data.")
        return None

    def get_templates(self) -> List[Dict[str, Any]]:
        return self.profile_data.get("templates", [])

    def get_rules(self) -> List[Dict[str, Any]]:
        return self.profile_data.get("rules", [])

    def get_all_region_configs(self) -> Dict[str, Dict[str, Any]]: # Used by GUI
        return {region.get("name", f"UnnamedRegion_{i}"): region for i, region in enumerate(self.get_regions())}


    @staticmethod
    def save_profile_data_to_path(filepath: str, data: Dict[str, Any]):
        """
        Static method to save provided profile data dictionary to a specific filepath as JSON.
        Ensures the parent directory exists.
        """
        if not filepath:
            logger.error("save_profile_data_to_path: Filepath is empty. Cannot save.")
            raise ValueError("Filepath cannot be empty for saving profile data.")
        if not isinstance(data, dict):
            logger.error(f"save_profile_data_to_path: Data to save is not a dictionary (type: {type(data)}).")
            raise TypeError("Profile data to save must be a dictionary.")

        logger.info(f"Attempting to save profile data to: {filepath}")
        try:
            parent_dir = os.path.dirname(filepath)
            if parent_dir: # Ensure parent_dir is not empty (e.g. if filepath is just "file.json")
                os.makedirs(parent_dir, exist_ok=True)
                logger.debug(f"Ensured directory exists: {parent_dir}")
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4) 
            logger.info(f"Profile data successfully saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save profile data to '{filepath}': {e}", exc_info=True)
            raise IOError(f"Could not save profile to file: {filepath}. Error: {e}")

    def save_current_profile(self, new_path: Optional[str] = None):
        """
        Saves the current `self.profile_data` to disk.
        If `new_path` is provided, it updates `self.profile_path` to this new path
        (resolved to absolute) and then saves. Otherwise, it saves to `self.profile_path`.
        Raises ValueError if no valid path is established.
        """
        logger.debug(f"save_current_profile called. new_path: '{new_path}', current self.profile_path: '{self.profile_path}'")
        target_path_to_save: Optional[str] = None

        if new_path:
            resolved_new_path = self._resolve_profile_path(new_path)
            if not resolved_new_path:
                logger.error(f"Cannot save profile: New path '{new_path}' could not be resolved to a valid file path.")
                raise ValueError(f"Invalid new path for saving profile: {new_path}")
            self.profile_path = resolved_new_path # Update instance's path
            target_path_to_save = self.profile_path
            logger.info(f"Profile path updated to '{target_path_to_save}' for saving.")
        elif self.profile_path:
            target_path_to_save = self.profile_path
        
        if not target_path_to_save:
            logger.error("Cannot save profile: No valid file path is set or resolved. Use 'Save As' functionality or provide a valid path.")
            raise ValueError("No file path set for saving the profile. Use Save As or ensure a path is provided.")
        
        # Ensure the 'templates' subdirectory exists next to the profile if there are templates defined
        if self.profile_data.get("templates"):
            profile_base = os.path.dirname(target_path_to_save)
            templates_dir = os.path.join(profile_base, TEMPLATES_SUBDIR_NAME)
            if not os.path.exists(templates_dir):
                try:
                    os.makedirs(templates_dir, exist_ok=True)
                    logger.info(f"Created missing templates directory for profile: {templates_dir}")
                except OSError as e:
                    logger.error(f"Could not create templates directory '{templates_dir}': {e}. Template files might not be saved correctly if paths are relative.")
        
        ConfigManager.save_profile_data_to_path(target_path_to_save, self.profile_data)
        logger.info(f"Current profile data saved to '{target_path_to_save}'.")


# Standalone test block
if __name__ == "__main__": # (Same test logic as before, verifying path resolution and load/save)
    if not logging.getLogger(APP_ROOT_LOGGER_NAME if 'APP_ROOT_LOGGER_NAME' in globals() else "py_pixel_bot").hasHandlers(): logging.basicConfig(level=logging.DEBUG,format='%(asctime)s-%(name)s-%(levelname)s-%(message)s'); logger.info("ConfigManager standalone:Min logging.")
    load_environment_variables(); logger.info("Testing ConfigManager..."); 
    tp_root=PROJECT_ROOT_FROM_CM; tp_dir=os.path.join(tp_root,PROFILES_DIR_NAME); os.makedirs(tp_dir,exist_ok=True)
    dpn="test_dummy_profile"; dpp=os.path.join(tp_dir,f"{dpn}.json")
    if not os.path.exists(dpp):logger.info(f"Creating dummy profile for test: {dpp}"); dd={"profile_description":"A test dummy","settings":{"interval":2.0}};with open(dpp,"w")as f:json.dump(dd,f,indent=4)
    try:
        logger.info("\n---T1:LoadByName---"); cm_n=ConfigManager(dpn);logger.info(f"LoadedByName:{cm_n.get_profile_path()} Desc:{cm_n.get_profile_data().get('profile_description')}")
        logger.info("\n---T2:LoadByRelPath---"); rp=os.path.join(PROFILES_DIR_NAME,f"{dpn}.json"); cm_rp=ConfigManager(rp);logger.info(f"LoadedByRelPath:{cm_rp.get_profile_path()} Interval:{cm_rp.get_setting('interval')}")
        logger.info("\n---T3:LoadByAbsPath---"); cm_ap=ConfigManager(dpp);logger.info(f"LoadedByAbsPath:{cm_ap.get_profile_path()}")
        logger.info("\n---T4:CreateIfMissing(memory)---"); cm_new=ConfigManager("new_nonexist",create_if_missing=True);logger.info(f"NewInMemoryPathTarget:{cm_new.get_profile_path()} DataDesc:{cm_new.get_profile_data()['profile_description']}")
        nsp_path=os.path.join(tp_dir,"saved_new_prof.json");logger.info(f"\n---T5:SaveNewInMemory to {nsp_path}---");cm_new.profile_data["profile_description"]="MySavedNew";cm_new.save_current_profile(nsp_path)
        if os.path.exists(nsp_path):logger.info("New profile saved.");cm_rld=ConfigManager("saved_new_prof");logger.info(f"Reloaded saved desc:{cm_rld.get_profile_data()['profile_description']}");os.remove(nsp_path);logger.info(f"Cleaned {nsp_path}");else:logger.error("Failed save new profile.")
        logger.info("\n---T6:FileNotFound(create_if_missing=False)---");try:ConfigManager("another_nonexist",create_if_missing=False);except FileNotFoundError as e:logger.info(f"Correctly caught FileNotFoundError:{e}")
        logger.info("\n---T7:GetProfileBasePath---");bp=cm_ap.get_profile_base_path();logger.info(f"BasePathFor'{cm_ap.get_profile_path()}':{bp}");
        if cm_new.get_profile_path():bp_new=cm_new.get_profile_base_path();logger.info(f"BasePathForNewSaved:{bp_new}")
        if os.path.exists(dpp):os.remove(dpp);logger.info(f"Cleaned dummy:{dpp}")
    except Exception as e:logger.exception(f"Error ConfigManager test:{e}")