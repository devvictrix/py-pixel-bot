import logging
import platform  # To identify the operating system for platform-specific notes/warnings
from typing import Optional, Dict, Any

import numpy as np
from PIL import Image, ImageGrab, UnidentifiedImageError  # Pillow's ImageGrab for screen capture
import cv2  # OpenCV for color conversion (RGB/RGBA from PIL to BGR for internal use)

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.capture_engine")


class CaptureEngine:
    """
    Responsible for capturing specified screen regions.

    It primarily uses Pillow's ImageGrab, which is generally efficient for Windows.
    It converts captures to OpenCV's standard BGR NumPy array format for consistent
    use by other engine components (AnalysisEngine, GeminiAnalyzer, etc.).

    Notes on Cross-Platform Capture:
    - Windows: Pillow ImageGrab.grab() is generally reliable and performant.
    - macOS: ImageGrab.grab() usually works but may require screen recording permissions
             for the application/terminal. Performance can vary.
    - Linux: ImageGrab.grab() often relies on external tools like 'scrot' or
             'gnome-screenshot' being installed. It also typically requires an active
             X server (may not work in pure Wayland sessions without XWayland, or headless).
    For future enhancements targeting optimal cross-platform performance and reliability,
    libraries like 'mss' or direct OS-specific APIs could be explored.
    """

    def __init__(self):
        """Initializes the CaptureEngine and logs the current operating system."""
        self.system = platform.system()
        logger.info(f"CaptureEngine initialized. Operating System: {self.system}.")

        if self.system == "Windows":
            logger.info("Capture method: Pillow ImageGrab.grab() (Optimized for Windows).")
        elif self.system == "Darwin":  # macOS
            logger.info("Capture method: Pillow ImageGrab.grab() for macOS. Ensure screen recording permissions are granted if issues occur.")
        elif self.system == "Linux":
            logger.info("Capture method: Pillow ImageGrab.grab() for Linux. May require 'scrot' or an X server.")
        else:
            logger.warning(f"Capture method: Pillow ImageGrab.grab() for unrecognized OS '{self.system}'. Capture behavior may vary.")

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
        x_coord = region_spec.get("x")
        y_coord = region_spec.get("y")
        width_val = region_spec.get("width")
        height_val = region_spec.get("height")

        # Ensure all coordinate and dimension values are integers
        if not all(isinstance(val, int) for val in [x_coord, y_coord, width_val, height_val]):
            logger.error(
                f"{log_prefix}: Capture FAILED. Invalid region specification. "
                f"Coordinates and dimensions must all be integers. Received: "
                f"x={x_coord}({type(x_coord).__name__}), y={y_coord}({type(y_coord).__name__}), "
                f"width={width_val}({type(width_val).__name__}), height={height_val}({type(height_val).__name__})."
            )
            return None

        # Ensure width and height are positive for a valid capture area
        if width_val <= 0 or height_val <= 0:
            logger.error(f"{log_prefix}: Capture FAILED. Width ({width_val}) and Height ({height_val}) must be positive.")
            return None

        # Pillow's ImageGrab.grab() uses a bounding box: (left, top, right, bottom)
        # All coordinates should be integers.
        left, top = int(x_coord), int(y_coord)
        right, bottom = int(x_coord + width_val), int(y_coord + height_val)
        # Construct the bounding box tuple
        bbox_to_capture = (left, top, right, bottom)

        logger.debug(f"{log_prefix}: Attempting capture with BoundingBox (L,T,R,B): {bbox_to_capture}")

        try:
            # `all_screens=True` is crucial for multi-monitor setups to ensure coordinates
            # are interpreted correctly relative to the entire virtual screen desktop.
            captured_pil_image: Optional[Image.Image] = ImageGrab.grab(bbox=bbox_to_capture, all_screens=True)

            if captured_pil_image is None:
                logger.error(f"{log_prefix}: Capture FAILED. Pillow ImageGrab.grab() returned None for BBox {bbox_to_capture}. This might indicate coordinates are off-screen or an OS-level issue.")
                return None

            logger.debug(f"{log_prefix}: Pillow capture successful. PIL Mode: {captured_pil_image.mode}, Size: {captured_pil_image.size}. Commencing conversion to OpenCV BGR format.")

            # Convert PIL Image (which can be in various modes like RGB, RGBA, L, P)
            # to an OpenCV NumPy array in BGR format.
            img_np_intermediate: np.ndarray = np.array(captured_pil_image)
            img_cv_bgr: Optional[np.ndarray] = None

            if captured_pil_image.mode == "RGB":
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_RGB2BGR)
            elif captured_pil_image.mode == "RGBA":
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_RGBA2BGR)  # Discards alpha
                logger.debug(f"{log_prefix}: RGBA image captured, converted to BGR (alpha channel discarded).")
            elif captured_pil_image.mode == "L":  # Grayscale
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_GRAY2BGR)  # Convert grayscale to BGR
                logger.debug(f"{log_prefix}: Grayscale (L mode) image captured, converted to BGR.")
            elif captured_pil_image.mode == "P":  # Palette-based
                logger.warning(f"{log_prefix}: Palette-based (P mode) image captured. Converting to RGB first, then to BGR. Colors might not be perfectly preserved if original palette was limited.")
                pil_rgb_converted = captured_pil_image.convert("RGB")  # Convert to RGB to resolve palette
                img_np_rgb_converted = np.array(pil_rgb_converted)
                img_cv_bgr = cv2.cvtColor(img_np_rgb_converted, cv2.COLOR_RGB2BGR)
            elif len(img_np_intermediate.shape) == 2:  # Grayscale without explicit L mode (e.g. some BMPs)
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_GRAY2BGR)
                logger.debug(f"{log_prefix}: Implicitly grayscale image (2D NumPy array) captured, converted to BGR.")
            elif img_np_intermediate.shape[2] == 4:  # Assume RGBA if 4 channels but mode wasn't RGBA
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_RGBA2BGR)
                logger.debug(f"{log_prefix}: 4-channel image (assumed RGBA) captured, converted to BGR.")
            elif img_np_intermediate.shape[2] == 3:  # Assume RGB if 3 channels and not already handled
                img_cv_bgr = cv2.cvtColor(img_np_intermediate, cv2.COLOR_RGB2BGR)
                logger.debug(f"{log_prefix}: 3-channel image (assumed RGB based on shape) captured, converted to BGR.")
            else:
                # Fallback for other unexpected modes or channel counts
                logger.error(f"{log_prefix}: Captured image in unexpected PIL mode '{captured_pil_image.mode}' or NumPy shape '{img_np_intermediate.shape}'. Cannot reliably convert to BGR.")
                return None

            logger.info(f"{log_prefix}: Capture and conversion to BGR successful. Final shape: {img_cv_bgr.shape if img_cv_bgr is not None else 'Error'}")
            return img_cv_bgr

        except UnidentifiedImageError as e_uie:  # Pillow specific error
            logger.error(f"{log_prefix}: Pillow could not identify image format from screen capture data (BBox {bbox_to_capture}). This is unusual for screen grabs. Error: {e_uie}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"{log_prefix}: Capture FAILED for BBox {bbox_to_capture}. Unexpected Error: {e}", exc_info=True)  # Include full stack trace for unexpected errors
            # More specific OS error interpretations (as in previous version)
            err_str = str(e).lower()
            if "scrot" in err_str or "gnome-screenshot" in err_str:
                logger.error(f"{log_prefix}: Pillow ImageGrab on Linux might be missing 'scrot' or 'gnome-screenshot'. Please ensure one is installed.")
            elif "cannot open display" in err_str or "xcb" in err_str or "x server" in err_str:
                logger.critical(
                    f"{log_prefix}: Critical capture failure: No display server (X11/XWayland) found or accessible. Mark-I cannot capture screen in headless or misconfigured display environments."
                )
            return None
