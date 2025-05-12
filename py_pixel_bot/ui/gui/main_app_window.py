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
from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow  # Changed from relative
from py_pixel_bot.ui.gui.gui_config import DEFAULT_PROFILE_STRUCTURE, CONDITION_TYPES, ACTION_TYPES, UI_PARAM_CONFIG, OPTIONS_CONST_MAP  # Changed from relative
from py_pixel_bot.ui.gui.gui_utils import validate_and_get_widget_value, parse_bgr_string, create_clickable_list_item  # Changed from relative
from py_pixel_bot.ui.gui.panels.details_panel import DetailsPanel  # Changed from relative


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
        self.selected_sub_condition_index: Optional[int] = None  # This is for MainAppWindow's perspective

        self.selected_region_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_template_item_widget: Optional[ctk.CTkFrame] = None
        self.selected_rule_item_widget: Optional[ctk.CTkFrame] = None
        # Note: selected_sub_condition_item_widget is managed by DetailsPanel

        self.details_panel_instance: Optional[DetailsPanel] = None

        self._setup_ui()

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

        self.grid_columnconfigure(0, weight=1, minsize=300)
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
        self.label_current_profile_path.grid(row=3, column=0, columnspan=2, padx=5, pady=(5, 0), sticky="ew")

        rsf = ctk.CTkFrame(self.left_panel)
        rsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5, 5))
        rsf.grid_columnconfigure(0, weight=1)
        rsf.grid_rowconfigure(1, weight=1)
        current_row += 1
        ctk.CTkLabel(rsf, text="Regions", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0, 5), sticky="w")
        self.regions_list_scroll_frame = ctk.CTkScrollableFrame(rsf, label_text="")
        self.regions_list_scroll_frame.grid(row=1, column=0, sticky="nsew")
        rbf = ctk.CTkFrame(rsf, fg_color="transparent")
        rbf.grid(row=2, column=0, pady=(5, 0), sticky="ew")
        ctk.CTkButton(rbf, text="Add", width=60, command=self._add_region).pack(side="left", padx=2)
        self.btn_remove_region = ctk.CTkButton(rbf, text="Remove", width=70, command=self._remove_selected_region, state="disabled")
        self.btn_remove_region.pack(side="left", padx=2)

        tsf = ctk.CTkFrame(self.left_panel)
        tsf.grid(row=current_row, column=0, sticky="nsew", padx=10, pady=(5, 10))
        tsf.grid_columnconfigure(0, weight=1)
        tsf.grid_rowconfigure(1, weight=1)
        current_row += 1
        ctk.CTkLabel(tsf, text="Templates", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, pady=(0, 5), sticky="w")
        self.templates_list_scroll_frame = ctk.CTkScrollableFrame(tsf, label_text="")
        self.templates_list_scroll_frame.grid(row=1, column=0, sticky="nsew")
        tbf = ctk.CTkFrame(tsf, fg_color="transparent")
        tbf.grid(row=2, column=0, pady=(5, 0), sticky="ew")
        ctk.CTkButton(tbf, text="Add", width=60, command=self._add_template).pack(side="left", padx=2)
        self.btn_remove_template = ctk.CTkButton(tbf, text="Remove", width=70, command=self._remove_selected_template, state="disabled")
        self.btn_remove_template.pack(side="left", padx=2)

        self.left_panel.grid_rowconfigure(1, weight=1)  # Regions list frame
        self.left_panel.grid_rowconfigure(2, weight=1)  # Templates list frame

    def _setup_center_panel_content(self):
        self.center_panel.grid_columnconfigure(0, weight=1)
        self.center_panel.grid_rowconfigure(1, weight=1)  # Make the scrollable frame expand
        ctk.CTkLabel(self.center_panel, text="Rules", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.rules_list_scroll_frame = ctk.CTkScrollableFrame(self.center_panel, label_text="")
        self.rules_list_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        rbf2 = ctk.CTkFrame(self.center_panel, fg_color="transparent")
        rbf2.grid(row=2, column=0, pady=10, padx=10, sticky="ew")  # Added padx for consistency
        ctk.CTkButton(rbf2, text="Add New Rule", command=self._add_new_rule).pack(side="left", padx=5)
        self.btn_remove_rule = ctk.CTkButton(rbf2, text="Remove Selected Rule", command=self._remove_selected_rule, state="disabled")
        self.btn_remove_rule.pack(side="left", padx=5)

    def _new_profile(self, event=None, prompt_save=True):
        if prompt_save and not self._prompt_save_if_dirty():
            return
        self.current_profile_path = None
        self.profile_data = copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
        self._populate_ui_from_profile_data()
        self._set_dirty_status(False)  # New profile is not dirty initially
        if hasattr(self, "label_current_profile_path"):
            self.label_current_profile_path.configure(text="Path: New Profile (unsaved)")

    def _open_profile(self, event=None):
        if not self._prompt_save_if_dirty():
            return
        fp = filedialog.askopenfilename(title="Open Profile", defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if fp:
            self._load_profile_from_path(fp)

    def _load_profile_from_path(self, fp: str):
        try:
            cm = ConfigManager(fp)  # ConfigManager handles existence check and loading
            self.profile_data = cm.get_profile_data()
            if not self.profile_data:  # Should be caught by CM, but as safeguard
                raise ValueError("Loaded profile data is empty or invalid.")
            self.current_profile_path = cm.get_profile_path()
            self._populate_ui_from_profile_data()
            self._set_dirty_status(False)
            self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
            logger.info(f"Profile '{fp}' loaded and UI populated.")
        except Exception as e:
            logger.error(f"Failed to load profile '{fp}': {e}", exc_info=True)
            messagebox.showerror("Load Error", f"Could not load profile: {fp}\nError: {e}")

    def _save_profile(self, event=None) -> bool:
        if not self.current_profile_path:
            return self._save_profile_as()

        if not self._update_profile_data_from_ui():  # This updates basic settings
            logger.warning("Save profile aborted due to invalid basic settings.")
            return False
        # Rule/Region/Template data is modified directly in self.profile_data by their apply methods

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
            self.label_current_profile_path.configure(text=f"Path: {self.current_profile_path}")
            return self._save_profile()  # Now calls save with the new path
        return False

    def _populate_ui_from_profile_data(self):
        logger.debug("Populating UI from profile_data...")
        self.entry_profile_desc.delete(0, tk.END)
        self.entry_profile_desc.insert(0, self.profile_data.get("profile_description", ""))

        settings = self.profile_data.get("settings", {})
        self.entry_monitor_interval.delete(0, tk.END)
        self.entry_monitor_interval.insert(0, str(settings.get("monitoring_interval_seconds", 1.0)))
        self.entry_dominant_k.delete(0, tk.END)
        self.entry_dominant_k.insert(0, str(settings.get("analysis_dominant_colors_k", 3)))

        # Reset selections
        self.selected_region_index = None
        self.selected_template_index = None
        self.selected_rule_index = None
        self.selected_sub_condition_index = None  # Reset this too

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
            self.details_panel_instance.update_display(None, "none")  # Clear details panel

        logger.debug("UI population from profile_data complete.")

    def _populate_specific_list_frame(
        self, list_key_prefix: str, frame_widget: ctk.CTkScrollableFrame, items_data: List[Dict], display_text_cb: Callable, remove_button: Optional[ctk.CTkButton], item_type_str: str
    ):
        for widget in frame_widget.winfo_children():  # Clear existing items
            widget.destroy()

        # Reset the main window's tracking of the selected widget for this list
        setattr(self, f"selected_{list_key_prefix}_item_widget", None)
        # setattr(self, f"selected_{list_key_prefix}_index", None) # Done in _populate_ui_from_profile_data

        if remove_button:
            remove_button.configure(state="disabled")

        for i, item_d in enumerate(items_data):
            text = display_text_cb(item_d, i)
            item_frame_container = {}  # To pass the frame by reference into lambda
            # Create item and bind click, passing item_d (from profile_data) and index i
            item_f = create_clickable_list_item(
                frame_widget,
                text,
                lambda e=None, item_type=item_type_str, data=item_d, index=i, frame_cont=item_frame_container: self._on_item_selected(item_type, data, index, frame_cont.get("frame")),
            )
            item_frame_container["frame"] = item_f  # Store the created frame in the container

    def _update_profile_data_from_ui(self) -> bool:
        """Updates basic profile settings from UI to self.profile_data. Returns success."""
        logger.debug("Updating profile_data from basic UI settings...")
        desc_val, desc_valid = validate_and_get_widget_value(
            self.entry_profile_desc, None, "Profile Description", str, self.profile_data.get("profile_description", ""), required=False, allow_empty_string=True
        )
        if desc_valid:
            self.profile_data["profile_description"] = desc_val
        # No else needed as it's not strictly required to be valid to save other parts

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
        if resp is True:  # Yes
            return self._save_profile()
        elif resp is False:  # No
            return True  # Proceed without saving
        else:  # Cancel
            return False  # Do not proceed

    def _on_close_window(self, event=None):
        if self._prompt_save_if_dirty():
            logger.info("Exiting MainAppWindow.")
            self.destroy()

    def _on_item_selected(self, list_name: str, item_data: Dict, item_index: int, item_widget_frame: Optional[ctk.CTkFrame]):
        # list_name: "region", "template", or "rule"
        # item_data: The dictionary for the selected item from self.profile_data
        # item_index: The index in the list
        # item_widget_frame: The CTkFrame representing the item in the list UI
        if not item_widget_frame:
            logger.warning(f"Item selection called for {list_name} but item_widget_frame is None. Aborting selection update.")
            return

        logger.info(f"Item selected: {list_name}, index {item_index}, name '{item_data.get('name')}'")

        # Clear selection highlights and disable remove buttons for OTHER lists
        lists_to_clear_state = {
            "region": (self.btn_remove_region, "selected_region_index", "selected_region_item_widget"),
            "template": (self.btn_remove_template, "selected_template_index", "selected_template_item_widget"),
            "rule": (self.btn_remove_rule, "selected_rule_index", "selected_rule_item_widget"),
        }

        for ln, (btn, idx_attr, widget_attr) in lists_to_clear_state.items():
            if ln != list_name:  # If it's not the currently selected list type
                self._highlight_selected_list_item(ln, None)  # Clear its highlight
                setattr(self, idx_attr, None)  # Reset its index
                if btn:
                    btn.configure(state="disabled")

        # If a rule is selected, also clear sub-condition selection in DetailsPanel
        if list_name == "rule" and self.details_panel_instance:
            self.selected_sub_condition_index = None  # Reset MainAppWindow's tracking
            # Call MainAppWindow's _highlight_selected_list_item, specifying it's for a sub-list
            # This will correctly target attributes on self.details_panel_instance
            self._highlight_selected_list_item("condition", None, is_sub_list=True)  # CORRECTED CALL
            if self.details_panel_instance.btn_remove_sub_condition:
                self.details_panel_instance.btn_remove_sub_condition.configure(state="disabled")

        # Set current selection for THIS list type
        setattr(self, lists_to_clear_state[list_name][1], item_index)  # Update index attribute
        self._highlight_selected_list_item(list_name, item_widget_frame)  # Highlight current item

        current_btn = lists_to_clear_state[list_name][0]
        if current_btn:
            current_btn.configure(state="normal")  # Enable its remove button

        # Update the details panel
        if self.details_panel_instance:
            self.details_panel_instance.update_display(copy.deepcopy(item_data), list_name)

    def _highlight_selected_list_item(self, list_name_for_attr: str, new_selected_widget: Optional[ctk.CTkFrame], is_sub_list: bool = False):
        # list_name_for_attr: "region", "template", "rule", or "condition" (for sub-conditions)
        # is_sub_list: True if this is for a sub-list like sub-conditions (managed by DetailsPanel)

        attr_name_prefix = "selected_sub_" if is_sub_list else "selected_"
        # For sub-conditions, list_name_for_attr will be "condition"
        # leading to "selected_sub_condition_item_widget"
        attr_name_widget = f"{attr_name_prefix}{list_name_for_attr}_item_widget"

        # Determine where the attribute (e.g., self.selected_rule_item_widget or self.details_panel_instance.selected_sub_condition_item_widget) is stored
        attr_target_object = self.details_panel_instance if is_sub_list and self.details_panel_instance else self

        old_selected_widget = getattr(attr_target_object, attr_name_widget, None)
        if old_selected_widget and old_selected_widget.winfo_exists():
            old_selected_widget.configure(fg_color="transparent")  # Revert old selection

        if new_selected_widget and new_selected_widget.winfo_exists():
            highlight_color = ctk.ThemeManager.theme.get("CTkSegmentedButton", {}).get("selected_color", ("#3a7ebf", "#1f538d"))  # Default CustomTkinter selection color
            new_selected_widget.configure(fg_color=highlight_color)
            setattr(attr_target_object, attr_name_widget, new_selected_widget)  # Store new selection
        else:  # Clearing selection
            setattr(attr_target_object, attr_name_widget, None)

    def _apply_region_changes(self):
        if self.selected_region_index is None or self.details_panel_instance is None:
            logger.warning("Apply region changes called but no region selected or details panel missing.")
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
            min_v = 1 if p in ["width", "height"] else None  # Width/Height must be positive
            default_coord_val = current_region_data.get(p, 0 if p in ["x", "y"] else 1)
            val, valid = validate_and_get_widget_value(coord_widget, None, p.capitalize(), int, default_coord_val, required=True, min_val=min_v)
            if not valid:
                all_valid = False
            else:
                new_values[p] = val

        if not all_valid:
            logger.error(f"Apply changes for region '{original_name}' aborted due to validation errors.")
            return

        # Check for name collision if name changed
        if new_values["name"] != original_name and any(r.get("name") == new_values["name"] for i, r in enumerate(self.profile_data["regions"]) if i != self.selected_region_index):
            messagebox.showerror("Name Error", f"Region name '{new_values['name']}' already exists.")
            return

        # Update the profile data
        current_region_data.update(new_values)
        self._set_dirty_status(True)
        self._populate_specific_list_frame(
            "region", self.regions_list_scroll_frame, self.profile_data["regions"], lambda item_data, idx: item_data.get("name", f"R{idx+1}"), self.btn_remove_region, "region"
        )
        # Re-display the (potentially updated) details and re-highlight
        if self.selected_region_index < len(self.profile_data["regions"]):  # Check index still valid
            new_item_widget = self.regions_list_scroll_frame.winfo_children()[self.selected_region_index] if self.regions_list_scroll_frame.winfo_children() else None
            self._highlight_selected_list_item("region", new_item_widget)  # Re-highlight, as frames are recreated
            self.details_panel_instance.update_display(copy.deepcopy(current_region_data), "region")

        messagebox.showinfo("Region Updated", f"Region '{new_values['name']}' updated successfully.")

    def _apply_template_changes(self):
        if self.selected_template_index is None or self.details_panel_instance is None:
            logger.warning("Apply template changes called but no template selected or details panel missing.")
            return
        current_template_data = self.profile_data["templates"][self.selected_template_index]
        original_name = current_template_data.get("name")
        logger.info(f"Applying changes for template: {original_name} (index {self.selected_template_index})")

        name_widget = self.details_panel_instance.detail_widgets.get("template_name")
        name_val, name_valid = validate_and_get_widget_value(name_widget, None, "Template Name", str, original_name, required=True)

        if not name_valid:
            return

        # Check for name collision if name changed
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
            new_item_widget = self.templates_list_scroll_frame.winfo_children()[self.selected_template_index] if self.templates_list_scroll_frame.winfo_children() else None
            self._highlight_selected_list_item("template", new_item_widget)
            self.details_panel_instance.update_display(copy.deepcopy(current_template_data), "template")
        messagebox.showinfo("Template Updated", f"Template '{name_val}' updated successfully.")

    def _apply_rule_changes(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning("Apply rule changes called but no rule selected or details panel missing.")
            return

        current_rule_data_orig = self.profile_data["rules"][self.selected_rule_index]
        old_name = current_rule_data_orig.get("name")
        logger.info(f"Attempting to apply changes for rule: '{old_name}' (index {self.selected_rule_index})")

        # Create a temporary copy to gather changes without modifying original until all valid
        temp_rule_data_for_validation = copy.deepcopy(current_rule_data_orig)

        # 1. Validate and get Rule Name
        name_widget = self.details_panel_instance.detail_widgets.get("rule_name")
        new_name, name_valid = validate_and_get_widget_value(name_widget, None, "Rule Name", str, old_name, required=True)
        if not name_valid:
            return
        if new_name != old_name and any(r.get("name") == new_name for i, r in enumerate(self.profile_data["rules"]) if i != self.selected_rule_index):
            messagebox.showerror("Name Error", f"Rule name '{new_name}' already exists.")
            return
        temp_rule_data_for_validation["name"] = new_name

        # 2. Get Default Rule Region
        rule_region_var = self.details_panel_instance.detail_optionmenu_vars.get("rule_region_var")
        temp_rule_data_for_validation["region"] = rule_region_var.get() if rule_region_var else ""

        # 3. Validate and get Condition block
        condition_block_ui = {}  # This will hold the condition data read from UI
        is_compound_in_ui = "logical_operator_var" in self.details_panel_instance.detail_optionmenu_vars

        if is_compound_in_ui:
            log_op_var = self.details_panel_instance.detail_optionmenu_vars.get("logical_operator_var")
            condition_block_ui["logical_operator"] = log_op_var.get() if log_op_var else "AND"

            new_sub_conds_from_ui = []
            existing_sub_conds_in_profile = temp_rule_data_for_validation.get("condition", {}).get("sub_conditions", [])

            all_subs_valid = True
            for idx, _ in enumerate(existing_sub_conds_in_profile):  # Iterate based on current number of sub-conditions in profile
                if self.selected_sub_condition_index == idx:  # If this sub-condition is currently active in editor
                    sub_c_type_var = self.details_panel_instance.detail_optionmenu_vars.get("subcond_condition_type_var")
                    if sub_c_type_var:
                        sub_c_type = sub_c_type_var.get()
                        sub_params = self.details_panel_instance._get_parameters_from_ui("conditions", sub_c_type, "subcond_")
                        if sub_params is None:  # Validation failed within _get_parameters_from_ui
                            all_subs_valid = False
                            break
                        new_sub_conds_from_ui.append(sub_params)
                    else:  # Should not happen if UI is consistent
                        logger.error(f"Missing type var for active sub-condition index {idx}. Aborting apply.")
                        all_subs_valid = False
                        break
                else:  # For sub-conditions not actively being edited, take their data directly from profile
                    new_sub_conds_from_ui.append(copy.deepcopy(existing_sub_conds_in_profile[idx]))

            if not all_subs_valid:
                logger.error("Rule apply aborted: Sub-condition validation failed.")
                return
            condition_block_ui["sub_conditions"] = new_sub_conds_from_ui
        else:  # Single condition
            cond_type_var = self.details_panel_instance.detail_optionmenu_vars.get("condition_type_var")
            single_cond_type = cond_type_var.get() if cond_type_var else "always_true"
            single_cond_params = self.details_panel_instance._get_parameters_from_ui("conditions", single_cond_type, "cond_")
            if single_cond_params is None:  # Validation failed
                logger.error("Rule apply aborted: Single condition validation failed.")
                return
            condition_block_ui = single_cond_params  # This will be the whole condition block

        temp_rule_data_for_validation["condition"] = condition_block_ui

        # 4. Validate and get Action block
        action_type_var = self.details_panel_instance.detail_optionmenu_vars.get("action_type_var")
        action_type = action_type_var.get() if action_type_var else "log_message"
        action_params = self.details_panel_instance._get_parameters_from_ui("actions", action_type, "act_")
        if action_params is None:  # Validation failed
            logger.error("Rule apply aborted: Action validation failed.")
            return
        temp_rule_data_for_validation["action"] = action_params

        # All validations passed, now commit to self.profile_data
        self.profile_data["rules"][self.selected_rule_index] = temp_rule_data_for_validation
        self._set_dirty_status(True)

        # Repopulate list and re-display details
        self._populate_specific_list_frame(
            "rule", self.rules_list_scroll_frame, self.profile_data["rules"], lambda item_data, idx: item_data.get("name", f"Rule{idx+1}"), self.btn_remove_rule, "rule"
        )
        if self.selected_rule_index < len(self.profile_data["rules"]):  # Check index still valid
            new_item_widget = self.rules_list_scroll_frame.winfo_children()[self.selected_rule_index] if self.rules_list_scroll_frame.winfo_children() else None
            self._highlight_selected_list_item("rule", new_item_widget)
            self.details_panel_instance.update_display(copy.deepcopy(temp_rule_data_for_validation), "rule")

        messagebox.showinfo("Rule Updated", f"Rule '{new_name}' updated successfully.")

    def _edit_region_coordinates_with_selector(self):
        if self.selected_region_index is None:
            logger.warning("Edit region coords called but no region selected.")
            return

        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Current profile has unsaved changes. Save before launching Region Selector?"):
                return  # User cancelled
            if not self._save_profile():  # Attempt to save failed
                logger.warning("Save failed. Aborting region coordinate editing.")
                return

        if not self.current_profile_path:
            messagebox.showerror("Error", "Profile must be saved to a file before editing region coordinates with selector.")
            return

        try:
            # Use a fresh ConfigManager for the selector to ensure it reads the saved state
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data:  # Should not happen if save was successful
                messagebox.showerror("Error", "Failed to re-load profile for Region Selector.")
                return

            # Pass a copy of the region data to be edited
            region_to_edit_data = copy.deepcopy(self.profile_data["regions"][self.selected_region_index])

            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector, existing_region_data=region_to_edit_data)
            self.wait_window(selector_dialog)  # Modal behavior

            if selector_dialog.changes_made:
                logger.info("RegionSelector made changes. Reloading profile into MainAppWindow.")
                # Reload the entire profile as RegionSelector modifies it directly
                self._load_profile_from_path(self.current_profile_path)
                self._set_dirty_status(True)  # Mark as dirty as it was reloaded
            else:
                logger.info("RegionSelector closed without making changes.")

        except Exception as e:
            logger.error(f"Error during Edit Region Coordinates: {e}", exc_info=True)
            messagebox.showerror("Region Selector Error", f"Error launching or using Region Selector:\n{e}")

    def _add_region(self):
        if not self.current_profile_path:
            if not messagebox.askokcancel("Save Required", "The profile must be saved to a file before adding regions. Save now?"):
                return
            if not self._save_profile_as():  # Prompts for path and saves
                return  # Save As was cancelled or failed

        if self._is_dirty:
            if not messagebox.askyesno("Save Changes?", "Current profile has unsaved changes. Save before launching Region Selector?"):
                return
            if not self._save_profile():  # Save to current path
                return

        try:
            cm_for_selector = ConfigManager(self.current_profile_path, create_if_missing=False)
            if not cm_for_selector.profile_data:
                messagebox.showerror("Error", "Failed to re-load profile for Region Selector.")
                return

            selector_dialog = RegionSelectorWindow(master=self, config_manager=cm_for_selector)
            self.wait_window(selector_dialog)  # Modal

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

            # Determine display callback for repopulating the list
            list_scroll_frame = getattr(self, f"{list_name_key}s_list_scroll_frame", None)
            display_cb_map = {
                "region": lambda item, idx: item.get("name", f"R{idx+1}"),
                "template": lambda item, idx: f"{item.get('name', 'T_NoName')} ({item.get('filename', 'F_NoName')})",
                "rule": lambda item, idx: item.get("name", f"Rule{idx+1}"),
            }
            display_cb = display_cb_map.get(list_name_key)

            if list_scroll_frame and display_cb and remove_button_widget:
                self._populate_specific_list_frame(list_name_key, list_scroll_frame, item_list, display_cb, remove_button_widget, list_name_key)

            self._set_dirty_status(True)
            setattr(self, selected_index_attr, None)  # Clear selection index
            if remove_button_widget:
                remove_button_widget.configure(state="disabled")
            if self.details_panel_instance:
                self.details_panel_instance.update_display(None, "none")  # Clear details

            # Special handling for template file deletion
            if list_name_key == "template" and self.current_profile_path:
                filename_to_delete = removed_item_data.get("filename")
                if filename_to_delete:
                    template_file_path = os.path.join(os.path.dirname(self.current_profile_path), "templates", filename_to_delete)
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

        if self._is_dirty:
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
            # Sanitize tpl_name for use as part of filename
            sane_base_for_filename = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in tpl_name).rstrip().replace(" ", "_")
            if not sane_base_for_filename:
                sane_base_for_filename = "template"  # Fallback

            target_filename = f"{sane_base_for_filename}{ext}"
            target_path = os.path.join(templates_dir, target_filename)

            counter = 1
            while os.path.exists(target_path):  # Ensure unique filename
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
        if not self.profile_data:  # Should not happen if UI is functional
            self._new_profile(prompt_save=False)  # Initialize with default structure

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
            "region": "",  # Default to no specific region, user can set
            "condition": {"type": "always_true"},  # Sensible default condition
            "action": {"type": "log_message", "message": f"Rule '{rule_name}' triggered.", "level": "INFO"},  # Sensible default action
        }
        self.profile_data.setdefault("rules", []).append(new_rule_data)
        self._populate_specific_list_frame(
            "rule", self.rules_list_scroll_frame, self.profile_data["rules"], lambda item_data, idx: item_data.get("name", f"Rule{idx+1}"), self.btn_remove_rule, "rule"
        )
        self._set_dirty_status(True)
        messagebox.showinfo("Rule Added", f"Rule '{rule_name}' added successfully.")

    def _on_rule_part_type_change(self, part_changed: str, new_type_selected: str):
        # part_changed: "condition" or "action"
        # This method is called when a type dropdown (condition or action) changes.
        # It should update the internal data model for the *currently selected rule*
        # and then re-render the dynamic parameters in the DetailsPanel.
        self._set_dirty_status(True)
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning(f"Cannot handle rule part type change: No rule selected or details panel missing.")
            return

        current_rule_data = self.profile_data["rules"][self.selected_rule_index]
        logger.info(f"Rule part type change for rule '{current_rule_data.get('name')}': part '{part_changed}' to type '{new_type_selected}'")

        if part_changed == "condition":
            target_frame_for_params: Optional[ctk.CTkFrame] = None
            condition_data_source_in_profile: Optional[Dict] = None  # This is the dict in self.profile_data
            widget_prefix = ""

            is_compound = "logical_operator" in current_rule_data.get("condition", {})

            if self.selected_sub_condition_index is not None and is_compound:
                # Editing an existing sub-condition's type
                sub_cond_list = current_rule_data.get("condition", {}).get("sub_conditions", [])
                if 0 <= self.selected_sub_condition_index < len(sub_cond_list):
                    condition_data_source_in_profile = sub_cond_list[self.selected_sub_condition_index]
                    target_frame_for_params = self.details_panel_instance.sub_condition_params_frame
                    widget_prefix = "subcond_"
                else:
                    logger.error("Selected sub-condition index out of bounds. Cannot change type.")
                    return
            elif not is_compound:  # Editing the main single condition's type
                condition_data_source_in_profile = current_rule_data.get("condition", {})
                target_frame_for_params = self.details_panel_instance.condition_params_frame
                widget_prefix = "cond_"
            else:
                logger.error("Cannot determine which condition part to change type for (compound rule but no sub-condition selected).")
                return  # Should not happen if UI logic is correct

            if target_frame_for_params and condition_data_source_in_profile is not None:
                if condition_data_source_in_profile.get("type") != new_type_selected:
                    # Preserve common fields if they exist in the old structure, otherwise clear them
                    preserved_data = {"type": new_type_selected}
                    # Common fields for conditions that might be worth preserving:
                    if "region" in condition_data_source_in_profile:
                        preserved_data["region"] = condition_data_source_in_profile["region"]
                    if "capture_as" in condition_data_source_in_profile:
                        preserved_data["capture_as"] = condition_data_source_in_profile["capture_as"]

                    condition_data_source_in_profile.clear()  # Clear old params
                    condition_data_source_in_profile.update(preserved_data)  # Set new type and preserved fields
                    logger.debug(f"Condition part data (in profile_data) reset for new type '{new_type_selected}': {condition_data_source_in_profile}")

                # Re-render parameters for this condition part using the (now updated) data_source
                self.details_panel_instance._render_dynamic_parameters(
                    "conditions", new_type_selected, condition_data_source_in_profile, target_frame_for_params, start_row=1, widget_prefix=widget_prefix
                )
            else:
                logger.error("Could not find target frame or data source for condition type change.")

        elif part_changed == "action":
            action_to_update_in_profile = current_rule_data.get("action", {})
            if action_to_update_in_profile.get("type") != new_type_selected:
                action_to_update_in_profile.clear()  # Clear old params
            action_to_update_in_profile["type"] = new_type_selected  # Set new type
            logger.debug(f"Action part data (in profile_data) reset for new type '{new_type_selected}': {action_to_update_in_profile}")

            if self.details_panel_instance and self.details_panel_instance.action_params_frame:
                self.details_panel_instance._render_dynamic_parameters(
                    "actions", new_type_selected, action_to_update_in_profile, self.details_panel_instance.action_params_frame, start_row=1, widget_prefix="act_"  # Use updated data from profile
                )
            else:
                logger.error("Could not find action_params_frame for action type change.")

        logger.info(f"Rule part '{part_changed}' type in profile_data model updated to '{new_type_selected}'. DetailsPanel should refresh based on this.")

    def _add_sub_condition_to_rule(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning("Cannot add sub-condition: No rule selected or details panel missing.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})

        if "logical_operator" not in cond_block:  # If it was a single condition
            current_single_cond_data = copy.deepcopy(cond_block)
            cond_block.clear()  # Clear the single condition structure
            cond_block["logical_operator"] = "AND"  # Default to AND
            cond_block["sub_conditions"] = [current_single_cond_data if current_single_cond_data.get("type") else {"type": "always_true"}]

        # Ensure sub_conditions list exists
        cond_block.setdefault("sub_conditions", [])

        # Add a new default sub-condition
        cond_block["sub_conditions"].append({"type": "always_true"})

        rule["condition"] = cond_block  # Update the rule's condition block
        self._set_dirty_status(True)

        # Update the display; this will re-render the condition editor for the rule
        self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")
        logger.info(f"Added new sub-condition to rule '{rule.get('name')}'.")

    def _remove_selected_sub_condition(self):
        if self.selected_rule_index is None or self.selected_sub_condition_index is None or self.details_panel_instance is None:
            logger.warning("Cannot remove sub-condition: No rule or sub-condition selected, or details panel missing.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        cond_block = rule.get("condition", {})
        sub_list = cond_block.get("sub_conditions")

        if sub_list and 0 <= self.selected_sub_condition_index < len(sub_list):
            removed_sub_cond = sub_list.pop(self.selected_sub_condition_index)
            logger.info(f"Removed sub-condition at index {self.selected_sub_condition_index} (type: {removed_sub_cond.get('type')}) from rule '{rule.get('name')}'.")

            self.selected_sub_condition_index = None  # Clear selection
            self._set_dirty_status(True)

            # Update the display; this will re-render the condition editor
            self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")
        else:
            logger.warning(f"Cannot remove sub-condition: Invalid index {self.selected_sub_condition_index} or sub_conditions list not found/empty.")

    def _convert_condition_structure(self):
        if self.selected_rule_index is None or self.details_panel_instance is None:
            logger.warning("Cannot convert condition structure: No rule selected or details panel missing.")
            return

        rule = self.profile_data["rules"][self.selected_rule_index]
        cond = rule.get("condition", {})
        is_currently_compound = "logical_operator" in cond

        if is_currently_compound:  # Convert to Single
            sub_conditions_list = cond.get("sub_conditions", [])
            if len(sub_conditions_list) > 1:
                if not messagebox.askyesno("Confirm Conversion", "Convert to a single condition? Only the first sub-condition will be kept. Others will be lost. Continue?"):
                    return

            # Take the first sub-condition as the new single condition, or a default if none
            new_single_condition = copy.deepcopy(sub_conditions_list[0]) if sub_conditions_list else {"type": "always_true"}
            rule["condition"] = new_single_condition
            logger.info(f"Rule '{rule.get('name')}' condition converted from compound to single: {new_single_condition}")

        else:  # Convert to Compound
            current_single_condition_data = copy.deepcopy(cond)
            if not current_single_condition_data.get("type"):  # Ensure it has a type if it was empty
                current_single_condition_data = {"type": "always_true"}

            rule["condition"] = {"logical_operator": "AND", "sub_conditions": [current_single_condition_data]}  # Default to AND
            logger.info(f"Rule '{rule.get('name')}' condition converted from single to compound. Original single: {current_single_condition_data}")

        self._set_dirty_status(True)
        self.selected_sub_condition_index = None  # Reset sub-condition selection

        # Re-render the details for the rule
        self.details_panel_instance.update_display(copy.deepcopy(rule), "rule")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # Ensure APP_ENV is set for logging_setup if it's called implicitly by other modules
    if "APP_ENV" not in os.environ:
        os.environ["APP_ENV"] = "development"

    ctk.set_appearance_mode("System")  # or "Light", "Dark"
    ctk.set_default_color_theme("blue")  # or "green", "dark-blue"

    app = MainAppWindow()
    app.mainloop()
