import logging
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
import copy
import shutil
from typing import Optional, Dict, Any, List, Callable, Union, Tuple

import customtkinter as ctk
from PIL import Image # For CTkImage and template previews

# Assuming ConfigManager and RegionSelectorWindow are correctly importable
try:
    from ...core.config_manager import ConfigManager
    from .region_selector import RegionSelectorWindow
except ImportError: # Fallback for potential execution context issues
    from py_pixel_bot.core.config_manager import ConfigManager
    from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow


logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_PROFILE_STRUCTURE = {
    "profile_description": "New Profile",
    "settings": {
        "monitoring_interval_seconds": 1.0,
        "analysis_dominant_colors_k": 3,
        "tesseract_cmd_path": None,
        "tesseract_config_custom": ""
    },
    "regions": [],
    "templates": [],
    "rules": []
}
MAX_PREVIEW_WIDTH = 200
MAX_PREVIEW_HEIGHT = 150

CONDITION_TYPES = ["pixel_color", "average_color_is", "template_match_found",
                   "ocr_contains_text", "dominant_color_matches", "always_true"]
ACTION_TYPES = ["click", "type_text", "press_key", "log_message"]
LOGICAL_OPERATORS = ["AND", "OR"]
CLICK_TARGET_RELATIONS = ["center_of_region", "center_of_last_match", "absolute", "relative_to_region"]
CLICK_BUTTONS = ["left", "middle", "right"]
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class MainAppWindow(ctk.CTk):
    def __init__(self, initial_profile_path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing MainAppWindow...")
        self.title("PyPixelBot Profile Editor")
        self.geometry("1350x800")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.current_profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = self._get_default_profile_structure()
        self._is_dirty: bool = False

        self.selected_region_index: Optional[int] = None
        self.selected_template_index: Optional[int] = None
        self.selected_rule_index: Optional[int] = None
        self.selected_sub_condition_index: Optional[int] = None
        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_region_item_widget: Optional[ctk.CTkFrame] = None # Added for consistency
        self.selected_template_item_widget: Optional[ctk.CTkFrame] = None # Added
        self.selected_rule_item_widget: Optional[ctk.CTkFrame] = None # Added


        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        self.detail_optionmenu_vars: Dict[str, tk.StringVar] = {}

        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None
        self.condition_params_frame: Optional[ctk.CTkFrame] = None
        self.action_params_frame: Optional[ctk.CTkFrame] = None
        self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None
        self.btn_convert_condition: Optional[ctk.CTkButton] = None
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None

        self._setup_ui()

        if initial_profile_path:
            logger.info(f"Attempting to load initial profile: {initial_profile_path}")
            self._load_profile_from_path(initial_profile_path)
        else:
            self._new_profile(prompt_save=False) # Start with a clean new profile

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        logger.info("MainAppWindow initialization complete.")

    def _get_default_profile_structure(self) -> Dict[str, Any]:
        return copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)

    def _create_clickable_list_item(self, parent_frame: ctk.CTkScrollableFrame, text: str, on_click_callback: Callable) -> ctk.CTkFrame:
        item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent", corner_radius=0)
        item_frame.pack(fill="x", pady=1, padx=1)
        label = ctk.CTkLabel(item_frame, text=text, anchor="w", cursor="hand2")
        label.pack(side="left", fill="x", expand=True, padx=5, pady=2)
        label.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
        item_frame.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
        return item_frame

    def _highlight_selected_list_item(self, list_name_for_attr: str, new_selected_widget: Optional[ctk.CTkFrame], is_sub_list: bool = False):
        attr_name_prefix = "selected_sub_" if is_sub_list else "selected_"
        attr_name = f"{attr_name_prefix}{list_name_for_attr}_item_widget"
        
        old_selected_widget = getattr(self, attr_name, None)
        if old_selected_widget and old_selected_widget.winfo_exists():
            old_selected_widget.configure(fg_color="transparent")
        
        if new_selected_widget and new_selected_widget.winfo_exists():
            new_selected_widget.configure(fg_color=("#DBDBDB", "#2B2B2B"))
            setattr(self, attr_name, new_selected_widget)
        else:
            setattr(self, attr_name, None)

    def _clear_details_panel_content(self):
        if hasattr(self, 'details_panel_content_frame') and self.details_panel_content_frame:
            for widget in self.details_panel_content_frame.winfo_children():
                widget.destroy()
        self.detail_widgets.clear()
        self.detail_optionmenu_vars.clear()
        
        if self.template_preview_image_label: self.template_preview_image_label.destroy(); self.template_preview_image_label = None
        if self.sub_conditions_list_frame: self.sub_conditions_list_frame.destroy(); self.sub_conditions_list_frame = None
        if self.condition_params_frame: self.condition_params_frame.destroy(); self.condition_params_frame = None
        if self.action_params_frame: self.action_params_frame.destroy(); self.action_params_frame = None
        if self.sub_condition_params_frame: self.sub_condition_params_frame.destroy(); self.sub_condition_params_frame = None
        logger.debug("Cleared details panel content and dynamic widget references.")

    def _setup_ui(self):
        logger.debug("Setting up static UI components (Menu, Panels)...")
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
        self.bind_all("<Control-Shift-S>", lambda e: self._save_profile_as()) # Note: Tkinter uses <Control-S> for Shift+S
                
        self.grid_columnconfigure(0, weight=1, minsize=300)
        self.grid_columnconfigure(1, weight=2, minsize=350)
        self.grid_columnconfigure(2, weight=2, minsize=400)
        self.grid_rowconfigure(0, weight=1)
        
        self.left_panel = ctk.CTkFrame(self, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0,2), pady=0)
        self._setup_left_panel()
        
        self.center_panel = ctk.CTkFrame(self, corner_radius=0)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=(0,2), pady=0)
        self._setup_center_panel()
        
        self.right_panel = ctk.CTkFrame(self, corner_radius=0)
        self.right_panel.grid(row=0, column=2, sticky="nsew", pady=0)
        self._setup_right_panel()
        logger.debug("Static UI components (Menu, Panels) setup complete.")

    def _setup_left_panel(self):
        self.left_panel.grid_columnconfigure(0, weight=1)
        current_row = 0
        
        # Profile Info Frame (pif)
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
        
        # Regions Section Frame (rsf)
        rsf = ctk.CTkFrame(self.left_panel)
        rsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5,5))
        rsf.grid_columnconfigure(0, weight=1)
        rsf.grid_rowconfigure(1, weight=1)
        current_row += 1
        
        ctk.CTkLabel(rsf, text="Regions", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0,5), sticky="w")
        self.regions_list_scroll_frame = ctk.CTkScrollableFrame(rsf, label_text="")
        self.regions_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        
        rbf = ctk.CTkFrame(rsf, fg_color="transparent") # Regions Buttons Frame
        rbf.grid(row=2, column=0, pady=(5,0), sticky="ew")
        ctk.CTkButton(rbf, text="Add", width=60, command=self._add_region).pack(side="left", padx=2)
        self.btn_remove_region = ctk.CTkButton(rbf, text="Remove", width=70, command=self._remove_selected_region, state="disabled")
        self.btn_remove_region.pack(side="left", padx=2)
        
        # Templates Section Frame (tsf)
        tsf = ctk.CTkFrame(self.left_panel)
        tsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5,10))
        tsf.grid_columnconfigure(0, weight=1)
        tsf.grid_rowconfigure(1, weight=1)
        current_row += 1
        
        ctk.CTkLabel(tsf, text="Templates", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0,5), sticky="w")
        self.templates_list_scroll_frame = ctk.CTkScrollableFrame(tsf, label_text="")
        self.templates_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        
        tbf = ctk.CTkFrame(tsf, fg_color="transparent") # Templates Buttons Frame
        tbf.grid(row=2, column=0, pady=(5,0), sticky="ew")
        ctk.CTkButton(tbf, text="Add", width=60, command=self._add_template).pack(side="left", padx=2)
        self.btn_remove_template = ctk.CTkButton(tbf, text="Remove", width=70, command=self._remove_selected_template, state="disabled")
        self.btn_remove_template.pack(side="left", padx=2)
        
        self.left_panel.grid_rowconfigure(1, weight=1) # Allow regions list to expand
        self.left_panel.grid_rowconfigure(2, weight=1) # Allow templates list to expand

    def _setup_center_panel(self):
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.center_panel, text="Rules", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.rules_list_scroll_frame = ctk.CTkScrollableFrame(self.center_panel, label_text="")
        self.rules_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        rbf2 = ctk.CTkFrame(self.center_panel, fg_color="transparent") # Rules Buttons Frame 2
        rbf2.grid(row=2, column=0, pady=10, sticky="ew")
        ctk.CTkButton(rbf2, text="Add New Rule", command=self._add_new_rule).pack(side="left", padx=5)
        self.btn_remove_rule = ctk.CTkButton(rbf2, text="Remove Selected Rule", command=self._remove_selected_rule, state="disabled")
        self.btn_remove_rule.pack(side="left", padx=5)

    def _setup_right_panel(self):
        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure(0, weight=1)
        
        self.details_panel_scroll_frame = ctk.CTkScrollableFrame(self.right_panel, label_text="Selected Item Details")
        self.details_panel_scroll_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        self.details_panel_content_frame = ctk.CTkFrame(self.details_panel_scroll_frame, fg_color="transparent")
        self.details_panel_content_frame.pack(fill="both", expand=True)
        
        self.label_details_placeholder = ctk.CTkLabel(self.details_panel_content_frame, text="Select an item from a list to see/edit details.", wraplength=380, justify="center")
        self.label_details_placeholder.pack(padx=10, pady=20, anchor="center", expand=True)

    def _new_profile(self, event=None, prompt_save=True):
        logger.info("New Profile action initiated.")
        if prompt_save:
            if not self._prompt_save_if_dirty():
                logger.info("New profile action cancelled by user.")
                return

        self.current_profile_path = None
        self.profile_data = self._get_default_profile_structure()
        self._populate_ui_from_profile_data()
        self._set_dirty_status(False)
        if hasattr(self, 'label_current_profile_path'):
            self.label_current_profile_path.configure(text="Path: New Profile (unsaved)")
        logger.info("New profile created in memory and UI populated.")

    def _open_profile(self, event=None):
        logger.info("Open Profile action initiated.")
        if not self._prompt_save_if_dirty():
            logger.info("Open profile action cancelled by user.")
            return

        fp = filedialog.askopenfilename(
            title="Open Profile",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        logger.info(f"File dialog returned path: {fp}")
        if fp:
            self._load_profile_from_path(fp)
        else:
            logger.info("Open file dialog was cancelled by user.")

    def _load_profile_from_path(self, fp: str):
        logger.info(f"Loading profile from: {fp}")
        try:
            cm = ConfigManager(fp) # Assumes ConfigManager loads on init or has a load method
            self.profile_data = cm.get_profile_data() # Assumes this method exists
            if not self.profile_data: # If get_profile_data returns None or empty on failure
                raise ValueError("Loaded profile data is empty or invalid.")
            self.current_profile_path = cm.get_profile_path() # Assumes this method exists
            self._populate_ui_from_profile_data()
            self._set_dirty_status(False)
            self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
            logger.info(f"Profile '{self.current_profile_path}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load profile '{fp}': {e}", exc_info=True)
            messagebox.showerror("Load Error", f"Could not load profile: {fp}\n\nError: {e}")

    def _save_profile(self, event=None):
        logger.info("Save Profile action initiated.")
        if not self.current_profile_path:
            logger.debug("No current profile path set, invoking Save Profile As...")
            self._save_profile_as() # This will handle everything if path is not set
            return

        logger.debug(f"Attempting to save to existing path: {self.current_profile_path}")
        is_valid_update = self._update_profile_data_from_ui()
        if not is_valid_update:
            logger.info("Save aborted due to validation errors in general profile settings.")
            # Errors would have been shown by _update_profile_data_from_ui
            return

        try:
            ConfigManager.save_profile_data_to_path(self.current_profile_path, self.profile_data) # Static method
            self._set_dirty_status(False)
            logger.info(f"Profile saved successfully to: {self.current_profile_path}")
        except Exception as e:
            logger.error(f"Failed to save profile to '{self.current_profile_path}': {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Could not save profile to: {self.current_profile_path}\n\nError: {e}")

    def _save_profile_as(self, event=None):
        logger.info("Save Profile As action initiated.")
        is_valid_update = self._update_profile_data_from_ui()
        if not is_valid_update:
            logger.info("Save As aborted due to validation errors in general profile settings.")
            return

        initial_filename = os.path.basename(self.current_profile_path) if self.current_profile_path else "new_profile.json"
        fp = filedialog.asksaveasfilename(
            title="Save Profile As",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=initial_filename
        )

        if fp:
            self.current_profile_path = fp
            self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
            self._save_profile() # Call regular save now that path is set
        else:
            logger.info("Save As dialog cancelled by user.")

    def _populate_ui_from_profile_data(self):
        logger.debug("Populating all UI elements from self.profile_data...")
        
        # Populate general settings
        self.entry_profile_desc.delete(0, tk.END)
        self.entry_profile_desc.insert(0, self.profile_data.get("profile_description", ""))
        
        settings = self.profile_data.get("settings", {})
        self.entry_monitor_interval.delete(0, tk.END)
        self.entry_monitor_interval.insert(0, str(settings.get("monitoring_interval_seconds", 1.0)))
        self.entry_dominant_k.delete(0, tk.END)
        self.entry_dominant_k.insert(0, str(settings.get("analysis_dominant_colors_k", 3)))

        # Populate lists
        self._populate_specific_list_frame(
            "region", self.regions_list_scroll_frame, self.profile_data.get("regions", []),
            lambda item, idx: item.get("name", f"Region {idx + 1}"),
            self.btn_remove_region, "region"
        )
        self._populate_specific_list_frame(
            "template", self.templates_list_scroll_frame, self.profile_data.get("templates", []),
            lambda item, idx: f"{item.get('name', f'Template {idx + 1}')} ({item.get('filename', 'N/A')})",
            self.btn_remove_template, "template"
        )
        self._populate_specific_list_frame(
            "rule", self.rules_list_scroll_frame, self.profile_data.get("rules", []),
            lambda item, idx: item.get("name", f"Rule {idx + 1}"),
            self.btn_remove_rule, "rule"
        )
        
        self._update_details_panel(None, "none") # Clear details panel
        logger.debug("UI population from profile_data complete.")

    def _populate_specific_list_frame(self, lstfn_attr_prefix: str, frame_widget: ctk.CTkScrollableFrame,
                                      items_data: List[Dict], display_text_callback: Callable,
                                      button_to_manage_state: ctk.CTkButton, list_type_for_selection_logic: str):
        for widget in frame_widget.winfo_children():
            widget.destroy()
        
        setattr(self, f"selected_{lstfn_attr_prefix}_item_widget", None)
        setattr(self, f"selected_{lstfn_attr_prefix}_index", None)

        if button_to_manage_state:
            button_to_manage_state.configure(state="disabled")

        for i, item_d in enumerate(items_data):
            display_text = display_text_callback(item_d, i)
            # Using a dict to pass item_frame by reference for binding
            item_frame_container = {}
            item_frame = self._create_clickable_list_item(
                frame_widget, display_text,
                lambda e=None, n=list_type_for_selection_logic, d=item_d, x=i, fc=item_frame_container: self._on_item_selected(n, d, x, fc.get("frame"))
            )
            item_frame_container["frame"] = item_frame


    def _update_profile_data_from_ui(self) -> bool:
        if not self.profile_data:
            self.profile_data = self._get_default_profile_structure()
        logger.debug("Updating profile_data (general settings) from UI input fields...")
        
        desc_val, desc_valid = self._validate_and_get_widget_value(self.entry_profile_desc, "Profile Description", str, default_val=self.profile_data.get("profile_description", ""), allow_empty_string=True, required=False)
        if desc_valid:
            self.profile_data["profile_description"] = desc_val

        settings = self.profile_data.get("settings", {})
        all_settings_valid = True

        interval_val, is_valid_interval = self._validate_and_get_widget_value(self.entry_monitor_interval, "Monitoring Interval", float, default_val=settings.get("monitoring_interval_seconds", 1.0), min_val=0.01, required=True)
        if is_valid_interval:
            settings["monitoring_interval_seconds"] = interval_val
        else:
            all_settings_valid = False

        k_val, is_valid_k = self._validate_and_get_widget_value(self.entry_dominant_k, "Dominant K", int, default_val=settings.get("analysis_dominant_colors_k", 3), min_val=1, max_val=20, required=True)
        if is_valid_k:
            settings["analysis_dominant_colors_k"] = k_val
        else:
            all_settings_valid = False
        
        self.profile_data["settings"] = settings
        if all_settings_valid:
            logger.debug(f"Profile_data (general settings) updated from UI. Current: {settings}")
        else:
            logger.error("One or more general profile settings failed validation. Please check messages.")
        return all_settings_valid

    def _set_dirty_status(self, is_d: bool):
        if self._is_dirty == is_d:
            return
        self._is_dirty = is_d
        title = "PyPixelBot Profile Editor"
        if self.current_profile_path:
            title += f" - {os.path.basename(self.current_profile_path)}"
        if self._is_dirty:
            title += "*"
        self.title(title)
        logger.debug(f"Profile dirty status set to: {self._is_dirty}")

    def _prompt_save_if_dirty(self) -> bool:
        if self._is_dirty:
            response = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes. Do you want to save them before proceeding?")
            if response is True:  # Yes
                logger.debug("User chose YES to save.")
                return self._save_profile() # This will attempt to save
            elif response is False:  # No
                logger.debug("User chose NO to save (discard changes).")
                return True  # Proceed without saving
            else:  # Cancel
                logger.debug("User chose CANCEL operation.")
                return False  # Do not proceed
        return True  # Not dirty, so proceed

    def _on_close_window(self, event=None):
        logger.info("Window close requested.")
        if self._prompt_save_if_dirty():
            logger.info("Exiting GUI application.")
            self.destroy()
        else:
            logger.info("Window close cancelled by user.")

    def _on_item_selected(self, list_name: str, item_data: Dict, item_index: int, item_widget_frame: ctk.CTkFrame):
        logger.info(f"Item selected in '{list_name}' list. Index: {item_index}, Name: '{item_data.get('name', 'N/A')}'")
        
        # Deselect items in other lists
        if list_name != "region":
            self._highlight_selected_list_item("region", None, False)
            self.selected_region_index = None
            if hasattr(self, 'btn_remove_region'): self.btn_remove_region.configure(state="disabled")
        if list_name != "template":
            self._highlight_selected_list_item("template", None, False)
            self.selected_template_index = None
            if hasattr(self, 'btn_remove_template'): self.btn_remove_template.configure(state="disabled")
        if list_name != "rule":
            self._highlight_selected_list_item("rule", None, False)
            self.selected_rule_index = None
            if hasattr(self, 'btn_remove_rule'): self.btn_remove_rule.configure(state="disabled")
            self.selected_sub_condition_index = None # Also deselect sub-condition
            self._highlight_selected_list_item("condition", None, True) # sub-condition highlight
            if self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled")


        # Select current item
        setattr(self, f"selected_{list_name}_index", item_index)
        self._highlight_selected_list_item(list_name, item_widget_frame, False)

        # Enable remove button for the selected list
        if list_name == "region" and hasattr(self, 'btn_remove_region'):
            self.btn_remove_region.configure(state="normal")
        elif list_name == "template" and hasattr(self, 'btn_remove_template'):
            self.btn_remove_template.configure(state="normal")
        elif list_name == "rule" and hasattr(self, 'btn_remove_rule'):
            self.btn_remove_rule.configure(state="normal")
            self.selected_sub_condition_index = None # Clear sub-condition selection when new rule is selected
            if self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled")


        self._update_details_panel(item_data, list_name)

    def _update_details_panel(self, item_data: Optional[Any], item_type: str):
        self._clear_details_panel_content()
        content_frame = self.details_panel_content_frame # Use the dedicated content frame

        if item_data and item_type == "region":
            logger.debug(f"Populating details for region: {item_data.get('name')}")
            content_frame.grid_columnconfigure(1, weight=1) # Allow entry to expand
            
            ctk.CTkLabel(content_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.detail_widgets["name"] = ctk.CTkEntry(content_frame)
            self.detail_widgets["name"].insert(0, str(item_data.get("name", "")))
            self.detail_widgets["name"].grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            self.detail_widgets["name"].bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
            
            coords = {"x": item_data.get("x", 0), "y": item_data.get("y", 0),
                      "width": item_data.get("width", 100), "height": item_data.get("height", 100)}
            for i, (k, v) in enumerate(coords.items()):
                ctk.CTkLabel(content_frame, text=f"{k.capitalize()}:").grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")
                self.detail_widgets[k] = ctk.CTkEntry(content_frame)
                self.detail_widgets[k].insert(0, str(v))
                self.detail_widgets[k].grid(row=i + 1, column=1, padx=5, pady=5, sticky="ew")
                self.detail_widgets[k].bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
            
            button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
            button_frame.grid(row=len(coords) + 1, column=0, columnspan=2, pady=10)
            ctk.CTkButton(button_frame, text="Apply Changes", command=self._apply_region_changes).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Edit Coords (Selector)", command=self._edit_region_coordinates_with_selector).pack(side="left", padx=5)

        elif item_data and item_type == "template":
            logger.debug(f"Populating details for template: {item_data.get('name')}")
            content_frame.grid_columnconfigure(1, weight=1)
            
            ctk.CTkLabel(content_frame, text="Name:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.detail_widgets["template_name"] = ctk.CTkEntry(content_frame)
            self.detail_widgets["template_name"].insert(0, str(item_data.get("name", "")))
            self.detail_widgets["template_name"].grid(row=0, column=1, padx=5, pady=5, sticky="ew")
            self.detail_widgets["template_name"].bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
            
            ctk.CTkLabel(content_frame, text="Filename:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            filename_label = ctk.CTkLabel(content_frame, text=str(item_data.get("filename", "N/A")), anchor="w")
            filename_label.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
            
            ctk.CTkLabel(content_frame, text="Preview:").grid(row=2, column=0, padx=5, pady=5, sticky="nw")
            self.template_preview_image_label = ctk.CTkLabel(content_frame, text="No preview", width=MAX_PREVIEW_WIDTH, height=MAX_PREVIEW_HEIGHT)
            self.template_preview_image_label.grid(row=2, column=1, padx=5, pady=5, sticky="w")
            self._display_template_preview(item_data.get("filename"))
            
            ctk.CTkButton(content_frame, text="Apply Changes", command=self._apply_template_changes).grid(row=3, column=0, columnspan=2, pady=10)

        elif item_data and item_type == "rule":
            logger.debug(f"Populating details for rule: {item_data.get('name')}")
            content_frame.grid_columnconfigure(1, weight=1)
            self.selected_sub_condition_index = None
            if self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled")

            row_idx = 0
            ctk.CTkLabel(content_frame, text="Rule Name:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
            self.detail_widgets["rule_name"] = ctk.CTkEntry(content_frame)
            self.detail_widgets["rule_name"].insert(0, item_data.get("name", ""))
            self.detail_widgets["rule_name"].grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
            self.detail_widgets["rule_name"].bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
            row_idx += 1

            ctk.CTkLabel(content_frame, text="Default Region:").grid(row=row_idx, column=0, sticky="w", padx=5, pady=2)
            region_names = [""] + [r.get("name", "") for r in self.profile_data.get("regions", []) if r.get("name")]
            self.detail_optionmenu_vars["rule_region"] = ctk.StringVar(value=item_data.get("region", ""))
            region_menu = ctk.CTkOptionMenu(content_frame, variable=self.detail_optionmenu_vars["rule_region"], values=region_names, command=lambda c: self._set_dirty_status(True))
            region_menu.grid(row=row_idx, column=1, sticky="ew", padx=5, pady=2)
            row_idx += 1

            condition_data = copy.deepcopy(item_data.get("condition", {}))
            action_data = copy.deepcopy(item_data.get("action", {}))

            # Condition Outer Frame
            cond_outer_frame = ctk.CTkFrame(content_frame)
            cond_outer_frame.grid(row=row_idx, column=0, columnspan=2, sticky="new", pady=(10, 0))
            cond_outer_frame.grid_columnconfigure(0, weight=1)
            row_idx += 1
            
            cond_header_frame = ctk.CTkFrame(cond_outer_frame, fg_color="transparent")
            cond_header_frame.pack(fill="x", padx=5)
            ctk.CTkLabel(cond_header_frame, text="CONDITION", font=ctk.CTkFont(weight="bold")).pack(side="left", anchor="w")
            
            is_compound = "logical_operator" in condition_data and isinstance(condition_data.get("sub_conditions"), list)
            btn_text = "Convert to Single" if is_compound else "Convert to Compound"
            
            if not self.btn_convert_condition or not self.btn_convert_condition.winfo_exists():
                self.btn_convert_condition = ctk.CTkButton(cond_header_frame, text=btn_text, command=self._convert_condition_structure, width=160)
                self.btn_convert_condition.pack(side="right", padx=(0, 5))
            else:
                self.btn_convert_condition.configure(text=btn_text)

            self.condition_params_frame = ctk.CTkFrame(cond_outer_frame, fg_color="transparent")
            self.condition_params_frame.pack(fill="x", expand=True, padx=5, pady=(0, 5))
            self.condition_params_frame.grid_columnconfigure(1, weight=1) # For param entries
            self._render_rule_condition_editor(condition_data) # This will populate condition_params_frame

            # Action Outer Frame
            act_outer_frame = ctk.CTkFrame(content_frame)
            act_outer_frame.grid(row=row_idx, column=0, columnspan=2, sticky="new", pady=(10, 0))
            act_outer_frame.grid_columnconfigure(0, weight=1)
            row_idx += 1
            ctk.CTkLabel(act_outer_frame, text="ACTION", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=5)
            
            self.action_params_frame = ctk.CTkFrame(act_outer_frame, fg_color="transparent")
            self.action_params_frame.pack(fill="x", expand=True, padx=5, pady=(0, 5))
            self.action_params_frame.grid_columnconfigure(1, weight=1) # For param entries
            
            ctk.CTkLabel(self.action_params_frame, text="Action Type:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            initial_action_type = str(action_data.get("type", "log_message"))
            self.detail_optionmenu_vars["action_type"] = ctk.StringVar(value=initial_action_type)
            action_type_menu = ctk.CTkOptionMenu(self.action_params_frame, variable=self.detail_optionmenu_vars["action_type"], values=ACTION_TYPES, command=lambda choice: self._on_rule_part_type_change("action", choice))
            action_type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self._render_action_parameters(action_data, self.action_params_frame, start_row=1)

            ctk.CTkButton(content_frame, text="Apply Rule Changes", command=self._apply_rule_changes).grid(row=row_idx, column=0, columnspan=2, pady=(20, 5))

        elif item_data: # Fallback for unknown item types (should not happen with current logic)
            details_text = json.dumps(item_data, indent=2)
            tb = ctk.CTkTextbox(content_frame, wrap="word", height=500)
            tb.pack(fill="both", expand=True, padx=5, pady=5)
            tb.insert("0.0", details_text)
            tb.configure(state="disabled")
            logger.debug(f"Details for {item_type} (raw JSON): {str(item_data)[:100]}")
        else: # No item selected
            if hasattr(self, 'label_details_placeholder') and self.label_details_placeholder.winfo_exists():
                self.label_details_placeholder.destroy() # Remove old one if exists
            self.label_details_placeholder = ctk.CTkLabel(content_frame, text="Select an item from a list to view/edit its details.", wraplength=380, justify="center")
            self.label_details_placeholder.pack(padx=10, pady=20, anchor="center", expand=True)
            logger.debug("Details panel cleared or showing placeholder.")
            
    def _render_rule_condition_editor(self, condition_data: Dict):
        # Clear previous condition editor content (excluding header)
        if not self.condition_params_frame:
            logger.error("Cannot render rule condition editor: condition_params_frame is None.")
            return
        for widget in self.condition_params_frame.winfo_children():
            widget.destroy()
        
        self.condition_params_frame.grid_columnconfigure(1, weight=1) # Ensure second column expands for widgets

        is_compound = "logical_operator" in condition_data and isinstance(condition_data.get("sub_conditions"), list)

        if is_compound:
            # Logical Operator Dropdown
            ctk.CTkLabel(self.condition_params_frame, text="Logical Operator:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            self.detail_optionmenu_vars["logical_operator"] = ctk.StringVar(value=condition_data.get("logical_operator", "AND"))
            op_menu = ctk.CTkOptionMenu(self.condition_params_frame, variable=self.detail_optionmenu_vars["logical_operator"], values=LOGICAL_OPERATORS, command=lambda c: self._set_dirty_status(True))
            op_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

            # Sub-conditions list and editor area
            sub_cond_frame = ctk.CTkFrame(self.condition_params_frame, fg_color="transparent")
            sub_cond_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(5,0))
            sub_cond_frame.grid_columnconfigure(0, weight=1) # List part
            sub_cond_frame.grid_columnconfigure(1, weight=2) # Editor part (if shown side-by-side, or below)
            
            # Sub-conditions list (Scrollable)
            sc_list_header = ctk.CTkFrame(sub_cond_frame, fg_color="transparent")
            sc_list_header.grid(row=0, column=0, sticky="ew")
            ctk.CTkLabel(sc_list_header, text="Sub-Conditions:", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)
            add_sub_btn = ctk.CTkButton(sc_list_header, text="+ Add", width=60, command=self._add_sub_condition_to_rule)
            add_sub_btn.pack(side="right", padx=5)
            self.btn_remove_sub_condition = ctk.CTkButton(sc_list_header, text="- Remove", width=75, command=self._remove_selected_sub_condition, state="disabled")
            self.btn_remove_sub_condition.pack(side="right", padx=(0,5))

            self.sub_conditions_list_frame = ctk.CTkScrollableFrame(sub_cond_frame, label_text="", height=150) # Fixed height for list
            self.sub_conditions_list_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
            self._populate_sub_conditions_list(condition_data.get("sub_conditions", []))

            # Sub-condition parameter editor (placeholder or for selected sub-condition)
            self.sub_condition_params_frame = ctk.CTkFrame(sub_cond_frame, fg_color="transparent") # This frame will hold params for *one* selected sub-condition
            self.sub_condition_params_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5) # Make it span full width below list
            self.sub_condition_params_frame.grid_columnconfigure(1, weight=1)
            # Initial placeholder for sub-condition editor
            ctk.CTkLabel(self.sub_condition_params_frame, text="Select a sub-condition above to edit its parameters.").pack(padx=5, pady=5)

        else: # Single condition
            ctk.CTkLabel(self.condition_params_frame, text="Condition Type:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
            current_cond_type = str(condition_data.get("type", "always_true"))
            self.detail_optionmenu_vars["condition_type"] = ctk.StringVar(value=current_cond_type)
            cond_type_menu = ctk.CTkOptionMenu(self.condition_params_frame, variable=self.detail_optionmenu_vars["condition_type"], values=CONDITION_TYPES, command=lambda choice: self._on_rule_part_type_change("condition", choice))
            cond_type_menu.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
            self._render_condition_parameters(condition_data, self.condition_params_frame, start_row=1, is_sub_condition=False)
        
        # Update Convert button text
        is_compound_now = "logical_operator" in condition_data
        btn_text = "Convert to Single" if is_compound_now else "Convert to Compound"
        if self.btn_convert_condition and self.btn_convert_condition.winfo_exists():
            self.btn_convert_condition.configure(text=btn_text)


    def _display_template_preview(self, fn: Optional[str]):
        if not self.template_preview_image_label or not fn or not self.current_profile_path:
            if self.template_preview_image_label:
                self.template_preview_image_label.configure(image=None, text="No preview available.")
            logger.debug("Template preview skipped: no label, filename, or profile path.")
            return

        profile_dir = os.path.dirname(self.current_profile_path)
        # Templates are expected in a 'templates' subdirectory relative to the profile JSON file
        template_path = os.path.join(profile_dir, "templates", fn)
        logger.debug(f"Attempting to load template preview from: {template_path}")

        if os.path.exists(template_path):
            try:
                img = Image.open(template_path)
                img.thumbnail((MAX_PREVIEW_WIDTH, MAX_PREVIEW_HEIGHT))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.template_preview_image_label.configure(image=ctk_img, text="")
                logger.debug(f"Template preview loaded for '{fn}'. Display size: {img.width}x{img.height}")
            except Exception as e:
                self.template_preview_image_label.configure(image=None, text=f"Error loading preview:\n{fn}")
                logger.error(f"Error loading template preview for '{template_path}': {e}", exc_info=True)
        else:
            self.template_preview_image_label.configure(image=None, text=f"Template file not found:\n{fn}")
            logger.warning(f"Template preview: File not found at '{template_path}'.")

    def _render_condition_parameters(self, cond_data: Dict, parent_frame: ctk.CTkFrame, start_row: int, is_sub_condition: bool = False):
        prefix = "subcond_" if is_sub_condition else "cond_"
        logger.debug(f"Rendering condition (sub={is_sub_condition}) parameters. Type: '{cond_data.get('type')}', Prefix: '{prefix}', Data: {cond_data}")

        # Clear previous parameters in this frame starting from start_row
        for widget in list(parent_frame.winfo_children()):
            grid_info = widget.grid_info()
            if grid_info and grid_info.get("row", -1) >= start_row:
                widget.destroy()
        
        # Clear related entries from detail_widgets and detail_optionmenu_vars
        keys_to_remove = [k for k in self.detail_widgets if k.startswith(prefix)]
        for key in keys_to_remove:
            self.detail_widgets.pop(key, None)
            self.detail_optionmenu_vars.pop(f"{key}_var", None) # For OptionMenus/CheckBoxes

        cond_type = cond_data.get("type")
        current_row = start_row

        def add_param_entry(key:str, default_value:Any, label_text:Optional[str]=None, row_override:Optional[int]=None, placeholder:Optional[str]=None, is_textbox:bool=False):
            nonlocal current_row
            target_row = row_override if row_override is not None else current_row
            
            _label = label_text if label_text else key.replace("_", " ").capitalize() + ":"
            ctk.CTkLabel(parent_frame, text=_label).grid(row=target_row, column=0, padx=5, pady=2, sticky="nw" if is_textbox else "w")
            
            if is_textbox:
                widget = ctk.CTkTextbox(parent_frame, height=60, wrap="word")
                widget.insert("0.0", str(cond_data.get(key, default_value)))
                widget.bind("<FocusOut>", lambda e: self._set_dirty_status(True)) # Or KeyRelease
            else:
                widget = ctk.CTkEntry(parent_frame, placeholder_text=placeholder if placeholder else str(default_value))
                widget.insert(0, str(cond_data.get(key, default_value)))
                widget.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
            
            widget.grid(row=target_row, column=1, padx=5, pady=2, sticky="ew")
            self.detail_widgets[f"{prefix}{key}"] = widget
            if row_override is None:
                current_row += 1
            return widget

        def add_param_optionmenu(key:str, default_value:Any, values:List[str], label_text:Optional[str]=None, row_override:Optional[int]=None):
            nonlocal current_row
            target_row = row_override if row_override is not None else current_row
            _label = label_text if label_text else key.replace("_", " ").capitalize() + ":"
            ctk.CTkLabel(parent_frame, text=_label).grid(row=target_row, column=0, padx=5, pady=2, sticky="w")
            
            var = ctk.StringVar(value=str(cond_data.get(key, default_value)))
            menu = ctk.CTkOptionMenu(parent_frame, variable=var, values=values, command=lambda choice: self._set_dirty_status(True))
            menu.grid(row=target_row, column=1, padx=5, pady=2, sticky="ew")
            self.detail_widgets[f"{prefix}{key}"] = menu
            self.detail_optionmenu_vars[f"{prefix}{key}_var"] = var # Store the variable
            if row_override is None:
                current_row += 1
            return menu

        def add_param_checkbox(key:str, default_value:bool, label_text:Optional[str]=None, row_override:Optional[int]=None):
            nonlocal current_row
            target_row = row_override if row_override is not None else current_row
            _label = label_text if label_text else key.replace("_", " ").capitalize() + ":"
            
            var = tk.BooleanVar(value=bool(cond_data.get(key, default_value))) # Use tk.BooleanVar
            checkbox = ctk.CTkCheckBox(parent_frame, text=_label, variable=var, command=lambda: self._set_dirty_status(True))
            checkbox.grid(row=target_row, column=0, columnspan=2, padx=5, pady=2, sticky="w")
            self.detail_widgets[f"{prefix}{key}"] = checkbox # Store checkbox itself
            self.detail_optionmenu_vars[f"{prefix}{key}_var"] = var # Store the BooleanVar
            if row_override is None:
                current_row += 1
            return checkbox

        if cond_type == "pixel_color":
            add_param_entry("relative_x", 0)
            add_param_entry("relative_y", 0)
            add_param_entry("expected_bgr", "0,0,0", placeholder="B,G,R")
            add_param_entry("tolerance", 0)
        elif cond_type == "average_color_is":
            add_param_entry("expected_bgr", "128,128,128", placeholder="B,G,R")
            add_param_entry("tolerance", 10)
        elif cond_type == "template_match_found":
            template_names = [""] + [t.get("name", "") for t in self.profile_data.get("templates", []) if t.get("name")]
            add_param_optionmenu("template_name", cond_data.get("template_name", ""), template_names, label_text="Template Name:")
            add_param_entry("min_confidence", 0.8)
            add_param_entry("capture_as", "", label_text="Capture Details As:", placeholder="Optional variable name")
        elif cond_type == "ocr_contains_text":
            add_param_entry("text_to_find", "")
            add_param_checkbox("case_sensitive", False, label_text="Case Sensitive")
            add_param_entry("min_ocr_confidence", 70.0)
            add_param_entry("capture_as", "", label_text="Capture Text As:", placeholder="Optional variable name")
        elif cond_type == "dominant_color_matches":
            add_param_entry("expected_bgr", "0,0,255", placeholder="B,G,R")
            add_param_entry("tolerance", 10)
            add_param_entry("check_top_n_dominant", 1)
            add_param_entry("min_percentage", 5.0)
        elif cond_type == "always_true":
            ctk.CTkLabel(parent_frame, text="This condition always evaluates to true. No parameters.").grid(row=current_row, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        
        logger.debug(f"Finished rendering parameters for condition type '{cond_type}' (sub={is_sub_condition}).")

    def _render_action_parameters(self, action_data: Dict, parent_frame: ctk.CTkFrame, start_row: int):
        prefix = "act_"
        logger.debug(f"Rendering action parameters. Type: '{action_data.get('type')}', Data: {action_data}")

        for widget in list(parent_frame.winfo_children()):
            grid_info = widget.grid_info()
            if grid_info and grid_info.get("row", -1) >= start_row:
                widget.destroy()
        
        keys_to_remove = [k for k in self.detail_widgets if k.startswith(prefix)]
        for key in keys_to_remove:
            self.detail_widgets.pop(key, None)
            self.detail_optionmenu_vars.pop(f"{key}_var", None)

        action_type = action_data.get("type")
        current_row = start_row

        def add_param_entry(key: str, default_value: Any, label_text: Optional[str] = None, row_override: Optional[int] = None, placeholder: Optional[str] = None, is_textbox: bool = False):
            nonlocal current_row
            target_row = row_override if row_override is not None else current_row
            _label = label_text if label_text else key.replace("_", " ").capitalize() + ":"
            ctk.CTkLabel(parent_frame, text=_label).grid(row=target_row, column=0, padx=5, pady=2, sticky="nw" if is_textbox else "w")
            if is_textbox:
                widget = ctk.CTkTextbox(parent_frame, height=60, wrap="word")
                widget.insert("0.0", str(action_data.get(key, default_value)))
                widget.bind("<FocusOut>", lambda e: self._set_dirty_status(True))
            else:
                widget = ctk.CTkEntry(parent_frame, placeholder_text=placeholder if placeholder else str(default_value))
                widget.insert(0, str(action_data.get(key, default_value)))
                widget.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
            widget.grid(row=target_row, column=1, padx=5, pady=2, sticky="ew")
            self.detail_widgets[f"{prefix}{key}"] = widget
            if row_override is None: current_row += 1
            return widget

        def add_param_optionmenu(key: str, default_value: Any, values: List[str], label_text: Optional[str] = None, row_override: Optional[int] = None):
            nonlocal current_row
            target_row = row_override if row_override is not None else current_row
            _label = label_text if label_text else key.replace("_", " ").capitalize() + ":"
            ctk.CTkLabel(parent_frame, text=_label).grid(row=target_row, column=0, padx=5, pady=2, sticky="w")
            var = ctk.StringVar(value=str(action_data.get(key, default_value)))
            menu = ctk.CTkOptionMenu(parent_frame, variable=var, values=values, command=lambda choice: self._set_dirty_status(True))
            menu.grid(row=target_row, column=1, padx=5, pady=2, sticky="ew")
            self.detail_widgets[f"{prefix}{key}"] = menu
            self.detail_optionmenu_vars[f"{prefix}{key}_var"] = var
            if row_override is None: current_row += 1
            return menu

        region_names = [""] + [r.get("name", "") for r in self.profile_data.get("regions", []) if r.get("name")]

        if action_type == "click":
            add_param_optionmenu("target_relation", "center_of_region", CLICK_TARGET_RELATIONS)
            add_param_optionmenu("target_region", "", region_names, label_text="Target Region:")
            add_param_entry("x", 0, placeholder="Abs/Rel X or {var}")
            add_param_entry("y", 0, placeholder="Abs/Rel Y or {var}")
            add_param_optionmenu("button", "left", CLICK_BUTTONS)
            add_param_entry("clicks", 1, placeholder="Number or {var}")
            add_param_entry("interval", 0.0, placeholder="Seconds or {var}")
            add_param_entry("pyautogui_pause_before", 0.0, label_text="Pause Before (s):", placeholder="Seconds or {var}")
        elif action_type == "type_text":
            add_param_entry("text", "", is_textbox=True, placeholder="Text to type or {var}")
            add_param_entry("interval", 0.0, placeholder="Seconds or {var}")
            add_param_entry("pyautogui_pause_before", 0.0, label_text="Pause Before (s):", placeholder="Seconds or {var}")
        elif action_type == "press_key":
            add_param_entry("key", "enter", placeholder="e.g., enter or ctrl,c or {var}")
            add_param_entry("pyautogui_pause_before", 0.0, label_text="Pause Before (s):", placeholder="Seconds or {var}")
        elif action_type == "log_message":
            add_param_entry("message", "Rule triggered", is_textbox=True, placeholder="Log message or {var}")
            add_param_optionmenu("level", "INFO", LOG_LEVELS)
        
        logger.debug(f"Finished rendering parameters for action type '{action_type}'.")

    def _validate_and_get_widget_value(self, widget_ref_or_key: Union[str, ctk.CTkBaseClass],
                                      field_name_for_error: str,
                                      target_type: type,
                                      default_val: Any,
                                      required: bool = False,
                                      allow_empty_string: bool = False,
                                      min_val: Optional[Union[int, float]] = None,
                                      max_val: Optional[Union[int, float]] = None) -> Tuple[Any, bool]:
        """
        Validates and retrieves value from a widget (CTkEntry, CTkOptionMenu variable, CTkCheckBox variable).
        Returns (value, is_valid_bool). Value will be default_val if validation fails.
        """
        val_str = ""
        is_valid = True
        actual_value = default_val # Start with default

        try:
            widget = None
            if isinstance(widget_ref_or_key, str): # It's a key for self.detail_widgets
                widget = self.detail_widgets.get(widget_ref_or_key)
            elif isinstance(widget_ref_or_key, ctk.CTkBaseClass): # It's the widget itself
                widget = widget_ref_or_key
            
            if widget is None:
                logger.error(f"Validation Error: Widget for '{field_name_for_error}' (key: {widget_ref_or_key}) not found.")
                if required: return default_val, False
                return default_val, True # Not required, not found, so valid as default

            if isinstance(widget, ctk.CTkEntry):
                val_str = widget.get().strip()
            elif isinstance(widget, ctk.CTkTextbox):
                 val_str = widget.get("0.0", "end-1c").strip() # Get all text, strip trailing newline
            elif isinstance(widget, ctk.CTkOptionMenu):
                # Value comes from the associated StringVar
                var_key = ""
                for k, v_widget in self.detail_widgets.items():
                    if v_widget == widget: # Find the key for this OptionMenu
                        var_key = f"{k}_var" # Construct var key (convention)
                        break
                string_var = self.detail_optionmenu_vars.get(var_key)
                if string_var:
                    val_str = string_var.get()
                else:
                    logger.warning(f"StringVar not found for OptionMenu '{field_name_for_error}' (key: {var_key}). Using default.")
                    val_str = str(default_val) # Fallback
            elif isinstance(widget, ctk.CTkCheckBox):
                # Value comes from associated BooleanVar
                var_key = ""
                for k, v_widget in self.detail_widgets.items():
                    if v_widget == widget:
                        var_key = f"{k}_var"
                        break
                bool_var = self.detail_optionmenu_vars.get(var_key)
                if bool_var and isinstance(bool_var, tk.BooleanVar):
                    actual_value = bool_var.get()
                    return actual_value, True # Checkboxes are inherently valid (True/False)
                else:
                    logger.warning(f"BooleanVar not found for CheckBox '{field_name_for_error}' (key: {var_key}). Using default.")
                    actual_value = default_val
                    return actual_value, True # Assume valid with default for checkbox if var missing

            # Common validation for string-based inputs
            if not allow_empty_string and not val_str and required:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' cannot be empty.")
                logger.warning(f"Validation failed for '{field_name_for_error}': Required field is empty.")
                return default_val, False
            
            if not val_str and not required and not allow_empty_string: # Not required, but also not allowed to be empty if something was typed then deleted
                 pass # Allow default to be used or it will be ""
            elif not val_str and allow_empty_string:
                actual_value = "" if target_type == str else default_val # Empty string is valid
                return actual_value, True


            # Type conversion and range checks
            if target_type == str:
                actual_value = val_str
            elif target_type == int:
                actual_value = int(val_str)
            elif target_type == float:
                actual_value = float(val_str)
            # bool is handled by checkbox case

            if min_val is not None and actual_value < min_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be at least {min_val}.")
                is_valid = False
            if max_val is not None and actual_value > max_val:
                messagebox.showerror("Input Error", f"'{field_name_for_error}' must be no more than {max_val}.")
                is_valid = False

        except ValueError:
            messagebox.showerror("Input Error", f"Invalid format for '{field_name_for_error}'. Expected a {target_type.__name__}.")
            is_valid = False
        except Exception as e:
            messagebox.showerror("Input Error", f"Unexpected error validating '{field_name_for_error}': {e}")
            logger.error(f"Unexpected validation error for '{field_name_for_error}': {e}", exc_info=True)
            is_valid = False

        if not is_valid and required:
            logger.warning(f"Validation failed for '{field_name_for_error}' (value: '{val_str}'). Returning default: {default_val}")
            return default_val, False
        
        return actual_value, is_valid
        
    def _parse_bgr_string(self, bgr_str: str, field_name_for_error: str) -> Optional[List[int]]:
        """Parses a 'B,G,R' string into a list of 3 integers. Returns None on failure."""
        try:
            parts = [int(p.strip()) for p in bgr_str.split(',')]
            if len(parts) == 3 and all(0 <= x <= 255 for x in parts):
                return parts
            else:
                messagebox.showerror("BGR Format Error", f"Invalid BGR format for '{field_name_for_error}'.\nExpected 3 numbers (0-255) separated by commas (e.g., '255,0,128').")
                return None
        except ValueError:
            messagebox.showerror("BGR Format Error", f"Invalid BGR values for '{field_name_for_error}'.\nNumbers must be integers between 0 and 255 (e.g., '255,0,128').")
            return None

    def _get_condition_parameters_from_ui(self, cond_type: str, is_sub_condition: bool = False) -> Optional[Dict[str, Any]]:
        prefix = "subcond_" if is_sub_condition else "cond_"
        params: Dict[str, Any] = {"type": cond_type}
        all_params_valid = True
        logger.debug(f"Getting UI parameters for condition type: '{cond_type}' (sub={is_sub_condition}), prefix: '{prefix}'")

        def get_param(key:str, field_name:str, target_type:type, default_val:Any, **kwargs_for_validation) -> None:
            nonlocal all_params_valid
            val, is_valid = self._validate_and_get_widget_value(f"{prefix}{key}", field_name, target_type, default_val, **kwargs_for_validation)
            if not is_valid and kwargs_for_validation.get("required", False): # If required and invalid, flag it
                all_params_valid = False
            params[key] = val # Store the value (could be default if validation failed but allowed default)

        def get_bgr_param(key:str, field_name:str, default_bgr_str:str) -> None:
            nonlocal all_params_valid
            bgr_str_val, is_str_valid = self._validate_and_get_widget_value(f"{prefix}{key}", field_name, str, default_bgr_str, required=True)
            if not is_str_valid: # String itself is invalid (e.g., empty when required)
                all_params_valid = False
                params[key] = [int(p) for p in default_bgr_str.split(',')] # Default BGR list
                return
            
            parsed_bgr = self._parse_bgr_string(bgr_str_val, field_name)
            if parsed_bgr is None:
                all_params_valid = False
                params[key] = [int(p) for p in default_bgr_str.split(',')] # Default BGR list
            else:
                params[key] = parsed_bgr
        
        def get_optionmenu_param(key:str, field_name:str, default_val:str) -> None:
            var = self.detail_optionmenu_vars.get(f"{prefix}{key}_var")
            if var: params[key] = var.get()
            else: logger.warning(f"StringVar not found for OptionMenu '{field_name}' (key: {prefix}{key}_var). Using default."); params[key] = default_val

        def get_checkbox_param(key:str, field_name:str, default_val:bool) -> None:
            var = self.detail_optionmenu_vars.get(f"{prefix}{key}_var")
            if var and isinstance(var, tk.BooleanVar): params[key] = var.get()
            else: logger.warning(f"BooleanVar not found for CheckBox '{field_name}' (key: {prefix}{key}_var). Using default."); params[key] = default_val


        if cond_type == "pixel_color":
            get_param("relative_x", "Relative X", int, 0, required=True)
            get_param("relative_y", "Relative Y", int, 0, required=True)
            get_bgr_param("expected_bgr", "Expected BGR", "0,0,0")
            get_param("tolerance", "Tolerance", int, 0, min_val=0, max_val=255, required=True)
        elif cond_type == "average_color_is":
            get_bgr_param("expected_bgr", "Expected BGR", "128,128,128")
            get_param("tolerance", "Tolerance", int, 10, min_val=0, max_val=255, required=True)
        elif cond_type == "template_match_found":
            get_optionmenu_param("template_name", "Template Name", "") # Name from dropdown
            # Resolve to filename
            sel_tpl_name = params.get("template_name", "")
            if not sel_tpl_name:
                messagebox.showerror("Input Error", "Template Name for 'template_match_found' must be selected.")
                all_params_valid = False
                params["template_filename"] = ""
            else:
                actual_fn = next((t.get("filename", "") for t in self.profile_data.get("templates", []) if t.get("name") == sel_tpl_name), "")
                if not actual_fn:
                    messagebox.showerror("Input Error", f"Could not find filename for selected template name '{sel_tpl_name}'.")
                    all_params_valid = False
                params["template_filename"] = actual_fn
            
            get_param("min_confidence", "Min Confidence", float, 0.8, min_val=0.0, max_val=1.0, required=True)
            get_param("capture_as", "Capture Details As", str, "", allow_empty_string=True, required=False)
        elif cond_type == "ocr_contains_text":
            get_param("text_to_find", "Text to Find", str, "", allow_empty_string=False, required=True)
            get_checkbox_param("case_sensitive", "Case Sensitive", False)
            get_param("min_ocr_confidence", "Min OCR Confidence", float, 70.0, min_val=0.0, max_val=100.0, required=False)
            get_param("capture_as", "Capture Text As", str, "", allow_empty_string=True, required=False)
        elif cond_type == "dominant_color_matches":
            get_bgr_param("expected_bgr", "Expected BGR", "0,0,255")
            get_param("tolerance", "Tolerance", int, 10, min_val=0, max_val=255, required=True)
            get_param("check_top_n_dominant", "Check Top N Dominant", int, 1, min_val=1, required=True)
            get_param("min_percentage", "Min Percentage", float, 5.0, min_val=0.0, max_val=100.0, required=True)
        
        if not all_params_valid:
            logger.error(f"Validation failed for one or more parameters of condition '{cond_type}' (sub={is_sub_condition}). Returning None.")
            return None
        logger.debug(f"Collected valid condition parameters (sub={is_sub_condition}) from UI: {params}")
        return params

    def _get_action_parameters_from_ui(self, action_type: str) -> Optional[Dict[str, Any]]:
        prefix = "act_"
        params: Dict[str, Any] = {"type": action_type}
        all_params_valid = True
        logger.debug(f"Getting UI parameters for action type: '{action_type}'")

        def get_param(key:str, field_name:str, target_type:type, default_val:Any, **kwargs_for_validation) -> None:
            nonlocal all_params_valid
            # For actions, we often want to store the string value directly if it might contain variables like {var_name}
            # ActionExecutor will handle conversion attempts. So, for many, target_type might just be str.
            val, is_valid = self._validate_and_get_widget_value(f"{prefix}{key}", field_name, target_type, default_val, **kwargs_for_validation)
            if not is_valid and kwargs_for_validation.get("required", False):
                all_params_valid = False
            params[key] = val # Store string value for now; ActionExecutor will parse

        def get_optionmenu_param(key:str, field_name:str, default_val:str) -> None:
            var = self.detail_optionmenu_vars.get(f"{prefix}{key}_var")
            if var: params[key] = var.get()
            else: logger.warning(f"StringVar not found for OptionMenu '{field_name}' (key: {prefix}{key}_var). Using default."); params[key] = default_val

        if action_type == "click":
            get_optionmenu_param("target_relation", "Target Relation", "center_of_region")
            get_optionmenu_param("target_region", "Target Region", "") # Can be empty
            get_param("x", "X Coord/Offset", str, "0", allow_empty_string=True, required=False)
            get_param("y", "Y Coord/Offset", str, "0", allow_empty_string=True, required=False)
            get_optionmenu_param("button", "Button", "left")
            get_param("clicks", "Number of Clicks", str, "1", allow_empty_string=True, required=False) # Allow "1" or "{num_clicks}"
            get_param("interval", "Click Interval (s)", str, "0.0", allow_empty_string=True, required=False)
            get_param("pyautogui_pause_before", "Pause Before (s)", str, "0.0", allow_empty_string=True, required=False)
        elif action_type == "type_text":
            get_param("text", "Text to Type", str, "", allow_empty_string=True, required=False) # Textbox value
            get_param("interval", "Typing Interval (s)", str, "0.0", allow_empty_string=True, required=False)
            get_param("pyautogui_pause_before", "Pause Before (s)", str, "0.0", allow_empty_string=True, required=False)
        elif action_type == "press_key":
            get_param("key", "Key(s) to Press", str, "enter", allow_empty_string=False, required=True)
            get_param("pyautogui_pause_before", "Pause Before (s)", str, "0.0", allow_empty_string=True, required=False)
        elif action_type == "log_message":
            get_param("message", "Log Message", str, "Rule triggered", allow_empty_string=True, required=False) # Textbox value
            get_optionmenu_param("level", "Log Level", "INFO")
        
        if not all_params_valid:
            logger.error(f"Validation failed for one or more parameters of action '{action_type}'. Returning None.")
            return None
        logger.debug(f"Collected valid action parameters from UI: {params}")
        return params

    def _apply_region_changes(self):
        if self.selected_region_index is None:
            logger.warning("Apply Region Changes: No region selected.")
            return
        
        region_list: List[Dict] = self.profile_data.get("regions", [])
        current_region_data = region_list[self.selected_region_index]
        original_name = current_region_data.get("name", "UnknownRegion")
        logger.info(f"Attempting to apply changes to region '{original_name}'.")

        all_valid = True
        new_values = {}

        name_val, name_is_valid = self._validate_and_get_widget_value(self.detail_widgets["name"], "Region Name", str, original_name, allow_empty_string=False, required=True)
        if not name_is_valid: all_valid = False
        else: new_values["name"] = name_val

        x_val, x_is_valid = self._validate_and_get_widget_value(self.detail_widgets["x"], "X Coordinate", int, current_region_data.get("x",0), required=True)
        if not x_is_valid: all_valid = False
        else: new_values["x"] = x_val
        
        y_val, y_is_valid = self._validate_and_get_widget_value(self.detail_widgets["y"], "Y Coordinate", int, current_region_data.get("y",0), required=True)
        if not y_is_valid: all_valid = False
        else: new_values["y"] = y_val

        width_val, width_is_valid = self._validate_and_get_widget_value(self.detail_widgets["width"], "Width", int, current_region_data.get("width",1), min_val=1, required=True)
        if not width_is_valid: all_valid = False
        else: new_values["width"] = width_val

        height_val, height_is_valid = self._validate_and_get_widget_value(self.detail_widgets["height"], "Height", int, current_region_data.get("height",1), min_val=1, required=True)
        if not height_is_valid: all_valid = False
        else: new_values["height"] = height_val

        if not all_valid:
            logger.error(f"Apply changes for region '{original_name}' aborted due to validation errors.")
            return

        # Check for name collision if name changed
        if new_values["name"] != original_name:
            for i, r_data in enumerate(region_list):
                if i != self.selected_region_index and r_data.get("name") == new_values["name"]:
                    messagebox.showerror("Name Error", f"A region with the name '{new_values['name']}' already exists.")
                    logger.warning(f"Region name collision for '{new_values['name']}'. Apply aborted.")
                    return
        
        current_region_data.update(new_values)
        logger.info(f"Region '{original_name}' updated in profile_data to '{new_values['name']}'.")
        self._set_dirty_status(True)
        self._populate_specific_list_frame("region", self.regions_list_scroll_frame, region_list, lambda item, idx: item.get("name", f"Region {idx + 1}"), self.btn_remove_region, "region")
        self._update_details_panel(current_region_data, "region") # Refresh details panel
        messagebox.showinfo("Region Updated", f"Region '{new_values['name']}' has been updated.")


    def _apply_template_changes(self):
        if self.selected_template_index is None:
            logger.warning("Apply Template Changes: No template selected.")
            return

        template_list: List[Dict] = self.profile_data.get("templates", [])
        current_template_data = template_list[self.selected_template_index]
        original_name = current_template_data.get("name", "UnknownTemplate")
        logger.info(f"Attempting to apply changes to template '{original_name}'.")

        name_val, name_is_valid = self._validate_and_get_widget_value(self.detail_widgets["template_name"], "Template Name", str, original_name, allow_empty_string=False, required=True)
        
        if not name_is_valid:
            logger.error(f"Apply changes for template '{original_name}' aborted: Name validation failed.")
            return

        # Check for name collision if name changed
        if name_val != original_name:
            for i, t_data in enumerate(template_list):
                if i != self.selected_template_index and t_data.get("name") == name_val:
                    messagebox.showerror("Name Error", f"A template with the name '{name_val}' already exists.")
                    logger.warning(f"Template name collision for '{name_val}'. Apply aborted.")
                    return
        
        current_template_data["name"] = name_val
        logger.info(f"Template '{original_name}' name updated in profile_data to '{name_val}'.")
        self._set_dirty_status(True)
        self._populate_specific_list_frame("template", self.templates_list_scroll_frame, template_list, lambda item, idx: f"{item.get('name', f'Template {idx + 1}')} ({item.get('filename', 'N/A')})", self.btn_remove_template, "template")
        self._update_details_panel(current_template_data, "template")
        messagebox.showinfo("Template Updated", f"Template '{name_val}' has been updated.")

    def _apply_rule_changes(self):
        if self.selected_rule_index is None or not self.profile_data:
            logger.warning("Apply Rule Changes: No rule selected or profile data missing.")
            return

        rule_list: List[Dict] = self.profile_data.get("rules", [])
        current_rule_data_orig = rule_list[self.selected_rule_index]
        old_name = current_rule_data_orig.get("name", "UnknownRule")
        logger.info(f"Attempting to apply changes to rule '{old_name}'.")
        
        temp_rule_data = copy.deepcopy(current_rule_data_orig) # Work on a copy

        new_name, name_valid = self._validate_and_get_widget_value(self.detail_widgets["rule_name"], "Rule Name", str, old_name, allow_empty_string=False, required=True)
        if not name_valid: return

        # Check for name collision if name changed
        if new_name != old_name:
            for i, r_data in enumerate(rule_list):
                if i != self.selected_rule_index and r_data.get("name") == new_name:
                    messagebox.showerror("Name Error", f"A rule with the name '{new_name}' already exists.")
                    logger.warning(f"Rule name collision for '{new_name}'. Apply aborted.")
                    return
        temp_rule_data["name"] = new_name
        
        new_default_region = self.detail_optionmenu_vars["rule_region"].get()
        temp_rule_data["region"] = new_default_region if new_default_region else ""

        # Condition Data
        condition_data_to_save = {}
        is_compound_in_ui = "logical_operator" in self.detail_optionmenu_vars # Check if logical_operator dropdown exists

        if is_compound_in_ui:
            condition_data_to_save["logical_operator"] = self.detail_optionmenu_vars["logical_operator"].get()
            saved_sub_conditions = []
            
            # Get sub-conditions from profile_data as the source of truth before edit
            profile_sub_conditions_list = temp_rule_data.get("condition", {}).get("sub_conditions", [])
            all_subs_valid = True

            for idx, sub_cond_from_profile in enumerate(profile_sub_conditions_list):
                if self.selected_sub_condition_index == idx: # This sub-condition was actively being edited in UI
                    sub_cond_type_var = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                    if sub_cond_type_var:
                        sub_cond_type_ui = sub_cond_type_var.get()
                        validated_sub_params = self._get_condition_parameters_from_ui(sub_cond_type_ui, is_sub_condition=True)
                        if validated_sub_params is None: # Validation failed
                            all_subs_valid = False
                            break 
                        saved_sub_conditions.append(validated_sub_params)
                    else: # Should not happen if UI is consistent
                        logger.error("Error applying sub-condition: type var not found in UI for selected sub-condition.")
                        all_subs_valid = False; break
                        # saved_sub_conditions.append(copy.deepcopy(sub_cond_from_profile))
                else: # Sub-condition not currently selected for edit, keep its data from profile_data
                    saved_sub_conditions.append(copy.deepcopy(sub_cond_from_profile))
            
            if not all_subs_valid:
                logger.error(f"Validation failed for an edited sub-condition of rule '{new_name}'. Aborting rule save.")
                return 
            condition_data_to_save["sub_conditions"] = saved_sub_conditions
        else: # Single condition
            cond_type_ui_var = self.detail_optionmenu_vars.get("condition_type")
            if not cond_type_ui_var:
                 logger.error(f"Cannot get single condition type for rule '{new_name}'. UI variable missing."); return
            cond_type_ui = cond_type_ui_var.get()
            validated_cond_params = self._get_condition_parameters_from_ui(cond_type_ui, is_sub_condition=False)
            if validated_cond_params is None: # Validation failed
                logger.error(f"Validation failed for the single condition of rule '{new_name}'. Aborting rule save.")
                return
            condition_data_to_save = validated_cond_params
        
        temp_rule_data["condition"] = condition_data_to_save

        # Action Data
        action_type_ui_var = self.detail_optionmenu_vars.get("action_type")
        if not action_type_ui_var:
             logger.error(f"Cannot get action type for rule '{new_name}'. UI variable missing."); return
        action_type_ui = action_type_ui_var.get()
        validated_action_params = self._get_action_parameters_from_ui(action_type_ui)
        if validated_action_params is None: # Validation failed
            logger.error(f"Validation failed for the action of rule '{new_name}'. Aborting rule save.")
            return
        temp_rule_data["action"] = validated_action_params
        
        # All validations passed, commit changes
        self.profile_data["rules"][self.selected_rule_index] = temp_rule_data
        logger.info(f"Rule '{old_name}' updated in profile_data to '{new_name}'.")
        self._set_dirty_status(True)
        self._populate_specific_list_frame("rule", self.rules_list_scroll_frame, rule_list, lambda item, idx: item.get("name", f"Rule {idx + 1}"), self.btn_remove_rule, "rule")
        self._update_details_panel(temp_rule_data, "rule") # Refresh details panel
        messagebox.showinfo("Rule Updated", f"Rule '{new_name}' has been updated.")


    def _edit_region_coordinates_with_selector(self):
        if self.selected_region_index is None:
            logger.warning("Edit Region Coordinates: No region selected.")
            return

        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "You have unsaved changes. Save them before editing coordinates externally?"):
                logger.info("Edit region coordinates cancelled by user (chose not to save).")
                return
            self._save_profile() # Attempt to save
            if self._is_dirty: # If save failed or was cancelled
                logger.info("Edit region coordinates cancelled because profile save failed or was cancelled.")
                return
        
        if not self.current_profile_path:
            messagebox.showerror("Error", "Profile must be saved to a file before editing region coordinates with the selector tool.")
            logger.error("Edit Region Coordinates: Current profile is not saved (no path).")
            return
        
        logger.info(f"Launching RegionSelectorWindow for region index {self.selected_region_index} of profile '{self.current_profile_path}'...")
        try:
            # Pass the specific region data to RegionSelectorWindow if it supports editing an existing one
            # Or, RegionSelectorWindow might always add a new one, and you replace it.
            # For this example, let's assume RegionSelectorWindow can take current config_manager
            # and potentially an index or name to edit.
            # The provided RegionSelector might be designed to always save to the ConfigManager's profile.
            
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False) # Load fresh copy for selector
            if not cm_for_selector.profile_data:
                messagebox.showerror("Error", f"Could not load profile '{self.current_profile_path}' for Region Selector.")
                return

            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector, 
                                                 region_to_edit_index=self.selected_region_index) # Pass index
            self.wait_window(selector_dialog) # Wait for the dialog to close

            # After RegionSelectorWindow closes, check if it modified the profile
            # This depends on how RegionSelectorWindow signals changes.
            # A simple way is to just reload the profile from disk.
            if selector_dialog.changes_made: # Assuming RegionSelectorWindow sets a flag
                logger.info("RegionSelectorWindow reported changes. Reloading profile...")
                self._load_profile_from_path(self.current_profile_path) # Reloads all data and repopulates UI
                # Potentially re-select the edited region if possible or just refresh all
                self._set_dirty_status(True) # Changes were made externally
            else:
                logger.info("RegionSelectorWindow closed, no changes reported or cancelled.")

        except Exception as e:
            logger.error(f"Error during Edit Region Coordinates with selector: {e}", exc_info=True)
            messagebox.showerror("Region Selector Error", f"An error occurred with the Region Selector tool:\n{e}")

    def _add_region(self):
        logger.info("Add Region action initiated.")
        if not self.current_profile_path:
            messagebox.showinfo("Save Required", "Please save the current profile to a file before adding a new region.")
            if not self._save_profile_as(): # Prompts user to save, returns True on success/False on cancel
                logger.info("Add Region cancelled: Profile not saved.")
                return
        
        if self._is_dirty: # If there are other unsaved changes after potentially saving
            if not messagebox.askyesno("Save Changes?", "Save current profile changes before launching the Region Selector tool?"):
                logger.info("Add Region cancelled by user (chose not to save existing changes).")
                return
            self._save_profile()
            if self._is_dirty: # Save failed
                logger.info("Add Region cancelled: Profile save failed.")
                return
        
        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data:
                messagebox.showerror("Error", f"Could not load profile '{self.current_profile_path}' for Region Selector.")
                return

            logger.info("Launching RegionSelectorWindow for adding a new region...")
            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector) # No region_to_edit_index means 'add new'
            self.wait_window(selector_dialog)

            if selector_dialog.changes_made: # RegionSelector should set this if a region was added
                logger.info("RegionSelectorWindow reported a new region was added. Reloading profile...")
                self._load_profile_from_path(self.current_profile_path)
                self._set_dirty_status(True)
            else:
                logger.info("RegionSelectorWindow closed, no new region added or cancelled.")
        except Exception as e:
            logger.error(f"Error launching or using RegionSelectorWindow for Add Region: {e}", exc_info=True)
            messagebox.showerror("Add Region Error", f"An error occurred with the Region Selector tool:\n{e}")

    def _remove_selected_item(self, list_name_key: str, profile_data_key: str, selected_index_attr: str, remove_button_widget: ctk.CTkButton):
        selected_index = getattr(self, selected_index_attr, None)
        
        if selected_index is None or not self.profile_data or profile_data_key not in self.profile_data:
            logger.warning(f"Cannot remove {list_name_key}: No item selected or profile data is missing/incomplete.")
            return

        item_list: List[Dict] = self.profile_data[profile_data_key]
        if 0 <= selected_index < len(item_list):
            removed_item_data = item_list.pop(selected_index)
            removed_item_name = removed_item_data.get('name', 'N/A')
            logger.info(f"Removed {list_name_key} '{removed_item_name}' at index {selected_index}.")

            # Determine which list frame and display callback to use
            list_scroll_frame = getattr(self, f"{list_name_key}s_list_scroll_frame", None) # e.g., self.regions_list_scroll_frame
            display_callback = None
            if list_name_key == "region":
                display_callback = lambda item, idx: item.get("name", f"Region {idx + 1}")
            elif list_name_key == "template":
                display_callback = lambda item, idx: f"{item.get('name', f'Template {idx + 1}')} ({item.get('filename', 'N/A')})"
            elif list_name_key == "rule":
                display_callback = lambda item, idx: item.get("name", f"Rule {idx + 1}")
            
            if list_scroll_frame and display_callback:
                self._populate_specific_list_frame(list_name_key, list_scroll_frame, item_list, display_callback, remove_button_widget, list_name_key)
            
            self._set_dirty_status(True)
            setattr(self, selected_index_attr, None) # Clear selection index
            remove_button_widget.configure(state="disabled")
            self._update_details_panel(None, "none") # Clear details panel

            # Special handling for template file deletion
            if list_name_key == "template" and self.current_profile_path:
                filename_to_delete = removed_item_data.get("filename")
                if filename_to_delete:
                    profile_directory = os.path.dirname(self.current_profile_path)
                    template_file_path = os.path.join(profile_directory, "templates", filename_to_delete)
                    try:
                        if os.path.exists(template_file_path):
                            os.remove(template_file_path)
                            logger.info(f"Successfully deleted template image file: {template_file_path}")
                        else:
                            logger.warning(f"Template image file not found for deletion: {template_file_path}")
                    except OSError as e_os:
                        logger.error(f"Error deleting template image file '{template_file_path}': {e_os}", exc_info=True)
                        messagebox.showwarning("File Deletion Error", f"Could not delete template image file:\n{filename_to_delete}\n\nError: {e_os.strerror}")
        else:
            logger.warning(f"Cannot remove {list_name_key}: Invalid index {selected_index}.")

    def _remove_selected_region(self): self._remove_selected_item("region", "regions", "selected_region_index", self.btn_remove_region)
    def _remove_selected_template(self): self._remove_selected_item("template", "templates", "selected_template_index", self.btn_remove_template)
    def _remove_selected_rule(self): self._remove_selected_item("rule", "rules", "selected_rule_index", self.btn_remove_rule)

    def _add_template(self):
        logger.info("Add Template action initiated.")
        if not self.current_profile_path:
            messagebox.showinfo("Save Required", "Please save the current profile to a file before adding a new template.")
            if not self._save_profile_as():
                logger.info("Add Template cancelled: Profile not saved.")
                return
        
        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Save current profile changes before adding a new template?"):
                logger.info("Add Template cancelled by user (chose not to save existing changes).")
                return
            self._save_profile()
            if self._is_dirty:
                logger.info("Add Template cancelled: Profile save failed.")
                return

        selected_image_path = filedialog.askopenfilename(
            title="Select Template Image",
            filetypes=[("PNG images", "*.png"), ("JPEG images", "*.jpg;*.jpeg"), ("All files", "*.*")]
        )
        if not selected_image_path:
            logger.info("Add Template: No image file selected.")
            return

        template_name_dialog = ctk.CTkInputDialog(text="Enter a unique name for this template:", title="Template Name")
        template_name = template_name_dialog.get_input()
        if not template_name or not template_name.strip():
            logger.info("Add Template: No valid name entered for the template.")
            return
        template_name = template_name.strip()

        if any(t.get("name") == template_name for t in self.profile_data.get("templates", [])):
            messagebox.showerror("Name Error", f"A template with the name '{template_name}' already exists.")
            logger.warning(f"Add Template: Name '{template_name}' already exists.")
            return

        profile_dir = os.path.dirname(self.current_profile_path)
        templates_target_dir = os.path.join(profile_dir, "templates")
        try:
            os.makedirs(templates_target_dir, exist_ok=True)
            logger.debug(f"Ensured templates directory exists: {templates_target_dir}")

            base, ext = os.path.splitext(os.path.basename(selected_image_path))
            # Sanitize template_name for use as part of filename
            sane_file_base = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in template_name).rstrip().replace(' ', '_')
            target_filename_base = sane_file_base
            counter = 1
            target_filename = f"{target_filename_base}{ext}"
            final_target_path = os.path.join(templates_target_dir, target_filename)
            
            while os.path.exists(final_target_path): # Avoid overwriting
                target_filename = f"{target_filename_base}_{counter}{ext}"
                final_target_path = os.path.join(templates_target_dir, target_filename)
                counter += 1
            
            shutil.copy2(selected_image_path, final_target_path)
            logger.info(f"Template image '{selected_image_path}' copied to '{final_target_path}'.")

            new_template_entry = {"name": template_name, "filename": target_filename}
            if "templates" not in self.profile_data:
                self.profile_data["templates"] = []
            self.profile_data["templates"].append(new_template_entry)
            
            logger.info(f"Added new template to profile_data: {new_template_entry}")
            self._populate_specific_list_frame("template", self.templates_list_scroll_frame, self.profile_data.get("templates", []), lambda item, idx: f"{item.get('name', f'Template {idx + 1}')} ({item.get('filename', 'N/A')})", self.btn_remove_template, "template")
            self._set_dirty_status(True)
            messagebox.showinfo("Template Added", f"Template '{template_name}' added successfully.")

        except Exception as e:
            logger.error(f"Error adding template '{template_name}': {e}", exc_info=True)
            messagebox.showerror("Add Template Error", f"Could not add template '{template_name}':\n{e}")

    def _add_new_rule(self):
        logger.info("Add New Rule action initiated.")
        if not self.profile_data: # Should always exist after init
            self._new_profile(prompt_save=False) 

        rule_name_dialog = ctk.CTkInputDialog(text="Enter a unique name for the new rule:", title="New Rule Name")
        rule_name = rule_name_dialog.get_input()
        if not rule_name or not rule_name.strip():
            logger.info("Add New Rule: No valid name entered.")
            return
        rule_name = rule_name.strip()

        if any(r.get("name") == rule_name for r in self.profile_data.get("rules", [])):
            messagebox.showerror("Name Error", f"A rule with the name '{rule_name}' already exists.")
            logger.warning(f"Add New Rule: Name '{rule_name}' already exists.")
            return
            
        new_rule = {
            "name": rule_name,
            "region": "", # Default region can be empty
            "condition": {"type": "always_true"}, # Default simple condition
            "action": {"type": "log_message", "message": f"Rule '{rule_name}' triggered.", "level": "INFO"} # Default action
        }
        
        if "rules" not in self.profile_data:
            self.profile_data["rules"] = []
        self.profile_data["rules"].append(new_rule)
        
        logger.info(f"Added new rule placeholder to profile_data: {new_rule}")
        self._populate_specific_list_frame("rule", self.rules_list_scroll_frame, self.profile_data.get("rules", []), lambda item, idx: item.get("name", f"Rule {idx + 1}"), self.btn_remove_rule, "rule")
        self._set_dirty_status(True)
        messagebox.showinfo("Rule Added", f"Rule '{rule_name}' added successfully.")
    
    def _on_rule_part_type_change(self, part_changed: str, new_type_selected: str):
        logger.info(f"Rule's part '{part_changed}' UI type changed to: '{new_type_selected}'. Redrawing parameters.")
        self._set_dirty_status(True)

        if self.selected_rule_index is None:
            logger.warning(f"Cannot change {part_changed} type, no rule selected.")
            return
        
        current_rule_data = self.profile_data["rules"][self.selected_rule_index]
        
        if part_changed == "condition":
            if self.selected_sub_condition_index is not None: # Editing a sub-condition's type
                if not self.sub_condition_params_frame:
                    logger.error("Sub-condition params frame is not available for type change.")
                    return
                
                sub_conditions_list = current_rule_data.get("condition", {}).get("sub_conditions", [])
                if 0 <= self.selected_sub_condition_index < len(sub_conditions_list):
                    sub_condition_to_update = sub_conditions_list[self.selected_sub_condition_index]
                    if sub_condition_to_update.get("type") != new_type_selected:
                        logger.debug(f"Sub-condition type changing. Clearing old params for sub-condition index {self.selected_sub_condition_index}.")
                        # Preserve essential keys like 'type', clear others to reset for new type
                        keys_to_keep = ["type"] 
                        for key in list(sub_condition_to_update.keys()):
                            if key not in keys_to_keep:
                                sub_condition_to_update.pop(key, None)
                    sub_condition_to_update["type"] = new_type_selected
                    self._render_condition_parameters(sub_condition_to_update, self.sub_condition_params_frame, start_row=1, is_sub_condition=True)
            elif "logical_operator" not in current_rule_data.get("condition", {}): # Editing a single main condition's type
                if not self.condition_params_frame:
                    logger.error("Main condition params frame is not available for type change.")
                    return
                condition_to_update = current_rule_data.get("condition", {})
                if condition_to_update.get("type") != new_type_selected:
                    logger.debug("Main single condition type changing. Clearing old params.")
                    keys_to_keep = ["type"]
                    for key in list(condition_to_update.keys()):
                        if key not in keys_to_keep:
                            condition_to_update.pop(key, None)
                condition_to_update["type"] = new_type_selected
                self._render_condition_parameters(condition_to_update, self.condition_params_frame, start_row=1, is_sub_condition=False) # start_row=1 for single cond params after type dropdown
        
        elif part_changed == "action": # Editing main action's type
            if not self.action_params_frame:
                logger.error("Action params frame is not available for type change.")
                return
            action_to_update = current_rule_data.get("action", {})
            if action_to_update.get("type") != new_type_selected:
                logger.debug("Action type changing. Clearing old action params.")
                keys_to_keep = ["type"]
                for key in list(action_to_update.keys()):
                    if key not in keys_to_keep:
                        action_to_update.pop(key, None)
            action_to_update["type"] = new_type_selected
            self._render_action_parameters(action_to_update, self.action_params_frame, start_row=1) # start_row=1 for action params after type dropdown

    def _populate_sub_conditions_list(self, sub_conditions_data: List[Dict]):
        if not self.sub_conditions_list_frame:
            logger.warning("Cannot populate sub-conditions list: sub_conditions_list_frame is None.")
            return

        for widget in self.sub_conditions_list_frame.winfo_children():
            widget.destroy()
        
        self.selected_sub_condition_index = None
        self.selected_sub_condition_item_widget = None # Reset highlight tracker
        if hasattr(self, 'btn_remove_sub_condition') and self.btn_remove_sub_condition:
            self.btn_remove_sub_condition.configure(state="disabled")

        for i, sub_cond in enumerate(sub_conditions_data):
            summary_text = f"#{i + 1} Type: {sub_cond.get('type', 'N/A')}"
            region_override = sub_cond.get('region')
            if region_override: summary_text += f", Region: {region_override}"
            capture_as = sub_cond.get("capture_as")
            if capture_as: summary_text += f", Capture: {capture_as}"
            
            # Need to pass the item_frame to the callback for highlighting
            item_frame_container = {} 
            item_frame = self._create_clickable_list_item(
                self.sub_conditions_list_frame, summary_text,
                # Lambda captures current values of sub_cond, i, and the container
                lambda e=None, sc_data=sub_cond, idx=i, ifc=item_frame_container: self._on_sub_condition_selected(sc_data, idx, ifc.get("frame"))
            )
            item_frame_container["frame"] = item_frame # Store the created frame in the container

        logger.debug(f"Populated sub-conditions list with {len(sub_conditions_data)} items.")
        
        # Clear sub-condition parameter editor if no sub-condition is selected
        if self.selected_sub_condition_index is None and self.sub_condition_params_frame:
            for widget in self.sub_condition_params_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.sub_condition_params_frame, text="Select a sub-condition above to edit its parameters.").pack(padx=5, pady=5)

    def _on_sub_condition_selected(self, sub_cond_data: Dict, index: int, item_widget_frame: Optional[ctk.CTkFrame]):
        logger.info(f"Sub-condition selected. Index: {index}, Data: {str(sub_cond_data)[:100]}")
        if item_widget_frame is None:
            logger.error(f"Sub-condition selection error: item_widget_frame is None for index {index}.")
            return

        self.selected_sub_condition_index = index
        self._highlight_selected_list_item("condition", item_widget_frame, is_sub_list=True) # True for sub-list highlighting
        
        if hasattr(self, 'btn_remove_sub_condition') and self.btn_remove_sub_condition:
            self.btn_remove_sub_condition.configure(state="normal")

        if not self.sub_condition_params_frame:
            logger.error("Cannot display sub-condition parameters: sub_condition_params_frame is missing!")
            return

        # Clear and repopulate the dedicated sub-condition parameter editor frame
        for widget in self.sub_condition_params_frame.winfo_children():
            widget.destroy()
        self.sub_condition_params_frame.grid_columnconfigure(1, weight=1) # Ensure second column expands

        ctk.CTkLabel(self.sub_condition_params_frame, text=f"Edit Sub-Condition #{index + 1} Type:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        current_sub_cond_type = sub_cond_data.get("type", "always_true")
        self.detail_optionmenu_vars["subcond_condition_type_var"] = ctk.StringVar(value=current_sub_cond_type) # Unique var key
        
        sub_cond_type_menu = ctk.CTkOptionMenu(
            self.sub_condition_params_frame,
            variable=self.detail_optionmenu_vars["subcond_condition_type_var"],
            values=CONDITION_TYPES,
            command=lambda choice: self._on_rule_part_type_change("condition", choice) # This will now correctly identify it's for a sub-condition
        )
        sub_cond_type_menu.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        
        self._render_condition_parameters(sub_cond_data, self.sub_condition_params_frame, start_row=1, is_sub_condition=True)
        logger.debug(f"Rendered parameters for selected sub-condition index {index}.")

    def _add_sub_condition_to_rule(self):
        if self.selected_rule_index is None:
            logger.warning("Cannot add sub-condition: No rule selected.")
            return
        
        rule_data = self.profile_data["rules"][self.selected_rule_index]
        condition_block = rule_data.get("condition", {})
        rule_name = rule_data.get("name", "UnknownRule")
        logger.info(f"Attempting to add sub-condition to rule '{rule_name}'.")

        if "logical_operator" not in condition_block:
            # Convert current single condition to a compound one
            logger.info(f"Rule '{rule_name}' is currently a single condition. Converting to compound (AND) to add sub-condition.")
            current_single_condition = copy.deepcopy(condition_block) # Get existing params
            if not current_single_condition.get("type"): # If it was empty or malformed
                current_single_condition = {"type": "always_true"}
            
            condition_block.clear() # Remove old single condition keys
            condition_block["logical_operator"] = "AND"
            condition_block["sub_conditions"] = [current_single_condition]
        
        new_sub_condition = {"type": "always_true"} # Default new sub-condition
        if "sub_conditions" not in condition_block: # Should exist now if converted
             condition_block["sub_conditions"] = []
        condition_block["sub_conditions"].append(new_sub_condition)
        
        rule_data["condition"] = condition_block # Ensure the modified block is set back
        self._set_dirty_status(True)
        self._update_details_panel(rule_data, "rule") # Refresh the rule details panel
        logger.info(f"Added new sub-condition to rule '{rule_name}'.")

    def _remove_selected_sub_condition(self):
        if self.selected_rule_index is None:
            logger.warning("Cannot remove sub-condition: No rule selected.")
            return
        if self.selected_sub_condition_index is None:
            logger.warning("Cannot remove sub-condition: No sub-condition selected.")
            return

        rule_data = self.profile_data["rules"][self.selected_rule_index]
        condition_block = rule_data.get("condition", {})
        sub_conditions_list = condition_block.get("sub_conditions")
        rule_name = rule_data.get("name", "UnknownRule")

        if sub_conditions_list and isinstance(sub_conditions_list, list) and \
           0 <= self.selected_sub_condition_index < len(sub_conditions_list):
            
            removed_sub_cond = sub_conditions_list.pop(self.selected_sub_condition_index)
            logger.info(f"Removed sub-condition at index {self.selected_sub_condition_index} from rule '{rule_name}': {removed_sub_cond}")
            
            self._set_dirty_status(True)
            self._update_details_panel(rule_data, "rule") # Refresh rule details panel
            
            # Reset sub-condition selection state
            self.selected_sub_condition_index = None
            if hasattr(self, 'btn_remove_sub_condition') and self.btn_remove_sub_condition:
                self.btn_remove_sub_condition.configure(state="disabled")
            self._highlight_selected_list_item("condition", None, is_sub_list=True) # Clear sub-condition highlight
        else:
            logger.warning(f"Problem removing sub-condition from rule '{rule_name}' at index {self.selected_sub_condition_index}. List: {sub_conditions_list}")

    def _convert_condition_structure(self):
        if self.selected_rule_index is None:
            logger.warning("Convert Condition Structure: No rule selected.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        condition_data = rule.get("condition", {})
        rule_name = rule.get("name", "UnknownRule")
        logger.info(f"Attempting to convert condition structure for rule '{rule_name}'. Current structure: {'Compound' if 'logical_operator' in condition_data else 'Single'}")

        is_currently_compound = "logical_operator" in condition_data and isinstance(condition_data.get("sub_conditions"), list)

        if is_currently_compound:
            # Convert Compound to Single
            sub_conditions = condition_data.get("sub_conditions", [])
            if len(sub_conditions) > 1:
                if not messagebox.askyesno("Confirm Conversion", "Convert compound condition to a single condition?\nOnly the first sub-condition will be kept. All other sub-conditions will be lost. Continue?"):
                    logger.info(f"Conversion from Compound to Single for rule '{rule_name}' cancelled by user.")
                    return
            
            new_single_condition = copy.deepcopy(sub_conditions[0]) if sub_conditions else {"type": "always_true"}
            logger.info(f"Converting Compound to Single for rule '{rule_name}'. Using first sub-condition (or default): {new_single_condition}")
            rule["condition"] = new_single_condition
        else:
            # Convert Single to Compound
            current_single_condition = copy.deepcopy(condition_data)
            if not current_single_condition.get("type"): # Ensure it's a valid basic condition
                current_single_condition = {"type": "always_true"}
            
            rule["condition"] = {
                "logical_operator": "AND", # Default to AND
                "sub_conditions": [current_single_condition]
            }
            logger.info(f"Converting Single to Compound for rule '{rule_name}'. Wrapped existing condition: {current_single_condition}")
        
        self._set_dirty_status(True)
        self._update_details_panel(rule, "rule") # Refresh the rule details panel to show new structure
        logger.info(f"Condition structure for rule '{rule_name}' converted successfully.")


    def _show_about_dialog(self):
        # Placeholder for an About dialog
        messagebox.showinfo("About PyPixelBot Editor", "PyPixelBot Profile Editor\nVersion: v3.0.0 (In Development)\n\nDeveloped by DevLead & AI Collaborator.")

    def _update_status_bar(self, message: str, duration_ms: int = 0):
        if hasattr(self, 'status_bar_label') and self.status_bar_label:
            self.status_bar_label.configure(text=message)
            if duration_ms > 0:
                self.after(duration_ms, lambda: self.status_bar_label.configure(text="Ready." if not self._is_dirty else "Unsaved changes."))
        else:
            logger.debug(f"Status bar update: {message} (status_bar_label not found)")


if __name__ == "__main__":
    # This allows running the MainAppWindow directly for testing,
    # but it's better to run via __main__.py as 'python -m py_pixel_bot edit'
    # which sets up logging and handles CLI args properly.
    
    # Basic logging setup for direct run
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Running MainAppWindow directly for testing...")

    # Ensure the appearance mode is set (CustomTkinter requirement)
    ctk.set_appearance_mode("System") 
    ctk.set_default_color_theme("blue")

    # Create a dummy ConfigManager if needed for basic functionality
    # This might be needed if ConfigManager relies on paths derived from a profile.
    class DummyConfigManager:
        def __init__(self, profile_path=None, create_if_missing=True):
            self.profile_path = profile_path
            self.profile_data = DEFAULT_PROFILE_STRUCTURE if create_if_missing else {}
            if profile_path and os.path.exists(profile_path) and not create_if_missing :
                try:
                    with open(profile_path, 'r') as f: self.profile_data = json.load(f)
                except Exception: pass # Ignore load errors for dummy
        def get_profile_data(self): return self.profile_data
        def get_profile_path(self): return self.profile_path
        @staticmethod
        def save_profile_data_to_path(path, data): print(f"DummyCM: Save to {path}"); return True
        def save_profile(self): print(f"DummyCM: Save self to {self.profile_path}"); return True
        def get_templates_subdir(self): return os.path.join(os.path.dirname(self.profile_path) if self.profile_path else ".", "templates")
        def ensure_templates_subdir_exists(self): pass


    # Monkey-patch ConfigManager if the real one fails to import during direct test
    if 'ConfigManager' not in globals() or globals()['ConfigManager'] is None:
        print("WARNING: Real ConfigManager not imported, using DummyConfigManager for direct test run.")
        ConfigManager = DummyConfigManager

    app = MainAppWindow()
    app.mainloop()