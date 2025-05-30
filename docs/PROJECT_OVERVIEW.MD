# Project Overview: Mark-I

## 1. Purpose

This project, **Mark-I** (inspired by Tony Stark's pioneering suit, with the long-term vision of evolving into a "J.A.R.V.I.S."-like assistant), is a Python-based desktop automation tool. It is designed to **capture and analyze specific regions of your screen in real-time**, extract information using both local computer vision techniques and advanced AI (Google Gemini), and then perform actions (mouse clicks, keyboard inputs, logging) based on a configurable rules engine or natural language commands.

Mark-I aims to provide a powerful, flexible, and user-friendly solution for automating tasks on the Windows desktop (with cross-platform considerations for core functionalities). It particularly shines in scenarios involving dynamic or non-standard UI elements where traditional automation selectors might falter.

**With v4.0.0, Mark-I significantly advanced its AI capabilities, enabling it to understand visual context more deeply and execute tasks based on natural language commands.**

**The vision for v5.0.0 is to further empower users by leveraging AI to assist in the _creation_ of automation profiles themselves, transforming high-level goals into executable Mark-I configurations.**

## 2. Vision

To create **Mark-I**, a precise, efficient, and highly intelligent visual automation tool that empowers users to automate a wide array of desktop tasks with increasing ease and sophistication. Mark-I distinguishes itself by focusing on visual cues and semantic understanding of screen content, augmented by cutting-edge AI.

- **Core v4.0.0 Achievement:** Evolved Mark-I into an intelligent assistant capable of:

  - Answering complex questions about screen regions (`gemini_vision_query`).
  - Identifying and precisely interacting with UI elements based on textual descriptions and visual context (bounding box actions).
  - Executing tasks based on simple goals provided by the user (`gemini_perform_task` - goal-driven).
  - Interpreting and acting upon natural language commands, decomposing them into executable steps (`gemini_perform_task` - NLU-driven).

- **Aspiration for v5.0.0 (AI-Driven Profile Generation):** To further reduce the manual effort in creating automations by enabling Mark-I to:
  - Understand a user's high-level automation goal expressed in natural language.
  - Generate a strategic plan of action using AI.
  - Interactively guide the user, with AI-powered suggestions for regions, conditions, and actions, to build a complete Mark-I profile from this plan.

The ultimate aspiration is to make Mark-I an exceptionally adaptable, intuitive, and increasingly autonomous assistant that can handle complex automation scenarios with minimal explicit programming, truly embodying the helpfulness and intelligence of a system like J.A.R.V.I.S. for visual desktop automation.

## 3. Core Goals

### Achieved in v4.0.0 and Earlier:

- **Targeted Screen Capture:** Reliably capture image data from user-defined screen areas.
- **Advanced Local Visual Information Extraction:** Pixel/average color detection, template matching, OCR, dominant color analysis.
- **AI-Powered Visual Understanding (Gemini - v4.0.0):**
  - Semantic visual querying via `gemini_vision_query`.
  - Precise interaction with AI-identified elements using bounding boxes.
- **Flexible Conditional Action Execution (Runtime):**
  - Trigger actions based on local or AI-driven visual analysis.
  - Sophisticated rules engine with single/compound conditions and variable handling.
- **AI-Informed Decision Making & NLU (Gemini - v4.0.0):**
  - `GeminiDecisionModule` enabling goal-driven single action execution and NLU-driven multi-step task orchestration via the `gemini_perform_task` action.
- **User-Friendly Configuration via GUI (`MainAppWindow`):** Comprehensive GUI for all aspects of manual profile creation and management, including all v4.0.0 Gemini features.
- **Performant and Reliable Bot Runtime:** Optimized loop, selective analysis, robust error handling, and detailed logging.

### Primary Goals for v5.0.0 (AI-Driven Profile Generation):

- **Goal-to-Plan Translation (`StrategyPlanner`):** Enable Mark-I to take a high-level user automation goal (natural language) and, using Gemini, generate a structured, intermediate plan of logical sub-steps.
- **Interactive AI-Assisted Profile Element Definition (`ProfileGenerator` & New GUI Wizard):**
  - Guide the user through translating each step of the AI-generated plan into concrete Mark-I profile elements (regions, rules, templates).
  - Utilize Gemini to provide intelligent suggestions for:
    - Relevant screen regions for each plan step.
    - Appropriate condition and action logic for each step.
    - Visual identification of target UI elements (candidate bounding boxes).
  - Allow users to easily confirm, edit, or override AI suggestions, and to manually define elements or capture templates when needed.
- **Automated Profile Assembly:** Construct a valid Mark-I JSON profile from the interactively defined and AI-assisted elements.
- **Intuitive GUI Workflow for Profile Generation:** Develop a new, user-friendly wizard (`ProfileCreationWizardWindow`) to manage the entire AI-driven profile creation process.

## 4. Non-Goals (Out of Scope for v4.0.0 & Initial v5.0.0 AI Profile Creator)

- Full-scale general computer vision AI beyond integrated local analysis and Gemini capabilities (e.g., real-time object tracking, fine-grained activity recognition without explicit prompting).
- General-purpose screen recording software (though screen capture is a core component).
- Fully autonomous AI agent behavior where the AI learns and adapts complex strategies for entirely novel tasks without any human guidance or intervention during profile creation or execution (v5.0.0 AI Profile Creator is _AI-assisted_, not fully autonomous generation).
- **(Limitation of v4.0.0 NLU & v5.0.0 AI Generation):** While powerful, the NLU for runtime commands and the AI's ability to generate plans/profiles from goals are dependent on the clarity of user input and Gemini's current capabilities. Highly abstract, ambiguous, or extremely complex goals/commands may not be reliably interpreted or translated into effective profiles without significant prompt engineering or user refinement.
- Direct UI element inspection using OS accessibility APIs (focus remains visual and AI-interpreted semantic analysis).

## 5. Target Users (Vision for v5.0.0)

Mark-I v5.0.0, with its AI Profile Creator, aims to broaden its appeal and utility:

- **Existing Target Users (Gamers, Testers, Power Users, etc.):** Will benefit from a significantly faster way to bootstrap complex automation profiles, reducing manual setup time.
- **Less Technical Users / Automation Novices:** The AI Profile Creator can lower the barrier to entry, allowing users to achieve useful automation by simply describing their goals in natural language and being guided through the specifics.
- **Business Process Automation:** Users looking to automate routine desktop application workflows can describe the process and have Mark-I assist in generating the automation profile.
- **Anyone needing to quickly prototype visual automations.**

## 6. Core Technology Stack (v4.0.0 Foundation, extended for v5.0.0)

- **Language:** Python (3.9+)
- **AI Model Interaction:** `google-generativeai` (for Google Gemini API) - used for runtime analysis/NLU (v4) and profile generation assistance (v5).
- **Local CV/OCR:** `OpenCV-Python`, `NumPy`, `Pillow`, `pytesseract`.
- **GUI:** `CustomTkinter`.
- **Core Automation & System:** `pyautogui`, `json`, `argparse`, `threading`, `python-dotenv`, `logging`.
- **(v5.0.0 New Modules):** `mark_i.generation.strategy_planner`, `mark_i.generation.profile_generator`, `mark_i.ui.gui.generation.profile_creation_wizard`, `mark_i.ui.gui.generation.sub_image_selector_window`.
