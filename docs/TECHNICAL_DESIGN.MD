// File: docs/TECHNICAL_DESIGN.MD

# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, v1.0.0 and v2.0.0 are complete. Development for v3.0.0 (Enhanced GUI & Usability) is concluded. The current focus is **v4.0.0 (Gemini-Powered Visual Intelligence)**, as detailed in ADR-008.

## 1. Core Architecture

The tool is modular, comprising several key Python components, all residing within the main `py_pixel_bot` package located at the project root:

- **`core.config_manager` Module:**
  - `load_environment_variables()` function: Called at application startup to load `.env` (containing `APP_ENV` and **`GEMINI_API_KEY` for v4.0.0+**) using `python-dotenv` (per ADR-007, ADR-008).
  - `ConfigManager` class: Responsible for loading, validating (basic structure), providing access to, and saving bot profiles (JSON files from the `profiles/` directory, per ADR-003). It also provides the base path for profile-related assets like templates.
  - **Utilized by the `MainAppWindow` (GUI) for loading, saving, and path resolution for profiles and associated template images.**
- **`core.logging_setup` Module:**
  - `setup_logging()` function: Called after environment variables are loaded. Initializes Python's `logging` system based on `APP_ENV`, configuring handlers (console, date-stamped rotating file), formatters, and log levels (per ADR-007). CLI flags can override console log level.
- **`engines.capture_engine.CaptureEngine` Class:**
  - Responsible for capturing image data from specified screen regions using `Pillow.ImageGrab.grab(bbox=(x, y, x + width, y + height))` for Windows capture (per ADR-001).
  - Converts captured Pillow Image objects to OpenCV BGR NumPy arrays for consistent use by the `AnalysisEngine` and `GeminiAnalyzer`.
- **`engines.analysis_engine.AnalysisEngine` Class:**
  - Performs various **local** visual analyses on captured image regions (NumPy BGR arrays).
  - Provides methods for:
    - Pixel color analysis (`analyze_pixel_color`).
    - Average color calculation (`analyze_average_color`).
    - Template matching (`match_template`) using OpenCV (per ADR-001).
    - OCR text extraction (`ocr_extract_text`) using `pytesseract`, returning a dictionary with extracted `text` and an `average_confidence` score.
    - Dominant color analysis (`analyze_dominant_colors`) using k-means clustering.
- **`engines.gemini_analyzer.GeminiAnalyzer` Class (NEW - for v4.0.0+):**
  - **Responsibility:** Handles all communication with the Google Gemini API for advanced visual understanding (per ADR-008).
  - **Initialization:** Takes API key (from `.env` via `ConfigManager`) and optional default model name.
  - **Key Methods:** Provides `query_vision_model(image_data, prompt, [model_name])` which sends image/prompt to the API and returns a structured response (including parsed text/JSON and status/error info).
  - **Configuration:** API key loaded from `.env`. Default model configurable via profile settings (`settings.gemini_default_model_name`).
  - **Logging:** Comprehensive logging of API interactions, errors, and latency.
  - _Details in Section 10._
- **`engines.rules_engine.RulesEngine` Class:**
  - Evaluates rules based on analysis results (from `AnalysisEngine` for local checks, or from **`GeminiAnalyzer` for Gemini-powered checks**).
  - Supports single conditions, compound conditions (AND/OR logic per ADR-004), and rule-scoped variable capture and substitution.
  - **Initialization (`__init__`):**
    - Pre-parses rules to build `_analysis_requirements_per_region` for **local** analyses (OCR, dominant color, average color). `gemini_vision_query` conditions (v4.0.0+) do **not** add to these local pre-emptive requirements.
    - **Instantiates or receives an instance of `GeminiAnalyzer` (for v4.0.0+).**
  - **`_evaluate_single_condition_logic(...)` (Updated for v4.0.0):**
    - Handles existing local condition types.
    - **For `gemini_vision_query` type (v4.0.0+):**
      - Retrieves the `captured_image` for the condition's target region.
      - **Calls the `GeminiAnalyzer` with the image and prompt from the condition spec.**
      - Evaluates Gemini's response based on `expected_response_contains` or `expected_response_json_path`/`expected_json_value`.
      - Handles API call errors gracefully (condition evaluates to `False`, log error).
      - If `capture_as` is defined, stores the relevant Gemini response (or part of it) in the `rule_variable_context`.
- **`engines.action_executor.ActionExecutor` Class:**
  - Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
  - Calculates target coordinates for actions.
  - **Enhancement for v4.0.0 (Phase 1 Stretch/Phase 2):** May be updated to handle a new `target_relation` like `center_of_gemini_identified_element`, requiring parsing of bounding box data (e.g., from a variable captured from a Gemini response).
- **`main_controller.MainController` Class:** (Located in `py_pixel_bot/main_controller.py`)
  - Orchestrates the main bot operation loop for runtime execution.
  - Runs the monitoring loop in a separate thread (per ADR-006).
  - For each monitored region in a profile:
    - Instructs `CaptureEngine` to capture the image (always performed).
    - Queries the `RulesEngine` instance (via `get_analysis_requirements_for_region`) to get the set of required **local** general analyses for the current region.
    - Conditionally instructs `AnalysisEngine` to perform **only** those required local general analyses.
    - Collects available local analysis results (and the captured image) into a data packet for that region.
  - Passes the dictionary of all region data packets to `RulesEngine.evaluate_rules()`. (**Note:** Gemini API calls (`GeminiAnalyzer`) are **not** invoked by `MainController`; they are made on-demand by `RulesEngine` during its evaluation).
- **`ui.cli` Module:**
  - Provides the Command-Line Interface using `argparse` (per ADR-005).
  - Handles subcommands: `run <profile>`, `add-region <profile>`, and `edit [profile]`.
- **`ui.gui.region_selector.RegionSelectorWindow` Class:**
  - Provides GUI for visually selecting screen regions.
- **`ui.gui.main_app_window.MainAppWindow` Class (v3.0.0, with v4.0.0 updates):**
  - The main application window (`CustomTkinter.CTk`) for the full GUI profile editor.
  - **Updates for v4.0.0:**
    - Will allow configuration of the new `gemini_vision_query` condition type and its parameters (prompt, response expectations, etc.) within the rule editor (DetailsPanel). See Section 11.
    - Will include UI elements in settings to indicate Gemini API key status (e.g., "Configured" or "Not Configured") and allow setting a default Gemini model.
- **`py_pixel_bot/__main__.py`:**
  - Entry point for the application. Initializes core components (Env Vars, Logging, Config) and dispatches CLI commands.

## 2. Key Libraries & Justifications (Summary from ADRs)

-   **Environment Management:** `python-dotenv` (ADR-007)
-   **Logging:** Python `logging` module (ADR-007)
-   **Screen Capture:** `Pillow` (`ImageGrab` for Windows), `OpenCV-Python` (for conversion and potential alternatives) (ADR-001).
-   **Image Processing & Analysis (Local):** `OpenCV-Python` (cv2), `NumPy`, `Pillow` (ADR-001).
-   **OCR (Local):** `pytesseract` (ADR-001).
-   **Remote Advanced Visual Analysis (NEW for v4.0.0):** `google-generativeai` (Python SDK for Gemini) (ADR-008).
-   **Input Simulation:** `pyautogui` (ADR-002).
-   **Configuration Storage:** `json` (Python built-in) (ADR-003).
-   **CLI Framework:** `argparse` (Python built-in) (ADR-005).
-   **GUI Framework:** `CustomTkinter` (and its dependency `Pillow` for `CTkImage`) (ADR-005).
-   **Concurrency (Bot Runtime):** Python `threading` module (ADR-006).

## 3. Defining and Capturing Regions

-   Regions are defined in the JSON profile with `name, x, y, width, height`.
-   The GUI (`MainAppWindow` using `RegionSelectorWindow`) allows users to define/edit these graphically.
-   `CaptureEngine.capture_region(region_spec)` uses `Pillow.ImageGrab.grab(bbox=(x, y, x + width, y + height))` on Windows. The result (Pillow Image) is converted to an OpenCV BGR NumPy array.
-   **This captured BGR image is then available for both local analysis by `AnalysisEngine` and remote analysis by `GeminiAnalyzer`.**

## 4. "Reading" from the Region - Analysis Strategies

1.  **Local Selective Pre-emptive Analysis (by `MainController` via `AnalysisEngine`):**
    -   `RulesEngine.__init__` pre-parses rules, creating `_analysis_requirements_per_region: Dict[region_name, Set[analysis_type_str]]` (e.g., `{"ocr", "dominant_color", "average_color"}`) for **local** analysis types that benefit from being run once per cycle if needed by any rule.
    -   In each cycle, `MainController` calls `rules_engine.get_analysis_requirements_for_region(region_name)`.
    -   Based on the returned set, `MainController` selectively calls `AnalysisEngine` methods (`analyze_ocr_text`, `analyze_dominant_colors`, `analyze_average_color`) **only** for required local analyses on the `captured_image`.
    -   Results are stored in the `all_region_data` packet for use by `RulesEngine`.
2.  **Local On-Demand Analysis (by `RulesEngine` via `AnalysisEngine`):**
    -   Conditions like `pixel_color` and `template_match_found` are evaluated directly by `RulesEngine._evaluate_single_condition_logic` using the `captured_image` from the `all_region_data` packet. These analyses are typically specific to the parameters of the condition being evaluated.
    -   `RulesEngine` includes fallback logic for local pre-emptive analyses if data is missing from the packet but the image is available (though this should be rare with the selective pre-emptive strategy).
3.  **Remote On-Demand Analysis (NEW - by `RulesEngine` via `GeminiAnalyzer` - for v4.0.0):**
    -   When a `gemini_vision_query` condition is evaluated by `RulesEngine._evaluate_single_condition_logic`:
        -   The `captured_image` for the target region is retrieved from the `all_region_data` packet.
        -   `RulesEngine` calls `GeminiAnalyzer.query_vision_model()` with this image and the prompt specified in the rule's condition parameters.
        -   The response from `GeminiAnalyzer` (e.g., text description, JSON data, error status) is then processed by `RulesEngine` to determine if the condition is met and to capture any specified variables.
    -   This is **"on-demand"** as costly and potentially slow Gemini API calls are made **only** when a rule specifically requiring Gemini analysis is being evaluated in the current cycle.

## 5. Rules Engine & Evaluation

(This section describes the JSON rule structure and `RulesEngine`'s processing logic, including single/compound conditions, variable handling, parameter evaluation, and the new Gemini integration.)

### 5.1. Rule Structure in JSON Profiles (Updates for v4.0.0)

(Profiles store a list of rule objects. Each rule has `name`, optional default `region`, a `condition` object, and an `action` object.)

-   **Condition Object:**
    -   **Single Condition (Existing Local Types):** `{"type": "local_condition_name", "param1": value1, ...}`. May include `"capture_as": "var_name"`.
    -   **Compound Condition (Existing Local Types):** `{"logical_operator": "AND" | "OR", "sub_conditions": [list_of_single_local_condition_objects]}`.
    -   **NEW `gemini_vision_query` type (Single Condition Structure - for v4.0.0):**
        ```json
        {
          "type": "gemini_vision_query",
          "region": "optional_region_name_override", // Uses rule's default region if omitted
          "prompt": "Describe this image in detail. Is there a prominent red button present? If so, describe its text.",
          "expected_response_contains": ["red button", "submit"], // Optional: list of strings or single string. Checks text_content from Gemini.
          // "expected_response_json_path": "elements[?(@.label=='button' && @.color=='red')].text", // Optional: JSONPath to query Gemini's json_content.
          // "expected_json_value": "Proceed", // Optional: value expected at JSONPath. Requires careful type handling.
          "case_sensitive_response_check": false, // Optional, defaults to false for 'expected_response_contains'
          "capture_as": "gemini_analysis_result", // Optional: stores Gemini's text_content or JSONPath extracted value.
          "model_name": "gemini-1.5-flash-latest" // Optional: overrides profile's default Gemini model for this query.
        }
        ```
-   **Action Object:** `{"type": "action_name", "param1": value1, ...}`. Parameters can contain placeholders like `{var_name}` or `{var_name.key}` for variable substitution.
    -   **Enhancement for v4.0.0 (Phase 1 Stretch/Phase 2):**
        -   A potential new `target_relation` for click/mouse actions: `center_of_gemini_identified_element`.
        -   Would require an associated parameter like `gemini_element_variable: "captured_button_info"`, where `captured_button_info` is a variable (from `capture_as` in a `gemini_vision_query` condition) expected to contain bounding box data (e.g., `{"box": [x,y,w,h], "label": "Confirm Button"}`). `ActionExecutor` would parse this.

### 5.2. `RulesEngine` Evaluation Logic (Updates for v4.0.0)

-   **Initialization (`__init__`):**
    -   Parses rules to build `_analysis_requirements_per_region` (for **local** analyses only).
    -   Loads templates into `_loaded_templates`.
    -   **Instantiates `GeminiAnalyzer`** if Gemini features are to be supported, passing the API key (obtained via `ConfigManager`).
-   **`evaluate_rules(all_region_data)`:** (Largely unchanged overall flow)
-   **`_check_condition(...)`:** (Largely unchanged overall flow for single/compound logic)
-   **`_evaluate_single_condition_logic(...)` (Key updates for v4.0.0):**
    -   Handles existing local condition types (pixel_color, template_match, ocr_contains_text, etc.) by interacting with `AnalysisEngine` or directly using data from `all_region_data`.
    -   **NEW for `gemini_vision_query` type:**
        1.  Validates that necessary parameters (`prompt`) are present in `single_condition_spec`.
        2.  Retrieves the `captured_image` for the target region from `region_data`. If no image, the condition fails.
        3.  **Calls `self.gemini_analyzer.query_vision_model()`** with the image, prompt, and any specified `model_name`.
        4.  If the `GeminiAnalyzer` call fails or returns an error status, the condition is marked as `False`, and the error is logged.
        5.  If successful, evaluates the **structured response** from `GeminiAnalyzer`:
            -   If `expected_response_contains` is specified, checks the `text_content` field.
            -   If `expected_response_json_path` and `expected_json_value` are specified, attempts to parse `json_content` (if present), extract the value using the path, and compare it. (Requires careful error handling for JSON parsing and path extraction).
            -   Sets `condition_met` accordingly.
        6.  If `condition_met` is `True` AND `capture_as` is defined:
            -   Stores the relevant data from Gemini's response (e.g., `text_content`, or the value extracted by JSONPath from `json_content`) into the `rule_variable_context` under the specified variable name. This makes Gemini's derived information available for subsequent conditions or actions.

-   **Action Execution Trigger:** (No change in logic flow: if rule's overall condition is True, action is prepared and executed).

### 5.3. Variable Handling (`RulesEngine`)

-   **Scope & Lifetime:** Rule-scoped, created during `evaluate_rules` for each rule, discarded after rule evaluation.
-   **Capture Points (Expanded for v4.0.0):**
    -   Existing: `ocr_contains_text` (captures full text), `template_match_found` (captures match details dict).
    -   **NEW:** `gemini_vision_query` can capture Gemini's `text_content` or a specific value extracted from its `json_content`. This captured data can be a string, a number, a boolean, or even a nested dictionary/list if Gemini returns complex JSON and `capture_as` targets a complex part via JSONPath.
-   **Substitution (`_substitute_variables` method):**
    -   Uses `PLACEHOLDER_REGEX` (`\{([\w_]+)((\.[\w_]+)*)\}`) to find placeholders in action parameters (strings, lists, dicts).
    -   Replaces `{var_name}` with the string representation of the variable's value from `rule_variable_context`.
    -   Supports basic dot notation access for nested dictionary keys or list indices (e.g., `{gemini_result.identified_button.coordinates.x}`). Handles `KeyError`, `IndexError`, `TypeError` during access gracefully, leaving the placeholder unsubstituted and logging a warning.

## 6. Data Flow Example (Simplified Continuous Loop with Gemini Query)

1.  **Init:** `RulesEngine` parses rules, builds **local** `_analysis_requirements_per_region`. `GeminiAnalyzer` is initialized with API key.
2.  `MainController` loop starts (`run_monitoring_loop` in thread):
    a.  For each `region_spec` in profile:
        i.  `CaptureEngine.capture_region()` captures image -> `captured_image` (NumPy BGR).
        ii. `RulesEngine.get_analysis_requirements_for_region()` -> `required_local_analyses`.
        iii. For each `analysis_type` in `required_local_analyses`: `AnalysisEngine.analyze_X(captured_image)` -> `local_result`.
        iv. Store `captured_image` and all `local_result`s in `region_data_packet`.
        v.  Add `region_data_packet` to `all_region_data` dict keyed by `region_name`.
    b.  `RulesEngine.evaluate_rules(all_region_data)`:
        i.  For each `rule`: Creates empty `rule_variable_context`.
        ii. `_check_condition` called for the rule's condition block:
            -   If the condition (or a sub-condition) is `gemini_vision_query`:
                -   `_evaluate_single_condition_logic` retrieves the `captured_image` from `all_region_data`.
                -   **Calls `self.gemini_analyzer.query_vision_model()`** with the image and prompt.
                -   Receives structured response (`status`, `text_content`, `json_content`, `error_message`).
                -   Evaluates response against `expected_*` parameters.
                -   If `capture_as` used and condition met, updates `rule_variable_context` with Gemini's output.
            -   For local conditions, uses data from `all_region_data` or `AnalysisEngine` fallbacks.
        iii. If rule's overall condition is `True`:
            -   `_substitute_variables` replaces placeholders in `action_spec` using the (potentially Gemini-populated) `rule_variable_context`.
            -   `ActionExecutor.execute_action(substituted_action_spec)` is called.
            -   **(Stretch/Phase 2):** If action targets `center_of_gemini_identified_element`, `ActionExecutor` will parse the `gemini_element_variable` from context to get bounding box data for click coordinates.
    c.  Wait for `monitoring_interval_seconds` (minus cycle execution time).
3.  Loop repeats until stop event.

## 7. Logging System (per ADR-007)

-   Uses Python's built-in `logging`, configured by `core.logging_setup`.
-   Format includes timestamp, logger name, level, module:func:lineno, and message for files. Console format is simpler based on `APP_ENV`.
-   Log levels controlled by `APP_ENV` (`DEBUG` for development, `INFO`+ for production) and CLI flags (`-v`).
-   Uses `logging.getLogger(__name__)` in modules.
-   Logs are written to `logs/YYYY-MM-DD.log` (rotating daily - originally intended, currently basic FileHandler).
-   **NEW for v4.0.0:**
    -   **`GeminiAnalyzer` MUST** log API requests (prompt summary, model used), API responses (status, success/error, latency), and **any errors** encountered during API communication (rate limits, auth errors, network issues, etc.). **Full image data MUST NOT be logged.**
    -   **`RulesEngine` MUST** log when it's invoking `GeminiAnalyzer`, the prompt used (summarized), the model targeted, and the outcome of the `gemini_vision_query` condition evaluation (met/not met, error status from GeminiAnalyzer).

## 8. Error Handling

-   Extensive `try-except` blocks are used throughout core components.
-   User-facing errors are shown via `messagebox` in the GUI or printed to stderr for CLI.
-   Detailed exceptions and context are logged using `logger.error` or `logger.exception`.
-   Graceful degradation where possible (e.g., skipping a rule if its template is missing, continuing the loop).
-   **NEW for v4.0.0:**
    -   **`GeminiAnalyzer` MUST** implement robust error handling for API calls (e.g., `google.api_core.exceptions`, network errors) and return structured error information in its response dictionary or raise specific exceptions that `RulesEngine` can catch.
    -   **`RulesEngine` MUST** gracefully handle failures from `GeminiAnalyzer` when evaluating `gemini_vision_query` conditions (e.g., treat condition as `False`, log the specific error clearly).
    -   The GUI (`MainAppWindow`) should inform the user if a configured Gemini API key is missing or seems invalid (e.g., via status bar or log message, potentially a non-blocking warning on save if Gemini features are used). Persistent Gemini API failures during potential future "test rule" functionality should be clearly indicated.

## 9. Full GUI Architecture (v3.0.0+) (`MainAppWindow` using `CustomTkinter`)

(This section details the GUI's structure, components, and core logic, including planned updates for v4.0.0 Gemini integration.)

### 9.1. Overview and Goals

-   Provide a comprehensive, user-friendly GUI for all aspects of profile creation, editing, and management.
-   Eliminate the need for direct JSON editing for most users.
-   **For v4.0.0:** Allow intuitive configuration of the new `gemini_vision_query` condition type.

### 9.2. Main Application Window (`MainAppWindow`)

-   Root window (`ctk.CTk`) managing the overall application layout and core file operations (New, Open, Save, Save As, Exit).
-   Handles dirty state tracking and prompts for saving unsaved changes.
-   Orchestrates interactions between the list panels (Left, Center) and the Details Panel.

### 9.3. GUI Layout and Components

-   **Three-Panel Layout:**
    -   **Left Panel:** Profile Settings (Description, Interval, K), Regions List, Templates List. Includes Add/Remove buttons for regions and templates.
    -   **Center Panel:** Rules List. Includes Add/Remove buttons for rules.
    -   **Right Panel (`DetailsPanel`):** Dynamically displays detailed editors for the selected item (Region, Template, Rule).

### 9.4. Core Functionality Logic (in `MainAppWindow` and `DetailsPanel`)

-   **Profile Operations:** Implemented in `MainAppWindow` (`_new_profile`, `_open_profile`, `_save_profile`, `_save_profile_as`). Use `ConfigManager` for backend file operations.
-   **Item Selection:** Clicking items in lists (Regions, Templates, Rules) triggers `_on_item_selected` in `MainAppWindow`, which updates the selection state, highlights the item, enables/disables remove buttons, and calls `DetailsPanel.update_display`. Sub-condition selection is managed within `DetailsPanel`.
-   **Details Editing:**
    -   `DetailsPanel` renders appropriate input widgets based on the selected item type and subtype using `gui_config.UI_PARAM_CONFIG`.
    -   Input validation uses `gui_utils.validate_and_get_widget_value`.
    -   "Apply Changes" buttons in `DetailsPanel` call corresponding methods in `MainAppWindow` (`_apply_region_changes`, `_apply_template_changes`, `_apply_rule_changes`). These methods retrieve validated data from `DetailsPanel` widgets, update the `self.profile_data` dictionary, set the dirty flag, and refresh the relevant list and details view.
-   **Settings Panel (Left Panel of `MainAppWindow`) (Updates for v4.0.0):**
    -   May add a read-only label indicating Gemini API Key status (e.g., "GEMINI_API_KEY: Configured via .env" / "Not Configured in .env").
    -   Will add an entry for `gemini_default_model_name` to be stored in `profile_data["settings"]`.
-   **Rule Editor (`DetailsPanel`) (Updates for v4.0.0):**
    -   When editing a rule's condition (single or sub-condition):
        -   The "Condition Type" dropdown MUST include `gemini_vision_query`.
        -   When `gemini_vision_query` is selected, `_render_dynamic_parameters` in `DetailsPanel` MUST dynamically create and display input fields for its specific parameters as defined in `UI_PARAM_CONFIG` (see Section 11):
            -   `prompt`: A `CTkTextbox` for potentially multi-line prompts.
            -   `expected_response_contains`: `CTkEntry` or `CTkTextbox`.
            -   `expected_response_json_path`: `CTkEntry`.
            -   `expected_json_value`: `CTkEntry`.
            -   `case_sensitive_response_check`: `CTkCheckBox`.
            -   `capture_as`: `CTkEntry`.
            -   `model_name`: `CTkEntry` (optional override).
    -   **(Stretch/Phase 2)** If implementing `center_of_gemini_identified_element` for actions, the "Target Relation" dropdown for click actions will include this. A new `gemini_element_variable` entry field would appear when selected.
-   Input validation (`gui_utils.validate_and_get_widget_value`) will apply to these new fields.

### 9.5. CLI Integration for GUI Editor

-   The `edit [profile]` CLI command launches `MainAppWindow`.
-   The `add-region <profile>` CLI command launches `RegionSelectorWindow`.

### 9.6. Logging for GUI Operations

-   GUI actions (button clicks, selections, file operations, apply attempts) are logged at INFO level.
-   UI state changes, dynamic rendering steps are logged at DEBUG level.
-   Validation failures, file I/O errors, unexpected exceptions are logged at WARNING or ERROR/CRITICAL level.
-   **v4.0.0:** Logging will include interactions with Gemini configuration elements.

### 9.7. Region Definition and Management Workflow

-   "Add Region" button in `MainAppWindow` launches `RegionSelectorWindow` modally.
-   `RegionSelectorWindow` allows drawing, provides preview/overlay, prompts for name, and calls `ConfigManager` to save the region to the profile file.
-   `MainAppWindow` reloads the profile if `RegionSelectorWindow` reports changes.
-   Region coordinates and name can also be edited directly via text entries in `DetailsPanel`.

### 9.8. GUI Modularity Refinements (Post v3.0.0 Core Stability - Implemented in v3.0.x)

-   `DetailsPanel` was introduced to encapsulate the logic for displaying and editing details of selected items, separating it from `MainAppWindow`'s primary role of managing lists, file operations, and overall layout.
-   Further refinement could involve creating dedicated view classes within `DetailsPanel` (e.g., `RegionDetailView`, `RuleDetailView`) if complexity increases significantly.

## 10. Gemini API Interaction (`GeminiAnalyzer` - NEW Section for v4.0.0)

This section details the design of the `GeminiAnalyzer` module, responsible for all interactions with the Google Gemini API, based on ADR-008.

### 10.1. Class Structure and Initialization

-   **Class:** `py_pixel_bot.engines.gemini_analyzer.GeminiAnalyzer`
-   **`__init__(self, api_key: str, default_model_name: str = "gemini-pro-vision")`:**
    -   Stores the `api_key`.
    -   Stores the `default_model_name` (e.g., "gemini-1.5-flash-latest").
    -   Initializes the `google-generativeai` client using the provided API key (e.g., `genai.configure(api_key=api_key)`).
    -   Logs initialization status, confirming API key presence (but not logging the key itself).

### 10.2. Core Method: `query_vision_model`

-   **Signature:** `query_vision_model(self, image_data: np.ndarray, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]`
-   **Functionality:**
    1.  Takes a NumPy BGR `image_data` and a text `prompt`.
    2.  Uses `model_name` if provided, otherwise falls back to `self.default_model_name`.
    3.  **Image Preparation:** Converts the NumPy BGR array to a PIL Image object (RGB format) as required by the `google-generativeai` SDK.
        ```python
        # Example within GeminiAnalyzer
        from PIL import Image
        import cv2
        # ...
        pil_image = Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB))
        ```
    4.  Constructs the request payload for the Gemini API, typically a list containing the prompt string and the PIL image object.
        ```python
        # Example with google-generativeai SDK (simplified)
        # model = genai.GenerativeModel(model_name_to_use)
        # response = model.generate_content([prompt, pil_image])
        ```
    5.  Sends the request to the API within a `try...except` block to handle potential API errors and network issues. Records the start time.
    6.  Handles the API response:
        -   Records the end time to calculate latency.
        -   Safely extracts the text content from the response (e.g., `response.text`).
        -   Attempts to parse the text content as JSON **if** the prompt was designed to elicit a JSON response. This requires robust error handling (`json.JSONDecodeError`). Stores the parsed object or `None`.
        -   Catches specific API exceptions (e.g., `google.api_core.exceptions.ResourceExhausted` for rate limits, `PermissionDenied` for auth issues) and general exceptions.
    7.  **Return Value:** A structured dictionary containing the outcome:
        ```python
        {
            "status": "success" | "error", # Indicates if the API call was successful
            "text_content": "Full text response from Gemini, or None if error or no text part.",
            "json_content": {parsed JSON object if successful and applicable, else None},
            "error_message": "Error details if status is 'error', else None",
            "model_used": "model_name_actually_queried",
            "latency_ms": 1234 # Time taken for the API call in milliseconds
        }
        ```
-   **Logging:** Logs the start of a query (summarized prompt, model). Logs the outcome (success/error, latency). If error, logs the `error_message`. **Does NOT log the API key or raw image data.**

### 10.3. API Key Handling

-   The API key is obtained by `ConfigManager` from the `.env` file (`GEMINI_API_KEY`).
-   The key is passed to `GeminiAnalyzer` during its instantiation (likely by `RulesEngine` or potentially `MainController` if centralized initialization is preferred).
-   If the API key is missing or invalid, `GeminiAnalyzer` logs this, and its `query_vision_model` method immediately returns an error status dictionary without attempting an API call.

### 10.4. Error Handling and Retries

-   Implement specific `try-except` blocks for relevant `google.api_core.exceptions` (e.g., `ResourceExhausted`, `PermissionDenied`, `InvalidArgument`, `DeadlineExceeded`, `InternalServerError`) and standard network errors (`requests.exceptions.RequestException` if using `requests`, or equivalent for the SDK's underlying transport).
-   For initial implementation (v4.0.0 Phase 1), **no automatic retries** will be implemented. Failures will be reported immediately in the return dictionary. Retries could be added later for transient errors if needed.
-   Return clear error messages in the `error_message` field of the response dictionary.

### 10.5. Configuration

-   The default Gemini model name (`default_model_name`) can be overridden per-query via the `model_name` parameter in the `gemini_vision_query` condition spec. It can also be set globally in the profile settings (`settings.gemini_default_model_name`).
-   API call timeout should be handled by the underlying SDK where possible, or a reasonable default should be assumed. Advanced configuration is deferred.

### 10.6. Security and Privacy

-   Documentation and GUI MUST explicitly state that image data for `gemini_vision_query` conditions is sent to Google servers.
-   API key (`GEMINI_API_KEY`) is sensitive and MUST be stored securely in `.env` and added to `.gitignore`.

## 11. GUI Configuration for Gemini (v4.0.0 - `MainAppWindow` & `DetailsPanel`)

This section details the configuration needed in `gui_config.py` and how `DetailsPanel` will use it to render the UI for the `gemini_vision_query` condition type.

-   **`gui_config.py` Updates:**
    -   Add `"gemini_vision_query"` to `CONDITION_TYPES` list.
    -   Extend `UI_PARAM_CONFIG["conditions"]` dictionary with an entry for `"gemini_vision_query"`:
        ```python
        "gemini_vision_query": [
            {"id": "prompt", "label": "Gemini Prompt:", "widget": "textbox", "type": str, "default": "Describe this image.", "required": True, "placeholder": "e.g., Is there a login button visible?"},
            {"id": "expected_response_contains", "label": "Response Contains (Keywords):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., login,error (comma-sep for OR)"},
            {"id": "case_sensitive_response_check", "label": "Case Sensitive Check", "widget": "checkbox", "type": bool, "default": False},
            {"id": "expected_response_json_path", "label": "JSON Path (for JSON response):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., data.items[0].name"},
            {"id": "expected_json_value", "label": "Expected JSON Value:", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "Value at JSON path (string comparison)"},
            {"id": "capture_as", "label": "Capture Response As:", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "var_name_for_gemini_output"},
            {"id": "model_name", "label": "Gemini Model (Optional):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., gemini-1.5-flash-latest"}
            # Add 'region' parameter if needed, similar to other conditions that need region override
            # {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ]
        ```
-   **`DetailsPanel._render_dynamic_parameters`:**
    -   Must correctly handle the `textbox` widget type for the `prompt` parameter.
    -   Will use the above configuration to dynamically create the appropriate labels, entry fields, checkbox, and potentially dropdowns when `gemini_vision_query` is selected as the condition type (or sub-condition type).
-   **`MainAppWindow` Profile Settings:**
    -   Add a non-editable label widget showing the status of the `GEMINI_API_KEY` (e.g., "Loaded from .env", "Not found").
    -   Add an editable `CTkEntry` widget bound to `profile_data["settings"]["gemini_default_model_name"]`.