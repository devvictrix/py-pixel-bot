// File: docs/adrs/ADR-006-Concurrency-Model-for-Real-time-Monitoring-Loop.md
# ADR-006: Concurrency Model for Real-time Monitoring Loop

*   **Status:** Approved
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool's core involves a continuous loop: Capture -> Analyze -> Evaluate Rules -> Act. This loop runs repeatedly (configurable rate/FPS). If it runs in the main thread, it blocks the UI (CLI/GUI), making the app unresponsive. We need a concurrency model allowing the loop to run in the background without freezing the main thread, enabling user interaction (e.g., to stop it via CLI Ctrl+C or a GUI button).

## Considered Options

1.  **Python `threading` Module:**
    *   Pros: Standard library. Simple for I/O-bound tasks or tasks releasing GIL (many C-level ops in capture/action libraries do). Good for background tasks. Easy communication (Queues, Events).
    *   Cons: GIL prevents true parallelism for CPU-bound Python code (though less critical here). Requires careful shared resource management.

2.  **Python `asyncio` Module:**
    *   Pros: Standard library. Excellent for I/O-bound, structured concurrency. Single thread avoids some multi-threading complexities.
    *   Cons: Steeper learning curve (async/await). Blocking I/O needs async equivalents or thread pool executor (OpenCV, PyAutoGUI are not natively async), potentially negating benefits. Overkill for a single background loop with simple start/stop.

3.  **Python `multiprocessing` Module:**
    *   Pros: Standard library. True parallelism (bypasses GIL). Good for CPU-bound tasks. Separate memory spaces.
    *   Cons: Higher overhead (process creation, IPC). Sharing data more involved. Overkill for this tool's I/O-heavy loop.

## Decision Outcome

**Chosen Option:** Python `threading` Module

**Justification:**
*   **Simplicity for the Task:** For managing a single, continuous background monitoring loop with basic start/stop control from the main thread, `threading` is the simplest and most direct.
*   **Suitability for I/O-Bound Nature:** The loop involves significant I/O-like operations (screen capture, image analysis via C-libs, action execution via PyAutoGUI) where `threading` performs well.
*   **Standard Library:** No external dependencies for core concurrency.
*   **Effective Stop Mechanism:** `threading.Event` can gracefully terminate the loop thread.
*   **Sufficient for Needs:** `asyncio`'s complexity for making components async-compatible outweighs benefits here. `multiprocessing` is unnecessary overhead for the main bot execution loop.

If CPU-bound Python code in the analysis loop becomes a significant bottleneck later, `multiprocessing` for specific, isolated tasks could be a targeted optimization, but `threading` is best for the main monitoring loop.

## Consequences

*   The main monitoring loop (in `MainController`) runs in a separate daemon thread.
*   The main thread handles user input (CLI, and will handle GUI event loop) and controls the monitoring thread's lifecycle (start, stop via `threading.Event`).
*   Care needed if data is shared between threads (use thread-safe mechanisms). Currently, communication is primarily one-way signals (start/stop) and data is passed into the loop per cycle.
*   Developers need basic Python threading understanding.

---