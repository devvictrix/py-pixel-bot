# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the **Mark-I** project. **It reflects the shift towards v4.0.0 (Gemini-Powered Visual Intelligence).**

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
*   **Overall Goal for First Major Deliverable:** `AI-Accelerated v1.0.0` - **COMPLETED**
*   **Overall Goal for Second Major Deliverable:** `v2.0.0 (Advanced Visual Analysis & Rules)` - **COMPLETED**
*   **Overall Goal for Third Major Deliverable:** `v3.0.0 (Enhanced GUI & Usability)` - **COMPLETED**
*   **Overall Goal for Fourth Major Deliverable (Current Target):** `v4.0.0 (Gemini-Powered Visual Intelligence)`
    *   This version integrates the Google Gemini API to enhance visual understanding, enabling more robust and context-aware automation rules. Details are in `FEATURE_ROADMAP.MD` and `ADR-008`.
*   **Active Version (Current Focus for Implementation):** `v4.0.0 (Gemini - Phase 2 Design: Gemini-Informed Decision Making)`
    *   *This version, set here, dictates the immediate components and features being designed and developed by the AI collaborator, contributing towards the larger v4.0.0 goal.*
*   **Primary Goal for Active Version:**
    1.  **AI Collaborator to design the "Gemini-Informed Decision Making" feature (Phase 2):**
        *   Develop detailed design specifications for a `GeminiDecisionModule`.
        *   Outline how user goals will be translated for Gemini and how Gemini's suggestions for actions (from a limited, predefined set) will be processed and executed safely by Mark-I.
        *   Propose updates to `TECHNICAL_DESIGN.MD` and determine if a new ADR is required for architectural changes.
    2.  **DevLead to review and approve the design.**
    3.  **AI Collaborator to proceed with prototyping and implementation upon design approval.**
*   **Testing Strategy for Active Version (and towards v4.0.0):**
    *   **Unit Tests:** Deferred until core components are more stable, or upon explicit DevLead enablement. **Testing `GeminiAnalyzer` and the new `GeminiDecisionModule` will require mocking the external `google-generativeai` API.**
        *   **Status:** `Pending DevLead Enablement`
    *   **Integration Tests (Phase 2 Focus):** Will involve manual testing of end-to-end scenarios where Gemini influences action selection. Log outputs will be crucial. GUI interactions for specifying goals/tasks will also require manual testing.
*   **Linting/Formatting Setup:**
    *   **Flake8 (Linter):** Enabled (Configured for Black compatibility via `.flake8`).
    *   **Black (Formatter):** Enabled (Configured via `pyproject.toml`).
    *   Manual adherence to PEP 8 encouraged.

## 3. Architectural & Design Approach
*   **Overall Architectural Style:** Modular (Capture, Analysis, Action, Rules, Gemini engines, UI). Approved ADRs are foundational.
    *   *Details in `TECHNICAL_DESIGN.MD`.*
*   **Logging Strategy:** Comprehensive and persistent logging using Python's `logging` module (per ADR-007). **v4.0.0: Logging must include details of Gemini API interactions, including decision-making processes.**
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
    *   `main`: Represents the latest stable release (currently post-v4.0.0 Phase 1.5).
    *   `develop`: Active development branch for ongoing work towards the current overall goal (v4.0.0 Phase 2). Feature branches (e.g., `feature/gemini-decision-module`) are created from `develop`.
*   **Commit Messages:** Aim for conventional commit style.

## 6. Documentation
*   **Docstring Style:** Google Python Style.
*   **Project Documentation Status:**
    *   **`CHANGELOG.MD`:** Should be updated for v4.0.0 Phase 1.5 release and maintained for Phase 2.
        *   **Status:** `Pending DevLead Update for v4.0.0 Phase 1.5 content`
    *   **`CONTRIBUTING.MD`:** Deferred.
        *   **Status:** `Pending DevLead Enablement`
    *   **Core Docs:** Established, updated iteratively. `ADR-008` guides v4.0.0. `AI_INSTRUCTIONS.MD` updated for v4.0.0 Phase 2. `TECHNICAL_DESIGN.MD`, Requirements, NFRs updated for v4.0.0 (Phase 1 & 1.5). Will require significant updates for Phase 2.
*   **README.md (Project Root):** Needs updates for **v4.0.0 (Gemini)** features once stable.

## 7. Development Environment
*   **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
*   **Development OS:** **Windows** (Assumed for DevLead).
*   **Key Dependencies Installation (Windows Focus):**
    *   Ensure Python 3.9+ is installed and in PATH.
    *   Create virtual environment: `python -m venv .venv` & activate.
    *   Install packages: `pip install -r requirements.txt`.
    *   **Tesseract OCR Engine:** Must be installed system-wide and in PATH for OCR features.
    *   **(v4.0.0+) Gemini API Key:** Requires a `.env` file with `GEMINI_API_KEY=your_key`.