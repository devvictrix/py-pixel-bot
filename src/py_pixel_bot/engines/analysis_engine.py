import logging
from typing import Optional, Dict, Any, List

import cv2
import numpy as np
import pytesseract
from pytesseract import Output
# from PIL import Image # Not directly used here, but good to remember it's available for CTkImage

logger = logging.getLogger(__name__)
# Ensure APP_ROOT_LOGGER_NAME is defined if used for hierarchical logging (e.g. in main or logging_setup)
# For now, assume __name__ resolves correctly under py_pixel_bot.engines

class AnalysisEngine:
    """
    Performs various visual analyses on captured image regions (NumPy BGR arrays).
    """

    def __init__(self, ocr_command: Optional[str] = None, ocr_config: str = ""):
        """
        Initializes the AnalysisEngine.

        Args:
            ocr_command: The command or path to the Tesseract executable.
                         If None, pytesseract will try to find it in PATH.
            ocr_config: Additional Tesseract configuration string (e.g., '--psm 6').
        """
        self.ocr_command = ocr_command
        if self.ocr_command:
            try:
                pytesseract.pytesseract.tesseract_cmd = self.ocr_command
                logger.info(f"Tesseract command explicitly set to: '{self.ocr_command}'")
            except Exception as e: # Catch potential errors if path is invalid during assignment (though unlikely)
                logger.error(f"Error setting tesseract_cmd to '{self.ocr_command}': {e}. Pytesseract will try PATH.")
        else:
            logger.info("Tesseract command not specified, pytesseract will search in PATH.")
            
        self.ocr_config = ocr_config
        logger.info(f"AnalysisEngine initialized. Tesseract OCR config: '{self.ocr_config if self.ocr_config else 'Default'}'.")


    def analyze_pixel_color(
        self,
        image_data: np.ndarray,
        x: int,
        y: int,
        expected_bgr: List[int], # Changed from list[int] for older Python type hint compatibility
        tolerance: int = 0,
    ) -> bool:
        """
        Checks the color of a specific pixel against an expected BGR color.

        Args:
            image_data: The image (NumPy array in BGR format).
            x: The x-coordinate of the pixel (relative to the image_data).
            y: The y-coordinate of the pixel (relative to the image_data).
            expected_bgr: A list of 3 integers representing the expected BGR color [B, G, R].
            tolerance: The allowed difference for each B, G, R component (0 to 255).

        Returns:
            True if the pixel color is within tolerance of the expected color, False otherwise.
        """
        if image_data is None:
            logger.warning("analyze_pixel_color: image_data is None. Cannot perform analysis.")
            return False
        
        # Validate coordinates and expected_bgr structure
        if not (isinstance(x, int) and isinstance(y, int)):
            logger.warning(f"analyze_pixel_color: Coordinates ({x},{y}) are not integers.")
            return False
        if not (isinstance(expected_bgr, list) and len(expected_bgr) == 3 and all(isinstance(c, int) for c in expected_bgr)):
            logger.warning(f"analyze_pixel_color: expected_bgr '{expected_bgr}' is not a list of 3 integers.")
            return False
        if not (isinstance(tolerance, int) and 0 <= tolerance <= 255):
            logger.warning(f"analyze_pixel_color: Tolerance '{tolerance}' is not a valid integer between 0-255. Using 0.")
            tolerance = 0

        height, width, channels = image_data.shape
        if channels != 3:
            logger.warning(f"analyze_pixel_color: image_data does not have 3 channels (BGR). Shape: {image_data.shape}")
            return False
        if not (0 <= y < height and 0 <= x < width):
            logger.warning(
                f"analyze_pixel_color: Pixel ({x},{y}) is out of bounds for image size ({width}x{height})."
            )
            return False

        actual_bgr = image_data[y, x]
        logger.debug(
            f"Pixel color check at ({x},{y}): Actual BGR {actual_bgr.tolist()}, Expected BGR {expected_bgr}, Tolerance {tolerance}"
        )

        return all(
            abs(int(actual) - int(expected)) <= tolerance # Ensure components are int for abs
            for actual, expected in zip(actual_bgr, expected_bgr)
        )

    def analyze_average_color(self, image_data: np.ndarray) -> Optional[List[int]]:
        """
        Calculates the average BGR color of an image.

        Args:
            image_data: The image (NumPy array in BGR format).

        Returns:
            A list of 3 integers representing the average BGR color [B, G, R], or None if image_data is invalid.
        """
        if image_data is None or image_data.size == 0:
            logger.warning("analyze_average_color: image_data is None or empty. Cannot perform analysis.")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"analyze_average_color: image_data is not a valid BGR image. Shape: {image_data.shape}")
            return None

        # Calculate mean across height and width (axis 0 and 1)
        avg_bgr_float = np.mean(image_data, axis=(0, 1))
        avg_bgr_int = avg_bgr_float.astype(int).tolist() # Convert to int list [B, G, R]
        logger.debug(f"Average color of image (shape: {image_data.shape}): BGR {avg_bgr_int}")
        return avg_bgr_int

    def match_template(
        self, image: np.ndarray, template: np.ndarray, threshold: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a template within an image using OpenCV's template matching (TM_CCOEFF_NORMED).

        Args:
            image: The image to search within (BGR format).
            template: The template image to find (BGR format).
            threshold: The minimum confidence score (0.0 to 1.0) to consider a match.

        Returns:
            A dictionary with match details:
            {'location': (x,y_top_left_of_match_in_image), 'confidence': score, 
             'width': template_width, 'height': template_height}
            if found above threshold, otherwise None.
        """
        if image is None or template is None or image.size == 0 or template.size == 0:
            logger.warning("match_template: Image or template is None or empty. Cannot perform matching.")
            return None
        if not (isinstance(threshold, float) and 0.0 <= threshold <= 1.0):
            logger.warning(f"match_template: Invalid threshold '{threshold}'. Must be float between 0.0-1.0. Using 0.8.")
            threshold = 0.8
            
        if image.ndim != 3 or template.ndim != 3 or image.shape[2] != 3 or template.shape[2] != 3:
            logger.warning(f"match_template: Image (shape {image.shape}) or template (shape {template.shape}) is not a valid BGR image.")
            return None

        img_h, img_w = image.shape[:2]
        tpl_h, tpl_w = template.shape[:2]

        if img_h < tpl_h or img_w < tpl_w:
            logger.warning(
                f"match_template: Template (h={tpl_h}, w={tpl_w}) is larger than "
                f"image (h={img_h}, w={img_w}). Cannot perform matching."
            )
            return None

        try:
            # TM_CCOEFF_NORMED is generally good for varying lighting if normalized
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result) # max_loc is (x,y) of top-left

            logger.debug(
                f"Template matching: Max confidence value {max_val:.4f} found at {max_loc}. Required threshold: {threshold:.4f}"
            )

            if max_val >= threshold:
                match_details = {
                    "location": max_loc,  # (x, y) top-left coordinates of the found template in the image
                    "confidence": float(max_val), # Ensure float
                    "width": tpl_w,
                    "height": tpl_h,
                }
                logger.info(
                    f"Template matched with confidence {max_val:.4f} at {max_loc} (Threshold: {threshold:.4f}). Template size: {tpl_w}x{tpl_h}."
                )
                return match_details
            else:
                logger.debug(f"Template not matched above threshold {threshold:.4f} (max confidence was {max_val:.4f}).")
                return None
        except cv2.error as e_cv2:
            logger.error(f"OpenCV error during template matching: {e_cv2}. This can happen if the template dimensions are invalid relative to the image after some internal processing.")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during template matching: {e}")
            return None

    def ocr_extract_text(self, image_data: np.ndarray, region_name_context: str = "UnknownRegion") -> Optional[Dict[str, Any]]:
        """
        Extracts text from an image using Tesseract OCR and calculates average word confidence.

        Args:
            image_data: The image (NumPy array in BGR format).
            region_name_context: Name of the region being OCR'd, for logging context.

        Returns:
            A dictionary containing:
            {
                "text": "The extracted string, joined by spaces",
                "average_confidence": 85.5,  # Float, 0-100 for actual words, or 0.0 if no confident words
                "raw_data": pytesseract_output_dict # The raw dict from image_to_data for debugging
            }
            or None if OCR fails, Tesseract is not found, or image_data is invalid.
        """
        if image_data is None or image_data.size == 0:
            logger.warning(f"OCR for region '{region_name_context}': image_data is None or empty. Cannot perform OCR.")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"OCR for region '{region_name_context}': image_data is not a valid BGR image. Shape: {image_data.shape}")
            return None

        try:
            # Pytesseract generally prefers RGB, but often handles BGR.
            # Explicit conversion can sometimes improve reliability.
            # image_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
            # For now, passing BGR directly as it has worked. If issues, uncomment conversion.
            
            # Use Tesseract's page segmentation mode that assumes a single uniform block of text if config not specific.
            # Custom config from self.ocr_config can override this.
            # Example: '--psm 6' for assuming a single uniform block of text.
            # Default language is 'eng'.
            ocr_data_dict = pytesseract.image_to_data(
                image_data, lang="eng", config=self.ocr_config, output_type=Output.DICT
            )
            
            if logger.isEnabledFor(logging.DEBUG): # Avoid costly formatting if not needed
                # Log a snippet or summary of raw_data if it's too large
                log_raw_data = {k: (v[:10] if isinstance(v, list) and len(v) > 10 else v) for k,v in ocr_data_dict.items()}
                logger.debug(f"OCR for region '{region_name_context}': Raw pytesseract data (summary): {log_raw_data}")

            extracted_words: List[str] = []
            confidences: List[float] = []
            num_entries = len(ocr_data_dict.get("level", [])) # Get length safely

            for i in range(num_entries):
                # Only consider entries that are actual words (level 5)
                # and have a positive confidence (Tesseract uses -1 for non-word blocks or uncertain parts)
                if ocr_data_dict["level"][i] == 5: # Level 5 is word
                    word_text = ocr_data_dict["text"][i].strip()
                    word_conf = float(ocr_data_dict["conf"][i])
                    if word_text and word_conf > 0: # Only append if text exists and confidence is positive
                        extracted_words.append(word_text)
                        confidences.append(word_conf)
            
            full_text = " ".join(extracted_words)
            average_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            logger.info(
                f"OCR for region '{region_name_context}': Extracted text (len {len(full_text)}): '{full_text[:70].replace(os.linesep, ' ')}...', "
                f"Avg Word Confidence: {average_confidence:.1f}% (from {len(confidences)} words)."
            )

            return {
                "text": full_text,
                "average_confidence": average_confidence,
                "raw_data": ocr_data_dict # Included for potential advanced debugging or future features
            }

        except pytesseract.TesseractNotFoundError:
            logger.error(
                "Tesseract OCR engine is not installed or not found in your system's PATH. "
                "OCR functionality will not work. Please install Tesseract and ensure it's in PATH."
            )
            return None # Critical failure for OCR
        except Exception as e:
            logger.exception(f"OCR for region '{region_name_context}': An unexpected error occurred during text extraction. Error: {e}")
            return None

    def analyze_dominant_colors(
        self, image_data: np.ndarray, num_colors: int = 3, region_name_context: str = "UnknownRegion"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Finds the N most dominant colors in an image using K-Means clustering.

        Args:
            image_data: The image (NumPy array in BGR format).
            num_colors: The number (K) of dominant colors to find. Must be > 0.
            region_name_context: Name of the region for logging context.

        Returns:
            A list of dictionaries, each representing a dominant color, sorted by percentage:
            [{"bgr_color": [B, G, R], "percentage": 45.5}, ...], 
            or None if analysis fails or image_data is unsuitable.
        """
        if image_data is None or image_data.size == 0:
            logger.warning(f"Dominant color analysis for region '{region_name_context}': image_data is None or empty.")
            return None
        if image_data.ndim != 3 or image_data.shape[2] != 3:
            logger.warning(f"Dominant color analysis for region '{region_name_context}': image_data is not a valid BGR image. Shape: {image_data.shape}")
            return None
        if not (isinstance(num_colors, int) and num_colors > 0):
            logger.warning(f"Dominant color analysis for region '{region_name_context}': Invalid num_colors '{num_colors}'. Must be int > 0. Defaulting to 3.")
            num_colors = 3
        
        # K-Means requires at least as many samples (pixels) as clusters (num_colors)
        num_pixels = image_data.shape[0] * image_data.shape[1]
        if num_pixels < num_colors :
            logger.warning(
                f"Dominant color analysis for region '{region_name_context}': Image has only {num_pixels} pixels, "
                f"which is less than the requested {num_colors} dominant colors. Reducing k to {num_pixels} or returning None if 0."
            )
            if num_pixels == 0: return None
            num_colors = num_pixels # Adjust k

        try:
            logger.debug(
                f"Dominant color analysis for region '{region_name_context}': Starting with k={num_colors}. Image shape: {image_data.shape}"
            )
            
            pixels = image_data.reshape((-1, 3)) # Reshape to (W*H, 3)
            pixels_float32 = np.float32(pixels)   # Convert to float32 for K-Means

            # Define K-Means criteria: (type, max_iter, epsilon)
            # cv2.TERM_CRITERIA_EPS: stop when specified accuracy (epsilon) is reached.
            # cv2.TERM_CRITERIA_MAX_ITER: stop after max_iter iterations.
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2) # Max 100 iterations or epsilon 0.2
            attempts = 10 # Number of times algorithm is executed with different initial labellings

            compactness, labels, centers = cv2.kmeans(
                pixels_float32, num_colors, None, criteria, attempts, cv2.KMEANS_RANDOM_CENTERS
            )
            # `centers` are the dominant colors in float BGR format.
            # `labels` is an array assigning each pixel to a cluster (0 to k-1).

            # Calculate the percentage of pixels belonging to each cluster
            unique_labels, counts = np.unique(labels, return_counts=True)
            total_pixels = pixels_float32.shape[0] # Same as num_pixels above
            
            dominant_colors_result: List[Dict[str, Any]] = []
            for i, label_val in enumerate(unique_labels):
                # Ensure center corresponds to this unique label index if K-Means returns fewer than `num_colors` centers
                # (e.g., if image had very few unique colors). `centers` rows correspond to cluster indices 0 to k-1.
                # `unique_labels` might be a subset if some clusters end up empty or merged.
                if label_val < len(centers):
                    bgr_color_float = centers[label_val]
                    bgr_color_int = [int(c) for c in bgr_color_float] # Convert float centers to int BGR
                    percentage = (counts[i] / total_pixels) * 100.0
                    dominant_colors_result.append({"bgr_color": bgr_color_int, "percentage": float(percentage)})
                else:
                    logger.warning(f"Dominant color analysis: Label value {label_val} is out of bounds for centers array (len {len(centers)}). Skipping this label.")

            
            # Sort by percentage in descending order
            dominant_colors_result.sort(key=lambda x: x["percentage"], reverse=True)

            if not dominant_colors_result:
                 logger.warning(f"Dominant color analysis for region '{region_name_context}' (k={num_colors}): No dominant colors were resolved (result list is empty).")
                 return None # Or empty list depending on how RulesEngine handles it

            formatted_results = [f"BGR: {d['bgr_color']}, Perc: {d['percentage']:.1f}%" for d in dominant_colors_result]
            logger.info(
                f"Dominant color analysis for region '{region_name_context}' (k={num_colors}): Found {len(dominant_colors_result)} colors: [{'; '.join(formatted_results)}]"
            )
            return dominant_colors_result

        except cv2.error as e_cv2:
            logger.error(
                f"Dominant color analysis for region '{region_name_context}': OpenCV error during K-Means (k={num_colors}). Error: {e_cv2}. "
                "This can happen if image is too small for k, or other internal OpenCV issues."
            )
            return None
        except Exception as e:
            logger.exception(
                f"Dominant color analysis for region '{region_name_context}': Unexpected error (k={num_colors}). Error: {e}"
            )
            return None