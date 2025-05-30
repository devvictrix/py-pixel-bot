import logging
import tkinter as tk
from typing import Optional, Dict, Any, List, Callable

import customtkinter as ctk

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.panels.condition_editor_component")


class ConditionEditorComponent(ctk.CTkFrame):
    """
    A component responsible for displaying and managing the UI for editing
    a rule's condition block (single or compound).
    This is part of the DetailsPanel refactoring.
    """

    def __init__(self, master: Any, parent_app: Any, initial_condition_data: Dict[str, Any], rule_name_for_context: str):
        super().__init__(master, fg_color="transparent")
        self.parent_app = parent_app  # MainAppWindow instance
        self.condition_data = initial_condition_data  # Store a reference or copy
        self.rule_name_for_context = rule_name_for_context
        logger.debug(f"ConditionEditorComponent: Initializing for rule '{rule_name_for_context}' with data: {self.condition_data}")

        self.grid_columnconfigure(0, weight=1)

        # --- Header for Condition Logic & Convert Button ---
        self.condition_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.condition_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ctk.CTkLabel(self.condition_header_frame, text="CONDITION LOGIC", font=ctk.CTkFont(weight="bold")).pack(side="left", anchor="w")

        is_compound_initial = "logical_operator" in self.condition_data and isinstance(self.condition_data.get("sub_conditions"), list)
        btn_convert_text_initial = "To Single Condition" if is_compound_initial else "To Compound (AND/OR)"
        self.btn_convert_condition_structure = ctk.CTkButton(
            self.condition_header_frame,
            text=btn_convert_text_initial,
            # Temporarily calls back to DetailsPanel, which then calls MainAppWindow
            command=lambda: self.master._cec_convert_condition_structure(), # master is DetailsPanel
            width=160
        )
        self.btn_convert_condition_structure.pack(side="right", padx=(0, 0))

        # --- Frame for Main Condition Editor (Single type/params OR Compound operator/sub-list) ---
        # DetailsPanel._render_rule_condition_editor_internal will populate this.
        self.main_condition_editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_condition_editor_frame.grid(row=1, column=0, sticky="new", pady=(0, 5))
        self.main_condition_editor_frame.grid_columnconfigure(1, weight=1) # For param value widgets to expand

        # --- Frame for Sub-Condition List and Buttons (Only for Compound) ---
        # This frame will be populated by DetailsPanel._render_rule_condition_editor_internal if compound.
        # It includes the sub-condition list itself and its Add/Remove buttons.
        self.sub_condition_list_outer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sub_condition_list_outer_frame.grid(row=2, column=0, sticky="new", pady=(5,0)) # Appears below main editor
        self.sub_condition_list_outer_frame.grid_columnconfigure(0, weight=1)
        # Widgets for sub-condition list (header, scrollable frame, buttons) will be created here by DetailsPanel logic.

        # --- Frame for Selected Sub-Condition's Parameters Editor ---
        # This frame will be populated by DetailsPanel._on_sub_condition_selected_internal.
        self.sub_condition_params_editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sub_condition_params_editor_frame.grid(row=3, column=0, sticky="new", pady=(5,0))
        self.sub_condition_params_editor_frame.grid_columnconfigure(1, weight=1) # For param value widgets to expand

        logger.debug(f"ConditionEditorComponent: UI frames created for rule '{self.rule_name_for_context}'.")

    def update_convert_button_text(self, is_now_compound: bool):
        """Called by DetailsPanel to update the convert button's text."""
        if hasattr(self, 'btn_convert_condition_structure') and self.btn_convert_condition_structure.winfo_exists():
            new_text = "To Single Condition" if is_now_compound else "To Compound (AND/OR)"
            self.btn_convert_condition_structure.configure(text=new_text)
            logger.debug(f"ConditionEditorComponent: Convert button text updated to '{new_text}'.")

    def get_condition_data_from_ui(self) -> Dict[str, Any]:
        """
        Gathers the condition data from the UI elements within this component.
        For this initial refactoring step, DetailsPanel still manages the actual
        data retrieval from its own widget maps. This method will be enhanced later
        when more logic moves into this component.
        For now, it might just return the initial_condition_data if it's not modified
        directly by this component yet, or signal that DetailsPanel should fetch it.
        """
        # Placeholder: In a full refactor, this would query its own widgets.
        # For now, we assume DetailsPanel pulls data from its centrally managed widgets.
        logger.warning("ConditionEditorComponent.get_condition_data_from_ui() is currently a placeholder. DetailsPanel manages data retrieval.")
        # This method will become more active as logic moves into ConditionEditorComponent.
        # It should effectively call the logic that was in DetailsPanel.get_all_rule_data_from_ui()
        # but scoped to only the condition part.

        # For now, we return the internal state, assuming DetailsPanel updates it via callbacks.
        # This is an approximation until full logic migration.
        return self.condition_data


    # Future methods to be migrated or implemented here:
    # - _internal_populate_sub_conditions_list
    # - _internal_on_sub_condition_selected
    # - _internal_render_sub_condition_params_editor
    # - _internal_add_sub_condition
    # - _internal_remove_selected_sub_condition
    # - _internal_convert_condition_structure
    # - _internal_on_condition_type_change (for single or sub-condition)