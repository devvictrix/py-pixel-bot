import sys
import os
import logging # Used early for initial messages before full setup

# --- Path Setup ---
# This block ensures that the 'src' directory (containing the 'py_pixel_bot' package)
# is on sys.path, allowing Python to find the modules when the application is run
# using `python -m py_pixel_bot` from the project root, or when `__main__.py` is
# executed directly (e.g., `python src/py_pixel_bot/__main__.py`).

# When run as `python -m py_pixel_bot`:
#   - __package__ will be "py_pixel_bot".
#   - The current working directory (project root) is typically on sys.path.
# When run as `python src/py_pixel_bot/__main__.py`:
#   - __package__ will be "py_pixel_bot" (due to relative imports within package).
#   - The directory of __main__.py (`src/py_pixel_bot`) is on sys.path.
#     We need its parent (`src`) or grandparent (project root) for `from py_pixel_bot...` imports
#     if other modules try to import from the top `py_pixel_bot` package level.
#     However, internal imports within the package (e.g., `from .core import ...`) work fine.
# For robustness, especially if this script might be invoked in unusual ways,
# explicitly adding the 'src' directory (parent of 'py_pixel_bot' package directory)
# to sys.path if it's not already there is a good measure.

# Path to the 'src' directory
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # py-pixel-bot/src/
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
    # Initial log before full logging setup, primarily for path debugging if needed.
    # This will go to stderr by default if no handlers are configured yet.
    logging.info(f"__main__.py: Added '{SRC_DIR}' to sys.path for module resolution.")


# Now, perform the actual imports after path setup
from py_pixel_bot.core import config_manager as cm
from py_pixel_bot.core import logging_setup
from py_pixel_bot.ui import cli # Imports create_parser and handler functions

# This logger will be configured by logging_setup.setup_logging() later
module_logger = logging.getLogger(__name__) # Use __name__ for module-level logger


def main():
    """
    Main entry point for the PyPixelBot application.
    Orchestrates initialization, CLI argument parsing, and command dispatching.
    """
    # 1. Load environment variables (especially APP_ENV) from .env file.
    # This must happen BEFORE logging setup if APP_ENV influences log config.
    try:
        cm.load_environment_variables() 
    except Exception as e_env:
        # Critical failure if .env loading itself fails badly, though python-dotenv is usually robust.
        # Log directly to stderr as full logging might not be up.
        sys.stderr.write(f"CRITICAL: Failed to execute load_environment_variables(): {e_env}\n")
        # Depending on how critical .env is, might exit. For APP_ENV, logging_setup has defaults.
        # For now, we proceed, as logging_setup will use defaults if APP_ENV is missing.

    # 2. Setup application-wide logging.
    # This reads APP_ENV (set by load_environment_variables or OS) to configure handlers and levels.
    try:
        logging_setup.setup_logging() 
    except Exception as e_log:
        sys.stderr.write(f"CRITICAL: Failed to setup logging: {e_log}\n")
        # If logging setup fails, further execution is risky/undiagnosable.
        sys.exit(2) # Use a distinct exit code for logging failure

    # Now that logging is configured, we can use the module_logger.
    module_logger.info("PyPixelBot application starting up...")
    module_logger.debug(f"Python version: {sys.version}")
    module_logger.debug(f"sys.path: {sys.path}")
    module_logger.debug(f"Current working directory: {os.getcwd()}")
    module_logger.debug(f"APP_ENV (after load & setup): '{os.getenv('APP_ENV', 'Not Set - Error?')}'")


    # 3. Create the CLI argument parser.
    try:
        parser = cli.create_parser()
    except Exception as e_parser:
        module_logger.critical(f"Failed to create CLI parser: {e_parser}", exc_info=True)
        sys.exit(3)

    # 4. Parse CLI arguments from sys.argv.
    try:
        args = parser.parse_args() # Exits on --help or error automatically
        module_logger.debug(f"Parsed CLI arguments: {args}")
    except SystemExit as e_argparse: # Handles -h or argparse errors
        # Argparse already prints help/error, so just exit with its code.
        # module_logger.info(f"Argparse exited with code {e_argparse.code}.") # Optional log
        sys.exit(e_argparse.code)
    except Exception as e_argparse_unexpected:
        module_logger.critical(f"Unexpected error during CLI argument parsing: {e_argparse_unexpected}", exc_info=True)
        sys.exit(4)


    # 5. Adjust console logging level based on CLI verbosity flags.
    # This must happen AFTER initial logging setup AND after parsing args.
    try:
        if hasattr(args, "verbose"): # Check if 'verbose' attr exists (it should if parser is set up)
            if args.verbose == 1:
                logging_setup.set_console_log_level(logging.INFO)
                # module_logger.info("Console logging level overridden to INFO by -v flag.") # Already logged by set_console_log_level
            elif args.verbose >= 2:
                logging_setup.set_console_log_level(logging.DEBUG)
                # module_logger.info("Console logging level overridden to DEBUG by -vv flag.")
    except Exception as e_verbose:
        module_logger.error(f"Error setting console verbosity: {e_verbose}", exc_info=True)


    # 6. Execute the dispatched command function.
    # Each subcommand in cli.py should have set_defaults(func=handler_function).
    if hasattr(args, "func") and callable(args.func):
        module_logger.info(f"Dispatching to command handler for: '{args.command}'")
        try:
            args.func(args) # Call the appropriate handler function (e.g., handle_run, handle_edit)
            exit_code = 0 # Assume success if handler doesn't exit
            module_logger.info(f"Command '{args.command}' completed successfully.")
        except SystemExit as se: # If a handler calls sys.exit()
            exit_code = se.code if se.code is not None else 1 # Default to 1 if no code in SystemExit
            if exit_code == 0:
                module_logger.info(f"Command '{args.command}' handler exited with code 0 (success).")
            else:
                module_logger.error(f"Command '{args.command}' handler exited with code {exit_code}.")
        except KeyboardInterrupt: # Handle Ctrl+C if not caught by the command handler (e.g., during GUI setup)
            module_logger.info(f"KeyboardInterrupt received during command '{args.command}'. Application terminating.")
            exit_code = 130 # Standard exit code for Ctrl+C
        except Exception as e_cmd: 
            module_logger.critical(f"A critical unhandled error occurred in command '{args.command}': {e_cmd}", exc_info=True)
            exit_code = 1 # General error
    else:
        # This case should ideally not be reached if subparsers are 'required=True'
        # and all subparsers have a default function set.
        module_logger.error("No command function was dispatched. This indicates a CLI setup issue.")
        parser.print_help() # Show help to the user
        exit_code = 1

    module_logger.info(f"PyPixelBot application shutting down with exit code {exit_code}.")
    sys.exit(exit_code) # Explicitly exit with the determined code


if __name__ == "__main__":
    # This makes the script executable.
    # When run as `python -m py_pixel_bot`, Python executes this `if __name__ == "__main__":` block.
    # When run as `python src/py_pixel_bot/__main__.py`, it also executes this.
    main()