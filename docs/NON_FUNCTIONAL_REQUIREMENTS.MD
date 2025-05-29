# Non-Functional Requirements for Mark-I

This document outlines the non-functional requirements for the Mark-I visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor, as applicable. This version reflects requirements up to v3.0.0 (GUI Editor) and **includes considerations for the planned v4.0.0 (Gemini-Powered Visual Intelligence) integration.**

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):**
    *   **Local Analysis:** Image analysis operations performed locally (color checking, template matching, OCR, dominant color) on captured regions SHOULD be computationally efficient. The total duration of these local analyses for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds` to avoid falling behind. The "Selective Analysis per Rule" feature (FR-ANALYZE-006) is critical for achieving this for local operations.
    *   **v4.0.0 (Gemini): API Call Latency:** Gemini API calls for `gemini_vision_query` conditions WILL introduce network and model processing latency (potentially several seconds per call). The system design (on-demand calls by `RulesEngine`) mitigates performing these unnecessarily, but users MUST be aware of this impact when designing profiles that use Gemini. Logging of API call latency by `GeminiAnalyzer` is required.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The capture/analysis/action loop speed (via `monitoring_interval_seconds` in profile settings) MUST be configurable by the user to balance responsiveness and system load. **v4.0.0 (Gemini): Users should be guided (e.g., via documentation and UI tooltips if feasible) that profiles heavily reliant on Gemini conditions will necessitate longer monitoring intervals due to API latency.**
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on local system performance (CPU, memory usage). **v4.0.0 (Gemini): Gemini API calls will introduce network bandwidth usage during those operations but should not excessively load local CPU/memory beyond image preparation.**
*   **NFR-PERF-005: Responsive GUI Profile Editor:** The `MainAppWindow` GUI SHOULD load and save profiles in a timely manner (e.g., within a few seconds for profiles of typical complexity and size). User interactions SHOULD feel responsive. **v4.0.0 (Gemini): Configuration of Gemini API key status display or default model in GUI settings should not introduce significant performance lag.**

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus):** Defining all aspects of a bot profile MUST be achievable and intuitive through the `MainAppWindow` GUI. **v4.0.0 (Gemini): This includes configuration of `gemini_vision_query` conditions, including multi-line prompts via `CTkTextbox`, response expectation parameters, model selection, and variable capture, all driven by `gui_config.py`. (v4.0.0 Phase 1.5) This also includes configuring actions to target Gemini-identified elements.**
*   **NFR-USAB-002: Intuitive Rule Creation & Editing (GUI):** The GUI MUST present rule structures and their parameters in a clear, organized, and understandable manner. **v4.0.0 (Gemini): While the GUI will facilitate setting up Gemini conditions, users must understand that effective prompt engineering is a separate skill crucial for success with these conditions. Documentation (NFR-USAB-010) will guide this.**
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** The system MUST provide clear, timely, and actionable feedback. This includes:
    *   Informative console output for CLI operations.
    *   Descriptive dialog boxes and status bar messages in the GUI.
    *   Comprehensive, persistent, and well-formatted logs (per ADR-007).
    *   **v4.0.0 (Gemini): Logs MUST clearly indicate Gemini API call initiation (summarized prompt, model), success/failure, latency, and summarized outcomes. The GUI MUST provide feedback on Gemini API key status (e.g., configured/not configured) in the settings panel.**
*   **NFR-USAB-004: Interruptibility (Bot Runtime):** Users MUST be able to easily start (CLI `run`) and stop (CLI `Ctrl+C`) the bot's monitoring loop.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** While the GUI is primary, the JSON profile format SHOULD be human-readable and well-documented. **v4.0.0 (Gemini): The JSON schema for `gemini_vision_query` conditions and actions targeting Gemini elements must be clearly defined (as in `TECHNICAL_DESIGN.MD`).**
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** The GUI editor MUST implement robust validation for all user-editable fields. **v4.0.0 (Gemini): This includes validation for Gemini prompt (e.g., not excessively long if known limits exist, though not strictly enforced by GUI), model name format, and other specific parameters, including action parameters for Gemini element targeting.**
*   **NFR-USAB-007: GUI State Management:** The GUI MUST reliably manage its internal state.
*   **NFR-USAB-008: API Key Management (v4.0.0 - Gemini):** The process for users to obtain and configure their `GEMINI_API_KEY` (via `.env` file) MUST be clearly documented. The application GUI (`MainAppWindow` settings) MUST display the status of the API key (e.g., "Loaded from .env" or "Not Found in .env").
*   **NFR-USAB-009: Cost and Usage Awareness (v4.0.0 - Gemini):** Users MUST be clearly informed (via documentation and potentially in-GUI notes near Gemini configuration) that using Gemini API features will incur costs based on their usage with Google Cloud. The tool itself will not track or limit costs but should point to official Gemini pricing documentation.
*   **NFR-USAB-010: Documentation for Advanced Features (v4.0.0 - Gemini):** Comprehensive documentation MUST be provided on how to use `gemini_vision_query` conditions effectively, including guidance on prompt engineering best practices for visual automation tasks (including obtaining bounding boxes), explanation of condition parameters, and examples. **(v4.0.0 Phase 1.5) This includes how to configure actions to use these bounding boxes.**

## NFR-ACCU: Accuracy (Bot Runtime)

*   **NFR-ACCU-001: Precise Region Capture:** Captured image data MUST accurately correspond to user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results:**
    *   Local analysis (color, template, OCR) SHOULD be accurate under consistent conditions, with user-configurable tolerances/thresholds.
    *   **v4.0.0 (Gemini): The accuracy of `gemini_vision_query` results depends on the capabilities of the chosen Gemini model and the quality of the user-provided prompt. This introduces a level of non-determinism and requires user testing and prompt refinement for specific tasks.**
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered SHOULD be performed reliably and accurately. **(v4.0.0 Phase 1.5) Actions targeting Gemini-identified elements depend on the accuracy of the bounding box data returned by Gemini.**

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Both bot runtime and GUI editor SHOULD operate stably.
*   **NFR-REL-002: Graceful Error Handling:** The system MUST handle errors gracefully.
    *   **v4.0.0 (Gemini): This includes robustly handling Gemini API errors (e.g., authentication failure, rate limits, invalid requests, network issues, server errors from Google, content blocking). Such errors should be logged clearly by `GeminiAnalyzer` and `RulesEngine`, and the relevant rule condition should evaluate to `False` without crashing the bot.**
    *   **(v4.0.0 Phase 1.5) `ActionExecutor` must gracefully handle malformed or missing bounding box data from Gemini variables.**
*   **NFR-REL-003: Data Integrity (Profile Saving):** The GUI editor MUST ensure saving a profile results in a structurally valid JSON file.
*   **NFR-REL-004: Resource Management:** The application should manage local system resources effectively. **v4.0.0 (Gemini): Gemini usage primarily involves network I/O; local resource impact should be from image handling before API calls.**
*   **NFR-REL-005: Internet Connectivity (v4.0.0 - Gemini):** Features relying on `gemini_vision_query` conditions REQUIRE an active internet connection to communicate with the Google Gemini API. The application (`RulesEngine` evaluating the condition) SHOULD handle temporary or permanent loss of connectivity gracefully (e.g., conditions fail, errors logged by `GeminiAnalyzer`) for Gemini-dependent rules, while allowing non-Gemini rules to continue functioning if possible.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** The codebase MUST be organized into clearly defined, modular Python packages and modules. **v4.0.0 (Gemini): The `GeminiAnalyzer` module encapsulates Gemini API interactions.** (Python package name remains `mark_i`)
*   **NFR-MAINT-002: Code Clarity & Documentation:** Code MUST be well-commented with comprehensive docstrings. Design decisions MUST be documented (ADRs, `TECHNICAL_DESIGN.MD`). **v4.0.0 (Gemini): `ADR-008` and `TECHNICAL_DESIGN.MD` updates cover Gemini integration details.**
*   **NFR-MAINT-003: Testability:** Core logic SHOULD be designed for testability. **v4.0.0 (Gemini): `GeminiAnalyzer` interactions require mocking the external API for effective unit/integration testing (mocking strategy outlined in `TECHNICAL_DESIGN.MD`). `ActionExecutor` logic for Gemini element targeting must be unit testable.**
*   **NFR-MAINT-004: Diagnosability:** The application MUST be highly diagnosable via comprehensive logging. **v4.0.0 (Gemini): Logging for `GeminiAnalyzer` and `RulesEngine`'s use of Gemini, and `ActionExecutor`'s handling of Gemini-derived coordinates is critical (see `TECHNICAL_DESIGN.MD` Section 7).**

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness (Bot Runtime):** Users MUST be made explicitly aware that the bot observes their screen and can perform inputs. **v4.0.0 (Gemini): This awareness MUST extend to informing users (via documentation and GUI disclaimers/tooltips near Gemini condition configuration) that selected screen region images are transmitted to Google servers when `gemini_vision_query` conditions are used.**
*   **NFR-SEC-002: Data Transmission:** The application SHOULD NOT transmit screen captures, configuration data, or logs over any network **unless explicitly configured by the user for features like `gemini_vision_query` (v4.0.0)**, which involves sending image data of specified regions and text prompts to Google's Gemini API. Any other network transmission (e.g., future webhook action) would require separate, clear user consent and configuration.
*   **NFR-SEC-003: Secure Configuration Handling:** Profile files and `.env` files are user-managed. The application must load them safely. The `.env` file MUST be in `.gitignore`.
*   **NFR-SEC-004: API Key Security (v4.0.0 - Gemini):** The `GEMINI_API_KEY` is highly sensitive. It MUST be loaded from the `.env` file (which is gitignored) by `ConfigManager.load_environment_variables()` into `os.environ`, and then accessed via `os.getenv()` by `GeminiAnalyzer`. It MUST NOT be logged or stored in profile files. Documentation MUST emphasize secure API key practices to the user.
*   **NFR-SEC-005: Data Privacy for External API Calls (v4.0.0 - Gemini):** Users MUST be explicitly informed (e.g., in documentation, GUI disclaimers/tooltips near Gemini configuration) that image data from regions analyzed by `gemini_vision_query` conditions is sent to Google servers for processing, subject to Google's data privacy policies.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Comprehensive Profile Configuration (via GUI & JSON):** All aspects of bot behavior MUST be configurable. **v4.0.0 (Gemini): This includes all parameters for `gemini_vision_query` conditions (prompt, expected response checks, model override, capture variable) and actions targeting Gemini elements, via the GUI and JSON, as defined in `gui_config.py`.**
*   **NFR-CONF-002: Logging Configuration:** Logging behavior MUST be primarily controlled via `APP_ENV` and secondarily via CLI runtime flags.
*   **NFR-CONF-003: Core Loop Interval (Bot Runtime):** The `monitoring_interval_seconds` MUST be configurable.
*   **NFR-CONF-004: Analysis Parameters:** Key parameters for local analysis engines (e.g., `analysis_dominant_colors_k`) SHOULD be configurable. **v4.0.0 (Gemini): The default Gemini model (e.g., "gemini-1.5-flash-latest") MUST be configurable in profile settings (`settings.gemini_default_model_name`), and can be overridden per `gemini_vision_query` condition.**

---