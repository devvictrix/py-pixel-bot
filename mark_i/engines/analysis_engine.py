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
                # Note: Modifying pytesseract.pytesseract.tesseract_cmd is a global change.
                # This is generally how it's used if Tesseract isn't in PATH.
                pytesseract.pytesseract.tesseract_cmd = self.ocr_command
                logger.info(f"Tesseract executable path explicitly set to: '{self.ocr_command}'")
            except Exception as e:
                logger.error(f"Error attempting to set tesseract_cmd to '{self.ocr_command}': {e}. Pytesseract will rely on PATH.", exc_info=True)
        else:
            logger.info("Tesseract executable path not specified; pytesseract will search in PATH.")

        self.ocr_config = ocr_config
        logger.info(f"AnalysisEngine initialized. Tesseract OCR custom config: '{self.ocr_config if self.ocr_config else 'None (using pytesseract defaults)'}'.")

    def analyze_pixel_color(self, image_data: np.ndarray, x: int, y: int, expected_bgr: List[int], tolerance: int = 0, region_name_context: str = "UnnamedRegion") -> bool:  # Added for better logging
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
        logger.debug(f"{log_prefix}: Actual BGR: {actual_bgr.tolist()}, Expected BGR: {expected_bgr}, Tolerance: {tolerance}")

        # Compare each B, G, R component
        match = all(abs(int(actual_component) - int(expected_component)) <= tolerance for actual_component, expected_component in zip(actual_bgr, expected_bgr))

        if match:
            logger.info(f"{log_prefix}: Color MATCHED. Actual: {actual_bgr.tolist()}, Expected: {expected_bgr}, Tol: {tolerance}.")
        else:
            logger.debug(f"{log_prefix}: Color MISMATCH. Actual: {actual_bgr.tolist()}, Expected: {expected_bgr}, Tol: {tolerance}.")
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
            # Calculate mean across height and width (axes 0 and 1)
            avg_bgr_float = np.mean(image_data, axis=(0, 1))
            # Convert to list of integers [B, G, R]
            avg_bgr_int = [int(round(c)) for c in avg_bgr_float]  # Use round before int conversion
            logger.info(f"{log_prefix}: Average BGR color calculated: {avg_bgr_int} for image shape {image_data.shape}.")
            return avg_bgr_int
        except Exception as e:
            logger.error(f"{log_prefix}: Error calculating average color: {e}", exc_info=True)
            return None

    def match_template(
        self,
        image_data: np.ndarray,  # The larger image to search within (BGR)
        template_image: np.ndarray,  # The smaller template image to find (BGR)
        threshold: float = 0.8,
        region_name_context: str = "UnnamedRegion",
        template_name_context: str = "UnnamedTemplate",
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
            A dictionary with match details:
            {
                "location_x": top_left_x_of_match_in_image,
                "location_y": top_left_y_of_match_in_image,
                "confidence": match_score (float),
                "width": template_width,
                "height": template_height
            }
            if found above threshold, otherwise None.
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
            # TM_CCOEFF_NORMED is robust to some lighting changes, range [-1, 1]
            # TM_CCORR_NORMED is also common, range [0, 1]
            # Using TM_CCOEFF_NORMED as it's often recommended.
            match_method = cv2.TM_CCOEFF_NORMED
            result_matrix = cv2.matchTemplate(image_data, template_image, match_method)
            _min_val, max_val, _min_loc, max_loc_top_left = cv2.minMaxLoc(result_matrix)

            confidence_score = float(max_val)  # max_val is the confidence for TM_CCOEFF_NORMED

            logger.debug(f"{log_prefix}: Max confidence value {confidence_score:.4f} found at {max_loc_top_left}. Required threshold: {threshold:.4f}")

            if confidence_score >= threshold:
                match_details = {
                    "location_x": int(max_loc_top_left[0]),  # Top-left x
                    "location_y": int(max_loc_top_left[1]),  # Top-left y
                    "confidence": confidence_score,
                    "width": int(tpl_w),
                    "height": int(tpl_h),
                }
                logger.info(f"{log_prefix}: TEMPLATE MATCHED. Confidence: {confidence_score:.4f} at ({match_details['location_x']},{match_details['location_y']}). Size: {tpl_w}x{tpl_h}.")
                return match_details
            else:
                logger.info(f"{log_prefix}: Template NOT matched above threshold {threshold:.4f} (max confidence was {confidence_score:.4f}).")
                return None
        except cv2.error as e_cv2:
            logger.error(f"{log_prefix}: OpenCV error during template matching: {e_cv2}. Check image/template dimensions and types.", exc_info=True)
            return None
        except Exception as e:
            logger.exception(f"{log_prefix}: Unexpected error during template matching: {e}")
            return None

    def ocr_extract_text(self, image_data: np.ndarray, region_name_context: str = "UnnamedRegion") -> Optional[Dict[str, Any]]:
        """
        Extracts text from an image using Tesseract OCR and calculates average word confidence.

        Args:
            image_data: The image (NumPy array in BGR format).
            region_name_context: Name of the region being OCR'd, for logging context.

        Returns:
            A dictionary containing:
            {
                "text": "The extracted string, joined by spaces.",
                "average_confidence": 85.5,  # Float (0-100) for actual words, or 0.0 if no confident words.
                "raw_data": pytesseract_output_dict # Raw Tesseract data for debugging.
            }
            or None if OCR fails, Tesseract is not found, or image_data is invalid.
        """
        log_prefix = f"Rgn '{region_name_context}', OCR"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data (None, empty, or not NumPy array).")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"{log_prefix}: image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}.")
            return None

        try:
            # Pytesseract generally prefers RGB, but often handles BGR correctly.
            # For maximum compatibility or if issues arise, convert:
            # image_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
            # For now, using BGR directly as it often works.

            # Using image_to_data to get detailed information including confidence scores.
            # lang='eng' is default for pytesseract, can be changed if other langs needed.
            # self.ocr_config can include options like '--psm 6' (assume a single uniform block of text).
            ocr_data_dict = pytesseract.image_to_data(image_data, lang="eng", config=self.ocr_config, output_type=Output.DICT)

            if logger.isEnabledFor(logging.DEBUG):
                # Log a snippet of raw_data if it's too large.
                # Create a summarized version for logging without overwhelming logs.
                summary_raw_data = {}
                for k, v_list in ocr_data_dict.items():
                    if isinstance(v_list, list):
                        summary_raw_data[k] = v_list[:5] + (["..."] if len(v_list) > 5 else [])
                    else:
                        summary_raw_data[k] = v_list  # Should not happen for Output.DICT
                logger.debug(f"{log_prefix}: Raw Tesseract data (summary): {summary_raw_data}")

            extracted_words: List[str] = []
            confidences: List[float] = []  # Tesseract confidences are 0-100. -1 means not applicable.

            num_entries = len(ocr_data_dict.get("level", []))  # Number of detected blocks/paragraphs/lines/words

            for i in range(num_entries):
                # Level 5 indicates a 'word' level detection.
                if ocr_data_dict["level"][i] == 5:
                    word_text = str(ocr_data_dict["text"][i]).strip()
                    try:
                        word_conf = float(ocr_data_dict["conf"][i])
                    except ValueError:
                        logger.warning(f"{log_prefix}: Could not convert confidence '{ocr_data_dict['conf'][i]}' to float for word '{word_text}'. Skipping.")
                        continue

                    # Consider a word valid if it has text and positive confidence.
                    # Tesseract uses -1 for confidence of non-word blocks or if it's very unsure.
                    if word_text and word_conf >= 0:  # Using >= 0 as sometimes 0 is a low but actual conf.
                        extracted_words.append(word_text)
                        confidences.append(word_conf)
                    elif word_text and word_conf < 0:
                        logger.debug(f"{log_prefix}: Word '{word_text}' found with non-positive confidence ({word_conf}). Ignoring for avg confidence calculation.")

            full_text = " ".join(extracted_words)
            average_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

            text_snippet = full_text[:70].replace(os.linesep, " ") + ("..." if len(full_text) > 70 else "")
            logger.info(f"{log_prefix}: Extracted (len {len(full_text)}): '{text_snippet}'. " f"Avg Word Confidence: {average_confidence:.1f}% ({len(confidences)} words).")

            return {"text": full_text, "average_confidence": average_confidence, "raw_data": ocr_data_dict}  # Return raw data for potential advanced use/debugging

        except pytesseract.TesseractNotFoundError:
            logger.error("Tesseract OCR engine is not installed or not found in your system's PATH. " "OCR functionality will be unavailable. Please install Tesseract and ensure it's in PATH.")
            return None  # Critical failure for OCR if Tesseract is missing
        except pytesseract.TesseractError as e_tess:
            logger.error(f"{log_prefix}: Tesseract error during OCR: {e_tess}", exc_info=True)
            return None
        except Exception as e:
            logger.exception(f"{log_prefix}: Unexpected error during OCR text extraction: {e}")
            return None

    def analyze_dominant_colors(self, image_data: np.ndarray, num_colors: int = 3, region_name_context: str = "UnnamedRegion") -> Optional[List[Dict[str, Any]]]:
        """
        Finds the N most dominant colors in an image using K-Means clustering.

        Args:
            image_data: The image (NumPy array in BGR format).
            num_colors: The number (K) of dominant colors to find. Must be > 0.
            region_name_context: Name of the region for logging context.

        Returns:
            A list of dictionaries, each representing a dominant color, sorted by percentage (desc):
            [{"bgr_color": [B, G, R], "percentage": 45.5}, ...],
            or None if analysis fails or image_data is unsuitable.
        """
        log_prefix = f"Rgn '{region_name_context}', DominantColorAnalysis (k={num_colors})"

        if not isinstance(image_data, np.ndarray) or image_data.size == 0:
            logger.warning(f"{log_prefix}: Invalid image_data (None, empty, or not NumPy array).")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"{log_prefix}: image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}.")
            return None
        if not (isinstance(num_colors, int) and num_colors > 0):
            logger.warning(f"{log_prefix}: Invalid num_colors '{num_colors}'. Must be int > 0. Defaulting to 3.")
            num_colors = 3

        num_pixels = image_data.shape[0] * image_data.shape[1]
        if num_pixels == 0:
            logger.warning(f"{log_prefix}: Image has zero pixels. Cannot perform K-Means.")
            return []  # Return empty list for zero pixel image
        if num_pixels < num_colors:
            logger.warning(f"{log_prefix}: Image has only {num_pixels} pixels, less than requested k={num_colors}. Reducing k to {num_pixels}.")
            num_colors = num_pixels

        try:
            logger.debug(f"{log_prefix}: Starting K-Means. Image shape: {image_data.shape}")

            # Reshape image to be a list of pixels ( W*H rows, 3 columns for BGR)
            pixels = image_data.reshape((-1, 3))
            pixels_float32 = np.float32(pixels)  # K-Means expects float32

            # Define K-Means criteria and attempts
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)  # Max 100 iter or epsilon 0.2
            attempts = 10  # Run K-Means 10 times with different initial center guesses

            # Apply K-Means
            # compactness: Sum of squared distance from each point to its corresponding center.
            # labels: Array of cluster_index for each pixel.
            # centers: Array of K cluster centers (the dominant colors).
            compactness, labels, centers_float = cv2.kmeans(pixels_float32, num_colors, None, criteria, attempts, cv2.KMEANS_RANDOM_CENTERS)

            # Calculate percentage of pixels belonging to each cluster
            unique_labels, counts = np.unique(labels.flatten(), return_counts=True)
            # total_pixels = labels.size # Should be same as num_pixels calculated earlier

            dominant_colors_result: List[Dict[str, Any]] = []
            for i, label_index in enumerate(unique_labels):
                # centers_float rows correspond to cluster indices 0 to k-1.
                # label_index should be within this range.
                if label_index < len(centers_float):
                    bgr_color_float = centers_float[label_index]
                    bgr_color_int = [int(round(c)) for c in bgr_color_float]  # Convert BGR floats to ints
                    percentage = (counts[i] / num_pixels) * 100.0
                    dominant_colors_result.append({"bgr_color": bgr_color_int, "percentage": float(percentage)})  # Ensure float
                else:
                    logger.warning(f"{log_prefix}: K-Means label index {label_index} out of bounds for centers array (len {len(centers_float)}). Skipping.")

            # Sort by percentage in descending order
            dominant_colors_result.sort(key=lambda x: x["percentage"], reverse=True)

            if not dominant_colors_result:
                logger.warning(f"{log_prefix}: No dominant colors were resolved (result list empty). This can happen with very small k or unusual images.")
                return []  # Return empty list

            formatted_results_log = [f"BGR:{d['bgr_color']}({d['percentage']:.1f}%)" for d in dominant_colors_result]
            logger.info(f"{log_prefix}: Found {len(dominant_colors_result)} colors: [{'; '.join(formatted_results_log)}]")
            return dominant_colors_result

        except cv2.error as e_cv2:
            logger.error(f"{log_prefix}: OpenCV error during K-Means: {e_cv2}. Often due to image size vs k.", exc_info=True)
            return None
        except Exception as e:
            logger.exception(f"{log_prefix}: Unexpected error during K-Means: {e}")
            return None
