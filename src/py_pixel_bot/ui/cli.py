import argparse
import logging
import sys 
from pathlib import Path 

logger = logging.getLogger(__name__) 

def parse_arguments():
    parser = argparse.ArgumentParser(description="PyPixelBot - Visual Automation Tool for Windows.", formatter_class=argparse.RawTextHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", title="commands", description="Valid commands", help="Use '<command> --help' for more.", required=True)
    run_parser = subparsers.add_parser("run", help="Run a bot profile.")
    run_parser.add_argument("profile", type=str, help="Name of JSON profile file (e.g., my_bot or my_bot.json) from 'profiles/'. '.json' optional.")
    run_parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase console verbosity for 'run'. -v INFO, -vv DEBUG.")
    add_region_parser = subparsers.add_parser("add-region", help="Launch GUI to add/update a region in a profile.")
    add_region_parser.add_argument("profile", type=str, help="Name of JSON profile file to add/update region in.")
    add_region_parser.add_argument("--name", type=str, default="", help="Optional initial name for new region in GUI.")
    add_region_parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase console verbosity for 'add-region'.")
    args = parser.parse_args()
    if hasattr(args, 'profile') and args.profile and not args.profile.lower().endswith(".json"):
        args.profile = args.profile + ".json"
    logger.debug(f"CLI arguments parsed: {args}")
    return args

def adjust_logging_for_cli_verbosity(verbose_level: int):
    if verbose_level == 0: return
    package_logger = logging.getLogger("py_pixel_bot")
    console_handler_to_adjust = None
    for handler in package_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and hasattr(handler.stream, 'fileno') and handler.stream.fileno() == sys.stdout.fileno():
            console_handler_to_adjust = handler; break
    if console_handler_to_adjust:
        current_console_level = console_handler_to_adjust.level; new_level = current_console_level
        if verbose_level == 1 and current_console_level > logging.INFO : new_level = logging.INFO
        elif verbose_level >= 2 and current_console_level > logging.DEBUG: new_level = logging.DEBUG
        if new_level < current_console_level:
            console_handler_to_adjust.setLevel(new_level)
            if new_level <= logging.DEBUG and "module" not in console_handler_to_adjust.formatter._fmt :
                 dev_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s [%(module)s:%(lineno)d] - %(message)s")
                 console_handler_to_adjust.setFormatter(dev_formatter)
            logger.info(f"CLI verbosity (-{'v'*verbose_level}) increased console log level to: {logging.getLevelName(new_level)}")
        elif verbose_level > 0 : logger.info(f"CLI verbosity (-{'v'*verbose_level}) requested, but console log level already {logging.getLevelName(current_console_level)}.")
    else: logger.warning("Could not find main console handler to adjust CLI verbosity.")

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent 
    if str(project_src_dir) not in sys.path: sys.path.insert(0, str(project_src_dir))
    from py_pixel_bot.core.config_manager import load_environment_variables
    load_environment_variables() 
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging() 
    test_logger_cli = logging.getLogger(__name__ + "_test"); test_logger_cli.info("--- CLI Module Direct Test Start (Subcommands) ---")
    test_cases_cli = [ (["run", "my_profile"], "command='run', profile='my_profile.json', verbose=0"), (["add-region", "secondary", "--name", "BannerArea", "-v"], "command='add-region', profile='secondary.json', name='BannerArea', verbose=1")]
    original_argv_cli = sys.argv.copy()
    for i, (test_args_cli, expected_log_cli) in enumerate(test_cases_cli):
        test_logger_cli.info(f"\n--- CLI Test Case {i+1}: Running with args: {test_args_cli} ---")
        sys.argv = [original_argv_cli[0]] + test_args_cli
        import os; os.environ['APP_ENV'] = 'production'; setup_logging() 
        test_logger_cli.info(f"(Re-initialized logging with APP_ENV=production for test)")
        try:
            parsed_args_cli = parse_arguments(); test_logger_cli.info(f"Parsed: {vars(parsed_args_cli)}")
            if hasattr(parsed_args_cli, 'verbose') and parsed_args_cli.verbose > 0: adjust_logging_for_cli_verbosity(parsed_args_cli.verbose)
            # Basic check, more robust would be specific assertions
            if parsed_args_cli.command in expected_log_cli and parsed_args_cli.profile in expected_log_cli: test_logger_cli.info(f"Test Case {i+1} PASS (basic field check).")
            else: test_logger_cli.error(f"Test Case {i+1} FAIL (basic field check). Expected part of '{expected_log_cli}'")
        except SystemExit as e_cli: test_logger_cli.info(f"Test Case {i+1} SystemExit {e_cli.code} (normal for --help).")
        except Exception as e_cli_exc: test_logger_cli.error(f"Test Case {i+1} FAIL: Exception for args {test_args_cli}: {e_cli_exc}", exc_info=True)
    sys.argv = original_argv_cli; test_logger_cli.info("\n--- CLI Module Direct Test End ---")