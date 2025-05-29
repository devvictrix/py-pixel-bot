# Mark-I: AI-Powered Visual Automation Tool

**Version: 4.0.0 (Gemini-Powered Visual Intelligence)**

Mark-I is a Python-based desktop automation tool designed to "see" specific regions of your screen, "think" about what it sees using local analysis and advanced AI (Google Gemini), and then "act" by simulating mouse and keyboard inputs. It aims to automate tasks that might be difficult with traditional selectors by relying on visual cues and, with v4.0.0, natural language commands and AI-driven decision-making.

![Conceptual Diagram of Mark-I (Placeholder - A diagram showing See -> Think (Local + AI) -> Act would be great here)]

## Core Capabilities

*   **Targeted Screen Monitoring:** Define specific rectangular regions on your screen for Mark-I to watch.
*   **Versatile Visual Analysis (The "Think" Step):**
    *   **Local Analysis:**
        *   Pixel color checks (specific or average color of a region).
        *   Template matching (find images within regions).
        *   Optical Character Recognition (OCR) to extract text.
        *   Dominant color analysis.
    *   **AI-Powered Analysis with Google Gemini (v4.0.0+):**
        *   **Visual Querying (`gemini_vision_query`):** Ask Gemini questions about a screen region (e.g., "Is there a red button?", "What text is on this label?").
        *   **Element Identification & Bounding Boxes:** Prompt Gemini to find specific UI elements and return their bounding box coordinates for precise interaction.
        *   **Goal-Driven Action Selection (`gemini_perform_task` - Phase 2 logic):** Give Mark-I a simple goal for a visual context, and it uses Gemini to decide on an appropriate action from a predefined set (e.g., "Click the button described as 'Continue'").
        *   **Natural Language Command Interface (`gemini_perform_task` - Phase 3 logic):** Issue higher-level commands in natural language (e.g., "Find the search bar, type 'Mark-I automation', and press enter"). Mark-I uses Gemini for NLU, decomposes the command into steps, and orchestrates execution.
*   **Flexible Action Execution (The "Act" Step):**
    *   Mouse clicks (left, right, middle, single/multiple) targeted at:
        *   Absolute coordinates.
        *   Region centers or relative offsets.
        *   Centers of matched templates.
        *   **Centers/corners of elements identified by Gemini via bounding boxes.**
    *   Keyboard input (typing text, pressing special keys, hotkeys).
    *   Dynamic actions using variables captured from analysis results.
*   **Powerful Configuration:**
    *   **Comprehensive GUI Editor:** A user-friendly interface (`MainAppWindow`) to create and manage all aspects of automation profiles:
        *   Visually define screen regions.
        *   Manage template images.
        *   Build complex rules with single or compound conditions (including all Gemini condition/task types).
        *   Configure actions with dynamic parameters.
        *   Set bot operational parameters.
    *   **JSON Profiles:** Human-readable (and editable) JSON files store all configurations.
    *   **CLI Control:** Run bots and launch the editor from the command line.
*   **Robust Operation:**
    *   Threaded monitoring loop for non-blocking operation.
    *   Detailed and configurable logging.

## Key Use Cases

*   **Gaming Automation:** Automate repetitive tasks based on visual cues (health bars, icons, text), click dynamic UI elements identified by Gemini, respond to game events.
*   **Application Interaction (especially for apps lacking APIs):** Automate data entry, button clicks, and monitoring in legacy or third-party applications by identifying elements visually or semantically.
*   **Software Testing & Visual Validation:** Verify UI elements, text, and colors; automate UI interaction steps. Gemini's understanding can make tests more robust to minor UI changes.
*   **Web Automation (for dynamic content):** Interact with websites where traditional selectors are brittle.
*   **General Repetitive Task Automation:** Monitor screens for events, automate responses to dialogs, extract data.
*   **Productivity Enhancement:** Create custom workflows that bridge different applications based on visual triggers and natural language commands.

## What's New in v4.0.0 (Gemini-Powered Visual Intelligence)

Version 4.0.0 introduces a major leap in Mark-I's intelligence by integrating Google's Gemini models:

1.  **`gemini_vision_query` Condition:** Directly ask Gemini questions about a screen region's content within your automation rules.
2.  **Actions on Gemini-Identified Elements:** Click or interact with UI elements precisely based on bounding boxes returned by Gemini.
3.  **`gemini_perform_task` Action Type:**
    *   **Goal-Driven Single Actions:** Provide a simple goal (e.g., "click the submit button"), and Mark-I uses Gemini to identify the target and execute the action.
    *   **Natural Language Command Interface:** Issue complex, multi-step commands in plain English (e.g., "If the status is 'Ready', find the 'Export' button and click it, then type 'report.pdf' and press enter."). Mark-I uses Gemini to understand, decompose, and execute these commands.

This allows for more resilient, flexible, and powerful automations that can better handle UI variations and understand user intent more deeply.

## Setup & Installation

1.  **Prerequisites:**
    *   Python 3.9+
    *   Tesseract OCR Engine:
        *   Install Tesseract OCR from the official source for your OS.
        *   **Crucially, ensure the Tesseract installation directory (containing `tesseract.exe` on Windows) is added to your system's PATH environment variable.** Mark-I (via `pytesseract`) needs this to find the engine.
2.  **Clone the Repository (if applicable) or Download Files:**
    ```bash
    # git clone [repository_url]
    # cd mark-i
    ```
3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv .venv
    # Activate it:
    # Windows: .venv\Scripts\activate
    # macOS/Linux: source .venv/bin/activate
    ```
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This will install `opencv-python`, `Pillow`, `pyautogui`, `pytesseract`, `python-dotenv`, `CustomTkinter`, and crucially for v4.0.0, `google-generativeai`.

5.  **Google Gemini API Key Setup (CRITICAL for v4.0.0 features):**
    *   You need a Google Gemini API key. Obtain one from [Google AI Studio](https://aistudio.google.com/app/apikey) or your Google Cloud Project.
    *   Create a file named `.env` in the root directory of the Mark-I project (the same directory where `FEATURE_ROADMAP.MD` is).
    *   Add your API key to this `.env` file like this:
        ```env
        GEMINI_API_KEY=YOUR_ACTUAL_API_KEY_HERE
        ```
    *   **Important:** The `.env` file should be (and is by default in the project's `.gitignore`) excluded from version control to keep your API key private.
    *   You can also set `APP_ENV=development` in your `.env` file for more verbose logging during development/testing:
        ```env
        APP_ENV=development
        GEMINI_API_KEY=YOUR_ACTUAL_API_KEY_HERE
        ```

## Running Mark-I

Mark-I is primarily controlled via its Command Line Interface (CLI) for running bots and launching the GUI editor.

**Main Commands:**

*   **Edit a Profile (GUI):**
    ```bash
    python -m mark_i edit [path_to_your_profile.json]
    ```
    If `path_to_your_profile.json` is omitted, a new, unsaved profile editor will open. This is the primary way to create and configure your automation profiles.
*   **Run a Profile (Bot Execution):**
    ```bash
    python -m mark_i run path_to_your_profile.json
    ```
    This will load the specified profile and start the bot's monitoring and action loop. Press `Ctrl+C` in the terminal to stop the bot.
*   **Add/Edit a Region (Legacy GUI Tool - use the full editor for most tasks):**
    ```bash
    python -m mark_i add-region path_to_your_profile.json
    ```

**CLI Options:**

*   `-v` or `--verbose`: Increase console logging to DEBUG level.
*   `--log-file path/to/custom.log`: Specify a custom log file path for the session.
*   `--no-file-logging`: Disable file logging for the session.

## Creating Automation Profiles (via GUI Editor)

The GUI editor (`python -m mark_i edit`) is the recommended way to build your automations. Here's a conceptual overview:

1.  **Profile Settings:**
    *   **Description:** Describe what your bot does.
    *   **Monitoring Interval (s):** How often Mark-I captures and analyzes the screen (e.g., `0.5` for twice a second). Be mindful of Gemini API latency for very short intervals if using AI features frequently.
    *   **Analysis - Dominant K:** For dominant color analysis, how many top colors to find.
    *   **Gemini Default Model (v4.0.0+):** Set a default Gemini model (e.g., `gemini-1.5-flash-latest`, `gemini-1.5-pro-latest`) to be used for Gemini conditions/tasks unless overridden in a specific rule.
    *   **Gemini API Key Status:** Shows if the API key is loaded from `.env`.

2.  **Regions:**
    *   Define named rectangular areas on the screen that Mark-I should monitor. Use the "Add" button which launches a visual region selector tool.
    *   Each region has an (x, y, width, height).

3.  **Templates (Optional):**
    *   Add template images (PNG, JPG) if you need to use template matching conditions.
    *   Store template images in a `templates/` subdirectory next to your profile JSON file. The GUI helps manage this.

4.  **Rules:** This is the core logic. Each rule has:
    *   **Name:** A unique name for the rule.
    *   **Default Region:** The screen region this rule primarily applies to (can be overridden in specific conditions).
    *   **Condition:** What Mark-I needs to "see" or "think" for the rule to trigger.
        *   **Single Condition:** e.g., `pixel_color`, `average_color_is`, `template_match_found`, `ocr_contains_text`, `dominant_color_matches`, `always_true`.
        *   **`gemini_vision_query` (v4.0.0+):** Ask a natural language question about the region, optionally checking the response or extracting JSON.
            *   **Prompt:** Your question/instruction to Gemini.
            *   **Expected Response Contains:** Keywords to check for in Gemini's text output.
            *   **JSON Path / Value:** Check specific values if Gemini returns JSON.
            *   **Capture As:** Store Gemini's response (text, full JSON, or extracted JSON value) in a variable.
            *   **Model Override:** Use a specific Gemini model for this query.
        *   **Compound Condition:** Combine multiple sub-conditions with `AND` or `OR`.
    *   **Action:** What Mark-I should do if the condition is met.
        *   **Types:** `click`, `type_text`, `press_key`, `log_message`.
        *   **`gemini_perform_task` (v4.0.0 Phase 2 & 3):** This powerful action type delegates a task to the `GeminiDecisionModule`.
            *   **Natural Language Command (Phase 3):** The primary input. You type what you want Mark-I to do (e.g., "Find the save icon and click it, then type 'backup' and press enter.").
            *   **Context Regions (CSV):** Comma-separated list of region names to provide as visual context for the NLU command. If empty, uses the rule's default region.
            *   **Allowed Sub-Actions (CSV - Optional):** Restrict the types of primitive actions Gemini can suggest for the decomposed steps of your NLU command (e.g., only allow `CLICK_DESCRIBED_ELEMENT`). Values from `GEMINI_TASK_ALLOWED_ACTION_TYPES_FOR_UI` in `gui_config.py`.
            *   **Confirm Each Gemini Step:** (Checkbox, default True for safety) Ask for user confirmation before executing each AI-decided sub-step of an NLU command.
            *   **Max Task Steps:** Limit how many steps an NLU command can be decomposed into.
            *   **Pause Before Task:** Standard pause before starting the NLU task.
        *   **Parameters:** Actions have specific parameters (e.g., coordinates for click, text for type). These can use `{variables}` captured by conditions.
            *   For `click` actions, `target_relation` can be `center_of_gemini_element` to click based on Gemini's bounding box output (use with a `gemini_vision_query` that captures box data).

## Example: Natural Language Command with `gemini_perform_task`

Imagine a rule:

*   **Name:** "Save And Close Notepad via NLU"
*   **Region:** (e.g., "notepad_window_area" - providing overall context)
*   **Condition:** `always_true` (or some trigger)
*   **Action:**
    *   **Type:** `gemini_perform_task`
    *   **Natural Language Command:** "Click the File menu, then click the Save option. After that, find the close button (usually an X at the top right) and click it."
    *   **Context Regions (CSV):** `notepad_window_area`
    *   **Confirm Each Gemini Step:** `True` (checked)
    *   **Allowed Sub-Actions (CSV):** `CLICK_DESCRIBED_ELEMENT, PRESS_KEY_SIMPLE` (to allow for potential Alt+F, S, etc.)

When this rule triggers, Mark-I will:
1.  Send "Click the File menu..." and an image of `notepad_window_area` to Gemini for NLU and decomposition.
2.  Gemini might respond with a plan like:
    1.  Step 1: Intent=CLICK, Target="File menu"
    2.  Step 2: Intent=CLICK, Target="Save option"
    3.  Step 3: Intent=FIND, Target="close button (X top right)"
    4.  Step 4: Intent=CLICK, Target="close button (X top right)"
3.  For each step, Mark-I's `GeminiDecisionModule` will:
    a.  Ask Gemini (Vision) to find "File menu" in the current screen context, get its bounding box.
    b.  Ask you to confirm: "AI proposes to click 'File menu'. Proceed?"
    c.  If yes, click it.
    d.  Then for "Save option", and so on.

## Important Considerations for Gemini Features

*   **Prompt Quality is Key:** The effectiveness of `gemini_vision_query` and especially `gemini_perform_task` (NLU) heavily depends on how clearly and specifically you write your prompts/commands.
*   **Latency:** Gemini API calls take time (seconds). Design your automation flows accordingly. High-frequency loops with many Gemini calls per cycle will be slow.
*   **Cost:** Gemini API usage is typically billed by Google. Be mindful of your usage.
*   **Non-Determinism:** LLMs can sometimes give slightly different answers or interpretations even for the same input. Robust error handling and clear feedback are important. Start with simple, well-defined tasks for NLU.
*   **Safety:** For `gemini_perform_task`, use the "Confirm Each Gemini Step" option, especially when starting. Carefully review the `PREDEFINED_ALLOWED_SUB_ACTIONS` that the NLU can decompose tasks into – these are designed to be simple and relatively safe UI interactions.

## Development Status & Future

*   **v4.0.0 is complete**, featuring the core Gemini integrations described.
*   Future development may include:
    *   More advanced agent-like behaviors and planning.
    *   Enhanced state management for complex tasks.
    *   Fuzzy template matching, motion detection.
    *   See `FEATURE_ROADMAP.MD` for more.

## Contributing & License
*(To be added - Placeholder for contribution guidelines and license information)*