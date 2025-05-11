import logging
import sys 
from pathlib import Path 

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

logger = logging.getLogger(__name__)

class ActionExecutor:
    def __init__(self):
        logger.info("ActionExecutor initialized.")
        if not PYAUTOGUI_AVAILABLE:
            logger.error("PyAutoGUI library not found. Mouse/Keyboard actions will NOT work.")
        else:
            logger.debug("PyAutoGUI library successfully imported.")
        self.pyautogui_available = PYAUTOGUI_AVAILABLE

    def _calculate_target_coordinates(self, action_spec: dict, 
                                      analysis_results_for_triggering_region: dict = None, 
                                      target_region_info: dict = None) -> tuple[int, int] | None:
        log_prefix_coord = f"CoordCalc for action type '{action_spec.get('type')}':"
        logger.debug(f"{log_prefix_coord} Spec: {action_spec}, TrigAnalysis: {analysis_results_for_triggering_region is not None}, TargetRegion: {target_region_info.get('name') if target_region_info else 'None'}")
        abs_x = action_spec.get("x")
        abs_y = action_spec.get("y")
        if abs_x is not None and abs_y is not None:
            logger.debug(f"{log_prefix_coord} Using absolute coordinates from action_spec: ({abs_x},{abs_y})")
            return int(abs_x), int(abs_y)
        target_relation = action_spec.get("target_relation")
        x_offset = int(action_spec.get("x_offset", 0))
        y_offset = int(action_spec.get("y_offset", 0))
        base_screen_x, base_screen_y = None, None 
        element_width, element_height = 0, 0     
        if target_relation == "center_of_region" or target_relation == "offset_from_region_tl":
            if target_region_info:
                base_screen_x = target_region_info.get("x", 0)
                base_screen_y = target_region_info.get("y", 0)
                element_width = target_region_info.get("width", 0)
                element_height = target_region_info.get("height", 0)
                logger.debug(f"{log_prefix_coord} Base is target_region '{target_region_info.get('name')}': screen_x={base_screen_x}, screen_y={base_screen_y}, w={element_width}, h={element_height}")
            else:
                logger.warning(f"{log_prefix_coord} Relation to region specified, but target_region_info is missing.")
                return None
        elif target_relation == "center_of_last_match" or target_relation == "offset_from_last_match_tl":
            if analysis_results_for_triggering_region:
                match_info = analysis_results_for_triggering_region.get('_last_template_match_info')
                if match_info:
                    if target_region_info: # Match coords are relative to the region they were found in
                        match_rel_x = match_info.get("x", 0)
                        match_rel_y = match_info.get("y", 0)
                        base_screen_x = target_region_info.get("x", 0) + match_rel_x 
                        base_screen_y = target_region_info.get("y", 0) + match_rel_y 
                        element_width = match_info.get("width", 0)
                        element_height = match_info.get("height", 0)
                        logger.debug(f"{log_prefix_coord} Base is last_match: screen_x={base_screen_x}, screen_y={base_screen_y}, w={element_width}, h={element_height} (found in region '{target_region_info.get('name')}')")
                    else:
                        logger.warning(f"{log_prefix_coord} Relation to last_match needs target_region_info to resolve match coordinates to screen.")
                        return None
                else:
                    logger.warning(f"{log_prefix_coord} Relation to last_match, but no '_last_template_match_info' found.")
                    return None
            else:
                logger.warning(f"{log_prefix_coord} Relation to last_match, but no analysis_results_for_triggering_region.")
                return None
        else: 
            logger.warning(f"{log_prefix_coord} No absolute coords and no valid 'target_relation' in action_spec: {action_spec}.")
            return None
        final_x, final_y = None, None
        if "center_of_" in (target_relation or ""):
            final_x = base_screen_x + (element_width // 2) + x_offset
            final_y = base_screen_y + (element_height // 2) + y_offset
        elif "offset_from_" in (target_relation or ""): 
            final_x = base_screen_x + x_offset
            final_y = base_screen_y + y_offset
        if final_x is not None and final_y is not None:
            logger.debug(f"{log_prefix_coord} Calculated target screen coordinates: ({final_x},{final_y}) using relation '{target_relation}' and offset ({x_offset},{y_offset})")
            return int(final_x), int(final_y)
        else:
            logger.error(f"{log_prefix_coord} Failed to derive final coordinates. Relation: {target_relation}")
            return None

    def execute_action(self, action_spec: dict, 
                       analysis_results_for_triggering_region: dict = None, 
                       target_region_info: dict = None):
        action_type = action_spec.get("type")
        region_name_for_log = target_region_info.get("name", "N/A") if target_region_info else "N/A"
        log_prefix = f"Action '{action_type}' for target_region '{region_name_for_log}':"
        logger.info(f"{log_prefix} Attempting with spec: {action_spec}")
        if not self.pyautogui_available:
            logger.error(f"{log_prefix} Cannot execute. PyAutoGUI library is not available.")
            return
        try:
            if action_type == "click":
                coords = self._calculate_target_coordinates(action_spec, analysis_results_for_triggering_region, target_region_info)
                if coords:
                    click_x, click_y = coords
                    button = action_spec.get("button", "left").lower()
                    num_clicks = int(action_spec.get("clicks", 1))
                    interval = float(action_spec.get("interval", 0.1))
                    pyautogui.PAUSE = float(action_spec.get("pyautogui_pause_before", 0.05)) 
                    logger.info(f"{log_prefix} Simulating {num_clicks} {button} click(s) at screen ({click_x},{click_y}) with interval {interval}s.")
                    pyautogui.click(x=click_x, y=click_y, clicks=num_clicks, interval=interval, button=button)
                else:
                    logger.error(f"{log_prefix} Could not determine target coordinates for click. Action spec: {action_spec}")
            elif action_type == "type_text":
                text_to_type = action_spec.get("text")
                if text_to_type is not None: 
                    interval = float(action_spec.get("interval", 0.01)) 
                    pyautogui.PAUSE = float(action_spec.get("pyautogui_pause_before", 0.05))
                    logger.info(f"{log_prefix} Simulating typing text: '{text_to_type[:50]}...' with interval {interval}s.")
                    pyautogui.typewrite(text_to_type, interval=interval)
                else:
                    logger.error(f"{log_prefix} 'type_text' action missing 'text' in spec: {action_spec}")
            elif action_type == "press_key":
                key_names = action_spec.get("key")
                if key_names:
                    pyautogui.PAUSE = float(action_spec.get("pyautogui_pause_before", 0.05))
                    if isinstance(key_names, list): 
                        logger.info(f"{log_prefix} Simulating hotkey press: {key_names}")
                        pyautogui.hotkey(*key_names)
                    else: 
                        logger.info(f"{log_prefix} Simulating single key press: '{key_names}'")
                        pyautogui.press(key_names)
                else:
                    logger.error(f"{log_prefix} 'press_key' action missing 'key' in spec: {action_spec}")
            elif action_type == "log_message":
                message = action_spec.get("message", "Default log action message.")
                logger.info(f"[ACTION_LOG from rule for region '{region_name_for_log}'] {message}")
            else:
                logger.warning(f"{log_prefix} Unknown or unsupported action type in spec: {action_spec}")
        except Exception as e:
            logger.error(f"{log_prefix} Error during execution: {e}", exc_info=True)

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent 
    if str(project_src_dir) not in sys.path:
        sys.path.insert(0, str(project_src_dir))
    from py_pixel_bot.core.config_manager import load_environment_variables
    load_environment_variables() 
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging() 
    test_logger = logging.getLogger(__name__ + "_test")
    test_logger.info("--- ActionExecutor Test Start (with refined coordinate calculation) ---")
    executor = ActionExecutor()
    if not executor.pyautogui_available:
        test_logger.critical("PyAutoGUI not available. Cannot run most action tests.")
    else:
        target_region_for_action = {"name": "action_target_area", "x": 500, "y": 600, "width": 100, "height": 50}
        analysis_data_from_triggering_rule = {"_last_template_match_info": {"x": 10, "y": 15, "width": 20, "height": 10, "confidence": 0.9}}
        test_logger.info(f"--- Testing _calculate_target_coordinates with target_region_for_action: {target_region_for_action.get('name')} ---")
        action_spec1 = {"type": "click", "x": 50, "y": 75}; coords1 = executor._calculate_target_coordinates(action_spec1)
        test_logger.info(f"Test 1 (Absolute): Coords={coords1} (Expected: (50,75))"); assert coords1 == (50,75)
        action_spec2 = {"type": "click", "target_relation": "center_of_region"}; coords2 = executor._calculate_target_coordinates(action_spec2, target_region_info=target_region_for_action)
        test_logger.info(f"Test 2 (Center of Region): Coords={coords2} (Expected: (550,625))"); assert coords2 == (550,625)
        action_spec4 = {"type": "click", "target_relation": "center_of_last_match"}; coords4 = executor._calculate_target_coordinates(action_spec4, analysis_results_for_triggering_region=analysis_data_from_triggering_rule, target_region_info=target_region_for_action)
        test_logger.info(f"Test 4 (Center of Last Match): Coords={coords4} (Expected: (520,620))"); assert coords4 == (520,620)
        test_logger.info("Coordinate calculation tests completed.")
        test_logger.info("--- Skipping actual PyAutoGUI actions in this consolidated view to prevent unintended input during review. ---")
    test_logger.info("--- ActionExecutor Test End ---")