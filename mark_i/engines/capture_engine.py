import logging
import platform
from typing import Optional, Dict, Any

import numpy as np
from PIL import Image, ImageGrab  # Pillow's ImageGrab for screen capture
import cv2  # OpenCV for color conversion (RGB/RGBA from PIL to BGR for internal use)

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.capture_engine")


class CaptureEngine:
    """
    Responsible for capturing specified screen regions.

    Currently, it primarily uses Pillow's ImageGrab, which is generally efficient
    and well-suited for Windows. It converts captures to OpenCV's standard BGR
    NumPy array format for consistent use by other engine components.

    Future considerations could include platform-specific capture libraries like 'mss'
    for performance optimization or broader cross-platform robustness if ImageGrab
    shows limitations on macOS or Linux.
    """

    def __init__(self):
        """Initializes the CaptureEngine and logs the current operating system."""
        self.system = platform.system()
        logger.info(f"CaptureEngine initialized. Operating System: {self.system}.")

        if self.system == "Windows":
            logger.info("Using Pillow's ImageGrab.grab() for screen capture on Windows.")
        elif self.system == "Darwin":  # macOS
            logger.warning(
                "Using Pillow's ImageGrab.grab() on macOS. For optimal performance or "
                "handling specific display server issues (e.g., Wayland vs X11 on Linux), "
                "alternative libraries like 'mss' or OS-specific commands might be "
                "considered in future versions if ImageGrab proves insufficient."
            )
            # macOS specific note: User may need to grant screen recording permission to the terminal/app.
        elif self.system == "Linux":
            logger.warning(
                "Using Pillow's ImageGrab.grab() on Linux. This might require 'scrot' "
                "or 'gnome-screenshot' to be installed, or an X server to be running. "
                "For headless environments or Wayland, this may fail. Consider 'mss' or "
                "other X11/Wayland specific tools for more robust Linux capture in future."
            )
        else:
            logger.warning(f"Unsupported or unrecognized operating system: {self.system}. Screen capture might not work as expected.")

    def capture_region(self, region_spec: Dict[str, Any]) -> Optional[np.ndarray]:
        """
        Captures the specified screen region defined by its coordinates and dimensions.

        The region_spec dictionary must contain 'x', 'y', 'width', and 'height' keys
        with integer values representing the top-left corner coordinates and the
        dimensions of the rectangle to capture.

        Args:
            region_spec: A dictionary defining the region. Example:
                         {"name": "my_region", "x": 100, "y": 100, "width": 200, "height": 150}

        Returns:
            A NumPy array representing the captured image in BGR format (OpenCV standard),
            or None if the capture fails, region_spec is invalid, or dimensions are non-positive.
        """
        region_name = region_spec.get("name", "UnnamedRegion")
        log_prefix = f"Rgn '{region_name}', Capture"

        # Validate region_spec parameters
        x = region_spec.get("x")
        y = region_spec.get("y")
        width = region_spec.get("width")
        height = region_spec.get("height")

        if not all(isinstance(val, int) for val in [x, y, width, height]):
            logger.error(
                f"{log_prefix}: Failed. Invalid region specification. "
                f"Coordinates and dimensions must all be integers. Got: x={x}({type(x)}), y={y}({type(y)}), "
                f"w={width}({type(width)}), h={height}({type(height)})."
            )
            return None

        # Ensure width and height are positive
        if width <= 0 or height <= 0:
            logger.error(f"{log_prefix}: Failed. Width ({width}) and Height ({height}) must be positive.")
            return None

        # Pillow's ImageGrab.grab() uses a bounding box: (left, top, right, bottom)
        # Ensure these are integers.
        left, top = int(x), int(y)
        right, bottom = int(x + width), int(y + height)
        bbox = (left, top, right, bottom)

        logger.debug(f"{log_prefix}: Attempting capture with BBox (L,T,R,B): {bbox}")

        try:
            # ImageGrab.grab() is used. `all_screens=True` is important for multi-monitor setups
            # to ensure coordinates are interpreted correctly across the entire virtual screen.
            # It returns a PIL Image object.
            captured_pil_image = ImageGrab.grab(bbox=bbox, all_screens=True)

            if captured_pil_image is None:
                # This case should be rare if bbox is valid and on screen for supported OS.
                logger.error(f"{log_prefix}: Failed. Pillow ImageGrab.grab() returned None for BBox {bbox}.")
                return None

            logger.debug(f"{log_prefix}: Pillow capture successful. Mode: {captured_pil_image.mode}, Size: {captured_pil_image.size}. Converting to OpenCV BGR format.")

            # Convert PIL Image (typically RGB or RGBA) to an OpenCV NumPy array
            img_np_intermediate = np.array(captured_pil_image)

            # Convert color format from PIL's mode to OpenCV's BGR standard
            if captured_pil_image.mode == "RGB":
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_RGB2BGR)
            elif captured_pil_image.mode == "RGBA":
                # Convert RGBA to BGR, effectively discarding the alpha channel.
                # If alpha is needed later, convert to BGRA: cv2.COLOR_RGBA2BGRA
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_RGBA2BGR)
                logger.debug(f"{log_prefix}: RGBA image captured, converted to BGR (alpha channel discarded).")
            elif captured_pil_image.mode == "L":  # Grayscale
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_GRAY2BGR)
                logger.debug(f"{log_prefix}: Grayscale (L mode) image captured, converted to BGR.")
            elif captured_pil_image.mode == "P":  # Palette-based
                logger.warning(f"{log_prefix}: Palette (P mode) image captured. Converting to RGB then BGR. Colors might be inaccurate if palette is limited.")
                pil_rgb_converted = captured_pil_image.convert("RGB")
                img_np_rgb_converted = np.array(pil_rgb_converted)
                img_cv_bgr = cv2.cvtColor(img_np_rgb_converted, cv2.COLOR_RGB2BGR)
            else:
                # For other modes (e.g., '1', 'CMYK'), conversion might be more complex or lossy.
                # Attempt a general conversion to RGB first, then to BGR.
                logger.warning(f"{log_prefix}: Captured image in unexpected PIL mode '{captured_pil_image.mode}'. Attempting conversion via RGB to BGR. This might be lossy or fail.")
                try:
                    pil_rgb_fallback = captured_pil_image.convert("RGB")
                    img_np_rgb_fallback = np.array(pil_rgb_fallback)
                    img_cv_bgr = cv2.cvtColor(img_np_rgb_fallback, cv2.COLOR_RGB2BGR)
                except Exception as e_conv_fallback:
                    logger.error(f"{log_prefix}: Failed to convert image from mode '{captured_pil_image.mode}' to BGR: {e_conv_fallback}", exc_info=True)
                    return None

            logger.info(f"{log_prefix}: Capture and conversion to BGR successful. Final shape: {img_cv_bgr.shape}")
            return img_cv_bgr

        except Exception as e:
            # Catch various errors:
            # - Coordinates off-screen (can happen with some backends/OS settings).
            # - Permissions issues (especially on macOS for screen recording, or Linux without proper X11 setup).
            # - Pillow/OS level errors if backend tools (like scrot on Linux) are missing.
            logger.error(f"{log_prefix}: Capture FAILED for BBox {bbox}. Error: {e}", exc_info=True)  # Include stack trace for debugging unexpected errors
            if "್ರೀನ್ಶಾಟ್" in str(e).lower() or "gnome-screenshot" in str(e).lower() or "scrot" in str(e).lower():
                logger.error(f"{log_prefix}: Pillow ImageGrab on Linux might be missing a required backend tool (like scrot or gnome-screenshot). Please ensure one is installed.")
            elif "cannot open display" in str(e).lower() or "xcb" in str(e).lower() or "X server" in str(e).lower():
                logger.critical(
                    f"{log_prefix}: Failed to capture screen: No display server found or accessible (e.g., running in a headless environment, Wayland without XWayland, or missing X server configuration on Linux)."
                )
            # Add more specific error message interpretations if common issues are found for other OS.
            return None


if __name__ == "__main__":
    # Basic test for CaptureEngine
    # Ensure logging is set up for the test to see output
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s")

    logger.info("--- Running CaptureEngine Self-Test ---")

    # Attempt to get primary screen dimensions for a test region.
    # This part uses pyautogui, which is an optional dependency for this test.
    screen_width, screen_height = 0, 0
    try:
        import pyautogui  # Local import for test only

        screen_width, screen_height = pyautogui.size()
        logger.info(f"Test: Detected screen size using pyautogui: {screen_width}x{screen_height}")
        # Define a reasonably sized test region, e.g., a quarter of the screen offset from top-left
        test_x = screen_width // 8
        test_y = screen_height // 8
        test_w = screen_width // 4
        test_h = screen_height // 4

        if test_w <= 0 or test_h <= 0:  # Handle tiny screens or detection issues
            raise ValueError("Calculated test region has non-positive dimensions.")

        test_region = {"name": "test_capture_center_screen_quarter", "x": test_x, "y": test_y, "width": test_w, "height": test_h}
    except Exception as e_pg:
        logger.warning(f"Test: Could not get screen size using pyautogui ({e_pg}). Using default small region at (0,0).")
        test_region = {"name": "test_capture_default_0_0_100_100", "x": 0, "y": 0, "width": 100, "height": 100}

    engine = CaptureEngine()
    logger.info(f"Test: Attempting to capture test region: {test_region}")
    image = engine.capture_region(test_region)

    if image is not None:
        logger.info(f"Test: Capture successful! Image shape: {image.shape}, dtype: {image.dtype}")

        # Attempt to display the captured image using OpenCV (requires a GUI environment)
        # This part is for visual verification during manual testing.
        try:
            cv2.imshow(f"Test Capture: {test_region.get('name', 'Default')}", image)
            logger.info("Displaying captured image. Press any key in the image window to close.")
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            logger.info("Image window closed.")
        except cv2.error as e_cv_display:
            logger.warning(f"Test: OpenCV error while trying to display image: {e_cv_display}. This can happen in headless environments or if no windowing system is available.")
            # Fallback: Try to save the image if display fails
            try:
                save_filename = "test_capture_output.png"
                cv2.imwrite(save_filename, image)
                logger.info(f"Test: Captured image saved to {os.path.abspath(save_filename)} as display failed.")
            except Exception as e_save:
                logger.error(f"Test: Failed to save test capture after display failure: {e_save}")
    else:
        logger.error(f"Test: Capture FAILED for region {test_region}.")

    logger.info("\nTest: Attempting to capture invalid region (negative width)...")
    invalid_region_neg_w = {"name": "invalid_width_neg", "x": 0, "y": 0, "width": -100, "height": 100}
    img_invalid = engine.capture_region(invalid_region_neg_w)
    assert img_invalid is None, "Capture of region with negative width should fail (return None)."
    logger.info("Test: Capture with negative width correctly failed.")

    logger.info("\nTest: Attempting to capture invalid region (non-integer coordinate)...")
    invalid_region_type_coord = {"name": "invalid_type_coord", "x": "abc", "y": 0, "width": 100, "height": 100}
    img_invalid_type = engine.capture_region(invalid_region_type_coord)  # type: ignore
    assert img_invalid_type is None, "Capture of region with non-integer coordinate should fail."
    logger.info("Test: Capture with non-integer coordinate correctly failed.")

    logger.info("\n--- CaptureEngine Self-Test Completed ---")
