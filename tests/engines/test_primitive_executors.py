import pytest
from unittest.mock import MagicMock, patch, call, create_autospec

import numpy as np

from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_analyzer import GeminiAnalyzer # For type hint
from mark_i.engines.primitive_executors import (
    ClickDescribedElementExecutor, TypeInDescribedFieldExecutor,
    PressKeySimpleExecutor, CheckVisualStateExecutor, PrimitiveSubActionExecuteResult
)

# --- Mock Fixtures ---
@pytest.fixture
def mock_action_executor():
    return create_autospec(ActionExecutor, instance=True)

@pytest.fixture
def mock_gemini_analyzer_for_primitives():
    ga_mock = create_autospec(GeminiAnalyzer, instance=True)
    ga_mock.client_initialized = True
    return ga_mock

@pytest.fixture
def mock_target_refiner():
    """Mocks the _refine_target_description_to_bbox function."""
    return MagicMock()

# Common dummy data for primitive executors
dummy_image_np = np.zeros((50,50,3), dtype=np.uint8)
dummy_context_images = {"primary_region": dummy_image_np}
dummy_task_params = {"pyautogui_pause_before": 0.05, "require_confirmation_per_step": False}


class TestClickDescribedElementExecutor:
    def test_execute_success(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_bbox_data = {
            "value": {"box": [10,10,20,20], "found": True, "element_label": "Login Button"},
            "_source_region_for_capture_": "primary_region"
        }
        mock_target_refiner.return_value = refined_bbox_data

        executor = ClickDescribedElementExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "Login Button", "parameters": {"button": "left"}}

        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")

        assert result.success is True
        mock_target_refiner.assert_called_once_with("Login Button", dummy_image_np, "primary_region", "TestRule_NLU")
        mock_action_executor.execute_action.assert_called_once()
        called_action_spec = mock_action_executor.execute_action.call_args[0][0]
        assert called_action_spec["type"] == "click"
        assert called_action_spec["target_relation"] == "center_of_gemini_element"
        assert "gemini_element_variable" in called_action_spec # Name is dynamic

    def test_execute_target_refinement_fails(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        mock_target_refiner.return_value = None # Simulate refinement failure
        executor = ClickDescribedElementExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "NonExistent Button"}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")
        assert result.success is False
        mock_action_executor.execute_action.assert_not_called()

    def test_execute_confirmation_declined(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_bbox_data = {"value": {"box": [10,10,20,20], "found": True}} # Simplified
        mock_target_refiner.return_value = refined_bbox_data
        task_params_confirm = {**dummy_task_params, "require_confirmation_per_step": True}

        executor = ClickDescribedElementExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        # Patch the executor's own confirmation helper to simulate "No"
        with patch.object(executor, '_confirm_action_if_needed', return_value=False) as mock_confirm:
            step_details = {"target_description": "Confirm Button"}
            result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", task_params_confirm, "LogPrefix")

            assert result.success is True # Step is "successful" as in no error, but action not performed
            mock_confirm.assert_called_once()
            mock_action_executor.execute_action.assert_not_called()


class TestTypeInDescribedFieldExecutor:
    def test_execute_success(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_field_data = {
            "value": {"box": [5,5,50,15], "found": True, "element_label": "Username Field"},
            "_source_region_for_capture_": "primary_region"
        }
        mock_target_refiner.return_value = refined_field_data
        executor = TypeInDescribedFieldExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "Username Field", "parameters": {"text_to_type": "testuser"}}

        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")

        assert result.success is True
        mock_target_refiner.assert_called_once_with("Username Field", dummy_image_np, "primary_region", "TestRule_NLU")
        # Expect two calls: one for click, one for type
        assert mock_action_executor.execute_action.call_count == 2
        click_call_args = mock_action_executor.execute_action.call_args_list[0][0][0]
        type_call_args = mock_action_executor.execute_action.call_args_list[1][0][0]
        assert click_call_args["type"] == "click"
        assert type_call_args["type"] == "type_text"
        assert type_call_args["text"] == "testuser"

class TestPressKeySimpleExecutor:
    def test_execute_success(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        executor = PressKeySimpleExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"key_name": "enter"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")
        assert result.success is True
        mock_action_executor.execute_action.assert_called_once()
        called_spec = mock_action_executor.execute_action.call_args[0][0]
        assert called_spec["type"] == "press_key"
        assert called_spec["key"] == "enter"

    def test_execute_missing_key_name(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        executor = PressKeySimpleExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {}} # Missing key_name
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")
        assert result.success is False
        mock_action_executor.execute_action.assert_not_called()

class TestCheckVisualStateExecutor:
    def test_execute_condition_true(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        mock_gemini_analyzer_for_primitives.query_vision_model.return_value = {
            "status": "success", "text_content": "true"
        }
        executor = CheckVisualStateExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"condition_description": "Is the light green?"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")
        assert result.success is True
        assert result.boolean_eval_result is True
        mock_gemini_analyzer_for_primitives.query_vision_model.assert_called_once()

    def test_execute_condition_false(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        mock_gemini_analyzer_for_primitives.query_vision_model.return_value = {
            "status": "success", "text_content": "false"
        }
        executor = CheckVisualStateExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"condition_description": "Is the light green?"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")
        assert result.success is True
        assert result.boolean_eval_result is False

    def test_execute_gemini_error(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        mock_gemini_analyzer_for_primitives.query_vision_model.return_value = {
            "status": "error_api", "error_message": "Some API error"
        }
        executor = CheckVisualStateExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"condition_description": "Is the light green?"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TestRule_NLU", dummy_task_params, "LogPrefix")
        assert result.success is False
        assert result.boolean_eval_result is False # Default on failure