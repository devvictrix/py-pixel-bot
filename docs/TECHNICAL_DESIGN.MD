# Technical Design Document: Mark-I

This document outlines the technical design and architectural considerations for the Mark-I visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, v1.0.0, v2.0.0, and v3.0.0 are complete. Development for **v4.0.0 (Gemini-Powered Visual Intelligence)** Phase 1 (Core Integration) is also complete. The current focus is on **v4.0.0 Phase 1.5 / Start of Phase 2: Action on Gemini-Identified Element Bounding Box**, as detailed in ADR-008 and this document.

## 1. Core Architecture

The tool is modular, comprising several key Python components, all residing within the main `mark_i` package located at the project root: (Note: Python package name remains `mark_i`)

- **`core.config_manager` Module:**
  - `load_environment_variables()` function: Called at application startup to load `.env` (containing `APP_ENV` and **`GEMINI_API_KEY` for v4.0.0+**) using `python-dotenv` (per ADR-007, ADR-008).
  - `ConfigManager` class: Responsible for loading, validating (basic structure), providing access to, and saving bot profiles (JSON files from the `profiles/` directory, per ADR-003). It also provides the base path for profile-related assets like templates.
  - **Utilized by the `MainAppWindow` (GUI) for loading, saving, and path resolution for profiles and associated template images.**
- **`core.logging_setup` Module:**
  - `setup_logging()` function: Called after environment variables are loaded. Initializes Python's `logging` system based on `APP_ENV`, configuring handlers (console, date-stamped rotating file), formatters, and log levels (per ADR-007). CLI flags can override console log level. The `APP_ROOT_LOGGER_NAME` is "mark_i".
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
- **`engines.gemini_analyzer.GeminiAnalyzer` Class (v4.0.0+):**
  - **Responsibility:** Handles all communication with the Google Gemini API for advanced visual understanding (per ADR-008).
  - **Initialization:** Takes API key (from `.env` via `os.getenv`) and optional default model name (from profile settings via `ConfigManager`).
  - **Key Methods:** Provides `query_vision_model(image_data, prompt, [model_name])` which sends image/prompt to the API and returns a structured response (including parsed text/JSON and status/error info).
  - **Configuration:** API key loaded from `.env`. Default model configurable via profile settings (`settings.gemini_default_model_name`).
  - **Logging:** Comprehensive logging of API interactions, errors, and latency.
  - _Details in Section 10._
- **`engines.rules_engine.RulesEngine` Class:**
  - Evaluates rules based on analysis results (from `AnalysisEngine` for local checks, or from **`GeminiAnalyzer` for Gemini-powered checks**).
  - Supports single conditions, compound conditions (AND/OR logic per ADR-004), and rule-scoped variable capture and substitution.
  - **Initialization (`__init__`):**
    - Pre-parses rules to build `_analysis_requirements_per_region` for **local** analyses (OCR, dominant color, average color). `gemini_vision_query` conditions (v4.0.0+) do **not** add to these local pre-emptive requirements.
    - **Instantiates `GeminiAnalyzer` (for v4.0.0+), passing API key from `os.getenv` and default model from `ConfigManager`.**
  - **`_evaluate_single_condition_logic(...)` (Updated for v4.0.0):**
    - Handles existing local condition types.
    - **For `gemini_vision_query` type (v4.0.0+):**
      - Retrieves the `captured_image` for the condition's target region.
      - **Calls the `GeminiAnalyzer` with the image and prompt from the condition spec.**
      - Evaluates Gemini's response based on `expected_response_contains` or `expected_response_json_path`/`expected_json_value`.
      - Handles API call errors gracefully (condition evaluates to `False`, log error).
      - If `capture_as` is defined, stores the relevant Gemini response (e.g., full text, specific JSON-extracted value, or the **entire parsed JSON object which could contain bounding box data, along with the source region name**) into the `rule_variable_context`.
- **`engines.action_executor.ActionExecutor` Class (Updated for v4.0.0 Phase 1.5):**
  - Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
  - Calculates target coordinates for actions.
  - **Enhancement for v4.0.0 Phase 1.5:**
    - Modified to handle new `target_relation` values like `center_of_gemini_element` and `top_left_of_gemini_element`.
    - Requires an associated parameter `gemini_element_variable` referencing a variable that holds element details including a `box` field (e.g., `{"value": {"box": [x_rel, y_rel, w, h], "label": "element_label", "found": true}, "_source_region_for_capture_": "region_name"}`).
    - `_get_target_coords` method updated to parse this variable and calculate absolute screen coordinates based on the bounding box relative to the region where the Gemini query was performed.
- **`main_controller.MainController` Class:** (Located in `mark_i/main_controller.py`)
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
  - The main application window (`ctk.CTk`) for the full GUI profile editor.
  - **Updates for v4.0.0 Phase 1.5:**
    - The `DetailsPanel` (managed by `MainAppWindow`) will be updated to support the new action parameters for clicking Gemini-identified elements (e.g., `target_relation: center_of_gemini_element`, `gemini_element_variable`).
- **`ui.gui.panels.details_panel.DetailsPanel` Class (v3.0.x, with v4.0.0 updates):**
  - Encapsulates the logic for displaying and editing details of selected items (Regions, Templates, Rules).
  - Dynamically renders input widgets based on `gui_config.UI_PARAM_CONFIG`.
  - **Updates for v4.0.0 Phase 1.5:** Will render specific widgets for the new action parameters related to Gemini bounding boxes, as defined in `gui_config.py`. This includes conditional visibility for the `gemini_element_variable` field based on the selected `target_relation`.
- **`mark_i/__main__.py`:**
  - Entry point for the application. Initializes core components (Env Vars, Logging, Config) and dispatches CLI commands.

## 2. Key Libraries & Justifications (Summary from ADRs)

-   **Environment Management:** `python-dotenv` (ADR-007)
-   **Logging:** Python `logging` module (ADR-007)
-   **Screen Capture:** `Pillow` (`ImageGrab` for Windows), `OpenCV-Python` (for conversion and potential alternatives) (ADR-001).
-   **Image Processing & Analysis (Local):** `OpenCV-Python` (cv2), `NumPy`, `Pillow` (ADR-001).
-   **OCR (Local):** `pytesseract` (ADR-001).
-   **Remote Advanced Visual Analysis (v4.0.0+):** `google-generativeai` (Python SDK for Gemini) (ADR-008).
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
    -   `RulesEngine` includes fallback logic for local pre-emptive analyses if data is missing from the packet but the image is available.
3.  **Remote On-Demand Analysis (NEW - by `RulesEngine` via `GeminiAnalyzer` - for v4.0.0):**
    -   When a `gemini_vision_query` condition is evaluated by `RulesEngine._evaluate_single_condition_logic`:
        -   The `captured_image` for the target region is retrieved from the `all_region_data` packet.
        -   `RulesEngine` calls `GeminiAnalyzer.query_vision_model()` with this image and the prompt specified in the rule's condition parameters.
        -   The response from `GeminiAnalyzer` (e.g., text description, JSON data, error status) is then processed by `RulesEngine` to determine if the condition is met and to capture any specified variables.
    -   This is **"on-demand"** as costly and potentially slow Gemini API calls are made **only** when a rule specifically requiring Gemini analysis is being evaluated in the current cycle.

## 5. Rules Engine & Evaluation

(This section describes the JSON rule structure and `RulesEngine`'s processing logic, including single/compound conditions, variable handling, parameter evaluation, and the Gemini integration.)

### 5.1. Rule Structure in JSON Profiles (Updates for v4.0.0 Phase 1.5 - Actions)

-   **Condition Object:**
    -   **Single Condition (Existing Local Types):** `{"type": "local_condition_name", "param1": value1, ...}`. May include `"capture_as": "var_name"`. May include `"region": "override_region_name"` to target a region different from the rule's default.
    -   **Compound Condition (Existing Local Types):** `{"logical_operator": "AND" | "OR", "sub_conditions": [list_of_single_local_condition_objects]}`. Each sub-condition can also have its own `"region": "override_region_name"`.
    -   **`gemini_vision_query` type (Single Condition Structure - for v4.0.0 Phase 1):**
        ```json
        {
          "type": "gemini_vision_query",
          "region": "optional_region_name_override",
          "prompt": "Describe this image in detail. Is there a prominent red button present? If so, describe its text. Respond with JSON: {\"button_present\": true/false, \"button_text\": \"text_or_null\"}",
          "expected_response_contains": ["red button", "submit"],
          "case_sensitive_response_check": false,
          "expected_response_json_path": "button_present",
          "expected_json_value": true,
          "capture_as": "gemini_analysis_result",
          "model_name": "gemini-1.5-flash-latest"
        }
        ```
        *(Note: All fields except `type` and `prompt` are optional for `gemini_vision_query`. If `region` is omitted, it uses the rule's default region.)*
    -   For **v4.0.0 Phase 1.5 (Bounding Box Actions)**, the `gemini_vision_query` condition is used to capture JSON containing bounding box data. The specific prompt and expected JSON structure are detailed in Section 10.3. The `capture_as` field will store this entire JSON object, wrapped in a structure that also includes its source region (see 5.3).

-   **Action Object:** (Updates for click/mouse actions in v4.0.0 Phase 1.5)
    ```json
    // Example click action using a Gemini-identified element
    {
      "type": "click",
      "target_relation": "center_of_gemini_element", // NEW target_relation
      "gemini_element_variable": "captured_button_info", // NEW parameter: name of variable holding element data
      "button": "left",
      "clicks": 1,
      "interval": 0.0,
      "pyautogui_pause_before": 0.1,
      "comment": "Clicks the center of the element identified by Gemini and stored in 'captured_button_info'"
    }
    ```
    -   **New `target_relation` values for click/mouse actions (v4.0.0 Phase 1.5):**
        -   `center_of_gemini_element`: Clicks the center of the bounding box provided by the Gemini-identified element.
        -   `top_left_of_gemini_element`: Clicks the top-left corner of the bounding box.
    -   **New action parameter `gemini_element_variable` (string) (v4.0.0 Phase 1.5):**
        -   Required when `target_relation` is one of the `*_gemini_element` types.
        -   Specifies the name of the rule-scoped variable (captured by a `gemini_vision_query` condition) that holds the structured data for the identified element. This data is expected to be a dictionary from the `RulesEngine` like `{"value": {"box": [x,y,w,h], "found":true}, "_source_region_for_capture_": "region_name"}`.

### 5.2. `RulesEngine` Evaluation Logic (Updates for v4.0.0 Phase 1.5)

-   **`_evaluate_single_condition_logic(...)` for `gemini_vision_query`:**
    -   If `capture_as` is defined, the `captured_value_for_var` (which can be the full text, specific JSON-extracted value, or entire parsed JSON object) is stored along with the `region_name` (where the Gemini query operated) in a dictionary structure: `{"value": captured_value_for_var, "_source_region_for_capture_": region_name}`. This combined object is then put into `rule_variable_context[capture_as_var_name]`.
    -   This ensures that `ActionExecutor` can later retrieve both the Gemini data (`value`) and the `_source_region_for_capture_` needed to correctly interpret relative bounding box coordinates.
-   **`evaluate_rules(...)` - Context for Actions (Updated for v4.0.0 Phase 1.5):**
    -   The `_check_condition` method now returns a tuple: `(condition_met_status, determinant_region_name)`.
    -   The `determinant_region_name` is used to populate `action_context["condition_region"]`. This `condition_region` provides general context for actions.
    -   For Gemini-specific actions, `ActionExecutor` primarily relies on the `_source_region_for_capture_` stored within the captured variable itself (retrieved via `gemini_element_variable`).

### 5.3. Variable Handling (`RulesEngine`)

-   **Scope & Lifetime:** Rule-scoped, created during `evaluate_rules` for each rule, discarded after rule evaluation.
-   **Capture Points (Expanded for v4.0.0):**
    -   Existing: `ocr_contains_text` (captures full text), `template_match_found` (captures match details dict).
    -   **NEW (v4.0.0):** `gemini_vision_query` can capture Gemini's `text_content`, a specific value extracted from its `json_content` (if `expected_response_json_path` is used for extraction), or the **entire `json_content` as a Python dictionary/list**.
    -   **NEW (v4.0.0 Phase 1.5): When `gemini_vision_query` captures data via `capture_as`, the value stored in `rule_variable_context` is a dictionary: `{"value": <actual_captured_data>, "_source_region_for_capture_": "region_name_of_gemini_query"}`.**
-   **Substitution (`_substitute_variables` method):**
    -   Uses `PLACEHOLDER_REGEX` (`\{([\w_]+)((\.[\w_]+)*)\}`) to find placeholders.
    -   Supports basic dot notation access for nested dictionary keys or list indices (e.g., `{my_gemini_var.value.box.0}` to get the x-coordinate if `my_gemini_var` holds the wrapped Gemini capture and `box` is `[x,y,w,h]` inside its `value`).
    -   For the `gemini_element_variable` action parameter, the placeholder mechanism will substitute the *name* of the variable. `ActionExecutor` then uses this name to look up the actual wrapped data (the dictionary with `value` and `_source_region_for_capture_`) from the `variables` sub-dictionary within the `action_context`.

## 6. Data Flow Example (Simplified Continuous Loop with Gemini Bounding Box Click - v4.0.0 Phase 1.5)

1.  **Init:** `RulesEngine` parses rules. `GeminiAnalyzer` is initialized.
2.  `MainController` loop starts (`run_monitoring_loop` in thread):
    a.  For each `region_spec` in profile (e.g., "main_app_area" at screen `100,200` with size `800x600`):
        i.  `CaptureEngine.capture_region()` captures image -> `captured_image` (NumPy BGR).
        ii. Selective local analysis performed if needed.
        iii. `all_region_data["main_app_area"]` gets `{"image": captured_image, ...}`.
    b.  `RulesEngine.evaluate_rules(all_region_data)`:
        i.  Considers a rule named "FindAndClickLoginButton":
            -   Rule's `condition`:
                ```json
                {
                    "type": "gemini_vision_query",
                    "region": "main_app_area", // Explicitly targets the region for this query
                    "prompt": "Find 'Login' button. Respond with JSON: {\"label\":\"login_btn\", \"box\":[x,y,w,h], \"found\":true/false}",
                    "capture_as": "login_button_data",
                    "expected_response_json_path": "found", // Example: also check 'found' is true
                    "expected_json_value": true
                }
                ```
            -   `_evaluate_single_condition_logic` is called for this condition on "main_app_area".
            -   It calls `self.gemini_analyzer.query_vision_model()` with "main_app_area"'s image and the prompt.
            -   Gemini responds, e.g., `{"status": "success", "json_content": {"label": "login_btn", "box": [50, 70, 120, 30], "found": true}, ...}`.
            -   `rule_variable_context["login_button_data"]` is set to `{"value": {"label": "login_btn", "box": [50, 70, 120, 30], "found": true}, "_source_region_for_capture_": "main_app_area"}`.
            -   The `expected_response_json_path` "found" and `expected_json_value` true are checked against the `json_content`, also passing.
            -   The overall condition for the rule is `True`.
        ii. Rule's `action` to be executed:
            ```json
            {
                "type": "click",
                "target_relation": "center_of_gemini_element",
                "gemini_element_variable": "login_button_data" // This is the key name
            }
            ```
        iii. `action_context` is constructed by `RulesEngine`:
            ```python
            action_context = {
                "rule_name": "FindAndClickLoginButton",
                "condition_region": "main_app_area", // From _check_condition's determinant_region
                "last_match_info": {...}, 
                "variables": {
                    "login_button_data": {"value": {"label": "login_btn", "box": [50, 70, 120, 30], "found": true}, "_source_region_for_capture_": "main_app_area"}
                }
            ```
        iv. `ActionExecutor.execute_action(substituted_action_spec, action_context)` is called.
            -   Inside `ActionExecutor._get_target_coords`:
                -   `target_relation` is "center_of_gemini_element".
                -   `gemini_var_name` from spec is "login_button_data".
                -   `wrapped_element_data` is retrieved from `action_context["variables"]["login_button_data"]`.
                -   `element_value = wrapped_element_data["value"]` (which is `{"box": [50,70,120,30], ...}`)
                -   `box_data` is `[50, 70, 120, 30]`.
                -   `gemini_query_region_name` is "main_app_area" from `wrapped_element_data["_source_region_for_capture_"]`.
                -   `gemini_query_region_config` for "main_app_area" is fetched: `{"x": 100, "y": 200, "width": 800, "height": 600}`.
                -   `region_base_x = 100`, `region_base_y = 200`.
                -   `rel_x=50, rel_y=70, box_w=120, box_h=30`.
                -   Calculates absolute click target: `abs_x = 100 + 50 + (120 // 2) = 210`. `abs_y = 200 + 70 + (30 // 2) = 285`.
                -   Returns `(210, 285)`.
            -   PyAutoGUI clicks at screen coordinates `(210, 285)`.
    c.  Wait for `monitoring_interval_seconds` (minus cycle execution time).
3.  Loop repeats until stop event.

## 7. Logging System (per ADR-007)

-   Uses Python's built-in `logging`, configured by `core.logging_setup`. Root logger for Mark-I is `mark_i`.
-   Format includes timestamp, logger name, level, module:func:lineno, and message for files.
-   **v4.0.0+ Specifics:**
    -   **`GeminiAnalyzer` MUST** log API requests (prompt summary, model used), API responses (status, success/error, latency), and **any errors** encountered.
    -   **`RulesEngine` MUST** log when it's invoking `GeminiAnalyzer`, the prompt used (summarized), the model targeted, and the outcome of the `gemini_vision_query` condition.
    -   **`ActionExecutor` MUST** log details when targeting Gemini-identified elements, including the variable name used, the extracted relative box, the base region name and coordinates, and the final calculated absolute screen coordinates.

## 8. Error Handling

-   Extensive `try-except` blocks. User-facing errors via `messagebox` or stderr. Detailed exceptions logged.
-   **v4.0.0+ Specifics:**
    -   **`GeminiAnalyzer` MUST** robustly handle API errors (authentication, rate limits, invalid requests, network issues, content blocking) and return structured error info.
    -   **`RulesEngine` MUST** gracefully handle failures from `GeminiAnalyzer` (condition evaluates `False`, log error).
    -   GUI informs user if API key is missing/invalid.
    -   **`ActionExecutor._get_target_coords` (v4.0.0 Phase 1.5):**
        -   Must handle cases where `gemini_element_variable` is missing from action spec or not found in rule context's `variables`.
        -   Must validate that the resolved variable's value is a dictionary and contains the `value` (actual Gemini data) and `_source_region_for_capture_` keys.
        -   Must validate that `element_data["value"]` is a dictionary and contains a `box` key.
        -   Must validate that `box` is a list of 4 numeric values.
        -   Should ideally check a `found: true` flag in the element data if present and skip action if `false`.
        -   Must handle cases where the `_source_region_for_capture_` is missing or its config cannot be found.
        -   All such errors should be logged clearly, and `_get_target_coords` should return `None`, causing the action to be skipped.

## 9. Full GUI Architecture (v3.0.0+) (`MainAppWindow` using `CustomTkinter`)

### 9.1. Overall Structure
(As previously defined: Main window, Left Panel for settings/regions/templates, Center Panel for rules list, Right Panel (DetailsPanel) for editing selected item.)

### 9.2. File Operations (Menu)
(New, Open, Save, Save As - as previously defined.)

### 9.3. Core Data Model (`self.profile_data` in `MainAppWindow`)
(Mirrors the JSON profile structure. Changes in UI update this dictionary, which is then saved.)

### 9.4. Core Functionality Logic (`MainAppWindow` and `DetailsPanel`) (Updates for v4.0.0 Phase 1.5)

-   **Settings Panel (`MainAppWindow` - Left Panel):**
    -   Displays a read-only label for Gemini API Key status (`Loaded from .env` / `Not Found in .env`).
    -   Includes an editable `CTkEntry` for `gemini_default_model_name` (stored in `profile_data["settings"]`).
-   **Rule Editor (`DetailsPanel`):**
    -   When editing a rule's condition (single or sub-condition):
        -   The "Condition Type" dropdown (from `CONDITION_TYPES` in `gui_config.py`) INCLUDES `gemini_vision_query`.
        -   When `gemini_vision_query` is selected, `DetailsPanel._render_dynamic_parameters` dynamically creates and displays input fields based on `UI_PARAM_CONFIG["conditions"]["gemini_vision_query"]` (see Section 11). This includes a `CTkTextbox` for multi-line `prompt`.
    -   When editing a rule's **action**:
        -   If action `type` is "click" (or other mouse actions supporting similar targeting):
            -   The "Target Relation" dropdown (`act_target_relation`) will include `center_of_gemini_element` and `top_left_of_gemini_element`.
            -   An `CTkEntry` for "Gemini Element Var:" (`act_gemini_element_variable`) will be shown **only if** a Gemini-related target relation is selected. This requires conditional UI logic in `DetailsPanel._render_dynamic_parameters` (e.g., reacting to changes in the "Target Relation" OptionMenu).
-   Input validation (`gui_utils.validate_and_get_widget_value`) applies to these new fields.

### 9.5. Item Lists (Regions, Templates, Rules, Sub-Conditions)
(Managed via `_populate_specific_list_frame` and `_highlight_selected_list_item` - as previously defined.)

### 9.6. Dynamic Parameter Rendering (`DetailsPanel._render_dynamic_parameters`) (Updated for v4.0.0 Phase 1.5)
-   This method reads `UI_PARAM_CONFIG` to create widgets.
-   **NEW:** It needs to interpret the `condition_show` meta-property (see Section 11) within parameter definitions.
-   When a controlling field (e.g., "Target Relation" OptionMenu for click actions) changes, it must trigger a re-evaluation of visibility for dependent fields. This can be done by:
    -   Binding a command to the controlling OptionMenu that calls a method to update dependent field visibility.
    -   This update method will iterate through param_defs, check `condition_show`, and `pack_forget()` or `grid_forget()` / `pack()` or `grid()` the dependent widget.
    -   The `required` status for `_get_parameters_from_ui` also needs to respect this conditional visibility.

### 9.7. Data Persistence (Saving/Loading)
(Handled by `MainAppWindow` calling `ConfigManager` or `ConfigManager.save_profile_data_to_path`.)

### 9.8. Component Refactoring (v3.0.x - Done)
(Refactoring of `MainAppWindow` and `DetailsPanel` into smaller components like `RegionDetailView`, `RuleDetailView`, etc., is complete.)

## 10. Gemini API Interaction (`GeminiAnalyzer` - for v4.0.0)

### 10.1. Class Structure and Initialization

-   **Class:** `mark_i.engines.gemini_analyzer.GeminiAnalyzer`
-   **`__init__(self, api_key: str, default_model_name: str = "gemini-1.5-flash-latest")`:**
    -   Stores `api_key` and `default_model_name`.
    -   Initializes `google-generativeai` client (`genai.configure(api_key=...)`). Logs status.

### 10.2. Core Method: `query_vision_model`

-   **Signature:** `query_vision_model(self, image_data: np.ndarray, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]`
-   **Functionality:**
    1.  Converts input BGR `image_data` (NumPy array) to PIL Image (RGB).
    2.  Constructs the request content (prompt + image).
    3.  Calls `genai.GenerativeModel(model_to_use).generate_content(contents, stream=False, safety_settings=..., generation_config=...)`.
    4.  Handles the response:
        -   Checks `response.prompt_feedback` for blocking.
        -   Checks `response.candidates[0].finish_reason` for safety blocking or other non-STOP reasons.
        -   Extracts text content from `response.candidates[0].content.parts`.
        -   Attempts to parse extracted text content as JSON.
    5.  Returns a structured dictionary:
        ```python
        {
            "status": "success" | "error" | "blocked_prompt" | "blocked_response",
            "text_content": "Full text response from Gemini, or None.",
            "json_content": {parsed JSON object if applicable, else None}, # This is key for bounding boxes
            "error_message": "Error details if status is 'error', else None",
            "model_used": "model_name_actually_queried",
            "latency_ms": 1234 # Time taken for the API call
        }
        ```
-   **Error Handling:** Robustly catches API errors, network issues, content filtering/blocking, and returns appropriate status/error messages in the result dictionary.

### 10.3. Prompting for Bounding Boxes (NEW - v4.0.0 Phase 1.5)

-   **Strategy:** Users must craft prompts that explicitly ask Gemini to return bounding box information, preferably in a structured JSON format. The JSON should ideally include a `box` key with an array of 4 numbers representing `[x_relative, y_relative, width, height]` and a `found` key (boolean).
-   **Example Prompt for Gemini:**
    ```text
    Analyze the provided image. Identify the element described as "the main login button".
    Respond ONLY with a single JSON object formatted exactly as follows:
    {
      "element_label": "login_button", // A consistent label for what was searched
      "found": true, // Boolean: true if the element is confidently identified, false otherwise
      "box": [50, 100, 120, 30] // Array [x, y, width, height] relative to top-left of THIS image. Null if not found.
      // Optional: "confidence_score": 0.85 // A score from Gemini if it provides one
    }
    If the element is not found, set "found" to false and "box" to null.
    Do not add any explanatory text outside of this JSON object.
    ```
-   **Expected JSON Response Structure (from Gemini, captured by `RulesEngine` into a variable):**
    The `gemini_vision_query` condition's `capture_as` variable (e.g., `login_button_data`) would hold a Python dictionary (wrapped by `RulesEngine` as described in 5.3):
    ```python
    # Example of what variable_context["login_button_data"] would hold:
    {
        "value": { # This is the actual data from Gemini
            "element_label": "login_button",
            "found": True,
            "box": [50, 100, 120, 30]  # [x_rel_to_img, y_rel_to_img, width, height]
        },
        "_source_region_for_capture_": "name_of_region_gemini_analyzed"
    }
    ```
    The `found: true` flag is highly recommended. `ActionExecutor` will check this; if `found` is `False` or the `box` is invalid/null, the action should be skipped.
-   **Coordinate System:** The `[x, y, width, height]` in the `box` array are coordinates **relative to the top-left of the image region that was sent to Gemini.** `ActionExecutor` must account for this by adding the screen `x, y` of that region (obtained from the `_source_region_for_capture_` field in the captured variable) to these relative coordinates to get absolute screen coordinates for PyAutoGUI.

### 10.4. Parsing Bounding Box Responses in `GeminiAnalyzer`

-   No specific changes are required in `GeminiAnalyzer.query_vision_model` for parsing bounding boxes beyond its existing capability to parse any valid JSON response from Gemini into the `json_content` field of its return dictionary.
-   The `RulesEngine` will then take this `json_content` (which is a Python dict/list) and store it (wrapped with source region info) in the `rule_variable_context` if `capture_as` is used. This makes the entire structured data (including the `box` array) and its origin available for `ActionExecutor`.

## 11. GUI Configuration for Gemini (v4.0.0 Phase 1.5 - Actions)

-   **`gui_config.py` Updates:**
    -   `CLICK_TARGET_RELATIONS` constant will be updated to include:
        -   `center_of_gemini_element`
        -   `top_left_of_gemini_element`
        ```python
        # In gui_config.py
        CLICK_TARGET_RELATIONS = [
            "center_of_region",
            "center_of_last_match",
            "absolute",
            "relative_to_region",
            "center_of_gemini_element", # NEW
            "top_left_of_gemini_element"  # NEW
        ]
        ```
    -   `UI_PARAM_CONFIG["actions"]["click"]` will have a new parameter definition added for `gemini_element_variable`:
        ```python
        # In gui_config.py, within UI_PARAM_CONFIG["actions"]["click"] list:
        # ... (other params)
        {
            "id": "gemini_element_variable", 
            "label": "Gemini Element Var:", 
            "widget": "entry", "type": str, 
            "default": "", "required": False, # Dynamically required
            "allow_empty_string": False, 
            "placeholder": "e.g., captured_button_data",
            "condition_show": {"field_id_prefix": "act_", "field": "target_relation", "values": ["center_of_gemini_element", "top_left_of_gemini_element"]}
        },
        # ... (button, clicks, interval, pyautogui_pause_before)
        ```
        The `condition_show` meta-property indicates that this "gemini_element_variable" field should only be shown (and considered required if its own `required` flag were True) when the `act_target_relation` widget's value is one of the specified `values`.
-   **`DetailsPanel._render_dynamic_parameters`:**
    -   Will be enhanced to read the `condition_show` meta-property.
    -   When rendering parameters, if a parameter definition includes `condition_show`:
        -   It will find the controlling widget (e.g., the OptionMenu for `act_target_relation`).
        -   It will initially show/hide the conditional widget based on the current value of the controlling widget.
        -   It will bind a callback to the `command` of the controlling widget (e.g., the "Target Relation" OptionMenu). This callback will trigger a re-evaluation of visibility for all dependent fields within the same parameter group (e.g., all action parameters).
-   **`DetailsPanel._get_parameters_from_ui`:**
    -   When validating and collecting parameters, if a field has a `condition_show` definition, its "required" status will be dynamically assessed. If its `condition_show` prerequisites are met (i.e., it's visible) AND its own `param_def.get("required", False)` is `True`, then it's treated as required. If it's hidden due to `condition_show`, it's not treated as required, regardless of its own `required` flag.

## 12. `ActionExecutor` - Handling Gemini Element Clicks (v4.0.0 Phase 1.5)

The `ActionExecutor._get_target_coords` method will be extended as shown in the previous `action_executor.py` code block. It will:
- Retrieve the wrapped Gemini data object using `gemini_element_variable` from the `context["variables"]`.
- Extract the `value` (actual Gemini JSON response) and `_source_region_for_capture_`.
- Validate the presence and format of `box` within `value`.
- Check the `found` flag in `value` if present.
- Use `_source_region_for_capture_` to get the base coordinates of the region Gemini analyzed.
- Calculate absolute screen coordinates for the click.
- Log errors and return `None` if any step fails, preventing the action.

## 13. Testing Strategy (v4.0.0 - Gemini Bounding Box Actions)

-   **Manual Integration Testing:**
    *   Craft profiles with `gemini_vision_query` conditions that ask for bounding boxes (including the `found` flag and `element_label` as per Section 10.3).
    *   Verify that variables capture the wrapped JSON structure correctly (inspect logs or use `log_message` action to print the variable: `{my_var.value.box}`).
    *   Test "click" actions using `center_of_gemini_element` and `top_left_of_gemini_element` target relations, ensuring accurate targeting on screen based on visual confirmation.
    *   Test with various Gemini models (Flash, Pro) if access permits, to see if box accuracy varies.
    *   Test error cases:
        -   `gemini_element_variable` specified in action but the variable is not captured by the condition (or condition failed).
        -   Captured variable does not contain a `value` or `_source_region_for_capture_` key.
        -   Captured `value` does not contain a `box` key or `box` is malformed.
        -   Captured `value` has `found: false`.
        -   Gemini fails to find the element or returns unexpected JSON.
        -   The `_source_region_for_capture_` is somehow lost or misidentified.
    *   Test cases where the Gemini query region (specified in the `gemini_vision_query` condition) is different from the rule's default region.
-   **Automated Testing (Requires Mocking `GeminiAnalyzer`):**
    *   Extend `MockGeminiAnalyzer` to return predefined JSON responses including `box`, `found`, and `element_label` keys for specific prompts/image hashes. This allows simulating Gemini's output without actual API calls.
    *   **Unit Tests for `ActionExecutor._get_target_coords`:**
        *   Provide various `action_spec` and `context` dictionaries (with mocked `variables` containing wrapped element data and mocked `_source_region_for_capture_` names).
        *   Verify correct absolute coordinate calculation for `center_of_gemini_element` and `top_left_of_gemini_element`.
        *   Test all error conditions outlined in manual testing. Ensure `None` is returned and errors are logged.
    *   **Integration Tests for `RulesEngine` + `ActionExecutor`:**
        *   Configure `RulesEngine` with the `MockGeminiAnalyzer`.
        *   Define test profiles with rules that:
            1.  Use `gemini_vision_query` (mocked to return specific box data and `found: true`).
            2.  Use `capture_as` to store this mocked Gemini response.
            3.  Have an action (e.g., "click") that uses `center_of_gemini_element` with the captured variable.
        *   Execute `RulesEngine.evaluate_rules` with mock region data.
        *   Verify that `ActionExecutor.execute_action` is called with the correctly formed `action_context` (including `variables` where Gemini captures are wrapped, and `condition_region`).
        *   Further mock or spy on `ActionExecutor._get_target_coords` or `pyautogui.click` to confirm the final coordinates would have been correct.
        *   Test scenarios where the mock `GeminiAnalyzer` returns `found: false` and ensure the action is appropriately skipped by `ActionExecutor`.