import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

# Add a print statement at the top of the module to confirm it's being loaded
print("DEBUG: py_pixel_bot.core.logging_setup module IS BEING LOADED AND EXECUTED.")


def setup_logging(
    console_log_level=logging.INFO, log_file_path=None, enable_file_logging=True
):
    """
    Configures logging for the application.
    Now correctly accepts console_log_level, log_file_path, and enable_file_logging.
    """
    # Add a print statement inside the function to confirm it's being called
    print(
        f"DEBUG: setup_logging CALLED with console_log_level={console_log_level}, log_file_path={log_file_path}, enable_file_logging={enable_file_logging}"
    )

    app_env = os.getenv("APP_ENV", "production").lower()
    project_root = os.getcwd()
    logs_dir = os.path.join(project_root, "logs")

    if not os.path.exists(logs_dir) and enable_file_logging:
        try:
            os.makedirs(logs_dir)
            print(f"DEBUG: Created logs directory: {logs_dir}")
        except OSError as e:
            sys.stderr.write(
                f"Warning: Could not create logs directory: {logs_dir}. Error: {e}\n"
            )
            enable_file_logging = False  # Fallback to console-only

    base_file_level = logging.INFO  # Default for production or uat
    console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"

    if app_env == "development":
        base_file_level = logging.DEBUG
        # console_formatter_str is more detailed for dev in __main__.py's initial setup
        # but this setup_logging can also refine it if desired.
        # For now, let's keep it simple and assume __main__.py sets the detailed dev console format initially
        # or we can enforce it here. Let's enforce for clarity.
        console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"

    # Configure the root logger
    # It's often better to get a specific application root logger than the absolute root logger
    # e.g., app_logger = logging.getLogger('py_pixel_bot')
    # For simplicity, we'll stick to the root logger for now as per previous structure.
    # However, this can lead to issues if other libraries also use the root logger.
    # A dedicated app logger is a good refinement later.

    log = logging.getLogger()  # Get root logger
    log.setLevel(logging.DEBUG)  # Set root logger to lowest level; handlers will filter

    # Clear existing handlers from the root logger to avoid duplicates if re-running setup
    # This is important if setup_logging can be called multiple times (e.g. by __main__ then a module)
    if log.hasHandlers():
        print(
            f"DEBUG: Clearing {len(log.handlers)} existing handlers from root logger."
        )
        log.handlers.clear()

    # Console Handler
    console_formatter = logging.Formatter(console_formatter_str)
    ch = logging.StreamHandler(sys.stdout)  # Use sys.stdout for console output
    ch.setLevel(console_log_level)
    ch.setFormatter(console_formatter)
    log.addHandler(ch)
    print(
        f"DEBUG: ConsoleHandler added with level {logging.getLevelName(console_log_level)}."
    )

    # File Handler (Timed Rotating)
    if enable_file_logging:
        final_log_file_path = ""
        if log_file_path:  # If a specific path is provided via CLI arg
            final_log_file_path = log_file_path
            # Ensure directory for custom log file path exists
            custom_log_dir = os.path.dirname(final_log_file_path)
            if custom_log_dir and not os.path.exists(custom_log_dir):
                try:
                    os.makedirs(custom_log_dir)
                    print(f"DEBUG: Created custom log directory: {custom_log_dir}")
                except OSError as e:
                    sys.stderr.write(
                        f"Warning: Could not create custom log directory: {custom_log_dir}. Error: {e}. File logging to this path disabled.\n"
                    )
                    # Potentially fall back to default logs_dir or disable file logging
                    final_log_file_path = os.path.join(
                        logs_dir, "app_fallback.log"
                    )  # Fallback example
                    if not os.path.exists(logs_dir):
                        os.makedirs(logs_dir)  # Ensure fallback dir exists

        else:  # Default log file path in 'logs/' directory
            default_log_filename = "py_pixel_bot.log"  # Base name for rotating log
            final_log_file_path = os.path.join(logs_dir, default_log_filename)

        print(f"DEBUG: Attempting to set up FileHandler for: {final_log_file_path}")
        file_formatter = logging.Formatter(file_formatter_str)

        try:
            # Rotate daily ('midnight'), keep 7 backup files
            fh = TimedRotatingFileHandler(
                final_log_file_path,
                when="midnight",
                interval=1,
                backupCount=7,
                encoding="utf-8",
            )
            fh.setLevel(base_file_level)  # Use base_file_level determined by APP_ENV
            fh.setFormatter(file_formatter)
            log.addHandler(fh)
            log.info(
                f"File logging enabled. Log level: {logging.getLevelName(base_file_level)}. Log file: {final_log_file_path}"
            )
            print(
                f"DEBUG: FileHandler added for {final_log_file_path} with level {logging.getLevelName(base_file_level)}."
            )
        except Exception as e:
            sys.stderr.write(
                f"Error setting up file handler for {final_log_file_path}: {e}\n"
            )
            log.warning(
                f"Could not set up file logging for {final_log_file_path} due to: {e}"
            )

    else:
        log.info("File logging explicitly disabled.")
        print("DEBUG: File logging explicitly disabled.")

    log.info(
        f"Logging setup complete. APP_ENV: '{app_env}'. Console level effective: {logging.getLevelName(ch.level)}."
    )
    print("DEBUG: setup_logging function finished.")
