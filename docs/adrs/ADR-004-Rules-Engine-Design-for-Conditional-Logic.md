# ADR-004: Rules Engine Design for Conditional Logic

*   **Status:** Approved (Implemented and Evolved; v4.0.0 additions like `gemini_vision_query` fit this structure)
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool's (Mark-I) core functionality relies on a "Rules Engine" that evaluates conditions based on visual analysis and triggers actions ("IF `visual_condition(s)` MET for `region(s)`, THEN PERFORM `action_sequence`."). We need a clear, extensible, and configurable way to define these rules.

The design should consider:
*   How conditions are expressed (e.g., color match, template found, text present, dominant color, **AI vision query (v4.0.0)**).
*   The ability to combine multiple conditions using logical operators (AND/OR).
*   Linking specific actions to these conditions (including standard actions and **AI-driven task actions (v4.0.0)**).
*   How these rules are stored within the configuration profile (JSON, as per ADR-003).
*   The potential for capturing data from a condition (e.g., OCR text, template coordinates, **Gemini API responses**) for use in actions.

## Considered Options

1.  **Simple List of Single-Condition Rule Objects (JSON):**
    *   Each rule is an object with a single condition type, its parameters, and an associated action.
    *   Pros: Very simple to understand and implement initially. Easy to parse.
    *   Cons: Limited expressiveness for complex logic. Combining multiple distinct checks (e.g., "color IS X **AND** template Y IS found") would require multiple rules and potentially complex external state management by the user or bot, or lead to very specific, inflexible combined condition types.

2.  **Structured Rule Objects with Compound Conditions (JSON):**
    *   Rules can have a more complex `condition` block that supports a primary logical operator (`AND` or `OR`) and a list of `sub_conditions`. Each sub-condition would be similar in structure to the single condition object from Option 1.
    *   Pros: Far more expressive. Allows users to construct complex logical relationships between different types of visual checks on various regions, all within a single, cohesive rule. Keeps related logic together.
    *   Cons: More complex to parse and to implement the evaluation logic in the `RulesEngine`. The JSON structure for rules becomes more deeply nested.

3.  **Dedicated Mini-Language or Expression Engine:**
    *   Define a custom string-based language or expression syntax for conditions (e.g., `"regionA.pixel(10,10).is_color([0,0,255]) AND regionB.has_template('icon.png')"`).
    *   Pros: Potentially very expressive and flexible, could allow for arithmetic or string operations within conditions.
    *   Cons: Significant implementation overhead (parser, lexer, evaluator). Steep learning curve for users not familiar with expression languages. Overkill for the initial and likely medium-term scope.

4.  **Behavior Tree Approach:**
    *   Represent rules, conditions, and actions as nodes in a behavior tree (common in game AI and robotics).
    *   Pros: Extremely powerful for complex sequences, conditional logic, state management, and prioritization.
    *   Cons: Significant implementation complexity. Likely overkill for the project's primary focus on reacting to visual states. User configuration would be very challenging without a dedicated visual behavior tree editor, which is far beyond the scope of the planned `CustomTkinter` GUI.

## Decision Outcome

**Chosen Option:** Start with **Option 1 (Simple List of Single-Condition Rule Objects)** for initial development (v0.x versions) and then **evolve to Option 2 (Structured Rule Objects with Compound Conditions)** as the project matured and the need for more complex logic became evident.

*   **Status:** The evolution to **Option 2 has been fully implemented** as part of the v2.0.0 feature set and remains the current standard. The `RulesEngine` supports rules with a `condition` block containing a `logical_operator` ("AND" or "OR") and a list of `sub_conditions`. Each sub-condition has its own `type` (e.g., `pixel_color`, `gemini_vision_query`) and parameters. The GUI (`MainAppWindow`) also supports creating and editing this compound structure.
*   Backwards compatibility for the Option 1 (single condition) format is maintained: if a rule's `condition` object directly contains a `type` field and no `logical_operator`, it's treated as a single condition.

**Justification for the Evolutionary Approach:**
*   **Initial Simplicity (Option 1):** Allowed for rapid development of core "IF visual_event THEN action" functionality.
*   **Meeting Evolving Needs (Option 2):** As more analysis types were added (including AI-driven ones in v4.0.0) and more complex automation scenarios were considered, Option 2 provided the necessary expressiveness.
*   **Manageable Complexity:** Option 2, while more complex than Option 1, is still significantly simpler to implement and manage within a JSON configuration and a Python-based `RulesEngine` than Options 3 or 4. The GUI helps abstract this complexity.

## Consequences

*   **`RulesEngine` Implementation:**
    *   Handles both simple single conditions and compound conditions with recursive/iterative evaluation of `sub_conditions` based on the `logical_operator`.
    *   Integrates various condition evaluation logics, including calls to `AnalysisEngine` for local checks and `GeminiAnalyzer` for `gemini_vision_query` conditions.
*   **JSON Profile Schema:**
    *   The `condition` object within a rule in the JSON profile supports both single and compound structures. This schema is documented in `TECHNICAL_DESIGN.MD`.
    *   The action object within a rule supports various types, including standard UI interactions and the AI-driven `gemini_perform_task`.
*   **GUI Development (`MainAppWindow`):**
    *   The GUI allows users to create and edit both single and compound conditions, and various action types with their specific parameters.
*   **Variable Capture & Usage:** The design of conditions (including `gemini_vision_query`) accommodates variable capture (`capture_as`) and the use of those variables in subsequent conditions or the rule's action.

---