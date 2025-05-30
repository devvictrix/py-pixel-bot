// File: docs/FUNCTIONAL_REQUIREMENTS.MD

# Functional Requirements for Mark-I

This document outlines the functional requirements for the Mark-I visual automation tool, describing _what_ the system will do.
**This version reflects the completed capabilities of v4.0.0 (including all Gemini integration phases) and incorporates detailed requirements for v5.0.0: AI-Driven Profile Generation (including its interactive GUI Workflow and AI-Assisted Element Suggestion logic).**

## FR-CORE: Core System

- **FR-CORE-001: Cross-Platform Operation:** The bot's core runtime engine and GUI editor SHOULD operate on Windows, macOS, and Linux. (Primary development and testing on Windows).
- **FR-CORE-002: Configuration Files (JSON):** The system MUST use JSON for saving and loading bot configurations (profiles). Profiles MUST store all necessary data for bot operation, including settings (e.g., `monitoring_interval_seconds`, `gemini_default_model_name`), region definitions (`name`, `x`, `y`, `width`, `height`, `comment`), template metadata (`name`, `filename`, `comment`), and rule definitions. Rule definitions include `name`, default `region`, `comment`, a `condition` block, and an `action` block (with `type` and specific parameters, including complex AI-driven action types like `gemini_perform_task` with its NLU parameters).
- **FR-CORE-003: Environment Configuration:** The system MUST read environment variables (e.g., from `.env` file via `python-dotenv`) for `APP_ENV` (influencing logging) and sensitive data like `GEMINI_API_KEY` (essential for all Gemini features).
- **FR-CORE-004: Logging:** The system MUST implement comprehensive, persistent, and configurable logging for all significant operations:
  - Decisions, errors, state changes in backend engines and GUI.
  - All AI interactions with Gemini: API calls for `gemini_vision_query`, NLU parsing, goal-driven decision-making (`GeminiDecisionModule`), and **(v5.0.0)** plan generation (`StrategyPlanner`) and element/logic suggestion (`ProfileGenerator`). Logs MUST include summarized prompts, model used, response status, latency, and key parsed data or error messages.

## FR-CAPTURE: Screen Region Capture Module (Bot Runtime & Profile Generation)

- **FR-CAPTURE-001: Define Target Region (Manual & AI-Assisted):**
  - **(Manual - Runtime & Editing):** The user MUST be able to manually define one or more named rectangular regions on the screen (`x`, `y`, `width`, `height`) via the GUI (`RegionSelectorWindow` operating on live screen, or `SubImageSelectorWindow` for templates from existing images).
  - **(v5.0.0 - AI-Assisted Profile Generation):** During the AI Profile Generation workflow, the system (via `ProfileGenerator` and the wizard GUI) MUST:
    - Allow the AI to suggest a relevant screen region (bounding box) for a given plan step based on full visual context.
    - Allow the user to visually confirm, adjust (e.g., by dragging/resizing the AI's suggested box), or manually draw/define the region for the step using an integrated tool.
    - Allow the user to name the defined/confirmed region.
- **FR-CAPTURE-002: Capture Specified Region (Runtime):** The system MUST capture image data from defined regions during bot runtime for analysis.
- **FR-CAPTURE-003: Real-time Capture (Runtime):** The system MUST support continuous real-time capture at a user-configurable interval.
- **FR-CAPTURE-004: Full Screen/Window Capture (Context for AI - v5.0.0 Profile Generation):** The AI Profile Generation wizard MUST allow capturing an image of the full screen or a user-selected application window to provide initial visual context to `StrategyPlanner` and ongoing context to `ProfileGenerator` for its suggestion methods.

## FR-ANALYZE: Region Analysis & AI Understanding Module

- **FR-ANALYZE-001: Pixel Color Analysis:** (As is - runtime rules: check specific pixel BGR colors with tolerance).
- **FR-ANALYZE-001B: Average Color Analysis:** (As is - runtime rules: check average BGR color of a region with tolerance).
- **FR-ANALYZE-002: Template Matching Analysis:** (As is - runtime rules: check for template image presence with confidence. Match details capturable).
- **FR-ANALYZE-003: OCR Text Extraction & Analysis:** (As is - runtime rules: extract text using Tesseract. Text and confidence capturable).
- **FR-ANALYZE-003B: OCR-Based Conditions:** (As is - runtime rules: conditions on OCR text content and confidence).
- **FR-ANALYZE-004: Configurable Analysis Rules (Runtime):** (As is - users define rules with single/compound conditions linking to actions).
- **FR-ANALYZE-005: Dominant Color Analysis:** (As is - runtime rules: check dominant colors and percentage).
- **FR-ANALYZE-006: Selective Local Analysis (Runtime):** (As is - `MainController` optimizes).
- **FR-ANALYZE-007: Gemini Vision Query (v4.0.0 - Runtime):** The `gemini_vision_query` condition type MUST function as defined (send image/prompt to Gemini, evaluate response, capture result as `{"value": <data>, "_source_region_for_capture_": "region_name"}`).
- **FR-ANALYZE-008: Gemini-Informed Action Suggestion (v4.0.0 Phase 2 - Runtime):** (`GeminiDecisionModule` via `gemini_perform_task` with `goal_prompt` - as is: AI suggests single primitive action).
- **FR-ANALYZE-009: Natural Language Command Understanding & Decomposition (v4.0.0 Phase 3 - Runtime):** `GeminiDecisionModule` (via `gemini_perform_task` with `natural_language_command`) MUST parse NL command to structured plan, decompose, orchestrate steps with AI visual refinement.
- **FR-ANALYZE-010: AI Goal-to-Plan Generation (v5.0.0 - Profile Generation):** The `StrategyPlanner` module MUST:
  - Accept a high-level user goal (natural language) and optional initial visual context (full screenshot or app window image).
  - Use `GeminiAnalyzer` to prompt Gemini to generate an "intermediate plan" - a sequence of logical, human-understandable sub-steps (structured as JSON, e.g., `[{"step_id": 1, "description": "...", "suggested_element_type_hint": "...", "required_user_input_for_step": [...]}, ...]`).
  - Parse and perform basic validation on this intermediate plan structure.
- **FR-ANALYZE-011: AI Plan-Step-to-Profile-Element Suggestion (v5.0.0 - Profile Generation):** The `ProfileGenerator` module, for each step in the intermediate plan and given relevant visual context, MUST:
  - **Region Suggestion:** Use `GeminiAnalyzer` to suggest a relevant screen region (bounding box `[x,y,w,h]`) for the current plan step, based on a full screen/app context image.
  - **Logic Suggestion:** Use `GeminiAnalyzer` to suggest appropriate Mark-I condition(s) (type and parameters) and action(s) (type and parameters) to implement the logic of the plan step within a user-confirmed/defined region for that step (using an image of that specific region). The suggestion should be in Mark-I JSON format.
  - **Element Refinement Suggestion:** If a suggested action from Logic Suggestion involves a textually described UI element (e.g., "click 'Login' button"), use `GeminiAnalyzer` to visually identify and suggest candidate bounding boxes for that element within the step's specific region image.
- **FR-ANALYZE-012: AI Template Identification Hint (v5.0.0 - Profile Generation):** If, during Logic Suggestion, `ProfileGenerator` (via Gemini) determines that a visual element crucial for a plan step is best identified using an image template, it MUST be able to signal this (e.g., in its suggested condition/action, or as separate metadata) so the GUI can prompt the user for template capture.

## FR-ACTION: Action Execution & Task Orchestration Module

- **FR-ACTION-001 - FR-ACTION-006:** (Mouse Click, Keyboard Input, Conditional Actions, Log Message, Dynamic Params, Pause Before Action - as is for runtime execution). Note: FR-ACTION-001 includes clicking Gemini-identified elements via `gemini_element_variable` or absolute coordinates derived by AI processes.
- **FR-ACTION-007: Execute Gemini-Suggested/Decomposed Actions (v4.0.0 Phase 2+ - Runtime):** (As is).
- **FR-ACTION-008: User Confirmation for AI-Driven Actions (v4.0.0 Phase 2+ - Runtime):** (As is - via `require_confirmation_per_step` in `gemini_perform_task`).
- **FR-ACTION-009: `gemini_perform_task` Action Type (v4.0.0 Phase 2 & 3 - Runtime):** (As is - primary input `natural_language_command`).
- **FR-ACTION-010: Assembling AI-Generated Profile Actions (v5.0.0 - Profile Generation):** The `ProfileGenerator` MUST correctly assemble user-confirmed and AI-assisted action specifications (for `click`, `type_text`, `press_key`, `log_message`, and potentially `gemini_vision_query` as a condition, or even simpler `gemini_perform_task` for sub-goals if generation becomes very advanced) into the standard Mark-I action structure within the generated JSON profile. If an action was targeted at a visually refined element, the generated action MUST correctly use absolute coordinates or a temporary variable mechanism as designed.

## FR-CONFIG: Configuration & Management (CLI, GUI, AI Generation)

- **FR-CONFIG-001 - FR-CONFIG-003:** (Save/Load Profile, Variable Capture, Gemini Settings - as is).
- **FR-CONFIG-004: Gemini NLU Task Definition in Profile (v4.0.0 Phase 3 - Runtime):** (As is - `gemini_perform_task` parameters).
- **FR-CONFIG-005: AI Profile Generation - Goal Input (v5.0.0):** The system (via `ProfileCreationWizardWindow`) MUST allow users to input a high-level natural language goal and optionally provide initial visual context (full screenshot, app window image, or image file) to initiate AI-driven profile generation by `StrategyPlanner`.
- **FR-CONFIG-006: AI Profile Generation - Interactive Element Definition (v5.0.0):** During AI profile generation, the GUI workflow driven by `ProfileGenerator` MUST interactively prompt the user to:
  - Confirm, adjust, or manually draw screen regions based on AI suggestions or plan steps, and name these regions.
  - Confirm, modify, or manually specify condition logic (type and parameters) based on AI suggestions or plan steps for the current region.
  - Confirm, modify, or manually specify action logic (type and parameters) based on AI suggestions or plan steps.
  - If an action targets a specific UI element, confirm AI-suggested bounding boxes for that element (selected from potentially multiple candidates) or manually indicate the target.
  - Capture template images (and name them), using a sub-image selection tool on the relevant region image, if the AI or user determines a template is necessary for a plan step. The system MUST stage this template image data for saving with the profile.
  - Provide any specific data values (e.g., text to be typed, file paths, specific OCR keywords) required by the AI-suggested or user-defined logic for the step.
- **FR-CONFIG-007: AI Profile Generation - Profile Output (v5.0.0):** The AI Profile Generation process MUST output a standard, structurally valid Mark-I JSON profile file. The `ProfileGenerator` MUST ensure that any staged template images (captured during the generation process) are saved to the appropriate `templates/` subdirectory when the main profile JSON is saved.
- **FR-CONFIG-008: AI Profile Generation - Plan Review (v5.0.0 - Optional):** The GUI workflow SHOULD offer an optional step to display the AI-generated intermediate plan to the user for review before interactive element definition begins.
- **FR-CONFIG-009: AI Profile Generation - Saving (v5.0.0):** The GUI workflow MUST allow the user to specify a filename and location to save the generated profile.

## FR-UI: User Interface

- **FR-UI-001: CLI Control:** (As is).
- **FR-UI-002: GUI for Region Definition (Component - Full Screen):** `RegionSelectorWindow` for visual region selection on live screen.
- **FR-UI-003: Full GUI Profile Editor (`MainAppWindow` - v4.0.0 Complete):** (As is, supporting all v4.0.0 features for manual editing).
- **FR-UI-004: User Feedback (General - v4.0.0 Complete):** (As is).
- **FR-UI-005: GUI for AI Profile Generation Invocation (v5.0.0):** `MainAppWindow` MUST provide a clear way (e.g., "File > New AI-Generated Profile...") to launch the `ProfileCreationWizardWindow`. This option SHOULD be disabled if `GEMINI_API_KEY` is not configured.
- **FR-UI-006: AI Profile Generation Wizard/Workflow GUI (v5.0.0 - `ProfileCreationWizardWindow`):** A new GUI component MUST:
  - Provide fields for goal input and initial visual context capture/loading.
  - (Optional) Display the AI-generated intermediate plan.
  - Guide the user step-by-step through defining profile elements for each plan step, including:
    - Displaying the current plan step description.
    - Presenting AI-suggested screen regions on a relevant screenshot (full context image); allowing user confirmation, adjustment (e.g., via an integrated region drawing tool), or manual definition; and prompting for region names.
    - Displaying the confirmed region's image as context for logic definition.
    - Presenting AI-suggested condition and action logic in editable fields.
    - If an action involves a specific UI element, displaying AI-suggested candidate bounding boxes overlaid on the region image, allowing user selection.
    - Providing a mechanism to launch a template capture tool (e.g., `SubImageSelectorWindow`) operating on the current step's confirmed region image.
    - Prompting for other necessary parameters.
  - Provide navigation controls ("Next Step," "Previous Step," "Cancel").
  - Display a summary of generated profile elements before final saving.
  - Allow saving the generated profile and optionally opening it in the main editor.
- **FR-UI-007: Visual Suggestion Display in AI Generation GUI (v5.0.0):** The `ProfileCreationWizardWindow` MUST display screen captures and overlay AI-suggested bounding boxes for regions or specific UI elements, allowing visual confirmation or selection.
- **FR-UI-008: Sub-Image Template Capture GUI (v5.0.0 - `SubImageSelectorWindow`):** A helper GUI window MUST be provided that displays a given image (e.g., a previously defined region's image) and allows the user to draw a rectangle on it to select a sub-area for a new template. It MUST return the coordinates of this selection relative to the provided image.

---
