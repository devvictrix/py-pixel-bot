import logging
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
import copy
import shutil  # For copying template files
from typing import Optional, Dict, Any, List, Callable, Union

import customtkinter as ctk
from PIL import Image, UnidentifiedImageError, ImageTk  # Added ImageTk

from mark_i.core.config_manager import ConfigManager, TEMPLATES_SUBDIR_NAME
from mark_i.ui.gui.region_selector import RegionSelectorWindow
from mark_i.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value, create_clickable_list_item
from mark_i.ui.gui.panels.details_panel import DetailsPanel

from mark_i.ui.gui.generation.profile_creation_wizard import ProfileCreationWizardWindow
from mark_i.engines.gemini_analyzer import GeminiAnalyzer

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.main_app_window")


class MainAppWindow(ctk.CTk):
    """
    The main application window for the Mark-I GUI Profile Editor.
    Handles profile file operations, displays lists of regions, templates,
    and rules, and manages the DetailsPanel for editing selected items.
    Launches the AI Profile Creation Wizard (v5.0.0).
    """

    def __init__(self, initial_profile_path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing MainAppWindow...")
        self.title("Mark-I Profile Editor")
        self.geometry("1350x800")
        self.minsize(1000, 700)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.current_profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self._is_dirty: bool = False

        # This ConfigManager instance is primarily for the *currently loaded/edited* profile
        # in the MainAppWindow. The AI Profile Creator Wizard will use its own.
        self.config_manager = ConfigManager(None, create_if_missing=True)

        self.selected_region_index: Optional[int] = None
        self.selected_template_index: Optional[int] = None
        self.selected_rule_index: Optional[int] = None
        self.selected_sub_condition_index: Optional[int] = None  # Managed by DetailsPanel but parent needs to know

        self.selected_region_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_template_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_rule_item_widget: Optional[ctk.CTkFrame] = None

        self.details_panel_instance: Optional[DetailsPanel] = None
        self.entry_profile_desc: Optional[ctk.CTkEntry] = None
        self.entry_monitor_interval: Optional[ctk.CTkEntry] = None
        self.entry_dominant_k: Optional[ctk.CTkEntry] = None
        self.entry_tesseract_cmd: Optional[ctk.CTkEntry] = None
        self.entry_tesseract_config: Optional[ctk.CTkEntry] = None
        self.entry_gemini_default_model: Optional[ctk.CTkEntry] = None
        self.label_gemini_api_key_status: Optional[ctk.CTkLabel] = None
        self.label_current_profile_path: Optional[ctk.CTkLabel] = None

        self.regions_list_scroll_frame: Optional[ctk.CTkScrollableFrame] = None
        self.templates_list_scroll_frame: Optional[ctk.CTkScrollableFrame] = None
        self.rules_list_scroll_frame: Optional[ctk.CTkScrollableFrame] = None
        self.btn_remove_region: Optional[ctk.CTkButton] = None
        self.btn_remove_template: Optional[ctk.CTkButton] = None
        self.btn_remove_rule: Optional[ctk.CTkButton] = None

        self.gemini_analyzer_instance: Optional[GeminiAnalyzer] = None
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            default_gem_model = self.profile_data.get("settings", {}).get("gemini_default_model_name", "gemini-1.5-flash-latest")
            self.gemini_analyzer_instance = GeminiAnalyzer(api_key=gemini_api_key, default_model_name=default_gem_model)
            if not self.gemini_analyzer_instance.client_initialized:
                logger.error("MainAppWindow: GeminiAnalyzer failed to initialize.")
        else:
            logger.warning("MainAppWindow: GEMINI_API_KEY not found.")

        self._setup_ui_layout_and_menu()

        if initial_profile_path:
            self._load_profile_from_path(initial_profile_path)
        else:
            self._new_profile(prompt_save=False)

        self.protocol("WM_DELETE_WINDOW", self._on_close_window)
        logger.info("MainAppWindow initialization complete.")

    def _check_gemini_api_key_status(self) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        if self.gemini_analyzer_instance and self.gemini_analyzer_instance.client_initialized:
            return "OK (Client Initialized)"
        elif api_key:
            return "Key Found but Client NOT Initialized (Check logs)"
        return "NOT FOUND in .env (AI features disabled)"

    def _setup_ui_layout_and_menu(self):
        self.menu_bar = tk.Menu(self)
        self.config(menu=self.menu_bar)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Profile", command=self._new_profile, accelerator="Ctrl+N")
        file_menu.add_command(label="New AI-Generated Profile...", command=self._launch_ai_profile_creator_wizard, accelerator="Ctrl+G")
        file_menu.add_separator()
        file_menu.add_command(label="Open Profile...", command=self._open_profile, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Save Profile", command=self._save_profile, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Profile As...", command=self._save_profile_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close_window)

        self.bind_all("<Control-n>", lambda e: self._new_profile())
        self.bind_all("<Control-g>", lambda e: self._launch_ai_profile_creator_wizard())
        self.bind_all("<Control-o>", lambda e: self._open_profile())
        self.bind_all("<Control-s>", lambda e: self._save_profile())
        self.bind_all("<Control-S>", lambda e: self._save_profile_as())

        self.grid_columnconfigure(0, weight=1, minsize=330)
        self.grid_columnconfigure(1, weight=2, minsize=380)
        self.grid_columnconfigure(2, weight=3, minsize=420)
        self.grid_rowconfigure(0, weight=1)

        self.left_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "gray20"))
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 1), pady=0)
        self._setup_left_panel_content()

        self.center_panel = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "gray17"))
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=(1, 1), pady=0)
        self._setup_center_panel_content()

        self.details_panel_instance = DetailsPanel(self, parent_app=self, corner_radius=0)
        self.details_panel_instance.grid(row=0, column=2, sticky="nsew", padx=(1, 0), pady=0)

    def _setup_left_panel_content(self):
        self.left_panel.grid_columnconfigure(0, weight=1)
        current_row_lp = 0
        pif_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        pif_frame.grid(row=current_row_lp, column=0, sticky="new", padx=10, pady=(10, 5))
        pif_frame.grid_columnconfigure(1, weight=1)
        current_row_lp += 1
        ctk.CTkLabel(pif_frame, text="Profile Path:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 0))
        self.label_current_profile_path = ctk.CTkLabel(pif_frame, text="Path: New Profile (unsaved)", anchor="w", wraplength=300, font=ctk.CTkFont(size=11))
        self.label_current_profile_path.grid(row=1, column=0, columnspan=2, padx=5, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(pif_frame, text="Description:").grid(row=2, column=0, padx=5, pady=(5, 2), sticky="w")
        self.entry_profile_desc = ctk.CTkEntry(pif_frame, placeholder_text="Brief description")
        self.entry_profile_desc.grid(row=2, column=1, padx=5, pady=(5, 2), sticky="ew")
        self.entry_profile_desc.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        ctk.CTkLabel(pif_frame, text="Monitor Interval (s):").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        self.entry_monitor_interval = ctk.CTkEntry(pif_frame, placeholder_text="e.g., 1.0")
        self.entry_monitor_interval.grid(row=3, column=1, padx=5, pady=2, sticky="ew")
        self.entry_monitor_interval.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        ctk.CTkLabel(pif_frame, text="Dominant Colors (K):").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        self.entry_dominant_k = ctk.CTkEntry(pif_frame, placeholder_text="e.g., 3")
        self.entry_dominant_k.grid(row=4, column=1, padx=5, pady=2, sticky="ew")
        self.entry_dominant_k.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        ctk.CTkLabel(pif_frame, text="Tesseract CMD Path (Optional):").grid(row=5, column=0, padx=5, pady=2, sticky="w")
        self.entry_tesseract_cmd = ctk.CTkEntry(pif_frame, placeholder_text="Path to tesseract.exe")
        self.entry_tesseract_cmd.grid(row=5, column=1, padx=5, pady=2, sticky="ew")
        self.entry_tesseract_cmd.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        ctk.CTkLabel(pif_frame, text="Tesseract Config Str (Optional):").grid(row=6, column=0, padx=5, pady=2, sticky="w")
        self.entry_tesseract_config = ctk.CTkEntry(pif_frame, placeholder_text="e.g., --psm 6 -l eng")
        self.entry_tesseract_config.grid(row=6, column=1, padx=5, pady=2, sticky="ew")
        self.entry_tesseract_config.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        ctk.CTkLabel(pif_frame, text="Gemini Default Model:").grid(row=7, column=0, padx=5, pady=2, sticky="w")
        self.entry_gemini_default_model = ctk.CTkEntry(pif_frame, placeholder_text="e.g., gemini-1.5-flash-latest")
        self.entry_gemini_default_model.grid(row=7, column=1, padx=5, pady=2, sticky="ew")
        self.entry_gemini_default_model.bind("<KeyRelease>", lambda e: self._set_dirty_status(True))
        ctk.CTkLabel(pif_frame, text="Gemini API Key Status:").grid(row=8, column=0, padx=5, pady=2, sticky="w")
        self.label_gemini_api_key_status = ctk.CTkLabel(pif_frame, text=self._check_gemini_api_key_status(), anchor="w")
        self.label_gemini_api_key_status.grid(row=8, column=1, padx=5, pady=2, sticky="ew")

        regions_outer_frame = ctk.CTkFrame(self.left_panel)
        regions_outer_frame.grid(row=current_row_lp, column=0, sticky="nsew", padx=10, pady=(5, 5))
        current_row_lp += 1
        regions_outer_frame.grid_columnconfigure(0, weight=1)
        regions_outer_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(regions_outer_frame, text="Screen Regions", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0, 5), sticky="w", padx=5)
        self.regions_list_scroll_frame = ctk.CTkScrollableFrame(regions_outer_frame, label_text="", fg_color=("gray95", "gray22"))
        self.regions_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=5)
        region_buttons_frame = ctk.CTkFrame(regions_outer_frame, fg_color="transparent")
        region_buttons_frame.grid(row=2, column=0, pady=(5, 0), sticky="ew", padx=5)
        ctk.CTkButton(region_buttons_frame, text="Add Region", width=100, command=self._add_region).pack(side="left", padx=(0, 5))
        self.btn_remove_region = ctk.CTkButton(region_buttons_frame, text="Remove Selected", width=120, command=self._remove_selected_region, state="disabled")
        self.btn_remove_region.pack(side="left", padx=5)

        templates_outer_frame = ctk.CTkFrame(self.left_panel)
        templates_outer_frame.grid(row=current_row_lp, column=0, sticky="nsew", padx=10, pady=(5, 10))
        current_row_lp += 1
        templates_outer_frame.grid_columnconfigure(0, weight=1)
        templates_outer_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(templates_outer_frame, text="Image Templates", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0, 5), sticky="w", padx=5)
        self.templates_list_scroll_frame = ctk.CTkScrollableFrame(templates_outer_frame, label_text="", fg_color=("gray95", "gray22"))
        self.templates_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=5)
        template_buttons_frame = ctk.CTkFrame(templates_outer_frame, fg_color="transparent")
        template_buttons_frame.grid(row=2, column=0, pady=(5, 0), sticky="ew", padx=5)
        ctk.CTkButton(template_buttons_frame, text="Add Template", width=100, command=self._add_template).pack(side="left", padx=(0, 5))
        self.btn_remove_template = ctk.CTkButton(template_buttons_frame, text="Remove Selected", width=120, command=self._remove_selected_template, state="disabled")
        self.btn_remove_template.pack(side="left", padx=5)

        self.left_panel.grid_rowconfigure(0, weight=0)
        self.left_panel.grid_rowconfigure(1, weight=1)
        self.left_panel.grid_rowconfigure(2, weight=1)

    def _setup_center_panel_content(self):
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.center_panel, text="Automation Rules", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.rules_list_scroll_frame = ctk.CTkScrollableFrame(self.center_panel, label_text="", fg_color=("gray95", "gray22"))
        self.rules_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 5))
        rule_buttons_frame = ctk.CTkFrame(self.center_panel, fg_color="transparent")
        rule_buttons_frame.grid(row=2, column=0, pady=(5, 10), padx=10, sticky="ew")
        ctk.CTkButton(rule_buttons_frame, text="Add New Rule", command=self._add_new_rule).pack(side="left", padx=(0, 5))
        self.btn_remove_rule = ctk.CTkButton(rule_buttons_frame, text="Remove Selected Rule", command=self._remove_selected_rule, state="disabled")
        self.btn_remove_rule.pack(side="left", padx=5)

    def _update_window_title(self):
        title = "Mark-I Profile Editor"
        if self.current_profile_path:
            title += f" - {os.path.basename(self.current_profile_path)}"
        else:
            title += " - New Profile"
        if self._is_dirty:
            title += "*"
        self.title(title)

    def _set_dirty_status(self, is_now_dirty: bool):
        if self._is_dirty == is_now_dirty:
            return
        self._is_dirty = is_now_dirty
        self._update_window_title()
        logger.debug(f"Dirty status set to {is_now_dirty}.")

    def _new_profile(self, event=None, prompt_save=True):
        if prompt_save and self._is_dirty and not self._prompt_save_if_dirty():
            return
        self.current_profile_path = None
        self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self.config_manager = ConfigManager(None, create_if_missing=True)
        self.config_manager.update_profile_data(self.profile_data)
        self._populate_ui_from_profile_data()
        self._set_dirty_status(False)
        logger.info("New profile created and UI reset.")

    def _launch_ai_profile_creator_wizard(self, event=None):
        if not self.gemini_analyzer_instance or not self.gemini_analyzer_instance.client_initialized:
            messagebox.showerror("Gemini Not Ready", "Gemini API client is not initialized. Please set API key.", parent=self)
            return
        if self._is_dirty and not self._prompt_save_if_dirty():
            return
        logger.info("Launching AI Profile Creator Wizard...")
        wizard = ProfileCreationWizardWindow(master=self, main_app_instance=self)
        self.wait_window(wizard)
        if hasattr(wizard, "newly_saved_profile_path") and wizard.newly_saved_profile_path:
            logger.info(f"AI Wizard saved new profile to: {wizard.newly_saved_profile_path}")
            self._load_profile_from_path(wizard.newly_saved_profile_path)
        elif hasattr(wizard, "user_cancelled_wizard") and wizard.user_cancelled_wizard:
            logger.info("AI Profile Creator Wizard cancelled.")
        else:
            logger.info("AI Profile Creator Wizard closed.")

    def _open_profile(self, event=None):
        if self._is_dirty and not self._prompt_save_if_dirty():
            return
        filepath = filedialog.askopenfilename(title="Open Profile", defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")], parent=self)
        if filepath:
            self._load_profile_from_path(filepath)

    def _load_profile_from_path(self, filepath: str):
        try:
            self.config_manager = ConfigManager(filepath, create_if_missing=False)
            self.profile_data = self.config_manager.get_profile_data()
            self.current_profile_path = self.config_manager.get_profile_path()
            self._populate_ui_from_profile_data()
            self._set_dirty_status(False)
            logger.info(f"Profile '{filepath}' loaded successfully.")
        except (FileNotFoundError, ValueError, IOError) as e:
            logger.error(f"Failed to load profile '{filepath}': {e}", exc_info=True)
            messagebox.showerror("Load Error", f"Could not load profile: {filepath}\nError: {e}", parent=self)
            self._new_profile(prompt_save=False)

    def _save_profile(self, event=None) -> bool:
        if not self.current_profile_path:
            return self._save_profile_as()
        if not self._update_profile_data_from_ui():
            logger.warning("Save profile aborted: invalid UI settings.")
            return False
        self.config_manager.update_profile_data(self.profile_data)
        try:
            if self.config_manager.save_current_profile():
                self._set_dirty_status(False)
                logger.info(f"Profile saved to: {self.current_profile_path}")
                return True
            else:
                messagebox.showerror("Save Error", "Could not save. Path invalid?", parent=self)
                return False
        except Exception as e:
            logger.error(f"Failed to save to '{self.current_profile_path}': {e}", exc_info=True)
            messagebox.showerror("Save Error", f"Error: {e}", parent=self)
            return False

    def _save_profile_as(self, event=None) -> bool:
        if not self._update_profile_data_from_ui():
            logger.warning("Save As aborted: invalid UI settings.")
            return False
        initial_fn = os.path.basename(self.current_profile_path) if self.current_profile_path else "new_profile.json"
        default_dir = self.config_manager.profiles_base_dir if self.config_manager else os.getcwd()
        filepath = filedialog.asksaveasfilename(
            title="Save Profile As", defaultextension=".json", initialdir=default_dir, filetypes=[("JSON files", "*.json"), ("All files", "*.*")], initialfile=initial_fn, parent=self
        )
        if filepath:
            self.current_profile_path = filepath
            self.config_manager = ConfigManager(self.current_profile_path, create_if_missing=True)
            self.config_manager.update_profile_data(self.profile_data)
            return self._save_profile()
        return False

    def _populate_ui_from_profile_data(self):
        logger.debug("Populating UI from MainAppWindow.profile_data...")
        if not all(
            [
                self.entry_profile_desc,
                self.entry_monitor_interval,
                self.entry_dominant_k,
                self.entry_tesseract_cmd,
                self.entry_tesseract_config,
                self.entry_gemini_default_model,
                self.label_gemini_api_key_status,
                self.label_current_profile_path,
                self.regions_list_scroll_frame,
                self.templates_list_scroll_frame,
                self.rules_list_scroll_frame,
                self.btn_remove_region,
                self.btn_remove_template,
                self.btn_remove_rule,
            ]
        ):
            logger.error("Core UI elements not init. Cannot populate UI.")
            return

        self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path if self.current_profile_path else 'New Profile (unsaved)'}")
        self._update_window_title()

        self.entry_profile_desc.delete(0, tk.END)
        self.entry_profile_desc.insert(0, self.profile_data.get("profile_description", ""))
        settings = self.profile_data.get("settings", {})
        self.entry_monitor_interval.delete(0, tk.END)
        self.entry_monitor_interval.insert(0, str(settings.get("monitoring_interval_seconds", 1.0)))
        self.entry_dominant_k.delete(0, tk.END)
        self.entry_dominant_k.insert(0, str(settings.get("analysis_dominant_colors_k", 3)))
        self.entry_tesseract_cmd.delete(0, tk.END)
        self.entry_tesseract_cmd.insert(0, str(settings.get("tesseract_cmd_path", "") or ""))
        self.entry_tesseract_config.delete(0, tk.END)
        self.entry_tesseract_config.insert(0, str(settings.get("tesseract_config_custom", "")))
        self.entry_gemini_default_model.delete(0, tk.END)
        self.entry_gemini_default_model.insert(0, str(settings.get("gemini_default_model_name", "gemini-1.5-flash-latest")))
        self.label_gemini_api_key_status.configure(text=self._check_gemini_api_key_status())

        self.selected_region_index = self.selected_template_index = self.selected_rule_index = None
        self._populate_specific_list_frame("region", self.regions_list_scroll_frame, self.profile_data.get("regions", []), lambda item, idx: item.get("name", f"R_{idx}"), self.btn_remove_region)
        self._populate_specific_list_frame(
            "template", self.templates_list_scroll_frame, self.profile_data.get("templates", []), lambda item, idx: f"{item.get('name','T_')}({item.get('filename','F_')})", self.btn_remove_template
        )
        self._populate_specific_list_frame("rule", self.rules_list_scroll_frame, self.profile_data.get("rules", []), lambda item, idx: item.get("name", f"Rule_{idx}"), self.btn_remove_rule)
        if self.details_panel_instance:
            self.details_panel_instance.update_display(None, "none")
        logger.debug("UI population from profile_data complete.")

    def _populate_specific_list_frame(self, list_key: str, frame: ctk.CTkScrollableFrame, items: List[Dict], display_cb: Callable, button: Optional[ctk.CTkButton]):
        for w in frame.winfo_children():
            w.destroy()
        setattr(self, f"selected_{list_key}_item_widget", None)
        if button and hasattr(button, "configure"):
            button.configure(state="disabled")
        for i, item_data in enumerate(items):
            txt = display_cb(item_data, i)
            item_frame_ref = {}
            item_ui_frame = create_clickable_list_item(frame, txt, lambda e=None, lk=list_key, d=item_data, idx=i, ifr=item_frame_ref: self._on_item_selected(lk, d, idx, ifr.get("frame")))
            item_frame_ref["frame"] = item_ui_frame

    def _update_profile_data_from_ui(self) -> bool:
        logger.debug("Updating MainAppWindow.profile_data from UI settings inputs...")
        if not all([self.entry_profile_desc, self.entry_monitor_interval, self.entry_dominant_k, self.entry_tesseract_cmd, self.entry_tesseract_config, self.entry_gemini_default_model]):
            logger.error("Cannot update profile data: Core settings UI elements not fully initialized.")
            return False

        desc, desc_ok = validate_and_get_widget_value(
            self.entry_profile_desc, None, "Profile Description", str, self.profile_data.get("profile_description", ""), required=False, allow_empty_string=True
        )
        if desc_ok:
            self.profile_data["profile_description"] = desc
        settings = self.profile_data.get("settings", {})
        all_ok = desc_ok
        val, ok = validate_and_get_widget_value(self.entry_monitor_interval, None, "Monitoring Interval", float, settings.get("monitoring_interval_seconds", 1.0), required=True, min_val=0.01)
        settings["monitoring_interval_seconds"] = val
        all_ok &= ok
        val, ok = validate_and_get_widget_value(self.entry_dominant_k, None, "Dominant K", int, settings.get("analysis_dominant_colors_k", 3), required=True, min_val=1, max_val=20)
        settings["analysis_dominant_colors_k"] = val
        all_ok &= ok
        val, ok = validate_and_get_widget_value(self.entry_tesseract_cmd, None, "Tesseract CMD Path", str, settings.get("tesseract_cmd_path", ""), required=False, allow_empty_string=True)
        settings["tesseract_cmd_path"] = val if val else None
        all_ok &= ok
        val, ok = validate_and_get_widget_value(self.entry_tesseract_config, None, "Tesseract Config Str", str, settings.get("tesseract_config_custom", ""), required=False, allow_empty_string=True)
        settings["tesseract_config_custom"] = val
        all_ok &= ok
        val, ok = validate_and_get_widget_value(
            self.entry_gemini_default_model, None, "Gemini Default Model", str, settings.get("gemini_default_model_name", "gemini-1.5-flash-latest"), required=False, allow_empty_string=True
        )
        settings["gemini_default_model_name"] = val if val else "gemini-1.5-flash-latest"
        all_ok &= ok
        self.profile_data["settings"] = settings
        if not all_ok:
            logger.warning("One or more settings invalid. Profile data may not be fully updated.")
            return False
        return True

    def _prompt_save_if_dirty(self) -> bool:
        if not self._is_dirty:
            return True
        resp = messagebox.askyesnocancel("Unsaved Changes", "Current profile has unsaved changes. Save before proceeding?", parent=self, icon=messagebox.QUESTION, default=messagebox.YES)
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
        if not item_widget_frame or not item_widget_frame.winfo_exists():
            logger.warning(f"Item selection for {list_name} failed: widget frame invalid.")
            return
        logger.info(f"Item selected: {list_name}, index {item_index}, name '{item_data.get('name')}'")
        list_map = {
            "region": (self.btn_remove_region, "selected_region_index", "selected_region_item_widget"),
            "template": (self.btn_remove_template, "selected_template_index", "selected_template_item_widget"),
            "rule": (self.btn_remove_rule, "selected_rule_index", "selected_rule_item_widget"),
        }
        for ln, (btn, idx_attr, widget_attr) in list_map.items():
            if ln != list_name:
                self._highlight_selected_list_item(ln, None)
                setattr(self, idx_attr, None)
                _ = btn.configure(state="disabled") if btn else None
        if list_name == "rule" and self.details_panel_instance:
            self.details_panel_instance.parent_app.selected_sub_condition_index = None
            self.details_panel_instance._highlight_selected_list_item("condition", None, is_sub_list=True)
            _ = self.details_panel_instance.btn_remove_sub_condition.configure(state="disabled") if self.details_panel_instance.btn_remove_sub_condition else None
        setattr(self, list_map[list_name][1], item_index)
        self._highlight_selected_list_item(list_name, item_widget_frame)
        btn_curr = list_map[list_name][0]
        _ = btn_curr.configure(state="normal") if btn_curr else None
        if self.details_panel_instance:
            self.details_panel_instance.update_display(copy.deepcopy(item_data), list_name)

    def _highlight_selected_list_item(self, list_name_key: str, new_selected_widget_frame: Optional[ctk.CTkFrame], is_sub_list: bool = False):
        attr_prefix = "selected_sub_" if is_sub_list else "selected_"
        attr_widget_name = f"{attr_prefix}{list_name_key}_item_widget"
        target_obj = self.details_panel_instance if is_sub_list and self.details_panel_instance else self
        old_widget = getattr(target_obj, attr_widget_name, None)
        if old_widget and isinstance(old_widget, ctk.CTkFrame) and old_widget.winfo_exists():
            old_widget.configure(fg_color="transparent")
        if new_selected_widget_frame and new_selected_widget_frame.winfo_exists():
            try:
                hl_colors = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
                hl_color = hl_colors[0] if isinstance(hl_colors, tuple) and ctk.get_appearance_mode() == "Light" else (hl_colors[1] if isinstance(hl_colors, tuple) else hl_colors)
            except:
                hl_color = "#3a7ebf"
            new_selected_widget_frame.configure(fg_color=hl_color)
            setattr(target_obj, attr_widget_name, new_selected_widget_frame)
        else:
            setattr(target_obj, attr_widget_name, None)

    def _apply_region_changes(self):
        if self.selected_region_index is None or self.details_panel_instance is None:
            return
        if not (0 <= self.selected_region_index < len(self.profile_data.get("regions", []))):
            return
        current_region = self.profile_data["regions"][self.selected_region_index]
        original_name = current_region.get("name")
        new_vals = {}
        all_valid = True
        name_w = self.details_panel_instance.detail_widgets.get("name")
        val, ok = validate_and_get_widget_value(name_w, None, "Region Name", str, original_name, True)
        new_vals["name"] = val
        all_valid &= ok
        for p in ["x", "y", "width", "height"]:
            w = self.details_panel_instance.detail_widgets.get(p)
            min_v = 1 if p in ["width", "height"] else None
            def_v = current_region.get(p, 0 if p in ["x", "y"] else 1)
            val, ok = validate_and_get_widget_value(w, None, p.capitalize(), int, def_v, True, min_val=min_v)
            new_vals[p] = val
            all_valid &= ok
        comment_w = self.details_panel_instance.detail_widgets.get("comment")
        val, ok = validate_and_get_widget_value(comment_w, None, "Comment", str, current_region.get("comment", ""), False, True)
        new_vals["comment"] = val
        all_valid &= ok
        if not all_valid:
            messagebox.showerror("Validation Error", "One or more region fields are invalid.", parent=self)
            return
        if new_vals["name"] != original_name and any(r.get("name") == new_vals["name"] for i, r in enumerate(self.profile_data["regions"]) if i != self.selected_region_index):
            messagebox.showerror("Name Error", f"Region name '{new_vals['name']}' already exists.", parent=self)
            return
        current_region.update(new_vals)
        self._set_dirty_status(True)
        self._populate_specific_list_frame("region", self.regions_list_scroll_frame, self.profile_data["regions"], lambda item, idx: item.get("name", f"R_{idx}"), self.btn_remove_region)
        if self.selected_region_index < len(self.profile_data["regions"]):
            children = self.regions_list_scroll_frame.winfo_children()
            new_item_w = children[self.selected_region_index] if children and self.selected_region_index < len(children) else None
            self._highlight_selected_list_item("region", new_item_w)
            self.details_panel_instance.update_display(copy.deepcopy(current_region), "region")
        messagebox.showinfo("Region Updated", f"Region '{new_vals['name']}' updated.", parent=self)

    def _apply_template_changes(self):
        if self.selected_template_index is None or self.details_panel_instance is None:
            return
        if not (0 <= self.selected_template_index < len(self.profile_data.get("templates", []))):
            return
        current_template = self.profile_data["templates"][self.selected_template_index]
        original_name = current_template.get("name")
        name_w = self.details_panel_instance.detail_widgets.get("template_name")
        name_val, name_valid = validate_and_get_widget_value(name_w, None, "Template Name", str, original_name, True)
        comment_w = self.details_panel_instance.detail_widgets.get("comment")
        comment_val, comment_valid = validate_and_get_widget_value(comment_w, None, "Comment", str, current_template.get("comment", ""), False, True)
        if not (name_valid and comment_valid):
            messagebox.showerror("Validation Error", "Template name or comment invalid.", parent=self)
            return
        if name_val != original_name and any(t.get("name") == name_val for i, t in enumerate(self.profile_data["templates"]) if i != self.selected_template_index):
            messagebox.showerror("Name Error", f"Template name '{name_val}' already exists.", parent=self)
            return
        current_template["name"] = name_val
        current_template["comment"] = comment_val
        self._set_dirty_status(True)
        self._populate_specific_list_frame(
            "template", self.templates_list_scroll_frame, self.profile_data["templates"], lambda item, idx: f"{item.get('name')}({item.get('filename')})", self.btn_remove_template
        )
        if self.selected_template_index < len(self.profile_data["templates"]):
            children = self.templates_list_scroll_frame.winfo_children()
            new_item_w = children[self.selected_template_index] if children and self.selected_template_index < len(children) else None
            self._highlight_selected_list_item("template", new_item_w)
            self.details_panel_instance.update_display(copy.deepcopy(current_template), "template")
        messagebox.showinfo("Template Updated", f"Template '{name_val}' updated.", parent=self)

    def _apply_rule_changes(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules", []))):
            return
        current_rule_orig = self.profile_data["rules"][self.selected_rule_index]
        old_name = current_rule_orig.get("name")
        logger.info(f"Applying changes for rule: '{old_name}' (index {self.selected_rule_index})")
        updated_rule_data_from_ui = self.details_panel_instance.get_all_rule_data_from_ui()
        if updated_rule_data_from_ui is None:
            messagebox.showerror("Validation Error", "Invalid rule parameters.", parent=self)
            return
        new_name = updated_rule_data_from_ui.get("name")
        if new_name != old_name and any(r.get("name") == new_name for i, r in enumerate(self.profile_data.get("rules", [])) if i != self.selected_rule_index):
            messagebox.showerror("Name Error", f"Rule name '{new_name}' already exists.", parent=self)
            return
        self.profile_data["rules"][self.selected_rule_index] = updated_rule_data_from_ui
        self._set_dirty_status(True)
        self._populate_specific_list_frame("rule", self.rules_list_scroll_frame, self.profile_data["rules"], lambda item, idx: item.get("name", f"Rule{idx}"), self.btn_remove_rule)
        if self.selected_rule_index < len(self.profile_data["rules"]):
            children = self.rules_list_scroll_frame.winfo_children()
            new_item_w = children[self.selected_rule_index] if children and self.selected_rule_index < len(children) else None
            self._highlight_selected_list_item("rule", new_item_w)
            self.details_panel_instance.update_display(copy.deepcopy(updated_rule_data_from_ui), "rule")
        messagebox.showinfo("Rule Updated", f"Rule '{new_name}' updated.", parent=self)

    def _add_region(self):
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "Profile must be saved before adding regions. Save now?", parent=self) or not self._save_profile_as():
                return
            if not self.current_profile_path:
                logger.warning("Add region aborted: Profile not saved.")
                return
        if self._is_dirty and not self._prompt_save_if_dirty():
            return
        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            selector = RegionSelectorWindow(master=self, config_manager_for_saving_path_only=cm_for_selector, existing_region_data=None)
            self.wait_window(selector)
            if hasattr(selector, "changes_made") and selector.changes_made and selector.saved_region_info:
                # RegionSelector now returns data, MainAppWindow adds it to its profile_data
                new_region_data = selector.saved_region_info
                if any(r.get("name") == new_region_data["name"] for r in self.profile_data.get("regions", [])):
                    messagebox.showerror("Name Conflict", f"Region name '{new_region_data['name']}' already exists.", parent=self)
                    return
                self.profile_data.setdefault("regions", []).append(new_region_data)
                self._set_dirty_status(True)
                self._populate_specific_list_frame("region", self.regions_list_scroll_frame, self.profile_data["regions"], lambda item, idx: item.get("name", f"R_{idx}"), self.btn_remove_region)
                # Optionally select the new region
                new_idx = len(self.profile_data["regions"]) - 1
                children = self.regions_list_scroll_frame.winfo_children()
                new_item_w = children[new_idx] if children and new_idx < len(children) else None
                self._on_item_selected("region", new_region_data, new_idx, new_item_w)

        except Exception as e:
            logger.error(f"Error in Add Region: {e}", exc_info=True)
            messagebox.showerror("Add Region Error", f"Error: {e}", parent=self)

    def _edit_region_coordinates_with_selector(self):
        if self.selected_region_index is None or not (0 <= self.selected_region_index < len(self.profile_data.get("regions", []))):
            return
        if self._is_dirty and not self._prompt_save_if_dirty():
            return
        if not self.current_profile_path:
            messagebox.showerror("Error", "Profile must be saved before editing region coordinates.", parent=self)
            return
        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            region_to_edit_data = copy.deepcopy(self.profile_data["regions"][self.selected_region_index])
            selector = RegionSelectorWindow(master=self, config_manager_for_saving_path_only=cm_for_selector, existing_region_data=region_to_edit_data)
            self.wait_window(selector)
            if hasattr(selector, "changes_made") and selector.changes_made and selector.saved_region_info:
                updated_region_data = selector.saved_region_info
                # Check name conflict if name was changed by selector (though selector dialog is primary for name)
                if updated_region_data["name"] != region_to_edit_data["name"] and any(
                    r.get("name") == updated_region_data["name"] for i, r in enumerate(self.profile_data["regions"]) if i != self.selected_region_index
                ):
                    messagebox.showerror("Name Conflict", f"Region name '{updated_region_data['name']}' already exists.", parent=self)
                    return  # Or revert name change if desired

                self.profile_data["regions"][self.selected_region_index].update(updated_region_data)
                self._set_dirty_status(True)
                self._populate_specific_list_frame("region", self.regions_list_scroll_frame, self.profile_data["regions"], lambda item, idx: item.get("name", f"R_{idx}"), self.btn_remove_region)
                children = self.regions_list_scroll_frame.winfo_children()
                new_item_w = children[self.selected_region_index] if children and self.selected_region_index < len(children) else None
                self._on_item_selected("region", self.profile_data["regions"][self.selected_region_index], self.selected_region_index, new_item_w)

        except Exception as e:
            logger.error(f"Error in Edit Region Coords: {e}", exc_info=True)
            messagebox.showerror("Edit Region Error", f"Error: {e}", parent=self)

    def _remove_selected_item(self, list_name_key: str, profile_data_key: str, selected_index_attr: str, remove_button_widget: Optional[ctk.CTkButton], display_cb: Callable):
        selected_idx = getattr(self, selected_index_attr, None)
        if selected_idx is None or not self.profile_data or profile_data_key not in self.profile_data:
            return
        item_list: List[Dict] = self.profile_data[profile_data_key]
        if 0 <= selected_idx < len(item_list):
            removed_item = item_list.pop(selected_idx)
            logger.info(f"Removed {list_name_key} '{removed_item.get('name','N/A')}' at index {selected_idx}.")
            list_frame = getattr(self, f"{list_name_key}s_list_scroll_frame", None)
            if list_frame:
                self._populate_specific_list_frame(list_name_key, list_frame, item_list, display_cb, remove_button_widget)
            self._set_dirty_status(True)
            setattr(self, selected_index_attr, None)
            if remove_button_widget and hasattr(remove_button_widget, "configure"):
                remove_button_widget.configure(state="disabled")
            if self.details_panel_instance:
                self.details_panel_instance.update_display(None, "none")
            if list_name_key == "template" and self.current_profile_path and removed_item.get("filename"):
                try:
                    # Use ConfigManager to get the correct path
                    tpl_path = self.config_manager.get_template_image_path(removed_item["filename"])
                    if tpl_path and os.path.exists(tpl_path):
                        os.remove(tpl_path)
                        logger.info(f"Deleted template image file: {tpl_path}")
                    elif tpl_path:
                        logger.warning(f"Template file '{tpl_path}' not found for deletion, but removed from profile.")
                    else:
                        logger.warning(f"Could not resolve path for template '{removed_item['filename']}' during removal.")
                except OSError as e_os:
                    logger.error(f"OS error deleting template file '{removed_item['filename']}': {e_os.strerror}", exc_info=True)
                    messagebox.showwarning("File Deletion Error", f"Could not delete image '{removed_item['filename']}':\n{e_os.strerror}", parent=self)
        else:
            logger.warning(f"Cannot remove {list_name_key}: Invalid index {selected_idx} for list len {len(item_list)}.")

    def _remove_selected_region(self):
        if self.btn_remove_region:
            self._remove_selected_item("region", "regions", "selected_region_index", self.btn_remove_region, lambda item, idx: item.get("name", f"R_{idx}"))

    def _remove_selected_template(self):
        if self.btn_remove_template:
            self._remove_selected_item("template", "templates", "selected_template_index", self.btn_remove_template, lambda item, idx: f"{item.get('name')}({item.get('filename')})")

    def _remove_selected_rule(self):
        if self.btn_remove_rule:
            self._remove_selected_item("rule", "rules", "selected_rule_index", self.btn_remove_rule, lambda item, idx: item.get("name", f"Rule{idx}"))

    def _add_template(self):
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "Profile must be saved before adding templates. Save now?", parent=self) or not self._save_profile_as():
                return
            if not self.current_profile_path:
                logger.warning("Add template aborted: Profile not saved.")
                return
        if self._is_dirty and not self._prompt_save_if_dirty():
            return
        img_path = filedialog.askopenfilename(title="Select Template Image", filetypes=[("PNG/JPG", "*.png;*.jpg;*.jpeg"), ("All", "*.*")], parent=self)
        if not img_path:
            return
        name_dialog = ctk.CTkInputDialog(text="Enter unique name for this template:", title="Template Name")
        tpl_name_input = name_dialog.get_input()
        if not tpl_name_input or not tpl_name_input.strip():
            logger.info("Add template cancelled: No name.")
            return
        tpl_name = tpl_name_input.strip()
        if any(t.get("name") == tpl_name for t in self.profile_data.get("templates", [])):
            messagebox.showerror("Name Error", f"Template '{tpl_name}' already exists.", parent=self)
            return
        if not self.current_profile_path:
            messagebox.showerror("Error", "Profile path error for template.", parent=self)
            return

        profile_dir = os.path.dirname(self.current_profile_path)
        templates_subdir = os.path.join(profile_dir, TEMPLATES_SUBDIR_NAME)  # Use constant
        try:
            os.makedirs(templates_subdir, exist_ok=True)
            base_fn, ext = os.path.splitext(os.path.basename(img_path))
            sane_base = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in tpl_name).rstrip().replace(" ", "_")
            sane_base = sane_base or "template"
            target_fn = f"{sane_base}{ext}"
            target_path = os.path.join(templates_subdir, target_fn)
            counter = 1
            while os.path.exists(target_path):
                target_fn = f"{sane_base}_{counter}{ext}"
                target_path = os.path.join(templates_subdir, target_fn)
                counter += 1
            shutil.copy2(img_path, target_path)
            logger.info(f"Copied template from '{img_path}' to '{target_path}'.")
            new_tpl = {"name": tpl_name, "filename": target_fn, "comment": ""}
            self.profile_data.setdefault("templates", []).append(new_tpl)
            if self.templates_list_scroll_frame and self.btn_remove_template:
                self._populate_specific_list_frame(
                    "template", self.templates_list_scroll_frame, self.profile_data["templates"], lambda item, idx: f"{item.get('name')}({item.get('filename')})", self.btn_remove_template
                )
            self._set_dirty_status(True)
            messagebox.showinfo("Template Added", f"Template '{tpl_name}' ({target_fn}) added.", parent=self)
        except Exception as e:
            logger.error(f"Error adding template '{tpl_name}': {e}", exc_info=True)
            messagebox.showerror("Add Template Error", f"Could not add template '{tpl_name}':\n{e}", parent=self)

    def _add_new_rule(self):
        if not self.profile_data:
            self._new_profile(prompt_save=False)
        name_dialog = ctk.CTkInputDialog(text="Enter unique name for new rule:", title="New Rule Name")
        rule_name_input = name_dialog.get_input()
        if not rule_name_input or not rule_name_input.strip():
            logger.info("Add new rule cancelled: No name.")
            return
        rule_name = rule_name_input.strip()
        if any(r.get("name") == rule_name for r in self.profile_data.get("rules", [])):
            messagebox.showerror("Name Error", f"Rule name '{rule_name}' already exists.", parent=self)
            return
        new_rule = {
            "name": rule_name,
            "region": "",
            "condition": {"type": "always_true"},
            "action": {"type": "log_message", "message": f"Rule '{rule_name}' triggered.", "level": "INFO"},
            "comment": "",
        }
        self.profile_data.setdefault("rules", []).append(new_rule)
        if self.rules_list_scroll_frame and self.btn_remove_rule:
            self._populate_specific_list_frame("rule", self.rules_list_scroll_frame, self.profile_data["rules"], lambda item, idx: item.get("name", f"Rule{idx}"), self.btn_remove_rule)
        self._set_dirty_status(True)
        messagebox.showinfo("Rule Added", f"Rule '{rule_name}' added.", parent=self)

    def _on_rule_part_type_change(self, part_changed: str, new_type_selected: str):
        self._set_dirty_status(True)
        if self.selected_rule_index is None or self.details_panel_instance is None:
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules", []))):
            return
        current_rule_data_model = self.profile_data["rules"][self.selected_rule_index]
        logger.info(f"Rule part type change for rule '{current_rule_data_model.get('name')}': part '{part_changed}' to type '{new_type_selected}' in data model.")
        target_data_block: Optional[Dict] = None
        param_group_key_for_config = ""
        widget_prefix_for_dp = ""
        target_frame_in_dp: Optional[ctk.CTkFrame] = None
        if part_changed == "condition":
            param_group_key_for_config = "conditions"
            is_compound_in_model = "logical_operator" in current_rule_data_model.get("condition", {})
            if self.details_panel_instance.parent_app.selected_sub_condition_index is not None and is_compound_in_model:
                sub_conds = current_rule_data_model.get("condition", {}).get("sub_conditions", [])
                if 0 <= self.details_panel_instance.parent_app.selected_sub_condition_index < len(sub_conds):
                    target_data_block = sub_conds[self.details_panel_instance.parent_app.selected_sub_condition_index]
                    widget_prefix_for_dp = "subcond_"
                    target_frame_in_dp = self.details_panel_instance.sub_condition_params_frame
                else:
                    logger.error("Selected sub-condition index out of bounds.")
                    return
            elif not is_compound_in_model:
                target_data_block = current_rule_data_model.get("condition", {})
                widget_prefix_for_dp = "cond_"
                target_frame_in_dp = self.details_panel_instance.condition_params_frame
            else:
                logger.error("Cannot determine target condition block for type change.")
                return
        elif part_changed == "action":
            param_group_key_for_config = "actions"
            target_data_block = current_rule_data_model.get("action", {})
            widget_prefix_for_dp = "act_"
            target_frame_in_dp = self.details_panel_instance.action_params_frame
        else:
            logger.error(f"Unknown rule part '{part_changed}'.")
            return
        if target_data_block is not None and target_frame_in_dp is not None:
            if target_data_block.get("type") != new_type_selected:
                preserved_fields = {"type": new_type_selected}
                if param_group_key_for_config == "conditions" and "region" in target_data_block:
                    preserved_fields["region"] = target_data_block["region"]
                new_type_param_defs = UI_PARAM_CONFIG.get(param_group_key_for_config, {}).get(new_type_selected, [])
                if "capture_as" in target_data_block and any(p.get("id") == "capture_as" for p in new_type_param_defs):
                    preserved_fields["capture_as"] = target_data_block["capture_as"]
                target_data_block.clear()
                target_data_block.update(preserved_fields)
                logger.debug(f"Data model for '{part_changed}' (prefix '{widget_prefix_for_dp}') reset for new type '{new_type_selected}': {target_data_block}")
            self.details_panel_instance._render_dynamic_parameters(
                param_group_key_for_config, new_type_selected, target_data_block, target_frame_in_dp, start_row=1, widget_prefix=widget_prefix_for_dp
            )
            logger.info(f"DetailsPanel display for '{part_changed}' (prefix '{widget_prefix_for_dp}') updated for type '{new_type_selected}'.")
        else:
            logger.error(f"Could not find target data block or UI frame for '{part_changed}' type change to '{new_type_selected}'.")

    def _add_sub_condition_to_rule(self):
        if self.selected_rule_index is None or not (0 <= self.selected_rule_index < len(self.profile_data.get("rules", []))):
            return
        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})
        if "logical_operator" not in cond_block:
            current_single = copy.deepcopy(cond_block)
            cond_block.clear()
            cond_block["logical_operator"] = "AND"
            cond_block["sub_conditions"] = [current_single if current_single.get("type") else {"type": "always_true"}]
        cond_block.setdefault("sub_conditions", []).append({"type": "always_true"})
        rule["condition"] = cond_block
        self._set_dirty_status(True)
        if self.details_panel_instance:
            self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")
        logger.info(f"Added new sub-condition to rule '{rule.get('name')}'.")

    def _remove_selected_sub_condition(self):
        if self.selected_rule_index is None or self.details_panel_instance is None or self.details_panel_instance.parent_app.selected_sub_condition_index is None:
            return
        if not (0 <= self.selected_rule_index < len(self.profile_data.get("rules", []))):
            return
        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})
        sub_list = cond_block.get("sub_conditions")
        sel_sub_idx = self.details_panel_instance.parent_app.selected_sub_condition_index
        if sub_list and isinstance(sub_list, list) and 0 <= sel_sub_idx < len(sub_list):
            removed = sub_list.pop(sel_sub_idx)
            logger.info(f"Removed sub-cond at index {sel_sub_idx} (type: {removed.get('type')}) from rule '{rule.get('name')}'.")
            if len(sub_list) == 1 and messagebox.askyesno("Convert to Single?", "Only one sub-condition remains. Convert rule to single condition?", parent=self):
                rule["condition"] = copy.deepcopy(sub_list[0])
            elif not sub_list:
                rule["condition"] = {"type": "always_true"}
            self.details_panel_instance.parent_app.selected_sub_condition_index = None
            self._set_dirty_status(True)
            if self.details_panel_instance:
                self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")
        else:
            logger.warning(f"Cannot remove sub-cond: Invalid index {sel_sub_idx} or sub_conditions list error.")

    def _convert_condition_structure(self):
        if self.selected_rule_index is None or not (0 <= self.selected_rule_index < len(self.profile_data.get("rules", []))):
            return
        rule = self.profile_data["rules"][self.selected_rule_index]
        cond = rule.get("condition", {})
        is_compound = "logical_operator" in cond
        if is_compound:
            subs = cond.get("sub_conditions", [])
            new_single = copy.deepcopy(subs[0]) if subs else {"type": "always_true"}
            if len(subs) > 1 and not messagebox.askyesno("Confirm Conversion", "Convert to single condition? Only first sub-condition kept. Others lost. Continue?", parent=self):
                return
            rule["condition"] = new_single
        else:
            curr_single = copy.deepcopy(cond)
            rule["condition"] = {"logical_operator": "AND", "sub_conditions": [curr_single if curr_single.get("type") else {"type": "always_true"}]}
        if self.details_panel_instance:
            self.details_panel_instance.parent_app.selected_sub_condition_index = None
        self._set_dirty_status(True)
        if self.details_panel_instance:
            self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")
