import logging
import logging.handlers
import os
import sys
from datetime import datetime

# Determine project root to ensure logs directory is created there
# Assuming this file is src/py_pixel_bot/core/logging_setup.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")

# Store the root logger for the application package
# This allows modules to use logging.getLogger(__name__) and inherit configuration.
APP_ROOT_LOGGER_NAME = "py_pixel_bot"

# Keep track of handlers to allow dynamic level changes (e.g., by CLI verbosity)
console_handler: Optional[logging.StreamHandler] = None
file_handler: Optional[logging.handlers.TimedRotatingFileHandler] = None


def setup_logging():
    """
    Configures logging for the application based on APP_ENV.
    Creates console and rotating file handlers.
    Should be called once at application startup.
    """
    global console_handler, file_handler # Allow modification of global handler vars

    app_env = os.getenv("APP_ENV", "production").lower() # Default to production if not set
    
    # Determine log levels based on environment
    console_log_level = logging.INFO
    file_log_level = logging.INFO
    log_format_string = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
    
    # Customize formatter for console in production to be less verbose if desired
    console_log_format_string = log_format_string 

    if app_env == "development":
        console_log_level = logging.DEBUG
        file_log_level = logging.DEBUG
        # log_format_string = "%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - (%(threadName)s) - %(message)s" # Example with thread
    elif app_env == "uat": # Or "testing"
        console_log_level = logging.INFO
        file_log_level = logging.DEBUG # Keep file logs detailed for UAT
    elif app_env == "production":
        console_log_level = logging.INFO # Production console might be less verbose
        file_log_level = logging.INFO
        # console_log_format_string = "%(asctime)s - %(levelname)s - %(message)s" # Simpler console format for prod


    # Get the application's root logger
    # Configuring this logger will affect all loggers obtained via logging.getLogger('py_pixel_bot.module_name')
    app_logger = logging.getLogger(APP_ROOT_LOGGER_NAME)
    app_logger.setLevel(logging.DEBUG)  # Set root logger to lowest level; handlers control effective level

    # Prevent multiple handlers if setup_logging is called again (e.g., in tests or by mistake)
    if app_logger.hasHandlers():
        # Check if our specific handlers were already added to avoid duplication if only levels change.
        # This is a bit simplistic; a more robust check might involve handler names or types.
        # For now, if any handlers exist, assume it's configured.
        # If dynamic level changes are needed often, store and reuse handlers.
        logging.getLogger(__name__).debug("Logging already configured. Skipping full setup, will only adjust levels if possible.")
        # If handlers are stored globally, their levels can be adjusted here.
        # For now, this simplified check just skips re-adding.
        return


    # --- Console Handler ---
    # (Store globally to allow level changes by CLI)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_log_level)
    console_formatter = logging.Formatter(console_log_format_string)
    console_handler.setFormatter(console_formatter)
    app_logger.addHandler(console_handler)

    # --- File Handler ---
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        # Use current date for the log filename
        log_filename = f"{datetime.now().strftime('%Y-%m-%d')}.log"
        log_filepath = os.path.join(LOGS_DIR, log_filename)

        # Rotating file handler - rotates daily, keeps 7 backups
        # (Store globally to allow level changes by CLI if desired for file too, though less common)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_filepath, when="midnight", interval=1, backupCount=7, encoding="utf-8"
        )
        file_handler.setLevel(file_log_level)
        # Include APP_ENV in file log messages for better context
        file_log_formatter = logging.Formatter(f"APP_ENV:{app_env} - {log_format_string}")
        file_handler.setFormatter(file_log_formatter)
        app_logger.addHandler(file_handler)
        
        logging.getLogger(__name__).info(f"File logging configured. Level: {logging.getLevelName(file_log_level)}. Path: {log_filepath}")

    except Exception as e:
        # If file logging setup fails, log to console and continue without file logging
        logging.getLogger(__name__).error(f"Failed to configure file logging to '{LOGS_DIR}': {e}", exc_info=True)
        file_handler = None # Ensure it's None if setup failed

    logging.getLogger(__name__).info(
        f"Logging setup complete for APP_ENV='{app_env}'. Console Level: {logging.getLevelName(console_log_level)}."
    )

def set_console_log_level(level: int):
    """
    Allows dynamic adjustment of the console log level after initial setup.
    Useful for CLI verbosity flags.
    """
    global console_handler
    logger = logging.getLogger(__name__) # Use this module's logger for messages about logging
    if console_handler:
        current_level_name = logging.getLevelName(console_handler.level)
        new_level_name = logging.getLevelName(level)
        if console_handler.level != level:
            console_handler.setLevel(level)
            logger.info(f"Console log level dynamically changed from {current_level_name} to {new_level_name}.")
        else:
            logger.debug(f"Console log level already set to {new_level_name}. No change.")
    else:
        logger.warning("Cannot set console log level: Console handler not initialized.")

# Example of how to use the logger in other modules:
# import logging
# logger = logging.getLogger(__name__) # or logging.getLogger('py_pixel_bot.module.submodule')
# logger.debug("This is a debug message.")
# logger.info("This is an info message.")

if __name__ == "__main__":
    # Test logging setup
    print(f"Project root determined as: {PROJECT_ROOT}")
    print(f"Logs directory target: {LOGS_DIR}")

    # Simulate different environments
    print("\n--- Testing with APP_ENV=development ---")
    os.environ["APP_ENV"] = "development"
    # If logging was already set up by a previous import in a test runner,
    # we might need a way to reset it for this standalone test.
    # For now, assume it's a fresh run or setup_logging handles it.
    # To ensure fresh setup for test, clear handlers from root logger if any
    root_app_logger_for_test = logging.getLogger(APP_ROOT_LOGGER_NAME)
    if root_app_logger_for_test.hasHandlers():
        print("Clearing existing handlers for test...")
        for handler_to_remove in list(root_app_logger_for_test.handlers): # Iterate copy
            root_app_logger_for_test.removeHandler(handler_to_remove)
            handler_to_remove.close()
        console_handler = None; file_handler = None # Reset global refs

    setup_logging()
    test_logger_dev = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.test_dev")
    test_logger_dev.debug("This is a DEV debug message (should appear on console and file).")
    test_logger_dev.info("This is a DEV info message.")
    set_console_log_level(logging.INFO) # Test dynamic change
    test_logger_dev.debug("This DEV debug message should NOT appear on console now, but in file.")


    print("\n--- Testing with APP_ENV=production ---")
    os.environ["APP_ENV"] = "production"
    # Clear handlers again for a clean test
    root_app_logger_for_test = logging.getLogger(APP_ROOT_LOGGER_NAME)
    if root_app_logger_for_test.hasHandlers():
        print("Clearing existing handlers for test...")
        for handler_to_remove in list(root_app_logger_for_test.handlers):
             root_app_logger_for_test.removeHandler(handler_to_remove)
             handler_to_remove.close()
        console_handler = None; file_handler = None

    setup_logging()
    test_logger_prod = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.test_prod")
    test_logger_prod.debug("This is a PROD debug message (should NOT appear on console, maybe file if file_level is DEBUG).")
    test_logger_prod.info("This is a PROD info message (should appear on console and file).")
    test_logger_prod.warning("This is a PROD warning message.")

    print(f"\nCheck logs in: {LOGS_DIR}")