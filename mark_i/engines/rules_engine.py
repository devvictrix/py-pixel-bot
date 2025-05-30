import logging
import os  # For os.linesep in log formatting and path joining
import re  # For variable substitution regex
from typing import Dict, List, Any, Optional, Tuple, Set, Callable  # Standard typing imports
from collections import defaultdict  # For _analysis_requirements_per_region

import cv2  # For image operations if any (e.g. loading templates)
import numpy as np  # For image data type

from mark_i.core.config_manager import ConfigManager
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_analyzer import GeminiAnalyzer  # For gemini_vision_query
from mark_i.engines.gemini_decision_module import GeminiDecisionModule  # For gemini_perform_task

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.rules_engine")

# Regex for finding placeholders like {var_name} or {var_name.key1.0.key2}
PLACEHOLDER_REGEX = re.compile(r"\{([\w_]+)((\.?[\w_]+)*(\.\d+)*)*\}")  # Allows more complex paths
TEMPLATES_SUBDIR_NAME = "templates"  # Standard subdirectory for template images


class RulesEngine:
    """
    Evaluates rules defined in a profile based on visual analysis data and triggers actions.
    Supports single conditions, compound conditions (AND/OR logic), rule-scoped
    variable capture, and placeholder substitution in action parameters.

    Integrates with:
    - `AnalysisEngine` for local visual checks.
    - `GeminiAnalyzer` for AI-powered `gemini_vision_query` conditions.
    - `GeminiDecisionModule` for executing AI-driven `gemini_perform_task` actions (NLU).
    - `ActionExecutor` for performing standard UI interaction actions.
    """

    def __init__(
        self, config_manager: ConfigManager, analysis_engine: AnalysisEngine, action_executor: ActionExecutor, gemini_decision_module: Optional[GeminiDecisionModule] = None  # For NLU tasks
    ):
        """
        Initializes the RulesEngine.

        Args:
            config_manager: Instance of ConfigManager for accessing profile data.
            analysis_engine: Instance of AnalysisEngine for local visual analysis.
            action_executor: Instance of ActionExecutor for performing standard actions.
            gemini_decision_module: Optional instance of GeminiDecisionModule for
                                    handling 'gemini_perform_task' actions.
        """
        if not isinstance(config_manager, ConfigManager):
            raise ValueError("RulesEngine requires a valid ConfigManager instance.")
        if not isinstance(analysis_engine, AnalysisEngine):
            raise ValueError("RulesEngine requires a valid AnalysisEngine instance.")
        if not isinstance(action_executor, ActionExecutor):
            raise ValueError("RulesEngine requires a valid ActionExecutor instance.")

        self.config_manager = config_manager
        self.analysis_engine = analysis_engine
        self.action_executor = action_executor
        self.gemini_decision_module = gemini_decision_module  # Store instance

        self.profile_data = self.config_manager.get_profile_data()  # Get a copy
        self.rules: List[Dict[str, Any]] = self.profile_data.get("rules", [])

        # Cache for loaded template images { (profile_base_path, template_filename): np.ndarray | None }
        self._loaded_templates: Dict[Tuple[str, str], Optional[np.ndarray]] = {}
        # Stores info from the last successful template match within a single rule's condition evaluation
        self._last_template_match_info: Dict[str, Any] = {"found": False}

        # Determines which local, general analyses (OCR, dominant color, avg color)
        # are needed per region based on all rules in the profile.
        self._analysis_requirements_per_region: Dict[str, Set[str]] = defaultdict(set)
        self._parse_rule_analysis_dependencies()

        # Initialize GeminiAnalyzer specifically for `gemini_vision_query` conditions handled by RulesEngine
        gemini_api_key_from_env = os.getenv("GEMINI_API_KEY")
        default_gemini_model_from_settings = self.config_manager.get_setting("gemini_default_model_name", "gemini-1.5-flash-latest")

        self.gemini_analyzer_for_query: Optional[GeminiAnalyzer] = None
        if gemini_api_key_from_env:
            self.gemini_analyzer_for_query = GeminiAnalyzer(api_key=gemini_api_key_from_env, default_model_name=default_gemini_model_from_settings)
            if not self.gemini_analyzer_for_query.client_initialized:
                logger.warning("RulesEngine: GeminiAnalyzer (for vision query conditions) failed API client initialization. `gemini_vision_query` conditions will likely fail.")
                self.gemini_analyzer_for_query = None  # Ensure it's None if unusable
            else:
                logger.info(f"RulesEngine: GeminiAnalyzer (for vision query conditions) enabled. Default model: '{default_gemini_model_from_settings}'")
        else:
            logger.warning("RulesEngine: GEMINI_API_KEY not found in environment. `gemini_vision_query` conditions will be disabled or fail.")

        if self.gemini_decision_module:
            logger.info("RulesEngine: GeminiDecisionModule integration is active for 'gemini_perform_task' actions.")
        else:
            logger.warning("RulesEngine: GeminiDecisionModule not provided or failed to initialize. 'gemini_perform_task' (NLU) actions will be skipped or fail.")

        if not self.rules:
            logger.warning("RulesEngine: No rules found in the loaded profile. The bot might not perform any actions based on rules.")
        else:
            logger.info(f"RulesEngine initialized successfully with {len(self.rules)} rules.")
            if self._analysis_requirements_per_region:
                logger.debug(f"RulesEngine: Determined local pre-emptive analysis requirements: {dict(self._analysis_requirements_per_region)}")
            else:
                logger.debug("RulesEngine: No pre-emptive local analyses required by any rule.")

    def _parse_rule_analysis_dependencies(self):
        logger.debug("RulesEngine: Parsing rule analysis dependencies for pre-emptive local analyses...")
        if not self.rules:
            return

        for i, rule in enumerate(self.rules):
            rule_name = rule.get("name", f"RuleIdx{i}")
            default_rule_region = rule.get("region")
            condition_spec_outer = rule.get("condition")
            if not isinstance(condition_spec_outer, dict):
                continue

            conditions_to_parse: List[Tuple[Dict[str, Any], Optional[str]]] = []
            # Check for compound condition structure first
            if "logical_operator" in condition_spec_outer and isinstance(condition_spec_outer.get("sub_conditions"), list):
                for sub_cond in condition_spec_outer["sub_conditions"]:
                    if isinstance(sub_cond, dict):
                        # Region for sub-condition can be its own, or rule's default, or None if not specified at all
                        sub_cond_region = sub_cond.get("region", default_rule_region)
                        conditions_to_parse.append((sub_cond, sub_cond_region))
            elif "type" in condition_spec_outer:  # Single condition
                # Region for single condition can be its own, or rule's default, or None
                single_cond_region = condition_spec_outer.get("region", default_rule_region)
                conditions_to_parse.append((condition_spec_outer, single_cond_region))
            # Else: malformed condition block, skip for dependency parsing

            for cond_spec, target_rgn in conditions_to_parse:
                cond_type = cond_spec.get("type")
                local_analysis_needed: Optional[str] = None
                if cond_type == "ocr_contains_text":
                    local_analysis_needed = "ocr"
                elif cond_type == "dominant_color_matches":
                    local_analysis_needed = "dominant_color"
                elif cond_type == "average_color_is":
                    local_analysis_needed = "average_color"

                if local_analysis_needed and target_rgn and isinstance(target_rgn, str):
                    self._analysis_requirements_per_region[target_rgn].add(local_analysis_needed)
                    # logger.debug(f"Dependency: Rule '{rule_name}', CondType '{cond_type}', Region '{target_rgn}' -> Requires Local '{local_analysis_needed}'")
        # logger.info(f"RulesEngine: Local analysis dependency parsing complete.")

    def get_analysis_requirements_for_region(self, region_name: str) -> Set[str]:
        return self._analysis_requirements_per_region.get(region_name, set())

    def _load_template_image_for_rule(self, template_filename: str, rule_name_for_context: str) -> Optional[np.ndarray]:
        profile_base = self.config_manager.get_profile_base_path()
        if not profile_base:
            logger.error(f"R '{rule_name_for_context}': Cannot load template '{template_filename}', profile is unsaved (no base path available).")
            return None

        cache_key = (profile_base, template_filename)  # Use tuple as dict key
        if cache_key in self._loaded_templates:
            return self._loaded_templates[cache_key]  # Return cached image (or None if load failed previously)

        full_path = os.path.join(profile_base, TEMPLATES_SUBDIR_NAME, template_filename)
        if not os.path.exists(full_path):
            logger.error(f"R '{rule_name_for_context}': Template image file not found at path: '{full_path}'.")
            self._loaded_templates[cache_key] = None  # Cache failure
            return None

        try:
            img = cv2.imread(full_path, cv2.IMREAD_COLOR)  # Load as BGR
            if img is None:
                raise ValueError("cv2.imread returned None, file might be corrupted or not a supported image format.")
            logger.info(f"R '{rule_name_for_context}': Successfully loaded template '{template_filename}' from '{full_path}' (Shape: {img.shape}).")
            self._loaded_templates[cache_key] = img
            return img
        except Exception as e:
            logger.exception(f"R '{rule_name_for_context}': Error loading template image '{full_path}': {e}")
            self._loaded_templates[cache_key] = None  # Cache failure
            return None

    def _substitute_variables(self, input_value: Any, variable_context: Dict[str, Any], log_context_prefix: str) -> Any:
        if not isinstance(input_value, (str, list, dict)):
            return input_value
        if not variable_context:
            return input_value  # No variables to substitute

        if isinstance(input_value, str):

            def replace_match(match_obj: re.Match) -> str:
                full_placeholder, var_name, dot_path_full, _dot_path_keys, _dot_path_indices = match_obj.groups()
                # logger.debug(f"{log_context_prefix}, Subst: Placeholder='{full_placeholder}', Var='{var_name}', Path='{dot_path_full or ''}'")
                if var_name in variable_context:
                    current_val = variable_context[var_name]  # This should be the wrapped dict {"value": data, "_source_region_for_capture_":...}

                    # Resolve dot path if present
                    if dot_path_full:
                        path_keys = dot_path_full.strip(".").split(".")
                        # If the first part of path is "value", start from the inner value
                        if path_keys[0] == "value" and isinstance(current_val, dict) and "value" in current_val:
                            resolved_val = current_val["value"]
                            remaining_path_keys = path_keys[1:]
                        else:  # Path does not start with .value, or var_name itself IS the value (e.g. simple capture)
                            resolved_val = current_val  # Assume current_val is the data structure to navigate
                            remaining_path_keys = path_keys

                        try:
                            for key_part in remaining_path_keys:
                                if isinstance(resolved_val, dict):
                                    resolved_val = resolved_val[key_part]
                                elif isinstance(resolved_val, list) and key_part.isdigit():
                                    resolved_val = resolved_val[int(key_part)]
                                else:  # Cannot navigate further
                                    logger.warning(f"{log_context_prefix}, Subst: Cannot access '{key_part}' in '{var_name}'. Path: '{dot_path_full}'. Placeholder left.")
                                    return full_placeholder
                            return str(resolved_val)
                        except (KeyError, IndexError, TypeError) as e:
                            logger.warning(f"{log_context_prefix}, Subst: Path resolution error for '{var_name}{dot_path_full}': {e}. Placeholder left.")
                            return full_placeholder
                    else:  # No dot path, just {var_name}
                        # If var_name directly holds a simple value (not a dict with "value"), return it.
                        # Otherwise, if it's the wrapped structure, default to its "value" field.
                        if isinstance(current_val, dict) and "value" in current_val:
                            return str(current_val["value"])
                        return str(current_val)

                logger.warning(f"{log_context_prefix}, Subst: Variable '{var_name}' not in context. Placeholder '{full_placeholder}' left.")
                return full_placeholder

            return PLACEHOLDER_REGEX.sub(replace_match, input_value)
        elif isinstance(input_value, list):
            return [self._substitute_variables(item, variable_context, log_context_prefix) for item in input_value]
        elif isinstance(input_value, dict):
            return {k: self._substitute_variables(v, variable_context, log_context_prefix) for k, v in input_value.items()}
        return input_value  # Should not be reached

    def _evaluate_single_condition_logic(
        self, single_condition_spec: Dict[str, Any], region_name: str, region_data: Dict[str, Any], rule_name_for_context: str, variable_context: Dict[str, Any]
    ) -> bool:
        condition_type = single_condition_spec.get("type")
        capture_as = single_condition_spec.get("capture_as")
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond '{condition_type}'"
        if not condition_type:
            logger.error(f"{log_prefix}: 'type' missing in condition spec.")
            return False

        image_np_bgr = region_data.get("image")  # Image is BGR NumPy array or None
        condition_met = False
        captured_value_for_context: Any = None  # Value to be stored if capture_as is set

        def get_pre_analyzed_data(key_name: str, analysis_func: Callable, *args_for_func):
            """Helper to get pre-analyzed data or call analysis_func on demand."""
            data = region_data.get(key_name)
            if data is None and image_np_bgr is not None:  # Image exists but data not pre-analyzed
                try:
                    data = analysis_func(*args_for_func)
                except Exception as e_analysis:
                    logger.error(f"{log_prefix}: On-demand analysis for '{key_name}' failed: {e_analysis}", exc_info=True)
                    data = None
            return data

        try:
            if condition_type == "pixel_color":
                rel_x, rel_y = single_condition_spec.get("relative_x", 0), single_condition_spec.get("relative_y", 0)
                exp_bgr = single_condition_spec.get("expected_bgr")
                tol = single_condition_spec.get("tolerance", 0)
                if image_np_bgr is not None and exp_bgr is not None:
                    condition_met = self.analysis_engine.analyze_pixel_color(image_np_bgr, rel_x, rel_y, exp_bgr, tol, rule_name_for_context)

            elif condition_type == "average_color_is":
                avg_color_data = get_pre_analyzed_data("average_color", self.analysis_engine.analyze_average_color, image_np_bgr, rule_name_for_context)
                exp_bgr = single_condition_spec.get("expected_bgr")
                tol = single_condition_spec.get("tolerance", 10)
                if avg_color_data is not None and exp_bgr is not None:
                    condition_met = np.all(np.abs(np.array(avg_color_data) - np.array(exp_bgr)) <= tol)

            elif condition_type == "template_match_found":
                tpl_filename = single_condition_spec.get("template_filename")
                min_conf = float(single_condition_spec.get("min_confidence", 0.8))
                if image_np_bgr is not None and tpl_filename:
                    template_image_np = self._load_template_image_for_rule(tpl_filename, rule_name_for_context)
                    if template_image_np is not None:
                        match_result = self.analysis_engine.match_template(image_np_bgr, template_image_np, min_conf, rule_name_for_context, tpl_filename)
                        if match_result:
                            condition_met = True
                            self._last_template_match_info = {"found": True, **match_result, "matched_region_name": region_name}
                            if capture_as:
                                captured_value_for_context = {"value": match_result, "_source_region_for_capture_": region_name}
                        else:
                            self._last_template_match_info = {"found": False}  # Reset if no match this time

            elif condition_type == "ocr_contains_text":
                ocr_analysis_data = get_pre_analyzed_data("ocr_analysis_result", self.analysis_engine.ocr_extract_text, image_np_bgr, rule_name_for_context)
                if ocr_analysis_data and "text" in ocr_analysis_data:
                    ocr_text, ocr_confidence = ocr_analysis_data.get("text", ""), ocr_analysis_data.get("average_confidence", 0.0)
                    text_to_find_param = single_condition_spec.get("text_to_find")
                    case_sensitive_search = single_condition_spec.get("case_sensitive", False)
                    min_ocr_conf_str = single_condition_spec.get("min_ocr_confidence")

                    texts_to_find_list = (
                        [s.strip() for s in text_to_find_param.split(",")]
                        if isinstance(text_to_find_param, str)
                        else [str(s).strip() for s in text_to_find_param] if isinstance(text_to_find_param, list) else []
                    )
                    min_ocr_conf_float = float(min_ocr_conf_str) if min_ocr_conf_str and str(min_ocr_conf_str).strip() else None

                    if texts_to_find_list:
                        processed_ocr_text = ocr_text if case_sensitive_search else ocr_text.lower()
                        text_match_found = any((s_find if case_sensitive_search else s_find.lower()) in processed_ocr_text for s_find in texts_to_find_list)
                        if text_match_found and (min_ocr_conf_float is None or ocr_confidence >= min_ocr_conf_float):
                            condition_met = True
                            if capture_as:
                                captured_value_for_context = {"value": ocr_text, "_source_region_for_capture_": region_name}

            elif condition_type == "dominant_color_matches":
                dominant_colors_data = get_pre_analyzed_data(
                    "dominant_colors_result", self.analysis_engine.analyze_dominant_colors, image_np_bgr, self.config_manager.get_setting("analysis_dominant_colors_k", 3), rule_name_for_context
                )
                if isinstance(dominant_colors_data, list):
                    exp_bgr = single_condition_spec.get("expected_bgr")
                    tol = single_condition_spec.get("tolerance", 10)
                    top_n = single_condition_spec.get("check_top_n_dominant", 1)
                    min_perc = single_condition_spec.get("min_percentage", 0.0)
                    if isinstance(exp_bgr, list) and len(exp_bgr) == 3:
                        for dom_color_info in dominant_colors_data[: min(top_n, len(dominant_colors_data))]:
                            if (
                                isinstance(dom_color_info.get("bgr_color"), list)
                                and np.all(np.abs(np.array(dom_color_info["bgr_color"]) - np.array(exp_bgr)) <= tol)
                                and dom_color_info.get("percentage", 0.0) >= min_perc
                            ):
                                condition_met = True
                                break

            elif condition_type == "gemini_vision_query":
                if self.gemini_analyzer_for_query and image_np_bgr is not None:
                    prompt_str = single_condition_spec.get("prompt")
                    model_override = single_condition_spec.get("model_name")  # Optional override
                    if prompt_str:
                        gemini_response = self.gemini_analyzer_for_query.query_vision_model(prompt=prompt_str, image_data=image_np_bgr, model_name_override=model_override)
                        if gemini_response["status"] == "success":
                            resp_text_content, resp_json_content = gemini_response.get("text_content", "") or "", gemini_response.get("json_content")

                            # Text check
                            exp_text_contains_param = single_condition_spec.get("expected_response_contains")
                            case_sensitive_text_check = single_condition_spec.get("case_sensitive_response_check", False)
                            exp_texts_list = (
                                [s.strip() for s in exp_text_contains_param.split(",")]
                                if isinstance(exp_text_contains_param, str)
                                else [str(s).strip() for s in exp_text_contains_param] if isinstance(exp_text_contains_param, list) else []
                            )
                            text_condition_part_met = not exp_texts_list or any(
                                (s_find if case_sensitive_text_check else s_find.lower()) in (resp_text_content if case_sensitive_text_check else resp_text_content.lower())
                                for s_find in exp_texts_list
                            )

                            # JSON path check
                            json_path_str = single_condition_spec.get("expected_response_json_path")
                            expected_json_val_str = single_condition_spec.get("expected_json_value")  # Keep as string for comparison
                            json_condition_part_met = True  # True if no JSON path check needed
                            extracted_json_value_for_capture = None

                            if json_path_str and isinstance(json_path_str, str) and resp_json_content is not None:
                                current_json_node = resp_json_content
                                path_is_valid = True
                                try:
                                    for key_or_index in json_path_str.strip(".").split("."):
                                        if isinstance(current_json_node, dict):
                                            current_json_node = current_json_node[key_or_index]
                                        elif isinstance(current_json_node, list) and key_or_index.isdigit():
                                            current_json_node = current_json_node[int(key_or_index)]
                                        else:
                                            path_is_valid = False
                                            break
                                    if path_is_valid:
                                        extracted_json_value_for_capture = current_json_node
                                except (KeyError, IndexError, TypeError):
                                    path_is_valid = False

                                if not path_is_valid:
                                    json_condition_part_met = False
                                elif expected_json_val_str is not None and str(current_json_node) != expected_json_val_str:
                                    json_condition_part_met = False
                            elif json_path_str and resp_json_content is None:  # Path specified but no JSON to parse
                                json_condition_part_met = False
                                logger.debug(f"{log_prefix}: JSON path '{json_path_str}' specified, but Gemini response was not valid JSON or had no JSON content.")

                            if text_condition_part_met and json_condition_part_met:
                                condition_met = True
                                if capture_as:
                                    # Determine what to capture: specific JSON path value, full JSON, or text
                                    if json_path_str and extracted_json_value_for_capture is not None:
                                        captured_value_for_context = {"value": extracted_json_value_for_capture, "_source_region_for_capture_": region_name}
                                    elif resp_json_content is not None:  # Capture full JSON if path not used or failed but JSON exists
                                        captured_value_for_context = {"value": resp_json_content, "_source_region_for_capture_": region_name}
                                    else:  # Fallback to text content
                                        captured_value_for_context = {"value": resp_text_content, "_source_region_for_capture_": region_name}
                        else:  # Gemini query failed
                            logger.warning(f"{log_prefix}: Gemini query failed. Status: {gemini_response['status']}, Error: {gemini_response.get('error_message')}")
                else:
                    logger.error(f"{log_prefix}: GeminiAnalyzer (for query) not available or image_np_bgr is None. Cannot execute gemini_vision_query.")

            elif condition_type == "always_true":
                condition_met = True

            else:  # Unknown condition type
                logger.error(f"{log_prefix}: Unknown condition type. Evaluation fails by default.")
                return False  # Explicitly return False for unknown types

            # Store captured value if condition met and capture_as specified
            if condition_met and capture_as and captured_value_for_context is not None:
                variable_context[capture_as] = captured_value_for_context
                # logger.info(f"{log_prefix}: Value captured for variable '{capture_as}'.") # Can be verbose

        except Exception as e:
            logger.exception(f"{log_prefix}: Unexpected exception during condition logic evaluation: {e}")
            return False  # Fail safe on any unexpected error

        # Final log for the condition's outcome
        logger.log(logging.INFO if condition_met else logging.DEBUG, f"{log_prefix}: Evaluation Result = {condition_met}")
        return condition_met

    def _check_condition(
        self, rule_name: str, condition_spec: Dict[str, Any], default_rule_region_from_rule: Optional[str], all_region_data: Dict[str, Dict[str, Any]], variable_context: Dict[str, Any]
    ) -> bool:
        log_operator = condition_spec.get("logical_operator")
        sub_conditions_list = condition_spec.get("sub_conditions")

        if log_operator and isinstance(sub_conditions_list, list):  # Compound Condition
            operator = log_operator.upper()
            if operator not in ["AND", "OR"] or not sub_conditions_list:
                logger.error(f"R '{rule_name}': Invalid compound condition - operator '{operator}' or empty sub_conditions. Fails.")
                return False

            # logger.debug(f"R '{rule_name}': Evaluating compound condition '{operator}' with {len(sub_conditions_list)} sub-conditions.")
            for i, sub_cond_spec_original in enumerate(sub_conditions_list):
                sub_log_context = f"{rule_name}/SubCond#{i+1}"
                if not isinstance(sub_cond_spec_original, dict):
                    logger.warning(f"R '{sub_log_context}': Sub-condition is not a dictionary. Skipping. If AND, this causes outer to fail.")
                    if operator == "AND":
                        return False
                    else:
                        continue  # For OR, skip invalid sub-condition

                # Substitute variables *within* the sub-condition spec itself before evaluation
                sub_cond_spec_substituted = self._substitute_variables(sub_cond_spec_original, variable_context, sub_log_context)

                target_region_for_sub_cond = sub_cond_spec_substituted.get("region", default_rule_region_from_rule)
                if not target_region_for_sub_cond or target_region_for_sub_cond not in all_region_data:
                    logger.error(f"R '{sub_log_context}': Target region '{target_region_for_sub_cond}' for sub-condition is missing or invalid (no data). Sub-condition fails.")
                    sub_condition_result = False
                else:
                    sub_condition_result = self._evaluate_single_condition_logic(
                        sub_cond_spec_substituted, target_region_for_sub_cond, all_region_data[target_region_for_sub_cond], sub_log_context, variable_context
                    )

                if operator == "AND" and not sub_condition_result:
                    return False  # Short-circuit AND
                if operator == "OR" and sub_condition_result:
                    return True  # Short-circuit OR

            return True if operator == "AND" else False  # All ANDs were true, or no OR was true

        else:  # Single Condition (or malformed compound treated as single for robustness)
            if "type" not in condition_spec:
                logger.error(f"R '{rule_name}': Condition spec missing 'type' and not a valid compound. Fails.")
                return False

            condition_spec_substituted = self._substitute_variables(condition_spec, variable_context, rule_name)
            target_region_for_single_cond = condition_spec_substituted.get("region", default_rule_region_from_rule)

            if not target_region_for_single_cond or target_region_for_single_cond not in all_region_data:
                logger.error(f"R '{rule_name}': Target region '{target_region_for_single_cond}' for single condition is missing or invalid. Condition fails.")
                return False

            return self._evaluate_single_condition_logic(condition_spec_substituted, target_region_for_single_cond, all_region_data[target_region_for_single_cond], rule_name, variable_context)

    def evaluate_rules(self, all_region_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluates all rules. If a rule's condition is met, its action is processed.
        For `gemini_perform_task`, invokes `GeminiDecisionModule`.
        For other actions, invokes `ActionExecutor` directly.
        Returns a list of standard action specifications that were explicitly executed by this engine
        (does not include actions taken by GeminiDecisionModule internally).
        """
        explicitly_executed_standard_actions: List[Dict[str, Any]] = []
        if not self.rules:
            logger.debug("RulesEngine: No rules in profile to evaluate.")
            return explicitly_executed_standard_actions

        logger.info(f"RulesEngine: Evaluating {len(self.rules)} rules for current cycle.")
        for rule_idx, rule_config in enumerate(self.rules):
            rule_name = rule_config.get("name", f"RuleIdx{rule_idx}")
            log_prefix_reval = f"R '{rule_name}'"  # Rule evaluation log prefix
            original_condition_spec = rule_config.get("condition")
            original_action_spec = rule_config.get("action")
            default_rule_region_name = rule_config.get("region")  # Rule's default region

            if not (isinstance(original_condition_spec, dict) and isinstance(original_action_spec, dict)):
                logger.warning(f"{log_prefix_reval}: Invalid or missing condition/action spec. Skipping rule.")
                continue

            self._last_template_match_info = {"found": False}  # Reset for each rule's evaluation context
            rule_variable_context: Dict[str, Any] = {}  # Fresh variable context for each rule

            # logger.debug(f"{log_prefix_reval}: Evaluating. Default region for rule conditions: '{default_rule_region_name}'.")
            try:
                condition_is_met = self._check_condition(rule_name, original_condition_spec, default_rule_region_name, all_region_data, rule_variable_context)  # Pass fresh context

                if condition_is_met:
                    action_type_from_spec_orig = original_action_spec.get("type")  # Get type before substitution for logging
                    logger.info(f"{log_prefix_reval}: Condition MET. Preparing action of type '{action_type_from_spec_orig}'.")

                    # Substitute variables in the action spec *before* further processing
                    action_spec_substituted = self._substitute_variables(original_action_spec, rule_variable_context, f"{rule_name}/ActionSubst")
                    final_action_type = action_spec_substituted.get("type")  # Get type from the *substituted* spec
                    logger.debug(f"{log_prefix_reval}, Action Prep: Substituted spec: {action_spec_substituted}. Variables captured in condition: {rule_variable_context}")

                    if final_action_type == "gemini_perform_task":
                        if self.gemini_decision_module and self.gemini_decision_module.gemini_analyzer and self.gemini_decision_module.gemini_analyzer.client_initialized:
                            nl_command = action_spec_substituted.get("natural_language_command", action_spec_substituted.get("goal_prompt", ""))

                            # Handle context_region_names: can be CSV string or list from JSON
                            ctx_rgn_names_param = action_spec_substituted.get("context_region_names", [])
                            ctx_rgn_names_list_for_gdm: List[str] = []
                            if isinstance(ctx_rgn_names_param, str):
                                ctx_rgn_names_list_for_gdm = [r.strip() for r in ctx_rgn_names_param.split(",") if r.strip()]
                            elif isinstance(ctx_r_names_param, list):  # Typo in original: ctx_r_names_param -> ctx_rgn_names_param
                                ctx_rgn_names_list_for_gdm = [str(r).strip() for r in ctx_rgn_names_param if str(r).strip()]

                            # Prepare task parameters for GeminiDecisionModule
                            task_params_for_gdm = {k: v for k, v in action_spec_substituted.items() if k not in ["type", "natural_language_command", "goal_prompt", "context_region_names"]}

                            allowed_override = task_params_for_gdm.get("allowed_actions_override", [])
                            if isinstance(allowed_override, str):
                                task_params_for_gdm["allowed_actions_override"] = [a.strip().upper() for a in allowed_override.split(",") if a.strip()]
                            elif isinstance(allowed_override, list):
                                task_params_for_gdm["allowed_actions_override"] = [str(a).strip().upper() for a in allowed_override if str(a).strip()]
                            else:
                                task_params_for_gdm["allowed_actions_override"] = []  # Default to empty list if invalid type

                            task_context_images: Dict[str, np.ndarray] = {}
                            can_run_nlu_task = True
                            if not nl_command:
                                logger.error(f"{log_prefix_reval}, NLU Task: 'natural_language_command' or 'goal_prompt' is missing. Task fails.")
                                can_run_nlu_task = False

                            if can_run_nlu_task:
                                target_regions_for_nlu_context = ctx_rgn_names_list_for_gdm
                                if not target_regions_for_nlu_context and default_rule_region_name:  # Fallback to rule's default region
                                    target_regions_for_nlu_context = [default_rule_region_name]

                                if not target_regions_for_nlu_context:  # Still no regions
                                    logger.error(f"{log_prefix_reval}, NLU Task: No context regions specified or derivable. Task fails.")
                                    can_run_nlu_task = False
                                else:
                                    for r_name_for_nlu_ctx in target_regions_for_nlu_context:
                                        if r_name_for_nlu_ctx in all_region_data and all_region_data[r_name_for_nlu_ctx].get("image") is not None:
                                            task_context_images[r_name_for_nlu_ctx] = all_region_data[r_name_for_nlu_ctx]["image"]
                                        else:
                                            logger.error(f"{log_prefix_reval}, NLU Task: Context region '{r_name_for_nlu_ctx}' image missing. Task fails.")
                                            can_run_nlu_task = False
                                            break
                                    if not task_context_images and can_run_nlu_task:  # Double check if any images were actually collected
                                        logger.error(f"{log_prefix_reval}, NLU Task: No valid images for context regions. Task fails.")
                                        can_run_nlu_task = False

                            if can_run_nlu_task:
                                logger.info(f"{log_prefix_reval}: Invoking GeminiDecisionModule for NLU command: '{nl_command[:70].replace(os.linesep, ' ')}...'")
                                task_execution_result = self.gemini_decision_module.execute_nlu_task(
                                    task_rule_name=rule_name, natural_language_command=nl_command, initial_context_images=task_context_images, task_parameters=task_params_for_gdm
                                )
                                logger.info(f"{log_prefix_reval}, NLU Task Result: Status='{task_execution_result.get('status')}', Msg='{task_execution_result.get('message')}'")
                        else:
                            logger.error(f"{log_prefix_reval}, Action 'gemini_perform_task': GeminiDecisionModule not available or not properly initialized. Task skipped.")
                    else:  # Standard action to be executed by ActionExecutor
                        action_execution_context = {
                            "rule_name": rule_name,
                            "condition_region": default_rule_region_name,  # Pass the rule's default region for context
                            "last_match_info": self._last_template_match_info.copy(),  # Pass info from last template match in this rule
                            "variables": rule_variable_context.copy(),  # Pass all captured variables for this rule
                        }
                        full_action_spec_for_executor = {**action_spec_substituted, "context": action_execution_context}

                        logger.info(f"{log_prefix_reval}: Directly executing standard action type '{final_action_type}'.")
                        self.action_executor.execute_action(full_action_spec_for_executor)
                        explicitly_executed_standard_actions.append(full_action_spec_for_executor)  # Track executed standard actions
            except Exception as e_rule_eval:
                logger.exception(f"{log_prefix_reval}: Unexpected error during rule evaluation or action dispatch: {e_rule_eval}")

        logger.info(f"RulesEngine: Cycle finished. {len(explicitly_executed_standard_actions)} standard actions were explicitly dispatched by RulesEngine.")
        return explicitly_executed_standard_actions
