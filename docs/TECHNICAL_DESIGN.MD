# TECHNICAL_DESIGN.MD
# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status towards the "AI-Accelerated v1.0.0".

## 1. Core Architecture

The tool is modular, comprising several key Python components:

*   **`core.config_manager` Module:**
    *   `load_environment_variables()` function: Called at application startup to load `.env` (containing `APP_ENV`) using `python-dotenv` (per ADR-007).
    *   `ConfigManager` class: Responsible for loading, validating (basic structure), providing access to, and saving bot profiles (JSON files from the `profiles/` directory, per ADR-003). It also provides the base path for profile-related assets like templates.
*   **`core.logging_setup` Module:**
    *   `setup_logging()` function: Called after environment variables are loaded. Initializes Python's `logging` system based on `APP_ENV`, configuring handlers (console, date-stamped rotating file), formatters, and log levels (per ADR-007).
*   **`engines.capture_engine.CaptureEngine` Class:**
    *   Responsible for capturing image data from specified screen regions using `Pillow.ImageGrab` (initially for Windows simplicity) and converting it to OpenCV BGR NumPy arrays (per ADR-001).
*   **`engines.analysis_engine.AnalysisEngine` Class:**
    *   Performs various analyses on captured image regions (NumPy BGR arrays).
    *   Provides methods for:
        *   Pixel color analysis (`analyze_pixel_color`).
        *   Average color calculation (`analyze_average_color`).
        *   Template matching (`match_template`) using OpenCV (per ADR-001).
        *   OCR text extraction (`ocr_extract_text`) using `pytesseract` (per ADR-001).
*   **`engines.rules_engine.RulesEngine` Class:**
    *   Evaluates conditions based on analysis results, adhering to ADR-004 (Option 1 initially).
    *   Retrieves rules from `ConfigManager`.
    *   For each rule:
        *   If a condition requires specific, on-demand analysis (e.g., pixel color at specific coordinates, template matching with a specific template file), it calls the appropriate `AnalysisEngine` method, passing the captured image for the rule's target region.
        *   Manages loading and caching of template images (e.g., from `profiles/templates/`) specified in rule conditions.
        *   Uses pre-calculated general analysis results (like average color, OCR text) provided by `MainController` for relevant conditions.
    *   Triggers actions via `ActionExecutor` if conditions are met.
*   **`engines.action_executor.ActionExecutor` Class:**
    *   Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
    *   Calculates target coordinates for actions based on absolute values, region-relative positions, or positions relative to found templates (using data passed from `RulesEngine`).
*   **`main_controller.MainController` Class:**
    *   Orchestrates the main bot operation loop: Capture -> General Analysis -> Rule Evaluation -> Action.
    *   Runs the monitoring loop in a separate thread to keep the UI responsive (per ADR-006).
    *   For each monitored region in a profile:
        *   Instructs `CaptureEngine` to capture the image.
        *   Instructs `AnalysisEngine` to perform *general, pre-emptive analyses* (e.g., average color, OCR) on the captured image.
        *   Collects these general analysis results along with the captured image itself.
    *   Passes the collected data (including raw images for on-demand analysis by `RulesEngine`) to `RulesEngine.evaluate_rules()`.
*   **`ui.cli` Module:**
    *   Provides the Command-Line Interface using `argparse` (per ADR-005).
    *   Handles subcommands:
        *   `run <profile>`: Loads a profile and starts the `MainController`.
        *   `add-region <profile>`: Launches the `RegionSelectorWindow` GUI to define/update a region and save it to the profile via `ConfigManager`.
    *   Allows verbosity control (`-v`, `-vv`) which adjusts console logging levels.
*   **`ui.gui.region_selector.RegionSelectorWindow` Class:**
    *   A `CustomTkinter` based Toplevel window for graphically selecting screen regions (per ADR-005).
    *   Allows users to draw a rectangle, name it, and confirm.
    *   Returns the selected region's name and coordinates.
*   **`__main__.py` (in `src/`):**
    *   The main application entry point (`python -m py_pixel_bot`).
    *   Ensures correct initialization order: loads `.env`, sets up logging, parses CLI arguments, then instantiates and starts the application logic based on the command.

## 2. Key Libraries & Justifications (Summary from ADRs)
    *   (This section remains largely the same as it lists decided libraries)
    *   Environment Management: `python-dotenv` (ADR-007)
    *   Logging: Python `logging` module (ADR-007)
    *   Screen Capture & Image Analysis: `OpenCV-Python` (cv2), `NumPy`, `Pillow` (ADR-001).
    *   OCR: `pytesseract` (ADR-001).
    *   Input Simulation: `pyautogui` (ADR-002).
    *   Configuration Storage: `json` (Python built-in) (ADR-003).
    *   CLI Framework: `argparse` (Python built-in) (ADR-005).
    *   GUI Framework (Initial): `CustomTkinter` (ADR-005).
    *   Concurrency: Python `threading` module (ADR-006).

## 3. Defining and Capturing Regions
    *   Regions are defined in the JSON profile with `name, x, y, width, height`.
    *   The `add-region` CLI command launches the `RegionSelectorWindow` GUI for users to define these graphically. The results are saved to the profile by `ConfigManager`.
    *   `CaptureEngine` uses these coordinates to capture screen areas via `Pillow.ImageGrab` (for Windows) and converts to BGR NumPy arrays.

## 4. "Reading" from the Region - Analysis Strategies
1.  **General Pre-emptive Analysis (by `MainController` using `AnalysisEngine`):**
    *   For each captured region image in the main loop, `MainController` instructs `AnalysisEngine` to perform analyses like:
        *   Average color (`analyze_average_color`).
        *   OCR text extraction (`ocr_extract_text`).
    *   These results are stored along with the captured image for the `RulesEngine`.
2.  **Specific On-Demand Analysis (by `RulesEngine` using `AnalysisEngine`):**
    *   When `RulesEngine` evaluates a rule's condition:
        *   If the condition is `pixel_color`, it calls `AnalysisEngine.analyze_pixel_color()` with the captured image for that region and coordinates from the rule.
        *   If the condition is `template_match_found`, `RulesEngine` first loads the specified template image (from `profiles/templates/` via its `_load_template_image_for_rule` method) and then calls `AnalysisEngine.match_template()` with the region's captured image and the loaded template image data.

## 5. Rules Engine & Evaluation (per ADR-004 Option 1)
*   Profiles contain a list of rule objects.
*   Current rule structure:
    ```json
    {
      "name": "RuleName",
      "region": "target_region_for_condition", 
      "condition": {
        "type": "pixel_color", "relative_x": 5, "relative_y": 5, "expected_bgr": [R,G,B]
        // OR "type": "average_color_is", "expected_bgr": [R,G,B], "tolerance": 10
        // OR "type": "template_match_found", "template_filename": "icon.png", "min_confidence": 0.8
        // OR "type": "ocr_contains_text", "text_to_find": "Ready", "case_sensitive": false
      },
      "action": {
        "type": "click", "target_relation": "center_of_last_match" 
        // OR "type": "type_text", "text": "Hello"
        // OR "type": "press_key", "key": "enter"
        // OR "type": "log_message", "message": "Condition met"
        // Action can also have "target_region" if different from condition's region.
      }
    }
    ```
*   `RulesEngine.evaluate_rules()` iterates these rules:
    1.  For a rule, it gets the `captured_image` and any pre-calculated analysis data for the rule's `region` from the data packet provided by `MainController`.
    2.  It calls its internal `_check_condition()` method, passing the rule's condition spec, the pre-calculated analysis data for that region, and the raw captured image.
    3.  `_check_condition()` performs the check:
        *   Uses pre-calculated data for `average_color_is`, `ocr_contains_text`.
        *   Calls `AnalysisEngine` methods for `pixel_color` and `template_match_found` (loading templates as needed).
    4.  If the condition is true, it retrieves the action spec and calls `ActionExecutor.execute_action()`, providing necessary context (like match location from `_last_template_match_info` or target region specs).

## 6. Data Flow Example (Simplified Continuous Loop)
    <!-- This section is largely still accurate from the previous version but is reinforced by the above. -->
1.  `MainController` thread starts.
2.  Loop iteration:
    a.  For each monitored `region_spec` in the profile:
        i.  `CaptureEngine` captures image for the region.
        ii. `MainController` calls `AnalysisEngine` for general analyses (average color, OCR) on this image.
        iii.Stores `captured_image` and general analysis results in a data packet for this region.
    b.  `MainController` passes the collection of all region data packets (for this iteration) to `RulesEngine.evaluate_rules()`.
    c.  `RulesEngine` iterates its defined rules. For each rule:
        i.  Uses the appropriate region's data packet (containing image and pre-calculated analyses).
        ii. Calls `_check_condition()`. If needed for the condition type (pixel, template), `_check_condition` uses the passed `captured_image` to call `AnalysisEngine` methods.
        iii.If condition met, `RulesEngine` calls `ActionExecutor` with action details and context.
    d. `ActionExecutor` performs the OS-level mouse/keyboard action.
3.  Loop repeats after `monitoring_interval`. Log messages are generated throughout.

## 7. Logging System (per ADR-007)
*   Initialized by `core.logging_setup.setup_logging()` using `APP_ENV` from `.env`.
*   Main package logger is `"py_pixel_bot"`; modules use child loggers like `logging.getLogger(__name__)`.
*   **File Logs:** Written to a `logs/` directory in the project root. Filenames are date-stamped (e.g., `2025-05-11.log`). `RotatingFileHandler` manages size within the day. The log format for files includes `APP_ENV`.
*   **Console Logs:** Verbosity and format depend on `APP_ENV` and can be overridden by CLI's `-v` flags.
*   Comprehensive logging at all important steps, decisions, errors, and state changes is a core principle.

## 8. Error Handling
*   Modules use `try-except` blocks for operations like file I/O, image processing, and external library calls.
*   Specific exceptions (e.g., `FileNotFoundError`, `json.JSONDecodeError`, `pytesseract.TesseractNotFoundError`) are caught where appropriate. Generic `Exception` with `exc_info=True` is used for unexpected issues.
*   `MainController`'s monitoring loop has a top-level `try-except` to log critical errors and allow graceful thread termination.
*   `src/__main__.py` has robust error handling for application startup and unhandled exceptions in the main thread, ensuring informative messages and proper exit codes.

---