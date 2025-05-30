import logging
import tkinter as tk
from tkinter import messagebox  # For error/info popups
import os
import copy
from typing import Optional, Dict, Any, List, Union, Callable

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError, ImageFont

from mark_i.ui.gui.gui_config import (
    UI_PARAM_CONFIG,
    OPTIONS_CONST_MAP,
    MAX_PREVIEW_WIDTH,
    MAX_PREVIEW_HEIGHT,
    ALL_CONDITION_TYPES,
    ALL_ACTION_TYPES,
    LOGICAL_OPERATORS,
)
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value, create_clickable_list_item
# NEW IMPORT for ConditionEditorComponent
from mark_i.ui.gui.panels.condition_editor_component import ConditionEditorComponent

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.panels.details_panel")


class DetailsPanel(ctk.CTkScrollableFrame):
    """
    A CTkScrollableFrame that dynamically displays and allows editing of details
    for a selected item (Region, Template, or Rule) from the MainAppWindow.
    It uses UI_PARAM_CONFIG from gui_config.py to render appropriate input widgets
    and handles conditional visibility of parameters.
    For rules, it now uses ConditionEditorComponent for the condition part.
    """

    def __init__(self, master: Any, parent_app: Any, **kwargs):
        super().__init__(master, label_text="Selected Item Details", **kwargs)
        self.parent_app = parent_app

        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        self.detail_optionmenu_vars: Dict[str, Union[tk.StringVar, tk.BooleanVar]] = {}
        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        self.content_frame.grid_columnconfigure(1, weight=1)

        self.label_placeholder = ctk.CTkLabel(
            self.content_frame,
            text="Select an item from the lists (Regions, Templates, Rules)\n to see or edit its details here.",
            wraplength=380,
            justify="center",
            font=ctk.CTkFont(size=14),
        )
        self.label_placeholder.pack(padx=20, pady=30, anchor="center", expand=True)

        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        # self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None # Now managed by ConditionEditorComponent
        # self.condition_params_frame: Optional[ctk.CTkFrame] = None # Now part of ConditionEditorComponent
        self.action_params_frame: Optional[ctk.CTkFrame] = None
        # self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None # Now managed by ConditionEditorComponent

        # self.btn_convert_condition: Optional[ctk.CTkButton] = None # Now in ConditionEditorComponent
        # self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None # Now in ConditionEditorComponent

        # NEW: Instance of ConditionEditorComponent for rule display
        self.condition_editor_component_instance: Optional[ConditionEditorComponent] = None

        logger.debug("DetailsPanel initialized.")

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        self.detail_widgets.clear()
        self.detail_optionmenu_vars.clear()

        self.template_preview_image_label = None
        # self.sub_conditions_list_frame = None # Managed by CEC
        # self.condition_params_frame = None # Managed by CEC
        self.action_params_frame = None
        # self.sub_condition_params_frame = None # Managed by CEC
        # self.btn_convert_condition = None # Managed by CEC
        # self.btn_remove_sub_condition = None # Managed by CEC
        self.selected_sub_condition_item_widget = None

        if self.condition_editor_component_instance:
            self.condition_editor_component_instance.destroy() # Ensure it's destroyed
            self.condition_editor_component_instance = None

        logger.debug("DetailsPanel content cleared and widget stores reset.")

    def update_display(self, item_data: Optional[Dict[str, Any]], item_type: str):
        self.clear_content()

        if item_data is None or item_type == "none":
            self.label_placeholder = ctk.CTkLabel(self.content_frame, text="Select an item from the lists to see or edit its details.", wraplength=380, justify="center", font=ctk.CTkFont(size=14))
            self.label_placeholder.pack(padx=20, pady=30, anchor="center", expand=True)
            logger.debug(f"DetailsPanel display updated: Showing placeholder as item_type is '{item_type}'.")
            return

        logger.info(f"DetailsPanel: Updating display for item_type '{item_type}', name: '{item_data.get('name', 'N/A')}'")
        self.content_frame.grid_columnconfigure(1, weight=1)

        if item_type == "region":
            self._display_region_details(item_data)
        elif item_type == "template":
            self._display_template_details(item_data)
        elif item_type == "rule":
            self._display_rule_details(item_data)
        else:
            logger.warning(f"DetailsPanel: Unknown item_type '{item_type}' in update_display.")
            ctk.CTkLabel(self.content_frame, text=f"Cannot display details for unknown item type: '{item_type}'.", wraplength=380).pack(padx=10, pady=20, anchor="center", expand=True)

    def _display_region_details(self, region_data: Dict[str, Any]):
        # This method remains largely the same as before
        logger.debug(f"Displaying region details for: {region_data.get('name', 'Unnamed Region')}")
        self.content_frame.grid_columnconfigure(1, weight=1)
        row_idx = 0
        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        name_e = ctk.CTkEntry(self.content_frame, placeholder_text="Unique region name")
        name_e.insert(0, str(region_data.get("name", "")))
        name_e.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        name_e.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["name"] = name_e
        row_idx += 1
        coords_map = {"x": 0, "y": 0, "width": 100, "height": 100}
        for key, def_val in coords_map.items():
            ctk.CTkLabel(self.content_frame, text=f"{key.capitalize()}:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
            entry_c = ctk.CTkEntry(self.content_frame, placeholder_text=f"Enter {key}")
            entry_c.insert(0, str(region_data.get(key, def_val)))
            entry_c.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
            entry_c.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
            self.detail_widgets[key] = entry_c
            row_idx += 1
        ctk.CTkLabel(self.content_frame, text="Comment:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="nw")
        comment_tb = ctk.CTkTextbox(self.content_frame, height=60, wrap="word")
        comment_tb.insert("0.0", str(region_data.get("comment", "")))
        comment_tb.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        comment_tb.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["comment"] = comment_tb
        row_idx += 1
        btn_fr = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_fr.grid(row=row_idx, column=0, columnspan=2, pady=(15, 10), padx=10, sticky="ew")
        btn_fr.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btn_fr, text="Apply Region Changes", command=self.parent_app._apply_region_changes).grid(row=0, column=0, padx=(0, 5), sticky="e")
        ctk.CTkButton(btn_fr, text="Edit Coords (Selector)", command=self.parent_app._edit_region_coordinates_with_selector).grid(row=0, column=1, padx=(5, 0), sticky="w")

    def _display_template_details(self, template_data: Dict[str, Any]):
        # This method remains largely the same as before
        logger.debug(f"Displaying template details for: {template_data.get('name', 'Unnamed Template')}")
        self.content_frame.grid_columnconfigure(1, weight=1)
        row_idx = 0
        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        name_e = ctk.CTkEntry(self.content_frame, placeholder_text="Unique template name")
        name_e.insert(0, str(template_data.get("name", "")))
        name_e.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        name_e.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["template_name"] = name_e
        row_idx += 1
        ctk.CTkLabel(self.content_frame, text="Filename:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        ctk.CTkLabel(self.content_frame, text=str(template_data.get("filename", "N/A")), anchor="w").grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        row_idx += 1
        ctk.CTkLabel(self.content_frame, text="Comment:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="nw")
        comment_tb = ctk.CTkTextbox(self.content_frame, height=60, wrap="word")
        comment_tb.insert("0.0", str(template_data.get("comment", "")))
        comment_tb.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        comment_tb.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["comment"] = comment_tb
        row_idx += 1
        ctk.CTkLabel(self.content_frame, text="Preview:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="nw")
        self.template_preview_image_label = ctk.CTkLabel(self.content_frame, text="Loading preview...", width=MAX_PREVIEW_WIDTH, height=MAX_PREVIEW_HEIGHT, anchor="w")
        self.template_preview_image_label.grid(row=row_idx, column=1, padx=5, pady=5, sticky="w")
        row_idx += 1
        self._update_template_preview_image(template_data.get("filename"))
        ctk.CTkButton(self.content_frame, text="Apply Template Changes", command=self.parent_app._apply_template_changes).grid(row=row_idx, column=0, columnspan=2, pady=(15, 10), padx=10)

    def _update_template_preview_image(self, filename: Optional[str]):
        # This method remains the same
        if not self.template_preview_image_label:
            return
        if not filename or not self.parent_app.current_profile_path:
            self.template_preview_image_label.configure(image=None, text="No preview (profile unsaved or no filename).")
            return
        template_path = self.parent_app.config_manager.get_template_image_path(filename)
        if template_path and os.path.exists(template_path):
            try:
                img = Image.open(template_path)
                img_copy = img.copy()
                img_copy.thumbnail((MAX_PREVIEW_WIDTH, MAX_PREVIEW_HEIGHT), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=(img_copy.width, img_copy.height))
                self.template_preview_image_label.configure(image=ctk_img, text="")
            except UnidentifiedImageError:
                self.template_preview_image_label.configure(image=None, text=f"Error: Not an image\n{filename}")
            except Exception as e:
                self.template_preview_image_label.configure(image=None, text=f"Error loading preview:\n{filename}")
        else:
            self.template_preview_image_label.configure(image=None, text=f"File not found:\n{filename}")

    def _display_rule_details(self, rule_data: Dict[str, Any]):
        logger.debug(f"DetailsPanel: Displaying rule details for: {rule_data.get('name', 'Unnamed Rule')}")
        self.parent_app.selected_sub_condition_index = None # Reset sub-condition selection
        self.content_frame.grid_columnconfigure(1, weight=1)
        current_master_row = 0

        # Rule Name
        ctk.CTkLabel(self.content_frame, text="Rule Name:").grid(row=current_master_row, column=0, sticky="w", padx=(10, 5), pady=2)
        name_e = ctk.CTkEntry(self.content_frame, placeholder_text="Unique rule name")
        name_e.insert(0, rule_data.get("name", ""))
        name_e.grid(row=current_master_row, column=1, sticky="ew", padx=5, pady=2)
        name_e.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["rule_name"] = name_e
        current_master_row += 1

        # Rule Default Region
        ctk.CTkLabel(self.content_frame, text="Default Region:").grid(row=current_master_row, column=0, sticky="w", padx=(10, 5), pady=2)
        regions = [""] + [r.get("name", "") for r in self.parent_app.profile_data.get("regions", []) if r.get("name")]
        var_region = ctk.StringVar(value=str(rule_data.get("region", "")))
        menu_region = ctk.CTkOptionMenu(self.content_frame, variable=var_region, values=regions, command=lambda c: self.parent_app._set_dirty_status(True))
        menu_region.grid(row=current_master_row, column=1, sticky="ew", padx=5, pady=2)
        self.detail_optionmenu_vars["rule_region_var"] = var_region
        self.detail_widgets["rule_region"] = menu_region
        current_master_row += 1

        # Rule Comment
        ctk.CTkLabel(self.content_frame, text="Comment (Rule):").grid(row=current_master_row, column=0, padx=(10, 5), pady=5, sticky="nw")
        rule_comment_tb = ctk.CTkTextbox(self.content_frame, height=40, wrap="word")
        rule_comment_tb.insert("0.0", str(rule_data.get("comment", "")))
        rule_comment_tb.grid(row=current_master_row, column=1, padx=5, pady=5, sticky="ew")
        rule_comment_tb.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["rule_comment"] = rule_comment_tb
        current_master_row += 1

        # --- Condition Section (using ConditionEditorComponent) ---
        cond_data_for_editor = copy.deepcopy(rule_data.get("condition", {"type": "always_true"}))
        self.condition_editor_component_instance = ConditionEditorComponent(
            self.content_frame,
            parent_app=self.parent_app, # Pass MainAppWindow instance
            initial_condition_data=cond_data_for_editor,
            rule_name_for_context=rule_data.get("name", "UnnamedRule")
        )
        self.condition_editor_component_instance.grid(row=current_master_row, column=0, columnspan=2, sticky="new", pady=(10, 5), padx=0)
        current_master_row += 1
        # Populate the ConditionEditorComponent using the existing DetailsPanel logic
        self._render_rule_condition_editor_internal(cond_data_for_editor)


        # --- Action Section ---
        act_data = copy.deepcopy(rule_data.get("action", {"type": "log_message"}))
        act_outer_fr = ctk.CTkFrame(self.content_frame) # Not self.content_frame directly
        act_outer_fr.grid(row=current_master_row, column=0, columnspan=2, sticky="new", pady=(10, 5), padx=5)
        act_outer_fr.grid_columnconfigure(0, weight=1)
        current_master_row += 1
        ctk.CTkLabel(act_outer_fr, text="ACTION TO PERFORM", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=0)
        self.action_params_frame = ctk.CTkFrame(act_outer_fr, fg_color="transparent")
        self.action_params_frame.pack(fill="x", expand=True, padx=0, pady=(0, 5))
        self.action_params_frame.grid_columnconfigure(1, weight=1) # Ensure value column expands

        ctk.CTkLabel(self.action_params_frame, text="Action Type:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        init_act_type = str(act_data.get("type", "log_message"))
        var_act_type = ctk.StringVar(value=init_act_type)
        menu_act_type = ctk.CTkOptionMenu(self.action_params_frame, variable=var_act_type, values=ALL_ACTION_TYPES, command=lambda choice: self.parent_app._on_rule_part_type_change("action", choice))
        menu_act_type.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.detail_optionmenu_vars["action_type_var"] = var_act_type
        self.detail_widgets["action_type"] = menu_act_type
        self._render_dynamic_parameters("actions", init_act_type, act_data, self.action_params_frame, start_row=1, widget_prefix="act_")

        # Apply All Rule Changes Button
        ctk.CTkButton(self.content_frame, text="Apply All Rule Changes", command=self.parent_app._apply_rule_changes, height=35, font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=current_master_row, column=0, columnspan=2, pady=(20, 10), padx=10, sticky="ew"
        )

    def _render_rule_condition_editor_internal(self, condition_data_to_display: Dict[str, Any]):
        """
        Renders the condition editor UI elements into the frames provided by
        self.condition_editor_component_instance.
        This method is called by _display_rule_details.
        """
        if not self.condition_editor_component_instance:
            logger.error("DP: ConditionEditorComponent instance not available for rendering rule condition editor.")
            return

        # Clear any previous content in the component's frames
        for frame in [
            self.condition_editor_component_instance.main_condition_editor_frame,
            self.condition_editor_component_instance.sub_condition_list_outer_frame,
            self.condition_editor_component_instance.sub_condition_params_editor_frame
        ]:
            for w in frame.winfo_children():
                w.destroy()

        # Target frames within the ConditionEditorComponent
        main_cond_editor_target_frame = self.condition_editor_component_instance.main_condition_editor_frame
        sub_cond_list_target_frame = self.condition_editor_component_instance.sub_condition_list_outer_frame
        sub_cond_params_target_frame = self.condition_editor_component_instance.sub_condition_params_editor_frame

        is_compound = "logical_operator" in condition_data_to_display and isinstance(condition_data_to_display.get("sub_conditions"), list)
        self.condition_editor_component_instance.update_convert_button_text(is_compound)

        if is_compound:
            # Setup for Compound Condition in CEC's main_condition_editor_frame
            ctk.CTkLabel(main_cond_editor_target_frame, text="Logical Operator:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
            var_log_op = ctk.StringVar(value=str(condition_data_to_display.get("logical_operator", "AND")))
            op_menu = ctk.CTkOptionMenu(main_cond_editor_target_frame, variable=var_log_op, values=LOGICAL_OPERATORS, command=lambda c: self.parent_app._set_dirty_status(True))
            op_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self.detail_optionmenu_vars["logical_operator_var"] = var_log_op # Stored in DetailsPanel
            self.detail_widgets["logical_operator"] = op_menu # Stored in DetailsPanel

            # Setup sub-condition list UI within CEC's sub_condition_list_outer_frame
            sc_hdr = ctk.CTkFrame(sub_cond_list_target_frame, fg_color="transparent")
            sc_hdr.grid(row=0, column=0, sticky="ew", pady=(0, 2))
            ctk.CTkLabel(sc_hdr, text="Sub-Conditions:", font=ctk.CTkFont(size=12)).pack(side="left", padx=0)
            # Buttons are created by CEC, but commands call temporary dispatchers in DetailsPanel
            # CEC's buttons will call:
            # self.master._cec_remove_selected_sub_condition()
            # self.master._cec_add_sub_condition()
            # (These buttons are created in CEC's __init__)

            # The scrollable frame for sub-conditions is now WITHIN CEC, but populated by DP
            cec_sub_list_scroll_frame = ctk.CTkScrollableFrame(sub_cond_list_target_frame, label_text="", height=120, fg_color=("gray90", "gray20"))
            cec_sub_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=2)
            # Store reference for _populate_sub_conditions_list_internal
            self._current_cec_sub_list_frame_ref = cec_sub_list_scroll_frame
            self._populate_sub_conditions_list_internal(condition_data_to_display.get("sub_conditions", []))

            # Placeholder/editor for selected sub-condition's params in CEC's sub_condition_params_editor_frame
            if self.parent_app.selected_sub_condition_index is None:
                ctk.CTkLabel(sub_cond_params_target_frame, text="Select a sub-condition above to edit its parameters.").pack(padx=5, pady=5)
            else:
                sub_conds = condition_data_to_display.get("sub_conditions", [])
                if 0 <= self.parent_app.selected_sub_condition_index < len(sub_conds):
                    self._on_sub_condition_selected_internal(
                        sub_conds[self.parent_app.selected_sub_condition_index],
                        self.parent_app.selected_sub_condition_index,
                        self.selected_sub_condition_item_widget # This widget is in CEC's list
                    )
        else:  # Single condition - render in CEC's main_condition_editor_frame
            ctk.CTkLabel(main_cond_editor_target_frame, text="Condition Type:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
            curr_cond_type = str(condition_data_to_display.get("type", "always_true"))
            var_cond_type = ctk.StringVar(value=curr_cond_type)
            menu_cond_type = ctk.CTkOptionMenu(
                main_cond_editor_target_frame, variable=var_cond_type, values=ALL_CONDITION_TYPES,
                # This command needs to be handled carefully - it affects the parameters displayed below it.
                # For now, it still calls parent_app._on_rule_part_type_change, which will re-render.
                command=lambda choice: self.parent_app._on_rule_part_type_change("condition", choice)
            )
            menu_cond_type.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self.detail_optionmenu_vars["condition_type_var"] = var_cond_type # Stored in DetailsPanel
            self.detail_widgets["condition_type"] = menu_cond_type # Stored in DetailsPanel
            self._render_dynamic_parameters("conditions", curr_cond_type, condition_data_to_display, main_cond_editor_target_frame, 1, "cond_")

    def _populate_sub_conditions_list_internal(self, sub_conditions_data: List[Dict[str, Any]]):
        # This method now populates into self._current_cec_sub_list_frame_ref (which is inside CEC)
        if not hasattr(self, '_current_cec_sub_list_frame_ref') or not self._current_cec_sub_list_frame_ref or not self._current_cec_sub_list_frame_ref.winfo_exists():
            logger.error("DP: Target frame for sub-conditions list (inside CEC) not available.")
            return

        target_list_frame = self._current_cec_sub_list_frame_ref
        for w in target_list_frame.winfo_children():
            w.destroy()
        self.selected_sub_condition_item_widget = None

        # CEC's remove button needs to be enabled/disabled by DetailsPanel
        # (This is an awkward coupling for this intermediate step)
        cec_remove_button = getattr(self.condition_editor_component_instance, 'btn_remove_sub_condition_placeholder', None) # Assuming CEC creates a button with this name
        remove_btn_state = "normal" if self.parent_app.selected_sub_condition_index is not None and sub_conditions_data else "disabled"
        if cec_remove_button and hasattr(cec_remove_button, 'configure'):
            cec_remove_button.configure(state=remove_btn_state)


        for i, sub_cond_data in enumerate(sub_conditions_data):
            s_type = sub_cond_data.get("type", "N/A")
            s_rgn = f",Rgn:{sub_cond_data.get('region')}" if sub_cond_data.get("region") else ""
            s_cap = f",Var:{sub_cond_data.get('capture_as')}" if sub_cond_data.get("capture_as") else ""
            sum_txt = f"#{i+1}: {s_type}{s_rgn}{s_cap}"
            sum_txt = sum_txt[:45] + "..." if len(sum_txt) > 48 else sum_txt
            item_fr_ref = {}
            item_ui_frame = create_clickable_list_item(
                target_list_frame, # Target is now the frame inside CEC
                sum_txt,
                lambda e=None, scd=copy.deepcopy(sub_cond_data), idx=i, ifr_cb_ref=item_fr_ref: self._on_sub_condition_selected_internal(scd, idx, ifr_cb_ref.get("frame")),
            )
            item_fr_ref["frame"] = item_ui_frame

            if i == self.parent_app.selected_sub_condition_index:
                self._highlight_selected_list_item("condition", item_ui_frame, is_sub_list=True) # Highlight within CEC's list
                self.selected_sub_condition_item_widget = item_ui_frame

        if self.parent_app.selected_sub_condition_index is None and self.condition_editor_component_instance:
            # Clear CEC's sub-param editor frame
            sub_params_editor_frame = self.condition_editor_component_instance.sub_condition_params_editor_frame
            for w_sub_editor in sub_params_editor_frame.winfo_children():
                w_sub_editor.destroy()
            ctk.CTkLabel(sub_params_editor_frame, text="Select a sub-condition above to edit its parameters.").pack(padx=5, pady=5)

    def _on_sub_condition_selected_internal(self, sub_cond_data: Dict[str, Any], new_idx: int, item_frame: Optional[ctk.CTkFrame]):
        # This method's logic for saving previous and rendering new editor remains largely the same,
        # but it now targets frames within self.condition_editor_component_instance.

        if item_frame is None:
            logger.warning("DP: Sub-condition item_frame is None in selection callback.")
            return

        prev_sel_idx = self.parent_app.selected_sub_condition_index
        rule_idx = self.parent_app.selected_rule_index

        if prev_sel_idx is not None and prev_sel_idx != new_idx and rule_idx is not None:
            # (Logic to save previous sub-condition state - unchanged from original)
            if 0 <= rule_idx < len(self.parent_app.profile_data["rules"]):
                rule_model = self.parent_app.profile_data["rules"][rule_idx]
                compound_cond_model = rule_model.get("condition", {})
                sub_list_model = compound_cond_model.get("sub_conditions", [])
                if 0 <= prev_sel_idx < len(sub_list_model):
                    prev_sub_cond_type_var = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                    prev_sub_cond_type_str = prev_sub_cond_type_var.get() if prev_sub_cond_type_var else sub_list_model[prev_sel_idx].get("type", "always_true")

                    if prev_sub_cond_type_str:
                        params_from_ui = self._get_parameters_from_ui("conditions", prev_sub_cond_type_str, "subcond_")
                        if params_from_ui is not None:
                            sub_list_model[prev_sel_idx] = params_from_ui
                            self.parent_app._set_dirty_status(True)
                        else:
                             logger.warning(f"DP: Validation failed for sub-cond idx {prev_sel_idx}. Changes not saved.")


        self.parent_app.selected_sub_condition_index = new_idx
        self._highlight_selected_list_item("condition", item_frame, is_sub_list=True)
        self.selected_sub_condition_item_widget = item_frame

        # Enable CEC's remove button
        cec_remove_button = getattr(self.condition_editor_component_instance, 'btn_remove_sub_condition_placeholder', None)
        if cec_remove_button and hasattr(cec_remove_button, 'configure'):
            cec_remove_button.configure(state="normal")


        # Render editor for the newly selected sub-condition IN CEC's frame
        if not self.condition_editor_component_instance or not self.condition_editor_component_instance.sub_condition_params_editor_frame:
            logger.error("DP: CEC or its sub_condition_params_editor_frame is None. Cannot render sub-cond editor.")
            return
        target_sub_param_frame = self.condition_editor_component_instance.sub_condition_params_editor_frame
        for w in target_sub_param_frame.winfo_children():
            w.destroy()
        target_sub_param_frame.grid_columnconfigure(1, weight=1)

        current_type_of_selected_sub = str(sub_cond_data.get("type", "always_true"))
        ctk.CTkLabel(target_sub_param_frame, text=f"Editing Sub-Condition #{new_idx+1} / Type:", font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 5), pady=(5, 2), sticky="w")
        var_sub_type = ctk.StringVar(value=current_type_of_selected_sub)
        menu_sub_type = ctk.CTkOptionMenu(
            target_sub_param_frame, variable=var_sub_type, values=ALL_CONDITION_TYPES,
            command=lambda choice: self.parent_app._on_rule_part_type_change("condition", choice)
        )
        menu_sub_type.grid(row=0, column=1, padx=5, pady=(5, 2), sticky="ew")
        self.detail_optionmenu_vars["subcond_condition_type_var"] = var_sub_type
        self.detail_widgets["subcond_condition_type"] = menu_sub_type
        self._render_dynamic_parameters("conditions", current_type_of_selected_sub, sub_cond_data, target_sub_param_frame, 1, "subcond_")

    # --- Dispatcher methods for CEC buttons ---
    # These are called by ConditionEditorComponent and then call MainAppWindow methods
    def _cec_convert_condition_structure(self):
        logger.debug("DetailsPanel: _cec_convert_condition_structure called, dispatching to parent_app.")
        self.parent_app._convert_condition_structure()

    def _cec_add_sub_condition(self):
        logger.debug("DetailsPanel: _cec_add_sub_condition called, dispatching to parent_app.")
        self.parent_app._add_sub_condition_to_rule()

    def _cec_remove_selected_sub_condition(self):
        logger.debug("DetailsPanel: _cec_remove_selected_sub_condition called, dispatching to parent_app.")
        self.parent_app._remove_selected_sub_condition()


    # _render_dynamic_parameters, _update_conditional_visibility_dp, _apply_all_conditional_visibility_dp,
    # get_all_rule_data_from_ui, _get_parameters_from_ui methods remain mostly unchanged for now,
    # as they are complex and their full refactoring is a larger step.
    # They will now be called to populate frames *within* ConditionEditorComponent or ActionEditorComponent (future).
    # The `widget_prefix` parameter becomes more important.

    def _render_dynamic_parameters(self, param_group_key: str, item_subtype: str, data_source: Dict[str, Any], parent_frame: ctk.CTkFrame, start_row: int, widget_prefix: str):
        current_pass_param_widgets_and_defs: List[Dict[str, Any]] = []
        current_pass_controlling_widgets: Dict[str, Union[ctk.CTkOptionMenu, ctk.CTkCheckBox]] = {}

        for child_widget in list(parent_frame.winfo_children()):
            grid_info = child_widget.grid_info()
            if grid_info and grid_info.get("row", -1) >= start_row:
                widget_key_to_pop = None
                for wk, w_instance in list(self.detail_widgets.items()):
                    if w_instance == child_widget and wk.startswith(widget_prefix):
                        widget_key_to_pop = wk
                        break
                if widget_key_to_pop:
                    self.detail_widgets.pop(widget_key_to_pop, None)
                    self.detail_optionmenu_vars.pop(f"{widget_key_to_pop}_var", None)
                child_widget.destroy()

        param_defs_for_subtype = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])
        current_r = start_row

        if not param_defs_for_subtype and item_subtype not in ["always_true"]:
            ctk.CTkLabel(parent_frame, text=f"No parameters defined for type '{item_subtype}'.", text_color="gray").grid(row=current_r, column=0, columnspan=2, pady=5)
            return

        for p_def in param_defs_for_subtype:
            p_id, lbl_txt, w_type, d_type, def_val = p_def["id"], p_def["label"], p_def["widget"], p_def["type"], p_def.get("default", "")
            current_value_for_param = data_source.get(p_id, def_val)
            widget_full_key = f"{widget_prefix}{p_id}"
            label_widget = ctk.CTkLabel(parent_frame, text=lbl_txt)
            created_widget_instance: Optional[Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = None

            if w_type == "entry":
                entry = ctk.CTkEntry(parent_frame, placeholder_text=str(p_def.get("placeholder", "")))
                display_value = ", ".join(map(str, current_value_for_param)) if d_type == "list_str_csv" and isinstance(current_value_for_param, list) else str(current_value_for_param)
                entry.insert(0, display_value)
                entry.bind("<KeyRelease>", lambda e, dp=self: dp.parent_app._set_dirty_status(True))
                created_widget_instance = entry
            elif w_type == "textbox":
                textbox = ctk.CTkTextbox(parent_frame, height=p_def.get("height", 60), wrap="word")
                textbox.insert("0.0", str(current_value_for_param))
                textbox.bind("<FocusOut>", lambda e, dp=self: dp.parent_app._set_dirty_status(True))
                created_widget_instance = textbox
            elif w_type.startswith("optionmenu"):
                options_list = []
                src_key = p_def.get("options_source") if w_type == "optionmenu_dynamic" else p_def.get("options_const_key")
                if w_type == "optionmenu_dynamic" and src_key == "regions":
                    options_list = [""] + [r.get("name", "") for r in self.parent_app.profile_data.get("regions", []) if r.get("name")]
                elif w_type == "optionmenu_dynamic" and src_key == "templates":
                    options_list = [""] + [t.get("name", "") for t in self.parent_app.profile_data.get("templates", []) if t.get("name")]
                elif w_type == "optionmenu_static" and src_key:
                    options_list = OPTIONS_CONST_MAP.get(src_key, [])
                if not options_list: options_list = [str(def_val)] if str(def_val) else [""]
                str_current_val = str(current_value_for_param)
                final_current_val_for_menu = str_current_val if str_current_val in options_list else (str(def_val) if str(def_val) in options_list else (options_list[0] if options_list else ""))
                tk_var = ctk.StringVar(value=final_current_val_for_menu)
                option_menu = ctk.CTkOptionMenu(parent_frame, variable=tk_var, values=options_list,
                                                command=lambda choice, p=p_def, cpw=current_pass_controlling_widgets, cppwd=current_pass_param_widgets_and_defs, wp=widget_prefix: self._update_conditional_visibility_dp(p, choice, cpw, cppwd, wp))
                self.detail_optionmenu_vars[f"{widget_full_key}_var"] = tk_var
                created_widget_instance = option_menu
                if any(other_pdef.get("condition_show", {}).get("field") == p_id for other_pdef in param_defs_for_subtype if other_pdef.get("condition_show")):
                    current_pass_controlling_widgets[p_id] = created_widget_instance
            elif w_type == "checkbox":
                tk_bool_var = tk.BooleanVar(value=bool(current_value_for_param))
                checkbox = ctk.CTkCheckBox(parent_frame, text="", variable=tk_bool_var,
                                           command=lambda p=p_def, v=tk_bool_var, cpw=current_pass_controlling_widgets, cppwd=current_pass_param_widgets_and_defs, wp=widget_prefix: self._update_conditional_visibility_dp(p, v.get(), cpw, cppwd, wp))
                self.detail_optionmenu_vars[f"{widget_full_key}_var"] = tk_bool_var
                created_widget_instance = checkbox
                if any(other_pdef.get("condition_show", {}).get("field") == p_id for other_pdef in param_defs_for_subtype if other_pdef.get("condition_show")):
                    current_pass_controlling_widgets[p_id] = created_widget_instance

            if created_widget_instance:
                self.detail_widgets[widget_full_key] = created_widget_instance
                label_widget.grid(row=current_r, column=0, padx=(0, 5), pady=2, sticky="nw" if w_type == "textbox" else "w")
                created_widget_instance.grid(row=current_r, column=1, padx=5, pady=2, sticky="ew")
                current_pass_param_widgets_and_defs.append({"widget": created_widget_instance, "label_widget": label_widget, "param_def": p_def})
                current_r += 1
            else: label_widget.destroy()
        self._apply_all_conditional_visibility_dp(current_pass_param_widgets_and_defs, current_pass_controlling_widgets, widget_prefix)

    def _update_conditional_visibility_dp(self, changed_param_def_controller: Dict[str,Any], new_value_of_controller: Any, controlling_widgets_map: Dict, param_widgets_list: List, widget_prefix: str):
        self.parent_app._set_dirty_status(True)
        logger.debug(f"DetailsPanel: Controller '{changed_param_def_controller.get('id')}' (prefix '{widget_prefix}') changed. Re-evaluating visibility.")
        self._apply_all_conditional_visibility_dp(param_widgets_list, controlling_widgets_map, widget_prefix)

    def _apply_all_conditional_visibility_dp(self, param_widgets_and_defs_list: List, controlling_widgets_map: Dict, current_widget_prefix: str):
        # This method remains the same, operates on the passed lists/maps
        if not param_widgets_and_defs_list: return # Removed other checks as prefix is now passed

        for item in param_widgets_and_defs_list:
            widget_instance, label_widget_instance, param_definition = item["widget"], item["label_widget"], item["param_def"]
            visibility_config = param_definition.get("condition_show")
            should_be_visible = True

            if visibility_config:
                controlling_field_id = visibility_config.get("field")
                expected_values_for_visibility = visibility_config.get("values", [])
                controller_widget_instance = controlling_widgets_map.get(controlling_field_id)
                current_controller_value = None

                if isinstance(controller_widget_instance, ctk.CTkOptionMenu):
                    tk_var_for_controller = self.detail_optionmenu_vars.get(f"{current_widget_prefix}{controlling_field_id}_var")
                    if tk_var_for_controller and isinstance(tk_var_for_controller, tk.StringVar): current_controller_value = tk_var_for_controller.get()
                elif isinstance(controller_widget_instance, ctk.CTkCheckBox):
                    tk_var_for_controller = self.detail_optionmenu_vars.get(f"{current_widget_prefix}{controlling_field_id}_var")
                    if tk_var_for_controller and isinstance(tk_var_for_controller, tk.BooleanVar): current_controller_value = tk_var_for_controller.get(); expected_values_for_visibility = [bool(v) for v in expected_values_for_visibility if isinstance(v, (str, int, bool))]
                if current_controller_value is None or current_controller_value not in expected_values_for_visibility: should_be_visible = False

            if widget_instance and widget_instance.winfo_exists():
                is_currently_mapped = widget_instance.winfo_ismapped()
                if should_be_visible and not is_currently_mapped: widget_instance.grid(); _ = label_widget_instance.grid() if label_widget_instance and label_widget_instance.winfo_exists() and not label_widget_instance.winfo_ismapped() else None
                elif not should_be_visible and is_currently_mapped: widget_instance.grid_remove(); _ = label_widget_instance.grid_remove() if label_widget_instance and label_widget_instance.winfo_exists() and label_widget_instance.winfo_ismapped() else None

    def get_all_rule_data_from_ui(self) -> Optional[Dict[str, Any]]:
        # This method needs to be updated to get condition data from self.condition_editor_component_instance
        if self.parent_app.selected_rule_index is None: return None
        if not (0 <= self.parent_app.selected_rule_index < len(self.parent_app.profile_data["rules"])): return None

        final_rule_data: Dict[str, Any] = {"name": "", "region": "", "condition": {}, "action": {}, "comment": ""}
        all_valid = True

        name_w = self.detail_widgets.get("rule_name"); val, ok = validate_and_get_widget_value(name_w, None, "Rule Name", str, "", True); final_rule_data["name"] = val; all_valid &= ok
        region_v = self.detail_optionmenu_vars.get("rule_region_var"); final_rule_data["region"] = region_v.get() if region_v else ""
        comment_w = self.detail_widgets.get("rule_comment"); val, ok = validate_and_get_widget_value(comment_w, None, "Rule Comment", str, "", False, True); final_rule_data["comment"] = val; all_valid &= ok

        # Get condition data from ConditionEditorComponent
        if self.condition_editor_component_instance:
            # This is where the logic for get_condition_data_from_ui in CEC would be called.
            # For now, we'll have CEC pass back data, or DP reconstructs it
            # based on its knowledge of widgets inside CEC (less ideal intermediate state).
            # Let's assume CEC can provide its data:
            # condition_data_from_cec = self.condition_editor_component_instance.get_condition_data_from_ui()
            # For this intermediate step, we reconstruct it in DetailsPanel from widgets known to be in CEC.

            is_compound_ui = "logical_operator_var" in self.detail_optionmenu_vars # Check if DP thinks it's compound
            if is_compound_ui:
                log_op_v = self.detail_optionmenu_vars.get("logical_operator_var")
                current_log_op = log_op_v.get() if log_op_v else "AND"
                current_sub_conditions_from_ui = []
                rule_model = self.parent_app.profile_data["rules"][self.parent_app.selected_rule_index] # get current model
                sub_conds_in_model = rule_model.get("condition", {}).get("sub_conditions", [])

                for i, sub_cond_data_model_item in enumerate(sub_conds_in_model):
                    if i == self.parent_app.selected_sub_condition_index: # If this sub-condition is the one being edited
                        sub_type_v = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                        if not sub_type_v: all_valid = False; break
                        sub_type = sub_type_v.get()
                        sub_params = self._get_parameters_from_ui("conditions", sub_type, "subcond_")
                        if sub_params is None: all_valid = False; break
                        current_sub_conditions_from_ui.append(sub_params)
                    else: # For other sub-conditions, use their existing model data
                        current_sub_conditions_from_ui.append(copy.deepcopy(sub_cond_data_model_item))
                if not all_valid: return None
                final_rule_data["condition"] = {"logical_operator": current_log_op, "sub_conditions": current_sub_conditions_from_ui}
            else: # Single condition
                cond_type_v = self.detail_optionmenu_vars.get("condition_type_var")
                if not cond_type_v: return None
                single_cond_type = cond_type_v.get()
                single_cond_params = self._get_parameters_from_ui("conditions", single_cond_type, "cond_")
                if single_cond_params is None: all_valid = False
                else: final_rule_data["condition"] = single_cond_params
        else: # Should not happen if rule details are displayed
            all_valid = False

        if not all_valid: return None

        act_type_v = self.detail_optionmenu_vars.get("action_type_var")
        if not act_type_v: return None
        act_type = act_type_v.get()
        act_params = self._get_parameters_from_ui("actions", act_type, "act_")
        if act_params is None: all_valid = False
        else: final_rule_data["action"] = act_params

        return final_rule_data if all_valid else None

    def _get_parameters_from_ui(self, param_group_key: str, item_subtype: str, widget_prefix: str) -> Optional[Dict[str, Any]]:
        # This method remains largely the same.
        params: Dict[str, Any] = {"type": item_subtype}
        all_ok = True
        param_defs = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])
        if not param_defs and item_subtype != "always_true": return params

        for p_def in param_defs:
            p_id, lbl_err, target_type, def_val, is_req_def = p_def["id"], p_def["label"].rstrip(":"), p_def["type"], p_def.get("default", ""), p_def.get("required", False)
            w_key = f"{widget_prefix}{p_id}"; widget = self.detail_widgets.get(w_key); tk_var = self.detail_optionmenu_vars.get(f"{w_key}_var")
            is_vis = False
            if widget and widget.winfo_exists(): is_vis = widget.winfo_ismapped()
            elif tk_var and isinstance(tk_var, tk.BooleanVar) and widget and widget.winfo_exists(): is_vis = widget.winfo_ismapped()
            eff_req = is_req_def and is_vis
            if not is_vis and not eff_req: continue
            if widget is None and not isinstance(tk_var, tk.BooleanVar):
                if eff_req: logger.error(f"DP: Widget for required '{lbl_err}' (ID: {p_id}) not found."); all_ok = False
                params[p_id] = def_val; continue
            val_args = {"required": eff_req, "allow_empty_string": p_def.get("allow_empty_string", target_type == str), "min_val": p_def.get("min_val"), "max_val": p_def.get("max_val")}
            val, valid = validate_and_get_widget_value(widget, tk_var, lbl_err, target_type, def_val, **val_args)
            if not valid: all_ok = False; val = def_val
            if target_type == "list_str_csv": params[p_id] = [s.strip() for s in val.split(',') if isinstance(val,str) and s.strip()] if isinstance(val,str) and val.strip() else ([] if not def_val or not isinstance(def_val,list) else def_val)
            else: params[p_id] = val
            if p_id == "template_name" and param_group_key == "conditions":
                selected_template_name = val; params["template_filename"] = ""
                if selected_template_name:
                    found_template_meta = next((t for t in self.parent_app.profile_data.get("templates", []) if t.get("name") == selected_template_name), None)
                    if found_template_meta and found_template_meta.get("filename"): params["template_filename"] = found_template_meta["filename"]
                    elif eff_req: messagebox.showerror("Internal Error", f"Filename for template '{selected_template_name}' not found.", parent=self); all_ok = False
                elif eff_req: messagebox.showerror("Input Error", f"'{lbl_err}' (Template Name) required.", parent=self); all_ok = False
                if "template_name" in params: del params["template_name"]
        if item_subtype == "always_true" and param_group_key == "conditions":
            region_param_def_for_at = next((pd for pd in UI_PARAM_CONFIG.get("conditions", {}).get("always_true", []) if pd["id"] == "region"), None)
            if region_param_def_for_at:
                region_val_for_at, _ = validate_and_get_widget_value(self.detail_widgets.get(f"{widget_prefix}region"), self.detail_optionmenu_vars.get(f"{widget_prefix}region_var"), "Region (always_true)", str, "", required=False)
                if region_val_for_at: params["region"] = region_val_for_at
        return params if all_ok else None