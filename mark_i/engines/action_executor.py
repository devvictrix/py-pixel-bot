import logging
import os
import pyautogui  # type: ignore
from typing import Dict, Any, Optional, List, Union

from tkinter import messagebox  # For showing errors directly to user during runtime if GUI is implied

from mark_i.core.config_manager import ConfigManager
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME  # <--- IMPORT HERE

logger = logging.getLogger(__name__)


class ActionExecutor:
    """
    Executes actions like mouse clicks and keyboard inputs based on action specifications.
    Handles parameter validation and type conversion for substituted variables.
    """

    def __init__(self, config_manager: ConfigManager):
        """
        Initializes the ActionExecutor.

        Args:
            config_manager: The ConfigManager instance, used to resolve region coordinates
                            if an action targets a region not directly provided in its context.
        """
        self.config_manager = config_manager
        pyautogui.FAILSAFE = True  # Move mouse to top-left (0,0) to abort PyAutoGUI actions
        # pyautogui.PAUSE = 0.0 # Default pause between PyAutoGUI actions; we use explicit pauses.
        logger.info("ActionExecutor initialized. PyAutoGUI FAILSAFE is ON.")

    def _validate_and_convert_coord_param(self, value: Any, param_name: str, action_type_for_log: str, rule_name_for_log: str) -> Optional[int]:
        """
        Validates and converts a coordinate parameter (potentially from a substituted variable) to an integer.
        Logs errors and shows messagebox on failure.
        """
        if isinstance(value, (int, float)):
            logger.debug(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' is numeric ({value}), converting to int.")
            return int(value)
        if isinstance(value, str):
            try:
                # Try float first to handle "10.0", then int
                val_int = int(float(value.strip()))
                logger.debug(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' string '{value}' converted to int {val_int}.")
                return val_int
            except ValueError:
                logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' has invalid numeric string value '{value}'. Cannot convert to integer.")
                # Removed messagebox call from here to avoid GUI dependency in core engine
                # messagebox.showerror("Action Execution Error", f"Rule '{rule_name_for_log}': Invalid numeric value '{value}' for '{param_name}' in action '{action_type_for_log}'.")
                return None
        logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' has unexpected type '{type(value)}' (value: {value}). Expected number or numeric string.")
        # messagebox.showerror("Action Execution Error", f"Rule '{rule_name_for_log}': Invalid type for '{param_name}' in action '{action_type_for_log}'. Expected number.")
        return None

    def _validate_and_convert_float_param(self, value: Any, param_name: str, action_type_for_log: str, rule_name_for_log: str, default_val: float, min_val: Optional[float] = None) -> float:
        """
        Validates and converts a parameter to float, with optional min bound.
        Logs errors and shows messagebox on failure, returning default.
        """
        if isinstance(value, (int, float)):
            val_float = float(value)
        elif isinstance(value, str):
            try:
                val_float = float(value.strip())
            except ValueError:
                logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' has invalid float string value '{value}'. Using default {default_val}.")
                # messagebox.showwarning("Action Execution Warning", f"Rule '{rule_name_for_log}': Invalid value '{value}' for '{param_name}' in action '{action_type_for_log}'. Using default {default_val}.")
                return default_val
        else:
            logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' has unexpected type '{type(value)}'. Using default {default_val}.")
            # messagebox.showwarning("Action Execution Warning", f"Rule '{rule_name_for_log}': Invalid type for '{param_name}' in action '{action_type_for_log}'. Using default {default_val}.")
            return default_val

        if min_val is not None and val_float < min_val:
            logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' value {val_float} is less than minimum {min_val}. Using default {default_val}.")
            # messagebox.showwarning("Action Execution Warning", f"Rule '{rule_name_for_log}': Value for '{param_name}' ({val_float}) is too small. Using default {default_val}.")
            return default_val

        logger.debug(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Param '{param_name}' validated to float {val_float}.")
        return val_float

    def _get_target_coords(self, action_spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[tuple[int, int]]:
        """
        Calculates target (x, y) screen coordinates based on action_spec and context.
        Handles potential string to int conversion for coordinate values.
        """
        target_relation = action_spec.get("target_relation")
        action_type_for_log = action_spec.get("type", "unknown_action")
        rule_name_for_log = context.get("rule_name", "UnknownRule")

        x_val: Optional[int] = None
        y_val: Optional[int] = None

        if target_relation == "absolute":
            x_val = self._validate_and_convert_coord_param(action_spec.get("x"), "x", action_type_for_log, rule_name_for_log)
            y_val = self._validate_and_convert_coord_param(action_spec.get("y"), "y", action_type_for_log, rule_name_for_log)
            if x_val is not None and y_val is not None:
                return x_val, y_val
            logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Missing or invalid 'x' or 'y' for absolute targeting.")
            return None

        target_region_name = action_spec.get("target_region") if action_spec.get("target_region") else context.get("condition_region")
        target_region_config = None
        if target_region_name:
            target_region_config = self.config_manager.get_region_config(target_region_name)

        if not target_region_config and target_relation in ["center_of_region", "relative_to_region"]:
            logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Target region '{target_region_name}' config not found for relation '{target_relation}'.")
            # messagebox.showerror("Action Error", f"Rule '{rule_name_for_log}': Region '{target_region_name}' not found for action.")
            return None

        region_x, region_y, region_w, region_h = 0, 0, 0, 0
        if target_region_config:
            region_x = target_region_config.get("x", 0)
            region_y = target_region_config.get("y", 0)
            region_w = target_region_config.get("width", 0)
            region_h = target_region_config.get("height", 0)

        if target_relation == "center_of_region":
            if not target_region_config:
                return None
            return region_x + region_w // 2, region_y + region_h // 2

        elif target_relation == "relative_to_region":
            if not target_region_config:
                return None
            rel_x = self._validate_and_convert_coord_param(action_spec.get("x"), "relative_x", action_type_for_log, rule_name_for_log)
            rel_y = self._validate_and_convert_coord_param(action_spec.get("y"), "relative_y", action_type_for_log, rule_name_for_log)
            if rel_x is not None and rel_y is not None:
                return region_x + rel_x, region_y + rel_y
            logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Missing or invalid relative 'x' or 'y' for region-relative targeting.")
            return None

        elif target_relation == "center_of_last_match":
            last_match_info = context.get("last_match_info", {})
            if not last_match_info.get("found"):
                logger.warning(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': 'center_of_last_match' requested, but no template match found in context.")
                return None

            matched_region_name = last_match_info.get("matched_region_name")
            if not matched_region_name:
                logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': 'center_of_last_match' - matched_region_name missing from last_match_info.")
                return None

            matched_region_config = self.config_manager.get_region_config(matched_region_name)
            if not matched_region_config:
                logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': 'center_of_last_match' - Config for matched_region '{matched_region_name}' not found.")
                # messagebox.showerror("Action Error", f"Rule '{rule_name_for_log}': Region '{matched_region_name}' (from template match) not found.")
                return None

            base_x = matched_region_config.get("x", 0)
            base_y = matched_region_config.get("y", 0)

            match_rel_x = last_match_info.get("location_x", 0)
            match_rel_y = last_match_info.get("location_y", 0)
            match_w = last_match_info.get("width", 0)
            match_h = last_match_info.get("height", 0)

            center_x = base_x + match_rel_x + match_w // 2
            center_y = base_y + match_rel_y + match_h // 2
            return center_x, center_y

        logger.error(f"Rule '{rule_name_for_log}', Action '{action_type_for_log}': Unknown or unsupported target_relation '{target_relation}'.")
        return None

    def execute_action(self, full_action_spec: Dict[str, Any]):
        action_type = full_action_spec.get("type")
        context = full_action_spec.get("context", {})
        rule_name = context.get("rule_name", "UnknownRule")

        pause_val_str = full_action_spec.get("pyautogui_pause_before", "0.0")
        pause_duration = self._validate_and_convert_float_param(pause_val_str, "pyautogui_pause_before", str(action_type), rule_name, 0.0, min_val=0.0)

        if pause_duration > 0:
            logger.debug(f"Rule '{rule_name}', Action '{action_type}': Pausing for {pause_duration:.2f}s before execution.")
            try:
                pyautogui.sleep(pause_duration)
            except Exception as e_sleep:
                logger.warning(f"Rule '{rule_name}', Action '{action_type}': Error during pyautogui.sleep({pause_duration}): {e_sleep}. Continuing action.")

        logger.info(f"Rule '{rule_name}': Executing action of type '{action_type}'. Spec (excluding context): " f"{ {k:v for k,v in full_action_spec.items() if k != 'context'} }")

        try:
            if action_type == "click":
                coords = self._get_target_coords(full_action_spec, context)
                if coords:
                    x_coord, y_coord = coords
                    button = str(full_action_spec.get("button", "left")).lower()

                    num_clicks_str = str(full_action_spec.get("clicks", "1"))
                    num_clicks = self._validate_and_convert_coord_param(num_clicks_str, "clicks", action_type, rule_name)
                    if num_clicks is None or num_clicks <= 0:
                        num_clicks = 1
                        logger.warning(f"R '{rule_name}', A 'click': Invalid 'clicks' val, defaulting to 1.")

                    interval_str = str(full_action_spec.get("interval", "0.0"))
                    interval_val = self._validate_and_convert_float_param(interval_str, "interval", action_type, rule_name, 0.0, min_val=0.0)

                    logger.info(f"Rule '{rule_name}': Simulating {button} click ({num_clicks}x, interval {interval_val:.2f}s) at ({x_coord},{y_coord}).")
                    pyautogui.click(x=x_coord, y=y_coord, clicks=num_clicks, interval=interval_val, button=button)
                else:
                    logger.error(f"Rule '{rule_name}', Action 'click': Could not determine target coordinates. Action skipped.")

            elif action_type == "type_text":
                text_to_type = str(full_action_spec.get("text", ""))
                interval_str = str(full_action_spec.get("interval", "0.0"))
                interval_val = self._validate_and_convert_float_param(interval_str, "interval", action_type, rule_name, 0.0, min_val=0.0)

                if text_to_type:
                    logger.info(
                        f"Rule '{rule_name}': Typing text (len: {len(text_to_type)}): '{text_to_type[:50].replace(os.linesep, ' ')}...' with interval {interval_val:.2f}s."
                    )  # os import needed
                    pyautogui.typewrite(text_to_type, interval=interval_val)
                else:
                    logger.info(f"Rule '{rule_name}', Action 'type_text': No text provided to type (or text is empty string).")

            elif action_type == "press_key":
                key_or_keys_param = full_action_spec.get("key")

                keys_to_press: Union[str, List[str], None] = None
                if isinstance(key_or_keys_param, str):
                    keys_to_press = key_or_keys_param.strip()
                    if not keys_to_press:
                        logger.warning(f"Rule '{rule_name}', Action 'press_key': 'key' parameter is an empty string. Action skipped.")
                        keys_to_press = None
                elif isinstance(key_or_keys_param, list):
                    keys_to_press = [str(k).strip() for k in key_or_keys_param if str(k).strip()]
                    if not keys_to_press:
                        logger.warning(f"Rule '{rule_name}', Action 'press_key': 'key' parameter list is empty or contains only empty strings. Action skipped.")
                        keys_to_press = None

                if keys_to_press:
                    if isinstance(keys_to_press, str):
                        logger.info(f"Rule '{rule_name}': Pressing key: '{keys_to_press}'.")
                        pyautogui.press(keys_to_press)
                    elif isinstance(keys_to_press, list):
                        logger.info(f"Rule '{rule_name}': Pressing keys (hotkey sequence): {keys_to_press}.")
                        pyautogui.hotkey(*keys_to_press)
                else:
                    logger.warning(f"Rule '{rule_name}', Action 'press_key': No valid key(s) provided in 'key' parameter: '{key_or_keys_param}'. Action skipped.")

            elif action_type == "log_message":
                message = str(full_action_spec.get("message", "Default log message from rule."))
                level_str = str(full_action_spec.get("level", "INFO")).upper()
                log_level = getattr(logging, level_str, logging.INFO)
                rule_event_logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.RuleActionLog")
                rule_event_logger.log(log_level, f"Rule '{rule_name}': {message}")

            else:
                logger.error(f"Rule '{rule_name}': Unknown action type '{action_type}'. Action skipped.")

        except pyautogui.FailSafeException:
            logger.critical(f"Rule '{rule_name}', Action '{action_type}': PyAutoGUI FAILSAFE triggered! Mouse moved to a corner.")
            raise
        except Exception as e:
            logger.exception(f"Rule '{rule_name}', Action '{action_type}': Error during execution. Error: {e}")
