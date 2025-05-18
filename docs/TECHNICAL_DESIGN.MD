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
  - The main application window (`ctk.CTk`) for the full GUI profile editor.
  - **Updates for v4.0.0:**
    - Allows configuration of the new `gemini_vision_query` condition type and its parameters (prompt, response expectations, etc.) within the rule editor (`DetailsPanel`) based on `gui_config.py`.
    - Includes UI elements in its settings panel to indicate Gemini API key status (e.g., "Configured" or "Not Configured") and allow setting a default Gemini model name (`settings.gemini_default_model_name`).
- **`ui.gui.panels.details_panel.DetailsPanel` Class (v3.0.x, with v4.0.0 updates):**
  - Encapsulates the logic for displaying and editing details of selected items (Regions, Templates, Rules).
  - Dynamically renders input widgets based on `gui_config.UI_PARAM_CONFIG`.
  - **Updates for v4.0.0:** Will render specific widgets (e.g., `CTkTextbox` with appropriate height for `prompt`) for the `gemini_vision_query` condition type as defined in `gui_config.py`.
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
    -   `RulesEngine` includes fallback logic for local pre-emptive analyses if data is missing from the packet but the image is available.
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
    -   **Single Condition (Existing Local Types):** `{"type": "local_condition_name", "param1": value1, ...}`. May include `"capture_as": "var_name"`. May include `"region": "override_region_name"` to target a region different from the rule's default.
    -   **Compound Condition (Existing Local Types):** `{"logical_operator": "AND" | "OR", "sub_conditions": [list_of_single_local_condition_objects]}`. Each sub-condition can also have its own `"region": "override_region_name"`.
    -   **NEW `gemini_vision_query` type (Single Condition Structure - for v4.0.0):**
        ```json
        {
          "type": "gemini_vision_query",
          "region": "optional_region_name_override", 
          "prompt": "Describe this image in detail. Is there a prominent red button present? If so, describe its text.",
          "expected_response_contains": ["red button", "submit"], 
          "case_sensitive_response_check": false, 
          "expected_response_json_path": "elements[?(@.label=='button' && @.color=='red')].text", 
          "expected_json_value": "Proceed", 
          "capture_as": "gemini_analysis_result", 
          "model_name": "gemini-2.5-pro-preview-03-25" 
        }
        ```
        *(Note: All fields except `type` and `prompt` are optional for `gemini_vision_query`. If `region` is omitted, it uses the rule's default region.)*

-   **Action Object:** `{"type": "action_name", "param1": value1, ...}`. Parameters can contain placeholders like `{var_name}` or `{var_name.key}` for variable substitution.
    -   **Enhancement for v4.0.0 (Phase 1 Stretch/Phase 2):**
        -   A potential new `target_relation` for click/mouse actions: `center_of_gemini_identified_element`.
        -   Would require an associated parameter like `gemini_element_variable: "captured_button_info"`, where `captured_button_info` is a variable (from `capture_as` in a `gemini_vision_query` condition) expected to contain bounding box data (e.g., `{"box": [x,y,w,h], "label": "Confirm Button"}`). `ActionExecutor` would parse this.

### 5.2. `RulesEngine` Evaluation Logic (Updates for v4.0.0)

-   **Initialization (`__init__`):**
    -   Parses rules to build `_analysis_requirements_per_region` (for **local** analyses only).
    -   Loads templates into `_loaded_templates`.
    -   **Instantiates `GeminiAnalyzer`** if API key is available, passing the API key (obtained via `os.getenv`) and default model from `ConfigManager`.
-   **`evaluate_rules(all_region_data)`:** (Largely unchanged overall flow)
-   **`_check_condition(...)`:** (Handles single/compound logic. For each condition/sub-condition, it determines the target region by checking the condition's own `region` parameter first, then falling back to the rule's default `region`.)
-   **`_evaluate_single_condition_logic(...)` (Key updates for v4.0.0):**
    -   Handles existing local condition types.
    -   **NEW for `gemini_vision_query` type:**
        1.  Validates that necessary parameters (`prompt`) are present.
        2.  Retrieves the `captured_image` for the target region (determined by `_check_condition`) from `region_data`. If no image, the condition fails.
        3.  Checks if `self.gemini_analyzer` is available. If not, logs error and condition fails.
        4.  **Calls `self.gemini_analyzer.query_vision_model()`** with the image, prompt, and any specified `model_name` override from the condition.
        5.  If the `GeminiAnalyzer` call fails or returns an error/blocked status, the condition is marked as `False`, and the error is logged.
        6.  If successful, evaluates the **structured response** from `GeminiAnalyzer`:
            -   If `expected_response_contains` is specified, checks the `text_content` field.
            -   If `expected_response_json_path` and `expected_json_value` are specified, attempts to parse `json_content` (if present), extract the value using basic dot-notation path accessor, and compare it as strings. (Full JSONPath via library is deferred).
            -   Sets `condition_met` accordingly. If no specific content checks are defined, a successful API call means `condition_met = True`.
        7.  If `condition_met` is `True` AND `capture_as` is defined:
            -   Stores the relevant data from Gemini's response (e.g., `text_content`, or the value extracted by JSONPath from `json_content`, or the full `json_content` if no path specified for extraction) into the `rule_variable_context`.

-   **Action Execution Trigger:** (No change in logic flow: if rule's overall condition is True, action is prepared and executed).

### 5.3. Variable Handling (`RulesEngine`)

-   **Scope & Lifetime:** Rule-scoped, created during `evaluate_rules` for each rule, discarded after rule evaluation.
-   **Capture Points (Expanded for v4.0.0):**
    -   Existing: `ocr_contains_text` (captures full text), `template_match_found` (captures match details dict).
    -   **NEW:** `gemini_vision_query` can capture Gemini's `text_content` or a specific value extracted from its `json_content` (or the whole `json_content` if no path specified for extraction).
-   **Substitution (`_substitute_variables` method):**
    -   Uses `PLACEHOLDER_REGEX` (`\{([\w_]+)((\.[\w_]+)*)\}`) to find placeholders.
    -   Supports basic dot notation access for nested dictionary keys or list indices.

## 6. Data Flow Example (Simplified Continuous Loop with Gemini Query)

1.  **Init:** `RulesEngine` parses rules, builds **local** `_analysis_requirements_per_region`. `GeminiAnalyzer` is initialized with API key and default model.
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
                -   `_evaluate_single_condition_logic` retrieves the `captured_image` for the target region from `all_region_data`.
                -   **Calls `self.gemini_analyzer.query_vision_model()`** with the image and prompt.
                -   Receives structured response (`status`, `text_content`, `json_content`, `error_message`).
                -   Evaluates response against `expected_*` parameters.
                -   If `capture_as` used and condition met, updates `rule_variable_context` with Gemini's output.
            -   For local conditions, uses data from `all_region_data` or `AnalysisEngine` fallbacks.
        iii. If rule's overall condition is `True`:
            -   `_substitute_variables` replaces placeholders in `action_spec` using the (potentially Gemini-populated) `rule_variable_context`.
            -   `ActionExecutor.execute_action(substituted_action_spec)` is called.
    c.  Wait for `monitoring_interval_seconds` (minus cycle execution time).
3.  Loop repeats until stop event.

## 7. Logging System (per ADR-007)

-   Uses Python's built-in `logging`, configured by `core.logging_setup`.
-   Format includes timestamp, logger name, level, module:func:lineno, and message for files.
-   **NEW for v4.0.0:**
    -   **`GeminiAnalyzer` MUST** log API requests (prompt summary, model used), API responses (status, success/error, latency), and **any errors** encountered.
    -   **`RulesEngine` MUST** log when it's invoking `GeminiAnalyzer`, the prompt used (summarized), the model targeted, and the outcome of the `gemini_vision_query` condition.

## 8. Error Handling

-   Extensive `try-except` blocks. User-facing errors via `messagebox` or stderr. Detailed exceptions logged.
-   **NEW for v4.0.0:**
    -   **`GeminiAnalyzer` MUST** robustly handle API errors and return structured error info.
    -   **`RulesEngine` MUST** gracefully handle failures from `GeminiAnalyzer` (condition evaluates `False`, log error).
    -   GUI informs user if API key is missing/invalid.

## 9. Full GUI Architecture (v3.0.0+) (`MainAppWindow` using `CustomTkinter`)

### 9.4. Core Functionality Logic (`MainAppWindow` and `DetailsPanel`) (Updates for v4.0.0)

-   **Settings Panel (`MainAppWindow` - Left Panel):**
    -   Displays a read-only label for Gemini API Key status (`Loaded from .env` / `Not Found in .env`).
    -   Includes an editable `CTkEntry` for `gemini_default_model_name` (stored in `profile_data["settings"]`).
-   **Rule Editor (`DetailsPanel`):**
    -   When editing a rule's condition (single or sub-condition):
        -   The "Condition Type" dropdown (from `CONDITION_TYPES` in `gui_config.py`) INCLUDES `gemini_vision_query`.
        -   When `gemini_vision_query` is selected, `DetailsPanel._render_dynamic_parameters` dynamically creates and displays input fields based on `UI_PARAM_CONFIG["conditions"]["gemini_vision_query"]` (see Section 11). This includes a `CTkTextbox` for multi-line `prompt`.
-   Input validation (`gui_utils.validate_and_get_widget_value`) applies to these new fields.

## 10. Gemini API Interaction (`GeminiAnalyzer` - for v4.0.0)

### 10.1. Class Structure and Initialization

-   **Class:** `py_pixel_bot.engines.gemini_analyzer.GeminiAnalyzer`
-   **`__init__(self, api_key: str, default_model_name: str = "gemini-2.5-pro-preview-03-25")`:**
    -   Stores `api_key` and `default_model_name`.
    -   Initializes `google-generativeai` client. Logs status.

### 10.2. Core Method: `query_vision_model`

-   **Signature:** `query_vision_model(self, image_data: np.ndarray, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]`
-   **Functionality:** Converts BGR `image_data` to PIL RGB. Sends request. Handles response (text, JSON parsing attempt, errors, blocked content).
-   **Return Value:** Structured dictionary: `{"status": "success" | "error" | "blocked_prompt" | "blocked_response", "text_content": ..., "json_content": ..., ...}`.

## 11. GUI Configuration for Gemini (v4.0.0 - `MainAppWindow` & `DetailsPanel`)

-   **`gui_config.py` Updates:**
    -   `"gemini_vision_query"` added to `CONDITION_TYPES`.
    -   `DEFAULT_PROFILE_STRUCTURE["settings"]` includes `"gemini_default_model_name": "gemini-2.5-pro-preview-03-25"`.
    -   `UI_PARAM_CONFIG["conditions"]` has an entry for `"gemini_vision_query"`:
        ```python
        "gemini_vision_query": [
            {"id": "prompt", "label": "Gemini Prompt:", "widget": "textbox", "type": str, "default": "Describe this image.", "required": True, "placeholder": "e.g., Is there a login button visible?", "height": 120}, # height attribute for textbox
            {"id": "expected_response_contains", "label": "Response Contains (CSV for OR):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., login,error"},
            {"id": "case_sensitive_response_check", "label": "Case Sensitive Check", "widget": "checkbox", "type": bool, "default": False},
            {"id": "expected_response_json_path", "label": "JSON Path (Basic Dot Notation):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., data.items.0.name"},
            {"id": "expected_json_value", "label": "Expected JSON Value (String):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "Value at JSON path"},
            {"id": "capture_as", "label": "Capture Response As:", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "var_name_for_gemini_output"},
            {"id": "model_name", "label": "Gemini Model (Optional):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., gemini-1.5-pro-latest"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False}
        ]
        ```
-   **`DetailsPanel._render_dynamic_parameters`:**
    -   Handles `widget: "textbox"` and respects the optional `height` attribute from `param_def` (e.g., `param_def.get("height", 60)` where 60 is a smaller default for other textboxes).
-   **`MainAppWindow` Settings Panel:**
    -   `self.entry_gemini_default_model = CTkEntry(...)`
    -   `self.label_gemini_api_key_status = CTkLabel(...)`
    -   `_populate_ui_from_profile_data` populates these.
    -   `_update_profile_data_from_ui` reads from these.

## 12. Testing Strategy (v4.0.0 - Gemini Integration)

-   **Manual Integration Testing (Primary):**
    -   Requires a valid `GEMINI_API_KEY` in the `.env` file.
    -   **Focus Areas:**
        -   GUI: Creating, editing, saving, and loading profiles containing `gemini_vision_query` conditions.
        -   `RulesEngine`: Correct invocation of `GeminiAnalyzer`, accurate evaluation of text and JSON responses, proper variable capture.
        -   `GeminiAnalyzer`: Handling of various API responses (success, errors, blocked content), image preparation.
        -   End-to-end bot runs with profiles using Gemini conditions to verify actions are triggered correctly.
        -   Error handling for API key issues, network problems, and invalid prompts.
-   **Automated Testing (Future - Requires Mocking):**
    -   **Mocking `GeminiAnalyzer`:**
        -   A `MockGeminiAnalyzer` class will be created (e.g., in a `tests/mocks/` directory).
        -   This mock class will implement the same `query_vision_model` interface as the real `GeminiAnalyzer`.
        -   It will be configurable to return predefined responses for specific (image_hash, prompt) inputs or follow a sequence of responses. This allows simulating:
            -   Successful responses with varying text/JSON content.
            -   API error statuses (`"status": "error", "error_message": "..."`).
            -   Blocked prompt/response statuses.
            -   Different latencies (by including a `time.sleep` in the mock).
        -   **Dependency Injection:** `RulesEngine` will be refactored slightly in its `__init__` to allow injecting an instance of `GeminiAnalyzer` (or `MockGeminiAnalyzer`). By default, it will create the real one. Test setups will instantiate `RulesEngine` with the mock.
            ```python
            # Example in RulesEngine.__init__
            # self.gemini_analyzer = gemini_analyzer_instance if gemini_analyzer_instance else GeminiAnalyzer(...)
            ```
    -   **Unit Tests (e.g., using `pytest`):**
        -   Test `RulesEngine._evaluate_single_condition_logic` for `gemini_vision_query` by providing various mock responses and verifying condition outcomes and variable capture.
        -   Test `GeminiAnalyzer` internal logic (e.g., image preparation, basic response parsing structure) if complex enough, though direct API interaction mocking is key.
    -   **Integration Tests (Automated):**
        -   Test `RulesEngine.evaluate_rules` with profiles containing Gemini conditions, using the `MockGeminiAnalyzer` to simulate a sequence of visual states and API responses.