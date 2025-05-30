# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the **Mark-I** project.
**Version 5.0.0 (AI-Driven Profile Generation) is now considered complete and stable.**
Focus will shift to planning for future enhancements (`vFuture`).

## 1. Core Project Setup

- **Project Name (Informal):** Mark-I
- **Python Package Name:** `mark_i`
- **Language:** Python
- **Python Version (Target):** 3.9+ (or as specified by dependencies like CustomTkinter or OpenCV)
- **Package Manager:** pip
- **Virtual Environment:** venv (standard, recommended)
  - Example setup: `python -m venv .venv` then `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).

## 1.1. Environment Configuration (per ADR-007, ADR-008)

- **Method:** `.env` file at the project root, loaded using the `python-dotenv` library.
- **Key Variables:**
  - `APP_ENV`: Controls logging, etc.
    - **Possible Values:** `development`, `uat`, `production`.
    - **Default for local development:** Create a `.env` file in the project root with `APP_ENV=development`.
  - **`GEMINI_API_KEY` (Required for v4.0.0+):** Your API key for accessing Google Gemini API.
    - Obtain from Google AI Studio or Google Cloud Console.
    - Add `GEMINI_API_KEY=your_api_key_here` to your `.env` file.
- **Purpose:** Controls environment-specific behavior (logging, API keys, etc.).
- **`.gitignore`:** The `.env` file **MUST** be added to `.gitignore` to prevent committing environment-specific or sensitive settings (like API keys). The `logs/` directory should also be ignored.

## 2. Current Development Phase Focus

- **Overall Goal for Fourth Major Deliverable:** `v4.0.0 (Gemini-Powered Visual Intelligence)` - **COMPLETED.**
- **Overall Goal for Fifth Major Deliverable:** `v5.0.0 (AI-Driven Profile Generation)` - **COMPLETED.**
  - This version enabled Mark-I to assist users in creating automation profiles by understanding high-level goals and translating them into Mark-I configurations via an interactive AI-assisted wizard.
  - Phase 1 (Core Backend Logic: `StrategyPlanner`, `ProfileGenerator` core) - `COMPLETED`.
  - Phase 2 (GUI Workflow & AI-Assisted Element Suggestion) - `COMPLETED`.
  - Phase 3 (Integration & Refinement) - `COMPLETED`.
  - Phase 4 (Documentation) - `COMPLETED`.

- **Active Version (Current State):** `v5.0.0 (AI-Driven Profile Generation) - STABLE`
  - **Primary Goal for Active Version:** This version is feature-complete. Current activities involve post-release refactoring, unit test implementation, E2E testing, and planning for future development cycles (`vFuture`).
- **Next Development Cycle Focus:** `vFuture - Planning Phase`
  - Evaluate features listed under "vFuture" in `FEATURE_ROADMAP.MD`.
  - Gather user feedback on v5.0.0 to inform priorities.
  - Consider revisiting deferred features like the "Profile Refinement Loop".
- **Linting/Formatting Setup:**
  - **Flake8 (Linter):** Enabled (Configured for Black compatibility via `.flake8`).
  - **Black (Formatter):** Enabled (Configured via `pyproject.toml`).
  - Manual adherence to PEP 8 encouraged.

## 3. Architectural & Design Approach

- **Overall Architectural Style:** Modular, with the `generation` package and `ProfileCreationWizardWindow` GUI components being key additions in v5.0.0.
  - _Details in `TECHNICAL_DESIGN.MD` Section 15 and ADR-009._
- **Logging Strategy:** Comprehensive logging implemented for the entire profile generation process, including GUI interactions and AI suggestion calls.
- **Code Design Principles:** Readability, Simplicity, Modularity, Testability, Diagnosability.

## 4. Tooling Choices (Key Tools - per ADRs)

- **Environment Management:** `python-dotenv`
- **Logging:** Python `logging` module.
- **Screen Capture:** `Pillow` (`ImageGrab`), `OpenCV-Python`.
- **Image Processing:** `OpenCV-Python`, `NumPy`, `Pillow`.
- **OCR:** `pytesseract`.
- **Input Simulation:** `pyautogui`.
- **Configuration Format:** JSON.
- **CLI:** `argparse`.
- **GUI:** `CustomTkinter`.
- **AI Vision API (v4.0.0+):** `google-generativeai` (Python SDK for Gemini).
- **Unit Testing Framework:** `pytest` (Status: `Planning` - for v5.0.2 implementation)
- **Linter:** `Flake8` (Status: `Enabled`)
- **Formatter:** `Black` (Status: `Enabled`)
- **Import Sorter (Future):** `isort` (Status: `Pending DevLead Enablement`)

## 5. Version Control

- **System:** Git
- **Branching (Simplified Strategy):**
  - `main`: Should now reflect the v5.0.0 stable release.
  - `develop`: Active development branch for any ongoing minor fixes for v5.0.0 or for starting `vFuture` work. Feature branches for new development are created from `develop`.
- **Commit Messages:** Aim for conventional commit style.

## 6. Documentation

- **Docstring Style:** Google Python Style.
- **Project Documentation Status:**
  - v4.0.0 documentation finalized.
  - v5.0.0 documentation (ADRs, `TECHNICAL_DESIGN.MD` Section 15, FRs/NFRs, `PROJECT_OVERVIEW.MD`, `README.MD`) updated and complete.
  - All new code modules for v5.0.0 (`StrategyPlanner`, `ProfileGenerator`, `ProfileCreationWizardWindow`, `SubImageSelectorWindow`) include comprehensive docstrings.
- **README.md (Project Root):** Updated for v5.0.0.

## 7. Development Environment

- **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
- **Development OS:** **Windows** (Assumed for DevLead).
- **Key Dependencies Installation (Windows Focus):**
  - Ensure Python 3.9+ is installed and in PATH.
  - Create virtual environment: `python -m venv .venv` & activate.
  - Install packages: `pip install -r requirements.txt`. (Ensure `requirements.txt` is created and maintained).
  - **Tesseract OCR Engine:** Must be installed system-wide and in PATH for OCR features.
  - **(v4.0.0+) Gemini API Key:** Requires a `.env` file with `GEMINI_API_KEY=your_key`.