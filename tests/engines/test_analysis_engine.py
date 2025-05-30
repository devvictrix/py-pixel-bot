import pytest
from unittest.mock import MagicMock, patch, create_autospec
import numpy as np
import cv2  # For cv2.error
import pytesseract  # For pytesseract.TesseractNotFoundError, TesseractError

from mark_i.engines.analysis_engine import AnalysisEngine

# --- Mock Fixtures & Dummy Data ---
dummy_image_bgr_ae = np.zeros((100, 100, 3), dtype=np.uint8)  # AE: AnalysisEngine
dummy_image_bgr_small = np.zeros((5, 5, 3), dtype=np.uint8)
dummy_template_image_ae = np.zeros((20, 20, 3), dtype=np.uint8)


@pytest.fixture
def analysis_engine_instance():
    """Provides a default AnalysisEngine instance for testing."""
    return AnalysisEngine()  # Uses default OCR command/config


@pytest.fixture
def analysis_engine_with_ocr_cmd():
    """Provides an AnalysisEngine instance with a mocked OCR command."""
    return AnalysisEngine(ocr_command="/mock/tesseract", ocr_config="--psm 6")


class TestAnalysisEnginePixelColor:
    def test_analyze_pixel_color_match(self, analysis_engine_instance: AnalysisEngine):
        img = np.array([[[255, 0, 0], [0, 255, 0]], [[0, 0, 255], [10, 20, 30]]], dtype=np.uint8)  # BGR
        assert analysis_engine_instance.analyze_pixel_color(img, 0, 0, [255, 0, 0], 0) is True
        assert analysis_engine_instance.analyze_pixel_color(img, 1, 1, [12, 22, 32], 2) is True

    def test_analyze_pixel_color_no_match(self, analysis_engine_instance: AnalysisEngine):
        img = np.array([[[255, 0, 0]]], dtype=np.uint8)
        assert analysis_engine_instance.analyze_pixel_color(img, 0, 0, [0, 0, 255], 0) is False

    def test_analyze_pixel_color_out_of_bounds(self, analysis_engine_instance: AnalysisEngine):
        assert analysis_engine_instance.analyze_pixel_color(dummy_image_bgr_ae, 200, 200, [0, 0, 0], 0) is False

    def test_analyze_pixel_color_invalid_input(self, analysis_engine_instance: AnalysisEngine):
        assert analysis_engine_instance.analyze_pixel_color(None, 0, 0, [0, 0, 0], 0) is False  # type: ignore
        assert analysis_engine_instance.analyze_pixel_color(np.zeros((10, 10)), 0, 0, [0, 0, 0], 0) is False  # Not 3 channels
        assert analysis_engine_instance.analyze_pixel_color(dummy_image_bgr_ae, 0, 0, [0, 0], 0) is False  # Invalid BGR
        assert analysis_engine_instance.analyze_pixel_color(dummy_image_bgr_ae, 0, 0, [0, 0, 300], 0) is False  # Invalid BGR val


class TestAnalysisEngineAverageColor:
    def test_analyze_average_color_valid(self, analysis_engine_instance: AnalysisEngine):
        img = np.array([[[10, 20, 30], [20, 30, 40]], [[30, 40, 50], [40, 50, 60]]], dtype=np.uint8)  # BGR
        # Expected: B_avg = (10+20+30+40)/4 = 25
        #           G_avg = (20+30+40+50)/4 = 35
        #           R_avg = (30+40+50+60)/4 = 45
        assert analysis_engine_instance.analyze_average_color(img) == [25, 35, 45]

    def test_analyze_average_color_invalid_image(self, analysis_engine_instance: AnalysisEngine):
        assert analysis_engine_instance.analyze_average_color(None) is None  # type: ignore
        assert analysis_engine_instance.analyze_average_color(np.array([])) is None
        assert analysis_engine_instance.analyze_average_color(np.zeros((10, 10, 2))) is None  # Not 3 channel


class TestAnalysisEngineTemplateMatch:
    @patch("cv2.matchTemplate")
    @patch("cv2.minMaxLoc")
    def test_match_template_found_above_threshold(self, mock_minMaxLoc: MagicMock, mock_matchTemplate: MagicMock, analysis_engine_instance: AnalysisEngine):
        mock_matchTemplate.return_value = np.array([[0.95]])  # Dummy result matrix
        mock_minMaxLoc.return_value = (0.1, 0.95, (0, 0), (5, 5))  # minVal, maxVal, minLoc, maxLoc

        result = analysis_engine_instance.match_template(dummy_image_bgr_ae, dummy_template_image_ae, threshold=0.8)
        assert result is not None
        assert result["confidence"] == 0.95
        assert result["location_x"] == 5
        assert result["location_y"] == 5
        assert result["width"] == dummy_template_image_ae.shape[1]
        assert result["height"] == dummy_template_image_ae.shape[0]

    @patch("cv2.matchTemplate")
    @patch("cv2.minMaxLoc")
    def test_match_template_found_below_threshold(self, mock_minMaxLoc: MagicMock, mock_matchTemplate: MagicMock, analysis_engine_instance: AnalysisEngine):
        mock_matchTemplate.return_value = np.array([[0.7]])
        mock_minMaxLoc.return_value = (0.1, 0.7, (0, 0), (5, 5))
        result = analysis_engine_instance.match_template(dummy_image_bgr_ae, dummy_template_image_ae, threshold=0.8)
        assert result is None

    def test_match_template_template_larger_than_image(self, analysis_engine_instance: AnalysisEngine):
        large_template = np.zeros((150, 150, 3), dtype=np.uint8)
        result = analysis_engine_instance.match_template(dummy_image_bgr_ae, large_template)  # dummy is 100x100
        assert result is None

    def test_match_template_invalid_images(self, analysis_engine_instance: AnalysisEngine):
        assert analysis_engine_instance.match_template(None, dummy_template_image_ae) is None  # type: ignore
        assert analysis_engine_instance.match_template(dummy_image_bgr_ae, None) is None  # type: ignore

    @patch("cv2.matchTemplate", side_effect=cv2.error("OpenCV Test Error"))
    def test_match_template_cv2_error(self, mock_matchTemplate: MagicMock, analysis_engine_instance: AnalysisEngine):
        result = analysis_engine_instance.match_template(dummy_image_bgr_ae, dummy_template_image_ae)
        assert result is None


class TestAnalysisEngineOcr:
    @patch("pytesseract.image_to_data")
    def test_ocr_extract_text_success(self, mock_image_to_data: MagicMock, analysis_engine_instance: AnalysisEngine):
        # Simulate pytesseract output
        mock_data = {"level": [1, 2, 3, 4, 5, 5], "text": ["", "", "", "", "Hello", "World"], "conf": [-1, -1, -1, -1, "90.0", "85.5"]}  # level 5 is word  # Confidence as string for word level
        mock_image_to_data.return_value = mock_data
        result = analysis_engine_instance.ocr_extract_text(dummy_image_bgr_ae)
        assert result is not None
        assert result["text"] == "Hello World"
        assert pytest.approx(result["average_confidence"]) == (90.0 + 85.5) / 2

    @patch("pytesseract.image_to_data", side_effect=pytesseract.TesseractNotFoundError)
    def test_ocr_tesseract_not_found(self, mock_image_to_data: MagicMock, analysis_engine_instance: AnalysisEngine):
        result = analysis_engine_instance.ocr_extract_text(dummy_image_bgr_ae)
        assert result is None

    @patch("pytesseract.image_to_data", side_effect=pytesseract.TesseractError("OCR engine error"))
    def test_ocr_tesseract_error(self, mock_image_to_data: MagicMock, analysis_engine_instance: AnalysisEngine):
        result = analysis_engine_instance.ocr_extract_text(dummy_image_bgr_ae)
        assert result is None

    def test_ocr_invalid_image(self, analysis_engine_instance: AnalysisEngine):
        assert analysis_engine_instance.ocr_extract_text(None) is None  # type: ignore


class TestAnalysisEngineDominantColors:
    @patch("cv2.kmeans")
    def test_analyze_dominant_colors_success(self, mock_kmeans: MagicMock, analysis_engine_instance: AnalysisEngine):
        # Simulate cv2.kmeans output
        # compactness, labels, centers
        mock_labels = np.array([[0], [1], [0], [0], [1]], dtype=np.int32)  # 3 pixels for color 0, 2 for color 1
        mock_centers = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.float32)  # Blue, Green
        mock_kmeans.return_value = (10.0, mock_labels, mock_centers)

        result = analysis_engine_instance.analyze_dominant_colors(dummy_image_bgr_small, num_colors=2)  # Small image
        assert result is not None
        assert len(result) == 2
        # Pixels for label 0 = 3, for label 1 = 2. Total = 5
        # Color 0 (Blue) should be ~60%, Color 1 (Green) ~40%
        # Results are sorted by percentage desc
        assert result[0]["bgr_color"] == [255, 0, 0]  # Blue
        assert pytest.approx(result[0]["percentage"]) == (3 / 5) * 100
        assert result[1]["bgr_color"] == [0, 255, 0]  # Green
        assert pytest.approx(result[1]["percentage"]) == (2 / 5) * 100

    def test_analyze_dominant_colors_k_larger_than_pixels(self, analysis_engine_instance: AnalysisEngine):
        # This should reduce k to number of pixels.
        # With a 2x1 image (2 pixels), and k=3, k should become 2.
        img_2px = np.array([[[10, 10, 10]], [[20, 20, 20]]], dtype=np.uint8)  # 2x1 image

        with patch("cv2.kmeans") as mock_kmeans_2px:
            mock_labels_2px = np.array([[0], [1]], dtype=np.int32)
            mock_centers_2px = np.array([[10, 10, 10], [20, 20, 20]], dtype=np.float32)
            mock_kmeans_2px.return_value = (1.0, mock_labels_2px, mock_centers_2px)
            result = analysis_engine_instance.analyze_dominant_colors(img_2px, num_colors=3)
            assert result is not None
            assert len(result) == 2
            # Check that cv2.kmeans was called with k=2 (num_pixels)
            assert mock_kmeans_2px.call_args[0][1] == 2  # num_colors (k) argument to kmeans

    @patch("cv2.kmeans", side_effect=cv2.error("OpenCV Kmeans Error"))
    def test_analyze_dominant_colors_cv2_error(self, mock_kmeans: MagicMock, analysis_engine_instance: AnalysisEngine):
        result = analysis_engine_instance.analyze_dominant_colors(dummy_image_bgr_ae, num_colors=3)
        assert result is None
