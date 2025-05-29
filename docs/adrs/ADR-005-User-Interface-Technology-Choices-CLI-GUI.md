# ADR-005: User Interface Technology Choices (CLI & GUI)

*   **Status:** Approved (and actively being implemented)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool (Mark-I) requires user interfaces for configuration and control:
1.  **Command-Line Interface (CLI):** For initial versions, for users who prefer CLI, and for potentially running bots in headless/scripted environments. Core CLI functions include loading profiles, starting/stopping bot runtime, and invoking GUI tools for specific tasks like region definition or full profile editing.
2.  **Graphical User Interface (GUI):** For user-friendly visual region definition, comprehensive profile management (including intuitive creation and editing of regions, templates, rules, conditions, actions, and settings), and potentially real-time feedback during bot setup or debugging (though live feedback is a more advanced feature).

We need Python technologies for both, prioritizing cross-platform compatibility, ease of development for the defined scope, good user experience, and future growth potential.

## Considered Options

### For Command-Line Interface (CLI)

1.  **`argparse` (Python built-in):**
    *   Pros: Standard library, no external dependencies for this part. Good for parsing arguments and subcommands. Mature and well-understood.
    *   Cons: Can become verbose to define for very complex CLIs with many nested commands or options. Interactive input beyond simple argument parsing needs separate handling (e.g., `input()`).
2.  **`click`:**
    *   Pros: Popular third-party library. Simplifies creating beautiful and composable command-line interfaces, often with less boilerplate than `argparse`. Good support for subcommands.
    *   Cons: External dependency.
3.  **`Typer`:**
    *   Pros: Built on `click` (and `FastAPI`'s Pydantic for validation). Uses Python type hints to define CLI parameters, which can be very modern and clean. Excellent autocompletion support.
    *   Cons: External dependency. Newer than `click` or `argparse`.

### For Graphical User Interface (GUI)

1.  **`Tkinter` (Python built-in):**
    *   Pros: Standard library, universally available with Python. Cross-platform. Simple for very basic GUIs.
    *   Cons: Widgets can look dated on some platforms without significant styling effort. Layout management (pack, grid, place) can be tricky for complex UIs. Advanced widgets often require manual creation or third-party extensions.
2.  **`CustomTkinter`:**
    *   Pros: A modern Python UI library based on Tkinter. Provides updated, themed widgets that look much more contemporary. Retains Tkinter's cross-platform nature and relative ease of use compared to heavier frameworks. Good for creating visually appealing desktop applications without a massive learning curve if one is familiar with Tkinter basics. Actively developed.
    *   Cons: External dependency. Newer than Tkinter itself, so the community and resources, while growing, are smaller than for Tkinter or Qt.
3.  **`PyQt` or `PySide` (Qt bindings):**
    *   Pros: Extremely powerful and feature-rich C++ framework with Python bindings. Produces professional-looking, native-feeling applications. Qt Designer allows for visual UI layout. Large widget set.
    *   Cons: Heavier external dependencies (Qt libraries need to be distributed or installed). Steeper learning curve. Licensing considerations (PyQt is GPL or commercial; PySide is LGPL, more permissive). Can lead to larger application package sizes.
4.  **`Kivy`:**
    *   Pros: Open-source, excellent for creating visually rich, novel UIs, especially those with touch interaction or custom graphics (uses OpenGL). Cross-platform, including mobile.
    *   Cons: External dependency. Follows a different design paradigm than traditional desktop widget toolkits. GUIs might not strictly adhere to the native look and feel of the host operating system, which may or may not be desired. Might be overkill for a tool-focused desktop application unless very specific visual requirements exist.

## Decision Outcome

**Chosen Options:**

*   **For CLI: `argparse` (Python built-in)**
    *   **Justification:** `argparse` is sufficient for the defined CLI scope: `run <profile>`, `add-region <profile>`, and the new `edit [profile]` command. It avoids introducing an external dependency solely for the CLI when the built-in solution is adequate for parsing these commands and their arguments. Its maturity and inclusion in the standard library are strong benefits.
*   **For GUI (Region Definition Tool in AI-Accelerated v1.0.0 & Full Profile Editor in v3.0.0): `CustomTkinter`**
    *   **Justification:** `CustomTkinter` strikes an excellent balance for this project. It allows for the creation of a modern-looking and user-friendly desktop application without the significant overhead, learning curve, or licensing complexities of frameworks like PyQt/PySide. It leverages the stability and cross-platform nature of Tkinter while providing much-needed aesthetic and widget improvements. This choice aligns with the goal of delivering a good user experience for profile configuration. The included themes (like `blue.json`, `dark-blue.json`) are directly from `CustomTkinter`.

## Consequences

*   **CLI Development:**
    *   The CLI is built using Python's `argparse` module, located in `mark_i/ui/cli.py`. It handles parsing commands and options passed at startup.
*   **GUI Development:**
    *   The project has a dependency on the `CustomTkinter` library (and its dependencies, like `Pillow`). This is managed via `requirements.txt`.
    *   The initial GUI component for region selection (`RegionSelectorWindow`) was built with `CustomTkinter`.
    *   The comprehensive profile editor (`MainAppWindow` for v3.0.0) is actively being developed using `CustomTkinter`, handling complex layouts, dynamic widget creation, and data binding for profile elements.
    *   Development requires careful integration between the GUI (`MainAppWindow`) and the backend logic, particularly `ConfigManager` for profile data persistence.
    *   Thorough testing of GUI interactions and state management across different user actions is critical.

---