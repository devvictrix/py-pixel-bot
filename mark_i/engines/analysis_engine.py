import logging
from typing import Optional, Dict, Any, List
import os  # Used for os.linesep in log formatting

import cv2  # OpenCV for image processing tasks
import numpy as np
import pytesseract  # For OCR
from pytesseract import Output  # For structured OCR data

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.analysis_engine")


class AnalysisEngine:
    """
    Performs various local visual analyses on captured image regions.
    All image_data inputs are expected to be NumPy arrays in BGR format.
    """

    def __init__(self, ocr_command: Optional[str] = None, ocr_config: str = ""):
        """
        Initializes the AnalysisEngine.

        Args:
            ocr_command: Optional. The command or path to the Tesseract executable.
                         If None, pytesseract will attempt to find it in the system PATH.
            ocr_config: Optional. Additional Tesseract configuration string (e.g., '--psm 6').
        """
        self.ocr_command = ocr_command
        if self.ocr_command:
            try:
                pytesseract.pytesseract.tesseract_cmd = self.ocr_command
                logger.info(f"Tesseract executable path explicitly set to: '{self.ocr_command}'")
            except Exception as e:  # pragma: no cover
                logger.error(f"Error attempting to set tesseract_cmd to '{self.ocr_command}': {e}. Pytesseract will rely on PATH.", exc_info=True)
        else:
            logger.info("Tesseract executable path not specified; pytesseract will search in PATH.")

        self.ocr_config = ocr_config
        logger.info(f"AnalysisEngine initialized. Tesseract OCR custom config: '{self.ocr_config if self.ocr_config else 'None (using pytesseract defaults)'}'.")

    def analyze_pixel_color(self, image_data: np.ndarray, x: int, y: int, expected_bgr: List[int], tolerance: int = 0, region_name_context: str = "UnnamedRegion") -> bool:
        """
        Checks the color of a specific pixel against an expected BGR color.

        Args:
            image_data: The image (NumPy array in BGR format).
            x: The x-coordinate of the pixel (relative to the top-left of image_data).
            y: The y-coordinate of the pixel (relative to the top-left of image_data).
            expected_bgr: A list of 3 integers representing the expected BGR color [B, G, R].
            tolerance: The allowed difference for each B, G, R component (0 to 255).
            region_name_context: Name of the region for contextual logging.

        Returns:
            True if the pixel color is within tolerance of the expected color, False otherwise.
        """
        log_prefix = f"Rgn '{region_name_context}', PixelColorCheck @({x},{y})"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data (None, empty, or not NumPy array). Cannot analyze.")
            return False
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"{log_prefix}: image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}.")
            return False

        if not (isinstance(x, int) and isinstance(y, int)):
            logger.warning(f"{log_prefix}: Coordinates ({x},{y}) are not integers.")
            return False
        if not (isinstance(expected_bgr, list) and len(expected_bgr) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in expected_bgr)):
            logger.warning(f"{log_prefix}: expected_bgr '{expected_bgr}' is not a list of 3 valid integers (0-255).")
            return False
        if not (isinstance(tolerance, int) and 0 <= tolerance <= 255):
            logger.warning(f"{log_prefix}: Tolerance '{tolerance}' is not a valid integer (0-255). Using 0.")
            tolerance = 0

        height, width, _ = image_data.shape
        if not (0 <= y < height and 0 <= x < width):
            logger.warning(f"{log_prefix}: Pixel coordinates ({x},{y}) are out of image bounds ({width}x{height}).")
            return False

        actual_bgr = image_data[y, x]  # BGR order
        # logger.debug(f"{log_prefix}: Actual BGR: {actual_bgr.tolist()}, Expected BGR: {expected_bgr}, Tolerance: {tolerance}")

        match = all(abs(int(actual_component) - int(expected_component)) <= tolerance for actual_component, expected_component in zip(actual_bgr, expected_bgr))

        log_level = logging.INFO if match else logging.DEBUG
        logger.log(log_level, f"{log_prefix}: {'MATCHED' if match else 'MISMATCH'}. Actual: {actual_bgr.tolist()}, Expected: {expected_bgr}, Tol: {tolerance}.")
        return match

    def analyze_average_color(self, image_data: np.ndarray, region_name_context: str = "UnnamedRegion") -> Optional[List[int]]:
        """
        Calculates the average BGR color of an image.

        Args:
            image_data: The image (NumPy array in BGR format).
            region_name_context: Name of the region for contextual logging.

        Returns:
            A list of 3 integers representing the average BGR color [B, G, R],
            or None if image_data is invalid or analysis fails.
        """
        log_prefix = f"Rgn '{region_name_context}', AvgColorAnalysis"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data (None, empty, or not NumPy array).")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"{log_prefix}: image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}.")
            return None

        try:
            avg_bgr_float = np.mean(image_data, axis=(0, 1))
            avg_bgr_int = [int(round(c)) for c in avg_bgr_float]
            logger.info(f"{log_prefix}: Average BGR color calculated: {avg_bgr_int} for image shape {image_data.shape}.")
            return avg_bgr_int
        except Exception as e:  # pragma: no cover
            logger.error(f"{log_prefix}: Error calculating average color: {e}", exc_info=True)
            return None

    def match_template(
        self, image_data: np.ndarray, template_image: np.ndarray, threshold: float = 0.8, region_name_context: str = "UnnamedRegion", template_name_context: str = "UnnamedTemplate"
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a template within an image using OpenCV's template matching.

        Args:
            image_data: The image to search within (NumPy array, BGR format).
            template_image: The template image to find (NumPy array, BGR format).
            threshold: The minimum confidence score (0.0 to 1.0) for a match.
            region_name_context: Name of the region being searched, for logging.
            template_name_context: Name of the template being used, for logging.

        Returns:
            A dictionary with match details if found above threshold, otherwise None.
            Match details: {"location_x": int, "location_y": int, "confidence": float, "width": int, "height": int}
        """
        log_prefix = f"Rgn '{region_name_context}', TemplateMatch '{template_name_context}'"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0 or not isinstance(template_image, np.ndarray) or template_image.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data or template_image (None, empty, or not NumPy array).")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3 or template_image.ndim != 3 or template_image.shape[2] != 3:
            logger.warning(f"{log_prefix}: image_data (shape {image_data.shape}) or template_image (shape {template_image.shape}) is not a 3-channel (BGR) image.")
            return None
        if not (isinstance(threshold, float) and 0.0 <= threshold <= 1.0):
            logger.warning(f"{log_prefix}: Invalid threshold '{threshold}'. Must be float 0.0-1.0. Using 0.8.")
            threshold = 0.8

        img_h, img_w = image_data.shape[:2]
        tpl_h, tpl_w = template_image.shape[:2]

        if img_h < tpl_h or img_w < tpl_w:
            logger.warning(f"{log_prefix}: Template (h={tpl_h}, w={tpl_w}) is larger than image (h={img_h}, w={img_w}). Cannot perform matching.")
            return None

        try:
            match_method = cv2.TM_CCOEFF_NORMED
            result_matrix = cv2.matchTemplate(image_data, template_image, match_method)
            _min_val, max_val, _min_loc, max_loc_top_left = cv2.minMaxLoc(result_matrix)
            confidence_score = float(max_val)

            # logger.debug(f"{log_prefix}: Max confidence {confidence_score:.4f} at {max_loc_top_left}. Threshold: {threshold:.4f}")

            if confidence_score >= threshold:
                match_details = {
                    "location_x": int(max_loc_top_left[0]),
                    "location_y": int(max_loc_top_left[1]),
                    "confidence": confidence_score,
                    "width": int(tpl_w),
                    "height": int(tpl_h),
                }
                logger.info(f"{log_prefix}: TEMPLATE MATCHED. Confidence: {confidence_score:.4f} at ({match_details['location_x']},{match_details['location_y']}). Size: {tpl_w}x{tpl_h}.")
                return match_details
            else:
                logger.info(f"{log_prefix}: Template NOT matched (Max confidence {confidence_score:.4f} < Threshold {threshold:.4f}).")
                return None
        except cv2.error as e_cv2:  # pragma: no cover
            logger.error(f"{log_prefix}: OpenCV error during template matching: {e_cv2}. Check image/template dimensions and types.", exc_info=True)
            return None
        except Exception as e:  # pragma: no cover
            logger.exception(f"{log_prefix}: Unexpected error during template matching: {e}")
            return None

    def ocr_extract_text(self, image_data: np.ndarray, region_name_context: str = "UnnamedRegion") -> Optional[Dict[str, Any]]:
        """
        Extracts text from an image using Tesseract OCR and calculates average word confidence.
        """
        log_prefix = f"Rgn '{region_name_context}', OCR"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data.")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:  # pragma: no cover
            logger.warning(f"{log_prefix}: image_data not BGR. Shape: {image_data.shape}.")
            return None

        try:
            ocr_data_dict = pytesseract.image_to_data(image_data, lang="eng", config=self.ocr_config, output_type=Output.DICT)

            if logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
                summary_raw_data = {k: (v_list[:5] + ["..."] if isinstance(v_list, list) and len(v_list) > 5 else v_list) for k, v_list in ocr_data_dict.items()}
                logger.debug(f"{log_prefix}: Raw Tesseract data (summary): {summary_raw_data}")

            extracted_words: List[str] = []
            confidences: List[float] = []
            num_entries = len(ocr_data_dict.get("level", []))

            for i in range(num_entries):
                if ocr_data_dict["level"][i] == 5:  # Level 5 is 'word'
                    word_text = str(ocr_data_dict["text"][i]).strip()
                    try:
                        word_conf = float(ocr_data_dict["conf"][i])
                    except ValueError:  # pragma: no cover
                        continue  # Skip if confidence is not a number
                    if word_text and word_conf >= 0:  # Consider 0 confidence as a reported value
                        extracted_words.append(word_text)
                        confidences.append(word_conf)

            full_text = " ".join(extracted_words)
            average_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
            text_snippet = full_text[:70].replace(os.linesep, " ") + ("..." if len(full_text) > 70 else "")
            logger.info(f"{log_prefix}: Extracted (len {len(full_text)}): '{text_snippet}'. Avg Word Conf: {average_confidence:.1f}% ({len(confidences)} words).")
            return {"text": full_text, "average_confidence": average_confidence, "raw_data": ocr_data_dict}
        except pytesseract.TesseractNotFoundError:  # pragma: no cover
            logger.error("Tesseract OCR engine not installed or not in PATH. OCR unavailable.")
            return None
        except pytesseract.TesseractError as e_tess:  # pragma: no cover
            logger.error(f"{log_prefix}: Tesseract error during OCR: {e_tess}", exc_info=True)
            return None
        except Exception as e:  # pragma: no cover
            logger.exception(f"{log_prefix}: Unexpected error during OCR: {e}")
            return None

    def analyze_dominant_colors(self, image_data: np.ndarray, num_colors: int = 3, region_name_context: str = "UnnamedRegion") -> Optional[List[Dict[str, Any]]]:
        """
        Finds N dominant colors in an image using K-Means clustering.
        """
        log_prefix = f"Rgn '{region_name_context}', DominantColor (k={num_colors})"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data.")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"{log_prefix}: image_data not BGR. Shape: {image_data.shape}.")
            return None

        original_k_requested = num_colors  # For logging

        if not isinstance(num_colors, int) or num_colors <= 0:
            logger.warning(f"{log_prefix}: Invalid num_colors '{original_k_requested}'. Cannot perform K-Means. Returning empty list.")
            return []

        num_pixels = image_data.shape[0] * image_data.shape[1]
        if num_pixels == 0:
            logger.warning(f"{log_prefix}: Image has zero pixels.")
            return []
        if num_pixels < num_colors:
            logger.warning(f"{log_prefix}: Image pixels ({num_pixels}) < k ({num_colors}). Reducing k to {num_pixels}.")
            num_colors = num_pixels

        if num_colors == 0:
            logger.warning(f"{log_prefix}: Effective k is 0 after adjustments (original k: {original_k_requested}). Cannot perform K-Means. Returning empty list.")
            return []

        try:
            pixels_reshaped = image_data.reshape((-1, 3))
            pixels_float32 = np.float32(pixels_reshaped)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
            attempts = 10

            _compactness, labels_flat, centers_float_bgr = cv2.kmeans(pixels_float32, num_colors, None, criteria, attempts, cv2.KMEANS_RANDOM_CENTERS)

            unique_cluster_indices, pixel_counts_per_cluster = np.unique(labels_flat, return_counts=True)

            actual_num_centers_found = centers_float_bgr.shape[0]

            dominant_colors_list: List[Dict[str, Any]] = []
            for i, cluster_idx_from_unique in enumerate(unique_cluster_indices):
                if cluster_idx_from_unique < actual_num_centers_found:
                    bgr_float_components = centers_float_bgr[cluster_idx_from_unique]
                    bgr_int_components = [int(round(c)) for c in bgr_float_components]
                    occurrence_percentage = (pixel_counts_per_cluster[i] / float(num_pixels)) * 100.0
                    dominant_colors_list.append({"bgr_color": bgr_int_components, "percentage": float(occurrence_percentage)})
                else:  # pragma: no cover
                    logger.warning(
                        f"{log_prefix}: K-Means label index {cluster_idx_from_unique} out of bounds for centers array (len {actual_num_centers_found}). This might indicate an issue with num_colors vs actual clusters found."
                    )

            dominant_colors_list.sort(key=lambda x: x["percentage"], reverse=True)

            if not dominant_colors_list:  # pragma: no cover
                logger.warning(f"{log_prefix}: No dominant colors resolved despite K-Means run.")
                return []

            log_summary = [f"BGR:{d['bgr_color']}({d['percentage']:.1f}%)" for d in dominant_colors_list]
            logger.info(f"{log_prefix}: Found {len(dominant_colors_list)} colors: [{'; '.join(log_summary)}]")
            return dominant_colors_list
        except cv2.error as e_cv2:  # pragma: no cover
            logger.error(f"{log_prefix}: OpenCV error during K-Means: {e_cv2}. Check if image is too small or k is too large for unique colors.", exc_info=True)
            return None
        except Exception as e:  # pragma: no cover
            logger.exception(f"{log_prefix}: Unexpected error during K-Means: {e}")
            return None
