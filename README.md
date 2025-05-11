# PyPixelBot - Visual Automation Tool for Windows

PyPixelBot is a Python-based desktop automation tool for Windows. It captures and analyzes specific, user-defined regions of the screen in real-time. Based on this visual analysis (e.g., detecting colors, matching images/templates, or recognizing text via OCR), it can perform actions like mouse clicks and keyboard inputs.

This tool is designed for automating tasks that rely on visual cues, especially in applications or games that may not offer traditional APIs for automation.

## Features (AI-Accelerated v1.0.0)

*   **Targeted Screen Region Analysis:** Define specific rectangular areas on your screen to monitor.
*   **Visual Analysis Capabilities:**
    *   **Pixel Color:** Check the color of specific pixels.
    *   **Average Color:** Determine the average color of a region.
    *   **Template Matching:** Find occurrences of a predefined image (template) within a region.
    *   **OCR (Optical Character Recognition):** Extract text from a region.
*   **Conditional Actions:** Define rules (IF visual condition is MET THEN perform action).
*   **Supported Actions:**
    *   Mouse clicks (left, right, middle) at specific or relative coordinates.
    *   Typing text.
    *   Pressing individual keys or hotkeys.
*   **Configuration via JSON Profiles:** Define regions, rules, and actions in human-readable JSON files.
*   **Command-Line Interface (CLI):**
    *   Run bot profiles.
    *   Graphically add/update regions to profiles using a built-in GUI selector.
*   **Environment-Aware Logging:** Comprehensive logging with configurable verbosity for development, UAT, and production.

## Prerequisites

1.  **Python:** Version 3.9+ (developed with 3.12.x on Windows). Download from [python.org](https://www.python.org/downloads/windows/).
    *   During installation, **ensure "Add Python to PATH" is checked.**
2.  **Tesseract OCR Engine (for OCR functionality):**
    *   Download a Tesseract installer for Windows (e.g., from [UB Mannheim Tesseract builds](https://github.com/UB-Mannheim/tesseract/wiki)).
    *   During Tesseract installation, **ensure it is added to your system's PATH.**
    *   Install language data files (e.g., `eng.traineddata`) for Tesseract.
3.  **Git (Optional):** For cloning.

## Setup Instructions

1.  **Clone/Download:** Get the source code and navigate to the `py-pixel-bot` directory.
2.  **Virtual Environment (Recommended):**
    ```bash
    # In project root (py-pixel-bot)
    py -m venv .venv
    .venv\Scripts\activate 
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create `.env` File:**
    In `py-pixel-bot` root, create `.env` with:
    ```dotenv
    APP_ENV=development
    ```
    *   Options: `development` (verbose logs), `uat`, `production`.

## Basic Usage

All commands are run from the project root (`py-pixel-bot/`) with the virtual environment activated.

### 1. Adding/Updating a Region to a Profile (GUI)

Launches a GUI to select a screen region.
```bash
python -m py_pixel_bot add-region <profile_filename> [--name <initial_region_name>] [-v[v]]
```
*   `<profile_filename>`: In `profiles/` (e.g., `my_game` or `my_game.json`). Created if new.
*   `--name <initial_region_name>` (Optional): Initial name for the region in GUI.
*   `-v` / `-vv` (Optional): Increases console log verbosity.

**Example:**
```bash
python -m py_pixel_bot add-region my_profile --name ScreenTopLeft -vv
```
Select a region, name it (if needed), click "Confirm Region". Press `ESC` or "Redraw/Cancel" to restart selection or close.

### 2. Running a Bot Profile

Executes the defined automation.
```bash
python -m py_pixel_bot run <profile_filename> [-v[v]]
```
*   `<profile_filename>`: Profile in `profiles/`.
*   `-v` / `-vv` (Optional): Increases console log verbosity.

**Example:**
```bash
python -m py_pixel_bot run my_profile -v
```
Press `Ctrl+C` in the console to stop the bot.

## Profile JSON Structure (`profiles/<your_profile_name>.json`)

A profile defines regions to watch, templates to find, and rules for actions.

*   **`profile_description`**: (String) A brief description.
*   **`settings`**: (Object) Bot-wide settings.
    *   `monitoring_interval_seconds`: (Float) How often the bot checks regions (e.g., `1.0`).
*   **`regions`**: (List of Objects) Areas on the screen. Each object:
    *   `name`: (String) Unique identifier for the region.
    *   `x`, `y`: (Integer) Top-left screen coordinates.
    *   `width`, `height`: (Integer) Dimensions of the region.
    *   `comment` (Optional String): Notes about the region.
*   **`templates` (Optional List of Objects)**: Defines template images for matching.
    *   `name`: (String) Unique identifier for this template definition (can be used by rules, though currently rules use `template_filename` directly).
    *   `filename`: (String) The image filename (e.g., `my_icon.png`). **Place these image files in a `profiles/templates/` subdirectory.**
*   **`rules`**: (List of Objects) Logic for the bot. Each rule object:
    *   `name`: (String) Descriptive name for the rule.
    *   `region`: (String) The `name` of a region (from the `regions` list) where this rule's condition is checked.
    *   `condition`: (Object) What to check.
        *   `type`: (String) Type of check:
            *   `"pixel_color"`: Checks a specific pixel.
                *   `relative_x`, `relative_y`: (Integer) Coordinates relative to the region's top-left.
                *   `expected_bgr`: (List of 3 Integers) `[Blue, Green, Red]` color values.
            *   `"average_color_is"`: Checks the region's average color.
                *   `expected_bgr`: (List of 3 Integers) `[B, G, R]`.
                *   `tolerance`: (Integer, Optional, default `0`) Allowed deviation per channel.
            *   `"template_match_found"`: Checks if a template image is found.
                *   `template_filename`: (String) Filename of the template image (from `profiles/templates/`).
                *   `min_confidence`: (Float, Optional, default `0.8`) Minimum similarity (0.0 to 1.0).
            *   `"ocr_contains_text"`: Checks if extracted text contains a substring.
                *   `text_to_find`: (String) The text to search for.
                *   `case_sensitive`: (Boolean, Optional, default `false`).
            *   `"always_true"`: (For testing) Condition always met.
    *   `action`: (Object) What to do if the condition is met.
        *   `type`: (String) Type of action: `click`, `type_text`, `press_key`, `log_message`.
        *   `target_region` (Optional String): Name of a region to target for the action (if different from the condition's `region`). If omitted, often implies the condition's region or screen-relative based on other params.
        *   **For `click`:**
            *   `x`, `y`: (Integer, Optional) Absolute screen coordinates.
            *   `target_relation` (Optional String): How to calculate click point if `x,y` not given:
                *   `"center_of_region"`: Center of the `action.target_region` (or rule's `region` if `action.target_region` omitted).
                *   `"offset_from_region_tl"`: Offset from Top-Left of `action.target_region`.
                *   `"center_of_last_match"`: Center of the template found by the triggering rule's condition (if applicable).
                *   `"offset_from_last_match_tl"`: Offset from Top-Left of found template.
            *   `x_offset`, `y_offset`: (Integer, Optional, default `0`) Additional offset for relative clicks.
            *   `button`: (String, Optional, default `"left"`) Mouse button: `"left"`, `"right"`, `"middle"`.
            *   `clicks`: (Integer, Optional, default `1`) Number of clicks.
            *   `interval`: (Float, Optional, default `0.1`) Seconds between multiple clicks.
        *   **For `type_text`:**
            *   `text`: (String) The text to type.
            *   `interval`: (Float, Optional, default `0.01`) Seconds between keystrokes.
        *   **For `press_key`:**
            *   `key`: (String or List of Strings) Key name(s) (e.g., `"enter"`, `"f5"`, `["ctrl", "c"]` for hotkeys). See PyAutoGUI docs for key names.
        *   **For `log_message`:**
            *   `message`: (String) The message to log at INFO level.
        *   `pyautogui_pause_before`: (Float, Optional, default `0.05`) Seconds to pause before PyAutoGUI executes the action.

## Example Profiles

See the `profiles/` directory for examples:

*   **`example_profile.json`**: A very basic starting point.
*   **`notepad_automator.json`**: Demonstrates OCR for interacting with Notepad.
    *   *Setup*: Open Notepad and ensure its text area covers the screen coordinates defined in `regions[0]`. Type "TODO:" into Notepad.
*   **`simple_game_helper.json`**: Simulates a game helper using average color (for a health bar) and template matching (for an action icon).
    *   *Setup*: You'll need to create a `profiles/templates/action_icon.png`. Then, arrange elements on your screen that match the colors and show the icon in the defined regions.

**Adjust coordinates in `regions` within these profiles to match your screen setup before running!**

## Logging

Log files are created daily in the `logs/` directory (e.g., `2025-05-11.log`).
Log verbosity is controlled by `APP_ENV` in `.env` and CLI flags (`-v`, `-vv`).

## Development

(Future: Contribution guidelines, advanced testing.)

## License

(To be determined)