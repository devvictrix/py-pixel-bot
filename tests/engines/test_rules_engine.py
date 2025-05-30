import pytest
from unittest.mock import MagicMock, patch, create_autospec, call
import numpy as np  # For dummy_image_bgr

from mark_i.core.config_manager import ConfigManager
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.engines.gemini_decision_module import GeminiDecisionModule
from mark_i.engines.rules_engine import RulesEngine
from mark_i.engines.condition_evaluators import ConditionEvaluationResult, ConditionEvaluator


# --- Mock Fixtures ---
@pytest.fixture
def mock_config_manager_re():
    cm_mock = create_autospec(ConfigManager, instance=True)
    cm_mock.get_profile_data.return_value = {"settings": {"gemini_default_model_name": "test-model", "analysis_dominant_colors_k": 3}, "rules": []}
    cm_mock.get_setting.side_effect = lambda key, default: {"gemini_default_model_name": "test-model", "analysis_dominant_colors_k": 3}.get(key, default)
    cm_mock.get_profile_base_path.return_value = "/fake/profile/dir"
    return cm_mock


@pytest.fixture
def mock_analysis_engine_re():
    return create_autospec(AnalysisEngine, instance=True)


@pytest.fixture
def mock_action_executor_re():
    return create_autospec(ActionExecutor, instance=True)


@pytest.fixture
def mock_gemini_decision_module_re():
    gdm_mock = create_autospec(GeminiDecisionModule, instance=True)
    gdm_mock.gemini_analyzer = create_autospec(GeminiAnalyzer, instance=True)
    gdm_mock.gemini_analyzer.client_initialized = True
    return gdm_mock


@pytest.fixture
def rules_engine_instance_base(mock_config_manager_re, mock_analysis_engine_re, mock_action_executor_re, mock_gemini_decision_module_re):
    with patch("mark_i.engines.rules_engine.GeminiAnalyzer") as MockGAForRulesEngine:
        mock_ga_instance = MockGAForRulesEngine.return_value
        mock_ga_instance.client_initialized = True
        engine = RulesEngine(
            config_manager=mock_config_manager_re, analysis_engine=mock_analysis_engine_re, action_executor=mock_action_executor_re, gemini_decision_module=mock_gemini_decision_module_re
        )
        # Ensure the engine's internal gemini_analyzer_for_query is the mocked one
        engine.gemini_analyzer_for_query = mock_ga_instance  # This is important
        return engine


@pytest.fixture
def mock_condition_evaluator_always_true():
    eval_mock = create_autospec(ConditionEvaluator, instance=True)
    eval_mock.evaluate.return_value = ConditionEvaluationResult(met=True)
    return eval_mock


@pytest.fixture
def mock_condition_evaluator_always_false():
    eval_mock = create_autospec(ConditionEvaluator, instance=True)
    eval_mock.evaluate.return_value = ConditionEvaluationResult(met=False)
    return eval_mock


@pytest.fixture
def dummy_image_bgr() -> np.ndarray:
    """A dummy BGR image for context in tests like GDM action dispatch."""
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[:, :] = [128, 128, 128]  # Gray
    return img


class TestRulesEngineVariableSubstitution:
    def test_substitute_simple_variable(self, rules_engine_instance_base: RulesEngine):
        context = {"name": "Alice"}
        assert rules_engine_instance_base._substitute_variables("Hello {name}!", context, "TestSimple") == "Hello Alice!"

    def test_substitute_multiple_variables(self, rules_engine_instance_base: RulesEngine):
        context = {"item": "book", "count": 5}
        assert rules_engine_instance_base._substitute_variables("Item: {item}, Count: {count}", context, "TestMultiple") == "Item: book, Count: 5"

    def test_substitute_no_variables_in_string(self, rules_engine_instance_base: RulesEngine):
        context = {"name": "Alice"}
        assert rules_engine_instance_base._substitute_variables("Hello world!", context, "TestNoVars") == "Hello world!"

    def test_substitute_variable_not_in_context(self, rules_engine_instance_base: RulesEngine):
        context = {"name": "Alice"}
        assert rules_engine_instance_base._substitute_variables("Hello {user}!", context, "TestVarNotInCtx") == "Hello {user}!"

    def test_substitute_with_empty_context(self, rules_engine_instance_base: RulesEngine):
        assert rules_engine_instance_base._substitute_variables("Value: {value}", {}, "TestEmptyCtx") == "Value: {value}"

    def test_substitute_in_list(self, rules_engine_instance_base: RulesEngine):
        context = {"city": "London"}
        input_list = ["Hello", "from {city}", {"detail": "Weather in {city} is good."}]
        expected_list = ["Hello", "from London", {"detail": "Weather in London is good."}]
        assert rules_engine_instance_base._substitute_variables(input_list, context, "TestList") == expected_list

    def test_substitute_in_dict(self, rules_engine_instance_base: RulesEngine):
        context = {"user": "Bob", "status": "active"}
        input_dict = {"greeting": "Hi {user}", "info": {"current_status": "{status}", "details": ["{user} is {status}"]}}
        expected_dict = {"greeting": "Hi Bob", "info": {"current_status": "active", "details": ["Bob is active"]}}
        assert rules_engine_instance_base._substitute_variables(input_dict, context, "TestDict") == expected_dict

    def test_substitute_complex_nested_structure(self, rules_engine_instance_base: RulesEngine):
        context = {"event": "meeting", "time": "3 PM"}
        input_val = [{"type": "reminder", "message": "Event: {event} at {time}"}, "Static item", {"details": {"notes": "Remember the {event}."}}]
        expected_val = [{"type": "reminder", "message": "Event: meeting at 3 PM"}, "Static item", {"details": {"notes": "Remember the meeting."}}]
        assert rules_engine_instance_base._substitute_variables(input_val, context, "TestComplexNested") == expected_val

    def test_substitute_numeric_value_to_string(self, rules_engine_instance_base: RulesEngine):
        context = {"id": 123}
        assert rules_engine_instance_base._substitute_variables("ID: {id}", context, "TestNumeric") == "ID: 123"

    def test_substitute_more_complex_paths(self, rules_engine_instance_base: RulesEngine):
        context = {
            "data": {  # This is a wrapped value typically from Gemini or OCR capture
                "value": {"user_list": [{"name": "Alice", "id": 101}, {"name": "Bob", "id": 102}], "config": {"active": True, "retries": 3}},
                "_source_region_for_capture_": "main_area",  # Part of the wrapper
            },
            "status_code": 200,  # This is a simple value in context
        }
        # Accessing parts of the "value" inside "data"
        # Accessing a simple variable "status_code"
        assert (
            rules_engine_instance_base._substitute_variables(
                "User: {data.value.user_list.0.name}, ID: {data.value.user_list.0.id}, Active: {data.value.config.active}. Status: {status_code}", context, "TestComplexPaths"
            )
            == "User: Alice, ID: 101, Active: True. Status: 200"
        )

    def test_substitute_variable_value_is_none(self, rules_engine_instance_base: RulesEngine):
        context = {"optional_field": None}  # Simple None value
        assert rules_engine_instance_base._substitute_variables("Field: {optional_field}", context, "TestNoneVal") == "Field: None"

        # Test with a wrapped None, common for captures
        context_wrapped_none = {"optional_wrap": {"value": None, "_source_region_for_capture_": "src"}}
        assert rules_engine_instance_base._substitute_variables("Wrapped Field: {optional_wrap.value}", context_wrapped_none, "TestWrappedNoneVal") == "Wrapped Field: None"

    def test_substitute_path_leads_to_none_midway(self, rules_engine_instance_base: RulesEngine):
        context = {"data": {"value": {"user": None}}}  # user is None
        # Trying to access .name on a None object should fail gracefully and leave placeholder
        assert rules_engine_instance_base._substitute_variables("User Name: {data.value.user.name}", context, "TestPathToNone") == "User Name: {data.value.user.name}"

    def test_substitute_path_key_not_exist(self, rules_engine_instance_base: RulesEngine):
        context = {"data": {"value": {"user": {"id": 101}}}}  # No "name" key
        assert rules_engine_instance_base._substitute_variables("User Name: {data.value.user.name}", context, "TestPathKeyMissing") == "User Name: {data.value.user.name}"

    def test_substitute_path_index_out_of_bounds(self, rules_engine_instance_base: RulesEngine):
        context = {"data": {"value": {"user_list": [{"name": "Alice"}]}}}  # List has only one item at index 0
        assert rules_engine_instance_base._substitute_variables("User Name: {data.value.user_list.1.name}", context, "TestPathIndexOutOfBounds") == "User Name: {data.value.user_list.1.name}"


class TestRulesEngineCheckConditionEnhanced:
    def test_check_single_condition_region_not_found(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"type": "always_true", "region": "non_existent_region"}
        variable_context = {}
        # Provide data for default_rgn so it's not the cause of failure
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "default_rgn", {"default_rgn": {"image": MagicMock()}}, variable_context) is False

    def test_check_single_condition_evaluator_not_found(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"type": "unknown_type"}
        variable_context = {}
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "r1", {"r1": {"image": MagicMock()}}, variable_context) is False

    def test_check_compound_malformed_missing_operator(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"sub_conditions": [{"type": "always_true"}]}
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "r1", {"r1": {"image": MagicMock()}}, {}) is False

    def test_check_compound_malformed_empty_subconditions(self, rules_engine_instance_base: RulesEngine):
        condition_spec_and = {"logical_operator": "AND", "sub_conditions": []}
        # AND with no conditions should be True. If strict evaluation, this could be False.
        # Current RulesEngine logic (if !sub_conditions_list: return False) will make it False for both.
        assert rules_engine_instance_base._check_condition("TestANDEmpty", condition_spec_and, "r1", {"r1": {"image": MagicMock()}}, {}) is False

        condition_spec_or = {"logical_operator": "OR", "sub_conditions": []}
        assert rules_engine_instance_base._check_condition("TestOREmpty", condition_spec_or, "r1", {"r1": {"image": MagicMock()}}, {}) is False

    def test_check_compound_subcondition_region_not_found(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_true):
        rules_engine_instance_base._condition_evaluators["type_true"] = mock_condition_evaluator_always_true
        condition_spec = {"logical_operator": "AND", "sub_conditions": [{"type": "type_true", "region": "r1"}, {"type": "type_true", "region": "non_existent_sub_region"}]}
        # Ensure "r1" has data, but "non_existent_sub_region" does not
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "default_rgn", {"r1": {"image": MagicMock()}, "default_rgn": {"image": MagicMock()}}, {}) is False
        # The first sub-condition (on "r1") should have been evaluated.
        mock_condition_evaluator_always_true.evaluate.assert_called_once()


class TestRulesEngineEvaluateRules:
    def test_evaluate_rules_no_rules(self, rules_engine_instance_base: RulesEngine):
        rules_engine_instance_base.rules = []
        assert rules_engine_instance_base.evaluate_rules({}) == []

    def test_evaluate_rules_rule_condition_false(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_false, mock_action_executor_re):
        rules_engine_instance_base._condition_evaluators["type_false"] = mock_condition_evaluator_always_false
        rules_engine_instance_base.rules = [{"name": "TestFalseRule", "region": "r1", "condition": {"type": "type_false"}, "action": {"type": "log_message"}}]
        rules_engine_instance_base.evaluate_rules({"r1": {"image": MagicMock()}})
        mock_action_executor_re.execute_action.assert_not_called()

    def test_evaluate_rules_action_dispatch_standard(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_true, mock_action_executor_re):
        rules_engine_instance_base._condition_evaluators["type_true"] = mock_condition_evaluator_always_true
        action_spec = {"type": "click", "button": "left"}
        rules_engine_instance_base.rules = [{"name": "TestClickRule", "region": "r1", "condition": {"type": "type_true"}, "action": action_spec}]
        executed_actions = rules_engine_instance_base.evaluate_rules({"r1": {"image": MagicMock()}})
        mock_action_executor_re.execute_action.assert_called_once()
        call_args = mock_action_executor_re.execute_action.call_args[0][0]
        assert call_args["type"] == "click"
        assert call_args["context"]["rule_name"] == "TestClickRule"
        assert len(executed_actions) == 1
        assert executed_actions[0]["type"] == "click"

    def test_evaluate_rules_action_dispatch_gemini_task(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_true, mock_gemini_decision_module_re, dummy_image_bgr):
        rules_engine_instance_base._condition_evaluators["type_true"] = mock_condition_evaluator_always_true
        gdm_action_spec = {"type": "gemini_perform_task", "natural_language_command": "do stuff", "context_region_names": ["r1"]}
        rules_engine_instance_base.rules = [{"name": "TestGeminiTaskRule", "region": "r1", "condition": {"type": "type_true"}, "action": gdm_action_spec}]
        rules_engine_instance_base.evaluate_rules({"r1": {"image": dummy_image_bgr}})
        mock_gemini_decision_module_re.execute_nlu_task.assert_called_once()
        call_args_gdm = mock_gemini_decision_module_re.execute_nlu_task.call_args[1]  # kwargs
        assert call_args_gdm["natural_language_command"] == "do stuff"
        assert "r1" in call_args_gdm["initial_context_images"]
        assert call_args_gdm["initial_context_images"]["r1"] is dummy_image_bgr

    def test_evaluate_rules_invalid_rule_structure(self, rules_engine_instance_base: RulesEngine, mock_action_executor_re):
        rules_engine_instance_base.rules = [{"name": "MalformedRule"}]  # Missing condition/action
        rules_engine_instance_base.evaluate_rules({})
        mock_action_executor_re.execute_action.assert_not_called()
