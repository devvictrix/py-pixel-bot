// File: docs/DEV_CONFIG.MD
# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the project.

## 1. Core Project Setup
*   **Language:** Python
*   **Python Version (Target):** 3.9+ (or as specified by dependencies like CustomTkinter or OpenCV)
*   **Package Manager:** pip
*   **Virtual Environment:** venv (standard, recommended)
    *   Example setup: `python -m venv .venv` then `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).

## 1.1. Environment Configuration (per ADR-007)
*   **Method:** `.env` file at the project root, loaded using the `python-dotenv` library.
*   **Key Variable:** `APP_ENV`
    *   **Possible Values:** `development`, `uat`, `production`.
    *   **Default for local development:** Create a `.env` file in the project root with `APP_ENV=development`.
*   **Purpose:** Controls environment-specific behavior, primarily logging verbosity (for file and console handlers), log destinations, and potentially other future settings.
*   **`.gitignore`:** The `.env` file MUST be added to `.gitignore` to prevent committing environment-specific or sensitive settings. The `logs/` directory and `profiles/templates/` (if users add their own templates there directly, though the GUI aims to manage copies) should also be considered for `.gitignore`, though template images *essential for example profiles* might be version-controlled. For now, `logs/` and `.env` are key.

## 2. Current Development Phase Focus
*   **Overall Goal for First Major Deliverable:** `AI-Accelerated v1.0.0` - **COMPLETED**
*   **Overall Goal for Second Major Deliverable:** `v2.0.0 (Advanced Visual Analysis & Rules)` - **COMPLETED**
*   **Overall Goal for Third Major Deliverable (Current Target):** `v3.0.0 (Enhanced GUI & Usability)`
    *   This version aims to provide a comprehensive graphical user interface for all aspects of bot configuration and management, significantly improving ease of use. Details are in `FEATURE_ROADMAP.MD`.
*   **Active Version (Current Focus for Implementation):** `v3.0.0 (GUI - Phase 1.8.1: Input Validation & Refinements)`
    *   *This version, set here, dictates the immediate components and features being developed by the AI collaborator, contributing towards the larger v3.0.0 goal.*
*   **Primary Goal for Active Version:** Enhance the existing GUI (`MainAppWindow`) by implementing robust input validation for all editable fields (profile settings, region attributes, template names, rule parameters), providing clear user feedback on errors. Also, dynamically update the "Convert Condition Structure" button text. This phase focuses on solidifying the GUI's data integrity and improving UX.
*   **Testing Strategy for Active Version (and towards v3.0.0):**
    *   **Unit Tests:** Deferred until core components (especially complex GUI interactions or critical backend logic not yet covered) are more stable, or upon explicit DevLead enablement.
        *   **Status:** `Pending DevLead Enablement`
    *   **Integration Tests:** Manual, focused on end-to-end scenarios for the target version features. Log outputs are crucial for validation. GUI interactions (creating/editing profiles, all fields, all buttons) will be tested manually by DevLead.
*   **Linting/Formatting Setup:**
    *   **Flake8 (Linter):** Configured via `.flake8` file in project root (max-line-length: 99, ignores for Black compatibility).
        *   **Status:** `Enabled (Configured for Black compatibility)`
    *   **Black (Formatter):** Configured via `pyproject.toml` (line-length: 99).
        *   **Status:** `Enabled (Initial Config via pyproject.toml)`
    *   Manual adherence to PEP 8 is still encouraged for aspects not covered by Black.

## 3. Architectural & Design Approach
*   **Overall Architectural Style:** Modular (Capture, Analysis, Action, Rules engines, UI components). Approved ADRs are foundational.
    *   *Details in `TECHNICAL_DESIGN.MD`.*
*   **Logging Strategy:** Comprehensive and persistent logging using Python's `logging` module, configured by `APP_ENV` and CLI flags. All significant operations in both backend and GUI must be logged.
    *   *Refer to `adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md` for full details.*
*   **Code Design Principles:** Readability, Simplicity (YAGNI - You Ain't Gonna Need It), Modularity, Testability (even if tests are manual for now), Diagnosability (heavily reliant on thorough logging). Adherence to Black formatting and configured Flake8 rules.

## 4. Tooling Choices (Key Tools - per ADRs)
*   **Environment Management:** `python-dotenv`
*   **Logging:** Python `logging` module.
*   **Screen Capture:** `Pillow` (`ImageGrab` for Windows capture), `OpenCV-Python` (for image format conversion and potential alternative capture).
*   **Image Processing:** `OpenCV-Python`, `NumPy`, `Pillow`.
*   **OCR:** `pytesseract` (Requires external Tesseract OCR engine installation).
*   **Input Simulation:** `pyautogui`.
*   **Configuration Format:** JSON (built-in `json` module).
*   **CLI:** `argparse` (built-in).
*   **GUI:** `CustomTkinter` (and its dependency `Pillow`).
*   **Unit Testing Framework (Future):** `pytest` (Status: `Pending DevLead Enablement`)
*   **Linter:** `Flake8` (Status: `Enabled (Configured for Black compatibility)`)
    *   Configuration: `.flake8` file in project root.
*   **Formatter:** `Black` (Status: `Enabled (Initial Config via pyproject.toml)`)
    *   Configuration: `pyproject.toml` file in project root.
*   **Import Sorter (Future):** `isort` (Status: `Pending DevLead Enablement` for active enforcement)

## 5. Version Control
*   **System:** Git
*   **Branching (Simplified Strategy):**
    *   `main`: Represents the latest stable release (currently post-v2.0.0).
    *   `develop`: Active development branch for ongoing work towards the current overall goal (v3.0.0). Feature branches (e.g., `feature/gui-input-validation`) are created from `develop`.
*   **Commit Messages:** Aim for conventional commit style where practical (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `style: ...`, `test: ...`, `chore: ...`).

## 6. Documentation
*   **Docstring Style:** Google Python Style for all new/updated functions and classes.
*   **Project Documentation Status:**
    *   **`CHANGELOG.MD`:** To be created/updated upon completion of v2.0.0 (to document its features) and then maintained for v3.0.0.
        *   **Status:** `Pending DevLead Enablement for v2.0.0 content`
    *   **`CONTRIBUTING.MD`:** Deferred until project is more mature and open for external contributions.
        *   **Status:** `Pending DevLead Enablement`
    *   **Core Docs (`PROJECT_OVERVIEW.MD`, `REQUIREMENTS.MD`, `TECHNICAL_DESIGN.MD`, ADRs):** Established, updated iteratively as features are designed and implemented. `AI_INSTRUCTIONS.MD` is the primary guide for AI collaboration.
*   **README.md (Project Root):** Current version reflects AI-Accelerated v1.0.0. It will need significant updates to cover v2.0.0 features and especially the v3.0.0 GUI editor functionality once that is stable.

## 7. Development Environment
*   **Target OS for Bot Runtime:** **Windows** (Primary initial focus).
*   **Development OS:** **Windows** (Assumed for DevLead).
*   **Key Dependencies Installation (Windows Focus):**
    *   Ensure Python 3.9+ is installed and in PATH.
    *   Create virtual environment: `python -m venv .venv` & activate.
    *   Install packages: `pip install -r requirements.txt` (once `requirements.txt` is finalized and contains all dependencies like `opencv-python`, `numpy`, `Pillow`, `pytesseract`, `pyautogui`, `python-dotenv`, `CustomTkinter`, `flake8`, `black`).
    *   **Tesseract OCR Engine:** Must be installed system-wide (e.g., from UB Mannheim installer for Windows) AND its installation directory must be added to the system `PATH` environment variable for `pytesseract` to find it. Language data packs (e.g., for English: `eng`) should also be installed with Tesseract.