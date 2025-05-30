# ADR-001: Choice of Core Technologies for Screen Capture and Region Analysis

*   **Status:** Approved (v4.0.0: Decision remains valid; image data also consumed by AI analysis modules)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool (Mark-I) requires the ability to:
1.  Capture image data from specific rectangular regions of the screen across different operating systems (Windows, macOS, Linux).
2.  Perform analysis on this captured image data, including pixel-level inspection, basic template matching, and eventually Optical Character Recognition (OCR).
3.  The capture and analysis need to be performant enough for potential real-time applications.
4.  **(Added for v4.0.0 context)** The captured image data also serves as input for advanced AI-powered visual analysis via external APIs (e.g., Google Gemini).

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

**Chosen Option:** `Pillow` (specifically `ImageGrab.grab()` on Windows) for primary screen capture due to its simplicity and good performance on the initial target OS (Windows), `OpenCV-Python` for image processing and analysis (including template matching and format conversion), supplemented by `pytesseract` for OCR capabilities. `mss` and OpenCV's direct capture methods are kept in consideration for future performance optimization or cross-platform capture enhancements if needed.

**Justification:**
*   **Simplicity & Performance on Target OS (Pillow for Windows Capture):** `ImageGrab.grab()` is straightforward and performs well on Windows for capturing screen regions.
*   **Comprehensive Analysis (OpenCV):** OpenCV provides a vast range of functionalities needed for image manipulation, filtering, template matching, and converting image data into a standardized format (NumPy BGR array) suitable for all subsequent analysis engines.
*   **Standard OCR (pytesseract):** `pytesseract` is the de facto standard Python wrapper for Tesseract.
*   **Power and Flexibility:** The combination offers the depth required for current and future complex analysis features, including preparing image data for external AI model consumption.
*   **Industry Standard:** OpenCV, Pillow, and Tesseract are well-known in their domains.
*   **Performance Path:** If Pillow's `ImageGrab` shows limitations or for broader cross-platform capture, direct OpenCV capture or `mss` can be integrated, feeding data into the OpenCV pipeline for analysis.

## Consequences

*   The project has dependencies on `Pillow`, `opencv-python`, `numpy` (usually comes with OpenCV), and `pytesseract`.
*   Users will need to install the Tesseract OCR engine separately for OCR features to work. This is documented in `README.md`.
*   Initial development of `CaptureEngine` focuses on `Pillow.ImageGrab.grab()` for Windows, converting to OpenCV format (BGR NumPy array). This standardized format is then used by `AnalysisEngine` (for local analysis) and `GeminiAnalyzer` (for AI-powered analysis, which internally converts to PIL RGB as needed by the Gemini SDK).
*   Developers need familiarity with Pillow for capture, OpenCV for image processing and format conversion, and `pytesseract` for OCR.

---