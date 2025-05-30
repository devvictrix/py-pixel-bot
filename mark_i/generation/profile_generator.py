import logging
import json
import copy
from typing import Dict, Any, Optional, List

import numpy as np # For image data type hinting
from PIL import Image # For potential image manipulations if needed by suggestions

from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.core.config_manager import ConfigManager
from mark_i.generation.strategy_planner import IntermediatePlan, IntermediatePlanStep

# Standardized logger
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.generation.profile_generator")

# Default structures for profile elements, used if AI suggestions are partial or need defaults
DEFAULT_REGION_STRUCTURE_PG = {"name": "", "x": 10, "y": 10, "width": 200, "height": 150, "comment": "AI-suggested region placeholder"}
DEFAULT_CONDITION_STRUCTURE_PG = {"type": "always_true", "comment": "AI-suggested condition placeholder"}
DEFAULT_ACTION_STRUCTURE_PG = {"type": "log_message", "message": "AI-suggested action placeholder executed", "level": "INFO", "comment": "AI-suggested action placeholder"}
DEFAULT_RULE_STRUCTURE_PG = {"name": "", "region": "", "condition": {}, "action": {}, "comment": "AI-generated rule placeholder"}
DEFAULT_TEMPLATE_STRUCTURE_PG = {"name": "", "filename": "placeholder_template.png", "comment": "AI-suggested template placeholder - user must capture"}

# Models for ProfileGenerator's internal AI assistance calls
DEFAULT_REGION_SUGGESTION_MODEL = "gemini-1.5-flash-latest" # Fast for visual box suggestion
DEFAULT_LOGIC_SUGGESTION_MODEL = "gemini-1.5-pro-latest"  # More reasoning for condition/action
DEFAULT_ELEMENT_REFINE_MODEL = "gemini-1.5-flash-latest" # Fast for targeted visual refinement


class ProfileGenerator:
    """
    Takes an "intermediate_plan" and interactively guides the user (via GUI)
    to translate each plan step into Mark-I profile elements.
    Uses GeminiAnalyzer for AI-assisted suggestions for regions, conditions, actions,
    and refining element locations.
    """

    def __init__(
        self,
        gemini_analyzer: GeminiAnalyzer,
        config_manager: ConfigManager
    ):
        if not isinstance(gemini_analyzer, GeminiAnalyzer) or not gemini_analyzer.client_initialized:
            logger.critical("ProfileGenerator CRITICAL: Initialized with invalid/uninitialized GeminiAnalyzer. AI-assist will fail.")
            raise ValueError("Valid, initialized GeminiAnalyzer instance required for ProfileGenerator.")
        self.gemini_analyzer = gemini_analyzer

        if not isinstance(config_manager, ConfigManager):
            logger.critical("ProfileGenerator CRITICAL: Initialized without valid ConfigManager. Profile saving will fail.")
            raise ValueError("ConfigManager instance required.")
        self.config_manager = config_manager
        
        self.intermediate_plan: Optional[IntermediatePlan] = None
        self.current_plan_step_index: int = -1
        self.generated_profile_data: Dict[str, Any] = {}
        self.current_full_visual_context_np: Optional[np.ndarray] = None # Full screen/app BGR NumPy image

        logger.info("ProfileGenerator initialized with AI-assist capabilities.")

    def start_profile_generation(
        self,
        intermediate_plan: IntermediatePlan,
        profile_description: str = "AI-Generated Profile",
        initial_profile_settings: Optional[Dict[str, Any]] = None,
        initial_full_screen_context_np: Optional[np.ndarray] = None # BGR NumPy array
    ) -> bool: # Unchanged from Phase 1 Impl
        if not isinstance(intermediate_plan, list) or not intermediate_plan:
            logger.error("ProfileGenerator: Cannot start: Intermediate plan empty/invalid."); return False
        self.intermediate_plan = intermediate_plan
        self.current_plan_step_index = -1
        from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE
        self.generated_profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self.generated_profile_data["profile_description"] = profile_description
        if initial_profile_settings and isinstance(initial_profile_settings, dict):
            self.generated_profile_data["settings"].update(initial_profile_settings)
        self.generated_profile_data.setdefault("regions", []); self.generated_profile_data.setdefault("templates", []); self.generated_profile_data.setdefault("rules", [])
        if initial_full_screen_context_np is not None and isinstance(initial_full_screen_context_np, np.ndarray):
            self.current_full_visual_context_np = initial_full_screen_context_np
            logger.info(f"ProfileGenerator: Initial visual context (shape: {initial_full_screen_context_np.shape}) set.")
        else: self.current_full_visual_context_np = None; logger.warning("ProfileGenerator: No initial visual context provided.")
        logger.info(f"ProfileGenerator: New profile generation started. Plan has {len(self.intermediate_plan)} steps. Desc: '{profile_description}'."); return True

    def set_current_visual_context(self, screen_capture_np: Optional[np.ndarray]): # Unchanged from Phase 1 Impl
        if screen_capture_np is not None and isinstance(screen_capture_np, np.ndarray): self.current_full_visual_context_np = screen_capture_np; logger.debug(f"PG: Visual context updated (shape: {screen_capture_np.shape}).")
        elif screen_capture_np is None: self.current_full_visual_context_np = None; logger.debug("PG: Visual context cleared.")
        else: logger.warning("PG: Invalid visual context (not NumPy array or None).")

    def get_current_plan_step(self) -> Optional[IntermediatePlanStep]: # Unchanged from Phase 1 Impl
        if self.intermediate_plan and 0 <= self.current_plan_step_index < len(self.intermediate_plan):
            return self.intermediate_plan[self.current_plan_step_index]
        return None

    def advance_to_next_plan_step(self) -> Optional[IntermediatePlanStep]: # Unchanged from Phase 1 Impl
        if not self.intermediate_plan: return None
        if self.current_plan_step_index < len(self.intermediate_plan) - 1:
            self.current_plan_step_index += 1; current_step = self.intermediate_plan[self.current_plan_step_index]
            logger.info(f"PG: Advanced to plan step {current_step.get('step_id', self.current_plan_step_index + 1)}: \"{current_step.get('description', 'N/A')}\""); return current_step
        else: self.current_plan_step_index = len(self.intermediate_plan); logger.info("PG: All plan steps processed."); return None

    # --- AI-Assisted Element Suggestion Methods (IMPLEMENTED for Phase 2 GUI & AI Assist) ---

    def suggest_region_for_step(self, plan_step: IntermediatePlanStep) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini and current_full_visual_context_np to suggest a relevant region
        (as a bounding box) for the current plan step.

        Returns:
            A dictionary like {"box": [x,y,w,h], "reasoning": "...", "suggested_region_name_hint": "..."} or None.
            Box coordinates are relative to self.current_full_visual_context_np.
        """
        log_prefix = f"PG.SuggestRegion (StepID: {plan_step.get('step_id', 'N/A')})"
        step_description = plan_step.get("description", "")
        logger.info(f"{log_prefix}: Requesting AI region suggestion for step: \"{step_description}\"")

        if not self.gemini_analyzer: logger.error(f"{log_prefix}: GeminiAnalyzer not available."); return None
        if self.current_full_visual_context_np is None: logger.warning(f"{log_prefix}: No current visual context image."); return None
        if not step_description: logger.warning(f"{log_prefix}: Plan step description empty."); return None

        prompt = (
            f"You are an AI assistant helping to define regions for visual automation. "
            f"The user is working on an automation step described as: \"{step_description}\".\n"
            f"Analyze the provided full screen image.\n"
            f"Identify the single most relevant rectangular region (bounding box) on this image for executing this task step. The region should be focused but large enough to contain key elements for the step.\n"
            f"Respond ONLY with a single JSON object containing these keys:\n"
            f"  - \"box\": [x, y, width, height] (integers, coordinates relative to the top-left of the provided image, ensure width and height are positive and greater than zero).\n"
            f"  - \"reasoning\": \"A brief explanation why you chose this region for this specific step.\"\n"
            f"  - \"suggested_region_name_hint\": \"A short, descriptive, snake_case name hint for this region (e.g., login_panel, main_document_area, confirm_button_zone)\".\n"
            f"If no specific sub-region seems highly relevant, suggest a larger encompassing area like an application window if identifiable, or the full image as a last resort if the step is very general (e.g., 'Wait for any change')."
        )
        logger.debug(f"{log_prefix}: Region suggestion prompt sent to Gemini.")

        response = self.gemini_analyzer.query_vision_model(
            prompt=prompt, # Prompt first
            image_data=self.current_full_visual_context_np,
            model_name_override=DEFAULT_REGION_SUGGESTION_MODEL
        )

        if response["status"] == "success" and response["json_content"]:
            try:
                content = response["json_content"]
                if isinstance(content, dict) and isinstance(content.get("box"), list) and len(content["box"]) == 4 and \
                   all(isinstance(n, (int, float)) for n in content["box"]) and \
                   int(round(content["box"][2])) > 0 and int(round(content["box"][3])) > 0: # width and height > 0
                    
                    int_box = [int(round(n)) for n in content["box"]]
                    name_hint_raw = str(content.get("suggested_region_name_hint", f"step{plan_step.get('step_id')}_region")).strip()
                    name_hint = "".join(c if c.isalnum() else "_" for c in name_hint_raw).lower() # Sanitize to snake_case
                    
                    suggested_data = {
                        "box": int_box, # [x,y,w,h]
                        "reasoning": str(content.get("reasoning", "No reasoning provided.")),
                        "suggested_region_name_hint": name_hint
                    }
                    logger.info(f"{log_prefix}: AI suggested region: Box={suggested_data['box']}, Hint='{suggested_data['suggested_region_name_hint']}'. Reasoning: {suggested_data['reasoning']}")
                    return suggested_data
                else:
                    logger.warning(f"{log_prefix}: AI region suggestion response has invalid 'box' data: {content.get('box')}")
            except Exception as e_parse:
                logger.error(f"{log_prefix}: Error parsing AI region suggestion JSON: {e_parse}. Response: {response['json_content']}", exc_info=True)
        else:
            logger.error(f"{log_prefix}: AI region suggestion query failed. Status: {response['status']}, Error: {response.get('error_message')}")
        
        return None

    def suggest_logic_for_step(
        self, plan_step: IntermediatePlanStep, focused_region_image: np.ndarray, focused_region_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Suggests Mark-I condition and action JSON structures for the current plan step,
        analyzing the focused_region_image.
        """
        log_prefix = f"PG.SuggestLogic (StepID: {plan_step.get('step_id')}, Region: '{focused_region_name}')"
        step_description = plan_step.get("description", "")
        required_user_inputs = plan_step.get("required_user_input_for_step", []) # List of placeholder names
        logger.info(f"{log_prefix}: Requesting AI logic suggestion for step: \"{step_description}\"")

        if not self.gemini_analyzer: logger.error(f"{log_prefix}: GeminiAnalyzer NA."); return None
        if focused_region_image is None: logger.warning(f"{log_prefix}: No focused region image."); return None
        if not step_description: logger.warning(f"{log_prefix}: Plan step description empty."); return None

        condition_example_str = json.dumps({"type": "ocr_contains_text", "text_to_find": "example", "region": focused_region_name})
        action_example_str = json.dumps({"type": "click", "target_relation": "center_of_region", "target_region": focused_region_name})

        prompt = (
            f"You are an AI expert for the Mark-I visual automation tool, helping to translate a plan step into a rule.\n"
            f"Current Plan Step: \"{step_description}\"\n"
            f"This step applies to the screen region named '{focused_region_name}', an image of which is provided.\n"
            f"User will need to provide values for these placeholders later: {required_user_inputs if required_user_inputs else 'None'}.\n\n"
            f"Suggest one Mark-I 'condition' object and one 'action' object to implement this step. "
            f"If no specific condition is needed before the action, use {{\"type\": \"always_true\"}} for the condition.\n"
            f"Valid Mark-I condition types: {json.dumps(['pixel_color', 'average_color_is', 'template_match_found', 'ocr_contains_text', 'dominant_color_matches', 'gemini_vision_query', 'always_true'])}.\n"
            f"Valid Mark-I action types: {json.dumps(['click', 'type_text', 'press_key', 'log_message'])}.\n\n"
            f"Key considerations for your suggestion:\n"
            f"1. If the step involves interacting with a specific UI element (e.g., 'click the login button', 'type into username field'), the 'action' parameters *MUST* include a 'target_description' field with a clear textual description of that element (e.g., \"target_description\": \"the blue button labeled 'Login'\"). The system will attempt to visually refine this target later.\n"
            f"2. If the step clearly implies finding a unique visual icon or very distinct small image, suggest 'template_match_found' for the condition. Use 'template_filename': 'USER_NEEDS_TO_CAPTURE_TEMPLATE_FOR_{{element_name_hint}}' (e.g., USER_NEEDS_TO_CAPTURE_TEMPLATE_FOR_save_icon).\n"
            f"3. For parameters requiring specific user data not in the step description (like text to type, values for checks), use placeholders like 'USER_INPUT_REQUIRED__{{param_name}}' (e.g., for a 'type_text' action: {{\"type\":\"type_text\", \"text\":\"USER_INPUT_REQUIRED__text_for_username_field\"}}).\n"
            f"4. If the step is mainly an observation or check (e.g., 'verify text X is visible'), the 'action' might be a 'log_message', or the 'condition' itself might be the primary outcome (e.g. a `gemini_vision_query` that checks the state).\n\n"
            f"Respond ONLY with a single JSON object with these top-level keys:\n"
            f"  - \"suggested_condition\": {{...Mark-I condition JSON...}} (Example: {condition_example_str})\n"
            f"  - \"suggested_action\": {{...Mark-I action JSON...}} (Example: {action_example_str})\n"
            f"  - \"element_to_refine_description\": \"Textual description of the key UI element from your suggested action that needs precise visual location (e.g., 'the login button', 'the username field'). This should match the 'target_description' in your action if one exists. Set to null if not applicable (e.g., action is 'log_message' or 'press_key' without a visual target).\"\n"
            f"  - \"reasoning\": \"Briefly, why you chose this condition and action for this step based on the step description and the provided image of region '{focused_region_name}'.\"\n\n"
            f"Analyze the provided image of region '{focused_region_name}' and the step description carefully."
        )
        logger.debug(f"{log_prefix}: Logic suggestion prompt prepared (len ~{len(prompt)}).")

        response = self.gemini_analyzer.query_vision_model(
            prompt=prompt,
            image_data=focused_region_image,
            model_name_override=DEFAULT_LOGIC_SUGGESTION_MODEL
        )

        if response["status"] == "success" and response["json_content"]:
            try:
                content = response["json_content"]
                if isinstance(content, dict) and \
                   isinstance(content.get("suggested_condition"), dict) and \
                   isinstance(content.get("suggested_action"), dict):
                    # Further validate types of condition and action if needed here
                    s_cond = content["suggested_condition"]
                    s_act = content["suggested_action"]
                    if not s_cond.get("type") in ALL_CONDITION_TYPES_FROM_CONFIG: s_cond["type"] = "always_true"; logger.warning(f"{log_prefix}: AI suggested invalid condition type '{s_cond.get('type')}', defaulting to 'always_true'.")
                    if not s_act.get("type") in ALL_ACTION_TYPES_FROM_CONFIG: s_act["type"] = "log_message"; logger.warning(f"{log_prefix}: AI suggested invalid action type '{s_act.get('type')}', defaulting to 'log_message'.")
                    
                    # Ensure region is not in AI suggested condition/action; it's implicitly the focused_region_name
                    s_cond.pop("region", None)
                    if s_act.get("type") == "click": s_act.pop("target_region", None) # Click target related to element_to_refine


                    logger.info(f"{log_prefix}: AI suggested logic: CondType='{s_cond.get('type')}', ActType='{s_act.get('type')}'")
                    logger.debug(f"{log_prefix}: Full AI logic suggestion: {json.dumps(content, indent=2)}")
                    return content
                else:
                    logger.warning(f"{log_prefix}: AI logic suggestion response has invalid structure. Content: {content}")
            except Exception as e_parse:
                logger.error(f"{log_prefix}: Error parsing AI logic suggestion JSON: {e_parse}. Response: {response['json_content']}", exc_info=True)
        else:
            logger.error(f"{log_prefix}: AI logic suggestion query failed. Status: {response['status']}, Error: {response.get('error_message')}")
            if response.get("text_content"): logger.error(f"{log_prefix}: Gemini raw text (logic failure): {response['text_content'][:500]}")
        return None

    def refine_element_location( # Unchanged from previous full version
        self, element_description: str, focused_region_image: np.ndarray, focused_region_name: str, task_rule_name_for_log: str = "AI_Gen_Profile"
    ) -> Optional[List[Dict[str, Any]]]:
        log_prefix = f"PG.RefineElement (Elem: '{element_description[:30]}...', Rgn: '{focused_region_name}')"
        logger.info(f"{log_prefix}: Requesting AI bounding box refinement.")
        if not self.gemini_analyzer or not self.gemini_analyzer.client_initialized: logger.error(f"{log_prefix}: GeminiAnalyzer NA."); return None
        if focused_region_image is None: logger.warning(f"{log_prefix}: No focused region image."); return None
        if not element_description: logger.warning(f"{log_prefix}: Element description empty."); return None
        prompt = (f"Precise visual element locator. In image of region '{focused_region_name}', identify all distinct elements matching: \"{element_description}\".\n"
                  f"Respond ONLY JSON: {{\"elements\": [{{\"found\": true/false, \"box\": [x,y,w,h_or_null], \"label_suggestion\":\"brief_label_if_multiple\"}}]}}.\n"
                  f"If none, \"elements\" is empty or {{\"elements\": [{{\"found\": false, \"box\": null}}]}}.")
        response = self.gemini_analyzer.query_vision_model(focused_region_image, prompt, model_name_override=DEFAULT_ELEMENT_REFINE_MODEL)
        candidates: List[Dict[str, Any]] = []
        if response["status"] == "success" and response["json_content"]:
            try:
                content = response["json_content"]
                if isinstance(content,dict) and isinstance(content.get("elements"),list):
                    for elem_data in content["elements"]:
                        if isinstance(elem_data,dict) and elem_data.get("found") and isinstance(elem_data.get("box"),list) and len(elem_data["box"])==4 and all(isinstance(n,(int,float)) for n in elem_data["box"]) and elem_data["box"][2]>0 and elem_data["box"][3]>0:
                            box = [int(round(n)) for n in elem_data["box"]]
                            candidates.append({"box":box, "label_suggestion":elem_data.get("label_suggestion", element_description), "confidence":elem_data.get("confidence",1.0)}) # GUI needs "box"
                    if candidates: logger.info(f"{log_prefix}: Refined to {len(candidates)} candidates. First: {candidates[0]['box']}")
                    else: logger.info(f"{log_prefix}: Refinement found no matching elements or box data invalid.")
                    return candidates # Can be empty list
            except Exception as e: logger.error(f"{log_prefix}: Error parsing refinement JSON: {e}. Resp: {response['json_content']}", exc_info=True)
        else: logger.error(f"{log_prefix}: Refinement query failed. Status: {response['status']}, Err: {response.get('error_message')}")
        return None

    # --- Methods for adding confirmed elements (unchanged from Phase 1 Impl) ---
    def add_region_definition(self, region_data: Dict[str, Any]) -> bool: # Unchanged
        if not (isinstance(region_data, dict) and region_data.get("name") and all(isinstance(region_data.get(k), int) for k in ["x","y","width","height"])): logger.error(f"PG: Invalid region data to add: {region_data}"); return False
        final_data = {**copy.deepcopy(DEFAULT_REGION_STRUCTURE_PG), **region_data}; self.generated_profile_data.setdefault("regions", []).append(final_data)
        logger.info(f"PG: Region '{final_data['name']}' added to draft."); return True

    def add_template_definition(self, template_data: Dict[str, Any]) -> bool: # Unchanged
        if not (isinstance(template_data, dict) and template_data.get("name") and template_data.get("filename")): logger.error(f"PG: Invalid template data: {template_data}"); return False
        final_data = {**copy.deepcopy(DEFAULT_TEMPLATE_STRUCTURE_PG), **template_data}; self.generated_profile_data.setdefault("templates", []).append(final_data)
        logger.info(f"PG: Template '{final_data['name']}' added to draft."); return True

    def add_rule_definition(self, rule_data: Dict[str, Any]) -> bool: # Unchanged
        if not (isinstance(rule_data, dict) and rule_data.get("name") and isinstance(rule_data.get("condition"),dict) and isinstance(rule_data.get("action"),dict)): logger.error(f"PG: Invalid rule data: {rule_data}"); return False
        final_data = copy.deepcopy(DEFAULT_RULE_STRUCTURE_PG); final_data.update(rule_data)
        final_data["condition"] = {**copy.deepcopy(DEFAULT_CONDITION_STRUCTURE_PG), **(rule_data.get("condition",{}))}
        final_data["action"] = {**copy.deepcopy(DEFAULT_ACTION_STRUCTURE_PG), **(rule_data.get("action",{}))}
        self.generated_profile_data.setdefault("rules",[]).append(final_data)
        logger.info(f"PG: Rule '{final_data['name']}' added to draft."); return True

    def get_generated_profile_data(self) -> Dict[str, Any]: # Unchanged
        return copy.deepcopy(self.generated_profile_data)

    def save_generated_profile(self, filepath_to_save: str) -> bool: # Unchanged
        if not self.generated_profile_data: logger.error("PG: No profile data to save."); return False
        if not filepath_to_save: logger.error("PG: No filepath to save profile."); return False
        try: self.config_manager.update_profile_data(self.generated_profile_data); return self.config_manager.save_current_profile(filepath_to_save)
        except Exception as e: logger.error(f"PG: Failed to save generated profile to '{filepath_to_save}': {e}", exc_info=True); return False