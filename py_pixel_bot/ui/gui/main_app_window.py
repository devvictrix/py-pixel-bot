import logging
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
import copy
import shutil
from typing import Optional, Dict, Any, List, Callable, Union

import customtkinter as ctk
from PIL import Image

try:
    from ...core.config_manager import ConfigManager
    from .region_selector import RegionSelectorWindow
    from .gui_config import (DEFAULT_PROFILE_STRUCTURE, CONDITION_TYPES, ACTION_TYPES,
                             UI_PARAM_CONFIG, OPTIONS_CONST_MAP) # Import new config
    from .gui_utils import validate_and_get_widget_value, parse_bgr_string, create_clickable_list_item # Import new utils
    from .panels.details_panel import DetailsPanel # Import the new DetailsPanel
except ImportError:
    from py_pixel_bot.core.config_manager import ConfigManager
    from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow
    from py_pixel_bot.ui.gui.gui_config import (DEFAULT_PROFILE_STRUCTURE, CONDITION_TYPES, ACTION_TYPES,
                                               UI_PARAM_CONFIG, OPTIONS_CONST_MAP)
    from py_pixel_bot.ui.gui.gui_utils import validate_and_get_widget_value, parse_bgr_string, create_clickable_list_item
    from py_pixel_bot.ui.gui.panels.details_panel import DetailsPanel


logger = logging.getLogger(__name__)

class MainAppWindow(ctk.CTk):
    def __init__(self, initial_profile_path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing MainAppWindow...")
        self.title("PyPixelBot Profile Editor")
        self.geometry("1350x800")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.current_profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self._is_dirty: bool = False

        self.selected_region_index: Optional[int] = None
        self.selected_template_index: Optional[int] = None
        self.selected_rule_index: Optional[int] = None
        self.selected_sub_condition_index: Optional[int] = None # Managed by DetailsPanel, but MainApp might need to know for context

        # References to UI elements for list highlighting (might be simplified further)
        self.selected_region_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_template_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_rule_item_widget: Optional[ctk.CTkFrame] = None
        # self.selected_sub_condition_item_widget is managed within DetailsPanel now

        self._setup_ui() # Sets up panels

        if initial_profile_path:
            self._load_profile_from_path(initial_profile_path)
        else:
            self._new_profile(prompt_save=False)

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        logger.info("MainAppWindow initialization complete.")

    def _setup_ui(self):
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Profile", command=self._new_profile, accelerator="Ctrl+N")
        file_menu.add_command(label="Open Profile...", command=self._open_profile, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save Profile", command=self._save_profile, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Profile As...", command=self._save_profile_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close_window)
        
        self.bind_all("<Control-n>", lambda e: self._new_profile())
        self.bind_all("<Control-o>", lambda e: self._open_profile())
        self.bind_all("<Control-s>", lambda e: self._save_profile())
        self.bind_all("<Control-S>", lambda e: self._save_profile_as())
                
        self.grid_columnconfigure(0, weight=1, minsize=300) # Left Panel
        self.grid_columnconfigure(1, weight=2, minsize=350) # Center Panel
        self.grid_columnconfigure(2, weight=2, minsize=400) # Right Panel (DetailsPanel)
        self.grid_rowconfigure(0, weight=1)
        
        # Left Panel (Profile Info, Regions, Templates)
        self.left_panel = ctk.CTkFrame(self, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0,2), pady=0)
        self._setup_left_panel_content() # Method to populate left panel
        
        # Center Panel (Rules List)
        self.center_panel = ctk.CTkFrame(self, corner_radius=0)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=(0,2), pady=0)
        self._setup_center_panel_content() # Method to populate center panel
        
        # Right Panel (Details - managed by DetailsPanel class)
        self.details_panel_instance = DetailsPanel(self, parent_app=self)
        self.details_panel_instance.grid(row=0, column=2, sticky="nsew", padx=(0,0), pady=0)

    def _setup_left_panel_content(self):
        self.left_panel.grid_columnconfigure(0, weight=1)
        current_row = 0
        
        pif = ctk.CTkFrame(self.left_panel)
        pif.grid(row=current_row, column=0, sticky="new", padx=10, pady=10)
        pif.grid_columnconfigure(1, weight=1)
        current_row += 1
        
        ctk.CTkLabel(pif, text="Desc:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_profile_desc = ctk.CTkEntry(pif, placeholder_text="Profile description")
        self.entry_profile_desc.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.entry_profile_desc.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        
        ctk.CTkLabel(pif, text="Interval(s):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_monitor_interval = ctk.CTkEntry(pif, placeholder_text="1.0")
        self.entry_monitor_interval.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.entry_monitor_interval.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        
        ctk.CTkLabel(pif, text="Dominant K:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.entry_dominant_k = ctk.CTkEntry(pif, placeholder_text="3")
        self.entry_dominant_k.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.entry_dominant_k.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        
        self.label_current_profile_path = ctk.CTkLabel(pif, text="Path: None", anchor="w", wraplength=280)
        self.label_current_profile_path.grid(row=3, column=0, columnspan=2, padx=5, pady=(5,0), sticky="ew")
        
        rsf = ctk.CTkFrame(self.left_panel)
        rsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5,5))
        rsf.grid_columnconfigure(0, weight=1); rsf.grid_rowconfigure(1, weight=1)
        current_row += 1
        ctk.CTkLabel(rsf, text="Regions", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0,5), sticky="w")
        self.regions_list_scroll_frame = ctk.CTkScrollableFrame(rsf, label_text="")
        self.regions_list_scroll_frame.grid(row=1, column=0, sticky="nsew")
        rbf = ctk.CTkFrame(rsf, fg_color="transparent")
        rbf.grid(row=2, column=0, pady=(5,0), sticky="ew")
        ctk.CTkButton(rbf, text="Add", width=60, command=self._add_region).pack(side="left", padx=2)
        self.btn_remove_region = ctk.CTkButton(rbf, text="Remove", width=70, command=self._remove_selected_region, state="disabled")
        self.btn_remove_region.pack(side="left", padx=2)
        
        tsf = ctk.CTkFrame(self.left_panel)
        tsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5,10))
        tsf.grid_columnconfigure(0, weight=1); tsf.grid_rowconfigure(1, weight=1)
        current_row += 1
        ctk.CTkLabel(tsf, text="Templates", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0,5), sticky="w")
        self.templates_list_scroll_frame = ctk.CTkScrollableFrame(tsf, label_text="")
        self.templates_list_scroll_frame.grid(row=1, column=0, sticky="nsew")
        tbf = ctk.CTkFrame(tsf, fg_color="transparent")
        tbf.grid(row=2, column=0, pady=(5,0), sticky="ew")
        ctk.CTkButton(tbf, text="Add", width=60, command=self._add_template).pack(side="left", padx=2)
        self.btn_remove_template = ctk.CTkButton(tbf, text="Remove", width=70, command=self._remove_selected_template, state="disabled")
        self.btn_remove_template.pack(side="left", padx=2)
        
        self.left_panel.grid_rowconfigure(1, weight=1)
        self.left_panel.grid_rowconfigure(2, weight=1)

    def _setup_center_panel_content(self):
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.center_panel, text="Rules", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.rules_list_scroll_frame = ctk.CTkScrollableFrame(self.center_panel, label_text="")
        self.rules_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        rbf2 = ctk.CTkFrame(self.center_panel, fg_color="transparent")
        rbf2.grid(row=2, column=0, pady=10, sticky="ew")
        ctk.CTkButton(rbf2, text="Add New Rule", command=self._add_new_rule).pack(side="left", padx=5)
        self.btn_remove_rule = ctk.CTkButton(rbf2, text="Remove Selected Rule", command=self._remove_selected_rule, state="disabled")
        self.btn_remove_rule.pack(side="left", padx=5)

    def _new_profile(self, event=None, prompt_save=True):
        if prompt_save and not self._prompt_save_if_dirty(): return
        self.current_profile_path = None
        self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self._populate_ui_from_profile_data()
        self._set_dirty_status(False)
        if hasattr(self, 'label_current_profile_path'): self.label_current_profile_path.configure(text="Path: New Profile (unsaved)")

    def _open_profile(self, event=None):
        if not self._prompt_save_if_dirty(): return
        fp = filedialog.askopenfilename(title="Open Profile", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if fp: self._load_profile_from_path(fp)

    def _load_profile_from_path(self, fp: str):
        try:
            cm = ConfigManager(fp)
            self.profile_data = cm.get_profile_data()
            if not self.profile_data: raise ValueError("Loaded profile data is empty.")
            self.current_profile_path = cm.get_profile_path()
            self._populate_ui_from_profile_data()
            self._set_dirty_status(False)
            self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
        except Exception as e:
            logger.error(f"Failed to load profile '{fp}': {e}", exc_info=True)
            messagebox.showerror("Load Error", f"Could not load profile: {fp}\nError: {e}")

    def _save_profile(self, event=None) -> bool:
        if not self.current_profile_path: return self._save_profile_as()
        if not self._update_profile_data_from_ui(): return False
        try:
            ConfigManager.save_profile_data_to_path(self.current_profile_path, self.profile_data)
            self._set_dirty_status(False)
            return True
        except Exception as e:
            logger.error(f"Failed to save to '{self.current_profile_path}': {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Could not save profile.\nError: {e}")
            return False

    def _save_profile_as(self, event=None) -> bool:
        if not self._update_profile_data_from_ui(): return False
        initial_fn = os.path.basename(self.current_profile_path) if self.current_profile_path else "new_profile.json"
        fp = filedialog.asksaveasfilename(title="Save Profile As", defaultextension=".json", filetypes=[("JSON files", "*.json")], initialfile=initial_fn)
        if fp:
            self.current_profile_path = fp
            self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
            return self._save_profile()
        return False

    def _populate_ui_from_profile_data(self):
        self.entry_profile_desc.delete(0, tk.END); self.entry_profile_desc.insert(0, self.profile_data.get("profile_description", ""))
        settings = self.profile_data.get("settings", {})
        self.entry_monitor_interval.delete(0, tk.END); self.entry_monitor_interval.insert(0, str(settings.get("monitoring_interval_seconds", 1.0)))
        self.entry_dominant_k.delete(0, tk.END); self.entry_dominant_k.insert(0, str(settings.get("analysis_dominant_colors_k", 3)))

        self._populate_specific_list_frame("region", self.regions_list_scroll_frame, self.profile_data.get("regions", []), lambda i,idx: i.get("name",f"R{idx+1}"), self.btn_remove_region, "region")
        self._populate_specific_list_frame("template", self.templates_list_scroll_frame, self.profile_data.get("templates", []), lambda i,idx: f"{i.get('name',f'T{idx+1}')} ({i.get('filename','N/A')})", self.btn_remove_template, "template")
        self._populate_specific_list_frame("rule", self.rules_list_scroll_frame, self.profile_data.get("rules", []), lambda i,idx: i.get("name",f"Rule{idx+1}"), self.btn_remove_rule, "rule")
        
        self.details_panel_instance.update_display(None, "none")

    def _populate_specific_list_frame(self, list_key_prefix: str, frame_widget: ctk.CTkScrollableFrame,
                                      items_data: List[Dict], display_text_cb: Callable,
                                      remove_button: ctk.CTkButton, item_type_str: str):
        for widget in frame_widget.winfo_children(): widget.destroy()
        setattr(self, f"selected_{list_key_prefix}_item_widget", None)
        setattr(self, f"selected_{list_key_prefix}_index", None)
        if remove_button: remove_button.configure(state="disabled")

        for i, item_d in enumerate(items_data):
            text = display_text_cb(item_d, i)
            item_frame_container = {}
            item_f = create_clickable_list_item(frame_widget, text, lambda e=None, n=item_type_str, d=item_d, x=i, fc=item_frame_container: self._on_item_selected(n, d, x, fc.get("frame")))
            item_frame_container["frame"] = item_f

    def _update_profile_data_from_ui(self) -> bool:
        # Basic settings validation
        desc_val, desc_valid = validate_and_get_widget_value(self.entry_profile_desc, None, "Profile Description", str, self.profile_data.get("profile_description",""), allow_empty_string=True, required=False)
        if desc_valid: self.profile_data["profile_description"] = desc_val

        settings = self.profile_data.get("settings", {})
        all_settings_valid = True
        interval_val, interval_valid = validate_and_get_widget_value(self.entry_monitor_interval, None, "Monitoring Interval", float, settings.get("monitoring_interval_seconds",1.0), min_val=0.01, required=True)
        if interval_valid: settings["monitoring_interval_seconds"] = interval_val
        else: all_settings_valid = False
        k_val, k_valid = validate_and_get_widget_value(self.entry_dominant_k, None, "Dominant K", int, settings.get("analysis_dominant_colors_k",3), min_val=1, max_val=20, required=True)
        if k_valid: settings["analysis_dominant_colors_k"] = k_val
        else: all_settings_valid = False
        self.profile_data["settings"] = settings
        return all_settings_valid

    def _set_dirty_status(self, is_d: bool):
        if self._is_dirty == is_d: return
        self._is_dirty = is_d
        title = "PyPixelBot Profile Editor"
        if self.current_profile_path: title += f" - {os.path.basename(self.current_profile_path)}"
        if self._is_dirty: title += "*"
        self.title(title)

    def _prompt_save_if_dirty(self) -> bool:
        if not self._is_dirty: return True
        resp = messagebox.askyesnocancel("Unsaved Changes", "Save changes before proceeding?")
        if resp is True: return self._save_profile()
        return resp is False # True if "No", False if "Cancel"

    def _on_close_window(self, event=None):
        if self._prompt_save_if_dirty(): self.destroy()

    def _on_item_selected(self, list_name: str, item_data: Dict, item_index: int, item_widget_frame: ctk.CTkFrame):
        logger.info(f"Item selected: {list_name}, index {item_index}, name '{item_data.get('name')}'")
        
        # Deselect from other lists
        lists_to_clear = {"region": self.btn_remove_region, "template": self.btn_remove_template, "rule": self.btn_remove_rule}
        for ln, btn in lists_to_clear.items():
            if ln != list_name:
                self._highlight_selected_list_item(ln, None)
                setattr(self, f"selected_{ln}_index", None)
                if btn: btn.configure(state="disabled")
        
        if list_name == "rule": # If a rule is selected, deselect any sub-condition
            self.selected_sub_condition_index = None
            if self.details_panel_instance: # Check if details panel is fully initialized
                 self.details_panel_instance._highlight_selected_list_item("condition", None, is_sub_list=True)
                 if self.details_panel_instance.btn_remove_sub_condition: self.details_panel_instance.btn_remove_sub_condition.configure(state="disabled")


        setattr(self, f"selected_{list_name}_index", item_index)
        self._highlight_selected_list_item(list_name, item_widget_frame)
        
        btn_to_enable = lists_to_clear.get(list_name)
        if btn_to_enable: btn_to_enable.configure(state="normal")
            
        self.details_panel_instance.update_display(item_data, list_name)

    def _highlight_selected_list_item(self, list_name_for_attr: str, new_selected_widget: Optional[ctk.CTkFrame], is_sub_list: bool = False):
        # This method is now also used by DetailsPanel for its sub-condition list
        attr_name_prefix = "selected_sub_" if is_sub_list else "selected_"
        attr_name_widget = f"{attr_name_prefix}{list_name_for_attr}_item_widget"
        
        old_widget_attr_target = self.details_panel_instance if is_sub_list else self
        
        old_selected_widget = getattr(old_widget_attr_target, attr_name_widget, None)
        if old_selected_widget and old_selected_widget.winfo_exists():
            old_selected_widget.configure(fg_color="transparent")
        
        if new_selected_widget and new_selected_widget.winfo_exists():
            new_selected_widget.configure(fg_color=ctk.ThemeManager.theme["CTkSegmentedButton"]["selected_color"]) # More theme-aware
            setattr(old_widget_attr_target, attr_name_widget, new_selected_widget)
        else:
            setattr(old_widget_attr_target, attr_name_widget, None)


    def _apply_region_changes(self):
        if self.selected_region_index is None: return
        current_region_data = self.profile_data["regions"][self.selected_region_index]
        original_name = current_region_data.get("name")
        
        all_valid = True; new_values = {}
        name_val, valid = validate_and_get_widget_value(self.details_panel_instance.detail_widgets["name"], None, "Region Name", str, original_name, req=True)
        if not valid: all_valid=False; else: new_values["name"]=name_val
        
        for p in ["x","y","width","height"]:
            min_v = 1 if p in ["width","height"] else None
            val,valid = validate_and_get_widget_value(self.details_panel_instance.detail_widgets[p], None, p.capitalize(), int, current_region_data.get(p,0), req=True, min_val=min_v)
            if not valid: all_valid=False; else: new_values[p]=val
        if not all_valid: return

        if new_values["name"] != original_name and any(r.get("name")==new_values["name"] for i,r in enumerate(self.profile_data["regions"]) if i!=self.selected_region_index):
            messagebox.showerror("Name Error", f"Region name '{new_values['name']}' already exists."); return
        
        current_region_data.update(new_values)
        self._set_dirty_status(True)
        self._populate_specific_list_frame("region", self.regions_list_scroll_frame, self.profile_data["regions"], lambda i,idx:i.get("name",f"R{idx+1}"), self.btn_remove_region, "region")
        self.details_panel_instance.update_display(current_region_data, "region") # Refresh
        messagebox.showinfo("Region Updated", f"Region '{new_values['name']}' updated.")


    def _apply_template_changes(self):
        if self.selected_template_index is None: return
        current_template_data = self.profile_data["templates"][self.selected_template_index]
        original_name = current_template_data.get("name")
        
        name_val, name_valid = validate_and_get_widget_value(self.details_panel_instance.detail_widgets["template_name"],None,"Template Name",str,original_name,req=True)
        if not name_valid: return
        if name_val != original_name and any(t.get("name")==name_val for i,t in enumerate(self.profile_data["templates"]) if i!=self.selected_template_index):
            messagebox.showerror("Name Error", f"Template name '{name_val}' already exists."); return
            
        current_template_data["name"] = name_val
        self._set_dirty_status(True)
        self._populate_specific_list_frame("template",self.templates_list_scroll_frame,self.profile_data["templates"],lambda i,idx:f"{i.get('name')} ({i.get('filename')})",self.btn_remove_template,"template")
        self.details_panel_instance.update_display(current_template_data, "template")
        messagebox.showinfo("Template Updated", f"Template '{name_val}' updated.")

    def _apply_rule_changes(self):
        if self.selected_rule_index is None: return
        current_rule_data = self.profile_data["rules"][self.selected_rule_index]
        old_name = current_rule_data.get("name")
        temp_rule_data = copy.deepcopy(current_rule_data) # Work on a copy

        new_name, name_valid = validate_and_get_widget_value(self.details_panel_instance.detail_widgets["rule_name"], None, "Rule Name", str, old_name, req=True)
        if not name_valid: return
        if new_name != old_name and any(r.get("name")==new_name for i,r in enumerate(self.profile_data["rules"]) if i!=self.selected_rule_index):
            messagebox.showerror("Name Error", f"Rule name '{new_name}' already exists."); return
        temp_rule_data["name"] = new_name
        
        temp_rule_data["region"] = self.details_panel_instance.detail_optionmenu_vars["rule_region_var"].get()

        # Condition logic
        is_compound = "logical_operator_var" in self.details_panel_instance.detail_optionmenu_vars
        new_cond_data = {}
        if is_compound:
            new_cond_data["logical_operator"] = self.details_panel_instance.detail_optionmenu_vars["logical_operator_var"].get()
            new_sub_conds = []
            profile_sub_conds = temp_rule_data.get("condition",{}).get("sub_conditions",[]) # From temp_rule_data copy
            all_subs_valid = True
            for idx, sub_c_profile_data in enumerate(profile_sub_conds):
                if self.selected_sub_condition_index == idx: # This one was being edited in UI
                    sub_c_type = self.details_panel_instance.detail_optionmenu_vars["subcond_condition_type_var"].get()
                    sub_params = self.details_panel_instance._get_parameters_from_ui("conditions", sub_c_type, "subcond_")
                    if sub_params is None: all_subs_valid=False; break
                    new_sub_conds.append(sub_params)
                else: # Not edited, keep profile version
                    new_sub_conds.append(copy.deepcopy(sub_c_profile_data))
            if not all_subs_valid: logger.error("Sub-condition validation failed. Rule not saved."); return
            new_cond_data["sub_conditions"] = new_sub_conds
        else: # Single condition
            single_cond_type = self.details_panel_instance.detail_optionmenu_vars["condition_type_var"].get()
            single_cond_params = self.details_panel_instance._get_parameters_from_ui("conditions", single_cond_type, "cond_")
            if single_cond_params is None: logger.error("Single condition validation failed. Rule not saved."); return
            new_cond_data = single_cond_params
        temp_rule_data["condition"] = new_cond_data

        # Action logic
        action_type = self.details_panel_instance.detail_optionmenu_vars["action_type_var"].get()
        action_params = self.details_panel_instance._get_parameters_from_ui("actions", action_type, "act_")
        if action_params is None: logger.error("Action validation failed. Rule not saved."); return
        temp_rule_data["action"] = action_params

        self.profile_data["rules"][self.selected_rule_index] = temp_rule_data
        self._set_dirty_status(True)
        self._populate_specific_list_frame("rule",self.rules_list_scroll_frame,self.profile_data["rules"],lambda i,idx:i.get("name",f"Rule{idx+1}"),self.btn_remove_rule,"rule")
        self.details_panel_instance.update_display(temp_rule_data, "rule")
        messagebox.showinfo("Rule Updated", f"Rule '{new_name}' updated.")


    def _edit_region_coordinates_with_selector(self):
        # (Logic remains largely the same, ensure it calls parent_app's _save_profile if needed)
        if self.selected_region_index is None: return
        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Save current profile changes before launching Region Selector?"): return
            if not self._save_profile(): return 
        if not self.current_profile_path:
            messagebox.showerror("Error", "Profile must be saved before editing region coordinates.")
            return
        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data: return

            # Pass a copy of the specific region data to edit
            region_to_edit_data = copy.deepcopy(self.profile_data["regions"][self.selected_region_index])

            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector, 
                                                 existing_region_data=region_to_edit_data) # Pass existing data
            self.wait_window(selector_dialog)
            if selector_dialog.changes_made: # RegionSelector sets this flag
                self._load_profile_from_path(self.current_profile_path) # Reload all data
                self._set_dirty_status(True) 
        except Exception as e:
            logger.error(f"Error during Edit Region Coordinates: {e}", exc_info=True)
            messagebox.showerror("Region Selector Error", f"Error with Region Selector:\n{e}")

    def _add_region(self):
        # (Logic remains largely the same)
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "Profile must be saved. Save now?"): return
            if not self._save_profile_as(): return
        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Save current changes before Region Selector?"): return
            if not self._save_profile(): return
        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data: return
            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector)
            self.wait_window(selector_dialog)
            if selector_dialog.changes_made:
                self._load_profile_from_path(self.current_profile_path); self._set_dirty_status(True)
        except Exception as e: messagebox.showerror("Add Region Error", f"Error with Region Selector:\n{e}")

    def _remove_selected_item(self, list_name_key: str, profile_data_key: str, selected_index_attr: str, remove_button_widget: Optional[ctk.CTkButton]):
        # (Logic remains largely the same, ensure remove_button_widget can be None if passed so)
        selected_index = getattr(self, selected_index_attr, None)
        if selected_index is None or not self.profile_data or profile_data_key not in self.profile_data: return

        item_list: List[Dict] = self.profile_data[profile_data_key]
        if 0 <= selected_index < len(item_list):
            removed_item_data = item_list.pop(selected_index)
            logger.info(f"Removed {list_name_key} '{removed_item_data.get('name', 'N/A')}' at index {selected_index}.")

            list_scroll_frame = getattr(self, f"{list_name_key}s_list_scroll_frame", None)
            display_cb_map = {
                "region": lambda i,idx:i.get("name",f"R{idx+1}"),
                "template": lambda i,idx: f"{i.get('name')} ({i.get('filename')})",
                "rule": lambda i,idx:i.get("name",f"Rule{idx+1}")
            }
            display_cb = display_cb_map.get(list_name_key)
            
            if list_scroll_frame and display_cb and remove_button_widget: # Check remove_button_widget
                self._populate_specific_list_frame(list_name_key, list_scroll_frame, item_list, display_cb, remove_button_widget, list_name_key)
            
            self._set_dirty_status(True); setattr(self, selected_index_attr, None)
            if remove_button_widget: remove_button_widget.configure(state="disabled")
            self.details_panel_instance.update_display(None, "none")

            if list_name_key == "template" and self.current_profile_path:
                fn_del = removed_item_data.get("filename")
                if fn_del:
                    tpl_path = os.path.join(os.path.dirname(self.current_profile_path), "templates", fn_del)
                    try:
                        if os.path.exists(tpl_path): os.remove(tpl_path)
                    except OSError as e_os: messagebox.showwarning("File Deletion Error", f"Could not delete '{fn_del}':\n{e_os.strerror}")
        else: logger.warning(f"Cannot remove {list_name_key}: Invalid index {selected_index}.")

    def _remove_selected_region(self): self._remove_selected_item("region", "regions", "selected_region_index", self.btn_remove_region)
    def _remove_selected_template(self): self._remove_selected_item("template", "templates", "selected_template_index", self.btn_remove_template)
    def _remove_selected_rule(self): self._remove_selected_item("rule", "rules", "selected_rule_index", self.btn_remove_rule)

    def _add_template(self):
        # (Logic remains largely the same)
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "Profile must be saved. Save now?"): return
            if not self._save_profile_as(): return
        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Save current changes before adding template?"): return
            if not self._save_profile(): return
        img_path = filedialog.askopenfilename(title="Select Template Image", filetypes=[("PNG", "*.png"),("JPEG","*.jpg;*.jpeg")])
        if not img_path: return
        name_dialog = ctk.CTkInputDialog(text="Unique name for template:", title="Template Name")
        tpl_name = name_dialog.get_input()
        if not tpl_name or not tpl_name.strip(): return; tpl_name=tpl_name.strip()
        if any(t.get("name") == tpl_name for t in self.profile_data.get("templates",[])):
            messagebox.showerror("Name Error", f"Template name '{tpl_name}' already exists."); return
        profile_dir = os.path.dirname(self.current_profile_path); templates_dir = os.path.join(profile_dir,"templates")
        try:
            os.makedirs(templates_dir,exist_ok=True)
            base,ext=os.path.splitext(os.path.basename(img_path)); sane_base="".join(c if c.isalnum() or c in (' ','_','-') else '_' for c in tpl_name).rstrip().replace(' ','_')
            tf=f"{sane_base}{ext}"; tp=os.path.join(templates_dir,tf); c=1
            while os.path.exists(tp): tf=f"{sane_base}_{c}{ext}";tp=os.path.join(templates_dir,tf);c+=1
            shutil.copy2(img_path,tp); new_tpl={"name":tpl_name,"filename":tf}
            self.profile_data.setdefault("templates",[]).append(new_tpl)
            self._populate_specific_list_frame("template",self.templates_list_scroll_frame,self.profile_data["templates"],lambda i,idx:f"{i.get('name')} ({i.get('filename')})",self.btn_remove_template,"template")
            self._set_dirty_status(True); messagebox.showinfo("Template Added", f"Template '{tpl_name}' added.")
        except Exception as e: messagebox.showerror("Add Template Error",f"Could not add template:\n{e}")

    def _add_new_rule(self):
        # (Logic remains largely the same)
        if not self.profile_data: self._new_profile(prompt_save=False)
        name_dialog=ctk.CTkInputDialog(text="Unique name for new rule:",title="New Rule Name"); rule_name=name_dialog.get_input()
        if not rule_name or not rule_name.strip(): return; rule_name=rule_name.strip()
        if any(r.get("name")==rule_name for r in self.profile_data.get("rules",[])):
            messagebox.showerror("Name Error",f"Rule name '{rule_name}' already exists."); return
        new_rule={"name":rule_name,"region":"","condition":{"type":"always_true"},"action":{"type":"log_message","message":f"Rule '{rule_name}' triggered.","level":"INFO"}}
        self.profile_data.setdefault("rules",[]).append(new_rule)
        self._populate_specific_list_frame("rule",self.rules_list_scroll_frame,self.profile_data["rules"],lambda i,idx:i.get("name",f"Rule{idx+1}"),self.btn_remove_rule,"rule")
        self._set_dirty_status(True); messagebox.showinfo("Rule Added",f"Rule '{rule_name}' added.")
    
    def _on_rule_part_type_change(self, part_changed: str, new_type_selected: str):
        # This will now largely delegate to DetailsPanel to re-render its specific section
        self._set_dirty_status(True)
        if self.selected_rule_index is None: return
        
        current_rule_data = self.profile_data["rules"][self.selected_rule_index]
        # The DetailsPanel itself will handle redrawing based on its own stored vars for type
        # This method in MainApp might just ensure the DetailsPanel is told to refresh its view
        # for that specific part, or the DetailsPanel's own command for the OptionMenu handles it.
        
        # For now, assume DetailsPanel methods manage the sub-rendering
        # This method ensures the data model is updated, which DetailsPanel might read
        if part_changed == "condition":
            if self.selected_sub_condition_index is not None:
                sub_cond_list = current_rule_data.get("condition", {}).get("sub_conditions", [])
                if 0 <= self.selected_sub_condition_index < len(sub_cond_list):
                    sub_cond_to_update = sub_cond_list[self.selected_sub_condition_index]
                    if sub_cond_to_update.get("type") != new_type_selected:
                         # Minimal reset, UI_PARAM_CONFIG will guide actual params
                        sub_cond_to_update.clear() 
                    sub_cond_to_update["type"] = new_type_selected
                    # DetailsPanel will re-render its sub_condition_params_frame
                    self.details_panel_instance._on_sub_condition_selected_internal(sub_cond_to_update, self.selected_sub_condition_index, None) # Pass None for widget frame, highlight logic is separate
            elif "logical_operator" not in current_rule_data.get("condition", {}): # Main single condition
                cond_to_update = current_rule_data.get("condition", {})
                if cond_to_update.get("type") != new_type_selected:
                    cond_to_update.clear()
                cond_to_update["type"] = new_type_selected
                # DetailsPanel will re-render its condition_params_frame
                self.details_panel_instance._render_dynamic_parameters("conditions", new_type_selected, cond_to_update, self.details_panel_instance.condition_params_frame, start_row=1, widget_prefix="cond_")

        elif part_changed == "action":
            action_to_update = current_rule_data.get("action",{})
            if action_to_update.get("type") != new_type_selected:
                action_to_update.clear()
            action_to_update["type"] = new_type_selected
            # DetailsPanel will re-render its action_params_frame
            self.details_panel_instance._render_dynamic_parameters("actions", new_type_selected, action_to_update, self.details_panel_instance.action_params_frame, start_row=1, widget_prefix="act_")
        
        logger.info(f"Rule part '{part_changed}' type model updated to '{new_type_selected}'. DetailsPanel should refresh.")


    def _add_sub_condition_to_rule(self):
        # Delegates to DetailsPanel or manipulates profile_data then tells DetailsPanel to refresh
        if self.selected_rule_index is None: return
        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})
        if "logical_operator" not in cond_block:
            current_single = copy.deepcopy(cond_block); cond_block.clear()
            cond_block["logical_operator"] = "AND"; cond_block["sub_conditions"] = [current_single if current_single.get("type") else {"type": "always_true"}]
        cond_block.setdefault("sub_conditions", []).append({"type": "always_true"})
        rule["condition"] = cond_block
        self._set_dirty_status(True)
        self.details_panel_instance.update_display(rule, "rule") # Full refresh of rule details

    def _remove_selected_sub_condition(self):
        # Delegates to DetailsPanel or manipulates profile_data then tells DetailsPanel to refresh
        if self.selected_rule_index is None or self.selected_sub_condition_index is None: return
        rule = self.profile_data["rules"][self.selected_rule_index]
        sub_list = rule.get("condition", {}).get("sub_conditions")
        if sub_list and 0 <= self.selected_sub_condition_index < len(sub_list):
            sub_list.pop(self.selected_sub_condition_index)
            self.selected_sub_condition_index = None # Deselect
            self._set_dirty_status(True)
            self.details_panel_instance.update_display(rule, "rule") # Full refresh

    def _convert_condition_structure(self):
        # (Logic remains largely the same, tells DetailsPanel to refresh at the end)
        if self.selected_rule_index is None: return
        rule = self.profile_data["rules"][self.selected_rule_index]
        cond = rule.get("condition", {}); is_compound = "logical_operator" in cond
        if is_compound:
            subs=cond.get("sub_conditions",[])
            if len(subs)>1 and not messagebox.askyesno("Confirm","Convert to single? First sub-cond kept. Others lost. Continue?"): return
            rule["condition"] = copy.deepcopy(subs[0]) if subs else {"type":"always_true"}
        else:
            single=copy.deepcopy(cond)
            if not single.get("type"): single={"type":"always_true"}
            rule["condition"] = {"logical_operator":"AND", "sub_conditions":[single]}
        self._set_dirty_status(True); self.details_panel_instance.update_display(rule,"rule")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ctk.set_appearance_mode("System"); ctk.set_default_color_theme("blue")
    app = MainAppWindow()
    app.mainloop()