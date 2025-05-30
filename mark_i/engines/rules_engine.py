import logging
import os # For os.linesep in log formatting and path joining
import re # For variable substitution regex
from typing import Dict, List, Any, Optional, Tuple, Set, Callable # Standard typing imports
from collections import defaultdict # For _analysis_requirements_per_region

import cv2 # For image operations if any (e.g. loading templates)
import numpy as np # For image data type

from mark_i.core.config_manager import ConfigManager
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_analyzer import GeminiAnalyzer # For gemini_vision_query
from mark_i.engines.gemini_decision_module import GeminiDecisionModule # For gemini_perform_task

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.rules_engine")

# Regex for finding placeholders like {var_name} or {var_name.key1.0.key2}
PLACEHOLDER_REGEX = re.compile(r"\{([\w_]+)((\.?[\w_]+)*(\.\d+)*)*\}") # Allows more complex paths
TEMPLATES_SUBDIR_NAME = "templates" # Standard subdirectory for template images


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
        self,
        config_manager: ConfigManager,
        analysis_engine: AnalysisEngine,
        action_executor: ActionExecutor,
        gemini_decision_module: Optional[GeminiDecisionModule] = None # For NLU tasks
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
        self.gemini_decision_module = gemini_decision_module # Store instance

        self.profile_data = self.config_manager.get_profile_data() # Get a copy
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
            self.gemini_analyzer_for_query = GeminiAnalyzer(
                api_key=gemini_api_key_from_env,
                default_model_name=default_gemini_model_from_settings
            )
            if not self.gemini_analyzer_for_query.client_initialized:
                logger.warning("RulesEngine: GeminiAnalyzer (for vision query conditions) failed API client initialization. `gemini_vision_query` conditions will likely fail.")
                self.gemini_analyzer_for_query = None # Ensure it's None if unusable
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

    def _parse_rule_analysis_dependencies(self): # No changes from previous full version
        logger.debug("RulesEngine: Parsing rule analysis dependencies for pre-emptive local analyses...")
        if not self.rules: return

        for i, rule in enumerate(self.rules):
            rule_name = rule.get("name", f"RuleIdx{i}")
            default_rule_region = rule.get("region")
            condition_spec_outer = rule.get("condition")
            if not isinstance(condition_spec_outer, dict): continue

            conditions_to_parse: List[Tuple[Dict[str, Any], Optional[str]]] = []
            if "logical_operator" in condition_spec_outer and isinstance(condition_spec_outer.get("sub_conditions"), list):
                for sub_cond in condition_spec_outer["sub_conditions"]:
                    if isinstance(sub_cond, dict): conditions_to_parse.append((sub_cond, sub_cond.get("region", default_rule_region)))
            else: conditions_to_parse.append((condition_spec_outer, condition_spec_outer.get("region", default_rule_region)))

            for cond_spec, target_rgn in conditions_to_parse:
                cond_type = cond_spec.get("type")
                local_analysis_needed: Optional[str] = None
                if cond_type == "ocr_contains_text": local_analysis_needed = "ocr"
                elif cond_type == "dominant_color_matches": local_analysis_needed = "dominant_color"
                elif cond_type == "average_color_is": local_analysis_needed = "average_color"
                
                if local_analysis_needed and target_rgn:
                    self._analysis_requirements_per_region[target_rgn].add(local_analysis_needed)
                    # logger.debug(f"Dependency: Rule '{rule_name}', CondType '{cond_type}', Region '{target_rgn}' -> Requires Local '{local_analysis_needed}'")
        # logger.info(f"RulesEngine: Local analysis dependency parsing complete.")

    def get_analysis_requirements_for_region(self, region_name: str) -> Set[str]: # No changes
        return self._analysis_requirements_per_region.get(region_name, set())

    def _load_template_image_for_rule(self, template_filename: str, rule_name_for_context: str) -> Optional[np.ndarray]: # No changes
        profile_base = self.config_manager.get_profile_base_path()
        if not profile_base: logger.error(f"R '{rule_name_for_context}': Cannot load template '{template_filename}', profile unsaved (no base path)."); return None
        cache_key = (profile_base, template_filename)
        if cache_key in self._loaded_templates: return self._loaded_templates[cache_key]
        
        full_path = os.path.join(profile_base, TEMPLATES_SUBDIR_NAME, template_filename)
        if not os.path.exists(full_path): logger.error(f"R '{rule_name_for_context}': Template file not found: '{full_path}'."); self._loaded_templates[cache_key] = None; return None
        try:
            img = cv2.imread(full_path, cv2.IMREAD_COLOR)
            if img is None: raise ValueError("cv2.imread returned None, file might be corrupted or not an image.")
            logger.info(f"R '{rule_name_for_context}': Loaded template '{template_filename}' (Shape: {img.shape}).")
            self._loaded_templates[cache_key] = img; return img
        except Exception as e: logger.exception(f"R '{rule_name_for_context}': Error loading template '{full_path}': {e}"); self._loaded_templates[cache_key] = None; return None

    def _substitute_variables(self, input_value: Any, variable_context: Dict[str, Any], log_context_prefix: str) -> Any: # No changes
        if not isinstance(input_value, (str, list, dict)): return input_value
        if not variable_context: return input_value # No variables to substitute

        if isinstance(input_value, str):
            def replace_match(match_obj: re.Match) -> str:
                full_placeholder, var_name, dot_path_full, _dot_path_keys, _dot_path_indices = match_obj.groups()
                # logger.debug(f"{log_context_prefix}, Subst: Placeholder='{full_placeholder}', Var='{var_name}', Path='{dot_path_full or ''}'")
                if var_name in variable_context:
                    current_val = variable_context[var_name]
                    if dot_path_full: # Path like ".value.box.0"
                        path_keys = dot_path_full.strip(".").split(".")
                        try:
                            for key_part in path_keys:
                                if isinstance(current_val, dict): current_val = current_val[key_part]
                                elif isinstance(current_val, list) and key_part.isdigit(): current_val = current_val[int(key_part)]
                                else: logger.warning(f"{log_context_prefix}, Subst: Cannot access '{key_part}' in '{var_name}'. Path: '{dot_path_full}'. Placeholder left."); return full_placeholder
                            return str(current_val)
                        except (KeyError, IndexError, TypeError) as e: logger.warning(f"{log_context_prefix}, Subst: Path error for '{var_name}{dot_path_full}': {e}. Placeholder left."); return full_placeholder
                    return str(current_val) # No dot path, just the var
                logger.warning(f"{log_context_prefix}, Subst: Variable '{var_name}' not in context. Placeholder '{full_placeholder}' left."); return full_placeholder
            return PLACEHOLDER_REGEX.sub(replace_match, input_value)
        elif isinstance(input_value, list):
            return [self._substitute_variables(item, variable_context, log_context_prefix) for item in input_value]
        elif isinstance(input_value, dict):
            return {k: self._substitute_variables(v, variable_context, log_context_prefix) for k, v in input_value.items()}
        return input_value # Should not be reached

    def _evaluate_single_condition_logic( # No changes from previous full version
        self, single_condition_spec: Dict[str, Any], region_name: str, region_data: Dict[str, Any], rule_name_for_context: str, variable_context: Dict[str, Any]
    ) -> bool:
        condition_type = single_condition_spec.get("type"); capture_as = single_condition_spec.get("capture_as")
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond '{condition_type}'"
        if not condition_type: logger.error(f"{log_prefix}: 'type' missing."); return False
        
        img = region_data.get("image"); met = False; cap_val: Any = None

        def get_data(key, func, *args):
            d = region_data.get(key)
            if d is None and img is not None:
                try: d = func(*args)
                except Exception as e: logger.error(f"{log_prefix}: Fallback calc for '{key}' failed: {e}", exc_info=True); d=None
            return d

        try:
            if condition_type == "pixel_color":
                rx,ry,ebgr,tol = map(single_condition_spec.get,["relative_x","relative_y","expected_bgr","tolerance"],[0,0,None,0])
                if img is not None and ebgr is not None: met = self.analysis_engine.analyze_pixel_color(img,rx,ry,ebgr,tol,rule_name_for_context)
            elif condition_type == "average_color_is":
                avg_c = get_data("average_color", self.analysis_engine.analyze_average_color, img, rule_name_for_context)
                ebgr,tol = map(single_condition_spec.get,["expected_bgr","tolerance"],[None,10])
                if avg_c is not None and ebgr is not None: met = np.all(np.abs(np.array(avg_c)-np.array(ebgr))<=tol)
            elif condition_type == "template_match_found":
                tpl_fn,min_c = single_condition_spec.get("template_filename"),float(single_condition_spec.get("min_confidence",0.8))
                if img is not None and tpl_fn:
                    tpl_img = self._load_template_image_for_rule(tpl_fn, rule_name_for_context)
                    if tpl_img is not None:
                        match_res = self.analysis_engine.match_template(img,tpl_img,min_c,rule_name_for_context,tpl_fn)
                        if match_res: met=True; self._last_template_match_info={"found":True,**match_res,"matched_region_name":region_name};_ = cap_val = {"value":match_res,"_source_region_for_capture_":region_name} if capture_as else None
                        else: self._last_template_match_info={"found":False}
            elif condition_type == "ocr_contains_text":
                ocr_d = get_data("ocr_analysis_result",self.analysis_engine.ocr_extract_text,img,rule_name_for_context)
                if ocr_d and "text" in ocr_d:
                    txt,conf = ocr_d.get("text",""),ocr_d.get("average_confidence",0.0)
                    find_p,cs,min_c_s = map(single_condition_spec.get,["text_to_find","case_sensitive","min_ocr_confidence"],[None,False,None])
                    find_l = ([s.strip() for s in find_p.split(',')] if isinstance(find_p,str) else [str(s).strip() for s in find_p] if isinstance(find_p,list) else [])
                    min_c_f = float(min_c_s) if min_c_s and str(min_c_s).strip() else None
                    if find_l:
                        proc_txt = txt if cs else txt.lower()
                        txt_match = any((s if cs else s.lower()) in proc_txt for s in find_l)
                        if txt_match and (min_c_f is None or conf >= min_c_f): met=True; _ = cap_val = {"value":txt,"_source_region_for_capture_":region_name} if capture_as else None
            elif condition_type == "dominant_color_matches":
                dom_c = get_data("dominant_colors_result",self.analysis_engine.analyze_dominant_colors,img,self.config_manager.get_setting("analysis_dominant_colors_k",3),rule_name_for_context)
                if isinstance(dom_c, list):
                    ebgr,tol,top_n,min_p = map(single_condition_spec.get,["expected_bgr","tolerance","check_top_n_dominant","min_percentage"],[None,10,1,0.0])
                    if isinstance(ebgr,list) and len(ebgr)==3:
                        for dci in dom_c[:min(top_n,len(dom_c))]:
                            if isinstance(dci.get("bgr_color"),list) and np.all(np.abs(np.array(dci["bgr_color"])-np.array(ebgr))<=tol) and dci.get("percentage",0.0)>=min_p: met=True;break
            elif condition_type == "gemini_vision_query":
                if self.gemini_analyzer_for_query and img is not None:
                    prompt,model_o = single_condition_spec.get("prompt"),single_condition_spec.get("model_name")
                    if prompt:
                        gem_res = self.gemini_analyzer_for_query.query_vision_model(prompt,img,model_o) # Corrected order for GAv4
                        if gem_res["status"]=="success":
                            txt_r,json_r=gem_res.get("text_content","") or "",gem_res.get("json_content")
                            exp_s_p,cs_c,json_pth,exp_j_v = map(single_condition_spec.get,["expected_response_contains","case_sensitive_response_check","expected_response_json_path","expected_json_value"],[None,False,None,None])
                            subs_l = ([s.strip() for s in exp_s_p.split(',')] if isinstance(exp_s_p,str) else [str(s).strip() for s in exp_s_p] if isinstance(exp_s_p,list) else [])
                            txt_m = not subs_l or any((s if cs_c else s.lower()) in (txt_r if cs_c else txt_r.lower()) for s in subs_l)
                            json_m=True; ext_json_v=None
                            if json_pth and json_r is not None:
                                cur_j=json_r; p_ok=True
                                try:
                                    for kp in json_pth.strip(".").split("."):
                                        if isinstance(cur_j,dict):cur_j=cur_j[kp]
                                        elif isinstance(cur_j,list) and kp.isdigit():cur_j=cur_j[int(kp)]
                                        else: p_ok=False;break
                                    if p_ok: ext_json_v=cur_j
                                except: p_ok=False
                                if not p_ok: json_m=False
                                elif exp_j_v is not None and str(cur_j)!=str(exp_j_v): json_m=False
                            elif json_pth and json_r is None: json_m=False
                            if txt_m and json_m: met=True;_ = cap_val = {"value":(ext_json_v if json_pth and ext_json_v is not None else (json_r if json_r is not None else txt_r)), "_source_region_for_capture_":region_name} if capture_as else None
                else: logger.error(f"{log_prefix}: GeminiAnalyzer (query) or image unavailable.")
            elif condition_type == "always_true": met=True
            else: logger.error(f"{log_prefix}: Unknown type. Fails."); return False
            if met and capture_as and cap_val is not None: variable_context[capture_as]=cap_val; # logger.info(f"{log_prefix}: Captured for '{capture_as}'.") # Too verbose for info
        except Exception as e: logger.exception(f"{log_prefix}: Exception: {e}"); return False
        # logger.log(logging.INFO if met else logging.DEBUG, f"{log_prefix}: Result = {met}") # Log final result once
        return met

    def _check_condition( # No changes from previous full version
        self, rule_name: str, condition_spec: Dict[str, Any], default_rule_region_from_rule: Optional[str], all_region_data: Dict[str, Dict[str, Any]], variable_context: Dict[str, Any]
    ) -> bool:
        log_op = condition_spec.get("logical_operator"); sub_conds = condition_spec.get("sub_conditions")
        if log_op and isinstance(sub_conds,list): # Compound
            op = log_op.upper()
            if op not in ["AND","OR"] or not sub_conds: return False
            # logger.debug(f"R '{rule_name}': Eval compound '{op}' with {len(sub_conds)} subs.")
            for i, sub_c_spec_orig in enumerate(sub_conds):
                ctx_sub = f"{rule_name}/Sub#{i+1}"
                if not isinstance(sub_c_spec_orig,dict): if op=="AND":return False; else: continue
                sub_c_spec_subst = self._substitute_variables(sub_c_spec_orig,variable_context,ctx_sub)
                sub_rgn = sub_c_spec_subst.get("region",default_rule_region_from_rule)
                if not sub_rgn or sub_rgn not in all_region_data: sub_res=False; logger.error(f"R '{ctx_sub}': Region '{sub_rgn}' missing/invalid.")
                else: sub_res = self._evaluate_single_condition_logic(sub_c_spec_subst,sub_rgn,all_region_data[sub_rgn],ctx_sub,variable_context)
                if op=="AND" and not sub_res: return False
                if op=="OR" and sub_res: return True
            return True if op=="AND" else False # All AND true, or no OR true
        else: # Single
            spec_subst = self._substitute_variables(condition_spec,variable_context,rule_name)
            rgn = spec_subst.get("region",default_rule_region_from_rule)
            if not rgn or rgn not in all_region_data: logger.error(f"R '{rule_name}': Single cond region '{rgn}' missing/invalid."); return False
            return self._evaluate_single_condition_logic(spec_subst,rgn,all_region_data[rgn],rule_name,variable_context)


    def evaluate_rules(self, all_region_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluates all rules. If a rule's condition is met, its action is processed.
        For `gemini_perform_task`, invokes `GeminiDecisionModule`.
        For other actions, invokes `ActionExecutor` directly.
        """
        explicitly_executed_standard_actions: List[Dict[str, Any]] = []
        if not self.rules: return explicitly_executed_standard_actions
        
        logger.info(f"RulesEngine: Evaluating {len(self.rules)} rules for current cycle.")
        for rule_idx, rule_config in enumerate(self.rules):
            rule_name = rule_config.get("name", f"RuleIdx{rule_idx}")
            log_prefix_reval = f"R '{rule_name}'"
            original_condition_spec = rule_config.get("condition")
            original_action_spec = rule_config.get("action")
            default_rule_region_name = rule_config.get("region")

            if not (original_condition_spec and isinstance(original_condition_spec, dict) and \
                    original_action_spec and isinstance(original_action_spec, dict)):
                logger.warning(f"{log_prefix_reval}: Invalid or missing condition/action spec. Skipping rule.")
                continue

            self._last_template_match_info = {"found": False} # Reset for each rule's context
            rule_variable_context: Dict[str, Any] = {} # Fresh for each rule

            # logger.debug(f"{log_prefix_reval}: Evaluating. Default region: '{default_rule_region_name}'.")
            try:
                condition_is_met = self._check_condition(
                    rule_name, original_condition_spec, default_rule_region_name,
                    all_region_data, rule_variable_context
                )

                if condition_is_met:
                    action_type_from_spec_orig = original_action_spec.get("type")
                    logger.info(f"{log_prefix_reval}: Condition MET. Preparing action of type '{action_type_from_spec_orig}'.")

                    action_spec_substituted = self._substitute_variables(
                        original_action_spec, rule_variable_context, f"{rule_name}/ActionSubstitution"
                    )
                    action_type_final = action_spec_substituted.get("type") # Get type from substituted spec
                    logger.debug(f"{log_prefix_reval}, Action Prep: Substituted spec: {action_spec_substituted}. Vars used: {rule_variable_context}")
                    
                    if action_type_final == "gemini_perform_task":
                        if self.gemini_decision_module and self.gemini_decision_module.gemini_analyzer: # Check GDM and its analyzer
                            nl_command = action_spec_substituted.get("natural_language_command", action_spec_substituted.get("goal_prompt", ""))
                            ctx_rgn_names_param = action_spec_substituted.get("context_region_names", [])
                            ctx_rgn_names_list = [r.strip() for r in ctx_rgn_names_param.split(',') if r.strip()] if isinstance(ctx_rgn_names_param, str) else \
                                                 [str(r).strip() for r in ctx_rgn_names_param if str(r).strip()] if isinstance(ctx_r_names_param, list) else []
                            
                            task_params_for_gdm = {k:v for k,v in action_spec_substituted.items() if k not in ["type","natural_language_command","goal_prompt","context_region_names"]}
                            
                            # Ensure allowed_actions_override is a list of strings
                            allowed_override = task_params_for_gdm.get("allowed_actions_override", [])
                            if isinstance(allowed_override, str): task_params_for_gdm["allowed_actions_override"] = [a.strip().upper() for a in allowed_override.split(',') if a.strip()]
                            elif isinstance(allowed_override, list): task_params_for_gdm["allowed_actions_override"] = [str(a).strip().upper() for a in allowed_override if str(a).strip()]
                            else: task_params_for_gdm["allowed_actions_override"] = []


                            task_ctx_imgs: Dict[str, np.ndarray] = {}
                            can_run_task = True
                            if not nl_command: logger.error(f"{log_prefix_reval}, NLU Task: 'natural_language_command' missing. Task fails."); can_run_task = False
                            
                            if can_run_task:
                                target_rgns_for_ctx = ctx_rgn_names_list
                                if not target_rgns_for_ctx and default_rule_region_name: target_rgns_for_ctx = [default_rule_region_name]
                                if not target_rgns_for_ctx: logger.error(f"{log_prefix_reval}, NLU Task: No context regions. Task fails."); can_run_task = False
                                else:
                                    for r_name_ctx in target_rgns_for_ctx:
                                        if r_name_ctx in all_region_data and all_region_data[r_name_ctx].get("image") is not None: task_ctx_imgs[r_name_ctx] = all_region_data[r_name_ctx]["image"]
                                        else: logger.error(f"{log_prefix_reval}, NLU Task: Context region '{r_name_ctx}' image missing. Task fails."); can_run_task = False; break
                                    if not task_ctx_imgs and can_run_task: logger.error(f"{log_prefix_reval}, NLU Task: No valid images for context. Task fails."); can_run_task = False
                            
                            if can_run_task:
                                logger.info(f"{log_prefix_reval}: Invoking GeminiDecisionModule for NLU command: '{nl_command[:70]}...'")
                                task_result = self.gemini_decision_module.execute_nlu_task(
                                    task_rule_name=rule_name, natural_language_command=nl_command,
                                    initial_context_images=task_ctx_imgs, task_parameters=task_params_for_gdm
                                )
                                logger.info(f"{log_prefix_reval}, NLU Task Result: Status='{task_result.get('status')}', Msg='{task_result.get('message')}'")
                        else:
                            logger.error(f"{log_prefix_reval}, Action 'gemini_perform_task': GeminiDecisionModule not available/initialized. Task skipped.")
                    else: # Standard action
                        action_exec_ctx = {
                            "rule_name": rule_name, "condition_region": default_rule_region_name,
                            "last_match_info": self._last_template_match_info.copy(),
                            "variables": rule_variable_context.copy(),
                        }
                        full_action_spec = {**action_spec_substituted, "context": action_exec_ctx}
                        logger.info(f"{log_prefix_reval}: Directly executing standard action '{action_type_final}'.")
                        self.action_executor.execute_action(full_action_spec)
                        explicitly_executed_standard_actions.append(full_action_spec)
            except Exception as e_rule:
                logger.exception(f"{log_prefix_reval}: Unexpected error during rule evaluation or action dispatch: {e_rule}")

        logger.info(f"RulesEngine: Cycle finished. {len(explicitly_executed_standard_actions)} standard actions executed directly by RulesEngine.")
        return explicitly_executed_standard_actions