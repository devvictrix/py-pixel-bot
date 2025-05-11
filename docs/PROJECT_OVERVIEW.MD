// File: docs/PROJECT_OVERVIEW.MD
# Project Overview

## 1. Purpose

This project is a Python-based desktop automation tool designed to **capture and analyze specific regions of the screen in real-time**. It aims to extract information (e.g., text, colors, patterns, dominant colors) from these defined areas and then perform actions (mouse clicks, keyboard inputs) based on the analysis, often within or related to that specific region. It also provides a **Graphical User Interface (GUI) for comprehensive profile creation and management.**

## 2. Vision

To create a precise, efficient, and user-friendly visual automation tool that empowers users to automate tasks requiring interaction with dynamic or non-standard UI elements. This tool will enable automation where traditional element selectors might fail or be unavailable, by focusing on visual cues within defined screen areas, and will be easily configurable through an intuitive GUI.

## 3. Core Goals

*   **Targeted Screen Capture:** Reliably capture image data from user-defined screen areas.
*   **Advanced Visual Information Extraction:** Implement capabilities to "read" or analyze captured areas (OCR with confidence, color detection, average color, dominant colors, template matching).
*   **Flexible Conditional Action Execution:** Trigger programmatic actions based on complex rule evaluations (single or compound conditions, variable usage).
*   **User-Friendly Configuration (GUI):** Provide a comprehensive GUI for creating, editing, and managing all aspects of bot profiles (regions, templates, rules, settings) without needing to directly edit JSON files.
*   **Performance for Real-time Use (Bot Runtime):** Optimize for responsiveness suitable for monitoring and reacting to on-screen changes, including selective analysis.
*   **Robustness & Diagnosability:** Ensure stable operation with comprehensive logging for easy troubleshooting across different environments (`development`, `uat`, `production`) for both the bot runtime and the GUI editor.

## 4. Non-Goals (Out of Scope for v3.0.0)

*   Full-scale general computer vision understanding (e.g., complex object recognition beyond templates or basic shapes).
*   General-purpose screen recording for playback.
*   Natural Language Understanding of on-screen content beyond keyword matching from OCR.
*   Automated discovery of "interesting" screen regions; the user must define the regions (though the GUI aids this).
*   Highly advanced UI element inspection using OS accessibility APIs (focus is on visual analysis).
*   Advanced GUI features like live visual feedback overlays during rule creation (marked as v3.0.0 "Real-time Visual Feedback in GUI" but might be deferred if initial GUI is extensive).
*   Drag-and-drop reordering in GUI lists (a "nice-to-have" that might be deferred from initial v3.0.0 GUI).

## 5. Target Users

*   Gamers automating in-game tasks.
*   Users interacting with applications lacking APIs or standard UI accessibility.
*   Testers performing visual validation.
*   Individuals needing to automate interactions with legacy systems or virtualized environments.
*   Developers and power users needing a scriptable (via JSON profiles) and GUI-configurable tool to react to visual on-screen events.

## 6. Core Technology Stack (Envisioned for v3.0.0)

*   **Language:** Python
*   **Environment Management:** `python-dotenv` for `.env` files (`APP_ENV`).
*   **Logging:** Python `logging` module.
*   **Screen Capture:** `Pillow` (`ImageGrab`), `OpenCV-Python`.
*   **Image Processing/Analysis:** `OpenCV-Python`, `NumPy`, `Pillow`.
*   **OCR:** `pytesseract` (Tesseract OCR wrapper).
*   **Input Simulation:** `pyautogui`.
*   **Configuration/Data Format:** JSON for profiles.
*   **CLI:** `argparse`.
*   **GUI:** `CustomTkinter`.

---