// File: adrs/ADR-004-Rules-Engine-Design-for-Conditional-Logic.md
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

**Chosen Option:** Start with **Option 1 (Simple List of Single-Condition Rule Objects)** and plan to evolve towards **Option 2 (Structured Rule Objects with Compound Conditions)** as the project matures and requirements for more complex logic become clearer.

**Justification (for starting with Option 1):**
*   **Simplicity and Rapid Initial Development:** Easiest to implement for core use cases.
*   **Clear Path to Core Value:** Delivers fundamental "IF visual_event THEN action" quickly.
*   **Manageable Configuration:** Straightforward JSON structure initially.

**Evolutionary Path to Option 2:**
*   Once Option 1 basics are stable and feedback indicates need for more complex logic, the rule structure can be enhanced.
*   The `condition` part of a rule object can be redesigned to accept a list of conditions with an associated logical operator (`AND`/`OR`).

This phased approach balances delivering initial value quickly with future flexibility.

## Consequences

*   **Initial Implementation (Option 1):**
    *   `rules_engine.py` iterates a list of rule objects, performs single condition check, executes action.
    *   Complex multi-condition logic initially requires multiple simple rules or external state management.
*   **Future Evolution (towards Option 2):**
    *   `rules_engine.py` will need updates for more complex condition structures.
    *   JSON schema for rules will change, requiring versioning or migration considerations for profiles (less concern for early versions).
*   Rule object structure (fields for `name`, `region`, `condition` type/params, `action` type/params) needs clear definition in `TECHNICAL_DESIGN.MD`.

---