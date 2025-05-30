import logging
import os
import re
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from collections import defaultdict

import cv2
import numpy as np

from mark_i.core.config_manager import ConfigManager
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.engines.gemini_decision_module import GeminiDecisionModule  # Assumed available

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.rules_engine")

PLACEHOLDER_REGEX = re.compile(r"\{([\w_]+)((\.[\w_]+)*)\}")
TEMPLATES_SUBDIR_NAME = "templates"


class RulesEngine:
    """
    Evaluates rules based on visual analysis data and triggers actions.
    Supports single conditions, compound conditions (AND/OR logic),
    rule-scoped variable capture and substitution.
    Pre-parses rules to determine analysis dependencies for selective analysis.
    Integrates GeminiAnalyzer for AI-powered visual queries (`gemini_vision_query` condition)
    and GeminiDecisionModule for NLU-driven tasks (`gemini_perform_task` action).
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        analysis_engine: AnalysisEngine,
        action_executor: ActionExecutor,
        gemini_decision_module: Optional[GeminiDecisionModule] = None,  # Made optional for graceful degradation
    ):
        """Initializes the RulesEngine and parses rule dependencies."""
        self.config_manager = config_manager
        self.analysis_engine = analysis_engine
        self.action_executor = action_executor
        self.gemini_decision_module = gemini_decision_module  # Store the passed instance
        self.profile_data = self.config_manager.get_profile_data()
        self.rules: List[Dict[str, Any]] = self.profile_data.get("rules", [])
        self._loaded_templates: Dict[Tuple[str, str], Optional[np.ndarray]] = {}
        self._last_template_match_info: Dict[str, Any] = {}  # Stores info from last successful template match in a rule eval

        self._analysis_requirements_per_region: Dict[str, Set[str]] = defaultdict(set)
        self._parse_rule_analysis_dependencies()  # Determines which local analyses are needed per region

        # Initialize GeminiAnalyzer specifically for `gemini_vision_query` conditions
        gemini_api_key_env = os.getenv("GEMINI_API_KEY")
        gemini_default_model_setting = self.config_manager.get_setting("gemini_default_model_name", "gemini-1.5-flash-latest")
        self.gemini_analyzer_for_query: Optional[GeminiAnalyzer] = None  # Renamed for clarity
        if gemini_api_key_env:
            self.gemini_analyzer_for_query = GeminiAnalyzer(api_key=gemini_api_key_env, default_model_name=gemini_default_model_setting)
            if not self.gemini_analyzer_for_query.client_initialized:
                logger.warning("RulesEngine: GeminiAnalyzer (for vision query) failed client init. `gemini_vision_query` conditions will fail.")
                self.gemini_analyzer_for_query = None
            else:
                logger.info(f"RulesEngine: GeminiAnalyzer (for vision query) enabled. Default model: '{gemini_default_model_setting}'")
        else:
            logger.warning("RulesEngine: GEMINI_API_KEY not found. `gemini_vision_query` conditions will be disabled/fail.")

        if self.gemini_decision_module:
            logger.info("RulesEngine: GeminiDecisionModule integration is active.")
        else:
            logger.warning("RulesEngine: GeminiDecisionModule not provided or failed to initialize. `gemini_perform_task` (NLU) actions will be skipped or fail.")

        if not self.rules:
            logger.warning("RulesEngine: No rules found in the loaded profile.")
        else:
            logger.info(f"RulesEngine initialized with {len(self.rules)} rules.")
            logger.debug(f"RulesEngine: Determined local analysis requirements: {dict(self._analysis_requirements_per_region)}")

    def _parse_rule_analysis_dependencies(self):
        """
        Parses all rules in the profile at initialization to determine which general
        local analyses (like OCR, dominant color, average color) need to be run
        pre-emptively by MainController for each region if any rule uses them.
        `gemini_vision_query` and `gemini_perform_task` do not add to these *local*
        pre-emptive requirements as their AI calls are on-demand.
        """
        logger.debug("RulesEngine: Parsing rule analysis dependencies...")
        if not self.rules:
            logger.debug("RulesEngine: No rules to parse for analysis dependencies.")
            return

        for i, rule in enumerate(self.rules):
            rule_name = rule.get("name", f"UnnamedRule_idx{i}")
            default_rule_region = rule.get("region")  # Rule's default region
            condition_spec_outer = rule.get("condition")

            if not condition_spec_outer or not isinstance(condition_spec_outer, dict):
                logger.warning(f"Rule '{rule_name}': Invalid or missing condition specification. Skipping for dependency parsing.")
                continue

            # Collect all individual condition specs that might require local analysis
            conditions_to_check_for_deps: List[Tuple[Dict[str, Any], Optional[str]]] = []  # (condition_dict, target_region_for_this_cond)

            if "logical_operator" in condition_spec_outer and "sub_conditions" in condition_spec_outer and isinstance(condition_spec_outer["sub_conditions"], list):
                # Compound condition
                for sub_cond_spec in condition_spec_outer["sub_conditions"]:
                    if isinstance(sub_cond_spec, dict):
                        # Sub-condition can override the rule's default region
                        sub_cond_target_region = sub_cond_spec.get("region", default_rule_region)
                        conditions_to_check_for_deps.append((sub_cond_spec, sub_cond_target_region))
            else:
                # Single condition, can also override the rule's default region
                single_cond_target_region = condition_spec_outer.get("region", default_rule_region)
                conditions_to_check_for_deps.append((condition_spec_outer, single_cond_target_region))

            for cond_spec, target_region in conditions_to_check_for_deps:
                cond_type = cond_spec.get("type")
                required_local_analysis_type: Optional[str] = None

                if cond_type == "ocr_contains_text":
                    required_local_analysis_type = "ocr"
                elif cond_type == "dominant_color_matches":
                    required_local_analysis_type = "dominant_color"
                elif cond_type == "average_color_is":
                    required_local_analysis_type = "average_color"
                # `gemini_vision_query` does not require pre-emptive *local* analysis by MainController.
                # Other types like pixel_color, template_match_found are on-demand within RulesEngine.

                if required_local_analysis_type and target_region:  # Must have a region to associate with
                    self._analysis_requirements_per_region[target_region].add(required_local_analysis_type)
                    logger.debug(f"Dependency: Rule '{rule_name}', CondType '{cond_type}' in Region '{target_region}' requires local analysis: '{required_local_analysis_type}'.")

        if self._analysis_requirements_per_region:
            logger.info(f"RulesEngine: Local analysis dependency parsing complete. Requirements: {dict(self._analysis_requirements_per_region)}")
        else:
            logger.info("RulesEngine: Local analysis dependency parsing complete. No pre-emptive local analyses required by any rule.")

    def get_analysis_requirements_for_region(self, region_name: str) -> Set[str]:
        """Returns the set of required local general analysis types for a given region."""
        reqs = self._analysis_requirements_per_region.get(region_name, set())
        # logger.debug(f"Queried local analysis requirements for region '{region_name}': {reqs if reqs else 'None'}") # Can be noisy
        return reqs

    def _load_template_image_for_rule(self, template_filename: str, rule_name_for_context: str) -> Optional[np.ndarray]:  # No changes from previous full version
        profile_base_path = self.config_manager.get_profile_base_path()
        if not profile_base_path:
            logger.error(f"R '{rule_name_for_context}': Cannot load template '{template_filename}', profile base path is unknown (profile likely unsaved).")
            return None
        cache_key = (profile_base_path, template_filename)  # Cache key includes profile base to handle same filename in different profiles
        if cache_key in self._loaded_templates:
            # logger.debug(f"R '{rule_name_for_context}': Using cached template '{template_filename}' from profile '{os.path.basename(profile_base_path)}'.")
            return self._loaded_templates[cache_key]

        template_full_path = os.path.join(profile_base_path, TEMPLATES_SUBDIR_NAME, template_filename)
        logger.debug(f"R '{rule_name_for_context}': Attempting to load template '{template_filename}' from full path '{template_full_path}'.")
        try:
            if not os.path.exists(template_full_path):
                logger.error(f"R '{rule_name_for_context}': Template image file not found at '{template_full_path}'.")
                self._loaded_templates[cache_key] = None
                return None
            template_image = cv2.imread(template_full_path, cv2.IMREAD_COLOR)  # Ensure BGR
            if template_image is None:
                logger.error(f"R '{rule_name_for_context}': Failed to load template (cv2.imread returned None) from '{template_full_path}'. File might be corrupted, not an image, or path issue.")
                self._loaded_templates[cache_key] = None
                return None
            logger.info(f"R '{rule_name_for_context}': Successfully loaded template '{template_filename}' (shape: {template_image.shape}) from '{template_full_path}'.")
            self._loaded_templates[cache_key] = template_image
            return template_image
        except Exception as e:
            logger.exception(f"R '{rule_name_for_context}': Exception while loading template image '{template_filename}' from '{template_full_path}'. Error: {e}")
            self._loaded_templates[cache_key] = None
            return None

    def _substitute_variables(self, input_value: Any, variable_context: Dict[str, Any], rule_name_for_context: str) -> Any:  # No changes from previous full version
        if isinstance(input_value, str):

            def replace_match(match_obj: re.Match) -> str:
                full_placeholder = match_obj.group(0)
                var_name = match_obj.group(1)
                dot_path_str = match_obj.group(2)  # This includes the leading dot, e.g., ".value.box.0"
                # logger.debug(f"R '{rule_name_for_context}', Subst: Placeholder='{full_placeholder}', Var='{var_name}', Path='{dot_path_str}'")
                if var_name in variable_context:
                    current_value = variable_context[var_name]
                    if dot_path_str:  # If there's a path like .value or .value.box.0
                        keys = dot_path_str.strip(".").split(".")
                        try:
                            for key_part in keys:
                                if isinstance(current_value, dict):
                                    current_value = current_value[key_part]
                                elif isinstance(current_value, list) and key_part.isdigit():
                                    idx = int(key_part)
                                    if 0 <= idx < len(current_value):
                                        current_value = current_value[idx]
                                    else:
                                        logger.warning(
                                            f"R '{rule_name_for_context}', Subst: Index '{idx}' out of bounds for var '{var_name}' list (len {len(current_value)}). Placeholder '{full_placeholder}' left."
                                        )
                                        return full_placeholder
                                else:
                                    logger.warning(
                                        f"R '{rule_name_for_context}', Subst: Cannot access key/index '{key_part}' in non-dict/list or invalid index for var '{var_name}'. Placeholder '{full_placeholder}' left."
                                    )
                                    return full_placeholder
                            str_value = str(current_value)
                            # logger.debug(f"R '{rule_name_for_context}', Subst: Replaced '{full_placeholder}' with value '{str_value}'.")
                            return str_value
                        except (KeyError, IndexError) as e_path:
                            logger.warning(f"R '{rule_name_for_context}', Subst: Path '{dot_path_str}' not found for var '{var_name}' (Error: {e_path}). Placeholder '{full_placeholder}' left.")
                            return full_placeholder
                        except Exception as e_access:  # Catch any other unexpected errors during path access
                            logger.warning(f"R '{rule_name_for_context}', Subst: Error accessing path '{dot_path_str}' for var '{var_name}': {e_access}. Placeholder left.")
                            return full_placeholder
                    else:  # No dot path, just the variable itself
                        str_value = str(current_value)
                        # logger.debug(f"R '{rule_name_for_context}', Subst: Replaced '{full_placeholder}' with value '{str_value}'.")
                        return str_value
                else:
                    logger.warning(f"R '{rule_name_for_context}', Subst: Variable '{var_name}' for placeholder '{full_placeholder}' not found in context. Placeholder left.")
                    return full_placeholder  # Leave placeholder if var not found

            return PLACEHOLDER_REGEX.sub(replace_match, input_value)
        elif isinstance(input_value, list):  # Recursively substitute in lists
            return [self._substitute_variables(item, variable_context, rule_name_for_context) for item in input_value]
        elif isinstance(input_value, dict):  # Recursively substitute in dict values
            return {key: self._substitute_variables(value, variable_context, rule_name_for_context) for key, value in input_value.items()}
        else:  # Not a string, list, or dict - return as is
            return input_value

    def _evaluate_single_condition_logic(  # No changes from previous full version needed for Phase 3 integration here
        self, single_condition_spec: Dict[str, Any], region_name: str, region_data: Dict[str, Any], rule_name_for_context: str, variable_context: Dict[str, Any]
    ) -> bool:
        condition_type = single_condition_spec.get("type")
        capture_as_var_name = single_condition_spec.get("capture_as")
        log_prefix_cond = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond '{condition_type}'"

        if not condition_type:
            logger.error(f"{log_prefix_cond}: 'type' missing in condition specification.")
            return False

        # logger.debug(f"{log_prefix_cond}: Evaluating. Spec: {single_condition_spec}")
        captured_image = region_data.get("image")  # NumPy BGR array or None
        condition_met = False
        captured_value_for_var: Any = None  # Value to be stored if 'capture_as' is used

        # Helper to get pre-analyzed data or compute on-the-fly if image available
        def get_analysis_data_with_fallback(data_key: str, analysis_func: Callable, *args_for_analysis_func) -> Any:
            data = region_data.get(data_key)
            if data is None and captured_image is not None:
                logger.debug(f"{log_prefix_cond}: Data for '{data_key}' not pre-analyzed. Fallback: Recalculating.")
                try:
                    data = analysis_func(*args_for_analysis_func)
                except Exception as e_fb:
                    logger.error(f"{log_prefix_cond}: Fallback calculation for '{data_key}' failed: {e_fb}", exc_info=True)
                    data = None  # Ensure None on failure
            elif data is None and captured_image is None:
                logger.warning(f"{log_prefix_cond}: Data for '{data_key}' not pre-analyzed AND no image available for fallback.")
            return data

        try:
            if condition_type == "pixel_color":
                if captured_image is None:
                    logger.warning(f"{log_prefix_cond}: Image is None.")
                    return False
                rx, ry, ebgr, tol = map(single_condition_spec.get, ["relative_x", "relative_y", "expected_bgr", "tolerance"], [0, 0, None, 0])
                if not all(isinstance(v, int) for v in [rx, ry]) or not (isinstance(ebgr, list) and len(ebgr) == 3 and all(isinstance(c, int) for c in ebgr)):
                    logger.error(f"{log_prefix_cond}: Invalid params (rx, ry, expected_bgr).")
                    return False
                condition_met = self.analysis_engine.analyze_pixel_color(captured_image, rx, ry, ebgr, tol, rule_name_for_context)  # Pass context

            elif condition_type == "average_color_is":
                avg_color_data = get_analysis_data_with_fallback("average_color", self.analysis_engine.analyze_average_color, captured_image, rule_name_for_context)
                if avg_color_data is None:
                    return False
                ebgr, tol = map(single_condition_spec.get, ["expected_bgr", "tolerance"], [None, 10])
                if not (isinstance(ebgr, list) and len(ebgr) == 3 and all(isinstance(c, int) for c in ebgr)):
                    logger.error(f"{log_prefix_cond}: Invalid expected_bgr.")
                    return False
                c_diff = np.abs(np.array(avg_color_data) - np.array(ebgr))
                condition_met = np.all(c_diff <= tol)

            elif condition_type == "template_match_found":
                if captured_image is None:
                    logger.warning(f"{log_prefix_cond}: Image is None.")
                    return False
                tpl_fn = single_condition_spec.get("template_filename")
                min_conf = float(single_condition_spec.get("min_confidence", 0.8))
                if not tpl_fn:
                    logger.error(f"{log_prefix_cond}: Missing template_filename.")
                    return False
                tpl_img = self._load_template_image_for_rule(tpl_fn, rule_name_for_context)
                if tpl_img is None:
                    return False  # Error logged in _load_template
                match_res = self.analysis_engine.match_template(captured_image, tpl_img, min_conf, rule_name_for_context, tpl_fn)
                if match_res:
                    condition_met = True
                    # Store detailed match info for potential use by 'center_of_last_match' action target
                    self._last_template_match_info = {"found": True, **match_res, "matched_region_name": region_name}
                    if capture_as_var_name:  # Capture simplified dictionary for user variables
                        captured_value_for_var = {
                            "value": {  # Wrapped for consistency with Gemini captures
                                "x": match_res["location_x"],
                                "y": match_res["location_y"],
                                "width": match_res["width"],
                                "height": match_res["height"],
                                "confidence": match_res["confidence"],
                            },
                            "_source_region_for_capture_": region_name,
                        }
                else:
                    self._last_template_match_info = {"found": False}  # Ensure it's reset if no match

            elif condition_type == "ocr_contains_text":
                ocr_result_dict = get_analysis_data_with_fallback("ocr_analysis_result", self.analysis_engine.ocr_extract_text, captured_image, region_name)
                if not ocr_result_dict or "text" not in ocr_result_dict:
                    logger.warning(f"{log_prefix_cond}: OCR result missing/invalid.")
                    return False

                actual_text = ocr_result_dict.get("text", "")
                actual_avg_confidence = ocr_result_dict.get("average_confidence", 0.0)

                texts_to_find_param = single_condition_spec.get("text_to_find")
                texts_to_find_list: List[str] = []
                if isinstance(texts_to_find_param, str):
                    texts_to_find_list = [s.strip() for s in texts_to_find_param.split(",") if s.strip()]
                elif isinstance(texts_to_find_param, list):
                    texts_to_find_list = [str(s).strip() for s in texts_to_find_param if str(s).strip()]

                if not texts_to_find_list:
                    logger.error(f"{log_prefix_cond}: 'text_to_find' is empty/missing.")
                    return False

                case_sensitive = single_condition_spec.get("case_sensitive", False)
                min_ocr_conf_val_str = str(single_condition_spec.get("min_ocr_confidence", "")).strip()
                min_ocr_conf_threshold: Optional[float] = None
                if min_ocr_conf_val_str:
                    try:
                        min_ocr_conf_threshold = float(min_ocr_conf_val_str)
                    except ValueError:
                        logger.warning(f"{log_prefix_cond}: Invalid min_ocr_confidence '{min_ocr_conf_val_str}'. Confidence check skipped.")

                processed_ocr_text = actual_text if case_sensitive else actual_text.lower()
                text_found_match = False
                for text_item_orig in texts_to_find_list:
                    processed_text_item = text_item_orig if case_sensitive else text_item_orig.lower()
                    if processed_text_item in processed_ocr_text:
                        text_found_match = True
                        break

                if not text_found_match:
                    logger.debug(f"{log_prefix_cond}: Keywords '{texts_to_find_list}' NOT found.")
                    return False

                # Text found, now check confidence if specified
                confidence_criteria_met = min_ocr_conf_threshold is None or actual_avg_confidence >= min_ocr_conf_threshold
                if confidence_criteria_met:
                    condition_met = True
                    if capture_as_var_name:
                        captured_value_for_var = {"value": actual_text, "_source_region_for_capture_": region_name}
                else:
                    logger.info(f"{log_prefix_cond}: Text found, but OCR confidence {actual_avg_confidence:.1f}% < threshold {min_ocr_conf_threshold}%.")

            elif condition_type == "dominant_color_matches":
                dominant_colors_list = get_analysis_data_with_fallback(
                    "dominant_colors_result", self.analysis_engine.analyze_dominant_colors, captured_image, self.config_manager.get_setting("analysis_dominant_colors_k", 3), region_name
                )
                if not isinstance(dominant_colors_list, list):
                    return False  # Handles None or other types

                ebgr, tol, top_n, min_perc = map(single_condition_spec.get, ["expected_bgr", "tolerance", "check_top_n_dominant", "min_percentage"], [None, 10, 1, 0.0])
                if not (isinstance(ebgr, list) and len(ebgr) == 3):
                    logger.error(f"{log_prefix_cond}: Invalid expected_bgr.")
                    return False

                for i, color_info in enumerate(dominant_colors_list[: min(top_n, len(dominant_colors_list))]):
                    actual_bgr, actual_percentage = color_info.get("bgr_color"), color_info.get("percentage", 0.0)
                    if isinstance(actual_bgr, list) and np.all(np.abs(np.array(actual_bgr) - np.array(ebgr)) <= tol) and actual_percentage >= min_perc:
                        condition_met = True
                        break

            elif condition_type == "gemini_vision_query":
                if not self.gemini_analyzer_for_query:
                    logger.error(f"{log_prefix_cond}: GeminiAnalyzer (for query) not available.")
                    return False
                if captured_image is None:
                    logger.warning(f"{log_prefix_cond}: Image is None.")
                    return False
                prompt = single_condition_spec.get("prompt")
                if not prompt:
                    logger.error(f"{log_prefix_cond}: 'prompt' missing.")
                    return False

                model_override = single_condition_spec.get("model_name")
                gemini_api_response = self.gemini_analyzer_for_query.query_vision_model(captured_image, prompt, model_name_override=model_override)

                if gemini_api_response["status"] != "success":
                    logger.warning(f"{log_prefix_cond}: API call failed/blocked. Status: {gemini_api_response['status']}, Err: {gemini_api_response['error_message']}.")
                    return False

                text_resp = gemini_api_response.get("text_content", "") or ""  # Ensure string
                json_resp_obj = gemini_api_response.get("json_content")  # Already parsed dict/list or None

                exp_subs_param = single_condition_spec.get("expected_response_contains")
                case_sens_check = single_condition_spec.get("case_sensitive_response_check", False)
                exp_json_path = single_condition_spec.get("expected_response_json_path")
                exp_json_val_config = single_condition_spec.get("expected_json_value")  # Can be any type from JSON

                text_check_passes = True
                if exp_subs_param:  # Only check if defined
                    subs_list: List[str] = []
                    if isinstance(exp_subs_param, str):
                        subs_list = [s.strip() for s in exp_subs_param.split(",") if s.strip()]
                    elif isinstance(exp_subs_param, list):
                        subs_list = [str(s).strip() for s in exp_subs_param if str(s).strip()]

                    if subs_list:  # Only if there are actual substrings to check
                        text_to_search = text_resp if case_sens_check else text_resp.lower()
                        text_check_passes = any((s if case_sens_check else s.lower()) in text_to_search for s in subs_list)
                        if not text_check_passes:
                            logger.debug(f"{log_prefix_cond}: Substrings '{subs_list}' not found in text.")

                json_check_passes = True
                actual_json_val_for_capture: Any = None
                if exp_json_path and json_resp_obj is not None:  # Check JSON path only if defined and we have JSON
                    current_json_val = json_resp_obj
                    path_valid = True
                    try:
                        for key_part in exp_json_path.strip(".").split("."):
                            if isinstance(current_json_val, dict):
                                current_json_val = current_json_val[key_part]
                            elif isinstance(current_json_val, list) and key_part.isdigit():
                                current_json_val = current_json_val[int(key_part)]
                            else:
                                path_valid = False
                                break
                        if path_valid:
                            actual_json_val_for_capture = current_json_val
                    except (KeyError, IndexError, TypeError):
                        path_valid = False

                    if not path_valid:
                        json_check_passes = False
                        logger.debug(f"{log_prefix_cond}: JSONPath '{exp_json_path}' not found or invalid.")
                    elif exp_json_val_config is not None:  # Only compare if an expected value is given
                        # Comparing potentially different types (e.g. int from JSON vs str from config)
                        # For simplicity, convert both to string for comparison, or handle types more carefully.
                        if str(current_json_val) != str(exp_json_val_config):
                            json_check_passes = False
                            logger.debug(f"{log_prefix_cond}: JSONPath value '{current_json_val}' != Expected '{exp_json_val_config}'.")
                elif exp_json_path and json_resp_obj is None:  # Path specified but no JSON from Gemini
                    json_check_passes = False
                    logger.debug(f"{log_prefix_cond}: JSONPath '{exp_json_path}' specified but no JSON in response.")

                if text_check_passes and json_check_passes:
                    condition_met = True
                    if capture_as_var_name:
                        data_to_be_captured = actual_json_val_for_capture if exp_json_path and actual_json_val_for_capture is not None else (json_resp_obj if json_resp_obj is not None else text_resp)
                        captured_value_for_var = {"value": data_to_be_captured, "_source_region_for_capture_": region_name}

            elif condition_type == "always_true":
                condition_met = True
            else:
                logger.error(f"{log_prefix_cond}: Unknown condition type. Evaluation fails.")
                return False  # Unknown type

            # Store captured value if condition met and capture was intended
            if condition_met and capture_as_var_name and captured_value_for_var is not None:
                variable_context[capture_as_var_name] = captured_value_for_var
                # Log snippet of captured value for easier debugging
                val_str_repr = str(captured_value_for_var)
                val_snippet = (val_str_repr[:67] + "...") if len(val_str_repr) > 70 else val_str_repr
                logger.info(f"{log_prefix_cond}: Captured value for '{capture_as_var_name}'. Snippet: '{val_snippet.replace(os.linesep, ' ')}'")
            elif (
                condition_met and capture_as_var_name and captured_value_for_var is None and condition_type not in ["template_match_found", "ocr_contains_text", "gemini_vision_query"]
            ):  # Types that explicitly set it
                logger.warning(f"{log_prefix_cond}: `capture_as` specified for condition type '{condition_type}' but no value was set for capture by its logic.")

        except Exception as e:
            logger.exception(f"{log_prefix_cond}: Unexpected exception during evaluation: {e}")
            return False  # Fail on any unexpected error

        logger.info(f"{log_prefix_cond}: Evaluation result = {condition_met}")
        return condition_met

    def _check_condition(  # No changes from previous full version
        self, rule_name: str, condition_spec: Dict[str, Any], default_rule_region_from_rule: Optional[str], all_region_data: Dict[str, Dict[str, Any]], variable_context: Dict[str, Any]
    ) -> bool:
        # logger.debug(f"R '{rule_name}': Start condition evaluation. Original Spec: {condition_spec}")
        logical_operator_str = condition_spec.get("logical_operator")
        sub_conditions_original = condition_spec.get("sub_conditions")

        if logical_operator_str and isinstance(sub_conditions_original, list):  # Compound condition
            operator = logical_operator_str.upper()
            if operator not in ["AND", "OR"]:
                logger.error(f"R '{rule_name}': Invalid logical_operator '{logical_operator_str}'. Defaulting to FALSE for condition.")
                return False
            if not sub_conditions_original:
                logger.warning(
                    f"R '{rule_name}': Compound operator '{operator}' but 'sub_conditions' list is empty. Defaulting to FALSE for condition (or TRUE for OR if that's desired - current is strict)."
                )
                return False  # Or True for OR if empty means vacuously true for OR, but typically means misconfig.

            # logger.info(f"R '{rule_name}': Evaluating compound condition with operator '{operator}' and {len(sub_conditions_original)} sub-conditions.")
            all_sub_results_for_logging = []  # For detailed logging if needed

            for i, sub_cond_orig_spec in enumerate(sub_conditions_original):
                sub_cond_context_name = f"{rule_name}/SubCond#{i+1}"
                if not isinstance(sub_cond_orig_spec, dict):
                    logger.error(f"R '{sub_cond_context_name}': Sub-condition is not a dictionary. Skipping. Spec: {sub_cond_orig_spec}")
                    if operator == "AND":
                        return False  # Invalid sub-condition breaks AND chain
                    continue  # For OR, skip invalid and continue

                # Substitute variables *within* the sub-condition spec before determining its region or type
                sub_cond_spec_substituted = self._substitute_variables(sub_cond_orig_spec, variable_context, sub_cond_context_name)

                # Determine target region for this sub-condition
                sub_cond_target_region = sub_cond_spec_substituted.get("region", default_rule_region_from_rule)

                if not sub_cond_target_region:
                    logger.error(
                        f"R '{sub_cond_context_name}': No target region specified (and no rule default). Sub-condition type: '{sub_cond_spec_substituted.get('type')}'. Cannot evaluate. Sub-condition fails."
                    )
                    if operator == "AND":
                        return False  # This sub-condition fails, so AND fails
                    all_sub_results_for_logging.append(False)
                    continue  # For OR, a failure here doesn't stop evaluation yet

                if sub_cond_target_region not in all_region_data:
                    logger.error(
                        f"R '{sub_cond_context_name}': Target region '{sub_cond_target_region}' for sub-condition not found in available region data (keys: {list(all_region_data.keys())}). Sub-condition fails."
                    )
                    if operator == "AND":
                        return False
                    all_sub_results_for_logging.append(False)
                    continue

                target_region_data_for_sub = all_region_data[sub_cond_target_region]
                sub_result = self._evaluate_single_condition_logic(sub_cond_spec_substituted, sub_cond_target_region, target_region_data_for_sub, sub_cond_context_name, variable_context)
                all_sub_results_for_logging.append(sub_result)

                if operator == "AND" and not sub_result:
                    logger.info(f"R '{rule_name}': Compound AND short-circuited to FALSE by sub-condition '{sub_cond_context_name}'.")
                    return False
                if operator == "OR" and sub_result:
                    logger.info(f"R '{rule_name}': Compound OR short-circuited to TRUE by sub-condition '{sub_cond_context_name}'.")
                    return True

            # If loop completes without short-circuiting:
            if operator == "AND":  # All must have been true
                final_compound_result = True
            elif operator == "OR":  # None were true
                final_compound_result = False
            else:  # Should not happen due to earlier check
                final_compound_result = False

            logger.info(f"R '{rule_name}': Compound condition final result = {final_compound_result}. Sub-results: {all_sub_results_for_logging}")
            return final_compound_result

        else:  # Single condition
            # Substitute variables in the single condition spec
            single_condition_spec_substituted = self._substitute_variables(condition_spec, variable_context, rule_name)

            # Determine target region for this single condition
            single_cond_target_region = single_condition_spec_substituted.get("region", default_rule_region_from_rule)

            if not single_cond_target_region:
                logger.error(
                    f"R '{rule_name}': Single condition, but no target region specified (and no rule default). Condition type: '{single_condition_spec_substituted.get('type')}'. Cannot evaluate. Condition fails."
                )
                return False
            if single_cond_target_region not in all_region_data:
                logger.error(f"R '{rule_name}': Target region '{single_cond_target_region}' for single condition not found in available region data. Condition fails.")
                return False

            target_region_data_for_single = all_region_data[single_cond_target_region]
            result = self._evaluate_single_condition_logic(single_condition_spec_substituted, single_cond_target_region, target_region_data_for_single, rule_name, variable_context)
            # Result already logged by _evaluate_single_condition_logic
            return result

    def evaluate_rules(self, all_region_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluates all rules in the current profile against the provided region data.
        If a rule's condition is met, its action is prepared and executed.
        For `gemini_perform_task` actions, invokes the `GeminiDecisionModule`.
        For other actions, invokes `ActionExecutor` directly.

        Args:
            all_region_data: A dictionary where keys are region names and values are
                             dictionaries of analysis data for that region (including 'image').

        Returns:
            A list of standard action specifications that were triggered and sent to
            ActionExecutor (this list will NOT include actions performed internally
            by GeminiDecisionModule as part of an NLU task).
        """
        explicitly_triggered_action_specs: List[Dict[str, Any]] = []
        if not self.rules:
            logger.debug("RulesEngine: No rules to evaluate in this cycle.")
            return explicitly_triggered_action_specs

        logger.info(f"RulesEngine: Starting evaluation of {len(self.rules)} rules.")

        for rule_idx, rule_config in enumerate(self.rules):
            rule_name = rule_config.get("name", f"UnnamedRule_idx{rule_idx}")
            original_condition_spec = rule_config.get("condition")
            original_action_spec = rule_config.get("action")
            # Rule's default region, can be overridden by specific conditions/sub-conditions
            default_rule_region_name = rule_config.get("region")

            log_prefix_rule_eval = f"R '{rule_name}'"

            if not original_condition_spec or not isinstance(original_condition_spec, dict) or not original_action_spec or not isinstance(original_action_spec, dict):
                logger.warning(f"{log_prefix_rule_eval}: Invalid or missing condition/action specification. Skipping rule.")
                continue

            self._last_template_match_info = {"found": False}  # Reset for each rule's context
            rule_variable_context: Dict[str, Any] = {}  # Fresh variable context for each rule

            logger.debug(f"{log_prefix_rule_eval}: Evaluating. Default region: '{default_rule_region_name}'.")

            try:
                condition_is_met = self._check_condition(rule_name, original_condition_spec, default_rule_region_name, all_region_data, rule_variable_context)

                if condition_is_met:
                    action_type_from_spec = original_action_spec.get("type")
                    logger.info(f"{log_prefix_rule_eval}: Condition MET. Preparing action of type '{action_type_from_spec}'.")

                    # Substitute variables into the entire action specification
                    action_spec_substituted = self._substitute_variables(original_action_spec, rule_variable_context, f"{rule_name}/ActionSubst")
                    logger.debug(f"{log_prefix_rule_eval}, Action Prep: Substituted action spec: {action_spec_substituted}. Variables used: {rule_variable_context}")

                    action_type_final = action_spec_substituted.get("type")  # Get type from substituted spec

                    if action_type_final == "gemini_perform_task":
                        if self.gemini_decision_module:
                            # Extract parameters for GeminiDecisionModule.execute_nlu_task()
                            # Parameter name changed from goal_prompt to natural_language_command in Phase 3 design
                            nl_command = action_spec_substituted.get("natural_language_command", action_spec_substituted.get("goal_prompt"))

                            context_r_names_param = action_spec_substituted.get("context_region_names", [])
                            # Ensure context_region_names is a list of strings
                            if isinstance(context_r_names_param, str) and context_r_names_param.strip():
                                context_region_names_list = [r.strip() for r in context_r_names_param.split(",") if r.strip()]
                            elif isinstance(context_r_names_param, list):
                                context_region_names_list = [str(r).strip() for r in context_r_names_param if str(r).strip()]
                            else:
                                context_region_names_list = []

                            # Other task parameters from the rule's action spec
                            task_specific_params = {
                                "allowed_actions_override": action_spec_substituted.get("allowed_actions_override", []),
                                "require_confirmation_per_step": action_spec_substituted.get("require_confirmation_per_step", True),  # Default True for NLU
                                "max_steps": int(action_spec_substituted.get("max_steps", 5)),
                                "pyautogui_pause_before": float(action_spec_substituted.get("pyautogui_pause_before", 0.1)),  # For the overall task start
                            }
                            # Ensure allowed_actions_override is a list of strings
                            if isinstance(task_specific_params["allowed_actions_override"], str) and task_specific_params["allowed_actions_override"].strip():
                                task_specific_params["allowed_actions_override"] = [a.strip() for a in task_specific_params["allowed_actions_override"].split(",") if a.strip()]
                            elif not isinstance(task_specific_params["allowed_actions_override"], list):
                                task_specific_params["allowed_actions_override"] = []

                            task_context_images_map: Dict[str, np.ndarray] = {}
                            can_proceed_with_task = True

                            if not nl_command or not isinstance(nl_command, str):
                                logger.error(f"{log_prefix_rule_eval}, Action 'gemini_perform_task': 'natural_language_command' is missing, empty, or not a string. Task cannot proceed.")
                                can_proceed_with_task = False

                            if can_proceed_with_task:
                                target_region_names_for_context = context_region_names_list
                                if not target_region_names_for_context and default_rule_region_name:  # Fallback to rule's default region
                                    logger.info(f"{log_prefix_rule_eval}, NLU Task: No 'context_region_names' specified, using rule's default region '{default_rule_region_name}' for NLU context.")
                                    target_region_names_for_context = [default_rule_region_name]

                                if not target_region_names_for_context:  # Still no regions
                                    logger.error(f"{log_prefix_rule_eval}, NLU Task: No context regions specified (and no valid rule default). Cannot provide visual context. Task fails.")
                                    can_proceed_with_task = False
                                else:
                                    for r_name_for_task_ctx in target_region_names_for_context:
                                        if r_name_for_task_ctx in all_region_data and all_region_data[r_name_for_task_ctx].get("image") is not None:
                                            task_context_images_map[r_name_for_task_ctx] = all_region_data[r_name_for_task_ctx]["image"]
                                        else:
                                            logger.error(
                                                f"{log_prefix_rule_eval}, NLU Task: Context region '{r_name_for_task_ctx}' not found in all_region_data or its image is None. Task cannot proceed with this context."
                                            )
                                            can_proceed_with_task = False
                                            break  # Stop if any context region is invalid
                                if not task_context_images_map and can_proceed_with_task:  # Double check if map is empty even if names were there
                                    logger.error(f"{log_prefix_rule_eval}, NLU Task: No valid images gathered for context regions. Task fails.")
                                    can_proceed_with_task = False

                            if can_proceed_with_task:
                                logger.info(
                                    f"{log_prefix_rule_eval}: Invoking GeminiDecisionModule for NLU command: '{nl_command[:70]}...' with context from regions: {list(task_context_images_map.keys())}"
                                )
                                task_execution_result = self.gemini_decision_module.execute_nlu_task(
                                    task_rule_name=rule_name,  # Pass rule name for GDM's logging
                                    natural_language_command=nl_command,
                                    initial_context_images=task_context_images_map,
                                    task_parameters=task_specific_params,
                                )
                                logger.info(f"{log_prefix_rule_eval}, NLU Task Result: Status='{task_execution_result.get('status')}', Message='{task_execution_result.get('message')}'")
                            # No action spec is added to explicitly_triggered_action_specs for NLU tasks,
                            # as GeminiDecisionModule handles its own sub-action executions.
                        else:
                            logger.error(f"{log_prefix_rule_eval}, Action 'gemini_perform_task': GeminiDecisionModule is not available. Task skipped.")
                    else:
                        # Standard action execution, directly by RulesEngine calling ActionExecutor
                        action_execution_context = {
                            "rule_name": rule_name,
                            "condition_region": default_rule_region_name,  # Rule's default region context
                            "last_match_info": self._last_template_match_info.copy(),
                            "variables": rule_variable_context.copy(),
                        }
                        full_action_spec_to_execute = {**action_spec_substituted, "context": action_execution_context}

                        logger.info(f"{log_prefix_rule_eval}: Directly executing standard action of type '{action_type_final}' via ActionExecutor.")
                        self.action_executor.execute_action(full_action_spec_to_execute)
                        explicitly_triggered_action_specs.append(full_action_spec_to_execute)  # Track standard actions

            except Exception as e:
                logger.exception(f"{log_prefix_rule_eval}: Unexpected error during rule evaluation or action dispatch: {e}")

        logger.info(f"RulesEngine: Finished evaluation cycle. {len(explicitly_triggered_action_specs)} standard explicit rule actions were executed directly by RulesEngine.")
        return explicitly_triggered_action_specs
