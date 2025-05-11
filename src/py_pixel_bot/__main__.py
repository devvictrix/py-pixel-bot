
from py_pixel_bot.core.config_manager import load_environment_variables
load_environment_variables() 

from py_pixel_bot.core.logging_setup import setup_logging
setup_logging() 

import logging 
import sys 
import time
import os 
import json 

from py_pixel_bot.core.config_manager import ConfigManager
from py_pixel_bot.ui.cli import parse_arguments, adjust_logging_for_cli_verbosity
from py_pixel_bot.ui.gui.region_selector import launch_region_selector_interactive 
import customtkinter as ctk 

from py_pixel_bot.engines.capture_engine import CaptureEngine
from py_pixel_bot.engines.analysis_engine import AnalysisEngine
from py_pixel_bot.engines.rules_engine import RulesEngine
from py_pixel_bot.engines.action_executor import ActionExecutor
from py_pixel_bot.main_controller import MainController

logger = logging.getLogger("py_pixel_bot.app") 

def handle_run_command(args):
    logger.info(f"Executing 'run' command for profile: '{args.profile}'")
    controller_instance = None
    try:
        config_manager = ConfigManager(profile_name=args.profile)
        config_data = config_manager.get_config()
        logger.info(f"Successfully loaded profile: '{args.profile}'. Desc: '{config_data.get('profile_description', 'N/A')}'")

        capture_engine = CaptureEngine()
        analysis_engine = AnalysisEngine()
        action_executor = ActionExecutor()
        rules_engine = RulesEngine(action_executor, config_manager, analysis_engine)
        
        controller_instance = MainController(config_data, capture_engine, analysis_engine, rules_engine)
        controller_instance.start_monitoring()
        
        logger.info("Bot monitoring started. Press Ctrl+C to stop.")
        while controller_instance.is_running():
            time.sleep(0.5)
            
    except FileNotFoundError as e:
        logger.critical(f"CRITICAL ERROR (run): Profile file issue for '{args.profile}' - {e}.")
        sys.exit(1)
    except json.JSONDecodeError as e: 
        logger.critical(f"CRITICAL ERROR (run): Profile '{args.profile}' invalid JSON: {e.msg} (line {e.lineno}, col {e.colno}).")
        sys.exit(1)
    finally: 
        if controller_instance and hasattr(controller_instance, 'is_running') and controller_instance.is_running():
            logger.info("handle_run_command ensuring controller shutdown...")
            controller_instance.stop_monitoring()

def handle_add_region_command(args):
    logger.info(f"Executing 'add-region' command for profile: '{args.profile}'. Initial name: '{args.name}'")
    
    try:
        ctk.set_appearance_mode(os.getenv("CTkAppearanceMode", "System")) 
        ctk.set_default_color_theme(os.getenv("CTkColorTheme", "blue"))
    except Exception as e_ctk:
        logger.warning(f"Could not set CustomTkinter theme: {e_ctk}")

    selected_region_data = launch_region_selector_interactive(initial_name=args.name)

    if selected_region_data and selected_region_data.get("name") and selected_region_data.get("coords"):
        region_name = selected_region_data["name"]
        coords = selected_region_data["coords"]
        logger.info(f"Region Selector GUI returned: Name='{region_name}', Coords={coords}")
        
        config_manager_instance = None
        try:
            config_manager_instance = ConfigManager(profile_name=args.profile)
        except FileNotFoundError:
            logger.info(f"Profile '{args.profile}' does not exist. Will create a new one.")
            config_manager_instance = ConfigManager(profile_name=args.profile) 
            config_manager_instance.config_data = { 
                "profile_description": f"New profile: {args.profile}",
                "settings": {"monitoring_interval_seconds": 1.0},
                "regions": [], "rules": [], "templates": []
            }
            logger.info(f"Initialized new in-memory config for '{args.profile}'")
        except json.JSONDecodeError as e:
            logger.error(f"Profile '{args.profile}' is corrupted: {e}. Cannot add region. Please fix or delete profile.")
            return 
        except Exception as e_load:
            logger.error(f"Unexpected error loading profile '{args.profile}' for add-region: {e_load}", exc_info=True)
            return

        try: 
            if config_manager_instance.add_region_to_config(region_name, coords):
                config_manager_instance.save_profile() 
                logger.info(f"Region '{region_name}' added/updated in profile '{args.profile}' and saved.")
            else:
                logger.error(f"Failed to add region '{region_name}' to in-memory config for profile '{args.profile}'. Profile not saved.")
        except Exception as e_save:
            logger.error(f"Error saving profile '{args.profile}' after attempting to add region: {e_save}", exc_info=True)
    else:
        logger.info("Region selection was cancelled or no valid data returned from GUI.")

def main_entry_point():
    logger.info(f"--- PyPixelBot Main Entry Point ---")
    effective_app_env = os.getenv('APP_ENV', 'development').lower()
    if effective_app_env not in ['development', 'uat', 'production']:
        effective_app_env = 'development (defaulted by logging_setup)'
    logger.info(f"Effective APP_ENV for this session: '{effective_app_env}'")
    
    try:
        args = parse_arguments()
        
        if hasattr(args, 'verbose') and args.verbose > 0:
            adjust_logging_for_cli_verbosity(args.verbose)

        if args.command == "run":
            handle_run_command(args)
        elif args.command == "add-region":
            handle_add_region_command(args)
        else:
            logger.error(f"Unknown command: {args.command}. Use --help for options.")
            # To print general help if command is unknown and subparsers.required = True
            # This is a bit of a workaround as argparse might exit before this.
            # A more robust way is to have a default subparser or handle it in parse_arguments.
            # For now, this is a fallback.
            if hasattr(args, 'parser_instance_for_help'): # If cli.py could pass the main parser
                args.parser_instance_for_help.print_help()
            sys.exit(1) 
            
    except KeyboardInterrupt: 
        logger.info("Application shutdown requested via KeyboardInterrupt at main entry point.")
    except Exception as e: 
        logger.critical(f"A top-level unhandled exception occurred: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info(f"--- PyPixelBot Main Execution Finished ---")

if __name__ == "__main__":
    main_entry_point()