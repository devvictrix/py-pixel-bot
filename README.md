# PyPixelBot: A Visual Automation Tool

PyPixelBot is a Python-based desktop automation tool that captures specific screen regions, analyzes their content (colors, images, text via OCR, dominant colors), and performs actions (mouse clicks, keyboard inputs) based on user-defined rules. It features a comprehensive GUI for creating and managing automation profiles, alongside a CLI for running bots.

**Current Development: v3.0.0 (Enhanced GUI & Usability)**
*   AI-Accelerated v1.0.0: Completed (Core features, basic GUI for region selection)
*   v2.0.0 (Advanced Visual Analysis & Rules): Completed (Compound conditions, OCR confidence, dominant colors, variables, selective analysis)
*   v3.0.0: In Progress (Full GUI Profile Editor - core editing features including input validation implemented, focus on refinements)

## Table of Contents

- [PyPixelBot: A Visual Automation Tool](#pypixelbot-a-visual-automation-tool)
  - [Table of Contents](#table-of-contents)
  - [Core Features](#core-features)
  - [How it Works](#how-it-works)
  - [Technology Stack](#technology-stack)
  - [Setup Instructions](#setup-instructions)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Environment Configuration](#environment-configuration)
    - [PYTHONPATH Configuration](#pythonpath-configuration)
  - [Usage (CLI)](#usage-cli)
    - [Running a Bot Profile](#running-a-bot-profile)
    - [Adding/Updating a Region (Simple GUI Tool)](#addingupdating-a-region-simple-gui-tool)
    - [Editing a Profile (Full GUI Editor)](#editing-a-profile-full-gui-editor)
  - [Configuration Profiles (.json)](#configuration-profiles-json)
    - [Structure Overview](#structure-overview)
    - [Example Profiles](#example-profiles)
  - [Logging](#logging)
  - [Development](#development)
  - [Contributing (Future)](#contributing-future)
  - [License](#license)

## Core Features

*   **Region-Based Screen Capture:** Define specific rectangular areas on your screen to monitor.
*   **Advanced Visual Analysis:**
    *   **Pixel & Average Color Analysis:** Check specific or average colors within a region.
    *   **Template Matching:** Detect if a small image (template) is present, with confidence scoring.
    *   **OCR Text Extraction:** Extract text using Tesseract, including average confidence scores.
    *   **Dominant Color Analysis:** Identify the main colors in a region using K-Means clustering.
*   **Flexible Rule Engine:**
    *   Define rules with **single conditions** or **compound conditions** (AND/OR logic with multiple sub-conditions).
    *   Utilize OCR confidence and dominant color properties in conditions.
    *   **Capture variables** from analysis results (e.g., OCR text, template match details) for use in subsequent conditions or actions.
*   **Versatile Actions:**
    *   **Mouse Simulation:** Clicks (left, right, middle), targeted precisely.
    *   **Keyboard Simulation:** Type text or press keys/hotkeys.
    *   **Log Custom Messages:** Action to write to logs.
    *   Use captured variables to make action parameters dynamic.
*   **Performance Optimization:** Selective analysis ensures only necessary computations are performed during bot runtime.
*   **Interfaces:**
    *   **Command-Line Interface (CLI):** For running bots and launching GUI tools.
    *   **Full GUI Profile Editor (v3.0.0 - In Progress):** Comprehensive `CustomTkinter`-based GUI for creating, editing, and managing all aspects of profiles (settings, regions, templates, rules with all parameters and structures, including input validation).
    *   **Simple Region Selector GUI:** A focused tool for graphically defining screen regions.
*   **Comprehensive Logging:** Detailed, persistent, and configurable logs for diagnostics and monitoring.

## How it Works

1.  **Configuration (via GUI Editor or JSON):** You define automation tasks in a JSON "profile" file. This profile specifies:
    *   `settings`: Global parameters like monitoring interval, `analysis_dominant_colors_k`.
    *   `regions`: Areas of the screen to monitor (name, x, y, width, height).
    *   `templates`: Definitions for template matching (name, relative filename). Template images are stored in a `templates/` subdirectory next to the profile by the GUI.
    *   `rules`: A list of conditions to check and actions to perform. Each rule links visual conditions (single or compound, with parameters like OCR confidence, variable captures) in a region to specific actions (which can use captured variables).
2.  **Bot Runtime (`run` command):**
    *   The bot loads the specified profile.
    *   It enters a continuous loop (threaded for CLI responsiveness).
    *   **Capture:** Captures images of all defined regions.
    *   **Selective Analysis:** Performs only those general analyses (OCR, dominant color, average color) on each region that are required by active rules.
    *   **Rule Evaluation:** Iterates through rules. For each rule:
        *   Creates a temporary variable context.
        *   Evaluates its condition (single or compound), substituting any variable placeholders.
        *   Performs on-demand analyses (pixel color, template match) if needed.
        *   Captures specified values into variables if conditions are met.
    *   **Action:** If a rule's condition is true, its action parameters are processed for variable substitution, and the action is executed.
3.  **Profile Editing (GUI - `edit` command):**
    *   Launches the `MainAppWindow`.
    *   Allows users to create new profiles or open existing ones.
    *   Provides a visual interface to manage all profile components: settings, regions (including graphical selection), templates (including image preview and file management), and rules (including condition types, parameters, compound logic, sub-conditions, action types, and action parameters).
    *   Includes input validation and feedback.
    *   Saves changes back to the JSON profile file.

## Technology Stack

*   **Language:** Python 3.9+
*   **Screen Capture:** Pillow (`ImageGrab`), OpenCV-Python
*   **Image Processing/Analysis:** OpenCV-Python, NumPy, Pillow
*   **OCR:** Tesseract OCR via `pytesseract`
*   **Input Simulation:** `pyautogui`
*   **GUI:** `CustomTkinter`
*   **Configuration:** JSON
*   **CLI:** `argparse`
*   **Environment Management:** `python-dotenv`
*   **Logging:** Python `logging` module
*   **Concurrency (Bot Runtime):** `threading`

## Setup Instructions

### Prerequisites

*   **Python:** Version 3.9 or newer.
*   **Tesseract OCR Engine:** **Required for OCR features.**
    *   **Windows:** Download and run the installer from [UB Mannheim Tesseract releases](https://github.com/UB-Mannheim/tesseract/wiki).
        *   **Important:** During installation, ensure you select to "Add Tesseract to system PATH" or manually add the Tesseract installation directory (e.g., `C:\Program Files\Tesseract-OCR`) to your system's `PATH` environment variable.
        *   Install language data packs (e.g., `eng` for English) with Tesseract.
    *   **macOS:** `brew install tesseract tesseract-lang`
    *   **Linux (Debian/Ubuntu):** `sudo apt-get install tesseract-ocr tesseract-ocr-all`
    *   Verify Tesseract by typing `tesseract --version` in a terminal.
*   **Pip:** Python package installer.
*   **Git:** For cloning the repository (if applicable).

### Installation

1.  **Clone/Download:** Obtain the project files.
    ```bash
    # If cloning:
    # git clone <repository_url>
    # cd py-pixel-bot 
    ```
    Navigate to the project's root directory.

2.  **Virtual Environment (Recommended):**
    ```bash
    python -m venv .venv
    ```
    *   Windows: `.venv\Scripts\activate`
    *   macOS/Linux: `source .venv/bin/activate`

3.  **Install Dependencies:**
    Ensure you have a `requirements.txt` file in the project root (as provided in the sync output). Then run:
    ```bash
    pip install -r requirements.txt
    ```

### Environment Configuration

1.  Create a file named `.env` in the project root.
2.  Add for local development: `APP_ENV=development`
    *   This controls logging verbosity. Other values: `uat`, `production`.
    *   The `.env` file should be in your `.gitignore`.

### PYTHONPATH Configuration

The application is designed to be run as a module from the project root directory (e.g., `python -m py_pixel_bot ...`). The `src/__main__.py` script attempts to correctly adjust `sys.path` so that modules within `src/py_pixel_bot/` can be imported.

*   **Primary Method:** Run from the project's root directory:
    ```bash
    # (ensure virtual env is active)
    python -m py_pixel_bot --help 
    ```
*   **If `ModuleNotFoundError` occurs:** This usually means Python cannot find the `py_pixel_bot` package.
    *   Ensure your current working directory IS the project root (`py-pixel-bot/`).
    *   Alternatively, you can explicitly set the `PYTHONPATH` environment variable to include the `src` directory. The project root (parent of `src`) is usually added to `sys.path` when running with `python -m`.

## Usage (CLI)

Ensure your virtual environment is activated. All commands are typically run from the project's root directory.

```bash
python -m py_pixel_bot <command> [options]
```

### Running a Bot Profile

Starts the bot's monitoring and action loop using a specified profile.
```bash
python -m py_pixel_bot run <profile_name_or_path> [-v | -vv]
```
*   `<profile_name_or_path>`: Name (e.g., `example_profile` looks for `profiles/example_profile.json`) or full/relative path.
*   `-v`: INFO level console logging.
*   `-vv`: DEBUG level console logging.
Press `Ctrl+C` to stop the bot.

### Adding/Updating a Region (Simple GUI Tool)

Launches a simple GUI tool to draw/name a screen region and save/update it in a profile.
```bash
python -m py_pixel_bot add-region <profile_name_or_path>
```
The profile will be created if it doesn't exist by the `ConfigManager` used by the tool.

### Editing a Profile (Full GUI Editor)

Launches the comprehensive GUI Profile Editor.
```bash
python -m py_pixel_bot edit [profile_name_or_path]
```
*   `[profile_name_or_path]`: (Optional) If provided, loads this profile on startup. Otherwise, starts with a new, unsaved profile.

## Configuration Profiles (.json)

Bot behavior is defined in JSON files (typically in `profiles/`). Template images for a profile should be placed in a `templates/` subdirectory next to that profile's JSON file (e.g., `profiles/my_bot_profile_dir/templates/icon.png` if profile is `profiles/my_bot_profile_dir/my_bot_profile.json`). The GUI's "Add Template" feature handles copying selected images to this location.

### Structure Overview

A profile contains:
*   `profile_description` (string)
*   `settings` (object): e.g., `monitoring_interval_seconds`, `analysis_dominant_colors_k`.
*   `regions` (array of objects): `name`, `x`, `y`, `width`, `height`.
*   `templates` (array of objects): `name`, `filename` (relative path within the profile's `templates/` dir).
*   `rules` (array of objects):
    *   `name` (string)
    *   `region` (string, default region for conditions)
    *   `condition` (object):
        *   Single: `{"type": "...", param: val, "capture_as": "var"}`
        *   Compound: `{"logical_operator": "AND"|"OR", "sub_conditions": [array_of_single_conditions]}`
    *   `action` (object): `{"type": "...", param: val}` (params can use `{var}` for substitution).

See `TECHNICAL_DESIGN.MD` and example profiles in the `profiles/` directory for full schema details.

### Example Profiles

The `profiles/` directory contains examples. Note that profiles using template matching (e.g., `line_messenger_abc.json`) require you to create the referenced `.png` template images and place them in a `templates/` subdirectory next to the respective profile file for them to work. The GUI editor helps manage this.

## Logging

*   Logs are written to the `logs/` directory in the project root (e.g., `YYYY-MM-DD.log`). This directory is created if it doesn't exist.
*   Verbosity is controlled by `APP_ENV` in `.env` and CLI flags (`-v`, `-vv` for console).
    *   `development`: DEBUG to console and file.
    *   `uat`/`production`: INFO to console (or WARNING) and file.
*   Comprehensive logging is crucial for debugging and understanding bot/GUI behavior.

## Development

*   See `docs/DEV_CONFIG.MD` for development choices.
*   ADRs (Architectural Decision Records) are in `docs/adrs/`.
*   Key design documents: `docs/TECHNICAL_DESIGN.MD`, `docs/FEATURE_ROADMAP.MD`.

## Contributing (Future)

Contribution guidelines will be added if the project is opened for wider collaboration.

## License

This project is intended to be licensed under a permissive open-source license like MIT (a `LICENSE.MD` file will be formally added). It utilizes third-party libraries which have their own licenses (e.g., OpenCV, CustomTkinter, Pillow, PyAutoGUI, Pytesseract, python-dotenv). Please refer to their respective documentation for specific license details. The NumPy `random` component included in the initially provided consolidated sources has its own dual NCSA/3-Clause BSD license, though the direct usage of this specific sub-component by PyPixelBot might be minimal or indirect via OpenCV/NumPy main usage.