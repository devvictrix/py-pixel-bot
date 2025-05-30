# ADR-008: Integrating Gemini API for Enhanced Visual Understanding, Decision Making, and NLU

*   **Status:** Implemented and Evolved through v4.0.0 (Initial Vision Query, Bounding Box Actions, Goal-Driven Decisions, NLU Command Interface)
*   **Date Decision Initially Made:** 2025-05-12
*   **Date Last Updated (to reflect v4.0.0 completion):** Current Date
*   **Deciders:** DevLead

## Context and Problem Statement

Mark-I initially operated on deterministic visual analysis (pixels, templates, OCR) and a rule engine with explicit user-configured conditions. This faced limitations in:
1.  **Limited Scene Comprehension:** Lacked deeper, semantic understanding beyond exact matches.
2.  **Brittleness to UI Changes:** Fragile to minor UI redesigns.
3.  **Inflexible Decision Making:** Current rules engine, though supporting compound conditions, remained deterministic.
4.  **Goal: Enhance AI Capabilities ("AI Moving More Freely"):** Strategic goal to evolve Mark-I to interpret visual information more intelligently and act with greater flexibility, adaptability, and understanding, including responding to natural language commands.

This ADR originally proposed integrating Google Gemini API for its multimodal capabilities as a step to enhance visual understanding. Its scope and realization have expanded through Mark-I v4.0.0.

## Original Considered Options (Summary)

1.  **Gemini for Visual Scene Description & Question Answering (Original Chosen Path - Realized as `gemini_vision_query` in v4.0.0 Phase 1):** Send images to Gemini with prompts for description, element identification, or Q&A. Output used in `RulesEngine`.
2.  **Gemini for Rule/Action Generation from Natural Language (Deferred/Future):** User describes task in NL, Gemini generates Mark-I JSON profile. Considered complex and high-risk for initial integration.
3.  **Gemini for End-to-End Visual Task Execution (Agent-like Behavior - Evolved into `GeminiDecisionModule` for v4.0.0 Phase 2 & 3):** Gemini directly decides next actions based on visual context and high-level goals. Originally seen as technologically immature for full autonomy but realized in a controlled manner.
4.  **No Gemini Integration (Rejected):** Fails to address stated problems or strategic AI goals.

## Decision Outcome and Evolution through v4.0.0

**Initial Chosen Option:** Option 1 (Gemini for Visual Scene Description & Q&A) was the starting point for v4.0.0 Phase 1.

**Evolution across v4.0.0 Phases:** The integration of Gemini evolved significantly:

*   **v4.0.0 Phase 1: Core Visual Querying:**
    *   Implemented `GeminiAnalyzer` for robust API interaction.
    *   Added the `gemini_vision_query` condition type to `RulesEngine`, allowing rules to directly ask Gemini questions about visual regions.
    *   Established API key management and basic GUI support.
*   **v4.0.0 Phase 1.5: Bounding Box Actions:**
    *   Extended `gemini_vision_query` and `ActionExecutor` to allow actions (e.g., clicks) to target precise coordinates derived from bounding boxes returned by Gemini for identified elements.
*   **v4.0.0 Phase 2: Gemini-Informed Decision Making (Single Goal):**
    *   Introduced the `GeminiDecisionModule`.
    *   Added a `gemini_perform_task` action type where users provide a simple goal. The `GeminiDecisionModule` uses Gemini to understand the goal in visual context and suggest/execute a single primitive action from a predefined safe set (e.g., click a described button).
*   **v4.0.0 Phase 3: Natural Language Command Interface:**
    *   Enhanced `GeminiDecisionModule` to parse complex natural language commands (provided via the `gemini_perform_task` action's `natural_language_command` parameter).
    *   Gemini is used for NLU to decompose the command into a sequence of sub-steps.
    *   The `GeminiDecisionModule` orchestrates the execution of these sub-steps, using Gemini for visual analysis and action refinement for each step, drawing upon the capabilities developed in earlier phases.

This phased approach allowed for incremental integration of increasingly sophisticated AI capabilities, moving from simple visual Q&A to NLU-driven task execution.

**Justification for the Evolved Approach:**
*   **Direct Enhancement of Perception & Action:** Directly addressed the core weaknesses of limited understanding and brittleness.
*   **Feasible and Incremental Path:** Allowed for delivering value incrementally, building foundational components first.
*   **Achieving "Freer Movement":** Each phase provided more "freedom" and intelligence to the bot:
    *   Semantic understanding over pixel matching.
    *   Robustness to UI tweaks.
    *   Goal-oriented action selection.
    *   Interpretation of natural language commands for multi-step tasks.
*   **Balanced Power and Control:** While leveraging powerful LMMs, the system retains control through predefined allowed sub-actions for the `GeminiDecisionModule` and user-configurable safety parameters (e.g., confirmation steps).

## Realization Details (Summary - Full details in `TECHNICAL_DESIGN.MD`)

*   **`GeminiAnalyzer` (`mark_i.engines.gemini_analyzer.GeminiAnalyzer`):** Core module for all Gemini API interactions (vision and text models).
*   **`RulesEngine` (`mark_i.engines.rules_engine.RulesEngine`):**
    *   Integrates `gemini_vision_query` condition type (calls `GeminiAnalyzer`).
    *   Handles `gemini_perform_task` action type by invoking `GeminiDecisionModule`.
*   **`GeminiDecisionModule` (`mark_i.engines.gemini_decision_module.GeminiDecisionModule`):**
    *   Parses natural language commands using `GeminiAnalyzer`.
    *   Decomposes commands into sequences of sub-steps.
    *   For each sub-step, uses `GeminiAnalyzer` to determine the primitive action and refine targets (e.g., get bounding boxes).
    *   Orchestrates execution via `ActionExecutor`.
    *   Manages a predefined set of allowed primitive sub-actions (`PREDEFINED_ALLOWED_SUB_ACTIONS`).
*   **Configuration:**
    *   `GEMINI_API_KEY` in `.env`.
    *   Profile settings for `gemini_default_model_name`.
    *   JSON parameters for `gemini_vision_query` (prompt, expectations, etc.).
    *   JSON parameters for `gemini_perform_task` (natural_language_command, context_regions, allowed_actions_override, require_confirmation_per_step, max_steps).
*   **GUI Support (`MainAppWindow` / `DetailsPanel`):**
    *   Configuration for all Gemini-related condition and action parameters.

## Consequences (Reflecting Full v4.0.0 Implementation)

*   **New Core Dependencies:** `google-generativeai` library.
*   **External Service Dependency:** Core functionalities now rely on Google's Gemini API availability and performance.
*   **Cost:** Users must manage Gemini API usage costs.
*   **Latency:** Gemini API calls (for vision queries, NLU parsing, decision making, target refinement) introduce noticeable latency (seconds per call). This impacts achievable `monitoring_interval_seconds` and overall task completion times for AI-heavy profiles/commands.
*   **Internet Requirement:** Mandatory for all Gemini-powered features.
*   **API Key Security:** Critical (handled via `.env` and `.gitignore`).
*   **Privacy:** Users explicitly informed that image data (for vision queries/context) and natural language command text are sent to Google servers.
*   **Prompt Engineering Skill:** Effectiveness of all Gemini features (queries, goal-driven tasks, NLU commands) heavily hinges on user-written prompts and commands. This introduces a new layer of complexity and skill for advanced configuration and usage.
*   **Increased Code Complexity:** Added `GeminiAnalyzer` and `GeminiDecisionModule`; modified `RulesEngine`, `MainController`, GUI components, profile schema, and all documentation.
*   **Non-Determinism:** Introduces variability in outcomes based on LMM responses. Robust error handling, clear feedback, and user confirmation options are crucial mitigations.
*   **New Capabilities:** Mark-I can now understand visual scenes more deeply, interact with elements semantically, make simple goal-oriented decisions, and interpret/execute natural language commands for multi-step tasks, significantly enhancing its automation power and user interaction paradigm.

This integration has successfully laid the foundation for future AI-driven enhancements, moving Mark-I closer to its vision as a truly intelligent visual assistant.

---