// File: docs/TECHNICAL_DESIGN.MD
# TECHNICAL_DESIGN.MD
# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, AI-Accelerated v1.0.0 and v2.0.0 (Advanced Visual Analysis & Rules) are complete. Development for v3.0.0 (Enhanced GUI & Usability) is now underway, with Phase 1.8.1 (GUI Input Validation & Refinements) of the Full GUI being the current focus.

## 1. Core Architecture

The tool is modular, comprising several key Python components:

*   **`core.config_manager` Module:**
    *   `load_environment_variables()` function: Called at application startup to load `.env` (containing `APP_ENV`) using `python-dotenv` (per ADR-007).
    *   `ConfigManager` class: Responsible for loading, validating (basic structure), providing access to, and saving bot profiles (JSON files from the `profiles/` directory, per ADR-003). It also provides the base path for profile-related assets like templates.
    *   **Utilized by the `MainAppWindow` (GUI) for loading, saving, and path resolution for profiles and associated template images.**
*   **`core.logging_setup` Module:**
    *   `setup_logging()` function: Called after environment variables are loaded. Initializes Python's `logging` system based on `APP_ENV`, configuring handlers (console, date-stamped rotating file), formatters, and log levels (per ADR-007). CLI flags can override console log level.
*   **`engines.capture_engine.CaptureEngine` Class:**
    *   Responsible for capturing image data from specified screen regions using `Pillow.ImageGrab.grab(bbox=(x, y, x + width, y + height))` for Windows capture (per ADR-001).
    *   Converts captured Pillow Image objects to OpenCV BGR NumPy arrays for consistent use by the `AnalysisEngine`.
*   **`engines.analysis_engine.AnalysisEngine` Class:**
    *   Performs various analyses on captured image regions (NumPy BGR arrays).
    *   Provides methods for:
        *   Pixel color analysis (`analyze_pixel_color`).
        *   Average color calculation (`analyze_average_color`).
        *   Template matching (`match_template`) using OpenCV (per ADR-001).
        *   OCR text extraction (`ocr_extract_text`) using `pytesseract`, returning a dictionary with extracted `text` and an `average_confidence` score.
        *   Dominant color analysis (`analyze_dominant_colors`) using k-means clustering, returning a list of dominant BGR colors and their pixel percentages.
*   **`engines.rules_engine.RulesEngine` Class:**
    *   Evaluates rules based on analysis results.
    *   Supports single conditions, compound conditions (AND/OR logic per ADR-004), and rule-scoped variable capture and substitution.
    *   Upon initialization (`__init__`): Pre-parses all rules in the loaded profile to determine the specific types of general analyses (e.g., "ocr", "dominant_color", "average_color") required for each region. This information is stored in `_analysis_requirements_per_region`.
    *   Provides `get_analysis_requirements_for_region()` for `MainController` to enable selective analysis.
    *   Retrieves rules from `ConfigManager` (via profile data).
    *   Uses analysis results (which may be selectively populated by `MainController`) from the `all_region_data` packet. Includes fallbacks to attempt on-demand calculation for certain analysis types if pre-analyzed data is unexpectedly missing but the raw image is available.
    *   Triggers actions via `ActionExecutor`.
*   **`engines.action_executor.ActionExecutor` Class:**
    *   Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
    *   Calculates target coordinates for actions based on various `target_relation` types.
    *   Handles type conversion (e.g., string to int/float) for action parameters that may have been substituted from string variables, with appropriate validation and logging.
*   **`main_controller.MainController` Class:**
    *   Orchestrates the main bot operation loop for runtime execution.
    *   Runs the monitoring loop in a separate thread (per ADR-006) using `threading.Event` for graceful shutdown.
    *   For each monitored region in a profile:
        *   Instructs `CaptureEngine` to capture the image (always performed).
        *   Queries the `RulesEngine` instance (via `get_analysis_requirements_for_region`) to get the set of required general analyses for the current region.
        *   Conditionally instructs `AnalysisEngine` to perform *only* those required general analyses.
        *   Collects available analysis results (and the captured image) into a data packet for that region.
    *   Passes the dictionary of all region data packets to `RulesEngine.evaluate_rules()`.
*   **`ui.cli` Module:**
    *   Provides the Command-Line Interface using `argparse` (per ADR-005).
    *   Handles subcommands: `run <profile>`, `add-region <profile>`, and `edit [profile]`.
*   **`ui.gui.region_selector.RegionSelectorWindow` Class:**
    *   A `CustomTkinter.CTkToplevel` window for graphically selecting screen regions. Used by the `add-region` CLI command and integrated into the `MainAppWindow` for adding/editing region coordinates.
*   **`ui.gui.main_app_window.MainAppWindow` Class (v3.0.0):**
    *   The main application window (`CustomTkinter.CTk`) for the full GUI profile editor.
    *   Responsible for the overall layout, menu operations (File: New, Open, Save, etc.), and managing the lifecycle of profile data (loading from/saving to JSON via `ConfigManager`).
    *   Contains UI panels for editing profile settings, regions, templates (including file management and image previews), and rules.
    *   Rule editing UI supports: editing name/default region; converting condition structure (single/compound); selecting condition/action types; dynamically rendering and editing parameters for selected types (including for sub-conditions); adding/removing sub-conditions.
    *   Implements input validation for all editable fields with user feedback via message boxes.
    *   Manages an "unsaved changes" (dirty) state.
*   **`__main__.py` (in `src/`):**
    *   The main application entry point (`python -m py_pixel_bot`).
    *   Handles initial `sys.path` adjustments for module resolution.
    *   Loads environment variables via `core.config_manager.load_environment_variables()`.
    *   Sets up logging via `core.logging_setup.setup_logging()`.
    *   Parses CLI arguments using `ui.cli.create_parser()`.
    *   Adjusts console logging verbosity based on CLI flags.
    *   Dispatches to the appropriate command handler function in `ui.cli` (e.g., `handle_run` starts `MainController`, `handle_edit` starts `MainAppWindow`).

## 2. Key Libraries & Justifications (Summary from ADRs)
    *   Environment Management: `python-dotenv` (ADR-007)
    *   Logging: Python `logging` module (ADR-007)
    *   Screen Capture: `Pillow` (`ImageGrab` for Windows), `OpenCV-Python` (for conversion and potential alternatives) (ADR-001).
    *   Image Processing & Analysis: `OpenCV-Python` (cv2), `NumPy`, `Pillow` (ADR-001).
    *   OCR: `pytesseract` (ADR-001).
    *   Input Simulation: `pyautogui` (ADR-002).
    *   Configuration Storage: `json` (Python built-in) (ADR-003).
    *   CLI Framework: `argparse` (Python built-in) (ADR-005).
    *   GUI Framework: `CustomTkinter` (and its dependency `Pillow` for `CTkImage`) (ADR-005).
    *   Concurrency (Bot Runtime): Python `threading` module (ADR-006).

## 3. Defining and Capturing Regions
    *   Regions are defined in the JSON profile with `name, x, y, width, height`.
    *   The GUI (`MainAppWindow` using `RegionSelectorWindow`) allows users to define/edit these graphically.
    *   `CaptureEngine.capture_region(region_spec)` uses `Pillow.ImageGrab.grab(bbox=(x, y, x + width, y + height))` on Windows. The result (Pillow Image) is converted to an OpenCV BGR NumPy array.

## 4. "Reading" from the Region - Analysis Strategies
1.  **Selective General Pre-emptive Analysis (by `MainController`):**
    *   `RulesEngine.__init__` pre-parses rules, creating `_analysis_requirements_per_region: Dict[region_name, Set[analysis_type_str]]` (e.g., `{"ocr", "dominant_color", "average_color"}`).
    *   In each cycle, `MainController` calls `rules_engine.get_analysis_requirements_for_region(region_name)`.
    *   Based on the returned set, `MainController` selectively calls `AnalysisEngine` methods (`analyze_ocr_text`, `analyze_dominant_colors`, `analyze_average_color`) only for required analyses on the `captured_image`.
    *   Results are stored in the `all_region_data` packet (e.g., as `ocr_analysis_result`, `dominant_colors_result`, `average_color`). If an analysis is skipped, its key might be absent or its value `None`.
2.  **On-Demand Analysis (by `RulesEngine`):**
    *   Conditions like `pixel_color` and `template_match_found` are evaluated directly by `RulesEngine._evaluate_single_condition_logic` using the `captured_image` from the `all_region_data` packet. These do not rely on pre-emptive analysis flags.
    *   `RulesEngine` includes fallback logic: if a pre-emptive analysis result (e.g., OCR text) is needed by a rule but was not provided by `MainController` (perhaps due to selective skipping), the `RulesEngine` will attempt an on-demand calculation if the `captured_image` is available. This is logged as a warning.

## 5. Rules Engine & Evaluation
    (This section describes the JSON rule structure and `RulesEngine`'s processing logic, including single/compound conditions, variable handling, and parameter evaluation.)

### 5.1. Rule Structure in JSON Profiles
    (Profiles store a list of rule objects. Each rule has `name`, optional default `region`, a `condition` object, and an `action` object.)
*   **Condition Object:**
    *   **Single Condition:** `{"type": "condition_name", "param1": value1, ...}`. May include `"capture_as": "var_name"`.
    *   **Compound Condition:** `{"logical_operator": "AND" | "OR", "sub_conditions": [list_of_single_condition_objects]}`.
*   **Action Object:** `{"type": "action_name", "param1": value1, ...}`. Parameters can contain placeholders like `{var_name}` or `{var_name.key}` for variable substitution.
*   Specific parameters for each condition type (e.g., `ocr_contains_text` has `text_to_find`, `case_sensitive`, `min_ocr_confidence`, `capture_as`) and action type (e.g., `click` has `target_relation`, `x`, `y`, `button`) are defined. The GUI provides editors for these.

### 5.2. `RulesEngine` Evaluation Logic
*   **Initialization (`__init__`):** Parses rules to build `_analysis_requirements_per_region`. Loads templates specified in the profile into `_loaded_templates` cache.
*   **`evaluate_rules(all_region_data)`:**
    *   Iterates through each rule from the profile.
    *   For each rule, creates a new, empty `rule_variable_context: Dict[str, Any]`.
    *   Resets `_last_template_match_info`.
    *   Calls `_check_condition(rule_name, condition_spec, default_rule_region, all_region_data, rule_variable_context)`.
*   **`_check_condition(...)`:**
    *   Determines if the `condition_spec` is single or compound.
    *   **Variable Substitution (for sub-conditions):** If compound, before evaluating each `sub_condition_spec`, it's processed by `_substitute_variables` using the current `rule_variable_context`.
    *   Calls `_evaluate_single_condition_logic(...)` for each actual condition check (either the main single condition or each sub-condition), passing the `rule_variable_context`.
    *   For compound conditions, applies `logical_operator` with short-circuiting.
*   **`_evaluate_single_condition_logic(...)`:**
    *   Retrieves the `condition_type` and its parameters from the (potentially substituted) `single_condition_spec`.
    *   Uses data from `region_data` (passed from `all_region_data`). If pre-analyzed data (like OCR results) is missing, it attempts an on-demand calculation using `AnalysisEngine` and the `captured_image` from `region_data` (logs a warning).
    *   Performs the specific condition check (e.g., pixel color, template match, OCR text/confidence, dominant color).
    *   If the condition is true AND `capture_as: "var_name"` is defined, it stores the relevant result (e.g., full OCR text, template match details dictionary) into the `rule_variable_context` under `"var_name"`.
    *   Stores details of a successful template match in `self._last_template_match_info` for use by `center_of_last_match` action targeting.
*   **Action Execution Trigger:** If `_check_condition` returns `True` for a rule:
    *   The rule's `action_spec` is processed by `_substitute_variables` using the final `rule_variable_context`.
    *   The (potentially modified) `action_spec_with_context` is passed to `ActionExecutor.execute_action()`.

### 5.3. Variable Handling (`RulesEngine`)
*   **Scope:** Rule-scoped. Variables exist only for the duration of a single rule's evaluation (from `_check_condition` start to action execution).
*   **Lifetime:** Created and populated within `_evaluate_single_condition_logic` if `capture_as` is used. Discarded after the rule is fully processed.
*   **Capture Points:**
    *   `ocr_contains_text`: Captures the full `ocr_analysis_result["text"]` if the condition (text and confidence) is met.
    *   `template_match_found`: Captures a dictionary `{"x", "y", "width", "height", "confidence"}` (coordinates relative to the search region) if the template is found.
*   **Substitution (`_substitute_variables` method):**
    *   Uses regex `re.compile(r"\{([\w_]+)((\.[\w_]+)*)\}")` to find placeholders like `{var_name}` or `{var_name.key.subkey}`.
    *   Recursively processes strings, lists, and dictionaries in condition/action parameters.
    *   Replaces placeholders with values from the current `rule_variable_context`.
    *   If a variable/key is not found, logs a warning and leaves the placeholder unchanged (safer than erroring or empty string).
    *   Values are substituted primarily as strings; `ActionExecutor` handles necessary type conversions.

## 6. Data Flow Example (Simplified Continuous Loop with Selective Analysis & Variables)
1.  **Init:** `RulesEngine` parses rules, builds `_analysis_requirements_per_region`.
2.  `MainController` loop:
    a.  For each `region_spec`: Captures image, gets `required_analyses`, selectively calls `AnalysisEngine`, populates `region_data_packet`. `all_region_data` is formed.
    b.  `RulesEngine.evaluate_rules(all_region_data)`:
        i.  For each `rule`: Creates empty `rule_variable_context`.
        ii. `_check_condition` called. If compound, `sub_condition_spec` is processed by `_substitute_variables`.
        iii.`_evaluate_single_condition_logic` is called. It checks condition, uses fallbacks if needed. If condition is true & `capture_as` exists, updates `rule_variable_context`.
        iv. If rule's overall condition is `True`: `action_spec` is processed by `_substitute_variables` using `rule_variable_context`.
        v.  `ActionExecutor.execute_action(substituted_action_spec)` is called.
    c.  `ActionExecutor` performs action, attempting type conversions for parameters (e.g., string "100" to int 100 for coordinate).
3.  Loop repeats.

## 7. Logging System (per ADR-007)
    *   Initialized by `core.logging_setup.setup_logging()` using `APP_ENV` and CLI flags.
    *   Modules use `logging.getLogger(__name__)`.
    *   Comprehensive logging covers:
        *   **Backend:** Application start/stop, profile loading, capture events, analysis results (including selective skips and fallbacks), rule evaluation steps (condition checks, variable capture/substitution, short-circuiting), action execution attempts and outcomes.
        *   **GUI:** User interactions (file ops, item selections, button clicks), data validation results (success/failure), internal state changes (dirty flag), dynamic UI rendering steps, errors.

## 8. Error Handling
    *   Extensive `try-except` blocks in all critical sections (engine methods, controller loop, GUI event handlers and apply methods).
    *   Specific exceptions (`FileNotFoundError`, `json.JSONDecodeError`, `ValueError`, `TypeError`, `OSError`) are caught where appropriate. Generic `Exception` with `exc_info=True` for unexpected issues.
    *   User-facing errors in the GUI are shown via `messagebox.showerror` or `messagebox.showwarning`.
    *   All errors are logged with `ERROR` or `CRITICAL` level, including stack traces for exceptions.
    *   `ActionExecutor` attempts safe type conversion of action parameters after variable substitution and logs failures.
    *   GUI input validation in "Apply" methods prevents saving invalid data structures.

## 9. Full GUI Architecture (v3.0.0+) (`MainAppWindow` using `CustomTkinter`)
    (This section details the GUI's structure, components, and core logic as implemented up to Phase 1.8.1, focusing on profile management, settings, region/template/rule list displays, and the dynamic detail panel for interactive editing of selected items, including parameters for conditions, actions, and sub-conditions, plus condition structure conversion and input validation.)

### 9.1. Overview and Goals
    (Provide a comprehensive, user-friendly GUI for all profile configuration tasks, minimizing direct JSON editing. Phase 1.X focuses on core editing layout, file operations, item management, parameter editing, and input validation.)

### 9.2. Main Application Window (`MainAppWindow`)
    (`customtkinter.CTk` based. Manages UI layout, menu actions, interaction with `ConfigManager`, internal `profile_data` state, dirty flag, and coordinates updates between various UI panels and the data model.)

### 9.3. GUI Layout and Components
    (Three-panel layout: Left [Profile Info, Regions, Templates], Center [Rules List], Right [Scrollable Details Panel]. Uses `CTkFrame`, `CTkScrollableFrame`, `CTkEntry`, `CTkButton`, `CTkLabel`, `CTkOptionMenu`, `CTkCheckBox`, `CTkTextbox`, `tkinter.Menu`, `tkinter.filedialog`, `tkinter.messagebox`. Template previews use `Pillow` and `CTkImage`.)

### 9.4. Core Functionality Logic (in `MainAppWindow`)
    *   **File Operations:** `_new_profile`, `_open_profile` (loads via `ConfigManager`), `_save_profile` (updates internal data from UI, saves via `ConfigManager`), `_save_profile_as`.
    *   **UI Data Sync:** `_populate_ui_from_profile_data` (renders UI from `profile_data`), `_update_profile_data_from_ui` (syncs basic settings from UI to `profile_data`; list items like rules are modified more directly in `profile_data` by their respective "Apply" logic).
    *   **State Management:** `_is_dirty` flag, `_set_dirty_status` (updates window title with "*"), `_prompt_save_if_dirty`.
    *   **Item Selection:** `_on_item_selected` (handles list clicks), `_highlight_selected_list_item`, updates detail panel via `_update_details_panel`.
    *   **Detail Panel Rendering (`_update_details_panel`):** Dynamically builds UI for selected region, template, or rule.
        *   **Regions:** Editable fields for name, x, y, width, height. Buttons for "Apply Changes", "Edit Coords via Selector".
        *   **Templates:** Editable name, read-only filename, image preview. Button for "Apply Changes".
        *   **Rules:** Editable name, default region. "Convert Condition Structure" button. Sections for Condition and Action.
            *   **Condition Editor (`_render_rule_condition_editor`):** If single, shows type dropdown and calls `_render_condition_parameters`. If compound, shows operator dropdown, sub-condition list (items call `_on_sub_condition_selected`), and a frame for selected sub-condition's parameters (`sub_condition_params_frame`).
            *   **Action Editor:** Shows type dropdown and calls `_render_action_parameters`.
    *   **Parameter Rendering (`_render_condition_parameters`, `_render_action_parameters`):** Dynamically create input widgets (`CTkEntry`, `CTkOptionMenu`, `CTkCheckBox`, `CTkTextbox`) based on condition/action type. Populate from data, store widget refs in `self.detail_widgets`, bind to dirty flag.
    *   **Parameter Collection (`_get_condition_parameters_from_ui`, `_get_action_parameters_from_ui`):** Retrieve values from dynamic widgets using `_validate_and_get_widget_value`, perform type conversion/validation.
    *   **Input Validation (`_validate_and_get_widget_value`, `_parse_bgr_string`):** Centralized helpers for type checking, range validation, non-empty checks, BGR string parsing. Show `messagebox.showerror` on failure.
    *   **"Apply" Methods (`_apply_region_changes`, `_apply_template_changes`, `_apply_rule_changes`):** Use validation helpers. If all valid, update `self.profile_data`, set dirty, refresh relevant UI list, re-display details.
    *   **List Management:** Methods for adding (placeholders or via dialogs like `RegionSelectorWindow`, template file copy) and removing items from regions, templates, rules, sub-conditions, updating `profile_data` and UI.

### 9.5. CLI Integration for GUI Editor
    (CLI command `edit [profile_path]` instantiates and runs `MainAppWindow`.)

### 9.6. Logging for GUI Operations
    (INFO for major user actions, DEBUG for UI state/rendering, WARNING/ERROR for validation failures or operational errors.)

---