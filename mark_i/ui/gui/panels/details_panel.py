import logging
import tkinter as tk
from tkinter import messagebox
import os
import copy  # For deepcopying data structures
from typing import Optional, Dict, Any, List, Union, Callable  # Added Callable

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError  # Added UnidentifiedImageError

from mark_i.ui.gui.gui_config import (
    UI_PARAM_CONFIG,
    OPTIONS_CONST_MAP,
    MAX_PREVIEW_WIDTH,
    MAX_PREVIEW_HEIGHT,
    CONDITION_TYPES,
    LOGICAL_OPERATORS,
    ACTION_TYPES,
    GEMINI_TASK_ALLOWED_PRIMITIVE_ACTIONS_FOR_UI_HINT,
)
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value, parse_bgr_string, create_clickable_list_item

logger = logging.getLogger(__name__)  # Standard module logger


class DetailsPanel(ctk.CTkScrollableFrame):
    """
    A CTkScrollableFrame that dynamically displays and allows editing of details
    for a selected item (Region, Template, or Rule) from the MainAppWindow.
    It uses UI_PARAM_CONFIG from gui_config.py to render appropriate input widgets.
    """

    def __init__(self, master: Any, parent_app: Any, **kwargs):  # parent_app is MainAppWindow
        super().__init__(master, label_text="Selected Item Details", **kwargs)
        self.parent_app = parent_app  # Reference to the MainAppWindow instance

        # Stores currently rendered dynamic widgets {widget_full_key: widget_instance}
        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        # Stores Tkinter variables for OptionMenus and CheckBoxes {widget_full_key_var: tk_variable}
        self.detail_optionmenu_vars: Dict[str, Union[tk.StringVar, tk.BooleanVar]] = {}

        # For managing selection highlight in sub-conditions list
        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None

        # Main content frame within the scrollable area
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        self.content_frame.grid_columnconfigure(1, weight=1)  # Make widget column expandable

        # Placeholder label when nothing is selected
        self.label_placeholder = ctk.CTkLabel(
            self.content_frame, text="Select an item from the lists (Regions, Templates, Rules) to see or edit its details here.", wraplength=380, justify="center", font=ctk.CTkFont(size=14)
        )
        self.label_placeholder.pack(padx=20, pady=30, anchor="center", expand=True)

        # Specific UI elements that might be created dynamically
        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None  # For compound rule conditions
        self.condition_params_frame: Optional[ctk.CTkFrame] = None  # For single condition params
        self.action_params_frame: Optional[ctk.CTkFrame] = None  # For action params
        self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None  # For selected sub-condition params
        self.btn_convert_condition: Optional[ctk.CTkButton] = None  # To switch rule condition type
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None  # To remove a sub-condition

        # To store the list of currently rendered dynamic parameter widgets for visibility updates
        self.param_widgets_and_defs_for_current_view: List[Dict[str, Any]] = []
        self.controlling_widgets_for_current_view: Dict[str, Union[ctk.CTkOptionMenu, ctk.CTkCheckBox]] = {}
        self.current_widget_prefix_for_visibility: str = ""

        logger.debug("DetailsPanel initialized.")

    def clear_content(self):
        """Destroys all widgets in the content_frame and clears internal state."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.detail_widgets.clear()
        self.detail_optionmenu_vars.clear()
        self.param_widgets_and_defs_for_current_view.clear()
        self.controlling_widgets_for_current_view.clear()
        self.current_widget_prefix_for_visibility = ""

        # Reset pointers to dynamically created frames/widgets
        self.template_preview_image_label = None
        self.sub_conditions_list_frame = None
        self.condition_params_frame = None
        self.action_params_frame = None
        self.sub_condition_params_frame = None
        self.btn_convert_condition = None
        self.btn_remove_sub_condition = None
        self.selected_sub_condition_item_widget = None  # Ensure this is also reset

        logger.debug("DetailsPanel content cleared.")

    def update_display(self, item_data: Optional[Dict[str, Any]], item_type: str):
        """
        Clears existing content and displays details for the newly selected item.

        Args:
            item_data: The data dictionary of the selected item. None if no item selected.
            item_type: A string indicating the type of item ("region", "template", "rule", "none").
        """
        self.clear_content()  # Clear previous details

        if item_data is None or item_type == "none":
            self.label_placeholder = ctk.CTkLabel(self.content_frame, text="Select an item from the lists to see or edit its details.", wraplength=380, justify="center", font=ctk.CTkFont(size=14))
            self.label_placeholder.pack(padx=20, pady=30, anchor="center", expand=True)
            logger.debug(f"DetailsPanel display updated: Showing placeholder for item_type '{item_type}'.")
            return

        logger.debug(f"DetailsPanel: Updating display for item_type '{item_type}', name '{item_data.get('name', 'N/A')}'.")
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

    def _display_region_details(self, region_data: Dict[str, Any]):
        """Populates the panel with input fields for editing a region's details."""
        logger.debug(f"Displaying region details for: {region_data.get('name', 'Unnamed Region')}")
        self.content_frame.grid_columnconfigure(1, weight=1)  # Ensure entry column expands

        row_idx = 0
        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        name_entry = ctk.CTkEntry(self.content_frame, placeholder_text="Unique region name")
        name_entry.insert(0, str(region_data.get("name", "")))
        name_entry.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        name_entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["name"] = name_entry
        row_idx += 1

        coords = {"x": region_data.get("x", 0), "y": region_data.get("y", 0), "width": region_data.get("width", 100), "height": region_data.get("height", 100)}
        for key, val in coords.items():
            ctk.CTkLabel(self.content_frame, text=f"{key.capitalize()}:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
            entry = ctk.CTkEntry(self.content_frame, placeholder_text=f"Enter {key}")
            entry.insert(0, str(val))
            entry.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
            entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
            self.detail_widgets[key] = entry
            row_idx += 1

        comment = region_data.get("comment", "")
        ctk.CTkLabel(self.content_frame, text="Comment:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="nw")
        comment_textbox = ctk.CTkTextbox(self.content_frame, height=60, wrap="word")
        comment_textbox.insert("0.0", comment)
        comment_textbox.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        comment_textbox.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["comment"] = comment_textbox  # Store Textbox widget
        row_idx += 1

        button_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        button_frame.grid(row=row_idx, column=0, columnspan=2, pady=(15, 10), padx=10, sticky="ew")
        button_frame.grid_columnconfigure(0, weight=1)  # Distribute space for buttons
        button_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(button_frame, text="Apply Region Changes", command=self.parent_app._apply_region_changes).grid(row=0, column=0, padx=(0, 5), sticky="e")
        ctk.CTkButton(button_frame, text="Edit Coords (Selector)", command=self.parent_app._edit_region_coordinates_with_selector).grid(row=0, column=1, padx=(5, 0), sticky="w")

    def _display_template_details(self, template_data: Dict[str, Any]):
        """Populates the panel with fields for editing a template's name and showing its preview."""
        logger.debug(f"Displaying template details for: {template_data.get('name', 'Unnamed Template')}")
        self.content_frame.grid_columnconfigure(1, weight=1)

        row_idx = 0
        ctk.CTkLabel(self.content_frame, text="Name:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        name_entry = ctk.CTkEntry(self.content_frame, placeholder_text="Unique template name")
        name_entry.insert(0, str(template_data.get("name", "")))
        name_entry.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        name_entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["template_name"] = name_entry  # Use a distinct key for template name
        row_idx += 1

        ctk.CTkLabel(self.content_frame, text="Filename:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        filename_label = ctk.CTkLabel(self.content_frame, text=str(template_data.get("filename", "N/A")), anchor="w")
        filename_label.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        row_idx += 1

        comment = template_data.get("comment", "")
        ctk.CTkLabel(self.content_frame, text="Comment:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="nw")
        comment_textbox = ctk.CTkTextbox(self.content_frame, height=60, wrap="word")
        comment_textbox.insert("0.0", comment)
        comment_textbox.grid(row=row_idx, column=1, padx=5, pady=5, sticky="ew")
        comment_textbox.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["comment"] = comment_textbox
        row_idx += 1

        ctk.CTkLabel(self.content_frame, text="Preview:").grid(row=row_idx, column=0, padx=(10, 5), pady=5, sticky="nw")
        self.template_preview_image_label = ctk.CTkLabel(self.content_frame, text="Loading preview...", width=MAX_PREVIEW_WIDTH, height=MAX_PREVIEW_HEIGHT, anchor="w")
        self.template_preview_image_label.grid(row=row_idx, column=1, padx=5, pady=5, sticky="w")
        self._update_template_preview_image(template_data.get("filename"))
        row_idx += 1

        ctk.CTkButton(self.content_frame, text="Apply Template Changes", command=self.parent_app._apply_template_changes).grid(row=row_idx, column=0, columnspan=2, pady=(15, 10), padx=10)

    def _update_template_preview_image(self, filename: Optional[str]):
        """Loads and displays the template image preview."""
        if not self.template_preview_image_label:
            return  # Should not happen if called after _display_template_details

        if not filename or not self.parent_app.current_profile_path:
            self.template_preview_image_label.configure(image=None, text="No preview available (profile not saved or no filename).")
            return

        profile_dir = os.path.dirname(self.parent_app.current_profile_path)
        template_path = os.path.join(profile_dir, "templates", filename)

        if os.path.exists(template_path):
            try:
                img = Image.open(template_path)
                # Create a thumbnail respecting aspect ratio
                img_copy = img.copy()  # Work on a copy
                img_copy.thumbnail((MAX_PREVIEW_WIDTH, MAX_PREVIEW_HEIGHT), Image.Resampling.LANCZOS)

                ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=(img_copy.width, img_copy.height))
                self.template_preview_image_label.configure(image=ctk_img, text="")  # Clear text if image shown
            except UnidentifiedImageError:
                self.template_preview_image_label.configure(image=None, text=f"Error: Cannot identify image file:\n{filename}")
                logger.error(f"Error loading template preview for '{template_path}': UnidentifiedImageError.", exc_info=True)
            except Exception as e:
                self.template_preview_image_label.configure(image=None, text=f"Error loading preview:\n{filename}")
                logger.error(f"Error loading template preview for '{template_path}': {e}", exc_info=True)
        else:
            self.template_preview_image_label.configure(image=None, text=f"File not found:\n{filename}")
            logger.warning(f"Template image file not found for preview: {template_path}")

    def _display_rule_details(self, rule_data: Dict[str, Any]):
        """Populates the panel with UI elements for editing a rule's details, condition, and action."""
        logger.debug(f"Displaying rule details for: {rule_data.get('name', 'Unnamed Rule')}")
        self.parent_app.selected_sub_condition_index = None  # Reset sub-condition selection

        self.content_frame.grid_columnconfigure(1, weight=1)  # Ensure right column expands
        current_master_row = 0

        # --- Rule Name and Default Region ---
        ctk.CTkLabel(self.content_frame, text="Rule Name:").grid(row=current_master_row, column=0, sticky="w", padx=(10, 5), pady=2)
        name_entry = ctk.CTkEntry(self.content_frame, placeholder_text="Unique rule name")
        name_entry.insert(0, rule_data.get("name", ""))
        name_entry.grid(row=current_master_row, column=1, sticky="ew", padx=5, pady=2)
        name_entry.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["rule_name"] = name_entry
        current_master_row += 1

        ctk.CTkLabel(self.content_frame, text="Default Region:").grid(row=current_master_row, column=0, sticky="w", padx=(10, 5), pady=2)
        region_names = [""] + [r.get("name", f"UnnamedRegion_{i}") for i, r in enumerate(self.parent_app.profile_data.get("regions", [])) if r.get("name")]
        var_rule_region = ctk.StringVar(value=str(rule_data.get("region", "")))
        region_menu = ctk.CTkOptionMenu(self.content_frame, variable=var_rule_region, values=region_names, command=lambda c: self.parent_app._set_dirty_status(True))
        region_menu.grid(row=current_master_row, column=1, sticky="ew", padx=5, pady=2)
        self.detail_optionmenu_vars["rule_region_var"] = var_rule_region
        self.detail_widgets["rule_region"] = region_menu
        current_master_row += 1

        comment = rule_data.get("comment", "")
        ctk.CTkLabel(self.content_frame, text="Comment (Rule):").grid(row=current_master_row, column=0, padx=(10, 5), pady=5, sticky="nw")
        rule_comment_textbox = ctk.CTkTextbox(self.content_frame, height=40, wrap="word")
        rule_comment_textbox.insert("0.0", comment)
        rule_comment_textbox.grid(row=current_master_row, column=1, padx=5, pady=5, sticky="ew")
        rule_comment_textbox.bind("<KeyRelease>", lambda e: self.parent_app._set_dirty_status(True))
        self.detail_widgets["rule_comment"] = rule_comment_textbox
        current_master_row += 1

        # --- Condition Editor Section ---
        condition_data_from_profile = copy.deepcopy(rule_data.get("condition", {"type": "always_true"}))

        cond_outer_frame = ctk.CTkFrame(self.content_frame)  # No fg_color makes it use parent's
        cond_outer_frame.grid(row=current_master_row, column=0, columnspan=2, sticky="new", pady=(10, 5), padx=5)
        cond_outer_frame.grid_columnconfigure(0, weight=1)
        current_master_row += 1

        cond_header_frame = ctk.CTkFrame(cond_outer_frame, fg_color="transparent")
        cond_header_frame.pack(fill="x", padx=0, pady=(0, 5))  # No internal padx for header
        ctk.CTkLabel(cond_header_frame, text="CONDITION LOGIC", font=ctk.CTkFont(weight="bold")).pack(side="left", anchor="w")

        is_compound = "logical_operator" in condition_data_from_profile and isinstance(condition_data_from_profile.get("sub_conditions"), list)
        btn_text = "Convert to Single Condition" if is_compound else "Convert to Compound (AND/OR)"
        self.btn_convert_condition = ctk.CTkButton(cond_header_frame, text=btn_text, command=self.parent_app._convert_condition_structure, width=200)
        self.btn_convert_condition.pack(side="right", padx=(0, 0))

        self.condition_params_frame = ctk.CTkFrame(cond_outer_frame, fg_color="transparent")
        self.condition_params_frame.pack(fill="x", expand=True, padx=0, pady=(0, 5))
        # _render_rule_condition_editor_internal will populate self.condition_params_frame
        self._render_rule_condition_editor_internal(condition_data_from_profile)

        # --- Action Editor Section ---
        action_data_from_profile = copy.deepcopy(rule_data.get("action", {"type": "log_message", "message": "Default action"}))

        act_outer_frame = ctk.CTkFrame(self.content_frame)
        act_outer_frame.grid(row=current_master_row, column=0, columnspan=2, sticky="new", pady=(10, 5), padx=5)
        act_outer_frame.grid_columnconfigure(0, weight=1)
        current_master_row += 1
        ctk.CTkLabel(act_outer_frame, text="ACTION TO PERFORM", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=0)

        self.action_params_frame = ctk.CTkFrame(act_outer_frame, fg_color="transparent")
        self.action_params_frame.pack(fill="x", expand=True, padx=0, pady=(0, 5))
        self.action_params_frame.grid_columnconfigure(1, weight=1)  # For param widgets

        ctk.CTkLabel(self.action_params_frame, text="Action Type:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
        initial_action_type = str(action_data_from_profile.get("type", "log_message"))
        var_action_type = ctk.StringVar(value=initial_action_type)
        action_type_menu = ctk.CTkOptionMenu(
            self.action_params_frame, variable=var_action_type, values=ACTION_TYPES, command=lambda choice: self.parent_app._on_rule_part_type_change("action", choice)
        )
        action_type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.detail_optionmenu_vars["action_type_var"] = var_action_type
        self.detail_widgets["action_type"] = action_type_menu
        self._render_dynamic_parameters("actions", initial_action_type, action_data_from_profile, self.action_params_frame, start_row=1, widget_prefix="act_")

        # --- Apply Button ---
        ctk.CTkButton(self.content_frame, text="Apply All Rule Changes", command=self.parent_app._apply_rule_changes, height=35, font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=current_master_row, column=0, columnspan=2, pady=(20, 10), padx=10, sticky="ew"
        )

    def _render_rule_condition_editor_internal(self, condition_data_to_display: Dict[str, Any]):
        """
        Renders the UI elements for editing either a single condition or a compound condition
        (logical operator, list of sub-conditions, and editor for a selected sub-condition).
        Populates self.condition_params_frame.
        """
        if not self.condition_params_frame:
            logger.error("Cannot render rule condition editor: self.condition_params_frame is None.")
            return
        for widget in self.condition_params_frame.winfo_children():  # Clear previous content
            widget.destroy()
        self.condition_params_frame.grid_columnconfigure(1, weight=1)  # Ensure param value column expands

        self.param_widgets_and_defs_for_current_view.clear()  # Reset for this new view
        self.controlling_widgets_for_current_view.clear()
        self.current_widget_prefix_for_visibility = ""

        is_compound = "logical_operator" in condition_data_to_display and isinstance(condition_data_to_display.get("sub_conditions"), list)

        if is_compound:
            self.current_widget_prefix_for_visibility = "subcond_"  # For sub-condition editor
            ctk.CTkLabel(self.condition_params_frame, text="Logical Operator:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
            var_log_op = ctk.StringVar(value=str(condition_data_to_display.get("logical_operator", "AND")))
            op_menu = ctk.CTkOptionMenu(self.condition_params_frame, variable=var_log_op, values=LOGICAL_OPERATORS, command=lambda c: self.parent_app._set_dirty_status(True))
            op_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self.detail_optionmenu_vars["logical_operator_var"] = var_log_op
            self.detail_widgets["logical_operator"] = op_menu

            # Frame for sub-conditions list and its controls
            sub_cond_outer_frame = ctk.CTkFrame(self.condition_params_frame, fg_color="transparent")
            sub_cond_outer_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5, 0))
            sub_cond_outer_frame.grid_columnconfigure(0, weight=1)  # Make sub-cond list expand

            sc_list_header = ctk.CTkFrame(sub_cond_outer_frame, fg_color="transparent")
            sc_list_header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
            ctk.CTkLabel(sc_list_header, text="Sub-Conditions:", font=ctk.CTkFont(size=12, weight="normal")).pack(side="left", padx=(0, 5))
            # Buttons on the right
            self.btn_remove_sub_condition = ctk.CTkButton(sc_list_header, text="- Remove Sel.", width=100, command=self.parent_app._remove_selected_sub_condition, state="disabled")
            self.btn_remove_sub_condition.pack(side="right", padx=(2, 0))
            ctk.CTkButton(sc_list_header, text="+ Add New", width=80, command=self.parent_app._add_sub_condition_to_rule).pack(side="right", padx=(0, 0))

            self.sub_conditions_list_frame = ctk.CTkScrollableFrame(sub_cond_outer_frame, label_text="", height=120, fg_color=("gray90", "gray20"))  # Slightly different bg
            self.sub_conditions_list_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=2)
            self._populate_sub_conditions_list_internal(condition_data_to_display.get("sub_conditions", []))

            # Frame for editing the *selected* sub-condition's parameters
            self.sub_condition_params_frame = ctk.CTkFrame(sub_cond_outer_frame, fg_color="transparent")  # Border for emphasis
            self.sub_condition_params_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=(5, 0))
            self.sub_condition_params_frame.grid_columnconfigure(1, weight=1)
            # Placeholder if no sub-condition is selected yet for editing
            if self.parent_app.selected_sub_condition_index is None:
                ctk.CTkLabel(self.sub_condition_params_frame, text="Select a sub-condition above to edit its parameters.").pack(padx=5, pady=5)
            else:
                # If a sub-condition *is* selected (e.g. after adding one or if one was pre-selected), render its editor
                sub_conds_list = condition_data_to_display.get("sub_conditions", [])
                if 0 <= self.parent_app.selected_sub_condition_index < len(sub_conds_list):
                    self._on_sub_condition_selected_internal(
                        sub_conds_list[self.parent_app.selected_sub_condition_index],
                        self.parent_app.selected_sub_condition_index,
                        self.selected_sub_condition_item_widget,  # Pass the highlighted widget frame if available
                    )

        else:  # Single condition
            self.current_widget_prefix_for_visibility = "cond_"
            ctk.CTkLabel(self.condition_params_frame, text="Condition Type:").grid(row=0, column=0, sticky="w", padx=(0, 5), pady=2)
            current_cond_type = str(condition_data_to_display.get("type", "always_true"))
            var_cond_type = ctk.StringVar(value=current_cond_type)
            cond_type_menu = ctk.CTkOptionMenu(
                self.condition_params_frame, variable=var_cond_type, values=CONDITION_TYPES, command=lambda choice: self.parent_app._on_rule_part_type_change("condition", choice)
            )
            cond_type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self.detail_optionmenu_vars["condition_type_var"] = var_cond_type  # Store the Tk var
            self.detail_widgets["condition_type"] = cond_type_menu  # Store the widget
            # Render parameters for this single condition type
            self._render_dynamic_parameters("conditions", current_cond_type, condition_data_to_display, self.condition_params_frame, start_row=1, widget_prefix="cond_")

        if self.btn_convert_condition:  # Update button text if it exists
            self.btn_convert_condition.configure(text="Convert to Single Condition" if is_compound else "Convert to Compound (AND/OR)")

    def _populate_sub_conditions_list_internal(self, sub_conditions_data: List[Dict[str, Any]]):
        """Populates the scrollable list of sub-conditions for a compound rule condition."""
        if not self.sub_conditions_list_frame:
            logger.error("Cannot populate sub-conditions: self.sub_conditions_list_frame is None.")
            return
        for widget in self.sub_conditions_list_frame.winfo_children():  # Clear previous items
            widget.destroy()

        self.selected_sub_condition_item_widget = None  # Reset highlight tracking for this list

        if self.btn_remove_sub_condition:  # Update remove button state
            self.btn_remove_sub_condition.configure(state="disabled" if self.parent_app.selected_sub_condition_index is None or not sub_conditions_data else "normal")

        for i, sub_cond_item_data in enumerate(sub_conditions_data):
            # Create a summary string for the list item
            item_type_str = sub_cond_item_data.get("type", "N/A")
            item_region_str = f", Rgn: {sub_cond_item_data.get('region')}" if sub_cond_item_data.get("region") else ""
            item_capture_str = f", Var: {sub_cond_item_data.get('capture_as')}" if sub_cond_item_data.get("capture_as") else ""
            summary_text = f"#{i+1}: {item_type_str}{item_region_str}{item_capture_str}"
            if len(summary_text) > 45:
                summary_text = summary_text[:42] + "..."

            item_frame_container = {}  # To pass the frame by reference for the callback
            item_frame_widget = create_clickable_list_item(
                self.sub_conditions_list_frame,
                summary_text,
                # Lambda needs to capture current values of i, sub_cond_item_data, and item_frame_container
                lambda event=None, scd=sub_cond_item_data, idx=i, ifc=item_frame_container: self._on_sub_condition_selected_internal(scd, idx, ifc.get("frame")),
            )
            item_frame_container["frame"] = item_frame_widget  # Store the created frame in the dict for the lambda

            # If this index matches a re-selected index, highlight it
            if i == self.parent_app.selected_sub_condition_index:
                self.parent_app._highlight_selected_list_item("condition", item_frame_widget, is_sub_list=True)  # Pass the sub-list context
                self.selected_sub_condition_item_widget = item_frame_widget  # Store the specific widget

    def _on_sub_condition_selected_internal(self, sub_cond_data_from_list: Dict[str, Any], new_selected_idx: int, item_widget_frame_clicked: Optional[ctk.CTkFrame]):
        """Handles selection of a sub-condition from the list within a compound rule."""
        if item_widget_frame_clicked is None:
            logger.warning("Attempted to select sub-condition, but its UI frame is None.")
            return

        log_prefix_sub_sel = f"Rule '{self.parent_app.profile_data['rules'][self.parent_app.selected_rule_index]['name'] if self.parent_app.selected_rule_index is not None else 'N/A'}'"

        # --- Commit changes for the PREVIOUSLY selected sub-condition (if any) ---
        # This is crucial to save any edits before switching to display another sub-condition.
        previously_selected_sub_idx = self.parent_app.selected_sub_condition_index
        if previously_selected_sub_idx is not None and previously_selected_sub_idx != new_selected_idx and self.parent_app.selected_rule_index is not None:

            logger.debug(f"{log_prefix_sub_sel}: Sub-condition selection changing from index {previously_selected_sub_idx} to {new_selected_idx}. Attempting to commit changes for old index.")

            # Get the current rule data from parent_app's profile_data
            rule_data_model = self.parent_app.profile_data["rules"][self.parent_app.selected_rule_index]
            compound_cond_block_model = rule_data_model.get("condition", {})
            sub_conds_list_model = compound_cond_block_model.get("sub_conditions", [])

            if 0 <= previously_selected_sub_idx < len(sub_conds_list_model):
                # Get type of the previously selected sub-condition from its TkVar (if available) or data model
                prev_sub_cond_type_tkvar = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                prev_sub_cond_type_str = prev_sub_cond_type_tkvar.get() if prev_sub_cond_type_tkvar else sub_conds_list_model[previously_selected_sub_idx].get("type")

                if prev_sub_cond_type_str:
                    logger.debug(f"{log_prefix_sub_sel}: Committing sub-condition at index {previously_selected_sub_idx} of type '{prev_sub_cond_type_str}' before switching.")
                    params_from_ui_for_prev_sub = self._get_parameters_from_ui("conditions", prev_sub_cond_type_str, "subcond_")

                    if params_from_ui_for_prev_sub is not None:  # UI validation passed for the old sub-condition
                        sub_conds_list_model[previously_selected_sub_idx] = params_from_ui_for_prev_sub
                        self.parent_app._set_dirty_status(True)  # Mark profile as dirty
                        logger.info(
                            f"{log_prefix_sub_sel}: Committed UI changes for sub-cond index {previously_selected_sub_idx} to profile_data model. New data: {sub_conds_list_model[previously_selected_sub_idx]}"
                        )
                    else:
                        logger.warning(
                            f"{log_prefix_sub_sel}: Validation failed for sub-cond index {previously_selected_sub_idx} before switching. Its changes were NOT saved to profile_data model. User might need to re-select and fix."
                        )
                        # Optionally, prevent switching or revert UI if validation fails. For now, it proceeds.
            else:
                logger.warning(f"{log_prefix_sub_sel}: Previously selected sub-cond index {previously_selected_sub_idx} out of bounds. Cannot commit its changes.")
        # --- End commit for previously selected sub-condition ---

        # Update selection state
        self.parent_app.selected_sub_condition_index = new_selected_idx
        self.parent_app._highlight_selected_list_item("condition", item_widget_frame_clicked, is_sub_list=True)
        self.selected_sub_condition_item_widget = item_widget_frame_clicked

        if self.btn_remove_sub_condition:  # Enable remove button for the newly selected sub-condition
            self.btn_remove_sub_condition.configure(state="normal")

        if not self.sub_condition_params_frame:  # Should be created by _render_rule_condition_editor_internal
            logger.error(f"{log_prefix_sub_sel}: self.sub_condition_params_frame is None. Cannot render editor for selected sub-condition.")
            return

        # Clear and re-render the editor for the NEWLY selected sub-condition
        for widget in self.sub_condition_params_frame.winfo_children():
            widget.destroy()
        self.sub_condition_params_frame.grid_columnconfigure(1, weight=1)  # Ensure param value col expands

        # Data for the newly selected sub-condition (passed in as sub_cond_data_from_list_item)
        current_sub_cond_type = str(sub_cond_data_from_list.get("type", "always_true"))

        # Header for the sub-condition editor part
        ctk.CTkLabel(self.sub_condition_params_frame, text=f"Editing Sub-Condition #{new_selected_idx + 1} / Type:", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=(0, 5), pady=(5, 2), sticky="w"
        )

        var_sub_cond_type_new = ctk.StringVar(value=current_sub_cond_type)
        sub_cond_type_menu = ctk.CTkOptionMenu(
            self.sub_condition_params_frame,
            variable=var_sub_cond_type_new,
            values=CONDITION_TYPES,
            command=lambda choice: self.parent_app._on_rule_part_type_change("condition", choice),  # This callback refers to the currently selected sub_cond
        )
        sub_cond_type_menu.grid(row=0, column=1, padx=5, pady=(5, 2), sticky="ew")
        self.detail_optionmenu_vars["subcond_condition_type_var"] = var_sub_cond_type_new  # Store Tk var for the selected sub-condition
        self.detail_widgets["subcond_condition_type"] = sub_cond_type_menu  # Store widget

        # Render dynamic parameters for this newly selected sub-condition
        self._render_dynamic_parameters(
            param_group_key="conditions",
            item_subtype=current_sub_cond_type,
            data_source=sub_cond_data_from_list,  # Use the data of the sub-condition item clicked
            parent_frame=self.sub_condition_params_frame,
            start_row=1,  # Parameters start from row 1 in sub_condition_params_frame
            widget_prefix="subcond_",
        )
        logger.info(f"{log_prefix_sub_sel}: Displayed editor for sub-condition index {new_selected_idx} (type: {current_sub_cond_type}).")

    def _render_dynamic_parameters(self, param_group_key: str, item_subtype: str, data_source: Dict[str, Any], parent_frame: ctk.CTkFrame, start_row: int, widget_prefix: str):
        """
        Dynamically creates and places UI widgets for parameters of a given condition/action subtype.
        Also handles setting up conditional visibility logic.
        """
        # Clear previous dynamic widgets for this specific prefix, except the type selector itself
        widgets_to_remove_keys = [k for k in self.detail_widgets if k.startswith(widget_prefix) and k != f"{widget_prefix}type"]
        for key_to_remove in widgets_to_remove_keys:
            widget = self.detail_widgets.pop(key_to_remove, None)
            if widget and widget.winfo_exists():
                widget.destroy()
            self.detail_optionmenu_vars.pop(f"{key_to_remove}_var", None)

        # Clear only widgets from start_row downwards in the specific parent_frame
        for child_widget in list(parent_frame.winfo_children()):
            grid_info = child_widget.grid_info()
            if grid_info and grid_info.get("row", -1) >= start_row:
                child_widget.destroy()

        param_definitions = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])
        current_render_row = start_row

        # Store created widgets and their definitions for this rendering pass
        # These will be used by _apply_all_conditional_visibility
        self.param_widgets_and_defs_for_current_view = []
        self.controlling_widgets_for_current_view = {}
        self.current_widget_prefix_for_visibility = widget_prefix

        if not param_definitions and item_subtype not in ["always_true"]:  # "always_true" might have an optional region
            no_params_label = ctk.CTkLabel(parent_frame, text=f"No parameters defined for type '{item_subtype}'.")
            no_params_label.grid(row=current_render_row, column=0, columnspan=2, sticky="w", padx=(0, 5), pady=2)
            # Store it so it can be cleared if type changes again
            self.param_widgets_and_defs_for_current_view.append({"widget": no_params_label, "label_widget": None, "param_def": {}, "row": current_render_row})
            return

        for p_def in param_definitions:
            param_id = p_def["id"]
            label_text = p_def["label"]
            widget_type = p_def["widget"]
            data_type = p_def["type"]  # Actual data type for validation
            default_value = p_def.get("default", "")
            # Get current value from data_source, fallback to default if not present
            current_value_from_data = data_source.get(param_id, default_value)

            widget_key_full = f"{widget_prefix}{param_id}"

            # --- Create Label ---
            param_label_widget = ctk.CTkLabel(parent_frame, text=label_text)
            # Checkbox handles its own label text via its 'text' property
            if widget_type != "checkbox":
                param_label_widget.grid(row=current_render_row, column=0, padx=(0, 5), pady=2, sticky="nw" if widget_type == "textbox" else "w")

            # --- Create Input Widget ---
            created_widget: Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox, None] = None

            if widget_type == "entry":
                entry_widget = ctk.CTkEntry(parent_frame, placeholder_text=str(p_def.get("placeholder", "")))
                # Handle list_str_csv for display in entry: join list to string
                display_value = ", ".join(current_value_from_data) if data_type == "list_str_csv" and isinstance(current_value_from_data, list) else str(current_value_from_data)
                entry_widget.insert(0, display_value)
                entry_widget.bind("<KeyRelease>", lambda e, wk=widget_key_full: self.parent_app._set_dirty_status(True))
                created_widget = entry_widget
            elif widget_type == "textbox":
                textbox_height = p_def.get("height", 80)
                text_widget = ctk.CTkTextbox(parent_frame, height=textbox_height, wrap="word")
                text_widget.insert("0.0", str(current_value_from_data))
                text_widget.bind("<FocusOut>", lambda e, wk=widget_key_full: self.parent_app._set_dirty_status(True))  # Mark dirty on focus out
                created_widget = text_widget
            elif widget_type.startswith("optionmenu"):
                options_list = []
                is_dynamic_options = widget_type == "optionmenu_dynamic"
                options_key = p_def.get("options_source") if is_dynamic_options else p_def.get("options_const_key")

                if is_dynamic_options and options_key:
                    if options_key == "regions":
                        options_list = [""] + [r.get("name", "") for r in self.parent_app.profile_data.get("regions", []) if r.get("name")]
                    elif options_key == "templates":
                        options_list = [""] + [t.get("name", "") for t in self.parent_app.profile_data.get("templates", []) if t.get("name")]
                elif not is_dynamic_options and options_key:  # static
                    options_list = OPTIONS_CONST_MAP.get(options_key, [])

                if not options_list:
                    options_list = [str(default_value)] if str(default_value) else [""]  # Fallback

                # Ensure current_value_from_data is a string and exists in options, or use default/first
                str_curr_val = str(current_value_from_data)
                if str_curr_val not in options_list:
                    str_curr_val = str(default_value) if str(default_value) in options_list else (options_list[0] if options_list else "")

                tk_var = ctk.StringVar(value=str_curr_val)
                optionmenu_widget = ctk.CTkOptionMenu(
                    parent_frame,
                    variable=tk_var,
                    values=options_list,
                    command=lambda choice, p=p_def, wk=widget_key_full: (self.parent_app._set_dirty_status(True), self._update_conditional_visibility(p, choice)),
                )  # Pass p_def and new_value
                self.detail_optionmenu_vars[f"{widget_key_full}_var"] = tk_var
                created_widget = optionmenu_widget
                # If this OptionMenu controls visibility of other fields
                if any(other_p_def.get("condition_show", {}).get("field") == param_id for other_p_def in param_definitions if other_p_def.get("condition_show")):
                    self.controlling_widgets_for_current_view[param_id] = created_widget

            elif widget_type == "checkbox":
                tk_bool_var = tk.BooleanVar(value=bool(current_value_from_data))
                # Label text is set directly on CTkCheckBox
                checkbox_widget = ctk.CTkCheckBox(
                    parent_frame,
                    text=label_text,
                    variable=tk_bool_var,
                    command=lambda p=p_def, wk=widget_key_full, v=tk_bool_var: (self.parent_app._set_dirty_status(True), self._update_conditional_visibility(p, v.get())),
                )  # Pass p_def and new_value
                self.detail_optionmenu_vars[f"{widget_key_full}_var"] = tk_bool_var
                created_widget = checkbox_widget
                if any(other_p_def.get("condition_show", {}).get("field") == param_id for other_p_def in param_definitions if other_p_def.get("condition_show")):
                    self.controlling_widgets_for_current_view[param_id] = created_widget

            if created_widget:
                self.detail_widgets[widget_key_full] = created_widget
                if widget_type == "checkbox":  # Checkbox takes columnspan and its own label
                    created_widget.grid(row=current_render_row, column=0, columnspan=2, padx=(0, 5), pady=2, sticky="w")
                else:  # Others have separate label in col 0, widget in col 1
                    created_widget.grid(row=current_render_row, column=1, padx=5, pady=2, sticky="ew")

                self.param_widgets_and_defs_for_current_view.append(
                    {"widget": created_widget, "label_widget": param_label_widget if widget_type != "checkbox" else None, "param_def": p_def, "row": current_render_row}
                )
                current_render_row += 1
            else:  # Should not happen if widget_type is valid
                if widget_type != "checkbox":  # Checkbox label is part of widget, so no separate label destroyed
                    param_label_widget.destroy()

        # After all widgets for this subtype are created, apply initial visibility based on controller states
        self._apply_all_conditional_visibility(self.param_widgets_and_defs_for_current_view, self.controlling_widgets_for_current_view, widget_prefix)

    def _update_conditional_visibility(self, changed_param_def_controller: Dict[str, Any], new_value_of_controller: Any):
        """
        Called when a controlling widget's value changes.
        Re-evaluates and applies visibility for all dynamic parameters in the current view.
        """
        self.parent_app._set_dirty_status(True)  # Mark dirty as a controlling value changed
        logger.debug(
            f"Controller '{changed_param_def_controller.get('id')}' value changed to '{new_value_of_controller}'. Re-evaluating conditional visibility for prefix '{self.current_widget_prefix_for_visibility}'."
        )

        # Re-apply visibility to all currently rendered dynamic parameters
        # This uses the lists that were populated by the last call to _render_dynamic_parameters
        if hasattr(self, "param_widgets_and_defs_for_current_view") and hasattr(self, "controlling_widgets_for_current_view") and hasattr(self, "current_widget_prefix_for_visibility"):
            self._apply_all_conditional_visibility(self.param_widgets_and_defs_for_current_view, self.controlling_widgets_for_current_view, self.current_widget_prefix_for_visibility)
        else:
            logger.warning("Cannot re-apply conditional visibility: current view widget/definition list or prefix not found. This may happen if no dynamic params were rendered.")

    def _apply_all_conditional_visibility(self, param_widgets_and_defs_list: list, controlling_widgets_map: dict, widget_prefix_of_view: str):
        """
        Iterates all rendered dynamic params in the current view and sets their visibility
        based on their 'condition_show' config and the current values of their controllers.

        Args:
            param_widgets_and_defs_list: List of {"widget": widget, "label_widget": label, "param_def": p_def, "row": r_idx}
            controlling_widgets_map: Dict of {param_id_of_controller: controller_widget_instance}
            widget_prefix_of_view: The prefix (e.g., "act_", "cond_") for widgets in this view.
        """
        # logger.debug(f"Applying all conditional visibility for prefix '{widget_prefix_of_view}'. Total items: {len(param_widgets_and_defs_list)}")

        for item_info in param_widgets_and_defs_list:
            widget_instance = item_info["widget"]
            label_widget_instance = item_info["label_widget"]  # Can be None for checkboxes
            p_def_for_item = item_info["param_def"]

            condition_show_config = p_def_for_item.get("condition_show")
            should_be_visible_based_on_condition = True  # Default to visible

            if condition_show_config:
                controller_param_id = condition_show_config.get("field")  # ID of the controlling field
                expected_controller_trigger_values = condition_show_config.get("values", [])

                # Get the controlling widget instance using the prefix and its ID
                # Note: controlling_widgets_map stores controller_widget_instance by its plain param_id, not prefixed key.
                controller_widget = controlling_widgets_map.get(controller_param_id)

                current_value_of_controller_widget: Any = None

                if isinstance(controller_widget, ctk.CTkOptionMenu):
                    # Construct the Tk variable key for this controller OptionMenu
                    controller_tk_var_key = f"{widget_prefix_of_view}{controller_param_id}_var"
                    controller_tk_var = self.detail_optionmenu_vars.get(controller_tk_var_key)
                    if controller_tk_var and isinstance(controller_tk_var, tk.StringVar):
                        current_value_of_controller_widget = controller_tk_var.get()
                elif isinstance(controller_widget, ctk.CTkCheckBox):
                    controller_tk_var_key = f"{widget_prefix_of_view}{controller_param_id}_var"
                    controller_tk_var = self.detail_optionmenu_vars.get(controller_tk_var_key)
                    if controller_tk_var and isinstance(controller_tk_var, tk.BooleanVar):
                        current_value_of_controller_widget = controller_tk_var.get()
                        # Ensure expected_values are boolean for checkbox controller comparison
                        expected_controller_trigger_values = [bool(v) for v in expected_controller_trigger_values]
                elif isinstance(controller_widget, ctk.CTkEntry):  # Less common for a controller
                    current_value_of_controller_widget = controller_widget.get()

                if current_value_of_controller_widget is None:  # Controller state unknown
                    should_be_visible_based_on_condition = False  # Hide if controller state is problematic
                    # logger.debug(f"Param '{p_def_for_item['id']}': Controller '{controller_param_id}' state unknown. Hiding.")
                elif current_value_of_controller_widget not in expected_controller_trigger_values:
                    should_be_visible_based_on_condition = False
                    # logger.debug(f"Param '{p_def_for_item['id']}': Controller '{controller_param_id}' value '{current_value_of_controller_widget}' not in {expected_controller_trigger_values}. Hiding.")
                # else: logger.debug(f"Param '{p_def_for_item['id']}': Controller '{controller_param_id}' value '{current_value_of_controller_widget}' IS in {expected_controller_trigger_values}. Showing.")

            # Apply visibility to the widget and its label
            if widget_instance and widget_instance.winfo_exists():
                is_currently_mapped = widget_instance.winfo_ismapped()
                if should_be_visible_based_on_condition:
                    if not is_currently_mapped:
                        widget_instance.grid()  # Re-grid if it was hidden
                        if label_widget_instance and label_widget_instance.winfo_exists() and not label_widget_instance.winfo_ismapped():
                            label_widget_instance.grid()
                else:  # Should be hidden
                    if is_currently_mapped:
                        widget_instance.grid_remove()
                        if label_widget_instance and label_widget_instance.winfo_exists() and label_widget_instance.winfo_ismapped():
                            label_widget_instance.grid_remove()
            # else: logger.warning(f"Widget for param '{p_def_for_item.get('id')}' does not exist or not found during visibility update.")

    def _get_parameters_from_ui(self, param_group_key: str, item_subtype: str, widget_prefix: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves and validates all parameters for a given item subtype from the currently displayed UI widgets.
        Handles conditional parameter requirement based on visibility.
        Parses 'list_str_csv' type for parameters like context_region_names.
        """
        params: Dict[str, Any] = {"type": item_subtype}  # Always include the type
        all_overall_params_valid = True  # Tracks validity of all effectively required fields
        param_definitions = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])

        if not param_definitions and item_subtype != "always_true":
            logger.debug(f"No parameters defined to get for '{param_group_key}/{item_subtype}' (prefix: {widget_prefix}). Returning only type.")
            return params

        for p_def in param_definitions:
            param_id = p_def["id"]
            widget_key_full = f"{widget_prefix}{param_id}"
            label_for_error = p_def["label"].rstrip(":")
            target_type = p_def["type"]
            default_from_config = p_def["default"]
            is_required_by_definition = p_def.get("required", False)

            widget_instance = self.detail_widgets.get(widget_key_full)
            tk_variable_instance = self.detail_optionmenu_vars.get(f"{widget_key_full}_var")

            # Determine if the widget is currently visible and gridded (should be on screen)
            is_effectively_visible = False
            if widget_instance and widget_instance.winfo_exists() and widget_instance.winfo_ismapped():
                is_effectively_visible = True

            # A parameter is effectively required if its definition says so AND it's currently visible.
            # If it's hidden due to condition_show, it's not required for submission from UI.
            is_effectively_required = is_required_by_definition and is_effectively_visible

            if not is_effectively_visible and not is_effectively_required:
                # If param is hidden by conditional logic and not strictly required in that state,
                # we might skip it or include its default. For safety and to ensure backend doesn't
                # miss an expected optional key, let's include its default if it's not required.
                # If it *was* required by definition but is hidden, it's a tricky case - usually means
                # it should not be part of the submitted data.
                # For now: if not visible, don't try to get value, it won't be in params.
                # If backend needs all keys, then add default_from_config here.
                logger.debug(f"Parameter '{param_id}' for '{item_subtype}' is not currently visible/gridded, skipping value retrieval for UI submission.")
                continue  # Skip trying to get value from a hidden widget

            # If widget_instance is None but it's a checkbox (which relies on tk_variable_instance)
            if widget_instance is None and not isinstance(tk_variable_instance, tk.BooleanVar):
                if is_effectively_required:  # Only error if it was supposed to be there and required
                    logger.error(f"Widget for required field '{label_for_error}' (key: {widget_key_full}) not found. Cannot get parameter.")
                    all_overall_params_valid = False
                params[param_id] = default_from_config  # Assign default even if widget missing, if key needed
                continue

            # Prepare args for validation util
            validation_config_args = {
                "required": is_effectively_required,  # Use the determined effective required status
                "allow_empty_string": p_def.get("allow_empty_string", target_type == str),
                "min_val": p_def.get("min_val"),
                "max_val": p_def.get("max_val"),
            }

            value_from_widget, is_value_valid = validate_and_get_widget_value(widget_instance, tk_variable_instance, label_for_error, target_type, default_from_config, **validation_config_args)

            if not is_value_valid:
                all_overall_params_valid = False
                # `validate_and_get_widget_value` returns default_from_config on validation failure.
                # We store this default (or a type-appropriate empty) to ensure the key exists if expected,
                # but the overall form submission will be marked invalid if any required field fails.
                if target_type == str:
                    params[param_id] = "" if p_def.get("allow_empty_string") else default_from_config
                elif target_type == int:
                    params[param_id] = 0 if not isinstance(default_from_config, int) else default_from_config
                elif target_type == float:
                    params[param_id] = 0.0 if not isinstance(default_from_config, float) else default_from_config
                elif target_type == bool:
                    params[param_id] = False if not isinstance(default_from_config, bool) else default_from_config
                elif target_type == "bgr_string":
                    params[param_id] = [0, 0, 0] if not (isinstance(default_from_config, list) and len(default_from_config) == 3) else default_from_config
                elif target_type == "list_str_csv":
                    params[param_id] = [] if not isinstance(default_from_config, list) else default_from_config
                else:
                    params[param_id] = default_from_config

                if is_effectively_required:
                    logger.error(f"Effectively required field '{label_for_error}' for '{item_subtype}' failed validation.")
            else:  # Value is valid
                if target_type == "list_str_csv":  # Parse CSV string from entry into a list of strings
                    if isinstance(value_from_widget, str) and value_from_widget.strip():
                        params[param_id] = [s.strip() for s in value_from_widget.split(",") if s.strip()]
                    elif isinstance(value_from_widget, list):  # Should not happen if widget is entry, but defensive
                        params[param_id] = value_from_widget
                    else:  # Empty string from entry or not a string -> empty list or default
                        params[param_id] = [] if not default_from_config or not isinstance(default_from_config, list) else default_from_config
                else:
                    params[param_id] = value_from_widget

            # Special handling for 'template_name' (used in UI) to store 'template_filename' (used by engine)
            if param_id == "template_name" and param_group_key == "conditions":
                selected_template_name_ui = value_from_widget  # This is the name string from OptionMenu
                if selected_template_name_ui:
                    # Find the corresponding filename from profile_data.templates
                    actual_filename_for_engine = next(
                        (t.get("filename", "") for t in self.parent_app.profile_data.get("templates", []) if t.get("name") == selected_template_name_ui), ""  # Default to empty string if not found
                    )
                    if not actual_filename_for_engine and is_effectively_required:
                        # This implies UI shows a template name that doesn't map to a file in data
                        messagebox.showerror("Internal Data Error", f"Could not find filename for selected template '{selected_template_name_ui}'. Data inconsistency likely.")
                        all_overall_params_valid = False  # Critical if required
                    params["template_filename"] = actual_filename_for_engine
                elif is_effectively_required:  # Template name is required, but UI selection ('value_from_widget') is empty
                    messagebox.showerror("Input Error", f"'{label_for_error}' (template selection) is required but not selected.")
                    all_overall_params_valid = False
                    params["template_filename"] = ""  # Ensure key exists, even if invalid
                else:  # Not required and empty selection
                    params["template_filename"] = ""
                if "template_name" in params:  # Remove the UI-only key if it was added
                    del params["template_name"]

        # For "always_true" condition, if it only had an optional region and it wasn't set,
        # params will just be {"type": "always_true"}. If region was set, it's included.
        if item_subtype == "always_true" and param_group_key == "conditions":
            region_param_def = next((pd for pd in param_definitions if pd["id"] == "region"), None)
            if region_param_def:
                widget_key = f"{widget_prefix}{region_param_def['id']}"
                widget_instance = self.detail_widgets.get(widget_key)
                tk_var_instance = self.detail_optionmenu_vars.get(f"{widget_key}_var")
                val, _ = validate_and_get_widget_value(
                    widget_instance,
                    tk_var_instance,
                    region_param_def["label"].rstrip(":"),
                    region_param_def["type"],
                    region_param_def["default"],
                    required=False,  # Region is optional for always_true
                )
                if val:  # Only include 'region' key if a value was actually selected
                    params[region_param_def["id"]] = val

        logger.debug(f"Collected parameters for '{param_group_key}/{item_subtype}' (prefix '{widget_prefix}'): {params}. Overall validity: {all_overall_params_valid}")
        return params if all_overall_params_valid else None  # Return None if any effectively required field failed validation

    # Other methods (_on_sub_condition_selected_internal, _populate_sub_conditions_list_internal)
    # remain largely as previously defined, ensuring they correctly use self.parent_app for callbacks
    # and state related to the main application window.
    # They also need to correctly handle the `param_widgets_and_defs_for_current_view`
    # and `controlling_widgets_for_current_view` for visibility updates if they re-render parts.
