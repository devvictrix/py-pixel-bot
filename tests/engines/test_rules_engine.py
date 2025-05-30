import pytest
from unittest.mock import MagicMock, patch, create_autospec, call

from mark_i.core.config_manager import ConfigManager
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.engines.gemini_decision_module import GeminiDecisionModule
from mark_i.engines.rules_engine import RulesEngine
from mark_i.engines.condition_evaluators import ConditionEvaluationResult  # For mocking


# --- Mock Fixtures ---
@pytest.fixture
def mock_config_manager_re():  # RE for RulesEngine
    cm_mock = create_autospec(ConfigManager, instance=True)
    # Default profile data structure for RulesEngine init
    cm_mock.get_profile_data.return_value = {"settings": {"gemini_default_model_name": "test-model"}, "rules": []}  # Start with no rules for some tests
    cm_mock.get_setting.side_effect = lambda key, default: {"gemini_default_model_name": "test-model"}.get(key, default)
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
    # Simulate GDM having its own initialized GA for tests that might reach it
    gdm_mock.gemini_analyzer = create_autospec(GeminiAnalyzer, instance=True)
    gdm_mock.gemini_analyzer.client_initialized = True
    return gdm_mock


@pytest.fixture
def rules_engine_instance(mock_config_manager_re, mock_analysis_engine_re, mock_action_executor_re, mock_gemini_decision_module_re):
    # Patch GeminiAnalyzer used by RulesEngine for its own query conditions
    with patch("mark_i.engines.rules_engine.GeminiAnalyzer") as MockGAForRulesEngine:
        mock_ga_instance = MockGAForRulesEngine.return_value
        mock_ga_instance.client_initialized = True  # Assume successful init
        engine = RulesEngine(
            config_manager=mock_config_manager_re, analysis_engine=mock_analysis_engine_re, action_executor=mock_action_executor_re, gemini_decision_module=mock_gemini_decision_module_re
        )
        # Allow access to the mocked GA instance if needed by specific tests
        engine.gemini_analyzer_for_query = mock_ga_instance
        return engine


class TestRulesEngineVariableSubstitution:
    def test_substitute_simple_variable(self, rules_engine_instance: RulesEngine):
        context = {"name": "PixelBot"}
        assert rules_engine_instance._substitute_variables("Hello {name}!", context, "TestRule") == "Hello PixelBot!"

    def test_substitute_nested_variable_dict(self, rules_engine_instance: RulesEngine):
        # Variables captured from Gemini or complex conditions are wrapped
        context = {"user": {"value": {"firstName": "Ada", "lastName": "Lovelace"}, "_source_region_for_capture_": "screen"}}
        assert rules_engine_instance._substitute_variables("User: {user.value.firstName} {user.value.lastName}", context, "TestRule") == "User: Ada Lovelace"

    def test_substitute_nested_variable_list(self, rules_engine_instance: RulesEngine):
        context = {"items": {"value": ["apple", "banana"], "_source_region_for_capture_": "list_area"}}
        assert rules_engine_instance._substitute_variables("Fruit: {items.value.0}", context, "TestRule") == "Fruit: apple"

    def test_substitute_variable_not_found(self, rules_engine_instance: RulesEngine):
        context = {"name": "PixelBot"}
        assert rules_engine_instance._substitute_variables("Hello {missing_var}!", context, "TestRule") == "Hello {missing_var}!"

    def test_substitute_invalid_path(self, rules_engine_instance: RulesEngine):
        context = {"user": {"value": {"firstName": "Ada"}}}
        assert rules_engine_instance._substitute_variables("Name: {user.value.nonexistent.key}", context, "TestRule") == "Name: {user.value.nonexistent.key}"

    def test_substitute_in_list_and_dict(self, rules_engine_instance: RulesEngine):
        context = {"city": "London", "count": 5}
        data_structure = {"message": "Report for {city}", "details": ["Item count: {count}", "Status: OK"]}
        expected = {"message": "Report for London", "details": ["Item count: 5", "Status: OK"]}
        assert rules_engine_instance._substitute_variables(data_structure, context, "TestRule") == expected

    def test_substitute_no_variables_in_string(self, rules_engine_instance: RulesEngine):
        context = {"name": "Test"}
        assert rules_engine_instance._substitute_variables("Just a plain string.", context, "TestRule") == "Just a plain string."

    def test_substitute_value_is_not_dict_with_value_key(self, rules_engine_instance: RulesEngine):
        context = {"simple_var": "CapturedDirectly"}
        assert rules_engine_instance._substitute_variables("Value: {simple_var}", context, "TestRule") == "Value: CapturedDirectly"


class TestRulesEngineCheckCondition:
    def test_check_single_condition_met(self, rules_engine_instance: RulesEngine, mock_analysis_engine_re):
        # Mock the specific evaluator that will be called
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = ConditionEvaluationResult(met=True)
        rules_engine_instance._condition_evaluators["always_true"] = mock_evaluator  # type: ignore

        condition_spec = {"type": "always_true"}
        variable_context = {}
        assert rules_engine_instance._check_condition("TestRule", condition_spec, "region1", {"region1": {}}, variable_context) is True
        mock_evaluator.evaluate.assert_called_once()

    def test_check_compound_condition_and_all_met(self, rules_engine_instance: RulesEngine):
        mock_eval_true = MagicMock()
        mock_eval_true.evaluate.return_value = ConditionEvaluationResult(met=True)
        rules_engine_instance._condition_evaluators["always_true"] = mock_eval_true  # type: ignore

        condition_spec = {"logical_operator": "AND", "sub_conditions": [{"type": "always_true"}, {"type": "always_true"}]}
        variable_context = {}
        assert rules_engine_instance._check_condition("TestRule", condition_spec, "r1", {"r1": {}}, variable_context) is True
        assert mock_eval_true.evaluate.call_count == 2

    def test_check_compound_condition_and_one_fails(self, rules_engine_instance: RulesEngine):
        mock_eval_true = MagicMock()
        mock_eval_true.evaluate.return_value = ConditionEvaluationResult(met=True)
        mock_eval_false = MagicMock()
        mock_eval_false.evaluate.return_value = ConditionEvaluationResult(met=False)

        rules_engine_instance._condition_evaluators["type_true"] = mock_eval_true  # type: ignore
        rules_engine_instance._condition_evaluators["type_false"] = mock_eval_false  # type: ignore

        condition_spec = {"logical_operator": "AND", "sub_conditions": [{"type": "type_true"}, {"type": "type_false"}]}
        variable_context = {}
        assert rules_engine_instance._check_condition("TestRule", condition_spec, "r1", {"r1": {}}, variable_context) is False
        # True one called, False one called, then short-circuited
        mock_eval_true.evaluate.assert_called_once()
        mock_eval_false.evaluate.assert_called_once()

    def test_check_compound_condition_or_one_met(self, rules_engine_instance: RulesEngine):
        mock_eval_true = MagicMock()
        mock_eval_true.evaluate.return_value = ConditionEvaluationResult(met=True)
        mock_eval_false = MagicMock()
        mock_eval_false.evaluate.return_value = ConditionEvaluationResult(met=False)
        rules_engine_instance._condition_evaluators["type_true"] = mock_eval_true  # type: ignore
        rules_engine_instance._condition_evaluators["type_false"] = mock_eval_false  # type: ignore

        condition_spec = {"logical_operator": "OR", "sub_conditions": [{"type": "type_false"}, {"type": "type_true"}]}
        variable_context = {}
        assert rules_engine_instance._check_condition("TestRule", condition_spec, "r1", {"r1": {}}, variable_context) is True
        mock_eval_false.evaluate.assert_called_once()
        mock_eval_true.evaluate.assert_called_once()  # OR needs to check until one is true

    def test_check_condition_variable_capture(self, rules_engine_instance: RulesEngine):
        captured_data = {"some_key": "some_value"}
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = ConditionEvaluationResult(met=True, captured_value=captured_data)
        rules_engine_instance._condition_evaluators["type_capture"] = mock_evaluator  # type: ignore

        condition_spec = {"type": "type_capture", "capture_as": "my_var"}
        variable_context = {}
        rules_engine_instance._check_condition("TestRule", condition_spec, "r1", {"r1": {}}, variable_context)
        assert "my_var" in variable_context
        assert variable_context["my_var"] == captured_data


# More tests for evaluate_rules (overall flow, action dispatching) would go here,
# likely involving more complex mocking of what _check_condition returns and
# verifying calls to ActionExecutor or GeminiDecisionModule.
# For v5.0.2 initial coverage, focusing on the refactored helpers is a good start.
