// File: docs/FUNCTIONAL_REQUIREMENTS.MD
# Functional Requirements

This document outlines the functional requirements for the visual automation tool, describing *what* the system will do. It reflects the capabilities of the system up to and including the v2.0.0 features and the ongoing development of the v3.0.0 GUI.

## FR-CORE: Core System

*   **FR-CORE-001: Cross-Platform Operation:** The bot's core engine (capture, analysis, action) SHOULD operate on Windows, macOS, and Linux. The GUI (`CustomTkinter`) is also designed to be cross-platform. (Primary development and testing on Windows per `DEV_CONFIG.MD`).
*   **FR-CORE-002: Configuration Files (JSON):** The system MUST use JSON for saving and loading bot configurations (profiles). These profiles MUST store:
    *   General profile settings (e.g., description, monitoring interval, analysis parameters like dominant_colors_k).
    *   Definitions of screen regions to monitor (name, coordinates).
    *   Definitions of template images (name, relative filename for images stored in a `templates/` subdirectory next to the profile).
    *   A list of rules, where each rule includes:
        *   A unique name.
        *   A default region for its conditions.
        *   A condition block, which can be:
            *   A single condition with a `type` and specific parameters.
            *   A compound condition with a `logical_operator` ("AND" or "OR") and a list of `sub_conditions` (each being a single condition structure).
        *   Parameters for capturing results into variables (e.g., `capture_as` for OCR or template matching).
        *   An action block with a `type` and specific parameters, which can use captured variables via placeholder substitution.
*   **FR-CORE-003: Environment Configuration:** The system MUST read an `APP_ENV` variable (e.g., from a `.env` file via `python-dotenv`) to determine its operational environment (e.g., `development`, `uat`, `production`), primarily influencing logging configuration.
*   **FR-CORE-004: Logging:** The system MUST implement comprehensive and persistent logging for all significant operations, decisions, errors, and state changes in both the backend engine and the GUI editor. Log levels and destinations MUST be configurable based on `APP_ENV` and CLI flags, as detailed in `adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md`.

## FR-CAPTURE: Screen Region Capture Module (Bot Runtime)

*   **FR-CAPTURE-001: Define Target Region:** The user MUST be able to define one or more named rectangular regions on the screen (x, y, width, height) to be monitored. This definition is stored in the profile.
*   **FR-CAPTURE-002: Capture Specified Region:** The system MUST be able to capture image data exclusively from the defined target region(s).
*   **FR-CAPTURE-003: Real-time Capture:** The system MUST support continuous real-time capture of defined regions at a user-configurable interval (FPS/delay) during bot operation.

## FR-ANALYZE: Region Analysis Module (Bot Runtime)

*   **FR-ANALYZE-001: Pixel Color Analysis:** The system MUST allow rules to check for specific pixel colors (BGR) at relative coordinates within a region, with a configurable tolerance.
*   **FR-ANALYZE-001B: Average Color Analysis:** The system MUST allow rules to check the average color (BGR) of a region against an expected color, with a configurable tolerance.
*   **FR-ANALYZE-002: Template Matching Analysis:** The system MUST allow rules to check if a user-provided template image (referenced by filename in the profile) is present within a region, with a configurable minimum confidence threshold. Match details (location, confidence) can be captured.
*   **FR-ANALYZE-003: OCR Text Extraction & Analysis:** The system MUST be able to extract text from a region using Tesseract OCR. The analysis result MUST include both the extracted text string and an average word confidence score. This result can be captured as a variable.
*   **FR-ANALYZE-003B: OCR-Based Conditions:** Rules MUST support conditions based on OCR results, such as:
    *   Checking if the extracted text contains a specific substring (case-sensitive or insensitive).
    *   Checking if the average OCR confidence meets a minimum threshold.
*   **FR-ANALYZE-004: Configurable Analysis Rules:** Users MUST be able to define rules that link analysis outcomes to actions. Rules MUST support:
    *   Single conditions.
    *   Compound conditions using "AND" or "OR" logical operators on a list of sub-conditions. Each sub-condition can target the rule's default region or specify its own.
*   **FR-ANALYZE-005: Dominant Color Analysis:** The system MUST allow rules to check if one of the top N dominant colors (found via k-means) in a region matches an expected BGR color (with tolerance) and optionally meets a minimum percentage of occurrence.
*   **FR-ANALYZE-006: Selective Analysis (Performance):** The bot runtime (`MainController`) MUST optimize performance by only executing general pre-emptive analyses (e.g., OCR, dominant color, average color) on a given region if at least one rule in the active profile explicitly requires that type of analysis for that region. Image capture for all monitored regions always occurs.

## FR-ACTION: Action Execution Module (Bot Runtime)

*   **FR-ACTION-001: Mouse Click Simulation:** The system MUST be able to simulate mouse clicks (left, right, middle, configurable number of clicks, interval) at:
    *   Absolute screen coordinates.
    *   The center of a specified region.
    *   Coordinates relative to a specified region's top-left corner.
    *   The center of the last successfully matched template (from a `template_match_found` condition).
*   **FR-ACTION-002: Keyboard Input Simulation:** The system MUST be able to simulate:
    *   Typing a string of characters (with configurable interval).
    *   Pressing individual special keys (e.g., "enter", "ctrl", "shift").
    *   Pressing key combinations (hotkeys, e.g., "ctrl,c").
*   **FR-ACTION-003: Conditional Actions:** Actions MUST only be triggered if their associated rule's condition (single or compound) evaluates to true.
*   **FR-ACTION-004: Log Message Action:** The system MUST provide an action to write a custom message (with a configurable log level) to the application logs.
*   **FR-ACTION-005: Dynamic Action Parameters (Variables):** Action parameters (e.g., text to type, X/Y coordinates for clicks, parts of log messages) MUST be able to utilize values captured into rule-scoped variables from conditions (e.g., OCR'd text, template match details) via a placeholder substitution mechanism (e.g., `{var_name}` or `{var_name.key}`). `ActionExecutor` must attempt to convert substituted string values to appropriate types (e.g., int for coordinates) where necessary.
*   **FR-ACTION-006: Configurable Pause Before Action:** Actions SHOULD allow a configurable pause (e.g., `pyautogui_pause_before`) before their execution via PyAutoGUI.

## FR-CONFIG: Configuration & Management (CLI & GUI)

*   **FR-CONFIG-001: Save/Load Bot Profile:** Users MUST be able to save the complete bot setup to a JSON profile file and load it for execution (via CLI `run`) or editing (via GUI `edit`).
*   **FR-CONFIG-002: Variable Capture in Rules:** Conditions (specifically `ocr_contains_text` and `template_match_found`) MUST allow their primary result (full OCR text or template match details dictionary) to be captured into a named, rule-scoped variable using a `capture_as` parameter in the JSON rule definition.

## FR-UI: User Interface

*   **FR-UI-001: CLI Control:** The system MUST provide Command Line Interface (CLI) controls for:
    *   Loading and running a bot profile (`run <profile>`).
    *   Launching the region selection GUI tool for a profile (`add-region <profile>`).
    *   Launching the full GUI profile editor, optionally loading a specific profile (`edit [profile]`).
*   **FR-UI-002: GUI for Region Definition (Component):** A GUI tool (`RegionSelectorWindow`) MUST be provided for users to visually select/draw screen regions, name them, and have their coordinates saved to a profile. This tool is invokable from the CLI and the main GUI editor.
*   **FR-UI-003: Full GUI Profile Editor (`MainAppWindow` - v3.0.0 Target):**
    *   **FR-UI-003.1: Profile File Operations:** The GUI MUST allow creating new profiles, opening existing JSON profiles, saving changes to the current profile, and saving as a new profile file. It MUST manage an "unsaved changes" (dirty) state and prompt the user accordingly.
    *   **FR-UI-003.2: Settings Editing:** The GUI MUST display and allow editing of general profile settings (e.g., "profile_description", "monitoring_interval_seconds", "analysis_dominant_colors_k").
    *   **FR-UI-003.3: Region Management & Editing:** The GUI MUST allow listing, adding (invoking `RegionSelectorWindow`), removing, and interactively editing (name, X, Y, width, height via text entries, or coordinates via `RegionSelectorWindow`) defined regions.
    *   **FR-UI-003.4: Template Management & Editing:** The GUI MUST allow listing, adding (including prompting for a name and copying the selected image file to a `templates/` subdirectory relative to the profile, storing the relative path), removing (including deleting the associated image file), and interactively editing (name) templates. It MUST display a preview of the selected template image.
    *   **FR-UI-003.5: Rule Management & Editing (Comprehensive):**
        *   The GUI MUST allow listing, adding (new placeholder rule), and removing rules.
        *   For a selected rule, the GUI MUST allow editing its name and default region (via dropdown of existing regions).
        *   **Condition Editing:**
            *   The GUI MUST allow converting a rule's condition structure between "single" and "compound" (with user confirmation if data loss might occur).
            *   For single conditions: Allow selection of condition `type` from a dropdown. Dynamically display and allow editing of all relevant parameters for the selected type using appropriate input widgets (entries, option menus, checkboxes).
            *   For compound conditions: Allow selection of `logical_operator` (AND/OR). List sub-conditions with a summary. Allow adding (placeholder) and removing selected sub-conditions.
            *   **Sub-Condition Editing:** For a selected sub-condition within a compound rule, the GUI MUST allow selection of its `type` and dynamically display/allow editing of all its relevant parameters.
        *   **Action Editing:** Allow selection of action `type` from a dropdown. Dynamically display and allow editing of all relevant parameters for the selected type.
        *   Parameter fields SHOULD support use of placeholders for variables captured within the same rule (e.g., `{my_var}`).
    *   **FR-UI-003.6: Input Validation & Feedback:** The GUI MUST validate user inputs for all editable fields (names, numeric values, BGR strings, selections) before applying changes to the profile data. Clear error messages MUST be displayed to the user for invalid inputs, preventing incorrect data from being saved.
*   **FR-UI-004: User Feedback (General):** The system (CLI and GUI) MUST provide clear feedback about its operations, successes, warnings, and errors, using console messages, log files, and GUI dialogs/status indicators as appropriate.

---