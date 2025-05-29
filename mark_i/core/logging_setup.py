import logging
import os
import sys
from datetime import date  # For daily filename

# (Keep print statements for debugging)
print("DEBUG: mark_i.core.logging_setup module IS BEING LOADED AND EXECUTED.")

APP_ROOT_LOGGER_NAME = "mark_i"  # Define the root logger name here


def setup_logging(console_log_level=logging.INFO, log_file_path=None, enable_file_logging=True):  # Parameter name changed back to log_file_path
    """
    Configures logging for the application.
    The active log file will be named YYYY-MM-DD.log (or .ext based on log_file_path).
    This version uses a basic FileHandler, so no automatic rotation or backupCount.
    """
    print(f"DEBUG: setup_logging CALLED with console_log_level={console_log_level}, " f"log_file_path={log_file_path}, enable_file_logging={enable_file_logging}")

    app_env = os.getenv("APP_ENV", "production").lower()
    try:
        module_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(module_dir))
    except NameError:
        project_root = os.getcwd()

    logs_dir = os.path.join(project_root, "logs")

    if not os.path.exists(logs_dir) and enable_file_logging:
        try:
            os.makedirs(logs_dir)
            print(f"DEBUG: Created logs directory: {logs_dir}")
        except OSError as e:
            sys.stderr.write(f"Warning: Could not create logs directory: {logs_dir}. Error: {e}\n")
            enable_file_logging = False

    base_file_level = logging.INFO
    console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - " "[%(module)s:%(funcName)s:%(lineno)d] - %(message)s"

    if app_env == "development":
        base_file_level = logging.DEBUG
        console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - " "[%(module)s:%(funcName)s:%(lineno)d] - %(message)s"

    log = logging.getLogger()  # Get the root logger to clear its handlers
    # If we want hierarchical logging like "mark_i.module_name",
    # we should configure the "mark_i" logger primarily.
    # log = logging.getLogger(APP_ROOT_LOGGER_NAME) # This would be the base for all app logs
    log.setLevel(logging.DEBUG)  # Set root/base logger to DEBUG, handlers control output

    if log.hasHandlers():
        print(f"DEBUG: Clearing {len(log.handlers)} existing handlers from logger '{log.name}'.")
        log.handlers.clear()

    console_formatter = logging.Formatter(console_formatter_str)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_log_level)
    ch.setFormatter(console_formatter)
    log.addHandler(ch)
    print(f"DEBUG: ConsoleHandler added to logger '{log.name}' with level {logging.getLevelName(console_log_level)}.")

    if enable_file_logging:
        final_log_file_path_for_handler = ""  # Renamed to avoid confusion with parameter
        today_date_str = date.today().strftime("%Y-%m-%d")

        if log_file_path:  # This is the override from CLI
            final_log_file_path_for_handler = log_file_path
            custom_log_dir = os.path.dirname(final_log_file_path_for_handler)
            if custom_log_dir and not os.path.exists(custom_log_dir):
                try:
                    os.makedirs(custom_log_dir)
                    print(f"DEBUG: Created custom log directory for override: {custom_log_dir}")
                except OSError as e:
                    sys.stderr.write(f"Warning: Could not create custom log directory " f"'{custom_log_dir}' for override path. Error: {e}.\n")
                    final_log_file_path_for_handler = os.path.join(logs_dir, f"{today_date_str}.log")
                    if not os.path.exists(logs_dir):
                        os.makedirs(logs_dir)  # Ensure default logs_dir
        else:
            final_log_file_path_for_handler = os.path.join(logs_dir, f"{today_date_str}.log")

        print("DEBUG: Attempting to set up FileHandler for active log: " f"{final_log_file_path_for_handler}")
        file_formatter = logging.Formatter(file_formatter_str)

        try:
            fh = logging.FileHandler(final_log_file_path_for_handler, mode="a", encoding="utf-8")
            fh.setLevel(base_file_level)
            fh.setFormatter(file_formatter)
            log.addHandler(fh)
            log.info(f"File logging enabled. Log level: {logging.getLevelName(base_file_level)}. " f"Active log file: {final_log_file_path_for_handler}")
            print(f"DEBUG: FileHandler added for {final_log_file_path_for_handler} " f"with level {logging.getLevelName(base_file_level)}.")
        except Exception as e:
            sys.stderr.write(f"Error setting up file handler for {final_log_file_path_for_handler}: {e}\n")
            log.warning(f"Could not set up file logging for {final_log_file_path_for_handler} " f"due to: {e}")
    else:
        log.info("File logging explicitly disabled.")
        print("DEBUG: File logging explicitly disabled.")

    log.info(f"Logging setup complete. APP_ENV: '{app_env}'. " f"Console level effective: {logging.getLevelName(ch.level)}.")
    print("DEBUG: setup_logging function finished.")
