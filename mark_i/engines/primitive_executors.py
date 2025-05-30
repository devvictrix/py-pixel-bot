import logging
import time
from typing import Dict, Any, Optional, Callable, Tuple

import numpy as np
import abc

from mark_i.engines.gemini_analyzer import GeminiAnalyzer, DEFAULT_VISUAL_REFINE_MODEL
from mark_i.engines.action_executor import ActionExecutor

# ConfigManager might be needed if an executor needs to resolve region configs, but refinement context comes from GDM

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.primitive_executors")


class PrimitiveSubActionExecuteResult:
    """Holds the result of a primitive sub-action execution."""

    def __init__(self, success: bool, boolean_eval_result: Optional[bool] = None):
        self.success = success  # True if the action execution was successful
        # For CHECK_VISUAL_STATE, this holds the boolean outcome of the check.
        # For other actions, it's typically None or not used.
        self.boolean_eval_result = boolean_eval_result


class PrimitiveSubActionExecutorBase(abc.ABC):
    """
    Abstract base class for executing a specific type of primitive sub-action
    derived from an NLU-parsed plan.
    """

    def __init__(
        self,
        action_executor_instance: ActionExecutor,
        gemini_analyzer_instance: GeminiAnalyzer,
        target_refiner_func: Callable[[str, np.ndarray, str, str], Optional[Dict[str, Any]]],
        # config_manager_instance: ConfigManager # If needed for region data access by an executor directly
    ):
        self.action_executor = action_executor_instance
        self.gemini_analyzer = gemini_analyzer_instance
        self._refine_target_description_to_bbox = target_refiner_func
        # self.config_manager = config_manager_instance

    @abc.abstractmethod
    def execute(
        self,
        step_instruction_details: Dict[str, Any],
        current_visual_context_images: Dict[str, np.ndarray],
        primary_context_region_name: str,
        task_rule_name_for_log: str,
        task_parameters_from_rule: Dict[str, Any],  # e.g., for pyautogui_pause_before, confirmation
        log_prefix_base: str,  # Base prefix for logging within the executor
    ) -> PrimitiveSubActionExecuteResult:
        """
        Executes the primitive sub-action.

        Args:
            step_instruction_details: Parsed details from NLU (intent_verb, target_description, parameters).
            current_visual_context_images: Dictionary of region_name to NumPy image data.
            primary_context_region_name: The main region for this step's visual context.
            task_rule_name_for_log: Name of the parent rule/task for logging.
            task_parameters_from_rule: Parameters from the `gemini_perform_task` action spec.
            log_prefix_base: Base logging prefix (e.g., "R 'RuleName', NLU SubStep").

        Returns:
            PrimitiveSubActionExecuteResult indicating success/failure and any boolean eval result.
        """
        pass

    def _confirm_action_if_needed(self, action_description_for_confirm: str, require_confirmation: bool, log_prefix: str) -> bool:
        """Handles user confirmation for an action if required."""
        if require_confirmation:
            # In a real GUI, this would show a dialog. For backend, simulate 'Yes'.
            logger.info(f"{log_prefix}: USER CONFIRMATION REQUIRED for: {action_description_for_confirm} (Simulating 'Yes' for backend execution)")
            # If a real confirmation mechanism existed:
            # confirmed = show_confirmation_dialog(action_description_for_confirm)
            # if not confirmed:
            #     logger.info(f"{log_prefix}: User declined action. Step skipped.")
            #     return False
            return True  # Simulate user confirmed
        return True  # No confirmation required


class ClickDescribedElementExecutor(PrimitiveSubActionExecutorBase):
    def execute(
        self, step_instruction_details: Dict, current_visual_context_images: Dict, primary_context_region_name: str, task_rule_name_for_log: str, task_parameters_from_rule: Dict, log_prefix_base: str
    ) -> PrimitiveSubActionExecuteResult:
        target_desc = step_instruction_details.get("target_description")
        params_from_nlu = step_instruction_details.get("parameters", {})
        log_prefix = f"{log_prefix_base} CLICK_DESCRIBED_ELEMENT"

        if not target_desc or not isinstance(target_desc, str):
            logger.error(f"{log_prefix}: 'target_description' missing or invalid: '{target_desc}'.")
            return PrimitiveSubActionExecuteResult(success=False)

        current_step_image_np = current_visual_context_images.get(primary_context_region_name)
        if current_step_image_np is None:
            logger.error(f"{log_prefix}: Primary context image for region '{primary_context_region_name}' is missing.")
            return PrimitiveSubActionExecuteResult(success=False)

        refined_target_data = self._refine_target_description_to_bbox(target_desc, current_step_image_np, primary_context_region_name, task_rule_name_for_log)
        if not refined_target_data:
            logger.error(f"{log_prefix}: Failed to refine target '{target_desc}'.")
            return PrimitiveSubActionExecuteResult(success=False)

        if not self._confirm_action_if_needed(f"Click on '{target_desc}'", task_parameters_from_rule.get("require_confirmation_per_step", True), log_prefix):
            return PrimitiveSubActionExecuteResult(success=True)  # User cancelled, but step itself didn't fail execution-wise

        temp_var_name = f"_nlu_click_target_{time.monotonic_ns()}"
        action_executor_spec = {
            "type": "click",
            "target_relation": "center_of_gemini_element",
            "gemini_element_variable": temp_var_name,
            "button": params_from_nlu.get("button", "left"),
            "clicks": int(params_from_nlu.get("clicks", 1)),
            "interval": float(params_from_nlu.get("interval", 0.0)),
            "pyautogui_pause_before": task_parameters_from_rule.get("pyautogui_pause_before", 0.1),
            "context": {
                "rule_name": f"{task_rule_name_for_log}_NLU_Click",
                "variables": {temp_var_name: refined_target_data},
                "condition_region": primary_context_region_name,
            },
        }
        try:
            loggable_spec = {k: v for k, v in action_executor_spec.items() if k != "context"}
            logger.info(f"{log_prefix}: Dispatching to ActionExecutor. Spec (params only): {loggable_spec}")
            self.action_executor.execute_action(action_executor_spec)
            logger.info(f"{log_prefix}: Click action on '{target_desc}' executed successfully.")
            return PrimitiveSubActionExecuteResult(success=True)
        except Exception as e_ae_exec:
            logger.error(f"{log_prefix}: Error during ActionExecutor execution for click: {e_ae_exec}", exc_info=True)
            return PrimitiveSubActionExecuteResult(success=False)


class TypeInDescribedFieldExecutor(PrimitiveSubActionExecutorBase):
    def execute(
        self, step_instruction_details: Dict, current_visual_context_images: Dict, primary_context_region_name: str, task_rule_name_for_log: str, task_parameters_from_rule: Dict, log_prefix_base: str
    ) -> PrimitiveSubActionExecuteResult:
        target_desc = step_instruction_details.get("target_description")
        params_from_nlu = step_instruction_details.get("parameters", {})
        text_to_type = params_from_nlu.get("text_to_type")
        log_prefix = f"{log_prefix_base} TYPE_IN_DESCRIBED_FIELD"

        if not target_desc or not isinstance(target_desc, str):
            logger.error(f"{log_prefix}: 'target_description' missing or invalid: '{target_desc}'.")
            return PrimitiveSubActionExecuteResult(success=False)
        if not isinstance(text_to_type, str):  # Empty string is allowed for typing
            logger.error(f"{log_prefix}: 'text_to_type' missing or invalid: '{text_to_type}'.")
            return PrimitiveSubActionExecuteResult(success=False)

        current_step_image_np = current_visual_context_images.get(primary_context_region_name)
        if current_step_image_np is None:
            logger.error(f"{log_prefix}: Primary context image for region '{primary_context_region_name}' is missing.")
            return PrimitiveSubActionExecuteResult(success=False)

        refined_field_data = self._refine_target_description_to_bbox(target_desc, current_step_image_np, primary_context_region_name, task_rule_name_for_log)
        if not refined_field_data:
            logger.error(f"{log_prefix}: Failed to refine field target '{target_desc}'.")
            return PrimitiveSubActionExecuteResult(success=False)

        if not self._confirm_action_if_needed(f"Type '{text_to_type[:30]}...' in '{target_desc}'", task_parameters_from_rule.get("require_confirmation_per_step", True), log_prefix):
            return PrimitiveSubActionExecuteResult(success=True)  # User cancelled

        # 1. Click the field
        click_var_name = f"_nlu_type_field_target_{time.monotonic_ns()}"
        click_spec = {
            "type": "click",
            "target_relation": "center_of_gemini_element",
            "gemini_element_variable": click_var_name,
            "button": "left",
            "clicks": 1,
            "pyautogui_pause_before": 0.15,  # Short pause before clicking field
            "context": {"rule_name": f"{task_rule_name_for_log}_NLU_ClickFieldForType", "variables": {click_var_name: refined_field_data}, "condition_region": primary_context_region_name},
        }
        try:
            logger.info(f"{log_prefix}: Executing pre-type click on field '{target_desc}'")
            self.action_executor.execute_action(click_spec)
            time.sleep(0.2)  # Small pause after click, before typing
        except Exception as e_click_field:
            logger.error(f"{log_prefix}: Failed to execute pre-type click on field '{target_desc}': {e_click_field}", exc_info=True)
            return PrimitiveSubActionExecuteResult(success=False)

        # 2. Type the text
        type_spec = {
            "type": "type_text",
            "text": text_to_type,
            "interval": float(params_from_nlu.get("typing_interval", 0.01)),
            "pyautogui_pause_before": task_parameters_from_rule.get("pyautogui_pause_before", 0.1),  # Pause from main task params
            "context": {"rule_name": f"{task_rule_name_for_log}_NLU_TypeText", "condition_region": primary_context_region_name},
        }
        try:
            loggable_spec = {k: v for k, v in type_spec.items() if k != "context"}
            logger.info(f"{log_prefix}: Dispatching type_text to ActionExecutor. Spec: {loggable_spec}")
            self.action_executor.execute_action(type_spec)
            logger.info(f"{log_prefix}: Type action in '{target_desc}' executed successfully.")
            return PrimitiveSubActionExecuteResult(success=True)
        except Exception as e_ae_exec:
            logger.error(f"{log_prefix}: Error during ActionExecutor execution for type_text: {e_ae_exec}", exc_info=True)
            return PrimitiveSubActionExecuteResult(success=False)


class PressKeySimpleExecutor(PrimitiveSubActionExecutorBase):
    def execute(
        self, step_instruction_details: Dict, current_visual_context_images: Dict, primary_context_region_name: str, task_rule_name_for_log: str, task_parameters_from_rule: Dict, log_prefix_base: str
    ) -> PrimitiveSubActionExecuteResult:
        params_from_nlu = step_instruction_details.get("parameters", {})
        key_name = params_from_nlu.get("key_name")
        log_prefix = f"{log_prefix_base} PRESS_KEY_SIMPLE"

        if not key_name or not isinstance(key_name, str):
            logger.error(f"{log_prefix}: 'key_name' missing or invalid: '{key_name}'.")
            return PrimitiveSubActionExecuteResult(success=False)

        if not self._confirm_action_if_needed(f"Press key '{key_name}'", task_parameters_from_rule.get("require_confirmation_per_step", True), log_prefix):
            return PrimitiveSubActionExecuteResult(success=True)  # User cancelled

        action_executor_spec = {
            "type": "press_key",
            "key": key_name,
            "pyautogui_pause_before": task_parameters_from_rule.get("pyautogui_pause_before", 0.1),
            "context": {"rule_name": f"{task_rule_name_for_log}_NLU_PressKey", "condition_region": primary_context_region_name},
        }
        try:
            loggable_spec = {k: v for k, v in action_executor_spec.items() if k != "context"}
            logger.info(f"{log_prefix}: Dispatching to ActionExecutor. Spec: {loggable_spec}")
            self.action_executor.execute_action(action_executor_spec)
            logger.info(f"{log_prefix}: Press key '{key_name}' executed successfully.")
            return PrimitiveSubActionExecuteResult(success=True)
        except Exception as e_ae_exec:
            logger.error(f"{log_prefix}: Error during ActionExecutor execution for press_key: {e_ae_exec}", exc_info=True)
            return PrimitiveSubActionExecuteResult(success=False)


class CheckVisualStateExecutor(PrimitiveSubActionExecutorBase):
    def execute(
        self, step_instruction_details: Dict, current_visual_context_images: Dict, primary_context_region_name: str, task_rule_name_for_log: str, task_parameters_from_rule: Dict, log_prefix_base: str
    ) -> PrimitiveSubActionExecuteResult:
        params_from_nlu = step_instruction_details.get("parameters", {})
        # NLU might put description in "target_description" or in params."condition_description"
        condition_desc = params_from_nlu.get("condition_description", step_instruction_details.get("target_description"))
        log_prefix = f"{log_prefix_base} CHECK_VISUAL_STATE"

        if not condition_desc or not isinstance(condition_desc, str):
            logger.error(f"{log_prefix}: 'condition_description' missing or invalid.")
            return PrimitiveSubActionExecuteResult(success=False, boolean_eval_result=False)

        current_step_image_np = current_visual_context_images.get(primary_context_region_name)
        if current_step_image_np is None:
            logger.error(f"{log_prefix}: Primary context image for region '{primary_context_region_name}' is missing.")
            return PrimitiveSubActionExecuteResult(success=False, boolean_eval_result=False)

        # No user confirmation for a check, it's an observation.
        check_prompt = f"Based on the provided image of region '{primary_context_region_name}', is the following condition true or false? Condition: \"{condition_desc}\". Respond with only the single word 'true' or 'false'."
        logger.info(f"{log_prefix}: Evaluating visual state: '{condition_desc}' in region '{primary_context_region_name}'")

        gemini_eval_response = self.gemini_analyzer.query_vision_model(
            prompt=check_prompt, image_data=current_step_image_np, model_name_override=task_parameters_from_rule.get("visual_refine_model_override", DEFAULT_VISUAL_REFINE_MODEL)
        )

        if gemini_eval_response["status"] == "success" and gemini_eval_response["text_content"]:
            response_text = gemini_eval_response["text_content"].strip().lower()
            if response_text == "true":
                logger.info(f"{log_prefix}: Visual state '{condition_desc}' evaluated to TRUE.")
                return PrimitiveSubActionExecuteResult(success=True, boolean_eval_result=True)
            elif response_text == "false":
                logger.info(f"{log_prefix}: Visual state '{condition_desc}' evaluated to FALSE.")
                return PrimitiveSubActionExecuteResult(success=True, boolean_eval_result=False)
            else:
                logger.warning(f"{log_prefix}: CHECK_VISUAL_STATE got ambiguous response: '{response_text}'. Interpreting as FALSE.")
                return PrimitiveSubActionExecuteResult(success=True, boolean_eval_result=False)  # Successful query, but condition false
        else:
            logger.error(f"{log_prefix}: CHECK_VISUAL_STATE query failed. Status: {gemini_eval_response['status']}, Error: {gemini_eval_response.get('error_message')}")
            return PrimitiveSubActionExecuteResult(success=False, boolean_eval_result=False)  # Query itself failed
