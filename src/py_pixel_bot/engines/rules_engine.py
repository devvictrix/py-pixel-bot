import logging
import os 
from pathlib import Path 

logger = logging.getLogger(__name__)

class RulesEngine:
    def __init__(self, action_executor, config_manager, analysis_engine):
        self.action_executor = action_executor
        self.config_manager = config_manager
        self.analysis_engine = analysis_engine
        self.loaded_templates = {} 
        logger.info("RulesEngine initialized with AnalysisEngine.")

    def _get_region_spec_by_name(self, region_name: str) -> dict | None:
        if not self.config_manager:
            logger.error("_get_region_spec_by_name: ConfigManager not available.")
            return None
        for region_spec in self.config_manager.get_regions():
            if region_spec.get("name") == region_name:
                return region_spec
        logger.warning(f"Region specification not found for name: '{region_name}'")
        return None

    def _load_template_image_for_rule(self, template_filename: str):
        if template_filename in self.loaded_templates:
            if self.loaded_templates[template_filename] is None:
                 logger.debug(f"Template '{template_filename}' previously failed to load, returning None from cache.")
                 return None
            logger.debug(f"Returning cached template: '{template_filename}'")
            return self.loaded_templates[template_filename]

        if not self.config_manager or not hasattr(self.config_manager, 'profiles_dir'):
            logger.error("Cannot load template: ConfigManager or its profiles_dir not available.")
            return None
        if not self.analysis_engine.imaging_libs_available: # cv2 needed for imread
            logger.error("Cannot load template: OpenCV (cv2) not available in AnalysisEngine.")
            return None
        
        # ConfigManager.profiles_dir should be absolute path to 'profiles' folder
        template_full_path = self.config_manager.profiles_dir / "templates" / template_filename

        logger.debug(f"Attempting to load template image from: {template_full_path}")
        try:
            import cv2 
            template_image_bgr = cv2.imread(str(template_full_path)) 
            if template_image_bgr is not None:
                logger.info(f"Successfully loaded template image: '{template_filename}' (shape: {template_image_bgr.shape}) from {template_full_path}")
                self.loaded_templates[template_filename] = template_image_bgr
                return template_image_bgr
            else:
                logger.error(f"Failed to load template image (cv2.imread returned None): {template_full_path}")
                self.loaded_templates[template_filename] = None 
                return None
        except Exception as e:
            logger.error(f"Error loading template image '{template_full_path}': {e}", exc_info=True)
            self.loaded_templates[template_filename] = None
            return None

    def _check_condition(self, condition_spec: dict, 
                         pre_calculated_analysis_data: dict, 
                         captured_image_for_region, 
                         rule_name_for_log: str) -> bool:
        condition_type = condition_spec.get("type")
        if not condition_type:
            logger.warning(f"Rule '{rule_name_for_log}': Condition has no type: {condition_spec}")
            return False
        logger.debug(f"Rule '{rule_name_for_log}': Checking condition type '{condition_type}' with spec: {condition_spec}")

        if condition_type == "pixel_color":
            rel_x = condition_spec.get("relative_x")
            rel_y = condition_spec.get("relative_y")
            expected_bgr_list = condition_spec.get("expected_bgr")
            if rel_x is None or rel_y is None or expected_bgr_list is None:
                logger.warning(f"Rule '{rule_name_for_log}': 'pixel_color' missing params. Spec: {condition_spec}")
                return False
            if captured_image_for_region is None:
                logger.warning(f"Rule '{rule_name_for_log}': 'pixel_color' check, no captured image.")
                return False
            actual_bgr_tuple = self.analysis_engine.analyze_pixel_color(captured_image_for_region, rel_x, rel_y)
            expected_bgr_tuple = tuple(expected_bgr_list) 
            if actual_bgr_tuple is not None and actual_bgr_tuple == expected_bgr_tuple:
                logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' at ({rel_x},{rel_y}) MET. Expected {expected_bgr_tuple}, Got {actual_bgr_tuple}")
                return True
            logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' at ({rel_x},{rel_y}) NOT MET. Expected {expected_bgr_tuple}, Got {actual_bgr_tuple}")
            return False
        elif condition_type == "average_color_is":
            expected_bgr_list = condition_spec.get("expected_bgr")
            tolerance = int(condition_spec.get("tolerance", 0))
            if expected_bgr_list is None:
                logger.warning(f"Rule '{rule_name_for_log}': 'average_color_is' missing 'expected_bgr'.")
                return False
            actual_avg_bgr_tuple = pre_calculated_analysis_data.get("average_color") 
            expected_bgr_tuple = tuple(expected_bgr_list)
            if actual_avg_bgr_tuple is not None:
                match = all(expected_bgr_tuple[i] - tolerance <= actual_avg_bgr_tuple[i] <= expected_bgr_tuple[i] + tolerance for i in range(3))
                if match:
                    logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' MET. Expected ~{expected_bgr_tuple}, Got {actual_avg_bgr_tuple}")
                    return True
            logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' NOT MET. Expected ~{expected_bgr_tuple}, Got {actual_avg_bgr_tuple}")
            return False
        elif condition_type == "template_match_found":
            template_filename = condition_spec.get("template_filename")
            min_confidence = float(condition_spec.get("min_confidence", 0.8))
            if not template_filename:
                logger.warning(f"Rule '{rule_name_for_log}': 'template_match_found' missing 'template_filename'.")
                return False
            if captured_image_for_region is None:
                logger.warning(f"Rule '{rule_name_for_log}': 'template_match_found' check, no captured image.")
                return False
            template_image_data = self._load_template_image_for_rule(template_filename)
            if template_image_data is None:
                logger.error(f"Rule '{rule_name_for_log}': Failed to load template '{template_filename}'. Cond False.")
                return False
            matches_list = self.analysis_engine.match_template(captured_image_for_region, template_image_data, threshold=min_confidence)
            if matches_list:
                logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' for '{template_filename}' MET. Found {len(matches_list)}.")
                if pre_calculated_analysis_data is not None:
                    pre_calculated_analysis_data['_last_template_match_info'] = matches_list[0]
                return True
            logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' for '{template_filename}' NOT MET (thresh: {min_confidence}).")
            return False
        elif condition_type == "ocr_contains_text":
            text_to_find = condition_spec.get("text_to_find")
            case_sensitive = condition_spec.get("case_sensitive", False)
            if text_to_find is None:
                logger.warning(f"Rule '{rule_name_for_log}': 'ocr_contains_text' missing 'text_to_find'.")
                return False
            extracted_text = pre_calculated_analysis_data.get("ocr_text", "") 
            search_text = text_to_find if case_sensitive else text_to_find.lower()
            text_corpus = extracted_text if case_sensitive else extracted_text.lower()
            if search_text and search_text in text_corpus:
                logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' - text '{text_to_find}' FOUND.")
                return True
            logger.debug(f"Rule '{rule_name_for_log}': Cond '{condition_type}' - text '{text_to_find}' NOT FOUND.")
            return False
        elif condition_type == "always_true":
            logger.debug(f"Rule '{rule_name_for_log}': Condition 'always_true' MET for testing.")
            return True
        logger.warning(f"Rule '{rule_name_for_log}': Unknown condition type '{condition_type}'. Evaluated to False.")
        return False

    def evaluate_rules(self, iteration_analysis_results_with_images: dict):
        rules = self.config_manager.get_rules()
        if not rules:
            logger.debug("No rules to evaluate.")
            return
        logger.debug(f"Starting evaluation of {len(rules)} rules.")
        for rule_spec in rules:
            rule_name = rule_spec.get("name", "Unnamed Rule")
            target_region_name_for_condition = rule_spec.get("region")
            if not target_region_name_for_condition:
                logger.warning(f"Rule '{rule_name}' has no target 'region' for condition. Skipping.")
                continue
            region_data_packet = iteration_analysis_results_with_images.get(target_region_name_for_condition)
            condition_met = False
            pre_calculated_data_for_action = {} # Initialize for action executor context

            if region_data_packet is None:
                logger.debug(f"No data for target region '{target_region_name_for_condition}' for rule '{rule_name}'. Cond False.")
            elif region_data_packet.get("capture_error", False):
                logger.debug(f"Capture error for region '{target_region_name_for_condition}' for rule '{rule_name}'. Cond False.")
            else:
                captured_image = region_data_packet.get("captured_image")
                pre_calculated_data_for_action = {k: v for k, v in region_data_packet.items() if k != "captured_image"}
                condition_met = self._check_condition(
                    rule_spec.get("condition", {}), 
                    pre_calculated_data_for_action,
                    captured_image,
                    rule_name
                )
            
            if condition_met:
                logger.info(f"Rule '{rule_name}' (Region: '{target_region_name_for_condition}') condition MET. Triggering action.")
                action_spec = rule_spec.get("action", {})
                action_target_region_name = action_spec.get("target_region", target_region_name_for_condition)
                action_target_region_spec = self._get_region_spec_by_name(action_target_region_name)
                self.action_executor.execute_action(
                    action_spec, 
                    analysis_results_for_triggering_region=pre_calculated_data_for_action, # This now includes _last_template_match_info if set
                    target_region_info=action_target_region_spec
                ) 
        logger.debug("Finished evaluating all rules.")

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent 
    if str(project_src_dir) not in sys.path:
        sys.path.insert(0, str(project_src_dir))
    from py_pixel_bot.core.config_manager import load_environment_variables, ConfigManager
    from py_pixel_bot.core.logging_setup import setup_logging
    from py_pixel_bot.engines.analysis_engine import AnalysisEngine 
    load_environment_variables()
    setup_logging()
    test_logger_re = logging.getLogger(__name__ + "_test")
    class MockActionExecutor:
        def execute_action(self, action_spec, analysis_results_for_triggering_region=None, target_region_info=None):
            region_name_log = target_region_info.get('name', 'N/A') if target_region_info else "N/A_RegionInfo"
            match_info_log = ""
            if analysis_results_for_triggering_region and '_last_template_match_info' in analysis_results_for_triggering_region:
                match_info_log = f" (MatchInfo: {analysis_results_for_triggering_region['_last_template_match_info']})"
            test_logger_re.info(f"-----> [MockActionExecutor] EXECUTED Action: '{action_spec.get('type')}' for target region '{region_name_log}'.{match_info_log}")
    class MockConfigManager:
        def __init__(self, profile_data, project_root_path): # Added project_root_path
            self.profile_data = profile_data
            self.project_root_dir = project_root_path # Needed for profiles_dir
            self.profiles_dir = self.project_root_dir / "profiles"
            test_logger_re.debug(f"MockConfigManager initialized. Profiles dir: {self.profiles_dir}")
        def get_rules(self): return self.profile_data.get("rules", [])
        def get_regions(self): return self.profile_data.get("regions", [])
    test_logger_re.info("--- RulesEngine Test Start (with proactive analysis calls) ---")
    project_root_for_test = project_src_dir.parent
    profiles_dir_for_test = project_root_for_test / "profiles"
    templates_dir_for_test = profiles_dir_for_test / "templates"
    templates_dir_for_test.mkdir(parents=True, exist_ok=True)
    dummy_template_name = "test_icon.png"
    dummy_template_path = templates_dir_for_test / dummy_template_name
    try:
        import numpy as np; import cv2
        template_data = np.full((10, 10, 3), (0, 255, 0), dtype=np.uint8)
        cv2.imwrite(str(dummy_template_path), template_data)
        test_logger_re.info(f"Created dummy template: {dummy_template_path}")
    except Exception as e: test_logger_re.error(f"Could not create dummy template: {e}")
    test_profile_re = {
        "regions": [{"name": "area1", "x":0,"y":0,"w":100,"h":100}, {"name": "area2", "x":0,"y":0,"w":100,"h":100}],
        "rules": [
            {"name": "R_Pixel","region":"area1","condition": {"type":"pixel_color","relative_x":5,"relative_y":5,"expected_bgr":[10,20,30]},"action":{"type":"log_pixel"}},
            {"name": "R_Template","region":"area2","condition": {"type":"template_match_found","template_filename":dummy_template_name,"min_confidence":0.7},"action":{"type":"log_template"}}
    ]}
    mock_action_ex_re = MockActionExecutor()
    mock_config_mgr_re = MockConfigManager(test_profile_re, project_root_for_test) 
    real_analysis_engine = AnalysisEngine() 
    rules_engine_instance_re = RulesEngine(mock_action_ex_re, mock_config_mgr_re, real_analysis_engine)
    try:
        img_area1 = np.full((100,100,3),(255,255,255),dtype=np.uint8); img_area1[5,5] = [10,20,30]
        img_area2 = np.full((100,100,3),(200,200,200),dtype=np.uint8); img_area2[20:30,20:30] = [0,255,0]
        iter_results = {"area1":{"captured_image":img_area1},"area2":{"captured_image":img_area2}}
        test_logger_re.info(f"\n--- Test Iteration with Proactive Analysis ---")
        rules_engine_instance_re.evaluate_rules(iter_results)
    except NameError as e: test_logger_re.critical(f"Test failed due to missing libs (cv2/numpy): {e}")
    except Exception as e: test_logger_re.error(f"Exception during test: {e}", exc_info=True)
    test_logger_re.info("--- RulesEngine Test End ---")