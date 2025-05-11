// File: docs/NON_FUNCTIONAL_REQUIREMENTS.MD
# Non-Functional Requirements

This document outlines the non-functional requirements for the visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor, as applicable.

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):** Image analysis operations (color checking, template matching, OCR, dominant color) on captured regions SHOULD be computationally efficient. The total duration of analysis for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds` to avoid falling behind. The "Selective Analysis per Rule" feature (FR-ANALYZE-006) is critical for this.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The capture/analysis/action loop speed (via `monitoring_interval_seconds`) MUST be configurable by the user to balance responsiveness and system load.
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on overall system performance (CPU, memory usage), especially when running in the background for extended periods. This is aided by selective analysis.
*   **NFR-PERF-005: Responsive GUI Profile Editor:** The `MainAppWindow` GUI SHOULD load and save profiles in a timely manner (e.g., within a few seconds for typical profiles). User interactions (selecting items, typing, changing options) SHOULD feel responsive, with UI updates occurring promptly. Dynamic rendering of parameter fields should not cause noticeable lag.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus):** Defining all aspects of a bot profile (settings, regions, templates, complex rules with conditions/actions/parameters/variables, and condition structure conversion) MUST be achievable and intuitive through the `MainAppWindow` GUI, minimizing the need for direct JSON editing for most users.
*   **NFR-USAB-002: Intuitive Rule Creation & Editing (GUI):** The GUI MUST present rule structures (single, compound, sub-conditions) and their parameters in a clear, organized, and understandable manner. Workflow for creating and modifying rules should be logical.
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** The system (CLI runtime and GUI editor) MUST provide clear, actionable feedback on its operations, current state, successes, warnings, and errors. This includes:
    *   Informative console output for CLI operations.
    *   Descriptive dialog boxes (info, warning, error) and status messages in the GUI.
    *   Comprehensive, persistent, and well-formatted logs (as per ADR-007) for diagnostics and operational review for both backend and GUI.
*   **NFR-USAB-004: Interruptibility (Bot Runtime):** Users MUST be able to easily start (CLI `run`) and stop (CLI `Ctrl+C`) the bot's operation.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** While the GUI is primary, the underlying JSON profile format SHOULD remain reasonably human-readable and be well-documented (e.g., in `TECHNICAL_DESIGN.MD` with examples). The GUI must accurately represent and manage this JSON structure.
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** The GUI editor MUST implement robust validation for all user-editable fields (names, numbers, selections, BGR strings, etc.). It MUST prevent saving of clearly invalid data and guide the user with specific error messages.
*   **NFR-USAB-007: GUI State Management:** The GUI MUST reliably manage its state, including unsaved changes (dirty flag), current selections, and consistency between the displayed UI and the internal `profile_data`.

## NFR-ACCU: Accuracy (Bot Runtime)

*   **NFR-ACCU-001: Precise Region Capture:** Captured image data MUST accurately correspond to user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results:**
    *   Color detection (pixel, average, dominant) SHOULD be accurate under consistent display conditions. Tolerances MUST be configurable.
    *   Template matching SHOULD reliably find defined templates with user-configurable confidence thresholds.
    *   OCR (when used) SHOULD achieve reasonable accuracy for clear, standard fonts. Reported confidence scores SHOULD be a meaningful indicator and usable in rules.
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered (mouse clicks, key presses) SHOULD be performed reliably and accurately at the intended target locations or with the intended inputs, respecting any configured pauses.

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Both the bot runtime engine and the GUI Profile Editor SHOULD operate stably for extended periods of use without crashing or freezing. The background monitoring loop (threaded) must be robust. The GUI must handle editing of complex profiles without instability.
*   **NFR-REL-002: Graceful Error Handling:** The system MUST handle common and unexpected errors gracefully. This includes:
    *   Runtime errors (e.g., OCR engine not found, capture issues, invalid action parameters after variable substitution).
    *   GUI errors (e.g., file I/O problems during profile load/save, invalid user inputs not caught by initial validation, issues rendering dynamic UI).
    *   Informative error messages should be provided to the user (console/GUI dialog) and detailed exceptions logged.
*   **NFR-REL-003: Data Integrity:** The GUI editor MUST ensure that saving a profile results in a structurally valid JSON file according to the defined schema. It should not corrupt existing profiles due to UI errors or partial saves.
*   **NFR-REL-004: Resource Management:** The application (both runtime and GUI) should manage resources (memory, file handles) effectively to prevent leaks or excessive consumption over time.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** The codebase MUST be organized into clearly defined, modular components (e.g., core services, engines for capture/analysis/rules/action, UI elements) with well-defined responsibilities and interfaces. This applies to both backend and GUI code.
*   **NFR-MAINT-002: Code Clarity & Documentation:** All Python code MUST be well-commented where logic is not immediately obvious. All public classes and methods MUST have comprehensive docstrings (Google Python Style). Key design decisions and architecture MUST be documented in ADRs and `TECHNICAL_DESIGN.MD`.
*   **NFR-MAINT-003: Testability:** Core logic (especially in engines and complex GUI interactions) SHOULD be designed with testability in mind, even if automated unit/integration tests are implemented later.
*   **NFR-MAINT-004: Diagnosability:** The application MUST be highly diagnosable, primarily through its comprehensive and structured logging output across all components. Logs should allow developers to trace execution flow and identify root causes of issues.

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness (Bot Runtime):** The bot operates with user permissions. Users MUST be made explicitly aware (e.g., through documentation and clear UI indicators if a bot is "running" from GUI in future) that the bot is observing parts of their screen and can perform inputs.
*   **NFR-SEC-002: No Unintended Data Transmission:** The bot SHOULD NOT transmit screen captures, configuration data, or logs over any network unless explicitly configured by the user as part of a specific feature (e.g., a future "webhook" action, which would itself require careful security design and user consent).
*   **NFR-SEC-003: Secure Configuration Handling:** Profile files (`.json`) and environment files (`.env`) are user-managed. The application should load them safely (e.g., `json.load` is safe; avoid `eval` or `pickle` on user-provided config data). The `.env` file containing potentially sensitive (though currently just `APP_ENV`) information MUST be in `.gitignore`. Template images are also user-provided; the application should handle them as image data without executing them.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Comprehensive Profile Configuration (via GUI & JSON):** All aspects of bot behavior—regions, templates, analysis types and their parameters, rule logic (single/compound, conditions, actions, variable usage), and general settings—MUST be configurable through the JSON profile, and manageable through the GUI editor.
*   **NFR-CONF-002: Logging Configuration:** Logging behavior (levels, output destinations) MUST be primarily controlled via the `APP_ENV` variable and secondarily via CLI runtime flags for console verbosity.
*   **NFR-CONF-003: Core Loop Interval (Bot Runtime):** The interval/FPS of the main monitoring loop MUST be configurable in the profile settings.

---