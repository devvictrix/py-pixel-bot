// File: adrs/ADR-007-Logging-Strategy-and-Environment-Configuration.md
# ADR-007: Logging Strategy and Environment Configuration

*   **Status:** Approved
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool needs robust logging for development, debugging, UAT, and production monitoring. Logs should be comprehensive, persistent, and their verbosity/destination configurable based on the application environment (`development`, `uat`, `production`). We also need a standard way to manage environment-specific settings.

## Considered Options for Environment Configuration

1.  **`.env` files with `python-dotenv` library:**
    *   Pros: Common practice. Keeps env vars out of version control. Simple.
    *   Cons: Requires `python-dotenv` dependency.
2.  **Separate JSON/YAML config files per environment:**
    *   Pros: Explicit, structured.
    *   Cons: Requires logic to load correct file. File proliferation.
3.  **Hardcoding (Not viable).**

## Considered Options for Logging

1.  **Python's built-in `logging` module:**
    *   Pros: Standard library, highly configurable (levels, handlers, formatters), thread-safe. Supports multiple handlers.
    *   Cons: Initial setup slightly verbose (one-time effort).
2.  **Third-party logging libraries (e.g., Loguru, structlog):**
    *   Pros: Simpler APIs, advanced features out-of-box.
    *   Cons: External dependencies. Overkill if standard logging suffices.
3.  **`print()` statements (Not viable for robust logging).**

## Decision Outcome

**Chosen Options:**

*   **Environment Configuration:** Use `.env` files (e.g., `.env` at project root) to store `APP_ENV`. The `python-dotenv` library will load these.
    *   `APP_ENV` values: `development`, `uat`, `production`.
*   **Logging:** Utilize Python's built-in `logging` module.

**Justification:**
*   **`.env` files (`python-dotenv`):** Standard, secure pattern for environment-specific configurations. Integrates well with deployment.
*   **`logging` module:** Powerful, flexible, standard library, well-suited for structured, filterable logs for different environments.

## Logging Strategy Details

*   **Logger Naming:** `logging.getLogger(__name__)` for hierarchical loggers.
*   **Log Levels:** Standard: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
*   **Log Format (Standard):** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`. Development may include `%(module)s:%(lineno)d`.
*   **Log Handlers and Configuration based on `APP_ENV`:**
    *   **`APP_ENV=development`:**
        *   Console Handler: `DEBUG` level, verbose format.
        *   File Handler (e.g., `app_dev.log`): `DEBUG` level, detailed format.
    *   **`APP_ENV=uat`:**
        *   Console Handler: `INFO` level, standard format.
        *   File Handler (e.g., `app_uat.log`): `INFO` level, standard format. Basic rotation.
    *   **`APP_ENV=production`:**
        *   Console Handler: `WARNING` (or `INFO`), concise format.
        *   File Handler (e.g., `app_prod.log`): `INFO` level, standard format. Robust log rotation (`logging.handlers.RotatingFileHandler` or `TimedRotatingFileHandler`).
*   **Initialization:** Logging configured once at app startup via a dedicated setup function, reading `APP_ENV`.
*   **Persistence:** Logs are persistent, managed by rotation, not "removed."

## Consequences

*   A `.env` file (e.g., with `APP_ENV=development`) needed in project root (added to `.gitignore`).
*   `python-dotenv` added as a dependency.
*   A dedicated module/function (e.g., `config.py` or `logging_setup.py`) for initializing logging.
*   All important steps, decisions, errors, state changes MUST include appropriate logging statements.
*   Clear documentation on setting `APP_ENV` for deployment.

---