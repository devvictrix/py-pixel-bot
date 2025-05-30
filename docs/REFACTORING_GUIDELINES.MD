# Refactoring Guidelines for Mark-I

## 1. Introduction

**Purpose:**
These guidelines are intended to assist developers in refactoring and enhancing the Mark-I codebase with a strong focus on **Modularity, Maintainability, and Readability**. Adherence to these principles is crucial as the project evolves, especially with the integration of complex AI features (v4.0.0, v5.0.0) and future enhancements (`vFuture`).

**Benefits:**
Focusing on these quality attributes leads to:
*   **Easier Understanding:** Code becomes simpler to comprehend for current and future developers.
*   **Reduced Complexity:** Well-structured code is less prone to bugs and easier to debug.
*   **Improved Scalability:** Modular design allows for easier addition of new features and modification of existing ones.
*   **Enhanced Collaboration:** Consistent, readable code facilitates teamwork.
*   **Lower Maintenance Costs:** Code that is easy to understand and modify reduces the effort required for updates and bug fixes.

These guidelines should be applied during ongoing development, before introducing significant new features, and when addressing technical debt.

## 2. Modularity

Modularity refers to designing the system as a set of distinct, independent, and interchangeable components (modules/classes).

### 2.1. Single Responsibility Principle (SRP)
*   **Guideline:** Each class, function, and module should have one, and only one, reason to change. It should be responsible for a single part of the application's functionality.
*   **Application in Mark-I:**
    *   `CaptureEngine` is responsible for screen capture.
    *   `AnalysisEngine` handles local image analysis.
    *   `GeminiAnalyzer` is solely for Gemini API communication.
    *   UI components (`MainAppWindow`, `ProfileCreationWizardWindow`) manage user interaction, separate from backend logic.
*   **Action:** If a class or module handles too many unrelated tasks, consider splitting it.

### 2.2. File and Class Size
*   **Guideline:** Avoid overly large files and classes. Large components are often a symptom of SRP violations and are harder to understand, test, and maintain.
*   **File Size Heuristic:** Aim for Python files (`.py`) to ideally be under **500-700 lines of code (LoC)**, excluding comments and blank lines. This is a soft guideline; if a file exceeds this, it should trigger a review to see if it can be logically decomposed.
*   **Class Size Heuristic:** Classes should also be focused. If a class has too many methods (e.g., >15-20, context-dependent) or an excessive number of instance variables, consider if it can be broken down or if some responsibilities can be delegated to helper classes.
*   **Function/Method Length:** Keep functions and methods concise, ideally fitting on one screen (e.g., <50-70 LoC). Break down longer functions into smaller, well-named private helper methods.

### 2.3. Clear Separation of Concerns
*   **Guideline:** Different aspects of the application should be handled by separate modules.
*   **Application in Mark-I:**
    *   The existing structure (e.g., `core`, `engines`, `ui`, `generation` packages) promotes this. Maintain this separation.
    *   **UI vs. Backend:** Keep UI logic (`CustomTkinter` interactions in `ui.gui`) separate from core business logic (`engines`, `generation`). UI should call into backend services/controllers but not contain deep processing logic.
    *   **Data vs. Logic:** Configuration data (JSON profiles, `.env`) is separate from the code that processes it (`ConfigManager`).
*   **Action:** When adding new features, identify the correct module or consider creating a new one if the functionality is distinct.

### 2.4. Interface Design (for future growth)
*   **Guideline:** For components with potential for multiple implementations or those forming critical boundaries, consider defining Abstract Base Classes (ABCs) or Protocols (Python 3.8+).
*   **Example:** If `CaptureEngine` were to support `mss` or other capture backends alongside `Pillow` (as considered in ADR-001), an abstract `BaseCaptureEngine` could define the common interface (`capture_region` method).
*   **Action:** While not a primary focus for immediate refactoring of v5.0.0, keep this in mind for `vFuture` features that introduce alternative strategies for core functionalities.

### 2.5. Dependency Management
*   **Guideline:**
    *   Minimize direct coupling between modules. Aim for loose coupling.
    *   Avoid circular dependencies (Module A imports B, and B imports A). These make the codebase harder to understand and maintain.
    *   Dependencies should flow in one direction where possible (e.g., UI depends on engines, engines don't depend on UI).
*   **Action:** Use dependency injection (passing dependencies as constructor arguments, as seen with `MainController` and engine initializations) rather than global instances where practical. Review import statements to identify and resolve circular dependencies.

## 3. Maintainability

Maintainable code is easy to modify, fix, and extend.

### 3.1. Coding Style & Formatting
*   **Guideline:** Adhere strictly to **PEP 8**.
*   **Tools:** Utilize **Black** for automated code formatting and **Flake8** for linting, as configured in the project (`pyproject.toml`, `.flake8`). This ensures consistency. (See `DEV_CONFIG.MD`)
*   **Action:** Run formatters and linters regularly. Address all linting warnings.

### 3.2. Configuration Over Hardcoding
*   **Guideline:** Avoid hardcoding values that might change or are environment-specific.
*   **Application in Mark-I:**
    *   Bot profiles (JSON) store user-defined automation logic (ADR-003).
    *   `.env` files manage API keys and environment settings (ADR-007).
    *   UI parameter configurations (`gui_config.py`) drive dynamic UI generation.
*   **Action:** Continue this practice. New configurable parameters should be added to profile settings or `.env` as appropriate.

### 3.3. Comprehensive Logging
*   **Guideline:** Implement detailed and contextual logging for all significant operations, decisions, state changes, errors, and AI interactions. (See ADR-007).
*   **Action:**
    *   Use `logging.getLogger(__name__)` for module-specific loggers.
    *   Log at appropriate levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
    *   Provide sufficient context in log messages.
    *   **Crucially for AI components:** Log prompts (summarized if sensitive/long), model used, response status/summary, latency, and any errors from `GeminiAnalyzer`, `GeminiDecisionModule`, `StrategyPlanner`, `ProfileGenerator`.

### 3.4. Robust Error Handling
*   **Guideline:** Anticipate and handle potential errors gracefully.
*   **Action:**
    *   Use `try-except` blocks for operations that can fail (file I/O, API calls, image processing).
    *   Catch specific exceptions rather than generic `Exception`.
    *   Provide clear error messages to the user (via GUI or CLI) and detailed logs for developers.
    *   Ensure the application can recover or terminate cleanly. (See error handling considerations in ADR-010 for GUI concurrency).

### 3.5. Testing
*   **Guideline:** Implement a comprehensive testing strategy.
*   **Action:**
    *   **Unit Tests (`pytest`):** Implement unit tests using `pytest` for core logic, utilities, and isolated components. (This is an **active initiative** as of v5.0.2 - see `FEATURE_ROADMAP.MD`).
        *   Mock external dependencies (APIs, UI libraries, file system I/O) to ensure tests are isolated and deterministic.
        *   Focus on testing business logic, calculations, and state changes within individual units.
    *   **Integration Tests:** Test interactions between modules (e.g., `RulesEngine` with `AnalysisEngine` and `ActionExecutor`). Mock external dependencies like `GeminiAnalyzer` for these tests. (Future goal).
    *   **End-to-End (E2E) Testing:** Manually test complete user workflows (CLI `run`, GUI profile editing, AI Profile Generation) as outlined in `FEATURE_ROADMAP.MD` (e.g., v5.0.3 Manual E2E Testing).
    *   Aim for good test coverage of critical components, especially after refactoring and for new features.

### 3.6. Code-Level Documentation
*   **Guideline:** Document code to explain its purpose, usage, and complex parts.
*   **Docstrings:**
    *   Write comprehensive docstrings for all modules, classes, public methods, and functions.
    *   Follow **Google Python Style** docstrings, as specified in `DEV_CONFIG.MD`.
    *   Include parameter descriptions, return types, and any exceptions raised.
*   **Inline Comments:**
    *   Use comments to explain non-obvious logic, workarounds, or important assumptions.
    *   Avoid commenting on what is already clear from the code. Focus on the "why".

### 3.7. Version Control
*   **Guideline:** Follow Git best practices.
*   **Action:** Adhere to the branching strategy and conventional commit message style outlined in `DEV_CONFIG.MD`. Make small, atomic commits.

### 3.8. The "Boy Scout Rule"
*   **Guideline:** "Always leave the code cleaner than you found it."
*   **Action:** When working on a piece of code, take small opportunities to improve its structure, readability, or documentation, even if it's not directly related to the current task.

## 4. Readability

Readable code is easy to follow and understand.

### 4.1. Naming Conventions
*   **Guideline:** Use clear, descriptive, and consistent names for variables, functions, classes, and modules.
*   **Action:**
    *   Follow PEP 8 naming conventions (e.g., `snake_case` for functions and variables, `CapWords` for classes).
    *   Avoid overly short or cryptic names (e.g., `x`, `df`, `process_data`). Be specific.
    *   Boolean variables/functions should suggest true/false (e.g., `is_valid`, `has_errors`).

### 4.2. Control Flow Simplicity
*   **Guideline:** Keep control flow (loops, conditionals) as simple as possible.
*   **Action:**
    *   Avoid deeply nested `if/else` statements or loops. Consider refactoring with helper functions, guard clauses, or polymorphism (e.g., Strategy pattern).
    *   Break down complex functions into smaller, single-purpose helper functions.

### 4.3. Type Hinting
*   **Guideline:** Utilize Python type hints extensively. (Project already uses this).
*   **Action:** Add type hints to all function signatures (parameters and return types) and important variables. This improves code clarity, helps static analysis tools (like MyPy, if adopted later), and acts as a form of documentation.

### 4.4. Constants for Magic Values
*   **Guideline:** Replace unnamed "magic" numbers or strings with named constants.
*   **Application in Mark-I:** Constants for UI element IDs, default settings, or fixed strings are already used in places like `gui_config.py` (`OPTIONS_CONST_MAP`, default structures) and `gemini_decision_module.py` (`PREDEFINED_ALLOWED_SUB_ACTIONS`).
*   **Action:** Continue this practice. Define constants at the module level or in a dedicated `constants.py` file if they are widely shared.

### 4.5. Function/Method Length
*   **Guideline:** As with file/class size, keep functions and methods focused and reasonably short.
*   **Action:** If a function or method does too many things or is too long (e.g., > 50-70 LoC), it's a good candidate for refactoring into smaller, more manageable units.

### 4.6. Effective Code Comments
*   **Guideline:** Write comments that add value and explain non-obvious parts of the code.
*   **Action:**
    *   Explain the "why" behind a piece of logic, not just the "what" (if the "what" is self-evident from well-written code).
    *   Document complex algorithms, workarounds for issues, or assumptions made.
    *   Keep comments up-to-date with code changes. Stale comments are misleading.
    *   Use `TODO:`, `FIXME:`, `NOTE:` prefixes for specific types of comments.

## 5. Leveraging Design Patterns

Design patterns are reusable solutions to commonly occurring problems within a given context in software design. They are not direct code but templates for how to solve problems.

### 5.1. When to Use Patterns
*   Use patterns to solve specific, recurring design problems, not for their own sake.
*   Understand the trade-offs of each pattern. Some can add complexity if overused or misapplied.
*   The existing codebase already implicitly or explicitly uses some patterns.

### 5.2. Recommended/Observed Patterns in Mark-I:

*   **Facade Pattern:**
    *   **Description:** Provides a simplified interface to a larger body of code, such as a complex subsystem.
    *   **Examples in Mark-I:**
        *   `GeminiAnalyzer` acts as a facade to the `google-generativeai` SDK.
        *   `ConfigManager` is a facade for JSON profile file I/O and path management.
    *   **Benefit:** Decouples clients from the internal complexity of the subsystem.

*   **Strategy Pattern:**
    *   **Description:** Defines a family of algorithms, encapsulates each one, and makes them interchangeable. Lets the algorithm vary independently from clients that use it.
    *   **Potential Application:**
        *   If `AnalysisEngine` needed to support significantly different template matching algorithms with the same interface.
        *   If `ActionExecutor` needed different execution strategies for a `click` based on OS or application context.
    *   **Benefit:** Increases flexibility and allows new strategies to be added easily.

*   **Command Pattern:**
    *   **Description:** Encapsulates a request as an object, thereby letting you parameterize clients with different requests, queue or log requests, and support undoable operations.
    *   **Examples in Mark-I (Conceptual Alignment):**
        *   `ActionExecutor` takes action specifications (similar to command objects) and executes them.
        *   The NLU-driven task execution in `GeminiDecisionModule` (ADR-008) where a natural language command is decomposed into a sequence of executable steps (commands).
    *   **Benefit:** Decouples the invoker of an operation from the object that knows how to perform it.

*   **Observer Pattern:**
    *   **Description:** Defines a one-to-many dependency between objects so that when one object changes state, all its dependents are notified and updated automatically.
    *   **Potential Application:**
        *   If the deferred "Real-time Visual Feedback in GUI" (v3.0.0 feature) is implemented, the GUI could observe `MainController` or analysis engines for state changes to display live feedback.
    *   **Benefit:** Promotes loose coupling between subject and observers.

*   **Factory Pattern (Simple Factory or Factory Method):**
    *   **Description:** Provides an interface for creating objects in a superclass, but lets subclasses alter the type of objects that will be created.
    *   **Potential Application:**
        *   If UI widgets needed to be created with significantly different configurations or types based on dynamic conditions (though `CustomTkinter` and `UI_PARAM_CONFIG` handle much of this declaratively).
        *   If `mark_i` needed to support different types of `Analyzer` instances based on configuration.
    *   **Benefit:** Decouples client code from concrete class instantiation.

*   **State Pattern:**
    *   **Description:** Allows an object to alter its behavior when its internal state changes. The object will appear to change its class.
    *   **Potential Application:**
        *   The `ProfileCreationWizardWindow` (ADR-009, ADR-010) navigates through different pages/states (`PAGE_GOAL_INPUT`, `PAGE_PLAN_REVIEW`, etc.). If the transitions and per-state logic become highly complex, this pattern could formalize state management.
    *   **Benefit:** Organizes state-specific behavior and makes state transitions explicit.

### 5.3. Guidance on Choosing and Implementing Patterns
*   **Identify the Problem:** First, clearly understand the design problem you're trying to solve.
*   **Understand the Pattern:** Study the chosen pattern's intent, applicability, structure, and consequences.
*   **Keep it Simple (KISS):** Don't force a pattern if a simpler solution suffices. Start with the simplest approach and refactor to a pattern if complexity warrants it.
*   **Adapt, Don't Adopt Blindly:** Patterns are templates. Adapt them to the specific context of Mark-I and Python.

## 6. Refactoring Process

### 6.1. When to Refactor
*   **Before Adding New Features:** Ensure the existing codebase related to the new feature is clean and well-structured.
*   **When Code Smells Appear:** Address issues like duplicated code, long methods/classes, complex conditionals, or tight coupling.
*   **After Bug Fixes:** If a bug was hard to find or fix due to poor code structure, refactor that area.
*   **Iteratively:** Refactoring is an ongoing process, not a one-time event.

### 6.2. Approach
*   **Small, Incremental Changes:** Avoid large, sweeping refactors that can destabilize the codebase. Make small, testable changes.
*   **Test-Driven Refactoring:** Write unit tests for the area being refactored *before* refactoring. Ensure these tests (and any existing relevant tests) pass after each small refactoring step. This provides a safety net. (Unit testing is being introduced in v5.0.2).
*   **Focus on Pain Points:** Prioritize refactoring areas that are difficult to work with or are frequent sources of bugs.
*   **Use Existing Documentation:** Refer to ADRs and `TECHNICAL_DESIGN.MD` to ensure refactoring aligns with established architectural decisions.

## 7. Conclusion

Refactoring for Modularity, Maintainability, and Readability is a continuous investment that pays off in the long run. By applying these guidelines, and by incorporating a robust unit testing strategy, the Mark-I team can ensure the project remains robust, adaptable, and a pleasure to work on as it grows in capability and complexity.