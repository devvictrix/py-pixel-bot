# Project Overview: Mark-I

## 1. Purpose

This project, **Mark-I** (inspired by Tony Stark's pioneering suit in Iron Man, with the long-term vision of evolving into a "J.A.R.V.I.S."-like assistant for visual automation), is a Python-based desktop automation tool designed to **capture and analyze specific regions of the screen in real-time**. It aims to extract information (e.g., text with confidence scores, colors, pixel patterns, dominant colors) from these user-defined areas and then perform actions (mouse clicks, keyboard inputs, logging) based on a configurable rules engine. **(v4.0.0 Goal)** It further aims to **leverage advanced AI models, specifically Google Gemini, for enhanced visual understanding and more robust decision-making** based on screen content. A key component is a Graphical User Interface (GUI) for comprehensive profile creation, editing, and management, making complex automation accessible.

## 2. Vision

To create a precise, efficient, and user-friendly visual automation tool, **Mark-I**, that empowers users to automate tasks requiring interaction with dynamic or non-standard UI elements. This tool will enable automation where traditional element selectors might fail, by focusing on visual cues. **By incorporating advanced AI like Google Gemini (v4.0.0+), the vision extends towards more intelligent, context-aware, and adaptable automation that can handle greater UI variability and interpret visual information more semantically – ultimately aspiring to the helpfulness and adaptability of a system like J.A.R.V.I.S.** It aims to be highly configurable through an intuitive GUI, while still offering a robust CLI for bot execution.

## 3. Core Goals

*   **Targeted Screen Capture:** Reliably capture image data from user-defined rectangular areas of the screen.
*   **Advanced Visual Information Extraction:** Implement a suite of analysis capabilities, including:
    *   Pixel and average color detection.
    *   Template (image pattern) matching with confidence scoring.
    *   Optical Character Recognition (OCR) for text extraction, including confidence scores.
    *   Dominant color analysis within a region.
    *   **(v4.0.0) AI-Powered Visual Understanding:** Integrate Google Gemini API to allow rules based on semantic scene description, element identification, and question-answering about visual content within regions.
*   **Flexible Conditional Action Execution:**
    *   Trigger programmatic actions (mouse, keyboard, logging) based on the results of visual analysis (both local and AI-driven).
    *   Support a rules engine with single conditions, compound conditions (AND/OR logic), and the ability to capture analysis results (including Gemini responses) into rule-scoped variables for use in subsequent conditions or actions.
*   **User-Friendly Configuration via GUI (Primary Goal for v3.0.0, Enhanced for v4.0.0):**
    *   Provide a comprehensive and intuitive GUI (`MainAppWindow`) for all aspects of profile creation and management: defining regions, managing templates, building complex rules (including **Gemini conditions (v4.0.0)** and **actions targeting Gemini-identified elements (v4.0.0 Phase 1.5)**), and configuring bot settings.
    *   Ensure robust input validation and user feedback within the GUI.
*   **Performant Bot Runtime:** Optimize the bot's execution loop for responsiveness, including features like selective local analysis. Acknowledge and manage the inherent latency of external API calls for AI features.
*   **Robustness & Diagnosability:** Ensure stable operation, graceful error handling (including external API issues), and comprehensive, configurable logging across all components.

## 4. Non-Goals (Out of Scope for Current v3.0.0 & v4.0.0 Phase 1.5 Definition)

*   Full-scale general computer vision AI beyond the capabilities offered by template matching and the integrated Gemini Vision models (e.g., complex object tracking, fine-grained activity recognition).
*   General-purpose screen recording software.
*   Natural Language Understanding (NLU) of on-screen content beyond keyword/pattern matching from OCR or the interpretations provided by Gemini prompts.
*   **(v4.0.0 Limitation)** Fully autonomous AI agent behavior where Gemini directly dictates sequences of actions without user-defined rules (this is a potential future direction, but beyond Phase 1.5).
*   Automated discovery or learning of "interesting" screen regions or automation rules; the user must explicitly define these.
*   Direct UI element inspection using OS accessibility APIs (the primary focus remains on *visual* analysis).

## 5. Target Users

*   Gamers automating repetitive tasks based on visual cues (health bars, icons, text), potentially handling more UI variations with AI assistance.
*   Users interacting with applications lacking APIs or standard accessibility (legacy apps, virtualized environments), where AI interpretation can improve robustness.
*   Testers performing visual validation or interacting with custom UI elements.
*   Individuals automating interactions with websites or applications where content is dynamic and AI can help interpret semantic meaning over brittle selectors.
*   Developers and power users needing a scriptable (via JSON) yet GUI-configurable tool to react to visual events, now with the option for more intelligent reactions via AI.

## 6. Core Technology Stack (Confirmed for v3.0.0 Development, with v4.0.0 additions)

*   **Language:** Python (targeting 3.9+)
*   **Environment Management:** `python-dotenv` (for `.env`: `APP_ENV`, `GEMINI_API_KEY`).
*   **Logging:** Python's built-in `logging` module.
*   **Screen Capture:** `Pillow` (`ImageGrab.grab()`).
*   **Image Processing & Analysis (Local):** `OpenCV-Python` (cv2), `NumPy`, `Pillow`.
*   **OCR (Local):** `pytesseract`.
*   **AI Vision Analysis (Remote - v4.0.0):** `google-generativeai` (Python SDK for Google Gemini API).
*   **Input Simulation:** `pyautogui`.
*   **Configuration Profile Format:** JSON.
*   **Command-Line Interface (CLI):** `argparse`.
*   **Graphical User Interface (GUI):** `CustomTkinter`.
*   **Concurrency (Bot Runtime):** `threading`.