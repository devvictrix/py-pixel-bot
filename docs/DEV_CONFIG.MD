// File: docs/DEV_CONFIG.MD

# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the **Mark-I** project. Version 4.0.0 is complete. **Focus is now on designing and implementing v5.0.0 (AI-Driven Profile Generation) Phase 2: GUI Workflow and AI-Assisted Element Suggestion.**

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
- **Overall Goal for Fifth Major Deliverable (Current Target):** `v5.0.0 (AI-Driven Profile Generation)`
  - This version aims to enable Mark-I to assist users in creating automation profiles by understanding high-level goals and translating them into Mark-I configurations.
  - Phase 1 (Core Backend Logic: `StrategyPlanner`, `ProfileGenerator` core) - `COMPLETED`.
- **Active Version (Current Focus for Implementation):** `v5.0.0 (Phase 2 Implementation: GUI for AI Profile Creation Workflow & AI-Assisted Element Suggestion)`
  - _This version dictates the immediate GUI implementation tasks for the AI collaborator, building upon the approved designs and backend logic._
- **Primary Goal for Active Version:**
  1.  **AI Collaborator to implement the `ProfileCreationWizardWindow` GUI:** This includes all UI screens (goal input, plan review, iterative step definition for regions/logic), user interaction logic, calls to `StrategyPlanner` and `ProfileGenerator` (including its AI-assist methods), display of AI suggestions (with visual overlays), and handling of user inputs/confirmations for defining profile elements interactively.
  2.  **AI Collaborator to implement template image file saving** within `ProfileGenerator.save_generated_profile()`.
  3.  **DevLead to review the GUI implementation and AI-assist integration.**
  4.  **Proceed to thorough testing upon implementation review.**
- **Testing Strategy for v5.0.0 Phase 2:** Will involve intensive manual testing of the interactive `ProfileCreationWizardWindow`, the quality and usability of AI suggestions for regions/logic/elements, the template capture flow, and the correctness of the finally generated profile.
- **Linting/Formatting Setup:**
  - **Flake8 (Linter):** Enabled (Configured for Black compatibility via `.flake8`).
  - **Black (Formatter):** Enabled (Configured via `pyproject.toml`).
  - Manual adherence to PEP 8 encouraged.

## 3. Architectural & Design Approach

- **Overall Architectural Style:** Modular, with a new `generation` package and new GUI components for the AI Profile Creator.
  - _Details in `TECHNICAL_DESIGN.MD` Section 15 and ADR-009._
- **Logging Strategy:** Comprehensive logging for the entire profile generation process, including GUI interactions and AI suggestion calls.
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
- **Unit Testing Framework (Future):** `pytest` (Status: `Pending DevLead Enablement`)
- **Linter:** `Flake8` (Status: `Enabled`)
- **Formatter:** `Black` (Status: `Enabled`)
- **Import Sorter (Future):** `isort` (Status: `Pending DevLead Enablement`)

## 5. Version Control

- **System:** Git
- **Branching (Simplified Strategy):**
  - `main`: Contains the v4.0.0 release.
  - `develop`: Active development branch for v5.0.0. Feature branches for v5.0.0 Phase 2 (e.g., `feature/ai-profile-wizard-gui`) are created from `develop`.
- **Commit Messages:** Aim for conventional commit style.

## 6. Documentation

- **Docstring Style:** Google Python Style.
- **Project Documentation Status:**
  - v4.0.0 documentation is finalized.
  - ADR-009 approved for v5.0.0.
  - `TECHNICAL_DESIGN.MD` Section 15 (including GUI workflow and AI-assist logic) is designed for v5.0.0 Phase 2.
  - `FUNCTIONAL_REQUIREMENTS.MD` and `NON_FUNCTIONAL_REQUIREMENTS.MD` updated for v5.0.0.
- **README.md (Project Root):** Will need major updates upon v5.0.0 completion.

## 7. Development Environment

- **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
- **Development OS:** **Windows** (Assumed for DevLead).
- **Key Dependencies Installation (Windows Focus):**
  - Ensure Python 3.9+ is installed and in PATH.
  - Create virtual environment: `python -m venv .venv` & activate.
  - Install packages: `pip install -r requirements.txt`.
  - **Tesseract OCR Engine:** Must be installed system-wide and in PATH for OCR features.
  - **(v4.0.0+) Gemini API Key:** Requires a `.env` file with `GEMINI_API_KEY=your_key`.
