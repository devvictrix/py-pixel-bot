// File: PROJECT_OVERVIEW.MD
# Project Overview

## 1. Purpose

This project is a Python-based desktop automation tool designed to **capture and analyze specific regions of the screen in real-time**. It aims to extract information (e.g., text, colors, simple patterns) from these defined areas and then perform actions (mouse clicks, keyboard inputs) based on the analysis, often within or related to that specific region.

## 2. Vision

To create a precise and efficient visual automation tool that empowers users to automate tasks requiring interaction with dynamic or non-standard UI elements by focusing on visual cues within defined screen areas. This tool will enable automation where traditional element selectors might fail or be unavailable.

## 3. Core Goals

*   **Targeted Screen Capture:** Reliably capture image data from a user-defined rectangular area of the screen.
*   **Visual Information Extraction:** Implement capabilities to "read" or analyze the content of the captured area (e.g., basic OCR, color detection, pixel pattern matching).
*   **Conditional Action Execution:** Trigger programmatic actions (mouse, keyboard) based on the results of the visual analysis.
*   **User-Defined Focus:** Allow users to easily specify and manage the target screen regions.
*   **Performance for Real-time Use:** Optimize for responsiveness suitable for monitoring and reacting to on-screen changes.
*   **Robustness & Diagnosability:** Ensure stable operation with comprehensive logging for easy troubleshooting across different environments (`development`, `uat`, `production`).

## 4. Non-Goals (Out of Scope for Initial Major Deliverable - AI-Accelerated v1.0.0)

*   Full-scale general computer vision understanding (e.g., complex object recognition beyond simple patterns or OCR).
*   General-purpose screen recording for playback (this tool focuses on live analysis and reaction).
*   Natural Language Understanding of on-screen content beyond basic keyword matching from OCR.
*   Automated discovery of "interesting" screen regions; the user must define the regions.
*   Highly advanced UI element inspection using OS accessibility APIs (focus is on visual analysis).

## 5. Target Users

*   Gamers automating in-game tasks based on visual cues (e.g., health bars, specific icons, cooldown timers).
*   Users interacting with applications that lack APIs or standard UI element accessibility.
*   Testers performing visual validation or interacting with custom UI elements.
*   Individuals needing to automate interactions with legacy systems or virtualized environments where element inspection is difficult.
*   Developers and power users needing a scriptable tool to react to visual on-screen events.

## 6. Core Technology Stack (Initial & Envisioned for AI-Accelerated v1.0.0)

*   **Language:** Python
*   **Environment Management:** `python-dotenv` for `.env` files (`APP_ENV`).
*   **Logging:** Python `logging` module.
*   **Screen Capture:** `OpenCV-Python` (cv2), potentially `mss` for performance exploration.
*   **Image Processing/Analysis:** `OpenCV-Python`, `NumPy`, `Pillow`.
*   **OCR (Optical Character Recognition):** `pytesseract` (Tesseract OCR wrapper).
*   **Input Simulation:** `pyautogui`.
*   **Configuration/Data Format:** JSON for profiles.
*   **CLI:** `argparse`.
*   **GUI (for Region Definition in AI-Accelerated v1.0.0):** `CustomTkinter`.

---