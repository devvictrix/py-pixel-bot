import argparse
import logging
import sys
import os
import time # For the sleep in handle_run to keep main thread alive for bot

# Path setup for CLI direct execution (less common, main entry is __main__.py)
# This attempts to make the script runnable for development/testing if called directly,
# e.g., `python src/py_pixel_bot/ui/cli.py run ...` (though this is not the primary way)
if __package__ is None or "." not in __package__: # Heuristic for direct script run
    # If run as script, __file__ is path to cli.py
    # ui_dir = os.path.dirname(os.path.abspath(__file__)) # py-pixel-bot/src/py_pixel_bot/ui/
    # py_pixel_bot_dir = os.path.dirname(ui_dir) # py-pixel-bot/src/py_pixel_bot/
    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # py-pixel-bot/src/
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        # Initial log, may go to stderr if full logging not yet configured by a higher-level entry point
        logging.getLogger(__name__).info(f"cli.py: Added '{src_dir}' to sys.path for direct script testing.")

# These imports should work if path is correct (either via `python -m` or above adjustment)
from py_pixel_bot.main_controller import MainController
from py_pixel_bot.core.config_manager import ConfigManager 
# GUI imports are done dynamically within their handler functions to avoid
# making GUI libraries a hard dependency if only CLI parts are used,
# and to prevent GUI windows from trying to init if not intended.

logger = logging.getLogger(__name__) # Uses 'py_pixel_bot.ui.cli' due to package structure

def create_parser() -> argparse.ArgumentParser:
    """Creates and returns the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="PyPixelBot: A Visual Automation Tool. Use -v or -vv for more verbose console output.",
        formatter_class=argparse.RawTextHelpFormatter # Allows for better help text formatting
    )
    # Global verbosity flag, handled in __main__.py after parsing
    parser.add_argument(
        "-v", "--verbose", 
        action="count", 
        default=0, 
        help="Increase console logging verbosity. -v for INFO, -vv for DEBUG."
    )

    subparsers = parser.add_subparsers(
        dest="command", 
        title="Available Commands",
        help="Run 'command --help' for more information on a specific command.",
        required=True # Ensures a subcommand must be provided
    )

    # --- Run Command ---
    run_parser = subparsers.add_parser(
        "run", 
        help="Run a bot profile for automation.",
        description="Loads and executes the specified bot profile, starting the monitoring and action loop."
    )
    run_parser.add_argument(
        "profile", 
        help="Name or path of the profile to run (e.g., 'example_profile' which looks for 'profiles/example_profile.json', or a direct path like 'profiles/my_bot.json')."
    )
    run_parser.set_defaults(func=handle_run)

    # --- Add-Region Command ---
    add_region_parser = subparsers.add_parser(
        "add-region", 
        help="Add or update a region in a profile using a simple GUI tool.",
        description="Launches a GUI tool to graphically select a screen region. The selected region (name and coordinates) is then saved to the specified profile JSON file. If the profile does not exist, it will be created."
    )
    add_region_parser.add_argument(
        "profile", 
        help="Name or path of the profile to add/update the region in (e.g., 'my_profile' or 'profiles/my_profile.json')."
    )
    add_region_parser.set_defaults(func=handle_add_region)

    # --- Edit Command ---
    edit_parser = subparsers.add_parser(
        "edit", 
        help="Open a profile in the full GUI editor, or start with a new profile.",
        description="Launches the main GUI application for comprehensive profile editing. If a profile path is provided, it attempts to load that profile. Otherwise, it starts with an empty, new profile."
    )
    edit_parser.add_argument(
        "profile", 
        nargs="?", # Makes the profile argument optional
        default=None, # Default if no profile is specified
        help="(Optional) Name or path of the profile to edit (e.g., 'example_profile' or 'profiles/my_profile.json'). If omitted, the editor starts with a new, unsaved profile."
    )
    edit_parser.set_defaults(func=handle_edit)

    logger.debug("CLI ArgumentParser created.")
    return parser

def handle_run(args: argparse.Namespace):
    """Handles the 'run' command: Initializes and starts the MainController."""
    logger.info(f"CLI: 'run' command initiated for profile: '{args.profile}'")
    controller: Optional[MainController] = None
    try:
        controller = MainController(args.profile) # This loads the profile
        controller.start() # Starts the monitoring loop in a new thread
        
        # Keep the main thread alive for the monitoring thread
        # and allow graceful exit with Ctrl+C.
        # The monitoring thread is a daemon, so it would exit if main thread exits,
        # but we want Ctrl+C to be handled by signaling the thread to stop.
        logger.info("Bot monitoring loop started. Press Ctrl+C to stop.")
        while True:
            if controller._monitor_thread and controller._monitor_thread.is_alive(): # type: ignore
                # Periodically check if the thread is alive; join with a timeout
                # This allows the main thread to be responsive to KeyboardInterrupt
                controller._monitor_thread.join(timeout=1.0) # type: ignore
            else:
                logger.info("Monitoring thread is no longer alive. Exiting run command.")
                break 
    except KeyboardInterrupt:
        logger.info("CLI: KeyboardInterrupt (Ctrl+C) received by 'run' handler. Signaling bot to stop...")
        # The main signal handler in __main__.py might also catch this,
        # but having it here ensures the controller's stop method is called.
    except ValueError as ve: 
        logger.error(f"CLI 'run': Error during MainController setup for profile '{args.profile}': {ve}", exc_info=True)
        # No need to sys.exit here, __main__.py will handle exit codes based on exceptions.
        raise # Re-raise for __main__ to catch and set exit code
    except Exception as e:
        logger.error(f"CLI 'run': An unexpected error occurred: {e}", exc_info=True)
        raise
    finally:
        if controller:
            logger.info("CLI 'run': Initiating bot stop sequence...")
            controller.stop() # Ensures stop is called even on error or KeyboardInterrupt
        logger.info(f"CLI: 'run' command for profile '{args.profile}' concluded.")


def handle_add_region(args: argparse.Namespace):
    """Handles the 'add-region' command: Launches the RegionSelectorWindow."""
    logger.info(f"CLI: 'add-region' command initiated for profile: '{args.profile}'")
    try:
        # Dynamic import for GUI components to keep CLI part lighter if GUI not used.
        from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow
        import customtkinter as ctk # Required by RegionSelectorWindow

        logger.debug("Dynamically imported GUI components for 'add-region'.")

        # RegionSelectorWindow needs a master. If no other CTk app is running,
        # we need to create a temporary root.
        # This is a common pattern for utility dialogs.
        temp_root_for_dialog: Optional[ctk.CTk] = None
        if tk._default_root is None and ctk.CTk._get_root_window() is None : # Check if a root Tk or CTk window already exists
            logger.debug("'add-region': No existing CTk root window found, creating temporary root for dialog.")
            temp_root_for_dialog = ctk.CTk()
            temp_root_for_dialog.withdraw() # Hide the dummy root window
        else:
            logger.debug("'add-region': Existing Tk/CTk root window detected or not needed.")


        # ConfigManager will create profile dir/file if `create_if_missing` and it doesn't exist.
        # This ensures RegionSelectorWindow has a valid file to save to.
        config_mngr = ConfigManager(args.profile, create_if_missing=True) 
        logger.info(f"'add-region': ConfigManager initialized for profile '{config_mngr.get_profile_path()}'.")
        
        # If temp_root_for_dialog is used, it becomes the master. Otherwise, Toplevel works without explicit master if a root exists.
        master_for_selector = temp_root_for_dialog if temp_root_for_dialog else ctk.CTk._get_root_window() # Fallback if any CTk window is there
        if master_for_selector is None and temp_root_for_dialog is None : # Absolute fallback for safety
             master_for_selector = ctk.CTk()
             master_for_selector.withdraw()
             logger.warning("'add-region': Had to create an emergency CTk root as no other was found.")


        selector_dialog = RegionSelectorWindow(master=master_for_selector, config_manager=config_mngr)
        logger.debug("'add-region': RegionSelectorWindow instantiated. Waiting for dialog...")
        
        # If we created a temporary root, we need to run its mainloop
        # if master_for_selector is temp_root_for_dialog and temp_root_for_dialog:
        #     temp_root_for_dialog.mainloop() # This blocks until selector_dialog is closed via its own destroy or root destroy
        # else: # If selector is a Toplevel on an existing root, or rootless Toplevel (less common)
        # The RegionSelectorWindow manages its own lifecycle as a Toplevel.
        # We need to ensure the script waits for it if it's modal or handle its closure.
        # For a CTkToplevel, we can use wait_window().
        selector_dialog.wait_window() # This will block until selector_dialog is destroyed.

        logger.debug("'add-region': RegionSelectorWindow closed.")

        if hasattr(selector_dialog, 'saved_region_info') and selector_dialog.saved_region_info:
            logger.info(f"CLI 'add-region': Region '{selector_dialog.saved_region_info['name']}' was saved to profile '{config_mngr.get_profile_path()}'.")
        else:
            logger.info("CLI 'add-region': Region selection cancelled or window closed without saving.")
        
        if temp_root_for_dialog and temp_root_for_dialog.winfo_exists():
            logger.debug("'add-region': Destroying temporary CTk root window.")
            temp_root_for_dialog.destroy()

    except ImportError as ie:
        logger.error(f"CLI 'add-region': GUI components (CustomTkinter/Pillow) not found or import error: {ie}. "
                     "Cannot run 'add-region'. Please ensure GUI dependencies are installed.", exc_info=True)
        raise # Re-raise for __main__
    except Exception as e:
        logger.error(f"CLI 'add-region': An unexpected error occurred: {e}", exc_info=True)
        raise

def handle_edit(args: argparse.Namespace):
    """Handles the 'edit' command by launching the MainAppWindow GUI editor."""
    profile_arg = args.profile if hasattr(args, "profile") else None # Ensure profile arg exists
    logger.info(f"CLI: 'edit' command initiated. Profile to load: '{profile_arg if profile_arg else 'New/Empty Profile'}'")
    try:
        from py_pixel_bot.ui.gui.main_app_window import MainAppWindow # Dynamic import
        # import customtkinter as ctk # MainAppWindow handles its own CTk setup

        logger.debug("Dynamically imported MainAppWindow for 'edit' command.")
        
        # MainAppWindow is a ctk.CTk instance, so it's its own root.
        app_editor = MainAppWindow(initial_profile_path=profile_arg)
        app_editor.mainloop() # Starts the GUI event loop for the editor
        
        logger.info("CLI 'edit': GUI editor main_app_window closed.")

    except ImportError as ie:
        logger.error(f"CLI 'edit': GUI components (CustomTkinter/Pillow) not found or import error: {ie}. "
                     "Cannot run 'edit'. Please ensure GUI dependencies are installed.", exc_info=True)
        raise # Re-raise for __main__
    except Exception as e:
        logger.error(f"CLI 'edit': An unexpected error occurred: {e}", exc_info=True)
        raise

# This allows testing CLI parsing if script is run directly (not via __main__.py)
if __name__ == '__main__':
    # For direct testing, setup minimal logging if not already done by an entry point
    if not logging.getLogger(APP_ROOT_LOGGER_NAME if 'APP_ROOT_LOGGER_NAME' in globals() else "py_pixel_bot").hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info("cli.py standalone: Minimal logging configured for direct script run.")

    parser_test = create_parser()
    
    # Example test invocations (would require actual profiles or mocks for handlers to run fully)
    logger.info("\n--- Testing CLI Parser (examples) ---")
    test_args_run = ["run", "profiles/example_profile.json", "-vv"]
    test_args_add = ["add-region", "my_new_profile"]
    test_args_edit_new = ["edit"]
    test_args_edit_load = ["edit", "profiles/example_profile.json", "-v"]
    
    try:
        logger.info(f"Testing with: {test_args_run}")
        args1 = parser_test.parse_args(test_args_run)
        logger.info(f"Parsed for run: {args1}")
        # args1.func(args1) # Don't call handler in this basic test
    except SystemExit: pass # Argparse exits on --help or error

    try:
        logger.info(f"Testing with: {test_args_add}")
        args2 = parser_test.parse_args(test_args_add)
        logger.info(f"Parsed for add-region: {args2}")
    except SystemExit: pass

    try:
        logger.info(f"Testing with: {test_args_edit_new}")
        args3 = parser_test.parse_args(test_args_edit_new)
        logger.info(f"Parsed for edit (new): {args3}")
    except SystemExit: pass

    try:
        logger.info(f"Testing with: {test_args_edit_load}")
        args4 = parser_test.parse_args(test_args_edit_load)
        logger.info(f"Parsed for edit (load): {args4}")
    except SystemExit: pass

    logger.info("--- CLI Parser test examples finished ---")