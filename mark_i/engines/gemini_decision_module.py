import logging
import json  # For parsing JSON responses from Gemini (NLU plan, step suggestions)
import time  # For potential delays between NLU task steps
from typing import Dict, Any, Optional, List, Tuple

import numpy as np

from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.engines.action_executor import ActionExecutor
from mark_i.core.config_manager import ConfigManager  # For resolving region data if needed

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_decision_module")

# Predefined set of "primitive" sub-actions that the NLU-decomposed plan can map to.
# Gemini will be prompted to suggest actions whose `action_type` (from its JSON response
# for a sub-step) maps to one of these keys.
PREDEFINED_ALLOWED_SUB_ACTIONS = {
    "CLICK_DESCRIBED_ELEMENT": {
        "description": "Clicks an element described textually (e.g., 'the blue button labeled Submit').",
        "expected_params_from_gemini": ["target_description"],  # What Gemini needs to provide for this sub-action
        "maps_to_action_executor_type": "click",  # The type ActionExecutor understands
        "refinement_needed": True,  # Indicates this action needs bounding box refinement
    },
    "TYPE_IN_DESCRIBED_FIELD": {
        "description": "Types text into an element described textually (e.g., 'the username input field').",
        "expected_params_from_gemini": ["text_to_type", "target_description"],
        "maps_to_action_executor_type": None,  # This is a sequence: click field, then type text
        "refinement_needed": True,  # For the field target (before clicking)
    },
    "PRESS_KEY_SIMPLE": {
        "description": "Presses a single standard keyboard key (e.g., 'enter', 'tab', 'esc').",
        "expected_params_from_gemini": ["key_name"],
        "maps_to_action_executor_type": "press_key",
        "refinement_needed": False,
    },
    "CHECK_VISUAL_STATE": {
        "description": "Checks if a visual condition described textually is met (e.g., 'if an error message is visible', 'is the Save button enabled?'). Responds true/false for conditional branching.",
        "expected_params_from_gemini": ["condition_description"],  # The condition to check
        "maps_to_action_executor_type": None,  # This is an internal check, not a direct PyAutoGUI action
        "refinement_needed": False,  # The description itself is the target for evaluation
    },
    # Example for a future simple non-interactive action:
    # "WAIT_SHORT": {
    #     "description": "Waits for a short duration (e.g., 1.5 seconds).",
    #     "expected_params_from_gemini": ["duration_seconds"],
    #     "maps_to_action_executor_type": "wait", # Assumes ActionExecutor has a 'wait' type
    #     "refinement_needed": False
    # },
}


class GeminiDecisionModule:
    """
    Parses Natural Language User Commands (Phase 3), decomposes them into tasks/steps,
    and orchestrates their execution. For each step, it uses Gemini (via GeminiAnalyzer)
    for visual analysis to determine appropriate primitive actions and refine targets,
    then calls ActionExecutor.
    Also handles simpler goal-driven single action selection (Phase 2).
    """

    def __init__(
        self,
        gemini_analyzer: GeminiAnalyzer,
        action_executor: ActionExecutor,
        config_manager: ConfigManager,
    ):
        self.gemini_analyzer = gemini_analyzer
        self.action_executor = action_executor
        self.config_manager = config_manager
        logger.info("GeminiDecisionModule (NLU Task Orchestrator & Goal Executor) initialized.")

    def _construct_nlu_parse_prompt(self, natural_language_command: str) -> str:
        """
        Constructs the prompt for Gemini to parse the NLU command into a structured plan.
        """
        nlu_schema_description = """
You are an NLU (Natural Language Understanding) parser for a desktop automation tool.
Your task is to analyze the user's natural language command and convert it into a structured JSON plan.
The user's command might describe a single action, a sequence of actions, or a conditional statement.

Respond with a single JSON object with a top-level key "parsed_task".
The "parsed_task" object MUST have:
1.  "command_type": A string, one of "SINGLE_INSTRUCTION", "SEQUENTIAL_INSTRUCTIONS", "CONDITIONAL_INSTRUCTION".
2.  If "command_type" is "SINGLE_INSTRUCTION":
    It MUST contain an "instruction_details" object with:
    - "intent_verb": A string representing the primary action verb (e.g., "CLICK", "TYPE", "PRESS_KEY", "FIND_ELEMENT", "CHECK_CONDITION").
    - "target_description": A string describing the UI element to interact with (e.g., "the login button", "the username field that is currently empty"). Can be null if not applicable (e.g., for PRESS_KEY 'enter').
    - "parameters": An object containing other necessary parameters, specific to the intent_verb. Examples:
        - For "TYPE": {"text_to_type": "user@example.com"}
        - For "PRESS_KEY": {"key_name": "tab"}
3.  If "command_type" is "SEQUENTIAL_INSTRUCTIONS":
    It MUST contain a "steps" array. Each element in the array is an object with:
    - "step_number": An integer (1-indexed).
    - "instruction_details": An object matching the "instruction_details" schema described above for "SINGLE_INSTRUCTION".
4.  If "command_type" is "CONDITIONAL_INSTRUCTION":
    It MUST contain:
    - "condition_description": A string describing the visual condition to check (e.g., "an error message is visible on screen", "the 'Save' button is enabled").
    - "then_branch": An object representing the task to perform if the condition is true. This object itself MUST conform to the "parsed_task" schema (i.e., it will have its own "command_type" and either "instruction_details" or "steps").
    - "else_branch": Optional. An object representing the task if the condition is false, also conforming to the "parsed_task" schema. Can be null or omitted if no 'else' action.

Focus on identifying the core actions, their targets, and any parameters.
Be precise. If a target isn't explicitly mentioned for an action that needs one (like TYPE), infer it from context if possible or make it null.

Example User Command: "If the light is green, click the 'Go' button and then type 'Proceeding'. Otherwise, just press Escape."
Expected "parsed_task" for example:
{
  "command_type": "CONDITIONAL_INSTRUCTION",
  "condition_description": "the light is green",
  "then_branch": {
    "command_type": "SEQUENTIAL_INSTRUCTIONS",
    "steps": [
      { "step_number": 1, "instruction_details": { "intent_verb": "CLICK", "target_description": "the 'Go' button", "parameters": {} } },
      { "step_number": 2, "instruction_details": { "intent_verb": "TYPE", "target_description": null, "parameters": { "text_to_type": "Proceeding" } } }
    ]
  },
  "else_branch": {
    "command_type": "SINGLE_INSTRUCTION",
    "instruction_details": { "intent_verb": "PRESS_KEY", "target_description": null, "parameters": { "key_name": "escape" } }
  }
}
"""
        prompt = f"""{nlu_schema_description}

User Command to Parse: "{natural_language_command}"

Provide your parsed JSON output now:
"""
        return prompt

    def _map_nlu_intent_to_allowed_sub_action(self, nlu_intent_verb: Optional[str]) -> Optional[str]:
        """Maps a parsed NLU intent verb to one of the PREDEFINED_ALLOWED_SUB_ACTIONS keys."""
        if not nlu_intent_verb or not isinstance(nlu_intent_verb, str):
            return None

        verb_upper = nlu_intent_verb.strip().upper()
        # More specific mappings
        if verb_upper in ["CLICK", "PRESS_BUTTON", "SELECT_OPTION"]:
            return "CLICK_DESCRIBED_ELEMENT"
        elif verb_upper in ["TYPE", "INPUT_TEXT", "ENTER_TEXT", "FILL_FIELD"]:
            return "TYPE_IN_DESCRIBED_FIELD"
        elif verb_upper in ["PRESS_KEY", "HIT_KEY"]:  # "PRESS" alone might be ambiguous
            return "PRESS_KEY_SIMPLE"
        elif verb_upper in ["CHECK", "VERIFY", "IS_VISIBLE", "IS_PRESENT", "IF_STATE_IS"]:
            return "CHECK_VISUAL_STATE"
        # Add more mappings as PREDEFINED_ALLOWED_SUB_ACTIONS expands
        # Example: "WAIT" -> "WAIT_SHORT"

        logger.warning(f"NLU Intent verb '{nlu_intent_verb}' (normalized to '{verb_upper}') could not be reliably mapped to a predefined sub-action.")
        return None  # Return None if no confident mapping

    def _construct_sub_step_action_suggestion_prompt(
        self,
        sub_step_goal_description: str,  # e.g., "Click the login button" or "Type 'hello' into the search bar"
        allowed_sub_actions_map: Dict[str, Any],  # The PREDEFINED_ALLOWED_SUB_ACTIONS (possibly filtered)
    ) -> str:
        """Constructs prompt for Gemini to suggest a *specific* primitive sub-action for a sub-step goal."""
        actions_description_parts = []
        for action_name, action_meta in allowed_sub_actions_map.items():
            # Parameters Gemini needs to fill for this action
            params_gemini_needs_to_provide = action_meta.get("expected_params_from_gemini", [])
            params_str = ", ".join(params_gemini_needs_to_provide)
            actions_description_parts.append(f"- Action Type: \"{action_name}\"\n  Description: {action_meta['description']}\n  Required Parameters from you: [{params_str}]")
        actions_description = "\n".join(actions_description_parts)

        prompt = f"""You are an AI assistant helping to execute a single step of an automated desktop task.
The current sub-goal for this step is: "{sub_step_goal_description}"

Based on the provided image of the current screen state, choose the *single most appropriate primitive action* from the following list to achieve this sub-goal.
Allowed Primitive Actions:
{actions_description}

You MUST respond with a single JSON object in the format:
{{
  "action_type": "CHOSEN_PRIMITIVE_ACTION_TYPE_FROM_LIST",
  "parameters": {{
    // Include ALL and ONLY the 'Required Parameters from you' for the chosen action_type.
    // Example for CLICK_DESCRIBED_ELEMENT: "target_description": "the blue button with text 'Login'"
    // Example for TYPE_IN_DESCRIBED_FIELD: "text_to_type": "user@example.com", "target_description": "the email input field"
  }},
  "reasoning": "Your brief reasoning for choosing this action and parameters for this specific sub-goal."
}}
Ensure 'action_type' is one of the allowed primitive action types listed above.
If the sub-goal cannot be directly achieved by one of these primitive actions, or if critical information is missing from the image, explain in reasoning and choose the best possible fit or indicate failure clearly in the JSON.
"""
        return prompt

    def _refine_target_description_to_bbox(
        self, target_description: str, context_image: np.ndarray, context_image_region_name: str, task_rule_name_for_log: str  # For better logging context
    ) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini (via GeminiAnalyzer's vision query) to get bounding box
        for a textually described target within a specific image.
        Returns a dict suitable for ActionExecutor's gemini_element_variable context.
        """
        log_prefix = f"R '{task_rule_name_for_log}', NLU Task TargetRefine"
        logger.info(f"{log_prefix}: Refining target description: '{target_description}' in region '{context_image_region_name}'")

        refinement_prompt = (
            f'You are a precise visual element locator. In the provided image, identify the UI element best described as: "{target_description}".\n'
            f"Respond ONLY with a single JSON object. The JSON object MUST have two keys: 'found' (boolean: true if the element is confidently identified, false otherwise) and 'box' (an array of four integers [x, y, width, height] relative to the top-left of THIS image if found, otherwise null).\n"
            f'Example if found: {{"found": true, "box": [10, 20, 100, 30]}}\n'
            f'Example if not found: {{"found": false, "box": null}}'
        )

        response = self.gemini_analyzer.query_vision_model(context_image, refinement_prompt)

        if response["status"] == "success" and response["json_content"]:
            json_data = response["json_content"]
            if isinstance(json_data, dict) and "found" in json_data and isinstance(json_data["found"], bool) and "box" in json_data:
                if json_data["found"]:
                    if isinstance(json_data["box"], list) and len(json_data["box"]) == 4 and all(isinstance(n, (int, float)) for n in json_data["box"]):
                        # Ensure integer coordinates for box
                        int_box = [int(round(n)) for n in json_data["box"]]
                        if int_box[2] > 0 and int_box[3] > 0:  # Width and height must be positive
                            logger.info(f"{log_prefix}: Target '{target_description}' refined to bbox: {int_box} in region '{context_image_region_name}'")
                            return {
                                "value": {"box": int_box, "found": True, "element_label": target_description},  # Mimic structure for ActionExecutor
                                "_source_region_for_capture_": context_image_region_name,
                            }
                        else:
                            logger.warning(f"{log_prefix}: Refined bounding box for '{target_description}' has non-positive width/height: {int_box}.")
                    else:  # Box data malformed
                        logger.warning(f"{log_prefix}: Target '{target_description}' found, but 'box' data is malformed: {json_data['box']}.")
                else:  # "found" is false
                    logger.info(f"{log_prefix}: Target '{target_description}' refinement: Gemini reported 'found: false' in region '{context_image_region_name}'.")
                # If found is false, or box is malformed/non-positive, return None (target not usable)
                return None
            logger.warning(f"{log_prefix}: Target '{target_description}' refinement: Gemini response JSON has unexpected structure: {json_data}")
        else:
            logger.error(f"{log_prefix}: Target '{target_description}' refinement: Gemini query failed. Status: {response['status']}, Error: {response.get('error_message')}")
        return None  # Default to None if any failure

    def _execute_primitive_sub_action(
        self,
        primitive_action_type: str,  # Key from PREDEFINED_ALLOWED_SUB_ACTIONS
        gemini_provided_params: Dict[str, Any],
        visual_context_image: np.ndarray,  # Image used for this step's visual analysis / refinement
        visual_context_region_name: str,  # Name of the region for the image
        task_rule_name_for_log: str,  # Original rule name for context
        task_parameters_from_rule: Dict[str, Any],  # Original task parameters for confirmation, pauses
    ) -> bool:
        """
        Executes a single primitive sub-action after it has been suggested by Gemini
        and its target (if any) has been refined.
        """
        log_prefix = f"R '{task_rule_name_for_log}', NLU SubAction Exec='{primitive_action_type}'"
        action_meta = PREDEFINED_ALLOWED_SUB_ACTIONS[primitive_action_type]  # Assumes type is already validated

        final_action_spec_for_executor: Dict[str, Any] = {
            "type": "",  # To be filled based on action_meta
            "context": {
                "rule_name": f"{task_rule_name_for_log}_NLU_SubStep_{primitive_action_type}",
                "variables": {},
                "condition_region": visual_context_region_name,  # Region providing visual context for this step
            },
            "pyautogui_pause_before": task_parameters_from_rule.get("pyautogui_pause_before", 0.1),  # Default from outer task
        }

        refined_target_info_for_ae: Optional[Dict[str, Any]] = None  # For actions needing coordinates

        if action_meta.get("refinement_needed", False):
            target_desc = gemini_provided_params.get("target_description")
            if not target_desc or not isinstance(target_desc, str):
                logger.error(f"{log_prefix}: Action requires 'target_description' from Gemini, but it's missing or invalid. Params: {gemini_provided_params}")
                return False

            refined_target_info_for_ae = self._refine_target_description_to_bbox(target_desc, visual_context_image, visual_context_region_name, task_rule_name_for_log)
            if not refined_target_info_for_ae:  # _refine_target_description_to_bbox logs failure details
                logger.error(f"{log_prefix}: Failed to refine target '{target_desc}' to usable coordinates.")
                return False

        # Construct ActionExecutor spec based on primitive_action_type
        if primitive_action_type == "CLICK_DESCRIBED_ELEMENT":
            if not refined_target_info_for_ae:
                return False  # Should have been caught
            var_name = "_nlu_click_target_var"  # Internal var name for ActionExecutor context
            final_action_spec_for_executor["context"]["variables"][var_name] = refined_target_info_for_ae

            final_action_spec_for_executor["type"] = action_meta["maps_to_action_executor_type"]  # "click"
            final_action_spec_for_executor["target_relation"] = "center_of_gemini_element"  # Default for AI identified
            final_action_spec_for_executor["gemini_element_variable"] = var_name
            final_action_spec_for_executor["button"] = gemini_provided_params.get("button", "left")
            final_action_spec_for_executor["clicks"] = int(gemini_provided_params.get("clicks", 1))
            final_action_spec_for_executor["interval"] = float(gemini_provided_params.get("interval", 0.0))

        elif primitive_action_type == "TYPE_IN_DESCRIBED_FIELD":
            if not refined_target_info_for_ae:
                return False
            text_to_type = gemini_provided_params.get("text_to_type")
            if not isinstance(text_to_type, str):  # text_to_type can be empty string
                logger.error(f"{log_prefix}: 'text_to_type' missing or invalid for TYPE_IN_DESCRIBED_FIELD. Params: {gemini_provided_params}")
                return False

            # Sequence: 1. Click the field
            click_var_name = "_nlu_type_field_click_target"
            click_context_vars = {click_var_name: refined_target_info_for_ae}
            click_spec = {
                "type": "click",
                "target_relation": "center_of_gemini_element",
                "gemini_element_variable": click_var_name,
                "button": "left",
                "pyautogui_pause_before": 0.15,  # Slightly longer pause before typing
                "context": {**final_action_spec_for_executor["context"], "variables": click_context_vars},
            }
            logger.info(f"{log_prefix}: Executing pre-type click on '{gemini_provided_params.get('target_description')}'")
            try:
                self.action_executor.execute_action(click_spec)
                time.sleep(0.1)  # Small pause after click before typing
            except Exception as e_click:
                logger.error(f"{log_prefix}: Failed to click field '{gemini_provided_params.get('target_description')}': {e_click}", exc_info=True)
                return False

            # 2. Type the text
            final_action_spec_for_executor["type"] = "type_text"  # ActionExecutor type
            final_action_spec_for_executor["text"] = text_to_type
            final_action_spec_for_executor["interval"] = float(gemini_provided_params.get("typing_interval", 0.02))
            # The main pyautogui_pause_before for the "type" part of the sequence

        elif primitive_action_type == "PRESS_KEY_SIMPLE":
            key_name = gemini_provided_params.get("key_name")
            if not key_name or not isinstance(key_name, str):
                logger.error(f"{log_prefix}: 'key_name' missing or invalid for PRESS_KEY_SIMPLE. Params: {gemini_provided_params}")
                return False
            final_action_spec_for_executor["type"] = action_meta["maps_to_action_executor_type"]  # "press_key"
            final_action_spec_for_executor["key"] = key_name  # ActionExecutor handles CSV for hotkeys if needed

        elif primitive_action_type == "CHECK_VISUAL_STATE":
            condition_desc_from_gemini = gemini_provided_params.get("condition_description")
            if not condition_desc_from_gemini:
                logger.error(f"{log_prefix}: 'condition_description' missing for CHECK_VISUAL_STATE. Params: {gemini_provided_params}")
                return False  # Or treat as True/False based on policy? For now, fail.

            check_prompt = f"Based on the provided image, is the following condition true or false? Condition: \"{condition_desc_from_gemini}\". Respond with only the word 'true' or 'false'."
            logger.info(f"{log_prefix}: Checking visual state: '{condition_desc_from_gemini}' in region '{visual_context_region_name}'")

            gemini_eval_response = self.gemini_analyzer.query_vision_model(visual_context_image, check_prompt)

            if gemini_eval_response["status"] == "success" and gemini_eval_response["text_content"]:
                response_text = gemini_eval_response["text_content"].strip().lower()
                if response_text == "true":
                    logger.info(f"{log_prefix}: Visual state '{condition_desc_from_gemini}' evaluated to TRUE by Gemini.")
                    return True  # This "action" succeeded, and the condition it checked is true.
                elif response_text == "false":
                    logger.info(f"{log_prefix}: Visual state '{condition_desc_from_gemini}' evaluated to FALSE by Gemini.")
                    return False  # This "action" succeeded, but the condition it checked is false.
                else:
                    logger.warning(f"{log_prefix}: CHECK_VISUAL_STATE received ambiguous text response from Gemini: '{response_text}'. Interpreting as condition FALSE.")
                    return False
            else:
                logger.error(f"{log_prefix}: CHECK_VISUAL_STATE failed. Gemini query status: {gemini_eval_response['status']}, Error: {gemini_eval_response.get('error_message')}")
                return False  # The check itself failed.
        else:
            logger.error(f"{log_prefix}: Logic to construct ActionExecutor spec for primitive action type '{primitive_action_type}' is not implemented.")
            return False

        # User Confirmation for actual UI-interacting actions
        # CHECK_VISUAL_STATE does not need this as it doesn't interact.
        if task_parameters_from_rule.get("require_confirmation_per_step", True) and final_action_spec_for_executor.get("type"):  # Only if it's an executable type

            # This requires a synchronous way to get user input if GUI is running.
            # For CLI or non-interactive, this might log and proceed, or have a config to auto-confirm/deny.
            # Placeholder:
            confirmed_by_user = True  # Assume yes for non-GUI testing for now
            action_desc_for_confirm = f"{final_action_spec_for_executor.get('type')} on target '{gemini_provided_params.get('target_description', 'N/A')}'"
            if primitive_action_type == "TYPE_IN_DESCRIBED_FIELD":
                action_desc_for_confirm = f"TYPE '{gemini_provided_params.get('text_to_type')}' in '{gemini_provided_params.get('target_description')}'"
            elif primitive_action_type == "PRESS_KEY_SIMPLE":
                action_desc_for_confirm = f"PRESS_KEY '{gemini_provided_params.get('key_name')}'"

            logger.info(f"{log_prefix}: USER CONFIRMATION REQUIRED for: {action_desc_for_confirm}")
            # print(f"AI PROPOSES TO: {action_desc_for_confirm}. Confirm (y/n)?") # Example CLI interaction
            # if input().strip().lower() != 'y':
            #     logger.info(f"{log_prefix}: User denied confirmation for action.")
            #     confirmed_by_user = False
            if not confirmed_by_user:
                return False  # User cancelled this step

        # Execute the action (if it's not a check that already returned)
        if final_action_spec_for_executor.get("type"):
            try:
                loggable_spec = {k: v for k, v in final_action_spec_for_executor.items() if k != "context"}  # For cleaner log
                logger.info(f"{log_prefix}: Executing final primitive action spec: {loggable_spec} with context keys: {list(final_action_spec_for_executor['context'].keys())}")
                self.action_executor.execute_action(final_action_spec_for_executor)
                logger.info(f"{log_prefix}: Primitive action '{final_action_spec_for_executor['type']}' on target '{gemini_provided_params.get('target_description', 'N/A')}' executed successfully.")
                return True
            except Exception as e_exec:
                logger.error(
                    f"{log_prefix}: Error executing primitive action '{final_action_spec_for_executor['type']}' on target '{gemini_provided_params.get('target_description', 'N/A')}': {e_exec}",
                    exc_info=True,
                )
                return False

        # Should only be reached if primitive_action_type was something like CHECK_VISUAL_STATE that returned early
        return False  # Should be unreachable if type was valid executable and no error before.

    def execute_nlu_task(self, task_rule_name: str, natural_language_command: str, initial_context_images: Dict[str, np.ndarray], task_parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrates execution of a task described by a natural language command.
        1. Parses NLU command into structured plan using Gemini.
        2. Executes steps in the plan, using Gemini for sub-step action selection and visual refinement.
        """
        overall_task_result = {"status": "failure", "message": "NLU task initiated."}
        log_prefix = f"R '{task_rule_name}', NLU Task Command='{natural_language_command[:60]}...'"
        logger.info(f"{log_prefix}: Starting execution of Natural Language Command.")

        if not self.gemini_analyzer or not self.gemini_analyzer.client_initialized:
            overall_task_result["message"] = "GeminiAnalyzer not available for NLU task."
            logger.error(f"{log_prefix}: {overall_task_result['message']}")
            return overall_task_result

        # 1. NLU Parsing and Task Decomposition
        nlu_parse_prompt = self._construct_nlu_parse_prompt(natural_language_command)
        logger.debug(f"{log_prefix}: Constructed NLU parse prompt. Length: {len(nlu_parse_prompt)}")

        # NLU parsing is primarily text-based. We can use a text model if available,
        # or a multimodal model with a minimal/no image.
        # For now, using query_vision_model with a dummy image if no initial context,
        # assuming the chosen default model can handle text-only or mostly-text prompts.
        nlu_context_image_for_parse = next(iter(initial_context_images.values()), None) if initial_context_images else None
        if nlu_context_image_for_parse is None:
            nlu_context_image_for_parse = np.zeros((10, 10, 3), dtype=np.uint8)  # Minimal dummy image
            logger.debug(f"{log_prefix}: No initial context image for NLU parse, using dummy image.")

        nlu_model_to_use = "gemini-1.5-pro-latest"  # Or another powerful model suitable for NLU/JSON
        nlu_response = self.gemini_analyzer.query_vision_model(nlu_context_image_for_parse, nlu_parse_prompt, model_name_override=nlu_model_to_use)

        if nlu_response["status"] != "success" or not nlu_response["json_content"]:
            overall_task_result["message"] = f"NLU parsing failed. Gemini Status: {nlu_response['status']}, Error: {nlu_response.get('error_message', 'No JSON content')}"
            logger.error(f"{log_prefix}: {overall_task_result['message']}. Raw NLU Response Text (if any): {nlu_response.get('text_content')}")
            return overall_task_result

        parsed_task_plan_outer: Optional[Dict[str, Any]] = None
        try:
            if not isinstance(nlu_response["json_content"], dict) or "parsed_task" not in nlu_response["json_content"]:
                raise ValueError("NLU JSON response missing 'parsed_task' top-level key.")
            parsed_task_plan_outer = nlu_response["json_content"]["parsed_task"]
            if not isinstance(parsed_task_plan_outer, dict):
                raise ValueError("'parsed_task' value is not a dictionary.")
            logger.info(f"{log_prefix}: Successfully parsed NLU command. Plan Type: {parsed_task_plan_outer.get('command_type')}")
            logger.debug(f"{log_prefix}: Full parsed plan: {json.dumps(parsed_task_plan_outer, indent=2)}")
        except Exception as e_parse:
            overall_task_result["message"] = f"Error processing NLU JSON response structure: {e_parse}. Response: {nlu_response['json_content']}"
            logger.error(f"{log_prefix}: {overall_task_result['message']}", exc_info=True)
            return overall_task_result

        # --- Recursive executor for the parsed plan (handles nested tasks for conditionals) ---
        def execute_parsed_plan_recursive(
            plan_node: Dict[str, Any], current_visual_context_images: Dict[str, np.ndarray], current_primary_context_region_name: str, recursion_depth=0  # A "parsed_task" object
        ) -> Tuple[bool, str]:  # (success_status, message)

            if recursion_depth > 5:  # Safeguard against deep recursion
                logger.error(f"{log_prefix}: Max recursion depth reached in NLU task execution. Aborting branch.")
                return False, "Max recursion depth reached."

            node_command_type = plan_node.get("command_type")
            node_log_prefix = f"{log_prefix}_depth{recursion_depth}_type{node_command_type}"

            if node_command_type == "SINGLE_INSTRUCTION":
                instruction = plan_node.get("instruction_details")
                if instruction and isinstance(instruction, dict):
                    step_success = self._execute_primitive_sub_action(
                        instruction_details=instruction,  # This is the new name for the method
                        context_images=current_visual_context_images,
                        primary_context_region_name=current_primary_context_region_name,
                        task_rule_name_for_log=task_rule_name,  # Original rule for top-level log
                        task_parameters_from_rule=task_parameters,
                    )
                    return step_success, f"Single instruction execution {'succeeded' if step_success else 'failed'}."
                else:
                    logger.error(f"{node_log_prefix}: SINGLE_INSTRUCTION missing valid 'instruction_details'.")
                    return False, "SINGLE_INSTRUCTION format error."

            elif node_command_type == "SEQUENTIAL_INSTRUCTIONS":
                steps = plan_node.get("steps", [])
                if not isinstance(steps, list) or not steps:
                    logger.error(f"{node_log_prefix}: SEQUENTIAL_INSTRUCTIONS missing valid 'steps' list.")
                    return False, "SEQUENTIAL_INSTRUCTIONS format error."

                max_steps_config = task_parameters.get("max_steps", len(steps))
                for i, step_data in enumerate(steps):
                    if i >= max_steps_config:
                        logger.info(f"{node_log_prefix}: Reached max_steps ({max_steps_config}). Stopping sequence.")
                        break
                    if not isinstance(step_data, dict) or "instruction_details" not in step_data:
                        logger.error(f"{node_log_prefix}: Invalid step data at index {i}: {step_data}. Aborting sequence.")
                        return False, f"Invalid step {i+1} in sequence."

                    instruction = step_data["instruction_details"]
                    step_num_from_plan = step_data.get("step_number", i + 1)
                    logger.info(f"{node_log_prefix}: Executing Step {step_num_from_plan}/{len(steps)}: Intent='{instruction.get('intent_verb')}' Target='{instruction.get('target_description')}'")

                    # TODO: Consider refreshing visual context before each step for more accuracy
                    # current_visual_context_images = refresh_context_images_function()

                    step_success = self._execute_primitive_sub_action(
                        instruction, current_visual_context_images, current_primary_context_region_name, f"{task_rule_name}_SeqStep{step_num_from_plan}", task_parameters
                    )
                    if not step_success:
                        return False, f"Sequential task failed at step {step_num_from_plan} (Intent: {instruction.get('intent_verb')})."
                    time.sleep(task_parameters.get("delay_between_nlu_steps", 0.3))  # Small delay
                return True, "Sequential instructions executed successfully."

            elif node_command_type == "CONDITIONAL_INSTRUCTION":
                condition_desc = plan_node.get("condition_description")
                then_branch_plan = plan_node.get("then_branch")
                else_branch_plan = plan_node.get("else_branch")

                if not condition_desc or not isinstance(then_branch_plan, dict):
                    logger.error(f"{node_log_prefix}: CONDITIONAL_INSTRUCTION missing 'condition_description' or valid 'then_branch'.")
                    return False, "CONDITIONAL_INSTRUCTION format error."

                condition_eval_instruction = {
                    "intent_verb": "CHECK_VISUAL_STATE",
                    "target_description": condition_desc,  # The condition is the target for CHECK
                    "parameters": {"condition_description": condition_desc},
                }
                logger.info(f"{node_log_prefix}: Evaluating IF condition: '{condition_desc}'")
                condition_is_true = self._execute_primitive_sub_action(
                    condition_eval_instruction, current_visual_context_images, current_primary_context_region_name, f"{task_rule_name}_IF_CondCheck", task_parameters
                )

                branch_to_execute_plan = None
                branch_name = ""
                if condition_is_true:
                    logger.info(f"{node_log_prefix}: IF condition '{condition_desc}' is TRUE. Proceeding with THEN branch.")
                    branch_to_execute_plan = then_branch_plan
                    branch_name = "THEN"
                elif isinstance(else_branch_plan, dict):  # Check if else_branch is a valid plan node
                    logger.info(f"{node_log_prefix}: IF condition '{condition_desc}' is FALSE. Proceeding with ELSE branch.")
                    branch_to_execute_plan = else_branch_plan
                    branch_name = "ELSE"
                else:
                    logger.info(f"{node_log_prefix}: IF condition '{condition_desc}' is FALSE. No ELSE branch provided. Conditional execution complete.")
                    return True, "Conditional: Condition false, no else branch."

                if branch_to_execute_plan:
                    logger.info(f"{node_log_prefix}: Executing {branch_name} branch...")
                    return execute_parsed_plan_recursive(branch_to_execute_plan, current_visual_context_images, current_primary_context_region_name, recursion_depth + 1)
                # Should not be reached if logic is correct for handling no else branch
                return False, "Conditional branch logic error."

            else:
                logger.error(f"{node_log_prefix}: Unknown 'command_type' in parsed plan: {node_command_type}.")
                return False, f"Unknown command type '{node_command_type}' in plan."

        # --- End of recursive executor ---

        # Determine primary context region for executing steps
        primary_context_region_name_for_steps = ""
        if task_parameters.get("context_region_names") and isinstance(task_parameters["context_region_names"], list) and task_parameters["context_region_names"]:
            primary_context_region_name_for_steps = task_parameters["context_region_names"][0]
        elif initial_context_images:  # Fallback to first available image's region name
            primary_context_region_name_for_steps = list(initial_context_images.keys())[0]

        if not primary_context_region_name_for_steps or primary_context_region_name_for_steps not in initial_context_images:
            overall_task_result["message"] = "Could not determine a valid primary context region with an image for executing NLU task steps."
            logger.error(f"{log_prefix}: {overall_task_result['message']}")
            return overall_task_result

        # Execute the parsed plan
        success, message = execute_parsed_plan_recursive(parsed_task_plan_outer, initial_context_images, primary_context_region_name_for_steps)

        overall_task_result["status"] = "success" if success else "failure"
        overall_task_result["message"] = message

        logger.info(f"{log_prefix}: Final NLU task status: {overall_task_result['status']}. Message: {overall_task_result['message']}")
        return overall_task_result
