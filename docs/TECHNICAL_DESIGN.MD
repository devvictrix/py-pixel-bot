# Technical Design Document

This document outlines the technical design and architectural considerations for the visual automation tool. It reflects decisions made in the Architectural Decision Records (ADRs) and current implementation status. As of the last update, AI-Accelerated v1.0.0 and v2.0.0 (Advanced Visual Analysis & Rules) are complete. Development for v3.0.0 (Enhanced GUI & Usability) is now underway, with Phase 1.8.1 (GUI Input Validation & Refinements) of the Full GUI being the current focus.

## 1. Core Architecture
...
(Existing content)
...

## 9. Full GUI Architecture (v3.0.0+) (`MainAppWindow` using `CustomTkinter`)
    (This section details the GUI's structure, components, and core logic as implemented up to Phase 1.8.1, focusing on profile management, settings, region/template/rule list displays, and the dynamic detail panel for interactive editing of selected items, including parameters for conditions, actions, and sub-conditions, plus condition structure conversion and input validation.)

### 9.1. Overview and Goals
    (Provide a comprehensive, user-friendly GUI for all profile configuration tasks, minimizing direct JSON editing. Phase 1.X focuses on core editing layout, file operations, item management, parameter editing, and input validation.)

### 9.2. Main Application Window (`MainAppWindow`)
    (`customtkinter.CTk` based. Manages UI layout, menu actions, interaction with `ConfigManager`, internal `profile_data` state, dirty flag, and coordinates updates between various UI panels and the data model.)

### 9.3. GUI Layout and Components
    (Three-panel layout: Left [Profile Info, Regions, Templates], Center [Rules List], Right [Scrollable Details Panel]. Uses `CTkFrame`, `CTkScrollableFrame`, `CTkEntry`, `CTkButton`, `CTkLabel`, `CTkOptionMenu`, `CTkCheckBox`, `CTkTextbox`, `tkinter.Menu`, `tkinter.filedialog`, `tkinter.messagebox`. Template previews use `Pillow` and `CTkImage`.)
    Regions are managed in the left panel. Adding a new region or editing the coordinates of an existing region invokes the `RegionSelectorWindow`.

### 9.4. Core Functionality Logic (in `MainAppWindow`)
    *   File Operations: `_new_profile`, `_open_profile` (loads via `ConfigManager`), `_save_profile` (updates internal data from UI, saves via `ConfigManager`), `_save_profile_as`.
    *   UI Data Sync: `_populate_ui_from_profile_data` (renders UI from `profile_data`), `_update_profile_data_from_ui` (syncs basic settings from UI to `profile_data`; list items like rules are modified more directly in `profile_data` by their respective "Apply" logic).
    *   State Management: `_is_dirty` flag, `_set_dirty_status` (updates window title with "*"), `_prompt_save_if_dirty`.
    *   Item Selection: `_on_item_selected` (handles list clicks), `_highlight_selected_list_item`, updates detail panel via `_update_details_panel`.
    *   Detail Panel Rendering (`_update_details_panel`): Dynamically builds UI for selected region, template, or rule.
        *   **Regions:** Editable fields for name, x, y, width, height. Buttons for "Apply Changes", "Edit Coords via Selector".
        *   **Templates:** Editable name, read-only filename, image preview. Button for "Apply Changes".
        *   **Rules:** Editable name, default region. "Convert Condition Structure" button. Sections for Condition and Action.
            *   **Condition Editor (`_render_rule_condition_editor`):** If single, shows type dropdown and calls `_render_condition_parameters`. If compound, shows operator dropdown, sub-condition list (items call `_on_sub_condition_selected`), and a frame for selected sub-condition's parameters (`sub_condition_params_frame`).
            *   **Action Editor:** Shows type dropdown and calls `_render_action_parameters`.
    *   Parameter Rendering (`_render_condition_parameters`, `_render_action_parameters`): Dynamically create input widgets (`CTkEntry`, `CTkOptionMenu`, `CTkCheckBox`, `CTkTextbox`) based on condition/action type. Populate from data, store widget refs in `self.detail_widgets`, bind to dirty flag.
    *   Parameter Collection (`_get_condition_parameters_from_ui`, `_get_action_parameters_from_ui`): Retrieve values from dynamic widgets using `_validate_and_get_widget_value`, perform type conversion/validation.
    *   Input Validation (`_validate_and_get_widget_value`, `_parse_bgr_string`): Centralized helpers for type checking, range validation, non-empty checks, BGR string parsing. Show `messagebox.showerror` on failure.
    *   "Apply" Methods (`_apply_region_changes`, `_apply_template_changes`, `_apply_rule_changes`): Use validation helpers. If all valid, update `self.profile_data`, set dirty, refresh relevant UI list, re-display details.
    *   List Management: Methods for adding (placeholders or via dialogs like `RegionSelectorWindow`, template file copy) and removing items from regions, templates, rules, sub-conditions, updating `profile_data` and UI.

### 9.5. CLI Integration for GUI Editor
    (CLI command `edit [profile_path]` instantiates and runs `MainAppWindow`.)

### 9.6. Logging for GUI Operations
    (INFO for major user actions, DEBUG for UI state/rendering, WARNING/ERROR for validation failures or operational errors.)

### 9.7. Region Definition and Management Workflow
    This section details the user experience and technical flow for defining and managing screen regions within the application.

    *   **Representation:** Regions are defined by a unique `name`, and integer coordinates `x`, `y`, `width`, and `height`. These are stored in the `regions` list within the JSON profile.
    *   **Listing in `MainAppWindow`:** The left panel of `MainAppWindow` displays a scrollable list of currently defined regions for the active profile. Each item shows the region's name.
    *   **Adding a New Region:**
        1.  The user clicks the "Add" button below the regions list in `MainAppWindow`.
        2.  The profile must be saved first (or saved as a new file if untitled). `MainAppWindow` prompts the user if necessary.
        3.  The `RegionSelectorWindow` is invoked. This is a modal, fullscreen, semi-transparent window.
        4.  The user clicks and drags on their screen to draw a rectangle.
        5.  Upon releasing the mouse, the user presses "Enter".
        6.  A `CTkInputDialog` appears, prompting for a unique name for the new region. The dialog also displays the selected coordinates (x, y, w, h).
        7.  If a valid, unique name is provided, the region data is saved to the currently open profile by `ConfigManager`, and `RegionSelectorWindow` closes.
        8.  `MainAppWindow` reloads the profile (if changes were made directly by `RegionSelectorWindow`) or updates its internal data and refreshes the regions list.
    *   **Editing an Existing Region's Properties (from `MainAppWindow` Details Panel):**
        1.  The user selects a region from the list in `MainAppWindow`.
        2.  The right-hand "Details Panel" populates with the selected region's properties: Name, X, Y, Width, Height (in `CTkEntry` widgets).
        3.  **Name/Coordinate Text Entry:** The user can directly edit these text fields. Input validation (e.g., for unique name, positive width/height, integer coordinates) is performed when "Apply Changes" is clicked.
        4.  **"Edit Coords via Selector" Button:**
            *   If clicked, the profile is saved (if dirty, with prompt).
            *   `RegionSelectorWindow` is invoked, pre-drawing the existing rectangle for that region.
            *   The user can redraw the rectangle or press "Enter" to keep the current one.
            *   The naming dialog appears, pre-filled with the region's current name. The user can confirm or change the name.
            *   Upon confirmation, the profile is updated by `RegionSelectorWindow`'s `ConfigManager`, and `MainAppWindow` reloads/refreshes.
    *   **Removing a Region:**
        1.  User selects a region from the list.
        2.  User clicks the "Remove" button.
        3.  The region is removed from the `profile_data` in `MainAppWindow`.
        4.  The UI list is refreshed. The profile is marked as dirty.
    *   **Assigning Regions to Rules/Conditions:**
        *   **Default Rule Region:** In the rule's details view (center panel in `MainAppWindow`), a dropdown menu lists all defined region names (plus an empty option for no default). The user selects a region from this list to set it as the default context for the rule's conditions.
        *   **Sub-Condition Specific Region:** When editing a sub-condition (if the rule has a compound condition), the sub-condition's parameter editor includes a similar dropdown menu. This allows a sub-condition to operate on a different region than the rule's default or other sub-conditions. If left empty, it inherits the rule's default region.
    *   **`RegionSelectorWindow` Technical Details:**
        *   Uses `ImageGrab.grab(all_screens=True)` to capture the screen content for its background (if successful). The canvas is sized to the captured image (potentially virtual desktop).
        *   The window itself is fullscreen on the primary monitor with `attributes("-fullscreen", True)`.
        *   Drawing is done using absolute screen coordinates (`event.x_root`, `event.y_root`) on the canvas.
        *   An instruction label is centered on the primary screen using `self.winfo_screenwidth()/2` for its x-placement.
        *   Handles Escape key for cancellation and Enter key for confirmation (which then shows the naming dialog).