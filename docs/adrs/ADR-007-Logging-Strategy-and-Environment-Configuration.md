# ADR-007: Logging Strategy and Environment Configuration

*   **Status:** Approved (Implemented; v4.0.0 includes `GEMINI_API_KEY` in .env and specific logging for AI interactions)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool (Mark-I), encompassing its bot runtime, AI interactions, and GUI editor, requires robust and configurable logging for:
*   Development: Detailed tracing, variable states, component interactions.
*   Debugging: Identifying issues, error contexts.
*   User Support/Troubleshooting: Gathering information.
*   Operational Monitoring (Bot Runtime): Recording key events, decisions, actions, **including AI model interactions (v4.0.0)**.

Logs need to be comprehensive, persistent, and configurable (level, destinations). We also need a standard for managing environment-specific settings, primarily `APP_ENV` and sensitive keys like `GEMINI_API_KEY`.

## Considered Options for Environment Configuration

1.  **`.env` files with `python-dotenv` library:**
    *   Pros: Common practice. Keeps environment-specific variables (like `APP_ENV`, **`GEMINI_API_KEY`**) out of version control. Simple.
    *   Cons: Requires `python-dotenv` external dependency.
2.  Separate JSON/YAML config files per environment.
3.  Direct OS Environment Variables.
4.  Hardcoding (Not viable).

## Considered Options for Logging

1.  **Python's built-in `logging` module:**
    *   Pros: Standard library. Highly flexible (levels, handlers, formatters, filters). Thread-safe. Hierarchical.
    *   Cons: Initial setup can be slightly verbose (one-time effort).
2.  Third-party logging libraries (e.g., Loguru, structlog).
3.  `print()` statements (Not viable).

## Decision Outcome

**Chosen Options:**

*   **Environment Configuration:** Use **`.env` files** at the project root, loaded by the **`python-dotenv` library**, to manage `APP_ENV` and **`GEMINI_API_KEY` (for v4.0.0+)**.
*   **Logging:** Utilize **Python's built-in `logging` module**, configured by `core/logging_setup.py`.

**Justification:**
*   **`.env` files with `python-dotenv`:** Standard, developer-friendly for managing environment-specific configurations (like API keys) without hardcoding or relying solely on OS variables.
*   **`logging` module:** Power, flexibility, and standard library status make it suitable. Provides all necessary features with careful setup, avoiding an extra dependency.

## Logging Strategy Details (Implemented in `core/logging_setup.py` and adhered to by modules)

*   **Logger Naming:** Modules use `logging.getLogger(__name__)`. Root application logger: `mark_i`.
*   **Log Levels:** Standard levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
*   **Log Format:**
    *   File logs: `%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s`
    *   Console logs: More concise, but detailed in `development` `APP_ENV`.
*   **Handlers & Configuration by `APP_ENV`:**
    *   `logs/` directory created (and gitignored).
    *   **Console Handler (`StreamHandler`):** `DEBUG` for `development`, `INFO` for `uat`/`production`. CLI flags can override.
    *   **File Handler (`TimedRotatingFileHandler`):** Rotates daily, `DEBUG` for `development`, `INFO` for `uat`/`production`.
*   **Initialization:** `core.logging_setup.setup_logging()` at startup.
*   **Critical Principle:** All significant operations, decisions, state changes, errors, user interactions (backend and GUI), **and especially all interactions with external APIs like Google Gemini (requests, summarized prompts, model used, responses, errors, latency, NLU parsing steps, decision outcomes from `GeminiDecisionModule`) MUST include appropriate and informative logging statements, as detailed in `TECHNICAL_DESIGN.MD` Section 7 and 14.**

## Consequences

*   A `.env` file (e.g., containing `APP_ENV=development` and `GEMINI_API_KEY=your_key_here`) is expected in the project root for local development. This file **MUST** be added to `.gitignore`.
*   The `python-dotenv` library is a project dependency.
*   `mark_i/core/logging_setup.py` encapsulates logging initialization.
*   Developers must be diligent in adding comprehensive logging statements, using appropriate levels, especially for all AI-related operations.
*   The `logs/` directory created by the application **MUST** be added to `.gitignore`.

---