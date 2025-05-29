# Functional Requirements for Mark-I

This document outlines the functional requirements for the Mark-I visual automation tool, describing *what* the system will do. **This version reflects the completed capabilities of v4.0.0, including Phase 1 (Core Gemini Vision Query), Phase 1.5 (Bounding Box Actions), Phase 2 (Gemini-Informed Decision Making), and Phase 3 (Natural Language Command Interface).**

## FR-CORE: Core System

*   **FR-CORE-001: Cross-Platform Operation:** The bot's core engine (capture, analysis, action) SHOULD operate on Windows, macOS, and Linux. The GUI (`CustomTkinter`) is also designed to be cross-platform. (Primary development and testing on Windows per `DEV_CONFIG.MD`).
*   **FR-CORE-002: Configuration Files (JSON):** The system MUST use JSON for saving and loading bot configurations (profiles). These profiles MUST store:
    *   General profile settings (e.g., description, monitoring interval, analysis parameters like `analysis_dominant_colors_k`, `gemini_default_model_name`).
    *   Definitions of screen regions to monitor (name, x, y, width, height).
    *   Definitions of template images (name, relative filename for images stored in a `templates/` subdirectory next to the profile JSON file).
    *   A list of rules, where each rule includes:
        *   A unique name.
        *   A default region for its conditions (can be empty if sub-conditions all specify their own, or if the condition type like `gemini_vision_query` specifies its own region).
        *   A condition block, which can be:
            *   A single condition with a `type` (e.g., "pixel_color", "ocr_contains_text", "gemini_vision_query") and specific parameters relevant to that type. This single condition can specify its own `region` to override the rule's default.
            *   A compound condition with a `logical_operator` ("AND" or "OR") and a list of `sub_conditions` (each sub-condition being a single condition structure, capable of specifying its own `region`).
        *   Parameters for capturing results into variables within conditions (e.g., `capture_as` field for `ocr_contains_text`, `template_match_found`, `gemini_vision_query`).
        *   An action block with a `type` (e.g., "click", "type_text", "gemini_perform_task") and specific parameters relevant to that type, which can use captured variables via placeholder substitution.
*   **FR-CORE-003: Environment Configuration:** The system MUST read environment variables (e.g., from a `.env` file via `python-dotenv`) to determine its operational environment (`APP_ENV`) and sensitive configurations like the `GEMINI_API_KEY`, primarily influencing logging configuration and external API access.
*   **FR-CORE-004: Logging:** The system MUST implement comprehensive and persistent logging for all significant operations, decisions, errors, and state changes in both the backend engine and the GUI editor. Log levels and destinations MUST be configurable based on `APP_ENV` and CLI flags, as detailed in `adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md`.
    *   **(v4.0.0):** Logging MUST include details of Gemini API interactions for `gemini_vision_query` (requests, responses, errors, latency).
    *   **(v4.0.0 Phase 2 & 3):** Logging MUST extend to cover the `GeminiDecisionModule`'s operations, including input goals/NLU commands, prompts to Gemini for action suggestions/NLU parsing, Gemini's raw suggestions/parsed plans, validation outcomes, refinement steps, decomposed task steps, and final executed actions or failure reasons.

## FR-CAPTURE: Screen Region Capture Module (Bot Runtime)

*   **FR-CAPTURE-001: Define Target Region:** The user MUST be able to define one or more named rectangular regions on the screen (x, y, width, height) to be monitored. This definition is stored in the profile and manageable via the GUI.
*   **FR-CAPTURE-002: Capture Specified Region:** The system MUST be able to capture image data exclusively from the defined target region(s) during bot runtime.
*   **FR-CAPTURE-003: Real-time Capture:** The system MUST support continuous real-time capture of defined regions at a user-configurable interval (FPS/delay) during bot operation.

## FR-ANALYZE: Region Analysis Module (Bot Runtime & Decision Support)

*   **FR-ANALYZE-001: Pixel Color Analysis:** The system MUST allow rules to check for specific pixel colors (BGR) at relative coordinates within a region, with a configurable tolerance.
*   **FR-ANALYZE-001B: Average Color Analysis:** The system MUST allow rules to check the average color (BGR) of a region against an expected color, with a configurable tolerance.
*   **FR-ANALYZE-002: Template Matching Analysis:** The system MUST allow rules to check if a user-provided template image is present within a region, with a configurable minimum confidence threshold. Match details (location, confidence, dimensions) can be captured into a variable.
*   **FR-ANALYZE-003: OCR Text Extraction & Analysis:** The system MUST be able to extract text from a region using Tesseract OCR. The analysis result MUST include both the extracted text string and an average word confidence score. The full extracted text can be captured into a variable.
*   **FR-ANALYZE-003B: OCR-Based Conditions:** Rules MUST support conditions based on OCR results, including:
    *   Checking if the extracted text contains specific substring(s) (case-sensitive or insensitive, comma-separated for OR logic on keywords).
    *   Checking if the average OCR confidence meets a minimum threshold (if specified).
*   **FR-ANALYZE-004: Configurable Analysis Rules:** Users MUST be able to define rules that link analysis outcomes to actions. Rules MUST support:
    *   Single conditions with various types and parameters.
    *   Compound conditions using "AND" or "OR" logical operators on a list of sub-conditions. Each sub-condition can target the rule's default region or specify its own.
*   **FR-ANALYZE-005: Dominant Color Analysis:** The system MUST allow rules to check if one of the top N dominant colors (found via k-means, with configurable 'k' for analysis) in a region matches an expected BGR color (with tolerance) and optionally meets a minimum percentage of occurrence.
*   **FR-ANALYZE-006: Selective Analysis (Performance):** The bot runtime (`MainController`) MUST optimize performance by only executing general pre-emptive **local** analyses (e.g., OCR, dominant color, average color) on a given region if at least one rule in the active profile explicitly requires that type of analysis for that region. Image capture for all monitored regions always occurs. Gemini analysis (for `gemini_vision_query` or by `GeminiDecisionModule`) is performed on-demand.
*   **FR-ANALYZE-007: Gemini Vision Query (v4.0.0 Phase 1+):** The system MUST provide a condition type (`gemini_vision_query`) that allows rules to:
    *   Send the captured image data of a specified region and a user-defined text prompt to the configured Google Gemini Vision API endpoint.
    *   Optionally specify a Gemini model name to override the profile's default model.
    *   Evaluate the condition based on the Gemini API's response (checking text content or JSON path values).
    *   Capture the Gemini API's response (text, full JSON object, or specific JSON-extracted value) into a rule-scoped variable structured as `{"value": <data>, "_source_region_for_capture_": "region_name"}`.
    *   Handle API errors gracefully.
*   **FR-ANALYZE-008: Gemini-Informed Action Suggestion (v4.0.0 Phase 2):** The `GeminiDecisionModule` MUST:
    *   Accept a user-defined goal/task description and visual context (images of relevant regions).
    *   Utilize `GeminiAnalyzer` to prompt Gemini to suggest a single, simple action from a predefined, limited set of allowed actions, based on the goal and visual context.
    *   Parse and validate Gemini's suggested action.
    *   If needed, use `GeminiAnalyzer` again to refine a textual target description from Gemini into precise bounding box coordinates.
*   **FR-ANALYZE-009: Natural Language Command Understanding & Decomposition (v4.0.0 Phase 3):** The `GeminiDecisionModule` MUST:
    *   Accept a user-provided natural language command (string).
    *   Utilize `GeminiAnalyzer` (with appropriate NLU-focused prompting) to parse this command into a structured representation (e.g., identifying main intent, sequence of sub-intents/steps, key entities, and parameters).
    *   Decompose the parsed command into an internal plan or sequence of executable sub-steps if the command is multi-step or conditional (basic conditionals).
    *   Validate that decomposed steps map to known, simple capabilities (ultimately relying on `PREDEFINED_ALLOWED_SUB_ACTIONS`).
    *   Manage basic state and context progression through the sequence of decomposed steps.

## FR-ACTION: Action Execution Module (Bot Runtime)

*   **FR-ACTION-001: Mouse Click Simulation:** The system MUST be able to simulate mouse clicks (left, right, middle, configurable number of clicks, interval between clicks) at:
    *   Absolute screen coordinates.
    *   The center of a specified region.
    *   Coordinates relative to a specified region's top-left corner.
    *   The center of the last successfully matched template.
    *   **(v4.0.0 Phase 1.5+)** Coordinates derived from bounding box data (captured from `gemini_vision_query` or refined by `GeminiDecisionModule`), using `gemini_element_variable` parameter.
*   **FR-ACTION-002: Keyboard Input Simulation:** The system MUST be able to simulate typing strings, pressing individual special keys, and hotkey combinations.
*   **FR-ACTION-003: Conditional Actions:** Actions (including `gemini_perform_task`) MUST only be triggered if their associated rule's condition evaluates to true.
*   **FR-ACTION-004: Log Message Action:** The system MUST provide an action to write a custom message to application logs.
*   **FR-ACTION-005: Dynamic Action Parameters (Variables):** Action parameters MUST be able to utilize values captured into rule-scoped variables.
*   **FR-ACTION-006: Configurable Pause Before Action:** Actions MUST allow a configurable pause before execution.
*   **FR-ACTION-007: Execute Gemini-Suggested/Decomposed Actions (v4.0.0 Phase 2+):** The `ActionExecutor` MUST be callable by the `GeminiDecisionModule` to perform primitive actions that are part of a Gemini-suggested plan or a decomposed step from an NLU command. The set of actions executable this way is limited by `GeminiDecisionModule.PREDEFINED_ALLOWED_SUB_ACTIONS`.
*   **FR-ACTION-008: User Confirmation for AI-Driven Actions (v4.0.0 Phase 2+):** The system (via `GeminiDecisionModule` and configured through `gemini_perform_task` parameters) MUST provide an option to require user confirmation (e.g., via a GUI dialog if applicable, or logged intent otherwise) before executing each action step suggested or derived by Gemini as part of a goal-driven or NLU task.
*   **FR-ACTION-009: `gemini_perform_task` Action Type (v4.0.0 Phase 2 & 3):** The system MUST support a rule action of type `gemini_perform_task`.
    *   This action triggers the `GeminiDecisionModule`.
    *   It MUST accept a `natural_language_command` (string) parameter as the primary input for NLU-driven tasks (Phase 3).
    *   It MAY accept a simpler `goal_prompt` (string) for single AI-decided actions (Phase 2 legacy, or if `natural_language_command` is empty).
    *   It MUST accept `context_region_names` (list of strings), `allowed_actions_override` (list of strings), `require_confirmation_per_step` (boolean), and `max_steps` (integer) as parameters to control the behavior of the `GeminiDecisionModule`.

## FR-CONFIG: Configuration & Management (CLI & GUI)

*   **FR-CONFIG-001: Save/Load Bot Profile:** Users MUST be able to save/load complete bot setups (profiles) as JSON files.
*   **FR-CONFIG-002: Variable Capture in Rules:** Conditions (`ocr_contains_text`, `template_match_found`, `gemini_vision_query`) MUST support capturing results into rule-scoped variables structured as `{"value": <data>, "_source_region_for_capture_": "region_name"}`.
*   **FR-CONFIG-003: Gemini Settings Management (v4.0.0 Phase 1+):**
    *   System loads `GEMINI_API_KEY` from `.env`.
    *   Users can configure a default Gemini model name in profile settings.
*   **FR-CONFIG-004: Gemini NLU Task Definition in Profile (v4.0.0 Phase 3):** Users MUST be able to define tasks to be driven by natural language commands within their profiles, using the `gemini_perform_task` action type and its associated parameters (`natural_language_command`, `context_region_names`, `allowed_actions_override`, `require_confirmation_per_step`, `max_steps`).

## FR-UI: User Interface

*   **FR-UI-001: CLI Control:** The system MUST provide CLI controls for running profiles (`run`), launching the GUI editor (`edit`), and the legacy region adder (`add-region`).
*   **FR-UI-002: GUI for Region Definition (Component):** `RegionSelectorWindow` MUST allow visual selection/drawing of screen regions.
*   **FR-UI-003: Full GUI Profile Editor (`MainAppWindow` - v4.0.0 Complete):**
    *   **FR-UI-003.1: Profile File Operations:** Create new, open, save, save as for profiles. Manage dirty state.
    *   **FR-UI-003.2: Settings Editing:** Edit general profile settings, including `gemini_default_model_name`. Display Gemini API key status.
    *   **FR-UI-003.3: Region Management & Editing:** List, add (invoke `RegionSelectorWindow`), remove, edit regions.
    *   **FR-UI-003.4: Template Management & Editing:** List, add, remove templates, with image preview.
    *   **FR-UI-003.5: Rule Management & Editing (Comprehensive):**
        *   List, add, remove rules. Edit rule name and default region.
        *   **Condition Editing:** Select condition `type` (including `gemini_vision_query`), dynamically edit parameters, convert between single/compound.
        *   **Action Editing:** Select action `type` (including `click`, `type_text`, `press_key`, `log_message`, and **`gemini_perform_task`**). Dynamically display and allow editing of all relevant parameters for the selected type, including:
            *   Parameters for `gemini_element_variable` (for click actions targeting Gemini-identified elements).
            *   Parameters for `gemini_perform_task`, such as `natural_language_command` (using a `CTkTextbox`), `context_region_names` (as CSV string in `CTkEntry`), `allowed_actions_override` (as CSV string), `require_confirmation_per_step` (`CTkCheckBox`), and `max_steps` (`CTkEntry`).
        *   Parameter fields SHOULD allow variable placeholders.
    *   **FR-UI-003.6: Input Validation & Feedback:** GUI MUST validate inputs and provide clear error messages.
*   **FR-UI-004: User Feedback (General - v4.0.0 Complete):**
    *   System MUST provide clear feedback on operations, successes, warnings, errors.
    *   **(v4.0.0):** Includes feedback on Gemini API interactions for `gemini_vision_query` and `gemini_perform_task`. If NLU task confirmation is enabled, GUI should present confirmation dialogs (actual dialog implementation might be basic for v4.0.0, relying on logs for detailed step-by-step if GUI interaction is complex).