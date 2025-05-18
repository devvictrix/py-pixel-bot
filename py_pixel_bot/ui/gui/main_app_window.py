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

# Standardized Absolute Imports
from py_pixel_bot.core.config_manager import ConfigManager
from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow
from py_pixel_bot.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE, CONDITION_TYPES, ACTION_TYPES, UI_PARAM_CONFIG, OPTIONS_CONST_MAP
from py_pixel_bot.ui.gui.gui_utils import validate_and_get_widget_value, parse_bgr_string, create_clickable_list_item
from py_pixel_bot.ui.gui.panels.details_panel import DetailsPanel


logger = logging.getLogger(__name__)


class MainAppWindow(ctk.CTk):
    def __init__(self, initial_profile_path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing MainAppWindow...")
        self.title("PyPixelBot Profile Editor")
        self.geometry("1350x800") # Increased width slightly for Gemini settings

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.current_profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self._is_dirty: bool = False

        self.selected_region_index: Optional[int] = None
        self.selected_template_index: Optional[int] = None
        self.selected_rule_index: Optional[int] = None
        self.selected_sub_condition_index: Optional[int] = None

        self.selected_region_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_template_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_rule_item_widget: Optional[ctk.CTkFrame] = None

        self.details_panel_instance: Optional[DetailsPanel] = None

        # UI elements for settings that need to be class members
        self.entry_profile_desc: Optional[ctk.CTkEntry] = None
        self.entry_monitor_interval: Optional[ctk.CTkEntry] = None
        self.entry_dominant_k: Optional[ctk.CTkEntry] = None
        self.entry_gemini_default_model: Optional[ctk.CTkEntry] = None # For v4.0.0
        self.label_gemini_api_key_status: Optional[ctk.CTkLabel] = None # For v4.0.0
        self.label_current_profile_path: Optional[ctk.CTkLabel] = None


        self._setup_ui()

        if initial_profile_path:
            self._load_profile_from_path(initial_profile_path)
        else:
            self._new_profile(prompt_save=False)

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        logger.info("MainAppWindow initialization complete.")

    def _check_gemini_api_key_status(self) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key and len(api_key) > 10: # Basic check for presence and some length
            # Mask most of the key if displaying anything about it
            # For status, just "Loaded" or "Not Found" is safer.
            return "Loaded from .env"
        return "Not Found in .env"

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
        self.bind_all("<Control-S>", lambda e: self._save_profile_as()) # Uppercase S for Shift+S

        self.grid_columnconfigure(0, weight=1, minsize=320) # Adjusted minsize for Gemini settings
        self.grid_columnconfigure(1, weight=2, minsize=350)
        self.grid_columnconfigure(2, weight=2, minsize=400)
        self.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(self, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=0)
        self._setup_left_panel_content()

        self.center_panel = ctk.CTkFrame(self, corner_radius=0)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 2), pady=0)
        self._setup_center_panel_content()

        self.details_panel_instance = DetailsPanel(self, parent_app=self)
        self.details_panel_instance.grid(row=0, column=2, sticky="nsew", padx=(0, 0), pady=0)

    def _setup_left_panel_content(self):
        self.left_panel.grid_columnconfigure(0, weight=1)
        current_row = 0

        # --- Profile Info Frame ---
        pif = ctk.CTkFrame(self.left_panel)
        pif.grid(row=current_row, column=0, sticky="new", padx=10, pady=10)
        pif.grid_columnconfigure(1, weight=1)
        current_row += 1

        # Profile Description
        ctk.CTkLabel(pif, text="Desc:").grid(row=0, column=0, padx=5, pady=(5,2), sticky="w")
        self.entry_profile_desc = ctk.CTkEntry(pif, placeholder_text="Profile description")
        self.entry_profile_desc.grid(row=0, column=1, padx=5, pady=(5,2), sticky="ew")
        self.entry_profile_desc.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))

        # Monitoring Interval
        ctk.CTkLabel(pif, text="Interval(s):").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.entry_monitor_interval = ctk.CTkEntry(pif, placeholder_text="1.0")
        self.entry_monitor_interval.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.entry_monitor_interval.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))

        # Dominant K
        ctk.CTkLabel(pif, text="Dominant K:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.entry_dominant_k = ctk.CTkEntry(pif, placeholder_text="3")
        self.entry_dominant_k.grid(row=2, column=1, padx=5, pady=2, sticky="ew")
        self.entry_dominant_k.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))

        # Gemini Default Model (v4.0.0)
        ctk.CTkLabel(pif, text="Gemini Model:").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.entry_gemini_default_model = ctk.CTkEntry(pif, placeholder_text="gemini-1.5-flash-latest")
        self.entry_gemini_default_model.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.entry_gemini_default_model.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))

        # Gemini API Key Status (v4.0.0)
        ctk.CTkLabel(pif, text="Gemini Key:").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.label_gemini_api_key_status = ctk.CTkLabel(pif, text=self._check_gemini_api_key_status(), anchor="w")
        self.label_gemini_api_key_status.grid(row=4, column=1, padx=5, pady=2, sticky="ew")


        # Current Profile Path
        self.label_current_profile_path = ctk.CTkLabel(pif, text="Path: None", anchor="w", wraplength=300) # Increased wraplength
        self.label_current_profile_path.grid(row=5, column=0, columnspan=2, padx=5, pady=(5, 0), sticky="ew")


        # --- Regions Frame ---
        rsf = ctk.CTkFrame(self.left_panel)
        rsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5, 5))
        rsf.grid_columnconfigure(0, weight=1)
        rsf.grid_rowconfigure(1, weight=1) # Scrollable frame should expand
        current_row += 1
        ctk.CTkLabel(rsf, text="Regions", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0, 5), sticky="w")
        self.regions_list_scroll_frame = ctk.CTkScrollableFrame(rsf, label_text="") # Removed label for cleaner look
        self.regions_list_scroll_frame.grid(row=1, column=0, sticky="nsew")
        rbf = ctk.CTkFrame(rsf, fg_color="transparent")
        rbf.grid(row=2, column=0, pady=(5, 0), sticky="ew")
        ctk.CTkButton(rbf, text="Add", width=60, command=self._add_region).pack(side="left", padx=2)
        self.btn_remove_region = ctk.CTkButton(rbf, text="Remove", width=70, command=self._remove_selected_region, state="disabled")
        self.btn_remove_region.pack(side="left", padx=2)

        # --- Templates Frame ---
        tsf = ctk.CTkFrame(self.left_panel)
        tsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5, 10))
        tsf.grid_columnconfigure(0, weight=1)
        tsf.grid_rowconfigure(1, weight=1) # Scrollable frame should expand
        # current_row += 1 # No need to increment, this is the last section in left_panel
        ctk.CTkLabel(tsf, text="Templates", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0, 5), sticky="w")
        self.templates_list_scroll_frame = ctk.CTkScrollableFrame(tsf, label_text="") # Removed label
        self.templates_list_scroll_frame.grid(row=1, column=0, sticky="nsew")
        tbf = ctk.CTkFrame(tsf, fg_color="transparent")
        tbf.grid(row=2, column=0, pady=(5, 0), sticky="ew")
        ctk.CTkButton(tbf, text="Add", width=60, command=self._add_template).pack(side="left", padx=2)
        self.btn_remove_template = ctk.CTkButton(tbf, text="Remove", width=70, command=self._remove_selected_template, state="disabled")
        self.btn_remove_template.pack(side="left", padx=2)

        self.left_panel.grid_rowconfigure(current_row -1, weight=1)  # Regions list frame (current_row is now 2)
        self.left_panel.grid_rowconfigure(current_row, weight=1)  # Templates list frame (current_row is now 2)

    def _setup_center_panel_content(self):
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.center_panel, text="Rules", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.rules_list_scroll_frame = ctk.CTkScrollableFrame(self.center_panel, label_text="")
        self.rules_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        rbf2 = ctk.CTkFrame(self.center_panel, fg_color="transparent")
        rbf2.grid(row=2, column=0, pady=10, padx=10, sticky="ew")
        ctk.CTkButton(rbf2, text="Add New Rule", command=self._add_new_rule).pack(side="left", padx=5)
        self.btn_remove_rule = ctk.CTkButton(rbf2, text="Remove Selected Rule", command=self._remove_selected_rule, state="disabled")
        self.btn_remove_rule.pack(side="left", padx=5)

    def _new_profile(self, event=None, prompt_save=True):
        if prompt_save and not self._prompt_save_if_dirty():
            return
        self.current_profile_path = None
        self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self._populate_ui_from_profile_data()
        self._set_dirty_status(False)
        if self.label_current_profile_path:
            self.label_current_profile_path.configure(text="Path: New Profile (unsaved)")

    def _open_profile(self, event=None):
        if not self._prompt_save_if_dirty():
            return
        fp = filedialog.askopenfilename(title="Open Profile", defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if fp:
            self._load_profile_from_path(fp)

    def _load_profile_from_path(self, fp: str):
        try:
            cm = ConfigManager(fp)
            loaded_data = cm.get_profile_data()
            if not loaded_data:
                raise ValueError("Loaded profile data is empty or invalid.")
            
            # Ensure all top-level keys and 'settings' sub-keys from DEFAULT_PROFILE_STRUCTURE exist
            self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE) # Start with default
            self.profile_data.update(copy.deepcopy(loaded_data)) # Update with loaded
            
            # Specifically ensure settings sub-keys exist
            default_settings = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE["settings"])
            loaded_settings = copy.deepcopy(loaded_data.get("settings", {}))
            default_settings.update(loaded_settings) # loaded overrides default
            self.profile_data["settings"] = default_settings

            self.current_profile_path = cm.get_profile_path()
            self._populate_ui_from_profile_data()
            self._set_dirty_status(False)
            if self.label_current_profile_path:
                self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path if self.current_profile_path else 'Error resolving path'}")
            logger.info(f"Profile '{fp}' loaded and UI populated.")
        except Exception as e:
            logger.error(f"Failed to load profile '{fp}': {e}", exc_info=True)
            messagebox.showerror("Load Error", f"Could not load profile: {fp}\nError: {e}")
            self._new_profile(prompt_save=False) # Fallback to a new profile state on load error

    def _save_profile(self, event=None) -> bool:
        if not self.current_profile_path:
            return self._save_profile_as()

        if not self._update_profile_data_from_ui():
            logger.warning("Save profile aborted due to invalid basic settings.")
            return False

        try:
            ConfigManager.save_profile_data_to_path(self.current_profile_path, self.profile_data)
            self._set_dirty_status(False)
            logger.info(f"Profile saved to: {self.current_profile_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save to '{self.current_profile_path}': {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Could not save profile.\nError: {e}")
            return False

    def _save_profile_as(self, event=None) -> bool:
        if not self._update_profile_data_from_ui():
            logger.warning("Save profile as aborted due to invalid basic settings.")
            return False

        initial_fn = os.path.basename(self.current_profile_path) if self.current_profile_path else "new_profile.json"
        fp = filedialog.asksaveasfilename(title="Save Profile As", defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], initialfile=initial_fn)
        if fp:
            self.current_profile_path = fp
            if self.label_current_profile_path:
                self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
            return self._save_profile()
        return False

    def _populate_ui_from_profile_data(self):
        logger.debug("Populating UI from profile_data...")
        # Ensure all UI elements exist before trying to configure them
        if not all([self.entry_profile_desc, self.entry_monitor_interval, self.entry_dominant_k,
                    self.entry_gemini_default_model, self.label_gemini_api_key_status,
                    self.regions_list_scroll_frame, self.templates_list_scroll_frame,
                    self.rules_list_scroll_frame]):
            logger.error("One or more core UI elements for settings not initialized. Cannot populate UI.")
            return

        self.entry_profile_desc.delete(0, tk.END)
        self.entry_profile_desc.insert(0, self.profile_data.get("profile_description", ""))

        settings = self.profile_data.get("settings", {})
        self.entry_monitor_interval.delete(0, tk.END)
        self.entry_monitor_interval.insert(0, str(settings.get("monitoring_interval_seconds", 1.0)))
        self.entry_dominant_k.delete(0, tk.END)
        self.entry_dominant_k.insert(0, str(settings.get("analysis_dominant_colors_k", 3)))
        
        # Populate Gemini settings (v4.0.0)
        self.entry_gemini_default_model.delete(0, tk.END)
        self.entry_gemini_default_model.insert(0, str(settings.get("gemini_default_model_name", "gemini-1.5-flash-latest")))
        self.label_gemini_api_key_status.configure(text=self._check_gemini_api_key_status())


        self.selected_region_index = None
        self.selected_template_index = None
        self.selected_rule_index = None
        self.selected_sub_condition_index = None

        self._populate_specific_list_frame(
            "region", self.regions_list_scroll_frame, self.profile_data.get("regions", []), lambda item_data, idx: item_data.get("name", f"UnnamedRegion_{idx+1}"), self.btn_remove_region, "region"
        )
        self._populate_specific_list_frame(
            "template",
            self.templates_list_scroll_frame,
            self.profile_data.get("templates", []),
            lambda item_data, idx: f"{item_data.get('name', f'UnnamedTemplate_{idx+1}')} ({item_data.get('filename', 'N/A')})",
            self.btn_remove_template,
            "template",
        )
        self._populate_specific_list_frame(
            "rule", self.rules_list_scroll_frame, self.profile_data.get("rules", []), lambda item_data, idx: item_data.get("name", f"UnnamedRule_{idx+1}"), self.btn_remove_rule, "rule"
        )

        if self.details_panel_instance:
            self.details_panel_instance.update_display(None, "none")

        logger.debug("UI population from profile_data complete.")

    def _populate_specific_list_frame(
        self, list_key_prefix: str, frame_widget: ctk.CTkScrollableFrame, items_data: List[Dict], display_text_cb: Callable, remove_button: Optional[ctk.CTkButton], item_type_str: str
    ):
        for widget in frame_widget.winfo_children():
            widget.destroy()

        setattr(self, f"selected_{list_key_prefix}_item_widget", None)

        if remove_button:
            remove_button.configure(state="disabled")

        for i, item_d in enumerate(items_data):
            text = display_text_cb(item_d, i)
            item_frame_container = {}
            item_f = create_clickable_list_item(
                frame_widget,
                text,
                lambda e=None, item_type=item_type_str, data=item_d, index=i, frame_cont=item_frame_container: self._on_item_selected(item_type, data, index, frame_cont.get("frame")),
            )
            item_frame_container["frame"] = item_f

    def _update_profile_data_from_ui(self) -> bool:
        logger.debug("Updating profile_data from basic UI settings...")
        if not self.entry_profile_desc: # Check if UI elements are initialized
             logger.error("Cannot update profile data from UI: Settings panel UI elements not fully initialized.")
             return False # Cannot proceed if UI elements don't exist

        desc_val, desc_valid = validate_and_get_widget_value(
            self.entry_profile_desc, None, "Profile Description", str, self.profile_data.get("profile_description", ""), required=False, allow_empty_string=True
        )
        if desc_valid: # Even if not required, if valid, update.
            self.profile_data["profile_description"] = desc_val

        settings = self.profile_data.get("settings", {})
        all_settings_valid = True

        interval_val, interval_valid = validate_and_get_widget_value(
            self.entry_monitor_interval, None, "Monitoring Interval", float, settings.get("monitoring_interval_seconds", 1.0), required=True, min_val=0.01
        )
        if interval_valid:
            settings["monitoring_interval_seconds"] = interval_val
        else:
            all_settings_valid = False

        k_val, k_valid = validate_and_get_widget_value(self.entry_dominant_k, None, "Dominant K", int, settings.get("analysis_dominant_colors_k", 3), required=True, min_val=1, max_val=20)
        if k_valid:
            settings["analysis_dominant_colors_k"] = k_val
        else:
            all_settings_valid = False
            
        # Gemini settings (v4.0.0)
        gemini_model_val, gemini_model_valid = validate_and_get_widget_value(
            self.entry_gemini_default_model, None, "Gemini Default Model", str, settings.get("gemini_default_model_name", "gemini-1.5-flash-latest"), required=False, allow_empty_string=True
        )
        if gemini_model_valid:
            # If empty, store None or a default. For now, store as is (empty string or value).
            # ADR-008 specifies model_name as Optional[str], so empty implies fallback in GeminiAnalyzer.
            settings["gemini_default_model_name"] = gemini_model_val if gemini_model_val else "gemini-1.5-flash-latest" # Fallback if empty
        # No else all_settings_valid = False, as it's not strictly required.

        self.profile_data["settings"] = settings
        if not all_settings_valid:
            logger.warning("One or more basic settings are invalid. Profile data may not be fully updated from UI.")
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
        logger.debug(f"Dirty status set to {is_d}. Window title: '{title}'")

    def _prompt_save_if_dirty(self) -> bool:
        if not self._is_dirty:
            return True
        resp = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes. Save before proceeding?")
        if resp is True:
            return self._save_profile()
        elif resp is False:
            return True
        else:
            return False

    def _on_close_window(self, event=None):
        if self._prompt_save_if_dirty():
            logger.info("Exiting MainAppWindow.")
            self.destroy()

    def _on_item_selected(self, list_name: str, item_data: Dict, item_index: int, item_widget_frame: Optional[ctk.CTkFrame]):
        if not item_widget_frame:
            logger.warning(f"Item selection called for {list_name} but item_widget_frame is None. Aborting selection update.")
            return

        logger.info(f"Item selected: {list_name}, index {item_index}, name '{item_data.get('name')}'")

        lists_to_clear_state = {
            "region": (self.btn_remove_region, "selected_region_index", "selected_region_item_widget"),
            "template": (self.btn_remove_template, "selected_template_index", "selected_template_item_widget"),
            "rule": (self.btn_remove_rule, "selected_rule_index", "selected_rule_item_widget"),
        }

        for ln, (btn, idx_attr, widget_attr) in lists_to_clear_state.items():
            if ln != list_name:
                self._highlight_selected_list_item(ln, None)
                setattr(self, idx_attr, None)
                if btn and hasattr(btn, 'configure'): # Ensure button exists and is a widget
                    btn.configure(state="disabled")

        if list_name == "rule" and self.details_panel_instance:
            self.selected_sub_condition_index = None
            self._highlight_selected_list_item("condition", None, is_sub_list=True)
            if self.details_panel_instance.btn_remove_sub_condition and hasattr(self.details_panel_instance.btn_remove_sub_condition, 'configure'):
                self.details_panel_instance.btn_remove_sub_condition.configure(state="disabled")

        setattr(self, lists_to_clear_state[list_name][1], item_index)
        self._highlight_selected_list_item(list_name, item_widget_frame)

        current_btn = lists_to_clear_state[list_name][0]
        if current_btn and hasattr(current_btn, 'configure'):
            current_btn.configure(state="normal")

        if self.details_panel_instance:
            self.details_panel_instance.update_display(copy.deepcopy(item_data), list_name)

    def _highlight_selected_list_item(self, list_name_for_attr: str, new_selected_widget: Optional[ctk.CTkFrame], is_sub_list: bool = False):
        attr_name_prefix = "selected_sub_" if is_sub_list else "selected_"
        attr_name_widget = f"{attr_name_prefix}{list_name_for_attr}_item_widget"
        attr_target_object = self.details_panel_instance if is_sub_list and self.details_panel_instance else self

        old_selected_widget = getattr(attr_target_object, attr_name_widget, None)
        if old_selected_widget and isinstance(old_selected_widget, ctk.CTkFrame) and old_selected_widget.winfo_exists(): # Check type and existence
            old_selected_widget.configure(fg_color="transparent")

        if new_selected_widget and isinstance(new_selected_widget, ctk.CTkFrame) and new_selected_widget.winfo_exists(): # Check type and existence
            # Try to get theme color, fallback if not found
            try:
                highlight_color = ctk.ThemeManager.theme["CTkSegmentedButton"]["selected_color"]
            except (KeyError, AttributeError): # ThemeManager might not be initialized or theme structure different
                highlight_color = ("#3a7ebf", "#1f538d") # Default blueish highlight

            new_selected_widget.configure(fg_color=highlight_color)
            setattr(attr_target_object, attr_name_widget, new_selected_widget)
        else:
            setattr(attr_target_object, attr_name_widget, None)

    def _apply_region_changes(self):
        if self.selected_region_index is None or self.details_panel_instance is None:
            logger.warning("Apply region changes called but no region selected or details panel missing.")
            return
        if not (0 <= self.selected_region_index < len(self.profile_data.get("regions", []))):
            logger.error(f"Selected region index {self.selected_region_index} is out of bounds for regions list.")
            return

        current_region_data = self.profile_data["regions"][self.selected_region_index]
        original_name = current_region_data.get("name")
        logger.info(f"Applying changes for region: {original_name} (index {self.selected_region_index})")

        all_valid = True
        new_values = {}

        name_widget = self.details_panel_instance.detail_widgets.get("name")
        name_val, valid = validate_and_get_widget_value(name_widget, None, "Region Name", str, original_name, required=True)
        if not valid:
            all_valid = False
        else:
            new_values["name"] = name_val

        for p in ["x", "y", "width", "height"]:
            coord_widget = self.details_panel_instance.detail_widgets.get(p)
            min_v = 1 if p in ["width", "height"] else None # Width/height > 0
            default_coord_val = current_region_data.get(p, 0 if p in ["x", "y"] else 1)
            val, valid = validate_and_get_widget_value(coord_widget, None, p.capitalize(), int, default_coord_val, required=True, min_val=min_v)
            if not valid:
                all_valid = False
            else:
                new_values[p] = val

        if not all_valid:
            logger.error(f"Apply changes for region '{original_name}' aborted due to validation errors.")
            return

        if new_values["name"] != original_name and any(r.get("name") == new_values["name"] for i, r in enumerate(self.profile_data["regions"]) if i != self.selected_region_index):
            messagebox.showerror("Name Error", f"Region name '{new_values['name']}' already exists.")
            return

        current_region_data.update(new_values)
        self._set_dirty_status(True)
        self._populate_specific_list_frame(
            "region", self.regions_list_scroll_frame, self.profile_data["regions"], lambda item_data, idx: item_data.get("name", f"R{idx+1}"), self.btn_remove_region, "region"
        )
        if self.selected_region_index < len(self.profile_data["regions"]): # Check bounds again after potential list modification elsewhere (unlikely here)
            children = self.regions_list_scroll_frame.winfo_children()
            new_item_widget = children[self.selected_region_index] if children and self.selected_region_index < len(children) else None
            self._highlight_selected_list_item("region", new_item_widget)
            if self.details_panel_instance:
                self.details_panel_instance.update_display(copy.deepcopy(current_region_data), "region")

        messagebox.showinfo("Region Updated", f"Region '{new_values['name']}' updated successfully.")

    def _apply_template_changes(self):
        if self.selected_template_index is None or self.details_panel_instance is None:
            logger.warning("Apply template changes called but no template selected or details panel missing.")
            return
        if not (0 <= self.selected_template_index < len(self.profile_data.get("templates", []))):
            logger.error(f"Selected template index {self.selected_template_index} is out of bounds for templates list.")
            return

        current_template_data = self.profile_data["templates"][self.selected_template_index]
        original_name = current_template_data.get("name")
        logger.info(f"Applying changes for template: {original_name} (index {self.selected_template_index})")

        name_widget = self.details_panel_instance.detail_widgets.get("template_name")
        name_val, name_valid = validate_and_get_widget_value(name_widget, None, "Template Name", str, original_name, required=True)

        if not name_valid:
            return

        if name_val != original_name and any(t.get("name") == name_val for i, t in enumerate(self.profile_data["templates"]) if i != self.selected_template_index):
            messagebox.showerror("Name Error", f"Template name '{name_val}' already exists.")
            return

        current_template_data["name"] = name_val
        self._set_dirty_status(True)
        self._populate_specific_list_frame(
            "template",
            self.templates_list_scroll_frame,
            self.profile_data["templates"],
            lambda item_data, idx: f"{item_data.get('name')} ({item_data.get('filename')})",
            self.btn_remove_template,
            "template",
        )
        if self.selected_template_index < len(self.profile_data["templates"]):
            children = self.templates_list_scroll_frame.winfo_children()
            new_item_widget = children[self.selected_template_index] if children and self.selected_template_index < len(children) else None
            self._highlight_selected_list_item("template", new_item_widget)
            if self.details_panel_instance:
                self.details_panel_instance.update_display(copy.deepcopy(current_template_data), "template")
        messagebox.showinfo("Template Updated", f"Template '{name_val}' updated successfully.")

    def _apply_rule_changes(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning("Apply rule changes called but no rule selected or details panel missing.")
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules", []))):
            logger.error(f"Selected rule index {self.selected_rule_index} is out of bounds for rules list.")
            return

        current_rule_data_orig = self.profile_data["rules"][self.selected_rule_index]
        old_name = current_rule_data_orig.get("name")
        logger.info(f"Attempting to apply changes for rule: '{old_name}' (index {self.selected_rule_index})")

        temp_rule_data_for_validation = copy.deepcopy(current_rule_data_orig) # Work on a copy

        name_widget = self.details_panel_instance.detail_widgets.get("rule_name")
        new_name, name_valid = validate_and_get_widget_value(name_widget, None, "Rule Name", str, old_name, required=True)
        if not name_valid: return
        if new_name != old_name and any(r.get("name") == new_name for i, r in enumerate(self.profile_data["rules"]) if i != self.selected_rule_index):
            messagebox.showerror("Name Error", f"Rule name '{new_name}' already exists.")
            return
        temp_rule_data_for_validation["name"] = new_name

        rule_region_var = self.details_panel_instance.detail_optionmenu_vars.get("rule_region_var")
        temp_rule_data_for_validation["region"] = rule_region_var.get() if rule_region_var else current_rule_data_orig.get("region", "")


        condition_block_ui = {}
        is_compound_in_ui = "logical_operator_var" in self.details_panel_instance.detail_optionmenu_vars

        if is_compound_in_ui:
            log_op_var = self.details_panel_instance.detail_optionmenu_vars.get("logical_operator_var")
            condition_block_ui["logical_operator"] = log_op_var.get() if log_op_var else "AND"
            
            # Important: If a sub-condition is currently selected for editing in DetailsPanel,
            # its parameters must be fetched from the UI. Others are taken from current profile_data.
            new_sub_conds_from_data_and_ui = []
            existing_sub_conds_in_profile = temp_rule_data_for_validation.get("condition", {}).get("sub_conditions", [])
            all_subs_valid = True

            for idx, sub_cond_data_from_profile in enumerate(existing_sub_conds_in_profile):
                if self.selected_sub_condition_index == idx: # This is the one being edited
                    sub_c_type_var = self.details_panel_instance.detail_optionmenu_vars.get("subcond_condition_type_var")
                    if sub_c_type_var:
                        sub_c_type = sub_c_type_var.get()
                        sub_params_from_ui = self.details_panel_instance._get_parameters_from_ui("conditions", sub_c_type, "subcond_")
                        if sub_params_from_ui is None: # Validation failed
                            all_subs_valid = False; break
                        new_sub_conds_from_data_and_ui.append(sub_params_from_ui)
                    else: # Should not happen if UI is consistent
                        all_subs_valid = False; break
                else: # Not being edited, take from current (potentially already modified) profile data copy
                    new_sub_conds_from_data_and_ui.append(copy.deepcopy(sub_cond_data_from_profile))
            
            if not all_subs_valid:
                logger.error("Rule apply aborted: Sub-condition validation failed for the sub-condition being edited.")
                return
            condition_block_ui["sub_conditions"] = new_sub_conds_from_data_and_ui
        else: # Single condition
            cond_type_var = self.details_panel_instance.detail_optionmenu_vars.get("condition_type_var")
            single_cond_type = cond_type_var.get() if cond_type_var else "always_true"
            single_cond_params_from_ui = self.details_panel_instance._get_parameters_from_ui("conditions", single_cond_type, "cond_")
            if single_cond_params_from_ui is None: # Validation failed
                logger.error("Rule apply aborted: Single condition validation failed.")
                return
            condition_block_ui = single_cond_params_from_ui
        
        temp_rule_data_for_validation["condition"] = condition_block_ui

        action_type_var = self.details_panel_instance.detail_optionmenu_vars.get("action_type_var")
        action_type = action_type_var.get() if action_type_var else "log_message"
        action_params_from_ui = self.details_panel_instance._get_parameters_from_ui("actions", action_type, "act_")
        if action_params_from_ui is None: # Validation failed
            logger.error("Rule apply aborted: Action validation failed.")
            return
        temp_rule_data_for_validation["action"] = action_params_from_ui

        # All validations passed, commit to self.profile_data
        self.profile_data["rules"][self.selected_rule_index] = temp_rule_data_for_validation
        self._set_dirty_status(True)

        self._populate_specific_list_frame(
            "rule", self.rules_list_scroll_frame, self.profile_data["rules"], lambda item_data, idx: item_data.get("name", f"Rule{idx+1}"), self.btn_remove_rule, "rule"
        )
        if self.selected_rule_index < len(self.profile_data["rules"]):
            children = self.rules_list_scroll_frame.winfo_children()
            new_item_widget = children[self.selected_rule_index] if children and self.selected_rule_index < len(children) else None
            self._highlight_selected_list_item("rule", new_item_widget)
            if self.details_panel_instance: # Update details panel with the (potentially modified) rule data
                self.details_panel_instance.update_display(copy.deepcopy(temp_rule_data_for_validation), "rule")
        messagebox.showinfo("Rule Updated", f"Rule '{new_name}' updated successfully.")

    def _edit_region_coordinates_with_selector(self):
        if self.selected_region_index is None:
            logger.warning("Edit region coords called but no region selected.")
            return
        if not (0 <= self.selected_region_index < len(self.profile_data.get("regions",[]))):
            logger.error(f"Cannot edit region coordinates: selected index {self.selected_region_index} out of bounds.")
            return

        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Current profile has unsaved changes. Save before launching Region Selector?"):
                return
            if not self._save_profile():
                logger.warning("Save failed. Aborting region coordinate editing.")
                return

        if not self.current_profile_path:
            messagebox.showerror("Error", "Profile must be saved to a file before editing region coordinates with selector.")
            return

        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data: # Should not happen if save succeeded
                messagebox.showerror("Error", "Failed to re-load profile for Region Selector.")
                return
            region_to_edit_data = copy.deepcopy(self.profile_data["regions"][self.selected_region_index])
            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector, existing_region_data=region_to_edit_data)
            # self.wait_window(selector_dialog) # CTkToplevel is modal by default with grab_set
            if selector_dialog.changes_made: # This flag should be set by RegionSelectorWindow upon successful save
                logger.info("RegionSelector made changes. Reloading profile into MainAppWindow.")
                self._load_profile_from_path(self.current_profile_path) # Reload to get changes from file
                # Re-select the edited region if possible
                if region_to_edit_data.get("name") in [r.get("name") for r in self.profile_data.get("regions",[])]:
                    for i, r_new in enumerate(self.profile_data.get("regions",[])):
                        if r_new.get("name") == region_to_edit_data.get("name"):
                            self.selected_region_index = i # Keep selection on the (potentially renamed or just re-coord'd) region
                            children = self.regions_list_scroll_frame.winfo_children()
                            new_item_widget = children[i] if children and i < len(children) else None
                            self._on_item_selected("region", r_new, i, new_item_widget)
                            break
                self._set_dirty_status(True) # Profile has changed
            else:
                logger.info("RegionSelector closed without making changes or save was cancelled.")
        except Exception as e:
            logger.error(f"Error during Edit Region Coordinates: {e}", exc_info=True)
            messagebox.showerror("Region Selector Error", f"Error launching or using Region Selector:\n{e}")

    def _add_region(self):
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "The profile must be saved to a file before adding regions. Save now?"):
                return
            if not self._save_profile_as():
                return

        if self._is_dirty: # If still dirty after potential save_as
            if not messagebox.askyesno("Save Changes?", "Current profile has unsaved changes. Save before launching Region Selector?"):
                return
            if not self._save_profile(): # Save to current path
                return

        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data:
                messagebox.showerror("Error", "Failed to re-load profile for Region Selector.")
                return
            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector)
            # self.wait_window(selector_dialog) # Modal by default
            if selector_dialog.changes_made:
                logger.info("RegionSelector added a region. Reloading profile into MainAppWindow.")
                self._load_profile_from_path(self.current_profile_path)
                self._set_dirty_status(True)
            else:
                logger.info("RegionSelector closed, no new region added or selection cancelled.")
        except Exception as e:
            logger.error(f"Error during Add Region: {e}", exc_info=True)
            messagebox.showerror("Add Region Error", f"Error launching or using Region Selector:\n{e}")

    def _remove_selected_item(self, list_name_key: str, profile_data_key: str, selected_index_attr: str, remove_button_widget: Optional[ctk.CTkButton]):
        selected_index = getattr(self, selected_index_attr, None)
        if selected_index is None or not self.profile_data or profile_data_key not in self.profile_data:
            logger.warning(f"Cannot remove {list_name_key}: No item selected or data missing.")
            return

        item_list: List[Dict] = self.profile_data[profile_data_key]
        if 0 <= selected_index < len(item_list):
            removed_item_data = item_list.pop(selected_index)
            logger.info(f"Removed {list_name_key} '{removed_item_data.get('name', 'N/A')}' at index {selected_index}.")

            list_scroll_frame = getattr(self, f"{list_name_key}s_list_scroll_frame", None) # e.g., self.regions_list_scroll_frame
            display_cb_map = {
                "region": lambda item, idx: item.get("name", f"R{idx+1}"),
                "template": lambda item, idx: f"{item.get('name', 'T_NoName')} ({item.get('filename', 'F_NoName')})",
                "rule": lambda item, idx: item.get("name", f"Rule{idx+1}"),
            }
            display_cb = display_cb_map.get(list_name_key)

            if list_scroll_frame and display_cb and remove_button_widget and hasattr(remove_button_widget, 'configure'):
                self._populate_specific_list_frame(list_name_key, list_scroll_frame, item_list, display_cb, remove_button_widget, list_name_key)

            self._set_dirty_status(True)
            setattr(self, selected_index_attr, None) # Clear selection index
            if remove_button_widget and hasattr(remove_button_widget, 'configure'):
                remove_button_widget.configure(state="disabled")
            if self.details_panel_instance: # Clear details panel
                self.details_panel_instance.update_display(None, "none")

            # Special handling for template file deletion
            if list_name_key == "template" and self.current_profile_path:
                filename_to_delete = removed_item_data.get("filename")
                if filename_to_delete:
                    profile_dir = os.path.dirname(self.current_profile_path)
                    template_file_path = os.path.join(profile_dir, "templates", filename_to_delete)
                    try:
                        if os.path.exists(template_file_path):
                            os.remove(template_file_path)
                            logger.info(f"Deleted template image file: {template_file_path}")
                        else:
                            logger.warning(f"Template image file not found for deletion: {template_file_path}")
                    except OSError as e_os:
                        logger.error(f"OS error deleting template file '{filename_to_delete}': {e_os.strerror}", exc_info=True)
                        messagebox.showwarning("File Deletion Error", f"Could not delete template image file '{filename_to_delete}':\n{e_os.strerror}")
        else:
            logger.warning(f"Cannot remove {list_name_key}: Invalid index {selected_index} for list of length {len(item_list)}.")

    def _remove_selected_region(self):
        self._remove_selected_item("region", "regions", "selected_region_index", self.btn_remove_region)

    def _remove_selected_template(self):
        self._remove_selected_item("template", "templates", "selected_template_index", self.btn_remove_template)

    def _remove_selected_rule(self):
        self._remove_selected_item("rule", "rules", "selected_rule_index", self.btn_remove_rule)

    def _add_template(self):
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "The profile must be saved to a file before adding templates. Save now?"):
                return
            if not self._save_profile_as():
                return

        if self._is_dirty: # After potential save_as
            if not messagebox.askyesno("Save Changes?", "Current profile has unsaved changes. Save before adding template?"):
                return
            if not self._save_profile():
                return

        img_path = filedialog.askopenfilename(title="Select Template Image", filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg;*.jpeg"), ("All files", "*.*")])
        if not img_path:
            return

        name_dialog = ctk.CTkInputDialog(text="Enter a unique name for this template:", title="Template Name")
        tpl_name_input = name_dialog.get_input()
        if not tpl_name_input or not tpl_name_input.strip():
            logger.info("Add template cancelled: No name entered.")
            return
        tpl_name = tpl_name_input.strip()

        if any(t.get("name") == tpl_name for t in self.profile_data.get("templates", [])):
            messagebox.showerror("Name Error", f"A template named '{tpl_name}' already exists.")
            return

        profile_dir = os.path.dirname(self.current_profile_path)
        templates_dir = os.path.join(profile_dir, "templates")
        try:
            os.makedirs(templates_dir, exist_ok=True)
            base_filename, ext = os.path.splitext(os.path.basename(img_path))
            sane_base_for_filename = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in tpl_name).rstrip().replace(" ", "_")
            if not sane_base_for_filename:
                sane_base_for_filename = "template" # Fallback if name results in empty

            target_filename = f"{sane_base_for_filename}{ext}"
            target_path = os.path.join(templates_dir, target_filename)
            counter = 1
            while os.path.exists(target_path): # Avoid overwriting
                target_filename = f"{sane_base_for_filename}_{counter}{ext}"
                target_path = os.path.join(templates_dir, target_filename)
                counter += 1

            shutil.copy2(img_path, target_path)
            logger.info(f"Copied template image from '{img_path}' to '{target_path}'.")

            new_tpl_data = {"name": tpl_name, "filename": target_filename}
            self.profile_data.setdefault("templates", []).append(new_tpl_data)
            self._populate_specific_list_frame(
                "template",
                self.templates_list_scroll_frame,
                self.profile_data["templates"],
                lambda item_data, idx: f"{item_data.get('name', 'T_NoName')} ({item_data.get('filename', 'F_NoName')})",
                self.btn_remove_template,
                "template",
            )
            self._set_dirty_status(True)
            messagebox.showinfo("Template Added", f"Template '{tpl_name}' (file: {target_filename}) added successfully.")
        except Exception as e:
            logger.error(f"Error adding template '{tpl_name}': {e}", exc_info=True)
            messagebox.showerror("Add Template Error", f"Could not add template '{tpl_name}':\n{e}")

    def _add_new_rule(self):
        if not self.profile_data: # Should not happen if constructor logic is sound
            self._new_profile(prompt_save=False) # Initialize if somehow empty

        name_dialog = ctk.CTkInputDialog(text="Enter a unique name for the new rule:", title="New Rule Name")
        rule_name_input = name_dialog.get_input()
        if not rule_name_input or not rule_name_input.strip():
            logger.info("Add new rule cancelled: No name entered.")
            return
        rule_name = rule_name_input.strip()

        if any(r.get("name") == rule_name for r in self.profile_data.get("rules", [])):
            messagebox.showerror("Name Error", f"A rule named '{rule_name}' already exists.")
            return

        new_rule_data = {
            "name": rule_name,
            "region": "", # Default to no specific region for the rule itself
            "condition": {"type": "always_true"}, # Default simple condition
            "action": {"type": "log_message", "message": f"Rule '{rule_name}' triggered.", "level": "INFO"}, # Default simple action
        }
        self.profile_data.setdefault("rules", []).append(new_rule_data)
        self._populate_specific_list_frame(
            "rule", self.rules_list_scroll_frame, self.profile_data["rules"], lambda item_data, idx: item_data.get("name", f"Rule{idx+1}"), self.btn_remove_rule, "rule"
        )
        self._set_dirty_status(True)
        messagebox.showinfo("Rule Added", f"Rule '{rule_name}' added successfully.")

    def _on_rule_part_type_change(self, part_changed: str, new_type_selected: str):
        self._set_dirty_status(True)
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning(f"Cannot handle rule part type change: No rule selected or details panel missing.")
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules",[]))):
            logger.error(f"Cannot handle rule part type change: selected rule index {self.selected_rule_index} out of bounds.")
            return

        current_rule_data = self.profile_data["rules"][self.selected_rule_index]
        logger.info(f"Rule part type change for rule '{current_rule_data.get('name')}': part '{part_changed}' to type '{new_type_selected}'")

        target_frame_for_params: Optional[ctk.CTkFrame] = None
        condition_or_action_data_in_profile: Optional[Dict] = None # The dict to modify in self.profile_data
        widget_prefix = ""

        if part_changed == "condition":
            is_compound = "logical_operator" in current_rule_data.get("condition", {})

            if self.selected_sub_condition_index is not None and is_compound:
                sub_cond_list = current_rule_data.get("condition", {}).get("sub_conditions", [])
                if 0 <= self.selected_sub_condition_index < len(sub_cond_list):
                    condition_or_action_data_in_profile = sub_cond_list[self.selected_sub_condition_index]
                    target_frame_for_params = self.details_panel_instance.sub_condition_params_frame
                    widget_prefix = "subcond_"
                else:
                    logger.error("Selected sub-condition index out of bounds for type change. Aborting.")
                    return
            elif not is_compound: # Single condition
                condition_or_action_data_in_profile = current_rule_data.get("condition", {})
                target_frame_for_params = self.details_panel_instance.condition_params_frame
                widget_prefix = "cond_"
            else: # Compound, but no sub-condition selected (e.g. changing rule default region) - should not get here for type change
                logger.error("Cannot determine which condition part to change type for (compound rule but no sub-condition selected).")
                return
            
            param_group = "conditions"

        elif part_changed == "action":
            condition_or_action_data_in_profile = current_rule_data.get("action", {})
            target_frame_for_params = self.details_panel_instance.action_params_frame
            widget_prefix = "act_"
            param_group = "actions"
        else:
            logger.error(f"Unknown rule part '{part_changed}' for type change.")
            return

        if target_frame_for_params and condition_or_action_data_in_profile is not None:
            # Reset the data for this part to only include the new type, preserving common fields if any (like region, capture_as for conditions)
            if condition_or_action_data_in_profile.get("type") != new_type_selected:
                preserved_data = {"type": new_type_selected}
                # For conditions, preserve 'region' and 'capture_as' if they exist and make sense for the new type
                if param_group == "conditions":
                    if "region" in condition_or_action_data_in_profile:
                        preserved_data["region"] = condition_or_action_data_in_profile["region"]
                    if "capture_as" in condition_or_action_data_in_profile: # Might not be relevant for all new types
                         # Check if new type typically supports capture_as
                        new_type_params = UI_PARAM_CONFIG.get(param_group, {}).get(new_type_selected, [])
                        if any(p.get("id") == "capture_as" for p in new_type_params):
                            preserved_data["capture_as"] = condition_or_action_data_in_profile["capture_as"]
                        
                condition_or_action_data_in_profile.clear()
                condition_or_action_data_in_profile.update(preserved_data)
                logger.debug(f"{param_group} part data (in profile_data model) reset for new type '{new_type_selected}': {condition_or_action_data_in_profile}")

            # Re-render the parameters for this part using the (potentially reset) data_source
            self.details_panel_instance._render_dynamic_parameters(
                param_group, new_type_selected, condition_or_action_data_in_profile, target_frame_for_params, start_row=1, widget_prefix=widget_prefix
            )
        else:
            logger.error(f"Could not find target frame or data source for {param_group} type change to '{new_type_selected}'.")
        
        logger.info(f"Rule part '{part_changed}' type in profile_data model updated to '{new_type_selected}'. DetailsPanel should reflect this.")


    def _add_sub_condition_to_rule(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning("Cannot add sub-condition: No rule selected or details panel missing.")
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules",[]))):
            logger.error(f"Cannot add sub-condition: selected rule index {self.selected_rule_index} out of bounds.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})

        if "logical_operator" not in cond_block: # If it's currently a single condition
            current_single_cond_data = copy.deepcopy(cond_block)
            cond_block.clear() # Prepare to make it compound
            cond_block["logical_operator"] = "AND" # Default new compound to AND
            # Use current single condition as the first sub-condition, or default if empty
            cond_block["sub_conditions"] = [current_single_cond_data if current_single_cond_data.get("type") else {"type": "always_true"}]
        
        # Now it's definitely compound, add a new default sub-condition
        cond_block.setdefault("sub_conditions", []).append({"type": "always_true"}) # Add a new default sub-condition
        
        rule["condition"] = cond_block # Ensure the modified block is set back
        self._set_dirty_status(True)
        # Update the details panel to reflect the (now compound) structure and the new sub-condition
        self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")
        logger.info(f"Added new sub-condition to rule '{rule.get('name')}'.")

    def _remove_selected_sub_condition(self):
        if self.selected_rule_index is None or self.selected_sub_condition_index is None or self.details_panel_instance is None:
            logger.warning("Cannot remove sub-condition: No rule or sub-condition selected, or details panel missing.")
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules",[]))):
            logger.error(f"Cannot remove sub-condition: selected rule index {self.selected_rule_index} out of bounds.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})
        sub_list = cond_block.get("sub_conditions")

        if sub_list and 0 <= self.selected_sub_condition_index < len(sub_list):
            removed_sub_cond = sub_list.pop(self.selected_sub_condition_index)
            logger.info(f"Removed sub-condition at index {self.selected_sub_condition_index} (type: {removed_sub_cond.get('type')}) from rule '{rule.get('name')}'.")
            
            # If only one sub-condition remains, ask user if they want to convert to single
            if len(sub_list) == 1:
                if messagebox.askyesno("Convert to Single?", "Only one sub-condition remains. Convert this rule to a single condition?"):
                    rule["condition"] = copy.deepcopy(sub_list[0]) # Promote the remaining sub-condition
                    logger.info(f"Rule '{rule.get('name')}' converted to single condition after sub-condition removal.")
            elif not sub_list: # No sub-conditions left, make it a default single "always_true"
                 rule["condition"] = {"type": "always_true"}
                 logger.info(f"Rule '{rule.get('name')}' converted to default single 'always_true' as no sub-conditions remain.")


            self.selected_sub_condition_index = None # Clear selection
            self._set_dirty_status(True)
            self.details_panel_instance.update_display(copy.deepcopy(rule), "rule") # Refresh panel
        else:
            logger.warning(f"Cannot remove sub-condition: Invalid index {self.selected_sub_condition_index} or sub_conditions list not found/empty.")

    def _convert_condition_structure(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning("Cannot convert condition structure: No rule selected or details panel missing.")
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules",[]))):
            logger.error(f"Cannot convert condition: selected rule index {self.selected_rule_index} out of bounds.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        cond = rule.get("condition", {})
        is_currently_compound = "logical_operator" in cond

        if is_currently_compound:
            sub_conditions_list = cond.get("sub_conditions", [])
            if len(sub_conditions_list) > 1:
                if not messagebox.askyesno("Confirm Conversion", "Convert to a single condition? Only the first sub-condition will be kept. Others will be lost. Continue?"):
                    return
            new_single_condition = copy.deepcopy(sub_conditions_list[0]) if sub_conditions_list else {"type": "always_true"}
            rule["condition"] = new_single_condition
            logger.info(f"Rule '{rule.get('name')}' condition converted from compound to single: {new_single_condition}")
        else: # Is currently single, convert to compound
            current_single_condition_data = copy.deepcopy(cond)
            if not current_single_condition_data.get("type"): # Ensure it's a valid structure
                current_single_condition_data = {"type": "always_true"}
            rule["condition"] = {"logical_operator": "AND", "sub_conditions": [current_single_condition_data]}
            logger.info(f"Rule '{rule.get('name')}' condition converted from single to compound. Original single: {current_single_condition_data}")

        self._set_dirty_status(True)
        self.selected_sub_condition_index = None # Clear sub-condition selection as structure changed
        self.details_panel_instance.update_display(copy.deepcopy(rule), "rule") # Refresh panel