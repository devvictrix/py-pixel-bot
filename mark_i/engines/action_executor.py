import logging
import os
import time  # For explicit pauses if not using pyautogui.PAUSE
from typing import Dict, Any, Optional, List, Union, Tuple  # Added Tuple

import pyautogui  # type: ignore # PyAutoGUI often has type hinting issues

# ConfigManager is needed to resolve region configurations by name
from mark_i.core.config_manager import ConfigManager

# Use the application's root logger name for consistency
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.action_executor")

# Valid special keys for PyAutoGUI's press/hotkey functions.
# This list helps validate user input for 'press_key' actions.
# It's not exhaustive but covers common and safe keys.
# Users can refer to PyAutoGUI documentation for the full list.
VALID_PYAUTOGUI_KEYS = pyautogui.KEYBOARD_KEYS  # Use PyAutoGUI's own list directly


class ActionExecutor:
    """
    Executes actions like mouse clicks and keyboard inputs based on action specifications.
    Handles parameter validation, type conversion for substituted variables from rule context,
    and calculates target coordinates for various targeting relations, including those
    derived from Gemini AI analysis (v4.0.0 Phase 1.5+).
    """

    def __init__(self, config_manager_instance: ConfigManager):
        """
        Initializes the ActionExecutor.

        Args:
            config_manager_instance: An instance of ConfigManager, used to resolve
                                     region configurations by name for coordinate calculations.
        """
        if not isinstance(config_manager_instance, ConfigManager):
            # This is a critical dependency for resolving region coordinates.
            logger.critical("ActionExecutor CRITICAL ERROR: Initialized without a valid ConfigManager instance. Region-based targeting will fail.")
            raise ValueError("A valid ConfigManager instance is required for ActionExecutor.")
        self.config_manager = config_manager_instance

        # PyAutoGUI Global Settings
        pyautogui.FAILSAFE = True  # Move mouse to top-left (0,0) to abort PyAutoGUI actions.
        # pyautogui.PAUSE = 0.0 # Default global pause between PyAutoGUI calls.
        # We prefer explicit pauses via 'pyautogui_pause_before' in action specs.
        logger.info(f"ActionExecutor initialized. PyAutoGUI FAILSAFE is ON. PyAutoGUI Default PAUSE: {pyautogui.PAUSE}s.")

    def _validate_and_convert_numeric_param(
        self,
        value: Any,
        param_name: str,
        target_type: type,  # int or float
        action_type_for_log: str,
        rule_name_for_log: str,
        default_val: Optional[Union[int, float]] = None,  # Make default_val match target_type expectation
        min_val: Optional[Union[int, float]] = None,
        max_val: Optional[Union[int, float]] = None,
    ) -> Optional[Union[int, float]]:
        """
        Validates and converts a parameter to the target numeric type (int or float).
        Logs errors and returns None on critical failure if no default, or default if bounds fail.
        """
        log_prefix = f"R '{rule_name_for_log}', A '{action_type_for_log}', Prm '{param_name}'"
        original_value_for_log = value  # Keep original for logging if conversion fails
        converted_value: Optional[Union[int, float]] = None

        if isinstance(value, (int, float)):
            converted_value = target_type(value)  # Convert to int or float
        elif isinstance(value, str):
            try:
                stripped_value = value.strip()
                if not stripped_value and default_val is not None:  # Handle empty string if default is allowed
                    logger.debug(f"{log_prefix}: Empty string value, using default {default_val}.")
                    return default_val
                elif not stripped_value and default_val is None:  # Empty string but no default, treat as error for required numeric
                    logger.error(f"{log_prefix}: Empty string value provided for required numeric parameter. Original: '{original_value_for_log}'.")
                    return None

                if target_type == int:
                    converted_value = int(float(stripped_value))  # float() first for "10.0"
                elif target_type == float:
                    converted_value = float(stripped_value)
                else:  # Should not happen with current usage
                    logger.error(f"{log_prefix}: Invalid target_type '{target_type}' for numeric conversion.")
                    return None
            except ValueError:
                logger.error(f"{log_prefix}: Invalid numeric string value '{original_value_for_log}'. Cannot convert to {target_type.__name__}.")
                return None  # Conversion failed
        else:
            logger.error(f"{log_prefix}: Unexpected type '{type(value).__name__}' (value: {original_value_for_log}). Expected number or numeric string.")
            return None  # Wrong input type

        # Check bounds if applicable and value was converted
        if converted_value is not None:
            if min_val is not None and converted_value < min_val:
                logger.warning(f"{log_prefix}: Value {converted_value} is less than minimum {min_val}. Using default {default_val if default_val is not None else 'None (fail)'}.")
                return default_val  # Use default if provided, otherwise None will propagate from init
            if max_val is not None and converted_value > max_val:
                logger.warning(f"{log_prefix}: Value {converted_value} is greater than maximum {max_val}. Using default {default_val if default_val is not None else 'None (fail)'}.")
                return default_val
            logger.debug(f"{log_prefix}: Value '{original_value_for_log}' validated and converted to {target_type.__name__}: {converted_value}.")
            return converted_value

        return None  # Should be unreachable if logic is correct, but defensive

    def _get_target_coords(self, action_spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """
        Calculates target (x, y) absolute screen coordinates based on action_spec and context.
        Supports various 'target_relation' types including 'absolute', region-based,
        template-match-based, and Gemini-element-based.
        """
        target_relation = action_spec.get("target_relation")
        action_type_for_log = action_spec.get("type", "unknown_action")
        rule_name_for_log = context.get("rule_name", "UnknownRule_TaskStep")  # Generic for rule or NLU task step
        log_prefix = f"R '{rule_name_for_log}', A '{action_type_for_log}', TargetCoord"

        x_abs: Optional[int] = None
        y_abs: Optional[int] = None

        if target_relation == "absolute":
            x_abs = self._validate_and_convert_numeric_param(action_spec.get("x"), "x_abs", int, action_type_for_log, rule_name_for_log)
            y_abs = self._validate_and_convert_numeric_param(action_spec.get("y"), "y_abs", int, action_type_for_log, rule_name_for_log)
            if x_abs is not None and y_abs is not None:
                logger.info(f"{log_prefix}: Absolute target: ({x_abs}, {y_abs}).")
                return x_abs, y_abs
            logger.error(f"{log_prefix}: Missing or invalid 'x' or 'y' for absolute targeting. Values: x='{action_spec.get('x')}', y='{action_spec.get('y')}'")
            return None

        # For other relations, we often need a base region's screen coordinates
        base_region_screen_x, base_region_screen_y = 0, 0

        if target_relation in ["center_of_region", "relative_to_region"]:
            # Determine the target region for these relations
            # It can be specified in action_spec.target_region or fallback to context.condition_region
            target_region_name = action_spec.get("target_region") or context.get("condition_region")
            if not target_region_name:
                logger.error(f"{log_prefix}: No 'target_region' in action spec and no 'condition_region' in context for relation '{target_relation}'.")
                return None

            region_config = self.config_manager.get_region_config(str(target_region_name))
            if not region_config:
                logger.error(f"{log_prefix}: Target region '{target_region_name}' config not found for relation '{target_relation}'.")
                return None

            base_region_screen_x = region_config.get("x", 0)
            base_region_screen_y = region_config.get("y", 0)
            region_w = region_config.get("width", 0)
            region_h = region_config.get("height", 0)

            if target_relation == "center_of_region":
                x_abs = base_region_screen_x + region_w // 2
                y_abs = base_region_screen_y + region_h // 2
                logger.info(f"{log_prefix}: Center of region '{target_region_name}' (abs_base {base_region_screen_x},{base_region_screen_y} size {region_w}x{region_h}): ({x_abs}, {y_abs}).")
                return x_abs, y_abs

            elif target_relation == "relative_to_region":
                rel_x = self._validate_and_convert_numeric_param(action_spec.get("x"), "x_rel", int, action_type_for_log, rule_name_for_log)
                rel_y = self._validate_and_convert_numeric_param(action_spec.get("y"), "y_rel", int, action_type_for_log, rule_name_for_log)
                if rel_x is not None and rel_y is not None:
                    x_abs, y_abs = base_region_screen_x + rel_x, base_region_screen_y + rel_y
                    logger.info(f"{log_prefix}: Relative to region '{target_region_name}' (abs_base {base_region_screen_x},{base_region_screen_y}; offset {rel_x},{rel_y}): ({x_abs}, {y_abs}).")
                    return x_abs, y_abs
                logger.error(f"{log_prefix}: Missing or invalid relative 'x' or 'y' for region-relative targeting. Values: x='{action_spec.get('x')}', y='{action_spec.get('y')}'")
                return None

        elif target_relation == "center_of_last_match":
            last_match = context.get("last_match_info", {})  # From RulesEngine context
            if not isinstance(last_match, dict) or not last_match.get("found"):
                logger.warning(f"{log_prefix}: 'center_of_last_match' requested, but no valid template match info found in context.")
                return None

            match_region_name = last_match.get("matched_region_name")
            match_region_cfg = self.config_manager.get_region_config(str(match_region_name)) if match_region_name else None
            if not match_region_cfg:
                logger.error(f"{log_prefix}: Region '{match_region_name}' (where template matched) not found in profile for 'center_of_last_match'.")
                return None

            base_region_screen_x = match_region_cfg.get("x", 0)
            base_region_screen_y = match_region_cfg.get("y", 0)

            # Coordinates from template match are relative to the region it was found in
            match_rel_x = last_match.get("location_x", 0)
            match_rel_y = last_match.get("location_y", 0)
            match_w = last_match.get("width", 0)
            match_h = last_match.get("height", 0)

            x_abs = base_region_screen_x + match_rel_x + match_w // 2
            y_abs = base_region_screen_y + match_rel_y + match_h // 2
            logger.info(f"{log_prefix}: Center of last template match (in region '{match_region_name}'): ({x_abs}, {y_abs}).")
            return x_abs, y_abs

        elif target_relation in ["center_of_gemini_element", "top_left_of_gemini_element"]:
            gemini_var_name = action_spec.get("gemini_element_variable")
            if not gemini_var_name or not isinstance(gemini_var_name, str):
                logger.error(f"{log_prefix}: 'gemini_element_variable' name not specified or invalid for '{target_relation}'.")
                return None

            # Retrieve the wrapped data from context.variables
            # This data should be in the format: {"value": {"box": [x,y,w,h], "found":true, ...}, "_source_region_for_capture_": "region_name"}
            wrapped_gemini_data = context.get("variables", {}).get(gemini_var_name)
            if not isinstance(wrapped_gemini_data, dict) or "value" not in wrapped_gemini_data or "_source_region_for_capture_" not in wrapped_gemini_data:
                logger.error(
                    f"{log_prefix}: Variable '{gemini_var_name}' for Gemini element targeting is missing, not a dict, or missing 'value'/'_source_region_for_capture_'. Data: {wrapped_gemini_data}"
                )
                return None

            element_data_value = wrapped_gemini_data["value"]  # This is the actual data from Gemini (e.g., {"box": ..., "found": ...})
            source_region_name_for_gemini = wrapped_gemini_data["_source_region_for_capture_"]

            if not isinstance(element_data_value, dict) or not element_data_value.get("found") or not isinstance(element_data_value.get("box"), list) or len(element_data_value["box"]) != 4:
                logger.error(f"{log_prefix}: Gemini element data in variable '{gemini_var_name}' is malformed, 'found' is false, or 'box' is invalid. Value: {element_data_value}")
                return None

            source_region_config_for_gemini = self.config_manager.get_region_config(str(source_region_name_for_gemini))
            if not source_region_config_for_gemini:
                logger.error(f"{log_prefix}: Source region '{source_region_name_for_gemini}' (for Gemini capture) not found in profile config.")
                return None

            base_region_screen_x = source_region_config_for_gemini.get("x", 0)
            base_region_screen_y = source_region_config_for_gemini.get("y", 0)

            box_coords_relative = element_data_value["box"]  # [rel_x, rel_y, width, height] relative to source_region
            try:
                rel_elem_x, rel_elem_y, elem_w, elem_h = [int(c) for c in box_coords_relative]
                if elem_w <= 0 or elem_h <= 0:
                    raise ValueError("Box dimensions non-positive")
            except (ValueError, TypeError):
                logger.error(f"{log_prefix}: Gemini element 'box' coordinates {box_coords_relative} are not all valid positive numbers.")
                return None

            if target_relation == "center_of_gemini_element":
                x_abs = base_region_screen_x + rel_elem_x + elem_w // 2
                y_abs = base_region_screen_y + rel_elem_y + elem_h // 2
            elif target_relation == "top_left_of_gemini_element":
                x_abs = base_region_screen_x + rel_elem_x
                y_abs = base_region_screen_y + rel_elem_y
            else:  # Should not happen if target_relation is one of the two
                logger.error(f"{log_prefix}: Internal error - unhandled Gemini element relation '{target_relation}'.")
                return None

            logger.info(
                f"{log_prefix}: Target '{target_relation}' for element from var '{gemini_var_name}' (label: '{element_data_value.get('element_label', 'N/A')}') in source region '{source_region_name_for_gemini}' (abs_base {base_region_screen_x},{base_region_screen_y}; rel_box {box_coords_relative}): Abs Target ({x_abs}, {y_abs})."
            )
            return x_abs, y_abs

        logger.error(f"{log_prefix}: Unknown or unsupported target_relation '{target_relation}'. Cannot determine coordinates.")
        return None

    def execute_action(self, full_action_spec_with_context: Dict[str, Any]):
        """
        Executes a single action based on its full specification which includes the
        action parameters and the necessary context from rule evaluation.

        Args:
            full_action_spec_with_context: A dictionary containing:
                - 'type': The action type (e.g., "click", "type_text").
                - ...other action-specific parameters...
                - 'context': A sub-dictionary with 'rule_name', 'variables',
                             'condition_region', 'last_match_info'.
        """
        action_spec_params = {k: v for k, v in full_action_spec_with_context.items() if k != "context"}
        context = full_action_spec_with_context.get("context", {})  # Ensure context is always a dict

        action_type = action_spec_params.get("type")
        rule_name = context.get("rule_name", "UnknownRuleOrTask")  # More generic name for log
        log_prefix = f"R '{rule_name}', Action '{action_type}'"

        pause_before_val_str = str(action_spec_params.get("pyautogui_pause_before", "0.0"))
        pause_duration_s = self._validate_and_convert_numeric_param(pause_before_val_str, "pyautogui_pause_before", float, str(action_type), rule_name, 0.0, min_val=0.0)
        if pause_duration_s is None:
            pause_duration_s = 0.0  # Default if validation failed but not critical

        if pause_duration_s > 0:
            logger.debug(f"{log_prefix}: Pausing for {pause_duration_s:.3f}s before execution.")
            time.sleep(pause_duration_s)  # Use time.sleep for explicit internal pauses

        logger.info(f"{log_prefix}: Executing. Parameters (excluding context): {action_spec_params}")

        try:
            if action_type == "click":
                # _get_target_coords uses action_spec_params for action details and context for context
                coords_tuple = self._get_target_coords(action_spec_params, context)
                if coords_tuple:
                    x, y = coords_tuple
                    button_val = str(action_spec_params.get("button", "left")).lower()
                    if button_val not in pyautogui.PRIMARY_BUTTONS:  # PyAutoGUI constant for mouse buttons
                        logger.warning(f"{log_prefix}: Invalid click button '{button_val}'. Defaulting to 'left'.")
                        button_val = "left"

                    clicks_val = self._validate_and_convert_numeric_param(str(action_spec_params.get("clicks", "1")), "clicks", int, str(action_type), rule_name, 1, min_val=1)
                    if clicks_val is None:
                        clicks_val = 1  # Default on error

                    interval_s = self._validate_and_convert_numeric_param(str(action_spec_params.get("interval", "0.0")), "interval", float, str(action_type), rule_name, 0.0, min_val=0.0)
                    if interval_s is None:
                        interval_s = 0.0

                    logger.info(f"{log_prefix}: Simulating {button_val} click ({clicks_val}x, interval {interval_s:.3f}s) at ({x},{y}).")
                    pyautogui.click(x=x, y=y, clicks=clicks_val, interval=interval_s, button=button_val)
                else:
                    logger.error(f"{log_prefix}: Could not determine target coordinates. Click action skipped.")

            elif action_type == "type_text":
                text_val = str(action_spec_params.get("text", ""))  # Ensure string, can be empty
                interval_s_type = self._validate_and_convert_numeric_param(
                    str(action_spec_params.get("interval", "0.01")), "interval", float, str(action_type), rule_name, 0.01, min_val=0.0
                )  # Default small interval
                if interval_s_type is None:
                    interval_s_type = 0.01

                if text_val:  # Only type if text is not empty
                    log_snippet = text_val[:50].replace("\n", "\\n").replace("\r", "\\r") + ("..." if len(text_val) > 50 else "")
                    logger.info(f"{log_prefix}: Typing text (len: {len(text_val)}): '{log_snippet}' with char interval {interval_s_type:.3f}s.")
                    pyautogui.typewrite(text_val, interval=interval_s_type)
                else:
                    logger.info(f"{log_prefix}: No text provided to type (text parameter is empty). Action skipped.")

            elif action_type == "press_key":
                key_param = action_spec_params.get("key")
                keys_to_press: List[str] = []
                if isinstance(key_param, str):
                    keys_to_press = [k.strip().lower() for k in key_param.split(",") if k.strip()]
                elif isinstance(key_param, list):
                    keys_to_press = [str(k).strip().lower() for k in key_param if str(k).strip()]

                if not keys_to_press:
                    logger.warning(f"{log_prefix}: No valid key(s) in 'key' param: '{key_param}'. Skipped.")
                    return

                valid_keys_for_pyautogui = [k for k in keys_to_press if k in VALID_PYAUTOGUI_KEYS]
                if not valid_keys_for_pyautogui:
                    logger.error(f"{log_prefix}: All specified keys {keys_to_press} are invalid for PyAutoGUI. Action skipped.")
                    return
                if len(valid_keys_for_pyautogui) < len(keys_to_press):
                    logger.warning(f"{log_prefix}: Some specified keys were invalid and ignored. Using: {valid_keys_for_pyautogui}")

                if len(valid_keys_for_pyautogui) == 1:
                    logger.info(f"{log_prefix}: Pressing single key: '{valid_keys_for_pyautogui[0]}'.")
                    pyautogui.press(valid_keys_for_pyautogui[0])
                else:  # Multiple valid keys, treat as hotkey sequence
                    logger.info(f"{log_prefix}: Pressing hotkey sequence: {valid_keys_for_pyautogui}.")
                    pyautogui.hotkey(*valid_keys_for_pyautogui)

            elif action_type == "log_message":
                message_val = str(action_spec_params.get("message", "Default log_message action from rule."))
                level_str_val = str(action_spec_params.get("level", "INFO")).upper()
                log_level_val = getattr(logging, level_str_val, logging.INFO)  # Default to INFO if level string invalid

                # Use a distinct logger for messages generated by user rules for easier filtering
                rule_event_logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.RuleDefinedLog")
                rule_event_logger.log(log_level_val, f"R_Log '{rule_name}': {message_val}")
                logger.info(f"{log_prefix}: Custom log message written with level {level_str_val}.")

            # Example: Handling a hypothetical "wait" action
            # elif action_type == "wait":
            #     duration_s_wait = self._validate_and_convert_numeric_param(
            #         str(action_spec_params.get("duration_seconds", "1.0")),
            #         "duration_seconds", float, str(action_type), rule_name, 1.0, min_val=0.01, max_val=300.0 # Max 5 min wait
            #     )
            #     if duration_s_wait is not None:
            #         logger.info(f"{log_prefix}: Waiting for {duration_s_wait:.2f} seconds.")
            #         time.sleep(duration_s_wait)
            #     else:
            #         logger.error(f"{log_prefix}: Invalid duration for wait action. Skipped.")

            else:
                logger.error(f"{log_prefix}: Unknown action type '{action_type}'. Action skipped.")

        except pyautogui.FailSafeException:
            logger.critical(f"{log_prefix}: PyAutoGUI FAILSAFE triggered! Mouse moved to a screen corner. Automation halted by user.")
            # This is a critical user-initiated stop, re-raise to halt further execution by this bot instance.
            raise
        except Exception as e:  # Catch any other unexpected error during PyAutoGUI calls or action logic
            logger.exception(f"{log_prefix}: Unexpected error during execution: {e}")
            # Depending on policy, we might re-raise this to stop the bot,
            # or absorb it to allow the bot to continue to the next cycle.
            # For now, log and absorb, unless it's FailSafe.
