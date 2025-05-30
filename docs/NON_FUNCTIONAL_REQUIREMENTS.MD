# Non-Functional Requirements for Mark-I

This document outlines the non-functional requirements for the Mark-I visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor/Generator, as applicable.
**This version reflects requirements for the completed v4.0.0 and incorporates NFRs for the planned v5.0.0 feature: AI-Driven Profile Generation.**

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):**
    *   **Local Analysis:** Local analysis operations SHOULD be computationally efficient. The total duration of these local analyses for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds`.
    *   **v4.0.0+ (Gemini - Runtime): API Call Latency:** Gemini API calls for `gemini_vision_query` conditions and within `GeminiDecisionModule` for NLU tasks WILL introduce network and model processing latency (potentially several seconds per call). Logging of API call latency is required.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The `monitoring_interval_seconds` MUST be configurable to balance responsiveness and system load, especially considering AI API latencies.
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on local system performance (CPU, memory). Gemini API calls primarily add network load.
*   **NFR-PERF-005: Responsive GUI Profile Editor (Manual Editing):** The `MainAppWindow` GUI (for manual profile editing) SHOULD load and save profiles in a timely manner and user interactions SHOULD feel responsive. Configuration of Gemini-related parameters in the GUI should not introduce significant performance lag.
*   **NFR-PERF-006: Gemini Decision Module / NLU Task Latency (v4.0.0 Phase 2 & 3 - Runtime):** Users MUST be aware that NLU tasks via `gemini_perform_task` involve multiple AI interactions and will have noticeable overall latency. Each AI-assisted step will contribute its own API call latency.
*   **NFR-PERF-007: AI Profile Generation Performance (v5.0.0 - Profile Generation):**
    *   The "Goal to Intermediate Plan" generation by `StrategyPlanner` (involving a Gemini call) SHOULD complete within a reasonable interactive timeframe (e.g., target < 10-30 seconds for typical goals, dependent on Gemini model and complexity). Users should be provided feedback (e.g., loading indicator) during this process.
    *   Each interactive step in the `ProfileGenerator`'s GUI workflow where AI suggests regions, conditions, or actions (involving Gemini calls for visual analysis or suggestion) SHOULD also respond within a few seconds to maintain user engagement and a fluid experience.
    *   The final assembly of the JSON profile from gathered elements SHOULD be fast (sub-second).
    *   Screen capture operations performed during profile generation for context SHOULD be efficient.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus - Manual & AI-Assisted):**
    *   **(v4.0.0):** Defining all aspects of a bot profile manually via `MainAppWindow` GUI MUST be intuitive.
    *   **(v5.0.0 - AI Profile Generation):** The AI-Driven Profile Generation workflow (wizard) MUST be highly intuitive and effectively guide the user through goal input, plan review (if offered), and the interactive definition/confirmation of profile elements (regions, conditions, actions, templates). AI's suggestions MUST be clearly presented, and user controls for accepting, modifying, or rejecting suggestions MUST be straightforward.
*   **NFR-USAB-002: Intuitive Rule/Task Creation & Editing (GUI):** GUI MUST present rule structures, NLU task parameters, and AI suggestions in a clear, organized manner. Users must understand that effective prompt engineering is key for all Gemini features (runtime queries/tasks and v5.0.0 profile generation assistance).
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** System MUST provide clear, timely, actionable feedback.
    *   **(v4.0.0 - Gemini Runtime):** Logs MUST detail Gemini API calls for queries and NLU tasks. GUI provides API key status.
    *   **(v5.0.0 - AI Profile Generation):**
        *   **GUI Feedback:** The Profile Generation Wizard MUST provide clear visual feedback on the current stage (e.g., "AI is generating plan...", "Review suggested region for step X", "Confirm action for step Y"). It should display AI suggestions clearly, allowing easy comparison with alternatives or manual input.
        *   **Logging:** Logs MUST detail the goal-to-plan generation process, AI suggestions for profile elements during interactive steps, user interactions/confirmations, and the final generated profile structure.
*   **NFR-USAB-004: Interruptibility (Bot Runtime & AI Generation):** Users MUST be able to easily start/stop the bot's runtime monitoring loop. **(v5.0.0):** The AI Profile Generation process (both plan generation and interactive step definition) SHOULD be cancellable by the user at any stage without corrupting existing data or leaving the application in an unstable state.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** JSON profiles (manually created or AI-generated for v5.0.0) SHOULD be human-readable and well-documented. The schema for all features MUST be clear.
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** GUI (for manual editing and AI generation workflow) MUST implement robust input validation for user-provided data.
*   **NFR-USAB-007: GUI State Management:** GUI MUST reliably manage its internal state during complex operations like AI profile generation.
*   **NFR-USAB-008: API Key Management (v4.0.0+):** (As is - clear documentation, GUI status).
*   **NFR-USAB-009: Cost and Usage Awareness (v4.0.0+):** (As is - inform users about Gemini API costs).
*   **NFR-USAB-010: Documentation for Advanced Features (v4.0.0+):**
    *   **(v4.0.0):** Comprehensive documentation for `gemini_vision_query`, `gemini_perform_task` (NLU commands), prompt engineering.
    *   **(v5.0.0 Addition):** Documentation MUST thoroughly explain the AI Profile Generation feature: how to state goals effectively for `StrategyPlanner`, how the interactive `ProfileGenerator` workflow functions, how to interpret and refine AI suggestions, and the expected quality/limitations of AI-generated profiles.
*   **NFR-USAB-011: Clarity of AI-Driven Actions/Suggestions:**
    *   **(v4.0.0 - Runtime):** (As is - logs and optional confirmations for `GeminiDecisionModule`).
    *   **(v5.0.0 - Profile Generation):** AI's suggestions for plans and profile elements MUST be presented clearly in the GUI for user validation. The generated profile should be understandable and editable.
*   **NFR-USAB-012: AI Profile Generation - User Control & Iteration (v5.0.0):** Users MUST have primary control during AI-assisted profile generation. They MUST be able to easily review, accept, modify, or reject AI suggestions for plan steps, regions, conditions, and actions. The system should support an iterative process where the user can refine inputs or choices if initial AI suggestions are not optimal. The generated profile is a starting point, editable by the user.

## NFR-ACCU: Accuracy

*   **NFR-ACCU-001: Precise Region Capture:** (As is).
*   **NFR-ACCU-002: Reliable Analysis Results (Local & AI Query - Runtime):** (As is).
*   **NFR-ACCU-003: Consistent Action Execution (Runtime):** (As is).
*   **NFR-ACCU-004: Gemini Decision & NLU Accuracy (v4.0.0 - Runtime):** (As is - depends on AI/prompt, non-deterministic).
*   **NFR-ACCU-005: AI-Generated Profile Quality & Relevance (v5.0.0 - Profile Generation):**
    *   The AI-generated "intermediate plan" by `StrategyPlanner` SHOULD be logical, relevant to the user's goal, and decomposable into actionable steps for Mark-I.
    *   AI-suggested profile elements (regions, conditions, actions) by `ProfileGenerator` during the interactive phase SHOULD be contextually relevant to the current plan step and the visual information on screen.
    *   The final AI-generated Mark-I JSON profile SHOULD be structurally valid and represent a functionally plausible (though not necessarily perfect or optimal) implementation of the user's stated goal. The expectation is a "strong first draft" that significantly accelerates profile creation. The accuracy of specific parameters (e.g., exact OCR text to find, precise template match thresholds) will heavily depend on the interactive refinement by the user.

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Bot runtime, GUI editor, and **(v5.0.0) AI Profile Generation workflow** SHOULD operate stably.
*   **NFR-REL-002: Graceful Error Handling:** System MUST handle errors gracefully.
    *   **(v4.0.0+ - Gemini Runtime):** (As is - robust handling of API errors for queries and NLU tasks).
    *   **(v5.0.0 - AI Profile Generation):** `StrategyPlanner` and `ProfileGenerator` MUST gracefully handle Gemini API errors during plan/suggestion generation (e.g., network issues, rate limits, content filtering), invalid or unexpected AI responses, or situations where a sensible profile element cannot be suggested. The GUI workflow should reflect these errors to the user and allow them to retry, modify input, define manually, or cancel.
*   **NFR-REL-003: Data Integrity (Profile Saving):** GUI editor and **(v5.0.0) AI Profile Generator** MUST save structurally valid JSON profiles.
*   **NFR-REL-004: Resource Management:** Application should manage resources effectively.
*   **NFR-REL-005: Internet Connectivity (v4.0.0+):** All Gemini-dependent features (runtime and profile generation) REQUIRE an active internet connection.
*   **NFR-REL-006: Gemini Decision Module & NLU Robustness (v4.0.0 - Runtime):** (As is).
*   **NFR-REL-007: AI Profile Generation Workflow Robustness (v5.0.0):** The interactive profile generation process MUST remain stable and usable even if some AI suggestions are imperfect, rejected by the user, or if Gemini fails to provide suggestions for certain steps. Users should be able to complete the workflow by manually defining elements where AI assistance falls short. The system should not crash due to unexpected AI output during suggestion phases.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** (As is). **(v5.0.0): New modules in `mark_i.generation` (`StrategyPlanner`, `ProfileGenerator`) and new GUI components for profile generation MUST be well-encapsulated and testable.**
*   **NFR-MAINT-002: Code Clarity & Documentation:** (As is). Design for AI Profile Generation covered by ADR-009 and `TECHNICAL_DESIGN.MD` Section 15.
*   **NFR-MAINT-003: Testability:** (As is). Gemini interactions within `StrategyPlanner` and `ProfileGenerator` MUST be mockable for testing their logic.
*   **NFR-MAINT-004: Diagnosability:** (As is). Logging for the AI Profile Generation process is critical.

## NFR-SEC: Security

*   **NFR-SEC-001 - NFR-SEC-005:** (User Control, Data Transmission, Secure Config, API Key, Privacy for External API calls - as is, principles apply to profile generation context too).
*   **NFR-SEC-006: Control over AI-Suggested/NLU-Driven Actions (v4.0.0 - Runtime):** (As is).
*   **NFR-SEC-007: Security of AI-Generated Profiles (v5.0.0 - Profile Generation):**
    *   The AI Profile Generator (`StrategyPlanner` and `ProfileGenerator`) MUST NOT generate or embed malicious code, arbitrary system commands, or unsafe constructs into the output JSON profile. The generated profile elements MUST map to Mark-I's standard, safe, and validated internal condition and action types.
    *   The system primarily uses AI to suggest structure and identify elements; the user provides/confirms specific data (like text to type) and validates the overall logic.
    *   Users are ultimately responsible for reviewing and validating any AI-generated profile before execution, as with any automation script, especially if sensitive operations are involved.

## NFR-CONF: Configurability

*   **NFR-CONF-001 - NFR-CONF-005:** (Profile Config, Logging, Loop Interval, Analysis Params, Gemini Decision Task Config - as is).
*   **NFR-CONF-006: AI Profile Generation - Goal Input (v5.0.0):** Users MUST be able to provide their high-level goal as natural language text and optionally provide initial visual screen context to the AI Profile Generation system.
*   **NFR-CONF-007: AI Profile Generation - Model Selection (v5.0.0 - Future Consideration):** Potentially allow users to select different Gemini models for the `StrategyPlanner` (plan generation) vs. `ProfileGenerator` (element suggestion/refinement) stages if performance/capability trade-offs are significant and warrant such user control. (Initial v5.0.0 may use fixed powerful models for planning and flexible models for visual assist).
*   **NFR-CONF-008: AI Profile Generation - Interactivity Levels (v5.0.0 - Future Consideration):** Future versions might allow users to configure the "level of AI assistance" or "degree of user confirmation required" during profile generation (e.g., "Max AI Assist - try to auto-confirm more" vs. "Highly Guided - confirm every detail"). Initial v5.0.0 will focus on a user-centric, interactive, confirm-heavy model for safety and reliability.

---