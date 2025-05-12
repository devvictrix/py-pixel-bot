import logging
import tkinter as tk
from tkinter import messagebox
import os

# import json # No longer needed here
import copy
from typing import Optional, Dict, Any, List, Union

import customtkinter as ctk
from PIL import Image

# Standardized Absolute Imports from the gui subpackage
from py_pixel_bot.ui.gui.gui_config import UI_PARAM_CONFIG, OPTIONS_CONST_MAP, MAX_PREVIEW_WIDTH, MAX_PREVIEW_HEIGHT, CONDITION_TYPES, LOGICAL_OPERATORS, ACTION_TYPES
from py_pixel_bot.ui.gui.gui_utils import validate_and_get_widget_value, parse_bgr_string, create_clickable_list_item


logger = logging.getLogger(__name__)


class DetailsPanel(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, parent_app: Any, **kwargs):  # parent_app is MainAppWindow
        super().__init__(master, label_text="Selected Item Details", **kwargs)
        self.parent_app = parent_app

        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        self.detail_optionmenu_vars: Dict[str, Union[tk.StringVar, tk.BooleanVar]] = {}

        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        self.label_placeholder = ctk.CTkLabel(self.content_frame, text="Select an item to see/edit details.", wraplength=380, justify="center")
        self.label_placeholder.pack(padx=10, pady=20, anchor="center", expand=True)

        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None
        self.condition_params_frame: Optional[ctk.CTkFrame] = None
        self.action_params_frame: Optional[ctk.CTkFrame] = None
        self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None
        self.btn_convert_condition: Optional[ctk.CTkButton] = None
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None

        logger.debug("DetailsPanel initialized.")

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.detail_widgets.clear()
        self.detail_optionmenu_vars.clear()

        self.template_preview_image_label = None
        self.sub_conditions_list_frame = None
        self.condition_params_frame = None
        self.action_params_frame = None
        self.sub_condition_params_frame = None
        self.btn_convert_condition = None
        self.btn_remove_sub_condition = None
        logger.debug("DetailsPanel content cleared.")

    def update_display(self, item_data: Optional[Dict[str, Any]], item_type: str):
        self.clear_content()
        self.content_frame.grid_columnconfigure(1, weight=1)

        if item_data is None or item_type == "none":
            self.label_placeholder = ctk.CTkLabel(self.content_frame, text="Select an item to see/edit details.", wraplength=380, justify="center")
            self.label_placeholder.pack(padx=10, pady=20, anchor="center", expand=True)
            return

        if item_type == "region":
            self._display_region_details(item_data)
        elif item_type == "template":
            self._display_template_details(item_data)
        elif item_type == "rule":
            self._display_rule_details(item_data)
        else:
            logger.warning(f"DetailsPanel: Unknown item_type '{item_type}' for display.")
            self.label_placeholder = ctk.CTkLabel(self.content_frame, text=f"Cannot display details for '{item_type}'.", wraplength=380)
            self.label_placeholder.pack(padx=10, pady=20, anchor="center", expand=True)

    def _display_region_details(self, region_data: Dict):
        logger.debug(f"Displaying region details: {region_data.get('name')}")

        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        name_entry = ctk.CTkEntry(self.content_frame)
        name_entry.insert(0, str(region_data.get("name", "")))
        name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        name_entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["name"] = name_entry

        coords = {"x": region_data.get("x", 0), "y": region_data.get("y", 0), "width": region_data.get("width", 100), "height": region_data.get("height", 100)}
        for i, (k, v) in enumerate(coords.items()):
            ctk.CTkLabel(self.content_frame, text=f"{k.capitalize()}:").grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")
            entry = ctk.CTkEntry(self.content_frame)
            entry.insert(0, str(v))
            entry.grid(row=i + 1, column=1, padx=5, pady=5, sticky="ew")
            entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
            self.detail_widgets[k] = entry

        button_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        button_frame.grid(row=len(coords) + 1, column=0, columnspan=2, pady=10)
        ctk.CTkButton(button_frame, text="Apply Changes", command=self.parent_app._apply_region_changes).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Edit Coords (Selector)", command=self.parent_app._edit_region_coordinates_with_selector).pack(side="left", padx=5)

    def _display_template_details(self, template_data: Dict):
        logger.debug(f"Displaying template details: {template_data.get('name')}")

        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        name_entry = ctk.CTkEntry(self.content_frame)
        name_entry.insert(0, str(template_data.get("name", "")))
        name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        name_entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["template_name"] = name_entry

        ctk.CTkLabel(self.content_frame, text="Filename:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(self.content_frame, text=str(template_data.get("filename", "N/A")), anchor="w").grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(self.content_frame, text="Preview:").grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        self.template_preview_image_label = ctk.CTkLabel(self.content_frame, text="No preview", width=MAX_PREVIEW_WIDTH, height=MAX_PREVIEW_HEIGHT)
        self.template_preview_image_label.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self._update_template_preview_image(template_data.get("filename"))

        ctk.CTkButton(self.content_frame, text="Apply Changes", command=self.parent_app._apply_template_changes).grid(row=3, column=0, columnspan=2, pady=10)

    def _update_template_preview_image(self, filename: Optional[str]):
        if not self.template_preview_image_label or not filename or not self.parent_app.current_profile_path:
            if self.template_preview_image_label:
                self.template_preview_image_label.configure(image=None, text="No preview.")
            return

        profile_dir = os.path.dirname(self.parent_app.current_profile_path)
        template_path = os.path.join(profile_dir, "templates", filename)
        if os.path.exists(template_path):
            try:
                img = Image.open(template_path)
                img.thumbnail((MAX_PREVIEW_WIDTH, MAX_PREVIEW_HEIGHT))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.template_preview_image_label.configure(image=ctk_img, text="")
            except Exception as e:
                self.template_preview_image_label.configure(image=None, text=f"Error preview:\n{filename}")
                logger.error(f"Error loading template preview for '{template_path}': {e}", exc_info=True)
        else:
            self.template_preview_image_label.configure(image=None, text=f"File not found:\n{filename}")

    def _display_rule_details(self, rule_data: Dict):
        logger.debug(f"Displaying rule details: {rule_data.get('name')}")
        self.parent_app.selected_sub_condition_index = None

        row_idx = 0
        ctk.CTkLabel(self.content_frame, text="Rule Name:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        name_entry = ctk.CTkEntry(self.content_frame)
        name_entry.insert(0, rule_data.get("name", ""))
        name_entry.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        name_entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["rule_name"] = name_entry
        row_idx += 1

        ctk.CTkLabel(self.content_frame, text="Default Region:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
        region_names = [""] + [r.get("name", "") for r in self.parent_app.profile_data.get("regions", []) if r.get("name")]
        var_rule_region = ctk.StringVar(value=rule_data.get("region", ""))
        region_menu = ctk.CTkOptionMenu(self.content_frame, variable=var_rule_region, values=region_names, command=lambda c: self.parent_app._set_dirty_status(True))
        region_menu.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
        self.detail_optionmenu_vars["rule_region_var"] = var_rule_region
        self.detail_widgets["rule_region"] = region_menu
        row_idx += 1

        condition_data = copy.deepcopy(rule_data.get("condition", {}))
        action_data = copy.deepcopy(rule_data.get("action", {}))

        cond_outer_frame = ctk.CTkFrame(self.content_frame)
        cond_outer_frame.grid(row=row_idx, column=0, columnspan=2, sticky="new", pady=(10, 0))
        cond_outer_frame.grid_columnconfigure(0, weight=1)
        row_idx += 1

        cond_header_frame = ctk.CTkFrame(cond_outer_frame, fg_color="transparent")
        cond_header_frame.pack(fill="x", padx=5)
        ctk.CTkLabel(cond_header_frame, text="CONDITION", font=ctk.CTkFont(weight="bold")).pack(side="left", anchor="w")

        is_compound = "logical_operator" in condition_data and isinstance(condition_data.get("sub_conditions"), list)
        btn_text = "Convert to Single" if is_compound else "Convert to Compound"
        self.btn_convert_condition = ctk.CTkButton(cond_header_frame, text=btn_text, command=self.parent_app._convert_condition_structure, width=160)
        self.btn_convert_condition.pack(side="right", padx=(0, 5))

        self.condition_params_frame = ctk.CTkFrame(cond_outer_frame, fg_color="transparent")
        self.condition_params_frame.pack(fill="x", expand=True, padx=5, pady=(0, 5))
        self._render_rule_condition_editor_internal(condition_data)

        act_outer_frame = ctk.CTkFrame(self.content_frame)
        act_outer_frame.grid(row=row_idx, column=0, columnspan=2, sticky="new", pady=(10, 0))
        act_outer_frame.grid_columnconfigure(0, weight=1)
        row_idx += 1
        ctk.CTkLabel(act_outer_frame, text="ACTION", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=5)

        self.action_params_frame = ctk.CTkFrame(act_outer_frame, fg_color="transparent")
        self.action_params_frame.pack(fill="x", expand=True, padx=5, pady=(0, 5))
        self.action_params_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.action_params_frame, text="Action Type:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        initial_action_type = str(action_data.get("type", "log_message"))
        var_action_type = ctk.StringVar(value=initial_action_type)
        action_type_menu = ctk.CTkOptionMenu(
            self.action_params_frame, variable=var_action_type, values=ACTION_TYPES, command=lambda choice: self.parent_app._on_rule_part_type_change("action", choice)
        )
        action_type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.detail_optionmenu_vars["action_type_var"] = var_action_type
        self.detail_widgets["action_type"] = action_type_menu
        self._render_dynamic_parameters("actions", initial_action_type, action_data, self.action_params_frame, start_row=1, widget_prefix="act_")

        ctk.CTkButton(self.content_frame, text="Apply Rule Changes", command=self.parent_app._apply_rule_changes).grid(row=row_idx, column=0, columnspan=2, pady=(20, 5))

    def _render_rule_condition_editor_internal(self, condition_data: Dict):
        if not self.condition_params_frame:
            return
        for widget in self.condition_params_frame.winfo_children():
            widget.destroy()
        self.condition_params_frame.grid_columnconfigure(1, weight=1)

        is_compound = "logical_operator" in condition_data and isinstance(condition_data.get("sub_conditions"), list)

        if is_compound:
            ctk.CTkLabel(self.condition_params_frame, text="Logical Operator:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            var_log_op = ctk.StringVar(value=condition_data.get("logical_operator", "AND"))
            op_menu = ctk.CTkOptionMenu(self.condition_params_frame, variable=var_log_op, values=LOGICAL_OPERATORS, command=lambda c: self.parent_app._set_dirty_status(True))
            op_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self.detail_optionmenu_vars["logical_operator_var"] = var_log_op
            self.detail_widgets["logical_operator"] = op_menu

            sub_cond_outer_frame = ctk.CTkFrame(self.condition_params_frame, fg_color="transparent")
            sub_cond_outer_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 0))
            sub_cond_outer_frame.grid_columnconfigure(0, weight=1)

            sc_list_header = ctk.CTkFrame(sub_cond_outer_frame, fg_color="transparent")
            sc_list_header.grid(row=0, column=0, sticky="ew")
            ctk.CTkLabel(sc_list_header, text="Sub-Conditions:", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
            ctk.CTkButton(sc_list_header, text="+ Add", width=60, command=self.parent_app._add_sub_condition_to_rule).pack(side="right", padx=5)
            self.btn_remove_sub_condition = ctk.CTkButton(sc_list_header, text="- Remove", width=75, command=self.parent_app._remove_selected_sub_condition, state="disabled")
            self.btn_remove_sub_condition.pack(side="right", padx=(0, 5))

            self.sub_conditions_list_frame = ctk.CTkScrollableFrame(sub_cond_outer_frame, label_text="", height=150)
            self.sub_conditions_list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
            self._populate_sub_conditions_list_internal(condition_data.get("sub_conditions", []))

            self.sub_condition_params_frame = ctk.CTkFrame(sub_cond_outer_frame, fg_color="transparent")
            self.sub_condition_params_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
            self.sub_condition_params_frame.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(self.sub_condition_params_frame, text="Select sub-condition to edit.").pack(padx=5, pady=5)
        else:
            ctk.CTkLabel(self.condition_params_frame, text="Condition Type:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            current_cond_type = str(condition_data.get("type", "always_true"))
            var_cond_type = ctk.StringVar(value=current_cond_type)
            cond_type_menu = ctk.CTkOptionMenu(
                self.condition_params_frame, variable=var_cond_type, values=CONDITION_TYPES, command=lambda choice: self.parent_app._on_rule_part_type_change("condition", choice)
            )
            cond_type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self.detail_optionmenu_vars["condition_type_var"] = var_cond_type
            self.detail_widgets["condition_type"] = cond_type_menu
            self._render_dynamic_parameters("conditions", current_cond_type, condition_data, self.condition_params_frame, start_row=1, widget_prefix="cond_")

        if self.btn_convert_condition:
            self.btn_convert_condition.configure(text="Convert to Single" if is_compound else "Convert to Compound")

    def _populate_sub_conditions_list_internal(self, sub_conditions_data: List[Dict]):
        if not self.sub_conditions_list_frame:
            return
        for widget in self.sub_conditions_list_frame.winfo_children():
            widget.destroy()

        if self.btn_remove_sub_condition:
            self.btn_remove_sub_condition.configure(state="disabled" if self.parent_app.selected_sub_condition_index is None else "normal")

        for i, sub_cond in enumerate(sub_conditions_data):
            summary = f"#{i+1} T: {sub_cond.get('type','N/A')}"
            if sub_cond.get("region"):
                summary += f", R: {sub_cond.get('region')}"
            if sub_cond.get("capture_as"):
                summary += f", C: {sub_cond.get('capture_as')}"

            item_frame_container = {}
            item_frame = create_clickable_list_item(
                self.sub_conditions_list_frame, summary, lambda e=None, scd=sub_cond, idx=i, ifc=item_frame_container: self._on_sub_condition_selected_internal(scd, idx, ifc.get("frame"))
            )
            item_frame_container["frame"] = item_frame
            if i == self.parent_app.selected_sub_condition_index:
                self.parent_app._highlight_selected_list_item("condition", item_frame, is_sub_list=True)

        if self.parent_app.selected_sub_condition_index is None and self.sub_condition_params_frame:
            for widget in self.sub_condition_params_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.sub_condition_params_frame, text="Select sub-condition to edit.").pack(padx=5, pady=5)

    def _on_sub_condition_selected_internal(self, sub_cond_data: Dict, index: int, item_widget_frame: Optional[ctk.CTkFrame]):
        if item_widget_frame is None:
            return
        self.parent_app.selected_sub_condition_index = index
        self.parent_app._highlight_selected_list_item("condition", item_widget_frame, is_sub_list=True)

        if self.btn_remove_sub_condition:
            self.btn_remove_sub_condition.configure(state="normal")
        if not self.sub_condition_params_frame:
            return
        for widget in self.sub_condition_params_frame.winfo_children():
            widget.destroy()
        self.sub_condition_params_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.sub_condition_params_frame, text=f"Edit Sub-Condition #{index + 1} Type:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        current_type = sub_cond_data.get("type", "always_true")
        var_sub_cond_type = ctk.StringVar(value=current_type)
        menu = ctk.CTkOptionMenu(
            self.sub_condition_params_frame, variable=var_sub_cond_type, values=CONDITION_TYPES, command=lambda choice: self.parent_app._on_rule_part_type_change("condition", choice)
        )
        menu.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.detail_optionmenu_vars["subcond_condition_type_var"] = var_sub_cond_type
        self.detail_widgets["subcond_condition_type"] = menu
        self._render_dynamic_parameters("conditions", current_type, sub_cond_data, self.sub_condition_params_frame, start_row=1, widget_prefix="subcond_")

    def _render_dynamic_parameters(self, param_group_key: str, item_subtype: str, data_source: Dict[str, Any], parent_frame: ctk.CTkFrame, start_row: int, widget_prefix: str):
        for widget_key_to_clear in list(self.detail_widgets.keys()):
            if widget_key_to_clear.startswith(widget_prefix) and widget_key_to_clear != f"{widget_prefix}type":
                widget_to_remove = self.detail_widgets.pop(widget_key_to_clear, None)
                if widget_to_remove and widget_to_remove.winfo_exists():
                    widget_to_remove.destroy()
                self.detail_optionmenu_vars.pop(f"{widget_key_to_clear}_var", None)

        for widget in list(parent_frame.winfo_children()):
            grid_info = widget.grid_info()
            if grid_info and grid_info.get("row", -1) >= start_row:
                widget.destroy()

        param_definitions = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])
        current_row = start_row

        if not param_definitions and item_subtype != "always_true":
            ctk.CTkLabel(parent_frame, text=f"No parameters for '{item_subtype}'.").grid(row=current_row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
            return
        elif item_subtype == "always_true":
            ctk.CTkLabel(parent_frame, text="No parameters needed.").grid(row=current_row, column=0, columnspan=2, sticky="w", padx=5, pady=2)
            return

        for param_def in param_definitions:
            param_id = param_def["id"]
            label_text = param_def["label"]
            widget_type_str = param_def["widget"]
            default_val = param_def["default"]
            current_val = data_source.get(param_id, default_val)
            widget_full_key = f"{widget_prefix}{param_id}"

            label = ctk.CTkLabel(parent_frame, text=label_text)

            widget: Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]

            if widget_type_str == "entry":
                widget = ctk.CTkEntry(parent_frame, placeholder_text=str(param_def.get("placeholder", default_val)))
                widget.insert(0, str(current_val))
                widget.bind("<KeyRelease>", lambda e, wk=widget_full_key: self.parent_app._set_dirty_status(True))
                label.grid(row=current_row, column=0, padx=5, pady=2, sticky="w")
                widget.grid(row=current_row, column=1, padx=5, pady=2, sticky="ew")
            elif widget_type_str == "textbox":
                widget = ctk.CTkTextbox(parent_frame, height=60, wrap="word")
                widget.insert("0.0", str(current_val))
                widget.bind("<FocusOut>", lambda e, wk=widget_full_key: self.parent_app._set_dirty_status(True))
                label.grid(row=current_row, column=0, padx=5, pady=2, sticky="nw")
                widget.grid(row=current_row, column=1, padx=5, pady=2, sticky="ew")
            elif widget_type_str.startswith("optionmenu"):
                options = []
                if widget_type_str == "optionmenu_dynamic":
                    source_key = param_def["options_source"]
                    if source_key == "regions":
                        options = [""] + [r.get("name", "") for r in self.parent_app.profile_data.get("regions", []) if r.get("name")]
                    elif source_key == "templates":
                        options = [""] + [t.get("name", "") for t in self.parent_app.profile_data.get("templates", []) if t.get("name")]
                elif widget_type_str == "optionmenu_static":
                    options = OPTIONS_CONST_MAP.get(param_def.get("options_const_key", ""), [])

                var = ctk.StringVar(value=str(current_val))
                widget = ctk.CTkOptionMenu(parent_frame, variable=var, values=options, command=lambda choice, wk=widget_full_key: self.parent_app._set_dirty_status(True))
                self.detail_optionmenu_vars[f"{widget_full_key}_var"] = var
                label.grid(row=current_row, column=0, padx=5, pady=2, sticky="w")
                widget.grid(row=current_row, column=1, padx=5, pady=2, sticky="ew")
            elif widget_type_str == "checkbox":
                var = tk.BooleanVar(value=bool(current_val))
                widget = ctk.CTkCheckBox(parent_frame, text=label_text, variable=var, command=lambda wk=widget_full_key: self.parent_app._set_dirty_status(True))
                self.detail_optionmenu_vars[f"{widget_full_key}_var"] = var
                widget.grid(row=current_row, column=0, columnspan=2, padx=5, pady=2, sticky="w")
            else:
                continue

            self.detail_widgets[widget_full_key] = widget
            current_row += 1

    def _get_parameters_from_ui(self, param_group_key: str, item_subtype: str, widget_prefix: str) -> Optional[Dict[str, Any]]:
        params: Dict[str, Any] = {"type": item_subtype}
        all_params_valid = True
        param_definitions = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])

        if not param_definitions and item_subtype != "always_true":
            return params

        for param_def in param_definitions:
            param_id = param_def["id"]
            widget_key = f"{widget_prefix}{param_id}"
            field_name = param_def["label"].rstrip(":")
            target_type_def = param_def["type"]
            default_val = param_def["default"]

            widget_instance = self.detail_widgets.get(widget_key)
            tk_var_instance = self.detail_optionmenu_vars.get(f"{widget_key}_var")

            validation_args = {
                "required": param_def.get("required", False),
                "allow_empty_string": param_def.get("allow_empty_string", target_type_def == str),
                "min_val": param_def.get("min_val"),
                "max_val": param_def.get("max_val"),
            }

            val, is_valid = validate_and_get_widget_value(widget_instance, tk_var_instance, field_name, target_type_def, default_val, **validation_args)

            if not is_valid and param_def.get("required", False):
                all_params_valid = False

            if param_id == "template_name" and param_group_key == "conditions":
                sel_tpl_name = val
                if not sel_tpl_name and param_def.get("required"):
                    messagebox.showerror("Input Error", f"'{field_name}' must be selected.")
                    all_params_valid = False
                    params["template_filename"] = ""
                elif sel_tpl_name:
                    actual_fn = next((t.get("filename", "") for t in self.parent_app.profile_data.get("templates", []) if t.get("name") == sel_tpl_name), "")
                    if not actual_fn:
                        messagebox.showerror("Input Error", f"Could not find filename for template '{sel_tpl_name}'.")
                        all_params_valid = False
                    params["template_filename"] = actual_fn
                else:
                    params["template_filename"] = ""
                params["template_name"] = sel_tpl_name
            else:
                params[param_id] = val

        return params if all_params_valid else None
