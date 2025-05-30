import pytest
from unittest.mock import MagicMock, patch, create_autospec, call

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
    cm_mock.get_profile_data.return_value = {
        "settings": {"gemini_default_model_name": "test-model", "analysis_dominant_colors_k": 3},
        "rules": []
    }
    cm_mock.get_setting.side_effect = lambda key, default: \
        {"gemini_default_model_name": "test-model", "analysis_dominant_colors_k": 3}.get(key, default)
    # Mock get_profile_base_path for template loading
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
    """Base RulesEngine instance for further modification in tests."""
    with patch('mark_i.engines.rules_engine.GeminiAnalyzer') as MockGAForRulesEngine:
        mock_ga_instance = MockGAForRulesEngine.return_value
        mock_ga_instance.client_initialized = True
        engine = RulesEngine(
            config_manager=mock_config_manager_re,
            analysis_engine=mock_analysis_engine_re,
            action_executor=mock_action_executor_re,
            gemini_decision_module=mock_gemini_decision_module_re
        )
        engine.gemini_analyzer_for_query = mock_ga_instance
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


class TestRulesEngineVariableSubstitution:
    def test_substitute_more_complex_paths(self, rules_engine_instance_base: RulesEngine):
        context = {
            "data": {
                "value": {
                    "user_list": [{"name": "Alice", "id": 101}, {"name": "Bob", "id": 102}],
                    "config": {"active": True, "retries": 3}
                },
                "_source_region_for_capture_": "main_area"
            },
            "status_code": 200
        }
        assert rules_engine_instance_base._substitute_variables(
            "User: {data.value.user_list.0.name}, ID: {data.value.user_list.0.id}, Active: {data.value.config.active}. Status: {status_code}",
            context, "TestComplexPaths"
        ) == "User: Alice, ID: 101, Active: True. Status: 200"

    def test_substitute_variable_value_is_none(self, rules_engine_instance_base: RulesEngine):
        context = {"optional_field": None}
        assert rules_engine_instance_base._substitute_variables(
            "Field: {optional_field}", context, "TestNoneVal"
        ) == "Field: None"

        context_wrapped_none = {"optional_wrap": {"value": None, "_source_region_for_capture_": "src"}}
        assert rules_engine_instance_base._substitute_variables(
            "Wrapped Field: {optional_wrap.value}", context_wrapped_none, "TestWrappedNoneVal"
        ) == "Wrapped Field: None"

    def test_substitute_path_leads_to_none_midway(self, rules_engine_instance_base: RulesEngine):
        context = {"data": {"value": {"user": None}}} # user is None
        assert rules_engine_instance_base._substitute_variables(
            "User Name: {data.value.user.name}", context, "TestPathToNone"
        ) == "User Name: {data.value.user.name}" # Path fails, placeholder remains


class TestRulesEngineCheckConditionEnhanced:
    def test_check_single_condition_region_not_found(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"type": "always_true", "region": "non_existent_region"}
        variable_context = {}
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "default_rgn", {"default_rgn":{}}, variable_context) is False

    def test_check_single_condition_evaluator_not_found(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"type": "unknown_type"}
        variable_context = {}
        # No evaluator for "unknown_type" in rules_engine_instance._condition_evaluators by default
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "r1", {"r1":{}}, variable_context) is False

    def test_check_compound_malformed_missing_operator(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"sub_conditions": [{"type": "always_true"}]} # Missing logical_operator
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "r1", {"r1":{}}, {}) is False

    def test_check_compound_malformed_empty_subconditions(self, rules_engine_instance_base: RulesEngine):
        condition_spec = {"logical_operator": "AND", "sub_conditions": []} # Empty sub_conditions
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "r1", {"r1":{}}, {}) is False # AND with no subs is True, OR is False. Current impl makes it False.

    def test_check_compound_subcondition_region_not_found(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_true):
        rules_engine_instance_base._condition_evaluators["type_true"] = mock_condition_evaluator_always_true
        condition_spec = {
            "logical_operator": "AND",
            "sub_conditions": [
                {"type": "type_true", "region": "r1"},
                {"type": "type_true", "region": "non_existent_sub_region"} # This one will fail
            ]
        }
        assert rules_engine_instance_base._check_condition("TestRule", condition_spec, "default_rgn", {"r1":{}, "default_rgn":{}}, {}) is False
        # First sub-condition (r1) should be evaluated
        mock_condition_evaluator_always_true.evaluate.assert_called_once()


class TestRulesEngineEvaluateRules:
    def test_evaluate_rules_no_rules(self, rules_engine_instance_base: RulesEngine):
        rules_engine_instance_base.rules = [] # Ensure no rules
        assert rules_engine_instance_base.evaluate_rules({}) == []

    def test_evaluate_rules_rule_condition_false(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_false, mock_action_executor_re):
        rules_engine_instance_base._condition_evaluators["type_false"] = mock_condition_evaluator_always_false
        rules_engine_instance_base.rules = [{
            "name": "TestFalseRule", "condition": {"type": "type_false"}, "action": {"type": "log_message"}
        }]
        rules_engine_instance_base.evaluate_rules({"default_rgn":{}})
        mock_action_executor_re.execute_action.assert_not_called()

    def test_evaluate_rules_action_dispatch_standard(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_true, mock_action_executor_re):
        rules_engine_instance_base._condition_evaluators["type_true"] = mock_condition_evaluator_always_true
        action_spec = {"type": "click", "button": "left"}
        rules_engine_instance_base.rules = [{
            "name": "TestClickRule", "region": "r1", "condition": {"type": "type_true"}, "action": action_spec
        }]
        executed_actions = rules_engine_instance_base.evaluate_rules({"r1":{}})
        mock_action_executor_re.execute_action.assert_called_once()
        call_args = mock_action_executor_re.execute_action.call_args[0][0]
        assert call_args["type"] == "click"
        assert call_args["context"]["rule_name"] == "TestClickRule"
        assert executed_actions[0]["type"] == "click"

    def test_evaluate_rules_action_dispatch_gemini_task(self, rules_engine_instance_base: RulesEngine, mock_condition_evaluator_always_true, mock_gemini_decision_module_re):
        rules_engine_instance_base._condition_evaluators["type_true"] = mock_condition_evaluator_always_true
        gdm_action_spec = {"type": "gemini_perform_task", "natural_language_command": "do stuff", "context_region_names": ["r1"]}
        rules_engine_instance_base.rules = [{
            "name": "TestGeminiTaskRule", "region": "r1", "condition": {"type": "type_true"}, "action": gdm_action_spec
        }]
        rules_engine_instance_base.evaluate_rules({"r1":{"image": dummy_image_bgr}}) # GDM needs image data
        mock_gemini_decision_module_re.execute_nlu_task.assert_called_once()
        call_args_gdm = mock_gemini_decision_module_re.execute_nlu_task.call_args[1] # kwargs
        assert call_args_gdm["natural_language_command"] == "do stuff"
        assert "r1" in call_args_gdm["initial_context_images"]

    def test_evaluate_rules_invalid_rule_structure(self, rules_engine_instance_base: RulesEngine, mock_action_executor_re):
        rules_engine_instance_base.rules = [{"name": "MalformedRule"}] # Missing condition/action
        rules_engine_instance_base.evaluate_rules({})
        mock_action_executor_re.execute_action.assert_not_called()