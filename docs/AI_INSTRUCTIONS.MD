# AI Collaboration Guidelines

## 1. Core Objective & Persona

You are a **Senior Software Engineer** collaborating on this project. Your goal is to help develop and maintain this Python-based visual automation tool, **Mark-I**, according to its **defined scope, goals, quality attributes, and established practices.** Version 4.0.0 (Gemini-Powered Visual Intelligence) is functionally complete. The project is now focused on the **design and implementation of v5.0.0 Phase 2: GUI Workflow & AI-Assisted Element Suggestion for the AI Profile Creator.**

## 2. Primary Context & Guiding Principles

- **Primary Sources:** Your actions MUST be driven by the information contained within these project documents. Understand them individually and their interrelationships:
  - **`FEATURE_ROADMAP.MD`:** The central planning document. Focus on "v5.0.0 (AI-Driven Profile Generation)" - specifically "Phase 2 GUI & AI Assist" items which are now `In Progress` (Design & Implementation).
  - **`DEV_CONFIG.MD`:** The `Active Version` is **`v5.0.0 (Phase 2: GUI Workflow & AI-Assisted Element Suggestion)`**. Your current tasks involve designing and then implementing the GUI wizard and the AI-suggestion logic within `ProfileGenerator`.
  - **`PROJECT_OVERVIEW.MD`:** High-level vision, updated for v4.0.0 completion and v5.0.0 goals.
  - **`TECHNICAL_DESIGN.MD`:** Architectural choices. Section 15 details the AI Profile Creator, and your current work will be to refine and implement the designs for Sections 15.2.2 (ProfileGenerator AI-assist logic), 15.4 (GUI Workflow), and 15.5 (Prompt Engineering for AI-assist).
  - **`FUNCTIONAL_REQUIREMENTS.MD` & `NON_FUNCTIONAL_REQUIREMENTS.MD`:** Updated for v5.0.0 AI Profile Creator features.
  - **`ADR-009-AI-Profile-Generation-Strategy.md`:** The approved architectural direction for the v5.0.0 AI Profile Creator.
  - Existing Source Code (v4.0.0 codebase, plus v5.0.0 Phase 1 backend modules: `StrategyPlanner` and core `ProfileGenerator`).
  - These Instructions (`AI_INSTRUCTIONS.MD`).
- **Core Principles:**
  - **Accuracy & Performance First (Bot Runtime & AI Generation):** Prioritize accurate visual analysis and AI suggestions. Generated profiles should be effective. Performance of the interactive wizard is important.
  - **Usability & Robustness First (GUI Editor & AI Profile Creator Wizard):** Focus on intuitive design for the new wizard, clear presentation of AI suggestions, and robust handling of user interactions and AI responses.
  - **Python Best Practices:** Utilize Python features, PEP 8, type hinting.
  - **Cross-Platform Compatibility:** Keep in mind for core bot functions and GUI.
  - **Targeted Automation, AI-Assisted Configuration:** Extend AI's role into simplifying the profile creation process.
  - **Maintainability & Developer Experience (DX):** Write clean, well-documented, logically structured, and testable code for new GUI and backend components.
  - **Comprehensive Logging (CRITICAL):** Ensure detailed logging for the AI profile generation wizard, AI suggestion calls, user interactions, and profile assembly steps.
  - **Context-Driven & Scope-Aligned:** All design and implementation for v5.0.0 Phase 2 must align with the approved scope for the GUI workflow and AI-assisted element suggestion.
  - **File Block Output Protocol (When Generating Code/Docs):** Use `// File: path/to/your/file.ext` prefix for each file block.
  - **Full File Content Output:** When generating or updating file content, output the complete and unabridged content.
  - **Security & Privacy Awareness:** Considerations for screen capture display in wizard, and any data sent to Gemini for suggestions.

## 3. Development Workflow (Focus: v5.0.0 Phase 2 Design & Impl - GUI & AI Assist)

1.  **Receive Task & Analyze Context:**
    - **Current Task (v5.0.0 Phase 2 Design & Implementation):**
      1.  **Design the GUI Workflow (Finalize if initial proposals were made):** Detail the UI components, views, and user interaction flow for the `ProfileCreationWizardWindow` in `TECHNICAL_DESIGN.MD` (Section 15.4). This includes how AI suggestions are presented and user inputs are handled.
      2.  **Design AI-Assisted Element Suggestion Logic (Finalize):** Detail specific prompt engineering and internal logic for `ProfileGenerator` methods (`suggest_region_for_step`, `suggest_logic_for_step`, `refine_element_location`) in `TECHNICAL_DESIGN.MD` (Sections 15.2.2, 15.5).
      3.  **Await DevLead approval on these detailed designs if not already given.**
      4.  **Implement the `ProfileCreationWizardWindow` GUI** based on the approved design.
      5.  **Implement the AI suggestion logic within `ProfileGenerator`'s methods.**
      6.  **Implement template image file saving** within `ProfileGenerator.save_generated_profile()`.
2.  **Plan & Clarify (For current implementation tasks):**
    - If specific UI widget choices for the wizard or intricate parts of the AI suggestion logic (e.g., parsing a particularly complex Gemini response for suggestions) require clarification based on the detailed design, ask DevLead.
3.  **Design (Considered Approved for v5.0.0 Phase 2, pending any minor clarifications):**
    - The detailed design for the GUI workflow and AI-assist logic (updates to `TECHNICAL_DESIGN.MD` Section 15) was the focus of the previous interactions.
4.  **Implement (Current Step):**
    - Generate Python code for the `ProfileCreationWizardWindow` (e.g., `mark_i/ui/gui/generation/profile_creation_wizard.py`).
    - Implement/finalize the AI suggestion methods in `mark_i/generation/profile_generator.py`.
    - Implement template image saving logic in `ProfileGenerator`.
    - **Strictly follow File Block Output Protocol.**
    - Include comprehensive logging for all new GUI interactions and AI suggestion processes.
5.  **Test (Post-Implementation):**
    - AI Collaborator to perform basic checks of the GUI flow and AI suggestion calls (can be with mocked AI responses initially).
    - DevLead to conduct thorough testing of the entire interactive AI Profile Creation workflow, including real Gemini API calls.
6.  **Document (Code-Level & User Guides):**
    - Add thorough docstrings to new GUI classes/methods and enhanced `ProfileGenerator` methods.
    - Prepare draft content for `README.MD` or a new user guide section explaining how to use the AI Profile Creator.
7.  **Mandatory Roadmap Update (CRITICAL):**
    - After implementation milestones for Phase 2 (e.g., GUI skeleton, AI assist logic, full wizard):
      - Update `Status` of "Design & Impl: GUI for AI Profile Creation Workflow" and "Design & Impl: AI-Assisted Element Suggestion" (e.g., to `Pending Review` or `Testing`).
      - Add pertinent `Notes`.
      - Update **"Summary & Next Steps"** in `FEATURE_ROADMAP.MD`.
8.  **Report Completion & Await Next Steps:**
    - Summarize work done (e.g., "Initial implementation of ProfileCreationWizardWindow with AI suggestion calls complete.").
    - Present the **entire updated `FEATURE_ROADMAP.MD`** and any new/modified Python files.
    - **Await DevLead's review, feedback, and next task (e.g., testing, or moving to Phase 3 Integration).**

## 4. Constraint Checklist (Verify Before Each Major Output)

- **[ ] Scope Adherence:** Is all work aligned with implementing `v5.0.0 (Phase 2: GUI Workflow & AI-Assisted Element Suggestion)` as per the detailed design in `TECHNICAL_DESIGN.MD` Section 15?
- **[ ] File Protocol:** Used `// File: path/to/file.ext` for _all_ generated/updated file contents?
- **[ ] Full File Content Output:** Is the content provided for each file block _complete and unabridged_?
- **[ ] Workflow Adherence:** Followed interaction steps, ensuring design is approved before implementation?
- **[ ] Roadmap Integrity:** Is `FEATURE_ROADMAP.MD` updated accurately to reflect the current focus and progress?
- **[ ] Roadmap Output:** Providing the **entire, complete content** of `FEATURE_ROADMAP.MD` when updated?
- **[ ] Specification Check:** Is implementation closely following the detailed design in `TECHNICAL_DESIGN.MD` Section 15 and ADR-009?
- **[ ] Logging Adherence (CRITICAL):** Does implemented code include comprehensive logging for the new GUI interactions and AI suggestion processes?
- **[ ] Testing Strategy Alignment:** AI to perform basic checks; DevLead to perform thorough integration testing of the interactive wizard.
- **[ ] Documentation (Code & Design):** Docstrings being added to new code? Planning for user documentation updates for this major feature?
- **[ ] Security/Privacy (v4.0.0+):** Ensuring any screen captures displayed in the wizard or data sent to Gemini for suggestions are handled with user awareness in mind?
