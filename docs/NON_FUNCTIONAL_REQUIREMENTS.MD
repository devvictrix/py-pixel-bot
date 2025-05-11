// File: docs/NON_FUNCTIONAL_REQUIREMENTS.MD
# Non-Functional Requirements

This document outlines the non-functional requirements for the visual automation tool, describing *how well* the system should perform its functions.

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture:** Screen capture of the defined region SHOULD be performed with minimal latency to enable near real-time analysis for bot runtime.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):** Image analysis operations on the captured region SHOULD be computationally efficient. The duration of analysis should be significantly less than the capture interval for continuous monitoring. **Selective analysis (FR-ANALYZE-006) contributes to this.**
*   **NFR-PERF-003: Configurable FPS/Interval:** For continuous monitoring, the capture/analysis loop speed SHOULD be configurable by the user.
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on overall system performance.
*   **NFR-PERF-005: Responsive GUI:** The GUI Profile Editor SHOULD be responsive to user interactions, loading and saving profiles in a timely manner for typical profile sizes. Complex operations (like re-rendering large rule editors) should not unduly freeze the UI.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI):** Defining target screen regions, templates, rules (including conditions, actions, parameters, variables), and profile settings SHOULD be straightforward and intuitive through the GUI editor.
*   **NFR-USAB-002: Intuitive Rule Creation (GUI):** Creating analysis rules and linking them to actions in the GUI SHOULD be understandable with clear visual cues and organization.
*   **NFR-USAB-003: Clear Feedback & Logging:** The system MUST provide clear feedback on its operations, detections, and any errors encountered (both in CLI runtime and GUI editor). Comprehensive and persistent logging, configurable by environment (`APP_ENV`), MUST be implemented to facilitate debugging and operational monitoring.
*   **NFR-USAB-004: Interruptibility (Bot Runtime):** Users MUST be able to easily start and stop the bot's operation (e.g., via CLI Ctrl+C).
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** The JSON profile format SHOULD be well-documented and logically structured. The GUI MUST present this information clearly.
*   **NFR-USAB-006: GUI Input Validation:** The GUI editor MUST validate user inputs for parameters and settings, preventing invalid data entry and providing helpful error messages.

## NFR-ACCU: Accuracy (Bot Runtime)

*   **NFR-ACCU-001: Precise Region Capture:** The captured image data MUST accurately correspond to the user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results:**
    *   Color detection SHOULD be accurate.
    *   Template matching SHOULD have configurable confidence levels.
    *   OCR SHOULD have reasonable accuracy, and its confidence scores SHOULD be usable.
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered SHOULD be performed reliably and accurately.

## NFR-REL: Reliability & Robustness

*   **NFR-REL-001: Stable Operation (Bot Runtime & GUI):** The bot and the GUI editor SHOULD operate stably for extended periods without crashing. The background monitoring loop must be robust. The GUI must handle complex profile data without instability.
*   **NFR-REL-002: Graceful Error Handling (Bot Runtime & GUI):** The system MUST handle common errors gracefully (e.g., OCR engine failure, invalid configuration, file I/O errors in GUI). It should provide informative messages (console/log for bot, dialogs/status for GUI).
*   **NFR-REL-003: Resilience to Minor Visual Noise (Future - Bot Runtime):** Analysis techniques SHOULD ideally offer options for some resilience to minor visual noise.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** The codebase SHOULD be modular (e.g., capture, analysis, action, rules engines, config management, UI components) to promote separation of concerns and ease of updates.
*   **NFR-MAINT-002: Code Clarity & Documentation:** Code SHOULD be well-commented, and key functions/classes/modules SHOULD have docstrings (Google Python Style). Design decisions SHOULD be documented in ADRs and `TECHNICAL_DESIGN.MD`. Code MUST include thorough logging.
*   **NFR-MAINT-003: Testability:** Core logic SHOULD be designed to be unit-testable.
*   **NFR-MAINT-004: Diagnosability:** The application MUST be highly diagnosable through its logging output.

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness:** Users MUST be aware that the bot (when running) is observing parts of their screen and can perform inputs. This should be clear in user documentation.
*   **NFR-SEC-002: No Unintended Data Transmission:** The bot SHOULD NOT transmit screen captures, configuration data, or logs over the network unless explicitly part of a user-configured feature.
*   **NFR-SEC-003: Secure Configuration:** Configuration files are user-managed. The `.env` file should be in `.gitignore`.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Analysis Parameters:** Parameters for analysis MUST be configurable by the user via the profile (and thus GUI).
*   **NFR-CONF-002: Action Parameters:** Details of actions MUST be configurable.
*   **NFR-CONF-003: Logging Configuration:** Logging behavior MUST be primarily controlled via `APP_ENV` and CLI flags.
*   **NFR-CONF-004: Core Loop Interval:** The interval/FPS of the main monitoring loop MUST be configurable.

---