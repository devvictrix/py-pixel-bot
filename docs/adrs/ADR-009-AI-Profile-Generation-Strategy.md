# ADR-009: Strategy for AI-Driven Profile Generation (AI Profile Creator)

- **Status:** Accepted
- **Date Decision Made:** 2025-05-29
- **Deciders:** DevLead

## Context and Problem Statement

Mark-I v4.0.0 significantly enhanced runtime AI capabilities (visual queries, NLU-driven task execution). However, creating complex and robust profiles still requires significant manual effort from the user in defining regions, conditions (including AI prompts), and actions.

The goal for v5.0.0 is to further leverage AI (Google Gemini) to assist in the **creation of these profiles themselves**. Users should be able to specify a high-level goal or demonstrate a task, and Mark-I should generate a functional Mark-I JSON profile (or a strong starting point) to achieve that goal. This feature is referred to as the "AI Profile Creator" or "Strategy Learning Mode."

We need to decide on a foundational architectural approach for this capability to guide the design of `StrategyPlanner`, `ProfileGenerator`, and the associated GUI workflow.

## Considered Options

1.  **Purely Generative Model Approach (End-to-End Profile Generation):**

    - **Description:** User provides a high-level natural language goal. This goal, possibly with initial visual context, is fed to a powerful Gemini model prompted to directly output a complete Mark-I JSON profile.
    - **Pros:** Potentially simplest user experience if perfect; leverages LLM's JSON generation.
    - **Cons:** Extremely high risk of invalid/incorrect/inefficient profiles; debugging LLM choices is hard; "black box" generation; limited user guidance during creation.

2.  **Interactive Goal-to-Plan-to-Profile Approach (Chosen):**

    - **Description:** A multi-stage, interactive process:
      - **Stage 1: Goal to Intermediate Plan (AI-Driven - `StrategyPlanner`):** User inputs goal. `StrategyPlanner` uses Gemini to break it into a sequence of logical, human-readable sub-steps (the "intermediate plan," e.g., as JSON).
      - **Stage 2: Plan to Mark-I Profile Elements (AI-Assisted + User Interaction - `ProfileGenerator` & GUI Wizard):** Mark-I (via `ProfileGenerator`) iterates through plan steps. For each step, it uses Gemini to suggest relevant regions, condition/action logic, and specific UI elements. The user interactively confirms, refines, draws regions, captures templates, and provides necessary parameters via a GUI wizard.
      - **Stage 3: Profile Assembly & Review:** `ProfileGenerator` assembles confirmed elements into a standard Mark-I JSON profile. User reviews and saves.
    - **Pros:** Balances AI planning with user control and validation; more robust and transparent; leverages existing Mark-I components for output; iterative refinement is possible; reduces user's initial cognitive load for complex tasks.
    - **Cons:** More complex to implement than Option 1 due to interactive workflow; still reliant on effective prompting for AI stages; requires user interaction.

3.  **Learning from Observation (Demonstration-Based Profile Generation):**
    - **Description:** User performs task, Mark-I records screen/inputs. AI (Gemini multimodal) infers logic and generates profile.
    - **Pros:** Intuitive "show, don't tell" for users.
    - **Cons:** Very high technical complexity (reliable intent inference, input recording, generalization from demonstrations); susceptible to noise in demonstrations; significant R&D.

## Decision Outcome

**Chosen Option:** **Option 2: Interactive Goal-to-Plan-to-Profile Approach.**

**Justification:**

This approach was chosen because it strikes the best balance between leveraging AI's strengths for strategic planning and semantic understanding, while retaining crucial user control and validation for the visual specifics and logical details of the automation. Key reasons:

- **Controllability & Robustness:** Breaking the problem into "AI generates plan" and "AI assists user to implement plan steps" is more robust than end-to-end generation. User validation at each step of profile element definition (regions, conditions, actions, templates) ensures the final profile is grounded in reality and user intent.
- **Feasibility & Iterative Development:** This approach allows for phased development of v5.0.0. The `StrategyPlanner` (goal-to-plan) and the core `ProfileGenerator` (iterating plan, placeholder elements) can be built first, followed by the interactive GUI and AI-suggestion logic for each element type.
- **Leverages Existing Mark-I Ecosystem:** The final output is a standard Mark-I JSON profile, fully compatible with the existing `RulesEngine`, `ActionExecutor`, and manual GUI editor (`MainAppWindow`). This maximizes reuse and ensures generated profiles are understandable and editable.
- **User Experience:** Offers a guided, "AI co-pilot" experience for profile creation. It aims to significantly reduce the effort of starting complex profiles from scratch, making automation more accessible, while still empowering the user with final say.
- **Transparency:** The intermediate plan and AI suggestions at each step make the generation process more transparent than a black-box generative model.
- **Foundation for Future:** Successfully implementing this provides a strong base upon which more advanced features (like plan editing, or even basic "learning from observation" to _suggest_ an initial plan) could be built.

## High-Level Implementation Plan (Outline)

_(This was detailed in `TECHNICAL_DESIGN.MD` Section 15. For this ADR, a summary suffices)_

1.  **Develop `StrategyPlanner`:** Takes user goal, uses `GeminiAnalyzer` for goal -> intermediate plan (JSON sequence of steps).
2.  **Develop `ProfileGenerator`:**
    - Takes intermediate plan.
    - Iterates steps. For each step:
      - Uses `GeminiAnalyzer` to suggest regions for the step based on full visual context.
      - Uses `GeminiAnalyzer` to suggest condition/action logic for the step based on the confirmed/defined region image for that step.
      - Uses `GeminiAnalyzer` to refine textual descriptions of UI elements into bounding boxes within the step's region.
    - Assembles confirmed/user-defined elements into profile data.
    - Handles saving of generated profile and associated template images.
3.  **Develop `ProfileCreationWizardWindow` GUI:** Manages user input of goal, display of plan (optional), and the interactive step-by-step process of defining regions, conditions, actions, and templates with AI suggestions and user confirmations.

## Consequences

- **New Core Modules:** Introduction of `mark_i.generation.strategy_planner.StrategyPlanner` and `mark_i.generation.profile_generator.ProfileGenerator`.
- **New GUI Components:** Development of `mark_i.ui.gui.generation.profile_creation_wizard.ProfileCreationWizardWindow` and helper windows like `SubImageSelectorWindow`.
- **Enhanced `GeminiAnalyzer` Usage:** `GeminiAnalyzer` will be used for new types of prompts related to planning, region suggestion, logic suggestion, and element refinement.
- **Increased Project Complexity:** The overall system becomes more complex, introducing a "design-time AI" workflow alongside the "runtime AI" features.
- **Shift in User Experience:** Offers a new primary method for creating complex profiles, potentially reducing reliance on purely manual construction for many users.
- **Criticality of Prompt Engineering:** The success of this feature will heavily depend on the quality and robustness of the prompts designed for `StrategyPlanner` (goal-to-plan) and `ProfileGenerator` (suggestion of regions, logic, elements).
- **Iterative Nature of Output:** AI-generated profiles are expected to be "strong first drafts" that users will likely review and refine using the standard `MainAppWindow` editor. Perfect, complex profiles from a single goal are a long-term aspiration, not the immediate guaranteed output.
- **Documentation & User Guidance:** Extensive new documentation and in-GUI guidance will be required to help users effectively state goals and interact with the AI suggestions during profile creation.

This "Interactive Goal-to-Plan-to-Profile" approach represents a significant step towards making Mark-I a more intelligent and user-friendly automation tool.