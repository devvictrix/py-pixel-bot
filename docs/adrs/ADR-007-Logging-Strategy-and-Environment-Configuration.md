// File: docs/adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md
# ADR-007: Logging Strategy and Environment Configuration

*   **Status:** Approved (and implemented)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool, encompassing both its bot runtime and GUI editor, requires robust and configurable logging for multiple purposes:
*   **Development:** Detailed tracing of execution paths, variable states, and component interactions.
*   **Debugging:** Identifying issues and understanding error contexts.
*   **User Support/Troubleshooting (UAT/Production):** Allowing users or support personnel to gather information about bot behavior or GUI issues.
*   **Operational Monitoring (Bot Runtime):** Recording key events, decisions, and actions taken by the bot.

Logs need to be:
*   **Comprehensive:** Covering all significant operations.
*   **Persistent:** Saved to files for later review.
*   **Configurable:** Log verbosity (level) and output destinations (console, file) should be adjustable based on the application environment (e.g., `development`, `uat`, `production`) or user preference (e.g., CLI flags).

We also need a standard method for managing environment-specific settings, primarily the `APP_ENV` variable that drives logging configuration.

## Considered Options for Environment Configuration

1.  **`.env` files with `python-dotenv` library:**
    *   Pros: Common, well-understood practice in Python projects. Keeps environment-specific variables (like API keys, or `APP_ENV` in our case) out of version control. Simple to use.
    *   Cons: Requires the `python-dotenv` external dependency.
2.  **Separate JSON/YAML config files per environment (e.g., `config_dev.json`, `config_prod.json`):**
    *   Pros: Explicit and structured. Can hold more complex configurations than simple key-value pairs if needed.
    *   Cons: Requires application logic to determine and load the correct file based on some external indicator (e.g., another environment variable). Can lead to file proliferation if many environments or settings.
3.  **Direct Environment Variables:** Relying solely on OS-level environment variables.
    *   Pros: Standard OS feature. No application-level dependencies.
    *   Cons: Less convenient for local development setup across different machines or for developers to manage. `.env` files provide a project-local way to define these.
4.  **Hardcoding:** Not a viable or professional option for configurable settings.

## Considered Options for Logging

1.  **Python's built-in `logging` module:**
    *   Pros: Part of the standard library (no external dependency for logging itself). Highly flexible and configurable with levels, handlers (console, file, network, etc.), formatters, and filters. Thread-safe. Supports hierarchical loggers, allowing fine-grained control over logging from different parts of the application.
    *   Cons: Initial setup can be slightly verbose compared to some third-party libraries, but this is a one-time effort for a reusable logging setup module.
2.  **Third-party logging libraries (e.g., Loguru, structlog):**
    *   Pros: Often provide simpler APIs for common logging tasks, more aesthetically pleasing default outputs, and advanced features like easier exception formatting or structured logging out-of-the-box.
    *   Cons: Introduce external dependencies. May be overkill if the standard `logging` module's capabilities are sufficient after proper configuration.
3.  **`print()` statements:** Not viable for robust, configurable, or production-grade logging due to lack of levels, timestamps, formatting control, and easy redirection.

## Decision Outcome

**Chosen Options:**

*   **Environment Configuration:** Use **`.env` files** at the project root, loaded by the **`python-dotenv` library**, to manage the `APP_ENV` variable.
    *   The primary variable will be `APP_ENV`, with possible values: `development`, `uat` (or `testing`), `production`.
*   **Logging:** Utilize **Python's built-in `logging` module**, configured by a dedicated setup module (`core/logging_setup.py`).

**Justification:**
*   **`.env` files with `python-dotenv`:** This is a standard and developer-friendly pattern for managing environment-specific configurations without hardcoding or relying solely on OS environment variables which can be cumbersome for local development. It allows each developer to have their local `APP_ENV` without committing it.
*   **`logging` module:** Its power, flexibility, and status as a standard library module make it the most suitable choice for a project aiming for robustness and maintainability. While third-party libraries can offer convenience, the standard module provides all necessary features (levels, multiple handlers, customizable formatting, hierarchical loggers) with careful setup. This avoids an extra dependency just for logging.

## Logging Strategy Details (Implemented in `core/logging_setup.py`)

*   **Logger Naming:** Modules use `logging.getLogger(__name__)` to leverage the hierarchical nature of loggers. The root logger for the application (e.g., `py_pixel_bot`) is configured.
*   **Log Levels:** Standard levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) are used.
*   **Log Format:** A consistent, detailed format is used for file logs:
    `%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s`
    Console log format might be slightly more concise depending on `APP_ENV`.
*   **Handlers & Configuration by `APP_ENV`:**
    *   A `logs/` directory is created at the project root if it doesn't exist (and is in `.gitignore`).
    *   **Console Handler (`StreamHandler`):**
        *   `development`: `DEBUG` level.
        *   `uat`/`production`: `INFO` level (or `WARNING` for production console if desired).
        *   CLI verbosity flags (`-v`, `-vv` in `__main__.py`) can further adjust the console handler's level at runtime.
    *   **File Handler (`TimedRotatingFileHandler`):**
        *   Rotates daily (e.g., `YYYY-MM-DD.log` inside `logs/`), keeping a configurable number of backup files.
        *   `development`: `DEBUG` level.
        *   `uat`/`production`: `INFO` level.
        *   Includes `APP_ENV` in the log file message format for context.
*   **Initialization:** Logging is configured once at application startup by `core.logging_setup.setup_logging()`, which reads `APP_ENV` (loaded by `core.config_manager.load_environment_variables()`).
*   **Critical Principle:** All significant operations, decisions, state changes, errors, and user interactions (both backend and GUI) MUST include appropriate and informative logging statements.

## Consequences

*   A `.env` file (e.g., containing `APP_ENV=development`) is expected in the project root for local development. This file **MUST** be added to `.gitignore`.
*   The `python-dotenv` library is a project dependency (listed in `requirements.txt`).
*   A dedicated module, `py_pixel_bot/core/logging_setup.py`, encapsulates all logging initialization logic.
*   Developers must be diligent in adding comprehensive logging statements throughout their code, using appropriate log levels.
*   The `logs/` directory needs to be created by the application if it doesn't exist and **MUST** be added to `.gitignore`.

---