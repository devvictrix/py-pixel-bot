// File: docs/PROJECT_OVERVIEW.MD
# Project Overview

## 1. Purpose

This project is a Python-based desktop automation tool designed to **capture and analyze specific regions of the screen in real-time**. It aims to extract information (e.g., text with confidence scores, colors, pixel patterns, dominant colors) from these user-defined areas and then perform actions (mouse clicks, keyboard inputs, logging) based on a configurable rules engine. A key component is a **Graphical User Interface (GUI) for comprehensive profile creation, editing, and management**, making complex automation accessible without direct JSON manipulation for most tasks.

## 2. Vision

To create a precise, efficient, and user-friendly visual automation tool that empowers users to automate tasks requiring interaction with dynamic or non-standard UI elements. This tool will enable automation where traditional element selectors might fail or be unavailable, by focusing on visual cues within defined screen areas. It aims to be highly configurable through an intuitive GUI, while still offering a robust CLI for bot execution.

## 3. Core Goals

*   **Targeted Screen Capture:** Reliably capture image data from user-defined rectangular areas of the screen.
*   **Advanced Visual Information Extraction:** Implement a suite of analysis capabilities, including:
    *   Pixel and average color detection.
    *   Template (image pattern) matching with confidence scoring.
    *   Optical Character Recognition (OCR) for text extraction, including confidence scores.
    *   Dominant color analysis within a region.
*   **Flexible Conditional Action Execution:**
    *   Trigger programmatic actions (mouse, keyboard, logging) based on the results of visual analysis.
    *   Support a rules engine with single conditions, compound conditions (AND/OR logic), and the ability to capture analysis results into rule-scoped variables for use in subsequent conditions or actions.
*   **User-Friendly Configuration via GUI (Primary Goal for v3.0.0):**
    *   Provide a comprehensive and intuitive GUI (`MainAppWindow` using CustomTkinter) for all aspects of profile creation and management: defining regions (graphically), managing templates (including file handling), building complex rules with all their parameters, and configuring bot settings.
    *   Ensure robust input validation and user feedback within the GUI.
*   **Performant Bot Runtime:** Optimize the bot's execution loop for responsiveness suitable for monitoring and reacting to on-screen changes, including features like selective analysis to minimize unnecessary computation.
*   **Robustness & Diagnosability:** Ensure stable operation of both the bot runtime and the GUI editor, with comprehensive and configurable logging (per ADR-007) across all components for easy troubleshooting and operational understanding.

## 4. Non-Goals (Out of Scope for Current v3.0.0 Definition)

*   Full-scale general computer vision AI (e.g., complex object recognition beyond template matching or basic shape detection if added later).
*   General-purpose screen recording software for video playback (the tool focuses on live analysis and reaction).
*   Natural Language Understanding (NLU) of on-screen content beyond keyword/pattern matching from OCR results.
*   Automated discovery or learning of "interesting" screen regions or automation rules; the user must explicitly define these through the GUI or JSON profile.
*   Direct UI element inspection using OS accessibility APIs (the primary focus remains on *visual* analysis of screen pixels).
*   Highly advanced GUI features for v3.0.0 like real-time visual feedback overlays *during rule creation within the editor* (this is a v3.0.0 item but might be a later phase or simplified initially).
*   Complex drag-and-drop reordering for all list items in the GUI (simple up/down buttons are more likely for initial v3.0.0 if reordering is implemented).

## 5. Target Users

*   Gamers automating repetitive in-game tasks based on visual cues (e.g., health bars, specific icons, cooldown timers, on-screen text).
*   Users needing to interact with applications that lack APIs or standard UI element accessibility (e.g., legacy applications, virtualized environments where introspection is difficult).
*   Testers performing visual validation tasks or interacting with custom UI elements during automated testing.
*   Individuals seeking to automate interactions with websites or applications where content is dynamic and selectors are unreliable.
*   Developers and power users who need a scriptable (via JSON profiles) yet GUI-configurable tool to react to visual events on their screen.

## 6. Core Technology Stack (Confirmed for v3.0.0 Development)

*   **Language:** Python (targeting 3.9+)
*   **Environment Management:** `python-dotenv` for `.env` files (managing `APP_ENV`).
*   **Logging:** Python's built-in `logging` module, configured via `core.logging_setup`.
*   **Screen Capture:** `Pillow` (specifically `ImageGrab.grab()` for Windows, due to its simplicity and performance for the primary target OS). OpenCV for potential cross-platform capture alternatives or specific needs.
*   **Image Processing & Analysis:** `OpenCV-Python` (cv2), `NumPy` (for array manipulation with OpenCV), `Pillow` (for basic image operations and format conversions).
*   **OCR (Optical Character Recognition):** `pytesseract` (Python wrapper for the Tesseract OCR engine).
*   **Input Simulation (Mouse & Keyboard):** `pyautogui`.
*   **Configuration Profile Format:** JSON (parsed and managed by `core.config_manager`).
*   **Command-Line Interface (CLI):** Python's built-in `argparse` module (for `run`, `add-region`, `edit` commands).
*   **Graphical User Interface (GUI):** `CustomTkinter` (for `RegionSelectorWindow` and the main `MainAppWindow` profile editor).
*   **Concurrency (Bot Runtime):** Python's built-in `threading` module (for running `MainController`'s monitoring loop in the background).

---