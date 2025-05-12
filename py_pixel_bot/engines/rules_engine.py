import logging
import os
import re
from typing import Dict, List, Any, Optional, Tuple, Set, Callable  # <--- IMPORT Callable HERE
from collections import defaultdict

import cv2
import numpy as np

from py_pixel_bot.core.config_manager import ConfigManager
from py_pixel_bot.engines.analysis_engine import AnalysisEngine
from py_pixel_bot.engines.action_executor import ActionExecutor

logger = logging.getLogger(__name__)

# Regex to find placeholders like {var_name} or {var_name.key} or {var_name.key.subkey}
PLACEHOLDER_REGEX = re.compile(r"\{([\w_]+)((\.[\w_]+)*)\}")
APP_ROOT_LOGGER_NAME = "py_pixel_bot"  # Consistent with logging_setup


class RulesEngine:
    """
    Evaluates rules based on visual analysis data and triggers actions.
    Supports single conditions, compound conditions (AND/OR logic),
    rule-scoped variable capture and substitution.
    Pre-parses rules to determine analysis dependencies for selective analysis.
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
        self.rules: List[Dict[str, Any]] = self.profile_data.get("rules", [])  # Ensure type hint
        self._loaded_templates: Dict[Tuple[str, str], Optional[np.ndarray]] = {}
        self._last_template_match_info: Dict[str, Any] = {}

        self._analysis_requirements_per_region: Dict[str, Set[str]] = defaultdict(set)
        self._parse_rule_analysis_dependencies()

        if not self.rules:
            logger.warning("No rules found in the loaded profile.")
        else:
            logger.info(f"RulesEngine initialized with {len(self.rules)} rules.")
            # Ensure dict() is used if defaultdict is logged for cleaner output.
            logger.debug(f"Determined analysis requirements: {dict(self._analysis_requirements_per_region)}")

    def _parse_rule_analysis_dependencies(self):
        """
        Parses all rules to determine which general analyses are required for each region.
        Populates self._analysis_requirements_per_region.
        """
        logger.debug("RulesEngine: Parsing rule analysis dependencies...")
        if not self.rules:
            logger.debug("RulesEngine: No rules to parse for analysis dependencies.")
            return

        for i, rule in enumerate(self.rules):
            rule_name = rule.get("name", f"UnnamedRule_idx{i}")
            default_rule_region = rule.get("region")  # This is the rule's top-level region
            condition_spec = rule.get("condition")

            if not condition_spec or not isinstance(condition_spec, dict):
                logger.warning(f"Rule '{rule_name}': Invalid or missing condition specification. Skipping for dependency parsing.")
                continue

            conditions_to_evaluate_for_deps: List[Tuple[Dict[str, Any], Optional[str], str]] = []

            # Check for compound condition structure first
            if "logical_operator" in condition_spec and "sub_conditions" in condition_spec and isinstance(condition_spec["sub_conditions"], list):
                logger.debug(f"Rule '{rule_name}': Is compound. Parsing sub-conditions for dependencies.")
                for sub_idx, sub_cond_spec in enumerate(condition_spec["sub_conditions"]):
                    if not isinstance(sub_cond_spec, dict):
                        logger.warning(f"Rule '{rule_name}/Sub#{sub_idx+1}': Invalid sub-condition spec (not a dict). Skipping.")
                        continue
                    # A sub-condition uses its own "region" key if present, otherwise rule's default region
                    sub_cond_region = sub_cond_spec.get("region", default_rule_region)
                    if sub_cond_region:  # Region must be defined for dependency to be meaningful
                        conditions_to_evaluate_for_deps.append((sub_cond_spec, sub_cond_region, f"{rule_name}/Sub#{sub_idx+1}"))
                    else:
                        # If a sub-condition has no region and the rule has no default region, it's problematic.
                        # However, some conditions like 'always_true' might not need a region.
                        # For dependency parsing, we only care if a specific analysis *on a region* is needed.
                        logger.debug(f"Rule '{rule_name}/Sub#{sub_idx+1}': No explicit or default region. Type: '{sub_cond_spec.get('type')}'. No region-specific dependency added.")
            else:  # Single condition structure
                logger.debug(f"Rule '{rule_name}': Is single condition. Parsing for dependencies.")
                if default_rule_region:  # Single condition needs a region for most analysis types
                    conditions_to_evaluate_for_deps.append((condition_spec, default_rule_region, rule_name))
                else:
                    logger.debug(f"Rule '{rule_name}' (single): No default region specified. Type: '{condition_spec.get('type')}'. No region-specific dependency added.")

            for cond_spec_item, region_name_item, cond_ctx_name_item in conditions_to_evaluate_for_deps:
                cond_type = cond_spec_item.get("type")
                required_analysis: Optional[str] = None

                if cond_type == "ocr_contains_text":
                    required_analysis = "ocr"
                elif cond_type == "dominant_color_matches":
                    required_analysis = "dominant_color"
                elif cond_type == "average_color_is":
                    required_analysis = "average_color"
                # "pixel_color" & "template_match_found" are on-demand by RulesEngine, not pre-emptive by MainController.
                # "always_true" requires no pre-emptive analysis.

                if required_analysis and region_name_item:  # Must have a region to associate with
                    self._analysis_requirements_per_region[region_name_item].add(required_analysis)
                    logger.debug(f"Dependency parser: Condition '{cond_ctx_name_item}' (type: {cond_type}) in region '{region_name_item}' " f"requires pre-emptive analysis: '{required_analysis}'.")
        logger.info(f"RulesEngine: Analysis dependency parsing complete. Requirements determined: {dict(self._analysis_requirements_per_region)}")

    def get_analysis_requirements_for_region(self, region_name: str) -> Set[str]:
        """
        Returns the set of required general analysis types (e.g., "ocr", "dominant_color")
        for the given region_name based on pre-parsed rule dependencies.
        """
        reqs = self._analysis_requirements_per_region.get(region_name, set())
        logger.debug(f"Queried analysis requirements for region '{region_name}': {reqs}")
        return reqs

    def _load_template_image_for_rule(self, template_filename: str, rule_name_for_context: str) -> Optional[np.ndarray]:
        profile_base_path = self.config_manager.get_profile_base_path()
        if not profile_base_path:  # Should not happen if profile is loaded/saved
            logger.error(f"Rule '{rule_name_for_context}': Cannot load template '{template_filename}', profile base path is unknown (profile likely unsaved).")
            return None
        cache_key = (profile_base_path, template_filename)  # Unique key using base path
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
            template_image = cv2.imread(template_full_path, cv2.IMREAD_COLOR)  # Load as BGR
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

            def replace_match(match_obj: re.Match) -> str:  # Explicit type for match_obj
                full_placeholder = match_obj.group(0)
                var_name = match_obj.group(1)
                dot_path_str = match_obj.group(2)  # e.g., ".key.subkey" or empty if no path
                logger.debug(f"Rule '{rule_name_for_context}', Substitution: Found placeholder '{full_placeholder}'. Var: '{var_name}', Path: '{dot_path_str}'")
                if var_name in variable_context:
                    current_value = variable_context[var_name]
                    if dot_path_str:  # Accessing keys in a dictionary
                        keys = dot_path_str.strip(".").split(".")
                        try:
                            for key_part in keys:
                                if isinstance(current_value, dict):
                                    current_value = current_value[key_part]
                                elif isinstance(current_value, list) and key_part.isdigit():
                                    current_value = current_value[int(key_part)]  # Basic list index access
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

        captured_image = region_data.get("image")  # This is always present if region was processed by MainController
        condition_met = False
        captured_value_for_var = None

        # Fallback helper
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
                # ... (validation of params, then call self.analysis_engine.analyze_pixel_color - same as before) ...
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
                # ... (rest of average_color_is logic - same as before) ...
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
                # ... (rest of template_match_found, including capture - same as before) ...
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
                if not ocr_res or "text" not in ocr_res:
                    return False  # If no text after fallback, condition fails
                # ... (rest of ocr_contains_text, including capture - same as before) ...
                actual_txt = ocr_res.get("text", "")
                actual_conf = ocr_res.get("average_confidence", 0.0)
                txt_find = single_condition_spec.get("text_to_find")
                cs = single_condition_spec.get("case_sensitive", False)
                min_ocr_conf = single_condition_spec.get("min_ocr_confidence")
                if not txt_find:
                    logger.error(f"R '{rule_name_for_context}',T 'ocr': Missing text_to_find.")
                    return False
                txts_check = [txt_find] if isinstance(txt_find, str) else txt_find
                proc_ocr_txt = actual_txt if cs else actual_txt.lower()
                txt_match = False
                for ti in txts_check:
                    proc_ti = ti if cs else ti.lower()
                    if proc_ti in proc_ocr_txt:
                        txt_match = True
                        break
                if not txt_match:
                    logger.debug(f"R '{rule_name_for_context}',OCR: Text '{txt_find}' NOT found (Conf:{actual_conf:.1f}%).")
                    return False
                conf_crit_met = True
                if min_ocr_conf is not None:
                    conf_crit_met = actual_conf >= float(min_ocr_conf)
                if conf_crit_met:
                    condition_met = True
                    logger.info(f"R '{rule_name_for_context}',OCR:MET. Text '{txt_find}' found (Conf:{actual_conf:.1f}%).")
                if capture_as_var_name and condition_met:
                    captured_value_for_var = actual_txt  # Capture full text if all criteria met
                else:
                    condition_met = False
                    logger.info(f"R '{rule_name_for_context}',OCR:NOT MET. Text found, but conf {actual_conf:.1f}% < {min_ocr_conf}%.")

            elif condition_type == "dominant_color_matches":
                dom_color_res = get_analysis_data_with_fallback(
                    "dominant_colors_result",
                    self.analysis_engine.analyze_dominant_colors,
                    captured_image,
                    self.config_manager.get_setting("analysis_dominant_colors_k", 3),
                    region_name,  # Get K from settings
                )
                if not dom_color_res:
                    return False  # If no dominant colors after fallback
                # ... (rest of dominant_color_matches - same as before) ...
                ebgr = single_condition_spec.get("expected_bgr")
                tol = single_condition_spec.get("tolerance", 10)
                top_n = single_condition_spec.get("check_top_n_dominant", 1)
                min_perc = single_condition_spec.get("min_percentage", 0.0)
                if not ebgr:
                    logger.error(f"R '{rule_name_for_context}',T DomColor:Missing expected_bgr.")
                    return False
                n_check = min(top_n, len(dom_color_res))

                if n_check == 0 and top_n > 0:
                    logger.debug(f"R '{rule_name_for_context}',T DomColor:No dom colors to check.")
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
                if not condition_met:
                    logger.info(f"R '{rule_name_for_context}',T DomColor:NOT MET.")

            elif condition_type == "always_true":
                condition_met = True
                logger.debug(f"R '{rule_name_for_context}', T 'always_true': Met.")
            else:
                logger.error(f"R '{rule_name_for_context}', Rgn '{region_name}': Unknown cond type '{condition_type}'.")
                return False

            if condition_met and capture_as_var_name and captured_value_for_var is not None:
                variable_context[capture_as_var_name] = captured_value_for_var
                val_snip = str(captured_value_for_var)
                val_snip = (val_snip[:67] + "...") if len(val_snip) > 70 else val_snip
                logger.info(f"R '{rule_name_for_context}', Capture: Var '{capture_as_var_name}'. Snippet: '{val_snip.replace(os.linesep,' ')}'")
                logger.debug(f"R '{rule_name_for_context}', Capture: Full value for '{capture_as_var_name}': {captured_value_for_var}")

        except Exception as e:
            logger.exception(f"R '{rule_name_for_context}', Rgn '{region_name}', T '{condition_type}': Exception: {e}")
            return False

        # Final log for this single condition's outcome
        logger.info(f"R '{rule_name_for_context}', Rgn '{region_name}', SingleCond '{condition_type}': Result = {condition_met}")
        return condition_met

    def _check_condition(
        self, rule_name: str, condition_spec: Dict[str, Any], default_rule_region: Optional[str], all_region_data: Dict[str, Dict[str, Any]], variable_context: Dict[str, Any]
    ) -> bool:  # (Logic for handling compound/single and substitution remains same)
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
                sub_cond_spec_subst = self._substitute_variables(sub_cond_orig_spec, variable_context, ctx_name)
                logger.debug(f"R '{ctx_name}': Subst sub-cond spec: {sub_cond_spec_subst}")
                sub_cond_region_name = sub_cond_spec_subst.get("region", default_rule_region)
                if not sub_cond_region_name:
                    logger.error(f"R '{ctx_name}': Region not specified/no default. Spec: {sub_cond_spec_subst}")
                    sub_result = False
                elif sub_cond_region_name not in all_region_data:
                    logger.error(f"R '{ctx_name}': Region '{sub_cond_region_name}' not in all_region_data (keys: {list(all_region_data.keys())}).")
                    sub_result = False
                else:
                    target_region_data = all_region_data[sub_cond_region_name]
                    sub_result = self._evaluate_single_condition_logic(sub_cond_spec_subst, sub_cond_region_name, target_region_data, ctx_name, variable_context)
                # Result of sub_result is logged by _evaluate_single_condition_logic itself now.
                all_sub_results.append(sub_result)
                if operator == "AND" and not sub_result:
                    logger.info(f"R '{rule_name}': AND short-circuited False by Sub#{i+1}.")
                    return False
                if operator == "OR" and sub_result:
                    logger.info(f"R '{rule_name}': OR short-circuited True by Sub#{i+1}.")
                    return True
            if operator == "AND":
                final_res = all(all_sub_results)
            elif operator == "OR":
                final_res = any(all_sub_results)
            else:
                final_res = False  # Should not happen
            logger.info(f"R '{rule_name}': Compound cond final result = {final_res}.")
            return final_res
        else:  # Single condition
            condition_spec_subst = self._substitute_variables(condition_spec, variable_context, rule_name)
            logger.debug(f"R '{rule_name}': Subst single cond spec: {condition_spec_subst}")
            if not default_rule_region:
                logger.error(f"R '{rule_name}': Single cond, no default region. Spec: {condition_spec_subst}")
                return False
            if default_rule_region not in all_region_data:
                logger.error(f"R '{rule_name}': Default region '{default_rule_region}' not in all_region_data (keys: {list(all_region_data.keys())}).")
                return False
            target_region_data = all_region_data[default_rule_region]
            result = self._evaluate_single_condition_logic(condition_spec_subst, default_rule_region, target_region_data, rule_name, variable_context)
            # Result already logged by _evaluate_single_condition_logic
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
            default_rule_region = rule.get("region")
            if not original_condition_spec or not original_action_spec:
                logger.warning(f"R '{rule_name}': Missing cond/action. Skipping.")
                continue
            self._last_template_match_info = {"found": False}
            rule_variable_context: Dict[str, Any] = {}
            logger.debug(f"Evaluating rule: '{rule_name}' with default region '{default_rule_region}'")
            try:
                condition_is_met = self._check_condition(rule_name, original_condition_spec, default_rule_region, all_region_data, rule_variable_context)
                if condition_is_met:  # Overall condition result already logged by _check_condition or its delegates
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
                    action_target_region_name = action_spec_subst.get("target_region", default_rule_region)  # Use substituted spec
                    if action_target_region_name:
                        action_context["target_region_config"] = self.config_manager.get_region_config(action_target_region_name)
                        if not action_context["target_region_config"]:
                            logger.warning(f"R '{rule_name}', Action '{action_spec_subst.get('type')}': target_region '{action_target_region_name}' not in profile regions.")

                    full_action_to_execute = {**action_spec_subst, "context": action_context}
                    triggered_actions_specs.append(full_action_to_execute)
                    self.action_executor.execute_action(full_action_to_execute)
                # else: Overall condition NOT MET already logged by _check_condition or its delegates.
            except Exception as e:
                logger.exception(f"R '{rule_name}': Unexpected error during rule eval/action prep: {e}")
        logger.info(f"Finished rule evaluation. {len(triggered_actions_specs)} actions were triggered in this cycle.")
        return triggered_actions_specs
