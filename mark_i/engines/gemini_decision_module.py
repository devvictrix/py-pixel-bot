import logging
import json
import time  # For optional delays between NLU task steps
from typing import Dict, Any, Optional, List, Tuple

import numpy as np

from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.engines.action_executor import ActionExecutor
from mark_i.core.config_manager import ConfigManager  # For resolving region data for refinement context

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_decision_module")

# --- Constants for GeminiDecisionModule ---

# Predefined set of "primitive" sub-actions that an NLU-decomposed plan can map to.
# Gemini will be prompted to suggest actions whose `action_type` (from its JSON response
# for a sub-step) maps to one of these keys.
# `expected_params_from_gemini`: Parameters Gemini needs to provide for this sub-action.
# `maps_to_action_executor_type`: The corresponding type understood by ActionExecutor.
# `refinement_needed`: True if this action typically needs visual target refinement (bounding box).
PREDEFINED_ALLOWED_SUB_ACTIONS: Dict[str, Dict[str, Any]] = {
    "CLICK_DESCRIBED_ELEMENT": {
        "description": "Clicks an element described textually (e.g., 'the blue button labeled Submit').",
        "expected_params_from_gemini": ["target_description"],
        "maps_to_action_executor_type": "click",
        "refinement_needed": True,
    },
    "TYPE_IN_DESCRIBED_FIELD": {
        "description": "Types text into an element described textually (e.g., 'the username input field').",
        "expected_params_from_gemini": ["text_to_type", "target_description"],
        "maps_to_action_executor_type": None,  # Handled as a sequence: click field, then type text
        "refinement_needed": True,  # For the field target (before clicking)
    },
    "PRESS_KEY_SIMPLE": {
        "description": "Presses a single standard keyboard key (e.g., 'enter', 'tab', 'escape').",
        "expected_params_from_gemini": ["key_name"],
        "maps_to_action_executor_type": "press_key",
        "refinement_needed": False,
    },
    "CHECK_VISUAL_STATE": {
        "description": "Checks if a visual condition described textually is met (e.g., 'if an error message is visible', 'is the Save button enabled?'). Used for conditional branching in NLU tasks. Result is true/false.",
        "expected_params_from_gemini": ["condition_description"],
        "maps_to_action_executor_type": None,  # Internal evaluation, not a direct PyAutoGUI action
        "refinement_needed": False,  # The description is evaluated against an image.
    },
    # Example: "WAIT_SHORT": {
    #     "description": "Waits for a short duration (e.g., 1.5 seconds).",
    #     "expected_params_from_gemini": ["duration_seconds"],
    #     "maps_to_action_executor_type": "wait", # Assumes ActionExecutor could have a 'wait' type
    #     "refinement_needed": False
    # },
}

# Default model for NLU parsing and complex planning, can be overridden by profile settings if desired
DEFAULT_NLU_PLANNING_MODEL = "gemini-1.5-pro-latest"
# Default model for visual refinement (bounding box) and visual state checks - flash is faster
DEFAULT_VISUAL_REFINE_MODEL = "gemini-1.5-flash-latest"


class GeminiDecisionModule:
    """
    Parses Natural Language User Commands (v4.0.0 Phase 3), decomposes them into
    tasks/steps, and orchestrates their execution. For each step, it uses Gemini
    (via GeminiAnalyzer) for visual analysis to determine appropriate primitive
    actions and refine targets, then calls ActionExecutor.
    Also handles simpler goal-driven single action selection (v4.0.0 Phase 2)
    if `natural_language_command` is not provided but `goal_prompt` is.
    """

    def __init__(
        self,
        gemini_analyzer: GeminiAnalyzer,
        action_executor: ActionExecutor,
        config_manager: ConfigManager,
    ):
        if not isinstance(gemini_analyzer, GeminiAnalyzer) or not gemini_analyzer.client_initialized:
            logger.critical("GeminiDecisionModule CRITICAL: Initialized with an invalid or uninitialized GeminiAnalyzer. AI decision features will fail.")
            raise ValueError("A valid, initialized GeminiAnalyzer instance is required for GeminiDecisionModule.")
        self.gemini_analyzer = gemini_analyzer

        if not isinstance(action_executor, ActionExecutor):
            logger.critical("GeminiDecisionModule CRITICAL: Initialized without a valid ActionExecutor.")
            raise ValueError("ActionExecutor instance is required.")
        self.action_executor = action_executor

        if not isinstance(config_manager, ConfigManager):
            logger.critical("GeminiDecisionModule CRITICAL: Initialized without a valid ConfigManager.")
            raise ValueError("ConfigManager instance is required.")
        self.config_manager = config_manager  # Used to get region screen coordinates for refinement

        logger.info("GeminiDecisionModule (NLU Task Orchestrator & Goal Executor) initialized.")

    def _construct_nlu_parse_prompt(self, natural_language_command: str) -> str:
        """Constructs the prompt for Gemini to parse the NLU command into a structured plan."""
        # NLU Schema Description as defined in TECHNICAL_DESIGN.MD Section 14.4.1 and implemented
        nlu_schema_description = """
You are an NLU (Natural Language Understanding) parser for a desktop automation tool named Mark-I.
Your task is to analyze the user's natural language command and convert it into a structured JSON plan.
The user's command might describe a single action, a sequence of actions, or a conditional statement.

Respond with a single JSON object with a top-level key "parsed_task".
The "parsed_task" object MUST have:
1.  "command_type": A string, one of "SINGLE_INSTRUCTION", "SEQUENTIAL_INSTRUCTIONS", "CONDITIONAL_INSTRUCTION".
2.  If "command_type" is "SINGLE_INSTRUCTION":
    It MUST contain an "instruction_details" object with:
    - "intent_verb": A string representing the primary action verb (e.g., "CLICK", "TYPE", "PRESS_KEY", "FIND_ELEMENT", "CHECK_CONDITION").
    - "target_description": A string describing the UI element to interact with (e.g., "the login button", "the username field that is currently empty"). Can be null if not applicable.
    - "parameters": An object containing other necessary parameters. Examples:
        - For "TYPE": {"text_to_type": "user@example.com"}
        - For "PRESS_KEY": {"key_name": "tab"}
3.  If "command_type" is "SEQUENTIAL_INSTRUCTIONS":
    It MUST contain a "steps" array. Each element is an object with:
    - "step_number": An integer (1-indexed).
    - "instruction_details": An object matching the "instruction_details" schema above.
4.  If "command_type" is "CONDITIONAL_INSTRUCTION":
    It MUST contain:
    - "condition_description": A string describing the visual condition to check (e.g., "an error message is visible on screen").
    - "then_branch": An object representing the task if the condition is true (conforming to "parsed_task" schema).
    - "else_branch": Optional. An object for the task if false (conforming to "parsed_task" schema). Can be null or omitted.

Focus on identifying core actions, targets, and parameters.
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
        prompt = f'{nlu_schema_description}\n\nUser Command to Parse: "{natural_language_command}"\n\nProvide your parsed JSON output now, ensuring it is a single, valid JSON object starting with `{{` and ending with `}}`:'
        return prompt

    def _map_nlu_intent_to_allowed_sub_action(self, nlu_intent_verb: Optional[str]) -> Optional[str]:
        """Maps a parsed NLU intent verb to one of the PREDEFINED_ALLOWED_SUB_ACTIONS keys."""
        if not nlu_intent_verb or not isinstance(nlu_intent_verb, str):
            return None
        verb = nlu_intent_verb.strip().upper()
        # This mapping needs to be robust and potentially expanded.
        if "CLICK" in verb or ("PRESS" in verb and "BUTTON" in verb) or "SELECT" in verb:
            return "CLICK_DESCRIBED_ELEMENT"
        if "TYPE" in verb or "ENTER" in verb and "KEY" not in verb or "FILL" in verb or "INPUT" in verb:
            return "TYPE_IN_DESCRIBED_FIELD"
        if ("PRESS" in verb and "KEY" in verb) or verb in ["HIT_ENTER", "SUBMIT_FORM_WITH_ENTER"]:
            return "PRESS_KEY_SIMPLE"  # More specific for keys
        if "CHECK" in verb or "VERIFY" in verb or "IS" in verb and ("VISIBLE" in verb or "PRESENT" in verb or "ENABLED" in verb or "DISABLED" in verb) or "IF" in verb and "STATE" in verb:
            return "CHECK_VISUAL_STATE"
        # if "WAIT" in verb or "PAUSE" in verb: return "WAIT_SHORT" # Example for future
        logger.warning(f"NLU Intent verb '{nlu_intent_verb}' (normalized to '{verb}') could not be mapped to a predefined sub-action type.")
        return None

    def _construct_sub_step_action_suggestion_prompt(self, sub_step_goal_description: str, allowed_sub_actions_map: Dict[str, Any]) -> str:  # Used if NLU step is too high-level
        # This method was part of the v4 Phase 2 design for single goal_prompts.
        # For NLU (Phase 3), the NLU parse should ideally give us primitive enough intents.
        # If an NLU step's intent_verb is too abstract, this *could* be used to ask Gemini
        # to pick a primitive from PREDEFINED_ALLOWED_SUB_ACTIONS for *that specific intent_verb*.
        # However, the primary NLU prompt now aims to get these primitive intents directly.
        # Keeping this for potential future use or if NLU output needs further refinement.
        logger.debug(f"Constructing sub-step action suggestion prompt for sub-goal: '{sub_step_goal_description}' (This path might be less used if NLU is direct).")
        actions_desc_parts = [f"- \"{name}\": {meta['description']} Expected parameters: [{', '.join(meta.get('expected_params_from_gemini',[]))}]" for name, meta in allowed_sub_actions_map.items()]
        prompt = f'You are an AI assistant executing one step of an automated task. Sub-goal: "{sub_step_goal_description}". Based on the image, choose ONE action from:\n{chr(10).join(actions_desc_parts)}\nRespond JSON: {{"action_type": "CHOSEN_TYPE", "parameters": {{...}}, "reasoning": "..."}}'
        return prompt

    def _refine_target_description_to_bbox(  # No changes from previous version
        self, target_description: str, context_image: np.ndarray, context_image_region_name: str, task_rule_name_for_log: str
    ) -> Optional[Dict[str, Any]]:
        log_prefix = f"R '{task_rule_name_for_log}', NLU Task TargetRefine"
        logger.info(f"{log_prefix}: Refining target: '{target_description}' in rgn '{context_image_region_name}'")
        prompt = (
            f"Precise visual element locator. In image '{context_image_region_name}', identify: \"{target_description}\".\n"
            f'Respond ONLY JSON: {{"found": true/false, "box": [x,y,w,h_or_null], "element_label": "{target_description}"}}'
        )
        response = self.gemini_analyzer.query_vision_model(context_image, prompt, model_name_override=DEFAULT_VISUAL_REFINE_MODEL)
        if response["status"] == "success" and response["json_content"]:
            data = response["json_content"]
            if isinstance(data, dict) and "found" in data and "box" in data:
                if data["found"] and isinstance(data["box"], list) and len(data["box"]) == 4 and all(isinstance(n, (int, float)) for n in data["box"]) and data["box"][2] > 0 and data["box"][3] > 0:
                    box = [int(round(n)) for n in data["box"]]
                    logger.info(f"{log_prefix}: Target '{target_description}' refined to bbox: {box}")
                    return {"value": {"box": box, "found": True, "element_label": target_description}, "_source_region_for_capture_": context_image_region_name}
                elif not data["found"]:
                    logger.info(f"{log_prefix}: Target '{target_description}' not found by Gemini.")
                else:
                    logger.warning(f"{log_prefix}: Refined box data for '{target_description}' invalid: {data['box']}")
            else:
                logger.warning(f"{log_prefix}: Refinement JSON structure unexpected: {data}")
        else:
            logger.error(f"{log_prefix}: Refinement query failed. Status: {response['status']}, Err: {response.get('error_message')}")
        return None

    def _execute_primitive_sub_action(  # Renamed from _execute_single_parsed_instruction
        self,
        step_instruction_details: Dict[str, Any],  # Contains intent_verb, target_description, parameters
        current_visual_context_images: Dict[str, np.ndarray],  # All available context images
        primary_context_region_name: str,  # The main region for this step's visual analysis/targeting
        task_rule_name_for_log: str,  # Original rule name for logging context
        task_parameters_from_rule: Dict[str, Any],  # Original task parameters for confirmation flags, etc.
    ) -> bool:  # Returns True if successful, False otherwise
        log_prefix = f"R '{task_rule_name_for_log}', NLU SubStep"
        intent_verb = step_instruction_details.get("intent_verb")
        target_desc_from_nlu = step_instruction_details.get("target_description")  # May be null
        params_from_nlu = step_instruction_details.get("parameters", {})
        if not isinstance(params_from_nlu, dict):
            params_from_nlu = {}  # Ensure dict

        logger.info(f"{log_prefix}: Executing primitive. Intent='{intent_verb}', TargetDesc='{target_desc_from_nlu}', NLU Params={params_from_nlu}")

        primitive_action_type = self._map_nlu_intent_to_allowed_sub_action(intent_verb)
        if not primitive_action_type:
            logger.error(f"{log_prefix}: Could not map NLU intent '{intent_verb}' to an allowed primitive sub-action. Step failed.")
            return False

        action_meta = PREDEFINED_ALLOWED_SUB_ACTIONS[primitive_action_type]
        final_ae_spec: Dict[str, Any] = {  # Spec for ActionExecutor
            "type": "",  # To be filled by action_meta["maps_to_action_executor_type"] or logic
            "context": {
                "rule_name": f"{task_rule_name_for_log}_NLU_SubStep_{primitive_action_type.replace('_','-')}",  # More specific context name
                "variables": {},  # For refined target data if needed by ActionExecutor
                "condition_region": primary_context_region_name,  # Region providing primary visual context
            },
            "pyautogui_pause_before": task_parameters_from_rule.get("pyautogui_pause_before", 0.1),  # From outer task spec
        }

        # Get current image for this step (must exist)
        current_step_image_np = current_visual_context_images.get(primary_context_region_name)
        if current_step_image_np is None:
            logger.error(f"{log_prefix}: Primary context image for region '{primary_context_region_name}' is missing for step. Cannot proceed. Step failed.")
            return False

        # Refine target if needed for this primitive action type
        refined_target_data_for_ae: Optional[Dict[str, Any]] = None
        if action_meta.get("refinement_needed", False):
            if not target_desc_from_nlu or not isinstance(target_desc_from_nlu, str):
                logger.error(f"{log_prefix}: Primitive action '{primitive_action_type}' requires 'target_description' from NLU, but it's missing or invalid. Params: {params_from_nlu}. Step failed.")
                return False
            refined_target_data_for_ae = self._refine_target_description_to_bbox(target_desc_from_nlu, current_step_image_np, primary_context_region_name, task_rule_name_for_log)
            if not refined_target_data_for_ae:  # _refine_target logs details
                logger.error(f"{log_prefix}: Failed to refine target '{target_desc_from_nlu}' for primitive action '{primitive_action_type}'. Step failed.")
                return False

        # --- Construct ActionExecutor spec based on primitive_action_type ---
        action_executor_type = action_meta.get("maps_to_action_executor_type")

        if primitive_action_type == "CLICK_DESCRIBED_ELEMENT":
            if not refined_target_data_for_ae:
                logger.critical(f"{log_prefix}: Internal error - refined target data missing for CLICK. Step failed.")
                return False
            temp_var_name = f"_nlu_step_target_{time.monotonic_ns()}"  # Unique temp var name
            final_ae_spec["context"]["variables"][temp_var_name] = refined_target_data_for_ae
            final_ae_spec["type"] = action_executor_type  # Should be "click"
            final_ae_spec["target_relation"] = "center_of_gemini_element"  # Default relation for AI found elements
            final_ae_spec["gemini_element_variable"] = temp_var_name
            final_ae_spec["button"] = params_from_nlu.get("button", "left")  # Allow NLU/Gemini to specify button
            final_ae_spec["clicks"] = int(params_from_nlu.get("clicks", 1))  # Allow NLU/Gemini to specify clicks
            final_ae_spec["interval"] = float(params_from_nlu.get("interval", 0.0))

        elif primitive_action_type == "TYPE_IN_DESCRIBED_FIELD":
            if not refined_target_data_for_ae:
                logger.critical(f"{log_prefix}: Internal error - refined target data missing for TYPE. Step failed.")
                return False
            text_to_type = params_from_nlu.get("text_to_type")
            if not isinstance(text_to_type, str):  # text can be empty
                logger.error(f"{log_prefix}: 'text_to_type' missing or invalid for TYPE_IN_DESCRIBED_FIELD. NLU Params: {params_from_nlu}. Step failed.")
                return False

            # Sequence: 1. Click the field to activate it
            click_var_name_type = f"_nlu_type_field_target_{time.monotonic_ns()}"
            click_context_vars = {click_var_name_type: refined_target_data_for_ae}
            click_spec_for_type = {
                "type": "click",
                "target_relation": "center_of_gemini_element",
                "gemini_element_variable": click_var_name_type,
                "button": "left",
                "clicks": 1,
                "pyautogui_pause_before": 0.15,  # Small pause before clicking field
                "context": {**final_ae_spec["context"], "variables": click_context_vars},  # Use step's context
            }
            logger.info(f"{log_prefix}: Executing pre-type click on '{target_desc_from_nlu}'")
            try:
                self.action_executor.execute_action(click_spec_for_type)
            except Exception as e_click_field:
                logger.error(f"{log_prefix}: Failed to execute pre-type click on field '{target_desc_from_nlu}': {e_click_field}", exc_info=True)
                return False
            time.sleep(0.2)  # Small delay after click, before typing, for UI to respond

            # 2. Type the text
            final_ae_spec["type"] = "type_text"  # ActionExecutor type
            final_ae_spec["text"] = text_to_type
            final_ae_spec["interval"] = float(params_from_nlu.get("typing_interval", 0.01))  # Allow NLU/Gemini to suggest typing speed
            # The main pyautogui_pause_before from final_ae_spec will apply before this typewrite action

        elif primitive_action_type == "PRESS_KEY_SIMPLE":
            key_name = params_from_nlu.get("key_name")
            if not key_name or not isinstance(key_name, str):
                logger.error(f"{log_prefix}: 'key_name' missing or invalid for PRESS_KEY_SIMPLE. NLU Params: {params_from_nlu}. Step failed.")
                return False
            final_ae_spec["type"] = action_executor_type  # "press_key"
            final_ae_spec["key"] = key_name  # ActionExecutor validates this key

        elif primitive_action_type == "CHECK_VISUAL_STATE":
            condition_desc_from_params = params_from_nlu.get("condition_description", target_desc_from_nlu)  # Fallback to target_desc if specific param missing
            if not condition_desc_from_params:
                logger.error(f"{log_prefix}: 'condition_description' missing for CHECK_VISUAL_STATE. Step failed.")
                return False

            check_prompt = f"Based on the provided image of region '{primary_context_region_name}', is the following condition true or false? Condition: \"{condition_desc_from_params}\". Respond with only the single word 'true' or 'false'."
            logger.info(f"{log_prefix}: Evaluating visual state: '{condition_desc_from_params}' in region '{primary_context_region_name}'")

            gemini_eval_response = self.gemini_analyzer.query_vision_model(current_step_image_np, check_prompt, model_name_override=DEFAULT_VISUAL_REFINE_MODEL)
            if gemini_eval_response["status"] == "success" and gemini_eval_response["text_content"]:
                response_text = gemini_eval_response["text_content"].strip().lower()
                if response_text == "true":
                    logger.info(f"{log_prefix}: Visual state '{condition_desc_from_params}' evaluated to TRUE by Gemini.")
                    return True
                elif response_text == "false":
                    logger.info(f"{log_prefix}: Visual state '{condition_desc_from_params}' evaluated to FALSE by Gemini.")
                    return False
                else:
                    logger.warning(f"{log_prefix}: CHECK_VISUAL_STATE got ambiguous response from Gemini: '{response_text}'. Interpreting as FALSE.")
                    return False
            else:
                logger.error(f"{log_prefix}: CHECK_VISUAL_STATE failed. Gemini query status: {gemini_eval_response['status']}, Error: {gemini_eval_response.get('error_message')}")
                return False

        else:  # Should be caught by earlier mapping check
            logger.error(f"{log_prefix}: Internal error - unhandled primitive action type '{primitive_action_type}'. Step failed.")
            return False

        # User Confirmation for actual UI-interacting actions
        if task_parameters_from_rule.get("require_confirmation_per_step", True) and final_ae_spec.get("type"):
            action_desc_for_confirm = f"{final_ae_spec.get('type')} on target '{target_desc_from_nlu or 'N/A'}'"
            if primitive_action_type == "TYPE_IN_DESCRIBED_FIELD":
                action_desc_for_confirm = f"TYPE '{params_from_nlu.get('text_to_type')}' in '{target_desc_from_nlu}'"
            elif primitive_action_type == "PRESS_KEY_SIMPLE":
                action_desc_for_confirm = f"PRESS_KEY '{params_from_nlu.get('key_name')}'"

            logger.info(f"{log_prefix}: USER CONFIRMATION REQUIRED for: {action_desc_for_confirm}")
            # Actual confirmation dialog would be handled by the GUI Wizard calling this module.
            # This module assumes if confirmation is needed, it's handled externally before proceeding OR it simulates 'yes'.
            # For now, we proceed as if confirmed by user for backend logic testing.
            # A real system would return a special status to GUI to pop up dialog.

        # Execute the prepared action (if it's not a check that already returned or a sequence handled above)
        if final_ae_spec.get("type"):  # Check if 'type' was set (CHECK_VISUAL_STATE doesn't set it for direct AE call)
            try:
                loggable_ae_spec = {k: v for k, v in final_ae_spec.items() if k != "context"}  # Log without large context
                logger.info(f"{log_prefix}: Dispatching to ActionExecutor. Spec (params only): {loggable_ae_spec}")
                self.action_executor.execute_action(final_ae_spec)  # Pass full spec with context
                logger.info(f"{log_prefix}: Primitive action '{final_ae_spec['type']}' targeting '{target_desc_from_nlu or 'N/A'}' executed successfully.")
                return True
            except Exception as e_ae_exec:
                logger.error(f"{log_prefix}: Error during ActionExecutor execution for primitive action '{final_ae_spec['type']}': {e_ae_exec}", exc_info=True)
                return False
        else:  # Should only be for CHECK_VISUAL_STATE which returns boolean directly
            logger.error(f"{log_prefix}: No ActionExecutor type set for primitive action '{primitive_action_type}'. This is unexpected if not CHECK_VISUAL_STATE.")
            return False

    def execute_nlu_task(  # Main entry point for NLU tasks from RulesEngine
        self,
        task_rule_name: str,  # Name of the rule that triggered this NLU task
        natural_language_command: str,
        initial_context_images: Dict[str, np.ndarray],  # {region_name: image_data_np_bgr}
        task_parameters: Dict[str, Any],  # Parameters from the "gemini_perform_task" action spec in the rule
    ) -> Dict[str, Any]:
        """
        Orchestrates execution of a task described by a natural language command.
        1. Parses NLU command into a structured plan using Gemini.
        2. Executes steps in the plan by calling _execute_primitive_sub_action for each.
        """
        overall_task_result = {"status": "failure", "message": "NLU task initiated.", "executed_steps_summary": []}
        log_prefix_task = f"R '{task_rule_name}', NLU Task Command='{natural_language_command[:60].replace(os.linesep,' ')}...'"
        logger.info(f"{log_prefix_task}: Starting execution of Natural Language Command.")

        if not self.gemini_analyzer or not self.gemini_analyzer.client_initialized:
            overall_task_result["message"] = "GeminiAnalyzer not available for NLU task."
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}")
            return overall_task_result

        # 1. NLU Parsing and Task Decomposition
        nlu_parse_prompt = self._construct_nlu_parse_prompt(natural_language_command)
        # Use a powerful model for NLU parsing. Image context is optional for this prompt.
        nlu_context_image = next(iter(initial_context_images.values()), None) if initial_context_images else np.zeros((1, 1, 3), dtype=np.uint8)  # Dummy if no image

        nlu_response = self.gemini_analyzer.query_vision_model(
            image_data=nlu_context_image,  # Can be None or dummy if model handles text-only well
            prompt=nlu_parse_prompt,
            model_name_override=task_parameters.get("nlu_model_override", DEFAULT_NLU_PLANNING_MODEL),
        )

        if nlu_response["status"] != "success" or not nlu_response["json_content"]:
            overall_task_result["message"] = f"NLU parsing query failed. Gemini Status: {nlu_response['status']}, Error: {nlu_response.get('error_message', 'No JSON content')}"
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}. Raw NLU Response Text: {nlu_response.get('text_content')}")
            return overall_task_result

        parsed_task_plan_from_nlu: Optional[Dict[str, Any]] = None
        try:
            json_response_content = nlu_response["json_content"]
            if not isinstance(json_response_content, dict) or "parsed_task" not in json_response_content:
                raise ValueError("NLU JSON response from Gemini missing 'parsed_task' top-level key.")
            parsed_task_plan_from_nlu = json_response_content["parsed_task"]
            if not isinstance(parsed_task_plan_from_nlu, dict):
                raise ValueError("'parsed_task' value in Gemini NLU response is not a dictionary.")
            logger.info(f"{log_prefix_task}: NLU command parsed successfully. Plan Type: {parsed_task_plan_from_nlu.get('command_type')}")
            logger.debug(f"{log_prefix_task}: Full NLU parsed plan: {json.dumps(parsed_task_plan_from_nlu, indent=2)}")
        except Exception as e_nlu_parse:
            overall_task_result["message"] = f"Error processing NLU JSON structure from Gemini: {e_nlu_parse}. Response: {nlu_response['json_content']}"
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}", exc_info=True)
            return overall_task_result

        # --- Recursive executor for the parsed plan (handles nested tasks for conditionals) ---
        # It needs access to the *current* visual context, which might change per step.
        # For v5.0.0 initial, we assume initial_context_images is used for all steps,
        # or a primary region from it. True multi-step with screen updates is more complex.

        current_visual_context_for_steps = initial_context_images

        # Determine primary context region for executing sub-steps
        # This is the region whose image will be passed for refinement or CHECK_VISUAL_STATE
        primary_context_region_name_for_steps = ""
        if task_parameters.get("context_region_names") and isinstance(task_parameters["context_region_names"], list) and task_parameters["context_region_names"]:
            primary_context_region_name_for_steps = task_parameters["context_region_names"][0]  # Use first specified
            if primary_context_region_name_for_steps not in current_visual_context_for_steps:
                logger.warning(f"{log_prefix_task}: Specified primary context region '{primary_context_region_name_for_steps}' not found in provided images. Will try first available.")
                primary_context_region_name_for_steps = ""  # Reset to find first available

        if not primary_context_region_name_for_steps and current_visual_context_for_steps:  # Fallback
            primary_context_region_name_for_steps = list(current_visual_context_for_steps.keys())[0]

        if not primary_context_region_name_for_steps:
            overall_task_result["message"] = "NLU Task Execution: Could not determine a primary context region with an image for executing steps."
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}")
            return overall_task_result

        logger.info(f"{log_prefix_task}: Primary context region for step execution set to '{primary_context_region_name_for_steps}'.")

        # --- Define recursive execution function ---
        # This function will process a "parsed_task" node (which can be single, sequential, or conditional)
        # It needs to manage its own state for step counting and results for logging.

        # Keep track of executed step descriptions for the summary
        executed_steps_log: List[str] = []

        def _recursive_execute_plan_node(
            plan_node_data: Dict[str, Any], current_images: Dict[str, np.ndarray], primary_rgn_name: str, depth: int = 0, branch_prefix: str = ""  # For logging, e.g., "THEN_Branch_Step"
        ) -> bool:  # True if all steps in this node (and sub-nodes) succeeded

            if depth > task_parameters.get("max_recursion_depth_nlu", 5):  # Safeguard recursion
                logger.error(f"{log_prefix_task}: Max recursion depth ({depth}) reached in NLU task execution. Aborting this branch: {branch_prefix}")
                executed_steps_log.append(f"Error: Max recursion at {branch_prefix}")
                return False

            node_type = plan_node_data.get("command_type")
            node_log_id = f"{branch_prefix}Type'{node_type}'"
            logger.debug(f"{log_prefix_task}: Recursive exec {node_log_id} at depth {depth}.")

            if node_type == "SINGLE_INSTRUCTION":
                instr_details = plan_node_data.get("instruction_details")
                if isinstance(instr_details, dict):
                    step_success = self._execute_primitive_sub_action(instr_details, current_images, primary_rgn_name, f"{task_rule_name}_{branch_prefix}Single", task_parameters)
                    executed_steps_log.append(f"{branch_prefix}Single '{instr_details.get('intent_verb')}': {'OK' if step_success else 'FAIL'}")
                    return step_success
                else:
                    logger.error(f"{log_prefix_task}: {node_log_id} missing valid 'instruction_details'.")
                    executed_steps_log.append(f"{branch_prefix}Single: FormatFAIL")
                    return False

            elif node_type == "SEQUENTIAL_INSTRUCTIONS":
                steps_list = plan_node_data.get("steps", [])
                if not isinstance(steps_list, list) or not steps_list:
                    logger.error(f"{log_prefix_task}: {node_log_id} missing valid 'steps' list.")
                    executed_steps_log.append(f"{branch_prefix}Sequence: FormatFAIL")
                    return False

                max_s = task_parameters.get("max_steps", len(steps_list))  # Max steps for this sequence
                for i, step_item_data in enumerate(steps_list):
                    if i >= max_s:
                        logger.info(f"{log_prefix_task}: {node_log_id} reached max_steps ({max_s}).")
                        break

                    if not isinstance(step_item_data, dict) or "instruction_details" not in step_item_data:
                        logger.error(f"{log_prefix_task}: {node_log_id} invalid step data at index {i}: {step_item_data}. Aborting sequence.")
                        executed_steps_log.append(f"{branch_prefix}SeqStep{i+1}: FormatFAIL")
                        return False

                    instr_details = step_item_data["instruction_details"]
                    step_num = step_item_data.get("step_number", i + 1)
                    logger.info(
                        f"{log_prefix_task}: {branch_prefix}SeqStep {step_num}/{len(steps_list)}: Intent='{instr_details.get('intent_verb')}' Target='{instr_details.get('target_description')}'"
                    )

                    # TODO: Implement visual context refresh per step:
                    # refreshed_images = self._refresh_visual_context(task_parameters.get("context_region_names", [primary_rgn_name]))
                    # current_images_for_step = refreshed_images if refreshed_images else current_images
                    current_images_for_step = current_images  # Using initial for now for all steps

                    step_success = self._execute_primitive_sub_action(instr_details, current_images_for_step, primary_rgn_name, f"{task_rule_name}_{branch_prefix}SeqStep{step_num}", task_parameters)
                    executed_steps_log.append(f"{branch_prefix}SeqStep{step_num} '{instr_details.get('intent_verb')}': {'OK' if step_success else 'FAIL'}")
                    if not step_success:
                        return False  # Halt sequence on first failure
                    time.sleep(float(task_parameters.get("delay_between_nlu_steps_sec", 0.3)))  # Small delay
                return True  # All steps in sequence succeeded

            elif node_type == "CONDITIONAL_INSTRUCTION":
                cond_desc = plan_node_data.get("condition_description")
                then_plan_node = plan_node_data.get("then_branch")
                else_plan_node = plan_node_data.get("else_branch")  # Optional

                if not cond_desc or not isinstance(then_plan_node, dict):
                    logger.error(f"{log_prefix_task}: {node_log_id} missing 'condition_description' or valid 'then_branch'.")
                    executed_steps_log.append(f"{branch_prefix}Condition: FormatFAIL")
                    return False

                eval_instr = {"intent_verb": "CHECK_VISUAL_STATE", "target_description": cond_desc, "parameters": {"condition_description": cond_desc}}
                logger.info(f"{log_prefix_task}: {branch_prefix}Evaluating IF condition: '{cond_desc}'")
                condition_met_bool = self._execute_primitive_sub_action(eval_instr, current_images, primary_rgn_name, f"{task_rule_name}_{branch_prefix}IF_Check", task_parameters)
                executed_steps_log.append(f"{branch_prefix}IF '{cond_desc}': {'TRUE' if condition_met_bool else 'FALSE'}")

                target_branch_plan = None
                new_branch_prefix_for_log = ""
                if condition_met_bool:
                    logger.info(f"{log_prefix_task}: {branch_prefix}IF condition is TRUE. Executing THEN branch.")
                    target_branch_plan = then_plan_node
                    new_branch_prefix_for_log = f"{branch_prefix}THEN."
                elif isinstance(else_plan_node, dict):  # Else branch exists and is a valid structure
                    logger.info(f"{log_prefix_task}: {branch_prefix}IF condition is FALSE. Executing ELSE branch.")
                    target_branch_plan = else_plan_node
                    new_branch_prefix_for_log = f"{branch_prefix}ELSE."
                else:  # Condition false, no else branch
                    logger.info(f"{log_prefix_task}: {branch_prefix}IF condition is FALSE. No ELSE branch. Conditional execution complete for this path.")
                    return True  # This path of conditional is considered successful

                if target_branch_plan:
                    return _recursive_execute_plan_node(target_branch_plan, current_images, primary_rgn_name, depth + 1, new_branch_prefix_for_log)
                return True  # No branch was executed (e.g. cond false, no else) - considered success for this conditional node.

            else:
                logger.error(f"{log_prefix_task}: {node_log_id} Unknown 'command_type'.")
                executed_steps_log.append(f"{branch_prefix}UnknownTypeFAIL")
                return False

        # --- End of recursive execution function ---

        # Start recursive execution with the top-level parsed plan
        final_success = _recursive_execute_plan_node(parsed_task_plan_from_nlu, current_visual_context_for_steps, primary_context_region_name_for_steps)

        overall_task_result["status"] = "success" if final_success else "failure"
        if final_success:
            overall_task_result["message"] = "NLU task executed all steps successfully."
        elif not overall_task_result.get("message") or overall_task_result["message"] == "NLU task initiated.":  # If no specific error message was set by a failing step
            overall_task_result["message"] = "NLU task failed at one or more steps."

        overall_task_result["executed_steps_summary"] = executed_steps_log
        logger.info(f"{log_prefix_task}: Final NLU task status: {overall_task_result['status']}. Summary: {overall_task_result['message']}")
        logger.debug(f"{log_prefix_task}: Executed steps log: {executed_steps_log}")
        return overall_task_result
