# ADR-006: Concurrency Model for Real-time Monitoring Loop

*   **Status:** Approved (Implemented; v4.0.0 AI API calls are I/O-bound within this model)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool's (Mark-I) core bot runtime involves a continuous loop: Capture -> Analyze -> Evaluate Rules -> Act. This loop, managed by `MainController`, runs repeatedly at a user-configurable rate (FPS/interval). If this loop were to run in the main application thread, it would block any other interactions.
Specifically:
1.  For the CLI `run` command, the main thread needs to remain responsive to signals like `Ctrl+C` for graceful shutdown.
2.  If, in the future, a GUI provides a "Start/Stop Bot" button for a loaded profile (distinct from the GUI *editor*), the GUI event loop must not freeze while the bot is running.

Therefore, a concurrency model is needed to allow the bot's monitoring loop to execute in the background without making the primary application thread (handling CLI or GUI events) unresponsive.

## Considered Options

1.  **Python `threading` Module:**
    *   Pros: Standard library. Relatively simple for I/O-bound tasks or tasks releasing the Python Global Interpreter Lock (GIL). Many C-extension libraries (OpenCV, Pillow, PyAutoGUI) and network operations (like calls to Gemini API) release the GIL during blocking, making threads effective. Good for managing background tasks.
    *   Cons: GIL prevents true CPU-bound parallelism for Python bytecode. Requires careful management of shared resources (minimized by current design).

2.  **Python `asyncio` Module:**
    *   Pros: Standard library. Excellent for I/O-bound operations with `async/await`.
    *   Cons: Steeper learning curve. Core libraries (OpenCV, Pillow capture, PyAutoGUI, Gemini SDK's synchronous methods) are blocking and not natively `asyncio`-compatible, requiring thread pool executors, which negates some benefits.

3.  **Python `multiprocessing` Module:**
    *   Pros: True parallelism by bypassing GIL. Good for CPU-bound tasks.
    *   Cons: Higher overhead for process creation and IPC. Overkill for the main bot loop, which is largely I/O-bound or uses GIL-releasing libraries.

## Decision Outcome

**Chosen Option:** Python `threading` Module

**Justification:**
*   **Simplicity and Directness:** For managing a single, continuous background monitoring loop with basic start/stop, `threading` is simplest.
*   **Suitability for I/O-Bound Nature:** The bot's loop involves significant operations effectively I/O-bound (screen capture, `time.sleep`, pyautogui actions, **and network requests to the Gemini API for v4.0.0 features**). C libraries used (OpenCV, Pillow) also release the GIL. `threading` performs well, allowing the main thread to remain responsive.
*   **Standard Library:** No external dependencies for this core concurrency.
*   **Effective Stop Mechanism:** `threading.Event` provides a clean stop signal.
*   **Sufficient for Current and Foreseeable Needs:** The added complexity of `asyncio` (due to non-async libraries) or `multiprocessing` is not justified.

If specific, highly CPU-intensive Python-coded analysis steps (not C library calls or external API calls) become a bottleneck *within* a single loop iteration in the future, `multiprocessing` could be considered for offloading just those specific computations. However, for the overall loop management, `threading` is the most appropriate choice.

## Consequences

*   The `MainController.run_monitoring_loop()` method is executed in a separate daemon thread.
*   The main application thread is responsible for creating/starting this thread and handling primary inputs (CLI/GUI).
*   A `threading.Event` (`self._stop_event` in `MainController`) signals the loop to stop.
*   Care taken to minimize direct data sharing between threads during loop execution.
*   Developers need basic Python threading understanding.

---