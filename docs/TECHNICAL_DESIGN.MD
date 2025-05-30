# Technical Design Document: Mark-I

This document outlines the technical design and architectural considerations for the Mark-I visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status.
Version 4.0.0 (Gemini-Powered Visual Intelligence), including all its sub-phases (Phase 1: Core Vision Query, Phase 1.5: Bounding Box Actions, Phase 2: Gemini-Informed Decision Making, and Phase 3: Natural Language Command Interface), is functionally complete.
**This document now incorporates the detailed design for v5.0.0, focusing on AI-Driven Profile Generation as per ADR-009, including Phase 2 GUI Workflow and AI-Assisted Element Suggestion details. It also includes considerations for the upcoming Unit Testing initiative (v5.0.2).**

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
  - Used by `RulesEngine` (for `gemini_vision_query`), `GeminiDecisionModule` (for NLU and step-specific visual queries), and **`StrategyPlanner` / `ProfileGenerator` (for v5.0.0 AI Profile Generation)**.
  - _Details in Section 10._
- **`engines.rules_engine.RulesEngine` Class:**
  - Evaluates rules defined in profiles based on analysis results.
  - Supports single conditions, compound conditions (AND/OR logic per ADR-004), and rule-scoped variable capture and substitution.
  - Handles `gemini_vision_query` conditions by invoking its internal `GeminiAnalyzer`.
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
  - Orchestrates execution of these steps by calling `ActionExecutor`.
  - Implements safety measures like using a predefined set of allowed sub-actions and optional user confirmation per step.
  - _Details extensively in Section 14._
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
  - **(v5.0.0 Consideration):** The AI Profile Generation workflow is managed by `ProfileCreationWizardWindow` which instantiates its own `StrategyPlanner` and `ProfileGenerator`. `MainController`'s role is primarily for runtime execution of profiles (manual or AI-generated).
- **`ui.cli` Module:**
  - Provides CLI using `argparse`.
  - **(v5.0.0 Consideration):** A CLI command `mark_i ai-create-profile` could be added to trigger a non-GUI version of profile generation if desired in the future, but current v5.0.0 focuses on GUI-driven generation.
- **`ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow` Class (NEW - v5.0.0 Phase 2):**
  - **Package:** `mark_i.ui.gui.generation`
  - **Responsibility:** A top-level `ctk.CTkToplevel` window that orchestrates the user-facing workflow for AI-driven profile generation. Interacts with `StrategyPlanner` and `ProfileGenerator`.
  - _GUI Workflow concepts detailed in Section 15.4._
- **`ui.gui.generation.sub_image_selector_window.SubImageSelectorWindow` Class (NEW - v5.0.0 Phase 2):**
  - **Package:** `mark_i.ui.gui.generation`
  - **Responsibility:** A helper Toplevel window that displays a provided PIL Image and allows the user to draw a rectangle to select a sub-area, returning its coordinates. Used for template capture within the `ProfileCreationWizardWindow`.
- **Other `ui.gui.*` Modules:** `MainAppWindow`, `DetailsPanel`, `RegionSelectorWindow` (for manual full-screen region def), `gui_config.py`, `gui_utils.py` support manual profile editing and provide shared utilities/configs.
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
- **Unit Testing:** `pytest` (and `pytest-cov` for coverage) - to be implemented in v5.0.2.

## 3. Defining and Capturing Regions

- Regions are defined as `{"name": str, "x": int, "y": int, "width": int, "height": int, "comment": Optional[str]}`.
- Manual definition via `RegionSelectorWindow` (full screen overlay).
- **v5.0.0 AI Profile Generation:** `ProfileCreationWizardWindow` will feature:
  - AI suggestion of regions based on plan steps and full screen context (via `ProfileGenerator` calling `GeminiAnalyzer`).
  - User confirmation/adjustment using an integrated region drawing tool operating on a displayed screenshot, or by invoking `RegionSelectorWindow` for full-screen context if needed.

## 4. "Reading" from the Region - Analysis Strategies

1.  **Local Selective Pre-emptive Analysis (Runtime - `MainController` via `AnalysisEngine`):** OCR, dominant color, average color if required by active rules.
2.  **Local On-Demand Analysis (Runtime - `RulesEngine` via `AnalysisEngine`):** Pixel color, template matching.
3.  **Remote On-Demand Visual Query (Runtime - `RulesEngine` via `GeminiAnalyzer`):** `gemini_vision_query` conditions.
4.  **Remote NLU & Contextual Visual Analysis for Task Orchestration (Runtime - `GeminiDecisionModule` via `GeminiAnalyzer`):** For `gemini_perform_task` actions.
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

_(As finalized for v4.0.0. This engine executes profiles, whether manually or AI-generated.)_

- `_parse_rule_analysis_dependencies()`: Determines pre-emptive local analysis needs.
- `_evaluate_single_condition_logic()`: Evaluates individual conditions (local & `gemini_vision_query`).
- `_check_condition()`: Handles single vs. compound logic.
- `evaluate_rules()`: Iterates rules. If condition met:
  - Substitutes variables in action spec.
  - If `gemini_perform_task`: Calls `GeminiDecisionModule.execute_nlu_task()`.
  - Else: Calls `ActionExecutor.execute_action()` directly.

### 5.3. Variable Handling (`RulesEngine` - Runtime)

_(As finalized for v4.0.0. Captured variables (including from Gemini) are structured as `{"value": <data>, "_source_region_for_capture_": "region_name"}` for bounding box consistency.)_

## 6. Data Flow Examples

_(Section 14.3 details NLU Task Runtime Data Flow. Section 15.3 details AI Profile Generation Data Flow.)_

## 7. Logging System (per ADR-007)

- Root logger: `mark_i`. Configured by `core.logging_setup`.
- **v4.0.0+:** Detailed logging for `GeminiAnalyzer`, `GeminiDecisionModule` (NLU, step execution), `RulesEngine` (AI condition/action invocation), `ActionExecutor` (Gemini targets).
- **v5.0.0:** Critical logging for `StrategyPlanner` (goal, plan generation, AI interactions) and `ProfileGenerator` (plan step processing, AI suggestions, user interactions, generated elements).

## 8. Error Handling

- Extensive `try-except` blocks. User feedback via GUI/CLI, detailed logs.
- **v4.0.0+ (Runtime):** Robust handling of Gemini API errors, NLU failures, unsafe suggestions.
- **v5.0.0 (Profile Generation):**
  - `StrategyPlanner`: Handles failures in goal-to-plan translation (e.g., API error, unparseable plan from Gemini).
  - `ProfileGenerator`: Handles failures in AI suggestions for regions/logic, allows user manual override or skipping steps. Ensures generated profile is structurally valid.

## 9. Full GUI Architecture (`MainAppWindow` using `CustomTkinter`)

_(Existing v4.0.0 GUI architecture for manual profile editing remains.)_

### 9.x. (NEW - v5.0.0): GUI for AI-Driven Profile Generation (`ProfileCreationWizardWindow`)

- Managed by `mark_i.ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow`.
- Launched from `MainAppWindow` (e.g., "File > New AI-Generated Profile...").
- Wizard-style, multi-page/view interface.
- Interacts with `StrategyPlanner` and `ProfileGenerator` backend modules.
- _Detailed workflow in Section 15.4._

## 10. Gemini API Interaction (`GeminiAnalyzer` - v4.0.0+)

_(Class structure, `__init__`, `query_vision_model` method, error handling, and response structure as finalized for v4.0.0. This module serves all other components needing direct Gemini API access.)_

### 10.3. Prompting for Bounding Boxes (v4.0.0 Phase 1.5+)

_(Standardized strategy for prompting Gemini Vision to return JSON with `box: [x,y,w,h]` and `found: true/false`. Used by `RulesEngine` for `capture_as` in `gemini_vision_query`, by `GeminiDecisionModule` for runtime target refinement, and will be used by `ProfileGenerator` (v5.0.0) for suggesting element locations during profile creation.)_

## 11. GUI Configuration for Gemini (Runtime Features - v4.0.0+)

- **`gui_config.py` (`UI_PARAM_CONFIG`):** Defines GUI elements for:
  - `gemini_vision_query` condition parameters.
  - `gemini_perform_task` action parameters (including `natural_language_command`, `context_region_names`, etc.).
  - `click` action's `gemini_element_variable` and related `target_relation` values.
- `DetailsPanel` uses this config to render editors dynamically.
- **(v5.0.0):** The AI Profile Generation Wizard will have its own dedicated UI logic, not directly driven by this `UI_PARAM_CONFIG` meant for manual rule editing.

## 12. `ActionExecutor` - Handling Actions

_(As finalized for v4.0.0. It executes primitive actions based on specs from `RulesEngine` or `GeminiDecisionModule`.)_

## 13. Testing Strategy

The project employs a multi-layered testing approach to ensure quality and stability.

### 13.1. Manual End-to-End (E2E) Testing
-   **Description:** Comprehensive manual testing of all user-facing features and workflows, simulating real user scenarios. This includes:
    -   CLI command execution (`run`, `edit`, legacy `add-region`).
    -   Full GUI Profile Editor (`MainAppWindow`) functionality: creating, editing, saving, loading profiles with all condition/action types, including Gemini-powered features.
    -   AI-Driven Profile Generation (`ProfileCreationWizardWindow`): complete workflow from goal input to profile saving and execution of generated profiles.
-   **Focus:** Validating overall system behavior, usability, integration of components, and correctness of automation outcomes.
-   **Responsibility:** Primarily DevLead.
-   **Timing:** Performed for major releases (e.g., v5.0.3) and significant feature additions.

### 13.2. Unit Testing (`pytest`) - (v5.0.2 Initiative)
-   **Framework:** `pytest` (with `pytest-cov` for coverage reporting).
-   **Goal:** To test individual units of code (functions, methods, classes) in isolation to verify their correctness.
-   **Scope:**
    -   **Core Logic:** Functions within `ConfigManager` (profile parsing, path resolution), `AnalysisEngine` (specific analysis algorithms like pixel color, average color, template matching logic before OpenCV calls), `RulesEngine` (condition evaluation logic, variable substitution), `ActionExecutor` (coordinate calculation logic).
    -   **Utility Functions:** Any helper functions in modules like `gui_utils.py`.
    -   **AI Component Logic (Non-API parts):** Internal logic within `StrategyPlanner` (plan parsing/validation), `ProfileGenerator` (profile data assembly, AI suggestion parsing), `GeminiDecisionModule` (NLU plan parsing, sub-action mapping).
-   **Approach:**
    -   Tests will be placed in a `tests/` directory at the project root, mirroring the `mark_i/` package structure (e.g., `tests/core/test_config_manager.py`).
    -   **Mocking:** External dependencies (Gemini API calls via `GeminiAnalyzer`, `pyautogui` calls, `Pillow.ImageGrab`, `cv2` I/O, `pytesseract`) **MUST** be mocked using `unittest.mock.patch` or `pytest-mock` to ensure tests are fast, deterministic, and don't rely on external services or UI.
    -   Focus on testing different input paths, edge cases, and expected outputs.
    -   Aim for clear, concise, and readable test cases.
-   **Benefits:** Early bug detection, easier refactoring, improved code design (testable code is often better designed), documentation via tests.
-   **Integration with Refactoring:** Unit tests will be written for newly refactored code (v5.0.1) and for new code going forward.

### 13.x. (NEW - v5.0.0): Testing AI-Driven Profile Generation

- **Unit/Integration for Backend:** Mock `GeminiAnalyzer` for `StrategyPlanner` (test plan parsing) and `ProfileGenerator` (test suggestion parsing and profile data assembly).
- **End-to-End (Manual with Real API):** Test full workflow from user goal input -> plan generation -> interactive element definition -> final profile saving. Evaluate quality and usability of generated profiles. (This is part of the broader E2E testing for v5.0.3).
- **GUI Testing:** Test the `ProfileCreationWizardWindow` for usability, correct data flow with backend, and graceful error handling.

---

## 14. Gemini Decision Module & NLU Task Orchestration (v4.0.0 Phase 2 & 3 - Final)

_(This section describes the runtime NLU capabilities implemented in v4.0.0. It remains as previously finalized, detailing the `GeminiDecisionModule`'s role in parsing `natural_language_command`s from `gemini_perform_task` actions, decomposing them, and orchestrating step-by-step execution with AI-assisted visual refinement.)_

### 14.1. Overview and Purpose (Final v4.0.0)

- Enables runtime execution of NLU commands and simple goal-driven tasks via `gemini_perform_task` action.
- `GeminiDecisionModule` uses `GeminiAnalyzer` for NLU, step-action suggestion, and visual target refinement.

### 14.2. Module Architecture and Components (Final v4.0.0)

- `mark_i.engines.gemini_decision_module.GeminiDecisionModule` Class.
- `PREDEFINED_ALLOWED_SUB_ACTIONS` constant (e.g., `CLICK_DESCRIBED_ELEMENT`, `TYPE_IN_DESCRIBED_FIELD`, `PRESS_KEY_SIMPLE`, `CHECK_VISUAL_STATE`).
- Internal methods: `_construct_nlu_parse_prompt`, `_map_nlu_intent_to_allowed_sub_action`, `_refine_target_description_to_bbox`, `_execute_primitive_sub_action`, and the main orchestrator `execute_nlu_task` with its recursive helper.

### 14.3. Data Flow and Interaction for NLU Task (Final v4.0.0)

- `Rule Trigger` -> `RulesEngine` (`gemini_perform_task`) -> `GeminiDecisionModule.execute_nlu_task()` -> Loop: [NLU Parse (Gemini) -> Decompose Plan -> For each Step: (Visual Context -> Sub-Goal -> Gemini Suggests Primitive Action -> Refine Target (Gemini Vision) -> Optional User Confirm -> ActionExecutor Executes Primitive)].

### 14.4. Prompt Engineering Strategies (Final v4.0.0)

- **NLU & Task Decomposition Prompts:** Detailed schema-driven prompts for `_construct_nlu_parse_prompt`.
- **Per-Step Action Suggestion & Refinement Prompts:** Prompts for `_construct_sub_step_action_suggestion_prompt` (less used if NLU is direct) and `_refine_target_description_to_bbox`.

### 14.5. Safety, Control, and Limitations (Final v4.0.0)

- Adherence to `PREDEFINED_ALLOWED_SUB_ACTIONS`.
- `max_steps` and `require_confirmation_per_step` parameters for `gemini_perform_task`.
- NLU accuracy limitations. Basic error handling.

### 14.6. GUI Integration (Final v4.0.0)

- `gemini_perform_task` action configurable in `DetailsPanel` with `natural_language_command` textbox and other parameters.

### 14.7. Invocation from `RulesEngine` (Final v4.0.0)

- `RulesEngine` calls `GeminiDecisionModule.execute_nlu_task()` for `gemini_perform_task` actions.

---

## 15. AI-Driven Profile Generation (v5.0.0 - `StrategyPlanner`, `ProfileGenerator`, & GUI Wizard)

This system, introduced in v5.0.0 (ADR-009), assists users in creating Mark-I profiles from high-level natural language goals through an interactive, AI-assisted workflow. **This section details the design for Phase 2: GUI Workflow and AI-Assisted Element Suggestion logic.**

### 15.1. Overview and Purpose (v5.0.0)

- **Goal:** User states a high-level automation goal. Mark-I uses AI to generate an intermediate plan, then interactively guides the user (with AI suggestions for regions, logic, and visual elements) to build a Mark-I JSON profile.
- **Output:** A standard, runnable Mark-I `.json` profile.

### 15.2. Core Components for Profile Generation (v5.0.0)

#### 15.2.1. `generation.strategy_planner.StrategyPlanner` Class

- **Input:** User goal (NL string), optional initial visual context (full screenshot/app window image).
- **Process:** Uses `GeminiAnalyzer` (e.g., Gemini 1.5 Pro) with a specialized prompt (`_construct_goal_to_plan_prompt`) to break the goal into an "intermediate plan" (JSON list of `IntermediatePlanStep` objects).
- **Output:** `IntermediatePlan` (e.g., `[{"step_id": 1, "description": "Locate username field.", "suggested_element_type_hint": "input_field", ...}, ...]`).
- **Method:** `generate_intermediate_plan(...)`.

#### 15.2.2. `generation.profile_generator.ProfileGenerator` Class (with Phase 2 AI Assist Logic)

- **Input:** `IntermediatePlan` from `StrategyPlanner`, access to `GeminiAnalyzer`, and interaction with `ProfileCreationWizardWindow` (GUI).
- **State:** Manages `generated_profile_data` (the profile draft), `current_plan_step_index`, `current_full_visual_context_np` (updated by GUI).
- **Key AI-Assist Methods (called by GUI Wizard for current step):**
  - **`set_current_visual_context(screen_capture_np)`:** GUI provides current screenshot.
  - **`suggest_region_for_step(plan_step)` -> `Optional[{"box": [x,y,w,h], "reasoning": ..., "name_hint": ...}]`:**
    - Prompts Gemini (e.g., Flash model) with `plan_step.description` and `current_full_visual_context_np` to suggest a relevant bounding box on the full context image for the current step. (See Section 15.5.1 for prompt design).
  - **`suggest_logic_for_step(plan_step, focused_region_image_np, focused_region_name)` -> `Optional[{"condition": {...}, "action": {...}, "refine_desc": "...", "reasoning": "..."}]`:**
    - Prompts Gemini (e.g., Pro model) with `plan_step.description` and the image of the _user-confirmed region for this step_.
    - Asks for Mark-I condition and action JSON objects, including `target_description` in actions if an element needs refinement. (See Section 15.5.2).
  - **`refine_element_location(element_description, focused_region_image_np, region_name)` -> `Optional[List[{"box": [x,y,w,h], ...}]]`:**
    - Prompts Gemini (e.g., Flash model) with `element_description` and the focused region image to find candidate bounding boxes for that element. (See Section 15.5.3).
- **Profile Assembly Methods:** `add_region_definition`, `add_template_definition` (now taking `_image_data_np_for_save`), `add_rule_definition`.
- **`save_generated_profile(filepath)` (Enhanced):**
  - Saves the main profile JSON using `self.config_manager`.
  - **Crucially, iterates through `self.generated_profile_data["templates"]`. If a template entry has `_image_data_np_for_save`, it saves this NumPy array as an image file (e.g., PNG using `cv2.imwrite`) into the `templates/` subdirectory relative to the `filepath` of the main profile. The `_image_data_np_for_save` key is then removed before saving the JSON.** Ensures unique template filenames within the profile's context.

### 15.3. Data Flow for AI Profile Generation Workflow (v5.0.0)

_(Mermaid diagram and detailed textual flow from ADR-009 and previous design iteration, emphasizing the loop through plan steps and the calls to `ProfileGenerator`'s AI-assist methods from the GUI wizard, are applicable here.)_

### 15.4. GUI Workflow for AI Profile Generation (`ProfileCreationWizardWindow` - v5.0.0 Phase 2)

A new modal `ctk.CTkToplevel` window (`mark_i.ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow`) guides the user.

- **Page 1: Goal Input & Initial Context:**
  - `CTkTextbox` for user's natural language goal.
  - Buttons to "Capture Full Screen," "Load Image from File" for initial context. `CTkLabel` to preview context image thumbnail.
  - "Generate Automation Plan" button -> calls `StrategyPlanner`. Displays loading state.
- **Page 2: Plan Review (Optional but Recommended):**
  - Displays the `IntermediatePlan` (list of step descriptions, hints) from `StrategyPlanner`.
  - (Future: options to edit/reorder plan). "Start Building Profile" button.
- **Page 3 (Looping): Interactive Step Definition - Part A: Define Region (`_setup_page_step_define_region`)**
  - Displays current `plan_step.description`.
  - Displays `current_full_context_pil` (full screenshot/window) in a `CTkLabel` (`self.region_step_context_display_label`).
  - **"AI Suggest Region" button:** Calls `ProfileGenerator.suggest_region_for_step()`. If successful, overlays suggested box (e.g., orange) on the full context display. Pre-fills region name entry with AI hint.
  - **"Draw/Adjust Manually" button:** Invokes `RegionSelectorWindow` (passing `current_full_context_pil`) for user to draw/adjust. Returns `{"name", "x", "y", "width", "height"}` relative to the full context image.
  - `CTkEntry` for user to confirm/edit region name.
  - **"Confirm Region & Define Logic >" button (wizard's "Next"):** Calls `_confirm_and_add_current_step_region()`, which validates name, adds region to `ProfileGenerator`'s draft, crops the region image (`current_step_region_image_np` & `_pil_for_display`) from `current_full_context_np`, and advances wizard to `PAGE_STEP_DEFINE_LOGIC`.
- **Page 4 (Looping): Interactive Step Definition - Part B: Define Logic (`_setup_page_step_define_logic`)**
  - Displays current `plan_step.description` and confirmed `current_step_region_name`.
  - **Left Panel (Visual Interaction):**
    - Displays `current_step_region_image_pil_for_display` (the cropped image of the confirmed region for this step) in `self.step_logic_region_image_label`. This label is bound for clicks.
    - `CTkEntry` (`self.element_refine_entry`) for user to type/confirm element description for AI refinement.
    - `CTkButton` ("AI Find Element" - `self.btn_refine_element`): Calls `_handle_ai_refine_element()`.
    - `CTkButton` ("Use Template Instead" - `self.btn_capture_template_for_step`): Calls `_handle_capture_template_for_step()`.
  - **Right Panel (Logic Configuration - `self.params_panel_scrollable`):**
    - Contains `self.step_logic_condition_frame` and `self.step_logic_action_frame`.
    - When page loads, `_trigger_ai_logic_suggestion_for_step()` is called:
      - Calls `ProfileGenerator.suggest_logic_for_step()` using `current_step_region_image_np`.
      - AI returns `{"suggested_condition": ..., "suggested_action": ..., "element_to_refine_description": ...}`.
      - `_render_step_logic_editors()` populates condition/action UI fields with these suggestions using `_render_dynamic_params_in_wizard_subframe`.
      - If `element_to_refine_description` is returned, it's pre-filled into `self.element_refine_entry`, and `btn_refine_element`/`btn_capture_template_for_step` are enabled.
  - **Element Refinement Interaction (`_handle_ai_refine_element`):**
    - Calls `ProfileGenerator.refine_element_location()`.
    - `_display_current_step_region_image_with_candidates()` overlays returned bounding box candidates on the region image.
    - `_on_region_image_click_for_element_selection()`: User clicks a candidate box.
    - `_update_action_params_with_selected_element()`: Updates the action UI (sets type to 'click', relation to 'center_of_gemini_element', sets `gemini_element_variable` to a temporary name like `_ai_gen_stepX_elem`). Stores confirmed element data (box, source region) in `self.confirmed_element_for_action`.
  - **Template Capture Interaction (`_handle_capture_template_for_step`):**
    - Prompts for template name. Launches `SubImageSelectorWindow` with `current_step_region_image_pil_for_display`.
    - User draws template box on region image. `SubImageSelectorWindow` returns relative coords.
    - Crops template from `current_step_region_image_np`.
    - Calls `ProfileGenerator.add_template_definition()` (passing NP image data via `_image_data_np_for_save`).
    - Updates condition UI to `template_match_found` and action UI to `click` `center_of_last_match`.
  - **"Confirm Logic & Next Step >" / "Finish & Review Profile >" button (wizard's "Next"):**
    - Calls `_get_current_step_logic_from_ui()` to retrieve and validate all condition/action parameters from the UI.
      - This method now handles the `self.confirmed_element_for_action` data: if a click action was set to use the temporary Gemini element variable, it converts the stored refined bounding box (relative to region image) into **absolute screen coordinates** and modifies the action spec to be an "absolute" click. This simplifies the generated rule.
    - Calls `ProfileGenerator.add_rule_definition()` with the assembled rule.
    - Advances wizard page.
- **Page 5: Final Profile Review & Save:**
  - Displays a JSON preview of the `ProfileGenerator.get_generated_profile_data()`.
  - `CTkEntry` for user to set profile filename.
  - "Save Profile & Close" button -> calls `_save_generated_profile()` which uses `ProfileGenerator.save_generated_profile()`.
  - Option to "Save and Open in Main Editor".

### 15.5. Prompt Engineering for Profile Generation (v5.0.0 Detailed)

_(This section details specific prompt structures for `StrategyPlanner`'s goal-to-plan, and `ProfileGenerator`'s methods for region suggestion, logic suggestion, and element refinement, as outlined in the "Design for Phase 3" and previous "Implementation for Phase 2 (GUI & AI Assist)" responses. Key aspects include clear JSON output schemas in prompts and few-shot examples where helpful.)_

- **`StrategyPlanner._construct_goal_to_plan_prompt()`:** As defined in `strategy_planner.py` implementation.
- **`ProfileGenerator.suggest_region_for_step()` Prompt Core:** As defined in `profile_generator.py` (Phase 2 Impl).
- **`ProfileGenerator.suggest_logic_for_step()` Prompt Core:** As defined in `profile_generator.py` (Phase 2 Impl).
- **`ProfileGenerator.refine_element_location()` Prompt Core:** As defined in `profile_generator.py` (Phase 2 Impl, similar to v4.0.0 bbox prompt).

### 15.6. Error Handling and User Feedback during Generation (v5.0.0)

_(Builds upon Section 8 notes for v5.0.0)_

- The `ProfileCreationWizardWindow` GUI MUST clearly display errors from `StrategyPlanner` or `ProfileGenerator` (e.g., "AI could not generate a plan. Please rephrase your goal," or "AI could not suggest a region for this step. Please define it manually.").
- It MUST provide "Retry" options for AI suggestion steps where feasible, or clear paths for manual override.
- Loading indicators/messages during long Gemini calls are essential.

---