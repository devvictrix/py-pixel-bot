# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, AI-Accelerated v1.0.0 and v2.0.0 (Advanced Visual Analysis & Rules) are complete. Development for v3.0.0 (Enhanced GUI & Usability) is now underway, with Phase 1.8.1 (GUI Input Validation & Refinements) of the Full GUI being the current focus.

## 1. Core Architecture

The tool is modular, comprising several key Python components, all residing within the main `py_pixel_bot` package located at the project root:

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
*   **`main_controller.MainController` Class:** (Located in `py_pixel_bot/main_controller.py`)
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
*   **`py_pixel_bot/__main__.py`:**
    *   The main application entry point when running as a module (`python -m py_pixel_bot`). The `py_pixel_bot` directory (at the project root) must be discoverable by Python (e.g., by running the command from the project root).
    *   Loads environment variables via `py_pixel_bot.core.config_manager.load_environment_variables()` (or equivalent relative import like `from .core.config_manager import ...`).
    *   Sets up logging via `py_pixel_bot.core.logging_setup.setup_logging()`.
    *   Parses CLI arguments using `py_pixel_bot.ui.cli.create_parser()`.
    *   Adjusts console logging verbosity based on CLI flags.
    *   Dispatches to the appropriate command handler function in `py_pixel_bot.ui.cli` (e.g., `handle_run` starts `MainController`, `handle_edit` starts `MainAppWindow`).

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
    *   Initialized by `py_pixel_bot.core.logging_setup.setup_logging()` using `APP_ENV` and CLI flags.
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
    <!-- Current implementation involves MainAppWindow and DetailsPanel handling significant amounts of logic. -->
    <!-- A planned refactoring aims to improve modularity (see Section 9.8). -->

### 9.3. GUI Layout and Components
    (Three-panel layout: Left [Profile Info, Regions, Templates], Center [Rules List], Right [Scrollable Details Panel, managed by `DetailsPanel` class]. Uses `CTkFrame`, `CTkScrollableFrame`, `CTkEntry`, `CTkButton`, `CTkLabel`, `CTkOptionMenu`, `CTkCheckBox`, `CTkTextbox`, `tkinter.Menu`, `tkinter.filedialog`, `tkinter.messagebox`. Template previews use `Pillow` and `CTkImage`.)
    Regions are managed in the left panel. Adding a new region or editing the coordinates of an existing region invokes the `RegionSelectorWindow`.

### 9.4. Core Functionality Logic (in `MainAppWindow` and `DetailsPanel`)
    <!-- This describes the current, less modular state. Section 9.8 outlines future improvements. -->
    *   File Operations (`MainAppWindow`): `_new_profile`, `_open_profile` (loads via `ConfigManager`), `_save_profile` (updates internal data from UI, saves via `ConfigManager`), `_save_profile_as`.
    *   UI Data Sync (`MainAppWindow`): `_populate_ui_from_profile_data` (renders UI from `profile_data`), `_update_profile_data_from_ui` (syncs basic settings from UI to `profile_data`). List item data (regions, templates, rules) is modified more directly in `self.profile_data` by their respective "Apply" logic, often orchestrated between `MainAppWindow` and `DetailsPanel`.
    *   State Management (`MainAppWindow`): `_is_dirty` flag, `_set_dirty_status` (updates window title with "*"), `_prompt_save_if_dirty`.
    *   Item Selection (`MainAppWindow`): `_on_item_selected` (handles list clicks), `_highlight_selected_list_item` (manages highlight state for main lists and, via delegation, sub-lists in `DetailsPanel`). Passes selected item data to `DetailsPanel` for display.
    *   Detail Panel Rendering (`DetailsPanel`): `update_display` dynamically builds UI for the selected region, template, or rule based on item type.
        *   **Regions:** Editable fields for name, x, y, width, height. Buttons for "Apply Changes" (handled by `MainAppWindow._apply_region_changes`), "Edit Coords via Selector" (handled by `MainAppWindow._edit_region_coordinates_with_selector`).
        *   **Templates:** Editable name, read-only filename, image preview. Button for "Apply Changes" (handled by `MainAppWindow._apply_template_changes`).
        *   **Rules:** Editable name, default region. "Convert Condition Structure" button. Sections for Condition and Action.
            *   **Condition Editor (`DetailsPanel._render_rule_condition_editor_internal`):** If single, shows type dropdown and calls `_render_dynamic_parameters`. If compound, shows operator dropdown, sub-condition list (items call `DetailsPanel._on_sub_condition_selected_internal`), and a frame for selected sub-condition's parameters.
            *   **Action Editor (`DetailsPanel`):** Shows type dropdown and calls `_render_dynamic_parameters`.
    *   Parameter Rendering (`DetailsPanel._render_dynamic_parameters`): Dynamically create input widgets based on condition/action type. Populate from data, store widget refs.
    *   Parameter Collection (`DetailsPanel._get_parameters_from_ui`): Retrieve values from dynamic widgets, perform type conversion/validation via `gui_utils.validate_and_get_widget_value`.
    *   Input Validation (`gui_utils.validate_and_get_widget_value`, `gui_utils.parse_bgr_string`): Centralized helpers for type checking, range validation, non-empty checks, BGR string parsing. Show `messagebox.showerror` on failure.
    *   "Apply" Methods (`MainAppWindow`): `_apply_region_changes`, `_apply_template_changes`, `_apply_rule_changes`. These methods typically:
        1. Read general item properties (e.g., rule name) from widgets directly managed by `DetailsPanel` or `MainAppWindow`.
        2. Call `DetailsPanel._get_parameters_from_ui` to get validated complex parameter blocks (like condition or action).
        3. If all data is valid, update `self.profile_data` in `MainAppWindow`.
        4. Set dirty status.
        5. Refresh the relevant UI list in `MainAppWindow`.
        6. Call `DetailsPanel.update_display` to re-render the details with the (potentially updated) data.
    *   List Management (`MainAppWindow`): Methods for adding (placeholders or via dialogs like `RegionSelectorWindow`, template file copy) and removing items from regions, templates, rules. Sub-condition list management is handled within `DetailsPanel` and `MainAppWindow._apply_rule_changes`.

### 9.5. CLI Integration for GUI Editor
    (CLI command `edit [profile_path]` instantiates and runs `MainAppWindow`.)

### 9.6. Logging for GUI Operations
    (INFO for major user actions, DEBUG for UI state/rendering, WARNING/ERROR for validation failures or operational errors.)

### 9.7. Region Definition and Management Workflow
    This section details the user experience and technical flow for defining and managing screen regions within the application.

    *   **Representation:** Regions are defined by a unique `name`, and integer coordinates `x`, `y`, `width`, and `height`. These are stored in the `regions` list within the JSON profile.
    *   **Listing in `MainAppWindow`:** The left panel of `MainAppWindow` displays a scrollable list of currently defined regions for the active profile. Each item shows the region's name.
    *   **Adding a New Region:**
        1.  The user clicks the "Add" button below the regions list in `MainAppWindow`.
        2.  The profile must be saved first (or saved as a new file if untitled). `MainAppWindow` prompts the user if necessary.
        3.  The `RegionSelectorWindow` is invoked. This is a modal, fullscreen, semi-transparent window.
        4.  The user clicks and drags on their screen to draw a rectangle.
        5.  Upon releasing the mouse, the user presses "Enter".
        6.  A `CTkInputDialog` appears, prompting for a unique name for the new region. The dialog also displays the selected coordinates (x, y, w, h).
        7.  If a valid, unique name is provided, the region data is saved to the currently open profile by `ConfigManager`, and `RegionSelectorWindow` closes.
        8.  `MainAppWindow` reloads the profile (if changes were made directly by `RegionSelectorWindow`) or updates its internal data and refreshes the regions list.
    *   **Editing an Existing Region's Properties (from `MainAppWindow` Details Panel):**
        1.  The user selects a region from the list in `MainAppWindow`.
        2.  The right-hand "Details Panel" populates with the selected region's properties: Name, X, Y, Width, Height (in `CTkEntry` widgets).
        3.  **Name/Coordinate Text Entry:** The user can directly edit these text fields. Input validation (e.g., for unique name, positive width/height, integer coordinates) is performed when "Apply Changes" is clicked.
        4.  **"Edit Coords via Selector" Button:**
            *   If clicked, the profile is saved (if dirty, with prompt).
            *   `RegionSelectorWindow` is invoked, pre-drawing the existing rectangle for that region.
            *   The user can redraw the rectangle or press "Enter" to keep the current one.
            *   The naming dialog appears, pre-filled with the region's current name. The user can confirm or change the name.
            *   Upon confirmation, the profile is updated by `RegionSelectorWindow`'s `ConfigManager`, and `MainAppWindow` reloads/refreshes.
    *   **Removing a Region:**
        1.  User selects a region from the list.
        2.  User clicks the "Remove" button.
        3.  The region is removed from the `profile_data` in `MainAppWindow`.
        4.  The UI list is refreshed. The profile is marked as dirty.
    *   **Assigning Regions to Rules/Conditions:**
        *   **Default Rule Region:** In the rule's details view (center panel in `MainAppWindow`), a dropdown menu lists all defined region names (plus an empty option for no default). The user selects a region from this list to set it as the default context for the rule's conditions.
        *   **Sub-Condition Specific Region:** When editing a sub-condition (if the rule has a compound condition), the sub-condition's parameter editor includes a similar dropdown menu. This allows a sub-condition to operate on a different region than the rule's default or other sub-conditions. If left empty, it inherits the rule's default region.
    *   **`RegionSelectorWindow` Technical Details:**
        *   Uses `ImageGrab.grab(all_screens=True)` to capture the screen content for its background (if successful). The canvas is sized to the captured image (potentially virtual desktop).
        *   The window itself is set to cover the virtual desktop dimensions using `self.geometry(widthxheight+0+0)` and `self.overrideredirect(True)` for a true borderless overlay. Fallback to primary screen `attributes("-fullscreen", True)` if full virtual desktop capture fails.
        *   Drawing is done using absolute screen coordinates (`event.x_root`, `event.y_root`) on the canvas.
        *   An instruction label is centered on the canvas (which should match virtual desktop size) using `canvas_width/2` for its x-placement.
        *   Handles Escape key for cancellation and Enter key for confirmation (which then shows the naming dialog).

### 9.8. Planned GUI Modularity Refinements (Post v3.0.0 Core Stability)
    To enhance long-term maintainability, testability, and code clarity, a refactoring of the GUI components is planned. The current implementation, while functional, concentrates significant logic within `MainAppWindow` and `DetailsPanel`. The refactoring aims to decompose these into smaller, more specialized, and potentially reusable components, inspired by component-based architecture.

    **Key Objectives:**
    *   Improve Separation of Concerns: Each GUI component should have a clear, single responsibility.
    *   Enhance Readability & Maintainability: Smaller, focused classes are easier to understand and modify.
    *   Increase Testability: Isolate UI logic for easier unit or component testing in the future.

    **Proposed Strategy:**
    1.  **`MainAppWindow` Streamlining:**
        *   Focus: Overall application window, menu bar, file operations (New, Open, Save, Save As via `ConfigManager`), managing the primary `profile_data` object, and managing the main item lists (Regions, Templates, Rules in left/center panels).
        *   Delegation: It will delegate the display and detailed editing of selected items to a dedicated coordinator/manager for the right panel.
    2.  **Introduce `DetailsCoordinator` (or `RightPanelManager`):**
        *   Responsibility: Manages the content of the right-hand details panel.
        *   Interaction: Receives the selected item type and data (or a reference/ID) from `MainAppWindow`.
        *   Function: Instantiates and displays the appropriate specialized "detail view" frame within the right panel. Clears or hides other detail views.
    3.  **Create Specialized Detail View Frames:**
        *   These will be new classes, likely residing in a dedicated subdirectory (e.g., `py_pixel_bot/ui/gui/panels/detail_views/`).
        *   **`RegionDetailView(ctk.CTkFrame)`:**
            *   Displays and manages the form for editing a region's name and coordinates (X, Y, Width, Height).
            *   Handles its own "Apply Region Changes" logic: validates its input fields and signals the validated data back to `MainAppWindow` for updating `profile_data`.
            *   Manages the "Edit Coords (Selector)" button, invoking `RegionSelectorWindow` (possibly via a callback to `MainAppWindow`).
        *   **`TemplateDetailView(ctk.CTkFrame)`:**
            *   Displays and manages the form for editing a template's name. Shows filename (read-only) and image preview.
            *   Handles its own "Apply Template Changes" logic.
        *   **`RuleDetailView(ctk.CTkFrame)`:**
            *   This will be a primary container for rule editing, itself composed of more specialized sub-components.
            *   Manages the overall display for a selected rule.
            *   Contains and coordinates:
                *   `RuleGeneralSettingsView(ctk.CTkFrame)`: For editing the rule's name and default region (dropdown).
                *   `ConditionEditorView(ctk.CTkFrame)`: A significant component responsible for:
                    *   Displaying and managing the UI for either a single condition or a compound condition.
                    *   Handling the "Convert Condition Structure" button logic (signaling to `MainAppWindow` to modify the rule structure in `profile_data`).
                    *   If compound: Managing the list of sub-conditions (add/remove, selection).
                    *   Dynamically rendering the parameter input fields for the selected condition or sub-condition type.
                *   `ActionEditorView(ctk.CTkFrame)`: Responsible for:
                    *   Displaying the action type dropdown.
                    *   Dynamically rendering the parameter input fields for the selected action type.
            *   Handles its own "Apply Rule Changes" logic: Gathers validated data from its sub-components and signals the complete, validated rule data back to `MainAppWindow`.
    4.  **Reusable Parameter Rendering Logic:**
        *   The current `DetailsPanel._render_dynamic_parameters` and `_get_parameters_from_ui` (which relies on `gui_utils.validate_and_get_widget_value`) will be refactored. This logic might become part of a base class for these new detail view frames or a dedicated utility module that these frames can use to build and manage their dynamic forms.
    5.  **Data Flow (Revised):**
        *   `MainAppWindow` continues to own the master `profile_data`.
        *   When an item is selected in `MainAppWindow`'s lists, a *copy* of the relevant data snippet (e.g., a specific rule dictionary) is passed to the `DetailsCoordinator`.
        *   The `DetailsCoordinator` passes this data to the instantiated `DetailView` frame.
        *   The `DetailView` frame populates its UI from this data.
        *   When the user clicks "Apply Changes" within a `DetailView`, that view validates its local form data.
        *   If valid, the `DetailView` signals the updated data snippet back to `MainAppWindow` (e.g., via a callback or by raising a custom event).
        *   `MainAppWindow` receives the updated snippet, merges it into the corresponding item in its `profile_data`, sets the dirty flag, and triggers a refresh of its lists and potentially signals the `DetailsCoordinator` to re-display the (now updated) item.

    This refactoring effort is tracked in `FEATURE_ROADMAP.MD` and aims to significantly improve the GUI's internal architecture for future development and maintenance.