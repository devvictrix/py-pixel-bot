# Technical Design Document: Mark-I

This document outlines the technical design and architectural considerations for the Mark-I visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status.
Version 4.0.0 (Gemini-Powered Visual Intelligence), including all its sub-phases (Phase 1: Core Vision Query, Phase 1.5: Bounding Box Actions, Phase 2: Gemini-Informed Decision Making, and Phase 3: Natural Language Command Interface), is functionally complete.
This document now incorporates the detailed design for v5.0.0, focusing on AI-Driven Profile Generation as per ADR-009, including Phase 2 GUI Workflow and AI-Assisted Element Suggestion details.
**This document has been updated for v5.0.2 to detail the Unit Testing strategy.**

## 1. Core Architecture

The tool is modular, comprising several key Python components, all residing within the main `mark_i` package:

- **`core.config_manager` Module:**
  - `load_environment_variables()`: Loads `.env` (for `APP_ENV`, `GEMINI_API_KEY`).
  - `ConfigManager` class: Manages loading, validation, access, and saving of JSON bot profiles. Handles path resolution for profiles and templates.
- **`core.logging_setup` Module:**
  - `setup_logging()`: Initializes Python's `logging` system based on `APP_ENV` and CLI flags. Root logger: `mark_i`.
- **`engines.capture_engine.CaptureEngine` Class:**
  - Captures screen regions (uses `Pillow.ImageGrab` on Windows). Converts to OpenCV BGR NumPy arrays.
- **`engines.analysis_engine.AnalysisEngine` Class:**
  - Performs local visual analyses (pixel color, average color, template matching, OCR, dominant colors) on BGR NumPy arrays.
- **`engines.gemini_analyzer.GeminiAnalyzer` Class (v4.0.0+):**
  - Handles all direct communication with Google Gemini APIs (both vision and text models as needed).
  - Manages API key, request formation (image/text prompts), response parsing (text/JSON), error handling, and detailed logging of API interactions.
  - Used by `RulesEngine` (for `gemini_vision_query` via `GeminiVisionQueryEvaluator`), `GeminiDecisionModule` (for NLU and step-specific visual queries), and **`StrategyPlanner` / `ProfileGenerator` (for v5.0.0 AI Profile Generation)**.
  - _Method `query_vision_model` refactored in v5.0.1 for improved modularity._
  - _Details in Section 10._
- **`engines.rules_engine.RulesEngine` Class:**
  - Evaluates rules defined in profiles based on analysis results.
  - Supports single conditions, compound conditions (AND/OR logic per ADR-004), and rule-scoped variable capture and substitution.
  - _Condition evaluation refactored in v5.0.1 to use the Strategy pattern with `ConditionEvaluator` classes in `condition_evaluators.py`._
  - For actions of type `gemini_perform_task`, it invokes the `GeminiDecisionModule` to handle NLU commands and goal-oriented task execution.
  - _Details in Section 5._
- **`engines.action_executor.ActionExecutor` Class:**
  - Simulates mouse and keyboard actions using `pyautogui`.
  - Calculates target coordinates, including for Gemini-identified bounding boxes (v4.0.0 Phase 1.5).
  - Called by `RulesEngine` for standard actions and by `GeminiDecisionModule` for executing primitive steps of an NLU-driven task.
- **`engines.gemini_decision_module.GeminiDecisionModule` Class (v4.0.0 Phase 2 & 3):**
  - NLU Task Orchestrator: Parses natural language user commands (received via the `gemini_perform_task` action's `natural_language_command` parameter).
  - Decomposes commands into a sequence of manageable steps/sub-goals using Gemini for NLU.
  - For each decomposed step, uses its `GeminiAnalyzer` instance for visual analysis and action refinement (e.g., finding specific elements, getting bounding boxes for described targets).
  - Manages basic state across steps of a single NLU task.
  - Orchestrates execution of these steps by calling `ActionExecutor` (via `PrimitiveSubActionExecutor` strategies since v5.0.1 refactor).
  - Implements safety measures like using a predefined set of allowed sub-actions and optional user confirmation per step.
  - _Method `_execute_primitive_sub_action` refactored in v5.0.1 to use Strategy pattern with `PrimitiveSubActionExecutor` classes._
  - _Method `execute_nlu_task` and its helper `_recursive_execute_plan_node` refactored in v5.0.1 for improved clarity by decomposing into node-specific handlers._
  - _Details extensively in Section 14._
- **`engines.condition_evaluators.py` Module (NEW - v5.0.1):**
  - Contains `ConditionEvaluator` (ABC) and concrete subclasses for each condition type (e.g., `PixelColorEvaluator`, `TemplateMatchEvaluator`, `GeminiVisionQueryEvaluator`). These implement the Strategy pattern for condition evaluation, called by `RulesEngine`.
- **`engines.primitive_executors.py` Module (NEW - v5.0.1):**
  - Contains `PrimitiveSubActionExecutorBase` (ABC) and concrete subclasses for primitive NLU sub-actions (e.g., `ClickDescribedElementExecutor`). Used by `GeminiDecisionModule`.
- **`generation.strategy_planner.StrategyPlanner` Module (NEW - v5.0.0):**
  - **Package:** `mark_i.generation.strategy_planner`
  - **Responsibility:** Takes a high-level user goal for automation. Uses `GeminiAnalyzer` to interact with a powerful Gemini model to break this goal down into an "intermediate plan." This plan is a sequence of logical, human-understandable sub-steps or sub-goals, structured typically as JSON.
  - _Detailed in Section 15.2.1._
- **`generation.profile_generator.ProfileGenerator` Module (NEW - v5.0.0):**
  - **Package:** `mark_i.generation.profile_generator`
  - **Responsibility:** Takes the "intermediate plan" from `StrategyPlanner`. Iterates through plan steps, managing an interactive workflow with the user (via `ProfileCreationWizardWindow`). For each step, it uses `GeminiAnalyzer` for visual suggestions (e.g., relevant regions, candidate UI elements) and logic suggestions (conditions, actions). User confirms/refines. Assembles profile. Handles staging and saving of new template images.
  - _Detailed in Section 15.2.2._
- **`main_controller.MainController` Class:**
  - Orchestrates the main bot loop for rule-based profile execution.
  - Instantiates all core engine components.
- **`ui.cli` Module:**
  - Provides CLI using `argparse`.
- **`ui.gui.main_app_window.MainAppWindow` Class:**
  - Main GUI for profile editing using `CustomTkinter`.
  - _Methods `_populate_ui_from_profile_data` and `_update_profile_data_from_ui` refactored in v5.0.1 for improved modularity._
- **`ui.gui.panels.details_panel.DetailsPanel` Class:**
  - Sub-component of `MainAppWindow` for displaying and editing details of selected profile items (regions, templates, rules).
  - _Methods `_render_dynamic_parameters` and `get_all_rule_data_from_ui` (and its helpers) refactored in v5.0.1 for improved modularity._
- **`ui.gui.panels.condition_editor_component.ConditionEditorComponent` Class (NEW - v3.0.x refactor):**
  - Sub-component of `DetailsPanel` specifically for editing rule conditions (single or compound).
- **`ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow` Class (NEW - v5.0.0 Phase 2):**
  - **Package:** `mark_i.ui.gui.generation`
  - **Responsibility:** A top-level `ctk.CTkToplevel` window that orchestrates the user-facing workflow for AI-driven profile generation. Interacts with `StrategyPlanner` and `ProfileGenerator`.
  - _GUI Workflow concepts detailed in Section 15.4._
- **`ui.gui.generation.sub_image_selector_window.SubImageSelectorWindow` Class (NEW - v5.0.0 Phase 2):**
  - **Package:** `mark_i.ui.gui.generation`
  - **Responsibility:** A helper Toplevel window that displays a provided PIL Image and allows the user to draw a rectangle to select a sub-area, returning its coordinates. Used for template capture within the `ProfileCreationWizardWindow`.
- **Other `ui.gui.*` Modules:** `RegionSelectorWindow`, `gui_config.py`, `gui_utils.py` support manual profile editing and provide shared utilities/configs.
- **`mark_i/__main__.py`:** Application entry point.

## 2. Key Libraries & Justifications (Summary from ADRs)

- **Environment Management:** `python-dotenv` (ADR-007)
- **Logging:** Python `logging` module (ADR-007)
- **Screen Capture:** `Pillow` (`ImageGrab` for Windows), `OpenCV-Python` (for conversion) (ADR-001).
- **Image Processing & Analysis (Local):** `OpenCV-Python` (cv2), `NumPy`, `Pillow` (ADR-001).
- **OCR (Local):** `pytesseract` (ADR-001).
- **Remote Advanced Visual Analysis, NLU, Decision Support, Plan Generation (v4.0.0+):** `google-generativeai` (Python SDK for Gemini) (ADR-008).
- **Input Simulation:** `pyautogui` (ADR-002).
- **Configuration Storage:** `json` (Python built-in) (ADR-003).
- **CLI Framework:** `argparse` (Python built-in) (ADR-005).
- **GUI Framework:** `CustomTkinter` (and its dependency `Pillow` for `CTkImage`) (ADR-005).
- **Concurrency (Bot Runtime):** Python `threading` module (ADR-006).
- **Unit Testing:** `pytest` (with `pytest-cov` for coverage) - **v5.0.2 Implementation IN PROGRESS**.

## 3. Defining and Capturing Regions

- Regions are defined as `{"name": str, "x": int, "y": int, "width": int, "height": int, "comment": Optional[str]}`.
- Manual definition via `RegionSelectorWindow` (full screen overlay).
- **v5.0.0 AI Profile Generation:** `ProfileCreationWizardWindow` will feature:
  - AI suggestion of regions based on plan steps and full screen context (via `ProfileGenerator` calling `GeminiAnalyzer`).
  - User confirmation/adjustment using an integrated region drawing tool operating on a displayed screenshot, or by invoking `RegionSelectorWindow` for full-screen context if needed.

## 4. "Reading" from the Region - Analysis Strategies

1.  **Local Selective Pre-emptive Analysis (Runtime - `MainController` via `AnalysisEngine`):** OCR, dominant color, average color if required by active rules.
2.  **Local On-Demand Analysis (Runtime - `RulesEngine` via `AnalysisEngine` and `ConditionEvaluator` strategies):** Pixel color, template matching (template loading still managed by `RulesEngine` but actual matching by `AnalysisEngine` via evaluator).
3.  **Remote On-Demand Visual Query (Runtime - `RulesEngine` via `GeminiVisionQueryEvaluator` which uses `GeminiAnalyzer`):** `gemini_vision_query` conditions.
4.  **Remote NLU & Contextual Visual Analysis for Task Orchestration (Runtime - `GeminiDecisionModule` via `GeminiAnalyzer` and `PrimitiveSubActionExecutor` strategies):** For `gemini_perform_task` actions.
5.  **Remote Analysis for Profile Generation (v5.0.0 - `StrategyPlanner` & `ProfileGenerator` via `GeminiAnalyzer`):**
    - `StrategyPlanner`: Goal-to-plan translation (text/multimodal).
    - `ProfileGenerator`: Suggests regions, condition/action logic, and refines element locations based on plan steps and visual context.

## 5. Rules Engine & Evaluation (`RulesEngine`)

### 5.1. Rule Structure in JSON Profiles (Final v4.0.0 / Target for v5.0.0 AI Generation)

- **Condition Object:**
  - Single: `{"type": "condition_name", ...params..., "region": "opt_override", "capture_as": "opt_var"}`.
  - Compound: `{"logical_operator": "AND"|"OR", "sub_conditions": [list_of_single_conditions]}`.
  - `gemini_vision_query` parameters: `prompt`, `expected_response_contains`, `case_sensitive_response_check`, `expected_response_json_path`, `expected_json_value`, `model_name`.
- **Action Object:**
  - Standard types: `click`, `type_text`, `press_key`, `log_message`.
  - `click` params include `target_relation`, `target_region`, `x`, `y`, `gemini_element_variable`, `button`, `clicks`, `interval`, `pyautogui_pause_before`.
  - `gemini_perform_task` (v4.0.0 NLU Runtime & v5.0.0 Generated Task Target) params: `natural_language_command`, `context_region_names` (list), `allowed_actions_override` (list), `require_confirmation_per_step` (bool), `max_steps` (int), `pyautogui_pause_before`.

### 5.2. `RulesEngine` Evaluation Logic (Runtime)

   - The `_evaluate_single_condition_logic` method has been refactored (v5.0.1) to use the Strategy pattern. It now dispatches to the appropriate `ConditionEvaluator` instance from `self._condition_evaluators` based on the condition `type`. Concrete condition evaluator classes are in `mark_i.engines.condition_evaluators.py`.
   - `_parse_rule_analysis_dependencies()`: Determines pre-emptive local analysis needs (unchanged).
   - `_check_condition()`: Handles single vs. compound logic, calling `_evaluate_single_condition_logic` for each individual condition.
   - `evaluate_rules()`: Iterates rules. If condition met:
     - Substitutes variables in action spec.
     - If `gemini_perform_task`: Calls `GeminiDecisionModule.execute_nlu_task()`.
     - Else: Calls `ActionExecutor.execute_action()` directly.

### 5.3. Variable Handling (`RulesEngine` - Runtime)

_(As finalized for v4.0.0. Captured variables (including from Gemini via evaluators) are structured as `{"value": <data>, "_source_region_for_capture_": "region_name"}` for bounding box consistency.)_

## 6. Data Flow Examples

_(Section 14.3 details NLU Task Runtime Data Flow. Section 15.3 details AI Profile Generation Data Flow.)_

## 7. Logging System (per ADR-007)

- Root logger: `mark_i`. Configured by `core.logging_setup`.
- **v4.0.0+:** Detailed logging for `GeminiAnalyzer`, `GeminiDecisionModule` (NLU, step execution), `RulesEngine` (AI condition/action invocation), `ActionExecutor` (Gemini targets).
- **v5.0.0:** Critical logging for `StrategyPlanner` (goal, plan generation, AI interactions) and `ProfileGenerator` (plan step processing, AI suggestions, user interactions, generated elements).
- **v5.0.1 Refactoring:** Logging within refactored methods (`RulesEngine`, `GeminiAnalyzer`, `GeminiDecisionModule`, GUI components) has been reviewed and maintained/improved for clarity during decomposition.

## 8. Error Handling

- Extensive `try-except` blocks. User feedback via GUI/CLI, detailed logs.
- **v4.0.0+ (Runtime):** Robust handling of Gemini API errors, NLU failures, unsafe suggestions.
- **v5.0.0 (Profile Generation):**
  - `StrategyPlanner`: Handles failures in goal-to-plan translation (e.g., API error, unparseable plan from Gemini).
  - `ProfileGenerator`: Handles failures in AI suggestions for regions/logic, allows user manual override or skipping steps. Ensures generated profile is structurally valid.
- **v5.0.1 Refactoring:** Error handling in refactored methods has been reviewed to ensure it remains robust and clear.

## 9. Full GUI Architecture (`MainAppWindow` using `CustomTkinter`)

_(Existing v4.0.0 GUI architecture for manual profile editing remains. Key methods in `MainAppWindow` and `DetailsPanel` were refactored in v5.0.1 for modularity.)_

### 9.x. (NEW - v5.0.0): GUI for AI-Driven Profile Generation (`ProfileCreationWizardWindow`)

- Managed by `mark_i.ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow`.
- Launched from `MainAppWindow` (e.g., "File > New AI-Generated Profile...").
- Wizard-style, multi-page/view interface.
- Interacts with `StrategyPlanner` and `ProfileGenerator` backend modules.
- _Detailed workflow in Section 15.4._

## 10. Gemini API Interaction (`GeminiAnalyzer` - v4.0.0+)

_(Class structure, `__init__` as finalized for v4.0.0. Method `query_vision_model` was refactored in v5.0.1 into private helpers: `_validate_and_prepare_api_input`, `_execute_sdk_call`, `_process_sdk_response` for improved clarity and maintainability. This module serves all other components needing direct Gemini API access.)_

### 10.3. Prompting for Bounding Boxes (v4.0.0 Phase 1.5+)

_(Standardized strategy for prompting Gemini Vision to return JSON with `box: [x,y,w,h]` and `found: true/false`. Used by `GeminiVisionQueryEvaluator` (for `capture_as` in `gemini_vision_query`), by `GeminiDecisionModule` (for runtime target refinement via `PrimitiveSubActionExecutor` strategies), and by `ProfileGenerator` (v5.0.0) for suggesting element locations.)_

## 11. GUI Configuration for Gemini (Runtime Features - v4.0.0+)

- **`gui_config.py` (`UI_PARAM_CONFIG`):** Defines GUI elements for:
  - `gemini_vision_query` condition parameters.
  - `gemini_perform_task` action parameters (including `natural_language_command`, `context_region_names`, etc.).
  - `click` action's `gemini_element_variable` and related `target_relation` values.
- `DetailsPanel` uses this config to render editors dynamically.
- **(v5.0.0):** The AI Profile Generation Wizard has its own dedicated UI logic, not directly driven by this `UI_PARAM_CONFIG` meant for manual rule editing.

## 12. `ActionExecutor` - Handling Actions

_(As finalized for v4.0.0. It executes primitive actions based on specs from `RulesEngine` or `GeminiDecisionModule`'s primitive executors.)_

## 13. Testing Strategy

The project employs a multi-layered testing approach to ensure quality and stability.

### 13.1. Manual End-to-End (E2E) Testing
-   **Description:** Comprehensive manual testing of all user-facing features and workflows, simulating real user scenarios. This includes:
    -   CLI command execution (`run`, `edit`, legacy `add-region`).
    -   Full GUI Profile Editor (`MainAppWindow`) functionality: creating, editing, saving, loading profiles with all condition/action types, including Gemini-powered features.
    -   AI-Driven Profile Generation (`ProfileCreationWizardWindow`): complete workflow from goal input to profile saving and execution of AI-generated profiles.
-   **Focus:** Validating overall system behavior, usability, integration of components, and correctness of automation outcomes.
-   **Responsibility:** Primarily DevLead.
-   **Timing:** Performed for major releases (e.g., v5.0.3 planned) and significant feature additions.

### 13.2. Unit Testing (`pytest`) - (v5.0.2 Implementation - IN PROGRESS)
-   **Framework:** `pytest` (Python testing framework). `pytest-cov` will be used for measuring test coverage.
-   **Goal:** To test individual units of code (functions, methods, classes) in isolation to verify their correctness, ensure they behave as expected under various conditions, and catch regressions early.
-   **Test File Location and Naming:**
    -   Unit tests will reside in a top-level `tests/` directory.
    -   The structure within `tests/` will mirror the `mark_i/` package structure. For example, tests for `mark_i/core/config_manager.py` will be in `tests/core/test_config_manager.py`.
    -   Test files will be named `test_*.py` and test functions/methods will be named `test_*()`.
-   **Scope (Initial Focus for v5.0.2):**
    -   **Core Logic & Utilities:**
        -   `mark_i.core.config_manager.ConfigManager`: Methods for profile path resolution (`_resolve_profile_path`), loading and saving (mocking file I/O), default structure initialization. **(Initial tests added for init and path resolution)**.
        -   `mark_i.ui.gui.gui_utils`: Utility functions like `parse_bgr_string`. **(Next target)**.
    -   **Refactored Engine Components:**
        -   `mark_i.engines.condition_evaluators`: Each concrete `ConditionEvaluator` subclass, mocking their dependencies (`AnalysisEngine`, `GeminiAnalyzer`).
        -   `mark_i.engines.primitive_executors`: Each concrete `PrimitiveSubActionExecutorBase` subclass, mocking dependencies.
    -   **Business Logic within Engines (Non-API/UI parts):**
        -   `mark_i.engines.analysis_engine`: Logic within analysis methods that can be tested without direct CV/OCR calls (e.g., parameter validation, result structuring).
        -   `mark_i.engines.rules_engine`: Logic for variable substitution (`_substitute_variables`), compound condition evaluation structure (mocking individual condition results).
        -   `mark_i.engines.gemini_analyzer`: Internal logic for prompt construction, JSON parsing from (mocked) API responses, not the API call itself.
        -   `mark_i.engines.gemini_decision_module`: NLU plan parsing, mapping intents to primitive actions (mocking `GeminiAnalyzer` responses).
-   **Mocking Strategy:**
    -   External dependencies **MUST** be mocked to ensure tests are isolated, fast, and deterministic.
    -   **Libraries to Mock:** `google-generativeai` (for `GeminiAnalyzer`), `pyautogui`, `Pillow.ImageGrab`, `cv2` (for image I/O and complex operations if not testing the operation itself), `pytesseract`, `dotenv`.
    -   **Tools:** Python's built-in `unittest.mock.patch` (and its variants like `patch.object`, `patch.dict`) or the `pytest-mock` plugin (which provides the `mocker` fixture) will be used.
    -   **Focus:** Mock at the boundary of the unit under test. For example, when testing a `ConditionEvaluator`, mock the methods of `AnalysisEngine` it calls, not the internal workings of `AnalysisEngine` itself.
-   **Test Coverage:**
    -   Aim for good coverage of critical business logic, complex functions, and areas prone to regressions.
    -   `pytest-cov` will be used to generate coverage reports. While 100% coverage is not always practical or necessary, key modules should have high coverage.
-   **Running Tests:**
    -   Tests will be run using the `pytest` command from the project root directory.
    -   The environment should be set up (e.g., virtual environment activated) so `pytest` can discover the `mark_i` package.
-   **Benefits:** Early bug detection, safer refactoring, documentation via tests, improved code design (testable code is often better designed).
-   **Integration with CI/CD (Future):** Unit tests will form the basis of automated testing in any future CI/CD pipeline.

### 13.x. (NEW - v5.0.0): Testing AI-Driven Profile Generation

- **Unit/Integration for Backend:** Mock `GeminiAnalyzer` for `StrategyPlanner` (test plan parsing) and `ProfileGenerator` (test suggestion parsing and profile data assembly).
- **End-to-End (Manual with Real API):** Test full workflow from user goal input -> plan generation -> interactive element definition -> final profile saving. Evaluate quality and usability of generated profiles. (This is part of the broader E2E testing for v5.0.3).
- **GUI Testing:** Test the `ProfileCreationWizardWindow` for usability, correct data flow with backend, and graceful error handling.

---

## 14. Gemini Decision Module & NLU Task Orchestration (v4.0.0 Phase 2 & 3 - Final, with v5.0.1 Refactoring Notes)

_(This section describes the runtime NLU capabilities. The method `_execute_primitive_sub_action` was refactored in v5.0.1 to use the Strategy pattern via `PrimitiveSubActionExecutor` classes in `primitive_executors.py`. The `execute_nlu_task` and its recursive helper `_recursive_execute_plan_node` were also refactored in v5.0.1 for clarity by decomposing into node-specific handlers like `_handle_single_instruction_node`, `_handle_sequential_instructions_node`, and `_handle_conditional_instruction_node`.)_

### 14.1. Overview and Purpose (Final v4.0.0)

- Enables runtime execution of NLU commands and simple goal-driven tasks via `gemini_perform_task` action.
- `GeminiDecisionModule` uses `GeminiAnalyzer` for NLU, step-action suggestion, and visual target refinement.

### 14.2. Module Architecture and Components (Reflects v5.0.1 Refactor)

- `mark_i.engines.gemini_decision_module.GeminiDecisionModule` Class.
- `PREDEFINED_ALLOWED_SUB_ACTIONS` constant maps NLU intent hint to `executor_class` in `primitive_executors.py`.
- Internal methods:
  - `_initialize_primitive_executors()`: Creates instances of `PrimitiveSubActionExecutor` strategies.
  - `_construct_nlu_parse_prompt()`.
  - `_map_nlu_intent_to_allowed_sub_action()`: Maps NLU intent string to a key in `PREDEFINED_ALLOWED_SUB_ACTIONS`.
  - `_refine_target_description_to_bbox()`: Helper for visual target refinement (passed to executors).
  - `_execute_primitive_sub_action()`: Now delegates to the appropriate `PrimitiveSubActionExecutor` strategy.
  - `execute_nlu_task()`: Main orchestrator for NLU tasks.
  - `_recursive_execute_plan_node()`: Recursive helper for `execute_nlu_task`, now dispatches to:
    - `_handle_single_instruction_node()`
    - `_handle_sequential_instructions_node()`
    - `_handle_conditional_instruction_node()`

### 14.3. Data Flow and Interaction for NLU Task (Final v4.0.0, execution uses strategies post-v5.0.1)

- `Rule Trigger` -> `RulesEngine` (`gemini_perform_task`) -> `GeminiDecisionModule.execute_nlu_task()` -> Loop: [NLU Parse (Gemini) -> Decompose Plan (`_recursive_execute_plan_node` dispatcher) -> For each Step/Node Type: (Call appropriate handler -> `_execute_primitive_sub_action` strategy -> Visual Context -> Sub-Goal -> Gemini Suggests Primitive Action (if needed by strategy) -> Refine Target (Gemini Vision, if needed by strategy) -> Optional User Confirm -> ActionExecutor Executes Primitive)].

### 14.4. Prompt Engineering Strategies (Final v4.0.0)

- **NLU & Task Decomposition Prompts:** Detailed schema-driven prompts for `_construct_nlu_parse_prompt`.
- **Per-Step Action Suggestion & Refinement Prompts (now within Primitive Executors or GDM._refine_target...):** Prompts for visual state checks, target refinement (e.g., `_refine_target_description_to_bbox`).

### 14.5. Safety, Control, and Limitations (Final v4.0.0)

- Adherence to `PREDEFINED_ALLOWED_SUB_ACTIONS` (keys mapped to executor strategies).
- `max_steps` and `require_confirmation_per_step` parameters for `gemini_perform_task`.
- NLU accuracy limitations. Basic error handling.

### 14.6. GUI Integration (Final v4.0.0)

- `gemini_perform_task` action configurable in `DetailsPanel` with `natural_language_command` textbox and other parameters.

### 14.7. Invocation from `RulesEngine` (Final v4.0.0)

- `RulesEngine` calls `GeminiDecisionModule.execute_nlu_task()` for `gemini_perform_task` actions.

---

## 15. AI-Driven Profile Generation (v5.0.0 - `StrategyPlanner`, `ProfileGenerator`, & GUI Wizard)

This system, introduced in v5.0.0 (ADR-009), assists users in creating Mark-I profiles from high-level natural language goals through an interactive, AI-assisted workflow.

### 15.1. Overview and Purpose (v5.0.0)

- **Goal:** User states a high-level automation goal. Mark-I uses AI to generate an intermediate plan, then interactively guides the user (with AI suggestions for regions, logic, and visual elements) to build a Mark-I JSON profile.
- **Output:** A standard, runnable Mark-I `.json` profile.

### 15.2. Core Components for Profile Generation (v5.0.0)

#### 15.2.1. `generation.strategy_planner.StrategyPlanner` Class

- **Input:** User goal (NL string), optional initial visual context (full screenshot/app window image).
- **Process:** Uses `GeminiAnalyzer` (e.g., Gemini 1.5 Pro) with a specialized prompt (`_construct_goal_to_plan_prompt`) to break the goal into an "intermediate plan" (JSON list of `IntermediatePlanStep` objects).
- **Output:** `IntermediatePlan` (e.g., `[{"step_id": 1, "description": "Locate username field.", "suggested_element_type_hint": "input_field", ...}, ...]`).
- **Method:** `generate_intermediate_plan(...)`.

#### 15.2.2. `generation.profile_generator.ProfileGenerator` Class

- **Input:** `IntermediatePlan` from `StrategyPlanner`, access to `GeminiAnalyzer`, and interaction with `ProfileCreationWizardWindow` (GUI).
- **State:** Manages `generated_profile_data` (the profile draft), `current_plan_step_index`, `current_full_visual_context_np` (updated by GUI).
- **Key AI-Assist Methods:** `suggest_region_for_step`, `suggest_logic_for_step`, `refine_element_location`.
- **Profile Assembly Methods:** `add_region_definition`, `add_template_definition`, `add_rule_definition`.
- **`save_generated_profile(filepath)`:** Saves JSON profile and associated template images.

### 15.3. Data Flow for AI Profile Generation Workflow (v5.0.0)

1.  **User (GUI - `ProfileCreationWizardWindow`):** Inputs natural language goal and optional initial screenshot.
2.  **`ProfileCreationWizardWindow` -> `StrategyPlanner.generate_intermediate_plan()`:** Passes goal and screenshot.
3.  **`StrategyPlanner` -> `GeminiAnalyzer.query_vision_model()`:** Sends composed prompt (goal + screenshot) to Gemini for planning.
4.  **`GeminiAnalyzer` -> Gemini API:** API call.
5.  **Gemini API -> `GeminiAnalyzer`:** Returns JSON plan.
6.  **`GeminiAnalyzer` -> `StrategyPlanner`:** Returns parsed plan.
7.  **`StrategyPlanner` -> `ProfileCreationWizardWindow`:** Returns `IntermediatePlan`.
8.  **`ProfileCreationWizardWindow` (Loop per plan step):**
    a.  Displays current plan step description to user.
    b.  **User Action (e.g., "AI Suggest Region" or manual definition):**
        i.  **(AI Suggest): `ProfileCreationWizardWindow` -> `ProfileGenerator.suggest_region_for_step()`** (passes current step and full context image).
        ii. `ProfileGenerator` -> `GeminiAnalyzer.query_vision_model()` (prompts Gemini with step + full image for region box).
        iii. Gemini -> `GeminiAnalyzer` -> `ProfileGenerator` -> `ProfileCreationWizardWindow` (returns suggested region box `[x,y,w,h]`).
    c.  User confirms/adjusts/draws region via GUI. `ProfileCreationWizardWindow` crops this confirmed region's image (`focused_region_image_np`).
    d.  **User Action (e.g., "AI Suggest Logic" or manual definition):**
        i.  **(AI Suggest): `ProfileCreationWizardWindow` -> `ProfileGenerator.suggest_logic_for_step()`** (passes step, `focused_region_image_np`, and confirmed region name).
        ii. `ProfileGenerator` -> `GeminiAnalyzer.query_vision_model()` (prompts Gemini with step + focused region image for Mark-I condition/action JSON).
        iii. Gemini -> `GeminiAnalyzer` -> `ProfileGenerator` -> `ProfileCreationWizardWindow` (returns suggested condition/action JSON and `element_to_refine_description`).
    e.  GUI displays suggested logic. If `element_to_refine_description` exists:
        i.  **User Action (e.g., "AI Find Element" or manual target selection/template capture):**
            1.  **(AI Find): `ProfileCreationWizardWindow` -> `ProfileGenerator.refine_element_location()`** (passes `element_to_refine_description`, `focused_region_image_np`).
            2.  `ProfileGenerator` -> `GeminiAnalyzer.query_vision_model()` (prompts Gemini with desc + focused image for candidate bounding boxes).
            3.  Gemini -> `GeminiAnalyzer` -> `ProfileGenerator` -> `ProfileCreationWizardWindow` (returns list of candidate boxes).
        ii. User selects a candidate box or captures a template via `SubImageSelectorWindow`.
    f.  User confirms/edits all parameters for the step's rule.
    g.  `ProfileCreationWizardWindow` calls `ProfileGenerator.add_rule_definition()` (and `add_region_definition`, `add_template_definition` as needed) to update the draft profile.
9.  **User (GUI - `ProfileCreationWizardWindow`):** Reviews final generated profile summary.
10. **`ProfileCreationWizardWindow` -> `ProfileGenerator.save_generated_profile()`:** Saves the complete JSON profile and any new template images.

### 15.4. GUI Workflow for AI Profile Generation (`ProfileCreationWizardWindow` - v5.0.0 Phase 2)

A modal `ctk.CTkToplevel` window (`mark_i.ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow`) guides the user.

- **Page 1: Goal Input & Initial Context:**
  - `CTkTextbox` for user's natural language goal.
  - Buttons to "Capture Full Screen," "Load Image from File" for initial context. `CTkLabel` to preview.
  - "Generate Automation Plan" button -> calls `StrategyPlanner` (threaded, displays loading state).
- **Page 2: Plan Review (Optional but Recommended):**
  - Displays `IntermediatePlan` from `StrategyPlanner`. "Start Building Profile" button.
- **Page 3 (Looping): Interactive Step Definition - Part A: Define Region:**
  - Displays current `plan_step.description`. Displays full context image.
  - "AI Suggest Region" button -> calls `ProfileGenerator.suggest_region_for_step()` (threaded). Overlays suggested box.
  - "Draw/Adjust Manually" button -> invokes `RegionSelectorWindow`.
  - `CTkEntry` for region name. "Confirm Region & Define Logic >" button.
- **Page 4 (Looping): Interactive Step Definition - Part B: Define Logic:**
  - Displays step description, confirmed region name, and cropped region image (interactive for element selection).
  - **Left Panel (Visual):** Region image. Entry for element description. "AI Find Element" button (calls `ProfileGenerator.refine_element_location()`, threaded, overlays candidates). "Use Template Instead" button (launches `SubImageSelectorWindow`).
  - **Right Panel (Logic):** Dynamically rendered editors for condition and action.
    - On page load or if user requests, calls `ProfileGenerator.suggest_logic_for_step()` (threaded).
    - Populates editors with AI's suggested Mark-I condition/action JSON.
  - User refines logic, selects refined element, or captures template.
  - "Confirm Logic & Next Step >" / "Finish & Review Profile >" button.
- **Page 5: Final Profile Review & Save:**
  - JSON preview of `ProfileGenerator.get_generated_profile_data()`.
  - `CTkEntry` for profile filename. "Save Profile & Close" button.

### 15.5. Prompt Engineering for Profile Generation (v5.0.0 Detailed)

- **`StrategyPlanner._construct_goal_to_plan_prompt()`:** Prompts for JSON output with "intermediate_plan" array, each step having "step_id", "description", "suggested_element_type_hint", "required_user_input_for_step". Emphasizes atomic, sequential steps.
- **`ProfileGenerator.suggest_region_for_step()` Prompt Core:** "Given plan step '{description}' and full screen image, identify the single most relevant rectangular region. Respond JSON: `{\"box\": [x,y,w,h], \"reasoning\": \"...\", \"suggested_region_name_hint\": \"...\"}`."
- **`ProfileGenerator.suggest_logic_for_step()` Prompt Core:** "For plan step '{description}' in region '{region_name}' (image provided), suggest Mark-I 'condition' and 'action' JSON. If interaction needed, action must include 'target_description'. If template needed, use 'USER_NEEDS_TO_CAPTURE_TEMPLATE_FOR_{element_name_hint}}'. Use placeholders for user data. Respond JSON: `{\"suggested_condition\": {...}, \"suggested_action\": {...}, \"element_to_refine_description\": \"...\", \"reasoning\": \"...\"}`."
- **`ProfileGenerator.refine_element_location()` Prompt Core:** "In image of region '{region_name}', find elements matching \"{element_description}\". Respond JSON: `{\"elements\": [{\"found\": true/false, \"box\": [x,y,w,h], \"label_suggestion\":\"...\", \"confidence_score\": ...}]}`."

### 15.6. Error Handling and User Feedback during Generation (v5.0.0)

- `ProfileCreationWizardWindow` clearly displays errors from `StrategyPlanner` or `ProfileGenerator` (e.g., "AI could not generate plan...").
- Provides "Retry" options for AI suggestion steps where feasible, or paths for manual override.
- Loading indicators/messages during long Gemini calls (handled via `threading` and GUI callbacks).

---