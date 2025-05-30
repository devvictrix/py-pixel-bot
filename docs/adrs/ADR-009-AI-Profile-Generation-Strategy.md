# ADR-009: Strategy for AI-Driven Profile Generation (AI Profile Creator)

- **Status:** Proposed
- **Date:** 2025-05-29 <!-- Use current date or date of decision -->
- **Deciders:** DevLead

## Context and Problem Statement

Mark-I v4.0.0 significantly enhanced runtime AI capabilities (visual queries, NLU-driven task execution). However, creating complex and robust profiles still requires significant manual effort from the user in defining regions, conditions (including AI prompts), and actions.

The goal for v5.0.0 is to further leverage AI (Google Gemini) to assist in the **creation of these profiles themselves**. Users should be able to specify a high-level goal or demonstrate a task, and Mark-I should generate a functional Mark-I JSON profile (or a strong starting point) to achieve that goal. This feature is referred to as the "AI Profile Creator" or "Strategy Learning Mode."

We need to decide on a foundational architectural approach for this capability.

## Considered Options

1.  **Purely Generative Model Approach (End-to-End Profile Generation):**

    - **Description:** User provides a high-level natural language goal (e.g., "Automate logging into myapp.com with username 'user' and password 'pass'"). This goal, possibly along with an initial screenshot or URL, is fed to a powerful Gemini model (e.g., Gemini 1.5 Pro with extensive context). The model is prompted to directly output a complete Mark-I JSON profile structure.
    - **Pros:**
      - Potentially the most "magical" user experience if it works perfectly.
      - Leverages LLM's ability to generate structured data (JSON).
    - **Cons:**
      - **Extremely High Risk & Complexity:** Generating a perfectly valid, semantically correct, and _efficient_ Mark-I profile (with correct region coordinates, template image concepts, appropriate condition types, and robust action sequences) directly from a high-level goal is a massive leap. High chance of invalid JSON, incorrect logic, or hallucinated UI elements.
      - **Brittleness:** The generated profile would be highly dependent on the LLM's "understanding" of the target application's UI from a single prompt or limited context, potentially leading to non-functional profiles.
      - **Debugging Hell:** If the generated profile is flawed, debugging why the LLM made certain choices would be very difficult.
      - **Black Box:** The process of how the profile is generated is opaque.
      - **Limited User Guidance/Interaction:** Less opportunity for the user to guide the generation process for specific tricky parts.

2.  **Interactive Goal-to-Plan-to-Profile Approach (Chosen Hybrid Approach):**

    - **Description:** A multi-stage, more interactive process:
      - **Stage 1: Goal to Intermediate Plan (AI-Driven):**
        - User provides a high-level goal in natural language (e.g., "Log me into the MyApp application").
        - Mark-I (via a new `StrategyPlanner` module using `GeminiAnalyzer`) sends this goal, possibly with an initial full screenshot or application context, to Gemini.
        - Gemini is prompted to break down the goal into a sequence of logical, human-understandable sub-steps or sub-goals (e.g., "1. Find username field. 2. Type username. 3. Find password field. 4. Type password. 5. Find login button. 6. Click login button."). This is an "intermediate plan."
      - **Stage 2: Plan to Mark-I Profile Elements (AI-Assisted + User Interaction):**
        - Mark-I iterates through the AI-generated intermediate plan steps.
        - For each step, Mark-I (again, using `GeminiAnalyzer` or leveraging `GeminiDecisionModule`'s visual refinement logic) attempts to:
          - **Identify/Suggest Regions:** "To 'Find username field', I need to look at this part of the screen. Is this correct?" (User confirms/adjusts a suggested region).
          - **Suggest Condition Types & Parameters:** "For 'Find username field', I could use OCR to look for the label 'Username:', or perhaps you can provide a template image of the field?"
          - **Suggest Action Types:** "For 'Type username', the action will be 'type_text'."
        - **User Interaction is Key:** The user actively confirms, refines, or provides necessary inputs (e.g., draws/confirms a region, types in the exact text for an OCR condition, captures a template image when prompted by the AI's suggestion, provides actual credentials).
        - Mark-I assembles these confirmed/refined elements into a standard Mark-I JSON profile.
      - **Stage 3: Profile Review & Execution:** User reviews the generated profile in the standard GUI editor and can run/test it.
    - **Pros:**
      - **More Controllable & Robust:** Breaks the problem down. AI assists with planning and element suggestion, but user validates and provides ground truth for visual specifics.
      - **Interactive & Guided:** User is part of the process, making it more transparent and allowing for correction/guidance.
      - **Leverages Existing Capabilities:** Can reuse `GeminiAnalyzer` for plan generation and visual element suggestion. The output is a standard Mark-I profile, usable by the existing `RulesEngine` and `ActionExecutor`.
      - **Reduces User's Cognitive Load:** AI does the initial heavy lifting of strategizing and suggesting how to automate.
      - **Iterative Refinement Possible:** User could potentially ask the AI to refine parts of the plan or profile.
    - **Cons:**
      - More complex to implement than a simple "runtime AI" feature due to the interactive workflow and the need to translate AI suggestions into profile structures.
      - Still relies heavily on effective prompting for both plan generation and per-step element suggestion.
      - User interaction is required, so not fully "hands-off" generation.

3.  **Learning from Observation (Demonstration-Based Profile Generation):**
    - **Description:**
      - User puts Mark-I into a "record" or "observe" mode.
      - User performs the task manually on their screen.
      - Mark-I records screen video/snapshots and user input events (mouse clicks, keystrokes – this requires new input recording capabilities).
      - This recording is then processed (potentially by Gemini multimodal models) to infer the sequence of actions, target UI elements, and conditions.
      - The inferred logic is translated into a Mark-I profile.
    - **Pros:**
      - Potentially very intuitive for users ("show, don't tell").
      - Captures real user behavior and interaction patterns.
    - **Cons:**
      - **Very High Technical Complexity:** Reliably inferring intent, identifying stable visual cues, and generalizing from a single or few demonstrations into a robust profile is extremely challenging. Input recording itself is platform-dependent and complex.
      - **Noise and Irrelevance:** User demonstrations can contain irrelevant actions, pauses, or mistakes that the AI would need to filter out.
      - **Generalization Issues:** A profile generated from one demonstration might not generalize well to slight UI variations.
      - Significant R&D effort, likely beyond the scope of a single major version increment if starting from scratch.

## Decision Outcome

**Chosen Option:** **Option 2: Interactive Goal-to-Plan-to-Profile Approach.**

**Justification:**

- **Balance of AI Power and User Control:** This approach leverages Gemini's strength in planning and semantic understanding to generate a high-level strategy (the intermediate plan) and suggest UI elements, while keeping the user in the loop to provide grounding, confirm visual details (regions, templates), and ensure the final profile is robust and correct. This mitigates the "black box" and brittleness risks of a purely generative approach.
- **Feasibility and Iterative Development:** While complex, it's more feasible to implement in stages than Option 3. The "Goal to Intermediate Plan" and "Plan Step to Profile Element Suggestion" can be developed and refined iteratively.
- **Leverages Existing Mark-I Strengths:** The final output is a standard Mark-I profile, which means it can be edited, understood, and executed by the existing, well-tested Mark-I engine. It also utilizes the `GeminiAnalyzer` and potentially parts of the `GeminiDecisionModule`'s visual refinement logic.
- **User Experience:** Provides a guided, AI-assisted experience for profile creation, which should be more user-friendly for complex tasks than starting from a blank slate, yet more reliable than a fully autonomous generation attempt.
- **Path to More Advanced Features:** Success with this approach could lay the groundwork for more sophisticated "learning from observation" or plan refinement capabilities in the future.

## High-Level Implementation Plan (for v5.0.0 focused on Option 2)

1.  **New Module: `StrategyPlanner` (or similar name):**
    - Responsible for taking the user's high-level goal.
    - Uses `GeminiAnalyzer` to prompt Gemini for an "intermediate plan" (sequence of human-readable steps/sub-goals).
    - Parses and validates this plan.
2.  **New Module/Logic: `ProfileGenerator` (or part of `StrategyPlanner`):**
    - Iterates through the intermediate plan steps.
    - For each step:
      - **Suggests Regions:** May use Gemini to analyze a full screenshot and suggest a relevant area for the step, then prompts user for confirmation/drawing via a `RegionSelector`-like interface.
      - **Suggests Condition/Action Logic:** Based on the step's intent (e.g., "find X," "type Y"), suggests appropriate Mark-I condition types (OCR, template, `gemini_vision_query`) or action types.
      - **Interactive Element Identification:** If a step is "click button X," it might use Gemini to highlight potential "button X" candidates on screen, asking the user to confirm the correct one. The user might then be prompted to capture a template for it, or the system might auto-generate a `gemini_vision_query` to find it semantically.
      - **Parameter Elicitation:** Prompts user for necessary parameters (e.g., "What text should I type?").
    - Assembles confirmed/defined elements into a `profile_data` dictionary structure.
3.  **GUI Workflow for "AI Create Profile":**
    - New entry point in `MainAppWindow` (e.g., "File > AI Create New Profile...").
    - Interface for user to input their high-level goal.
    - Step-by-step guided UI where Mark-I presents suggestions from the `ProfileGenerator` and the user confirms, adjusts, or provides input (e.g., drawing regions, capturing templates, confirming text for OCR).
    - Option to review and save the generated profile, which then opens in the standard editor.
4.  **Prompt Engineering:** Significant effort will be required to develop effective prompts for Gemini for both the "Goal to Intermediate Plan" stage and the "Plan Step to Profile Element Suggestion" stage.

## Consequences

- **New Core Modules:** Introduction of `StrategyPlanner` and `ProfileGenerator` (or equivalent logic).
- **Significant GUI Development:** A new interactive workflow for AI-assisted profile creation.
- **Enhanced `GeminiAnalyzer` Usage:** Will be used for more complex planning and suggestion tasks, not just runtime queries.
- **Increased Complexity:** The overall system complexity will increase.
- **User Experience Shift:** Offers a new, potentially much faster way to create initial profile drafts for complex tasks.
- **Dependency on Prompt Quality:** The quality of generated profiles will heavily depend on the effectiveness of the prompts used to guide Gemini in both planning and element suggestion stages.
- **Iterative Process:** The AI-generated profile is likely to be a "good first draft" that users will then refine using the existing GUI editor. Perfect, ready-to-run complex profiles from a single goal description are unlikely initially.
- **Documentation:** Extensive new documentation will be needed for this feature.

This approach provides a path to significantly enhancing Mark-I's utility by using AI in the profile creation process, making complex automation more accessible.

---
