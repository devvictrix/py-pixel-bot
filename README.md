# Mark-I: AI-Powered Visual Desktop Automation Tool

**Version: 5.0.0 (AI-Driven Profile Generation) - STABLE**

Mark-I (inspired by Tony Stark's pioneering suit, with the long-term vision of evolving into a "J.A.R.V.I.S."-like assistant) is a Python-based desktop automation tool. It is designed to capture and analyze specific regions of your screen in real-time, extract information using both local computer vision techniques and advanced AI (Google Gemini), and then perform actions (mouse clicks, keyboard inputs, logging) based on a configurable rules engine or natural language commands.

Mark-I aims to provide a powerful, flexible, and user-friendly solution for automating tasks on the Windows desktop (with cross-platform considerations for core functionalities). It particularly shines in scenarios involving dynamic or non-standard UI elements where traditional automation selectors might falter.

## Key Features (v5.0.0)

*   **Targeted Screen Capture:** Reliably capture image data from user-defined screen areas.
*   **Advanced Local Visual Analysis:**
    *   Pixel/average color detection.
    *   Template (image) matching.
    *   Optical Character Recognition (OCR) via Tesseract.
    *   Dominant color analysis.
*   **AI-Powered Visual Understanding & Interaction (Google Gemini - v4.0.0 capabilities):**
    *   Semantic visual querying (`gemini_vision_query`): Ask questions about screen regions.
    *   Precise interaction with AI-identified elements using bounding boxes.
    *   Natural Language Command Execution (`gemini_perform_task`): Execute tasks described in natural language, with AI decomposing them into steps.
*   **AI-Driven Profile Generation (New in v5.0.0):**
    *   **Goal-to-Plan:** Translate a high-level user automation goal (natural language) into a structured plan of sub-steps using AI.
    *   **Interactive AI-Assisted Profile Creation:** A GUI wizard guides users through implementing the plan, with AI suggestions for:
        *   Relevant screen regions.
        *   Condition and action logic.
        *   Visual identification of target UI elements.
    *   Automated assembly of a standard Mark-I JSON profile.
*   **Flexible Conditional Action Execution:**
    *   Sophisticated rules engine supporting single or compound (AND/OR) conditions.
    *   Rule-scoped variable capture and use in actions.
*   **User-Friendly Configuration:**
    *   **Manual GUI Editor (`MainAppWindow`):** Comprehensive GUI for creating and managing all aspects of profiles, including regions, templates, and complex rules.
    *   **AI Profile Creator Wizard (`ProfileCreationWizardWindow`):** New intuitive GUI for the AI-driven profile generation workflow.
*   **CLI Control:** For running profiles and launching GUI tools.
*   **Performant and Reliable Bot Runtime:** Threaded monitoring loop, selective analysis, robust error handling, and detailed logging.

## Technology Stack

*   **Language:** Python (3.9+)
*   **AI Model Interaction:** `google-generativeai` (for Google Gemini API)
*   **Local CV/OCR:** `OpenCV-Python`, `NumPy`, `Pillow`, `pytesseract`
*   **GUI:** `CustomTkinter`
*   **Core Automation & System:** `pyautogui`, `json`, `argparse`, `threading`, `python-dotenv`, `logging`

## Setup and Installation

1.  **Clone the repository (if applicable) or ensure all project files are present.**
2.  **Python:** Ensure Python 3.9+ is installed and added to your system's PATH.
3.  **Virtual Environment (Recommended):**
    ```bash
    python -m venv .venv
    # On Windows
    .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Tesseract OCR Engine (Required for OCR features):**
    *   Install Tesseract OCR for your operating system.
    *   Ensure the Tesseract installation directory (containing `tesseract.exe` on Windows) is added to your system's PATH.
    *   Alternatively, you can specify the full path to `tesseract.exe` in a profile's settings via the GUI (`Settings > Tesseract CMD Path`).
6.  **Environment Variables (`.env` file):**
    *   Create a file named `.env` in the project root directory (next to `README.MD`).
    *   Add the following, replacing `your_api_key_here` with your actual key:
        ```env
        APP_ENV=development
        GEMINI_API_KEY=your_api_key_here
        ```
    *   `APP_ENV`: Set to `development` for verbose logging, or `production` for less.
    *   `GEMINI_API_KEY`: **Required** for all AI-powered features (v4.0.0 vision queries, NLU tasks, and v5.0.0 AI Profile Generation). Obtain this key from [Google AI Studio](https://aistudio.google.com/app/apikey) or your Google Cloud Console.
    *   **Important:** The `.env` file should be added to your `.gitignore` if you are using Git, to prevent committing your API key.

## Usage

### Command-Line Interface (CLI)

Mark-I can be controlled via the command line:

*   **Run a profile:**
    ```bash
    python -m mark_i run <profile_name_or_path>
    # Example: python -m mark_i run profiles/example_profile.json
    # Example: python -m mark_i run my_bot (if my_bot.json is in profiles/)
    ```
*   **Edit or create a profile with the GUI:**
    ```bash
    python -m mark_i edit [profile_name_or_path]
    # Example (edit existing): python -m mark_i edit profiles/example_profile.json
    # Example (create new, or open 'my_new_bot' if it exists, or suggest name): python -m mark_i edit my_new_bot
    # Example (open GUI for a completely new, unnamed profile): python -m mark_i edit
    ```
    The `edit` command launches the `MainAppWindow`, where you can manually create/edit profiles or launch the AI Profile Creator wizard ("File > New AI-Generated Profile...").

*   **General CLI options:**
    *   `-v` or `--verbose`: Increase console logging to DEBUG level.
    *   `--log-file <path>`: Specify a custom log file path for the session.
    *   `--no-file-logging`: Disable file logging for the session.

    Run `python -m mark_i --help` for a full list of commands and options.

### Graphical User Interface (GUI)

*   **Main Profile Editor (`MainAppWindow`):** Launched via `mark_i edit`. Provides comprehensive tools to manually:
    *   Manage profile settings (description, monitoring interval, Tesseract paths, Gemini model).
    *   Define and edit screen regions (using a visual selector).
    *   Add and manage template images.
    *   Create and configure complex automation rules (conditions, actions, including Gemini-powered ones).
*   **AI Profile Creator Wizard (`ProfileCreationWizardWindow`):** Launched from `MainAppWindow` ("File > New AI-Generated Profile...").
    *   Guides you through creating an automation profile by stating a high-level goal.
    *   Uses AI to suggest a plan, screen regions, conditions, and actions.
    *   Allows interactive refinement and template capture.

## Configuration

*   Bot configurations (profiles) are stored as **JSON files** (e.g., `my_profile.json`).
*   By default, profiles are expected in a `profiles/` directory within the project root.
*   Templates associated with a profile should be stored in a `templates/` subdirectory next to their respective profile JSON file (e.g., `profiles/my_profile_templates/icon.png` for `profiles/my_profile.json`). The GUI and `ConfigManager` handle this structure.
*   Example profiles are provided in the `profiles/` directory.

## AI Integration (Google Gemini)

*   **v4.0.0 Runtime AI:**
    *   `gemini_vision_query`: Allows rules to ask Gemini questions about screen regions.
    *   `gemini_perform_task`: Enables the bot to execute tasks based on natural language commands, using Gemini for NLU and visual refinement.
*   **v5.0.0 Design-Time AI (Profile Creation):**
    *   The AI Profile Creator wizard uses Gemini to:
        *   Translate user goals into automation plans.
        *   Suggest relevant screen regions for plan steps.
        *   Suggest Mark-I condition/action logic.
        *   Visually refine target UI elements.
*   **API Key:** A `GEMINI_API_KEY` (see Setup) is **mandatory** for all Gemini-powered features. Users are responsible for managing API usage and associated costs.

## Documentation

Detailed technical design, architectural decisions, and requirements are available in the `docs/` directory:

*   `PROJECT_OVERVIEW.MD`: High-level vision and goals.
*   `TECHNICAL_DESIGN.MD`: System architecture and component details.
*   `FEATURE_ROADMAP.MD`: Feature planning and status.
*   `adrs/`: Architectural Decision Records.
*   ... and other relevant documents.

## Contributing

(Placeholder - Contributions are welcome! Please refer to `CONTRIBUTING.MD` if available, or open an issue to discuss potential changes.)

## License

(Placeholder - Specify project license, e.g., MIT, Apache 2.0. If not specified, assume proprietary.)