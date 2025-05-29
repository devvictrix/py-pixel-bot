# PyPixelBot - Visual Desktop Automation Tool (v4.0.0 - Gemini Integration In Progress)

PyPixelBot is a Python-based desktop automation tool designed to capture and analyze specific regions of the screen in real-time. It extracts visual information and performs actions based on a configurable rules engine. With v4.0.0, it integrates Google Gemini for AI-powered visual understanding.

**Project Status:** Actively under development. Core features up to v3.0.0 (Enhanced GUI) are complete. Version 4.0.0 (Gemini Integration) is the current focus.

## Core Features

*   **Targeted Screen Capture:** Define and capture specific rectangular areas of your screen.
*   **Local Visual Analysis:**
    *   Pixel and average color detection.
    *   Template (image pattern) matching.
    *   Optical Character Recognition (OCR) for text extraction.
    *   Dominant color analysis.
*   **AI-Powered Visual Analysis (v4.0.0+):**
    *   Leverage Google Gemini API for semantic scene description, element identification, and question-answering about visual content.
    *   Create rules based on Gemini's interpretations.
*   **Flexible Rules Engine:**
    *   Define rules with single or compound (AND/OR) conditions.
    *   Trigger actions (mouse clicks, keyboard input, logging) based on analysis results.
    *   Capture analysis results (including from Gemini) into variables for use in actions.
*   **Comprehensive GUI Profile Editor:**
    *   User-friendly interface to create, edit, and manage bot profiles.
    *   Visually define regions, manage templates, and build complex rules (including Gemini conditions).
*   **CLI for Bot Execution:** Run configured profiles from the command line.

## Getting Started (High-Level Overview - Detailed Guide Coming Soon)

### Prerequisites

1.  **Python:** Version 3.9+ recommended.
2.  **Tesseract OCR Engine:**
    *   Required for local OCR functionality.
    *   Must be installed on your system and its executable (`tesseract.exe` on Windows) typically needs to be in your system's PATH.
    *   Download from: [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
3.  **Google Gemini API Key (for v4.0.0+ features):**
    *   To use AI-powered visual analysis features, you need a Google Gemini API key.
    *   Obtain a key from [Google AI Studio](https://aistudio.google.com/app/apikey) or your Google Cloud project.
    *   **Important:** This is a paid service from Google. Be aware of potential costs associated with API usage.

### Installation

1.  **Clone the repository (if applicable) or download the source code.**
    ```bash
    # git clone <repository_url>
    # cd py-pixel-bot
    ```
2.  **Create and activate a Python virtual environment:**
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # macOS/Linux
    # source .venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up Environment Variables:**
    *   Create a file named `.env` in the project root directory (e.g., alongside `README.md`).
    *   Add the following lines to your `.env` file:
        ```dotenv
        APP_ENV=development

        # For Gemini features (v4.0.0+) - REQUIRED
        GEMINI_API_KEY=your_actual_gemini_api_key_here
        ```
    *   Replace `your_actual_gemini_api_key_here` with your Gemini API key.
    *   **Security:** The `.env` file contains sensitive information and should **NOT** be committed to version control. Ensure it's listed in your `.gitignore` file.

### Running PyPixelBot

*   **Open the Profile Editor GUI:**
    ```bash
    python -m mark_i edit [optional_profile_path.json]
    ```
    If no profile path is provided, a new, unsaved profile editor will open.
*   **Run a Bot Profile (CLI):**
    ```bash
    python -m mark_i run path/to/your/profile.json
    ```
*   **Get Help:**
    ```bash
    python -m mark_i --help
    ```

## Configuration Profiles

PyPixelBot uses JSON files to store bot configurations (profiles). These profiles define:
*   General settings (monitoring interval, default Gemini model, etc.).
*   Screen regions to monitor.
*   Template images for matching.
*   Rules that link analysis outcomes to actions.

The GUI (`MainAppWindow`) is the primary tool for creating and editing these profiles.

## Using Gemini Vision Query Conditions (v4.0.0+)

The `gemini_vision_query` condition type allows you to send an image of a screen region to the Google Gemini API with a text prompt. The bot can then act based on Gemini's response.

**Key Parameters in the GUI/JSON:**

*   **`prompt`**: Your question or instruction to Gemini about the image (e.g., "Is the 'Submit' button active?", "Describe the icon in the top-right corner.", "What is the status shown in this dialog box?").
*   **`expected_response_contains`**: (Optional) Keywords (comma-separated for OR logic) that must be present in Gemini's text response for the condition to be true.
*   **`case_sensitive_response_check`**: (Optional) Whether the keyword check is case-sensitive.
*   **`expected_response_json_path`**: (Optional) A basic dot-notation path (e.g., `data.status.message`) to extract a value if Gemini returns JSON.
*   **`expected_json_value`**: (Optional) The string value expected at the `expected_response_json_path`.
*   **`capture_as`**: (Optional) A variable name to store Gemini's text response or the extracted JSON value. This variable can then be used in action parameters.
*   **`model_name`**: (Optional) Override the default Gemini model specified in the profile settings.
*   **`region`**: (Optional) Override the rule's default region for this specific Gemini query.

**Important Considerations for Gemini:**

*   **API Key:** A valid `GEMINI_API_KEY` must be in your `.env` file.
*   **Cost:** Gemini API usage incurs costs. Monitor your Google Cloud billing.
*   **Latency:** API calls add latency (seconds) to rule evaluation. Adjust your bot's `monitoring_interval_seconds` accordingly.
*   **Internet:** An active internet connection is required.
*   **Privacy:** Image data from regions analyzed by Gemini conditions is sent to Google servers.
*   **Prompt Engineering:** The quality of Gemini's responses heavily depends on how well you write your prompts. Experimentation is key.

## Documentation

Detailed documentation is under development and will be available in the `docs/` directory:
*   `TECHNICAL_DESIGN.MD`: For architectural details.
*   `FUNCTIONAL_REQUIREMENTS.MD` & `NON_FUNCTIONAL_REQUIREMENTS.MD`: For system specifications.
*   ADRs (`docs/adrs/`): For key design decisions.
*   More user-focused guides coming soon.

## Contributing

(Contribution guidelines will be added later.)

## License

(License information will be added later.)