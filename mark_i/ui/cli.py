# File: mark_i/ui/cli.py
import argparse
import logging
import os
import sys
import time  # For simple sleep in run command
from typing import Optional # Added this line

# --- Placeholder Command Handlers ---
# Logger for this module, using hierarchical naming
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.cli")


def _validate_profile_path(profile_path_or_name: str, for_new_edit: bool = False) -> Optional[str]:
    """
    Validates the profile path.
    If it's a name, tries to resolve it against the default profiles directory.
    Returns the resolved absolute path if valid, or None.
    """
    if not profile_path_or_name:
        if for_new_edit:  # For 'edit' without a profile, this is fine to return None.
            return None
        logger.error("Profile path/name cannot be empty.")
        return None

    # Attempt to resolve using a temporary ConfigManager to leverage its path logic
    # This avoids duplicating path resolution logic here.
    try:
        from mark_i.core.config_manager import ConfigManager  # Local import

        # Create a temporary CM instance just for path resolution.
        # We don't want to load the profile here, just check existence if not for_new_edit.
        temp_cm_for_path_check = ConfigManager(profile_path_or_name, create_if_missing=True)  # create_if_missing=True to avoid FileNotFoundError if only name given
        resolved_path = temp_cm_for_path_check.get_profile_path()  # This will be absolute

        if for_new_edit:  # For 'edit' with a new profile name, path doesn't need to exist yet
            if resolved_path and not resolved_path.lower().endswith(".json"):
                logger.warning(f"Profile file '{resolved_path}' does not end with .json. GUI will enforce .json on save.")
            return resolved_path  # Return resolved path even if it doesn't exist yet

        # For 'run' or 'add-region', or 'edit existing', the file must exist
        if not resolved_path or not os.path.exists(resolved_path):
            logger.error(f"Profile file not found at resolved path: '{resolved_path}' (Original input: '{profile_path_or_name}')")
            return None

        if not resolved_path.lower().endswith(".json"):  # Should be caught by CM's _resolve_profile_path usually
            logger.warning(f"Profile file does not end with .json: {resolved_path}")
            # Allow continuation if it exists, GUI/CM will handle extension on save if needed.

        return resolved_path
    except ImportError:
        logger.error("ConfigManager could not be imported for profile path validation. CLI commands may fail.")
        # Fallback to simpler check if CM not available, though this is bad.
        if for_new_edit and profile_path_or_name:
            return os.path.abspath(profile_path_or_name)  # Assume it's a path
        if not os.path.exists(profile_path_or_name):
            logger.error(f"Profile file not found (basic check): {profile_path_or_name}")
            return None
        return os.path.abspath(profile_path_or_name)


def handle_run(args):
    logger.info(f"Executing 'run' command for profile input: {args.profile}")

    resolved_profile_path = _validate_profile_path(args.profile, for_new_edit=False)
    if not resolved_profile_path:
        sys.exit(1)  # _validate_profile_path logs error

    try:
        from mark_i.main_controller import MainController

        logger.debug("Successfully imported MainController for run command.")
    except ImportError as e:
        logger.critical(f"Failed to import MainController for 'run' command: {e}", exc_info=True)
        print(f"Error: Core components for running the bot could not be loaded: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        logger.info(f"Initializing MainController with resolved profile: '{resolved_profile_path}'.")
        controller = MainController(profile_name_or_path=resolved_profile_path)
        logger.info("MainController initialized. Starting monitoring loop...")
        controller.start()

        # Keep main thread alive while bot runs in daemon thread
        # Allows Ctrl+C to be caught by this main thread.
        while controller._monitor_thread and controller._monitor_thread.is_alive():
            time.sleep(0.5)
        logger.info("Monitoring loop has finished or was stopped from controller's perspective.")

    except FileNotFoundError:  # Should be caught by _validate_profile_path, but defensive
        logger.error(f"Profile file '{resolved_profile_path}' not found during MainController init.")
        print(f"Error: Profile file '{resolved_profile_path}' not found.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, IOError) as e_profile_load:  # Catch profile loading/parsing errors from MC init
        logger.error(f"Error loading profile '{resolved_profile_path}': {e_profile_load}", exc_info=True)
        print(f"Error: Could not load profile '{resolved_profile_path}'. Invalid format or read error: {e_profile_load}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Ctrl+C received in CLI 'run' command. Signaling bot to stop...")
        if "controller" in locals() and controller:  # Ensure controller was initialized
            controller.stop()  # Graceful stop
    except Exception as e:
        logger.critical(f"An unexpected error occurred during 'run' command execution: {e}", exc_info=True)
        if "controller" in locals() and controller:
            controller.stop()  # Attempt to stop if error
    finally:
        # Ensure controller is stopped if it might still be running, e.g., after an error
        if "controller" in locals() and controller and controller._monitor_thread and controller._monitor_thread.is_alive():
            logger.info("Ensuring bot is stopped due to 'run' command completion or error.")
            controller.stop()
        logger.info("Bot 'run' command finished.")


def handle_edit(args):
    profile_input_for_edit = args.profile  # This can be None for a new profile
    resolved_profile_path_for_edit: Optional[str] = None

    if profile_input_for_edit:  # If a profile was specified
        resolved_profile_path_for_edit = _validate_profile_path(profile_input_for_edit, for_new_edit=False)  # Must exist if specified
        if not resolved_profile_path_for_edit:
            logger.error(f"Specified profile '{profile_input_for_edit}' not found or invalid. Cannot open for editing.")
            print(f"Error: Profile '{profile_input_for_edit}' not found or invalid.", file=sys.stderr)
            sys.exit(1)
        logger.info(f"Executing 'edit' command. Profile to open: {resolved_profile_path_for_edit}")
    else:  # No profile specified, means "new profile"
        logger.info(f"Executing 'edit' command. Opening editor for a new profile.")
        # resolved_profile_path_for_edit remains None

    try:
        from mark_i.ui.gui.main_app_window import MainAppWindow

        logger.debug("Successfully imported MainAppWindow for edit command.")
    except ImportError as e:
        logger.critical(f"Failed to import GUI components (MainAppWindow): {e}", exc_info=True)
        print(f"Error: GUI components could not be loaded: {e}. Is CustomTkinter installed?", file=sys.stderr)
        sys.exit(1)

    try:
        logger.info(f"Initializing MainAppWindow. Profile to load: {resolved_profile_path_for_edit if resolved_profile_path_for_edit else 'New Profile'}")
        app_gui = MainAppWindow(initial_profile_path=resolved_profile_path_for_edit)
        logger.info("MainAppWindow initialized. Starting GUI main loop...")
        app_gui.mainloop()
        logger.info("GUI main loop finished.")
    except SystemExit:
        logger.warning(f"GUI initiated a system exit (e.g., user closed window prompting save).")
        # Allow system exit to propagate
    except Exception as e:
        logger.error(f"An error occurred while trying to launch or run the GUI editor: {e}", exc_info=True)
        print(f"An error occurred with the GUI editor: {e}", file=sys.stderr)
        sys.exit(1)


def handle_add_region(args):  # Legacy, MainAppWindow's "Add Region" is preferred
    logger.warning("'add-region' CLI command is legacy. Please use 'edit' command and the main GUI's 'Add Region' button.")
    logger.info(f"Executing legacy 'add-region' command for profile: {args.profile}")

    resolved_profile_path = _validate_profile_path(args.profile, for_new_edit=False)
    if not resolved_profile_path:
        sys.exit(1)

    try:
        from mark_i.ui.gui.region_selector import RegionSelectorWindow
        from mark_i.core.config_manager import ConfigManager

        logger.debug("Successfully imported RegionSelectorWindow and ConfigManager for add-region.")
    except ImportError as e:
        logger.critical(f"Failed to import necessary modules for 'add-region': {e}", exc_info=True)
        print(f"Error: Core components for region selection could not be loaded: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        logger.info(f"Loading profile {resolved_profile_path} for region selection tool.")
        # RegionSelectorWindow needs a ConfigManager for the profile being edited.
        # It doesn't save directly TO this CM, but uses it for context (e.g., existing region names if needed).
        # The MainAppWindow now handles saving changes made via RegionSelector.
        cm_for_region_selector_context = ConfigManager(profile_name_or_path=resolved_profile_path, create_if_missing=False)

        # RegionSelectorWindow typically needs a master CTk window.
        # For CLI invocation, we can create a temporary hidden root.
        import customtkinter as ctk  # Local import for this specific use

        temp_root = ctk.CTk()
        temp_root.withdraw()  # Hide the temporary root window

        logger.info("Initializing RegionSelectorWindow...")
        region_selector_app = RegionSelectorWindow(
            master=temp_root, config_manager_for_saving_path_only=cm_for_region_selector_context, existing_region_data=None  # Pass the CM  # For 'add new' via CLI, no existing data to pre-fill
        )
        # region_selector_app.mainloop() # This blocks and is not ideal for CLI.
        # RegionSelectorWindow is modal (grab_set). It should handle its own loop if shown.
        # The main use case for RegionSelectorWindow is now from MainAppWindow, which handles the modal loop.
        # For CLI, this interaction model is a bit broken as it expects a GUI loop.
        # A true CLI region add would need a different non-GUI mechanism or different GUI interaction.
        logger.warning("CLI 'add-region' is deprecated. RegionSelectorWindow will likely not function as expected without a parent GUI managing its lifecycle. Use 'edit' command.")

        # Simulate a short display if it were to run, then destroy.
        # This is mostly for conceptual completeness of the handler, though its utility is low.
        temp_root.deiconify()  # Show it briefly
        temp_root.after(3000, temp_root.destroy)  # Auto-close after 3s for demo
        temp_root.mainloop()  # Start its loop

        # Logic to actually get data back and save it to the profile via ConfigManager would be here,
        # but RegionSelectorWindow is designed to be called by MainAppWindow which handles the data.
        # e.g., if region_selector_app.saved_region_info: ... cm_for_region_selector_context.add_region(...).save_current_profile()

        logger.info("RegionSelectorWindow (legacy CLI call) finished or timed out.")
    except Exception as e:
        logger.error(f"An error occurred with the RegionSelectorWindow via CLI: {e}", exc_info=True)
        print(f"An error occurred with the Region Selector via CLI: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if "temp_root" in locals() and temp_root.winfo_exists():
            temp_root.destroy()


def create_parser():
    parser = argparse.ArgumentParser(description="Mark-I: AI-Powered Visual Desktop Automation Tool.")
    parser.add_argument("-v", "--verbose", action="store_const", const=logging.DEBUG, default=logging.INFO, help="Increase console logging verbosity to DEBUG.")
    parser.add_argument("--log-file", type=str, default=None, help="Specify a custom path for the log file for this session.")
    parser.add_argument("--no-file-logging", action="store_true", help="Disable file logging for this session.")

    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a bot profile.")
    run_parser.add_argument("profile", help="Path or name of the bot profile JSON file (e.g., my_bot or profiles/my_bot.json).")
    run_parser.set_defaults(func=handle_run)

    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Edit or create a bot profile using the GUI.")
    edit_parser.add_argument(
        "profile",
        nargs="?",
        default=None,  # Optional: path/name of profile to open
        help="Optional: Path or name of a bot profile JSON file to open (e.g., my_bot). If omitted, opens editor for a new profile.",
    )
    edit_parser.set_defaults(func=handle_edit)

    # Add-region command (legacy)
    add_region_parser = subparsers.add_parser("add-region", help="[LEGACY] Add/edit a region for a profile using GUI tool. Use 'edit' instead.")
    add_region_parser.add_argument("profile", help="Path or name of the bot profile JSON file.")
    add_region_parser.set_defaults(func=handle_add_region)

    return parser