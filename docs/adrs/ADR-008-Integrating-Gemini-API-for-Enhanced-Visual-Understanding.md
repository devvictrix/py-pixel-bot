// File: docs/adrs/ADR-008-Integrating-Gemini-API-for-Enhanced-Visual-Understanding.md

# ADR-008: Integrating Gemini API for Enhanced Visual Understanding and Decision Making

*   **Status:** Approved <!-- Assuming DevLead approves based on roadmap -->
*   **Date:** 2025-05-12 <!-- Date decision was finalized -->
*   **Deciders:** DevLead

## Context and Problem Statement

Mark-I currently operates based on deterministic visual analysis techniques (pixel color matching, template image searching, Optical Character Recognition) and a rule engine that triggers predefined actions based on explicit, user-configured conditions. While effective for well-defined, stable automation tasks, this approach faces limitations:

1.  **Limited Scene Comprehension:** The bot lacks a deeper, semantic understanding of the visual scene. It cannot infer context, recognize objects or UI elements beyond exact templates/text patterns, or understand relationships between elements without explicit rules.
2.  **Brittleness to UI Changes:** Reliance on pixel-perfect color matches or exact template images makes automations fragile. Minor UI redesigns, changes in resolution, themes, or font rendering can easily break existing rules.
3.  **Inflexible Decision Making:** The current rules engine, even with compound conditions, is fundamentally deterministic. It cannot make nuanced decisions based on a holistic interpretation of the visual environment or handle ambiguity effectively.
4.  **Goal: Enhance AI Capabilities ("AI Moving More Freely"):** There is a strategic goal to evolve Mark-I towards incorporating more sophisticated AI, enabling it to interpret visual information more intelligently and act with greater flexibility, adaptability, and understanding – moving beyond rigid, pre-programmed responses.

This ADR proposes integrating the Google Gemini API, specifically its multimodal capabilities (understanding images and text), as a concrete step to enhance the bot's visual understanding and pave the way for more intelligent decision-making.

## Considered Options

1.  **Gemini for Visual Scene Description & Question Answering (Chosen Path - v4.0.0 Phase 1):**
    *   *Description:* Mark-I captures screen regions as usual. For specific rules, these images (or designated sub-regions) are sent to a Gemini Vision model (e.g., Gemini Pro Vision, Gemini Flash) via API call, along with a carefully crafted text prompt. The prompt instructs Gemini to perform tasks like:
        *   Describe the scene/region content.
        *   Identify specific types of elements (buttons, text fields, icons with certain characteristics).
        *   Answer questions about the visual content ("Is the status 'Complete'?", "What text is on the red button?").
        *   Extract structured information (e.g., return identified elements and their approximate locations as JSON).
    *   *Integration:* Gemini's response (text or structured JSON) is received by Mark-I. This output can then be used:
        *   Within the existing `RulesEngine` via new condition types (e.g., `gemini_vision_query` checking if the response contains keywords, matches expected JSON values, etc.).
        *   Potentially by a new "GeminiDecisionModule" in later phases to influence action selection based on the richer context provided by Gemini.
    *   *Pros:*
        *   **Semantic Understanding:** Directly addresses the limitation of current analysis by leveraging a powerful foundation model for higher-level visual comprehension.
        *   **Increased Robustness:** Can make automations more resilient to minor UI changes by focusing on semantic meaning ("find the login button") rather than exact pixels/templates.
        *   **Handles Ambiguity/Novelty:** Potential to interpret unexpected UI states or recognize elements without pre-defined templates, guided by the prompt.
        *   **Incremental Integration:** Provides a clear, phased approach to integrating advanced AI into the existing architecture. New condition types or modules can be added without replacing the entire system initially.
        *   **Foundation for Future AI:** Builds essential infrastructure (API client, prompt handling, response parsing) for more advanced AI features later.
    *   *Cons:*
        *   **API Latency:** Introduces network latency for API calls, making it unsuitable for very high-frequency (<1-2 second) real-time loops without careful design.
        *   **API Costs:** Gemini API usage incurs costs based on input/output tokens and potentially image analysis.
        *   **API Key Management:** Requires secure handling and user configuration of API keys.
        *   **Prompt Engineering:** The effectiveness heavily relies on designing good prompts, which is a skill in itself. Poor prompts yield poor results.
        *   **Data Privacy/Security:** Screen content (images of selected regions) is sent to Google's servers. User awareness and consent are crucial. API key security is paramount.
        *   **Internet Dependency:** Requires an active internet connection for features utilizing Gemini.
        *   **Determinism Reduction:** Introduces non-determinism from the AI model's responses.

2.  **Gemini for Rule/Action Generation from Natural Language:**
    *   *Description:* User describes an automation task in natural language (e.g., "If I see an error message, click the OK button"). A Gemini text model attempts to parse this description and generate the corresponding Mark-I JSON profile structure.
    *   *Pros:* Potentially offers a very user-friendly way to configure simple automations.
    *   *Cons:*
        *   **High Complexity & Risk:** Extremely challenging to implement reliably and safely. High risk of misinterpreting instructions and generating incorrect or even harmful automation rules. Requires sophisticated parsing and mapping to the specific profile schema.
        *   **Focus on Configuration, Not Runtime:** This enhances the configuration experience but does not directly improve the bot's *runtime* visual understanding or decision-making freedom.
        *   **Ambiguity:** Natural language is inherently ambiguous; translating it accurately to formal rules is difficult.

3.  **Gemini for End-to-End Visual Task Execution (Agent-like Behavior):**
    *   *Description:* Mark-I provides visual context (full screen or relevant regions) to a Gemini model (likely a hypothetical future Vision-Language-Action model or a complex prompting strategy with current models). The model directly decides the *next* action (e.g., "click coordinates (x,y)", "type 'text'") needed to achieve a high-level user goal (e.g., "Respond to the latest message"). Mark-I executes the action, captures the new visual state, and feeds it back to the model in a loop.
    *   *Pros:* Represents the ultimate vision of an AI "moving freely" and performing complex tasks autonomously based on visual input.
    *   *Cons:*
        *   **Technologically Immature/Complex:** Currently at the edge of research and practical reliability for general, unconstrained desktop automation. Requires sophisticated prompting, state management, and potentially fine-tuning.
        *   **Safety & Control:** Major concerns regarding safety, predictability, and ensuring the agent doesn't perform unintended or harmful actions. Defining boundaries and overrides is critical and difficult.
        *   **Very High Latency:** Each step in the sequence requires an API call, making it potentially very slow.
        *   **Massive Scope:** Implementing such an agent is a large research and engineering undertaking, far beyond the scope of the initial Gemini integration.

4.  **No Gemini Integration (Maintain Status Quo):**
    *   *Pros:* Avoids the complexities, costs, latency, and security considerations associated with external API calls. Maintains the current deterministic behavior.
    *   *Cons:* Fails to address the stated problem of limited visual understanding and brittleness. Does not advance the strategic goal of enhancing AI capabilities. Leaves the bot constrained by its current analysis methods.

## Decision Outcome

**Chosen Option:** **Option 1: Gemini for Visual Scene Description & Question Answering.**

**Justification:**
*   **Direct Enhancement of Perception:** This option directly targets the core weakness of the current system – its limited ability to understand visual content semantically. It leverages Gemini's powerful multimodal capabilities to provide richer interpretations.
*   **Feasible and Incremental Path:** It offers a practical and phased approach to integrating advanced AI. New condition types (`gemini_vision_query`) can be added to the existing `RulesEngine` without requiring an immediate, complete architectural overhaul. This allows for delivering value incrementally.
*   **Foundation for Growth:** Successfully implementing this phase builds crucial infrastructure and experience (API client, prompt management, response handling) that can be leveraged for more sophisticated AI features in subsequent phases (e.g., Gemini-informed action selection).
*   **Achieving "Freer Movement" (Phase 1):** While not full autonomy, the enhanced understanding grants the AI more "freedom" by:
    *   Allowing rules based on semantic meaning rather than brittle pixel/template matches.
    *   Enabling reactions to a wider range of visual states, including novel ones if prompts are well-designed.
    *   Reducing the need for constant profile updates due to minor UI tweaks.
*   **Balanced Approach:** Strikes a reasonable balance between the transformative potential of using a large foundation model and the practical implementation challenges (latency, cost, complexity) compared to the more ambitious Options 2 and 3.

## Clearest Path to Achieve This Goal (High-Level Steps for Initial Integration - v4.0.0 Phase 1)

1.  **Core `GeminiAnalyzer` Module (`mark_i.engines.gemini_analyzer.GeminiAnalyzer`):**
    *   Implement robust interaction using the `google-generativeai` Python SDK.
    *   Include methods like `query_vision_model(image_data: np.ndarray, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]`.
    *   Handle image preparation (NumPy BGR to PIL RGB suitable for the SDK).
    *   Handle API responses: parse text/JSON, manage errors (API errors, network issues, rate limits, content filtering), log interactions thoroughly.
    *   Initialize with API key and default model name.
2.  **API Key Management & Configuration:**
    *   Add `GEMINI_API_KEY` to `.env` file specification.
    *   `ConfigManager` loads the key from `.env`.
    *   `MainAppWindow` settings UI should indicate if the key is configured (read-only status).
    *   Add a profile setting (`settings.gemini_default_model_name`) to allow users to specify a preferred Gemini model (e.g., "gemini-1.5-flash-latest", "gemini-1.5-pro-latest"). Default to a sensible choice like Flash for cost/latency balance initially.
3.  **New Condition Type in `RulesEngine` (`gemini_vision_query`):**
    *   Define schema in JSON (see `TECHNICAL_DESIGN.MD` Section 5.1 for details):
        *   `type`: "gemini_vision_query"
        *   `region`: Optional override for rule's default region.
        *   `prompt` (str, required): Text prompt for Gemini.
        *   `expected_response_contains` (Optional, str or list[str]): Checks if Gemini's text response contains substring(s).
        *   `case_sensitive_response_check` (Optional, bool, default `False`): For `expected_response_contains`.
        *   `expected_response_json_path` (Optional, str): JSONPath expression to query if Gemini returns JSON.
        *   `expected_json_value` (Optional, any): Value expected at the JSONPath. Comparison needs type flexibility.
        *   `capture_as` (Optional, str): Variable name to store Gemini's full text response or the extracted JSON value.
        *   `model_name` (Optional, str): Override profile's default Gemini model for this specific query.
4.  **`RulesEngine` Integration:**
    *   Update `_parse_rule_analysis_dependencies`: `gemini_vision_query` does *not* add requirements for *local* pre-emptive analysis.
    *   Modify `_evaluate_single_condition_logic`:
        *   If type is `gemini_vision_query`:
            *   Get captured image for the target region.
            *   Instantiate/get `GeminiAnalyzer` instance (needs API key).
            *   Call `gemini_analyzer.query_vision_model()`.
            *   Evaluate the returned dictionary (`status`, `text_content`, `json_content`, `error_message`) based on the condition's `expected_*` parameters.
            *   Handle API call errors gracefully (condition evaluates to `False`, log error).
            *   If `capture_as` defined and condition met, store relevant response part in `rule_variable_context`.
5.  **GUI Support (`MainAppWindow` / `DetailsPanel`):**
    *   Add `gemini_vision_query` to `CONDITION_TYPES` in `gui_config.py`.
    *   Update `UI_PARAM_CONFIG` to define widgets for all `gemini_vision_query` parameters (e.g., `CTkTextbox` for multi-line `prompt`, entries for expectations, checkbox for case sensitivity, entry for `capture_as`, entry for `model_name`).
    *   Ensure `DetailsPanel._render_dynamic_parameters` correctly creates these widgets when the type is selected.
    *   Implement validation for these new fields using `gui_utils.validate_and_get_widget_value`.
6.  **Action Parameterization using Gemini-derived Bounding Boxes (Stretch Goal for Phase 1 / Target for Phase 2):**
    *   Requires prompting Gemini to reliably return bounding boxes for identified elements (likely within a JSON structure).
    *   Requires adding a new `target_relation` (e.g., `center_of_gemini_identified_element`) for click actions.
    *   Requires action parameters like `gemini_element_variable` (referencing a variable captured from a `gemini_vision_query` holding element details including bounding box).
    *   Requires `ActionExecutor` to parse this variable and calculate coordinates.
7.  **Documentation and User Guidance:**
    *   Update `README.md`, `TECHNICAL_DESIGN.MD`, `FUNCTIONAL_REQUIREMENTS.MD` (add FR for Gemini condition type), `NON_FUNCTIONAL_REQUIREMENTS.MD` (add NFRs for latency, cost, privacy, internet dependency).
    *   Provide clear instructions on setting up the Gemini API key.
    *   Explain potential costs and data privacy implications explicitly.
    *   Offer guidance and examples on effective prompt engineering for visual automation tasks.

## Consequences

*   **New Core Dependencies:** `google-generativeai` library (or chosen SDK).
*   **External Service Dependency:** Core functionality for rules using Gemini now depends on Google's API availability and performance.
*   **Cost:** Users need to manage Gemini API usage costs. Clear documentation and potentially usage warnings/limits (future feature) are important.
*   **Latency:** Gemini API calls will introduce noticeable latency (potentially seconds) into rule evaluation cycles where used. This impacts the achievable `monitoring_interval_seconds` for profiles heavily reliant on Gemini.
*   **Internet Requirement:** An active internet connection is mandatory for Gemini-powered features.
*   **API Key Security:** Secure management of the `GEMINI_API_KEY` (via `.env` and `.gitignore`) is critical.
*   **Privacy:** Users must be explicitly informed that image data from regions analyzed by Gemini conditions is sent to Google servers.
*   **Prompt Engineering Skill:** The effectiveness of Gemini conditions hinges heavily on user-written prompts. This introduces a new layer of complexity and skill requirement for configuration.
*   **Increased Code Complexity:** Adds a new engine (`GeminiAnalyzer`), modifies `RulesEngine`, `ConfigManager`, GUI components (`MainAppWindow`, `DetailsPanel`), profile schema, and requires updates across all documentation.
*   **Non-Determinism:** Introduces variability in outcomes based on the foundation model's responses.

This foundational integration sets the stage for future ADRs exploring more advanced AI-driven capabilities, such as dynamic action selection or planning based on Gemini's insights.