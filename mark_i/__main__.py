import sys
import logging

# --- Attempt to set up core components first ---
try:
    from .core.config_manager import load_environment_variables
    from .core.logging_setup import setup_logging
    from .ui import cli  # Imports mark_i.ui.cli
except ImportError as e:
    sys.stderr.write(
        f"Fatal Error: Failed to import core modules. Please check installation and file structure.\n"
    )
    sys.stderr.write(f"Details: {e}\n")
    sys.exit(1)
except Exception as e:
    sys.stderr.write(
        f"Fatal Error: An unexpected error occurred during initial imports.\n"
    )
    sys.stderr.write(f"Details: {e}\n")
    sys.exit(1)

logger = logging.getLogger(__name__)


def main():
    try:
        load_environment_variables()
    except Exception as e:
        sys.stderr.write(f"Error loading environment variables: {e}\n")

    # --- Debugging the cli import ---
    print(f"DEBUG __main__: Imported cli module object: {cli}")
    print(f"DEBUG __main__: Type of cli object: {type(cli)}")
    print(f"DEBUG __main__: Attributes available in cli module (dir(cli)): {dir(cli)}")
    # --- End Debugging ---

    try:
        parser = cli.create_parser()  # The problematic line
    except AttributeError:
        sys.stderr.write(
            f"Failed to create CLI parser: module 'mark_i.ui.cli' ({cli}) does not appear to have 'create_parser'.\n"
        )
        sys.stderr.write(
            f"Check the debug prints above from cli.py to see if it loaded correctly and defined create_parser.\n"
        )
        sys.exit(1)
    except Exception as e:
        sys.stderr.write(
            f"An unexpected error occurred while trying to call cli.create_parser(): {e}\n"
        )
        sys.exit(1)

    try:
        args = parser.parse_args()
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(f"Error parsing command-line arguments: {e}\n")
        sys.exit(1)

    console_log_level_override = logging.INFO
    if hasattr(args, "verbose") and args.verbose:
        console_log_level_override = args.verbose

    enable_file_logging = True
    if hasattr(args, "no_file_logging") and args.no_file_logging:
        enable_file_logging = False

    log_file_path_override = None
    if hasattr(args, "log_file") and args.log_file:
        log_file_path_override = args.log_file

    try:
        setup_logging(
            console_log_level=console_log_level_override,
            log_file_path=log_file_path_override,
            enable_file_logging=enable_file_logging,
        )
        logger.info("Logging re-initialized with command-line argument settings.")
    except Exception as e:
        sys.stderr.write(
            f"Critical Error: Failed to setup logging: {e}. Application cannot continue reliably.\n"
        )
        sys.exit(1)

    if hasattr(args, "func"):
        try:
            logger.info(f"Executing command: {args.command}")
            args.func(args)
            logger.info(f"Command '{args.command}' finished.")
        except SystemExit:
            logger.warning(f"Command '{args.command}' initiated a system exit.")
            raise
        except KeyboardInterrupt:
            logger.info(
                f"Keyboard interrupt received during command '{args.command}'. Exiting."
            )
            sys.exit(0)
        except Exception as e:
            logger.critical(
                f"An unhandled error occurred during execution of command '{args.command}': {e}",
                exc_info=True,
            )
            print(
                f"Error: An unexpected problem occurred. Check the logs for details: {e}",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        logger.error(
            "No command function found. This indicates an issue with CLI parser setup."
        )
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as e:
        logging.basicConfig(
            level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.critical(
            f"A critical unhandled exception occurred at the top level: {e}",
            exc_info=True,
        )
        print(f"A critical error occurred: {e}. Please check logs.", file=sys.stderr)
        sys.exit(1)
