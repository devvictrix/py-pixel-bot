// File: docs/DEV_CONFIG.MD
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
*   **Overall Goal for First Major Deliverable:** `AI-Accelerated v1.0.0` - **COMPLETED**
*   **Overall Goal for Second Major Deliverable (Current Target):** `v2.0.0 (Advanced Visual Analysis & Rules)`
    *   This version aims to enhance the rule engine's capabilities, introduce more sophisticated analysis options, and improve performance. Details are in `FEATURE_ROADMAP.MD`.
*   **Active Version (Current Focus for Implementation):** `v2.0.0 (Analysis - OCR Confidence Thresholds)`
    *   *This version, set here, dictates the immediate components and features being developed by the AI collaborator, contributing towards the larger v2.0.0 goal.*
*   **Primary Goal for Active Version:** Enhance OCR analysis to include confidence scores and enable rules to use these scores as part of their conditions (e.g., "IF text CONTAINS 'X' AND overall_ocr_confidence > 0.85"). This involves updates to `AnalysisEngine`, `MainController` (for data packet), JSON schema for rules, and `RulesEngine`.
*   **Testing Strategy for Active Version (and towards v2.0.0):**
    *   **Unit Tests:** Deferred until core components are more stable, or upon explicit DevLead enablement.
        *   **Status:** `Pending DevLead Enablement`
    *   **Integration Tests:** Manual, focused on end-to-end scenarios for the v2.0.0 features. Log outputs will be crucial for validation.
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
    *   `main`: Represents the latest stable release (AI-Accelerated v1.0.0).
    *   `develop`: Active development branch for ongoing work towards the current overall goal (v2.0.0). Feature branches are created from `develop`.
    *   Feature branches: e.g., `feature/ocr-confidence-thresholds`, `feature/color-palette-analysis`.
*   **Commit Messages:** Aim for conventional commit style if possible (e.g., `feat: ...`, `fix: ...`, `docs: ...`).

## 6. Documentation
*   **Docstring Style:** Google Python Style.
*   **Project Documentation Status:**
    *   **`CHANGELOG.MD`:** Deferred until v2.0.0 is near completion.
        *   **Status:** `Pending DevLead Enablement`
    *   **`CONTRIBUTING.MD`:** Deferred.
        *   **Status:** `Pending DevLead Enablement`
    *   **Core Docs (Overview, Requirements, Design, ADRs):** Established, will be updated iteratively.
*   **README.md (Project Root):** v1.0.0 version complete and accurate.

## 7. Development Environment
*   **Target OS for Bot:** **Windows**
*   **Development OS:** **Windows**
*   **Key Dependencies Installation (Windows Focus):**
    ```bash
    # From requirements.txt
    # pip install opencv-python numpy Pillow pytesseract pyautogui python-dotenv CustomTkinter
    ```
    Ensure Tesseract OCR for Windows is installed system-wide and in PATH.

---