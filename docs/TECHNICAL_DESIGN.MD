# Technical Design Document: Mark-I

This document outlines the technical design and architectural considerations for the Mark-I visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. **Version 4.0.0 (Gemini-Powered Visual Intelligence), including all its sub-phases (Phase 1: Core Vision Query, Phase 1.5: Bounding Box Actions, Phase 2: Gemini-Informed Decision Making, and Phase 3: Natural Language Command Interface), is now considered functionally complete.**

## 1. Core Architecture

The tool is modular, comprising several key Python components, all residing within the main `mark_i` package located at the project root:

- **`core.config_manager` Module:**
  - `load_environment_variables()` function: Called at application startup to load `.env` (containing `APP_ENV` and `GEMINI_API_KEY` for v4.0.0+) using `python-dotenv` (per ADR-007, ADR-008).
  - `ConfigManager` class: Responsible for loading, validating (basic structure), providing access to, and saving bot profiles (JSON files from the `profiles/` directory, per ADR-003). It also provides the base path for profile-related assets like templates.
  - Utilized by the `MainAppWindow` (GUI) for loading, saving, and path resolution for profiles and associated template images.
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
  - Responsibility: Handles all direct communication with the Google Gemini API for advanced visual understanding (per ADR-008), supporting both vision and text model interactions as needed.
  - Initialization: Takes API key (from `.env` via `os.getenv`) and optional default model name (from profile settings via `ConfigManager`).
  - Key Methods: Provides `query_vision_model(image_data, prompt, [model_name])` which sends image/prompt to the API and returns a structured response (including parsed text/JSON and status/error info). Can also be used for text-only prompts by providing minimal/no image data if the underlying model supports it.
  - Configuration: API key loaded from `.env`. Default model configurable via profile settings (`settings.gemini_default_model_name`).
  - Logging: Comprehensive logging of API interactions, errors, and latency.
  - _Details in Section 10._
- **`engines.rules_engine.RulesEngine` Class:**
  - Evaluates rules based on analysis results (from `AnalysisEngine` for local checks, or from `GeminiAnalyzer` for Gemini-powered `gemini_vision_query` conditions).
  - Supports single conditions, compound conditions (AND/OR logic per ADR-004), and rule-scoped variable capture and substitution.
  - Instantiates its own `GeminiAnalyzer` (for v4.0.0+) for handling `gemini_vision_query` conditions.
  - For actions of type `gemini_perform_task`, it invokes the `GeminiDecisionModule` to handle NLU commands and goal-oriented task execution.
  - _Details in Section 5._
- **`engines.action_executor.ActionExecutor` Class:**
  - Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
  - Calculates target coordinates for actions, including those derived from Gemini bounding boxes (v4.0.0 Phase 1.5).
  - Called by `RulesEngine` for standard actions (if `RulesEngine` directly executes them, or prepares specs for `MainController`) and by `GeminiDecisionModule` for executing primitive steps of an NLU-driven task.
- **`engines.gemini_decision_module.GeminiDecisionModule` Class (v4.0.0 Phase 2 & 3):**
  - **NLU Task Orchestrator:** Parses natural language user commands (received via the `gemini_perform_task` action's `natural_language_command` parameter).
  - Decomposes these commands into a sequence of manageable steps/sub-goals using Gemini for NLU.
  - For each decomposed step, uses `GeminiAnalyzer` for visual analysis (if needed) and action refinement (e.g., finding specific elements, getting bounding boxes for described targets).
  - Manages basic state across steps of a single NLU task.
  - Orchestrates execution of these steps by constructing specifications for and calling `ActionExecutor`.
  - Implements safety measures like using a predefined set of allowed sub-actions and optional user confirmation per step.
  - _Details extensively in Section 14._
- **`main_controller.MainController` Class:**
  - Orchestrates the main bot operation loop for rule-based profile execution.
  - Runs the monitoring loop in a separate thread (per ADR-006).
  - Instantiates all engine components: `CaptureEngine`, `AnalysisEngine`, `ActionExecutor`, a shared `GeminiAnalyzer` (primarily for `GeminiDecisionModule`), and `GeminiDecisionModule`. It then passes these to `RulesEngine` (which also instantiates its own `GeminiAnalyzer` for `gemini_vision_query` conditions, ensuring modularity).
  - For each monitored region in a profile:
    - Instructs `CaptureEngine` to capture the image.
    - Selectively instructs `AnalysisEngine` to perform required **local** general analyses based on `RulesEngine`'s pre-parsed dependencies.
  - Passes collected region data to `RulesEngine.evaluate_rules()`. The `RulesEngine` then handles dispatching actions to `ActionExecutor` or `GeminiDecisionModule`.
- **`ui.cli` Module:**
  - Provides the Command-Line Interface using `argparse` (per ADR-005).
  - Handles subcommands: `run <profile>`, `add-region <profile>`, and `edit [profile]`.
  - **(v4.0.0 Phase 3):** A direct CLI command for NLU tasks (e.g., `mark_i nlu-task "command" --profile <p>`) is a future consideration but not part of the initial Phase 3 GUI-driven implementation. NLU tasks are invoked via profiles.
- **`ui.gui.*` Modules (`MainAppWindow`, `DetailsPanel`, `RegionSelectorWindow`, `gui_config.py`, `gui_utils.py`):**
  - Provide the comprehensive GUI editor using `CustomTkinter`.
  - The GUI supports configuration of all features, including:
    - `gemini_vision_query` conditions.
    - `gemini_perform_task` actions, with parameters for `natural_language_command`, `context_region_names`, `allowed_actions_override`, `require_confirmation_per_step`, and `max_steps`.
  - _Details in Section 9 and 11._
- **`mark_i/__main__.py`:**
  - Application entry point. Initializes core components (Env Vars, Logging, Config) and dispatches CLI commands.

## 2. Key Libraries & Justifications (Summary from ADRs)

-   **Environment Management:** `python-dotenv` (ADR-007)
-   **Logging:** Python `logging` module (ADR-007)
-   **Screen Capture:** `Pillow` (`ImageGrab` for Windows), `OpenCV-Python` (for conversion and potential alternatives) (ADR-001).
-   **Image Processing & Analysis (Local):** `OpenCV-Python` (cv2), `NumPy`, `Pillow` (ADR-001).
-   **OCR (Local):** `pytesseract` (ADR-001).
-   **Remote Advanced Visual Analysis & Decision Support (v4.0.0+):** `google-generativeai` (Python SDK for Gemini) (ADR-008).
-   **Input Simulation:** `pyautogui` (ADR-002).
-   **Configuration Storage:** `json` (Python built-in) (ADR-003).
-   **CLI Framework:** `argparse` (Python built-in) (ADR-005).
-   **GUI Framework:** `CustomTkinter` (and its dependency `Pillow` for `CTkImage`) (ADR-005).
-   **Concurrency (Bot Runtime):** Python `threading` module (ADR-006).

## 3. Defining and Capturing Regions

-   Regions are defined in the JSON profile with `name, x, y, width, height`.
-   The GUI (`MainAppWindow` using `RegionSelectorWindow`) allows users to define/edit these graphically.
-   `CaptureEngine.capture_region(region_spec)` uses `Pillow.ImageGrab.grab(bbox=(x, y, x + width, y + height))` on Windows. The result (Pillow Image) is converted to an OpenCV BGR NumPy array.
-   This captured BGR image is then available for local analysis by `AnalysisEngine`, remote analysis by `GeminiAnalyzer` (for `gemini_vision_query` conditions), and as visual context for the `GeminiDecisionModule`'s NLU tasks.

## 4. "Reading" from the Region - Analysis Strategies

1.  **Local Selective Pre-emptive Analysis (by `MainController` via `AnalysisEngine`):**
    -   `RulesEngine.__init__` pre-parses rules, creating `_analysis_requirements_per_region` for **local** analysis types (OCR, dominant color, average color).
    -   `MainController` selectively calls `AnalysisEngine` methods based on these requirements for specified regions.
2.  **Local On-Demand Analysis (by `RulesEngine` via `AnalysisEngine`):**
    -   Conditions like `pixel_color` and `template_match_found` are evaluated directly by `RulesEngine._evaluate_single_condition_logic` using the `captured_image` from the data packet passed by `MainController`.
3.  **Remote On-Demand Analysis for Vision Queries (by `RulesEngine` via `GeminiAnalyzer` - v4.0.0 Phase 1+):**
    -   When a `gemini_vision_query` condition is evaluated by `RulesEngine._evaluate_single_condition_logic`, it calls `GeminiAnalyzer.query_vision_model()` with the relevant image and prompt.
4.  **Remote NLU Processing and Contextual Visual Analysis for Task Orchestration (by `GeminiDecisionModule` via `GeminiAnalyzer` - v4.0.0 Phase 3):**
    -   The `GeminiDecisionModule`, when executing an NLU task:
        *   First calls `GeminiAnalyzer` with a text-based prompt (and potentially an initial overview image) to parse the `natural_language_command` into a structured plan.
        *   Then, for each decomposed step in the plan, it may call `GeminiAnalyzer` again with specific visual context (images of relevant regions for that step) and prompts to:
            *   Suggest a primitive action (from `PREDEFINED_ALLOWED_SUB_ACTIONS`).
            *   Refine a `target_description` into precise bounding box coordinates.
            *   Evaluate a `CHECK_VISUAL_STATE` condition.

## 5. Rules Engine & Evaluation (`RulesEngine`)

### 5.1. Rule Structure in JSON Profiles

-   **Condition Object:**
    -   **Single Condition (Local Types):** `{"type": "local_condition_name", "param1": value1, ...}`. May include `"capture_as": "var_name"` and `"region": "override_region_name"`.
    -   **Compound Condition (Local Types):** `{"logical_operator": "AND" | "OR", "sub_conditions": [list_of_single_local_condition_objects]}`. Each sub-condition can also have its own `"region"`.
    -   **`gemini_vision_query` type (Single Condition Structure - v4.0.0 Phase 1+):**
        ```json
        {
          "type": "gemini_vision_query",
          "region": "optional_region_name_override",
          "prompt": "Describe this image. Is there a red button?",
          "expected_response_contains": "red button",
          "capture_as": "gemini_description",
          "model_name": "gemini-1.5-flash-latest" // Optional
        }
        ```
-   **Action Object:**
    *   Standard types: `click`, `type_text`, `press_key`, `log_message`.
    *   The `click` action supports `target_relation` values like `center_of_gemini_element` and `top_left_of_gemini_element`, requiring a `gemini_element_variable` parameter that references a variable holding bounding box data (captured via `gemini_vision_query`). (v4.0.0 Phase 1.5).
    *   **`gemini_perform_task` type (v4.0.0 Phase 2 & 3 - NLU Task Execution):**
        ```json
        {
          "type": "gemini_perform_task",
          "natural_language_command": "Find the 'File' menu, click it, then click 'Open'.",
          "context_region_names": ["main_app_area", "menu_bar_area"], // Optional, list of region names
          "allowed_actions_override": ["CLICK_DESCRIBED_ELEMENT"], // Optional, list of allowed sub-action types
          "require_confirmation_per_step": true, // Optional, boolean
          "max_steps": 5, // Optional, integer
          "pyautogui_pause_before": 0.2 // Standard action pause
        }
        ```
        *(Note: `goal_prompt` was the Phase 2 design name for the primary textual input; Phase 3 standardizes on `natural_language_command` for clarity. `RulesEngine` might handle both for backward compatibility if needed, but `gui_config.py` uses `natural_language_command` for new configurations.)*

### 5.2. `RulesEngine` Evaluation Logic

-   **`_parse_rule_analysis_dependencies()`:** Pre-parses rules at initialization to determine which **local** analyses (`ocr`, `dominant_color`, `average_color`) are required for each region, enabling `MainController` to perform them selectively once per cycle. `gemini_vision_query` and `gemini_perform_task` do not add to these *pre-emptive local* requirements as their Gemini calls are on-demand.
-   **`_evaluate_single_condition_logic(...)`:** Handles evaluation of individual condition specifications (local types and `gemini_vision_query`). For `gemini_vision_query`, it invokes `self.gemini_analyzer`.
-   **`_check_condition(...)`:** Handles single vs. compound condition logic, including short-circuiting for AND/OR.
-   **`evaluate_rules(...)`:**
    *   Iterates through all defined rules in the profile.
    *   For each rule, calls `_check_condition()` to evaluate its conditional part, managing `rule_variable_context`.
    *   If a rule's condition is met:
        *   Substitutes variables into the rule's action specification.
        *   **If action type is `gemini_perform_task`:**
            *   Extracts `natural_language_command` and other task parameters.
            *   Gathers current images for the specified `context_region_names` from `all_region_data`.
            *   Calls `self.gemini_decision_module.execute_nlu_task()` with these inputs. The `GeminiDecisionModule` then handles the entire NLU task lifecycle.
        *   **For other standard action types:**
            *   Constructs a `full_action_to_execute` spec including context.
            *   Calls `self.action_executor.execute_action()` directly to perform the action. (This implies `MainController` no longer queues actions from `RulesEngine` but `RulesEngine` executes them directly upon condition met).

### 5.3. Variable Handling (`RulesEngine`)

-   Rule-scoped variables are created during `evaluate_rules` for each rule via the `capture_as` parameter in conditions.
-   Supported capture types include OCR text, template match details (dictionary with `x,y,width,height,confidence`), and Gemini responses (text, full JSON object, or specific JSON-extracted value).
-   For Gemini captures (both `gemini_vision_query` and bounding boxes refined within `GeminiDecisionModule` steps), the captured variable is structured as `{"value": <actual_captured_data>, "_source_region_for_capture_": "region_name_of_query"}` to ensure relative coordinates from bounding boxes can be correctly translated to absolute screen coordinates by `ActionExecutor`.
-   The `_substitute_variables` method uses regex (`\{([\w_]+)((\.[\w_]+)*)\}`) to find and replace placeholders (e.g., `{my_var}`, `{my_var.value.box.0}`) in action parameter strings with their corresponding values from the `rule_variable_context`.

## 6. Data Flow Example for NLU Task (`gemini_perform_task` - Phase 3)

1.  **`MainController` Loop:**
    a.  Captures images for all monitored regions (e.g., `full_app_window`, `dialog_area`) into `all_region_data`.
    b.  Calls `RulesEngine.evaluate_rules(all_region_data)`.
2.  **`RulesEngine.evaluate_rules()`:**
    a.  A rule "AutomateLoginViaNLU" has its condition met.
    b.  Action spec is: `{"type": "gemini_perform_task", "natural_language_command": "Enter username 'dev' and password 'secret', then click login", "context_region_names": ["full_app_window"]}`.
    c.  `RulesEngine` calls `self.gemini_decision_module.execute_nlu_task("Enter username...", {"full_app_window": image_data}, task_params)`.
3.  **`GeminiDecisionModule.execute_nlu_task()`:**
    a.  **NLU Parse:** Sends "Enter username..." and the `full_app_window` image (as general context) to `GeminiAnalyzer` with an NLU parsing prompt.
    b.  Gemini (text/multimodal model) returns JSON like:
        ```json
        { "parsed_task": { "command_type": "SEQUENTIAL_INSTRUCTIONS", "steps": [
            {"step_number": 1, "instruction_details": {"intent_verb": "TYPE", "target_description": "the username field", "parameters": {"text_to_type": "dev"}}},
            {"step_number": 2, "instruction_details": {"intent_verb": "TYPE", "target_description": "the password field", "parameters": {"text_to_type": "secret"}}},
            {"step_number": 3, "instruction_details": {"intent_verb": "CLICK", "target_description": "the login button", "parameters": {}}}
        ]}}
        ```
    c.  **Loop through steps:**
        i.  **Step 1 (Type username):**
            *   `GeminiDecisionModule` takes "Type 'dev' in 'the username field'". `current_image` is `full_app_window` image.
            *   It maps "TYPE" to `TYPE_IN_DESCRIBED_FIELD`.
            *   Calls `_refine_target_description_to_bbox("the username field", current_image, "full_app_window", ...)`. `GeminiAnalyzer` (vision) returns `{"value": {"box": [x1,y1,w1,h1], "found": true}, "_source_region_for_capture_": "full_app_window"}`.
            *   If confirmation enabled, prompts user.
            *   Calls `ActionExecutor` to first click `[x1,y1,w1,h1]` center, then type "dev".
            *   (Future: re-capture screen for next step's context).
        ii. **Step 2 (Type password):** Similar flow for password field.
        iii. **Step 3 (Click login):** Similar flow for login button.
    d.  Returns overall task status (success/failure) to `RulesEngine`.
4.  `RulesEngine` logs result. Loop continues.

## 7. Logging System (per ADR-007)

-   Uses Python's built-in `logging`, configured by `core.logging_setup`. Root logger for Mark-I is `mark_i`.
-   Format includes timestamp, logger name, level, module:func:lineno, and message for files.
-   **v4.0.0+ Specifics:**
    -   `GeminiAnalyzer` logs API requests (prompt summary, model used), API responses (status, success/error, latency), and any errors.
    -   `RulesEngine` logs when it's invoking `GeminiAnalyzer` for `gemini_vision_query`, the prompt used, and the outcome. It also logs invocation of `GeminiDecisionModule`.
    -   `ActionExecutor` logs details when targeting Gemini-identified elements, including variable name, relative box, base region, and final absolute coordinates.
    -   **`GeminiDecisionModule` (Phase 3 NLU):** Logs received natural language command, NLU parsing prompts/responses, decomposed plan steps, sub-step visual refinement prompts/responses, user confirmations (if enabled), final actions sent to `ActionExecutor`, and overall task/step success/failure.

## 8. Error Handling

-   Extensive `try-except` blocks. User-facing errors via `messagebox` or stderr. Detailed exceptions logged.
-   **v4.0.0+ Specifics:**
    -   `GeminiAnalyzer` robustly handles API errors (authentication, rate limits, invalid requests, network issues, content blocking) and returns structured error info.
    -   `RulesEngine` gracefully handles failures from `GeminiAnalyzer` for `gemini_vision_query` conditions (evaluates to `False`).
    -   `ActionExecutor` gracefully handles malformed or missing bounding box data from Gemini variables for targeted clicks (action skipped, error logged).
    -   **`GeminiDecisionModule` (Phase 3 NLU):**
        *   Handles NLU parsing failures (e.g., Gemini returns non-JSON or unparseable plan). Task fails with error.
        *   Handles task decomposition failures (e.g., NLU step intent doesn't map to an allowed sub-action). Task fails.
        *   Handles sub-step target refinement failures (e.g., Gemini can't find the described element for a bounding box). Current sub-step fails, potentially halting the overall NLU task.
        *   Handles `ActionExecutor` errors during sub-step execution. Halts task.
        *   Uses `max_steps` to prevent infinite loops if task decomposition is flawed.

## 9. Full GUI Architecture (`MainAppWindow` using `CustomTkinter`)

### 9.1. Overall Structure
(Main window with Left Panel for settings/regions/templates, Center Panel for rules list, Right Panel (`DetailsPanel`) for editing selected item – as previously defined.)

### 9.2. File Operations (Menu)
(New, Open, Save, Save As – as previously defined.)

### 9.3. Core Data Model (`self.profile_data` in `MainAppWindow`)
(Mirrors the JSON profile structure. Changes in UI update this dictionary.)

### 9.4. Core Functionality Logic (`MainAppWindow` and `DetailsPanel`)

-   **Settings Panel:** Includes fields for `gemini_default_model_name` and read-only status of `GEMINI_API_KEY`.
-   **Rule Editor (`DetailsPanel`):**
    *   Dynamically renders parameters for selected condition types (including `gemini_vision_query`) and action types (including `gemini_perform_task`).
    *   For `gemini_vision_query`: `CTkTextbox` for `prompt`, entries for expectations, etc.
    *   For `gemini_perform_task` (Phase 3):
        *   `CTkTextbox` for `natural_language_command`.
        *   `CTkEntry` for `context_region_names` (expects CSV, parsed by `_get_parameters_from_ui`).
        *   `CTkEntry` for `allowed_actions_override` (expects CSV of valid `PREDEFINED_ALLOWED_SUB_ACTIONS` keys, parsed).
        *   `CTkCheckBox` for `require_confirmation_per_step`.
        *   `CTkEntry` for `max_steps`.
    *   Handles conditional visibility of parameters (e.g., `gemini_element_variable` for click actions).
-   Input validation via `gui_utils.validate_and_get_widget_value`.
-   `DetailsPanel._get_parameters_from_ui` parses CSV string inputs for `list_str_csv` types into Python lists.

### 9.5. Item Lists (Regions, Templates, Rules, Sub-Conditions)
(Managed via `_populate_specific_list_frame` and `_highlight_selected_list_item` – as previously defined.)

### 9.6. Dynamic Parameter Rendering (`DetailsPanel._render_dynamic_parameters`)
(Reads `UI_PARAM_CONFIG` to create widgets. Handles `condition_show` for dynamic visibility. Stores a list of currently rendered dynamic widgets (`self.param_widgets_and_defs_for_current_view`) to allow `_update_conditional_visibility` to function correctly when controller widgets change.)

### 9.7. Data Persistence (Saving/Loading)
(Handled by `MainAppWindow` calling `ConfigManager`.)

### 9.8. Component Refactoring (v3.0.x - Done)
(Refactoring of `MainAppWindow` and `DetailsPanel` into smaller components is complete.)

## 10. Gemini API Interaction (`GeminiAnalyzer` - v4.0.0 Phase 1+)

### 10.1. Class Structure and Initialization
-   `mark_i.engines.gemini_analyzer.GeminiAnalyzer`
-   `__init__(self, api_key: str, default_model_name: str)`: Configures `genai` client.

### 10.2. Core Method: `query_vision_model`
-   `query_vision_model(self, image_data: np.ndarray, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]`
-   Handles BGR to PIL Image conversion, constructs request, calls `genai.GenerativeModel().generate_content()`.
-   Parses response text, attempts JSON parsing, handles API errors, content blocking, and returns a structured dictionary: `{"status": ..., "text_content": ..., "json_content": ..., "error_message": ..., "model_used": ..., "latency_ms": ...}`.
-   Can be used for text-only NLU prompts by `GeminiDecisionModule` if `image_data` is minimal/None and the model endpoint supports it (e.g., "gemini-pro" for text, or multimodal models can also take text-only prompts).

### 10.3. Prompting for Bounding Boxes (v4.0.0 Phase 1.5+)
-   Used by `RulesEngine` (for `gemini_vision_query` `capture_as` a box) and `GeminiDecisionModule` (for refining `target_description` from NLU steps).
-   Strategy: Prompt Gemini to return JSON with `box: [x_rel, y_rel, width, height]` and `found: true/false` for a described element within a given image.
-   The `_source_region_for_capture_` key is added by the calling module (`RulesEngine` or `GeminiDecisionModule`) to the captured/refined data to ensure correct interpretation of relative box coordinates.

## 11. GUI Configuration for Gemini (v4.0.0+)

-   **`gui_config.py` (`UI_PARAM_CONFIG`):**
    *   Defines all parameters for `gemini_vision_query` condition.
    *   Defines parameters for `gemini_perform_task` action:
        *   `natural_language_command` (textbox, required).
        *   `context_region_names` (entry, `type: "list_str_csv"`).
        *   `allowed_actions_override` (entry, `type: "list_str_csv"`).
        *   `require_confirmation_per_step` (checkbox).
        *   `max_steps` (entry, int).
    *   `CLICK_TARGET_RELATIONS` includes `center_of_gemini_element`, `top_left_of_gemini_element`.
    *   `click` action has `gemini_element_variable` parameter with `condition_show` logic.
-   **`DetailsPanel._render_dynamic_parameters`:** Creates UI elements based on `UI_PARAM_CONFIG`.
-   **`DetailsPanel._get_parameters_from_ui`:** Retrieves and validates values, parsing `list_str_csv` input from `CTkEntry` into Python lists of strings.

## 12. `ActionExecutor` - Handling Actions

-   `_get_target_coords()`: Calculates click coordinates. Extended in Phase 1.5 to handle `gemini_element_variable` by parsing the wrapped bounding box data ( `{"value": {"box": [...]}, "_source_region_for_capture_": "..."}` ) and using `_source_region_for_capture_` to get the base screen coordinates of the region the Gemini query was performed on.
-   `execute_action()`: Takes a full action specification (including context with variables) and performs the PyAutoGUI simulation.
-   It is called by `RulesEngine` for standard rule actions and by `GeminiDecisionModule` for primitive sub-steps of NLU tasks.

## 13. Testing Strategy (v4.0.0 Overall)

-   **Manual Integration Testing (Primary for Gemini Features):**
    *   Test `gemini_vision_query` with diverse prompts and image conditions.
    *   Test actions on Gemini-identified bounding boxes: accuracy, error handling.
    *   Test `gemini_perform_task` (goal-driven single actions - Phase 2): various goals, visual contexts, validation of `PREDEFINED_ALLOWED_ACTIONS`.
    *   Test `gemini_perform_task` (NLU-driven multi-step tasks - Phase 3):
        *   Variety of natural language commands (simple, sequential, basic conditional).
        *   NLU parsing accuracy and task decomposition logic.
        *   Execution of multi-step plans, including target refinement for each step.
        *   State management (basic).
        *   Error handling at NLU, decomposition, and step execution stages.
        *   User confirmation flows (`require_confirmation_per_step`).
        *   `max_steps` enforcement.
    *   Verify GUI configuration for all Gemini-related features.
    *   Extensive log review for all Gemini interactions and decision processes.
-   **Automated Testing (Future Enhancement - `pytest`):**
    *   Unit tests for non-Gemini components.
    *   Mock `GeminiAnalyzer` to test `RulesEngine` (`gemini_vision_query`), `GeminiDecisionModule` (NLU parsing, step logic, refinement calls), and `ActionExecutor` (bounding box coordinate calculation) without actual API calls. Mock responses should cover success, failure, various JSON structures, and content blocking scenarios.

---
## 14. Gemini Decision Module & NLU Task Orchestration (v4.0.0 Phase 2 & 3 - Final)

This section details the architecture and operation of the `GeminiDecisionModule`.
For Phase 2, it handled single goal-to-action translations.
**For Phase 3 (and the final v4.0.0 state), it is enhanced into an NLU Task Orchestrator, responsible for understanding natural language commands, decomposing them into steps, and managing their execution.**

### 14.1. Overview and Purpose (Final v4.0.0)

*   **Goal:** To enable users to issue high-level commands in natural language (via the `gemini_perform_task` action's `natural_language_command` parameter). The `GeminiDecisionModule` parses these commands, decomposes them into a sequence of executable sub-steps, and orchestrates their execution. Each sub-step typically involves using Gemini for precise visual targeting and action selection from a predefined set of primitive capabilities.
*   **Operation:** It acts as an intermediary between a high-level natural language instruction and a sequence of concrete, low-level UI interactions performed by `ActionExecutor`. It leverages `GeminiAnalyzer` for NLU and for visual analysis/refinement during step execution.

### 14.2. Module Architecture and Components (Final v4.0.0)

*   **`mark_i.engines.gemini_decision_module.GeminiDecisionModule` Class:**
    *   **Core Responsibilities (Phase 3 Enhancements):**
        1.  **Natural Language Command Parsing (`execute_nlu_task` primary entry point):** Receives `natural_language_command` string. Calls `_construct_nlu_parse_prompt()` and uses `GeminiAnalyzer` to parse the command into a structured JSON plan (intents, steps, parameters).
        2.  **Task Decomposition & Planning:** Converts the structured NLU JSON output into an internal executable plan (e.g., a list of step dictionaries). Validates that decomposed step intents can map to `PREDEFINED_ALLOWED_SUB_ACTIONS`.
        3.  **Step Execution Orchestration (`execute_nlu_task` loop, calling `_execute_single_parsed_instruction`):** Iterates through the planned steps. For each step:
            *   Gathers/updates visual context from provided `context_images`.
            *   The `instruction_details` from the NLU plan (intent, target description, parameters) form the sub-goal for the current step.
            *   Calls `_map_nlu_intent_to_allowed_action()` to determine the primitive action type.
            *   If the primitive action requires visual target refinement (e.g., `CLICK_DESCRIBED_ELEMENT`), calls `_refine_target_description_to_bbox()` using `GeminiAnalyzer` to get precise coordinates.
            *   Handles `require_confirmation_per_step` by logging (actual GUI dialog is a UI concern if this module needs to signal).
            *   Constructs the final specification for `ActionExecutor` and invokes `self.action_executor.execute_action()`.
        4.  **State Management (Basic for v4.0.0):** Manages progression through the decomposed step list. Does not carry complex data payloads between steps beyond what's implicit in sequential execution on the same UI.
        5.  **Error Handling & Reporting:** Manages errors from NLU parsing, decomposition, Gemini API calls for sub-steps, target refinement, and action execution. Halts the NLU task on critical errors and returns a failure status.
*   **`PREDEFINED_ALLOWED_SUB_ACTIONS` Constant:** Defines primitive actions Gemini can be guided to use for decomposed steps (e.g., `CLICK_DESCRIBED_ELEMENT`, `TYPE_IN_DESCRIBED_FIELD`, `PRESS_KEY_SIMPLE`, `CHECK_VISUAL_STATE`). Each maps to an `ActionExecutor` type or internal logic.
*   **Internal Task Plan:** Generated from NLU, typically a list of step objects, each specifying an `intent_verb`, `target_description`, and `parameters`.

### 14.3. Data Flow and Interaction for NLU Task (Final v4.0.0)

*(The Mermaid diagram and textual flow description from the "Design for Phase 3" proposal accurately represent this section and are considered part of this final design.)*

**Simplified Flow:**
`Rule Trigger` -> `RulesEngine` (detects `gemini_perform_task`) -> `RulesEngine` calls `GeminiDecisionModule.execute_nlu_task(natural_language_command, initial_context_images, task_params)` ->
`GDM` uses `GeminiAnalyzer` (text prompt for NLU) -> `GDM` gets NLU JSON plan (sequence of steps) ->
`GDM` loops through steps:
  For each step:
    `GDM` forms sub-goal from step plan.
    If step involves visual target (e.g., "click 'button X'"):
      `GDM` uses `GeminiAnalyzer` (vision prompt with current screen image + sub-goal's `target_description`) to call `_refine_target_description_to_bbox()`.
      Gets `box` coordinates.
    `GDM` (optionally logs confirmation intent).
    `GDM` constructs final primitive action spec.
    `GDM` calls `ActionExecutor.execute_action()`.
    If step fails, GDM halts NLU task.
`GDM` returns overall task status to `RulesEngine`.

### 14.4. Prompt Engineering Strategies (Final v4.0.0)

#### 14.4.1. Prompts for NLU & Task Decomposition (`_construct_nlu_parse_prompt`)

*   **Strategy:** Provide Gemini with the raw natural language command and a detailed JSON schema it must adhere to for its output. The schema defines how to represent single actions, sequences, and basic conditionals (if supported), including intents, target descriptions, and parameters.
*   **Key elements of the prompt:**
    *   System role: "You are an NLU parser for a desktop automation tool..."
    *   User's raw command.
    *   Detailed instructions on the desired JSON output structure (`parsed_task` with `command_type`, `instruction_details` or `steps`, parameters for each step like `intent_verb`, `target_description`, `text_to_type`, `key_name`).
    *   Few-shot examples demonstrating command-to-JSON mapping.
*   **Model Choice:** A capable text model (e.g., Gemini Pro) or a multimodal model if initial screen context aids NLU. `GeminiAnalyzer` handles the call.

#### 14.4.2. Prompts for Per-Step Visual Target Refinement (`_refine_target_description_to_bbox`)

*   **Strategy:** Given a textual `target_description` for a UI element (derived from an NLU step) and an image of the relevant screen region, prompt Gemini Vision to locate this element and return its bounding box.
*   **Key elements of the prompt:**
    *   Role: "You are a precise visual element locator."
    *   Instruction: "Identify the element best described as: `'{target_description}'`. Respond ONLY with JSON: `{\"found\": true/false, \"box\": [x,y,w,h_or_null]}`."
    *   Few-shot examples of image descriptions and expected JSON output for `box`.

### 14.5. Safety, Control, and Limitations (Final v4.0.0)

*   **Restricted Sub-Action Space:** The NLU-decomposed steps are mapped to and executed as one of the `PREDEFINED_ALLOWED_SUB_ACTIONS`. This list is intentionally small and simple.
*   **Validation:** `GeminiDecisionModule` validates that NLU outputs and sub-step suggestions conform to expected structures and action types.
*   **`max_steps` Parameter:** Enforced for `gemini_perform_task` to prevent runaway NLU-driven sequences.
*   **`require_confirmation_per_step` Parameter:** Provides user oversight for each AI-decided sub-step in an NLU task. Default is `True` for safety.
*   **NLU Accuracy & Ambiguity:** The system's ability to correctly interpret and execute complex or ambiguous natural language commands is limited by Gemini's NLU capabilities and the robustness of the prompt engineering. Failures in NLU or decomposition will result in task failure. Advanced clarification dialogs are not part of v4.0.0.
*   **State Management:** Basic sequential step progression. No complex memory of past interactions or data passing between NLU task steps is explicitly designed in v4.0.0, beyond what Gemini might infer from sequential prompting for sub-steps (if implemented that way).
*   **Error Recovery:** Basic: halt overall NLU task on sub-step failure. No automated error recovery or re-planning by Gemini within a single `gemini_perform_task` invocation.

### 14.6. GUI Integration (Final v4.0.0)

*   The `gemini_perform_task` action type in the `DetailsPanel` is configured via `gui_config.py` to accept:
    *   `natural_language_command` (multi-line `CTkTextbox`).
    *   `context_region_names` (`CTkEntry` for CSV, parsed to list).
    *   `allowed_actions_override` (`CTkEntry` for CSV of `PREDEFINED_ALLOWED_SUB_ACTIONS` keys, parsed to list).
    *   `require_confirmation_per_step` (`CTkCheckBox`).
    *   `max_steps` (`CTkEntry` for integer).
*   Runtime feedback primarily relies on detailed logs. If `require_confirmation_per_step` is true, the current implementation relies on logging the intent to confirm, as direct GUI dialog invocation from `GeminiDecisionModule` is complex; a production system would need a callback or event mechanism to the GUI.

### 14.7. Invocation from `RulesEngine` (Final v4.0.0)

*   When a rule action `type: "gemini_perform_task"` is triggered, `RulesEngine` extracts its parameters.
*   It calls `self.gemini_decision_module.execute_nlu_task()` with the `natural_language_command`, relevant `initial_context_images` (gathered by `MainController` and passed to `RulesEngine`), and other task parameters (`max_steps`, `require_confirmation_per_step`, etc.).
*   The `GeminiDecisionModule` then manages the entire lifecycle of that NLU task.