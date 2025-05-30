# Functional Requirements for Mark-I

This document outlines the functional requirements for the Mark-I visual automation tool, describing *what* the system will do.
**This version reflects the completed capabilities of v4.0.0 (including all Gemini integration phases) and incorporates requirements for the planned v5.0.0 feature: AI-Driven Profile Generation.**

## FR-CORE: Core System

*   **FR-CORE-001: Cross-Platform Operation:** The bot's core runtime engine and GUI editor SHOULD operate on Windows, macOS, and Linux. (Primary development and testing on Windows).
*   **FR-CORE-002: Configuration Files (JSON):** The system MUST use JSON for saving and loading bot configurations (profiles). These profiles MUST store all necessary data for bot operation, including settings, region definitions, template metadata, and rule definitions (conditions and actions with their parameters, including complex AI-driven action types like `gemini_perform_task`).
*   **FR-CORE-003: Environment Configuration:** The system MUST read environment variables (e.g., from `.env` file) for `APP_ENV` (logging control) and sensitive data like `GEMINI_API_KEY`.
*   **FR-CORE-004: Logging:** The system MUST implement comprehensive, persistent, and configurable logging for all significant operations, decisions, errors, AI interactions (Gemini API calls for queries, NLU, decision-making, and profile generation assistance), and state changes.

## FR-CAPTURE: Screen Region Capture Module (Bot Runtime & Profile Generation)

*   **FR-CAPTURE-001: Define Target Region:** The user MUST be able to define one or more named rectangular regions on the screen (x, y, width, height) to be monitored or analyzed. This definition is stored in the profile and manageable via the GUI.
*   **FR-CAPTURE-002: Capture Specified Region:** The system MUST be able to capture image data exclusively from user-defined target region(s) during bot runtime.
*   **FR-CAPTURE-003: Real-time Capture (Bot Runtime):** The system MUST support continuous real-time capture of defined regions at a user-configurable interval.
*   **FR-CAPTURE-004: Full Screen Capture (for AI Profile Generation - v5.0.0):** The system (specifically for the AI Profile Generation mode) MUST be able to capture an image of the full screen (or a user-selected application window) to provide initial visual context to the `StrategyPlanner` and `ProfileGenerator` AI components.

## FR-ANALYZE: Region Analysis & AI Understanding Module

*   **FR-ANALYZE-001: Pixel Color Analysis:** Rules/conditions MUST support checking specific pixel colors (BGR) with tolerance.
*   **FR-ANALYZE-001B: Average Color Analysis:** Rules/conditions MUST support checking the average color (BGR) of a region with tolerance.
*   **FR-ANALYZE-002: Template Matching Analysis:** Rules/conditions MUST support checking for template image presence with a confidence threshold. Match details MUST be capturable.
*   **FR-ANALYZE-003: OCR Text Extraction & Analysis:** System MUST extract text from regions using Tesseract. Results MUST include text and average confidence. Text MUST be capturable.
*   **FR-ANALYZE-003B: OCR-Based Conditions:** Rules MUST support conditions based on OCR text content and confidence.
*   **FR-ANALYZE-004: Configurable Analysis Rules (Runtime):** Users MUST define rules linking analysis outcomes to actions, supporting single and compound (AND/OR) conditions.
*   **FR-ANALYZE-005: Dominant Color Analysis:** Rules/conditions MUST support checking dominant colors and their percentage.
*   **FR-ANALYZE-006: Selective Local Analysis (Performance - Runtime):** `MainController` MUST optimize by only running specific local analyses if an active rule requires it.
*   **FR-ANALYZE-007: Gemini Vision Query (v4.0.0 Phase 1+ - Runtime):** The `gemini_vision_query` condition type MUST allow rules to send image data and a text prompt to Gemini, evaluate responses (text/JSON), and capture results.
*   **FR-ANALYZE-008: Gemini-Informed Action Suggestion (v4.0.0 Phase 2 - Runtime):** The `GeminiDecisionModule` (invoked by `gemini_perform_task` action) MUST accept a user goal, use `GeminiAnalyzer` to suggest a primitive action from a predefined set, validate it, and refine targets using vision if needed.
*   **FR-ANALYZE-009: Natural Language Command Understanding & Decomposition (v4.0.0 Phase 3 - Runtime):** The `GeminiDecisionModule` (invoked by `gemini_perform_task` action with `natural_language_command`) MUST:
    *   Parse the natural language command into a structured plan (sequence of sub-steps/intents) using `GeminiAnalyzer`.
    *   Decompose this plan into executable primitive steps, validating against allowed actions.
    *   Manage basic state and orchestrate the execution of these steps.
*   **FR-ANALYZE-010: AI Goal-to-Plan Generation (v5.0.0 - Profile Generation):** The `StrategyPlanner` module MUST:
    *   Accept a high-level user goal (natural language) and optional initial visual context.
    *   Use `GeminiAnalyzer` to prompt Gemini to break down this goal into an "intermediate plan" (a sequence of logical, human-understandable sub-steps relevant to achieving the automation goal).
    *   Parse and validate this intermediate plan.
*   **FR-ANALYZE-011: AI Plan-Step-to-Profile-Element Suggestion (v5.0.0 - Profile Generation):** The `ProfileGenerator` module, for each step in the intermediate plan, MUST:
    *   Use `GeminiAnalyzer` (with current screen context) to suggest relevant screen regions for the step.
    *   Use `GeminiAnalyzer` to suggest appropriate Mark-I condition types (e.g., OCR, template, `gemini_vision_query`) and potential parameters to implement the logic of the plan step.
    *   Use `GeminiAnalyzer` to suggest appropriate Mark-I action types and potential parameters.
    *   If an interaction with a specific UI element is implied by a plan step, use `GeminiAnalyzer` to visually suggest candidate elements on screen (e.g., by highlighting or returning bounding boxes).

## FR-ACTION: Action Execution & Task Orchestration Module

*   **FR-ACTION-001: Mouse Click Simulation:** System MUST simulate mouse clicks with various options (button, count, interval) at targets including absolute coords, region-relative, template-relative, and **Gemini-identified element coordinates (v4.0.0 Phase 1.5+)**.
*   **FR-ACTION-002: Keyboard Input Simulation:** System MUST simulate typing text strings, pressing special keys, and hotkeys.
*   **FR-ACTION-003: Conditional Actions (Runtime):** Actions defined in rules MUST only trigger if their associated rule's condition evaluates to true.
*   **FR-ACTION-004: Log Message Action:** System MUST provide an action to write custom messages to logs.
*   **FR-ACTION-005: Dynamic Action Parameters (Variables - Runtime):** Action parameters MUST support variable substitution using values captured from conditions.
*   **FR-ACTION-006: Configurable Pause Before Action (Runtime):** Actions MUST allow a configurable pause before execution.
*   **FR-ACTION-007: Execute Gemini-Suggested/Decomposed Actions (v4.0.0 Phase 2+ - Runtime):** `ActionExecutor` MUST execute primitive actions as instructed by `GeminiDecisionModule` (which validates and refines them from Gemini's suggestions or NLU-decomposed steps).
*   **FR-ACTION-008: User Confirmation for AI-Driven Actions (v4.0.0 Phase 2+ - Runtime):** `GeminiDecisionModule` MUST support an option (`require_confirmation_per_step`) to prompt for user confirmation before executing each AI-decided/NLU-derived action step.
*   **FR-ACTION-009: `gemini_perform_task` Action Type (v4.0.0 Phase 2 & 3 - Runtime):** This action type MUST trigger `GeminiDecisionModule` to process either a simple `goal_prompt` or a `natural_language_command`, orchestrating AI-driven task execution.
*   **FR-ACTION-010: Assembling AI-Generated Profile Actions (v5.0.0 - Profile Generation):** The `ProfileGenerator` MUST assemble confirmed and user-refined action specifications (based on AI suggestions for plan steps) into the standard Mark-I action structure within the generated JSON profile.

## FR-CONFIG: Configuration & Management (CLI, GUI, AI Generation)

*   **FR-CONFIG-001: Save/Load Bot Profile:** Users MUST be able to save/load complete bot profiles (JSON).
*   **FR-CONFIG-002: Variable Capture in Rules:** Conditions MUST support capturing results into rule-scoped variables.
*   **FR-CONFIG-003: Gemini Settings Management (v4.0.0+):** Manage `GEMINI_API_KEY` (via `.env`) and `gemini_default_model_name` (in profile settings).
*   **FR-CONFIG-004: Gemini NLU Task Definition in Profile (v4.0.0 Phase 3):** Users MUST be able to define NLU-driven tasks using the `gemini_perform_task` action and its parameters (`natural_language_command`, `context_region_names`, etc.) via GUI and JSON.
*   **FR-CONFIG-005: AI Profile Generation - Goal Input (v5.0.0):** The system MUST provide a mechanism (initially GUI) for users to input a high-level natural language goal to initiate AI-driven profile generation.
*   **FR-CONFIG-006: AI Profile Generation - Interactive Element Definition (v5.0.0):** During AI profile generation, the system MUST interactively prompt the user to:
    *   Confirm, adjust, or draw screen regions suggested by the AI for plan steps.
    *   Confirm or modify AI-suggested condition logic and parameters.
    *   Confirm or modify AI-suggested action logic and parameters.
    *   Capture template images if the AI plan suggests a template is necessary and the user agrees.
    *   Provide any specific data values (e.g., text to type) that the AI cannot infer.
*   **FR-CONFIG-007: AI Profile Generation - Output (v5.0.0):** The AI Profile Generation process MUST output a standard, valid Mark-I JSON profile file that can be loaded, edited, and run by the existing system.

## FR-UI: User Interface

*   **FR-UI-001: CLI Control:** Provide CLI for running profiles, launching editor. **(v5.0.0 Consideration):** Potentially a CLI command to trigger AI profile generation.
*   **FR-UI-002: GUI for Region Definition (Component):** `RegionSelectorWindow` for visual region selection.
*   **FR-UI-003: Full GUI Profile Editor (`MainAppWindow` - v4.0.0 Complete):**
    *   **FR-UI-003.1 - FR-UI-003.4:** (Profile ops, Settings, Region Mgmt, Template Mgmt - as is).
    *   **FR-UI-003.5: Rule Management & Editing (Comprehensive):** Support for all condition types (including `gemini_vision_query`) and action types (including `gemini_perform_task` with all its NLU parameters like `natural_language_command`).
    *   **FR-UI-003.6: Input Validation & Feedback:** (As is).
*   **FR-UI-004: User Feedback (General - v4.0.0 Complete):** Clear feedback for operations, including AI interactions. Confirmation dialogs for AI-driven steps if configured.
*   **FR-UI-005: GUI for AI Profile Generation Invocation (v5.0.0):** The `MainAppWindow` MUST provide a clear way to initiate the AI Profile Generation mode (e.g., menu item "File > New AI-Generated Profile...").
*   **FR-UI-006: AI Profile Generation Wizard/Workflow (v5.0.0):** A new set of GUI views or a wizard-like interface MUST guide the user through the AI-driven profile generation process:
    *   Input for high-level goal.
    *   (Optional) Display of AI-generated intermediate plan for review.
    *   Interactive prompts for each plan step, allowing the user to confirm/adjust AI-suggested regions (potentially using an embedded `RegionSelector`-like tool), condition logic, action logic, and provide necessary parameters or capture templates.
    *   Mechanism to review the constructed profile elements before final generation.
    *   Option to save the generated profile.
*   **FR-UI-007: Visual Suggestion Display (v5.0.0 - AI Profile Generation):** During interactive element definition, if the AI suggests visual targets (e.g., candidate bounding boxes for a button), the GUI MUST be able to overlay these suggestions on a relevant screen capture to allow the user to select or confirm.

---