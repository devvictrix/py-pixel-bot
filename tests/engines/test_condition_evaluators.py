import pytest
from unittest.mock import MagicMock, patch, create_autospec

import numpy as np
import cv2 # For cv2.error
import pytesseract # For pytesseract.TesseractNotFoundError, TesseractError

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
    return create_autospec(AnalysisEngine, instance=True)

@pytest.fixture
def mock_gemini_analyzer():
    mock_ga = create_autospec(GeminiAnalyzer, instance=True)
    mock_ga.client_initialized = True
    return mock_ga

@pytest.fixture
def mock_template_loader():
    return MagicMock()

@pytest.fixture
def mock_config_settings_getter():
    def getter(key, default_val):
        if key == "analysis_dominant_colors_k": return 3
        return default_val
    return MagicMock(side_effect=getter)

# Common dummy data
dummy_image_bgr = np.zeros((100, 100, 3), dtype=np.uint8)
dummy_region_data_packet_with_image = {"image": dummy_image_bgr, "ocr_analysis_result": None, "average_color": None, "dominant_colors_result": None}
dummy_region_data_packet_no_image = {"image": None, "ocr_analysis_result": None, "average_color": None, "dominant_colors_result": None}


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

    def test_evaluate_missing_params_in_spec(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = PixelColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        # 'expected_bgr' is critical for analyze_pixel_color, if None, analyze_pixel_color itself will log warning and return False
        spec_no_bgr = {"relative_x": 10, "relative_y": 10}
        result = evaluator.evaluate(spec_no_bgr, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False # analyze_pixel_color would return False
        # mock_analysis_engine.analyze_pixel_color.assert_called_once() # It would be called

        spec_no_coords = {"expected_bgr": [0,0,0]} # Default coords 0,0 will be used by analyze_pixel_color
        mock_analysis_engine.analyze_pixel_color.return_value = True # Assume it would match at 0,0
        result = evaluator.evaluate(spec_no_coords, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True


class TestAverageColorEvaluator:
    def test_evaluate_match_from_pre_analyzed(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        pre_analyzed_packet = {"image": dummy_image_bgr, "average_color": [50, 60, 70]}
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [55, 65, 75], "tolerance": 10}
        result = evaluator.evaluate(spec, "test_rgn", pre_analyzed_packet, "test_rule")
        assert result.met == True # Changed from 'is'
        mock_analysis_engine.analyze_average_color.assert_not_called()

    def test_evaluate_match_on_demand(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.analyze_average_color.return_value = [50, 60, 70]
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [55, 65, 75], "tolerance": 10}
        packet = {"image": dummy_image_bgr}
        result = evaluator.evaluate(spec, "test_rgn", packet, "test_rule")
        assert result.met == True # Changed from 'is'
        mock_analysis_engine.analyze_average_color.assert_called_once_with(dummy_image_bgr, "test_rule/test_rgn")

    def test_evaluate_no_match_due_to_color(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.analyze_average_color.return_value = [100, 100, 100]
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [50, 50, 50], "tolerance": 5}
        result = evaluator.evaluate(spec, "test_rgn", {"image": dummy_image_bgr}, "test_rule")
        assert result.met == False # Changed from 'is'

    def test_evaluate_no_image(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = AverageColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [50, 50, 50]}
        # Simulate AE returning None if image is None
        mock_analysis_engine.analyze_average_color.return_value = None
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_no_image, "test_rule")
        assert result.met is False
        # With the change to _get_pre_analyzed_data, analyze_average_color WILL be called with None
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

    def test_evaluate_no_match(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_analysis_engine.match_template.return_value = None
        dummy_template_image = np.zeros((5,5,3), dtype=np.uint8)
        mock_template_loader.return_value = dummy_template_image
        evaluator = TemplateMatchEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"template_filename": "test.png", "min_confidence": 0.8}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False
        assert result.template_match_info == {"found": False}

    def test_evaluate_template_loader_fails(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        mock_template_loader.return_value = None # Simulate template not found/loaded
        evaluator = TemplateMatchEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"template_filename": "nonexistent.png"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False
        mock_analysis_engine.match_template.assert_not_called()

    def test_evaluate_missing_filename(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = TemplateMatchEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"min_confidence": 0.8} # Missing template_filename
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False


class TestOcrContainsTextEvaluator:
    def test_evaluate_match_and_capture_pre_analyzed(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        ocr_result = {"text": "Hello World Status OK", "average_confidence": 85.0}
        pre_analyzed_packet = {"image": dummy_image_bgr, "ocr_analysis_result": ocr_result}
        evaluator = OcrContainsTextEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"text_to_find": "Status", "capture_as": "ocr_text"}
        result = evaluator.evaluate(spec, "test_rgn", pre_analyzed_packet, "test_rule")
        assert result.met is True
        assert result.captured_value == {"value": "Hello World Status OK", "_source_region_for_capture_": "test_rgn"}
        mock_analysis_engine.ocr_extract_text.assert_not_called()

    def test_evaluate_match_on_demand(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        ocr_result = {"text": "Hello World Status OK", "average_confidence": 85.0}
        mock_analysis_engine.ocr_extract_text.return_value = ocr_result
        evaluator = OcrContainsTextEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"text_to_find": "Status"}
        result = evaluator.evaluate(spec, "test_rgn", {"image": dummy_image_bgr}, "test_rule")
        assert result.met is True
        mock_analysis_engine.ocr_extract_text.assert_called_once_with(dummy_image_bgr, "test_rule/test_rgn")

    def test_evaluate_empty_text_to_find(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        ocr_result = {"text": "Some text", "average_confidence": 85.0}
        mock_analysis_engine.ocr_extract_text.return_value = ocr_result
        evaluator = OcrContainsTextEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)

        spec_empty_list = {"text_to_find": []}
        result = evaluator.evaluate(spec_empty_list, "test_rgn", {"image": dummy_image_bgr}, "test_rule")
        assert result.met is False # Should not match if text_to_find is empty

        spec_list_empty_str = {"text_to_find": ["", "   "]} # These become empty after strip
        result = evaluator.evaluate(spec_list_empty_str, "test_rgn", {"image": dummy_image_bgr}, "test_rule")
        assert result.met is False # Should not match if text_to_find effectively contains only empty strings


class TestDominantColorEvaluator:
    def test_evaluate_match_k_from_config(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        dominant_colors = [{"bgr_color": [200, 50, 50], "percentage": 60.0}]
        mock_analysis_engine.analyze_dominant_colors.return_value = dominant_colors
        # Setup mock_config_settings_getter to return a specific K
        mock_config_settings_getter.side_effect = lambda key, default: 5 if key == "analysis_dominant_colors_k" else default

        evaluator = DominantColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": [205, 55, 55], "tolerance": 10}
        result = evaluator.evaluate(spec, "test_rgn", {"image": dummy_image_bgr}, "test_rule")
        assert result.met is True
        # Verify that AE was called with K=5 from config
        mock_analysis_engine.analyze_dominant_colors.assert_called_once_with(dummy_image_bgr, 5, "test_rule/test_rgn")

    def test_evaluate_invalid_expected_bgr(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        dominant_colors = [{"bgr_color": [200, 50, 50], "percentage": 60.0}]
        mock_analysis_engine.analyze_dominant_colors.return_value = dominant_colors
        evaluator = DominantColorEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"expected_bgr": "not_a_list", "tolerance": 10}
        result = evaluator.evaluate(spec, "test_rgn", {"image": dummy_image_bgr}, "test_rule")
        assert result.met is False


class TestGeminiVisionQueryEvaluator:
    def test_evaluate_json_path_capture(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        gemini_response = {"status": "success", "json_content": {"data": {"item": "found_item"}}}
        mock_gemini_analyzer.query_vision_model.return_value = gemini_response
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Find item", "expected_response_json_path": "data.item", "capture_as": "item_found"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True # True because path exists, no expected_json_value given
        assert result.captured_value == {"value": "found_item", "_source_region_for_capture_": "test_rgn"}

    def test_evaluate_full_json_capture(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        full_json = {"status": "ok", "details": "complex"}
        gemini_response = {"status": "success", "json_content": full_json}
        mock_gemini_analyzer.query_vision_model.return_value = gemini_response
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Get status", "capture_as": "full_response"} # No JSON path, expect full JSON
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        assert result.captured_value == {"value": full_json, "_source_region_for_capture_": "test_rgn"}

    def test_evaluate_text_capture_if_no_json(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        text_content = "Analysis complete. Result is positive."
        gemini_response = {"status": "success", "text_content": text_content, "json_content": None}
        mock_gemini_analyzer.query_vision_model.return_value = gemini_response
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Analyze", "capture_as": "text_result"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is True
        assert result.captured_value == {"value": text_content, "_source_region_for_capture_": "test_rgn"}

    def test_evaluate_json_path_not_found(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        gemini_response = {"status": "success", "json_content": {"data": {"info": "other"}}}
        mock_gemini_analyzer.query_vision_model.return_value = gemini_response
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {"prompt": "Find", "expected_response_json_path": "data.item", "expected_json_value": "any"}
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False # Path not found, so value check not met

    def test_evaluate_no_prompt(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = GeminiVisionQueryEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        spec = {} # Missing prompt
        result = evaluator.evaluate(spec, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result.met is False
        mock_gemini_analyzer.query_vision_model.assert_not_called()


class TestAlwaysTrueEvaluator:
    def test_evaluate_always_returns_true(self, mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter):
        evaluator = AlwaysTrueEvaluator(mock_analysis_engine, mock_template_loader, mock_gemini_analyzer, mock_config_settings_getter)
        # Test with image and without to ensure it doesn't depend on them
        result_with_img = evaluator.evaluate({}, "test_rgn", dummy_region_data_packet_with_image, "test_rule")
        assert result_with_img.met is True
        result_no_img = evaluator.evaluate({}, "test_rgn", dummy_region_data_packet_no_image, "test_rule")
        assert result_no_img.met is True