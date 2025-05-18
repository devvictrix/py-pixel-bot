import logging
import os
import re
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from collections import defaultdict

import cv2
import numpy as np

from py_pixel_bot.core.config_manager import ConfigManager
from py_pixel_bot.core.logging_setup import APP_ROOT_LOGGER_NAME
from py_pixel_bot.engines.analysis_engine import AnalysisEngine
from py_pixel_bot.engines.action_executor import ActionExecutor
from py_pixel_bot.engines.gemini_analyzer import GeminiAnalyzer # New Import

logger = logging.getLogger(__name__)

PLACEHOLDER_REGEX = re.compile(r"\{([\w_]+)((\.[\w_]+)*)\}")
TEMPLATES_SUBDIR_NAME = "templates" # Moved from config_manager for local use


class RulesEngine:
    """
    Evaluates rules based on visual analysis data and triggers actions.
    Supports single conditions, compound conditions (AND/OR logic),
    rule-scoped variable capture and substitution.
    Pre-parses rules to determine analysis dependencies for selective analysis.
    Integrates GeminiAnalyzer for AI-powered visual queries.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        analysis_engine: AnalysisEngine,
        action_executor: ActionExecutor,
    ):
        """Initializes the RulesEngine and parses rule dependencies."""
        self.config_manager = config_manager
        self.analysis_engine = analysis_engine
        self.action_executor = action_executor
        self.profile_data = self.config_manager.get_profile_data()
        self.rules: List[Dict[str, Any]] = self.profile_data.get("rules", [])
        self._loaded_templates: Dict[Tuple[str, str], Optional[np.ndarray]] = {}
        self._last_template_match_info: Dict[str, Any] = {}

        self._analysis_requirements_per_region: Dict[str, Set[str]] = defaultdict(set)
        self._parse_rule_analysis_dependencies()

        # Initialize GeminiAnalyzer
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        gemini_default_model = self.config_manager.get_setting("gemini_default_model_name", "gemini-2.5-pro-preview-03-25")
        self.gemini_analyzer: Optional[GeminiAnalyzer] = None
        if gemini_api_key:
            self.gemini_analyzer = GeminiAnalyzer(api_key=gemini_api_key, default_model_name=gemini_default_model)
            if not self.gemini_analyzer.client_initialized:
                logger.warning("GeminiAnalyzer initialized but API client configuration failed (e.g., bad key format). Gemini queries will fail.")
                self.gemini_analyzer = None # Ensure it's None if not usable
            else:
                logger.info(f"GeminiAnalyzer integration enabled. Default model: '{gemini_default_model}'")
        else:
            logger.warning("GEMINI_API_KEY not found in environment. Gemini-powered conditions will be disabled/fail.")
            self.gemini_analyzer = None


        if not self.rules:
            logger.warning("No rules found in the loaded profile.")
        else:
            logger.info(f"RulesEngine initialized with {len(self.rules)} rules.")
            logger.debug(f"Determined local analysis requirements: {dict(self._analysis_requirements_per_region)}")

    def _parse_rule_analysis_dependencies(self):
        logger.debug("RulesEngine: Parsing rule analysis dependencies...")
        if not self.rules:
            logger.debug("RulesEngine: No rules to parse for analysis dependencies.")
            return

        for i, rule in enumerate(self.rules):
            rule_name = rule.get("name", f"UnnamedRule_idx{i}")
            default_rule_region = rule.get("region")
            condition_spec = rule.get("condition")

            if not condition_spec or not isinstance(condition_spec, dict):
                logger.warning(f"Rule '{rule_name}': Invalid or missing condition specification. Skipping for dependency parsing.")
                continue

            conditions_to_evaluate_for_deps: List[Tuple[Dict[str, Any], Optional[str], str]] = []

            if "logical_operator" in condition_spec and "sub_conditions" in condition_spec and isinstance(condition_spec["sub_conditions"], list):
                logger.debug(f"Rule '{rule_name}': Is compound. Parsing sub-conditions for dependencies.")
                for sub_idx, sub_cond_spec in enumerate(condition_spec["sub_conditions"]):
                    if not isinstance(sub_cond_spec, dict):
                        logger.warning(f"Rule '{rule_name}/Sub#{sub_idx+1}': Invalid sub-condition spec (not a dict). Skipping.")
                        continue
                    sub_cond_region = sub_cond_spec.get("region", default_rule_region)
                    if sub_cond_region:
                        conditions_to_evaluate_for_deps.append((sub_cond_spec, sub_cond_region, f"{rule_name}/Sub#{sub_idx+1}"))
                    else:
                        # If type is gemini_vision_query, it doesn't need a region for local pre-analysis
                        if sub_cond_spec.get("type") != "gemini_vision_query":
                             logger.debug(f"Rule '{rule_name}/Sub#{sub_idx+1}': No explicit or default region for local analysis type. Type: '{sub_cond_spec.get('type')}'. No region-specific dependency added.")
            else: # Single condition
                logger.debug(f"Rule '{rule_name}': Is single condition. Parsing for dependencies.")
                cond_region_name = condition_spec.get("region", default_rule_region) # Handle region override in single condition too
                if cond_region_name:
                    conditions_to_evaluate_for_deps.append((condition_spec, cond_region_name, rule_name))
                else:
                    if condition_spec.get("type") != "gemini_vision_query":
                        logger.debug(f"Rule '{rule_name}' (single): No region specified for local analysis type. Type: '{condition_spec.get('type')}'. No region-specific dependency added.")

            for cond_spec_item, region_name_item, cond_ctx_name_item in conditions_to_evaluate_for_deps:
                cond_type = cond_spec_item.get("type")
                required_analysis: Optional[str] = None
                if cond_type == "ocr_contains_text":
                    required_analysis = "ocr"
                elif cond_type == "dominant_color_matches":
                    required_analysis = "dominant_color"
                elif cond_type == "average_color_is":
                    required_analysis = "average_color"
                # `gemini_vision_query` does not add to *local* pre-emptive analysis requirements.

                if required_analysis and region_name_item:
                    self._analysis_requirements_per_region[region_name_item].add(required_analysis)
                    logger.debug(f"Dependency parser: Condition '{cond_ctx_name_item}' (type: {cond_type}) in region '{region_name_item}' " f"requires pre-emptive local analysis: '{required_analysis}'.")
        logger.info(f"RulesEngine: Local analysis dependency parsing complete. Requirements determined: {dict(self._analysis_requirements_per_region)}")

    def get_analysis_requirements_for_region(self, region_name: str) -> Set[str]:
        reqs = self._analysis_requirements_per_region.get(region_name, set())
        logger.debug(f"Queried local analysis requirements for region '{region_name}': {reqs}")
        return reqs

    def _load_template_image_for_rule(self, template_filename: str, rule_name_for_context: str) -> Optional[np.ndarray]:
        profile_base_path = self.config_manager.get_profile_base_path()
        if not profile_base_path:
            logger.error(f"Rule '{rule_name_for_context}': Cannot load template '{template_filename}', profile base path is unknown (profile likely unsaved).")
            return None
        cache_key = (profile_base_path, template_filename)
        if cache_key in self._loaded_templates:
            logger.debug(f"Rule '{rule_name_for_context}': Using cached template '{template_filename}' from profile '{os.path.basename(profile_base_path)}'.")
            return self._loaded_templates[cache_key]

        template_full_path = os.path.join(profile_base_path, TEMPLATES_SUBDIR_NAME, template_filename)
        logger.debug(f"Rule '{rule_name_for_context}': Attempting to load template '{template_filename}' from full path '{template_full_path}'.")
        try:
            if not os.path.exists(template_full_path):
                logger.error(f"Rule '{rule_name_for_context}': Template image file not found at '{template_full_path}'.")
                self._loaded_templates[cache_key] = None
                return None
            template_image = cv2.imread(template_full_path, cv2.IMREAD_COLOR)
            if template_image is None:
                logger.error(f"Rule '{rule_name_for_context}': Failed to load template (cv2.imread returned None) from '{template_full_path}'. File might be corrupted or unsupported format.")
                self._loaded_templates[cache_key] = None
                return None
            logger.info(f"Rule '{rule_name_for_context}': Successfully loaded template '{template_filename}' (shape: {template_image.shape}) from '{template_full_path}'.")
            self._loaded_templates[cache_key] = template_image
            return template_image
        except Exception as e:
            logger.exception(f"Rule '{rule_name_for_context}': Exception while loading template image '{template_filename}' from '{template_full_path}'. Error: {e}")
            self._loaded_templates[cache_key] = None
            return None

    def _substitute_variables(self, input_value: Any, variable_context: Dict[str, Any], rule_name_for_context: str) -> Any:
        if isinstance(input_value, str):

            def replace_match(match_obj: re.Match) -> str:
                full_placeholder = match_obj.group(0)
                var_name = match_obj.group(1)
                dot_path_str = match_obj.group(2)
                logger.debug(f"Rule '{rule_name_for_context}', Substitution: Found placeholder '{full_placeholder}'. Var: '{var_name}', Path: '{dot_path_str}'")
                if var_name in variable_context:
                    current_value = variable_context[var_name]
                    if dot_path_str:
                        keys = dot_path_str.strip(".").split(".")
                        try:
                            for key_part in keys:
                                if isinstance(current_value, dict):
                                    current_value = current_value[key_part]
                                elif isinstance(current_value, list) and key_part.isdigit():
                                    current_value = current_value[int(key_part)]
                                else:
                                    logger.warning(
                                        f"R '{rule_name_for_context}', Subst: Cannot access key '{key_part}' in non-dict/list or invalid index for var '{var_name}'. Placeholder '{full_placeholder}' left."
                                    )
                                    return full_placeholder
                            str_value = str(current_value)
                            logger.debug(f"R '{rule_name_for_context}', Subst: Replaced '{full_placeholder}' with value '{str_value}'.")
                            return str_value
                        except (KeyError, IndexError):
                            logger.warning(f"R '{rule_name_for_context}', Subst: Path '{dot_path_str}' not found for var '{var_name}'. Placeholder '{full_placeholder}' left.")
                            return full_placeholder
                        except Exception as e:
                            logger.warning(f"R '{rule_name_for_context}', Subst: Error accessing path '{dot_path_str}' for var '{var_name}': {e}. Placeholder left.")
                            return full_placeholder
                    else:
                        str_value = str(current_value)
                        logger.debug(f"R '{rule_name_for_context}', Subst: Replaced '{full_placeholder}' with value '{str_value}'.")
                        return str_value
                else:
                    logger.warning(f"R '{rule_name_for_context}', Subst: Var '{var_name}' for '{full_placeholder}' not found. Placeholder left.")
                    return full_placeholder

            return PLACEHOLDER_REGEX.sub(replace_match, input_value)
        elif isinstance(input_value, list):
            return [self._substitute_variables(item, variable_context, rule_name_for_context) for item in input_value]
        elif isinstance(input_value, dict):
            return {key: self._substitute_variables(value, variable_context, rule_name_for_context) for key, value in input_value.items()}
        else:
            return input_value

    def _evaluate_single_condition_logic(
        self, single_condition_spec: Dict[str, Any], region_name: str, region_data: Dict[str, Any], rule_name_for_context: str, variable_context: Dict[str, Any]
    ) -> bool:
        condition_type = single_condition_spec.get("type")
        capture_as_var_name = single_condition_spec.get("capture_as")
        if not condition_type:
            logger.error(f"R '{rule_name_for_context}', Rgn '{region_name}': Cond 'type' missing.")
            return False
        logger.debug(f"R '{rule_name_for_context}', Rgn '{region_name}': Eval single cond type '{condition_type}'. Spec: {single_condition_spec}")

        captured_image = region_data.get("image")
        condition_met = False
        captured_value_for_var: Any = None # Allow any type for capture

        def get_analysis_data_with_fallback(data_key: str, analysis_func: Callable, *args_for_analysis_func) -> Any:
            data = region_data.get(data_key)
            if data is None and captured_image is not None:
                logger.warning(f"R '{rule_name_for_context}', Rgn '{region_name}', T '{condition_type}': Data for '{data_key}' not pre-analyzed. Fallback: Recalculating.")
                try:
                    data = analysis_func(*args_for_analysis_func)
                except Exception as e_fb:
                    logger.error(f"R '{rule_name_for_context}', Fallback calc for '{data_key}' failed: {e_fb}")
                    data = None
            elif data is None and captured_image is None:
                logger.warning(f"R '{rule_name_for_context}', Rgn '{region_name}', T '{condition_type}': Data for '{data_key}' not pre-analyzed AND no image for fallback.")
            return data

        try:
            if condition_type == "pixel_color":
                if captured_image is None:
                    logger.warning(f"R '{rule_name_for_context}', T 'pixel_color': Image is None.")
                    return False
                rx = single_condition_spec.get("relative_x")
                ry = single_condition_spec.get("relative_y")
                ebgr = single_condition_spec.get("expected_bgr")
                tol = single_condition_spec.get("tolerance", 0)
                if not all(isinstance(v, int) for v in [rx, ry]) or not (isinstance(ebgr, list) and len(ebgr) == 3 and all(isinstance(c, int) for c in ebgr)):
                    logger.error(f"R '{rule_name_for_context}',T 'pixel_color': Invalid params.")
                    return False
                condition_met = self.analysis_engine.analyze_pixel_color(captured_image, rx, ry, ebgr, tol)


            elif condition_type == "average_color_is":
                avg_color_data = get_analysis_data_with_fallback("average_color", self.analysis_engine.analyze_average_color, captured_image)
                if avg_color_data is None:
                    return False
                ebgr = single_condition_spec.get("expected_bgr")
                tol = single_condition_spec.get("tolerance", 10)
                if not (isinstance(ebgr, list) and len(ebgr) == 3 and all(isinstance(c, int) for c in ebgr)):
                    logger.error(f"R '{rule_name_for_context}',T 'avg_color': Invalid expected_bgr.")
                    return False
                c_diff = np.abs(np.array(avg_color_data) - np.array(ebgr))
                condition_met = np.all(c_diff <= tol)
                logger.debug(f"R '{rule_name_for_context}', T 'avg_color': Avg {avg_color_data}, Exp {ebgr}, Tol {tol}. Met: {condition_met}")

            elif condition_type == "template_match_found":
                if captured_image is None:
                    logger.warning(f"R '{rule_name_for_context}', T 'template': Image is None.")
                    return False
                tpl_fn = single_condition_spec.get("template_filename")
                min_conf = single_condition_spec.get("min_confidence", 0.8)
                if not tpl_fn:
                    logger.error(f"R '{rule_name_for_context}',T 'template': Missing filename.")
                    return False
                tpl_img = self._load_template_image_for_rule(tpl_fn, rule_name_for_context)
                if tpl_img is None:
                    return False
                match_res = self.analysis_engine.match_template(captured_image, tpl_img, min_conf)
                if match_res:
                    condition_met = True
                    self._last_template_match_info = {"found": True, **match_res, "matched_region_name": region_name}
                    logger.info(f"R '{rule_name_for_context}',T 'template':'{tpl_fn}' FOUND conf {match_res['confidence']:.2f}.")
                    if capture_as_var_name:
                        captured_value_for_var = {
                            "x": match_res["location"][0],
                            "y": match_res["location"][1],
                            "width": match_res["width"],
                            "height": match_res["height"],
                            "confidence": match_res["confidence"],
                        }
                else:
                    self._last_template_match_info = {"found": False}
                    condition_met = False
                    logger.debug(f"R '{rule_name_for_context}',T 'template':'{tpl_fn}' NOT found.")

            elif condition_type == "ocr_contains_text":
                ocr_res = get_analysis_data_with_fallback("ocr_analysis_result", self.analysis_engine.ocr_extract_text, captured_image, region_name)
                if not ocr_res or "text" not in ocr_res: # Check if ocr_res itself is None or if "text" key is missing
                    logger.warning(f"R '{rule_name_for_context}',T 'ocr': OCR result missing or invalid for region '{region_name}'.")
                    return False
                
                actual_txt = ocr_res.get("text", "")
                actual_conf = ocr_res.get("average_confidence", 0.0)
                
                # text_to_find can be a string (single keyword) or list of strings (keywords from JSON)
                # GUI config for entry implies comma-separated for multiple values.
                txts_check_param = single_condition_spec.get("text_to_find")
                txts_check: List[str] = []
                if isinstance(txts_check_param, str):
                    txts_check = [s.strip() for s in txts_check_param.split(',') if s.strip()]
                elif isinstance(txts_check_param, list): # Already a list from JSON
                    txts_check = [str(s).strip() for s in txts_check_param if str(s).strip()]
                
                if not txts_check: # If after processing, list is empty
                    logger.error(f"R '{rule_name_for_context}',T 'ocr': 'text_to_find' is missing or resolved to empty list of keywords.")
                    return False

                cs = single_condition_spec.get("case_sensitive", False)
                min_ocr_conf_str = single_condition_spec.get("min_ocr_confidence") # GUI sends as string via entry
                min_ocr_conf: Optional[float] = None
                if min_ocr_conf_str is not None and str(min_ocr_conf_str).strip(): # Check if not None and not empty string
                    try:
                        min_ocr_conf = float(min_ocr_conf_str)
                    except ValueError:
                        logger.warning(f"R '{rule_name_for_context}',T 'ocr': Invalid min_ocr_confidence value '{min_ocr_conf_str}'. Confidence check skipped.")
                
                proc_ocr_txt = actual_txt if cs else actual_txt.lower()
                txt_match = False
                for ti_orig in txts_check:
                    proc_ti = ti_orig if cs else ti_orig.lower()
                    if proc_ti in proc_ocr_txt:
                        txt_match = True
                        break # Found one keyword, text_match is True
                
                if not txt_match:
                    ocr_txt_snippet = proc_ocr_txt[:100].replace(os.linesep, ' ') + ('...' if len(proc_ocr_txt) > 100 else '')
                    logger.debug(f"R '{rule_name_for_context}',OCR: Keywords '{txts_check}' NOT found in '{ocr_txt_snippet}' (FullConf:{actual_conf:.1f}%).")
                    return False # No need to check confidence if text not found
                
                # Text found, now check confidence if specified
                conf_crit_met = True
                if min_ocr_conf is not None: # Ensure it's not None before comparing
                    conf_crit_met = actual_conf >= min_ocr_conf
                
                if conf_crit_met:
                    condition_met = True
                    logger.info(f"R '{rule_name_for_context}',OCR:MET. Keywords '{txts_check}' found (Conf:{actual_conf:.1f}%).")
                    if capture_as_var_name: # Capture full original text if condition met
                        captured_value_for_var = actual_txt 
                else: # Text found, but confidence not met
                    condition_met = False # Ensure condition_met is false
                    logger.info(f"R '{rule_name_for_context}',OCR:NOT MET. Text found, but conf {actual_conf:.1f}% < {min_ocr_conf}%.")


            elif condition_type == "dominant_color_matches":
                dom_color_res = get_analysis_data_with_fallback(
                    "dominant_colors_result", self.analysis_engine.analyze_dominant_colors, captured_image, self.config_manager.get_setting("analysis_dominant_colors_k", 3), region_name
                )
                if not dom_color_res:
                    return False
                ebgr = single_condition_spec.get("expected_bgr")
                tol = single_condition_spec.get("tolerance", 10)
                top_n = single_condition_spec.get("check_top_n_dominant", 1)
                min_perc = single_condition_spec.get("min_percentage", 0.0)
                if not ebgr:
                    logger.error(f"R '{rule_name_for_context}',T DomColor:Missing expected_bgr.")
                    return False
                n_check = min(top_n, len(dom_color_res))
                if n_check == 0 and top_n > 0: # If dom_color_res was empty but top_n > 0
                    logger.debug(f"R '{rule_name_for_context}',T DomColor:No dominant colors returned from analysis to check.")
                    return False
                for i in range(n_check):
                    dci = dom_color_res[i]
                    act_bgr, act_p = dci["bgr_color"], dci["percentage"]
                    cmatch = np.all(np.abs(np.array(act_bgr) - np.array(ebgr)) <= tol)
                    pmatch = act_p >= min_perc
                    logger.debug(f"R '{rule_name_for_context}',DomColorChk#{i+1}:Actual {act_bgr}(Perc {act_p:.1f}%).Exp {ebgr}.CMatch:{cmatch}.PMatch:{pmatch}.")
                    if cmatch and pmatch:
                        condition_met = True
                        logger.info(f"R '{rule_name_for_context}',T DomColor:MET.Dom BGR {act_bgr}(Perc {act_p:.1f}%) matched.")
                        break
                if not condition_met: # Only log if loop finished without a match
                    logger.info(f"R '{rule_name_for_context}',T DomColor:NOT MET after checking top {n_check} colors.")

            elif condition_type == "gemini_vision_query":
                if self.gemini_analyzer is None:
                    logger.error(f"R '{rule_name_for_context}', T 'gemini_vision_query': GeminiAnalyzer is not available (e.g., API key missing/invalid). Condition fails.")
                    return False
                if captured_image is None:
                    logger.warning(f"R '{rule_name_for_context}', T 'gemini_vision_query': Image for region '{region_name}' is None. Condition fails.")
                    return False

                prompt = single_condition_spec.get("prompt")
                if not prompt:
                    logger.error(f"R '{rule_name_for_context}', T 'gemini_vision_query': 'prompt' parameter is missing or empty. Condition fails.")
                    return False

                model_override = single_condition_spec.get("model_name") # Optional
                gemini_response = self.gemini_analyzer.query_vision_model(captured_image, prompt, model_name=model_override)

                if gemini_response["status"] != "success":
                    logger.warning(
                        f"R '{rule_name_for_context}', T 'gemini_vision_query': API call failed or blocked. "
                        f"Status: {gemini_response['status']}. Error: {gemini_response['error_message']}. Condition fails."
                    )
                    return False # API call itself failed or was blocked

                # API call successful, now evaluate expectations
                response_text = gemini_response.get("text_content", "") if gemini_response.get("text_content") is not None else ""
                response_json_obj = gemini_response.get("json_content") # This is already a Python dict/list if parsed

                # 1. Check expected_response_contains (text content)
                expected_substrings_param = single_condition_spec.get("expected_response_contains")
                case_sensitive = single_condition_spec.get("case_sensitive_response_check", False)
                
                substrings_to_check: List[str] = []
                if isinstance(expected_substrings_param, str):
                    substrings_to_check = [s.strip() for s in expected_substrings_param.split(',') if s.strip()]
                elif isinstance(expected_substrings_param, list):
                    substrings_to_check = [str(s).strip() for s in expected_substrings_param if str(s).strip()]

                text_check_met = True # If no substrings specified, this check passes by default
                if substrings_to_check: # Only perform check if there are substrings to find
                    text_check_met = False # Assume not met until a substring is found
                    text_to_search_in = response_text if case_sensitive else response_text.lower()
                    for sub in substrings_to_check:
                        processed_sub = sub if case_sensitive else sub.lower()
                        if processed_sub in text_to_search_in:
                            text_check_met = True
                            logger.info(f"R '{rule_name_for_context}', GeminiQuery: Found keyword '{sub}' in text response.")
                            break # Found one, no need to check others for this part
                    if not text_check_met:
                         logger.info(f"R '{rule_name_for_context}', GeminiQuery: Keywords '{substrings_to_check}' not found in text response '{text_to_search_in[:100].replace(os.linesep, ' ')}...'.")
                
                # 2. Check expected_response_json_path and expected_json_value (basic dot notation)
                json_path_str = single_condition_spec.get("expected_response_json_path")
                expected_json_val_str = str(single_condition_spec.get("expected_json_value", "")) # Compare as string for simplicity

                json_check_met = True # If no JSON path specified, this check passes by default
                extracted_json_value_for_capture: Any = None

                if json_path_str and response_json_obj is not None: # Only if path specified and JSON content exists
                    json_check_met = False # Assume not met
                    try:
                        current_val = response_json_obj
                        keys = json_path_str.strip(".").split(".")
                        valid_path = True
                        for key_part in keys:
                            if isinstance(current_val, dict) and key_part in current_val:
                                current_val = current_val[key_part]
                            elif isinstance(current_val, list) and key_part.isdigit() and 0 <= int(key_part) < len(current_val):
                                current_val = current_val[int(key_part)]
                            else:
                                logger.warning(f"R '{rule_name_for_context}', GeminiQuery: JSON path '{json_path_str}' part '{key_part}' not found or invalid index in JSON response.")
                                valid_path = False
                                break
                        if valid_path:
                            extracted_json_value_for_capture = current_val # Store the actual typed value
                            actual_json_val_str = str(current_val)
                            # Perform comparison if expected_json_value was actually provided (not empty default from config)
                            if str(single_condition_spec.get("expected_json_value")) : # Check original spec value
                                if actual_json_val_str == expected_json_val_str: # Simple string comparison for phase 1
                                    json_check_met = True
                                    logger.info(f"R '{rule_name_for_context}', GeminiQuery: JSON path '{json_path_str}' value '{actual_json_val_str}' matched expected '{expected_json_val_str}'.")
                                else:
                                    logger.info(f"R '{rule_name_for_context}', GeminiQuery: JSON path '{json_path_str}' value '{actual_json_val_str}' DID NOT match expected '{expected_json_val_str}'.")
                            else: # No expected_json_value was specified, so path existing is enough
                                json_check_met = True
                                logger.info(f"R '{rule_name_for_context}', GeminiQuery: JSON path '{json_path_str}' found. No specific value check requested.")
                        # else: json_check_met remains False if path was invalid
                    except Exception as e_json_path:
                        logger.warning(f"R '{rule_name_for_context}', GeminiQuery: Error accessing JSON path '{json_path_str}': {e_json_path}. Check JSON structure and path syntax.")
                        # json_check_met remains False
                elif json_path_str and response_json_obj is None:
                     logger.warning(f"R '{rule_name_for_context}', GeminiQuery: JSON path '{json_path_str}' specified, but Gemini response did not contain parsable JSON content.")
                     json_check_met = False # Cannot meet condition if no JSON to check

                # Combine checks: for gemini_vision_query, ALL specified checks must pass.
                if not substrings_to_check and not json_path_str: # No specific content checks requested
                    condition_met = True # Successful API call is enough
                    logger.info(f"R '{rule_name_for_context}', GeminiQuery: Condition met (successful API call, no specific content checks requested).")
                elif text_check_met and json_check_met:
                    condition_met = True
                    logger.info(f"R '{rule_name_for_context}', GeminiQuery: Condition met (all specified content checks passed).")
                else: # One of the specified checks failed
                    condition_met = False
                    logger.info(f"R '{rule_name_for_context}', GeminiQuery: Condition NOT met (one or more specified content checks failed. Text check: {text_check_met}, JSON check: {json_check_met}).")

                # Handle capture_as
                if condition_met and capture_as_var_name:
                    if json_path_str and extracted_json_value_for_capture is not None:
                        # If JSON path was used and value extracted, prioritize that for capture
                        captured_value_for_var = extracted_json_value_for_capture
                    else:
                        # Otherwise, capture the full text response
                        captured_value_for_var = response_text
                    logger.info(f"R '{rule_name_for_context}', GeminiQuery: Capturing result as '{capture_as_var_name}'.")


            elif condition_type == "always_true":
                condition_met = True
                logger.debug(f"R '{rule_name_for_context}', T 'always_true': Met.")
            else:
                logger.error(f"R '{rule_name_for_context}', Rgn '{region_name}': Unknown cond type '{condition_type}'.")
                return False

            # General capture logic after condition_met is determined and captured_value_for_var might be set
            if condition_met and capture_as_var_name and captured_value_for_var is not None:
                variable_context[capture_as_var_name] = captured_value_for_var
                val_snip = str(captured_value_for_var)
                val_snip = (val_snip[:67] + "...") if len(val_snip) > 70 else val_snip
                val_snip_log = val_snip.replace(os.linesep, ' ') # Ensure no newlines in log snippet
                logger.info(f"R '{rule_name_for_context}', Capture: Var '{capture_as_var_name}'. Snippet: '{val_snip_log}'")
                logger.debug(f"R '{rule_name_for_context}', Capture: Full value for '{capture_as_var_name}': {captured_value_for_var}")
            elif condition_met and capture_as_var_name and captured_value_for_var is None and condition_type not in ["template_match_found", "ocr_contains_text", "gemini_vision_query"]:
                 # Log if capture_as was specified but no value was explicitly set for capture by the condition type's logic
                logger.warning(f"R '{rule_name_for_context}', Capture: `capture_as` specified for condition type '{condition_type}' but no value was set for capture.")


        except Exception as e:
            logger.exception(f"R '{rule_name_for_context}', Rgn '{region_name}', T '{condition_type}': Exception: {e}")
            return False

        logger.info(f"R '{rule_name_for_context}', Rgn '{region_name}', SingleCond '{condition_type}': Result = {condition_met}")
        return condition_met

    def _check_condition(
        self, rule_name: str, condition_spec: Dict[str, Any], default_rule_region_from_rule: Optional[str], all_region_data: Dict[str, Dict[str, Any]], variable_context: Dict[str, Any]
    ) -> bool:
        logger.debug(f"R '{rule_name}': Start cond eval. Orig Spec: {condition_spec}")
        logical_operator_str = condition_spec.get("logical_operator")
        sub_conditions_original = condition_spec.get("sub_conditions")
        
        if logical_operator_str and isinstance(sub_conditions_original, list):
            operator = logical_operator_str.upper()
            if operator not in ["AND", "OR"]:
                logger.error(f"R '{rule_name}': Invalid op '{logical_operator_str}'.")
                return False
            if not sub_conditions_original:
                logger.warning(f"R '{rule_name}': Compound op '{operator}' no subs. False.")
                return False
            logger.info(f"R '{rule_name}': Compound op '{operator}', {len(sub_conditions_original)} subs.")
            all_sub_results = []
            for i, sub_cond_orig_spec in enumerate(sub_conditions_original):
                ctx_name = f"{rule_name}/Sub#{i+1}"
                logger.debug(f"R '{ctx_name}': Orig sub-cond spec: {sub_cond_orig_spec}")
                
                # Substitute variables in the sub-condition spec *before* determining its region
                sub_cond_spec_subst = self._substitute_variables(sub_cond_orig_spec, variable_context, ctx_name)
                logger.debug(f"R '{ctx_name}': Subst sub-cond spec: {sub_cond_spec_subst}")

                # Determine target region for this sub-condition
                # A sub-condition can override the rule's default region
                sub_cond_target_region_name = sub_cond_spec_subst.get("region", default_rule_region_from_rule)
                
                if not sub_cond_target_region_name:
                    logger.error(f"R '{ctx_name}': Region not specified for sub-condition and no rule default. Spec: {sub_cond_spec_subst}")
                    sub_result = False
                elif sub_cond_target_region_name not in all_region_data:
                    logger.error(f"R '{ctx_name}': Region '{sub_cond_target_region_name}' for sub-condition not in all_region_data (keys: {list(all_region_data.keys())}).")
                    sub_result = False
                else:
                    target_region_data_for_sub = all_region_data[sub_cond_target_region_name]
                    sub_result = self._evaluate_single_condition_logic(sub_cond_spec_subst, sub_cond_target_region_name, target_region_data_for_sub, ctx_name, variable_context)
                
                all_sub_results.append(sub_result)
                if operator == "AND" and not sub_result:
                    logger.info(f"R '{rule_name}': AND short-circuited False by Sub#{i+1}.")
                    return False
                if operator == "OR" and sub_result:
                    logger.info(f"R '{rule_name}': OR short-circuited True by Sub#{i+1}.")
                    return True
            
            final_res = all(all_sub_results) if operator == "AND" else any(all_sub_results)
            logger.info(f"R '{rule_name}': Compound cond final result = {final_res}.")
            return final_res
        else: # Single condition
            condition_spec_subst = self._substitute_variables(condition_spec, variable_context, rule_name)
            logger.debug(f"R '{rule_name}': Subst single cond spec: {condition_spec_subst}")

            # Determine target region for this single condition
            # A single condition can also have its own "region" param, overriding rule's default.
            single_cond_target_region_name = condition_spec_subst.get("region", default_rule_region_from_rule)

            if not single_cond_target_region_name:
                logger.error(f"R '{rule_name}': Single cond, no region specified and no rule default. Spec: {condition_spec_subst}")
                return False
            if single_cond_target_region_name not in all_region_data:
                logger.error(f"R '{rule_name}': Target region '{single_cond_target_region_name}' for single condition not in all_region_data (keys: {list(all_region_data.keys())}).")
                return False
            
            target_region_data_for_single = all_region_data[single_cond_target_region_name]
            result = self._evaluate_single_condition_logic(condition_spec_subst, single_cond_target_region_name, target_region_data_for_single, rule_name, variable_context)
            return result

    def evaluate_rules(self, all_region_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        triggered_actions_specs = []
        if not self.rules:
            logger.debug("No rules to evaluate.")
            return triggered_actions_specs
        logger.info(f"Starting evaluation of {len(self.rules)} rules.")
        for rule in self.rules:
            rule_name = rule.get("name", "UnnamedRule")
            original_condition_spec = rule.get("condition")
            original_action_spec = rule.get("action")
            default_rule_region = rule.get("region") # This is the rule's default region
            if not original_condition_spec or not original_action_spec:
                logger.warning(f"R '{rule_name}': Missing cond/action. Skipping.")
                continue
            self._last_template_match_info = {"found": False}
            rule_variable_context: Dict[str, Any] = {}
            logger.debug(f"Evaluating rule: '{rule_name}' with rule's default region '{default_rule_region}'")
            try:
                condition_is_met = self._check_condition(rule_name, original_condition_spec, default_rule_region, all_region_data, rule_variable_context)
                if condition_is_met:
                    logger.info(f"R '{rule_name}': Overall Condition MET. Preparing action: {original_action_spec.get('type')}")
                    logger.debug(f"R '{rule_name}', Action Prep: Orig action spec: {original_action_spec}. Variables: {rule_variable_context}")
                    action_spec_subst = self._substitute_variables(original_action_spec, rule_variable_context, f"{rule_name}/Action")
                    logger.debug(f"R '{rule_name}', Action Prep: Subst action spec: {action_spec_subst}")
                    
                    action_context = {
                        "rule_name": rule_name,
                        "condition_region": default_rule_region, 
                        "last_match_info": self._last_template_match_info.copy(),
                        "variables": rule_variable_context.copy(),
                    }
                    
                    full_action_to_execute = {**action_spec_subst, "context": action_context}
                    triggered_actions_specs.append(full_action_to_execute)
                    self.action_executor.execute_action(full_action_to_execute)
            except Exception as e:
                logger.exception(f"R '{rule_name}': Unexpected error during rule eval/action prep: {e}")
        logger.info(f"Finished rule evaluation. {len(triggered_actions_specs)} actions were triggered in this cycle.")
        return triggered_actions_specs