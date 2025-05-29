import argparse
import logging
import os
import sys

# --- Placeholder Command Handlers ---
logger = logging.getLogger(__name__)

print(
    "DEBUG: mark_i.ui.cli module IS BEING LOADED AND EXECUTED."
)  # Add this at the very top


def _validate_profile_path(profile_path, for_new_edit=False):
    if not profile_path:
        if for_new_edit:  # For 'edit' without a profile, this is fine.
            return True
        logger.error("Profile path cannot be empty.")
        return False
    if not for_new_edit and not os.path.exists(profile_path):
        logger.error(f"Profile file not found: {profile_path}")
        return False
    if profile_path and not profile_path.endswith(".json"):
        logger.warning(f"Profile file does not end with .json: {profile_path}")
    return True


def handle_run(args):
    logger.info(f"Executing 'run' command for profile: {args.profile}")
    if not _validate_profile_path(args.profile):
        sys.exit(1)
    try:
        # Adjusted import paths based on typical project structure
        from mark_i.core.config_manager import ConfigManager
        from mark_i.main_controller import MainController

        logger.debug(
            "Successfully imported ConfigManager and MainController for run command."
        )
    except ImportError as e:
        logger.error(
            f"Failed to import necessary modules for 'run' command: {e}", exc_info=True
        )
        print(
            f"Error: Core components for running the bot could not be loaded: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.info(f"Attempting to load profile: {args.profile}")
    # ConfigManager now expects profile_path_or_name
    config_manager = ConfigManager(profile_path_or_name=args.profile)
    if not config_manager.profile_data or not config_manager.profile_path:
        logger.error(
            f"Failed to load profile data from {args.profile}. Check profile existence and format."
        )
        print(f"Error: Could not load profile {args.profile}.", file=sys.stderr)
        sys.exit(1)

    logger.info(f"Profile '{args.profile}' loaded. Initializing MainController.")
    # MainController also expects profile_name_or_path
    controller = MainController(profile_name_or_path=args.profile)
    logger.info("MainController initialized. Starting monitoring loop...")
    controller.start()
    try:
        # A better check would be a method in MainController, e.g., controller.is_running()
        # For now, assume thread presence implies running for a simple test
        while controller._monitor_thread and controller._monitor_thread.is_alive():
            import time
            time.sleep(0.5) # Keep main thread alive while bot runs
        logger.info("Monitoring loop has finished or was stopped.")
    except KeyboardInterrupt:
        logger.info("Ctrl+C received in CLI. Signaling bot to stop...")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred in the main CLI loop: {e}", exc_info=True
        )
    finally:
        # Ensure controller is stopped if it was started and might still be running
        if controller._monitor_thread and controller._monitor_thread.is_alive(): # Check if it was ever started
            logger.info("Ensuring bot is stopped...")
            controller.stop()
        logger.info("Bot run command finished.")


def handle_edit(args):
    logger.info(
        f"Executing 'edit' command. Profile to open: {args.profile if args.profile else 'New Profile'}"
    )
    profile_to_load = args.profile
    if args.profile and not _validate_profile_path(args.profile, for_new_edit=False):
        logger.error(
            f"Specified profile '{args.profile}' not found or invalid. Cannot open for editing."
        )
        print(f"Error: Profile '{args.profile}' not found or invalid.", file=sys.stderr)
        sys.exit(1)
    try:
        from mark_i.ui.gui.main_app_window import MainAppWindow # Adjusted import

        logger.debug("Successfully imported MainAppWindow for edit command.")
    except ImportError as e:
        logger.error(
            f"Failed to import GUI components (MainAppWindow): {e}", exc_info=True
        )
        print(
            f"Error: GUI components could not be loaded: {e}. Is CustomTkinter installed?",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        logger.info(f"Initializing MainAppWindow. Profile to load: {profile_to_load}")
        # Corrected argument name here
        app_gui = MainAppWindow(initial_profile_path=profile_to_load) 
        logger.info("MainAppWindow initialized. Starting GUI main loop...")
        app_gui.mainloop()
        logger.info("GUI main loop finished.")
    except SystemExit: # Allow SystemExit to propagate for clean exits
        logger.warning(f"GUI initiated a system exit.")
        raise
    except Exception as e:
        logger.error(
            f"An error occurred while trying to launch or run the GUI: {e}",
            exc_info=True,
        )
        print(f"An error occurred with the GUI: {e}", file=sys.stderr)
        sys.exit(1)


def handle_add_region(args):
    logger.info(f"Executing 'add-region' command for profile: {args.profile}")
    if not _validate_profile_path(args.profile):
        sys.exit(1)
    try:
        from mark_i.ui.gui.region_selector import RegionSelectorWindow # Adjusted import
        from mark_i.core.config_manager import ConfigManager # Adjusted import

        logger.debug(
            "Successfully imported RegionSelectorWindow and ConfigManager for add-region."
        )
    except ImportError as e:
        logger.error(
            f"Failed to import necessary modules for 'add-region': {e}", exc_info=True
        )
        print(
            f"Error: Core components for region selection could not be loaded: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    logger.info(f"Loading profile {args.profile} for region selection.")
    config_manager = ConfigManager(profile_path_or_name=args.profile)
    if not config_manager.profile_data or not config_manager.profile_path:
        logger.error(f"Failed to load profile {args.profile} for region selection.")
        print(
            f"Error: Could not load profile {args.profile} to add/edit region.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        logger.info("Initializing RegionSelectorWindow.")
        # RegionSelectorWindow might need a master, for CLI it can create its own hidden root
        # Or we create a simple CTk root here if needed.
        # For now, assume CTkToplevel handles master=None if it's the only window.
        # If RegionSelectorWindow requires a master explicitly from CTk:
        import customtkinter as ctk
        temp_root = ctk.CTk() # Create a temporary root
        temp_root.withdraw() # Hide it
        
        region_selector_app = RegionSelectorWindow(master=temp_root, config_manager=config_manager)
        region_selector_app.mainloop() # This might block here.
        # If it's a modal dialog, it should return control after closing.
        
        if temp_root.winfo_exists(): # Clean up temp root if created
            temp_root.destroy()
            
        logger.info("RegionSelectorWindow finished.")
    except Exception as e:
        logger.error(
            f"An error occurred with the RegionSelectorWindow: {e}", exc_info=True
        )
        print(f"An error occurred with the Region Selector: {e}", file=sys.stderr)
        sys.exit(1)


def create_parser():
    print(
        "DEBUG: create_parser() function in mark_i.ui.cli IS CALLED."
    )  # Add this
    parser = argparse.ArgumentParser(
        description="PyPixelBot: Visual Desktop Automation Tool."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
        help="Increase console logging verbosity to DEBUG.",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Specify a custom path for the log file for this session.",
    )
    parser.add_argument(
        "--no-file-logging",
        action="store_true",
        help="Disable file logging for this session.",
    )
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )
    run_parser = subparsers.add_parser("run", help="Run a bot profile.")
    run_parser.add_argument("profile", help="Path to the bot profile JSON file.")
    run_parser.set_defaults(func=handle_run)
    edit_parser = subparsers.add_parser(
        "edit", help="Edit a bot profile using the GUI."
    )
    edit_parser.add_argument(
        "profile",
        nargs="?",
        default=None,
        help="Optional path to a bot profile JSON file to open.",
    )
    edit_parser.set_defaults(func=handle_edit)
    add_region_parser = subparsers.add_parser(
        "add-region", help="Add/edit a region for a profile using GUI tool (legacy)."
    )
    add_region_parser.add_argument("profile", help="Path to the bot profile JSON file.")
    add_region_parser.set_defaults(func=handle_add_region)
    return parser


print(
    "DEBUG: mark_i.ui.cli module finished loading. create_parser IS DEFINED."
)  # Add this at the end