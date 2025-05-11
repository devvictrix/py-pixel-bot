// File: docs/adrs/ADR-003-Configuration-Profile-Storage-Format.md
# ADR-003: Configuration Profile Storage Format

*   **Status:** Approved
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool needs to store user configurations (bot profiles), which include:
*   Definitions of screen regions to monitor.
*   Analysis parameters for these regions.
*   Rules that link analysis outcomes to specific actions.
*   Details of the actions to be performed.

This collection of settings needs to be saved to a file and loaded back. The format should be human-readable, easy to parse by Python, and flexible.

## Considered Options

1.  **JSON (JavaScript Object Notation):**
    *   Pros: Widely adopted, human-readable. Natively supported by Python's `json` module. Good for nested data.
    *   Cons: No native comments. Strict syntax.

2.  **INI File Format (via `configparser`):**
    *   Pros: Simple, supports comments. Python's `configparser` module.
    *   Cons: Less suited for deeply nested data. Values read as strings requiring conversion.

3.  **YAML (YAML Ain't Markup Language):**
    *   Pros: Very human-readable, supports comments. Good for complex, nested data.
    *   Cons: Requires an external library (e.g., `PyYAML`). Parsing can be slower.

4.  **Custom Binary Format (e.g., using `pickle`):**
    *   Pros: Efficient storage/parsing. Can serialize Python objects.
    *   Cons: Not human-readable. Python-specific. Security risks with `pickle`. Version compatibility.

## Decision Outcome

**Chosen Option:** JSON

**Justification:**
*   **Human Readability & Editability:** JSON strikes a good balance and is familiar.
*   **Native Python Support:** The built-in `json` module is trivial to integrate, no external dependencies for this core function.
*   **Sufficient Data Structuring:** JSON's support for nested objects (dictionaries) and arrays (lists) is well-suited for representing regions, rules, and actions.
*   **Wide Adoption:** De facto standard for configuration files.
*   **Performance:** Adequate for anticipated profile sizes.

The lack of comments is a minor drawback mitigated by clear key naming and the potential for a `"comment"` field within objects if needed. The primary interface for editing profiles will be the GUI.

## Consequences

*   Bot profiles will be stored in `.json` files, typically in a `profiles/` directory.
*   The application will use Python's `json` module for loading and saving profiles.
*   A clear schema for the JSON profiles will be defined and documented (e.g., in `TECHNICAL_DESIGN.MD` or a dedicated schema file).
*   Manual editing by users, while possible, should be approached with caution. GUI tools will be the primary interface.

---