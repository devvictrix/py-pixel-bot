// File: docs/adrs/ADR-001-Choice-Screen-Capture-Analysis-Tech.md
# ADR-001: Choice of Core Technologies for Screen Capture and Region Analysis

*   **Status:** Approved
*   **Date:** 2025-05-11 <!-- Assuming current date for approval -->
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool requires the ability to:
1.  Capture image data from specific rectangular regions of the screen across different operating systems (Windows, macOS, Linux).
2.  Perform analysis on this captured image data, including pixel-level inspection, basic template matching, and eventually Optical Character Recognition (OCR).
3.  The capture and analysis need to be performant enough for potential real-time applications.

We need to select foundational Python libraries for these core tasks.

## Considered Options

1.  **`OpenCV-Python` as primary for capture and analysis, `pytesseract` for OCR:**
    *   Pros:
        *   OpenCV is a comprehensive and powerful library for image capture (can access system backends), extensive image processing, and includes template matching.
        *   `pytesseract` is a well-established Python wrapper for the Tesseract OCR engine.
        *   Large community support and ample documentation for both.
        *   NumPy, a dependency of OpenCV, is excellent for efficient pixel manipulation.
    *   Cons:
        *   OpenCV can be a heavy dependency.
        *   Tesseract OCR (and `pytesseract`) requires a separate installation of the Tesseract engine.
        *   Default screen capture with OpenCV might not always be the absolute fastest.
2.  **`mss` for capture, `Pillow` for basic analysis, `OpenCV-Python` for advanced analysis/template matching, `pytesseract` for OCR:**
    *   Pros:
        *   `mss` is known for very fast screen capture.
        *   `Pillow` is lighter than OpenCV for simple image operations if complex processing isn't immediately needed.
    *   Cons:
        *   Potentially more libraries to integrate.
        *   OpenCV would still likely be needed for template matching and more advanced image processing, reducing the benefit of avoiding it initially.
3.  **Platform-specific capture libraries + `Pillow` + `pytesseract`:**
    *   Pros: Potentially the most performant capture if optimized for each OS.
    *   Cons: Significantly increases development and maintenance complexity due to separate codebases for capture on each OS. Defeats the goal of rapid cross-platform development.

## Decision Outcome

**Chosen Option:** `OpenCV-Python` as the primary library for screen capture and image analysis (including template matching), supplemented by `pytesseract` for OCR capabilities. `mss` will be kept in consideration for future performance optimization of screen capture if needed. Pillow is also included as `pyautogui` and `CustomTkinter` (for `CTkImage`) depend on it, and it's useful for direct screen capture on Windows (`ImageGrab.grab()`).

**Justification:**
*   **Unified Toolkit:** OpenCV provides a vast range of functionalities needed (capture, image manipulation, filtering, template matching) within a single, well-integrated ecosystem. Pillow provides simple and fast cross-platform image manipulation and capture, especially effective on Windows.
*   **Power and Flexibility:** They offer the depth required for future, more complex analysis features.
*   **Cross-Platform Abstraction:** While performance can vary, OpenCV and Pillow aim to provide a consistent API across platforms for capture.
*   **Industry Standard:** OpenCV, Pillow, and Tesseract are de facto standards in their respective domains.
*   **Performance Path:** While `mss` is noted for speed, OpenCV's capabilities are broad. If specific capture bottlenecks arise with OpenCV's default methods or Pillow's `ImageGrab`, `mss` can be integrated as an alternative capture source, feeding data into the OpenCV pipeline for analysis.

## Consequences

*   The project will have dependencies on `opencv-python`, `numpy` (usually comes with OpenCV), `Pillow`, and `pytesseract`.
*   Users will need to install the Tesseract OCR engine separately for OCR features to work. This needs to be clearly documented in `README.md` and user guides.
*   Initial development will focus on leveraging Pillow's `ImageGrab` for Windows screen capture due to its simplicity and good performance there, and OpenCV for image processing. Performance testing will guide if/when to explore other capture methods or optimize.
*   Developers will need to be familiar with OpenCV's API for image processing, Pillow for capture/basic manipulation, and `pytesseract` for OCR.

---