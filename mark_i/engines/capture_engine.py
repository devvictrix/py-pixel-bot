import logging
import platform
from typing import Optional, Dict, Any

import numpy as np
from PIL import Image, ImageGrab # For screen capture, especially on Windows
import cv2 # For color conversion

logger = logging.getLogger(__name__)

class CaptureEngine:
    """
    Responsible for capturing specified screen regions.
    Currently uses Pillow's ImageGrab for Windows, which is generally efficient.
    Converts captures to OpenCV (NumPy BGR) format.
    """

    def __init__(self):
        self.system = platform.system()
        logger.info(f"CaptureEngine initialized for system: {self.system}.")
        if self.system != "Windows":
            logger.warning(
                f"CaptureEngine currently optimized for Windows using Pillow.ImageGrab. "
                f"Capture on '{self.system}' might be slower or require alternative methods "
                f"(e.g., mss, or direct OpenCV if backend supports it well for this OS)."
            )
        # TODO: Investigate and implement optimal capture methods for Linux and macOS
        # For Linux: python-mss, Scrot via subprocess, or Xlib.
        # For macOS: python-mss, screencapture via subprocess.
        # OpenCV's VideoCapture can sometimes work but might be slow or require specific backends.

    def capture_region(self, region_spec: Dict[str, Any]) -> Optional[np.ndarray]:
        """
        Captures the specified screen region.

        Args:
            region_spec: A dictionary defining the region, expected to have
                         'x', 'y', 'width', 'height' keys with integer values.
                         Example: {"name": "my_region", "x": 100, "y": 100, "width": 200, "height": 150}

        Returns:
            A NumPy array representing the captured image in BGR format (OpenCV standard),
            or None if capture fails or region_spec is invalid.
        """
        region_name = region_spec.get("name", "UnnamedRegion")
        x = region_spec.get("x")
        y = region_spec.get("y")
        width = region_spec.get("width")
        height = region_spec.get("height")

        if not all(isinstance(val, int) for val in [x, y, width, height]):
            logger.error(
                f"Capture failed for region '{region_name}': Invalid region specification. "
                f"Coordinates and dimensions must be integers. Got: x={x}, y={y}, w={width}, h={height}."
            )
            return None
        
        if width <= 0 or height <= 0:
            logger.error(
                f"Capture failed for region '{region_name}': Width ({width}) and Height ({height}) must be positive."
            )
            return None

        # Define the bounding box for capture: (left, top, right, bottom)
        bbox = (x, y, x + width, y + height)
        logger.debug(f"Attempting to capture region '{region_name}' with bbox: {bbox}")

        try:
            # Using Pillow's ImageGrab, which is generally good on Windows.
            # For other OS, this might need to be conditional or use a different library.
            # ImageGrab.grab() returns a PIL Image object in RGB format.
            captured_pil_image = ImageGrab.grab(bbox=bbox, all_screens=True) # all_screens=True for multi-monitor
            
            if captured_pil_image:
                logger.debug(f"Successfully captured region '{region_name}' with Pillow.ImageGrab. Mode: {captured_pil_image.mode}, Size: {captured_pil_image.size}")
                # Convert PIL Image (RGB or RGBA) to OpenCV format (NumPy array, BGR)
                # 1. Convert to NumPy array
                img_np_rgb = np.array(captured_pil_image)
                
                # 2. Convert RGB/RGBA to BGR for OpenCV consistency
                if captured_pil_image.mode == 'RGB':
                    img_cv_bgr = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
                elif captured_pil_image.mode == 'RGBA':
                    # If RGBA, convert to BGR (discarding alpha for now, or could convert to BGRA if needed later)
                    img_cv_bgr = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGBA2BGR)
                    logger.debug(f"Region '{region_name}': RGBA image captured, converted to BGR (alpha channel discarded).")
                else:
                    logger.warning(f"Region '{region_name}': Captured image in unexpected mode '{captured_pil_image.mode}'. Attempting direct BGR conversion if 3 channels.")
                    if img_np_rgb.shape[2] == 3: # Assume it might be BGR already if 3 channels and not RGB
                        img_cv_bgr = img_np_rgb
                    else: # Fallback, try to convert to RGB then BGR
                         pil_rgb_fallback = captured_pil_image.convert("RGB")
                         img_np_rgb_fallback = np.array(pil_rgb_fallback)
                         img_cv_bgr = cv2.cvtColor(img_np_rgb_fallback, cv2.COLOR_RGB2BGR)


                logger.debug(f"Region '{region_name}' converted to OpenCV BGR format. Shape: {img_cv_bgr.shape}")
                return img_cv_bgr
            else:
                # This case should be rare with ImageGrab if bbox is valid and on screen,
                # but good to handle.
                logger.error(f"Capture failed for region '{region_name}': ImageGrab.grab() returned None.")
                return None

        except Exception as e:
            # This can catch various errors, e.g., if coordinates are off-screen
            # for some capture backends, or permissions issues on some OS (though ImageGrab is usually robust).
            logger.error(
                f"Capture failed for region '{region_name}' with bbox {bbox}. Error: {e}",
                exc_info=True # Include stack trace for unexpected errors
            )
            # More specific error handling could be added here if common exceptions are identified.
            # For example, on Linux without a display server, ImageGrab will fail.
            if "cannot open display" in str(e).lower() or "xcb" in str(e).lower():
                logger.critical("Failed to capture screen: No display server found or accessible (e.g., running in a headless environment or missing X server configuration on Linux).")
            elif "screen grab failed" in str(e).lower(): # Common mss error message if used
                logger.error("Screen grab failed, possibly due to display server issues or permissions.")

            return None

if __name__ == "__main__":
    # Basic test for CaptureEngine
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Attempt to find primary screen dimensions for a test region
    try:
        screen_width, screen_height = pyautogui.size()
        logger.info(f"Detected screen size: {screen_width}x{screen_height}")
        test_region = {
            "name": "test_capture_center_screen",
            "x": screen_width // 4,
            "y": screen_height // 4,
            "width": screen_width // 2,
            "height": screen_height // 2
        }
        if test_region["width"] <=0 or test_region["height"] <=0:
            raise ValueError("Calculated test region has non-positive dimensions.")
    except Exception as e:
        logger.warning(f"Could not get screen size using pyautogui for test region setup ({e}). Using default small region.")
        test_region = {"name": "test_capture_default", "x": 0, "y": 0, "width": 100, "height": 100}


    engine = CaptureEngine()
    logger.info(f"Attempting to capture test region: {test_region}")
    image = engine.capture_region(test_region)

    if image is not None:
        logger.info(f"Capture successful! Image shape: {image.shape}, dtype: {image.dtype}")
        try:
            # Display the captured image using OpenCV (requires a GUI environment)
            cv2.imshow(f"Test Capture: {test_region['name']}", image)
            logger.info("Displaying captured image. Press any key in the image window to close.")
            cv2.waitKey(0)  # Wait for a key press
            cv2.destroyAllWindows()
            logger.info("Image window closed.")
        except cv2.error as e_cv:
            logger.warning(f"OpenCV error while trying to display image: {e_cv}. This can happen in headless environments.")
        except Exception as e_disp:
            logger.warning(f"Could not display image using OpenCV: {e_disp}")
            # Fallback: Try to save it
            try:
                save_path = "test_capture.png"
                cv2.imwrite(save_path, image)
                logger.info(f"Captured image saved to {os.path.abspath(save_path)}")
            except Exception as e_save:
                logger.error(f"Failed to save test capture: {e_save}")
    else:
        logger.error("Capture failed.")

    # Test with invalid region
    logger.info("\nAttempting to capture invalid region (negative width)...")
    invalid_region = {"name": "invalid_width", "x": 0, "y": 0, "width": -100, "height": 100}
    engine.capture_region(invalid_region)

    logger.info("\nAttempting to capture invalid region (non-integer)...")
    invalid_region_type = {"name": "invalid_type", "x": 0, "y": 0, "width": "100a", "height": 100}
    engine.capture_region(invalid_region_type) # type: ignore