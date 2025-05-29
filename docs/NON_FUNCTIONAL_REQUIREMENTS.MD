# Non-Functional Requirements for Mark-I

This document outlines the non-functional requirements for the Mark-I visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor, as applicable. **This version reflects requirements for the completed v4.0.0, including Phase 1 (Core Gemini Vision Query), Phase 1.5 (Bounding Box Actions), Phase 2 (Gemini-Informed Decision Making), and Phase 3 (Natural Language Command Interface).**

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):**
    *   **Local Analysis:** Image analysis operations performed locally (color checking, template matching, OCR, dominant color) on captured regions SHOULD be computationally efficient. The total duration of these local analyses for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds` to avoid falling behind. The "Selective Analysis per Rule" feature (FR-ANALYZE-006) is critical for achieving this for local operations.
    *   **v4.0.0 (Gemini - `gemini_vision_query`): API Call Latency:** Gemini API calls for `gemini_vision_query` conditions WILL introduce network and model processing latency (potentially several seconds per call). The system design (on-demand calls by `RulesEngine`) mitigates performing these unnecessarily, but users MUST be aware of this impact when designing profiles that use Gemini. Logging of API call latency by `GeminiAnalyzer` is required.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The capture/analysis/action loop speed (via `monitoring_interval_seconds` in profile settings) MUST be configurable by the user to balance responsiveness and system load. **v4.0.0 (Gemini): Users should be guided (e.g., via documentation and UI tooltips if feasible) that profiles heavily reliant on Gemini conditions or `gemini_perform_task` actions will necessitate longer monitoring intervals due to API latency for each Gemini interaction.**
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on local system performance (CPU, memory usage). **v4.0.0 (Gemini): Gemini API calls will introduce network bandwidth usage during those operations but should not excessively load local CPU/memory beyond image preparation.**
*   **NFR-PERF-005: Responsive GUI Profile Editor:** The `MainAppWindow` GUI SHOULD load and save profiles in a timely manner (e.g., within a few seconds for profiles of typical complexity and size). User interactions SHOULD feel responsive. Configuration of Gemini-related parameters in the GUI should not introduce significant performance lag.
*   **NFR-PERF-006: Gemini Decision Module / NLU Task Latency (v4.0.0 Phase 2 & 3):**
    *   The `GeminiDecisionModule` (for both goal-driven single actions and NLU-driven multi-step tasks via `gemini_perform_task`) will involve at least one, and potentially multiple, Gemini API calls per task or per decomposed step (e.g., one for NLU parsing, one for initial action suggestion for a step, another for target refinement if needed).
    *   Users MUST be aware that tasks driven by this module will have noticeable latency (potentially several seconds or more per AI-involved step). The system should strive to minimize unnecessary API calls within its orchestration logic.
    *   Comprehensive logging of API call latencies for each stage (NLU, action suggestion, refinement) within the `GeminiDecisionModule` is required.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus):** Defining all aspects of a bot profile MUST be achievable and intuitive through the `MainAppWindow` GUI.
    *   **(v4.0.0 - Gemini):** This includes configuration of `gemini_vision_query` conditions, actions targeting Gemini-identified elements, and parameters for `gemini_perform_task` actions (including `natural_language_command`, `context_region_names`, `allowed_actions_override`, `require_confirmation_per_step`, `max_steps`).
*   **NFR-USAB-002: Intuitive Rule Creation & Editing (GUI):** The GUI MUST present rule structures and their parameters in a clear, organized, and understandable manner. **v4.0.0 (Gemini): While the GUI will facilitate setting up Gemini conditions and tasks, users must understand that effective prompt engineering (for vision queries, NLU commands, and goal prompts) is a separate skill crucial for success. Documentation (NFR-USAB-010) will guide this.**
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** The system MUST provide clear, timely, and actionable feedback. This includes:
    *   Informative console output for CLI operations.
    *   Descriptive dialog boxes and status bar messages in the GUI.
    *   Comprehensive, persistent, and well-formatted logs (per ADR-007).
    *   **(v4.0.0 - Gemini): Logs MUST clearly indicate all Gemini API call initiations (summarized prompt, model), success/failure, latency, and summarized outcomes for `gemini_vision_query`, and all stages of `GeminiDecisionModule` operation (NLU, step decision, refinement). The GUI MUST provide feedback on Gemini API key status.**
*   **NFR-USAB-004: Interruptibility (Bot Runtime):** Users MUST be able to easily start (CLI `run`) and stop (CLI `Ctrl+C`) the bot's monitoring loop, including NLU-driven tasks in progress.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** While the GUI is primary, the JSON profile format SHOULD be human-readable and well-documented. The JSON schema for all Gemini-related conditions and actions (`gemini_vision_query`, `gemini_perform_task` with NLU parameters) must be clearly defined.
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** The GUI editor MUST implement robust validation for all user-editable fields, including those specific to Gemini features.
*   **NFR-USAB-007: GUI State Management:** The GUI MUST reliably manage its internal state (e.g., unsaved changes, selections when configuring complex Gemini tasks).
*   **NFR-USAB-008: API Key Management (v4.0.0 - Gemini):** The process for users to obtain and configure their `GEMINI_API_KEY` (via `.env` file) MUST be clearly documented. The application GUI (`MainAppWindow` settings) MUST display the status of the API key.
*   **NFR-USAB-009: Cost and Usage Awareness (v4.0.0 - Gemini):** Users MUST be clearly informed (via documentation and potentially in-GUI notes) that using Gemini API features will incur costs based on their usage with Google Cloud.
*   **NFR-USAB-010: Documentation for Advanced Features (v4.0.0 - Gemini):** Comprehensive documentation MUST be provided on how to use `gemini_vision_query` conditions and `gemini_perform_task` actions effectively.
    *   This includes guidance on prompt engineering for visual queries, obtaining bounding boxes, configuring actions to use these boxes, writing effective `natural_language_command`s for the NLU interface, selecting `context_region_names`, understanding `PREDEFINED_ALLOWED_SUB_ACTIONS` (for `allowed_actions_override`), and interpreting the module's behavior and logs.
    *   Documentation must reiterate the experimental nature and potential non-determinism of AI-driven decision-making and NLU.
*   **NFR-USAB-011: Clarity of AI-Driven Actions (v4.0.0 Phase 2+):** When the `GeminiDecisionModule` is active (via `gemini_perform_task`), it MUST be clear to the user (through logs, and optionally through GUI feedback/confirmation dialogs if `require_confirmation_per_step` is enabled) that Gemini is influencing action selection and execution. The reasoning provided by Gemini (if captured) should be logged for transparency.

## NFR-ACCU: Accuracy (Bot Runtime)

*   **NFR-ACCU-001: Precise Region Capture:** Captured image data MUST accurately correspond to user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results:**
    *   **Local Analysis:** Local analysis SHOULD be accurate under consistent conditions.
    *   **(v4.0.0 - Gemini - `gemini_vision_query`):** Accuracy depends on Gemini model capabilities and prompt quality. Non-deterministic.
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered SHOULD be performed reliably. Actions targeting Gemini-identified elements depend on the accuracy of Gemini's bounding box data.
*   **NFR-ACCU-004: Gemini Decision & NLU Accuracy (v4.0.0 Phase 2 & 3):**
    *   The accuracy and appropriateness of actions suggested by `GeminiDecisionModule` (for single goals or NLU-decomposed steps) and the correctness of NLU parsing/decomposition depend heavily on Gemini model capabilities, prompt quality, and visual context. This introduces significant non-determinism.
    *   The system aims to provide useful suggestions/interpretations, but correctness is not guaranteed. Users are responsible for crafting clear commands/goals and testing automations in safe environments. The safety boundaries (limited action set, validation) are critical.

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Both bot runtime and GUI editor SHOULD operate stably.
*   **NFR-REL-002: Graceful Error Handling:** The system MUST handle errors gracefully.
    *   **(v4.0.0 - Gemini):** This includes robustly handling Gemini API errors for `gemini_vision_query` conditions (condition fails) and within all operations of `GeminiDecisionModule` (NLU parsing, step action suggestion, target refinement – task/step fails gracefully with logs).
    *   **(v4.0.0 - Gemini - Phase 1.5):** `ActionExecutor` handles malformed bounding box data.
*   **NFR-REL-003: Data Integrity (Profile Saving):** GUI editor MUST save structurally valid JSON profiles.
*   **NFR-REL-004: Resource Management:** Application should manage local resources effectively.
*   **NFR-REL-005: Internet Connectivity (v4.0.0 - Gemini):** All Gemini-dependent features (`gemini_vision_query`, `gemini_perform_task`) REQUIRE an active internet connection. The application MUST handle connectivity loss gracefully (e.g., conditions/tasks fail, errors logged).
*   **NFR-REL-006: Gemini Decision Module & NLU Robustness (v4.0.0 Phase 2 & 3):** The `GeminiDecisionModule` MUST robustly handle:
    *   API errors from `GeminiAnalyzer`.
    *   Invalid or unexpected JSON structures (or non-JSON responses) from Gemini for NLU parsing or action suggestions.
    *   Suggestions for actions not in its `PREDEFINED_ALLOWED_SUB_ACTIONS` list or its task-specific `allowed_actions_override`.
    *   Missing or invalid parameters in Gemini's suggestions.
    *   Failures during target refinement for sub-steps.
    *   Such failures should result in the current task or NLU-driven step failing gracefully with clear error logging, not crashing the bot. The module must not attempt to execute partially formed or unsafe actions. It should respect `max_steps` for NLU tasks.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** Codebase MUST be organized into clearly defined, modular Python packages/modules. The `GeminiAnalyzer` and `GeminiDecisionModule` encapsulate distinct AI interaction functionalities.
*   **NFR-MAINT-002: Code Clarity & Documentation:** Code MUST be well-commented with comprehensive docstrings. Design decisions documented in ADRs and `TECHNICAL_DESIGN.MD`.
*   **NFR-MAINT-003: Testability:** Core logic designed for testability. Gemini interactions (`GeminiAnalyzer`, `GeminiDecisionModule`) MUST be mockable for testing.
*   **NFR-MAINT-004: Diagnosability:** Application MUST be highly diagnosable via comprehensive logging. Logging for all stages of `GeminiDecisionModule`'s NLU and task orchestration is critical.

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness (Bot Runtime):** Users MUST be explicitly aware Mark-I observes their screen and can perform inputs. This awareness extends to image data transmission for Gemini features.
*   **NFR-SEC-002: Data Transmission:** No network transmission unless explicitly for Gemini API calls (or future user-configured webhooks).
*   **NFR-SEC-003: Secure Configuration Handling:** `.env` file (for API key) MUST be gitignored.
*   **NFR-SEC-004: API Key Security (v4.0.0 - Gemini):** `GEMINI_API_KEY` handled securely (loaded from `.env`, not logged or stored in profiles).
*   **NFR-SEC-005: Data Privacy for External API Calls (v4.0.0 - Gemini):** Users explicitly informed that image data and NLU command text are sent to Google servers for processing.
*   **NFR-SEC-006: Control over AI-Suggested/NLU-Driven Actions (v4.0.0 Phase 2 & 3):**
    *   The set of `PREDEFINED_ALLOWED_SUB_ACTIONS` for `GeminiDecisionModule` (used for both goal-driven tasks and NLU-decomposed steps) MUST be hardcoded, limited, and consist of simple UI interactions.
    *   Gemini (via NLU or action suggestion) MUST NOT be able to suggest arbitrary system commands or direct code execution.
    *   The `require_confirmation_per_step` parameter for `gemini_perform_task` provides user control.
    *   Documentation must emphasize the experimental nature of NLU-driven automation and the importance of testing in safe environments.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Comprehensive Profile Configuration (via GUI & JSON):** All aspects of bot behavior MUST be configurable. This includes all parameters for `gemini_vision_query` conditions and `gemini_perform_task` actions (including `natural_language_command`, `context_region_names`, `allowed_actions_override`, `require_confirmation_per_step`, `max_steps`).
*   **NFR-CONF-002: Logging Configuration:** Controlled via `APP_ENV` and CLI flags.
*   **NFR-CONF-003: Core Loop Interval (Bot Runtime):** `monitoring_interval_seconds` configurable.
*   **NFR-CONF-004: Analysis Parameters:** Local analysis parameters (e.g., `analysis_dominant_colors_k`) and `gemini_default_model_name` configurable in profile settings.
*   **NFR-CONF-005: Gemini Decision Task Configuration (v4.0.0 Phase 2 & 3):** All parameters for the `gemini_perform_task` action, governing how the `GeminiDecisionModule` operates for single goals or NLU commands, MUST be configurable via profile JSON and GUI.
