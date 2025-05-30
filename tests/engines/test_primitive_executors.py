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
    return MagicMock()

# Common dummy data for primitive executors
dummy_image_np = np.zeros((50,50,3), dtype=np.uint8)
dummy_context_images = {"primary_region": dummy_image_np}
dummy_task_params_no_confirm = {"pyautogui_pause_before": 0.05, "require_confirmation_per_step": False}
dummy_task_params_with_confirm = {"pyautogui_pause_before": 0.05, "require_confirmation_per_step": True}


class TestClickDescribedElementExecutor:
    def test_execute_success_no_confirm(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_bbox_data = {"value": {"box": [10,10,20,20], "found": True, "element_label": "Login Btn"}}
        mock_target_refiner.return_value = refined_bbox_data
        executor = ClickDescribedElementExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "Login Btn", "parameters": {"button": "left"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is True
        mock_action_executor.execute_action.assert_called_once()

    def test_execute_missing_target_description(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        executor = ClickDescribedElementExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {}} # Missing target_description
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is False
        mock_target_refiner.assert_not_called()
        mock_action_executor.execute_action.assert_not_called()

    def test_execute_primary_context_image_missing(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        executor = ClickDescribedElementExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "Login Button"}
        result = executor.execute(step_details, {}, "primary_region", "TR", dummy_task_params_no_confirm, "LP") # Empty context_images
        assert result.success is False
        mock_target_refiner.assert_not_called()


class TestTypeInDescribedFieldExecutor:
    def test_execute_success_no_confirm(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_field_data = {"value": {"box": [5,5,50,15], "found": True, "element_label": "User Field"}}
        mock_target_refiner.return_value = refined_field_data
        executor = TypeInDescribedFieldExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "User Field", "parameters": {"text_to_type": "test"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is True
        assert mock_action_executor.execute_action.call_count == 2 # Click then Type

    def test_execute_missing_text_to_type(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_field_data = {"value": {"box": [5,5,50,15], "found": True}}
        mock_target_refiner.return_value = refined_field_data # Refinement would succeed
        executor = TypeInDescribedFieldExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "User Field", "parameters": {}} # Missing text_to_type
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is False
        mock_action_executor.execute_action.assert_not_called() # Should fail before click/type

    def test_execute_click_field_fails(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        refined_field_data = {"value": {"box": [5,5,50,15], "found": True}}
        mock_target_refiner.return_value = refined_field_data
        mock_action_executor.execute_action.side_effect = [Exception("AE Click Failed"), None] # First call (click) fails
        executor = TypeInDescribedFieldExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"target_description": "User Field", "parameters": {"text_to_type": "test"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is False
        mock_action_executor.execute_action.assert_called_once() # Only click was attempted


class TestPressKeySimpleExecutor:
    def test_execute_invalid_key_name_type(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        executor = PressKeySimpleExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"key_name": 123}} # Invalid type for key_name
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is False
        mock_action_executor.execute_action.assert_not_called()


class TestCheckVisualStateExecutor:
    def test_execute_missing_condition_description(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        executor = CheckVisualStateExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {}} # Missing condition_description
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is False
        assert result.boolean_eval_result is False
        mock_gemini_analyzer_for_primitives.query_vision_model.assert_not_called()

    def test_execute_gemini_returns_no_text(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        mock_gemini_analyzer_for_primitives.query_vision_model.return_value = {"status": "success", "text_content": None}
        executor = CheckVisualStateExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"condition_description": "Is it green?"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is False # If text is None, it's treated as eval failure
        assert result.boolean_eval_result is False

    def test_execute_gemini_returns_ambiguous_text(self, mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner):
        mock_gemini_analyzer_for_primitives.query_vision_model.return_value = {"status": "success", "text_content": "Maybe"}
        executor = CheckVisualStateExecutor(mock_action_executor, mock_gemini_analyzer_for_primitives, mock_target_refiner)
        step_details = {"parameters": {"condition_description": "Is it green?"}}
        result = executor.execute(step_details, dummy_context_images, "primary_region", "TR", dummy_task_params_no_confirm, "LP")
        assert result.success is True # Query was successful
        assert result.boolean_eval_result is False # Ambiguous text defaults to False