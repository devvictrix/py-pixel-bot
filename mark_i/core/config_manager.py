import json
import logging
import os
from typing import Dict, Any, Optional, List
import copy  # For deepcopying default profile structure
import sys  # For printing to stderr in critical failure

import dotenv  # For loading .env files

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME  # Use the app's root for consistency if desired

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.core.config_manager")
# Alternatively, for strict module-level logging:
# logger = logging.getLogger(__name__)


# Constants for directory and file names
PROFILES_DIR_NAME = "profiles"
TEMPLATES_SUBDIR_NAME = "templates"


def load_environment_variables():
    """
    Loads environment variables from a .env file located in the project root.
    The project root is determined by navigating up from this file's location.
    This function should be called once at application startup, typically by __main__.py.

    Key variables expected:
        - APP_ENV: (e.g., development, uat, production) for logging configuration.
        - GEMINI_API_KEY: (for v4.0.0+ Gemini features).
    """
    try:
        # Determine project root: project_root/mark_i/core/config_manager.py -> project_root/
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        # package_dir is 'mark_i'
        package_dir = os.path.dirname(current_file_dir)
        # project_root is the parent of 'mark_i'
        project_root = os.path.dirname(package_dir)

        dotenv_path = os.path.join(project_root, ".env")

        if os.path.exists(dotenv_path):
            # load_dotenv returns True if it found and loaded the file, False otherwise.
            # Some versions might return the number of variables loaded.
            # Checking for a "truthy" value is generally safe.
            was_loaded = dotenv.load_dotenv(dotenv_path, override=True)  # Override OS vars with .env vars
            if was_loaded:
                logger.info(f"Successfully loaded environment variables from: {dotenv_path}")
            else:
                logger.warning(f".env file found at {dotenv_path}, but python-dotenv reported no new variables loaded. File might be empty, malformed, or all variables already set in OS.")
        else:
            logger.info(f".env file not found at {dotenv_path}. Application will rely on OS-level environment variables or defaults.")

        # Log status of key environment variables for diagnostics
        app_env_val = os.getenv("APP_ENV")
        gemini_key_val = os.getenv("GEMINI_API_KEY")

        logger.info(f"APP_ENV after .env load attempt: '{app_env_val if app_env_val else 'Not Set (logging_setup will use default)'}'")
        if gemini_key_val:
            # Avoid logging the key itself, just its presence and length for confirmation
            logger.info(f"GEMINI_API_KEY after .env load attempt: Detected (length: {len(gemini_key_val)})")
        else:
            logger.warning("GEMINI_API_KEY after .env load attempt: Not Set or Empty. Gemini-dependent features will be unavailable or fail.")

    except Exception as e:
        # Use basic print to stderr if logging isn't (or might not be) configured yet
        print(f"ERROR: Critical failure during environment variable loading: {e}", file=sys.stderr)
        # Also attempt to log it, in case logging was partially set up
        logger.critical(f"Failed to load environment variables: {e}", exc_info=True)
        # Depending on how critical .env is, might sys.exit(1) here. For now, allow continuation.


class ConfigManager:
    """
    Manages loading, accessing, validating, and saving bot profile configurations
    (JSON files). It also handles path resolution for profiles and their
    associated assets like templates. Ensures basic profile structure keys exist
    when data is loaded or created by merging with a default structure.
    """

    def __init__(self, profile_path_or_name: Optional[str] = None, create_if_missing: bool = False):
        """
        Initializes the ConfigManager.

        If profile_path_or_name is provided, it attempts to load that profile.
        If create_if_missing is True and the profile doesn't exist (or no path/name
        is given), it initializes with a default profile structure in memory.

        Args:
            profile_path_or_name: The name of the profile (assumed to be in the default
                                  profiles directory, e.g., "my_bot_profile") or a
                                  full/relative path to a .json profile file. If None and
                                  create_if_missing is True, prepares for a new, unsaved profile.
            create_if_missing: If True and the specified profile doesn't exist, a new
                               default profile structure will be initialized in memory.
                               If False (default) and profile not found, FileNotFoundError is raised.
        """
        self.project_root = self._find_project_root()
        self.profiles_base_dir = os.path.join(self.project_root, PROFILES_DIR_NAME)
        # Ensure the base directory for profiles exists
        try:
            os.makedirs(self.profiles_base_dir, exist_ok=True)
        except OSError as e:
            logger.error(f"Could not create base profiles directory '{self.profiles_base_dir}': {e}. Profiles may not save correctly to default location.", exc_info=True)
            # Continue, but saving to default location might fail if it's not project root.

        self.profile_path: Optional[str] = None  # Absolute path to the current .json file
        self.profile_data: Dict[str, Any] = {}  # In-memory representation of the profile

        if profile_path_or_name:
            self.profile_path = self._resolve_profile_path(profile_path_or_name)
            if os.path.exists(self.profile_path):
                self._load_profile()  # Loads into self.profile_data
            elif create_if_missing:
                logger.info(f"Profile file '{self.profile_path}' not found. Initializing with default structure for a new profile (as create_if_missing=True).")
                self._initialize_default_profile_data()  # Sets self.profile_data
            else:
                # Profile path specified, does not exist, and not creating: error.
                logger.error(f"Profile file not found at resolved path '{self.profile_path}' and create_if_missing is False.")
                raise FileNotFoundError(f"Profile file not found: {self.profile_path}")
        elif create_if_missing:  # No path/name given, but create_if_missing is true (e.g., GUI "New Profile")
            logger.info("No profile path/name provided, but create_if_missing is True. Initializing new default profile in memory. Profile path is currently None.")
            self._initialize_default_profile_data()  # self.profile_path remains None
        else:
            # No path/name and not create_if_missing. This is a valid state for an
            # empty ConfigManager instance if the application logic handles it (e.g. MainAppWindow).
            # For safety, still initialize with a default structure.
            logger.debug("ConfigManager initialized without loading or creating a specific profile (no path/name, create_if_missing=False). Using default empty structure.")
            self._initialize_default_profile_data()

        if self.profile_path or create_if_missing:  # Log if we attempted to load/create
            logger.info(f"ConfigManager initialized. Current profile target: '{self.profile_path if self.profile_path else 'New Unsaved Profile'}'.")

    def _initialize_default_profile_data(self):
        """
        Sets self.profile_data to a deep copy of the default profile structure,
        ensuring all essential top-level keys and basic settings exist.
        """
        # Local import to avoid potential circular dependencies at module load time,
        # as gui_config might indirectly import from core.
        try:
            from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE
        except ImportError:  # Fallback if GUI components are somehow not in path during very specific uses
            logger.error("Failed to import DEFAULT_PROFILE_STRUCTURE from gui_config. Using an internal minimal default.")
            DEFAULT_PROFILE_STRUCTURE = {  # Minimal internal fallback
                "profile_description": "New Profile (Minimal Default)",
                "settings": {"monitoring_interval_seconds": 1.0, "analysis_dominant_colors_k": 3, "gemini_default_model_name": "gemini-1.5-flash-latest"},
                "regions": [],
                "templates": [],
                "rules": [],
            }

        self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        # Ensure essential keys are present even if default structure changes
        self.profile_data.setdefault("profile_description", "New Profile")
        self.profile_data.setdefault("settings", {})
        self.profile_data["settings"].setdefault("monitoring_interval_seconds", 1.0)
        self.profile_data["settings"].setdefault("analysis_dominant_colors_k", 3)
        self.profile_data["settings"].setdefault("gemini_default_model_name", "gemini-1.5-flash-latest")
        self.profile_data["settings"].setdefault("tesseract_cmd_path", None)  # Ensure it exists
        self.profile_data["settings"].setdefault("tesseract_config_custom", "")  # Ensure it exists
        self.profile_data.setdefault("regions", [])
        self.profile_data.setdefault("templates", [])
        self.profile_data.setdefault("rules", [])
        logger.debug("Initialized in-memory profile_data with default structure.")

    def _find_project_root(self) -> str:
        """Determines the project root directory."""
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        package_dir = os.path.dirname(current_file_dir)
        project_root_dir = os.path.dirname(package_dir)
        logger.debug(f"Project root determined as: {project_root_dir}")
        return project_root_dir

    def _resolve_profile_path(self, profile_path_or_name: str) -> str:
        """
        Resolves a profile name or a partial/full path to an absolute .json file path.
        Appends .json extension if not present.
        """
        path_input = profile_path_or_name.strip()
        if not path_input:
            default_filename = "untitled.json"
            logger.warning(f"Empty profile path or name provided. Defaulting to '{default_filename}' in profiles directory: '{os.path.join(self.profiles_base_dir, default_filename)}'")
            return os.path.abspath(os.path.join(self.profiles_base_dir, default_filename))

        # Ensure .json extension
        if not path_input.lower().endswith(".json"):
            path_with_ext = f"{path_input}.json"
        else:
            path_with_ext = path_input

        if os.path.isabs(path_with_ext):
            logger.debug(f"Resolved '{profile_path_or_name}' as absolute path: '{path_with_ext}'")
            return path_with_ext

        # Check if it contains path separators (could be relative to project root or CWD)
        # This handles both '/' and '\' correctly on relevant OS
        if os.sep in path_with_ext or (os.altsep and os.altsep in path_with_ext):
            # Try resolving relative to project root first, as this is common for CLI usage
            path_rel_to_project = os.path.join(self.project_root, path_with_ext)
            # A simple check: if the directory part of this resolved path exists, assume it's valid.
            # This isn't foolproof but better than just CWD.
            if os.path.exists(os.path.dirname(os.path.abspath(path_rel_to_project))):
                logger.debug(f"Resolved '{profile_path_or_name}' as project-relative path: '{os.path.abspath(path_rel_to_project)}'")
                return os.path.abspath(path_rel_to_project)
            # Fallback: resolve relative to current working directory if not clearly project-relative or dir doesn't exist yet.
            # This is how filedialog would behave for relative paths if base dir not set.
            logger.debug(f"Resolved '{profile_path_or_name}' as CWD-relative path: '{os.path.abspath(path_with_ext)}' (project-relative check failed or dir non-existent).")
            return os.path.abspath(path_with_ext)

        # If no path separators, treat as a simple name to be found in self.profiles_base_dir
        resolved_path_in_profiles_dir = os.path.join(self.profiles_base_dir, path_with_ext)
        logger.debug(f"Resolved '{profile_path_or_name}' as profile name in default profiles_base_dir: '{os.path.abspath(resolved_path_in_profiles_dir)}'")
        return os.path.abspath(resolved_path_in_profiles_dir)

    def _load_profile(self):
        """
        Loads the JSON profile data from `self.profile_path` into `self.profile_data`.
        Merges loaded data with defaults to ensure all expected top-level keys and
        basic settings are present, providing some backward compatibility.
        """
        if not self.profile_path or not os.path.exists(self.profile_path):
            logger.error(f"Cannot load profile: Path '{self.profile_path}' is invalid or file does not exist. Initializing with default data.")
            self._initialize_default_profile_data()
            # In strict mode, we might raise FileNotFoundError here.
            # For GUI resilience, loading a default is often preferred over crashing.
            return

        logger.info(f"Loading profile from: {self.profile_path}")
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                loaded_data_from_file = json.load(f)

            # Merge with default structure to ensure all keys exist and add new default settings
            # Local import to avoid potential circular dependencies
            from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE

            # Start with a deep copy of the default structure
            merged_profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)

            # Update top-level keys from loaded_data if they exist and match type (for lists/dicts)
            for key, default_value_type_example in DEFAULT_PROFILE_STRUCTURE.items():
                if key in loaded_data_from_file:
                    if isinstance(default_value_type_example, dict) and isinstance(loaded_data_from_file[key], dict):
                        # For 'settings' dictionary, merge to preserve existing user settings
                        # and add any new default settings from DEFAULT_PROFILE_STRUCTURE.
                        merged_profile_data[key] = {**default_value_type_example, **loaded_data_from_file[key]}
                    elif isinstance(default_value_type_example, list) and isinstance(loaded_data_from_file[key], list):
                        # For lists like regions, templates, rules, take the user's list entirely.
                        merged_profile_data[key] = copy.deepcopy(loaded_data_from_file[key])
                    elif not isinstance(default_value_type_example, (dict, list)):  # Simple values
                        merged_profile_data[key] = loaded_data_from_file[key]
                    # else: type mismatch, keep default. Log warning?

            self.profile_data = merged_profile_data
            logger.info(f"Profile '{os.path.basename(self.profile_path)}' loaded and merged with defaults successfully.")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from profile '{self.profile_path}': {e}. Loading default profile structure instead.", exc_info=True)
            self._initialize_default_profile_data()
            # Propagate error for UI to handle
            raise ValueError(f"Invalid JSON in profile file: {self.profile_path}. Error: {e}")
        except Exception as e:  # Catch other IOErrors, etc.
            logger.error(f"Failed to load profile '{self.profile_path}' due to an unexpected error: {e}. Loading default profile structure.", exc_info=True)
            self._initialize_default_profile_data()
            raise IOError(f"Could not read or process profile file: {self.profile_path}. Error: {e}")

    def get_profile_data(self) -> Dict[str, Any]:
        """Returns a deep copy of the current in-memory profile data."""
        return copy.deepcopy(self.profile_data)

    def update_profile_data(self, new_data: Dict[str, Any]):
        """
        Updates the in-memory `self.profile_data` with `new_data`.
        Typically called by the GUI editor before saving.
        It performs a merge with default structure to ensure integrity.
        """
        from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE  # Local import

        merged_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)  # Start with defaults
        for key, default_value_type_example in DEFAULT_PROFILE_STRUCTURE.items():
            if key in new_data:
                if isinstance(default_value_type_example, dict) and isinstance(new_data[key], dict):
                    merged_data[key] = {**default_value_type_example, **new_data[key]}  # Merge dicts (e.g. settings)
                else:  # For lists or simple values, new_data takes precedence
                    merged_data[key] = copy.deepcopy(new_data[key])
            # If key from default is not in new_data, it remains as default from merged_data initialization

        self.profile_data = merged_data
        logger.info("In-memory profile data updated (merged with defaults). Ready for saving.")

    def get_profile_path(self) -> Optional[str]:
        """Returns the absolute path of the current profile file, or None if unsaved."""
        return self.profile_path

    def get_profile_name(self) -> str:
        """Returns the filename (basename) of the current profile, or 'Unsaved Profile'."""
        if self.profile_path:
            return os.path.basename(self.profile_path)
        return "Unsaved Profile"  # Consistent name for new/unsaved profiles

    def get_profile_base_path(self) -> Optional[str]:
        """Returns the directory containing the current profile file, or None if unsaved."""
        if self.profile_path:
            return os.path.dirname(self.profile_path)
        # logger.warning("Requested profile base path, but current profile is unsaved or its path is not set.")
        return None

    def get_template_image_path(self, template_filename: str) -> Optional[str]:
        """Constructs the full absolute path to a template image file, relative to the current profile's location."""
        profile_base = self.get_profile_base_path()
        if not profile_base:
            logger.warning(f"Cannot get template path for '{template_filename}': Profile is unsaved, base path unknown.")
            return None
        if not template_filename or not isinstance(template_filename, str):
            logger.warning(f"Invalid template filename '{template_filename}' provided.")
            return None

        # Templates are expected in a 'templates' subdirectory next to the profile .json file
        template_dir = os.path.join(profile_base, TEMPLATES_SUBDIR_NAME)
        return os.path.join(template_dir, template_filename)

    def get_setting(self, key: str, default: Optional[Any] = None) -> Any:
        """Safely retrieves a value from the 'settings' dictionary in the profile data."""
        return self.profile_data.get("settings", {}).get(key, default)

    def get_regions(self) -> List[Dict[str, Any]]:
        """Returns a copy of the list of region configurations."""
        return copy.deepcopy(self.profile_data.get("regions", []))

    def get_region_config(self, region_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves a copy of a specific region's configuration by its name."""
        for region in self.profile_data.get("regions", []):  # Iterate internal data
            if region.get("name") == region_name:
                return copy.deepcopy(region)
        logger.debug(f"Region named '{region_name}' not found in current profile.")
        return None

    def get_templates(self) -> List[Dict[str, Any]]:
        """Returns a copy of the list of template configurations."""
        return copy.deepcopy(self.profile_data.get("templates", []))

    def get_rules(self) -> List[Dict[str, Any]]:
        """Returns a copy of the list of rule configurations."""
        return copy.deepcopy(self.profile_data.get("rules", []))

    def get_all_region_configs(self) -> Dict[str, Dict[str, Any]]:
        """Returns a dictionary of copies of all region configurations, keyed by region name."""
        return {
            region.get("name", f"UnnamedRegion_idx{i}"): copy.deepcopy(region)
            for i, region in enumerate(self.profile_data.get("regions", []))
            if region.get("name")  # Ensure region has a name to be used as key
        }

    @staticmethod
    def save_profile_data_to_path(filepath: str, data_to_save: Dict[str, Any]):
        """
        Static method to save provided profile data to a specified filepath.
        Ensures parent directory for the profile and its 'templates' subdirectory exist.
        """
        logger.info(f"Attempting to save profile data to: {filepath}")
        if not filepath or not isinstance(filepath, str):
            err_msg = "Invalid filepath provided for saving profile."
            logger.error(err_msg)
            raise ValueError(err_msg)
        if not isinstance(data_to_save, dict):
            err_msg = "Invalid data_to_save provided (not a dictionary)."
            logger.error(err_msg)
            raise ValueError(err_msg)

        try:
            profile_dir = os.path.dirname(filepath)
            if profile_dir:  # If filepath includes a directory part (it should for absolute paths)
                os.makedirs(profile_dir, exist_ok=True)

            # Ensure the templates subdirectory exists next to (or within if profile_dir is base) the profile
            templates_dir_path = os.path.join(profile_dir if profile_dir else os.getcwd(), TEMPLATES_SUBDIR_NAME)
            os.makedirs(templates_dir_path, exist_ok=True)
            logger.debug(f"Ensured templates directory exists at: {templates_dir_path}")

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4)
            logger.info(f"Profile data successfully saved to: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save profile data to '{filepath}': {e}", exc_info=True)
            raise IOError(f"Could not save profile to file: {filepath}. Error: {e}")  # Re-raise for caller

    def save_current_profile(self, new_path_or_name: Optional[str] = None) -> bool:
        """
        Saves the current in-memory `self.profile_data`.
        If `new_path_or_name` is provided, it updates `self.profile_path` and saves to the
        new location (effectively a "Save As" operation).
        Otherwise, it saves to the existing `self.profile_path` ("Save" operation).
        A profile must have a path (either initially set or via `new_path_or_name`) to be saved.

        Args:
            new_path_or_name: Optional. If provided, resolves this to an absolute path
                              and sets it as the current `self.profile_path`.

        Returns:
            True if save was successful, False otherwise.
        """
        if new_path_or_name:  # "Save As" intent or setting path for a new profile
            resolved_new_path = self._resolve_profile_path(new_path_or_name)
            if not resolved_new_path:  # Should be handled by _resolve_profile_path returning a default
                logger.error(f"Cannot save profile: New path '{new_path_or_name}' could not be validly resolved.")
                return False
            self.profile_path = resolved_new_path  # Update current path
            logger.info(f"Profile path set to '{self.profile_path}' for saving.")

        if not self.profile_path:
            logger.error("Cannot save profile: `self.profile_path` is not set. Use 'Save As' functionality by providing a path/name.")
            # This indicates a logical error in the calling code (e.g., GUI didn't prompt for filename for new profile)
            return False

        try:
            ConfigManager.save_profile_data_to_path(self.profile_path, self.profile_data)
            return True
        except (IOError, ValueError) as e:  # Catch errors from the static save method
            logger.error(f"Saving current profile to '{self.profile_path}' failed: {e}")
            return False
