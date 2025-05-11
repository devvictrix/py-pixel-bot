// File: docs/adrs/ADR-004-Rules-Engine-Design-for-Conditional-Logic.md
# ADR-004: Rules Engine Design for Conditional Logic

*   **Status:** Approved
*   **Date:** 2025-05-11
*   **Deciders:** DevLead

## Context and Problem Statement

The tool's core functionality relies on a "Rules Engine" that evaluates conditions based on visual analysis and triggers actions ("IF `visual_condition(s)` MET for `region(s)`, THEN PERFORM `action_sequence`."). We need a clear, extensible, and configurable way to define these rules.

The design should consider:
*   How conditions are expressed (color match, template found, text present).
*   Combining multiple conditions (AND/OR logic).
*   Linking actions to conditions.
*   Storage in the configuration profile (JSON, per ADR-003).

## Considered Options

1.  **Simple List of Single-Condition Rule Objects (JSON):**
    *   Each rule is an object with a single condition type, parameters, and an action.
    *   Pros: Simple to understand and implement initially. Easy to parse.
    *   Cons: Limited expressiveness for complex logic (no direct AND/OR between different condition types on different regions within a single rule block without custom evaluation).

2.  **Structured Rule Objects with Compound Conditions (JSON):**
    *   Rules can have a complex `condition` block supporting AND/OR logic and multiple sub-conditions.
    *   Pros: More expressive. Keeps related logic within a single rule.
    *   Cons: More complex to parse and implement evaluation logic. JSON can become more deeply nested.

3.  **Dedicated Mini-Language or Expression Engine:**
    *   Define a custom string-based language for conditions.
    *   Pros: Potentially very expressive and flexible.
    *   Cons: Significant implementation overhead (parser, evaluator). Steep learning curve for users. Overkill initially.

4.  **Behavior Tree Approach:**
    *   Represent rules/actions as nodes in a behavior tree.
    *   Pros: Very powerful for complex sequences and conditional logic.
    *   Cons: Significant implementation complexity. Overkill initially. User configuration challenging without a dedicated editor.

## Decision Outcome

**Chosen Option:** Start with **Option 1 (Simple List of Single-Condition Rule Objects)** and evolve towards **Option 2 (Structured Rule Objects with Compound Conditions)** as the project matures and requirements for more complex logic become clearer.
*This evolution to Option 2 has been implemented as part of v2.0.0.*

**Justification (for starting with Option 1, then evolving to Option 2):**
*   **Simplicity and Rapid Initial Development (Option 1):** Easiest to implement for core use cases. Delivers fundamental "IF visual_event THEN action" quickly. Manageable initial configuration.
*   **Enhanced Expressiveness (Option 2):** Addresses the need for more complex logic by allowing `AND`/`OR` combinations of multiple sub-conditions within a single rule structure. The `condition` part of a rule object can accept a `logical_operator` and a list of `sub_conditions`.

This phased approach balanced delivering initial value quickly with achieving necessary flexibility.

## Consequences

*   **Initial Implementation (Option 1 - Completed for v0.x):**
    *   `rules_engine.py` iterated a list of rule objects, performed single condition check, executed action.
*   **Evolution (Option 2 - Implemented for v2.0.0):**
    *   `rules_engine.py` was updated to parse and evaluate complex condition structures with `logical_operator` and `sub_conditions`.
    *   JSON schema for rules was extended, while maintaining backwards compatibility for single-condition rules where `logical_operator` is absent.
*   Rule object structure (fields for `name`, `region` (default), `condition` object, `action` object) is clearly defined in `TECHNICAL_DESIGN.MD`.

---