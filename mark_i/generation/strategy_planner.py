import logging
import json  # For parsing Gemini's JSON response and debug logging
from typing import Dict, Any, Optional, List
import os  # For os.linesep

import numpy as np  # For type hint of initial_visual_context_image

# Assuming GeminiAnalyzer is correctly located for import
from mark_i.engines.gemini_analyzer import GeminiAnalyzer

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.generation.strategy_planner")

# --- Type Aliases for Clarity ---
# Defines the expected structure of a single step in the intermediate plan
IntermediatePlanStep = Dict[str, Any]
# Example:
# {
#   "step_id": 1,
#   "description": "Locate and identify the 'Username' input field on the login screen.",
#   "suggested_element_type_hint": "input_field", # Optional hint
#   "required_user_input_for_step": ["username_value_to_type"] # Optional list of params user needs to provide later
# }

# Defines the overall intermediate plan structure
IntermediatePlan = List[IntermediatePlanStep]

# Default model for complex planning, can be overridden
DEFAULT_STRATEGY_PLANNING_MODEL = "gemini-1.5-flash-latest"  # Or another powerful model suitable for JSON generation and reasoning


class StrategyPlanner:
    """
    Responsible for taking a high-level user goal and, using Gemini via GeminiAnalyzer,
    translating it into an "intermediate plan." This plan is a sequence of logical,
    human-understandable sub-steps, structured as JSON, which will then be used
    by the ProfileGenerator to guide the interactive creation of a Mark-I profile.
    This is a core component of the v5.0.0 AI-Driven Profile Generation feature.
    """

    def __init__(self, gemini_analyzer: GeminiAnalyzer):
        """
        Initializes the StrategyPlanner.

        Args:
            gemini_analyzer: An instance of GeminiAnalyzer to communicate with Gemini models.
                             This is a critical dependency.
        """
        if not isinstance(gemini_analyzer, GeminiAnalyzer) or not gemini_analyzer.client_initialized:
            logger.critical("StrategyPlanner CRITICAL ERROR: Initialized without a valid or initialized GeminiAnalyzer instance. Plan generation will fail.")
            raise ValueError("A valid, initialized GeminiAnalyzer instance is required for StrategyPlanner.")
        self.gemini_analyzer = gemini_analyzer
        logger.info("StrategyPlanner initialized successfully with GeminiAnalyzer.")

    def _construct_goal_to_plan_prompt(self, user_goal: str, application_context_description: Optional[str] = None) -> str:
        """
        Constructs the detailed prompt for Gemini to break down a high-level user goal
        into a sequence of logical, human-understandable sub-steps, ensuring output as JSON.

        Args:
            user_goal: The natural language goal provided by the user.
            application_context_description: Optional. Brief textual description of the
                                             application or context (e.g., "target application is MyApp v2.3",
                                             "currently on the main dashboard of the web app").

        Returns:
            The formatted prompt string to be sent to Gemini.
        """
        # Detailed schema and instructions for the "intermediate plan" JSON
        plan_schema_description = """
You are an expert automation planner for a visual desktop automation tool named Mark-I.
Your primary task is to take a user's high-level automation goal and decompose it into a sequence of clear, logical, and distinct sub-steps.
Each sub-step should represent a simple user interaction (like finding an element, clicking an element, typing text into a field) or a necessary observation/check required to achieve the overall goal.
The output of these steps will guide a human user, with further AI assistance, in creating a detailed automation profile for Mark-I.

The user's goal is: "{user_goal}"
{application_context_info}

You *MUST* respond with a single JSON object. This JSON object *MUST* have a top-level key named "intermediate_plan".
The value associated with "intermediate_plan" *MUST* be an array of "plan_step" objects.
Each "plan_step" object in the array *MUST* adhere to the following structure:
  - "step_id": (Integer, Required) A unique integer, starting from 1, identifying the step in its sequential order.
  - "description": (String, Required) A concise, human-readable natural language description of the sub-goal for this specific step. This description should be unambiguous and clear enough for another AI or a human to understand precisely what needs to be visually identified on the screen or what action needs to be performed.
        Examples:
        - "Locate and identify the 'Username' input field on the current login screen."
        - "Type the user-provided username into the identified username field."
        - "Find the button distinctly labeled 'Login' or 'Sign In'."
        - "Click the identified 'Login' or 'Sign In' button."
        - "Verify that a 'Login Successful' message or the main dashboard is visible after submission."
  - "suggested_element_type_hint": (String, Optional, can be null or omitted) A hint about the type of UI element primarily involved in this step (e.g., "button", "input_field", "text_label", "menu_item", "dialog_box", "icon", "checkbox", "dropdown", "link").
  - "required_user_input_for_step": (Array of Strings, Optional, can be null or an empty array) An array where each string is a placeholder or description of specific data values the user will likely need to provide when Mark-I later helps implement this step (e.g., ["actual_username_to_type"], ["filename_for_saving_report.pdf"], ["specific_error_text_to_check_for"]).

Example of a single "plan_step" object within the "intermediate_plan" array:
{{
  "step_id": 1,
  "description": "Find and identify the primary 'File' menu item, usually at the top of the application window.",
  "suggested_element_type_hint": "menu_item",
  "required_user_input_for_step": []
}}

Key Considerations for your Plan:
- Ensure the steps are in a logical and correct sequence to achieve the user's overall goal.
- Step descriptions should be atomic enough to map to one or two simple visual automation primitives later (e.g., find element, click, type, check text).
- Avoid ambiguity in descriptions. Be explicit about what to find or do.
- If the user's goal is too vague, overly complex for a simple sequence, or seems unsafe to automate directly with visual primitives, you should still attempt to generate a plan for the initial, most plausible interpretation. If truly impossible, your JSON can have an empty "intermediate_plan" array and a "reasoning_for_empty_plan" key explaining why.
- The plan should typically consist of a reasonable number of steps (e.g., 3-15 steps for common desktop tasks). For very complex goals, focus on outlining the initial key stages.
"""
        app_context_info_str = (
            f"Additional application context to consider: {application_context_description}"
            if application_context_description
            else "No specific application context was provided beyond the user's goal and any accompanying initial screenshot (if provided to the multimodal endpoint)."
        )

        prompt = plan_schema_description.format(user_goal=user_goal, application_context_info=app_context_info_str)
        prompt += "\n\nNow, generate the JSON object containing the 'intermediate_plan' based on the user's goal and any provided context. Your entire response MUST be only this single, valid JSON object, starting with `{` and ending with `}`."
        return prompt

    def generate_intermediate_plan(
        self,
        user_goal: str,
        initial_visual_context_image: Optional[np.ndarray] = None,  # BGR NumPy array
        application_context_description: Optional[str] = None,
        plan_generation_model_override: Optional[str] = None,
    ) -> Optional[IntermediatePlan]:
        """
        Generates an intermediate, step-by-step plan from a high-level user goal using Gemini.

        Args:
            user_goal: The natural language goal from the user.
            initial_visual_context_image: Optional. A NumPy BGR image of the initial screen state
                                          to provide visual context to Gemini.
            application_context_description: Optional. A textual description of the application context.
            plan_generation_model_override: Optional. Specific Gemini model to use. If None,
                                            a powerful default (e.g., DEFAULT_STRATEGY_PLANNING_MODEL) is used.

        Returns:
            An IntermediatePlan (list of step dictionaries) if successful, otherwise None.
        """
        log_prefix = f"StrategyPlanner (Goal: '{user_goal[:70].replace(os.linesep, ' ')}...')"
        logger.info(f"{log_prefix}: Attempting to generate intermediate plan from user goal.")

        if not user_goal or not user_goal.strip():
            logger.error(f"{log_prefix}: User goal is empty. Cannot generate plan.")
            return None
        if not self.gemini_analyzer:
            logger.critical(f"{log_prefix}: GeminiAnalyzer is not available. Cannot generate plan.")
            return None

        prompt_for_plan = self._construct_goal_to_plan_prompt(user_goal, application_context_description)

        model_to_use = plan_generation_model_override if plan_generation_model_override else DEFAULT_STRATEGY_PLANNING_MODEL
        logger.info(f"{log_prefix}: Using Gemini model '{model_to_use}' for plan generation.")

        if initial_visual_context_image is None and ("vision" in model_to_use.lower() or "flash" in model_to_use.lower() or "pro" in model_to_use.lower() and "text" not in model_to_use.lower()):
            logger.debug(f"{log_prefix}: Using multimodal model '{model_to_use}' for planning, but no initial image was provided.")
        elif initial_visual_context_image is not None and not ("vision" in model_to_use.lower() or "flash" in model_to_use.lower() or "pro" in model_to_use.lower()):
            logger.warning(f"{log_prefix}: Initial image provided, but model '{model_to_use}' may be text-only. Visual context might not be used for planning.")

        gemini_api_response = self.gemini_analyzer.query_vision_model(prompt=prompt_for_plan, image_data=initial_visual_context_image, model_name_override=model_to_use)

        if gemini_api_response["status"] != "success" or not gemini_api_response["json_content"]:
            logger.error(
                f"{log_prefix}: Failed to get valid structured plan from Gemini. Status: {gemini_api_response['status']}. Error: {gemini_api_response.get('error_message', 'No JSON content')}"
            )
            if gemini_api_response.get("text_content"):
                logger.error(f"{log_prefix}: Gemini raw text response (on plan failure or non-JSON): {gemini_api_response['text_content'][:1000].replace(os.linesep, ' ')}")
            return None

        try:
            parsed_json_content = gemini_api_response["json_content"]
            if not isinstance(parsed_json_content, dict) or "intermediate_plan" not in parsed_json_content:
                logger.error(f"{log_prefix}: Gemini's plan response JSON missing 'intermediate_plan' key. Response: {parsed_json_content}")
                raise ValueError("Invalid plan structure from AI: 'intermediate_plan' key missing.")

            raw_plan_steps = parsed_json_content["intermediate_plan"]
            if not isinstance(raw_plan_steps, list):
                logger.error(f"{log_prefix}: 'intermediate_plan' value in Gemini's response is not a list. Value: {raw_plan_steps}")
                raise ValueError("'intermediate_plan' value from AI is not a list.")

            if not raw_plan_steps:  # Handles both empty list and explicit empty plan with reasoning
                reasoning = parsed_json_content.get("reasoning_for_empty_plan", "AI returned an empty plan without specific reasoning.")
                logger.warning(f"{log_prefix}: Gemini returned an empty plan. Reasoning: {reasoning}")
                return []

            validated_plan_steps: IntermediatePlan = []
            for idx, step_data_raw in enumerate(raw_plan_steps):
                if not isinstance(step_data_raw, dict):
                    logger.warning(f"{log_prefix}: Plan step at index {idx} is not a dictionary: {step_data_raw}. Skipping.")
                    continue

                step_id_val = step_data_raw.get("step_id")
                description_val = step_data_raw.get("description")
                final_step_id = idx + 1
                if isinstance(step_id_val, int) and step_id_val > 0:
                    final_step_id = step_id_val
                elif step_id_val is not None:
                    logger.warning(f"{log_prefix}: Step idx {idx} invalid 'step_id' ('{step_id_val}'). Using sequential {final_step_id}.")

                if not isinstance(description_val, str) or not description_val.strip():
                    logger.warning(f"{log_prefix}: Step ID {final_step_id} (idx {idx}) empty/invalid 'description'. Skipping critical step.")
                    continue

                type_hint_val = str(step_data_raw.get("suggested_element_type_hint", "")).strip()
                user_inputs_list_raw = step_data_raw.get("required_user_input_for_step", [])
                final_user_inputs: List[str] = [str(ui).strip() for ui in user_inputs_list_raw if isinstance(user_inputs_list_raw, list) and isinstance(ui, str) and str(ui).strip()]
                if not isinstance(user_inputs_list_raw, list) and user_inputs_list_raw is not None:
                    logger.warning(f"{log_prefix}: Step ID {final_step_id} 'required_user_input_for_step' not a list (type: {type(user_inputs_list_raw).__name__}). Ignoring.")

                validated_plan_steps.append(
                    {
                        "step_id": final_step_id,
                        "description": description_val.strip(),
                        "suggested_element_type_hint": type_hint_val if type_hint_val else None,
                        "required_user_input_for_step": final_user_inputs,
                    }
                )

            if not validated_plan_steps and raw_plan_steps:
                logger.error(f"{log_prefix}: Gemini generated steps, but none were valid after validation. Raw: {raw_plan_steps}")
                return None

            log_msg = (
                f"{log_prefix}: Successfully generated and validated intermediate plan with {len(validated_plan_steps)} steps."
                if validated_plan_steps
                else f"{log_prefix}: Gemini returned an empty plan or no valid steps."
            )
            logger.info(log_msg)
            if logger.isEnabledFor(logging.DEBUG) and validated_plan_steps:
                logger.debug(f"{log_prefix}: Generated plan details:\n{json.dumps(validated_plan_steps, indent=2)}")
            return validated_plan_steps

        except ValueError as e_val_parse:
            logger.error(f"{log_prefix}: Error validating Gemini's plan structure: {e_val_parse}. Raw JSON: {gemini_api_response.get('json_content')}", exc_info=False)
            return None
        except Exception as e_unexpected_processing:
            logger.error(f"{log_prefix}: Unexpected error processing Gemini's plan response: {e_unexpected_processing}. Raw JSON: {gemini_api_response.get('json_content')}", exc_info=True)
            return None
