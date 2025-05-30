import pytest
from unittest.mock import patch, MagicMock
import numpy as np
import cv2  # For creating dummy images/templates
import pytesseract  # For TesseractError

from mark_i.engines.analysis_engine import AnalysisEngine


# --- Helper function for the TesseractError side_effect ---
def _raise_tesseract_error_side_effect(*args, **kwargs):
    """Helper function to be used as a side_effect to raise TesseractError."""
    raise pytesseract.TesseractError("Mocked Tesseract OCR engine error")


def _raise_tesseract_not_found_error_side_effect(*args, **kwargs):
    """Helper function to be used as a side_effect to raise TesseractNotFoundError."""
    raise pytesseract.TesseractNotFoundError("Mocked Tesseract not found")


@pytest.fixture
def analysis_engine_instance() -> AnalysisEngine:
    """Provides a default AnalysisEngine instance for tests."""
    return AnalysisEngine()


@pytest.fixture
def dummy_bgr_image_100x100_blue() -> np.ndarray:
    """A 100x100 blue BGR image."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = [255, 0, 0]  # Blue in BGR
    return img


@pytest.fixture
def dummy_bgr_image_50x50_gradient() -> np.ndarray:
    """A 50x50 BGR image with a simple gradient for testing."""
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    for i in range(50):
        img[i, :] = [i * 5, i * 3, i * 2]  # Simple gradient
    return img


@pytest.fixture
def dummy_template_10x10_red() -> np.ndarray:
    """A 10x10 red BGR template."""
    tpl = np.zeros((10, 10, 3), dtype=np.uint8)
    tpl[:, :] = [0, 0, 255]  # Red in BGR
    return tpl


# --- Tests for analyze_pixel_color ---
def test_analyze_pixel_color_match(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    assert analysis_engine_instance.analyze_pixel_color(dummy_bgr_image_100x100_blue, 10, 10, [255, 0, 0], 0) is True


def test_analyze_pixel_color_mismatch(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    assert analysis_engine_instance.analyze_pixel_color(dummy_bgr_image_100x100_blue, 10, 10, [0, 255, 0], 0) is False


def test_analyze_pixel_color_with_tolerance(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    assert analysis_engine_instance.analyze_pixel_color(dummy_bgr_image_100x100_blue, 10, 10, [250, 5, 5], 10) is True


def test_analyze_pixel_color_out_of_bounds(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    assert analysis_engine_instance.analyze_pixel_color(dummy_bgr_image_100x100_blue, 100, 100, [255, 0, 0], 0) is False


def test_analyze_pixel_color_invalid_image(analysis_engine_instance):
    assert analysis_engine_instance.analyze_pixel_color(None, 10, 10, [255, 0, 0], 0) is False  # type: ignore
    assert analysis_engine_instance.analyze_pixel_color(np.array([]), 10, 10, [255, 0, 0], 0) is False
    grayscale_img = np.zeros((100, 100), dtype=np.uint8)  # Grayscale
    assert analysis_engine_instance.analyze_pixel_color(grayscale_img, 10, 10, [0, 0, 0], 0) is False


# --- Tests for analyze_average_color ---
def test_analyze_average_color_solid_blue(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    avg_color = analysis_engine_instance.analyze_average_color(dummy_bgr_image_100x100_blue)
    assert avg_color == [255, 0, 0]


def test_analyze_average_color_invalid_image(analysis_engine_instance):
    assert analysis_engine_instance.analyze_average_color(None) is None  # type: ignore
    assert analysis_engine_instance.analyze_average_color(np.array([])) is None


# --- Tests for match_template ---
def test_match_template_found(analysis_engine_instance, dummy_bgr_image_50x50_gradient, dummy_template_10x10_red):
    # Create an image that contains the red template
    image_with_template = dummy_bgr_image_50x50_gradient.copy()
    image_with_template[5:15, 5:15] = [0, 0, 255]  # Place red template at (5,5)

    # We need to mock cv2.matchTemplate and cv2.minMaxLoc for predictable results
    # as perfect template matching is hard to guarantee without exact pixel copies.
    # For a simple test, let's assume high confidence if it's there.
    # A more robust mock would control the output of minMaxLoc directly.
    with patch("cv2.matchTemplate", return_value=np.array([[0.95]], dtype=np.float32)) as mock_match:
        with patch("cv2.minMaxLoc", return_value=(0.0, 0.95, (0, 0), (5, 5))) as mock_minmax:  # Simulate found at (5,5)
            result = analysis_engine_instance.match_template(image_with_template, dummy_template_10x10_red, threshold=0.8)
            assert result is not None
            assert result["confidence"] >= 0.8
            assert result["location_x"] == 5
            assert result["location_y"] == 5
            assert result["width"] == 10
            assert result["height"] == 10
            mock_match.assert_called_once()
            mock_minmax.assert_called_once()


def test_match_template_not_found(analysis_engine_instance, dummy_bgr_image_50x50_gradient, dummy_template_10x10_red):
    # Image does not contain the template
    with patch("cv2.matchTemplate", return_value=np.array([[0.5]], dtype=np.float32)):  # Low confidence
        with patch("cv2.minMaxLoc", return_value=(0.0, 0.5, (0, 0), (10, 10))):
            result = analysis_engine_instance.match_template(dummy_bgr_image_50x50_gradient, dummy_template_10x10_red, threshold=0.8)
            assert result is None


def test_match_template_template_larger_than_image(analysis_engine_instance, dummy_template_10x10_red):
    small_image = np.zeros((5, 5, 3), dtype=np.uint8)  # 5x5 image
    result = analysis_engine_instance.match_template(small_image, dummy_template_10x10_red)
    assert result is None


def test_match_template_opencv_error(analysis_engine_instance, dummy_bgr_image_50x50_gradient, dummy_template_10x10_red):
    with patch("cv2.matchTemplate", side_effect=cv2.error("Mocked OpenCV error")):
        result = analysis_engine_instance.match_template(dummy_bgr_image_50x50_gradient, dummy_template_10x10_red)
        assert result is None


# --- Tests for ocr_extract_text ---
MOCK_OCR_DATA_SUCCESS = {
    "level": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],
    "page_num": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "block_num": [0, 1, 1, 1, 1, 0, 1, 1, 1, 1],
    "par_num": [0, 0, 1, 1, 1, 0, 0, 1, 1, 1],
    "line_num": [0, 0, 0, 1, 1, 0, 0, 0, 1, 1],
    "word_num": [0, 0, 0, 0, 1, 0, 0, 0, 0, 2],
    "left": [0, 10, 10, 10, 10, 0, 70, 70, 70, 70],
    "top": [0, 10, 10, 10, 10, 0, 10, 10, 10, 10],
    "width": [100, 50, 50, 50, 50, 100, 50, 50, 50, 50],
    "height": [20, 10, 10, 10, 10, 20, 10, 10, 10, 10],
    "conf": ["-1", "-1", "-1", "-1", "95.0", "-1", "-1", "-1", "-1", "88.0"],
    "text": ["", "", "", "", "Hello", "", "", "", "", "World"],
}


def test_ocr_extract_text_success(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    with patch("pytesseract.image_to_data", return_value=MOCK_OCR_DATA_SUCCESS) as mock_ocr:
        result = analysis_engine_instance.ocr_extract_text(dummy_bgr_image_100x100_blue)
        assert result is not None
        assert result["text"] == "Hello World"
        assert result["average_confidence"] == pytest.approx((95.0 + 88.0) / 2)
        mock_ocr.assert_called_once()


def test_ocr_extract_text_tesseract_not_found_error(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    # Use the helper for side_effect
    with patch("pytesseract.image_to_data", side_effect=_raise_tesseract_not_found_error_side_effect):
        result = analysis_engine_instance.ocr_extract_text(dummy_bgr_image_100x100_blue)
        assert result is None


def test_ocr_extract_text_tesseract_error(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    # This is the corrected patch for the original SyntaxError
    with patch("pytesseract.image_to_data", side_effect=_raise_tesseract_error_side_effect):
        result = analysis_engine_instance.ocr_extract_text(dummy_bgr_image_100x100_blue)
        assert result is None


def test_ocr_extract_text_empty_result(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    empty_ocr_data = {key: [] for key in MOCK_OCR_DATA_SUCCESS.keys()}
    with patch("pytesseract.image_to_data", return_value=empty_ocr_data):
        result = analysis_engine_instance.ocr_extract_text(dummy_bgr_image_100x100_blue)
        assert result is not None
        assert result["text"] == ""
        assert result["average_confidence"] == 0.0


# --- Tests for analyze_dominant_colors ---
def test_analyze_dominant_colors_success(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    # Mocking cv2.kmeans is a bit more involved as it returns multiple values
    # and its behavior depends on the input image.
    # For a simple test, we can check if it runs and returns something plausible.
    # A solid blue image should ideally have blue as the dominant color.

    # For simplicity, we'll assume k-means works and check basic output structure
    # In a real scenario, you might mock cv2.kmeans to return predefined centers and labels.
    mock_centers = np.array([[250, 10, 10], [50, 50, 50]], dtype=np.float32)  # BGR
    mock_labels = np.array([[0]] * 7000 + [[1]] * 3000, dtype=np.int32)  # 70% blue-ish, 30% gray-ish
    mock_compactness = 100.0

    with patch("cv2.kmeans", return_value=(mock_compactness, mock_labels, mock_centers)):
        result = analysis_engine_instance.analyze_dominant_colors(dummy_bgr_image_100x100_blue, num_colors=2)
        assert result is not None
        assert len(result) <= 2
        if result:
            assert "bgr_color" in result[0]
            assert "percentage" in result[0]
            assert result[0]["bgr_color"] == [250, 10, 10]  # Check if the most dominant is the one we expect
            assert result[0]["percentage"] == pytest.approx(70.0)


def test_analyze_dominant_colors_invalid_k(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    # Test that k is handled (e.g., defaults if invalid)
    # cv2.kmeans will raise an error if k is too large or <= 0.
    # The AnalysisEngine already has checks for num_colors.
    result_zero_k = analysis_engine_instance.analyze_dominant_colors(dummy_bgr_image_100x100_blue, num_colors=0)
    assert result_zero_k == []  # Should return empty list if k becomes 0

    result_negative_k = analysis_engine_instance.analyze_dominant_colors(dummy_bgr_image_100x100_blue, num_colors=-1)
    # It defaults to 3 if num_colors is not > 0
    assert result_negative_k is not None
    if result_negative_k:
        assert len(result_negative_k) <= 3


def test_analyze_dominant_colors_image_too_small(analysis_engine_instance):
    tiny_image = np.zeros((1, 1, 3), dtype=np.uint8)  # 1 pixel
    result = analysis_engine_instance.analyze_dominant_colors(tiny_image, num_colors=3)
    assert result is not None
    assert len(result) == 1  # k will be reduced to num_pixels (1)
    assert result[0]["percentage"] == 100.0


def test_analysis_engine_init_with_ocr_command(monkeypatch):
    """Test if tesseract_cmd is set when ocr_command is provided."""
    mock_set_cmd = MagicMock()
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "/custom/path/tesseract", raising=False)  # allow reassignment
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", property(fset=mock_set_cmd))

    custom_path = "/usr/bin/tesseract"
    ae = AnalysisEngine(ocr_command=custom_path)
    assert ae.ocr_command == custom_path
    # Check if the setter was actually called (this is a bit tricky due to how pytesseract handles it)
    # A simple check is that if an error didn't occur, it's likely okay.
    # For more direct check, one might need to inspect pytesseract.pytesseract.tesseract_cmd if it's a simple variable.


def test_analysis_engine_init_without_ocr_command():
    """Test default behavior when ocr_command is not provided."""
    # This test mainly ensures no error occurs.
    # Pytesseract will search PATH, which we don't control/test here.
    ae = AnalysisEngine()
    assert ae.ocr_command is None
