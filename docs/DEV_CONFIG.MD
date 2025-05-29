// File: docs/DEV_CONFIG.MD

# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the **Mark-I** project. **It reflects the shift towards v4.0.0 (Gemini-Powered Visual Intelligence).**

## 1. Core Project Setup
*   **Project Name (Informal):** Mark-I
*   **Python Package Name:** `py_pixel_bot` (Remains unchanged)
*   **Language:** Python
*   **Python Version (Target):** 3.9+ (or as specified by dependencies like CustomTkinter or OpenCV)
*   **Package Manager:** pip
*   **Virtual Environment:** venv (standard, recommended)
    *   Example setup: `python -m venv .venv` then `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).

## 1.1. Environment Configuration (per ADR-007, ADR-008)
*   **Method:** `.env` file at the project root, loaded using the `python-dotenv` library.
*   **Key Variables:**
    *   `APP_ENV`: Controls logging, etc.
        *   **Possible Values:** `development`, `uat`, `production`.
        *   **Default for local development:** Create a `.env` file in the project root with `APP_ENV=development`.
    *   **`GEMINI_API_KEY` (Required for v4.0.0+):** Your API key for accessing Google Gemini API.
        *   Obtain from Google AI Studio or Google Cloud Console.
        *   Add `GEMINI_API_KEY=your_api_key_here` to your `.env` file.
*   **Purpose:** Controls environment-specific behavior (logging, API keys, etc.).
*   **`.gitignore`:** The `.env` file **MUST** be added to `.gitignore` to prevent committing environment-specific or sensitive settings (like API keys). The `logs/` directory should also be ignored.

## 2. Current Development Phase Focus
*   **Overall Goal for First Major Deliverable:** `AI-Accelerated v1.0.0` - **COMPLETED**
*   **Overall Goal for Second Major Deliverable:** `v2.0.0 (Advanced Visual Analysis & Rules)` - **COMPLETED**
*   **Overall Goal for Third Major Deliverable:** `v3.0.0 (Enhanced GUI & Usability)` - **COMPLETED**
*   **Overall Goal for Fourth Major Deliverable (Current Target):** `v4.0.0 (Gemini-Powered Visual Intelligence)`
    *   This version integrates the Google Gemini API to enhance visual understanding, enabling more robust and context-aware automation rules. Details are in `FEATURE_ROADMAP.MD` and `ADR-008`.
*   **Active Version (Current Focus for Implementation):** `v4.0.0 (Gemini - Phase 1: Core Integration)`
    *   *This version, set here, dictates the immediate components and features being developed by the AI collaborator, contributing towards the larger v4.0.0 goal.*
*   **Primary Goal for Active Version:** Implement the foundational integration with the Gemini API as outlined in ADR-008 Phase 1:
    *   Create the `GeminiAnalyzer` module for API communication.
    *   Implement secure API key management (`.env` and `ConfigManager`).
    *   Add the `gemini_vision_query` condition type to the `RulesEngine`.
    *   Add basic GUI support in `MainAppWindow`/`DetailsPanel` for configuring `gemini_vision_query` conditions.
    *   Update all relevant documentation (ADRs, Technical Design, Requirements, NFRs, Roadmap).
*   **Testing Strategy for Active Version (and towards v4.0.0):**
    *   **Unit Tests:** Deferred until core components are more stable, or upon explicit DevLead enablement. **Testing `GeminiAnalyzer` will likely require mocking the external `google-generativeai` API.**
        *   **Status:** `Pending DevLead Enablement`
    *   **Integration Tests:** Manual, focused on end-to-end scenarios for the target version features. Log outputs are crucial. GUI interactions (creating/editing profiles with Gemini conditions) will be tested manually by DevLead. **Requires a valid `GEMINI_API_KEY` in `.env` for testing Gemini features.**
*   **Linting/Formatting Setup:**
    *   **Flake8 (Linter):** Enabled (Configured for Black compatibility via `.flake8`).
    *   **Black (Formatter):** Enabled (Configured via `pyproject.toml`).
    *   Manual adherence to PEP 8 encouraged.

## 3. Architectural & Design Approach
*   **Overall Architectural Style:** Modular (Capture, Analysis, Action, Rules, Gemini engines, UI). Approved ADRs are foundational.
    *   *Details in `TECHNICAL_DESIGN.MD`.*
*   **Logging Strategy:** Comprehensive and persistent logging using Python's `logging` module (per ADR-007). **v4.0.0: Logging must include details of Gemini API interactions.**
*   **Code Design Principles:** Readability, Simplicity, Modularity, Testability, Diagnosability (via logs). Adherence to Black/Flake8.

## 4. Tooling Choices (Key Tools - per ADRs)
*   **Environment Management:** `python-dotenv`
*   **Logging:** Python `logging` module.
*   **Screen Capture:** `Pillow` (`ImageGrab`), `OpenCV-Python`.
*   **Image Processing:** `OpenCV-Python`, `NumPy`, `Pillow`.
*   **OCR:** `pytesseract`.
*   **Input Simulation:** `pyautogui`.
*   **Configuration Format:** JSON.
*   **CLI:** `argparse`.
*   **GUI:** `CustomTkinter`.
*   **AI Vision API (v4.0.0+):** `google-generativeai` (Python SDK for Gemini).
*   **Unit Testing Framework (Future):** `pytest` (Status: `Pending DevLead Enablement`)
*   **Linter:** `Flake8` (Status: `Enabled`)
*   **Formatter:** `Black` (Status: `Enabled`)
*   **Import Sorter (Future):** `isort` (Status: `Pending DevLead Enablement`)

## 5. Version Control
*   **System:** Git
*   **Branching (Simplified Strategy):**
    *   `main`: Represents the latest stable release (currently post-v3.0.0).
    *   `develop`: Active development branch for ongoing work towards the current overall goal (v4.0.0). Feature branches (e.g., `feature/gemini-core-integration`) are created from `develop`.
*   **Commit Messages:** Aim for conventional commit style.

## 6. Documentation
*   **Docstring Style:** Google Python Style.
*   **Project Documentation Status:**
    *   **`CHANGELOG.MD`:** Should be updated for v3.0.0 release and maintained for v4.0.0.
        *   **Status:** `Pending DevLead Update for v3.0.0 content`
    *   **`CONTRIBUTING.MD`:** Deferred.
        *   **Status:** `Pending DevLead Enablement`
    *   **Core Docs:** Established, updated iteratively. `ADR-008` added for v4.0.0. `AI_INSTRUCTIONS.MD` updated for v4.0.0. `TECHNICAL_DESIGN.MD`, Requirements, NFRs updated for v4.0.0.
*   **README.md (Project Root):** Needs updates for v3.0.0 (GUI) and **v4.0.0 (Gemini)** features once stable.

## 7. Development Environment
*   **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
*   **Development OS:** **Windows** (Assumed for DevLead).
*   **Key Dependencies Installation (Windows Focus):**
    *   Ensure Python 3.9+ is installed and in PATH.
    *   Create virtual environment: `python -m venv .venv` & activate.
    *   Install packages: `pip install -r requirements.txt` (ensure `google-generativeai` is added for v4.0.0).
    *   **Tesseract OCR Engine:** Must be installed system-wide and in PATH for OCR features.
    *   **(v4.0.0+) Gemini API Key:** Requires a `.env` file with `GEMINI_API_KEY=your_key`.