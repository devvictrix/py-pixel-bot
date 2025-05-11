// File: docs/FEATURE_ROADMAP.MD
# Feature Roadmap & Status

This document tracks planned features and their status for this visual automation tool. The primary goal is to achieve the "AI-Accelerated v1.0.0" as the first major deliverable, followed by further enhancements up to v3.0.0.

**Key Supporting Documents:**
*   `PROJECT_OVERVIEW.MD`
*   `TECHNICAL_DESIGN.MD`
*   `STATUS_LEGEND.MD` 
*   `DEV_CONFIG.MD`
*   `adrs/` 

---

## AI-Accelerated v1.0.0: Target Feature Set <!-- Completed -->
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
| **AI-Accelerated v1.0.0 STABILIZATION & DOCUMENTATION** | Integration Testing, README Finalization, Error Handling Review | Done               | Critical |

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
| **v1.0.0 (AI-Accelerated Release) - STABILIZATION & DOCUMENTATION** |
| v1.0.0  | Done        | Critical | Integration & Testing      | Consolidate & Test All AI-Accelerated v1.0.0 Features | Thoroughly test the `run` and `add-region` commands with various profiles and screen conditions. Identify and fix bugs. Log extensively. | All modules.                                                                              |
| v1.0.0  | Done        | High     | Documentation              | User Guide & README Finalization                   | Review and finalize the `README.md` to ensure it's accurate, clear, and complete for a v1.0.0 user. Add more example profiles.         | Markdown.                                                                                 |
| v1.0.0  | Done        | Critical | Error Handling             | Robust Global Error Handling & Logging Review      | Final review of error messages and log clarity based on testing experiences. Ensure graceful failure modes.                                | Python `logging`, try-except.                                                             |
| **v2.0.0 (Advanced Visual Analysis & Rules) - COMPLETED** |
| v2.0.0  | Done        | High     | Rules Engine Enhancement   | Compound Conditions (AND/OR Logic)                 | Evolve RulesEngine to support ADR-004 Option 2: multiple conditions per rule with AND/OR logic.                                          | Enhanced `rules_engine.py`, JSON profile schema update.                                   |
| v2.0.0  | Done        | High     | Advanced Analysis          | OCR Confidence Thresholds in Rules                 | Allow rules to use OCR confidence scores (e.g., "IF text CONTAINS 'X' AND confidence > 0.85").                                         | `pytesseract` features, `rules_engine.py`.                                                |
| v2.0.0  | Done        | Medium   | Advanced Analysis          | Color Palette Analysis / Dominant Color            | Analyze region for dominant colors using K-Means. Rules can check against these.                                                           | `OpenCV-Python` (k-means).                                                                |
| v2.0.0  | Done        | Medium   | Rules Engine               | Variables in Rules / Actions                       | Allow defining temporary rule-scoped variables from analysis (OCR, template match) and using them in subsequent conditions/actions.      | `rules_engine.py` (variable context, substitution).                                       |
| v2.0.0  | Done        | Medium   | Performance                | Selective Analysis per Rule                        | Optimize `MainController` to only run specific general analyses (OCR, dominant color) on a region if an active rule requires it.            | `main_controller.py`, `rules_engine.py` interaction.                                      |
| **v3.0.0 (Enhanced GUI & Usability)** |
| v3.0.0  | In Progress | High     | Usability                  | Full GUI for Profile & Rule Configuration          | A comprehensive GUI (`MainAppWindow`) to visually create/edit profiles: regions, templates, rules (conditions, actions, parameters, structure conversion), settings. Includes robust input validation and refinements. | `CustomTkinter`. Phase 1.8.1 (Input Validation & Refinements) is current.                 |
| v3.0.0  | Not Started | Low      | Usability                  | GUI - Sub-condition/Rule Reordering (Simple)       | Add simple "Move Up/Down" buttons for sub-conditions and rules in the GUI editor lists.                                                    | `CustomTkinter`.                                                                          |
| v3.0.0  | Not Started | Medium   | Usability                  | Real-time Visual Feedback in GUI                   | GUI shows live view of monitored region(s), overlays detected elements (templates, text boxes) for easier debugging/setup of rules.    | `OpenCV-Python` with GUI library.                                                         |
| v3.0.0  | Not Started | Medium   | Action Execution           | Chained Actions / Simple Macros                    | Allow defining a sequence of multiple actions to be performed if a single condition is met.                                                | Data structure for action sequences in profile, `action_executor.py`.                     |
| v3.0.0  | Not Started | Medium   | Usability                  | Profile Importer/Exporter                          | Simple way to share bot profiles.                                                                                                          | `ConfigManager` enhancements.                                                             |
| **vFuture (Advanced Enhancements & Integrations - Post v3.0.0)** |
| vFuture | Not Started | Medium   | Advanced Analysis          | Fuzzy Template Matching & Tolerance                | Allow template matching with varying degrees of tolerance for slight changes in color, rotation, or scale.                             | Advanced `OpenCV-Python` techniques.                                                      |
| vFuture | Not Started | Medium   | Advanced Analysis          | Motion/Change Detection within Region              | Detect if any significant visual change or motion occurs within a monitored region, not just static states.                                | Frame differencing, background subtraction.                                               |
| vFuture | Not Started | Low      | Advanced Analysis          | Basic Object/Shape Detection (Simplified)          | Detect simple geometric shapes (circles, rectangles) or basic pre-trained objects.                                                         | `OpenCV-Python` (contour detection, basic ML models if lightweight).                      |
| vFuture | Not Started | High     | Advanced Actions           | Dynamic Action Parameters based on Analysis        | Allow actions to use data extracted during analysis more deeply (e.g., type OCR'd number, click at OCR'd text location).                 | Enhanced `action_executor.py`, `rules_engine.py`.                                         |
| vFuture | Not Started | Low      | Advanced Actions           | Sound Alerts / System Notifications                | Play a sound or send a system notification when a condition is met.                                                                      | `playsound` library, platform-specific notification libs.                                 |
| vFuture | Not Started | Medium   | Integration                | Webhook / API Call Action                          | Allow the bot to send an HTTP request to an external service when a condition is met.                                                    | `requests` library. Potential ADR for security/config.                                    |
| vFuture | Not Started | High     | Usability                  | Visual Logging & Debugging History                 | Save snapshots of monitored regions when rules trigger/fail. Provide a visual history or step-through for debugging rules.               | Image saving, GUI enhancements. Potential ADR.                                            |
| vFuture | Not Started | Medium   | Usability                  | Region/Rule Library & Reusability                  | Allow users to save and import/export individual regions or rule definitions to be reused across different profiles.                       | Enhanced `config_manager.py`.                                                             |

---

**Summary & Next Steps:**

*   **AI-Accelerated v1.0.0 Complete.**
*   **v2.0.0 (Advanced Visual Analysis & Rules) Complete.**
*   **Current Development Focus: `v3.0.0 (Enhanced GUI & Usability)`**
    *   **"Full GUI for Profile & Rule Configuration"** is the primary epic.
    *   Core GUI layout, file operations, and detailed editing for profiles, regions, templates, and rules (including conditions, actions, parameters, sub-conditions, structure conversion, and input validation) are substantially implemented.
    *   **Phase 1.8.1 (Input Validation & Refinements)** is the current active phase, having just delivered significant validation enhancements.
*   **Immediate Next Step (within Phase 1.8 of Full GUI):** Continue with GUI Refinements and UX Improvements. Based on the previous plan for Phase 1.8, this involves:
    1.  **GUI State Consistency:** Thoroughly test and improve list selection behavior after edits, button states, and overall UI responsiveness. Ensure detail panels always reflect the true state of a selected item.
    2.  **Usability Enhancements (Small Wins):**
        *   Implement tooltips for key UI elements (e.g., `CTkToolTip` or basic mouse-over text).
        *   Add a simple Status Bar at the bottom of `MainAppWindow` for persistent messages like "Profile Saved", "Unsaved changes*", or brief error summaries.
    3.  **Code Refinements:** Review `MainAppWindow` for any parts that can be further broken down into smaller, more focused helper methods to improve readability and maintainability, especially within the `_update_details_panel` and "Apply" methods.
    4.  **Comprehensive Logging Review:** A final pass over all GUI interaction logs to ensure clarity, consistency, and completeness.
*   After these refinements, we will assess if "Sub-condition/Rule Reordering (Simple)" is feasible for the initial v3.0.0 GUI or if it should be deferred. Then, we can consider the "Full GUI for Profile & Rule Configuration" feature complete and move to other v3.0.0 items like "Real-time Visual Feedback" or "Chained Actions".

---