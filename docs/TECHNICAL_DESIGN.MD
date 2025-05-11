// File: docs/TECHNICAL_DESIGN.MD
# TECHNICAL_DESIGN.MD
# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, AI-Accelerated v1.0.0 and v2.0.0 (Advanced Visual Analysis & Rules) are complete. Development for v3.0.0 (Enhanced GUI & Usability) is now underway, with Phase 1.8.1 (GUI Input Validation & Refinements) of the Full GUI being the current focus.

## 1. Core Architecture

The tool is modular, comprising several key Python components:

*   **`core.config_manager` Module:**
    *   `load_environment_variables()` function: Called at application startup to load `.env` (containing `APP_ENV`) using `python-dotenv` (per ADR-007).
    *   `ConfigManager` class: Responsible for loading, validating (basic structure), providing access to, and saving bot profiles (JSON files from the `profiles/` directory, per ADR-003). It also provides the base path for profile-related assets like templates.
    *   **Will be directly utilized by the new `MainAppWindow` (GUI) for loading, saving, and providing paths for profiles and associated assets (e.g., templates).**
*   **`core.logging_setup` Module:**
    *   `setup_logging()` function: Called after environment variables are loaded. Initializes Python's `logging` system based on `APP_ENV`, configuring handlers (console, date-stamped rotating file), formatters, and log levels (per ADR-007). CLI flags can override console log level.
*   **`engines.capture_engine.CaptureEngine` Class:**
    *   Responsible for capturing image data from specified screen regions using `Pillow.ImageGrab` (for Windows simplicity) and converting it to OpenCV BGR NumPy arrays (per ADR-001).
*   **`engines.analysis_engine.AnalysisEngine` Class:**
    *   Performs various analyses on captured image regions (NumPy BGR arrays).
    *   Provides methods for:
        *   Pixel color analysis (`analyze_pixel_color`).
        *   Average color calculation (`analyze_average_color`).
        *   Template matching (`match_template`) using OpenCV (per ADR-001).
        *   OCR text extraction (`ocr_extract_text`) using `pytesseract` (returns dict with text and average confidence).
        *   Dominant color analysis (`analyze_dominant_colors`) using k-means clustering.
*   **`engines.rules_engine.RulesEngine` Class:**
    *   Evaluates conditions based on analysis results.
    *   Supports single conditions, compound conditions (AND/OR logic), and rule-scoped variable capture and substitution.
    *   Upon initialization, it pre-parses all rules to determine specific general analyses required per region for optimization (`_analysis_requirements_per_region`).
    *   Provides `get_analysis_requirements_for_region()` for `MainController`.
    *   Retrieves rules from `ConfigManager`.
    *   Uses analysis results (selectively populated by `MainController`) and includes fallbacks for on-demand calculation if needed.
    *   Triggers actions via `ActionExecutor`.
*   **`engines.action_executor.ActionExecutor` Class:**
    *   Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
    *   Calculates target coordinates for actions.
    *   Handles type conversion for action parameters that may have been substituted from string variables (with validation and logging).
*   **`main_controller.MainController` Class:**
    *   Orchestrates the main bot operation loop.
    *   Runs the monitoring loop in a separate thread (per ADR-006).
    *   For each monitored region:
        *   Captures image (always).
        *   Queries `RulesEngine` for required general analyses for that region.
        *   Conditionally instructs `AnalysisEngine` to perform only those required analyses.
        *   Collects results into a data packet.
    *   Passes all region data packets to `RulesEngine.evaluate_rules()`.
*   **`ui.cli` Module:**
    *   Provides CLI using `argparse` (per ADR-005). Commands: `run`, `add-region`, `edit`.
*   **`ui.gui.region_selector.RegionSelectorWindow` Class:**
    *   `CustomTkinter` Toplevel window for graphically selecting screen regions, used by `add-region` CLI and the full GUI editor.
*   **`ui.gui.main_app_window.MainAppWindow` Class (New for v3.0.0):**
    *   Main application window for the full GUI profile editor (`CustomTkinter`).
    *   Handles layout, menus, profile data management (via `ConfigManager`), and UI updates for profile settings, regions, templates, and rules (including conditions, actions, parameters, sub-conditions, structure conversion).
    *   Implements input validation and user feedback.
*   **`__main__.py` (in `src/`):**
    *   Main application entry point. Handles path setup, loads `.env`, sets up logging, parses CLI arguments, and dispatches to appropriate handlers (e.g., starting `MainController` for `run` or `MainAppWindow` for `edit`).

## 2. Key Libraries & Justifications (Summary from ADRs)
    *   Environment Management: `python-dotenv` (ADR-007)
    *   Logging: Python `logging` module (ADR-007)
    *   Screen Capture & Image Analysis: `OpenCV-Python` (cv2), `NumPy`, `Pillow` (`ImageGrab`) (ADR-001).
    *   OCR: `pytesseract` (ADR-001).
    *   Input Simulation: `pyautogui` (ADR-002).
    *   Configuration Storage: `json` (Python built-in) (ADR-003).
    *   CLI Framework: `argparse` (Python built-in) (ADR-005).
    *   GUI Framework: `CustomTkinter` (ADR-005).
    *   Concurrency: Python `threading` module (ADR-006).

## 3. Defining and Capturing Regions
    *   Regions defined in JSON profile (`name, x, y, width, height`).
    *   GUI (`RegionSelectorWindow` or `MainAppWindow`) allows graphical definition and editing.
    *   `CaptureEngine` uses `Pillow.ImageGrab.grab(bbox=(x, y, x + width, y + height))` for capture, then converts to OpenCV format.

## 4. "Reading" from the Region - Analysis Strategies
1.  **Selective General Pre-emptive Analysis (by `MainController`):**
    *   `RulesEngine` pre-parses rules to map `region_name -> Set[analysis_type_str]` (e.g., "ocr", "dominant_color").
    *   `MainController` queries this map and only calls `AnalysisEngine` for required analyses on each region's captured image.
    *   Results (e.g., `ocr_analysis_result`, `dominant_colors_result`, `average_color`) are stored in `all_region_data` packet.
2.  **On-Demand Analysis (by `RulesEngine`):**
    *   `pixel_color` and `template_match_found` conditions trigger direct calls to `AnalysisEngine` using the already captured image from `all_region_data`.
    *   `RulesEngine` includes fallbacks: if pre-analyzed data (e.g., OCR) is missing but needed, it attempts on-demand calculation using the captured image (logged as a warning).

## 5. Rules Engine & Evaluation
    (Details specific rule structures, variable handling, and evaluation flow)

### 5.1. Rule Structure in JSON Profiles
    (Includes single conditions, compound conditions with `logical_operator` and `sub_conditions`, `capture_as` for variables, and specific parameters for each condition/action type like `min_ocr_confidence` or `dominant_color_matches` params. The GUI now allows comprehensive editing of these structures.)

    *   **Example Single Condition with Capture:**
        ```json
        {
          "name": "CaptureOrderID",
          "region": "order_details_area",
          "condition": {
            "type": "ocr_contains_text",
            "text_to_find": "ID: ",
            "capture_as": "order_id_text" 
          },
          "action": { "type": "log_message", "message": "Found: {order_id_text}" }
        }
        ```
    *   **Example Compound Condition:**
        ```json
        {
          "name": "ComplexCheck",
          "condition": {
            "logical_operator": "AND",
            "sub_conditions": [
              {"type": "template_match_found", "region": "icon_area", "template_filename": "go.png", "capture_as": "go_button"},
              {"type": "pixel_color", "region": "status_light", "relative_x": 5, "relative_y": 5, "expected_bgr": [0,255,0]}
            ]
          },
          "action": { "type": "click", "target_relation": "center_of_last_match"} 
          // ActionExecutor needs to know which match if multiple templates captured. For now, _last_template_match_info is simple.
        }
        ```
    *   The GUI (`MainAppWindow`) provides an interface to create and modify these structures without direct JSON editing, including converting between single and compound condition types.

### 5.2. `RulesEngine` Evaluation Logic
*   **Initialization:** Parses rules to build `_analysis_requirements_per_region`.
*   **`evaluate_rules(all_region_data)`:**
    *   For each rule, creates a fresh `rule_variable_context` dictionary.
    *   Calls `_check_condition(..., rule_variable_context)`.
*   **`_check_condition(..., variable_context)`:**
    *   Determines if single or compound.
    *   **Substitution:** Before evaluating a (sub-)condition's spec, it calls `_substitute_variables` on the spec using the current `variable_context`.
    *   Calls `_evaluate_single_condition_logic(..., variable_context)` for each actual condition check.
*   **`_evaluate_single_condition_logic(..., variable_context)`:**
    *   Performs the specific analysis check (using `AnalysisEngine` or pre-analyzed data).
    *   If condition is true and `capture_as` is defined, populates `variable_context` with the captured value.
*   **Action Execution:** If overall rule condition is true, `evaluate_rules` calls `_substitute_variables` on the `action_spec` using the rule's final `variable_context`, then passes it to `ActionExecutor`.

### 5.3. Variable Handling
*   **Scope:** Rule-scoped (exist only during one rule's evaluation).
*   **Lifetime:** Created when a rule evaluation starts, discarded when it ends.
*   **Capture:** Via `capture_as` in `ocr_contains_text` (captures full OCR'd text) and `template_match_found` (captures `{"x", "y", "width", "height", "confidence"}` relative to its search region).
*   **Substitution:** Uses `{var_name}` or `{var_name.key}` syntax in subsequent condition parameters and action parameters. `_substitute_variables` handles replacement.

## 6. Data Flow Example (Simplified Continuous Loop with Selective Analysis)
1.  **Init:** `RulesEngine` parses rules, builds `_analysis_requirements_per_region`.
2.  `MainController` loop:
    a.  For each `region_spec`:
        i.  `CaptureEngine` captures image.
        ii. `MainController` gets `required_analyses` from `RulesEngine`.
        iii.Conditionally calls `AnalysisEngine` methods, populating `region_data_packet`.
    b.  Passes `all_region_data` to `RulesEngine.evaluate_rules()`.
    c.  `RulesEngine` iterates rules:
        i.  Creates `rule_variable_context`.
        ii. `_check_condition` (with var substitution for sub-conds) calls `_evaluate_single_condition_logic`.
        iii.`_evaluate_single_condition_logic` checks condition, potentially populates `rule_variable_context`.
        iv. If rule met, `action_spec` is processed by `_substitute_variables`, then sent to `ActionExecutor`.
    d. `ActionExecutor` performs action (with internal type conversion for params).
3.  Loop repeats.

## 7. Logging System (per ADR-007)
    *   Initialized by `core.logging_setup.setup_logging()`.
    *   Hierarchical loggers (`logging.getLogger(__name__)`).
    *   Configurable via `APP_ENV` and CLI flags.
    *   Comprehensive logging for backend operations (capture, analysis, rule evaluation, variable handling, actions) and GUI interactions (file ops, selections, edits, validation).

## 8. Error Handling
    *   Extensive `try-except` blocks in engine methods, controller loop, and GUI event handlers.
    *   Specific exceptions caught where possible, generic `Exception` for unexpected issues.
    *   User-facing errors in GUI shown via `messagebox`, all errors logged.
    *   `ActionExecutor` attempts safe type conversion for parameters derived from variables.

## 9. Full GUI Architecture (v3.0.0+)
    (This section details the `MainAppWindow` structure, panels, core methods for profile management, UI data synchronization, dirty state, item selection, parameter rendering for regions, templates, and rules (including sub-conditions and condition structure conversion), and input validation as implemented up to Phase 1.8.1. The content is largely as detailed in previous planning responses for these GUI phases.)

### 9.1. Overview and Goals
    (Phase 1: Core layout, file ops, settings, list views. Phase 1.1-1.8: Interactive editing for regions, templates, rules, sub-conditions, condition conversion, input validation.)

### 9.2. Main Application Window (`MainAppWindow`)
    (`customtkinter.CTk` based, manages overall UI and data flow via `ConfigManager`.)

### 9.3. GUI Layout and Components
    (Menu bar, Left Panel [Profile Info, Regions, Templates], Center Panel [Rules], Right Panel [Scrollable Details for selected item with dynamic parameter editors].)

### 9.4. Core Functionality Logic (in `MainAppWindow`)
    (_new_profile, _open_profile, _save_profile, _save_profile_as, _populate_ui_from_profile_data, _update_profile_data_from_ui, _set_dirty_status, _prompt_save_if_dirty, _on_item_selected, item-specific "Apply" methods like _apply_rule_changes, parameter rendering helpers like _render_condition_parameters, input validation helpers like _validate_and_get_widget_value, _parse_bgr_string.)

### 9.5. CLI Integration for GUI Editor
    (`edit [profile_path]` command launches `MainAppWindow`.)

### 9.6. Logging for GUI Operations
    (INFO for user actions, DEBUG for internal state, ERROR/EXCEPTION for UI issues.)

---