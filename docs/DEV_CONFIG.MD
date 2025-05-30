# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the **Mark-I** project. Version 4.0.0 is complete. **Focus is now on planning v5.0.0 (AI-Driven Profile Generation).**

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
*   **Overall Goal for Fourth Major Deliverable:** `v4.0.0 (Gemini-Powered Visual Intelligence)` - **COMPLETED.**
*   **Overall Goal for Fifth Major Deliverable (Current Target):** `v5.0.0 (AI-Driven Profile Generation)`
    *   This version aims to enable Mark-I to assist users in creating automation profiles by understanding high-level goals and translating them into Mark-I configurations.
*   **Active Version (Current Focus for Design & Planning):** `v5.0.0 (Phase 1 Design: AI Profile Creator - Scoping & ADR)`
    *   *This version, set here, dictates the immediate design tasks for the AI collaborator, contributing towards the larger v5.0.0 goal.*
*   **Primary Goal for Active Version:**
    1.  **AI Collaborator to draft a new Architectural Decision Record (ADR) for the "AI Profile Creator / Strategy Learning Mode."** This ADR will define the high-level architecture, approaches, key components, and interaction flows.
    2.  **AI Collaborator to propose initial updates to `TECHNICAL_DESIGN.MD`** to integrate this new capability conceptually.
    3.  **DevLead to review and approve the ADR and initial technical design direction.**
*   **Testing Strategy for v5.0.0:** Will require extensive testing of the AI's ability to generate valid and useful profiles, and the usability of the generation/refinement process. Mocking Gemini for plan generation will be important.
*   **Linting/Formatting Setup:**
    *   **Flake8 (Linter):** Enabled (Configured for Black compatibility via `.flake8`).
    *   **Black (Formatter):** Enabled (Configured via `pyproject.toml`).
    *   Manual adherence to PEP 8 encouraged.

## 3. Architectural & Design Approach
*   **Overall Architectural Style:** Modular. v5.0.0 will introduce new modules for AI-driven profile generation, possibly a "StrategyPlanner" or similar, interacting with existing engines.
    *   *Details to be defined in new ADR and `TECHNICAL_DESIGN.MD` updates.*
*   **Logging Strategy:** Comprehensive logging will be essential for diagnosing the AI profile generation process.
*   **Code Design Principles:** Readability, Simplicity, Modularity, Testability, Diagnosability.

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
    *   `main`: Represents latest stable release (v4.0.0).
    *   `develop`: Active development branch for v5.0.0. Feature branches (e.g., `feature/ai-profile-creator`) created from `develop`.
*   **Commit Messages:** Aim for conventional commit style.

## 6. Documentation
*   **Docstring Style:** Google Python Style.
*   **Project Documentation Status:**
    *   All v4.0.0 documentation considered complete and finalized (pending `README.MD` and optional `CHANGELOG.MD` final pass).
    *   **New ADR required for v5.0.0 AI Profile Creator.**
    *   `TECHNICAL_DESIGN.MD`, `FUNCTIONAL_REQUIREMENTS.MD`, `NON_FUNCTIONAL_REQUIREMENTS.MD` will require significant updates for v5.0.0 features.
*   **README.md (Project Root):** Updated for v4.0.0. Will need updates again for v5.0.0.

## 7. Development Environment
*   **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
*   **Development OS:** **Windows** (Assumed for DevLead).
*   **Key Dependencies Installation (Windows Focus):**
    *   Ensure Python 3.9+ is installed and in PATH.
    *   Create virtual environment: `python -m venv .venv` & activate.
    *   Install packages: `pip install -r requirements.txt`.
    *   **Tesseract OCR Engine:** Must be installed system-wide and in PATH for OCR features.
    *   **(v4.0.0+) Gemini API Key:** Requires a `.env` file with `GEMINI_API_KEY=your_key`.