# ADR-003: Configuration Profile Storage Format

*   **Status:** Approved (v4.0.0: Schema expanded for AI features, format remains JSON)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool (Mark-I) needs to store user configurations (bot profiles), which include:
*   Definitions of screen regions to monitor.
*   Paths to template images for matching.
*   Analysis parameters for these regions/conditions.
*   Rules that link analysis outcomes to specific actions (single or compound conditions).
*   Details of the actions to be performed, including parameters for variable capture and use. **(v4.0.0 Update): This now includes parameters for AI-driven actions like `gemini_perform_task` which can take natural language commands.**
*   General profile settings (e.g., monitoring interval, **default Gemini model name**).

This collection of settings needs to be saved to a file and loaded back. The format should be human-readable (to a degree), easy to parse by Python, and flexible enough to accommodate evolving rule structures and features.

## Considered Options

1.  **JSON (JavaScript Object Notation):**
    *   Pros: Widely adopted, human-readable. Natively supported by Python's `json` module. Good for nested data structures like rules, conditions, and actions.
    *   Cons: No native comments. Strict syntax (though less of an issue when primarily GUI-managed).

2.  **INI File Format (via `configparser`):**
    *   Pros: Simple, supports comments. Python's `configparser` module.
    *   Cons: Less suited for deeply nested or complex data structures (like lists of rules, each with nested conditions/actions). Values are read as strings, requiring manual conversion.

3.  **YAML (YAML Ain't Markup Language):**
    *   Pros: Very human-readable, supports comments. Excellent for complex, nested data.
    *   Cons: Requires an external library (e.g., `PyYAML`). Parsing can be slower than JSON. Potential security concerns with default `yaml.load()` if not using `yaml.safe_load()`.

4.  **Custom Binary Format (e.g., using `pickle`):**
    *   Pros: Efficient storage/parsing. Can directly serialize Python objects.
    *   Cons: Not human-readable. Python-specific. Significant security risks with `pickle` if loading untrusted files. Version compatibility issues between Python versions or application versions if object structures change.

## Decision Outcome

**Chosen Option:** JSON

**Justification:**
*   **Human Readability & Editability:** JSON strikes a good balance. While not as comment-friendly as YAML, its structure is widely understood, and manual inspection/tweaking is possible if necessary (though the GUI is the primary editor).
*   **Native Python Support:** The built-in `json` module is trivial to integrate and requires no external dependencies for this core function, which is a significant advantage.
*   **Sufficient Data Structuring:** JSON's support for nested objects (Python dictionaries) and arrays (Python lists) is perfectly suited for representing the hierarchical nature of profiles. This has proven flexible enough to accommodate new AI-driven rule conditions (e.g., `gemini_vision_query`) and complex actions (e.g., `gemini_perform_task` with its own set of parameters like `natural_language_command`).
*   **Wide Adoption:** It's a de facto standard for configuration files and data interchange in many applications.
*   **Performance:** JSON parsing is generally fast and efficient for the anticipated sizes of profile files.
*   **GUI Focus:** Since the GUI (`MainAppWindow`) is the primary means of creating and editing profiles, the lack of comments in JSON is less of a drawback. The GUI provides context and descriptions for all fields.

The strict syntax of JSON is managed by `json.dump()` for saving (ensuring well-formed output) and `json.load()` for loading (which will raise errors on malformed files, aiding in data integrity).

## Consequences

*   Bot profiles will be stored in `.json` files, typically within a `profiles/` directory located next to the main application or in a user-configurable location managed by `ConfigManager`. Template images associated with a profile will be stored in a `templates/` subdirectory next to their respective profile JSON file.
*   The application (`ConfigManager`) will use Python's built-in `json` module for loading and saving profiles.
*   A clear schema or an example of the JSON profile structure (including regions, templates, rules with single/compound conditions, variable capture, standard actions, **AI-driven task actions like `gemini_perform_task` with its parameters for natural language commands and context**, and settings like **`gemini_default_model_name`**) is documented in `TECHNICAL_DESIGN.MD` and exemplified by sample profiles.
*   The GUI editor (`MainAppWindow`) is responsible for presenting these JSON structures in a user-friendly way and ensuring that user inputs are correctly translated back into the valid JSON format upon saving.

---