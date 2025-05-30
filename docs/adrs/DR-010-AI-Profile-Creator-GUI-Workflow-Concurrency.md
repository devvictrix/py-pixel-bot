// File: docs/adrs/DR-010-AI-Profile-Creator-GUI-Workflow-Concurrency.md

# ADR-010: Concurrency Model for AI Profile Creator GUI Wizard

- **Status:** Accepted
- **Date Decision Made:** 2025-05-29
- **Deciders:** DevLead

## Context and Problem Statement

The Mark-I v5.0.0 "AI Profile Creator" feature, managed by the `ProfileCreationWizardWindow` GUI, involves several potentially long-running operations. These operations primarily consist of API calls to Google Gemini made via the `StrategyPlanner` (for initial goal-to-plan generation) and `ProfileGenerator` (for suggesting regions, condition/action logic, and refining element locations for each step of the plan).

These Gemini API calls are synchronous by nature of the current `google-generativeai` SDK's standard `generate_content` method. If these calls are made directly in the main GUI thread (CustomTkinter's Tkinter event loop), the `ProfileCreationWizardWindow` will freeze and become unresponsive to user input during the AI processing times (which can be several seconds per call). This leads to a poor user experience, where the application might appear to have crashed or hung.

A concurrency model is needed for the `ProfileCreationWizardWindow` to perform these long-running AI tasks in the background, allowing the GUI to remain responsive and provide feedback (e.g., loading indicators) to the user, and then update the GUI with results once the AI tasks are complete.

## Considered Options

1.  **Python `threading` Module with Callbacks or Queue-like Mechanism for GUI Updates (Chosen):**

    - **Description:** Each significant AI call (e.g., `StrategyPlanner.generate_intermediate_plan()`, `ProfileGenerator.suggest_region_for_step()`, etc., when invoked by a GUI action) would be executed in a separate worker thread (`threading.Thread`).
      - The GUI event handler (e.g., button click method) would initiate the task by creating and starting the worker thread.
      - Immediately after starting the thread, the GUI would update to show a "loading" or "AI is thinking..." message and disable relevant controls to prevent concurrent conflicting actions.
      - The worker thread performs the blocking AI call.
      - Upon completion (success or failure), the worker thread needs to communicate the result back to the main GUI thread. This can be achieved via:
        - **Tkinter's `widget.after(delay_ms, callback, *args)`:** The worker thread schedules a callback function to be executed by the Tkinter main loop. This is thread-safe.
        - **`queue.Queue`:** The worker thread puts the result (or an error indicator) onto a thread-safe queue. The GUI thread periodically checks this queue using `widget.after()` for new messages.
        - **Tkinter custom events (`widget.event_generate("<<MyCustomEvent>>", data=...)`):** Worker thread generates a custom event with data. GUI thread binds a handler to this event.
    - **Pros:**
      - **Keeps GUI Responsive:** This is the primary requirement and is effectively achieved.
      - **Standard Library:** `threading` and `queue` are part of Python's standard library.
      - **Good Fit for Tkinter/CustomTkinter:** Tkinter provides built-in mechanisms (`after`, `event_generate`) for safe cross-thread communication to its main event loop.
      - **Relatively Straightforward for Discrete Tasks:** For the wizard's step-by-step nature, where each AI call is a discrete background task, this model is understandable and manageable.
    - **Cons:**
      - Manual management of threads, result passing, and GUI updates from callbacks/queue handlers.
      - Requires careful error handling in worker threads and ensuring errors are correctly propagated and displayed in the GUI thread.
      - Callback hell can become an issue if interactions are very deeply nested, but for the wizard's flow, it should be manageable.

2.  **Python `asyncio` with Thread Pool Executor:**

    - **Description:** Attempt to use `async/await` in the wizard's methods. The blocking Gemini SDK calls would be wrapped using `loop.run_in_executor(None, blocking_function, args)` to run them in `asyncio`'s default thread pool.
    - **Pros:** Modern `async/await` syntax for concurrency.
    - **Cons:**
      - **Tkinter/CustomTkinter Mainloop Integration:** Tkinter's main event loop is not an `asyncio` event loop. Making them work together smoothly to allow `async` GUI methods to update widgets typically requires third-party libraries (e.g., `asyncio-tkinter`, `tkasync`) or complex manual bridging. This often re-introduces the complexity of managing callbacks or queue-like mechanisms to bridge the two event loops.
      - **Underlying Blocking Calls:** Since the Gemini SDK calls are synchronous, `asyncio` would still be using threads via its executor, diminishing some of the "pure asyncio" benefits for this specific case. The primary benefit of `asyncio` (efficiently managing many non-blocking I/O operations on a single thread) is less applicable here.

3.  **No Concurrency (Synchronous Calls - UI Freezes):**
    - **Description:** Make all AI API calls directly within the GUI event handlers (e.g., button click methods).
    - **Pros:** Simplest to code initially.
    - **Cons:** **Unacceptable User Experience.** The GUI will freeze for the duration of each Gemini API call (potentially 2-10+ seconds or more depending on the task and model). This makes the application appear unresponsive or crashed and is not suitable for an interactive wizard.

## Decision Outcome

**Chosen Option:** **Option 1: Python `threading` Module with Callbacks (primarily using `widget.after()`) for GUI Updates.**

**Justification:**

- **GUI Responsiveness (Primary Requirement):** This approach directly addresses the need to keep the `ProfileCreationWizardWindow` responsive during AI processing.
- **Compatibility and Simplicity with Tkinter/CustomTkinter:** Tkinter's `widget.after(delay, func, *args)` provides a robust and straightforward way to schedule a function to be run in the main GUI thread from a worker thread. This avoids the complexities of trying to integrate `asyncio`'s event loop with Tkinter's.
- **Standard Library Solution:** Relies on built-in Python modules (`threading`).
- **Suitability for Wizard Workflow:** The wizard's flow consists of discrete user actions that trigger potentially long AI operations. Starting a new thread for each such operation and using `after()` for the result callback is a well-understood and effective pattern for such scenarios in Tkinter applications.
- **Error Handling:** Exceptions in the worker thread can be caught, and an error status/message can be passed back to the GUI thread via the callback for user notification (e.g., displaying a `messagebox.showerror`).

**High-Level Implementation Pattern in `ProfileCreationWizardWindow`:**

1.  **User action (e.g., clicks "Generate Plan" or "AI Suggest Region"):**
    - The GUI event handler method (e.g., `self._handle_generate_plan_click`):
      - Disables relevant UI controls (e.g., the button itself, "Next" button).
      - Displays a visual loading indicator (e.g., "AI is thinking...").
      - Creates a target function (e.g., `_perform_plan_generation_in_thread`) that will call the blocking AI method (e.g., `self.strategy_planner.generate_intermediate_plan(...)`).
      - Starts a new `threading.Thread(target=self._perform_plan_generation_in_thread, args=(...))`.
2.  **Worker Thread (`_perform_plan_generation_in_thread`):**
    - Calls the blocking AI method (e.g., `plan = self.strategy_planner.generate_intermediate_plan(...)`).
    - Catches any exceptions during the AI call.
    - Schedules a result handler to run in the GUI thread using `self.after(0, self._handle_plan_generation_result, plan, potential_error)`.
3.  **Result Handler in GUI Thread (`_handle_plan_generation_result(self, plan, error)`):**
    - This method runs in the main Tkinter thread.
    - Removes the loading indicator.
    - Re-enables UI controls.
    - If an error occurred, displays an error message to the user.
    - If successful, processes the `plan` (e.g., updates wizard state, populates UI elements with the plan).
    - Updates navigation button states.

This pattern will be applied to all interactions within the wizard that trigger AI calls (`generate_intermediate_plan`, `suggest_region_for_step`, `suggest_logic_for_step`, `refine_element_location`).

## Consequences

- **Increased Complexity in GUI Code:** `ProfileCreationWizardWindow` will need to manage threads and callbacks for AI operations, making its event handling logic more complex than purely synchronous code.
- **Thread Safety for GUI Updates:** All direct manipulations of CustomTkinter/Tkinter widgets MUST occur in the main GUI thread. `self.after()` is the primary mechanism to ensure this.
- **Error Propagation:** A clear system for catching errors in worker threads and passing them to the GUI thread for display to the user must be implemented.
- **Improved User Experience:** The wizard will remain responsive, providing feedback during AI processing, which is a significant improvement over a freezing UI.
- **Testability:** Testing methods that spawn threads can be more complex. Mocking the AI call within the worker thread's target function and verifying the callback mechanism will be important.

This decision ensures a responsive user experience for the AI Profile Creator wizard, which is critical given the potential latency of the involved AI API calls.