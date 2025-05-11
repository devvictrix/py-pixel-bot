// File: adrs/ADR-005-User-Interface-Technology-Choices-CLI-GUI.md
# ADR-005: User Interface Technology Choices (CLI & GUI)

*   **Status:** Approved
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool requires user interfaces for configuration and control:
1.  **Command-Line Interface (CLI):** For initial versions (loading profiles, start/stop, basic parameters).
2.  **Graphical User Interface (GUI):** For future versions (visual region definition, profile management, real-time feedback).

We need Python technologies for both, prioritizing cross-platform compatibility, ease of development for initial scope, and future growth.

## Considered Options

### For Command-Line Interface (CLI)

1.  **`argparse` (Python built-in):**
    *   Pros: Standard library. Good for parsing arguments. Mature.
    *   Cons: Can be verbose for complex CLIs. Interactive input needs separate handling.
2.  **`click`:**
    *   Pros: Popular third-party. Simplifies creating composable CLIs.
    *   Cons: External dependency.
3.  **`Typer`:**
    *   Pros: Built on `click`. Uses type hints. Modern. Good autocompletion.
    *   Cons: External dependency. Newer.

### For Graphical User Interface (GUI) - Initial (AI-Accelerated v1.0.0 Region Selector) & Future

1.  **`Tkinter` (Python built-in):**
    *   Pros: Standard library. Cross-platform. Simple for basic GUIs.
    *   Cons: Can look dated. Layout can be tricky. Advanced widgets need effort.
2.  **`CustomTkinter`:**
    *   Pros: Modernizes `Tkinter` with new widgets/themes. Retains Tkinter's simplicity.
    *   Cons: External dependency. Relatively new.
3.  **`PyQt` or `PySide` (Qt bindings):**
    *   Pros: Very powerful, feature-rich. Professional look. Qt Designer.
    *   Cons: External dependencies. Steeper learning curve. Licensing (PyQt: GPL/commercial, PySide: LGPL). Larger app sizes.
4.  **`Kivy`:**
    *   Pros: Open-source, good for visually rich UIs, touch support. Cross-platform.
    *   Cons: External dependency. Different paradigm (OpenGL). Might not match native OS look.

## Decision Outcome

**Chosen Options:**

*   **For CLI: `argparse` (Python built-in)**
    *   **Justification:** Sufficient for initial CLI needs (profile loading, start/stop), avoids external dependencies for this core interaction.
*   **For initial GUI (Region Definition Tool in AI-Accelerated v1.0.0): `CustomTkinter`**
    *   **Justification:** `CustomTkinter` offers a good balance: modern look with Tkinter's stability and cross-platform nature. Ideal for user-friendly region selection and basic profile management. Dependency is manageable. Avoids `PyQt` licensing/complexity for initial GUI scope.

## Consequences

*   **CLI Development:**
    *   Initial CLI built using `argparse`. Interactive elements beyond arguments use `input()`.
*   **GUI Development (Initial & Future):**
    *   The project will depend on `CustomTkinter` (and thus `Tkinter`).
    *   Development will focus on specific GUI tools (like region selection) initially.
    *   Care needed for smooth GUI-backend integration.
    *   If `CustomTkinter` poses issues for low-level screen interaction (e.g., transparent overlays), `Tkinter`'s direct capabilities or platform-specific APIs for that component might be explored.

---