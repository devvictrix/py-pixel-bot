# ADR-006: Concurrency Model for Real-time Monitoring Loop

*   **Status:** Approved (and implemented)
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
    *   Pros: Standard library, no external dependencies for this. Relatively simple to understand and use for I/O-bound tasks or tasks that release the Python Global Interpreter Lock (GIL). Many C-extension libraries used in image processing (OpenCV, Pillow) and system interaction (PyAutoGUI) release the GIL during their blocking operations, making threads effective for such workloads. Good for managing background tasks that need to be started, stopped, or monitored from a main thread. Communication between threads can be managed using `queue.Queue`, `threading.Event`, `threading.Lock`, etc.
    *   Cons: The GIL prevents true CPU-bound parallelism for Python bytecode execution across multiple threads on multi-core processors. However, our loop is heavily I/O-bound (screen capture, sleeps, GUI interactions from PyAutoGUI) or uses C libraries that release GIL. Requires careful management of shared resources if any (though current design minimizes direct sharing during the loop's execution by passing data).

2.  **Python `asyncio` Module:**
    *   Pros: Standard library. Excellent for I/O-bound operations and provides a structured way to write concurrent code using `async/await`. Can be very efficient by using a single thread and an event loop to manage many concurrent tasks.
    *   Cons: Steeper learning curve. Requires that I/O operations be "async-aware" or wrapped to work with the event loop. Libraries like OpenCV, Pillow (ImageGrab), and PyAutoGUI perform blocking I/O and are not natively `asyncio`-compatible. Using them with `asyncio` would typically involve running them in a thread pool executor (`loop.run_in_executor`), which can negate some of the simplicity benefits of `asyncio` for this specific use case and essentially reintroduces threads. Might be overkill for managing a single, primary background loop.

3.  **Python `multiprocessing` Module:**
    *   Pros: Standard library. Achieves true parallelism by using separate processes, thus bypassing the GIL. Excellent for CPU-bound tasks where calculations need to be distributed across multiple cores. Provides separate memory spaces, which can simplify some aspects of state management but complicates data sharing.
    *   Cons: Higher overhead for process creation and Inter-Process Communication (IPC) compared to threads. Sharing data between processes is more complex (requires mechanisms like `multiprocessing.Queue`, `Pipe`, shared memory). Overkill for our main bot loop, which is more I/O-bound and where the primary concern is responsiveness of the main thread, not CPU-bound parallel computation within the loop itself.

## Decision Outcome

**Chosen Option:** Python `threading` Module

**Justification:**
*   **Simplicity and Directness for the Task:** For managing a single, continuous background monitoring loop that needs basic start/stop control from the main application thread, `threading` is the simplest and most direct standard library solution.
*   **Suitability for I/O-Bound Nature:** The bot's loop involves significant operations that are effectively I/O-bound (waiting for screen capture, `time.sleep` for interval, pyautogui actions which interact with the OS GUI system) or are performed by C libraries that release the GIL (OpenCV/Pillow image processing). `threading` performs well in these scenarios, allowing the main thread to remain responsive.
*   **Standard Library:** No external dependencies are introduced for this core concurrency mechanism.
*   **Effective Stop Mechanism:** `threading.Event` provides a clean and straightforward way for the main thread to signal the background monitoring loop to terminate gracefully.
*   **Sufficient for Current and Foreseeable Needs:** The added complexity of `asyncio` (due to non-async libraries) or `multiprocessing` (overhead and IPC complexity) is not justified for the primary task of running the monitoring loop in the background.

If specific, highly CPU-intensive Python-coded analysis steps (not C library calls) become a bottleneck *within* a single loop iteration in the future, `multiprocessing` could be considered for offloading just those specific computations. However, for the overall loop management, `threading` is the most appropriate choice.

## Consequences

*   The `MainController.run_monitoring_loop()` method is executed in a separate daemon thread created when `MainController.start()` is called.
*   The main application thread (e.g., in `cli.handle_run` or a future GUI's "start bot" action) is responsible for creating and starting this thread, and then typically waits for it or remains responsive to other inputs (like `Ctrl+C` or GUI events).
*   A `threading.Event` (`self._stop_event` in `MainController`) is used to signal the monitoring loop to stop. The loop checks this event in each iteration.
*   Care must be taken if any data needs to be shared between the monitoring thread and the main thread while the loop is active. The current design largely avoids this by having the loop operate on data prepared at the start of each cycle or configuration loaded at initialization.
*   Developers working on `MainController` or related components need a basic understanding of Python threading concepts (thread creation, daemon threads, events, joining).

---