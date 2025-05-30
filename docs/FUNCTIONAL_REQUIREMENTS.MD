# Functional Requirements for Mark-I

This document outlines the functional requirements for the Mark-I visual automation tool, describing *what* the system will do.
**This version reflects the completed capabilities of v4.0.0 and incorporates detailed requirements for v5.0.0: AI-Driven Profile Generation (including GUI Workflow and AI-Assisted Element Suggestion).**

## FR-CORE: Core System

*   **FR-CORE-001: Cross-Platform Operation:** The bot's core runtime engine and GUI editor SHOULD operate on Windows, macOS, and Linux. (Primary development and testing on Windows).
*   **FR-CORE-002: Configuration Files (JSON):** The system MUST use JSON for saving and loading bot configurations (profiles). Profiles MUST store all necessary data, including settings, region definitions, template metadata, and rule definitions.
*   **FR-CORE-003: Environment Configuration:** The system MUST read environment variables (e.g., from `.env` file) for `APP_ENV` and `GEMINI_API_KEY`.
*   **FR-CORE-004: Logging:** The system MUST implement comprehensive, persistent, and configurable logging for all significant operations, decisions, errors, AI interactions (Gemini API calls for queries, NLU, decision-making, plan generation, and element suggestion), and state changes.

## FR-CAPTURE: Screen Region Capture Module (Bot Runtime & Profile Generation)

*   **FR-CAPTURE-001: Define Target Region (Manual & AI-Assisted):**
    *   **(Manual):** The user MUST be able to manually define one or more named rectangular regions on the screen (x, y, width, height) via the GUI (`RegionSelectorWindow` or integrated tool).
    *   **(v5.0.0 - AI-Assisted):** During AI Profile Generation, the system (via `ProfileGenerator` and GUI) MUST allow the user to confirm, adjust, or manually draw regions suggested by AI for specific plan steps.
*   **FR-CAPTURE-002: Capture Specified Region (Runtime):** The system MUST capture image data from defined regions during bot runtime.
*   **FR-CAPTURE-003: Real-time Capture (Runtime):** The system MUST support continuous real-time capture at a user-configurable interval.
*   **FR-CAPTURE-004: Full Screen/Window Capture (Context for AI - v5.0.0):** The AI Profile Generation workflow MUST allow capturing an image of the full screen or a user-selected application window to provide initial visual context to `StrategyPlanner` and ongoing context to `ProfileGenerator`.

## FR-ANALYZE: Region Analysis & AI Understanding Module

*   **FR-ANALYZE-001: Pixel Color Analysis:** (As is - for runtime rules)
*   **FR-ANALYZE-001B: Average Color Analysis:** (As is - for runtime rules)
*   **FR-ANALYZE-002: Template Matching Analysis:** (As is - for runtime rules)
*   **FR-ANALYZE-003: OCR Text Extraction & Analysis:** (As is - for runtime rules)
*   **FR-ANALYZE-003B: OCR-Based Conditions:** (As is - for runtime rules)
*   **FR-ANALYZE-004: Configurable Analysis Rules (Runtime):** (As is - for runtime rules)
*   **FR-ANALYZE-005: Dominant Color Analysis:** (As is - for runtime rules)
*   **FR-ANALYZE-006: Selective Local Analysis (Runtime):** (As is - for runtime rules)
*   **FR-ANALYZE-007: Gemini Vision Query (v4.0.0 - Runtime):** (As is - `gemini_vision_query` condition)
*   **FR-ANALYZE-008: Gemini-Informed Action Suggestion (v4.0.0 Phase 2 - Runtime):** (`GeminiDecisionModule` for single goal execution via `gemini_perform_task` - as is)
*   **FR-ANALYZE-009: Natural Language Command Understanding & Decomposition (v4.0.0 Phase 3 - Runtime):** (`GeminiDecisionModule` for NLU command execution via `gemini_perform_task` - as is)
*   **FR-ANALYZE-010: AI Goal-to-Plan Generation (v5.0.0 - Profile Generation):** The `StrategyPlanner` module MUST:
    *   Accept a high-level user goal (natural language) and optional initial visual context.
    *   Use `GeminiAnalyzer` to prompt Gemini to generate an "intermediate plan" (a sequence of logical, human-understandable sub-steps as structured JSON).
    *   Parse and validate this intermediate plan.
*   **FR-ANALYZE-011: AI Plan-Step-to-Profile-Element Suggestion (v5.0.0 - Profile Generation):** The `ProfileGenerator` module, for each step in the intermediate plan, MUST:
    *   Use `GeminiAnalyzer` (with current screen context relevant to the step) to suggest potential screen regions for the step.
    *   Use `GeminiAnalyzer` to suggest appropriate Mark-I condition types and parameters to implement the logic of the plan step within a chosen/defined region.
    *   Use `GeminiAnalyzer` to suggest appropriate Mark-I action types and parameters for the plan step.
    *   If a plan step implies interaction with a specific UI element, use `GeminiAnalyzer` to visually suggest candidate elements (e.g., by returning bounding boxes) within the relevant region.
*   **FR-ANALYZE-012: AI Template Identification Hint (v5.0.0 - Profile Generation):** During plan-step-to-profile-element suggestion, if `ProfileGenerator` (via Gemini) identifies that a visual element is best matched using a template, it MUST be able to indicate this to the GUI to prompt the user for template capture.

## FR-ACTION: Action Execution & Task Orchestration Module

*   **FR-ACTION-001 - FR-ACTION-006:** (Mouse Click, Keyboard Input, Conditional Actions, Log Message, Dynamic Params, Pause Before Action - as is for runtime)
*   **FR-ACTION-007: Execute Gemini-Suggested/Decomposed Actions (v4.0.0 Phase 2+ - Runtime):** (As is - `ActionExecutor` called by `GeminiDecisionModule`)
*   **FR-ACTION-008: User Confirmation for AI-Driven Actions (v4.0.0 Phase 2+ - Runtime):** (As is - for `gemini_perform_task`)
*   **FR-ACTION-009: `gemini_perform_task` Action Type (v4.0.0 Phase 2 & 3 - Runtime):** (As is - with `natural_language_command` parameter)
*   **FR-ACTION-010: Assembling AI-Generated Profile Actions (v5.0.0 - Profile Generation):** The `ProfileGenerator` MUST correctly assemble user-confirmed and AI-assisted action specifications into the standard Mark-I action structure (for `click`, `type_text`, `press_key`, `log_message`, and potentially `gemini_vision_query` or even simpler `gemini_perform_task` as parts of a larger generated automation) within the generated JSON profile.

## FR-CONFIG: Configuration & Management (CLI, GUI, AI Generation)

*   **FR-CONFIG-001 - FR-CONFIG-003:** (Save/Load Profile, Variable Capture, Gemini Settings - as is)
*   **FR-CONFIG-004: Gemini NLU Task Definition in Profile (v4.0.0 Phase 3 - Runtime):** (As is - for `gemini_perform_task` action)
*   **FR-CONFIG-005: AI Profile Generation - Goal Input (v5.0.0):** The system MUST provide a GUI mechanism for users to input a high-level natural language goal and optional initial visual context (e.g., full screenshot, specific application window) to initiate AI-driven profile generation by the `StrategyPlanner`.
*   **FR-CONFIG-006: AI Profile Generation - Interactive Element Definition (v5.0.0):** During AI profile generation, the GUI workflow driven by `ProfileGenerator` MUST interactively prompt the user to:
    *   Confirm, adjust, or manually draw screen regions based on AI suggestions or plan steps.
    *   Name defined regions.
    *   Confirm, modify, or manually specify condition logic and parameters based on AI suggestions or plan steps.
    *   Confirm, modify, or manually specify action logic and parameters based on AI suggestions or plan steps.
    *   Capture template images (and name them) if the AI or user determines a template is necessary for a plan step.
    *   Provide any specific data values (e.g., text to be typed, file paths) that the AI cannot infer for conditions or actions.
*   **FR-CONFIG-007: AI Profile Generation - Output (v5.0.0):** The AI Profile Generation process MUST output a standard, structurally valid Mark-I JSON profile file.
*   **FR-CONFIG-008: AI Profile Generation - Plan Review (v5.0.0 - Optional):** The GUI workflow for AI Profile Generation SHOULD offer an optional step to display the intermediate plan (generated by `StrategyPlanner`) to the user for review before proceeding to interactive element definition.
*   **FR-CONFIG-009: AI Profile Generation - Saving (v5.0.0):** The GUI workflow MUST allow the user to save the generated profile to a user-specified location and filename.

## FR-UI: User Interface

*   **FR-UI-001: CLI Control:** (As is)
*   **FR-UI-002: GUI for Region Definition (Component):** (As is - `RegionSelectorWindow` or similar integrated tool)
*   **FR-UI-003: Full GUI Profile Editor (`MainAppWindow` - v4.0.0 Complete):**
    *   (All sub-points FR-UI-003.1 to FR-UI-003.6 remain as is, reflecting support for all v4.0.0 manual editing capabilities, including `gemini_perform_task` with NLU parameters.)
*   **FR-UI-004: User Feedback (General - v4.0.0 Complete):** (As is - clear feedback for runtime operations, including AI interactions and confirmations)
*   **FR-UI-005: GUI for AI Profile Generation Invocation (v5.0.0):** The `MainAppWindow` MUST provide a clear entry point (e.g., "File > New AI-Generated Profile..." menu item or a dedicated button) to launch the AI Profile Generation workflow/wizard.
*   **FR-UI-006: AI Profile Generation Wizard/Workflow GUI (v5.0.0 - `ProfileCreationWizardWindow`):** A new GUI component (e.g., a top-level window or sequence of views) MUST:
    *   Provide a field for the user to input their high-level automation goal (natural language text).
    *   Provide options for capturing/providing initial visual context (full screen, application window).
    *   (Optional) Display the AI-generated intermediate plan for user review.
    *   Guide the user step-by-step through the process of defining profile elements for each step of the intermediate plan. This includes:
        *   Displaying the current plan step description.
        *   Presenting AI-suggested screen regions on a relevant screenshot, allowing user confirmation, adjustment (e.g., via an integrated region drawing tool), or manual definition.
        *   Prompting for region names.
        *   Presenting AI-suggested condition logic (type, parameters) with editable fields.
        *   Presenting AI-suggested action logic (type, parameters) with editable fields.
        *   If an AI suggestion involves a specific visual element, display candidate bounding boxes (from `ProfileGenerator`'s refinement call) overlaid on the relevant screen image snippet, allowing the user to click and confirm the correct element.
        *   Prompting for template capture if AI or user decides a template is needed for an element.
        *   Prompting for any other necessary parameters (e.g., text values, file paths).
    *   Provide controls like "Next Step," "Previous Step" (if feasible for reviewing/editing), "Accept Suggestion," "Define Manually," "Skip Step."
    *   Display a summary of the generated profile elements before final saving.
    *   Allow saving the generated profile to a `.json` file.
    *   Offer an option to open the newly generated profile in the standard `MainAppWindow` editor for further refinement.
*   **FR-UI-007: Visual Suggestion Display in AI Generation GUI (v5.0.0):** The AI Profile Generation GUI MUST be able to display screen captures (full screen or specific regions) and overlay AI-suggested bounding boxes for regions or specific UI elements, allowing the user to visually confirm or select these suggestions.

---