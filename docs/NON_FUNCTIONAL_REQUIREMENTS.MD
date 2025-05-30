// File: docs/NON_FUNCTIONAL_REQUIREMENTS.MD

# Non-Functional Requirements for Mark-I

This document outlines the non-functional requirements for the Mark-I visual automation tool, describing _how well_ the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor/Generator, as applicable.
**This version reflects requirements for the completed v4.0.0 and incorporates detailed NFRs for v5.0.0: AI-Driven Profile Generation (including its interactive GUI Workflow and AI-Assisted Element Suggestion logic).**

## NFR-PERF: Performance

- **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
- **NFR-PERF-002: Efficient Analysis (Bot Runtime):**
  - **Local Analysis:** Local analysis operations (color, template, OCR, dominant color) SHOULD be computationally efficient, with their total duration per cycle significantly less than the `monitoring_interval_seconds`.
  - **v4.0.0+ (Gemini - Runtime): API Call Latency:** Gemini API calls for `gemini_vision_query` conditions and within `GeminiDecisionModule` for NLU tasks WILL introduce network and model processing latency (target a few seconds per call, but can vary). Logging of API call latency is required.
- **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The `monitoring_interval_seconds` MUST be configurable. Users should be guided that AI-heavy runtime profiles require longer intervals.
- **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD minimize its impact on local system performance (CPU, memory).
- **NFR-PERF-005: Responsive GUI Profile Editor (Manual Editing):** The `MainAppWindow` GUI SHOULD be responsive for manual profile editing, including configuration of Gemini features.
- **NFR-PERF-006: Gemini Decision Module / NLU Task Latency (v4.0.0 - Runtime):** Users MUST be aware that NLU tasks via `gemini_perform_task` involve multiple AI interactions and will have noticeable overall latency. Each AI-assisted step contributes its own API call latency.
- **NFR-PERF-007: AI Profile Generation Performance (v5.0.0 - Profile Generation Workflow):**
  - **Goal-to-Plan Generation (`StrategyPlanner`):** The initial generation of the "intermediate plan" from a user's goal (involving a significant Gemini call) SHOULD complete within an acceptable interactive timeframe (e.g., target 5-20 seconds, dependent on goal complexity and Gemini model responsiveness). The GUI MUST display a clear loading/processing indicator.
  - **Per-Step AI Suggestions (`ProfileGenerator`):** Each call to Gemini for suggesting regions, logic (conditions/actions), or refining element locations during the interactive profile building steps SHOULD also respond within a few seconds (e.g., target 2-10 seconds) to maintain a fluid user experience. Loading indicators for these AI calls in the GUI are necessary.
  - **GUI Responsiveness (Wizard):** The `ProfileCreationWizardWindow` itself (UI interactions, page transitions, displaying suggestions) SHOULD remain responsive and not freeze during AI calls (AI calls should be offloaded from the main GUI thread if they are synchronous SDK calls, or the GUI should be updated via callbacks if async). _Note: Current Gemini SDK is synchronous, so GUI might appear to "hang" during these calls; clear "AI is thinking..." messages are crucial._
  - **Profile Assembly & Saving:** Final assembly of the generated JSON profile and its saving SHOULD be fast (sub-second after user confirmation). Saving of captured template image files should also be efficient.

## NFR-USAB: Usability

- **NFR-USAB-001: Ease of Configuration (GUI Focus - Manual & AI-Assisted):**
  - **(v4.0.0):** Manual profile definition via `MainAppWindow` MUST be intuitive.
  - **(v5.0.0 - AI Profile Generation):** The `ProfileCreationWizardWindow` MUST be highly intuitive, providing clear instructions and guidance at each step. AI suggestions (for plans, regions, logic, elements) MUST be presented clearly, and user controls for accepting, modifying, rejecting suggestions, or manually defining elements MUST be straightforward and easily accessible.
- **NFR-USAB-002: Intuitive Rule/Task Creation & Editing (GUI):** (As is for v4.0.0). **(v5.0.0):** The AI Profile Creator aims to simplify initial profile creation, but users must still understand the generated Mark-I constructs if they wish to refine them. Effective prompt engineering for the initial goal is key.
- **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** (As is for v4.0.0).
  - **(v5.0.0 - AI Profile Generation):**
    - **GUI Feedback:** The Wizard MUST provide continuous feedback: current goal, current plan step, AI processing status ("AI thinking...", "AI suggested X..."), results of AI suggestions, and clear prompts for user input or confirmation. Visual overlays for suggested regions/elements must be unambiguous.
    - **Logging:** Comprehensive logs for the entire generation process (goal, plan, per-step suggestions, user choices, errors).
- **NFR-USAB-004: Interruptibility (Bot Runtime & AI Generation):** (As is for Runtime). **(v5.0.0):** The AI Profile Generation wizard SHOULD be cancellable by the user at any point, discarding any partially generated profile data cleanly.
- **NFR-USAB-005: Configuration Clarity (JSON & GUI):** (As is). AI-generated profiles (v5.0.0) MUST adhere to the standard, human-readable Mark-I JSON schema.
- **NFR-USAB-006: GUI Input Validation & Error Prevention:** (As is for `MainAppWindow`). **(v5.0.0):** The `ProfileCreationWizardWindow` MUST validate user inputs (e.g., goal text not empty, region names, template names).
- **NFR-USAB-007: GUI State Management:** (As is for `MainAppWindow`). **(v5.0.0):** The `ProfileCreationWizardWindow` MUST reliably manage its state across multiple pages and user interactions. "Previous" button functionality should ideally restore user inputs for the prior step.
- **NFR-USAB-008: API Key Management (v4.0.0+):** (As is). Wizard should not proceed if API key is invalid/missing.
- **NFR-USAB-009: Cost and Usage Awareness (v4.0.0+):** (As is). Users should be aware that AI Profile Generation (v5.0.0) will also incur Gemini API costs for planning and suggestion calls.
- **NFR-USAB-010: Documentation for Advanced Features (v4.0.0+):**
  - **(v5.0.0 Addition):** Documentation MUST thoroughly explain the AI Profile Generation feature: how to effectively state automation goals for `StrategyPlanner`, how the interactive `ProfileGenerator` workflow functions, how to interpret and interact with AI suggestions for regions/logic/elements, how to perform template capture within the wizard, and the expected nature/quality of AI-generated profiles (i.e., good starting points needing review).
- **NFR-USAB-011: Clarity of AI-Driven Actions/Suggestions:** (As is for Runtime). **(v5.0.0 - Profile Generation):** AI's suggestions for plans and profile elements during generation MUST be presented clearly in the GUI. Reasoning from AI (if provided) should be shown.
- **NFR-USAB-012: AI Profile Generation - User Control & Iteration (v5.0.0):** Users MUST have primary control. They MUST be able to easily review, accept, modify, or reject AI suggestions for plan steps, regions, conditions, actions, and templates. The system MUST allow users to manually define elements if AI suggestions are unsatisfactory. The process should feel collaborative, not fully prescriptive by the AI.
- **NFR-USAB-013: AI Profile Generation - Output Expectations (v5.0.0):** Users should be informed (e.g., via UI text, documentation) that AI-generated profiles are powerful starting points but may require manual review and refinement in the standard editor for optimal performance and robustness, especially for complex tasks.

## NFR-ACCU: Accuracy

- **NFR-ACCU-001: Precise Region Capture:** (As is).
- **NFR-ACCU-002: Reliable Analysis Results (Local & AI Query - Runtime):** (As is).
- **NFR-ACCU-003: Consistent Action Execution (Runtime):** (As is).
- **NFR-ACCU-004: Gemini Decision & NLU Accuracy (v4.0.0 - Runtime):** (As is).
- **NFR-ACCU-005: AI-Generated Profile Quality & Relevance (v5.0.0 - Profile Generation):**
  - The AI-generated "intermediate plan" by `StrategyPlanner` SHOULD be logical, coherent, and relevant to the user's goal. The steps should be decomposable into Mark-I primitives.
  - AI-suggested profile elements (regions, conditions, actions, template needs) by `ProfileGenerator` during the interactive phase SHOULD be contextually relevant and accurate given the plan step and visual information.
  - The final AI-generated Mark-I JSON profile SHOULD be structurally valid and represent a functionally plausible "first draft" implementation of the user's stated goal. The accuracy of specific parameters (e.g., OCR keywords, template confidence, precise coordinates not refined by user) will depend on AI's suggestion quality and requires user validation.

## NFR-REL: Reliability & Robustness (System-Wide)

- **NFR-REL-001: Stable Operation:** Bot runtime, GUI editor, and **(v5.0.0) AI Profile Generation wizard** SHOULD operate stably.
- **NFR-REL-002: Graceful Error Handling:** (As is for Runtime). **(v5.0.0 - AI Profile Generation):** `StrategyPlanner` and `ProfileGenerator` (and the wizard GUI) MUST gracefully handle API errors, timeouts, invalid/unexpected AI responses (e.g., malformed JSON for plans or suggestions), or situations where AI cannot provide a useful suggestion. The user should be informed, and the wizard should allow retries, manual overrides, or clean cancellation.
- **NFR-REL-003: Data Integrity (Profile Saving):** (As is). **(v5.0.0):** The AI Profile Generator MUST save structurally valid JSON profiles and correctly save associated template image files.
- **NFR-REL-004: Resource Management:** (As is). Profile generation involving multiple AI calls and image processing should manage memory effectively.
- **NFR-REL-005: Internet Connectivity (v4.0.0+):** (As is - applies to all Gemini interactions).
- **NFR-REL-006: Gemini Decision Module & NLU Robustness (v4.0.0 - Runtime):** (As is).
- **NFR-REL-007: AI Profile Generation Workflow Robustness (v5.0.0):** The interactive profile generation wizard MUST remain stable and responsive. It should not crash due to unexpected AI outputs. Users should be able to complete the workflow even if some AI suggestions are skipped or manually overridden. The process should be resumable if possible (advanced future NFR).

## NFR-MAINT: Maintainability

- **NFR-MAINT-001: Modular Code:** (As is). **(v5.0.0): New modules in `mark_i.generation` and `mark_i.ui.gui.generation` MUST be well-encapsulated, with clear interfaces and responsibilities.**
- **NFR-MAINT-002: Code Clarity & Documentation:** (As is). Design for AI Profile Generation covered by ADR-009 and `TECHNICAL_DESIGN.MD` Section 15. All new code needs thorough docstrings.
- **NFR-MAINT-003: Testability:** (As is). Logic in `StrategyPlanner` and `ProfileGenerator` (including AI interaction points) MUST be designed for unit and integration testing, likely requiring extensive mocking of `GeminiAnalyzer`.
- **NFR-MAINT-004: Diagnosability:** (As is). Comprehensive logging for the AI Profile Generation process is critical.

## NFR-SEC: Security

- **NFR-SEC-001 - NFR-SEC-005:** (User Control, Data Transmission, Secure Config, API Key, Privacy for External API calls - as is, principles apply with added emphasis for profile generation context if full screen images are sent).
- **NFR-SEC-006: Control over AI-Suggested/NLU-Driven Actions (v4.0.0 - Runtime):** (As is).
- **NFR-SEC-007: Security of AI-Generated Profiles (v5.0.0 - Profile Generation):**
  - The AI Profile Generator MUST NOT generate or embed malicious code or unsafe system commands into the output JSON profile. Generated elements must map to Mark-I's standard, safe primitives.
  - Users are responsible for reviewing any AI-generated profile before execution.
  - If full screen context is used for AI suggestions, documentation should remind users about potential privacy implications of this broader visual context being sent to the API.

## NFR-CONF: Configurability

- **NFR-CONF-001 - NFR-CONF-005:** (Profile Config, Logging, Loop Interval, Analysis Params, Gemini Decision Task Config - as is).
- **NFR-CONF-006: AI Profile Generation - Goal Input (v5.0.0):** Users MUST be able to provide their high-level goal as natural language text and optionally provide initial visual screen context.
- **NFR-CONF-007: AI Profile Generation - Model Selection (v5.0.0 - Future Consideration):** Potentially allow user selection of different Gemini models for planning vs. visual suggestion stages. (Initial v5.0.0 uses predefined defaults in `ProfileGenerator`).
- **NFR-CONF-008: AI Profile Generation - Interactivity Levels (v5.0.0 - Future Consideration):** (As is - initial v5.0.0 is confirm-heavy).
- **NFR-CONF-009: AI Profile Generation - Template Save Path (v5.0.0):** Template images captured during AI profile generation MUST be saved into a `templates` subdirectory relative to the location where the user chooses to save the generated `.json` profile file.

---
