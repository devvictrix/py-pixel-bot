# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the **Mark-I** project. **Version 4.0.0 (Gemini-Powered Visual Intelligence) is now COMPLETE.**

## 1. Core Project Setup
*   **Project Name (Informal):** Mark-I
*   **Python Package Name:** `mark_i`
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
*   **Overall Goal for Fourth Major Deliverable:** `v4.0.0 (Gemini-Powered Visual Intelligence)` - **COMPLETED**
    *   Phase 1: Core Gemini Integration - `COMPLETED`
    *   Phase 1.5: Bounding Box Actions - `COMPLETED`
    *   Phase 2: Gemini-Informed Decision Making - `COMPLETED`
    *   Phase 3: Natural Language Command Interface - `COMPLETED`
*   **Active Version (Current Focus):** `v4.0.0 (Release Finalization & v5.0.0 Planning)`
    *   *Current activities involve finalizing all documentation for v4.0.0, DevLead preparing for a potential release tag, and initiating discussions for prioritizing features for v5.0.0 from the "vFuture" list in `FEATURE_ROADMAP.MD`.*
*   **Primary Goal for Active Version:**
    1.  **Finalize all v4.0.0 documentation** (`README.MD`, `CHANGELOG.MD` if used, ensuring all technical docs are accurate).
    2.  **DevLead to perform final review and consider tagging v4.0.0 release.**
    3.  **Begin planning and prioritizing features for v5.0.0.**
*   **Testing Strategy:** Focus on regression testing for v4.0.0 if any patches are made. New feature testing will apply to v5.0.0 development.
*   **Linting/Formatting Setup:**
    *   **Flake8 (Linter):** Enabled (Configured for Black compatibility via `.flake8`).
    *   **Black (Formatter):** Enabled (Configured via `pyproject.toml`).
    *   Manual adherence to PEP 8 encouraged.

## 3. Architectural & Design Approach
*   **Overall Architectural Style:** Modular, with agent-like capabilities introduced in v4.0.0 Phase 3.
    *   *Details in `TECHNICAL_DESIGN.MD`.*
*   **Logging Strategy:** Comprehensive and persistent logging using Python's `logging` module (per ADR-007).
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
    *   `main`: Represents the latest stable release (to be tagged as v4.0.0).
    *   `develop`: Base for any v4.0.x patches or for starting v5.0.0 development.
*   **Commit Messages:** Aim for conventional commit style.

## 6. Documentation
*   **Docstring Style:** Google Python Style.
*   **Project Documentation Status:**
    *   **`CHANGELOG.MD`:** Needs final entries for v4.0.0 release (if DevLead decides to maintain it).
        *   **Status:** `Pending Update for v4.0.0 release content`
    *   **`CONTRIBUTING.MD`:** Deferred.
        *   **Status:** `Pending DevLead Enablement`
    *   **Core Docs:** `TECHNICAL_DESIGN.MD`, `FUNCTIONAL_REQUIREMENTS.MD`, `NON_FUNCTIONAL_REQUIREMENTS.MD`, `ADR-008`, `PROJECT_OVERVIEW.MD`, `AI_INSTRUCTIONS.MD`, `STATUS_LEGEND.MD` are considered final and accurate for v4.0.0.
*   **README.md (Project Root):** Requires comprehensive update to reflect all v4.0.0 features.
    *   **Status:** `Pending Update for v4.0.0 release content` (AI Collaborator will provide a draft).

## 7. Development Environment
*   **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
*   **Development OS:** **Windows** (Assumed for DevLead).
*   **Key Dependencies Installation (Windows Focus):**
    *   Ensure Python 3.9+ is installed and in PATH.
    *   Create virtual environment: `python -m venv .venv` & activate.
    *   Install packages: `pip install -r requirements.txt`.
    *   **Tesseract OCR Engine:** Must be installed system-wide and in PATH for OCR features.
    *   **(v4.0.0+) Gemini API Key:** Requires a `.env` file with `GEMINI_API_KEY=your_key`.