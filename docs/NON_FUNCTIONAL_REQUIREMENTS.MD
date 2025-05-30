# Non-Functional Requirements for Mark-I

This document outlines the non-functional requirements for the Mark-I visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor/Generator, as applicable.
**This version reflects requirements for the completed v4.0.0 and incorporates NFRs for the planned v5.0.0 feature: AI-Driven Profile Generation.**

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):**
    *   **Local Analysis:** Local analysis operations SHOULD be computationally efficient. The total duration of these local analyses for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds`.
    *   **v4.0.0 (Gemini - Runtime): API Call Latency:** Gemini API calls for `gemini_vision_query` conditions and within `GeminiDecisionModule` for NLU tasks WILL introduce network and model processing latency (potentially several seconds per call). Logging of API call latency is required.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The `monitoring_interval_seconds` MUST be configurable to balance responsiveness and system load, especially considering AI API latencies.
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on local system performance (CPU, memory). Gemini API calls primarily add network load.
*   **NFR-PERF-005: Responsive GUI Profile Editor:** The `MainAppWindow` GUI (for manual profile editing) SHOULD load and save profiles in a timely manner and user interactions SHOULD feel responsive.
*   **NFR-PERF-006: Gemini Decision Module / NLU Task Latency (v4.0.0 Phase 2 & 3 - Runtime):** Users MUST be aware that NLU tasks via `gemini_perform_task` involve multiple AI interactions and will have noticeable overall latency. Each AI-assisted step will contribute its own API call latency.
*   **NFR-PERF-007: AI Profile Generation Performance (v5.0.0 - Profile Generation):**
    *   The "Goal to Intermediate Plan" generation by `StrategyPlanner` (involving a Gemini call) SHOULD complete within a reasonable time (e.g., target < 10-30 seconds, model dependent) for typical goals.
    *   Each interactive step in the `ProfileGenerator` workflow where AI suggests regions, conditions, or actions (involving Gemini calls) SHOULD also respond within a few seconds to maintain user engagement.
    *   The final assembly of the JSON profile SHOULD be fast.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus - Manual & AI-Assisted):**
    *   **(v4.0.0):** Defining all aspects of a bot profile manually via `MainAppWindow` GUI MUST be intuitive.
    *   **(v5.0.0 - AI Profile Generation):** The AI-Driven Profile Generation workflow MUST be intuitive and guide the user effectively through goal input, plan review (optional), and interactive definition/confirmation of profile elements (regions, conditions, actions, templates). The AI's suggestions should be clearly presented.
*   **NFR-USAB-002: Intuitive Rule/Task Creation & Editing (GUI):** GUI MUST present rule structures, NLU task parameters, and AI suggestions in a clear, organized manner. Users must understand that effective prompt engineering is key for all Gemini features.
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** System MUST provide clear, timely, actionable feedback via console, GUI dialogs/status, and comprehensive logs.
    *   **(v4.0.0 - Gemini Runtime):** Logs MUST detail Gemini API calls for queries and NLU tasks.
    *   **(v5.0.0 - AI Profile Generation):** Logs MUST detail the goal-to-plan generation process, AI suggestions for profile elements, and user interactions/confirmations during AI-assisted profile creation. GUI should clearly indicate current stage of AI generation.
*   **NFR-USAB-004: Interruptibility (Bot Runtime & AI Generation):** Users MUST be able to easily start/stop the bot's monitoring loop. **(v5.0.0):** The AI Profile Generation process SHOULD be cancellable by the user at various stages.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** JSON profiles (manually created or AI-generated) SHOULD be human-readable and well-documented. The schema for all features MUST be clear.
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** GUI (for manual editing and AI generation workflow) MUST implement robust input validation.
*   **NFR-USAB-007: GUI State Management:** GUI MUST reliably manage its internal state.
*   **NFR-USAB-008: API Key Management (v4.0.0+):** Process for `GEMINI_API_KEY` setup MUST be clearly documented. GUI MUST show API key status.
*   **NFR-USAB-009: Cost and Usage Awareness (v4.0.0+):** Users MUST be clearly informed about potential Gemini API costs.
*   **NFR-USAB-010: Documentation for Advanced Features (v4.0.0+):** Comprehensive documentation MUST guide users on `gemini_vision_query`, `gemini_perform_task` (NLU commands), prompt engineering, and **(v5.0.0) the AI Profile Generation feature, including how to state goals effectively.**
*   **NFR-USAB-011: Clarity of AI-Driven Actions/Suggestions:**
    *   **(v4.0.0 - Runtime):** When `GeminiDecisionModule` acts, logs (and optional confirmations) must clarify AI's role.
    *   **(v5.0.0 - Profile Generation):** AI's suggestions for plans and profile elements MUST be presented clearly to the user for validation. The generated profile should be understandable.
*   **NFR-USAB-012: AI Profile Generation - User Control (v5.0.0):** Users MUST have the ability to review, accept, modify, or reject AI suggestions at each significant step of the profile generation process (e.g., region definition, condition logic, action parameters). The generated profile is a starting point.

## NFR-ACCU: Accuracy

*   **NFR-ACCU-001: Precise Region Capture:** Captured image data MUST accurately correspond to user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results (Local & AI Query):** Local analysis SHOULD be accurate. `gemini_vision_query` accuracy depends on AI model and prompt.
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered SHOULD be performed reliably by `ActionExecutor`.
*   **NFR-ACCU-004: Gemini Decision & NLU Accuracy (v4.0.0 Phase 2 & 3 - Runtime):** Accuracy of AI-suggested actions and NLU parsing depends on Gemini and prompt quality. Non-deterministic. Safety boundaries are key.
*   **NFR-ACCU-005: AI-Generated Profile Quality (v5.0.0 - Profile Generation):**
    *   The AI-generated "intermediate plan" SHOULD be a logical and plausible sequence of steps to achieve the user's high-level goal.
    *   AI-suggested profile elements (regions, conditions, actions) during the interactive generation phase SHOULD be relevant to the current plan step and the visual context.
    *   The final AI-generated Mark-I JSON profile SHOULD be structurally valid and represent a reasonable attempt to implement the user's goal. It is expected to be a "good starting point" requiring user review and potential refinement, not necessarily a perfect, immediately runnable solution for highly complex goals.

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Bot runtime, GUI editor, and **(v5.0.0) AI Profile Generation workflow** SHOULD operate stably.
*   **NFR-REL-002: Graceful Error Handling:** System MUST handle errors gracefully.
    *   **(v4.0.0+ - Gemini Runtime):** Robust handling of Gemini API errors for queries and NLU tasks.
    *   **(v5.0.0 - AI Profile Generation):** `StrategyPlanner` and `ProfileGenerator` MUST gracefully handle API errors during plan/suggestion generation, invalid AI responses, or situations where a sensible profile element cannot be suggested for a plan step (e.g., by allowing user to skip or manually define).
*   **NFR-REL-003: Data Integrity (Profile Saving):** GUI editor and **(v5.0.0) AI Profile Generator** MUST save structurally valid JSON profiles.
*   **NFR-REL-004: Resource Management:** Application should manage resources effectively.
*   **NFR-REL-005: Internet Connectivity (v4.0.0+):** All Gemini-dependent features REQUIRE an active internet connection. Failures due to connectivity loss must be handled gracefully.
*   **NFR-REL-006: Gemini Decision Module & NLU Robustness (v4.0.0 Phase 2 & 3 - Runtime):** `GeminiDecisionModule` MUST robustly handle API errors, invalid JSON, disallowed action suggestions, and respect `max_steps`.
*   **NFR-REL-007: AI Profile Generation Workflow Robustness (v5.0.0):** The interactive profile generation process MUST allow users to proceed even if some AI suggestions are imperfect or rejected. The system should not crash if Gemini provides unexpected (but non-malicious) output during plan or element suggestion.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** Codebase MUST be modular. **(v5.0.0): New modules like `StrategyPlanner` and `ProfileGenerator` MUST be well-encapsulated.**
*   **NFR-MAINT-002: Code Clarity & Documentation:** Code MUST be well-commented with docstrings. Design decisions (including for AI Profile Generation via ADR-009) MUST be documented.
*   **NFR-MAINT-003: Testability:** Core logic designed for testability. All Gemini interactions (including for profile generation) MUST be mockable.
*   **NFR-MAINT-004: Diagnosability:** Application MUST be highly diagnosable via comprehensive logging, including detailed logs for the AI Profile Generation process.

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness:** Users MUST be aware of screen observation, input simulation, and data transmission to Gemini.
*   **NFR-SEC-002: Data Transmission:** No network transmission unless explicitly for Gemini API calls.
*   **NFR-SEC-003: Secure Configuration Handling:** `.env` file gitignored.
*   **NFR-SEC-004: API Key Security (v4.0.0+):** `GEMINI_API_KEY` handled securely.
*   **NFR-SEC-005: Data Privacy for External API Calls (v4.0.0+):** Users informed that images and text (goals, NLU commands) are sent to Google.
*   **NFR-SEC-006: Control over AI-Suggested/NLU-Driven Actions (v4.0.0 Phase 2 & 3 - Runtime):** AI actions limited by `PREDEFINED_ALLOWED_SUB_ACTIONS` and optional user confirmation.
*   **NFR-SEC-007: Security of AI-Generated Profiles (v5.0.0 - Profile Generation):**
    *   The AI Profile Generator itself MUST NOT generate or embed malicious code or commands into the output JSON profile. The generated profile elements (conditions, actions) must map to Mark-I's standard, safe, and validated internal components.
    *   While the AI suggests logic, the user is ultimately responsible for reviewing and validating the generated profile before execution, as with any automation script.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Comprehensive Profile Configuration (Manual Editing):** All aspects of bot behavior configurable via GUI/JSON.
*   **NFR-CONF-002: Logging Configuration:** Controlled via `APP_ENV` and CLI flags.
*   **NFR-CONF-003: Core Loop Interval (Bot Runtime):** `monitoring_interval_seconds` configurable.
*   **NFR-CONF-004: Analysis Parameters:** Local analysis parameters and `gemini_default_model_name` configurable.
*   **NFR-CONF-005: Gemini Decision Task / NLU Configuration (v4.0.0 Phase 2 & 3 - Runtime):** Parameters for `gemini_perform_task` (e.g., `natural_language_command`, `context_region_names`, `allowed_actions_override`, `require_confirmation_per_step`, `max_steps`) MUST be configurable.
*   **NFR-CONF-006: AI Profile Generation - Goal Input (v5.0.0):** Users MUST be able to provide their high-level goal as natural language text to initiate the AI profile generation process.
*   **NFR-CONF-007: AI Profile Generation - Interactivity Levels (v5.0.0 - Future Consideration):** Potentially offer different levels of AI autonomy vs. user interaction during profile generation (e.g., "fully guided" vs. "more suggestions, less confirmation"). Initial v5.0.0 will likely focus on a user-confirming interactive model.

---