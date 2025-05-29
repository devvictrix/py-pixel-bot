# Non-Functional Requirements for Mark-I

This document outlines the non-functional requirements for the Mark-I visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor, as applicable. This version reflects requirements up to v4.0.0 Phase 1.5 (Gemini Bounding Box Actions) and **includes considerations for the planned v4.0.0 Phase 2 (Gemini-Informed Decision Making) integration.**

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):**
    *   **Local Analysis:** Image analysis operations performed locally (color checking, template matching, OCR, dominant color) on captured regions SHOULD be computationally efficient. The total duration of these local analyses for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds` to avoid falling behind. The "Selective Analysis per Rule" feature (FR-ANALYZE-006) is critical for achieving this for local operations.
    *   **v4.0.0 (Gemini - `gemini_vision_query`): API Call Latency:** Gemini API calls for `gemini_vision_query` conditions WILL introduce network and model processing latency (potentially several seconds per call). The system design (on-demand calls by `RulesEngine`) mitigates performing these unnecessarily, but users MUST be aware of this impact when designing profiles that use Gemini. Logging of API call latency by `GeminiAnalyzer` is required.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The capture/analysis/action loop speed (via `monitoring_interval_seconds` in profile settings) MUST be configurable by the user to balance responsiveness and system load. **v4.0.0 (Gemini): Users should be guided (e.g., via documentation and UI tooltips if feasible) that profiles heavily reliant on Gemini conditions will necessitate longer monitoring intervals due to API latency.**
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on local system performance (CPU, memory usage). **v4.0.0 (Gemini): Gemini API calls will introduce network bandwidth usage during those operations but should not excessively load local CPU/memory beyond image preparation.**
*   **NFR-PERF-005: Responsive GUI Profile Editor:** The `MainAppWindow` GUI SHOULD load and save profiles in a timely manner (e.g., within a few seconds for profiles of typical complexity and size). User interactions SHOULD feel responsive. **v4.0.0 (Gemini): Configuration of Gemini API key status display or default model in GUI settings should not introduce significant performance lag.**
*   **NFR-PERF-006: Gemini Decision Module Latency (v4.0.0 Phase 2):** The `GeminiDecisionModule` will involve at least one, and potentially multiple, Gemini API calls per task step (e.g., one for initial action suggestion, another for target refinement if needed). Users MUST be aware that tasks driven by this module will have noticeable latency (potentially several seconds or more per step). The system should strive to minimize unnecessary calls. Logging of overall task step latency by `GeminiDecisionModule` is required.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus):** Defining all aspects of a bot profile MUST be achievable and intuitive through the `MainAppWindow` GUI.
    *   **(v4.0.0 - Gemini - Phase 1 & 1.5):** This includes configuration of `gemini_vision_query` conditions (multi-line prompts, response parameters, model selection, variable capture) and actions targeting Gemini-identified elements (via `gemini_element_variable`).
    *   **(v4.0.0 - Gemini - Phase 2):** This includes configuration of parameters for "Gemini Tasks" (e.g., `goal_prompt`, `context_region_names`, `allowed_actions_override`, `require_confirmation_before_each_step`) if invoked via a rule action.
*   **NFR-USAB-002: Intuitive Rule Creation & Editing (GUI):** The GUI MUST present rule structures and their parameters in a clear, organized, and understandable manner. **v4.0.0 (Gemini): While the GUI will facilitate setting up Gemini conditions and tasks, users must understand that effective prompt engineering is a separate skill crucial for success. Documentation (NFR-USAB-010) will guide this.**
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** The system MUST provide clear, timely, and actionable feedback. This includes:
    *   Informative console output for CLI operations.
    *   Descriptive dialog boxes and status bar messages in the GUI.
    *   Comprehensive, persistent, and well-formatted logs (per ADR-007).
    *   **(v4.0.0 - Gemini): Logs MUST clearly indicate Gemini API call initiation (summarized prompt, model), success/failure, latency, and summarized outcomes for both `gemini_vision_query` and `GeminiDecisionModule` interactions. The GUI MUST provide feedback on Gemini API key status.**
*   **NFR-USAB-004: Interruptibility (Bot Runtime):** Users MUST be able to easily start (CLI `run`) and stop (CLI `Ctrl+C`) the bot's monitoring loop.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** While the GUI is primary, the JSON profile format SHOULD be human-readable and well-documented.
    *   **(v4.0.0 - Gemini - Phase 1 & 1.5):** The JSON schema for `gemini_vision_query` conditions and actions targeting Gemini elements must be clearly defined.
    *   **(v4.0.0 - Gemini - Phase 2):** The JSON schema for "Gemini Task" definitions (e.g., as a rule action) must be clearly defined.
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** The GUI editor MUST implement robust validation for all user-editable fields. **v4.0.0 (Gemini): This includes validation for Gemini prompts, model names, and other specific parameters for conditions, actions, and tasks.**
*   **NFR-USAB-007: GUI State Management:** The GUI MUST reliably manage its internal state (e.g., unsaved changes, selections).
*   **NFR-USAB-008: API Key Management (v4.0.0 - Gemini):** The process for users to obtain and configure their `GEMINI_API_KEY` (via `.env` file) MUST be clearly documented. The application GUI (`MainAppWindow` settings) MUST display the status of the API key (e.g., "Loaded from .env" or "Not Found in .env").
*   **NFR-USAB-009: Cost and Usage Awareness (v4.0.0 - Gemini):** Users MUST be clearly informed (via documentation and potentially in-GUI notes near Gemini configuration) that using Gemini API features will incur costs based on their usage with Google Cloud. The tool itself will not track or limit costs but should point to official Gemini pricing documentation.
*   **NFR-USAB-010: Documentation for Advanced Features (v4.0.0 - Gemini):** Comprehensive documentation MUST be provided on how to use `gemini_vision_query` conditions and "Gemini Tasks" effectively.
    *   **(Phase 1 & 1.5):** Guidance on prompt engineering for visual queries, obtaining bounding boxes, and configuring actions to use these boxes.
    *   **(Phase 2 Addition):** Guidance on writing effective `goal_prompt`s for the `GeminiDecisionModule`, selecting `context_region_names`, understanding the `PREDEFINED_ALLOWED_ACTIONS`, and interpreting the module's behavior and logs. It must reiterate the experimental nature and potential non-determinism of AI-driven decision-making.
*   **NFR-USAB-011: Clarity of AI-Driven Actions (v4.0.0 Phase 2):** When the `GeminiDecisionModule` is active, it MUST be clear to the user (through logs, and optionally through GUI feedback if `require_confirmation_before_each_step` is enabled) that Gemini is influencing action selection. The reasoning provided by Gemini (if captured in the response) should be logged for transparency.

## NFR-ACCU: Accuracy (Bot Runtime)

*   **NFR-ACCU-001: Precise Region Capture:** Captured image data MUST accurately correspond to user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results:**
    *   **Local Analysis:** Local analysis (color, template, OCR) SHOULD be accurate under consistent conditions, with user-configurable tolerances/thresholds.
    *   **(v4.0.0 - Gemini - `gemini_vision_query`):** The accuracy of `gemini_vision_query` results depends on the capabilities of the chosen Gemini model and the quality of the user-provided prompt. This introduces a level of non-determinism and requires user testing and prompt refinement for specific tasks.
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered (either by explicit rules or `GeminiDecisionModule`) SHOULD be performed reliably and accurately by `ActionExecutor`. Actions targeting Gemini-identified elements depend on the accuracy of the bounding box data returned by Gemini.
*   **NFR-ACCU-004: Gemini Decision Accuracy (v4.0.0 Phase 2):** The accuracy and appropriateness of actions suggested by the `GeminiDecisionModule` depend heavily on the Gemini model's capabilities, the quality of the `goal_prompt` and visual context, and the effectiveness of the prompt engineering strategy. This introduces significant non-determinism. The system aims to provide a useful suggestion, but correctness is not guaranteed and relies on the user's goal formulation and the safety boundaries (limited action set, validation). The user is ultimately responsible for testing and validating task automations in safe environments.

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Both bot runtime and GUI editor SHOULD operate stably without frequent crashes or freezes under normal usage patterns defined by the functional requirements.
*   **NFR-REL-002: Graceful Error Handling:** The system MUST handle errors gracefully, providing informative messages (to logs and, where appropriate, to the user via GUI/CLI) rather than abrupt crashes.
    *   **(v4.0.0 - Gemini - `gemini_vision_query`):** This includes robustly handling Gemini API errors (e.g., authentication failure, rate limits, invalid requests, network issues, server errors from Google, content blocking) for `gemini_vision_query` conditions. Such errors should be logged clearly by `GeminiAnalyzer` and `RulesEngine`, and the relevant rule condition should evaluate to `False`.
    *   **(v4.0.0 - Gemini - Phase 1.5):** `ActionExecutor` must gracefully handle malformed or missing bounding box data from Gemini variables.
*   **NFR-REL-003: Data Integrity (Profile Saving):** The GUI editor MUST ensure saving a profile results in a structurally valid JSON file that conforms to the defined schema.
*   **NFR-REL-004: Resource Management:** The application should manage local system resources (CPU, memory) effectively and avoid memory leaks or excessive sustained resource consumption that would degrade overall system performance. **v4.0.0 (Gemini): Gemini usage primarily involves network I/O; local resource impact should be from image handling before API calls.**
*   **NFR-REL-005: Internet Connectivity (v4.0.0 - Gemini):** Features relying on `gemini_vision_query` conditions or the `GeminiDecisionModule` REQUIRE an active internet connection to communicate with the Google Gemini API. The application (`RulesEngine` or `GeminiDecisionModule`) SHOULD handle temporary or permanent loss of connectivity gracefully (e.g., conditions/tasks fail, errors logged by `GeminiAnalyzer`) for Gemini-dependent operations, while allowing non-Gemini rules/features to continue functioning if possible.
*   **NFR-REL-006: Gemini Decision Module Robustness (v4.0.0 Phase 2):** The `GeminiDecisionModule` MUST robustly handle:
    *   API errors from `GeminiAnalyzer` during action suggestion or target refinement calls.
    *   Invalid or unexpected JSON structures (or non-JSON responses) from Gemini when expecting action suggestions.
    *   Suggestions for actions not in the `PREDEFINED_ALLOWED_ACTIONS` list.
    *   Missing or invalid parameters in Gemini's suggestions for allowed actions.
    *   Failures during the target refinement step (e.g., Gemini cannot find the described element for bounding box extraction).
    *   Such failures should result in the task step failing gracefully with clear error logging, not crashing the bot. The module should not attempt to execute partially formed or unsafe actions.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** The codebase MUST be organized into clearly defined, modular Python packages and modules with high cohesion and low coupling to facilitate understanding, modification, and testing.
    *   **(v4.0.0 - Gemini):** The `GeminiAnalyzer` module encapsulates Gemini API interactions. The `GeminiDecisionModule` will encapsulate AI-driven task processing logic.
*   **NFR-MAINT-002: Code Clarity & Documentation:** Code MUST be well-commented with comprehensive docstrings (Google Python Style). Design decisions MUST be documented (ADRs, `TECHNICAL_DESIGN.MD`). **v4.0.0 (Gemini): `ADR-008` and `TECHNICAL_DESIGN.MD` updates cover Gemini integration details, including the `GeminiDecisionModule` for Phase 2.**
*   **NFR-MAINT-003: Testability:** Core logic SHOULD be designed for testability.
    *   **(v4.0.0 - Gemini):** Interactions with external services like the Gemini API (`GeminiAnalyzer`, `GeminiDecisionModule`) MUST be mockable for effective unit/integration testing (mocking strategy outlined in `TECHNICAL_DESIGN.MD`).
*   **NFR-MAINT-004: Diagnosability:** The application MUST be highly diagnosable via comprehensive logging (per ADR-007).
    *   **(v4.0.0 - Gemini):** Logging for `GeminiAnalyzer`, `RulesEngine`'s use of Gemini, `ActionExecutor`'s handling of Gemini-derived coordinates, and the `GeminiDecisionModule`'s entire decision-making process is critical (see `TECHNICAL_DESIGN.MD`).

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness (Bot Runtime):** Users MUST be made explicitly aware that the bot observes their screen and can perform inputs. **v4.0.0 (Gemini): This awareness MUST extend to informing users (via documentation and GUI disclaimers/tooltips) that selected screen region images are transmitted to Google servers when Gemini features are used.**
*   **NFR-SEC-002: Data Transmission:** The application SHOULD NOT transmit screen captures, configuration data, or logs over any network **unless explicitly configured by the user for features like `gemini_vision_query` or the `GeminiDecisionModule` (v4.0.0)**, which involve sending image data of specified regions and text prompts to Google's Gemini API. Any other network transmission (e.g., future webhook action) would require separate, clear user consent and configuration.
*   **NFR-SEC-003: Secure Configuration Handling:** Profile files and `.env` files are user-managed. The application must load them safely. The `.env` file MUST be in `.gitignore`.
*   **NFR-SEC-004: API Key Security (v4.0.0 - Gemini):** The `GEMINI_API_KEY` is highly sensitive. It MUST be loaded from the `.env` file (which is gitignored) by `ConfigManager.load_environment_variables()` into `os.environ`, and then accessed via `os.getenv()` by components like `GeminiAnalyzer`. It MUST NOT be logged or stored in profile files. Documentation MUST emphasize secure API key practices to the user.
*   **NFR-SEC-005: Data Privacy for External API Calls (v4.0.0 - Gemini):** Users MUST be explicitly informed (e.g., in documentation, GUI disclaimers/tooltips near Gemini configuration) that image data from regions analyzed by Gemini conditions or tasks is sent to Google servers for processing, subject to Google's data privacy policies.
*   **NFR-SEC-006: Control over AI-Suggested Actions (v4.0.0 Phase 2):**
    *   The set of `PREDEFINED_ALLOWED_ACTIONS` that the `GeminiDecisionModule` can instruct `ActionExecutor` to perform MUST be hardcoded, limited, and consist of simple, generally safe UI interactions (e.g., click, type, press key).
    *   Gemini MUST NOT be able to suggest arbitrary system commands, file operations, or direct code execution.
    *   The optional user confirmation step (`require_confirmation_before_each_step` setting) provides an additional layer of user control and safety.
    *   Users must be made aware (via documentation) of the experimental nature of AI-driven action selection and the importance of testing tasks in safe, non-critical environments first.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Comprehensive Profile Configuration (via GUI & JSON):** All aspects of bot behavior (regions, templates, rules, settings) MUST be configurable.
    *   **(v4.0.0 - Gemini):** This includes all parameters for `gemini_vision_query` conditions, actions targeting Gemini elements, and parameters for "Gemini Tasks" (Phase 2), via the GUI and JSON.
*   **NFR-CONF-002: Logging Configuration:** Logging behavior MUST be primarily controlled via `APP_ENV` and secondarily via CLI runtime flags (per ADR-007).
*   **NFR-CONF-003: Core Loop Interval (Bot Runtime):** The `monitoring_interval_seconds` MUST be configurable in profile settings.
*   **NFR-CONF-004: Analysis Parameters:** Key parameters for local analysis engines (e.g., `analysis_dominant_colors_k`) SHOULD be configurable in profile settings. **v4.0.0 (Gemini): The default Gemini model (e.g., "gemini-1.5-flash-latest") MUST be configurable in profile settings (`settings.gemini_default_model_name`), and can be overridden per `gemini_vision_query` condition.**
*   **NFR-CONF-005: Gemini Decision Task Configuration (v4.0.0 Phase 2):** Users MUST be able to configure all parameters for a "Gemini Task" (e.g., `goal_prompt`, `context_region_names`, `allowed_actions_override`, `max_steps`, `require_confirmation_before_each_step`) via the profile JSON and GUI, as defined in `gui_config.py` and implemented in the GUI editor.