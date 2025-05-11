import logging
import sys 
from pathlib import Path 
import os # Needed for os.path.exists and the tesseract_cmd workaround

try:
    import numpy as np
    import cv2 
    IMAGING_LIBS_AVAILABLE = True
except ImportError:
    IMAGING_LIBS_AVAILABLE = False
    # Optional: print a warning if critical libs are missing at module import time
    # print("WARNING (AnalysisEngine import): NumPy or OpenCV (cv2) Python library not found.")

try:
    import pytesseract
    PYTESSERACT_PYTHON_LIB_AVAILABLE = True # Indicates the Python wrapper is installed

    # --- EXPLICIT TESSERACT PATH WORKAROUND ---
    # This attempts to set the path to tesseract.exe directly.
    # This is a common workaround if the system PATH isn't picked up correctly by Python/pytesseract.
    # Ensure this path matches your Tesseract installation directory.
    _tesseract_exe_path_windows = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 

    if sys.platform.startswith('win'): # Apply only on Windows for this specific path
        if os.path.exists(_tesseract_exe_path_windows):
            pytesseract.pytesseract.tesseract_cmd = _tesseract_exe_path_windows
            # This print occurs at module import time, before full logging might be set up.
            # It's for immediate feedback during development/startup if this path is used.
            print(f"INFO (AnalysisEngine Pre-Log): Explicitly set pytesseract.tesseract_cmd to: '{_tesseract_exe_path_windows}'")
        else:
            # If the explicit path doesn't exist, pytesseract will rely on finding tesseract in PATH.
            print(f"WARNING (AnalysisEngine Pre-Log): Explicit Tesseract path not found: '{_tesseract_exe_path_windows}'. OCR will rely on system PATH.")
    # --- END OF WORKAROUND ---

except ImportError:
    PYTESSERACT_PYTHON_LIB_AVAILABLE = False
    print("WARNING (AnalysisEngine import): pytesseract Python library not found. OCR functionality will be unavailable.")

logger = logging.getLogger(__name__) # Gets a logger like "py_pixel_bot.engines.analysis_engine"

class AnalysisEngine:
    def __init__(self):
        logger.info("AnalysisEngine initialized.")
        self.imaging_libs_available = IMAGING_LIBS_AVAILABLE # Store module-level import status
        self.tesseract_engine_usable = False # Assume Tesseract engine is not usable until verified

        if not self.imaging_libs_available:
            logger.error("NumPy or OpenCV (cv2) not installed. Some analysis functions will fail.")
        else:
            logger.debug("NumPy and OpenCV Python libraries successfully imported for AnalysisEngine.")
        
        if not PYTESSERACT_PYTHON_LIB_AVAILABLE:
            logger.warning("pytesseract Python library not found (on import). OCR functionality will be unavailable.")
            # self.tesseract_engine_usable remains False
        else:
            logger.debug("pytesseract Python library successfully imported.")
            # Now check if the Tesseract *engine* can be accessed
            try:
                # This call will use pytesseract.tesseract_cmd if set, otherwise system PATH.
                tesseract_version = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract OCR version {tesseract_version} successfully accessed by pytesseract.")
                self.tesseract_engine_usable = True # Mark Tesseract engine as usable
            except pytesseract.TesseractNotFoundError:
                logger.error(
                    "Tesseract OCR engine NOT FOUND by pytesseract. "
                    "This can happen if tesseract.exe is not in your system PATH "
                    "AND the explicit path set in AnalysisEngine (if any) is incorrect or tesseract.exe is missing there. "
                    "OCR will FAIL. Please verify Tesseract installation and PATH settings."
                )
                # self.tesseract_engine_usable remains False
            except Exception as e:
                logger.warning(f"Could not get Tesseract version (or other Tesseract init error). Error: {e}. OCR might fail or be unreliable.")
                # self.tesseract_engine_usable remains False, as we couldn't confirm version.

    def analyze_pixel_color(self, image_bgr, x: int, y: int) -> tuple | None:
        """
        Checks the color of a specific pixel in the BGR image.
        Coordinates are relative to the top-left of the provided image.
        Returns (B, G, R) tuple or None on error.
        """
        if not self.imaging_libs_available:
            logger.error("analyze_pixel_color: Required imaging libraries (NumPy/OpenCV) are not available.")
            return None
        if image_bgr is None:
            logger.warning("analyze_pixel_color received None image.")
            return None

        logger.debug(f"Analyzing pixel color at relative image coordinates ({x},{y})")
        try:
            height, width = image_bgr.shape[:2]
            if 0 <= y < height and 0 <= x < width:
                pixel_bgr_values = image_bgr[y, x]
                color_tuple = tuple(int(c) for c in pixel_bgr_values)
                logger.info(f"Pixel color at relative ({x},{y}): BGR={color_tuple}")
                return color_tuple
            else:
                logger.warning(f"Pixel coordinates ({x},{y}) are out of image bounds (Image H: {height}, W: {width}).")
                return None
        except IndexError: # More specific error if x,y are somehow still bad after check (e.g. not 3 channels)
             logger.error(f"IndexError analyzing pixel color at ({x},{y}) - possibly malformed image or coords. Image shape: {image_bgr.shape}", exc_info=True)
             return None
        except Exception as e:
            logger.error(f"Error analyzing pixel color at ({x},{y}): {e}", exc_info=True)
            return None

    def analyze_average_color(self, image_bgr) -> tuple | None:
        """
        Calculates the average color of the BGR image.
        Returns (B_avg, G_avg, R_avg) tuple or None on error.
        """
        if not self.imaging_libs_available:
            logger.error("analyze_average_color: Required imaging libraries (NumPy/OpenCV) are not available.")
            return None
        if image_bgr is None:
            logger.warning("analyze_average_color received None image.")
            return None
        if image_bgr.size == 0 : # Handle empty image
            logger.warning("analyze_average_color received an empty image.")
            return None


        logger.debug(f"Analyzing average color of image with shape {image_bgr.shape}")
        try:
            # Ensure it's a 3-channel image for BGR average
            if len(image_bgr.shape) < 3 or image_bgr.shape[2] != 3:
                logger.warning(f"analyze_average_color expected 3-channel BGR image, got shape {image_bgr.shape}.")
                return None
            avg_color_bgr_float = np.mean(image_bgr, axis=(0, 1))
            avg_color_bgr_int = tuple(int(c) for c in avg_color_bgr_float)
            logger.info(f"Average image color: BGR={avg_color_bgr_int}")
            return avg_color_bgr_int
        except Exception as e:
            logger.error(f"Error analyzing average color: {e}", exc_info=True)
            return None

    def match_template(self, image_bgr, template_bgr, threshold=0.8) -> list:
        """
        Matches a template image (BGR) within a larger image (BGR) using cv2.TM_CCOEFF_NORMED.
        Returns a list of match dictionaries [{"x", "y", "width", "height", "confidence"}].
        """
        if not self.imaging_libs_available:
            logger.error("match_template: Required imaging libraries (NumPy, OpenCV) are not available.")
            return []
        if image_bgr is None or template_bgr is None:
            logger.warning("match_template: Input image_bgr or template_bgr is None.")
            return []
        if image_bgr.size == 0 or template_bgr.size == 0:
            logger.warning("match_template: Input image_bgr or template_bgr is empty.")
            return []


        logger.debug(f"Attempting to match template (shape: {template_bgr.shape}) in image (shape: {image_bgr.shape}) with threshold={threshold}")
        
        try:
            # Ensure images are suitable for matchTemplate (typically 8-bit, 1 or 3 channel)
            # cv2.matchTemplate can handle grayscale template in color image and vice-versa if channels differ,
            # but it's often better to ensure consistency or handle grayscale explicitly if intended.
            # For now, we assume BGR for both as per type hints, but add checks.

            # Convert to uint8 if not already
            if image_bgr.dtype != np.uint8: image_bgr = np.array(image_bgr, dtype=np.uint8)
            if template_bgr.dtype != np.uint8: template_bgr = np.array(template_bgr, dtype=np.uint8)

            # Ensure 3 channels if they are color images, or convert template to match image channels if one is gray
            if len(image_bgr.shape) == 2: image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
            if len(template_bgr.shape) == 2: template_bgr = cv2.cvtColor(template_bgr, cv2.COLOR_GRAY2BGR)

            if image_bgr.shape[2] != 3 or template_bgr.shape[2] != 3:
                logger.error(f"match_template: Images must be 3-channel BGR. Image shape: {image_bgr.shape}, Template shape: {template_bgr.shape}")
                return []
            
            if template_bgr.shape[0] > image_bgr.shape[0] or \
               template_bgr.shape[1] > image_bgr.shape[1]:
                logger.warning(f"Template (h={template_bgr.shape[0]}, w={template_bgr.shape[1]}) "
                               f"is larger than image (h={image_bgr.shape[0]}, w={image_bgr.shape[1]}). No match possible.")
                return []

            result = cv2.matchTemplate(image_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
            loc = np.where(result >= threshold)
            
            matches = []
            template_h, template_w = template_bgr.shape[:2]
            
            for pt_y, pt_x in zip(*loc): # Correct iteration for np.where output
                confidence = float(result[pt_y, pt_x]) 
                match_info = {
                    "x": int(pt_x), "y": int(pt_y),
                    "width": int(template_w), "height": int(template_h),
                    "confidence": confidence
                }
                matches.append(match_info)
            
            if matches:
                matches.sort(key=lambda m: m["confidence"], reverse=True)
                logger.info(f"Template matched at {len(matches)} location(s) with confidence >= {threshold}.")
                logger.debug(f"Best match details: {matches[0]}")
            else:
                logger.debug(f"Template not matched with confidence >= {threshold}.")
            return matches
            
        except cv2.error as e_cv2: # Catch specific OpenCV errors
             logger.error(f"OpenCV error during template matching: {e_cv2}", exc_info=True)
             return []
        except Exception as e:
            logger.error(f"Generic error during template matching: {e}", exc_info=True)
            return []

    def ocr_extract_text(self, image_bgr, lang='eng', psm=3, oem=3) -> str | None:
        """
        Extracts text from a BGR image using Tesseract OCR via pytesseract.
        """
        if not self.tesseract_engine_usable: # This flag is set in __init__
            logger.error("Cannot extract text: Tesseract OCR engine is not usable (not found or pytesseract library missing).")
            return None
        if not self.imaging_libs_available: # Should be redundant if tesseract_engine_usable is true
            logger.error("Cannot extract text: NumPy/OpenCV not available for image handling.")
            return None
        if image_bgr is None:
            logger.warning("ocr_extract_text received None image.")
            return None
        if image_bgr.size == 0:
            logger.warning("ocr_extract_text received an empty image.")
            return "" # Return empty string for empty image, not None (which implies error)

        logger.debug(f"Attempting OCR text extraction with lang='{lang}', psm={psm}, oem={oem} on image shape {image_bgr.shape}")
        
        try:
            # Convert BGR (OpenCV default) to RGB (Pytesseract/Pillow default)
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            
            custom_config = f'--oem {oem} --psm {psm}'
            
            # Perform OCR
            text = pytesseract.image_to_string(image_rgb, lang=lang, config=custom_config)
            
            stripped_text = text.strip()
            if stripped_text:
                logger.info(f"OCR Extracted text (first 100 chars): '{stripped_text[:100].replace('\n', ' ')}'")
            else:
                logger.info("OCR successfully ran but extracted no text or only whitespace.")
            return stripped_text
            
        except pytesseract.TesseractNotFoundError:
            # This specific error is critical if Tesseract goes missing at runtime
            # after __init__ thought it was okay (e.g., PATH changed, Tesseract uninstalled).
            logger.error("Tesseract OCR engine NOT FOUND by pytesseract at runtime. "
                         "Please ensure Tesseract is installed AND in your system's PATH "
                         "or the explicit path in AnalysisEngine is correct.")
            self.tesseract_engine_usable = False # Update runtime status
            return None
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            return None # Indicates an error during OCR processing itself

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent 
    if str(project_src_dir) not in sys.path:
        sys.path.insert(0, str(project_src_dir))

    from py_pixel_bot.core.config_manager import load_environment_variables
    load_environment_variables() 
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging() 
    
    test_logger = logging.getLogger(__name__ + "_test") # For test-specific logs
    test_logger.info("--- AnalysisEngine Test Start (with explicit Tesseract path if applicable) ---")
    
    engine = AnalysisEngine() # __init__ attempts to set tesseract_cmd and checks version
    
    if not engine.imaging_libs_available:
        test_logger.critical("NumPy or OpenCV not available. Cannot run detailed analysis tests.")
    else:
        # Create a dummy image with text for OCR testing
        img_h, img_w = 100, 350 # Wider for more text
        ocr_test_image = np.full((img_h, img_w, 3), 255, dtype=np.uint8) # White background
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_to_draw = "PyPixelBot OCR Test ABC 123 XYZ"
        # Place text with some margin
        cv2.putText(ocr_test_image, text_to_draw, (10, img_h // 2 + 10), font, 0.8, (0,0,0), 2, cv2.LINE_AA) 
        test_logger.info(f"Created dummy image with text: '{text_to_draw}' for OCR test.")
        
        # Save for inspection if needed
        # logs_dir_test = project_src_dir.parent / "logs"
        # logs_dir_test.mkdir(exist_ok=True)
        # cv2.imwrite(str(logs_dir_test / "ocr_test_image_analysis_engine.png"), ocr_test_image)
        # test_logger.debug("Saved ocr_test_image_analysis_engine.png to logs directory for inspection.")

        if engine.tesseract_engine_usable: # Check the flag set by __init__
            test_logger.info("Testing ocr_extract_text (Tesseract engine expected to be usable)...")
            extracted_text = engine.ocr_extract_text(ocr_test_image, lang='eng')
            
            if extracted_text is not None:
                test_logger.info(f"OCR Extracted: '{extracted_text}'")
                # Tesseract might add form feed '\f' or other chars, be a bit lenient in test
                normalized_extracted = extracted_text.lower().replace('\f', '').replace('\n', ' ').strip()
                normalized_drawn = text_to_draw.lower().strip()
                
                if normalized_drawn in normalized_extracted:
                    test_logger.info(f"PASS: OCR test successfully extracted drawn text (or a superset containing it).")
                else:
                    test_logger.warning(f"WARN: OCR extracted text does not precisely contain the drawn text. "
                                     f"Drawn='{normalized_drawn}', Extracted (normalized)='{normalized_extracted}'. This might be due to OCR accuracy.")
            else: 
                # This case implies an error during pytesseract.image_to_string itself,
                # even if Tesseract was initially found.
                test_logger.error("FAIL: OCR extraction returned None, indicating an error during the OCR process. Check Tesseract logs if any or image quality.")
        else:
            test_logger.warning("Skipping OCR specific tests as Tesseract engine was marked unusable during AnalysisEngine initialization.")
            test_logger.warning("If you expected OCR to work, please check Tesseract installation, PATH, and any explicit path in AnalysisEngine.")

    test_logger.info("--- AnalysisEngine Test End ---")