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
    image_with_template = dummy_bgr_image_50x50_gradient.copy()
    image_with_template[5:15, 5:15] = [0, 0, 255]

    with patch("cv2.matchTemplate", return_value=np.array([[0.95]], dtype=np.float32)) as mock_match:
        with patch("cv2.minMaxLoc", return_value=(0.0, 0.95, (0, 0), (5, 5))) as mock_minmax:
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
    with patch("cv2.matchTemplate", return_value=np.array([[0.5]], dtype=np.float32)):
        with patch("cv2.minMaxLoc", return_value=(0.0, 0.5, (0, 0), (10, 10))):
            result = analysis_engine_instance.match_template(dummy_bgr_image_50x50_gradient, dummy_template_10x10_red, threshold=0.8)
            assert result is None


def test_match_template_template_larger_than_image(analysis_engine_instance, dummy_template_10x10_red):
    small_image = np.zeros((5, 5, 3), dtype=np.uint8)
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
    with patch("pytesseract.image_to_data", side_effect=_raise_tesseract_not_found_error_side_effect):
        result = analysis_engine_instance.ocr_extract_text(dummy_bgr_image_100x100_blue)
        assert result is None


def test_ocr_extract_text_tesseract_error(analysis_engine_instance, dummy_bgr_image_100x100_blue):
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
    mock_centers = np.array([[250, 10, 10], [50, 50, 50]], dtype=np.float32)
    mock_labels = np.array([[0]] * 7000 + [[1]] * 3000, dtype=np.int32)
    mock_compactness = 100.0

    with patch("cv2.kmeans", return_value=(mock_compactness, mock_labels, mock_centers)):
        result = analysis_engine_instance.analyze_dominant_colors(dummy_bgr_image_100x100_blue, num_colors=2)
        assert result is not None
        assert len(result) <= 2
        if result:
            assert "bgr_color" in result[0]
            assert "percentage" in result[0]
            assert result[0]["bgr_color"] == [250, 10, 10]
            assert result[0]["percentage"] == pytest.approx(70.0)


def test_analyze_dominant_colors_invalid_k(analysis_engine_instance, dummy_bgr_image_100x100_blue):
    result_zero_k = analysis_engine_instance.analyze_dominant_colors(dummy_bgr_image_100x100_blue, num_colors=0)
    assert result_zero_k == []

    result_negative_k = analysis_engine_instance.analyze_dominant_colors(dummy_bgr_image_100x100_blue, num_colors=-1)
    assert result_negative_k == []


def test_analyze_dominant_colors_image_too_small(analysis_engine_instance):
    tiny_image = np.zeros((1, 1, 3), dtype=np.uint8) # 1 pixel
    tiny_image[0,0] = [10,20,30] # BGR color

    # Mock the behavior of cv2.kmeans and np.unique for this specific 1-pixel case
    # When k=1, kmeans should return the pixel itself as the center.
    # labels_flat should indicate all pixels belong to cluster 0.
    # unique_cluster_indices should be [0], pixel_counts_per_cluster should be [1].
    mock_kmeans_centers = np.array([[10, 20, 30]], dtype=np.float32) # The color of the single pixel
    mock_kmeans_labels_flat = np.array([[0]], dtype=np.int32) # The single pixel belongs to cluster 0
    mock_kmeans_compactness = 1.0

    mock_unique_indices = np.array([0], dtype=np.int32)
    mock_unique_counts = np.array([1], dtype=np.int32) # 1 pixel in the cluster

    with patch("cv2.kmeans", return_value=(mock_kmeans_compactness, mock_kmeans_labels_flat, mock_kmeans_centers)) as mock_cv_kmeans:
        with patch("numpy.unique", return_value=(mock_unique_indices, mock_unique_counts)) as mock_np_unique:
            result = analysis_engine_instance.analyze_dominant_colors(tiny_image, num_colors=3) # num_colors will be reduced to 1

            assert result is not None
            assert len(result) == 1  # k was reduced to 1
            assert result[0]["bgr_color"] == [10, 20, 30]
            assert result[0]["percentage"] == pytest.approx(100.0)

            # Check that cv2.kmeans was called with k=1 (num_colors reduced from 3)
            # pixels_float32, num_colors, None, criteria, attempts, cv2.KMEANS_RANDOM_CENTERS
            # The first arg is image.data.reshape(-1,3) (np.float32)
            # The second arg is the 'k' value
            assert mock_cv_kmeans.call_args[0][1] == 1 # Check k was 1
            # Check that np.unique was called with the labels from kmeans
            mock_np_unique.assert_called_once_with(mock_kmeans_labels_flat, return_counts=True)


def test_analysis_engine_init_with_ocr_command(monkeypatch):
    mock_set_cmd = MagicMock()
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "/custom/path/tesseract", raising=False)
    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", property(fset=mock_set_cmd))

    custom_path = "/usr/bin/tesseract"
    ae = AnalysisEngine(ocr_command=custom_path)
    assert ae.ocr_command == custom_path


def test_analysis_engine_init_without_ocr_command():
    ae = AnalysisEngine()
    assert ae.ocr_command is None