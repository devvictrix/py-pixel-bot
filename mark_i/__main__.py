import sys
import logging

# --- Attempt to set up core components first ---
try:
    # Ensure relative imports work correctly when run as a module
    # If run as `python -m mark_i`, then `.core` etc. should work.
    # If run as `python mark_i/__main__.py` directly from project root,
    # and `py-pixel-bot` is in PYTHONPATH or is the CWD, then `mark_i.core` might be needed.
    # The `python -m mark_i` invocation style is generally preferred for packages.
    from .core.config_manager import load_environment_variables
    from .core.logging_setup import setup_logging, APP_ROOT_LOGGER_NAME  # Import APP_ROOT_LOGGER_NAME
    from .ui import cli
except ImportError as e:
    # This fallback might help if running script directly for quick tests,
    # but generally, the package structure should be respected.
    try:
        from core.config_manager import load_environment_variables
        from core.logging_setup import setup_logging, APP_ROOT_LOGGER_NAME
        from ui import cli

        sys.stderr.write("Warning: Imported core modules using direct relative paths. " "Consider running as a module: `python -m mark_i` for robust imports.\n")
    except ImportError:
        sys.stderr.write(f"Fatal Error: Failed to import core modules. Please check installation, file structure, and PYTHONPATH.\n")
        sys.stderr.write(f"Details: {e}\n")
        sys.exit(1)
except Exception as e:
    sys.stderr.write(f"Fatal Error: An unexpected error occurred during initial imports.\n")
    sys.stderr.write(f"Details: {e}\n")
    sys.exit(1)

# Get the root logger for the application after setup_logging potentially creates it.
# This ensures that if logging_setup customizes the "mark_i" logger, we use that.
# However, APP_ROOT_LOGGER_NAME should be "mark_i" and getLogger(__name__)
# when __name__ is "__main__" will be the "__main__" logger, not "mark_i" root.
# For application-wide logging, modules should use logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.module_name")
# or just logging.getLogger(__name__) and rely on propagation if root logger is configured.
# Here, for the main entry point, using a general logger.
logger = logging.getLogger(APP_ROOT_LOGGER_NAME)  # Use the app's root logger defined in logging_setup


def main():
    """
    Main function to initialize and run the Mark-I application.
    It loads environment variables, sets up logging, parses CLI arguments,
    and dispatches to the appropriate command handler.
    """
    try:
        load_environment_variables()
        # Initial basic logging setup until args are parsed
        # This ensures `load_environment_variables` can log.
        # It will be reconfigured after args parsing.
        setup_logging()  # Initial call with defaults
        logger.info("Mark-I application starting...")
    except Exception as e:
        # Use basic print if logging setup itself fails catastrophically
        sys.stderr.write(f"Critical Error during pre-setup (env vars or initial logging): {e}\n")
        # Fallback basic config for logging critical error if setup_logging failed
        logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
        logging.critical(f"Critical Error during pre-setup: {e}", exc_info=True)
        sys.exit(1)

    try:
        parser = cli.create_parser()
    except AttributeError as e:
        logger.critical(f"Failed to create CLI parser: module 'mark_i.ui.cli' does not appear to have 'create_parser'. This is a critical setup error.", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.critical(f"An unexpected error occurred while trying to call cli.create_parser(): {e}", exc_info=True)
        sys.exit(1)

    try:
        args = parser.parse_args()
    except SystemExit as e:  # Handles -h or --help automatically
        logger.info(f"Argument parsing resulted in SystemExit (e.g. help invoked). Code: {e.code}")
        sys.exit(e.code)  # Propagate the exit code
    except Exception as e:
        logger.error(f"Error parsing command-line arguments: {e}", exc_info=True)
        parser.print_help()  # Show help on argument error
        sys.exit(1)

    # Reconfigure logging based on CLI arguments
    console_log_level_override = logging.INFO  # Default if not verbose
    if hasattr(args, "verbose") and args.verbose:  # args.verbose will be logging.DEBUG if -v is set
        console_log_level_override = args.verbose

    enable_file_logging_arg = True
    if hasattr(args, "no_file_logging") and args.no_file_logging:
        enable_file_logging_arg = False

    log_file_path_override_arg = None
    if hasattr(args, "log_file") and args.log_file:
        log_file_path_override_arg = args.log_file

    try:
        setup_logging(  # Re-initialize with parsed args
            console_log_level=console_log_level_override,
            log_file_path=log_file_path_override_arg,
            enable_file_logging=enable_file_logging_arg,
        )
        logger.info("Logging re-initialized with command-line argument settings.")
    except Exception as e:
        # If re-setup fails, critical, but initial logs might exist.
        logger.critical(f"Critical Error: Failed to re-setup logging with CLI args: {e}. Application cannot continue reliably.", exc_info=True)
        sys.exit(1)

    if hasattr(args, "func") and callable(args.func):
        try:
            logger.info(f"Executing command: '{args.command}' with arguments: {vars(args)}")
            args.func(args)  # Call the appropriate handler function (handle_run, handle_edit, etc.)
            logger.info(f"Command '{args.command}' finished successfully.")
        except SystemExit as e:  # Allow command handlers to exit
            logger.warning(f"Command '{args.command}' initiated a system exit with code {e.code}.")
            raise  # Re-raise to exit with the specific code
        except KeyboardInterrupt:
            logger.info(f"Keyboard interrupt (Ctrl+C) received during command '{args.command}'. Exiting gracefully.")
            # Perform any necessary cleanup here if command handlers don't do it
            sys.exit(130)  # Standard exit code for Ctrl+C
        except Exception as e:
            logger.critical(
                f"An unhandled error occurred during execution of command '{args.command}': {e}",
                exc_info=True,
            )
            # Optionally, provide a simpler message to stdout/stderr for the user
            print(f"\nError: An unexpected problem occurred while running '{args.command}'.", file=sys.stderr)
            print(f"Details: {e}", file=sys.stderr)
            print("Please check the log files for more detailed information.", file=sys.stderr)
            sys.exit(1)
    else:
        logger.error("No command function found or function not callable. This indicates an issue with CLI parser setup.")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    # This top-level try-except is a final safeguard.
    try:
        main()
    except SystemExit as e:
        # logger might not be fully configured if SystemExit happens very early.
        # Use print for truly critical early exits if needed.
        if e.code != 0:  # Log non-zero exits as warnings/errors if logger is available
            if logger and logger.handlers:  # Check if logger has handlers
                logger.warning(f"Application exited with code {e.code}.")
            else:
                print(f"Application exited with code {e.code}.", file=sys.stderr)
        else:
            if logger and logger.handlers:
                logger.info("Application exited successfully.")
    except Exception as e:
        # If main() itself throws an unhandled exception before logging is robustly set up.
        # Fallback to basicConfig for this critical error.
        logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
        logging.critical(
            f"A critical unhandled exception occurred at the top level of __main__: {e}",
            exc_info=True,
        )
        print(f"A critical error occurred: {e}. Please check logs if any were created.", file=sys.stderr)
        sys.exit(1)
