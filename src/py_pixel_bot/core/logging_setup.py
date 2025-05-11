import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime

def setup_logging():
    app_env_original = os.getenv('APP_ENV')
    app_env = app_env_original.lower() if app_env_original else 'development'
    
    project_root = Path(__file__).resolve().parent.parent.parent.parent 
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("py_pixel_bot") 
    logger.setLevel(logging.DEBUG) 

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter_str = ""

    current_date_str = datetime.now().strftime("%Y-%m-%d")
    log_file_name = f"{current_date_str}.log"
    log_file_path = logs_dir / log_file_name

    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path, maxBytes=10*1024*1024, backupCount=5
    )
    # Define base file formatter string without APP_ENV first
    base_file_formatter_str = "%(asctime)s - %(levelname)s - [%(name)s:%(module)s:%(lineno)d] - %(message)s"
    
    # Determine actual app_env for formatter string, handling invalid/None cases
    app_env_for_log_msg = app_env
    if app_env not in ['development', 'uat', 'production']:
        if not app_env_original: # Was None or empty
             print(f"Warning: APP_ENV not set. Defaulting to 'development' logging.", file=sys.stderr)
        else: # Was an invalid value
             print(f"Warning: Invalid APP_ENV '{app_env_original}'. Defaulting to 'development' logging.", file=sys.stderr)
        app_env_for_log_msg = 'development' # Use 'development' for the actual settings

    file_formatter_str_with_env = f"%(asctime)s - %(levelname)s - [{app_env_for_log_msg.upper()}] - %(name)s [%(module)s:%(lineno)d] - %(message)s"


    if app_env_for_log_msg == 'development': # Use the potentially corrected app_env
        console_handler.setLevel(logging.DEBUG)
        console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s [%(module)s:%(lineno)d] - %(message)s"
        file_handler.setLevel(logging.DEBUG)
    elif app_env_for_log_msg == 'uat':
        console_handler.setLevel(logging.INFO)
        console_formatter_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        file_handler.setLevel(logging.INFO)
    elif app_env_for_log_msg == 'production':
        console_handler.setLevel(logging.WARNING) 
        console_formatter_str = "%(asctime)s - %(levelname)s - %(message)s"
        file_handler.setLevel(logging.INFO) 
        
    console_handler.setFormatter(logging.Formatter(console_formatter_str))
    file_handler.setFormatter(logging.Formatter(file_formatter_str_with_env))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info(f"Logging setup complete. Effective APP_ENV for logging: '{app_env_for_log_msg}'. Logging to console and file: '{log_file_path}'")

if __name__ == '__main__':
    if 'APP_ENV' not in os.environ:
      os.environ['APP_ENV'] = 'development' 
    
    setup_logging()
    
    app_logger = logging.getLogger("py_pixel_bot") 
    app_logger.debug("This is a debug message from py_pixel_bot logger.")
    app_logger.info("This is an info message from py_pixel_bot logger.")
    app_logger.warning("This is a warning message from py_pixel_bot logger.")
    
    module_logger = logging.getLogger("py_pixel_bot.core.logging_setup_test")
    module_logger.info("Info from logging_setup_test.")
    module_logger.error("Error from logging_setup_test.")