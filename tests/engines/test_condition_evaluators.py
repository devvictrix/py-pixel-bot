// File: tests/engines/test_condition_evaluators.py
import pytest
from unittest.mock import MagicMock, patch, create_autospec

import numpy as np

from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.engines.condition_evaluators import (
    PixelColorEvaluator, AverageColorEvaluator, TemplateMatchEvaluator,
    OcrContainsTextEvaluator, DominantColorEvaluator, GeminiVisionQueryEvaluator,
    AlwaysTrueEvaluator, ConditionEvaluationResult
)

# --- Mock Fixtures ---
@pytest.fixture
def mock_analysis_engine():
    """Provides a MagicMock for AnalysisEngine."""
    return create_autospec(AnalysisEngine, instance=True)

@pytest.fixture
def mock_gemini_analyzer():
    """Provides a MagicMock for GeminiAnalyzer."""
    mock_ga = create_autospec(GeminiAnalyzer, instance=True)
    mock_ga.client_initialized = True # Assume initialized for tests that use it
    return mock_ga

@pytest.fixture
def mock_template_loader():
    """Provides a MagicMock for the template_loader_func."""
    return MagicMock()

@pytest.fixture
def mock_config_settings_getter():
    """Provides a MagicMock for the config_settings_getter_func."""
    # Default behavior: return a default value if key not specifically set
    def getter(key, default_val):
        if key == "analysis_dominant_colors_k": return 3 # Common setting
        return default_val
    return MagicMock(side_effect=getter)

# Common dummy data
dummy_image_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
dummy_region_data_packet_with_image = {"image": dummy_image_bgr}
dummy_region_data_packet_no_image = {"image": None}

# --- Test Classes for each Evaluator ---

class TestPixelColorEvaluator:
    def test_evaluate_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.analyze_pixel_color.return_value = True
        evaluator = PixelColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"relative_x": 10, "relative_y": 10, "expected_bgr": [0,0,0], "tolerance": 0}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        assert result.captured_value is None
        mock_analysis_engine.analyze_pixel_color.assert_called_once_with(
            dummy_image_bgr, 10, 10, [0,0,0], 0, region_name_context="test_rule/test_rgn"
        )

    def test_evaluate_no_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.analyze_pixel_color.return_value = False
        evaluator = PixelColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"relative_x": 10, "relative_y": 10, "expected_bgr": [255,255,255], "tolerance": 5}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False

    def test_evaluate_no_image(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = PixelColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"relative_x": 10, "relative_y": 10, "expected_bgr": [0,0,0]}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_no_image, "test_rule")
        assert result.met is False
        mock_analysis_engine.analyze_pixel_color.assert_not_called()


class TestAverageColorEvaluator:
    def test_evaluate_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        # Simulate AnalysisEngine returning an average color that matches criteria
        mock_analysis_engine.analyze_average_color.return_value = [50, 60, 70] # Actual avg color
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [55, 65, 75], "tolerance": 10}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        mock_analysis_engine.analyze_average_color.assert_called_once_with(dummy_image_bgr, "test_rule/test_rgn")


    def test_evaluate_no_match_due_to_color(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.analyze_average_color.return_value = [100, 100, 100]
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [50, 50, 50], "tolerance": 5}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False

    def test_evaluate_no_image(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [50, 50, 50]}
        # Make on-demand analysis return None if image is None
        mock_analysis_engine.analyze_average_color.return_value = None
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_no_image, "test_rule")
        assert result.met is False
        # It would call _get_pre_analyzed_data, which would call analyze_average_color with None image
        mock_analysis_engine.analyze_average_color.assert_called_once_with(None, "test_rule/test_rgn")


class TestTemplateMatchEvaluator:
    def test_evaluate_match_and_capture(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        match_details = {"location_x": 10, "location_y": 20, "confidence": 0.9, "width": 5, "height": 5}
        mock_analysis_engine.match_template.return_value = match_details
        dummy_template_image = np.zeros((5,5,3), dtype=np.uint8)
        mock_template_loader.return_value = dummy_template_image

        evaluator = TemplateMatchEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"template_filename": "test.png", "min_confidence": 0.8, "capture_as": "tpl_match"}

        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")

        assert result.met is True
        assert result.captured_value == {"value": match_details, "_source_region_for_capture_": "test_rgn"}
        assert result.template_match_info == {"found": True, **match_details, "matched_region_name": "test_rgn"}
        mock_template_loader.assert_called_once_with("test.png", "test_rule")
        mock_analysis_engine.match_template.assert_called_once_with(
            dummy_image_bgr, dummy_template_image, 0.8,
            region_name_context="test_rule/test_rgn", template_name_context="test.png"
        )

    def test_evaluate_no_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.match_template.return_value = None
        dummy_template_image = np.zeros((5,5,3), dtype=np.uint8)
        mock_template_loader.return_value = dummy_template_image
        evaluator = TemplateMatchEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"template_filename": "test.png", "min_confidence": 0.8}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False
        assert result.template_match_info == {"found": False}


class TestOcrContainsTextEvaluator:
    def test_evaluate_match_and_capture(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        ocr_result = {"text": "Hello World Status OK", "average_confidence": 85.0}
        mock_analysis_engine.ocr_extract_text.return_value = ocr_result
        evaluator = OcrContainsTextEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"text_to_find": "Status", "case_sensitive": False, "min_ocr_confidence": "70", "capture_as": "ocr_text"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        assert result.captured_value == {"value": "Hello World Status OK", "_source_region_for_capture_": "test_rgn"}

    def test_evaluate_no_text_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        ocr_result = {"text": "Hello World", "average_confidence": 90.0}
        mock_analysis_engine.ocr_extract_text.return_value = ocr_result
        evaluator = OcrContainsTextEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"text_to_find": "Error", "case_sensitive": False}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False

    def test_evaluate_confidence_too_low(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        ocr_result = {"text": "Found Text", "average_confidence": 50.0}
        mock_analysis_engine.ocr_extract_text.return_value = ocr_result
        evaluator = OcrContainsTextEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"text_to_find": "Text", "min_ocr_confidence": "60"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False


class TestDominantColorEvaluator:
    def test_evaluate_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        dominant_colors = [{"bgr_color": [200, 50, 50], "percentage": 60.0}] # Blueish
        mock_analysis_engine.analyze_dominant_colors.return_value = dominant_colors
        # Ensure mock_config_settings_getter provides 'analysis_dominant_colors_k'
        mock_config_settings_getter.side_effect = lambda key, default: 1 if key == "analysis_dominant_colors_k" else default

        evaluator = DominantColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [205, 55, 55], "tolerance": 10, "check_top_n_dominant": 1, "min_percentage": 50.0}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        mock_analysis_engine.analyze_dominant_colors.assert_called_once_with(dummy_image_bgr, 1, "test_rule/test_rgn")

class TestGeminiVisionQueryEvaluator:
    def test_evaluate_match_text_and_json_and_capture(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        gemini_response = {
            "status": "success",
            "text_content": "The button is green and says 'Submit'.",
            "json_content": {"color": "green", "label": "Submit", "actionable": True}
        }
        mock_gemini_analyzer.query_vision_model.return_value = gemini_response
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {
            "prompt": "Describe the button.",
            "expected_response_contains": "green,Submit",
            "expected_response_json_path": "actionable",
            "expected_json_value": "True", # Comparison is string based
            "capture_as": "button_details"
        }
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        assert result.captured_value == {"value": True, "_source_region_for_capture_": "test_rgn"} # Captures JSON path value
        mock_gemini_analyzer.query_vision_model.assert_called_once()

    def test_evaluate_text_mismatch(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_gemini_analyzer.query_vision_model.return_value = {"status": "success", "text_content": "The button is red."}
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Color?", "expected_response_contains": "green"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False

    def test_evaluate_json_path_value_mismatch(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_gemini_analyzer.query_vision_model.return_value = {"status": "success", "json_content": {"status": "disabled"}}
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Status?", "expected_response_json_path": "status", "expected_json_value": "enabled"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False

    def test_evaluate_gemini_api_error(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_gemini_analyzer.query_vision_model.return_value = {"status": "error_api", "error_message": "Quota exceeded."}
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Describe"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False

    def test_evaluate_no_gemini_analyzer(self, mock_analysis_engine, mock_template_loader, mock_config_settings_getter):
        # Initialize with gemini_analyzer=None
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, None, mock_config_settings_getter)
        spec = {"prompt": "Describe"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False


class TestAlwaysTrueEvaluator:
    def test_evaluate_always_returns_true(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = AlwaysTrueEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        result = evaluator.evaluate({}, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        assert result.captured_value is None
        assert result.template_match_info is None # always_true doesn't deal with templates