import logging
import json
import time
from typing import Dict, Any, Optional, List, Tuple, Callable  # Added Callable
import os

import numpy as np

from mark_i.engines.gemini_analyzer import GeminiAnalyzer, DEFAULT_NLU_PLANNING_MODEL, DEFAULT_VISUAL_REFINE_MODEL
from mark_i.engines.action_executor import ActionExecutor
from mark_i.core.config_manager import ConfigManager

# Import new primitive executor classes
from mark_i.engines.primitive_executors import (
    PrimitiveSubActionExecutorBase,
    ClickDescribedElementExecutor,
    TypeInDescribedFieldExecutor,
    PressKeySimpleExecutor,
    CheckVisualStateExecutor,
    PrimitiveSubActionExecuteResult,
)

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_decision_module")

PREDEFINED_ALLOWED_SUB_ACTIONS: Dict[str, Dict[str, Any]] = {
    "CLICK_DESCRIBED_ELEMENT": {"description": "Clicks an element described textually.", "executor_class": ClickDescribedElementExecutor},
    "TYPE_IN_DESCRIBED_FIELD": {"description": "Types text into an element described textually.", "executor_class": TypeInDescribedFieldExecutor},
    "PRESS_KEY_SIMPLE": {"description": "Presses a single standard keyboard key.", "executor_class": PressKeySimpleExecutor},
    "CHECK_VISUAL_STATE": {"description": "Checks if a visual condition is met.", "executor_class": CheckVisualStateExecutor},
}


class GeminiDecisionModule:
    def __init__(
        self,
        gemini_analyzer: GeminiAnalyzer,
        action_executor: ActionExecutor,
        config_manager: ConfigManager,
    ):
        if not isinstance(gemini_analyzer, GeminiAnalyzer) or not gemini_analyzer.client_initialized:
            logger.critical("GDM CRITICAL: Invalid GeminiAnalyzer.")
            raise ValueError("Valid, initialized GeminiAnalyzer instance required for GeminiDecisionModule.")
        self.gemini_analyzer = gemini_analyzer

        if not isinstance(action_executor, ActionExecutor):
            logger.critical("GDM CRITICAL: Invalid ActionExecutor.")
            raise ValueError("ActionExecutor instance is required.")
        self.action_executor = action_executor

        if not isinstance(config_manager, ConfigManager):
            logger.critical("GDM CRITICAL: Invalid ConfigManager.")
            raise ValueError("ConfigManager instance is required.")
        self.config_manager = config_manager

        # Initialize primitive sub-action executors (Strategy Pattern)
        self._primitive_executors: Dict[str, PrimitiveSubActionExecutorBase] = self._initialize_primitive_executors()

        logger.info("GeminiDecisionModule (NLU Task Orchestrator & Goal Executor) initialized.")

    def _initialize_primitive_executors(self) -> Dict[str, PrimitiveSubActionExecutorBase]:
        """Initializes and returns a dictionary of primitive_action_type to executor instance."""
        executors: Dict[str, PrimitiveSubActionExecutorBase] = {}
        shared_dependencies = {
            "action_executor_instance": self.action_executor,
            "gemini_analyzer_instance": self.gemini_analyzer,
            "target_refiner_func": self._refine_target_description_to_bbox,  # Pass method reference
        }
        for action_type, meta in PREDEFINED_ALLOWED_SUB_ACTIONS.items():
            executor_class = meta.get("executor_class")
            if executor_class:
                try:
                    executors[action_type] = executor_class(**shared_dependencies)
                except Exception as e_init_exec:
                    logger.error(f"GDM: Failed to initialize primitive executor for '{action_type}': {e_init_exec}", exc_info=True)
            else:
                logger.warning(f"GDM: No executor_class defined for primitive action type '{action_type}' in PREDEFINED_ALLOWED_SUB_ACTIONS.")
        logger.debug(f"GDM: Initialized {len(executors)} primitive sub-action executors.")
        return executors

    def _construct_nlu_parse_prompt(self, natural_language_command: str) -> str:
        # Unchanged from previous version
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
}"""
        prompt = f'{nlu_schema_description}\n\nUser Command to Parse: "{natural_language_command}"\n\nProvide your parsed JSON output now, ensuring it is a single, valid JSON object starting with `{{` and ending with `}}`:'
        return prompt

    def _map_nlu_intent_to_allowed_sub_action(self, nlu_intent_verb: Optional[str]) -> Optional[str]:
        # Unchanged from previous version
        if not nlu_intent_verb or not isinstance(nlu_intent_verb, str):
            return None
        verb = nlu_intent_verb.strip().upper()
        if "CLICK" in verb or ("PRESS" in verb and "BUTTON" in verb) or "SELECT" in verb:
            return "CLICK_DESCRIBED_ELEMENT"
        if "TYPE" in verb or ("ENTER" in verb and "KEY" not in verb and "TEXT" in verb) or "FILL" in verb or "INPUT" in verb:
            return "TYPE_IN_DESCRIBED_FIELD"
        if ("PRESS" in verb and "KEY" in verb) or verb in ["HIT_ENTER", "SUBMIT_FORM_WITH_ENTER", "PRESS_ENTER", "PRESS_TAB", "PRESS_ESCAPE"]:
            return "PRESS_KEY_SIMPLE"
        if "CHECK" in verb or "VERIFY" in verb or "IS" in verb and ("VISIBLE" in verb or "PRESENT" in verb or "ENABLED" in verb or "DISABLED" in verb) or "IF" in verb and "STATE" in verb:
            return "CHECK_VISUAL_STATE"
        logger.warning(f"NLU Intent verb '{nlu_intent_verb}' (normalized to '{verb}') could not be mapped to a predefined sub-action type.")
        return None

    def _refine_target_description_to_bbox(self, target_description: str, context_image_np: np.ndarray, context_image_region_name: str, task_rule_name_for_log: str) -> Optional[Dict[str, Any]]:
        # Unchanged from previous version (this method is now passed to primitive executors)
        log_prefix = f"R '{task_rule_name_for_log}', NLU Task TargetRefine"
        logger.info(f"{log_prefix}: Refining target: '{target_description}' in rgn '{context_image_region_name}'")
        prompt = (
            f"Precise visual element locator. In the provided image of region '{context_image_region_name}', find the element best described as: \"{target_description}\".\n"
            f'If found, respond ONLY with JSON: {{"found": true, "box": [x,y,w,h], "element_label": "{target_description}", "confidence_score": 0.0_to_1.0}}. The box coordinates [x,y,w,h] must be integers relative to the top-left of the provided image. Ensure width and height are positive.\n'
            f'If not found or ambiguous, respond ONLY with JSON: {{"found": false, "box": null, "element_label": "{target_description}", "reasoning": "why_not_found_or_ambiguous"}}.'
        )
        response = self.gemini_analyzer.query_vision_model(prompt=prompt, image_data=context_image_np, model_name_override=DEFAULT_VISUAL_REFINE_MODEL)
        if response["status"] == "success" and response["json_content"]:
            data = response["json_content"]
            if isinstance(data, dict) and "found" in data:
                if (
                    data["found"]
                    and isinstance(data.get("box"), list)
                    and len(data["box"]) == 4
                    and all(isinstance(n, (int, float)) for n in data["box"])
                    and data["box"][2] > 0
                    and data["box"][3] > 0
                ):
                    box = [int(round(n)) for n in data["box"]]
                    logger.info(f"{log_prefix}: Target '{target_description}' refined to bbox: {box}. Confidence: {data.get('confidence_score', 'N/A')}")
                    return {
                        "value": {"box": box, "found": True, "element_label": data.get("element_label", target_description), "confidence": data.get("confidence_score", 1.0)},
                        "_source_region_for_capture_": context_image_region_name,
                    }
                elif not data["found"]:
                    logger.info(f"{log_prefix}: Target '{target_description}' not found by Gemini. Reasoning: {data.get('reasoning', 'N/A')}")
                else:
                    logger.warning(f"{log_prefix}: Refined box data for '{target_description}' invalid. Data: {data}")
            else:
                logger.warning(f"{log_prefix}: Refinement JSON structure unexpected: {data}")
        else:
            logger.error(f"{log_prefix}: Refinement query failed. Status: {response['status']}, Err: {response.get('error_message')}")
        return None

    def _execute_primitive_sub_action(
        self,
        step_instruction_details: Dict[str, Any],
        current_visual_context_images: Dict[str, np.ndarray],
        primary_context_region_name: str,
        task_rule_name_for_log: str,
        task_parameters_from_rule: Dict[str, Any],
    ) -> PrimitiveSubActionExecuteResult:
        """
        Delegates execution of a primitive sub-action to the appropriate executor
        based on the mapped NLU intent. (Refactored to use Strategy Pattern)
        """
        intent_verb = step_instruction_details.get("intent_verb")
        log_prefix_base = f"R '{task_rule_name_for_log}', NLU SubStep"
        logger.info(
            f"{log_prefix_base}: Executing primitive. Intent='{intent_verb}', TargetDesc='{step_instruction_details.get('target_description')}', NLU Params={step_instruction_details.get('parameters', {})}"
        )

        primitive_action_type = self._map_nlu_intent_to_allowed_sub_action(intent_verb)
        if not primitive_action_type:
            logger.error(f"{log_prefix_base}: Could not map NLU intent '{intent_verb}' to an allowed primitive sub-action. Step failed.")
            return PrimitiveSubActionExecuteResult(success=False, boolean_eval_result=False)

        executor = self._primitive_executors.get(primitive_action_type)
        if not executor:
            logger.error(f"{log_prefix_base}: No executor found for primitive action type '{primitive_action_type}'. Step failed.")
            return PrimitiveSubActionExecuteResult(success=False, boolean_eval_result=False)

        try:
            # Pass all necessary context to the specific executor's execute method
            result = executor.execute(
                step_instruction_details=step_instruction_details,
                current_visual_context_images=current_visual_context_images,
                primary_context_region_name=primary_context_region_name,
                task_rule_name_for_log=task_rule_name_for_log,
                task_parameters_from_rule=task_parameters_from_rule,
                log_prefix_base=log_prefix_base,
            )
            return result
        except Exception as e_exec_primitive:
            logger.error(f"{log_prefix_base}: Unexpected error during execution of primitive '{primitive_action_type}': {e_exec_primitive}", exc_info=True)
            return PrimitiveSubActionExecuteResult(success=False, boolean_eval_result=False)

    def execute_nlu_task(
        self,
        task_rule_name: str,
        natural_language_command: str,
        initial_context_images: Dict[str, np.ndarray],
        task_parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        # This method's core logic (NLU parsing, recursive plan execution) remains.
        # The key change is how _execute_primitive_sub_action is called.
        # The recursive helper `_recursive_execute_plan_node` will now use the refactored
        # `_execute_primitive_sub_action` which delegates to strategy executors.

        overall_task_result = {"status": "failure", "message": "NLU task initiated.", "executed_steps_summary": []}
        log_prefix_task = f"R '{task_rule_name}', NLU Task Cmd='{natural_language_command[:60].replace(os.linesep,' ')}...'"
        logger.info(f"{log_prefix_task}: Starting execution.")

        if not self.gemini_analyzer or not self.gemini_analyzer.client_initialized:
            overall_task_result["message"] = "GeminiAnalyzer not available."
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}")
            return overall_task_result

        nlu_parse_prompt = self._construct_nlu_parse_prompt(natural_language_command)
        nlu_context_image_for_parsing = next(iter(initial_context_images.values()), None) if initial_context_images else None
        nlu_response = self.gemini_analyzer.query_vision_model(
            prompt=nlu_parse_prompt, image_data=nlu_context_image_for_parsing, model_name_override=task_parameters.get("nlu_model_override", DEFAULT_NLU_PLANNING_MODEL)
        )

        if nlu_response["status"] != "success" or not nlu_response["json_content"]:
            overall_task_result["message"] = f"NLU parsing query failed. Status: {nlu_response['status']}, Err: {nlu_response.get('error_message', 'No JSON')}"
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}. Raw NLU Response Text: {nlu_response.get('text_content')}")
            return overall_task_result

        parsed_task_plan_from_nlu: Optional[Dict[str, Any]] = None
        try:
            json_response_content = nlu_response["json_content"]
            if not isinstance(json_response_content, dict) or "parsed_task" not in json_response_content:
                raise ValueError("NLU JSON missing 'parsed_task'")
            parsed_task_plan_from_nlu = json_response_content["parsed_task"]
            if not isinstance(parsed_task_plan_from_nlu, dict):
                raise ValueError("'parsed_task' not a dict.")
            logger.info(f"{log_prefix_task}: NLU parsed. Plan Type: {parsed_task_plan_from_nlu.get('command_type')}")
            logger.debug(f"{log_prefix_task}: Full NLU parsed plan: {json.dumps(parsed_task_plan_from_nlu, indent=2)}")
        except Exception as e_nlu_parse:
            overall_task_result["message"] = f"Error processing NLU JSON: {e_nlu_parse}. Resp: {nlu_response['json_content']}"
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}", exc_info=True)
            return overall_task_result

        current_visual_context_for_steps = initial_context_images
        primary_context_region_name_for_steps = ""
        if task_parameters.get("context_region_names") and isinstance(task_parameters["context_region_names"], list) and task_parameters["context_region_names"]:
            primary_context_region_name_for_steps = task_parameters["context_region_names"][0]
            if primary_context_region_name_for_steps not in current_visual_context_for_steps:
                logger.warning(f"{log_prefix_task}: Specified primary context region '{primary_context_region_name_for_steps}' not in images. Will try first available.")
                primary_context_region_name_for_steps = ""
        if not primary_context_region_name_for_steps and current_visual_context_for_steps:
            primary_context_region_name_for_steps = list(current_visual_context_for_steps.keys())[0]
        if not primary_context_region_name_for_steps:
            overall_task_result["message"] = "NLU Task: No primary context region image available."
            logger.error(f"{log_prefix_task}: {overall_task_result['message']}")
            return overall_task_result
        logger.info(f"{log_prefix_task}: Primary context region for steps: '{primary_context_region_name_for_steps}'.")

        executed_steps_log: List[str] = []

        # Inner recursive helper for plan execution
        def _recursive_execute_plan_node(plan_node_data: Dict[str, Any], current_images: Dict[str, np.ndarray], primary_rgn_name: str, depth: int = 0, branch_prefix: str = "") -> bool:
            if depth > task_parameters.get("max_recursion_depth_nlu", 5):
                logger.error(f"{log_prefix_task}: Max recursion depth ({depth}) reached: {branch_prefix}")
                executed_steps_log.append(f"Error: Max recursion at {branch_prefix}")
                return False
            node_type = plan_node_data.get("command_type")
            node_log_id = f"{branch_prefix}Type'{node_type}'"
            logger.debug(f"{log_prefix_task}: Recursive exec {node_log_id} depth {depth}.")

            if node_type == "SINGLE_INSTRUCTION":
                instr_details = plan_node_data.get("instruction_details")
                if isinstance(instr_details, dict):
                    # Call to the refactored method
                    exec_result = self._execute_primitive_sub_action(instr_details, current_images, primary_rgn_name, f"{task_rule_name}_{branch_prefix}Single", task_parameters)
                    executed_steps_log.append(f"{branch_prefix}Single '{instr_details.get('intent_verb')}': {'OK' if exec_result.success else 'FAIL'}")
                    return exec_result.success
                else:
                    logger.error(f"{log_prefix_task}: {node_log_id} missing 'instruction_details'.")
                    executed_steps_log.append(f"{branch_prefix}Single: FormatFAIL")
                    return False
            elif node_type == "SEQUENTIAL_INSTRUCTIONS":
                steps_list = plan_node_data.get("steps", [])
                if not isinstance(steps_list, list) or not steps_list:
                    logger.error(f"{log_prefix_task}: {node_log_id} missing 'steps'.")
                    executed_steps_log.append(f"{branch_prefix}Sequence: FormatFAIL")
                    return False
                max_s = task_parameters.get("max_steps", len(steps_list))
                for i, step_item_data in enumerate(steps_list):
                    if i >= max_s:
                        logger.info(f"{log_prefix_task}: {node_log_id} reached max_steps ({max_s}).")
                        break
                    if not isinstance(step_item_data, dict) or "instruction_details" not in step_item_data:
                        logger.error(f"{log_prefix_task}: {node_log_id} invalid step data at {i}: {step_item_data}.")
                        executed_steps_log.append(f"{branch_prefix}SeqStep{i+1}: FormatFAIL")
                        return False
                    instr_details = step_item_data["instruction_details"]
                    step_num = step_item_data.get("step_number", i + 1)
                    logger.info(
                        f"{log_prefix_task}: {branch_prefix}SeqStep {step_num}/{len(steps_list)}: Intent='{instr_details.get('intent_verb')}' Target='{instr_details.get('target_description')}'"
                    )
                    current_images_for_step = current_images  # TODO: Context refresh logic for sequential steps
                    # Call to the refactored method
                    exec_result = self._execute_primitive_sub_action(instr_details, current_images_for_step, primary_rgn_name, f"{task_rule_name}_{branch_prefix}SeqStep{step_num}", task_parameters)
                    executed_steps_log.append(f"{branch_prefix}SeqStep{step_num} '{instr_details.get('intent_verb')}': {'OK' if exec_result.success else 'FAIL'}")
                    if not exec_result.success:
                        return False
                    time.sleep(float(task_parameters.get("delay_between_nlu_steps_sec", 0.3)))
                return True
            elif node_type == "CONDITIONAL_INSTRUCTION":
                cond_desc = plan_node_data.get("condition_description")
                then_plan_node = plan_node_data.get("then_branch")
                else_plan_node = plan_node_data.get("else_branch")
                if not cond_desc or not isinstance(then_plan_node, dict):
                    logger.error(f"{log_prefix_task}: {node_log_id} missing 'condition_description' or 'then_branch'.")
                    executed_steps_log.append(f"{branch_prefix}Condition: FormatFAIL")
                    return False
                eval_instr = {"intent_verb": "CHECK_VISUAL_STATE", "target_description": cond_desc, "parameters": {"condition_description": cond_desc}}
                logger.info(f"{log_prefix_task}: {branch_prefix}Evaluating IF: '{cond_desc}'")
                # Call to the refactored method
                condition_exec_result = self._execute_primitive_sub_action(eval_instr, current_images, primary_rgn_name, f"{task_rule_name}_{branch_prefix}IF_Check", task_parameters)
                condition_met_bool = condition_exec_result.boolean_eval_result if condition_exec_result.success else False
                executed_steps_log.append(f"{branch_prefix}IF '{cond_desc}': {'TRUE' if condition_met_bool else 'FALSE'} (ExecSuccess: {condition_exec_result.success})")
                if not condition_exec_result.success:
                    return False  # If the check itself failed, abort conditional
                target_branch_plan = None
                new_branch_prefix_for_log = ""
                if condition_met_bool:
                    logger.info(f"{log_prefix_task}: {branch_prefix}IF TRUE. Executing THEN.")
                    target_branch_plan = then_plan_node
                    new_branch_prefix_for_log = f"{branch_prefix}THEN."
                elif isinstance(else_plan_node, dict):
                    logger.info(f"{log_prefix_task}: {branch_prefix}IF FALSE. Executing ELSE.")
                    target_branch_plan = else_plan_node
                    new_branch_prefix_for_log = f"{branch_prefix}ELSE."
                else:
                    logger.info(f"{log_prefix_task}: {branch_prefix}IF FALSE. No ELSE. Conditional complete.")
                    return True
                if target_branch_plan:
                    return _recursive_execute_plan_node(target_branch_plan, current_images, primary_rgn_name, depth + 1, new_branch_prefix_for_log)
                return True  # No branch to execute or branch executed successfully
            else:
                logger.error(f"{log_prefix_task}: {node_log_id} Unknown 'command_type'.")
                executed_steps_log.append(f"{branch_prefix}UnknownTypeFAIL")
                return False

        final_success = _recursive_execute_plan_node(parsed_task_plan_from_nlu, current_visual_context_for_steps, primary_context_region_name_for_steps)
        overall_task_result["status"] = "success" if final_success else "failure"
        overall_task_result["message"] = (
            "NLU task executed all steps successfully."
            if final_success
            else (overall_task_result.get("message") if overall_task_result.get("message") != "NLU task initiated." else "NLU task failed at one or more steps.")
        )
        overall_task_result["executed_steps_summary"] = executed_steps_log
        logger.info(f"{log_prefix_task}: Final NLU task status: {overall_task_result['status']}. Msg: {overall_task_result['message']}")
        logger.debug(f"{log_prefix_task}: Executed steps log: {executed_steps_log}")
        return overall_task_result
