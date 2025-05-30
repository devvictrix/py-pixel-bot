import logging
import os  # For os.linesep if used in logging text processing
import time  # For explicit pauses if needed, though pyautogui.sleep is preferred for its own pauses
from typing import Dict, Any, Optional, List, Union

import pyautogui  # type: ignore # PyAutoGUI often has type hinting issues

# Assuming ConfigManager might be needed for some context, but it's not directly used in current actions
# from mark_i.core.config_manager import ConfigManager # Not strictly needed by current methods

# Use the application's root logger name, or __name__ for module-specific logging
# For consistency with other modules:
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.action_executor")
# If APP_ROOT_LOGGER_NAME is not consistently set up before this module logs,
# using logger = logging.getLogger(__name__) is a safe fallback.

# Valid special keys for PyAutoGUI's press/hotkey functions (not exhaustive, but common ones)
# This can be expanded. See PyAutoGUI documentation for a full list.
VALID_PYAUTOGUI_KEYS = [
    "\t",
    "\n",
    "\r",
    " ",
    "!",
    '"',
    "#",
    "$",
    "%",
    "&",
    "'",
    "(",
    ")",
    "*",
    "+",
    ",",
    "-",
    ".",
    "/",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    ":",
    ";",
    "<",
    "=",
    ">",
    "?",
    "@",
    "[",
    "\\",
    "]",
    "^",
    "_",
    "`",
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "{",
    "|",
    "}",
    "~",
    "accept",
    "add",
    "alt",
    "altleft",
    "altright",
    "apps",
    "backspace",
    "browserback",
    "browserfavorites",
    "browserforward",
    "browserhome",
    "browserrefresh",
    "browsersearch",
    "browserstop",
    "capslock",
    "clear",
    "convert",
    "ctrl",
    "ctrlleft",
    "ctrlright",
    "decimal",
    "del",
    "delete",
    "divide",
    "down",
    "end",
    "enter",
    "esc",
    "escape",
    "execute",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
    "f13",
    "f14",
    "f15",
    "f16",
    "f17",
    "f18",
    "f19",
    "f20",
    "f21",
    "f22",
    "f23",
    "f24",
    "final",
    "fn",
    "hanguel",
    "hangul",
    "hanja",
    "help",
    "home",
    "insert",
    "junja",
    "kana",
    "kanji",
    "launchapp1",
    "launchapp2",
    "launchmail",
    "launchmediaselect",
    "left",
    "modechange",
    "multiply",
    "nexttrack",
    "nonconvert",
    "num0",
    "num1",
    "num2",
    "num3",
    "num4",
    "num5",
    "num6",
    "num7",
    "num8",
    "num9",
    "numlock",
    "pagedown",
    "pageup",
    "pause",
    "pgdn",
    "pgup",
    "playpause",
    "prevtrack",
    "print",
    "printscreen",
    "prntscrn",
    "prtsc",
    "prtscr",
    "return",
    "right",
    "scrolllock",
    "select",
    "separator",
    "shift",
    "shiftleft",
    "shiftright",
    "sleep",
    "space",
    "stop",
    "subtract",
    "tab",
    "up",
    "volumedown",
    "volumemute",
    "volumeup",
    "win",
    "winleft",
    "winright",
    "yen",
    "command",
    "option",
    "optionleft",
    "optionright",
]


class ActionExecutor:
    """
    Executes actions like mouse clicks and keyboard inputs based on action specifications.
    Handles parameter validation, type conversion for substituted variables, and
    calculating target coordinates for various targeting relations, including those
    derived from Gemini AI analysis.
    """

    def __init__(self, config_manager_instance: Any):  # Type hint for ConfigManager if it's imported
        """
        Initializes the ActionExecutor.

        Args:
            config_manager_instance: An instance of ConfigManager, used to resolve
                                     region configurations for coordinate calculations.
        """
        self.config_manager = config_manager_instance
        pyautogui.FAILSAFE = True  # Move mouse to top-left (0,0) to abort PyAutoGUI
        # pyautogui.PAUSE = 0.0 # Global pause, prefer explicit pauses per action via pyautogui_pause_before
        logger.info(f"ActionExecutor initialized. PyAutoGUI FAILSAFE is ON. Default PAUSE: {pyautogui.PAUSE}s.")

    def _validate_and_convert_coord_param(self, value: Any, param_name: str, action_type_for_log: str, rule_name_for_log: str) -> Optional[int]:
        """
        Validates and converts a coordinate parameter to an integer.
        Logs errors and returns None on failure.
        """
        log_prefix = f"R '{rule_name_for_log}', A '{action_type_for_log}', Prm '{param_name}'"
        if isinstance(value, (int, float)):
            val_int = int(value)
            logger.debug(f"{log_prefix}: Numeric value '{value}' converted to int {val_int}.")
            return val_int
        if isinstance(value, str):
            try:
                # Try float first to handle "10.0", then int
                val_int = int(float(value.strip()))
                logger.debug(f"{log_prefix}: String value '{value}' converted to int {val_int}.")
                return val_int
            except ValueError:
                logger.error(f"{log_prefix}: Invalid numeric string value '{value}'. Cannot convert to integer.")
                return None
        logger.error(f"{log_prefix}: Unexpected type '{type(value).__name__}' (value: {value}). Expected number or numeric string.")
        return None

    def _validate_and_convert_float_param(
        self, value: Any, param_name: str, action_type_for_log: str, rule_name_for_log: str, default_val: float, min_val: Optional[float] = None, max_val: Optional[float] = None
    ) -> float:
        """
        Validates and converts a parameter to float, with optional bounds.
        Logs warnings and returns default_val on failure or if out of bounds.
        """
        log_prefix = f"R '{rule_name_for_log}', A '{action_type_for_log}', Prm '{param_name}'"
        val_float: float

        if isinstance(value, (int, float)):
            val_float = float(value)
        elif isinstance(value, str):
            try:
                val_float = float(value.strip())
            except ValueError:
                logger.warning(f"{log_prefix}: Invalid float string value '{value}'. Using default {default_val}.")
                return default_val
        else:
            logger.warning(f"{log_prefix}: Unexpected type '{type(value).__name__}'. Using default {default_val}.")
            return default_val

        if min_val is not None and val_float < min_val:
            logger.warning(f"{log_prefix}: Value {val_float} is less than minimum {min_val}. Using default {default_val}.")
            return default_val
        if max_val is not None and val_float > max_val:
            logger.warning(f"{log_prefix}: Value {val_float} is greater than maximum {max_val}. Using default {default_val}.")
            return default_val

        logger.debug(f"{log_prefix}: Validated to float {val_float}.")
        return val_float

    def _get_target_coords(self, action_spec: Dict[str, Any], context: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        """
        Calculates target (x, y) screen coordinates based on action_spec and context.
        Handles various target_relation types, including those using Gemini-derived data.

        Args:
            action_spec: The specification for the action, containing targeting parameters.
            context: The context of the rule evaluation, containing `condition_region`,
                     `last_match_info`, and `variables` (which may hold Gemini data).

        Returns:
            A tuple (x, y) of absolute screen coordinates, or None if coords cannot be determined.
        """
        target_relation = action_spec.get("target_relation")
        action_type_for_log = action_spec.get("type", "unknown_action")
        rule_name_for_log = context.get("rule_name", "UnknownRule")
        log_prefix_coord = f"R '{rule_name_for_log}', A '{action_type_for_log}', TargetCoord"

        x_val: Optional[int] = None
        y_val: Optional[int] = None

        if target_relation == "absolute":
            x_val = self._validate_and_convert_coord_param(action_spec.get("x"), "x_abs", action_type_for_log, rule_name_for_log)
            y_val = self._validate_and_convert_coord_param(action_spec.get("y"), "y_abs", action_type_for_log, rule_name_for_log)
            if x_val is not None and y_val is not None:
                logger.info(f"{log_prefix_coord}: Absolute target: ({x_val}, {y_val}).")
                return x_val, y_val
            logger.error(f"{log_prefix_coord}: Missing or invalid 'x' or 'y' for absolute targeting.")
            return None

        # For region-based, template-based, or Gemini-based targeting
        base_region_x, base_region_y = 0, 0
        target_region_name_for_relative: Optional[str] = None  # For relative_to_region or center_of_region

        if target_relation in ["center_of_region", "relative_to_region"]:
            target_region_name_for_relative = action_spec.get("target_region") or context.get("condition_region")
            if not target_region_name_for_relative:
                logger.error(f"{log_prefix_coord}: No target_region specified and no condition_region in context for '{target_relation}'.")
                return None
            region_config = self.config_manager.get_region_config(target_region_name_for_relative)
            if not region_config:
                logger.error(f"{log_prefix_coord}: Target region '{target_region_name_for_relative}' config not found for relation '{target_relation}'.")
                return None
            base_region_x = region_config.get("x", 0)
            base_region_y = region_config.get("y", 0)
            region_w = region_config.get("width", 0)
            region_h = region_config.get("height", 0)

            if target_relation == "center_of_region":
                x_val, y_val = base_region_x + region_w // 2, base_region_y + region_h // 2
                logger.info(f"{log_prefix_coord}: Center of region '{target_region_name_for_relative}' ({base_region_x},{base_region_y} {region_w}x{region_h}): ({x_val}, {y_val}).")
                return x_val, y_val
            elif target_relation == "relative_to_region":
                rel_x = self._validate_and_convert_coord_param(action_spec.get("x"), "x_rel", action_type_for_log, rule_name_for_log)
                rel_y = self._validate_and_convert_coord_param(action_spec.get("y"), "y_rel", action_type_for_log, rule_name_for_log)
                if rel_x is not None and rel_y is not None:
                    x_val, y_val = base_region_x + rel_x, base_region_y + rel_y
                    logger.info(f"{log_prefix_coord}: Relative to region '{target_region_name_for_relative}' (base {base_region_x},{base_region_y}; offset {rel_x},{rel_y}): ({x_val}, {y_val}).")
                    return x_val, y_val
                logger.error(f"{log_prefix_coord}: Missing or invalid relative 'x' or 'y' for region-relative targeting.")
                return None

        elif target_relation == "center_of_last_match":
            last_match_info = context.get("last_match_info", {})
            if not last_match_info.get("found"):
                logger.warning(f"{log_prefix_coord}: 'center_of_last_match' requested, but no template match found in context.")
                return None

            match_region_name = last_match_info.get("matched_region_name")
            match_region_config = self.config_manager.get_region_config(match_region_name) if match_region_name else None
            if not match_region_config:
                logger.error(f"{log_prefix_coord}: Region '{match_region_name}' (where template matched) not found in profile config.")
                return None

            base_region_x = match_region_config.get("x", 0)
            base_region_y = match_region_config.get("y", 0)
            match_rel_x = last_match_info.get("location_x", 0)
            match_rel_y = last_match_info.get("location_y", 0)
            match_w = last_match_info.get("width", 0)
            match_h = last_match_info.get("height", 0)
            x_val = base_region_x + match_rel_x + match_w // 2
            y_val = base_region_y + match_rel_y + match_h // 2
            logger.info(f"{log_prefix_coord}: Center of last template match in region '{match_region_name}': ({x_val}, {y_val}).")
            return x_val, y_val

        elif target_relation in ["center_of_gemini_element", "top_left_of_gemini_element"]:
            gemini_var_name = action_spec.get("gemini_element_variable")
            if not gemini_var_name:
                logger.error(f"{log_prefix_coord}: 'gemini_element_variable' not specified for '{target_relation}'.")
                return None

            wrapped_element_data = context.get("variables", {}).get(gemini_var_name)
            if not isinstance(wrapped_element_data, dict) or "value" not in wrapped_element_data or "_source_region_for_capture_" not in wrapped_element_data:
                logger.error(
                    f"{log_prefix_coord}: Variable '{gemini_var_name}' for Gemini element is missing, not a dict, or missing 'value'/'_source_region_for_capture_'. Data: {wrapped_element_data}"
                )
                return None

            element_value = wrapped_element_data["value"]
            source_region_name = wrapped_element_data["_source_region_for_capture_"]

            if not isinstance(element_value, dict) or not element_value.get("found") or not isinstance(element_value.get("box"), list) or len(element_value["box"]) != 4:
                logger.error(f"{log_prefix_coord}: Gemini element data in var '{gemini_var_name}' is malformed, 'found' is false, or 'box' is invalid. Value: {element_value}")
                return None

            source_region_config = self.config_manager.get_region_config(source_region_name)
            if not source_region_config:
                logger.error(f"{log_prefix_coord}: Source region '{source_region_name}' for Gemini capture not found in profile config.")
                return None

            base_region_x = source_region_config.get("x", 0)
            base_region_y = source_region_config.get("y", 0)

            # Box is [rel_x, rel_y, width, height] relative to the source_region_config
            box_coords = element_value["box"]
            try:
                rel_el_x, rel_el_y, el_w, el_h = [int(c) for c in box_coords]
            except (ValueError, TypeError):
                logger.error(f"{log_prefix_coord}: Gemini element 'box' coordinates are not all numbers: {box_coords}")
                return None

            if target_relation == "center_of_gemini_element":
                x_val = base_region_x + rel_el_x + el_w // 2
                y_val = base_region_y + rel_el_y + el_h // 2
            elif target_relation == "top_left_of_gemini_element":
                x_val = base_region_x + rel_el_x
                y_val = base_region_y + rel_el_y

            if x_val is not None and y_val is not None:
                logger.info(
                    f"{log_prefix_coord}: Target '{target_relation}' for element from var '{gemini_var_name}' (described as '{element_value.get('element_label','N/A')}') in source region '{source_region_name}' (base {base_region_x},{base_region_y}; relative box {box_coords}): ({x_val}, {y_val})."
                )
                return x_val, y_val
            # Should not be reached if logic is correct above
            logger.error(f"{log_prefix_coord}: Unexpectedly failed to calculate coordinates for '{target_relation}'.")
            return None

        logger.error(f"{log_prefix_coord}: Unknown or unsupported target_relation '{target_relation}'.")
        return None

    def execute_action(self, full_action_spec: Dict[str, Any]):
        """
        Executes a single action based on its specification and context.

        Args:
            full_action_spec: A dictionary containing the action 'type', its parameters,
                              and a 'context' sub-dictionary (with 'rule_name', 'variables', etc.).
        """
        action_type = full_action_spec.get("type")
        context = full_action_spec.get("context", {})  # Ensure context always exists
        rule_name_for_log = context.get("rule_name", "UnknownRule_or_TaskStep")
        log_prefix_action = f"R '{rule_name_for_log}', Action '{action_type}'"

        pause_before_str = str(full_action_spec.get("pyautogui_pause_before", "0.0"))
        pause_duration = self._validate_and_convert_float_param(pause_before_str, "pyautogui_pause_before", str(action_type), rule_name_for_log, 0.0, min_val=0.0)

        if pause_duration > 0:
            logger.debug(f"{log_prefix_action}: Pausing for {pause_duration:.3f}s before execution.")
            try:
                # Using time.sleep as pyautogui.sleep might be just an alias to time.sleep
                # and this makes the dependency explicit if we ever change pyautogui's PAUSE.
                time.sleep(pause_duration)
            except Exception as e_sleep:  # Should be rare for time.sleep
                logger.warning(f"{log_prefix_action}: Error during time.sleep({pause_duration}): {e_sleep}. Continuing action.")

        # Log the action spec without the potentially large context for brevity
        action_params_for_log = {k: v for k, v in full_action_spec.items() if k != "context"}
        logger.info(f"{log_prefix_action}: Executing. Params: {action_params_for_log}")

        try:
            if action_type == "click":
                coords = self._get_target_coords(full_action_spec, context)
                if coords:
                    x_coord, y_coord = coords
                    button = str(full_action_spec.get("button", "left")).lower()
                    if button not in ["left", "middle", "right", "primary", "secondary"]:  # pyautogui valid buttons
                        logger.warning(f"{log_prefix_action}: Invalid click button '{button}'. Defaulting to 'left'.")
                        button = "left"

                    num_clicks_str = str(full_action_spec.get("clicks", "1"))
                    num_clicks = self._validate_and_convert_coord_param(num_clicks_str, "clicks", str(action_type), rule_name_for_log)
                    if num_clicks is None or num_clicks <= 0:
                        logger.warning(f"{log_prefix_action}: Invalid 'clicks' value '{num_clicks_str}'. Defaulting to 1.")
                        num_clicks = 1

                    interval_str = str(full_action_spec.get("interval", "0.0"))  # Interval between clicks
                    interval_val = self._validate_and_convert_float_param(interval_str, "interval", str(action_type), rule_name_for_log, 0.0, min_val=0.0)

                    logger.info(f"{log_prefix_action}: Simulating {button} click ({num_clicks}x, interval {interval_val:.3f}s) at ({x_coord},{y_coord}).")
                    pyautogui.click(x=x_coord, y=y_coord, clicks=num_clicks, interval=interval_val, button=button)
                else:
                    logger.error(f"{log_prefix_action}: Could not determine target coordinates. Action skipped.")

            elif action_type == "type_text":
                text_to_type = str(full_action_spec.get("text", ""))  # Ensure string
                interval_str = str(full_action_spec.get("interval", "0.0"))  # Interval between key presses
                interval_val = self._validate_and_convert_float_param(interval_str, "interval", str(action_type), rule_name_for_log, 0.0, min_val=0.0)

                if text_to_type:  # Only type if there's text
                    text_snippet = text_to_type[:50].replace("\n", "\\n").replace("\r", "\\r") + ("..." if len(text_to_type) > 50 else "")
                    logger.info(f"{log_prefix_action}: Typing text (len: {len(text_to_type)}): '{text_snippet}' with interval {interval_val:.3f}s.")
                    pyautogui.typewrite(text_to_type, interval=interval_val)
                else:
                    logger.info(f"{log_prefix_action}: No text provided to type (text parameter is empty or missing). Action effectively skipped.")

            elif action_type == "press_key":
                key_param_value = full_action_spec.get("key")
                keys_to_press_list: List[str] = []

                if isinstance(key_param_value, str):
                    # If it's a comma-separated string, treat as hotkey parts
                    keys_to_press_list = [k.strip().lower() for k in key_param_value.split(",") if k.strip()]
                elif isinstance(key_param_value, list):
                    keys_to_press_list = [str(k).strip().lower() for k in key_param_value if str(k).strip()]

                if not keys_to_press_list:
                    logger.warning(f"{log_prefix_action}: No valid key(s) provided in 'key' parameter: '{key_param_value}'. Action skipped.")
                    return

                # Validate keys against PyAutoGUI's known keys for safety
                validated_keys = []
                for k_to_check in keys_to_press_list:
                    if k_to_check in VALID_PYAUTOGUI_KEYS:
                        validated_keys.append(k_to_check)
                    else:
                        logger.warning(f"{log_prefix_action}: Invalid or unsupported key '{k_to_check}' specified. It will be ignored.")

                if not validated_keys:
                    logger.error(f"{log_prefix_action}: All specified keys were invalid. Action skipped.")
                    return

                if len(validated_keys) == 1:
                    logger.info(f"{log_prefix_action}: Pressing single key: '{validated_keys[0]}'.")
                    pyautogui.press(validated_keys[0])
                else:  # Multiple keys, treat as hotkey
                    logger.info(f"{log_prefix_action}: Pressing hotkey sequence: {validated_keys}.")
                    pyautogui.hotkey(*validated_keys)

            elif action_type == "log_message":
                message = str(full_action_spec.get("message", "Default log message from rule action."))
                level_str = str(full_action_spec.get("level", "INFO")).upper()
                log_level = getattr(logging, level_str, logging.INFO)  # Default to INFO if invalid level

                # Use a specific logger for rule-generated log messages for easier filtering if needed
                rule_event_logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.RuleEvents")
                rule_event_logger.log(log_level, f"R '{rule_name_for_log}': {message}")
                # Also log to main action executor logger for context
                logger.info(f"{log_prefix_action}: Custom log message written with level {level_str}.")

            # Example for a future "WAIT_SHORT" action that might be suggested by GeminiDecisionModule
            # elif action_type == "wait":
            #     duration_str = str(full_action_spec.get("duration_seconds", "1.0"))
            #     duration_val = self._validate_and_convert_float_param(
            #         duration_str, "duration_seconds", str(action_type), rule_name_for_log, 1.0, min_val=0.01, max_val=60.0 # Max wait 1 min
            #     )
            #     logger.info(f"{log_prefix_action}: Waiting for {duration_val:.2f} seconds.")
            #     time.sleep(duration_val)

            else:
                logger.error(f"{log_prefix_action}: Unknown action type '{action_type}'. Action skipped.")

        except pyautogui.FailSafeException:
            # This exception is raised if the mouse is moved to a screen corner (0,0 by default)
            logger.critical(f"{log_prefix_action}: PyAutoGUI FAILSAFE triggered! Mouse was moved to a corner, aborting action.")
            # Depending on application design, this might warrant stopping the bot. Re-raise for now.
            raise
        except Exception as e:
            logger.exception(f"{log_prefix_action}: Error during execution. Error: {e}")
            # Optionally, re-raise or handle more specifically if certain errors are recoverable
            # For now, log and absorb to allow bot to continue next cycle, unless it's FailSafe.
