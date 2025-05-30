import logging
import tkinter as tk
from tkinter import messagebox # For error/info popups
import os # For path operations (though not directly used here much)
import copy # For deepcopying data structures
from typing import Optional, Dict, Any, List, Union, Callable

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError, ImageFont # For template preview, ImageFont for overlays

# Import configurations and utilities
from mark_i.ui.gui.gui_config import (
    UI_PARAM_CONFIG,           # Main configuration for dynamic UI
    OPTIONS_CONST_MAP,         # Maps const keys to lists for static optionmenus
    MAX_PREVIEW_WIDTH,         # For template image preview
    MAX_PREVIEW_HEIGHT,        # For template image preview
    CONDITION_TYPES as ALL_CONDITION_TYPES, # All available condition types
    ACTION_TYPES as ALL_ACTION_TYPES,       # All available action types
    LOGICAL_OPERATORS          # For compound conditions
)
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value, create_clickable_list_item

# Standardized logger
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.panels.details_panel")

# Font for candidate box overlays (if DetailsPanel were to show them, currently wizard does)
# FONT_PATH_PRIMARY_DP = "arial.ttf"
# FONT_PATH_FALLBACK_DP = "DejaVuSans.ttf"


class DetailsPanel(ctk.CTkScrollableFrame):
    """
    A CTkScrollableFrame that dynamically displays and allows editing of details
    for a selected item (Region, Template, or Rule) from the MainAppWindow.
    It uses UI_PARAM_CONFIG from gui_config.py to render appropriate input widgets
    and handles conditional visibility of parameters.
    """
    def __init__(self, master: Any, parent_app: Any, **kwargs): # parent_app is the MainAppWindow instance
        super().__init__(master, label_text="Selected Item Details", **kwargs)
        self.parent_app = parent_app # Reference to the MainAppWindow instance

        # Stores currently rendered dynamic widgets {widget_full_key: widget_instance}
        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        # Stores Tkinter variables for OptionMenus and CheckBoxes {widget_full_key_var: tk_variable}
        self.detail_optionmenu_vars: Dict[str, Union[tk.StringVar, tk.BooleanVar]] = {}

        # For managing selection highlight in sub-conditions list (if displaying a compound rule)
        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None

        # Main content frame within this scrollable panel
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        # Configure the content_frame's grid: column 1 (for values/widgets) should expand
        self.content_frame.grid_columnconfigure(1, weight=1)

        # Placeholder label shown when no item is selected for editing
        self.label_placeholder = ctk.CTkLabel(
            self.content_frame,
            text="Select an item from the lists (Regions, Templates, Rules)\n to see or edit its details here.",
            wraplength=380, # Adjust as needed for panel width
            justify="center",
            font=ctk.CTkFont(size=14)
        )
        self.label_placeholder.pack(padx=20, pady=30, anchor="center", expand=True) # Use pack for simple placeholder

        # Specific UI elements that might be created dynamically depending on selected item
        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None
        self.condition_params_frame: Optional[ctk.CTkFrame] = None # For single condition params OR overall compound editor
        self.action_params_frame: Optional[ctk.CTkFrame] = None
        self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None # For selected sub-condition's params
        
        self.btn_convert_condition: Optional[ctk.CTkButton] = None # To switch rule condition type
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None # To remove a sub-condition

        # For managing conditional visibility of parameters within the currently displayed editor
        self.param_widgets_and_defs_for_current_view: List[Dict[str, Any]] = []
        self.controlling_widgets_for_current_view: Dict[str, Union[ctk.CTkOptionMenu, ctk.CTkCheckBox]] = {}
        self.current_widget_prefix_for_visibility: str = ""

        logger.debug("DetailsPanel initialized.")

    def clear_content(self):
        """Destroys all widgets currently in the content_frame and resets internal widget/var stores."""
        for widget in self.content_frame.winfo_children():
            widget.destroy() # Destroy all children of content_frame
        
        self.detail_widgets.clear()
        self.detail_optionmenu_vars.clear()
        self.param_widgets_and_defs_for_current_view.clear()
        self.controlling_widgets_for_current_view.clear()
        self.current_widget_prefix_for_visibility = ""

        # Reset pointers to dynamically created frames/widgets that might be re-created
        self.template_preview_image_label = None
        self.sub_conditions_list_frame = None
        self.condition_params_frame = None
        self.action_params_frame = None
        self.sub_condition_params_frame = None
        self.btn_convert_condition = None
        self.btn_remove_sub_condition = None
        self.selected_sub_condition_item_widget = None # Crucial for sub-condition list highlight
        
        logger.debug("DetailsPanel content cleared and widget stores reset.")

    def update_display(self, item_data: Optional[Dict[str, Any]], item_type: str):
        """
        Clears existing content and then populates the panel to display details
        for the newly selected item (Region, Template, or Rule).

        Args:
            item_data: The data dictionary of the selected item. None if no item is selected.
            item_type: A string indicating the type of item ("region", "template", "rule", or "none").
        """
        self.clear_content() # Clear previous details thoroughly

        if item_data is None or item_type == "none":
            # Re-create the placeholder label if no item is selected
            self.label_placeholder = ctk.CTkLabel(
                self.content_frame,
                text="Select an item from the lists to see or edit its details.",
                wraplength=380, justify="center", font=ctk.CTkFont(size=14)
            )
            self.label_placeholder.pack(padx=20, pady=30, anchor="center", expand=True)
            logger.debug(f"DetailsPanel display updated: Showing placeholder as item_type is '{item_type}'.")
            return

        logger.info(f"DetailsPanel: Updating display for item_type '{item_type}', name: '{item_data.get('name', 'N/A')}'")
        
        # Ensure content_frame's column 1 (for widget values) is configured to expand
        self.content_frame.grid_columnconfigure(1, weight=1)

        if item_type == "region":
            self._display_region_details(item_data)
        elif item_type == "template":
            self._display_template_details(item_data)
        elif item_type == "rule":
            self._display_rule_details(item_data)
        else:
            logger.warning(f"DetailsPanel: Unknown item_type '{item_type}' received in update_display.")
            self.label_placeholder = ctk.CTkLabel(self.content_frame, text=f"Cannot display details for unknown item type: '{item_type}'.", wraplength=380)
            self.label_placeholder.pack(padx=10, pady=20, anchor="center", expand=True)

    def _display_region_details(self, region_data: Dict[str, Any]): # No change from v4.0.0
        logger.debug(f"Displaying region details for: {region_data.get('name', 'Unnamed Region')}")
        self.content_frame.grid_columnconfigure(1, weight=1)
        row_idx = 0
        # Name
        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="w")
        name_e = ctk.CTkEntry(self.content_frame, placeholder_text="Unique region name"); name_e.insert(0, str(region_data.get("name", ""))); name_e.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew"); name_e.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets["name"] = name_e; row_idx += 1
        # Coordinates & Dimensions
        coords_map = {"x":0, "y":0, "width":100, "height":100}
        for key, def_val in coords_map.items():
            ctk.CTkLabel(self.content_frame, text=f"{key.capitalize()}:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="w")
            entry_c = ctk.CTkEntry(self.content_frame, placeholder_text=f"Enter {key}"); entry_c.insert(0, str(region_data.get(key, def_val))); entry_c.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew"); entry_c.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets[key] = entry_c; row_idx += 1
        # Comment
        ctk.CTkLabel(self.content_frame, text="Comment:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="nw")
        comment_tb = ctk.CTkTextbox(self.content_frame, height=60, wrap="word"); comment_tb.insert("0.0", str(region_data.get("comment", ""))); comment_tb.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew"); comment_tb.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets["comment"] = comment_tb; row_idx += 1
        # Buttons
        btn_fr = ctk.CTkFrame(self.content_frame, fg_color="transparent"); btn_fr.grid(row=row_idx, column=0, columnspan=2, pady=(15,10), padx=10, sticky="ew"); btn_fr.grid_columnconfigure((0,1), weight=1)
        ctk.CTkButton(btn_fr, text="Apply Region Changes", command=self.parent_app._apply_region_changes).grid(row=0, column=0, padx=(0,5), sticky="e")
        ctk.CTkButton(btn_fr, text="Edit Coords (Selector)", command=self.parent_app._edit_region_coordinates_with_selector).grid(row=0, column=1, padx=(5,0), sticky="w")

    def _display_template_details(self, template_data: Dict[str, Any]): # No change from v4.0.0
        logger.debug(f"Displaying template details for: {template_data.get('name', 'Unnamed Template')}")
        self.content_frame.grid_columnconfigure(1, weight=1); row_idx = 0
        # Name
        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="w")
        name_e = ctk.CTkEntry(self.content_frame, placeholder_text="Unique template name"); name_e.insert(0, str(template_data.get("name", ""))); name_e.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew"); name_e.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets["template_name"] = name_e; row_idx += 1
        # Filename (read-only display)
        ctk.CTkLabel(self.content_frame, text="Filename:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="w")
        ctk.CTkLabel(self.content_frame, text=str(template_data.get("filename", "N/A")), anchor="w").grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew"); row_idx += 1
        # Comment
        ctk.CTkLabel(self.content_frame, text="Comment:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="nw")
        comment_tb = ctk.CTkTextbox(self.content_frame, height=60, wrap="word"); comment_tb.insert("0.0", str(template_data.get("comment", ""))); comment_tb.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew"); comment_tb.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets["comment"] = comment_tb; row_idx += 1
        # Preview
        ctk.CTkLabel(self.content_frame, text="Preview:").grid(row=row_idx, column=0, padx=(10,5), pady=5, sticky="nw")
        self.template_preview_image_label = ctk.CTkLabel(self.content_frame, text="Loading preview...", width=MAX_PREVIEW_WIDTH, height=MAX_PREVIEW_HEIGHT, anchor="w"); self.template_preview_image_label.grid(row=row_idx, column=1, padx=5, pady=5, sticky="w"); row_idx += 1
        self._update_template_preview_image(template_data.get("filename"))
        # Apply Button
        ctk.CTkButton(self.content_frame, text="Apply Template Changes", command=self.parent_app._apply_template_changes).grid(row=row_idx, column=0, columnspan=2, pady=(15,10), padx=10)

    def _update_template_preview_image(self, filename: Optional[str]): # No change from v4.0.0
        if not self.template_preview_image_label: return
        if not filename or not self.parent_app.current_profile_path: self.template_preview_image_label.configure(image=None, text="No preview (profile unsaved or no filename)."); return
        profile_dir = os.path.dirname(self.parent_app.current_profile_path); template_path = os.path.join(profile_dir, "templates", filename)
        if os.path.exists(template_path):
            try: img = Image.open(template_path); img_copy = img.copy(); img_copy.thumbnail((MAX_PREVIEW_WIDTH,MAX_PREVIEW_HEIGHT),Image.Resampling.LANCZOS); ctk_img=ctk.CTkImage(light_image=img_copy,dark_image=img_copy,size=(img_copy.width,img_copy.height)); self.template_preview_image_label.configure(image=ctk_img,text="")
            except UnidentifiedImageError: self.template_preview_image_label.configure(image=None, text=f"Error: Not an image\n{filename}"); logger.error(f"Error previewing '{template_path}': UnidentifiedImageError.", exc_info=False)
            except Exception as e: self.template_preview_image_label.configure(image=None, text=f"Error loading preview:\n{filename}"); logger.error(f"Error previewing '{template_path}': {e}", exc_info=True)
        else: self.template_preview_image_label.configure(image=None, text=f"File not found:\n{filename}"); logger.warning(f"Template image not found for preview: {template_path}")

    def _display_rule_details(self, rule_data: Dict[str, Any]): # No change from v4.0.0
        logger.debug(f"Displaying rule details for: {rule_data.get('name', 'Unnamed Rule')}")
        self.parent_app.selected_sub_condition_index = None # Reset sub-condition selection when a new rule is selected
        self.content_frame.grid_columnconfigure(1, weight=1); current_master_row = 0
        # Rule Name
        ctk.CTkLabel(self.content_frame, text="Rule Name:").grid(row=current_master_row, column=0, sticky="w", padx=(10,5), pady=2)
        name_e = ctk.CTkEntry(self.content_frame, placeholder_text="Unique rule name"); name_e.insert(0, rule_data.get("name", "")); name_e.grid(row=current_master_row, column=1, sticky="ew", padx=5, pady=2); name_e.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets["rule_name"] = name_e; current_master_row += 1
        # Default Region
        ctk.CTkLabel(self.content_frame, text="Default Region:").grid(row=current_master_row, column=0, sticky="w", padx=(10,5), pady=2)
        regions = [""] + [r.get("name","") for r in self.parent_app.profile_data.get("regions",[]) if r.get("name")]; var_region = ctk.StringVar(value=str(rule_data.get("region",""))); menu_region = ctk.CTkOptionMenu(self.content_frame,variable=var_region,values=regions,command=lambda c:self.parent_app._set_dirty_status(True)); menu_region.grid(row=current_master_row,column=1,sticky="ew",padx=5,pady=2); self.detail_optionmenu_vars["rule_region_var"]=var_region; self.detail_widgets["rule_region"]=menu_region; current_master_row+=1
        # Rule Comment
        ctk.CTkLabel(self.content_frame, text="Comment (Rule):").grid(row=current_master_row, column=0, padx=(10,5), pady=5, sticky="nw"); rule_comment_tb = ctk.CTkTextbox(self.content_frame, height=40, wrap="word"); rule_comment_tb.insert("0.0", str(rule_data.get("comment",""))); rule_comment_tb.grid(row=current_master_row, column=1, padx=5, pady=5, sticky="ew"); rule_comment_tb.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); self.detail_widgets["rule_comment"] = rule_comment_tb; current_master_row += 1
        # Condition Section
        cond_data = copy.deepcopy(rule_data.get("condition", {"type":"always_true"}))
        cond_outer_fr = ctk.CTkFrame(self.content_frame); cond_outer_fr.grid(row=current_master_row, column=0, columnspan=2, sticky="new", pady=(10,5), padx=5); cond_outer_fr.grid_columnconfigure(0,weight=1); current_master_row+=1
        cond_hdr_fr = ctk.CTkFrame(cond_outer_fr,fg_color="transparent"); cond_hdr_fr.pack(fill="x",padx=0,pady=(0,5))
        ctk.CTkLabel(cond_hdr_fr,text="CONDITION LOGIC",font=ctk.CTkFont(weight="bold")).pack(side="left",anchor="w")
        is_comp = "logical_operator" in cond_data and isinstance(cond_data.get("sub_conditions"),list); btn_txt = "To Single" if is_comp else "To Compound"; self.btn_convert_condition = ctk.CTkButton(cond_hdr_fr,text=btn_txt,command=self.parent_app._convert_condition_structure, width=140); self.btn_convert_condition.pack(side="right",padx=(0,0))
        self.condition_params_frame = ctk.CTkFrame(cond_outer_fr,fg_color="transparent"); self.condition_params_frame.pack(fill="x",expand=True,padx=0,pady=(0,5))
        self._render_rule_condition_editor_internal(cond_data) # Populates self.condition_params_frame
        # Action Section
        act_data = copy.deepcopy(rule_data.get("action", {"type":"log_message"})); act_outer_fr = ctk.CTkFrame(self.content_frame); act_outer_fr.grid(row=current_master_row,column=0,columnspan=2,sticky="new",pady=(10,5),padx=5); act_outer_fr.grid_columnconfigure(0,weight=1); current_master_row+=1
        ctk.CTkLabel(act_outer_fr,text="ACTION TO PERFORM",font=ctk.CTkFont(weight="bold")).pack(anchor="w",padx=0)
        self.action_params_frame = ctk.CTkFrame(act_outer_fr,fg_color="transparent"); self.action_params_frame.pack(fill="x",expand=True,padx=0,pady=(0,5)); self.action_params_frame.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(self.action_params_frame,text="Action Type:").grid(row=0,column=0,sticky="w",padx=(0,5),pady=2); init_act_type=str(act_data.get("type","log_message")); var_act_type=ctk.StringVar(value=init_act_type); menu_act_type=ctk.CTkOptionMenu(self.action_params_frame,variable=var_act_type,values=ALL_ACTION_TYPES,command=lambda choice:self.parent_app._on_rule_part_type_change("action",choice)); menu_act_type.grid(row=0,column=1,sticky="ew",padx=5,pady=2); self.detail_optionmenu_vars["action_type_var"]=var_act_type; self.detail_widgets["action_type"]=menu_act_type
        self._render_dynamic_parameters("actions",init_act_type,act_data,self.action_params_frame,start_row=1,widget_prefix="act_")
        # Apply Button
        ctk.CTkButton(self.content_frame,text="Apply All Rule Changes",command=self.parent_app._apply_rule_changes,height=35,font=ctk.CTkFont(size=14,weight="bold")).grid(row=current_master_row,column=0,columnspan=2,pady=(20,10),padx=10,sticky="ew")

    def _render_rule_condition_editor_internal(self, condition_data_to_display: Dict[str, Any]): # No change from v4.0.0
        if not self.condition_params_frame: return
        for w in self.condition_params_frame.winfo_children(): w.destroy()
        self.condition_params_frame.grid_columnconfigure(1,weight=1)
        self.param_widgets_and_defs_for_current_view.clear(); self.controlling_widgets_for_current_view.clear() # Reset for this view
        is_compound = "logical_operator" in condition_data_to_display and isinstance(condition_data_to_display.get("sub_conditions"), list)
        if is_compound:
            self.current_widget_prefix_for_visibility = "subcond_" # For sub-condition editor
            ctk.CTkLabel(self.condition_params_frame,text="Logical Operator:").grid(row=0,column=0,sticky="w",padx=(0,5),pady=2)
            var_log_op = ctk.StringVar(value=str(condition_data_to_display.get("logical_operator","AND"))); op_menu = ctk.CTkOptionMenu(self.condition_params_frame,variable=var_log_op,values=LOGICAL_OPERATORS,command=lambda c:self.parent_app._set_dirty_status(True)); op_menu.grid(row=0,column=1,sticky="ew",padx=5,pady=2); self.detail_optionmenu_vars["logical_operator_var"]=var_log_op; self.detail_widgets["logical_operator"]=op_menu
            sub_outer_fr = ctk.CTkFrame(self.condition_params_frame,fg_color="transparent"); sub_outer_fr.grid(row=1,column=0,columnspan=2,sticky="nsew",pady=(5,0)); sub_outer_fr.grid_columnconfigure(0,weight=1)
            sc_hdr = ctk.CTkFrame(sub_outer_fr,fg_color="transparent"); sc_hdr.grid(row=0,column=0,sticky="ew",pady=(0,2))
            ctk.CTkLabel(sc_hdr,text="Sub-Conditions:",font=ctk.CTkFont(size=12)).pack(side="left",padx=0)
            self.btn_remove_sub_condition=ctk.CTkButton(sc_hdr,text="- Remove Sel.",width=100,command=self.parent_app._remove_selected_sub_condition,state="disabled"); self.btn_remove_sub_condition.pack(side="right",padx=(2,0))
            ctk.CTkButton(sc_hdr,text="+ Add New",width=80,command=self.parent_app._add_sub_condition_to_rule).pack(side="right",padx=(0,0))
            self.sub_conditions_list_frame = ctk.CTkScrollableFrame(sub_outer_fr,label_text="",height=120,fg_color=("gray90","gray20")); self.sub_conditions_list_frame.grid(row=1,column=0,sticky="nsew",padx=0,pady=2)
            self._populate_sub_conditions_list_internal(condition_data_to_display.get("sub_conditions",[]))
            self.sub_condition_params_frame = ctk.CTkFrame(sub_outer_fr,fg_color="transparent"); self.sub_condition_params_frame.grid(row=2,column=0,sticky="nsew",padx=0,pady=(5,0)); self.sub_condition_params_frame.grid_columnconfigure(1,weight=1)
            if self.parent_app.selected_sub_condition_index is None: ctk.CTkLabel(self.sub_condition_params_frame,text="Select sub-condition above to edit.").pack(padx=5,pady=5)
            else: # If an index is selected (e.g., after adding/re-selecting), render its editor
                sub_conds = condition_data_to_display.get("sub_conditions",[])
                if 0 <= self.parent_app.selected_sub_condition_index < len(sub_conds): self._on_sub_condition_selected_internal(sub_conds[self.parent_app.selected_sub_condition_index], self.parent_app.selected_sub_condition_index, self.selected_sub_condition_item_widget)
        else: # Single condition
            self.current_widget_prefix_for_visibility = "cond_"
            ctk.CTkLabel(self.condition_params_frame,text="Condition Type:").grid(row=0,column=0,sticky="w",padx=(0,5),pady=2)
            curr_cond_type=str(condition_data_to_display.get("type","always_true")); var_cond_type=ctk.StringVar(value=curr_cond_type); menu_cond_type=ctk.CTkOptionMenu(self.condition_params_frame,variable=var_cond_type,values=ALL_CONDITION_TYPES,command=lambda choice:self.parent_app._on_rule_part_type_change("condition",choice)); menu_cond_type.grid(row=0,column=1,sticky="ew",padx=5,pady=2); self.detail_optionmenu_vars["condition_type_var"]=var_cond_type; self.detail_widgets["condition_type"]=menu_cond_type
            self._render_dynamic_parameters("conditions",curr_cond_type,condition_data_to_display,self.condition_params_frame,1,"cond_")
        if self.btn_convert_condition: self.btn_convert_condition.configure(text="To Single" if is_compound else "To Compound")

    def _populate_sub_conditions_list_internal(self, sub_conditions_data: List[Dict[str, Any]]): # No change from v4.0.0
        if not self.sub_conditions_list_frame: return
        for w in self.sub_conditions_list_frame.winfo_children(): w.destroy()
        self.selected_sub_condition_item_widget = None
        if self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled" if self.parent_app.selected_sub_condition_index is None or not sub_conditions_data else "normal")
        for i, sub_cond_data in enumerate(sub_conditions_data):
            s_type = sub_cond_data.get('type','N/A'); s_rgn = f",Rgn:{sub_cond_data.get('region')}" if sub_cond_data.get('region') else ""; s_cap = f",Var:{sub_cond_data.get('capture_as')}" if sub_cond_data.get('capture_as') else ""
            sum_txt = f"#{i+1}: {s_type}{s_rgn}{s_cap}"; sum_txt = sum_txt[:45]+"..." if len(sum_txt)>48 else sum_txt
            item_fr_ref={}; item_fr_w = create_clickable_list_item(self.sub_conditions_list_frame,sum_txt, lambda e=None,scd=sub_cond_data,idx=i,ifr=item_fr_ref: self._on_sub_condition_selected_internal(scd,idx,ifr.get("frame"))); item_fr_ref["frame"]=item_fr_w
            if i == self.parent_app.selected_sub_condition_index: self.parent_app._highlight_selected_list_item("condition",item_fr_w,is_sub_list=True); self.selected_sub_condition_item_widget=item_fr_w
        if self.parent_app.selected_sub_condition_index is None and self.sub_condition_params_frame:
            for w in self.sub_condition_params_frame.winfo_children(): w.destroy()
            ctk.CTkLabel(self.sub_condition_params_frame,text="Select a sub-condition to edit its parameters.").pack(padx=5,pady=5)

    def _on_sub_condition_selected_internal(self, sub_cond_data: Dict[str, Any], new_idx: int, item_frame: Optional[ctk.CTkFrame]): # No change from v4.0.0
        if item_frame is None: return
        prev_sel_idx = self.parent_app.selected_sub_condition_index; rule_idx = self.parent_app.selected_rule_index
        if prev_sel_idx is not None and prev_sel_idx != new_idx and rule_idx is not None:
            rule_model = self.parent_app.profile_data["rules"][rule_idx]; comp_cond_model = rule_model.get("condition",{}); sub_list_model = comp_cond_model.get("sub_conditions",[])
            if 0 <= prev_sel_idx < len(sub_list_model):
                prev_type_var = self.detail_optionmenu_vars.get("subcond_condition_type_var"); prev_type_str = prev_type_var.get() if prev_type_var else sub_list_model[prev_sel_idx].get("type")
                if prev_type_str: params_ui = self._get_parameters_from_ui("conditions", prev_type_str, "subcond_");_ = sub_list_model[prev_sel_idx] = params_ui if params_ui is not None else sub_list_model[prev_sel_idx]; self.parent_app._set_dirty_status(True) if params_ui is not None else None
        self.parent_app.selected_sub_condition_index = new_idx; self.parent_app._highlight_selected_list_item("condition",item_frame,is_sub_list=True); self.selected_sub_condition_item_widget = item_frame
        if self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="normal")
        if not self.sub_condition_params_frame: return
        for w in self.sub_condition_params_frame.winfo_children(): w.destroy()
        self.sub_condition_params_frame.grid_columnconfigure(1,weight=1)
        curr_type = str(sub_cond_data.get("type","always_true"))
        ctk.CTkLabel(self.sub_condition_params_frame,text=f"Editing Sub-Condition #{new_idx+1} / Type:",font=ctk.CTkFont(size=12)).grid(row=0,column=0,padx=(0,5),pady=(5,2),sticky="w")
        var_sub_type = ctk.StringVar(value=curr_type); menu_sub_type = ctk.CTkOptionMenu(self.sub_condition_params_frame,variable=var_sub_type,values=ALL_CONDITION_TYPES,command=lambda choice:self.parent_app._on_rule_part_type_change("condition",choice)); menu_sub_type.grid(row=0,column=1,padx=5,pady=(5,2),sticky="ew"); self.detail_optionmenu_vars["subcond_condition_type_var"]=var_sub_type; self.detail_widgets["subcond_condition_type"]=menu_sub_type
        self._render_dynamic_parameters("conditions",curr_type,sub_cond_data,self.sub_condition_params_frame,1,"subcond_")

    def _render_dynamic_parameters(self, param_group_key: str, item_subtype: str, data_source: Dict[str, Any], parent_frame: ctk.CTkFrame, start_row: int, widget_prefix: str): # Logic as reviewed, uses instance vars for current view state
        # Clear previous widgets for this specific prefix, except type selector
        widgets_to_remove = [k for k in self.detail_widgets if k.startswith(widget_prefix) and k != f"{widget_prefix}type"]
        for key_rem in widgets_to_remove: self.detail_widgets.pop(key_rem,None); self.detail_optionmenu_vars.pop(f"{key_rem}_var",None)
        for child in list(parent_frame.winfo_children()): # Clear from frame
            if child.grid_info().get("row",0) >= start_row: child.destroy()

        self.param_widgets_and_defs_for_current_view = []; self.controlling_widgets_for_current_view = {}; self.current_widget_prefix_for_visibility = widget_prefix
        param_defs = UI_PARAM_CONFIG.get(param_group_key,{}).get(item_subtype,[]); current_r = start_row
        if not param_defs and item_subtype not in ["always_true"]: ctk.CTkLabel(parent_frame,text=f"No params for '{item_subtype}'.").grid(row=current_r,column=0,columnspan=2); return

        for p_def in param_defs:
            p_id, lbl_txt, w_type, d_type, def_val = p_def["id"], p_def["label"], p_def["widget"], p_def["type"], p_def.get("default","")
            cur_val = data_source.get(p_id, def_val); w_key = f"{widget_prefix}{p_id}"
            lbl = ctk.CTkLabel(parent_frame, text=lbl_txt); created_w = None
            if w_type == "entry": entry = ctk.CTkEntry(parent_frame, placeholder_text=str(p_def.get("placeholder",""))); disp_val = ", ".join(cur_val) if d_type == "list_str_csv" and isinstance(cur_val,list) else str(cur_val); entry.insert(0,disp_val); entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True)); created_w=entry
            elif w_type == "textbox": tb = ctk.CTkTextbox(parent_frame, height=p_def.get("height",60), wrap="word"); tb.insert("0.0",str(cur_val)); tb.bind("<FocusOut>", lambda e: self.parent_app._set_dirty_status(True)); created_w=tb
            elif w_type.startswith("optionmenu"):
                opts = []; src_key = p_def.get("options_source") if w_type=="optionmenu_dynamic" else p_def.get("options_const_key")
                if w_type=="optionmenu_dynamic" and src_key=="regions": opts = [""] + [r.get("name","") for r in self.parent_app.profile_data.get("regions",[]) if r.get("name")]
                elif w_type=="optionmenu_dynamic" and src_key=="templates": opts = [""] + [t.get("name","") for t in self.parent_app.profile_data.get("templates",[]) if t.get("name")]
                elif w_type=="optionmenu_static" and src_key: opts = OPTIONS_CONST_MAP.get(src_key, [])
                if not opts: opts = [str(def_val)] if str(def_val) else [""]
                s_cur = str(cur_val); s_cur = s_cur if s_cur in opts else (str(def_val) if str(def_val) in opts else (opts[0] if opts else ""))
                var = ctk.StringVar(value=s_cur); menu = ctk.CTkOptionMenu(parent_frame, variable=var, values=opts, command=lambda choice,p=p_def: self._update_conditional_visibility_dp(p,choice)); self.detail_optionmenu_vars[f"{w_key}_var"]=var; created_w=menu
                if any(opd.get("condition_show",{}).get("field")==p_id for opd in param_defs if opd.get("condition_show")): self.controlling_widgets_for_current_view[p_id]=created_w
            elif w_type == "checkbox": var = tk.BooleanVar(value=bool(cur_val)); cb = ctk.CTkCheckBox(parent_frame, text=lbl_txt, variable=var, command=lambda p=p_def,v=var: self._update_conditional_visibility_dp(p,v.get())); self.detail_optionmenu_vars[f"{w_key}_var"]=var; created_w=cb
                if any(opd.get("condition_show",{}).get("field")==p_id for opd in param_defs if opd.get("condition_show")): self.controlling_widgets_for_current_view[p_id]=created_w
            if created_w:
                self.detail_widgets[w_key] = created_w
                if w_type=="checkbox": created_w.grid(row=current_r,column=0,columnspan=2,padx=(0,5),pady=2,sticky="w")
                else: lbl.grid(row=current_r,column=0,padx=(0,5),pady=2,sticky="nw" if w_type=="textbox" else "w"); created_w.grid(row=current_r,column=1,padx=5,pady=2,sticky="ew")
                self.param_widgets_and_defs_for_current_view.append({"widget":created_w, "label_widget":lbl if w_type!="checkbox" else None, "param_def":p_def})
                current_r+=1
            elif w_type!="checkbox": lbl.destroy()
        self._apply_all_conditional_visibility_dp()

    def _update_conditional_visibility_dp(self, changed_param_def_controller: Dict[str,Any], new_value_of_controller: Any): # Scoped to DetailsPanel
        self.parent_app._set_dirty_status(True); logger.debug(f"DetailsPanel: Controller '{changed_param_def_controller.get('id')}' changed. Re-evaluating visibility for prefix '{self.current_widget_prefix_for_visibility}'.")
        if hasattr(self, 'param_widgets_and_defs_for_current_view') and hasattr(self, 'controlling_widgets_for_current_view') and hasattr(self, 'current_widget_prefix_for_visibility'):
            self._apply_all_conditional_visibility_dp()
        else: logger.warning("DP: Cannot re-apply conditional visibility: current view widget list/prefix not found.")

    def _apply_all_conditional_visibility_dp(self): # Scoped to DetailsPanel
        for item in self.param_widgets_and_defs_for_current_view:
            widget,lbl_w,p_def = item["widget"],item["label_widget"],item["param_def"]
            cfg=p_def.get("condition_show"); visible=True
            if cfg:
                ctrl_id=cfg.get("field"); exp_vals=cfg.get("values",[]); ctrl_widget_inst=self.controlling_widgets_for_current_view.get(ctrl_id); cur_ctrl_val=None
                if isinstance(ctrl_widget_inst,ctk.CTkOptionMenu):var=self.detail_optionmenu_vars.get(f"{self.current_widget_prefix_for_visibility}{ctrl_id}_var");cur_ctrl_val=var.get() if var else None
                elif isinstance(ctrl_widget_inst,ctk.CTkCheckBox):var=self.detail_optionmenu_vars.get(f"{self.current_widget_prefix_for_visibility}{ctrl_id}_var");cur_ctrl_val=var.get() if var else None;exp_vals=[bool(v) for v in exp_vals]
                elif isinstance(ctrl_widget_inst,ctk.CTkEntry):cur_ctrl_val=ctrl_widget_inst.get()
                if cur_ctrl_val is None or cur_ctrl_val not in exp_vals: visible=False
            if widget and widget.winfo_exists():
                is_mapped=widget.winfo_ismapped()
                if visible and not is_mapped: widget.grid();_ = lbl_w.grid() if lbl_w and lbl_w.winfo_exists() and not lbl_w.winfo_ismapped() else None
                elif not visible and is_mapped: widget.grid_remove();_ = lbl_w.grid_remove() if lbl_w and lbl_w.winfo_exists() and lbl_w.winfo_ismapped() else None

    def get_all_rule_data_from_ui(self) -> Optional[Dict[str, Any]]: # No change from v4.0.0
        """Collects all parts of the currently edited rule from the UI and validates them."""
        if self.parent_app.selected_rule_index is None : logger.warning("DP: Get all rule data called, but no rule selected in parent."); return None
        rule_data_model = self.parent_app.profile_data["rules"][self.parent_app.selected_rule_index]
        
        final_rule_data: Dict[str, Any] = {"name": "", "region": "", "condition": {}, "action": {}, "comment": ""}
        all_valid = True

        name_w = self.detail_widgets.get("rule_name"); val,ok = validate_and_get_widget_value(name_w,None,"Rule Name",str,rule_data_model.get("name",""),True); final_rule_data["name"]=val; all_valid&=ok
        region_v = self.detail_optionmenu_vars.get("rule_region_var"); final_rule_data["region"] = region_v.get() if region_v else ""
        comment_w = self.detail_widgets.get("rule_comment"); val,ok = validate_and_get_widget_value(comment_w,None,"Rule Comment",str,rule_data_model.get("comment",""),False,True); final_rule_data["comment"]=val; all_valid&=ok

        # Condition block
        is_compound_ui = "logical_operator_var" in self.detail_optionmenu_vars # Check if compound editor is active
        if is_compound_ui:
            log_op_v = self.detail_optionmenu_vars.get("logical_operator_var"); current_log_op = log_op_v.get() if log_op_v else "AND"
            current_sub_conditions_from_ui = []
            # Iterate over sub-conditions *currently in the data model* because UI list might not reflect non-committed edits to sub-conditions not currently selected for editing
            sub_conds_in_model = rule_data_model.get("condition",{}).get("sub_conditions",[])
            for i, sub_cond_data_model in enumerate(sub_conds_in_model):
                if i == self.parent_app.selected_sub_condition_index: # This is the one currently in the sub-editor
                    sub_type_v = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                    if not sub_type_v: logger.error("DP: Sub-condition type var not found. Cannot get its params."); all_valid=False; break
                    sub_type = sub_type_v.get()
                    sub_params = self._get_parameters_from_ui("conditions",sub_type,"subcond_")
                    if sub_params is None: all_valid=False; break # Validation failed for this sub-condition
                    current_sub_conditions_from_ui.append(sub_params)
                else: # For sub-conditions not currently open in editor, use their existing data from model
                    current_sub_conditions_from_ui.append(copy.deepcopy(sub_cond_data_model))
            if not all_valid: return None # Stop if any sub-condition failed
            final_rule_data["condition"] = {"logical_operator": current_log_op, "sub_conditions": current_sub_conditions_from_ui}
        else: # Single condition
            cond_type_v = self.detail_optionmenu_vars.get("condition_type_var")
            if not cond_type_v: logger.error("DP: Single condition type var not found."); return None
            single_cond_type = cond_type_v.get()
            single_cond_params = self._get_parameters_from_ui("conditions",single_cond_type,"cond_")
            if single_cond_params is None: all_valid=False
            else: final_rule_data["condition"] = single_cond_params
        
        if not all_valid: return None # Stop if condition part failed

        # Action block
        act_type_v = self.detail_optionmenu_vars.get("action_type_var")
        if not act_type_v: logger.error("DP: Action type var not found."); return None
        act_type = act_type_v.get()
        act_params = self._get_parameters_from_ui("actions",act_type,"act_")
        if act_params is None: all_valid=False
        else: final_rule_data["action"] = act_params
        
        if not all_valid: logger.error("DP: Rule data collection failed due to validation errors."); return None
        logger.info(f"DP: Successfully collected all UI data for rule '{final_rule_data['name']}'.")
        return final_rule_data


    def _get_parameters_from_ui(self, param_group_key: str, item_subtype: str, widget_prefix: str) -> Optional[Dict[str, Any]]: # No change from v4.0.0
        params: Dict[str,Any]={"type":item_subtype}; all_ok=True; param_defs=UI_PARAM_CONFIG.get(param_group_key,{}).get(item_subtype,[])
        if not param_defs and item_subtype!="always_true": return params
        for p_def in param_defs:
            p_id,lbl_err,target_type,def_val,is_req_def = p_def["id"],p_def["label"].rstrip(":"),p_def["type"],p_def.get("default",""),p_def.get("required",False)
            w_key=f"{widget_prefix}{p_id}"; widget=self.detail_widgets.get(w_key); tk_var=self.detail_optionmenu_vars.get(f"{w_key}_var")
            is_vis= widget.winfo_ismapped() if widget and widget.winfo_exists() else False
            eff_req = is_req_def and is_vis
            if not is_vis and not eff_req: continue # Skip hidden optional
            if widget is None and not isinstance(tk_var, tk.BooleanVar):
                if eff_req: logger.error(f"DP: Widget for required '{lbl_err}' not found."); all_ok=False
                params[p_id]=def_val; continue
            val_args={"required":eff_req,"allow_empty_string":p_def.get("allow_empty_string",target_type==str),"min_val":p_def.get("min_val"),"max_val":p_def.get("max_val")}
            val,valid = validate_and_get_widget_value(widget,tk_var,lbl_err,target_type,def_val,**val_args)
            if not valid: all_ok=False; val=def_val # Use default but mark invalid
            if target_type=="list_str_csv": params[p_id]=[s.strip() for s in val.split(',') if s.strip()] if isinstance(val,str) and val.strip() else ([] if not def_val or not isinstance(def_val,list) else def_val)
            else: params[p_id]=val
            if p_id=="template_name" and param_group_key=="conditions":
                s_tpl_name=val; params["template_filename"] = "" # Ensure key exists
                if s_tpl_name:
                    fname_actual=next((t.get("filename","") for t in self.parent_app.profile_data.get("templates",[]) if t.get("name")==s_tpl_name),"")
                    if not fname_actual and eff_req: messagebox.showerror("Internal Error",f"Filename for template '{s_tpl_name}' missing.",parent=self);all_ok=False
                    params["template_filename"]=fname_actual
                elif eff_req: messagebox.showerror("Input Error",f"'{lbl_err}' required.",parent=self);all_ok=False
                if "template_name" in params: del params["template_name"]
        if item_subtype=="always_true" and param_group_key=="conditions": # Handle optional region for always_true
            region_pdef=next((pd for pd in param_defs if pd["id"]=="region"),None)
            if region_pdef: val,_ = validate_and_get_widget_value(self.detail_widgets.get(f"{widget_prefix}region"),self.detail_optionmenu_vars.get(f"{widget_prefix}region_var"),"Region",str,"",required=False);_ = params.update({"region":val}) if val else None
        return params if all_ok else None