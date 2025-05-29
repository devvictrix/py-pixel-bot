# Project Overview: Mark-I

## 1. Purpose

This project, **Mark-I** (inspired by Tony Stark's pioneering suit, with the long-term vision of evolving into a "J.A.R.V.I.S."-like assistant), is a Python-based desktop automation tool. It is designed to **capture and analyze specific regions of the screen in real-time**, extract information using both local computer vision techniques and advanced AI (Google Gemini), and then perform actions (mouse clicks, keyboard inputs, logging) based on a configurable rules engine or natural language commands. Mark-I aims to provide a powerful, flexible, and user-friendly solution for automating tasks on the Windows desktop, especially those involving dynamic or non-standard UI elements.

## 2. Vision

To create **Mark-I**, a precise, efficient, and highly intelligent visual automation tool that empowers users to automate a wide array of desktop tasks. Mark-I excels where traditional element selectors might fail by focusing on visual cues and understanding screen content semantically.

**With the completion of v4.0.0 (Gemini-Powered Visual Intelligence), Mark-I's vision has significantly advanced towards becoming a true "great assistance."** It now not only reacts to predefined visual conditions but can also:
*   Understand and answer complex questions about screen regions.
*   Identify and interact with UI elements based on textual descriptions and visual context.
*   Execute tasks based on simple goals provided by the user.
*   Interpret and act upon natural language commands, decomposing them into executable steps.

The aspiration is to continue evolving Mark-I into an increasingly adaptable, intuitive, and autonomous assistant, capable of handling complex automation scenarios with minimal explicit programming, truly embodying the helpfulness and intelligence of a system like J.A.R.V.I.S. for visual automation.

## 3. Core Goals (Achieved and Evolving)

*   **Targeted Screen Capture:** Reliably capture image data from user-defined rectangular areas of the screen.
*   **Advanced Visual Information Extraction:** Implement and maintain a robust suite of analysis capabilities:
    *   **Local Analysis:** Pixel and average color detection, template (image pattern) matching, Optical Character Recognition (OCR) for text extraction, and dominant color analysis.
    *   **AI-Powered Visual Understanding (v4.0.0):**
        *   **Gemini Vision Queries:** Allow rules to ask complex questions about screen content via Gemini.
        *   **Gemini Element Identification:** Enable precise interaction with UI elements by having Gemini identify them and return their bounding boxes.
*   **Flexible and Intelligent Conditional Action Execution:**
    *   Trigger programmatic actions based on the results of both local and AI-driven visual analysis.
    *   Support a rules engine with single conditions, compound conditions (AND/OR logic), and variable capture.
    *   **AI-Informed Decision Making (v4.0.0):**
        *   Enable Mark-I (via `GeminiDecisionModule`) to select and parameterize actions based on simple user-defined goals and visual context (`gemini_perform_task` action).
        *   **Natural Language Command Interface (v4.0.0):** Allow users to issue high-level, potentially multi-step commands in natural language, which Mark-I interprets (using Gemini NLU), decomposes, and orchestrates for execution.
*   **User-Friendly Configuration & Management:**
    *   Provide a comprehensive and intuitive GUI (`MainAppWindow`) for all aspects of profile creation and management, including regions, templates, complex rules (with all Gemini features), NLU task parameters, and bot settings.
    *   Ensure robust input validation and user feedback within the GUI.
*   **Performant and Reliable Bot Runtime:**
    *   Optimize the bot's execution loop, including selective local analysis.
    *   Acknowledge and manage the inherent latency of external API calls for AI features, providing clear feedback.
    *   Ensure stable operation, graceful error handling (including external API issues), and comprehensive, configurable logging.

## 4. Non-Goals (Out of Scope for v4.0.0)

*   Full-scale general computer vision AI beyond the capabilities offered by the integrated local analysis and Gemini Vision models (e.g., complex real-time object tracking across the entire screen, fine-grained human activity recognition).
*   General-purpose screen recording software.
*   **(Limitation of v4.0.0 NLU):** While capable of understanding and decomposing many commands, the NLU is not a fully open-ended conversational AI or a general-purpose planner. It works best with commands that can be mapped to sequences of its known primitive actions and visual checks. Highly abstract or ambiguous commands may not be reliably interpreted without very specific prompt engineering by the user.
*   Automated discovery or learning of "interesting" screen regions or entirely new automation rules without any user guidance (though AI can *generate* profiles based on a goal as a future concept - see "AI Profile Creator" idea).
*   Direct UI element inspection using OS accessibility APIs (the primary focus remains on *visual* and *AI-interpreted semantic* analysis).

## 5. Target Users (Expanded with v4.0.0 capabilities)

*   **Gamers:** Automating complex sequences, reacting to dynamic events understood by AI, and using natural language to command in-game actions.
*   **Users of Legacy/API-less Applications:** Automating interactions where Gemini's visual and textual understanding can identify and operate UI elements that are otherwise inaccessible.
*   **Software Testers:** Performing more robust visual validation and UI testing by describing test steps or expected states in natural language, or by having AI identify elements semantically.
*   **Content Creators & Data Entry Specialists:** Automating tasks involving information extraction and interaction across various applications, potentially guided by NLU commands.
*   **Power Users & Developers:** Leveraging Mark-I as a highly configurable platform to build sophisticated visual automations, now with the ability to integrate AI reasoning and NLU for more complex workflows.
*   Anyone looking to reduce repetitive desktop tasks by describing what they want to achieve in natural language to an intelligent visual assistant.

## 6. Core Technology Stack (Final for v4.0.0)

*   **Language:** Python (targeting 3.9+)
*   **Environment Management:** `python-dotenv` (for `.env`: `APP_ENV`, `GEMINI_API_KEY`).
*   **Logging:** Python's built-in `logging` module.
*   **Screen Capture:** `Pillow` (`ImageGrab.grab()`).
*   **Image Processing & Analysis (Local):** `OpenCV-Python` (cv2), `NumPy`, `Pillow`.
*   **OCR (Local):** `pytesseract`.
*   **AI Vision Analysis, NLU, & Decision Support (Remote - v4.0.0):** `google-generativeai` (Python SDK for Google Gemini API).
*   **Input Simulation:** `pyautogui`.
*   **Configuration Profile Format:** JSON.
*   **Command-Line Interface (CLI):** `argparse`.
*   **Graphical User Interface (GUI):** `CustomTkinter`.
*   **Concurrency (Bot Runtime):** `threading`.