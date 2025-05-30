# Technical Design Document: Mark-I

This document outlines the technical design and architectural considerations for the Mark-I visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status.
Version 4.0.0 (Gemini-Powered Visual Intelligence), including all its sub-phases, is functionally complete.
**This document now incorporates the design for v5.0.0, focusing on AI-Driven Profile Generation as per ADR-009.**

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
  - Used by `RulesEngine` (for `gemini_vision_query`), `GeminiDecisionModule` (for NLU and step-specific visual queries), and **`StrategyPlanner` (for v5.0.0 AI Profile Generation)**.
  - _Details in Section 10._
- **`engines.rules_engine.RulesEngine` Class:**
  - Evaluates rules based on analysis results.
  - Supports single/compound conditions, variable capture/substitution.
  - Handles `gemini_vision_query` conditions by invoking `GeminiAnalyzer`.
  - For actions of type `gemini_perform_task`, it invokes the `GeminiDecisionModule` to handle NLU commands and goal-oriented task execution.
  - _Details in Section 5._
- **`engines.action_executor.ActionExecutor` Class:**
  - Simulates mouse and keyboard actions using `pyautogui`.
  - Calculates target coordinates, including for Gemini-identified bounding boxes.
  - Called by `RulesEngine` for standard actions and by `GeminiDecisionModule` for executing primitive steps of an NLU-driven task.
- **`engines.gemini_decision_module.GeminiDecisionModule` Class (v4.0.0 Phase 2 & 3):**
  - NLU Task Orchestrator: Parses natural language user commands.
  - Decomposes commands into a sequence of manageable steps/sub-goals using Gemini for NLU.
  - For each decomposed step, uses `GeminiAnalyzer` for visual analysis and action refinement.
  - Manages basic state across steps of a single NLU task.
  - Orchestrates execution of these steps by calling `ActionExecutor`.
  - _Details extensively in Section 14._
- **`generation.strategy_planner.StrategyPlanner` Module (NEW - v5.0.0):**
  - Takes a high-level user goal for automation.
  - Uses `GeminiAnalyzer` to interact with Gemini to break this goal down into an "intermediate plan" (a sequence of logical, human-understandable sub-steps or sub-goals).
  - _Details in Section 15._
- **`generation.profile_generator.ProfileGenerator` Module (NEW - v5.0.0):**
  - Takes the "intermediate plan" from the `StrategyPlanner`.
  - Iterates through plan steps, interacting with the user (via GUI) and `GeminiAnalyzer` (for visual suggestions) to define concrete Mark-I profile elements (regions, conditions, actions, templates).
  - Assembles these elements into a Mark-I JSON profile structure.
  - _Details in Section 15._
- **`main_controller.MainController` Class:**
  - Orchestrates the main bot loop for rule-based profile execution.
  - Instantiates core engine components.
  - **(v5.0.0 Consideration):** A new controller or mode might be needed to manage the AI Profile Generation workflow, distinct from the runtime bot loop.
- **`ui.cli` Module:**
  - Provides CLI using `argparse`.
  - **(v5.0.0 Consideration):** May require a new CLI command (e.g., `mark_i generate-profile --goal "my goal"`) to trigger AI profile generation.
- **`ui.gui.*` Modules:**
  - `MainAppWindow`, `DetailsPanel`, etc., provide the GUI editor.
  - **(v5.0.0 Consideration):** Significant new GUI components will be needed for the AI Profile Generation workflow (goal input, plan review, interactive element definition guided by AI).
  - _Details in Section 9 and 11 (for existing features) and Section 15.4 (for new GUI)._
- **`mark_i/__main__.py`:** Application entry point.

## 2. Key Libraries & Justifications (Summary from ADRs)
*(No changes to core library stack from v4.0.0)*
-   **Environment Management:** `python-dotenv`
-   **Logging:** Python `logging` module
-   **Screen Capture:** `Pillow` (`ImageGrab`), `OpenCV-Python`
-   **Image Processing & Analysis (Local):** `OpenCV-Python`, `NumPy`, `Pillow`
-   **OCR (Local):** `pytesseract`
-   **Remote Advanced Visual Analysis, NLU, Decision Support, Plan Generation (v4.0.0+):** `google-generativeai`
-   **Input Simulation:** `pyautogui`
-   **Configuration Storage:** `json`
-   **CLI Framework:** `argparse`
-   **GUI Framework:** `CustomTkinter`
-   **Concurrency (Bot Runtime):** Python `threading` module

## 3. Defining and Capturing Regions
*(No fundamental changes. For v5.0.0 AI Profile Generation, region *suggestion* by AI and confirmation/drawing by user will be a new interaction, but the underlying region definition structure remains.)*

## 4. "Reading" from the Region - Analysis Strategies
*(Existing strategies remain. For v5.0.0 AI Profile Generation, `GeminiAnalyzer` will be heavily used by `StrategyPlanner` and `ProfileGenerator` to understand context and suggest elements for the profile.)*

## 5. Rules Engine & Evaluation (`RulesEngine`)

### 5.1. Rule Structure in JSON Profiles
*(Existing structure for conditions and actions remains. The AI Profile Generator (v5.0.0) will *output* profiles adhering to this established structure.)*

-   **Condition Object:** Single local, compound local, `gemini_vision_query`.
-   **Action Object:** `click` (with Gemini bounding box support), `type_text`, `press_key`, `log_message`, `gemini_perform_task` (for NLU runtime execution).

### 5.2. `RulesEngine` Evaluation Logic
*(No fundamental changes for v5.0.0. The RulesEngine executes profiles; the AI Profile Generator creates them.)*

### 5.3. Variable Handling (`RulesEngine`)
*(No fundamental changes for v5.0.0.)*

## 6. Data Flow Example for NLU Task (`gemini_perform_task` - v4.0.0 Phase 3)
*(This existing data flow remains valid for *runtime execution* of NLU tasks. Section 15.3 will detail the new data flow for *AI-driven profile generation*.)*

## 7. Logging System (per ADR-007)
- Root logger: `mark_i`.
- **(v5.0.0 Enhancement):** Logging for `StrategyPlanner` and `ProfileGenerator` will be critical:
    *   User's input goal.
    *   Prompts to Gemini for plan generation.
    *   Gemini's raw and parsed intermediate plan.
    *   For each plan step: prompts for element/region suggestions, AI's suggestions, user's confirmations/modifications.
    *   Details of the generated profile elements.
    *   Errors or ambiguities encountered during the generation process.

## 8. Error Handling
- **(v5.0.0 Enhancement):**
    *   **`StrategyPlanner`:** Must handle Gemini failures in generating a coherent plan (e.g., API errors, unusable output). Fallback: notify user, suggest rephrasing goal.
    *   **`ProfileGenerator`:** Must handle failures in suggesting specific profile elements (e.g., Gemini can't identify a relevant region for a step, or a user rejects all suggestions). Allow user to skip a step, manually define the element, or abandon generation.
    *   Ensure generated profiles are structurally valid JSON.

## 9. Full GUI Architecture (`MainAppWindow` using `CustomTkinter`)
*(Existing GUI architecture for profile editing remains.)*

### 9.x. (NEW - v5.0.0): GUI for AI-Driven Profile Generation
-   **Invocation:** A new menu item (e.g., "File > New AI-Generated Profile...") or a button in `MainAppWindow`.
-   **Workflow Stages:**
    1.  **Goal Input:** A dialog or dedicated panel with a `CTkTextbox` for the user to type their high-level automation goal. Option to provide an initial full screenshot or select an application window for context.
    2.  **Plan Review & Confirmation (Optional but Recommended):** Display the intermediate plan (sequence of steps) generated by `StrategyPlanner` (from Gemini). Allow user to review, possibly reorder or remove steps, or ask for regeneration.
    3.  **Interactive Element Definition:** For each step in the (confirmed) plan:
        *   **Region Focus:** The GUI might highlight a suggested screen area (based on AI suggestion) or ask the user to draw/confirm a region relevant to the current step (using a `RegionSelector`-like overlay).
        *   **Condition/Action Suggestion:** Display AI's suggestion for how to implement the step (e.g., "Condition: OCR text 'Username:' is present. Action: Click nearby field.").
        *   **Element Grounding:** If AI suggests interacting with "the username field," it might overlay bounding box suggestions on the screen capture. User clicks to confirm the correct one.
        *   **Template Capture Prompt:** If AI suggests a template is needed (e.g., "Look for this icon: [description]"), prompt the user to capture that template image from the screen.
        *   **Parameter Input:** Prompt for any parameters AI cannot infer (e.g., "What username should I type?").
    4.  **Profile Summary & Save:** Once all steps are processed, show a summary of the generated profile structure (regions, rules). Allow user to save it as a new `.json` file, which can then be opened in the standard editor for further refinement.
-   This interactive GUI will be a major new component, likely managed by a new top-level window or a dedicated mode within `MainAppWindow`.

## 10. Gemini API Interaction (`GeminiAnalyzer` - v4.0.0+)
*(No fundamental changes to `GeminiAnalyzer` itself. For v5.0.0, it will be used by `StrategyPlanner` for goal-to-plan generation (likely text/multimodal prompts) and by `ProfileGenerator` for suggesting visual elements/regions for specific plan steps (likely vision prompts).)*

### 10.3. Prompting for Bounding Boxes (v4.0.0 Phase 1.5+)
*(This existing capability will be crucial for the `ProfileGenerator` in v5.0.0 to help ground AI's textual descriptions of UI elements to actual screen locations for the generated profile.)*

## 11. GUI Configuration for Gemini (v4.0.0+)
*(Existing GUI config for `gemini_vision_query` and `gemini_perform_task` remains. For v5.0.0, new UI elements for the AI Profile Generation workflow will not be part of `UI_PARAM_CONFIG` but rather a new GUI view/dialog system.)*

## 12. `ActionExecutor`
*(No fundamental changes. It will execute actions defined in the AI-generated profiles just like any other profile.)*

## 13. Testing Strategy
### 13.x. (NEW - v5.0.0): Testing AI-Driven Profile Generation
-   **Goal-to-Plan Generation:**
    *   Test with diverse high-level goals.
    *   Mock `GeminiAnalyzer` to simulate various plan structures (correct, incomplete, illogical) from Gemini.
    *   Verify `StrategyPlanner` correctly parses plans and handles errors.
-   **Plan-to-Profile Element Generation:**
    *   For each type of plan step, test the `ProfileGenerator`'s ability to:
        *   Suggest relevant regions (mock visual context).
        *   Suggest appropriate condition/action types.
        *   Guide user through template capture or parameter input.
        *   Correctly assemble the JSON for that rule/element.
-   **End-to-End Profile Generation:**
    *   Manual testing with real Gemini API.
    *   Provide a goal, go through the interactive GUI workflow.
    *   Evaluate the quality, correctness, and efficiency of the generated Mark-I profile.
    *   Test if the generated profile actually works when run by Mark-I's execution engine.
-   **Usability:** Test the intuitiveness and helpfulness of the AI-assisted profile creation GUI.

---
## 14. Gemini Decision Module & NLU Task Orchestration (v4.0.0 Phase 2 & 3 - Final)

*(This entire section, as detailed in the previous response where Phase 3 was completed, remains valid. It describes the runtime NLU capabilities of Mark-I v4.0.0. For v5.0.0, this module's visual refinement capabilities might be leveraged by the `ProfileGenerator`.)*

### 14.1. Overview and Purpose (Final v4.0.0)
*   **Goal:** Enables users to issue high-level commands via the `gemini_perform_task` action's `natural_language_command` parameter. The `GeminiDecisionModule` parses these, decomposes them, and orchestrates execution. Each sub-step uses Gemini for precise visual targeting and action selection from `PREDEFINED_ALLOWED_SUB_ACTIONS`.
*   **Operation:** Acts as an intermediary between an NLU instruction and a sequence of UI interactions.

### 14.2. Module Architecture and Components (Final v4.0.0)
*   **`mark_i.engines.gemini_decision_module.GeminiDecisionModule` Class:**
    *   **Responsibilities:** NLU & Command Parsing, Task Decomposition & Planning, Step Execution Orchestration (calling `_execute_primitive_sub_action`), State Management (basic), Error Handling.
*   **`PREDEFINED_ALLOWED_SUB_ACTIONS` Constant:** Defines primitive actions (e.g., `CLICK_DESCRIBED_ELEMENT`, `TYPE_IN_DESCRIBED_FIELD`, `PRESS_KEY_SIMPLE`, `CHECK_VISUAL_STATE`).
*   **Internal Task Plan:** List of step objects from NLU.

### 14.3. Data Flow and Interaction for NLU Task (Final v4.0.0)
*   `Rule Trigger` -> `RulesEngine` (`gemini_perform_task`) -> `GeminiDecisionModule.execute_nlu_task()` -> `GDM` uses `GA` for NLU -> `GDM` gets plan -> Loop steps: `GDM` uses `GA` for sub-step action/refinement -> `GDM` (optional confirm) -> `GDM` calls `AE`.

### 14.4. Prompt Engineering Strategies (Final v4.0.0)
#### 14.4.1. Prompts for NLU & Task Decomposition (`_construct_nlu_parse_prompt`)
*   System role, user command, detailed JSON output schema instructions, few-shot examples.
#### 14.4.2. Prompts for Per-Step Visual Target Refinement (`_refine_target_description_to_bbox`)
*   Role ("precise visual element locator"), target description, JSON output instructions for `box` and `found`.

### 14.5. Safety, Control, and Limitations (Final v4.0.0)
*   Adherence to `PREDEFINED_ALLOWED_SUB_ACTIONS`.
*   Validation of NLU outputs.
*   `max_steps` and `require_confirmation_per_step` parameters.
*   NLU accuracy dependent on Gemini and prompt quality. Basic error handling.

### 14.6. GUI Integration (Final v4.0.0)
*   `gemini_perform_task` action in `DetailsPanel` configured via `gui_config.py` (parameters: `natural_language_command`, `context_region_names`, `allowed_actions_override`, `require_confirmation_per_step`, `max_steps`).

### 14.7. Invocation from `RulesEngine` (Final v4.0.0)
*   `RulesEngine` calls `GeminiDecisionModule.execute_nlu_task()` when `gemini_perform_task` action is triggered.

---
## 15. AI-Driven Profile Generation (v5.0.0 - `StrategyPlanner` & `ProfileGenerator`)

This section details the architecture for Mark-I v5.0.0's "AI Profile Creator" feature, designed to assist users in generating Mark-I JSON profiles from high-level natural language goals, as per ADR-009. **This update details the GUI Workflow and AI-Assisted Element Suggestion logic for Phase 2 of v5.0.0.**

### 15.1. Overview and Purpose (v5.0.0)
*(Remains as previously defined in the v5.0.0 design for `TECHNICAL_DESIGN.MD`)*
The primary goal is to use AI to translate a user's high-level automation goal into an intermediate plan, and then interactively guide the user, with AI assistance, to convert this plan into a functional Mark-I JSON profile.

### 15.2. Core Components for Profile Generation (v5.0.0)

#### 15.2.1. `generation.strategy_planner.StrategyPlanner` Class
*(Core responsibilities and `generate_intermediate_plan` method remain as designed in v5.0.0 Phase 1. It produces the `IntermediatePlan`.)*

#### 15.2.2. `generation.profile_generator.ProfileGenerator` Class (Enhanced for v5.0.0 Phase 2 AI Assist)

*   **Responsibilities (Recap & Enhancements):**
    *   Takes the "intermediate plan" from `StrategyPlanner`.
    *   Manages an interactive workflow with the user via the `ProfileCreationWizardWindow` GUI.
    *   Iterates through each step of the plan:
        *   **Visual Contextualization:** Receives current screen capture relevant to the step.
        *   **(NEW - AI Assist) Region Suggestion/Definition:** Calls `self.suggest_region_for_current_step()` which uses `GeminiAnalyzer` to suggest a relevant screen area. Passes suggestion to GUI. GUI allows user to confirm, adjust (invoking a region selection tool), or manually define. The final region is added to the profile draft.
        *   **(NEW - AI Assist) Condition/Action Logic Suggestion & Formulation:** Calls `self.suggest_logic_for_current_step()` which uses `GeminiAnalyzer` to suggest Mark-I condition(s) and action(s) appropriate for the plan step and defined region. Passes suggestions to GUI.
        *   **(NEW - AI Assist & GUI Interaction) Interactive Element Grounding & Parameter Elicitation:**
            *   If an AI-suggested action involves a specific UI element (e.g., "click 'Login' button"), `ProfileGenerator` may use `GeminiAnalyzer` again to get candidate bounding boxes for that element description within the step's region.
            *   GUI displays these candidates (e.g., overlays on a screenshot snippet). User clicks to confirm.
            *   If AI or user decides a template is best, GUI prompts user to capture it. Template saved, metadata added to profile draft.
            *   GUI prompts user for any parameters AI cannot infer (e.g., text to type, specific file names).
            *   User confirms/modifies all AI-suggested and user-provided parameters for conditions and actions.
        *   **Rule Assembly:** Assembles the confirmed elements into a Mark-I rule and adds it to `profile_data`.
    *   Maintains the `profile_data` dictionary (regions, templates, rules, settings) as it's being built.
*   **Key Enhanced/New Methods for AI Assist:**
    *   `suggest_region_for_current_step(self, plan_step: IntermediatePlanStep, current_full_screen_capture: np.ndarray) -> Optional[Dict[str, Any]]`:
        *   Input: Current plan step description, full screen capture.
        *   Process: Crafts prompt for `GeminiAnalyzer` (vision model) asking it to identify and return a bounding box `{"box": [x,y,w,h], "reasoning": "..."}` for the most relevant screen area for *this specific plan step*.
        *   Output: A dictionary `{"x": ..., "y": ..., "width": ..., "height": ..., "ai_confidence": ..., "ai_reasoning": ...}` or `None`.
    *   `suggest_logic_for_current_step(self, plan_step: IntermediatePlanStep, current_region_capture: np.ndarray, region_name: str) -> Optional[Dict[str, Any]]`:
        *   Input: Current plan step, image of the *focused region for this step*, name of this region.
        *   Process: Crafts prompt for `GeminiAnalyzer` asking it to suggest a Mark-I `condition` object and an `action` object (with types and parameters) to implement the `plan_step.description` within the given `current_region_capture`. The prompt will include examples of Mark-I condition/action JSON structures.
        *   Output: `{"suggested_condition": {...}, "suggested_action": {...}, "ai_reasoning": "..."}` or `None`.
    *   `refine_element_location_for_step(self, element_description: str, current_region_capture: np.ndarray, region_name: str) -> Optional[Dict[str, Any]]`:
        *   Input: A textual description of an element (e.g., "the username field," "the submit button") from a plan step or AI logic suggestion, image of the current working region.
        *   Process: Uses `GeminiAnalyzer` with a vision prompt (similar to Phase 1.5 `_refine_target_description_to_bbox`) to get bounding box candidates for the `element_description` within the `current_region_capture`.
        *   Output: List of `{"box": [x,y,w,h], "label_suggestion": "...", "confidence": ...}` or `None`.
*   *(Other methods like `initialize_profile_generation`, `get_next_plan_step_description`, `add_region_to_profile`, etc., remain structurally similar but will be called by the new GUI wizard.)*

### 15.3. Data Flow for AI Profile Generation Workflow (v5.0.0 - Enhanced for Interactivity)
*(The Mermaid diagram from ADR-009 and previous design is still a good high-level. The "ProfileGenerator" box now has more internal calls to GeminiAnalyzer for suggestions during its loop.)*

1.  **User Goal Input (GUI):** User provides goal string and optional initial screen context image.
2.  **`StrategyPlanner.generate_intermediate_plan(goal, initial_context)`:**
    *   `SP` -> `GeminiAnalyzer` (text/multimodal model with goal-to-plan prompt) -> Gemini returns JSON plan.
    *   `SP` parses plan, returns `IntermediatePlan` (list of `IntermediatePlanStep` dicts).
3.  **`ProfileCreationWizardWindow` (GUI) starts, gets plan from `SP`.**
4.  **Loop through each `IntermediatePlanStep` in the GUI Wizard, managed by `ProfileGenerator`:**
    a.  **GUI:** Displays `plan_step.description`. Takes current full screenshot.
    b.  **`ProfileGenerator.suggest_region_for_current_step(plan_step, full_screenshot)`:**
        *   `PG` -> `GeminiAnalyzer` (vision prompt for region box) -> Returns suggested box.
    c.  **GUI:** Displays suggested region on screenshot. User confirms, adjusts (invoking `RegionSelector`-like tool), or draws manually. User names the region.
    d.  **`ProfileGenerator.add_region_to_profile(user_defined_region_spec)`.**
    e.  **`ProfileGenerator.suggest_logic_for_current_step(plan_step, image_of_confirmed_region, region_name)`:**
        *   `PG` -> `GeminiAnalyzer` (prompt for condition/action JSON structure) -> Returns `{"suggested_condition": ..., "suggested_action": ...}`.
    f.  **GUI:** Displays suggested condition and action with editable parameters.
        *   If suggestion involves a specific element (e.g., action target "the login button"):
            *   **`ProfileGenerator.refine_element_location_for_step("login button", image_of_confirmed_region, region_name)`:**
                *   `PG` -> `GeminiAnalyzer` (vision prompt for bounding boxes of "login button") -> Returns candidate boxes.
            *   **GUI:** Overlays candidate boxes. User clicks to confirm THE "login button".
            *   If user chooses "Use Template" for this element: GUI prompts for template capture. `ProfileGenerator.add_template_to_profile()`. The condition/action is updated to use this template.
            *   Else (user confirms a bounding box or AI suggestion): The action parameters (e.g., `target_relation: "center_of_gemini_element"`, `gemini_element_variable` pointing to this refined box) are prepared.
        *   User provides any other needed parameters (e.g., text for `type_text`).
    g.  **`ProfileGenerator.add_rule_to_profile(user_confirmed_rule_spec)`.**
    h.  GUI proceeds to next plan step.
5.  **Finalization (GUI):** User reviews all generated regions, templates, rules. Clicks "Save Profile."
6.  **`ProfileCreationWizardWindow` -> `ProfileGenerator.save_generated_profile(filepath)`.**

### 15.4. GUI Workflow for AI Profile Generation (`ProfileCreationWizardWindow` - v5.0.0 Phase 2)

This new GUI component will guide the user through the AI-assisted profile creation.

*   **Overall Structure:** Likely a `ctk.CTkToplevel` window acting as a wizard. It will have "Next Step," "Previous Step" (optional), "Define Manually," "Accept Suggestion," and "Cancel" buttons.
*   **Screen 1: Goal Input & Initial Context:**
    *   Large `CTkTextbox` for "Describe your automation goal:"
    *   Button: "Use Current Full Screen as Context" (takes screenshot).
    *   Button: "Select Application Window as Context" (lists open windows, user selects, captures that window).
    *   Button: "Proceed without Initial Image Context."
    *   "Generate Automation Plan" button -> calls `StrategyPlanner`.
*   **Screen 2: Plan Review & Confirmation (Optional):**
    *   If `StrategyPlanner` returns a plan, display it as a list of step descriptions.
    *   User can review. (Future: edit/reorder).
    *   "Start Building Profile from this Plan" button -> calls `ProfileGenerator.start_profile_generation_from_plan()`.
*   **Screen 3 (Repeats for each plan step): Interactive Step Definition:**
    *   **Display Area:** Shows current full screenshot (or selected app window screenshot). This area will be used to overlay AI-suggested regions and element bounding boxes.
    *   **Plan Step Display:** Clearly shows the current `plan_step.description` (e.g., "Locate the 'Username' input field.").
    *   **AI Suggestion Area:**
        *   **Region:** "AI suggests focusing on this area for this step:" (displays a highlighted rectangle from `ProfileGenerator.suggest_region_for_current_step()`). Buttons: "Accept Suggested Region," "Draw/Adjust Region Manually."
            *   If "Draw/Adjust": Invokes an embedded or modal `RegionSelector`-like tool. User defines/names the region. `ProfileGenerator.add_region_to_profile()`.
        *   **Logic:** "AI suggests for this step in region `'{confirmed_region_name}'`:"
            *   Displays suggested Condition (type, params).
            *   Displays suggested Action (type, params).
            *   Editable fields for all parameters.
        *   **Element Grounding:** If action needs a target (e.g., "Click 'Login Button'"):
            *   `ProfileGenerator.refine_element_location_for_step()` is called.
            *   "AI found these candidates for 'Login Button':" (Highlights are shown on the screenshot snippet of the confirmed region). User clicks one.
            *   Option: "Element not listed / Capture Template Instead." -> Template capture workflow.
        *   **Parameter Input:** Prompts for any `required_user_input_for_step` from the plan (e.g., "Enter text to type:").
    *   **Controls:** "Confirm Step & Add to Profile," "Skip Step / Define Manually Later," "Cancel Profile Generation."
*   **Screen 4: Final Review & Save:**
    *   Displays a tree-like summary of generated `profile_data` (regions, templates, rules).
    *   "Save Profile As..." button.
    *   "Open in Editor for Refinement" button (saves then opens in `MainAppWindow`).

### 15.5. Prompt Engineering for Profile Generation - Element Suggestion (v5.0.0 Phase 2)

This details prompts for `ProfileGenerator`'s AI-assist methods.

*   **For `ProfileGenerator.suggest_region_for_current_step()`:**
    *   **Input:** Full screen image, current `plan_step.description`.
    *   **Prompt Snippet:** "...Given the full screen image and the current task step: `'{plan_step.description}'`. Your goal is to identify the primary rectangular area on this screen where this step is most likely to take place. Respond ONLY with a JSON object containing a 'box' key with an array of four integers [x, y, width, height] representing this area, and a 'reasoning' key explaining your choice. The coordinates must be relative to the top-left of the provided full image."
*   **For `ProfileGenerator.suggest_logic_for_current_step()`:**
    *   **Input:** Image of the *focused/confirmed region for this step*, `plan_step.description`, `region_name`.
    *   **Prompt Snippet:** "...For the task step `'{plan_step.description}'` to be performed within the provided image (which is region `'{region_name}'`), suggest a Mark-I condition object and a Mark-I action object to implement it.
        Valid condition types: `pixel_color`, `average_color_is`, `template_match_found`, `ocr_contains_text`, `dominant_color_matches`, `gemini_vision_query`, `always_true`.
        Valid action types: `click`, `type_text`, `press_key`, `log_message`.
        Provide parameters. If a template is best, for `template_match_found` use `\"template_filename\": \"USER_TO_CAPTURE_TEMPLATE_FOR_{element_description}\"`. If an element needs precise clicking, describe it for the `click` action's `target_description` (e.g., `\"target_description\": \"the green OK button\"`).
        Respond ONLY with JSON: `{\"suggested_condition\": {\"type\": \"...\", ...}, \"suggested_action\": {\"type\": \"...\", ...}, \"reasoning\": \"...\"}`."
*   **For `ProfileGenerator.refine_element_location_for_step()` (finding specific element box):**
    *   *(This reuses the robust bounding box prompt from v4.0.0 Phase 1.5/Section 10.3/14.4.2)*: "You are a precise visual element locator. In the provided image (of region `'{region_name}'`), identify the UI element best described as: `'{element_description}'`. Respond ONLY with JSON: `{\"found\": true/false, \"box\": [x,y,w,h_or_null], \"element_label\": \"{element_description}\"}`."

### 15.6. Error Handling and User Feedback during Generation (v5.0.0 Phase 2)
*(Builds upon Section 8 notes)*
*   The GUI Wizard must clearly display errors from `StrategyPlanner` or `ProfileGenerator`.
*   If AI fails to suggest a region, condition, or action for a step, the GUI should allow the user to:
    *   Manually define the element (e.g., draw region, manually create condition/action using standard GUI elements similar to `DetailsPanel`).
    *   Ask the AI to "try again" (perhaps with a rephrased step description by the user).
    *   Skip the current plan step (leaving a placeholder or comment in the generated profile).
*   Progress indicators for long Gemini calls.

---