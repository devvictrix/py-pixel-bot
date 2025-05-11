import logging
import sys 
from pathlib import Path 

try:
    from PIL import ImageGrab
    import numpy as np
    import cv2
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)

class CaptureEngine:
    def __init__(self):
        logger.info("CaptureEngine initialized.")
        if not PIL_AVAILABLE:
            logger.error("Pillow (PIL), NumPy, or OpenCV (cv2) not installed. Screen capture will not function.")
        else:
            logger.debug("Pillow, NumPy, and OpenCV successfully imported for CaptureEngine.")
        self.pil_available = PIL_AVAILABLE

    def capture_region(self, x: int, y: int, width: int, height: int):
        if not self.pil_available:
            logger.error("Cannot capture region: Required imaging libraries (Pillow/NumPy/cv2) are not available.")
            return None

        logger.debug(f"Attempting to capture screen region: x={x}, y={y}, w={width}, h={height}")
        
        if width <= 0 or height <= 0:
            logger.error(f"Invalid region dimensions: width ({width}) and height ({height}) must be positive.")
            return None

        try:
            bbox = (x, y, x + width, y + height)
            pil_image = ImageGrab.grab(bbox=bbox, all_screens=True) 
            
            if pil_image is None:
                logger.error("ImageGrab.grab() returned None. Capture failed.")
                return None

            cv_image_rgb = np.array(pil_image)
            cv_image_bgr = cv2.cvtColor(cv_image_rgb, cv2.COLOR_RGB2BGR)
            
            logger.info(f"Region captured successfully: shape={cv_image_bgr.shape} at ({x},{y})")
            return cv_image_bgr
            
        except Exception as e:
            logger.error(f"Error during screen capture with Pillow: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent 
    if str(project_src_dir) not in sys.path:
        sys.path.insert(0, str(project_src_dir))

    from py_pixel_bot.core.config_manager import load_environment_variables
    load_environment_variables() 
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging() 

    test_logger = logging.getLogger(__name__ + "_test") 
    test_logger.info("--- CaptureEngine Test Start ---")
    
    engine = CaptureEngine()
    
    if not engine.pil_available:
        test_logger.critical("Pillow/NumPy/cv2 not available. Cannot run capture test.")
    else:
        test_x, test_y, test_w, test_h = 50, 50, 200, 200 
        test_logger.info(f"Attempting test capture of screen region: x={test_x}, y={test_y}, w={test_w}, h={test_h}")
        
        captured_image = engine.capture_region(x=test_x, y=test_y, width=test_w, height=test_h)
        
        if captured_image is not None:
            test_logger.info(f"Test capture successful. Image shape: {captured_image.shape}, dtype: {captured_image.dtype}")
            try:
                logs_dir = project_src_dir.parent / "logs"
                logs_dir.mkdir(exist_ok=True)
                save_path = logs_dir / "test_capture_engine_output.png"
                # Need cv2 import here for imwrite if not already available globally for the test
                import cv2 
                cv2.imwrite(str(save_path), captured_image)
                test_logger.info(f"Test capture saved to: {save_path}")
            except Exception as e:
                test_logger.error(f"Could not save test_capture.png: {e}", exc_info=True)
        else:
            test_logger.error("Test capture failed (returned None). Check logs for errors.")
            
    test_logger.info("--- CaptureEngine Test End ---")