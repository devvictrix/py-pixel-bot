import logging
import logging.handlers
import os
import sys
from datetime import date  # For default log filename if TimedRotatingFileHandler isn't used (not current)
from typing import Optional  # Added this line

# This name should be used by all modules in the application when getting a logger
# e.g., logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.my_module")
# or, more simply, logger = logging.getLogger(__name__) which will result in names like "mark_i.core.some_module"
APP_ROOT_LOGGER_NAME = "mark_i"


class MaxLevelFilter(logging.Filter):
    """Filters log records to allow only those below or equal to a max level."""

    def __init__(self, max_level):
        super().__init__()
        self.max_level = max_level

    def filter(self, record):
        return record.levelno <= self.max_level


def setup_logging(
    console_log_level: int = logging.INFO,
    log_file_path_override: Optional[str] = None,
    enable_file_logging: bool = True,
    log_file_base_name: str = "mark_i_runtime",  # Base name for default log files
    log_file_when: str = "midnight",  # Rotate at midnight
    log_file_interval: int = 1,  # Rotate every 1 day (when='midnight' makes interval less relevant for D)
    log_file_backup_count: int = 7,  # Keep 7 backup log files
):
    """
    Configures logging for the Mark-I application.

    Sets up console handlers (one for INFO and above to stdout, one for WARNING and above to stderr)
    and a timed rotating file handler. Log levels and formats are determined by the `APP_ENV`
    environment variable. CLI arguments can override the console log level and log file path.

    Args:
        console_log_level: The *minimum* logging level for the primary console (stdout) handler.
        log_file_path_override: If provided, this full path is used for the log file.
        enable_file_logging: If False, file logging will be disabled.
        log_file_base_name: Base name for default log files (e.g., "mark_i_runtime.log").
        log_file_when: Type of interval for rotation for TimedRotatingFileHandler.
        log_file_interval: Interval for rotation.
        log_file_backup_count: Number of backup log files to keep.
    """
    app_env = os.getenv("APP_ENV", "production").lower()  # Default to production for safety
    logger_instance = logging.getLogger(APP_ROOT_LOGGER_NAME)

    logger_instance.setLevel(logging.DEBUG)  # Logger itself set to lowest, handlers filter

    if logger_instance.hasHandlers():
        logger_instance.handlers.clear()
    logger_instance.propagate = False  # Prevent messages going to default root logger handlers

    # Determine formats based on environment
    # Console format for INFO and DEBUG (stdout)
    stdout_console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # Console format for WARNING and above (stderr) - more detail potentially
    stderr_console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
    # File format - always detailed
    file_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s (Env: " + app_env.upper() + ")"

    file_log_level_setting = logging.INFO  # Default file log level
    if app_env == "development":
        # More verbose console logging for development on stdout if console_log_level is DEBUG
        if console_log_level <= logging.DEBUG:
            stdout_console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
        file_log_level_setting = logging.DEBUG

    # --- Console Handlers ---
    # 1. Handler for stdout (DEBUG if console_log_level is DEBUG, else INFO and below)
    stdout_formatter = logging.Formatter(stdout_console_formatter_str)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(stdout_formatter)
    stdout_handler.setLevel(console_log_level)  # Minimum level for this handler
    # Filter to only show messages up to INFO if console_log_level is INFO or higher.
    # If console_log_level is DEBUG, this filter allows DEBUG and INFO.
    stdout_handler.addFilter(MaxLevelFilter(logging.INFO if console_log_level > logging.DEBUG else logging.DEBUG))
    logger_instance.addHandler(stdout_handler)

    # 2. Handler for stderr (WARNING and above, always)
    stderr_formatter = logging.Formatter(stderr_console_formatter_str)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(stderr_formatter)
    stderr_handler.setLevel(logging.WARNING)  # Only WARNING, ERROR, CRITICAL
    logger_instance.addHandler(stderr_handler)

    # --- File Handler (Timed Rotating) ---
    if enable_file_logging:
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            package_dir = os.path.dirname(current_file_dir)
            project_root = os.path.dirname(package_dir)
            default_logs_dir = os.path.join(project_root, "logs")

            final_log_file_for_handler: str
            if log_file_path_override:
                final_log_file_for_handler = os.path.abspath(log_file_path_override)
                log_file_dir_to_ensure = os.path.dirname(final_log_file_for_handler)
                # Use logger_instance here as it should be configured for basic console output by now
                logger_instance.info(f"Custom log file path specified: {final_log_file_for_handler}")
            else:
                final_log_file_for_handler = os.path.join(default_logs_dir, f"{log_file_base_name}.log")
                log_file_dir_to_ensure = default_logs_dir
                logger_instance.info(f"Using default rotating log file strategy in directory: {default_logs_dir}")

            if not os.path.exists(log_file_dir_to_ensure):
                os.makedirs(log_file_dir_to_ensure)
                logger_instance.info(f"Created logs directory: {log_file_dir_to_ensure}")

            file_formatter_obj = logging.Formatter(file_formatter_str)

            file_handler_timed = logging.handlers.TimedRotatingFileHandler(
                filename=final_log_file_for_handler,
                when=log_file_when,
                interval=log_file_interval,
                backupCount=log_file_backup_count,
                encoding="utf-8",
                delay=False,  # Create log file immediately
                utc=False,  # Use local time for rotation calculations
            )
            file_handler_timed.setFormatter(file_formatter_obj)
            file_handler_timed.setLevel(file_log_level_setting)
            logger_instance.addHandler(file_handler_timed)
            logger_instance.info(
                f"File logging enabled. Level: {logging.getLevelName(file_log_level_setting)}. Log file base: {final_log_file_for_handler}. Rotation: when='{log_file_when}', interval={log_file_interval}, backups={log_file_backup_count}."
            )

        except Exception as e:
            logger_instance.error(f"Failed to set up file logging: {e}", exc_info=True)
            print(f"ERROR: Could not set up file logging for path '{log_file_path_override or default_logs_dir if 'default_logs_dir' in locals() else 'unknown'}': {e}", file=sys.stderr)
    else:
        logger_instance.info("File logging is disabled by configuration.")

    # Final confirmation log message, using the newly configured logger_instance
    # This message will go to console (and file if enabled).
    # Showing effective console level for stdout handler. Stderr handler is fixed at WARNING.
    effective_stdout_level_name = logging.getLevelName(stdout_handler.level)
    # If stdout_handler's level is DEBUG, it shows DEBUG and INFO. If INFO, it shows INFO.
    # The MaxLevelFilter ensures it doesn't show WARNING+ on stdout.

    logger_instance.info(
        f"Logging setup complete for '{APP_ROOT_LOGGER_NAME}'. APP_ENV: '{app_env}'. "
        f"Console (stdout) Level Effective Min: {effective_stdout_level_name} (shows up to INFO). "
        f"Console (stderr) Level Effective Min: {logging.getLevelName(logging.WARNING)}. "
        f"File Level Effective Min: {logging.getLevelName(file_log_level_setting) if enable_file_logging and 'file_handler_timed' in locals() else 'N/A (Disabled)'}."
    )
