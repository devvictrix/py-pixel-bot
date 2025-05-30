import logging
import logging.handlers  # For TimedRotatingFileHandler
import os
import sys
from datetime import date  # For daily log filename if not using TimedRotatingFileHandler's naming

# This name should be used by all modules in the application when getting a logger
# e.g., logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.my_module")
# or, more simply, logger = logging.getLogger(__name__) which will result in names like "mark_i.core.some_module"
APP_ROOT_LOGGER_NAME = "mark_i"

# Store initial sys.stdout and sys.stderr in case they get redirected (e.g., by some GUI libraries)
# and we want to ensure console logs go to the actual original console.
# However, standard StreamHandler(sys.stdout) should generally work.
_original_stdout = sys.stdout
_original_stderr = sys.stderr


def setup_logging(
    console_log_level: int = logging.INFO,
    log_file_path_override: Optional[str] = None,  # Renamed for clarity
    enable_file_logging: bool = True,
    log_file_base_name: str = "mark_i_runtime",  # Base name for log files
    log_file_when: str = "D",  # Rotate daily
    log_file_interval: int = 1,  # Rotate every 1 day
    log_file_backup_count: int = 7,  # Keep 7 backup log files
):
    """
    Configures logging for the Mark-I application.

    Sets up a console handler and a timed rotating file handler.
    The log levels and formats are determined by the `APP_ENV` environment variable.
    CLI arguments can override the console log level and log file path.

    Args:
        console_log_level: The logging level for the console handler.
        log_file_path_override: If provided, this full path is used for the log file,
                                overriding the default naming and location. Rotation might behave
                                differently or might need to be disabled if this is a fixed name.
                                If this path includes a directory, that directory will be used.
        enable_file_logging: If False, file logging will be disabled.
        log_file_base_name: Base name for default log files (e.g., "mark_i_runtime.log.YYYY-MM-DD").
        log_file_when: Type of interval for rotation ('S', 'M', 'H', 'D', 'W0'-'W6', 'midnight').
        log_file_interval: Interval for rotation (e.g., 1 for daily if when='D').
        log_file_backup_count: Number of backup log files to keep.
    """
    app_env = os.getenv("APP_ENV", "production").lower()  # Default to production for safety
    logger_instance = logging.getLogger(APP_ROOT_LOGGER_NAME)  # Get the application's root logger

    # Set the *logger's* level to the lowest possible (DEBUG).
    # Handlers will then filter messages based on their own configured levels.
    # This ensures that if a handler is set to DEBUG, it can actually receive DEBUG messages.
    logger_instance.setLevel(logging.DEBUG)

    # Clear any existing handlers from previous setups (e.g., if called multiple times)
    # This is important to avoid duplicate log messages.
    if logger_instance.hasHandlers():
        logger_instance.handlers.clear()
        # Also prevent propagation to the absolute root logger if we are configuring "mark_i"
        # and don't want its messages to also go to a default basicConfig handler.
        logger_instance.propagate = False

    # Determine formats based on environment
    console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s (Env: " + app_env.upper() + ")"  # Add ENV to file logs

    if app_env == "development":
        # More verbose console logging for development
        console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
        file_log_level = logging.DEBUG  # File logs are DEBUG in dev
    else:  # uat, production, or any other
        file_log_level = logging.INFO  # File logs are INFO otherwise

    # --- Console Handler ---
    console_formatter = logging.Formatter(console_formatter_str)
    console_handler = logging.StreamHandler(sys.stdout)  # Use original stdout if concerned about redirection
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(console_log_level)  # Set by arg, defaults to INFO
    logger_instance.addHandler(console_handler)

    # --- File Handler (Timed Rotating) ---
    if enable_file_logging:
        try:
            # Determine project root for default logs directory
            # Assumes: project_root/mark_i/core/logging_setup.py
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            package_dir = os.path.dirname(current_file_dir)
            project_root = os.path.dirname(package_dir)
            default_logs_dir = os.path.join(project_root, "logs")

            final_log_file_path: Optional[str] = None
            use_standard_rotation = True

            if log_file_path_override:
                # User specified an exact file path.
                # Rotation might be implicitly disabled or behave based on handler if it's a fixed name.
                # For TimedRotatingFileHandler, if the path is absolute and doesn't vary,
                # it will append date/time to it for rotated files.
                final_log_file_path = os.path.abspath(log_file_path_override)
                log_file_dir_to_create = os.path.dirname(final_log_file_path)
                logger.info(f"Custom log file path specified: {final_log_file_path}")
            else:
                # Default behavior: logs/mark_i_runtime.log (which will then be rotated)
                final_log_file_path = os.path.join(default_logs_dir, f"{log_file_base_name}.log")
                log_file_dir_to_create = default_logs_dir
                logger.info(f"Using default rotating log file strategy in directory: {default_logs_dir}")

            # Create the directory for the log file if it doesn't exist
            if not os.path.exists(log_file_dir_to_create):
                os.makedirs(log_file_dir_to_create)
                logger.info(f"Created logs directory: {log_file_dir_to_create}")

            file_formatter = logging.Formatter(file_formatter_str)

            # Use TimedRotatingFileHandler
            # filename will be the base name; it appends date/time automatically.
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=final_log_file_path,  # This is the path to the *current* log file
                when=log_file_when,
                interval=log_file_interval,
                backupCount=log_file_backup_count,
                encoding="utf-8",
                delay=False,  # True delays file creation until first log write
                utc=False,  # Use local time for timestamps in filenames
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(file_log_level)  # From APP_ENV logic
            logger_instance.addHandler(file_handler)
            logger_instance.info(
                f"File logging enabled. Level: {logging.getLevelName(file_log_level)}. Log file base: {final_log_file_path}. Rotation: when='{log_file_when}', interval={log_file_interval}, backups={log_file_backup_count}."
            )

        except Exception as e:
            # If file logging setup fails, log to console and continue without file logging.
            logger_instance.error(f"Failed to set up file logging: {e}", exc_info=True)
            # Use basic print to stderr if console handler itself might have issues (though unlikely here)
            print(f"ERROR: Could not set up file logging for path '{log_file_path_override if log_file_path_override else default_logs_dir}': {e}", file=sys.stderr)
    else:
        logger_instance.info("File logging is disabled by configuration.")

    logger_instance.info(
        f"Logging setup complete for '{APP_ROOT_LOGGER_NAME}'. APP_ENV: '{app_env}'. "
        f"Effective Console Level: {logging.getLevelName(console_handler.level)}. "
        f"Effective File Level: {logging.getLevelName(file_log_level) if enable_file_logging and 'file_handler' in locals() else 'N/A (Disabled)'}."
    )


if __name__ == "__main__":
    # Example Usage & Test
    print("--- Testing logging_setup.py ---")

    # Test Case 1: Development environment
    os.environ["APP_ENV"] = "development"
    print("\n[Test Case 1: APP_ENV=development, default console level (INFO)]")
    setup_logging()  # Uses default console_log_level=INFO
    dev_logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.dev_test")
    dev_logger.debug("This is a DEV debug message (should appear in file, maybe not console).")
    dev_logger.info("This is a DEV info message (should appear in console and file).")
    dev_logger.warning("This is a DEV warning message.")

    # Test Case 2: Production environment, verbose console
    os.environ["APP_ENV"] = "production"
    print("\n[Test Case 2: APP_ENV=production, console level DEBUG]")
    setup_logging(console_log_level=logging.DEBUG)
    prod_logger_verbose_console = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.prod_test_verbose_console")
    prod_logger_verbose_console.debug("This is a PROD debug message (should appear in console due to override, and file if dev mode was still active - it's not).")  # File level is INFO for prod
    prod_logger_verbose_console.info("This is a PROD info message.")

    # Test Case 3: Custom log file path
    os.environ["APP_ENV"] = "development"  # Back to dev for DEBUG file logs
    custom_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs", "custom_test_log.log")  # Place in project logs dir
    print(f"\n[Test Case 3: Custom log file path: {custom_log_path}]")
    setup_logging(log_file_path_override=custom_log_path, console_log_level=logging.DEBUG)
    custom_logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.custom_path_test")
    custom_logger.debug(f"This message should go to '{custom_log_path}' and console (dev + debug console).")
    if os.path.exists(custom_log_path):
        print(f"SUCCESS: Custom log file created at {custom_log_path}")
        # Note: TimedRotatingFileHandler might append date/time to this if not handled as a fixed name.
        # The current implementation of TRFH takes the `filename` as the base for the *current* log.
    else:
        print(f"FAILURE: Custom log file NOT created at {custom_log_path}")

    # Test Case 4: Disabling file logging
    print("\n[Test Case 4: File logging disabled]")
    setup_logging(enable_file_logging=False, console_log_level=logging.INFO)
    no_file_logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.no_file_test")
    no_file_logger.info("This message should only appear on the console.")
    no_file_logger.error("This error message should also only appear on the console.")

    print("\n--- Logging setup tests completed. Check console output and log files in 'logs/' directory. ---")
    print(f"--- Default logs should be in a 'logs' subdirectory of the project root. ---")
    print(f"--- Example: project_root/logs/{date.today().strftime('%Y-%m-%d')}.log or similar based on rotation. ---")
