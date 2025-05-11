// File: docs/NON_FUNCTIONAL_REQUIREMENTS.MD
# Non-Functional Requirements

This document outlines the non-functional requirements for the visual automation tool, describing *how well* the system should perform its functions, its qualities, and constraints. These apply to both the bot runtime engine and the GUI Profile Editor, as applicable.

## NFR-PERF: Performance

*   **NFR-PERF-001: Low Latency Capture (Bot Runtime):** Screen capture of defined regions SHOULD be performed with minimal latency (e.g., target < 50-100ms where feasible, system dependent) to enable near real-time analysis for typical interactive use cases.
*   **NFR-PERF-002: Efficient Analysis (Bot Runtime):** Image analysis operations (color checking, template matching, OCR, dominant color) on captured regions SHOULD be computationally efficient. The total duration of analysis for all regions in a cycle SHOULD be significantly less than the `monitoring_interval_seconds` to avoid falling behind. The "Selective Analysis per Rule" feature (FR-ANALYZE-006) is critical for achieving this.
*   **NFR-PERF-003: Configurable Monitoring Interval (Bot Runtime):** The capture/analysis/action loop speed (via `monitoring_interval_seconds` in profile settings) MUST be configurable by the user to balance responsiveness and system load.
*   **NFR-PERF-004: Minimal System Impact (Bot Runtime):** While active, the bot SHOULD strive to minimize its impact on overall system performance (CPU, memory usage), especially when running in the background for extended periods. This is aided by selective analysis and efficient library use.
*   **NFR-PERF-005: Responsive GUI Profile Editor:** The `MainAppWindow` GUI SHOULD load and save profiles in a timely manner (e.g., within a few seconds for profiles of typical complexity and size). User interactions (selecting items, typing in fields, changing options via dropdowns) SHOULD feel responsive, with UI updates (e.g., dynamic parameter field rendering) occurring promptly without noticeable lag or freezing.

## NFR-USAB: Usability

*   **NFR-USAB-001: Ease of Configuration (GUI Focus):** Defining all aspects of a bot profile—including settings, regions (with graphical selection), templates (with image preview and file management), and complex rules (with single/compound conditions, sub-conditions, condition/action types, all parameters, variable captures, and condition structure conversion)—MUST be achievable and intuitive through the `MainAppWindow` GUI. The GUI should significantly reduce the need for direct JSON editing for most users.
*   **NFR-USAB-002: Intuitive Rule Creation & Editing (GUI):** The GUI MUST present rule structures and their parameters in a clear, organized, and understandable manner. The workflow for creating, modifying, and managing rules (including sub-conditions) should be logical and discoverable.
*   **NFR-USAB-003: Clear Feedback & Logging (System-Wide):** The system (CLI runtime and GUI editor) MUST provide clear, timely, and actionable feedback on its operations, current state, successes, warnings, and errors. This includes:
    *   Informative console output for CLI operations.
    *   Descriptive dialog boxes (info, warning, error) and a persistent status bar for messages in the GUI.
    *   Comprehensive, persistent, and well-formatted logs (as per ADR-007) for diagnostics and operational review for both backend and GUI components.
*   **NFR-USAB-004: Interruptibility (Bot Runtime):** Users MUST be able to easily start (via CLI `run` command) and stop (via CLI `Ctrl+C`) the bot's monitoring and action execution loop.
*   **NFR-USAB-005: Configuration Clarity (JSON & GUI):** While the GUI is the primary editor, the underlying JSON profile format SHOULD remain reasonably human-readable and be well-documented (e.g., in `TECHNICAL_DESIGN.MD` with examples). The GUI must accurately represent and faithfully manage this JSON structure.
*   **NFR-USAB-006: GUI Input Validation & Error Prevention:** The GUI editor MUST implement robust validation for all user-editable fields (names, numeric values, BGR color strings, file selections, etc.). It MUST prevent the direct saving of clearly invalid data structures or parameter values and guide the user with specific, helpful error messages displayed via `messagebox`.
*   **NFR-USAB-007: GUI State Management:** The GUI MUST reliably manage its internal state, including tracking unsaved changes (dirty flag and visual indicator like "*" in title), current selections in lists, and maintaining consistency between the displayed UI elements and the internal `profile_data` representation. It must correctly handle prompts to save on close or when opening new profiles if changes are unsaved.

## NFR-ACCU: Accuracy (Bot Runtime)

*   **NFR-ACCU-001: Precise Region Capture:** Captured image data MUST accurately correspond to user-defined screen region coordinates.
*   **NFR-ACCU-002: Reliable Analysis Results:**
    *   Color detection (pixel, average, dominant) SHOULD be accurate under consistent display conditions. Tolerances MUST be configurable by the user.
    *   Template matching SHOULD reliably find defined templates when present, respecting user-configurable confidence thresholds.
    *   OCR (when used) SHOULD achieve reasonable accuracy for clear, standard fonts within the defined region. Reported average word confidence scores SHOULD be a meaningful indicator and usable as a criterion in rules.
*   **NFR-ACCU-003: Consistent Action Execution:** Actions triggered (mouse clicks, key presses) SHOULD be performed reliably and accurately at the intended target locations or with the intended inputs, respecting any configured pre-action pauses.

## NFR-REL: Reliability & Robustness (System-Wide)

*   **NFR-REL-001: Stable Operation:** Both the bot runtime engine and the GUI Profile Editor SHOULD operate stably for extended periods of use without unexpected crashes, freezes, or memory leaks. The background monitoring loop (threaded) for the bot must be robust. The GUI must handle editing of complex profiles and dynamic UI updates without instability.
*   **NFR-REL-002: Graceful Error Handling:** The system MUST handle common and unexpected errors gracefully across all components. This includes:
    *   Runtime errors (e.g., Tesseract OCR engine not found, screen capture permission issues, invalid action parameters after variable substitution).
    *   GUI errors (e.g., file I/O problems during profile load/save, invalid user inputs that bypass initial validation, issues rendering dynamic UI elements, problems with template image file operations).
    *   Informative error messages should be provided to the user (console for CLI, GUI dialogs/status bar for GUI editor) and detailed exceptions MUST be logged.
*   **NFR-REL-003: Data Integrity (Profile Saving):** The GUI editor MUST ensure that saving a profile results in a structurally valid JSON file according to the application's defined schema. It should prevent corruption of existing profiles due to UI errors or incomplete save operations. User should be notified of save success/failure.
*   **NFR-REL-004: Resource Management:** The application (both runtime bot and GUI editor) should manage system resources (memory, file handles, GDI objects on Windows if applicable) effectively to prevent leaks or excessive consumption over time.

## NFR-MAINT: Maintainability

*   **NFR-MAINT-001: Modular Code:** The codebase MUST be organized into clearly defined, modular Python packages and modules (e.g., `core`, `engines`, `ui.cli`, `ui.gui`) with well-defined responsibilities and interfaces to promote separation of concerns and ease of updates or extensions.
*   **NFR-MAINT-002: Code Clarity & Documentation:** All Python code MUST be well-commented where logic is non-obvious. All public classes, methods, and significant functions MUST have comprehensive docstrings adhering to the Google Python Style. Key design decisions and system architecture MUST be documented in ADRs and `TECHNICAL_DESIGN.MD`.
*   **NFR-MAINT-003: Testability:** Core logic in engines and complex GUI interaction handlers SHOULD be designed with testability in mind, facilitating future implementation of automated unit or integration tests.
*   **NFR-MAINT-004: Diagnosability:** The application MUST be highly diagnosable, primarily through its comprehensive, structured, and configurable logging output across all components. Logs should allow developers to trace execution flow, understand state changes, and identify root causes of issues efficiently.

## NFR-SEC: Security

*   **NFR-SEC-001: User Control & Awareness (Bot Runtime):** The bot operates with the permissions of the user running it. Users MUST be made explicitly aware (e.g., through documentation and clear UI indicators if a bot is "running" from GUI in a future feature) that the bot is observing parts of their screen and can perform system-level inputs (mouse, keyboard).
*   **NFR-SEC-002: No Unintended Data Transmission:** The application SHOULD NOT transmit screen captures, configuration data, or logs over any network unless explicitly configured by the user as part of a specific, user-initiated feature (e.g., a future "webhook" action, which would itself require careful security design, user consent, and clear indication of data being sent).
*   **NFR-SEC-003: Secure Configuration Handling:** Profile files (`.json`) and environment files (`.env`) are user-managed. The application must load them safely (e.g., `json.load` is safe; avoid `eval()` or `pickle` on user-provided configuration data). The `.env` file, which may contain environment-specifics, MUST be included in `.gitignore`. Template images provided by the user are treated as data; the application should handle them as image files without executing them. File operations in the GUI (like template copying/deletion) must be restricted to expected project/profile directories.

## NFR-CONF: Configurability

*   **NFR-CONF-001: Comprehensive Profile Configuration (via GUI & JSON):** All aspects of bot behavior—regions, templates, analysis types and their parameters, rule logic (single/compound conditions, sub-conditions, actions, variable capture and usage), and general settings—MUST be configurable through the JSON profile format, and fully manageable through the `MainAppWindow` GUI editor.
*   **NFR-CONF-002: Logging Configuration:** Logging behavior (levels, output destinations, formats) MUST be primarily controlled via the `APP_ENV` variable (in `.env`) and secondarily via CLI runtime flags which can override console handler verbosity.
*   **NFR-CONF-003: Core Loop Interval (Bot Runtime):** The `monitoring_interval_seconds` for the bot's main execution loop MUST be configurable in the profile settings and editable via the GUI.
*   **NFR-CONF-004: Analysis Parameters:** Key parameters for analysis engines (e.g., `analysis_dominant_colors_k`) should be configurable in profile settings and editable via the GUI.

---