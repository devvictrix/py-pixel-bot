# ADR-002: Input Simulation Library Choice

*   **Status:** Approved
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The visual automation tool (Mark-I) requires the ability to programmatically simulate mouse movements, clicks (left, right, middle), and keyboard presses (character keys, special keys) as part of its "React" phase. This functionality needs to be reliable and cross-platform (Windows, macOS, Linux) to align with the project's core requirements.

## Considered Options

1.  **`pyautogui`:**
    *   Pros:
        *   Widely used and well-known for cross-platform GUI automation.
        *   Provides comprehensive mouse and keyboard control functions.
        *   Includes additional utility functions like screen size detection.
        *   Relatively easy to install and use.
    *   Cons:
        *   Can sometimes have issues with certain games or applications that use low-level input hooks.
        *   Has dependencies like Pillow, which is acceptable as Pillow is already chosen for capture/image manipulation (see ADR-001).

2.  **`pynput` (for control):**
    *   Pros:
        *   Excellent for low-level control of mouse and keyboard.
        *   Cross-platform.
    *   Cons:
        *   Its API is more low-level compared to `pyautogui`, potentially requiring more code for common automation tasks.

3.  **Platform-specific libraries (e.g., `ctypes` for Windows SendInput, `Xlib` for Linux, `Quartz` for macOS via `pyobjc`):**
    *   Pros:
        *   Potentially the most direct and performant control for each specific OS.
    *   Cons:
        *   Massively increases development complexity and maintenance overhead.
        *   Requires separate codebases for input simulation for each target OS.

## Decision Outcome

**Chosen Option:** `pyautogui`

**Justification:**
*   **Balance of Features and Ease of Use:** `pyautogui` offers a good balance, providing robust cross-platform mouse and keyboard simulation capabilities with a user-friendly API.
*   **Cross-Platform Support:** This is a critical requirement, and `pyautogui` is designed for this.
*   **Sufficient for Project Needs:** For simulating clicks and key presses based on visual analysis, `pyautogui`'s capabilities are well-suited.
*   **Community and Maintenance:** It's a mature and actively maintained library.
*   **Dependency Alignment:** Its dependency on Pillow aligns with other technology choices.

## Consequences

*   The project will have a dependency on `pyautogui`.
*   Developers will need to be familiar with the `pyautogui` API for action execution (`ActionExecutor` module).
*   Potential limitations in highly specialized environments (e.g., some full-screen games with anti-cheat or low-level input blocking) might need to be addressed on a case-by-case basis if they arise, potentially by exploring `pynput` as a fallback for specific scenarios if `pyautogui` fails.
*   Ensure `pyautogui`'s dependencies (like Pillow, Xlib on Linux, etc.) are handled correctly during installation (covered by `requirements.txt`).

---