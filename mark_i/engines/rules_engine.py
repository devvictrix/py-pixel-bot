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
from mark_i.engines.gemini_analyzer import GeminiAnalyzer  # For gemini_vision_query (via evaluator)
from mark_i.engines.gemini_decision_module import GeminiDecisionModule  # For gemini_perform_task

# Import new evaluator classes
from mark_i.engines.condition_evaluators import (
    ConditionEvaluator,
    PixelColorEvaluator,
    AverageColorEvaluator,
    TemplateMatchEvaluator,
    OcrContainsTextEvaluator,
    DominantColorEvaluator,
    GeminiVisionQueryEvaluator,
    AlwaysTrueEvaluator,
    ConditionEvaluationResult,  # Import the result class
)


logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.rules_engine")

# Regex for finding placeholders like {var_name} or {var_name.key1.0.key2}
# Group 1: var_name
# Group 2: the entire dot path starting with the first dot (e.g., .value.user_list.0.name)
PLACEHOLDER_REGEX = re.compile(r"\{([\w_]+)((?:\.[\w\d_]+)*)\}")
TEMPLATES_SUBDIR_NAME = "templates"  # Standard subdirectory for template images


class RulesEngine:
    """
    Evaluates rules defined in a profile based on visual analysis data and triggers actions.
    Supports single conditions, compound conditions (AND/OR logic), rule-scoped
    variable capture, and placeholder substitution in action parameters.

    Integrates with:
    - `AnalysisEngine` for local visual checks (via ConditionEvaluators).
    - `GeminiAnalyzer` for AI-powered `gemini_vision_query` conditions (via GeminiVisionQueryEvaluator).
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
        if not isinstance(config_manager, ConfigManager):  # pragma: no cover
            raise ValueError("RulesEngine requires a valid ConfigManager instance.")
        if not isinstance(analysis_engine, AnalysisEngine):  # pragma: no cover
            raise ValueError("RulesEngine requires a valid AnalysisEngine instance.")
        if not isinstance(action_executor, ActionExecutor):  # pragma: no cover
            raise ValueError("RulesEngine requires a valid ActionExecutor instance.")

        self.config_manager = config_manager
        self.analysis_engine = analysis_engine
        self.action_executor = action_executor
        self.gemini_decision_module = gemini_decision_module  # Store instance

        self.profile_data = self.config_manager.get_profile_data()  # Get a copy
        self.rules: List[Dict[str, Any]] = self.profile_data.get("rules", [])

        self._loaded_templates: Dict[Tuple[str, str], Optional[np.ndarray]] = {}
        self._last_template_match_info: Dict[str, Any] = {"found": False}
        self._analysis_requirements_per_region: Dict[str, Set[str]] = defaultdict(set)
        self._parse_rule_analysis_dependencies()

        gemini_api_key_from_env = os.getenv("GEMINI_API_KEY")
        default_gemini_model_from_settings = self.config_manager.get_setting("gemini_default_model_name", "gemini-1.5-flash-latest")
        self.gemini_analyzer_for_query: Optional[GeminiAnalyzer] = None
        if gemini_api_key_from_env:  # pragma: no branch
            self.gemini_analyzer_for_query = GeminiAnalyzer(api_key=gemini_api_key_from_env, default_model_name=default_gemini_model_from_settings)
            if not self.gemini_analyzer_for_query.client_initialized:  # pragma: no cover
                logger.warning("RulesEngine: GeminiAnalyzer (for query conditions) failed API client initialization. `gemini_vision_query` conditions will likely fail.")
                self.gemini_analyzer_for_query = None
            else:  # pragma: no cover
                logger.info(f"RulesEngine: GeminiAnalyzer (for query conditions) enabled. Default model: '{default_gemini_model_from_settings}'")
        else:  # pragma: no cover
            logger.warning("RulesEngine: GEMINI_API_KEY not found. `gemini_vision_query` conditions will be disabled or fail.")

        # Initialize condition evaluators (Strategy Pattern)
        self._condition_evaluators: Dict[str, ConditionEvaluator] = self._initialize_condition_evaluators()

        if self.gemini_decision_module:  # pragma: no cover
            logger.info("RulesEngine: GeminiDecisionModule integration is active for 'gemini_perform_task' actions.")
        else:  # pragma: no cover
            logger.warning("RulesEngine: GeminiDecisionModule not provided or failed to initialize. 'gemini_perform_task' (NLU) actions will be skipped or fail.")

        if not self.rules:  # pragma: no cover
            logger.warning("RulesEngine: No rules found in the loaded profile. The bot might not perform any actions based on rules.")
        else:  # pragma: no cover
            logger.info(f"RulesEngine initialized successfully with {len(self.rules)} rules.")
            if self._analysis_requirements_per_region:
                logger.debug(f"RulesEngine: Determined local pre-emptive analysis requirements: {dict(self._analysis_requirements_per_region)}")
            else:
                logger.debug("RulesEngine: No pre-emptive local analyses required by any rule.")

    def _initialize_condition_evaluators(self) -> Dict[str, ConditionEvaluator]:
        """Initializes and returns a dictionary of condition type to evaluator instance."""

        def _config_getter(key: str, default: Any) -> Any:
            return self.config_manager.get_setting(key, default)

        shared_dependencies = {
            "analysis_engine": self.analysis_engine,
            "template_loader_func": self._load_template_image_for_rule,  # Pass the method itself
            "gemini_analyzer_instance": self.gemini_analyzer_for_query,
            "config_settings_getter_func": _config_getter,
        }
        evaluators = {
            "pixel_color": PixelColorEvaluator(**shared_dependencies),
            "average_color_is": AverageColorEvaluator(**shared_dependencies),
            "template_match_found": TemplateMatchEvaluator(**shared_dependencies),
            "ocr_contains_text": OcrContainsTextEvaluator(**shared_dependencies),
            "dominant_color_matches": DominantColorEvaluator(**shared_dependencies),
            "gemini_vision_query": GeminiVisionQueryEvaluator(**shared_dependencies),
            "always_true": AlwaysTrueEvaluator(**shared_dependencies),
        }
        logger.debug(f"RulesEngine: Initialized {len(evaluators)} condition evaluators.")
        return evaluators  # type: ignore # MyPy might complain about dict general type

    def _parse_rule_analysis_dependencies(self):  # pragma: no cover
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
            if "logical_operator" in condition_spec_outer and isinstance(condition_spec_outer.get("sub_conditions"), list):
                for sub_cond in condition_spec_outer["sub_conditions"]:
                    if isinstance(sub_cond, dict):
                        sub_cond_region = sub_cond.get("region", default_rule_region)
                        conditions_to_parse.append((sub_cond, sub_cond_region))
            elif "type" in condition_spec_outer:
                single_cond_region = condition_spec_outer.get("region", default_rule_region)
                conditions_to_parse.append((condition_spec_outer, single_cond_region))

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

    def get_analysis_requirements_for_region(self, region_name: str) -> Set[str]:  # pragma: no cover
        return self._analysis_requirements_per_region.get(region_name, set())

    def _load_template_image_for_rule(self, template_filename: str, rule_name_for_context: str) -> Optional[np.ndarray]:  # pragma: no cover
        profile_base = self.config_manager.get_profile_base_path()
        if not profile_base:
            logger.error(f"R '{rule_name_for_context}': Cannot load template '{template_filename}', profile is unsaved (no base path available).")
            return None
        cache_key = (profile_base, template_filename)
        if cache_key in self._loaded_templates:
            return self._loaded_templates[cache_key]
        full_path = os.path.join(profile_base, TEMPLATES_SUBDIR_NAME, template_filename)
        if not os.path.exists(full_path):
            logger.error(f"R '{rule_name_for_context}': Template image file not found at path: '{full_path}'.")
            self._loaded_templates[cache_key] = None
            return None
        try:
            img = cv2.imread(full_path, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("cv2.imread returned None, file might be corrupted or not a supported image format.")
            logger.info(f"R '{rule_name_for_context}': Successfully loaded template '{template_filename}' from '{full_path}' (Shape: {img.shape}).")
            self._loaded_templates[cache_key] = img
            return img
        except Exception as e:
            logger.exception(f"R '{rule_name_for_context}': Error loading template image '{full_path}': {e}")
            self._loaded_templates[cache_key] = None
            return None

    def _substitute_variables(self, input_value: Any, variable_context: Dict[str, Any], log_context_prefix: str) -> Any:
        if not isinstance(input_value, (str, list, dict)):
            return input_value
        if not variable_context: # No variables to substitute
            return input_value

        if isinstance(input_value, str):
            def replace_match(match_obj: re.Match) -> str:
                full_placeholder = match_obj.group(0)
                var_name = match_obj.group(1)
                dot_path_full_segment = match_obj.group(2) # This will be like ".value.user_list.0.name"

                if var_name in variable_context:
                    current_val = variable_context[var_name] 

                    if dot_path_full_segment: 
                        path_keys = dot_path_full_segment.strip(".").split(".")
                        resolved_val = current_val 
                        try:
                            for key_part in path_keys:
                                if resolved_val is None:
                                    logger.warning(f"{log_context_prefix}, Subst: Encountered None while traversing path for '{var_name}{dot_path_full_segment}' at '{key_part}'. Placeholder left.")
                                    return full_placeholder
                                if isinstance(resolved_val, dict):
                                    resolved_val = resolved_val[key_part]
                                elif isinstance(resolved_val, list) and key_part.isdigit():
                                    idx = int(key_part)
                                    if 0 <= idx < len(resolved_val):
                                        resolved_val = resolved_val[idx]
                                    else: 
                                        raise IndexError(f"Index {idx} out of bounds for list of length {len(resolved_val)} in '{var_name}{dot_path_full_segment}'.")
                                else: 
                                    logger.warning(
                                        f"{log_context_prefix}, Subst: Cannot access '{key_part}' in '{var_name}'. Path: '{dot_path_full_segment}'. Current value type: {type(resolved_val)}. Placeholder left."
                                    )
                                    return full_placeholder
                            return str(resolved_val) 
                        except (KeyError, IndexError, TypeError) as e:
                            logger.warning(f"{log_context_prefix}, Subst: Path resolution error for '{var_name}{dot_path_full_segment}': {e}. Placeholder left.")
                            return full_placeholder
                    else: 
                        if isinstance(current_val, dict) and "value" in current_val and "_source_region_for_capture_" in current_val:
                            return str(current_val["value"])
                        return str(current_val) 
                else: 
                    logger.warning(f"{log_context_prefix}, Subst: Variable '{var_name}' not in context. Placeholder '{full_placeholder}' left.")
                    return full_placeholder

            return PLACEHOLDER_REGEX.sub(replace_match, input_value)
        elif isinstance(input_value, list):
            return [self._substitute_variables(item, variable_context, log_context_prefix) for item in input_value]
        elif isinstance(input_value, dict):
            return {k: self._substitute_variables(v, variable_context, log_context_prefix) for k, v in input_value.items()}
        return input_value  # Should not be reached

    def _evaluate_single_condition_logic(
        self, single_condition_spec: Dict[str, Any], region_name: str, region_data_packet: Dict[str, Any], rule_name_for_context: str, variable_context: Dict[str, Any]
    ) -> bool:
        condition_type = single_condition_spec.get("type")
        capture_as = single_condition_spec.get("capture_as")
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond '{condition_type}'"

        if not condition_type:
            logger.error(f"{log_prefix}: 'type' missing in condition spec.")
            return False

        evaluator = self._condition_evaluators.get(condition_type)
        if not evaluator:
            logger.error(f"{log_prefix}: Unknown condition type. No evaluator found. Evaluation fails by default.")
            return False

        try:
            eval_result: ConditionEvaluationResult = evaluator.evaluate(single_condition_spec, region_name, region_data_packet, rule_name_for_context)
            condition_met = eval_result.met
            captured_value_for_context = eval_result.captured_value
            if eval_result.template_match_info is not None:
                self._last_template_match_info = eval_result.template_match_info
            if condition_met and capture_as and captured_value_for_context is not None:
                variable_context[capture_as] = captured_value_for_context
            return condition_met
        except Exception as e:  # pragma: no cover
            logger.exception(f"{log_prefix}: Unexpected exception during condition evaluation via evaluator: {e}")
            return False

    def _check_condition(
        self, rule_name: str, condition_spec: Dict[str, Any], default_rule_region_from_rule: Optional[str], all_region_data: Dict[str, Dict[str, Any]], variable_context: Dict[str, Any]
    ) -> bool:
        log_operator = condition_spec.get("logical_operator")
        sub_conditions_list = condition_spec.get("sub_conditions")

        if log_operator and isinstance(sub_conditions_list, list):
            operator = log_operator.upper()
            if operator not in ["AND", "OR"] or not sub_conditions_list:  # pragma: no cover
                logger.error(f"R '{rule_name}': Invalid compound condition - operator '{operator}' or empty sub_conditions. Fails.")
                return False
            for i, sub_cond_spec_original in enumerate(sub_conditions_list):
                sub_log_context = f"{rule_name}/SubCond#{i+1}"
                if not isinstance(sub_cond_spec_original, dict):  # pragma: no cover
                    logger.warning(f"R '{sub_log_context}': Sub-condition is not a dictionary. Skipping. If AND, this causes outer to fail.")
                    if operator == "AND":
                        return False
                    else:
                        continue
                sub_cond_spec_substituted = self._substitute_variables(sub_cond_spec_original, variable_context, sub_log_context)
                target_region_for_sub_cond = sub_cond_spec_substituted.get("region", default_rule_region_from_rule)
                if not target_region_for_sub_cond or target_region_for_sub_cond not in all_region_data:  # pragma: no cover
                    logger.error(f"R '{sub_log_context}': Target region '{target_region_for_sub_cond}' for sub-condition is missing or invalid. Sub-condition fails.")
                    sub_condition_result = False
                else:
                    sub_condition_result = self._evaluate_single_condition_logic(
                        sub_cond_spec_substituted, target_region_for_sub_cond, all_region_data[target_region_for_sub_cond], sub_log_context, variable_context
                    )
                if operator == "AND" and not sub_condition_result:
                    return False
                if operator == "OR" and sub_condition_result:
                    return True
            return True if operator == "AND" else False  # If AND, all sub-conditions must have been true. If OR, all must have been false.
        else:  # Single Condition
            if "type" not in condition_spec:  # pragma: no cover
                logger.error(f"R '{rule_name}': Condition spec missing 'type' and not a valid compound. Fails.")
                return False
            condition_spec_substituted = self._substitute_variables(condition_spec, variable_context, rule_name)
            target_region_for_single_cond = condition_spec_substituted.get("region", default_rule_region_from_rule)
            if not target_region_for_single_cond or target_region_for_single_cond not in all_region_data:  # pragma: no cover
                logger.error(f"R '{rule_name}': Target region '{target_region_for_single_cond}' for single condition is missing or invalid. Condition fails.")
                return False
            return self._evaluate_single_condition_logic(condition_spec_substituted, target_region_for_single_cond, all_region_data[target_region_for_single_cond], rule_name, variable_context)

    def evaluate_rules(self, all_region_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:  # pragma: no cover
        explicitly_executed_standard_actions: List[Dict[str, Any]] = []
        if not self.rules:
            logger.debug("RulesEngine: No rules in profile to evaluate.")
            return explicitly_executed_standard_actions

        logger.info(f"RulesEngine: Evaluating {len(self.rules)} rules for current cycle.")
        for rule_idx, rule_config in enumerate(self.rules):
            rule_name = rule_config.get("name", f"RuleIdx{rule_idx}")
            log_prefix_reval = f"R '{rule_name}'"
            original_condition_spec = rule_config.get("condition")
            original_action_spec = rule_config.get("action")
            default_rule_region_name = rule_config.get("region")

            if not (isinstance(original_condition_spec, dict) and isinstance(original_action_spec, dict)):
                logger.warning(f"{log_prefix_reval}: Invalid or missing condition/action spec. Skipping rule.")
                continue

            self._last_template_match_info = {"found": False}
            rule_variable_context: Dict[str, Any] = {}

            try:
                condition_is_met = self._check_condition(rule_name, original_condition_spec, default_rule_region_name, all_region_data, rule_variable_context)
                if condition_is_met:
                    action_type_from_spec_orig = original_action_spec.get("type")
                    logger.info(f"{log_prefix_reval}: Condition MET. Preparing action of type '{action_type_from_spec_orig}'.")
                    action_spec_substituted = self._substitute_variables(original_action_spec, rule_variable_context, f"{rule_name}/ActionSubst")
                    final_action_type = action_spec_substituted.get("type")
                    logger.debug(f"{log_prefix_reval}, Action Prep: Substituted spec: {action_spec_substituted}. Variables captured: {rule_variable_context}")

                    if final_action_type == "gemini_perform_task":
                        if self.gemini_decision_module and self.gemini_decision_module.gemini_analyzer and self.gemini_decision_module.gemini_analyzer.client_initialized:
                            nl_command = action_spec_substituted.get("natural_language_command", action_spec_substituted.get("goal_prompt", ""))
                            ctx_rgn_names_param = action_spec_substituted.get("context_region_names", [])
                            ctx_rgn_names_list_for_gdm: List[str] = (
                                [r.strip() for r in ctx_rgn_names_param.split(",") if r.strip()]
                                if isinstance(ctx_rgn_names_param, str)
                                else [str(r).strip() for r in ctx_rgn_names_param if str(r).strip()] if isinstance(ctx_rgn_names_param, list) else []
                            )
                            task_params_for_gdm = {k: v for k, v in action_spec_substituted.items() if k not in ["type", "natural_language_command", "goal_prompt", "context_region_names"]}
                            allowed_override = task_params_for_gdm.get("allowed_actions_override", [])
                            task_params_for_gdm["allowed_actions_override"] = (
                                [a.strip().upper() for a in allowed_override.split(",") if a.strip()]
                                if isinstance(allowed_override, str)
                                else [str(a).strip().upper() for a in allowed_override if str(a).strip()] if isinstance(allowed_override, list) else []
                            )
                            task_context_images: Dict[str, np.ndarray] = {}
                            can_run_nlu_task = True
                            if not nl_command:
                                logger.error(f"{log_prefix_reval}, NLU Task: 'natural_language_command' or 'goal_prompt' is missing. Task fails.")
                                can_run_nlu_task = False
                            if can_run_nlu_task:
                                target_regions_for_nlu_context = ctx_rgn_names_list_for_gdm or ([default_rule_region_name] if default_rule_region_name else [])
                                if not target_regions_for_nlu_context:
                                    logger.error(f"{log_prefix_reval}, NLU Task: No context regions specified. Task fails.")
                                    can_run_nlu_task = False
                                else:
                                    for r_name_for_nlu_ctx in target_regions_for_nlu_context:
                                        if r_name_for_nlu_ctx in all_region_data and all_region_data[r_name_for_nlu_ctx].get("image") is not None:
                                            task_context_images[r_name_for_nlu_ctx] = all_region_data[r_name_for_nlu_ctx]["image"]
                                        else:
                                            logger.error(f"{log_prefix_reval}, NLU Task: Context region '{r_name_for_nlu_ctx}' image missing. Task fails.")
                                            can_run_nlu_task = False
                                            break
                                    if not task_context_images and can_run_nlu_task:
                                        logger.error(f"{log_prefix_reval}, NLU Task: No valid images for context regions. Task fails.")
                                        can_run_nlu_task = False
                            if can_run_nlu_task:
                                logger.info(f"{log_prefix_reval}: Invoking GeminiDecisionModule for NLU command: '{nl_command[:70].replace(os.linesep, ' ')}...'")
                                task_execution_result = self.gemini_decision_module.execute_nlu_task(
                                    task_rule_name=rule_name, natural_language_command=nl_command, initial_context_images=task_context_images, task_parameters=task_params_for_gdm
                                )
                                logger.info(f"{log_prefix_reval}, NLU Task Result: Status='{task_execution_result.get('status')}', Msg='{task_execution_result.get('message')}'")
                        else:
                            logger.error(f"{log_prefix_reval}, Action 'gemini_perform_task': GeminiDecisionModule not available. Task skipped.")
                    else:
                        action_execution_context = {
                            "rule_name": rule_name,
                            "condition_region": default_rule_region_name,
                            "last_match_info": self._last_template_match_info.copy(),
                            "variables": rule_variable_context.copy(),
                        }
                        full_action_spec_for_executor = {**action_spec_substituted, "context": action_execution_context}
                        logger.info(f"{log_prefix_reval}: Directly executing standard action type '{final_action_type}'.")
                        self.action_executor.execute_action(full_action_spec_for_executor)
                        explicitly_executed_standard_actions.append(full_action_spec_for_executor)
            except Exception as e_rule_eval:
                logger.exception(f"{log_prefix_reval}: Unexpected error during rule evaluation or action dispatch: {e_rule_eval}")
        logger.info(f"RulesEngine: Cycle finished. {len(explicitly_executed_standard_actions)} standard actions dispatched.")
        return explicitly_executed_standard_actions