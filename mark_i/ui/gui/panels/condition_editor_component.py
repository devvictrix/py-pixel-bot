import logging
import tkinter as tk
from typing import Optional, Dict, Any, List, Callable
import copy

import customtkinter as ctk

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

from mark_i.ui.gui.gui_utils import create_clickable_list_item
from mark_i.ui.gui.gui_config import CONDITION_TYPES, LOGICAL_OPERATORS  # Changed from ALL_CONDITION_TYPES


logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.panels.condition_editor_component")


class ConditionEditorComponent(ctk.CTkFrame):
    """
    A component responsible for displaying and managing the UI for editing
    a rule's condition block (single or compound).
    This is part of the DetailsPanel refactoring.
    """

    def __init__(self, master: Any, parent_app: Any, rule_name_for_context: str):
        super().__init__(master, fg_color="transparent")
        self.details_panel_instance = master
        self.parent_app = parent_app
        self.rule_name_for_context = rule_name_for_context
        self.condition_data_model: Dict[str, Any] = {}

        logger.debug(f"ConditionEditorComponent: Initializing for rule '{self.rule_name_for_context}'.")

        self.grid_columnconfigure(0, weight=1)

        self.condition_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.condition_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ctk.CTkLabel(self.condition_header_frame, text="CONDITION LOGIC", font=ctk.CTkFont(weight="bold")).pack(side="left", anchor="w")
        self.btn_convert_condition_structure = ctk.CTkButton(self.condition_header_frame, text="Convert", command=lambda: self.details_panel_instance._cec_convert_condition_structure(), width=160)
        self.btn_convert_condition_structure.pack(side="right", padx=(0, 0))

        self.main_condition_editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_condition_editor_frame.grid(row=1, column=0, sticky="new", pady=(0, 5))
        self.main_condition_editor_frame.grid_columnconfigure(1, weight=1)

        self.sub_condition_list_outer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sub_condition_list_outer_frame.grid(row=2, column=0, sticky="new", pady=(5, 0))
        self.sub_condition_list_outer_frame.grid_columnconfigure(0, weight=1)

        self.sub_condition_params_editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sub_condition_params_editor_frame.grid(row=3, column=0, sticky="new", pady=(5, 0))
        self.sub_condition_params_editor_frame.grid_columnconfigure(1, weight=1)

        self.sub_conditions_scroll_frame: Optional[ctk.CTkScrollableFrame] = None
        self.btn_add_sub_condition: Optional[ctk.CTkButton] = None
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None
        self.selected_sub_condition_item_widget_cec: Optional[ctk.CTkFrame] = None

        logger.debug(f"ConditionEditorComponent: UI frames created for rule '{self.rule_name_for_context}'.")

    def update_ui_with_condition_data(self, condition_data: Dict[str, Any]):
        self.condition_data_model = copy.deepcopy(condition_data)
        logger.debug(f"CEC: Updating UI with data: {self.condition_data_model}")

        for frame in [self.main_condition_editor_frame, self.sub_condition_list_outer_frame, self.sub_condition_params_editor_frame]:
            for widget in frame.winfo_children():
                widget.destroy()
        self.sub_conditions_scroll_frame = None
        self.btn_add_sub_condition = None
        self.btn_remove_sub_condition = None
        self.selected_sub_condition_item_widget_cec = None

        is_compound = "logical_operator" in self.condition_data_model and isinstance(self.condition_data_model.get("sub_conditions"), list)
        self.update_convert_button_text(is_compound)

        if is_compound:
            self._render_compound_condition_ui_elements(self.condition_data_model)
        else:
            self._render_single_condition_ui_elements(self.condition_data_model)

    def _render_single_condition_ui_elements(self, single_condition_data: Dict[str, Any]):
        target_frame = self.main_condition_editor_frame
        ctk.CTkLabel(target_frame, text="Condition Type:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        current_type = str(single_condition_data.get("type", "always_true"))
        type_var = ctk.StringVar(value=current_type)
        type_menu = ctk.CTkOptionMenu(
            target_frame, variable=type_var, values=CONDITION_TYPES, command=lambda choice: self.details_panel_instance._cec_on_condition_type_change("condition", choice)
        )  # Corrected: CONDITION_TYPES
        type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.details_panel_instance.detail_optionmenu_vars["condition_type_var"] = type_var
        self.details_panel_instance.detail_widgets["condition_type"] = type_menu

        self.details_panel_instance._render_dynamic_parameters("conditions", current_type, single_condition_data, target_frame, 1, "cond_")
        logger.debug(f"CEC: Rendered single condition editor (type: {current_type}).")

    def _render_compound_condition_ui_elements(self, compound_condition_data: Dict[str, Any]):
        op_target_frame = self.main_condition_editor_frame
        ctk.CTkLabel(op_target_frame, text="Logical Operator:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        log_op_var = ctk.StringVar(value=str(compound_condition_data.get("logical_operator", "AND")))
        op_menu = ctk.CTkOptionMenu(op_target_frame, variable=log_op_var, values=LOGICAL_OPERATORS, command=lambda c: self.parent_app._set_dirty_status(True))
        op_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.details_panel_instance.detail_optionmenu_vars["logical_operator_var"] = log_op_var
        self.details_panel_instance.detail_widgets["logical_operator"] = op_menu

        list_target_frame = self.sub_condition_list_outer_frame
        sc_header_frame = ctk.CTkFrame(list_target_frame, fg_color="transparent")
        sc_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        ctk.CTkLabel(sc_header_frame, text="Sub-Conditions:", font=ctk.CTkFont(size=12)).pack(side="left", padx=0)

        self.btn_remove_sub_condition = ctk.CTkButton(sc_header_frame, text="- Remove Sel.", width=100, command=self._remove_selected_sub_condition_action, state="disabled")
        self.btn_remove_sub_condition.pack(side="right", padx=(2, 0))
        self.btn_add_sub_condition = ctk.CTkButton(sc_header_frame, text="+ Add New", width=80, command=self._add_new_sub_condition_action)
        self.btn_add_sub_condition.pack(side="right", padx=(0, 0))

        self.sub_conditions_scroll_frame = ctk.CTkScrollableFrame(list_target_frame, label_text="", height=120, fg_color=("gray90", "gray20"))
        self.sub_conditions_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=2)
        self._populate_sub_conditions_list(compound_condition_data.get("sub_conditions", []))

        self._render_selected_sub_condition_editor()
        logger.debug(f"CEC: Rendered compound condition editor (operator: {log_op_var.get()}).")

    def _populate_sub_conditions_list(self, sub_conditions_data: List[Dict[str, Any]]):
        if not self.sub_conditions_scroll_frame:
            logger.error("CEC: sub_conditions_scroll_frame not initialized for populating list.")
            return
        for w in self.sub_conditions_scroll_frame.winfo_children():
            w.destroy()
        self.selected_sub_condition_item_widget_cec = None

        current_selected_idx_in_parent = self.parent_app.selected_sub_condition_index
        remove_btn_state = "normal" if current_selected_idx_in_parent is not None and sub_conditions_data else "disabled"
        if self.btn_remove_sub_condition:
            self.btn_remove_sub_condition.configure(state=remove_btn_state)

        for i, sub_cond_item_data in enumerate(sub_conditions_data):
            s_type = sub_cond_item_data.get("type", "N/A")
            s_rgn = f",Rgn:{sub_cond_item_data.get('region')}" if sub_cond_item_data.get("region") else ""
            s_cap = f",Var:{sub_cond_item_data.get('capture_as')}" if sub_cond_item_data.get("capture_as") else ""
            sum_txt = f"#{i+1}: {s_type}{s_rgn}{s_cap}"
            sum_txt = sum_txt[:45] + "..." if len(sum_txt) > 48 else sum_txt
            item_fr_ref = {}
            item_ui_frame = create_clickable_list_item(
                self.sub_conditions_scroll_frame,
                sum_txt,
                lambda e=None, scd=copy.deepcopy(sub_cond_item_data), idx=i, ifr_cb_ref=item_fr_ref: self._on_sub_condition_selected(scd, idx, ifr_cb_ref.get("frame")),
            )
            item_fr_ref["frame"] = item_ui_frame
            if i == current_selected_idx_in_parent:
                self._highlight_cec_sub_condition_item(item_ui_frame)
                self.selected_sub_condition_item_widget_cec = item_ui_frame
        logger.debug(f"CEC: Populated sub-conditions list with {len(sub_conditions_data)} items.")

    def _on_sub_condition_selected(self, sub_cond_data: Dict[str, Any], new_idx: int, item_frame_widget: Optional[ctk.CTkFrame]):
        if item_frame_widget is None:
            logger.warning("CEC: Sub-condition item_frame is None in selection callback.")
            return
        logger.debug(f"CEC: Sub-condition #{new_idx + 1} selected. Data: {sub_cond_data}")

        self.parent_app.selected_sub_condition_index = new_idx
        self._highlight_cec_sub_condition_item(item_frame_widget)
        self.selected_sub_condition_item_widget_cec = item_frame_widget
        if self.btn_remove_sub_condition:
            self.btn_remove_sub_condition.configure(state="normal")

        self.details_panel_instance._cec_render_sub_condition_params_editor(sub_cond_data, new_idx)

    def _render_selected_sub_condition_editor(self):
        target_editor_frame = self.sub_condition_params_editor_frame
        for w in target_editor_frame.winfo_children():
            w.destroy()

        selected_idx = self.parent_app.selected_sub_condition_index
        sub_conditions = self.condition_data_model.get("sub_conditions", [])

        if selected_idx is not None and 0 <= selected_idx < len(sub_conditions):
            sub_cond_to_edit = sub_conditions[selected_idx]
            current_type = str(sub_cond_to_edit.get("type", "always_true"))

            ctk.CTkLabel(target_editor_frame, text=f"Editing Sub-Condition #{selected_idx+1} / Type:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 5), pady=(5, 2), sticky="w")
            type_var = ctk.StringVar(value=current_type)
            type_menu = ctk.CTkOptionMenu(
                target_editor_frame,
                variable=type_var,
                values=CONDITION_TYPES,  # Corrected: CONDITION_TYPES
                command=lambda choice: self.details_panel_instance._cec_on_condition_type_change("condition", choice),
            )
            type_menu.grid(row=0, column=1, padx=5, pady=(5, 2), sticky="ew")
            self.details_panel_instance.detail_optionmenu_vars["subcond_condition_type_var"] = type_var
            self.details_panel_instance.detail_widgets["subcond_condition_type"] = type_menu

            self.details_panel_instance._render_dynamic_parameters("conditions", current_type, sub_cond_to_edit, target_editor_frame, 1, "subcond_")
        else:
            ctk.CTkLabel(target_editor_frame, text="Select a sub-condition above to edit its parameters.").pack(padx=5, pady=5)
        logger.debug(f"CEC: Rendered/cleared selected sub-condition editor. Selected index: {selected_idx}")

    def _highlight_cec_sub_condition_item(self, new_selected_widget_frame: Optional[ctk.CTkFrame]):
        if self.selected_sub_condition_item_widget_cec and self.selected_sub_condition_item_widget_cec.winfo_exists():
            self.selected_sub_condition_item_widget_cec.configure(fg_color="transparent")

        if new_selected_widget_frame and new_selected_widget_frame.winfo_exists():
            try:
                hl_colors = ctk.ThemeManager.theme["CTkButton"]["hover_color"]
                hl_color = hl_colors[0] if isinstance(hl_colors, tuple) and ctk.get_appearance_mode().lower() == "light" else (hl_colors[1] if isinstance(hl_colors, tuple) else hl_colors)
            except Exception:
                hl_color = "#565b5e"
            new_selected_widget_frame.configure(fg_color=hl_color)
            self.selected_sub_condition_item_widget_cec = new_selected_widget_frame
        else:
            self.selected_sub_condition_item_widget_cec = None

    def _add_new_sub_condition_action(self):
        logger.debug("CEC: Add New Sub-Condition button clicked.")
        self.details_panel_instance._cec_add_sub_condition()

    def _remove_selected_sub_condition_action(self):
        logger.debug("CEC: Remove Selected Sub-Condition button clicked.")
        if self.parent_app.selected_sub_condition_index is None:
            messagebox.showinfo("No Selection", "Please select a sub-condition to remove.", parent=self)
            return
        self.details_panel_instance._cec_remove_selected_sub_condition()

    def update_convert_button_text(self, is_now_compound: bool):
        if hasattr(self, "btn_convert_condition_structure") and self.btn_convert_condition_structure.winfo_exists():
            new_text = "To Single Condition" if is_now_compound else "To Compound (AND/OR)"
            self.btn_convert_condition_structure.configure(text=new_text)
            logger.debug(f"CEC: Convert button text updated to '{new_text}'.")

    def get_condition_data_from_ui(self) -> Dict[str, Any]:
        logger.warning("CEC.get_condition_data_from_ui() is not fully self-contained yet.")
        return self.condition_data_model
