// File: DEV_CONFIG.MD
# Development Configuration & Choices

This document outlines key development choices, current phase settings, and environment setup for the project.

## 1. Core Project Setup
*   **Language:** Python
*   **Python Version (Target):** 3.9+ (or as specified by dependencies like OpenCV)
*   **Package Manager:** pip
*   **Virtual Environment:** venv (standard, recommended)
    *   Example setup: `python -m venv .venv` then `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).

## 1.1. Environment Configuration (per ADR-007)
*   **Method:** `.env` file at the project root, loaded using the `python-dotenv` library.
*   **Key Variable:** `APP_ENV`
    *   **Possible Values:** `development`, `uat`, `production`.
    *   **Default for local development:** Create a `.env` file in the project root with `APP_ENV=development`.
*   **Purpose:** Controls environment-specific behavior, primarily logging verbosity, log destinations, and potentially other future settings.
*   **`.gitignore`:** The `.env` file MUST be added to `.gitignore` to prevent committing environment-specific or sensitive settings.

## 2. Current Development Phase Focus
*   **Overall Goal for First Major Deliverable:** `AI-Accelerated v1.0.0`
    *   This version aims to deliver a comprehensive suite of core functionalities as the first major output, leveraging AI-assisted development. Details are in `FEATURE_ROADMAP.MD`.
*   **Active Version (Current Focus for Implementation):** `v0.1.0 (Core Modules & Basic Interactions for AI-Accelerated v1.0.0)`
    *   *This version, set here, dictates the immediate components and features being developed by the AI collaborator, contributing towards the larger AI-Accelerated v1.0.0 goal.*
*   **Primary Goal for Active Version:** Implement core modules for region definition, capture, basic analysis (pixel/color), simple rule evaluation, foundational logging setup, and CLI control. Establish the backbone for the AI-Accelerated v1.0.0.
*   **Testing Strategy for Active Version (and towards AI-Accelerated v1.0.0):**
    *   **Unit Tests:** Deferred until core components are more stable, or upon explicit DevLead enablement.
        *   **Status:** `Pending DevLead Enablement`
    *   **Integration Tests:** Manual, focused on end-to-end scenarios for the AI-Accelerated v1.0.0 features. Log outputs will be crucial for validation.
*   **Linting/Formatting Setup:** Basic setup during initial module development (e.g., Flake8, Black to be integrated later as per Tooling Choices).

## 3. Architectural & Design Approach
*   **Overall Architectural Style:** Modular (Capture, Analysis, Action, Rules engines). Approved ADRs are foundational.
    *   *Details in `TECHNICAL_DESIGN.MD`.*
*   **Logging Strategy:** Comprehensive and persistent logging using Python's `logging` module, configured by `APP_ENV`.
    *   *Refer to `adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md` for full details.*
*   **Code Design Principles:** Readability, Simplicity (YAGNI), Modularity, Testability, Diagnosability (via logging).

## 4. Tooling Choices (Key Tools - per ADRs)
*   **Environment Management:** `python-dotenv`
*   **Logging:** Python `logging` module.
*   **Screen Capture:** `OpenCV-Python` (`opencv-python` package)
*   **Image Processing:** `OpenCV-Python`, `NumPy`, `Pillow`
*   **OCR (for AI-Accelerated v1.0.0):** `pytesseract` (Requires external Tesseract OCR engine installation)
*   **Input Simulation:** `pyautogui`
*   **Configuration Format:** JSON (built-in `json` module)
*   **CLI:** `argparse` (built-in)
*   **GUI (for AI-Accelerated v1.0.0 region selection):** `CustomTkinter`
*   **Unit Testing Framework (Future):** `pytest` (Pending DevLead Enablement)
*   **Linter (Future):** `Flake8` (Pending DevLead Enablement for active enforcement)
*   **Formatter (Future):** `Black` (Pending DevLead Enablement for active enforcement)
*   **Import Sorter (Future):** `isort` (Pending DevLead Enablement for active enforcement)

## 5. Version Control
*   **System:** Git
*   **Branching (Simplified Strategy):**
    *   `main`: Represents the latest stable release (or the AI-Accelerated v1.0.0 once achieved).
    *   `develop`: Active development branch for ongoing work towards the current overall goal. Feature branches are created from `develop`.
    *   Feature branches: e.g., `feature/core-capture-engine`, `feature/gui-region-selector`.
*   **Commit Messages:** Aim for conventional commit style if possible (e.g., `feat: ...`, `fix: ...`, `docs: ...`).

## 6. Documentation
*   **Docstring Style:** Google Python Style.
*   **Project Documentation Status:**
    *   **`CHANGELOG.MD`:** Deferred until AI-Accelerated v1.0.0 is near completion.
        *   **Status:** `Pending DevLead Enablement`
    *   **`CONTRIBUTING.MD`:** Deferred.
        *   **Status:** `Pending DevLead Enablement`
    *   **Core Docs (Overview, Requirements, Design, ADRs):** Established, will be updated iteratively.
*   **README.md (Project Root):** A good `README.md` should be created early, outlining the project, setup instructions (including virtual environment and `.env` file), and basic usage.

## 7. Development Environment
*   **Target OS for Bot:** **Windows**
*   **Development OS:** **Windows**
*   **Key Dependencies Installation (Windows Focus):**
    ```bash
    # Example for a requirements.txt (to be created)
    # pip install opencv-python numpy Pillow pytesseract pyautogui python-dotenv CustomTkinter
    ```
    Ensure Tesseract OCR for Windows is installed system-wide if OCR features are being developed/tested.

---