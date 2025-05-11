// File: docs/FUNCTIONAL_REQUIREMENTS.MD
# Functional Requirements

This document outlines the functional requirements for the visual automation tool, describing *what* the system will do.

## FR-CORE: Core System

*   **FR-CORE-001: Cross-Platform Operation:** The bot SHOULD operate on Windows, macOS, and Linux for its core engine. The GUI (`CustomTkinter`) is also cross-platform.
*   **FR-CORE-002: Configuration Files:** The system MUST use JSON for saving and loading bot configurations (profiles), including region definitions, template references, analysis rules (single and compound), variable captures, and associated actions.
*   **FR-CORE-003: Environment Configuration:** The system MUST read an `APP_ENV` variable (e.g., from a `.env` file) to determine its operational environment (e.g., `development`, `uat`, `production`), primarily influencing logging.
*   **FR-CORE-004: Logging:** The system MUST implement comprehensive logging at important operational steps (both backend and GUI), with log levels and destinations configurable based on `APP_ENV`, as detailed in `adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md`.

## FR-CAPTURE: Screen Region Capture Module

*   **FR-CAPTURE-001: Define Target Region:** The user MUST be able to define one or more rectangular regions on the screen to be monitored.
    *   Initially via coordinates in a configuration file.
    *   Achieved: Via a GUI tool (`RegionSelectorWindow` accessible via CLI `add-region` and integrated into the full GUI editor).
*   **FR-CAPTURE-002: Capture Specified Region:** The system MUST be able to capture the image data only from the defined target region(s).
*   **FR-CAPTURE-003: Real-time/On-demand Capture:** The system MUST support continuous real-time capture (at a configurable FPS/delay) for bot runtime. The GUI editor does not perform continuous capture.

## FR-ANALYZE: Region Analysis Module

*   **FR-ANALYZE-001: Pixel Color Analysis:** The system MUST allow users to check for specific pixel colors.
*   **FR-ANALYZE-001B: Average Color Analysis:** The system MUST allow users to check for average colors within the captured region.
*   **FR-ANALYZE-002: Basic Image Matching (Template Matching):** The system MUST allow users to check if a small user-provided template image is present within the captured region, with configurable confidence.
*   **FR-ANALYZE-003: OCR Text Extraction:** The system MUST be able to extract text from the captured region using OCR, providing text and average confidence scores.
*   **FR-ANALYZE-003B: OCR Confidence Usage:** Rules MUST be able to use the OCR confidence score as a condition.
*   **FR-ANALYZE-004: Configurable Analysis Rules:** Users MUST be able to define rules or conditions based on the analysis output (e.g., "IF color IS red THEN...", "IF text CONTAINS 'Start' AND confidence > 80 THEN...", "IF template 'icon.png' IS found THEN..."), supporting single and compound (AND/OR) conditions, as per `adrs/ADR-004`.
*   **FR-ANALYZE-005: Dominant Color Analysis:** The system MUST be able to identify dominant colors in a region and allow rules to check against these.
*   **FR-ANALYZE-006: Selective Analysis (Performance):** The system (specifically `MainController` during bot runtime) SHOULD only perform general analyses (like OCR, dominant color) on a region if an active rule requires that analysis type for that region.

## FR-ACTION: Action Execution Module

*   **FR-ACTION-001: Mouse Click Simulation (Targeted):** The system MUST be able to simulate mouse clicks (left, right, middle) at specific coordinates, relative to regions, or relative to a found pattern/text.
*   **FR-ACTION-002: Keyboard Input Simulation:** The system MUST be able to simulate keyboard presses (character keys, special keys) and typing strings.
*   **FR-ACTION-003: Conditional Actions:** Actions MUST be triggerable based on the outcome of the analysis rules.
*   **FR-ACTION-004: Log Message Action:** The system MUST provide an action to write a custom message to the application logs.
*   **FR-ACTION-005: Dynamic Action Parameters (Variables):** Action parameters (e.g., text to type, coordinates) MUST be configurable to use values captured into variables by conditions within the same rule.

## FR-CONFIG: Configuration & Management

*   **FR-CONFIG-001: Save/Load Bot Profile:** Users MUST be able to save the entire bot setup (defined regions, templates, analysis rules, variable captures, associated actions, settings) to a JSON profile file and load it later, via both CLI (for runtime) and the GUI editor.
*   **FR-CONFIG-002: Start/Stop Bot Operation:** Users MUST be able to start and stop the bot's monitoring and action execution loop via the CLI (`run` command).
*   **FR-CONFIG-003: Variable Capture in Rules:** Conditions (e.g., OCR, template match) MUST allow specific results to be captured into named, rule-scoped variables.

## FR-UI: User Interface

*   **FR-UI-001: CLI Control (Core):** The system MUST provide Command Line Interface (CLI) controls for:
    *   Loading and running a bot profile (`run <profile>`).
    *   Launching the region selection GUI tool (`add-region <profile>`).
    *   **Launching the full GUI profile editor (`edit [profile]`).**
*   **FR-UI-002: GUI for Region Definition (Achieved):** A GUI tool (`RegionSelectorWindow`) IS provided for users to visually select/draw screen regions.
*   **FR-UI-003: Full GUI for Profile & Rule Configuration (v3.0.0 Target - In Progress):**
    *   **FR-UI-003.1: Profile Operations:** The GUI MUST allow creating new profiles, opening existing JSON profiles, saving, and saving as.
    *   **FR-UI-003.2: Settings Editing:** GUI MUST allow editing of general profile settings (description, interval, dominant K).
    *   **FR-UI-003.3: Region Management:** GUI MUST allow adding (via `RegionSelectorWindow`), removing, and editing (name, coordinates) regions.
    *   **FR-UI-003.4: Template Management:** GUI MUST allow adding (with file selection and copy to profile's `templates/` dir), removing (including associated file), renaming templates, and previewing template images.
    *   **FR-UI-003.5: Rule Management & Editing:**
        *   GUI MUST allow adding and removing rules.
        *   GUI MUST allow editing basic rule properties (name, default region).
        *   GUI MUST allow changing a rule's condition structure (single vs. compound) and main condition/action types.
        *   GUI MUST allow editing all parameters for all defined single condition types and action types with appropriate input widgets and validation.
        *   GUI MUST allow adding/removing sub-conditions for compound rules.
        *   GUI MUST allow editing the type and all parameters for individual sub-conditions within a compound rule.
    *   **FR-UI-003.6: Input Validation:** The GUI MUST validate user inputs for parameters and settings, providing clear error feedback.
*   **FR-UI-004: User Feedback (GUI & CLI):** The system MUST provide clear feedback to the user about its current state and operations, primarily through console output (influenced by logging configuration), log files, and GUI messages/status indicators.

---