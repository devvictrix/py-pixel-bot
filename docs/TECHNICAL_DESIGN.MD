// File: docs/TECHNICAL_DESIGN.MD
# TECHNICAL_DESIGN.MD
# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, AI-Accelerated v1.0.0 is complete. Development for v2.0.0 is underway, with "Compound Conditions" implemented and "OCR Confidence Thresholds in Rules" being the current focus.

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
        *   OCR text extraction (`ocr_extract_text`) using `pytesseract` (per ADR-001). **This method now returns a dictionary containing the extracted text and an average confidence score.**
*   **`engines.rules_engine.RulesEngine` Class:**
    *   Evaluates conditions based on analysis results.
    *   Supports both single conditions (ADR-004 Option 1) and compound conditions (ADR-004 Option 2).
    *   Retrieves rules from `ConfigManager`.
    *   For each rule:
        *   If a condition requires specific, on-demand analysis (e.g., pixel color, template matching), its evaluation logic calls the appropriate `AnalysisEngine` method.
        *   Manages loading and caching of template images.
        *   Uses pre-calculated general analysis results (average color, OCR text and confidence) provided by `MainController`.
        *   **For OCR conditions, it can now use the reported average confidence score against a user-defined threshold in the rule.**
    *   Triggers actions via `ActionExecutor` if the overall rule condition is met.
*   **`engines.action_executor.ActionExecutor` Class:**
    *   Simulates mouse and keyboard actions using `pyautogui` (per ADR-002).
    *   Calculates target coordinates for actions.
*   **`main_controller.MainController` Class:**
    *   Orchestrates the main bot operation loop.
    *   Runs the monitoring loop in a separate thread (per ADR-006).
    *   For each monitored region:
        *   Instructs `CaptureEngine` to capture the image.
        *   Instructs `AnalysisEngine` to perform general analyses (average color, **OCR with confidence**).
        *   Collects these results into a data packet for each region. **The OCR result is now a dictionary: `{"text": "...", "average_confidence": ...}`.**
    *   Passes the dictionary of all region data packets to `RulesEngine.evaluate_rules()`.
*   **`ui.cli` Module:** (No changes in this feature)
*   **`ui.gui.region_selector.RegionSelectorWindow` Class:** (No changes in this feature)
*   **`__main__.py` (in `src/`):** (No changes in this feature)

## 2. Key Libraries & Justifications (Summary from ADRs)
    *   (This section remains largely the same)
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
    *   (This section remains the same)
    *   Regions are defined in the JSON profile with `name, x, y, width, height`.
    *   The `add-region` CLI command launches the `RegionSelectorWindow` GUI for users to define these graphically. The results are saved to the profile by `ConfigManager`.
    *   `CaptureEngine` uses these coordinates to capture screen areas via `Pillow.ImageGrab` (for Windows) and converts to BGR NumPy arrays.

## 4. "Reading" from the Region - Analysis Strategies
1.  **General Pre-emptive Analysis (by `MainController` using `AnalysisEngine`):**
    *   For each captured region image in the main loop, `MainController` instructs `AnalysisEngine` to perform analyses like:
        *   Average color (`analyze_average_color`).
        *   OCR text extraction (`ocr_extract_text`). **This method now returns a dictionary containing the extracted `text` and an `average_confidence` score (e.g., a float 0-100). `MainController` stores this dictionary under the key `ocr_analysis_result` in the region's data packet.**
    *   These results are stored along with the `captured_image` in a data packet for this region. This entire collection of region data packets is then passed to the `RulesEngine`.
2.  **Specific On-Demand Analysis (by `RulesEngine`'s `_evaluate_single_condition_logic` using `AnalysisEngine`):**
    *   When `RulesEngine` evaluates a specific (sub-)condition:
        *   If the condition is `pixel_color`, it calls `AnalysisEngine.analyze_pixel_color()` with the captured image for that (sub-)condition's target region and coordinates from the rule.
        *   If the condition is `template_match_found`, `RulesEngine` first loads the specified template image and then calls `AnalysisEngine.match_template()` with the (sub-)condition's target region's captured image and the loaded template image data.
        *   **Note:** OCR is now primarily a pre-emptive analysis. `RulesEngine` consumes the `ocr_analysis_result` (text and confidence) from the data packet.

## 5. Rules Engine & Evaluation (per ADR-004 Options 1 & 2)

The `RulesEngine` is responsible for interpreting rules defined in JSON profiles and determining if their conditions are met. It supports single-condition rules, compound conditions (AND/OR logic), and now, OCR conditions with confidence thresholds.

### 5.1. Rule Structure in JSON Profiles

Profiles contain a list of rule objects.

**Single Condition Rule (Backwards Compatible):**
```json
{
  "name": "RuleNameSimple",
  "region": "target_region_for_condition",
  "condition": {
    "type": "pixel_color", 
    "relative_x": 5, "relative_y": 5, "expected_bgr": [0,0,255]
  },
  "action": { /* ... */ }
}
```

**Compound Condition Rule:**
```json
{
  "name": "RuleNameCompound",
  "region": "default_region_for_subconditions",
  "condition": {
    "logical_operator": "AND", 
    "sub_conditions": [ /* ... array of single condition objects ... */ ]
  },
  "action": { /* ... */ }
}
```

**Enhanced `ocr_contains_text` Condition Type (Applicable in single or sub-conditions):**
```json
{
  "type": "ocr_contains_text",
  "text_to_find": "Ready",
  "case_sensitive": false,
  "min_ocr_confidence": 75.0 // Optional: float (0-100). If present, average OCR confidence must meet this.
}
```
*   If `min_ocr_confidence` is specified, the text must be found AND the average confidence score from the OCR analysis for that region must be greater than or equal to this value. If not specified, only the text match is considered.

### 5.2. `RulesEngine` Evaluation Logic

*   **`evaluate_rules(self, all_region_data: Dict[str, Dict])`:**
    *   (No change to overall flow for this feature) Iterates rules, calls `_check_condition`.

*   **`_check_condition(self, rule_name: str, condition_spec: Dict, default_rule_region: Optional[str], all_region_data: Dict) -> bool`:**
    *   (No change to overall flow for this feature) Determines if single or compound, then calls or iterates to `_evaluate_single_condition_logic`.

*   **`_evaluate_single_condition_logic(self, single_condition_spec: Dict, region_name: str, region_data: Dict, rule_name_for_context: str) -> bool`:**
    *   This helper method evaluates individual, non-compound conditions.
    *   **For `condition_type == "ocr_contains_text"`:**
        1.  Retrieves the `ocr_analysis_result` dictionary (containing `text` and `average_confidence`) from `region_data` (which was populated by `MainController` from `AnalysisEngine`).
        2.  If `ocr_analysis_result` or its necessary keys are missing, the condition typically evaluates to false (error logged).
        3.  Extracts the `actual_ocr_text` and `actual_average_confidence`.
        4.  Performs the text matching against `actual_ocr_text` based on `text_to_find` and `case_sensitive` parameters from `single_condition_spec`. Let this be `text_found_result`.
        5.  Retrieves `min_ocr_confidence_threshold` from `single_condition_spec`.
        6.  **If `min_ocr_confidence_threshold` is specified:** The condition is true if AND ONLY IF `text_found_result` is true AND `actual_average_confidence >= min_ocr_confidence_threshold`. Logging will detail both checks.
        7.  **If `min_ocr_confidence_threshold` is NOT specified:** The condition is true if AND ONLY IF `text_found_result` is true.
    *   Other condition types (`pixel_color`, `template_match_found`, etc.) are handled as previously described.

*   **`_load_template_image_for_rule(...)`:** (No changes for this feature)

## 6. Data Flow Example (Simplified Continuous Loop)
1.  `MainController` thread starts.
2.  Loop iteration:
    a.  For each monitored `region_spec` in the profile:
        i.  `CaptureEngine` captures image for the region.
        ii. `MainController` calls `AnalysisEngine` for general analyses.
            *   `analyze_average_color(...)` returns average color.
            *   **`analyze_ocr_text(...)` now returns `{"text": "...", "average_confidence": ...}`.**
        iii.Stores these in a data packet for this region (e.g., `all_region_data[region_name]["ocr_analysis_result"] = ocr_dict`).
    b.  `MainController` passes `all_region_data` to `RulesEngine.evaluate_rules()`.
    c.  `RulesEngine` iterates rules. For each rule's condition (or sub-condition):
        i.  If it's an `ocr_contains_text` condition, `_evaluate_single_condition_logic` retrieves the `ocr_analysis_result` (text and confidence) from the relevant region's data in `all_region_data`.
        ii. It checks the text and, if `min_ocr_confidence` is set in the rule, also checks the confidence score.
        iii.Other conditions are evaluated as before.
    d. If condition met, `ActionExecutor` performs the action.
3.  Loop repeats.

## 7. Logging System (per ADR-007)
*   (No fundamental changes to the logging system itself).
*   New log messages will be added to `AnalysisEngine` to detail the average OCR confidence.
*   `RulesEngine` logging for `ocr_contains_text` conditions will be enhanced to show:
    *   The text found (or not).
    *   The actual average confidence score.
    *   The required minimum confidence (if set).
    *   The outcome of the confidence check.

## 8. Error Handling
*   (No fundamental changes to error handling strategy).
*   `AnalysisEngine.ocr_extract_text` will handle potential errors from `pytesseract.image_to_data` and in calculating average confidence, returning `None` or a partial result with clear error logging.
*   `RulesEngine` will gracefully handle cases where `ocr_analysis_result` or its expected keys (`text`, `average_confidence`) are missing from `region_data`, typically evaluating the condition to false and logging a warning.

---
