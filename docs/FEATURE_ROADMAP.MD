# Feature Roadmap & Status

This document tracks planned features and their status for this visual automation tool. The primary goal is to achieve the "AI-Accelerated v1.0.0" as the first major deliverable, followed by further enhancements.

**Key Supporting Documents:**
*   `PROJECT_OVERVIEW.MD`
*   `TECHNICAL_DESIGN.MD`
*   `STATUS_LEGEND.MD` 
*   `DEV_CONFIG.MD`
*   `adrs/` 

---

## AI-Accelerated v1.0.0: Target Feature Set

| AI-Accelerated v1.0.0 Component        | Corresponding Granular Features (Illustrative)                                       | Status             | Priority |
| :------------------------------------- | :----------------------------------------------------------------------------------- | :----------------- | :------- |
| **Core Engine & Configuration**        | v0.0.1 (Project Setup, Docs, Logging), v0.0.3 (Config PoC), v0.1.0 (CLI Ctrl, Profile Mgmt, `__main__`) | Done               | Critical |
| **Region Definition & Capture**        | v0.0.1 (Define Region via file, Capture Impl), v0.1.0 (Multi-Region from file)       | Done               | Critical |
| **Basic Visual Analysis**              | v0.0.2 (Pixel Color Impl), v0.1.0 (Avg Color Impl)                                   | Done               | Critical |
| **Template Matching Analysis**         | v0.2.0 (Basic Template Matching Impl, incl. template loading by RulesEngine)          | Done               | Critical |
| **OCR Text Analysis**                  | v0.3.0 (OCR Text Extraction Impl)                                                    | Done               | Critical |
| **Rules Engine & Conditional Actions** | v0.0.3 (Basic Action), v0.1.0 (Click), v0.2.0 (Rules Impl), v0.3.0 (Text Cond Impl)   | Done               | Critical |
| **Continuous Monitoring Loop**         | v0.1.0 (Core Loop Impl in MainController), v0.2.0 (Configurable FPS)                 | Done               | Critical |
| **Initial GUI (Region Selection)**     | v0.4.0 (GUI Tool for Region Selection, Naming, Confirming, CLI Integration Save)     | Done               | High     |
| **Logging & Error Handling**           | ADR-007 Impl., Error Handling Review & Initial Pass                                  | Done               | Critical |
| **User Documentation (Basic)**         | `README.md` first draft complete (incl. setup, usage, examples)                      | Done               | High     |

---

## Granular Feature Breakdown (Logical Steps & Future Enhancements)

| Version | Status      | Priority | Epic                       | Feature Name                                         | Description                                                                                                                                | Notes / Key Libraries                                                                     |
| :------ | :---------- | :------- | :------------------------- | :--------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------- |
| **v0.0.x (Core Foundations & Basic Visual PoCs) - Components of AI-Accelerated v1.0.0** |
| `v0.0.1`  | Done        | Critical | Core Capture PoC           | Define Region (Coordinates) & Capture Image        | Allow user to define a single rectangular region via (x,y,w,h) in config. Capture a single image of this region.                         | `OpenCV-Python`, `Pillow`, `json`.                                                        |
| `v0.0.1`  | Done        | Critical | Basic Setup                | Project Structure, Initial Docs, Logging Foundation  | Setup basic project folders, virtual env, core docs, foundational logging setup (per ADR-007) based on `APP_ENV`.                        | Manual setup, `python-dotenv`, `logging`.                                                 |
| `v0.0.2`  | Done        | Critical | Basic Analysis PoC         | Specific Pixel Color Check                         | In the captured region, check the color of a specific predefined pixel.                                                                    | `OpenCV-Python` (NumPy).                                                                  |
| `v0.0.2`  | Done        | High     | Basic Control PoC          | CLI - Trigger Capture & Basic Analysis (Conceptual)  | Basic CLI command to trigger one-shot capture and pixel color check (now part of full CLI).                                                | `argparse`.                                                                               |
| `v0.0.3`  | Done        | Critical | Basic Action PoC           | Conditional Mouse Click (Fixed Pos - Evolved)       | IF pixel color IS specific_color, THEN simulate a mouse click. (Evolved to richer actions).                                                | `pyautogui`.                                                                              |
| `v0.0.3`  | Done        | High     | Configuration PoC          | Load Region & Pixel Check Params from File       | Load region coords, target pixel offset, and expected color from a JSON config file.                                                       | `json` module.                                                                            |
| **v0.1.0 (Core Modules & Basic Interactions - Components of AI-Accelerated v1.0.0)** |
| v0.1.0  | Done        | Critical | Region Management          | Multiple Region Definitions (Config)               | Allow defining multiple named regions in the config file.                                                                                  | `json`.                                                                                   |
| v0.1.0  | Done        | Critical | Enhanced Analysis          | Average Color of Region/Sub-region                 | Calculate the average color of the entire defined region or a sub-rectangle within it.                                                   | `OpenCV-Python`, `NumPy`.                                                                 |
| v0.1.0  | Done        | Critical | Enhanced Actions           | Click within Target Region                         | IF condition MET, click at specific relative coordinates *within* the monitored region, or its center.                                   | `pyautogui`.                                                                              |
| v0.1.0  | Done        | Critical | Core Loop                  | Continuous Monitoring Loop (Fixed Interval)        | Implement a threaded loop that repeatedly captures, analyzes, and potentially acts.                                                        | `threading`, `time`.                                                                      |
| v0.1.0  | Done        | Critical | CLI Controls               | CLI - Start/Stop Monitoring, Load Profile          | Functional CLI (`argparse`) to load a profile, start/stop continuous monitoring.                                                           | `argparse`.                                                                               |
| **v0.2.0 (Template Matching & Improved Rules - Components of AI-Accelerated v1.0.0)** |
| v0.2.0  | Done        | Critical | Advanced Analysis          | Basic Template (Image) Matching                    | User provides template image. Bot searches for this template. Reports if found, location, confidence. Template loading implemented.      | `OpenCV-Python`.                                                                          |
| v0.2.0  | Done        | Critical | Enhanced Actions           | Click Relative to Found Template                   | IF template IS found, click at an offset relative to the template's found location.                                                        | `pyautogui`.                                                                              |
| v0.2.0  | Done        | High     | Rules Engine               | Simple Rules (IF visual_event THEN action)         | Formalize rule structure in config (per ADR-004 Option 1).                                                                                 | `json` for rules.                                                                         |
| v0.2.0  | Done        | Medium   | Performance                | Configurable FPS/Delay for Monitoring Loop         | Allow user to configure the speed of the continuous monitoring loop via profile settings.                                                | Profile parameter.                                                                        |
| **v0.3.0 (OCR Integration - Components of AI-Accelerated v1.0.0)** |
| v0.3.0  | Done        | Critical | Advanced Analysis          | OCR - Text Extraction from Region                  | Extract text from the monitored region using Tesseract.                                                                                    | `pytesseract`, `OpenCV-Python`.                                                           |
| v0.3.0  | Done        | Critical | Rules Engine               | Text-Based Conditions                              | Rules like: "IF text CONTAINS 'keyword' THEN action".                                                                                      | String matching.                                                                          |
| v0.3.0  | Done        | High     | Action Execution           | Basic Keyboard Input Action                        | IF condition MET, simulate typing a predefined string or pressing specific keys.                                                           | `pyautogui`.                                                                              |
| v0.3.0  | Done        | Medium   | Error Handling             | Basic OCR Error Handling                           | Handle Tesseract not found or OCR failures.                                                                                                | Try-except, logging.                                                                      |
| **v0.4.0 (Basic GUI for Region Definition - Components of AI-Accelerated v1.0.0)** |
| v0.4.0  | Done        | High     | Usability                  | GUI Tool for Region Selection                      | GUI (`CustomTkinter`) to draw, name, confirm regions.                                                                                      | `CustomTkinter`.                                                                          |
| v0.4.0  | Done        | Medium   | Configuration              | GUI for Profile Management (Add Region to Profile) | CLI command `--add-region` uses GUI to update profile via `ConfigManager`.                                                                 | `CustomTkinter`, `ConfigManager`.                                                         |
| **AI-Accelerated v1.0.0 - STABILIZATION & DOCUMENTATION** |
| v1.0.0  | In Progress | Critical | Integration & Testing      | Consolidate & Test All AI-Accelerated v1.0.0 Features | Thoroughly test the `run` and `add-region` commands with various profiles and screen conditions. Identify and fix bugs. Log extensively. | All modules.                                                                              |
| v1.0.0  | In Progress | High     | Documentation              | User Guide & README Finalization                   | Review and finalize the `README.md` to ensure it's accurate, clear, and complete for a v1.0.0 user. Add more example profiles.         | Markdown.                                                                                 |
| v1.0.0  | In Progress | Critical | Error Handling             | Robust Global Error Handling & Logging Review      | Final review of error messages and log clarity based on testing experiences. Ensure graceful failure modes.                                | Python `logging`, try-except.                                                             |
| **v2.0.0 (Advanced Visual Analysis & Rules - Post AI-Accelerated v1.0.0)** |
| v2.0.0  | Not Started | High     | Advanced Analysis          | Multiple Template Matching & Logic                 | Support for checking multiple templates; AND/OR logic for conditions (evolution of ADR-004 to Option 2).                               | Enhanced rules engine.                                                                    |
| <!-- ... other v2.0.0, v3.0.0, and vFuture items remain "Not Started" ... -->

---

**Summary & Next Steps:**

*   **Current Status:** The "AI-Accelerated v1.0.0" is feature-complete in terms of its initial implementation. All core modules and functionalities outlined for this version have been developed.
*   **Immediate Focus (Finalizing AI-Accelerated v1.0.0):**
    1.  **Rigorous End-to-End Testing:** This is the most critical next step. We need to:
        *   Test the `run` command with `notepad_automator.json`, `simple_game_helper.json`, and the basic `example_profile.json` (from README) under various screen conditions.
        *   Test the `add-region` command thoroughly: creating new profiles, adding to existing profiles, naming regions.
        *   Specifically test OCR and Template Matching rules by setting up the screen to meet their conditions.
        *   Test edge cases: empty profiles, profiles with no rules/regions, missing template files, incorrect coordinates.
        *   Test on Windows with different screen resolutions or scaling if possible (though primary testing on dev machine is key).
    2.  **Bug Fixing:** Address any issues identified during testing. Pay close attention to logs.
    3.  **README.md Polish:** Add any final clarifications or troubleshooting tips to `README.md` based on testing. Ensure the example profiles are well-explained.
    4.  **Final Logging Review:** One last check to ensure logs are providing clear, actionable information, especially for errors or unexpected behavior found during testing.
*   **Declaration of v1.0.0:** Once the above steps are complete and we are confident in the stability and functionality of the current feature set, we can declare the "AI-Accelerated v1.0.0" as "Done".
*   **Next Major Development (Post v1.0.0):** After v1.0.0 is declared stable, we will update `DEV_CONFIG.MD` to set a new `Active Version` (e.g., `v2.0.0 (Advanced Rule Logic)`) and begin planning and implementing features from the `v2.0.0` section of the roadmap, such as evolving the `RulesEngine` to support ADR-004 Option 2 (compound conditions).

---