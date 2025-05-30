import sys
import logging

# --- Attempt to set up core components first ---
try:
    # Ensure relative imports work correctly when run as a module
    # If run as `python -m mark_i`, then `.core` etc. should work.
    from .core.config_manager import load_environment_variables
    from .core.logging_setup import setup_logging, APP_ROOT_LOGGER_NAME
    from .ui import cli
except ImportError as e:
    # This fallback might help if running script directly for quick tests,
    # but generally, the package structure should be respected.
    try:
        from core.config_manager import load_environment_variables
        from core.logging_setup import setup_logging, APP_ROOT_LOGGER_NAME
        from ui import cli

        sys.stderr.write("Warning: Imported core modules using direct relative paths. " "Consider running as a module: `python -m mark_i` for robust imports.\n")
    except ImportError:  # Final fallback if direct relative also fails
        sys.stderr.write(f"Fatal Error: Failed to import core modules. Please check installation, file structure, and PYTHONPATH.\n")
        sys.stderr.write(f"Details: {e}\n")
        sys.exit(1)  # Exit if core components cannot be imported
except Exception as e:  # Catch any other unexpected error during these critical initial imports
    sys.stderr.write(f"Fatal Error: An unexpected error occurred during initial imports.\n")
    sys.stderr.write(f"Details: {e}\n")
    sys.exit(1)

# Get the application's root logger.
# Modules should typically use logging.getLogger(__name__) for hierarchical logging.
# This top-level logger is for messages from __main__ itself.
logger = logging.getLogger(APP_ROOT_LOGGER_NAME)


def main():
    """
    Main function to initialize and run the Mark-I application.
    It loads environment variables, sets up logging (initially then reconfigures
    based on CLI args), parses CLI arguments, and dispatches to the
    appropriate command handler function defined in `mark_i.ui.cli`.
    """
    try:
        load_environment_variables()
        # Initial logging setup with defaults. This allows `load_environment_variables`
        # and early messages to be logged. It will be reconfigured after CLI args are parsed.
        setup_logging()
        logger.info("Mark-I application starting...")
    except Exception as e:
        # Use basic print if logging setup itself fails catastrophically,
        # as the logger might not be functional.
        sys.stderr.write(f"CRITICAL ERROR during pre-setup (env vars or initial logging): {e}\n")
        # Attempt a fallback basic config for logging this specific critical error
        logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s")
        logging.critical(f"CRITICAL ERROR during pre-setup: {e}", exc_info=True)
        sys.exit(1)  # Cannot proceed without basic setup

    try:
        parser = cli.create_parser()  # Create the argparse parser from the cli module
    except AttributeError as e:
        logger.critical("Failed to create CLI parser: `create_parser` function not found in `mark_i.ui.cli` module. This is a critical setup error.", exc_info=True)
        sys.exit(1)
    except Exception as e:  # Catch any other error during parser creation
        logger.critical(f"An unexpected error occurred while trying to create the CLI parser: {e}", exc_info=True)
        sys.exit(1)

    try:
        args = parser.parse_args()  # Parse command-line arguments
    except SystemExit as e:
        # argparse raises SystemExit for -h, --help, or argument errors.
        # Log this event and exit with the provided code.
        logger.info(f"Argument parsing resulted in SystemExit (e.g., help invoked or arg error). Exit code: {e.code}")
        sys.exit(e.code)
    except Exception as e:  # Catch other unexpected parsing errors
        logger.error(f"Error parsing command-line arguments: {e}", exc_info=True)
        parser.print_help()  # Show help to the user
        sys.exit(1)

    # Reconfigure logging based on parsed CLI arguments
    console_log_level_from_args = logging.INFO  # Default
    if hasattr(args, "verbose") and args.verbose is not None:  # verbose sets to logging.DEBUG
        console_log_level_from_args = args.verbose

    file_logging_enabled_from_args = True
    if hasattr(args, "no_file_logging") and args.no_file_logging:
        file_logging_enabled_from_args = False

    log_file_override_from_args = None
    if hasattr(args, "log_file") and args.log_file:
        log_file_override_from_args = args.log_file

    try:
        # Re-initialize logging with settings derived from CLI arguments
        setup_logging(
            console_log_level=console_log_level_from_args,
            log_file_path_override=log_file_override_from_args,
            enable_file_logging=file_logging_enabled_from_args,
        )
        logger.info("Logging re-initialized with command-line argument settings.")
    except Exception as e:
        # If re-setup of logging fails, this is critical. Initial logs might exist.
        logger.critical(f"CRITICAL ERROR: Failed to re-setup logging with CLI arguments: {e}. Application cannot continue reliably.", exc_info=True)
        sys.exit(1)

    # Dispatch to the command handler function set by argparse subcommands
    if hasattr(args, "func") and callable(args.func):
        try:
            logger.info(f"Executing command: '{args.command}' with arguments: {vars(args)}")
            args.func(args)  # Call the handler (e.g., handle_run, handle_edit)
            logger.info(f"Command '{args.command}' finished successfully.")
        except SystemExit as e:  # Allow command handlers to signal exit
            logger.warning(f"Command '{args.command}' initiated a system exit with code {e.code}.")
            raise  # Re-raise to exit with the specific code
        except KeyboardInterrupt:
            logger.info(f"Keyboard interrupt (Ctrl+C) received during execution of command '{args.command}'. Exiting gracefully.")
            # Perform any global cleanup here if necessary, though individual commands should handle their own.
            sys.exit(130)  # Standard exit code for Ctrl+C
        except Exception as e:  # Catch-all for unhandled exceptions in command handlers
            logger.critical(
                f"An unhandled error occurred during execution of command '{args.command}': {e}",
                exc_info=True,
            )
            # Provide user-friendly error message to stderr
            print(f"\nERROR: An unexpected problem occurred while running command '{args.command}'.", file=sys.stderr)
            print(f"Details: {e}", file=sys.stderr)
            print("Please check the log files for more detailed technical information.", file=sys.stderr)
            sys.exit(1)
    else:
        # This case should ideally not be reached if subparsers are 'required=True' in argparse setup.
        logger.error("No command function associated with parsed arguments. This indicates an issue with CLI parser subcommand setup.")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    # Top-level try-except for the entire application run.
    # This is the final safety net.
    try:
        main()
    except SystemExit as e:
        # SystemExit is often a "clean" exit (e.g., help, or intentional exit from a command).
        # Log non-zero exits as warnings or errors if the logger is available.
        exit_code = e.code if e.code is not None else 0
        if exit_code != 0:
            if logger and logger.handlers:  # Check if logger was successfully initialized
                logger.warning(f"Application exited with code {exit_code}.")
            else:  # Logger not set up, print to stderr
                print(f"Application exited with code {exit_code}.", file=sys.stderr)
        else:
            if logger and logger.handlers:
                logger.info("Application exited successfully (code 0).")
            # else: print("Application exited successfully (code 0).") # Optional print for success
    except Exception as e:
        # If an unhandled exception reaches here, it means something went wrong
        # very early or outside the main command execution flow's try-except.
        # Attempt to log it using a very basic logger configuration as a last resort.
        logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - ROOT - %(levelname)s - %(message)s")
        logging.critical(
            f"A critical unhandled exception occurred at the top level of Mark-I execution: {e}",
            exc_info=True,
        )
        print(f"CRITICAL UNHANDLED ERROR: {e}. Mark-I cannot continue.", file=sys.stderr)
        print("If logs were created, please check them for more details.", file=sys.stderr)
        sys.exit(1)  # Exit with a generic error code
