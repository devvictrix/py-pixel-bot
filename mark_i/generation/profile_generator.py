import logging
import json
import copy
import os  # For path joining and directory creation
from typing import Dict, Any, Optional, List

import numpy as np  # For image data type hinting and saving
from PIL import Image  # For potential image manipulations if needed by suggestions
import cv2  # For cv2.imwrite

from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.core.config_manager import ConfigManager, TEMPLATES_SUBDIR_NAME  # Import TEMPLATES_SUBDIR_NAME
from mark_i.generation.strategy_planner import IntermediatePlan, IntermediatePlanStep
from mark_i.ui.gui.gui_config import CONDITION_TYPES as ALL_CONDITION_TYPES_FROM_CONFIG, ACTION_TYPES as ALL_ACTION_TYPES_FROM_CONFIG  # For validation


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
DEFAULT_REGION_SUGGESTION_MODEL = "gemini-1.5-flash-latest"  # Fast for visual box suggestion
DEFAULT_LOGIC_SUGGESTION_MODEL = "gemini-1.5-flash-latest"  # More reasoning for condition/action
DEFAULT_ELEMENT_REFINE_MODEL = "gemini-1.5-flash-latest"  # Fast for targeted visual refinement


class ProfileGenerator:
    """
    Takes an "intermediate_plan" and interactively guides the user (via GUI)
    to translate each plan step into Mark-I profile elements.
    Uses GeminiAnalyzer for AI-assisted suggestions for regions, conditions, actions,
    and refining element locations.
    Handles staging and saving of new template images.
    """

    def __init__(self, gemini_analyzer: GeminiAnalyzer, config_manager: ConfigManager):  # This CM is for the *profile being generated*
        if not isinstance(gemini_analyzer, GeminiAnalyzer) or not gemini_analyzer.client_initialized:
            logger.critical("ProfileGenerator CRITICAL: Initialized with invalid/uninitialized GeminiAnalyzer. AI-assist will fail.")
            raise ValueError("Valid, initialized GeminiAnalyzer instance required for ProfileGenerator.")
        self.gemini_analyzer = gemini_analyzer

        if not isinstance(config_manager, ConfigManager):
            logger.critical("ProfileGenerator CRITICAL: Initialized without valid ConfigManager. Profile saving will fail.")
            raise ValueError("ConfigManager instance required for ProfileGenerator.")
        self.config_manager_for_generated_profile = config_manager  # Renamed for clarity

        self.intermediate_plan: Optional[IntermediatePlan] = None
        self.current_plan_step_index: int = -1
        self.generated_profile_data: Dict[str, Any] = {}  # This will be built up and saved via self.config_manager_for_generated_profile
        self.current_full_visual_context_np: Optional[np.ndarray] = None  # Full screen/app BGR NumPy image

        logger.info("ProfileGenerator initialized with AI-assist capabilities.")

    def start_profile_generation(
        self,
        intermediate_plan: IntermediatePlan,
        profile_description: str = "AI-Generated Profile",
        initial_profile_settings: Optional[Dict[str, Any]] = None,
        initial_full_screen_context_np: Optional[np.ndarray] = None,  # BGR NumPy array
    ) -> bool:
        if not isinstance(intermediate_plan, list) or not intermediate_plan:  # Allow empty plan if AI generates it
            logger.warning("ProfileGenerator: Starting profile generation with an empty or invalid intermediate plan. User will need to define all elements manually or re-generate plan.")
            self.intermediate_plan = []
        else:
            self.intermediate_plan = intermediate_plan

        self.current_plan_step_index = -1  # Ready for first call to advance_to_next_plan_step

        self.config_manager_for_generated_profile._initialize_default_profile_data()
        self.generated_profile_data = self.config_manager_for_generated_profile.get_profile_data()

        self.generated_profile_data["profile_description"] = profile_description
        if initial_profile_settings and isinstance(initial_profile_settings, dict):
            self.generated_profile_data["settings"].update(initial_profile_settings)

        self.generated_profile_data.setdefault("regions", [])
        self.generated_profile_data.setdefault("templates", [])
        self.generated_profile_data.setdefault("rules", [])

        if initial_full_screen_context_np is not None and isinstance(initial_full_screen_context_np, np.ndarray):
            self.current_full_visual_context_np = initial_full_screen_context_np
            logger.info(f"ProfileGenerator: Initial visual context (shape: {initial_full_screen_context_np.shape}) set.")
        else:
            self.current_full_visual_context_np = None
            logger.warning("ProfileGenerator: No initial visual context provided for profile generation.")

        logger.info(f"ProfileGenerator: New profile generation started. Plan has {len(self.intermediate_plan)} steps. Desc: '{profile_description}'.")
        return True

    def set_current_visual_context(self, screen_capture_np: Optional[np.ndarray]):
        if screen_capture_np is not None and isinstance(screen_capture_np, np.ndarray):
            self.current_full_visual_context_np = screen_capture_np
            logger.debug(f"PG: Visual context updated (shape: {screen_capture_np.shape}).")
        elif screen_capture_np is None:
            self.current_full_visual_context_np = None
            logger.debug("PG: Visual context cleared.")
        else:
            logger.warning("PG: Invalid visual context provided (not NumPy array or None).")

    def get_current_plan_step(self) -> Optional[IntermediatePlanStep]:
        if self.intermediate_plan and 0 <= self.current_plan_step_index < len(self.intermediate_plan):
            return self.intermediate_plan[self.current_plan_step_index]
        return None

    def advance_to_next_plan_step(self) -> Optional[IntermediatePlanStep]:
        if not self.intermediate_plan:
            logger.warning("PG: Cannot advance, no intermediate plan loaded.")
            return None
        if self.current_plan_step_index < len(self.intermediate_plan) - 1:
            self.current_plan_step_index += 1
            current_step = self.intermediate_plan[self.current_plan_step_index]
            logger.info(f"PG: Advanced to plan step {current_step.get('step_id', self.current_plan_step_index + 1)}: \"{current_step.get('description', 'N/A')}\"")
            return current_step
        else:  # Reached end of plan
            self.current_plan_step_index = len(self.intermediate_plan)  # Point past the end
            logger.info("PG: All plan steps have been processed.")
            return None

    def suggest_region_for_step(self, plan_step: IntermediatePlanStep) -> Optional[Dict[str, Any]]:
        log_prefix = f"PG.SuggestRegion (StepID: {plan_step.get('step_id', 'N/A')})"
        step_description = plan_step.get("description", "")
        logger.info(f'{log_prefix}: Requesting AI region suggestion for step: "{step_description}"')
        if not self.gemini_analyzer:
            logger.error(f"{log_prefix}: GeminiAnalyzer not available.")
            return None
        if self.current_full_visual_context_np is None:
            logger.warning(f"{log_prefix}: No current visual context image for AI suggestion.")
            return None
        if not step_description:
            logger.warning(f"{log_prefix}: Plan step description is empty, cannot suggest region effectively.")
            return None

        prompt = (
            f"You are an AI assistant helping to define regions for visual automation. "
            f'The user is working on an automation step described as: "{step_description}".\n'
            f"Analyze the provided full screen image.\n"
            f"Identify the single most relevant rectangular region (bounding box) on this image for executing this task step. The region should be focused but large enough to contain key elements for the step.\n"
            f"Respond ONLY with a single JSON object containing these keys:\n"
            f'  - "box": [x, y, width, height] (integers, coordinates relative to the top-left of the provided image, ensure width and height are positive and greater than zero).\n'
            f'  - "reasoning": "A brief explanation why you chose this region for this specific step."\n'
            f'  - "suggested_region_name_hint": "A short, descriptive, snake_case name hint for this region (e.g., login_panel, main_document_area, confirm_button_zone)".\n'
            f"If no specific sub-region seems highly relevant, suggest a larger encompassing area like an application window if identifiable, or the full image as a last resort if the step is very general (e.g., 'Wait for any change')."
        )
        logger.debug(f"{log_prefix}: Region suggestion prompt sent to Gemini.")
        response = self.gemini_analyzer.query_vision_model(prompt=prompt, image_data=self.current_full_visual_context_np, model_name_override=DEFAULT_REGION_SUGGESTION_MODEL)

        if response["status"] == "success" and response["json_content"]:
            try:
                content = response["json_content"]
                if (
                    isinstance(content, dict)
                    and isinstance(content.get("box"), list)
                    and len(content["box"]) == 4
                    and all(isinstance(n, (int, float)) for n in content["box"])
                    and int(round(content["box"][2])) > 0
                    and int(round(content["box"][3])) > 0
                ):

                    int_box = [int(round(n)) for n in content["box"]]
                    name_hint_raw = str(content.get("suggested_region_name_hint", f"step{plan_step.get('step_id','X')}_ai_region")).strip()
                    name_hint = "".join(c if c.isalnum() else "_" for c in name_hint_raw).lower()

                    suggested_data = {"box": int_box, "reasoning": str(content.get("reasoning", "No reasoning provided.")), "suggested_region_name_hint": name_hint}  # [x,y,w,h]
                    logger.info(f"{log_prefix}: AI suggested region: Box={suggested_data['box']}, Hint='{suggested_data['suggested_region_name_hint']}'. Reasoning: {suggested_data['reasoning']}")
                    return suggested_data
                else:
                    logger.warning(f"{log_prefix}: AI region suggestion response has invalid 'box' data or structure: {content}")
            except Exception as e_parse:
                logger.error(f"{log_prefix}: Error parsing AI region suggestion JSON: {e_parse}. Response: {response['json_content']}", exc_info=True)
        else:
            logger.error(f"{log_prefix}: AI region suggestion query failed. Status: {response['status']}, Error: {response.get('error_message')}")
        return None

    def suggest_logic_for_step(self, plan_step: IntermediatePlanStep, focused_region_image: np.ndarray, focused_region_name: str) -> Optional[Dict[str, Any]]:
        log_prefix = f"PG.SuggestLogic (StepID: {plan_step.get('step_id')}, Region: '{focused_region_name}')"
        step_description = plan_step.get("description", "")
        required_user_inputs = plan_step.get("required_user_input_for_step", [])
        logger.info(f'{log_prefix}: Requesting AI logic suggestion for step: "{step_description}"')
        if not self.gemini_analyzer:
            logger.error(f"{log_prefix}: GeminiAnalyzer NA.")
            return None
        if focused_region_image is None:
            logger.warning(f"{log_prefix}: No focused region image for AI logic suggestion.")
            return None
        if not step_description:
            logger.warning(f"{log_prefix}: Plan step description empty for AI logic suggestion.")
            return None

        condition_example_str = json.dumps({"type": "ocr_contains_text", "text_to_find": "example"})  # Removed region from example as it's implicit
        action_example_str = json.dumps({"type": "click", "target_relation": "center_of_region"})  # Removed target_region as it's implicit

        prompt = (
            f"You are an AI expert for the Mark-I visual automation tool, helping to translate a plan step into a rule.\n"
            f'Current Plan Step: "{step_description}"\n'
            f"This step applies to the screen region named '{focused_region_name}', an image of which is provided.\n"
            f"User will need to provide values for these placeholders later: {required_user_inputs if required_user_inputs else 'None'}.\n\n"
            f"Suggest one Mark-I 'condition' object and one 'action' object to implement this step. The condition and action will implicitly target the region '{focused_region_name}' unless overridden by specific action parameters (like 'target_region' for click, which is usually not needed if action is on element in current region).\n"
            f'If no specific condition is needed before the action, use {{"type": "always_true"}} for the condition.\n'
            f"Valid Mark-I condition types: {json.dumps(ALL_CONDITION_TYPES_FROM_CONFIG)}.\n"
            f"Valid Mark-I action types: {json.dumps(ALL_ACTION_TYPES_FROM_CONFIG)}.\n\n"
            f"Key considerations for your suggestion:\n"
            f"1. If the step involves interacting with a specific UI element (e.g., 'click the login button', 'type into username field'), the 'action' parameters *MUST* include a 'target_description' field with a clear textual description of that element (e.g., \"target_description\": \"the blue button labeled 'Login'\"). The system will attempt to visually refine this target later using the provided region image.\n"
            f"2. If the step clearly implies finding a unique visual icon or very distinct small image, suggest 'template_match_found' for the condition. Use 'template_filename': 'USER_NEEDS_TO_CAPTURE_TEMPLATE_FOR_{{element_name_hint}}' (e.g., USER_NEEDS_TO_CAPTURE_TEMPLATE_FOR_save_icon). Do NOT include 'region' in this template condition.\n"
            f'3. For parameters requiring specific user data not in the step description (like text to type, values for checks), use placeholders like \'USER_INPUT_REQUIRED__{{param_name}}\' (e.g., for a \'type_text\' action: {{"type":"type_text", "text":"USER_INPUT_REQUIRED__text_for_username_field"}}).\n'
            f"4. If the step is mainly an observation or check (e.g., 'verify text X is visible'), the 'action' might be a 'log_message', or the 'condition' itself might be the primary outcome (e.g. a `gemini_vision_query` that checks the state).\n\n"
            f"Respond ONLY with a single JSON object with these top-level keys:\n"
            f'  - "suggested_condition": {{...Mark-I condition JSON...}} (Example: {condition_example_str})\n'
            f'  - "suggested_action": {{...Mark-I action JSON...}} (Example: {action_example_str})\n'
            f"  - \"element_to_refine_description\": \"Textual description of the key UI element from your suggested action that needs precise visual location (e.g., 'the login button', 'the username field'). This should match the 'target_description' in your action if one exists. Set to null if not applicable (e.g., action is 'log_message' or 'press_key' without a visual target).\"\n"
            f'  - "reasoning": "Briefly, why you chose this condition and action for this step based on the step description and the provided image of region \'{focused_region_name}\'."\n\n'
            f"Analyze the provided image of region '{focused_region_name}' and the step description carefully."
        )
        logger.debug(f"{log_prefix}: Logic suggestion prompt prepared (len ~{len(prompt)}).")
        response = self.gemini_analyzer.query_vision_model(prompt=prompt, image_data=focused_region_image, model_name_override=DEFAULT_LOGIC_SUGGESTION_MODEL)

        if response["status"] == "success" and response["json_content"]:
            try:
                content = response["json_content"]
                if isinstance(content, dict) and isinstance(content.get("suggested_condition"), dict) and isinstance(content.get("suggested_action"), dict):
                    s_cond = content["suggested_condition"]
                    s_act = content["suggested_action"]
                    if not s_cond.get("type") in ALL_CONDITION_TYPES_FROM_CONFIG:
                        s_cond["type"] = "always_true"
                        logger.warning(f"{log_prefix}: AI suggested invalid condition type '{s_cond.get('type')}', defaulting to 'always_true'.")
                    if not s_act.get("type") in ALL_ACTION_TYPES_FROM_CONFIG:
                        s_act["type"] = "log_message"
                        logger.warning(f"{log_prefix}: AI suggested invalid action type '{s_act.get('type')}', defaulting to 'log_message'.")

                    # Remove 'region' from AI suggested condition/action as it's implicit to focused_region_name for this step's rule
                    s_cond.pop("region", None)
                    if s_act.get("type") == "click":
                        s_act.pop("target_region", None)

                    logger.info(f"{log_prefix}: AI suggested logic: CondType='{s_cond.get('type')}', ActType='{s_act.get('type')}'")
                    logger.debug(f"{log_prefix}: Full AI logic suggestion: {json.dumps(content, indent=2)}")
                    return content
                else:
                    logger.warning(f"{log_prefix}: AI logic suggestion response has invalid structure. Content: {content}")
            except Exception as e_parse:
                logger.error(f"{log_prefix}: Error parsing AI logic suggestion JSON: {e_parse}. Response: {response['json_content']}", exc_info=True)
        else:
            logger.error(f"{log_prefix}: AI logic suggestion query failed. Status: {response['status']}, Error: {response.get('error_message')}")
            if response.get("text_content"):
                logger.error(f"{log_prefix}: Gemini raw text (logic failure): {response['text_content'][:500]}")
        return None

    def refine_element_location(
        self, element_description: str, focused_region_image: np.ndarray, focused_region_name: str, task_rule_name_for_log: str = "AI_Gen_Profile"
    ) -> Optional[List[Dict[str, Any]]]:
        log_prefix = f"PG.RefineElement (Elem: '{element_description[:30]}...', Rgn: '{focused_region_name}')"
        logger.info(f"{log_prefix}: Requesting AI bounding box refinement.")
        if not self.gemini_analyzer or not self.gemini_analyzer.client_initialized:
            logger.error(f"{log_prefix}: GeminiAnalyzer NA.")
            return None
        if focused_region_image is None:
            logger.warning(f"{log_prefix}: No focused region image for refinement.")
            return None
        if not element_description:
            logger.warning(f"{log_prefix}: Element description empty for refinement.")
            return None

        prompt = (
            f"Precise visual element locator. In the provided image of region '{focused_region_name}', identify all distinct, clearly visible UI elements that best match the description: \"{element_description}\".\n"
            f"For each element found, respond with its bounding box `[x,y,w,h]` (integers, relative to top-left of image, w/h > 0), a confidence score (0.0-1.0), and a brief label if multiple elements match.\n"
            f'Output ONLY JSON: {{"elements": [{{"found": true, "box": [x,y,w,h], "label_suggestion":"brief_label (e.g., button_top_left)", "confidence_score": 0.0_to_1.0}}]}}.\n'
            f'If no elements match or are too ambiguous, respond with {{"elements": [{{"found": false, "box": null, "reasoning": "why_not_found"}}]}} or an empty elements array.'
        )
        response = self.gemini_analyzer.query_vision_model(
            prompt=prompt, image_data=focused_region_image, model_name_override=DEFAULT_ELEMENT_REFINE_MODEL  # Prompt first for clarity with multimodal
        )
        candidates: List[Dict[str, Any]] = []
        if response["status"] == "success" and response["json_content"]:
            try:
                content = response["json_content"]
                if isinstance(content, dict) and isinstance(content.get("elements"), list):
                    for elem_data in content["elements"]:
                        if (
                            isinstance(elem_data, dict)
                            and elem_data.get("found")
                            and isinstance(elem_data.get("box"), list)
                            and len(elem_data["box"]) == 4
                            and all(isinstance(n, (int, float)) for n in elem_data["box"])
                            and elem_data["box"][2] > 0
                            and elem_data["box"][3] > 0
                        ):  # w,h > 0

                            box = [int(round(n)) for n in elem_data["box"]]
                            candidates.append(
                                {"box": box, "label_suggestion": elem_data.get("label_suggestion", element_description), "confidence": elem_data.get("confidence_score", 1.0)}  # Use confidence_score
                            )
                    if candidates:
                        logger.info(f"{log_prefix}: Refined to {len(candidates)} candidates. First: {candidates[0]['box']}")
                    else:
                        logger.info(f"{log_prefix}: Refinement found no matching elements or box data invalid. Response: {content}")
                    return candidates
            except Exception as e:
                logger.error(f"{log_prefix}: Error parsing refinement JSON: {e}. Resp: {response['json_content']}", exc_info=True)
        else:
            logger.error(f"{log_prefix}: Refinement query failed. Status: {response['status']}, Err: {response.get('error_message')}")
        return None  # Explicitly return None on failure or no valid candidates

    def add_region_definition(self, region_data: Dict[str, Any]) -> bool:
        if not (isinstance(region_data, dict) and region_data.get("name") and all(isinstance(region_data.get(k), int) for k in ["x", "y", "width", "height"])):
            logger.error(f"PG: Invalid region data provided to add_region_definition: {region_data}")
            return False

        # Ensure region name is unique within the draft, or replace if user confirmed overwrite
        existing_regions = self.generated_profile_data.setdefault("regions", [])
        name_to_add = region_data["name"]
        self.generated_profile_data["regions"] = [r for r in existing_regions if r.get("name") != name_to_add]  # Remove old if exists

        final_data_to_add = {**copy.deepcopy(DEFAULT_REGION_STRUCTURE_PG), **region_data}
        self.generated_profile_data["regions"].append(final_data_to_add)
        logger.info(f"PG: Region '{final_data_to_add['name']}' definition added/updated in draft profile.")
        return True

    def add_template_definition(self, template_data: Dict[str, Any]) -> bool:
        if not (isinstance(template_data, dict) and template_data.get("name") and template_data.get("filename")):
            logger.error(f"PG: Invalid template data (missing name or filename): {template_data}")
            return False
        if "_image_data_np_for_save" not in template_data or not isinstance(template_data["_image_data_np_for_save"], np.ndarray):
            logger.error(f"PG: Template data for '{template_data.get('name')}' missing or invalid '_image_data_np_for_save'.")
            return False

        final_data = {**copy.deepcopy(DEFAULT_TEMPLATE_STRUCTURE_PG), **template_data}
        self.generated_profile_data.setdefault("templates", []).append(final_data)
        logger.info(f"PG: Template '{final_data['name']}' (filename: {final_data['filename']}) metadata and image data staged in draft.")
        return True

    def add_rule_definition(self, rule_data: Dict[str, Any]) -> bool:
        if not (isinstance(rule_data, dict) and rule_data.get("name") and isinstance(rule_data.get("condition"), dict) and isinstance(rule_data.get("action"), dict)):
            logger.error(f"PG: Invalid rule data provided to add_rule_definition: {rule_data}")
            return False

        # Ensure rule name is unique within the draft, or replace if user confirmed overwrite
        existing_rules = self.generated_profile_data.setdefault("rules", [])
        name_to_add = rule_data["name"]
        self.generated_profile_data["rules"] = [r for r in existing_rules if r.get("name") != name_to_add]  # Remove old if exists

        final_data_to_add = copy.deepcopy(DEFAULT_RULE_STRUCTURE_PG)
        final_data_to_add.update(rule_data)
        # Ensure condition and action blocks exist and have defaults if partially specified
        final_data_to_add["condition"] = {**copy.deepcopy(DEFAULT_CONDITION_STRUCTURE_PG), **(rule_data.get("condition", {}))}
        final_data_to_add["action"] = {**copy.deepcopy(DEFAULT_ACTION_STRUCTURE_PG), **(rule_data.get("action", {}))}

        self.generated_profile_data["rules"].append(final_data_to_add)
        logger.info(f"PG: Rule '{final_data_to_add['name']}' definition added/updated in draft profile.")
        return True

    def get_generated_profile_data(self) -> Dict[str, Any]:
        profile_copy = copy.deepcopy(self.generated_profile_data)
        if "templates" in profile_copy and isinstance(profile_copy["templates"], list):
            for tpl in profile_copy["templates"]:
                if isinstance(tpl, dict):
                    tpl.pop("_image_data_np_for_save", None)
        return profile_copy

    def save_generated_profile(self, filepath_to_save: str) -> bool:
        if not self.generated_profile_data:
            logger.error("PG: No profile data has been generated to save.")
            return False
        if not filepath_to_save:
            logger.error("PG: No filepath provided to save the generated profile.")
            return False

        profile_data_for_json = copy.deepcopy(self.generated_profile_data)
        staged_templates_with_image_data: List[Dict[str, Any]] = []

        if "templates" in profile_data_for_json and isinstance(profile_data_for_json["templates"], list):
            clean_templates_for_json = []
            for tpl_meta in profile_data_for_json["templates"]:
                if isinstance(tpl_meta, dict):
                    if "_image_data_np_for_save" in tpl_meta and isinstance(tpl_meta["_image_data_np_for_save"], np.ndarray):
                        staged_templates_with_image_data.append(copy.deepcopy(tpl_meta))
                    clean_tpl_entry = {k: v for k, v in tpl_meta.items() if k != "_image_data_np_for_save"}
                    clean_templates_for_json.append(clean_tpl_entry)
            profile_data_for_json["templates"] = clean_templates_for_json

        self.config_manager_for_generated_profile.update_profile_data(profile_data_for_json)
        json_save_success = self.config_manager_for_generated_profile.save_current_profile(filepath_to_save)

        if not json_save_success:
            logger.error(f"PG: Failed to save the main profile JSON to '{filepath_to_save}'. Template images will not be saved.")
            return False
        logger.info(f"PG: Main profile JSON saved successfully to '{filepath_to_save}'.")

        profile_base_dir = self.config_manager_for_generated_profile.get_profile_base_path()
        if not profile_base_dir:
            logger.error("PG: Profile base directory not determined after saving JSON. Cannot save template images.")
            return False

        templates_target_dir = os.path.join(profile_base_dir, TEMPLATES_SUBDIR_NAME)
        try:
            os.makedirs(templates_target_dir, exist_ok=True)
            logger.debug(f"PG: Ensured templates directory exists at: {templates_target_dir}")
        except OSError as e:
            logger.error(f"PG: Could not create templates directory '{templates_target_dir}': {e}. Template images will not be saved.", exc_info=True)
            return False

        all_templates_saved = True
        for tpl_data_with_image in staged_templates_with_image_data:
            template_filename = tpl_data_with_image.get("filename")
            image_np_to_save = tpl_data_with_image.get("_image_data_np_for_save")
            template_name_for_log = tpl_data_with_image.get("name", "UnnamedTemplate")

            if not template_filename or image_np_to_save is None:
                logger.warning(f"PG: Skipping template '{template_name_for_log}' due to missing filename or image data.")
                all_templates_saved = False
                continue

            template_image_full_path = os.path.join(templates_target_dir, template_filename)
            try:
                save_status = cv2.imwrite(template_image_full_path, image_np_to_save)
                if save_status:
                    logger.info(f"PG: Template image '{template_filename}' (for '{template_name_for_log}') saved to: {template_image_full_path}")
                else:
                    logger.error(f"PG: Failed to save template image '{template_filename}' using cv2.imwrite (returned false). Path: {template_image_full_path}")
                    all_templates_saved = False
            except Exception as e_img_save:
                logger.error(f"PG: Error saving template image '{template_filename}' to '{template_image_full_path}': {e_img_save}", exc_info=True)
                all_templates_saved = False

        if not all_templates_saved:
            logger.warning("PG: One or more template images failed to save. The profile JSON was saved, but templates may be missing.")
            # Return True because JSON saved, but with a warning. Criticality of templates might vary.
        else:
            logger.info("PG: All staged template images saved successfully.")
        return True
