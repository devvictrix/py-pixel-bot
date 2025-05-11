import json
import logging
import os
import sys # For pre-logging print target
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__) 

def load_environment_variables():
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    dotenv_path = project_root / ".env"
    
    # Override=True ensures that variables in .env take precedence over existing os environment variables.
    loaded_from_file = load_dotenv(dotenv_path=dotenv_path, override=True)
    app_env_value = os.getenv('APP_ENV') # Get it after attempting to load

    # Determine if main logger "py_pixel_bot" is already configured
    main_logger_configured = logging.getLogger("py_pixel_bot").hasHandlers()
    log_target_stream = sys.stderr if "WARNING" in (app_env_value or "") else sys.stdout

    message = ""
    log_level_for_print = "INFO"

    if loaded_from_file: # .env was found and processed
        message = f"load_dotenv successfully processed '{dotenv_path}'. APP_ENV is '{app_env_value}'"
    elif dotenv_path.exists(): # .env exists but load_dotenv might not have changed anything
        message = f"load_dotenv considered '{dotenv_path}'. Current APP_ENV is '{app_env_value}' (may have been pre-set and not overridden if override=False was used, but we use True)."
    else: # .env file does not exist
        message = f".env file not found at '{dotenv_path}'. Using system env vars or defaults. APP_ENV is '{app_env_value}'."
        log_level_for_print = "WARNING"
    
    if not app_env_value:
        message += " APP_ENV is not set. Logging will default to 'development'."
        log_level_for_print = "WARNING"

    if not main_logger_configured: # If logging isn't set up, print to console
        print(f"{log_level_for_print} (pre-logging): {message}", file=log_target_stream)
    else: # Logging is set up, use the logger
        if log_level_for_print == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

class ConfigManager:
    def __init__(self, profile_name: str = "example_profile.json"):
        self.profile_name = profile_name
        self.project_root_dir = Path(__file__).resolve().parent.parent.parent.parent
        self.profiles_dir = self.project_root_dir / "profiles"
        self.config_data = {} # Always initialize to an empty dict

        try:
            self._load_profile() # Attempt to load if file exists
        except FileNotFoundError:
            # This is not an error if the intention is to create a new profile (e.g., via add-region)
            # The caller (__main__.py) will decide if this is an error or an opportunity to init new config.
            logger.info(f"Profile '{self.profile_name}' not found. It may be created if using 'add-region'.")
            # No need to raise here; self.config_data remains {}
        except (json.JSONDecodeError, Exception) as e: # Catch other load errors
            logger.error(f"Failed to load profile '{self.profile_name}' due to error: {e}. Config will be empty.", exc_info=True)
            # self.config_data remains {}, but error logged. Caller might still proceed or exit.
            # Re-raising here would make ConfigManager unusable if a profile is corrupt.
            # Better to let __main__ handle if it wants to exit on this.

    def _load_profile(self):
        profile_path = self.profiles_dir / self.profile_name
        # This method is only called by __init__. If file not found, FileNotFoundError is raised.
        # If called at other times, and file must exist, caller should handle FileNotFoundError.
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile file not found at {profile_path}")

        logger.info(f"Attempting to load profile: {profile_path}")
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            self.config_data = loaded_data # Assign only on successful load
            logger.info(f"Successfully loaded profile: {self.profile_name}")
            if logger.getEffectiveLevel() <= logging.DEBUG:
                 logger.debug(f"Profile data for '{self.profile_name}': {json.dumps(self.config_data, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from profile file {profile_path}: {e.msg} at line {e.lineno} col {e.colno}")
            raise # Re-raise for constructor or __main__ to handle
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading profile {profile_path}: {e}", exc_info=True)
            raise # Re-raise

    def get_config(self) -> dict:
        return self.config_data # Will be {} if load failed or profile was new

    def add_region_to_config(self, region_name: str, region_coords: tuple) -> bool:
        if not region_name or not isinstance(region_name, str):
            logger.error("Cannot add region: Invalid region name provided."); return False
        if not (isinstance(region_coords, tuple) and len(region_coords) == 4 and all(isinstance(n, int) for n in region_coords)):
            logger.error(f"Cannot add region '{region_name}': Invalid coords {region_coords}. Expected (int,int,int,int)."); return False

        new_region_spec = {"name": region_name, "x": region_coords[0], "y": region_coords[1], "width": region_coords[2], "height": region_coords[3]}

        if "regions" not in self.config_data or not isinstance(self.config_data.get("regions"), list):
            self.config_data["regions"] = []
            logger.info("Initialized 'regions' list in config data.")

        found_existing = False
        for i, existing_region in enumerate(self.config_data["regions"]):
            if isinstance(existing_region, dict) and existing_region.get("name") == region_name:
                self.config_data["regions"][i] = new_region_spec
                logger.info(f"Updated existing region '{region_name}' with coords: {region_coords}")
                found_existing = True; break
        if not found_existing:
            self.config_data["regions"].append(new_region_spec)
            logger.info(f"Added new region '{region_name}' with coords: {region_coords}")
        return True

    def save_profile(self, profile_name_override: str = None):
        save_to_name = profile_name_override if profile_name_override else self.profile_name
        if not save_to_name:
            logger.error("Cannot save profile: No profile name specified or initialized."); raise ValueError("No profile name for saving.")
        if self.config_data == {} and not (self.profiles_dir / save_to_name).exists(): # Only warn if saving empty to a new file
            logger.warning(f"Attempting to save a potentially new profile '{save_to_name}' with empty or default config data. This is usually okay for 'add-region' on a new profile.")
        
        profile_path = self.profiles_dir / save_to_name
        logger.info(f"Attempting to save current config to profile: {profile_path}")
        try:
            self.profiles_dir.mkdir(parents=True, exist_ok=True) 
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4) 
            logger.info(f"Successfully saved profile: {profile_path}")
        except IOError as e: logger.error(f"IOError saving profile {profile_path}: {e}", exc_info=True); raise
        except TypeError as e: logger.error(f"TypeError serializing config for {profile_path}: {e}", exc_info=True); raise
        except Exception as e: logger.error(f"Unexpected error saving profile {profile_path}: {e}", exc_info=True); raise

    def get_regions(self) -> list: return self.get_config().get("regions", [])
    def get_rules(self) -> list: return self.get_config().get("rules", [])
    def get_monitoring_interval(self, default_interval: float = 1.0) -> float:
        try: # Ensure float conversion
            return float(self.get_config().get("settings", {}).get("monitoring_interval_seconds", default_interval))
        except (ValueError, TypeError):
            logger.warning(f"Invalid monitoring_interval_seconds in profile, using default {default_interval}s.")
            return default_interval

if __name__ == '__main__':
    load_environment_variables() 
    import sys; from pathlib import Path
    project_src_dir = Path(__file__).resolve().parent.parent.parent 
    if str(project_src_dir) not in sys.path: sys.path.insert(0, str(project_src_dir))
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging()
    test_logger_cm = logging.getLogger("py_pixel_bot.config_manager_test") 
    test_logger_cm.info("--- ConfigManager Test Start (save, add region to new/existing) ---")
    project_root_dir = project_src_dir.parent 
    test_profiles_dir = project_root_dir / "profiles"; test_profiles_dir.mkdir(exist_ok=True)
    
    existing_pfile = "cm_test_existing.json"
    existing_pfile_path = test_profiles_dir / existing_pfile
    initial_content = {"profile_description":"Existing", "regions":[{"name":"old_r","x":1,"y":1,"w":1,"h":1}]}
    with open(existing_pfile_path, 'w') as f: json.dump(initial_content, f, indent=4)
    test_logger_cm.info(f"Created {existing_pfile_path}")

    cm_existing = ConfigManager(profile_name=existing_pfile)
    cm_existing.add_region_to_config("new_r_in_existing", (10,10,10,10))
    cm_existing.save_profile()
    with open(existing_pfile_path, 'r') as f: data = json.load(f)
    assert len(data.get("regions",[])) == 2, "Failed to add region to existing profile"
    test_logger_cm.info(f"Verified adding region to existing profile '{existing_pfile}'")

    new_pfile = "cm_test_newly_created.json"
    new_pfile_path = test_profiles_dir / new_pfile
    if new_pfile_path.exists(): new_pfile_path.unlink()
    
    cm_new = None
    try:
        cm_new = ConfigManager(profile_name=new_pfile) # This will init with config_data={} due to FileNotFoundError
    except FileNotFoundError: # This means __init__ successfully re-raised, which __main__ would handle
         test_logger_cm.info(f"Correctly caught FileNotFoundError for new profile '{new_pfile}' in test.")
         cm_new = ConfigManager(profile_name=new_pfile) # For test, re-init to get name stored
         cm_new.config_data = { # Simulate __main__'s action for 'add-region' to new file
                "profile_description": f"Newly created for test: {new_pfile}",
                "settings": {"monitoring_interval_seconds": 1.0},
                "regions": [], "rules": [], "templates": []}
         test_logger_cm.info(f"Simulated initialization of new config for '{new_pfile}'")

    if cm_new:
        cm_new.add_region_to_config("first_r_in_new", (1,2,3,4))
        cm_new.save_profile()
        assert new_pfile_path.exists(), f"New profile '{new_pfile}' not created by save_profile."
        with open(new_pfile_path, 'r') as f: data_new = json.load(f)
        assert len(data_new.get("regions",[])) == 1, "Region not added to new file"
        test_logger_cm.info(f"Verified creating and adding region to new profile '{new_pfile}'")
    else:
        test_logger_cm.error("Failed to instantiate ConfigManager for new profile test logic.")

    test_logger_cm.info("--- ConfigManager Test End ---")