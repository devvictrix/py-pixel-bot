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
# This relies on __main__.py or PYTHONPATH correctly setting up 'src' directory.
from py_pixel_bot.core.config_manager import ConfigManager
from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow 

logger = logging.getLogger(__name__) # Logger for this module: py_pixel_bot.ui.gui.main_app_window

# --- Constants ---
DEFAULT_PROFILE_STRUCTURE = {
    "profile_description": "New Profile",
    "settings": {
        "monitoring_interval_seconds": 1.0, 
        "analysis_dominant_colors_k": 3,
        "tesseract_cmd_path": None, # Optional: Path to tesseract executable
        "tesseract_config_custom": ""  # Optional: Custom tesseract config string
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
LOGICAL_OPERATORS = ["AND", "OR"] # For compound conditions
CLICK_TARGET_RELATIONS = ["center_of_region", "center_of_last_match", "absolute", "relative_to_region"]
CLICK_BUTTONS = ["left", "middle", "right"]
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class MainAppWindow(ctk.CTk):
    """
    Main application window for the PyPixelBot Profile Editor GUI.
    Manages profile loading, saving, and editing of all components including
    settings, regions, templates, and rules (with conditions, actions, and parameters).
    Implements input validation for user-editable fields.
    """
    def __init__(self, initial_profile_path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        logger.info("Initializing MainAppWindow...")
        self.title("PyPixelBot Profile Editor")
        self.geometry("1350x800") # Adjusted size for better layout

        # Ensure CTk settings are applied early
        ctk.set_appearance_mode("System") # Options: "System", "Dark", "Light"
        ctk.set_default_color_theme("blue") # Options: "blue", "green", "dark-blue"

        # Profile data and state
        self.current_profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = self._get_default_profile_structure()
        self._is_dirty: bool = False 
        
        # Selected item indices for lists
        self.selected_region_index: Optional[int] = None
        self.selected_template_index: Optional[int] = None
        self.selected_rule_index: Optional[int] = None
        self.selected_sub_condition_index: Optional[int] = None 
        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None # For sub-condition highlight

        # UI Widget Storage for dynamic elements (primarily in details panel)
        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {} 
        self.detail_optionmenu_vars: Dict[str, tk.StringVar] = {} # For CTkOptionMenu selected values
        
        # Specific UI elements that need direct reference
        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None
        self.condition_params_frame: Optional[ctk.CTkFrame] = None 
        self.action_params_frame: Optional[ctk.CTkFrame] = None
        self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None
        self.btn_convert_condition: Optional[ctk.CTkButton] = None
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None

        self._setup_ui() # Build the static parts of the UI

        # Load initial profile or set up a new one
        if initial_profile_path:
            logger.info(f"Attempting to load initial profile: {initial_profile_path}")
            self._load_profile_from_path(initial_profile_path) # This calls _populate_ui and resets dirty
        else:
            self._populate_ui_from_profile_data() # Populate with default empty profile
            self._set_dirty_status(False) # New profile isn't dirty initially
            self.label_current_profile_path.configure(text="Path: New Profile (unsaved)")

        self.protocol("WM_DELETE_WINDOW", self._on_close_window) # Handle window close (X button)
        logger.info("MainAppWindow initialization complete.")

    # --- Helper Methods ---
    def _get_default_profile_structure(self) -> Dict[str, Any]:
        """Returns a deep copy of the default profile structure to avoid shared mutable state."""
        return copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)

    def _create_clickable_list_item(self, parent_frame: ctk.CTkScrollableFrame, text: str, on_click_callback: Callable) -> ctk.CTkFrame:
        """Helper to create a clickable item (label within a frame) in a scrollable list."""
        item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent", corner_radius=0)
        item_frame.pack(fill="x", pady=1, padx=1) # Small padding between items
        
        label = ctk.CTkLabel(item_frame, text=text, anchor="w", cursor="hand2")
        label.pack(side="left", fill="x", expand=True, padx=5, pady=2)
        
        # Bind click to both label and frame for better click target
        label.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
        item_frame.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
        return item_frame

    def _highlight_selected_list_item(self, list_name_for_attr: str, new_selected_widget: Optional[ctk.CTkFrame], is_sub_list: bool = False):
        """Manages highlighting for selected items in main lists or sub-lists."""
        attr_name_prefix = "selected_sub_" if is_sub_list else "selected_"
        attr_name = f"{attr_name_prefix}{list_name_for_attr}_item_widget"
        
        old_selected_widget = getattr(self, attr_name, None)
        if old_selected_widget and old_selected_widget.winfo_exists(): # Check if widget still exists
            old_selected_widget.configure(fg_color="transparent") 
        
        if new_selected_widget and new_selected_widget.winfo_exists():
            new_selected_widget.configure(fg_color=("#DBDBDB", "#2B2B2B")) # Standard CTk selection colors
            setattr(self, attr_name, new_selected_widget)
        else: 
            setattr(self, attr_name, None) # Clear if new widget is None or doesn't exist

    def _clear_details_panel_content(self):
        """Clears all dynamically added widgets from the main details panel's content frame."""
        if hasattr(self, 'details_panel_content_frame') and self.details_panel_content_frame:
            for widget in self.details_panel_content_frame.winfo_children():
                widget.destroy()
        self.detail_widgets.clear() # Clear references to dynamic input widgets
        self.detail_optionmenu_vars.clear() # Clear stored StringVars for OptionMenus
        
        # Explicitly destroy specific complex widgets if they exist
        if self.template_preview_image_label: self.template_preview_image_label.destroy(); self.template_preview_image_label = None
        if self.sub_conditions_list_frame: self.sub_conditions_list_frame.destroy(); self.sub_conditions_list_frame = None
        if self.condition_params_frame: self.condition_params_frame.destroy(); self.condition_params_frame = None
        if self.action_params_frame: self.action_params_frame.destroy(); self.action_params_frame = None
        if self.sub_condition_params_frame: self.sub_condition_params_frame.destroy(); self.sub_condition_params_frame = None
        
        logger.debug("Cleared details panel content and dynamic widget references.")

    # --- UI Setup Methods ---
    def _setup_ui(self): # (Menu setup and main layout grid)
        logger.debug("Setting up static UI components (Menu, Panels)...")
        self.menu_bar=tk.Menu(self); self.config(menu=self.menu_bar) 
        file_menu=tk.Menu(self.menu_bar,tearoff=0); self.menu_bar.add_cascade(label="File",menu=file_menu)
        file_menu.add_command(label="New Profile",command=self._new_profile,accelerator="Ctrl+N")
        file_menu.add_command(label="Open Profile...",command=self._open_profile,accelerator="Ctrl+O")
        file_menu.add_separator(); file_menu.add_command(label="Save Profile",command=self._save_profile,accelerator="Ctrl+S")
        file_menu.add_command(label="Save Profile As...",command=self._save_profile_as,accelerator="Ctrl+Shift+S")
        file_menu.add_separator();file_menu.add_command(label="Exit",command=self._on_close_window)
        
        self.bind_all("<Control-n>", lambda e: self._new_profile())
        self.bind_all("<Control-o>", lambda e: self._open_profile())
        self.bind_all("<Control-s>", lambda e: self._save_profile())
        self.bind_all("<Control-Shift-S>", lambda e: self._save_profile_as())
                
        self.grid_columnconfigure(0, weight=1, minsize=300) 
        self.grid_columnconfigure(1, weight=2, minsize=350) 
        self.grid_columnconfigure(2, weight=2, minsize=400) 
        self.grid_rowconfigure(0, weight=1)    
        
        self.left_panel=ctk.CTkFrame(self,corner_radius=0); self.left_panel.grid(row=0,column=0,sticky="nsew",padx=(0,2),pady=0); self._setup_left_panel()
        self.center_panel=ctk.CTkFrame(self,corner_radius=0); self.center_panel.grid(row=0,column=1,sticky="nsew",padx=(0,2),pady=0); self._setup_center_panel()
        self.right_panel=ctk.CTkFrame(self,corner_radius=0); self.right_panel.grid(row=0,column=2,sticky="nsew",pady=0); self._setup_right_panel()
        logger.debug("Static UI components (Menu, Panels) setup complete.")

    def _setup_left_panel(self): # (Profile info, Regions list, Templates list)
        self.left_panel.grid_columnconfigure(0,weight=1); current_row=0
        pif=ctk.CTkFrame(self.left_panel);pif.grid(row=current_row,column=0,sticky="new",padx=10,pady=10);pif.grid_columnconfigure(1,weight=1);current_row+=1
        ctk.CTkLabel(pif,text="Desc:").grid(row=0,column=0,padx=5,pady=5,sticky="w");self.entry_profile_desc=ctk.CTkEntry(pif,placeholder_text="Profile description");self.entry_profile_desc.grid(row=0,column=1,padx=5,pady=5,sticky="ew");self.entry_profile_desc.bind("<KeyRelease>",lambda e:self._set_dirty_status(True))
        ctk.CTkLabel(pif,text="Interval(s):").grid(row=1,column=0,padx=5,pady=5,sticky="w");self.entry_monitor_interval=ctk.CTkEntry(pif,placeholder_text="1.0");self.entry_monitor_interval.grid(row=1,column=1,padx=5,pady=5,sticky="ew");self.entry_monitor_interval.bind("<KeyRelease>",lambda e:self._set_dirty_status(True))
        ctk.CTkLabel(pif,text="Dominant K:").grid(row=2,column=0,padx=5,pady=5,sticky="w");self.entry_dominant_k=ctk.CTkEntry(pif,placeholder_text="3");self.entry_dominant_k.grid(row=2,column=1,padx=5,pady=5,sticky="ew");self.entry_dominant_k.bind("<KeyRelease>",lambda e:self._set_dirty_status(True))
        self.label_current_profile_path=ctk.CTkLabel(pif,text="Path: None",anchor="w",wraplength=280);self.label_current_profile_path.grid(row=3,column=0,columnspan=2,padx=5,pady=(5,0),sticky="ew")
        
        rsf=ctk.CTkFrame(self.left_panel);rsf.grid(row=current_row,column=0,sticky="nsew",padx=10,pady=(5,5));rsf.grid_columnconfigure(0,weight=1);rsf.grid_rowconfigure(1,weight=1);current_row+=1
        ctk.CTkLabel(rsf,text="Regions",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,pady=(0,5),sticky="w");self.regions_list_scroll_frame=ctk.CTkScrollableFrame(rsf,label_text="");self.regions_list_scroll_frame.grid(row=1,column=0,sticky="nsew",padx=0,pady=0)
        rbf=ctk.CTkFrame(rsf,fg_color="transparent");rbf.grid(row=2,column=0,pady=(5,0),sticky="ew");ctk.CTkButton(rbf,text="Add",width=60,command=self._add_region).pack(side="left",padx=2);self.btn_remove_region=ctk.CTkButton(rbf,text="Remove",width=70,command=self._remove_selected_region,state="disabled");self.btn_remove_region.pack(side="left",padx=2)
        
        tsf=ctk.CTkFrame(self.left_panel);tsf.grid(row=current_row,column=0,sticky="nsew",padx=10,pady=(5,10));tsf.grid_columnconfigure(0,weight=1);tsf.grid_rowconfigure(1,weight=1);current_row+=1
        ctk.CTkLabel(tsf,text="Templates",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,pady=(0,5),sticky="w");self.templates_list_scroll_frame=ctk.CTkScrollableFrame(tsf,label_text="");self.templates_list_scroll_frame.grid(row=1,column=0,sticky="nsew",padx=0,pady=0)
        tbf=ctk.CTkFrame(tsf,fg_color="transparent");tbf.grid(row=2,column=0,pady=(5,0),sticky="ew");ctk.CTkButton(tbf,text="Add",width=60,command=self._add_template).pack(side="left",padx=2);self.btn_remove_template=ctk.CTkButton(tbf,text="Remove",width=70,command=self._remove_selected_template,state="disabled");self.btn_remove_template.pack(side="left",padx=2)
        
        self.left_panel.grid_rowconfigure(1,weight=1);self.left_panel.grid_rowconfigure(2,weight=1) # Make lists expand

    def _setup_center_panel(self): # (Rules list)
        self.center_panel.grid_columnconfigure(0,weight=1);self.center_panel.grid_rowconfigure(1,weight=1) 
        ctk.CTkLabel(self.center_panel,text="Rules",font=ctk.CTkFont(size=16,weight="bold")).grid(row=0,column=0,padx=10,pady=10,sticky="w")
        self.rules_list_scroll_frame=ctk.CTkScrollableFrame(self.center_panel,label_text="");self.rules_list_scroll_frame.grid(row=1,column=0,sticky="nsew",padx=10,pady=5)
        rbf2=ctk.CTkFrame(self.center_panel,fg_color="transparent");rbf2.grid(row=2,column=0,pady=10,sticky="ew");ctk.CTkButton(rbf2,text="Add New Rule",command=self._add_new_rule).pack(side="left",padx=5);self.btn_remove_rule=ctk.CTkButton(rbf2,text="Remove Selected Rule",command=self._remove_selected_rule,state="disabled");self.btn_remove_rule.pack(side="left",padx=5)

    def _setup_right_panel(self): # (Details panel - placeholder initially)
        self.right_panel.grid_columnconfigure(0,weight=1);self.right_panel.grid_rowconfigure(0,weight=1) 
        self.details_panel_scroll_frame=ctk.CTkScrollableFrame(self.right_panel,label_text="Selected Item Details");self.details_panel_scroll_frame.pack(padx=10,pady=10,fill="both",expand=True)
        # Content frame is where dynamic editors will be placed. It's inside the scrollable one.
        self.details_panel_content_frame=ctk.CTkFrame(self.details_panel_scroll_frame,fg_color="transparent");self.details_panel_content_frame.pack(fill="both",expand=True) 
        self.label_details_placeholder=ctk.CTkLabel(self.details_panel_content_frame,text="Select an item from a list to see/edit details.",wraplength=380,justify="center");self.label_details_placeholder.pack(padx=10,pady=20,anchor="center",expand=True)

    # --- Core Profile Management & UI Sync/State Methods ---
    # (_new_profile to _on_item_selected are largely same, focus on validation in Apply methods)
    def _new_profile(self,event=None):logger.info("New Profile");self._set_dirty_status(False);S=self._prompt_save_if_dirty();logger.debug(f"Prompt save:{S}");if S:self.current_profile_path=None;self.profile_data=self._get_default_profile_structure();self._populate_ui_from_profile_data();self._set_dirty_status(False);self.label_current_profile_path.configure(text="Path:New(unsaved)");logger.info("New profile created.");else:logger.info("New profile cancelled.")
    def _open_profile(self,event=None):logger.info("Open Profile");if not self._prompt_save_if_dirty():logger.info("Open cancelled.");return;fp=filedialog.askopenfilename(title="Open",defaultextension=".json",filetypes=[("JSON","*.json"),("All","*.*")]);logger.info(f"Filepath:{fp}");if fp:self._load_profile_from_path(fp);else:logger.info("Open dialog cancelled.")
    def _load_profile_from_path(self,fp:str):logger.info(f"Loading:{fp}");try:cm=ConfigManager(fp);self.profile_data=cm.get_profile_data();self.current_profile_path=cm.get_profile_path();self._populate_ui_from_profile_data();self._set_dirty_status(False);self.label_current_profile_path.configure(text=f"Path:{self.current_profile_path}");logger.info(f"Loaded:{self.current_profile_path}");except Exception as e:logger.error(f"Failed load '{fp}':{e}",exc_info=True);messagebox.showerror("Load Error",f"Could not load:{fp}\n\nError:{e}")
    def _save_profile(self,event=None):logger.info("Save Profile");P=self.current_profile_path;D=self.profile_data;U=self._update_profile_data_from_ui;CM=ConfigManager;SD=self._set_dirty_status;I=logger.info;E=logger.error;MBE=messagebox.showerror;SA=self._save_profile_as;if P:try:valid_update=U();if valid_update:CM.save_profile_data_to_path(P,D);SD(False);I(f"Saved:{P}");else:I("Save aborted due to validation errors in settings.");except Exception as e:E(f"Failed save'{P}':{e}",exc_info=True);MBE("Save Error",f"Could not save:{P}\n\nError:{e}");else:logger.debug("No path, Save As...");SA()
    def _save_profile_as(self,event=None):logger.info("Save Profile As");U=self._update_profile_data_from_ui;P=self.current_profile_path;L=self.label_current_profile_path;SP=self._save_profile;I=logger.info;valid_update=U();if not valid_update: I("Save As aborted: validation errors in settings."); return;infn=os.path.basename(P)if P else "new_profile.json";fp=filedialog.asksaveasfilename(title="Save As",defaultextension=".json",filetypes=[("JSON","*.json"),("All","*.*")],initialfile=infn);if fp:self.current_profile_path=fp;L.configure(text=f"Path:{self.current_profile_path}");SP();else:I("Save As cancelled.")
    def _populate_ui_from_profile_data(self):logger.debug("Populating UI...");EPD=self.entry_profile_desc;S=self.profile_data.get("settings",{});EMI=self.entry_monitor_interval;EDK=self.entry_dominant_k;PSLF=self._populate_specific_list_frame;RLSF=self.regions_list_scroll_frame;PDGR=self.profile_data.get("regions",[]);BRR=self.btn_remove_region;TLSF=self.templates_list_scroll_frame;PDGT=self.profile_data.get("templates",[]);BRT=self.btn_remove_template;RLSF2=self.rules_list_scroll_frame;PDGR2=self.profile_data.get("rules",[]);BRR2=self.btn_remove_rule;UDP=self._update_details_panel; EPD.delete(0,tk.END);EPD.insert(0,self.profile_data.get("profile_description","")); EMI.delete(0,tk.END);EMI.insert(0,str(S.get("monitoring_interval_seconds",1.0)));EDK.delete(0,tk.END);EDK.insert(0,str(S.get("analysis_dominant_colors_k",3))); PSLF("region",RLSF,PDGR,lambda i,x:i.get("name",f"Region {x+1}"),BRR,"region");PSLF("template",TLSF,PDGT,lambda i,x:f"{i.get('name',f'Template {x+1}')} ({i.get('filename','N/A')})",BRT,"template");PSLF("rule",RLSF2,PDGR2,lambda i,x:i.get("name",f"Rule {x+1}"),BRR2,"rule"); UDP(None,"none");logger.debug("UI population complete.")
    def _populate_specific_list_frame(self,ltn_attr_prefix:str,fw:ctk.CTkScrollableFrame,items_data:List[Dict],dtcb:Callable,btm_to_manage_state:ctk.CTkButton,list_type_for_selection_logic:str): 
        for w in fw.winfo_children():w.destroy(); setattr(self,f"selected_{lstfn_attr}_item_widget",None);setattr(self,f"selected_{lstfn_attr}_index",None);
        if btm_to_manage_state:btm_to_manage_state.configure(state="disabled");
        for i,item_d in enumerate(items_data):display_text=dtcb(item_d,i);item_f=ctk.CTkFrame(fw,fg_color="transparent",corner_radius=0);item_f.pack(fill="x",pady=1,padx=1);lbl=ctk.CTkLabel(item_f,text=display_text,anchor="w",cursor="hand2");lbl.pack(side="left",fill="x",expand=True,padx=5,pady=2);lbl.bind("<Button-1>",lambda e,n=list_type_for_selection_logic,d=item_d,x=i,f=item_f:self._on_item_selected(n,d,x,f));item_f.bind("<Button-1>",lambda e,n=list_type_for_selection_logic,d=item_d,x=i,f=item_f:self._on_item_selected(n,d,x,f))
    def _update_profile_data_from_ui(self) -> bool: # MODIFIED to return validation status
        if not self.profile_data: self.profile_data = self._get_default_profile_structure()
        logger.debug("Updating profile_data (settings) from UI input fields...")
        
        desc_val, desc_valid = self._validate_and_get_widget_value(self.entry_profile_desc, "Profile Description", str, default_val=self.profile_data.get("profile_description",""), allow_empty_string=True, required=False)
        if desc_valid: self.profile_data["profile_description"] = desc_val
        # Not aborting for description, just log if it failed (though str should always be valid here)

        settings = self.profile_data.get("settings", {})
        all_settings_valid = True

        interval_val, is_valid_interval = self._validate_and_get_widget_value(self.entry_monitor_interval, "Monitoring Interval", float, default_val=settings.get("monitoring_interval_seconds", 1.0), min_val=0.01, required=True)
        if is_valid_interval: settings["monitoring_interval_seconds"] = interval_val
        else: all_settings_valid = False

        k_val, is_valid_k = self._validate_and_get_widget_value(self.entry_dominant_k, "Dominant K", int, default_val=settings.get("analysis_dominant_colors_k", 3), min_val=1, max_val=20, required=True)
        if is_valid_k: settings["analysis_dominant_colors_k"] = k_val
        else: all_settings_valid = False
        
        self.profile_data["settings"] = settings
        if all_settings_valid: logger.debug(f"Profile_data (settings) updated from UI. Current: {settings}")
        else: logger.error("One or more profile settings failed validation. Check messages.");
        return all_settings_valid

    def _set_dirty_status(self,is_d:bool): # (Same)
        if self._is_dirty==is_d:return; self._is_dirty=is_d;T="PyPixelBot Profile Editor";P=self.current_profile_path; if P:T+=f" - {os.path.basename(P)}"; if self._is_dirty:T+="*"; self.title(T);logger.debug(f"Profile dirty: {self._is_dirty}")
    def _prompt_save_if_dirty(self)->bool: # (Same)
        if self._is_dirty: R=messagebox.askyesnocancel("Unsaved Changes","Save changes?"); P=self._save_profile;S=self._is_dirty; if R is True:P();return not S; elif R is False:return True; else:return False; return True
    def _on_close_window(self,event=None):logger.info("Window close req.");S=self._prompt_save_if_dirty;D=self.destroy;I=logger.info; if S():I("Exiting GUI.");D(); else:I("Window close cancelled.")
    def _on_item_selected(self,ln:str,id:Dict,ii:int,iwf:ctk.CTkFrame): # (Same)
        logger.info(f"Item selected in '{ln}' list. Idx: {ii}, Name: '{id.get('name','N/A')}'"); HSLI=self._highlight_selected_list_item; SRI=self.selected_region_index;BRR=self.btn_remove_region;STI=self.selected_template_index;BRT=self.btn_remove_template;SRUI=self.selected_rule_index;BRR2=self.btn_remove_rule;UDP=self._update_details_panel; if ln!="region":HSLI("region",None,False);self.selected_region_index=None;if hasattr(BRR,'configure'):BRR.configure(state="disabled"); if ln!="template":HSLI("template",None,False);self.selected_template_index=None;if hasattr(BRT,'configure'):BRT.configure(state="disabled"); if ln!="rule":HSLI("rule",None,False);self.selected_rule_index=None;if hasattr(BRR2,'configure'):BRR2.configure(state="disabled"); setattr(self,f"selected_{ln}_index",ii);HSLI(ln,iwf,False); if ln=="region" and hasattr(BRR,'configure'):BRR.configure(state="normal"); elif ln=="template"and hasattr(BRT,'configure'):BRT.configure(state="normal"); elif ln=="rule"and hasattr(BRR2,'configure'):BRR2.configure(state="normal"); UDP(id,ln)

    # --- Details Panel Update & Parameter Rendering ---
    def _update_details_panel(self, item_data: Optional[Any], item_type: str): # MODIFIED for Convert button text update
        self._clear_details_panel_content() 
        if item_data and item_type == "region": logger.debug(f"Details for region: {item_data.get('name')}"); ctk.CTkLabel(self.details_panel_content_frame,text="Name:").grid(row=0,column=0,padx=5,pady=5,sticky="w");self.detail_widgets["name"]=ctk.CTkEntry(self.details_panel_content_frame);self.detail_widgets["name"].insert(0,str(item_data.get("name","")));self.detail_widgets["name"].grid(row=0,column=1,padx=5,pady=5,sticky="ew");self.detail_widgets["name"].bind("<KeyRelease>",lambda e:self._set_dirty_status(True));coords={"x":item_data.get("x",0),"y":item_data.get("y",0),"width":item_data.get("width",100),"height":item_data.get("height",100)};for i,(k,v)in enumerate(coords.items()):ctk.CTkLabel(self.details_panel_content_frame,text=f"{k.capitalize()}:").grid(row=i+1,column=0,padx=5,pady=5,sticky="w");self.detail_widgets[k]=ctk.CTkEntry(self.details_panel_content_frame);self.detail_widgets[k].insert(0,str(v));self.detail_widgets[k].grid(row=i+1,column=1,padx=5,pady=5,sticky="ew");self.detail_widgets[k].bind("<KeyRelease>",lambda e:self._set_dirty_status(True));bf=ctk.CTkFrame(self.details_panel_content_frame,fg_color="transparent");bf.grid(row=len(coords)+1,column=0,columnspan=2,pady=10);ctk.CTkButton(bf,text="Apply Changes",command=self._apply_region_changes).pack(side="left",padx=5);ctk.CTkButton(bf,text="Edit Coords (Selector)",command=self._edit_region_coordinates_with_selector).pack(side="left",padx=5)
        elif item_data and item_type == "template": logger.debug(f"Details for template: {item_data.get('name')}");self.details_panel_content_frame.grid_columnconfigure(1,weight=1);ctk.CTkLabel(self.details_panel_content_frame,text="Name:").grid(row=0,column=0,padx=5,pady=5,sticky="w");self.detail_widgets["template_name"]=ctk.CTkEntry(self.details_panel_content_frame);self.detail_widgets["template_name"].insert(0,str(item_data.get("name","")));self.detail_widgets["template_name"].grid(row=0,column=1,padx=5,pady=5,sticky="ew");self.detail_widgets["template_name"].bind("<KeyRelease>",lambda e:self._set_dirty_status(True));ctk.CTkLabel(self.details_panel_content_frame,text="Filename:").grid(row=1,column=0,padx=5,pady=5,sticky="w");fnl=ctk.CTkLabel(self.details_panel_content_frame,text=str(item_data.get("filename","N/A")),anchor="w");fnl.grid(row=1,column=1,padx=5,pady=5,sticky="ew");ctk.CTkLabel(self.details_panel_content_frame,text="Preview:").grid(row=2,column=0,padx=5,pady=5,sticky="nw");self.template_preview_image_label=ctk.CTkLabel(self.details_panel_content_frame,text="No preview",width=MAX_PREVIEW_WIDTH,height=MAX_PREVIEW_HEIGHT);self.template_preview_image_label.grid(row=2,column=1,padx=5,pady=5,sticky="w");self._display_template_preview(item_data.get("filename"));ctk.CTkButton(self.details_panel_content_frame,text="Apply Changes",command=self._apply_template_changes).grid(row=3,column=0,columnspan=2,pady=10)
        elif item_data and item_type == "rule": 
            logger.debug(f"Populating details for rule: {item_data.get('name')}")
            self.details_panel_content_frame.grid_columnconfigure(1, weight=1); self.selected_sub_condition_index=None; 
            if self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled")
            row_idx=0;ctk.CTkLabel(self.details_panel_content_frame,text="Rule Name:").grid(row=row_idx,column=0,sticky="w",padx=5,pady=2);self.detail_widgets["rule_name"]=ctk.CTkEntry(self.details_panel_content_frame);self.detail_widgets["rule_name"].insert(0,item_data.get("name",""));self.detail_widgets["rule_name"].grid(row=row_idx,column=1,sticky="ew",padx=5,pady=2);row_idx+=1
            ctk.CTkLabel(self.details_panel_content_frame,text="Default Region:").grid(row=row_idx,column=0,sticky="w",padx=5,pady=2);r_names=[""]+[r.get("name","")for r in self.profile_data.get("regions",[])if r.get("name")];self.detail_optionmenu_vars["rule_region"]=ctk.StringVar(value=item_data.get("region",""));r_menu=ctk.CTkOptionMenu(self.details_panel_content_frame,variable=self.detail_optionmenu_vars["rule_region"],values=r_names,command=lambda c:self._set_dirty_status(True));r_menu.grid(row=row_idx,column=1,sticky="ew",padx=5,pady=2);row_idx+=1
            cond_data=copy.deepcopy(item_data.get("condition",{}));act_data=copy.deepcopy(item_data.get("action",{}))
            cond_outer_f=ctk.CTkFrame(self.details_panel_content_frame);cond_outer_f.grid(row=row_idx,column=0,columnspan=2,sticky="new",pady=(10,0));cond_outer_f.grid_columnconfigure(0,weight=1);row_idx+=1
            cond_hdr_f=ctk.CTkFrame(cond_outer_f,fg_color="transparent");cond_hdr_f.pack(fill="x",padx=5);ctk.CTkLabel(cond_hdr_f,text="CONDITION",font=ctk.CTkFont(weight="bold")).pack(side="left",anchor="w")
            is_compound="logical_operator"in cond_data and isinstance(cond_data.get("sub_conditions"),list)
            btn_text = "Convert to Single" if is_compound else "Convert to Compound"
            if not self.btn_convert_condition or not self.btn_convert_condition.winfo_exists(): # Create if doesn't exist
                 self.btn_convert_condition = ctk.CTkButton(cond_hdr_f,text=btn_text,command=self._convert_condition_structure,width=160)
                 self.btn_convert_condition.pack(side="right",padx=(0,5))
            else: self.btn_convert_condition.configure(text=btn_text) # Update existing
            
            self.condition_params_frame=ctk.CTkFrame(cond_outer_f,fg_color="transparent");self.condition_params_frame.pack(fill="x",expand=True,padx=5,pady=(0,5));self.condition_params_frame.grid_columnconfigure(1,weight=1)
            self._render_rule_condition_editor(cond_data)
            act_outer_f=ctk.CTkFrame(self.details_panel_content_frame);act_outer_f.grid(row=row_idx,column=0,columnspan=2,sticky="new",pady=(10,0));act_outer_f.grid_columnconfigure(0,weight=1);row_idx+=1;ctk.CTkLabel(act_outer_f,text="ACTION",font=ctk.CTkFont(weight="bold")).pack(anchor="w",padx=5);self.action_params_frame=ctk.CTkFrame(act_outer_f,fg_color="transparent");self.action_params_frame.pack(fill="x",expand=True,padx=5,pady=(0,5));self.action_params_frame.grid_columnconfigure(1,weight=1);ctk.CTkLabel(self.action_params_frame,text="Action Type:").grid(row=0,column=0,sticky="w",padx=5,pady=2);i_act_type=str(act_data.get("type","log_message"));self.detail_optionmenu_vars["action_type"]=ctk.StringVar(value=i_act_type);act_type_menu=ctk.CTkOptionMenu(self.action_params_frame,variable=self.detail_optionmenu_vars["action_type"],values=ACTION_TYPES,command=lambda choice:self._on_rule_part_type_change("action",choice));act_type_menu.grid(row=0,column=1,sticky="ew",padx=5,pady=2);self._render_action_parameters(act_data,self.action_params_frame,start_row=1)
            ctk.CTkButton(self.details_panel_content_frame,text="Apply Rule Changes",command=self._apply_rule_changes).grid(row=row_idx,column=0,columnspan=2,pady=(20,5))
        elif item_data: details_text=json.dumps(item_data,indent=2);tb=ctk.CTkTextbox(self.details_panel_content_frame,wrap="word",height=500);tb.pack(fill="both",expand=True,padx=5,pady=5);tb.insert("0.0",details_text);tb.configure(state="disabled");logger.debug(f"Details for {item_type}(JSON):{str(item_data)[:100]}")
        else: self.label_details_placeholder = ctk.CTkLabel(self.details_panel_content_frame, text="Select an item.", wraplength=250); self.label_details_placeholder.pack(padx=10, pady=10, anchor="center"); logger.debug("Details panel cleared.")

    # --- Parameter Rendering & Collection, Apply Changes methods ---
    def _display_template_preview(self,fn:Optional[str]): # (Same)
        if not self.template_preview_image_label or not fn or not self.current_profile_path:
            if self.template_preview_image_label:self.template_preview_image_label.configure(image=None,text="No preview");logger.debug("Tpl preview skip.");return
        pd=os.path.dirname(self.current_profile_path);tp=os.path.join(pd,"templates",fn);logger.debug(f"Loading tpl preview:{tp}");
        if os.path.exists(tp):try:img=Image.open(tp);img.thumbnail((MAX_PREVIEW_WIDTH,MAX_PREVIEW_HEIGHT));ctk_img=ctk.CTkImage(light_image=img,dark_image=img,size=(img.width,img.height));self.template_preview_image_label.configure(image=ctk_img,text="");logger.debug(f"Tpl preview loaded '{fn}'.Sz:{img.width}x{img.height}");except Exception as e:self.template_preview_image_label.configure(image=None,text=f"Err preview:\n{fn}");logger.error(f"Err load tpl preview '{tp}':{e}",exc_info=True)
        else:self.template_preview_image_label.configure(image=None,text=f"Not found:\n{fn}");logger.warning(f"Tpl preview:File not found '{tp}'.")
    def _render_condition_parameters(self,cd:Dict,pf:ctk.CTkFrame,sr:int,issc:bool=False):# (Same)
        px="subcond_"if issc else"cond_";logger.debug(f"Render cond(sub={issc})params type:{cd.get('type')},prefix:{px},data:{cd}");
        for w in list(pf.winfo_children()):gi=w.grid_info();if gi and gi.get("row",-1)>=sr:w.destroy()
        ktr=[k for k in self.detail_widgets if k.startswith(px)];for k in ktr:self.detail_widgets.pop(k);self.detail_optionmenu_vars.pop(f"{k}_var",None)
        ct=cd.get("type");cr=sr;def add_pe(k,dv,l=None,r=None,p=None,itb=False):nonlocal cr;row=r if r is not None else cr;_l=l if l else k.replace("_"," ").capitalize()+":";ctk.CTkLabel(pf,text=_l).grid(row=row,column=0,padx=5,pady=2,sticky="nw"if itb else"w");
        if itb:w=ctk.CTkTextbox(pf,h=60,wrap="word");w.insert("0.0",str(cd.get(k,dv)));w.bind("<FocusOut>",lambda e:self._set_dirty_status(True));else:w=ctk.CTkEntry(pf,ph=p if p else str(dv));w.insert(0,str(cd.get(k,dv)));w.bind("<KeyRelease>",lambda e:self._set_dirty_status(True));
        w.grid(row=row,column=1,padx=5,pady=2,sticky="ew");self.detail_widgets[f"{px}{k}"]=w;if r is None:cr+=1;return w
        def add_po(k,dv,vs,l=None,r=None):nonlocal cr;row=r if r is not None else cr;_l=l if l else k.replace("_"," ").capitalize()+":";ctk.CTkLabel(pf,text=_l).grid(row=row,column=0,padx=5,pady=2,sticky="w");
        v=ctk.StringVar(value=str(cd.get(k,dv)));m=ctk.CTkOptionMenu(pf,variable=v,values=vs,command=lambda choice:self._set_dirty_status(True));m.grid(row=row,column=1,padx=5,pady=2,sticky="ew");self.detail_widgets[f"{px}{k}"]=m;self.detail_optionmenu_vars[f"{px}{key}_var"]=v;if r is None:cr+=1;return m
        def add_pcb(k,dv,l=None,r=None):nonlocal cr;row=r if r is not None else cr;_l=l if l else k.replace("_"," ").capitalize()+":";
        v=ctk.BooleanVar(value=bool(cd.get(k,dv)));cb=ctk.CTkCheckBox(pf,text=_l,variable=v,command=lambda:self._set_dirty_status(True));cb.grid(row=row,column=0,columnspan=2,padx=5,pady=2,sticky="w");self.detail_widgets[f"{px}{key}"]=cb;self.detail_optionmenu_vars[f"{px}{key}_var"]=v;if r is None:cr+=1;return cb
        if ct=="pixel_color":add_pe("relative_x",0);add_pe("relative_y",0);add_pe("expected_bgr","0,0,0",ph="B,G,R");add_pe("tolerance",0)
        elif ct=="average_color_is":add_pe("expected_bgr","128,128,128",ph="B,G,R");add_pe("tolerance",10)
        elif ct=="template_match_found":tpl_n=[""]+[t.get("name","")for t in self.profile_data.get("templates",[])if t.get("name")];add_po("template_name",cd.get("template_name",""),tpl_n,lbl="Template Name:");add_pe("min_confidence",0.8);add_pe("capture_as","",lbl="Capture Details As:")
        elif ct=="ocr_contains_text":add_pe("text_to_find","");add_pcb("case_sensitive",False,lbl="Case Sensitive");add_pe("min_ocr_confidence",70.0);add_pe("capture_as","",lbl="Capture Text As:")
        elif ct=="dominant_color_matches":add_pe("expected_bgr","0,0,255",ph="B,G,R");add_pe("tolerance",10);add_pe("check_top_n_dominant",1);add_pe("min_percentage",5.0)
        elif ct=="always_true":ctk.CTkLabel(pf,text="No parameters.").grid(row=cr,column=0,columnspan=2,padx=5,pady=2,sticky="w")
        logger.debug(f"Rendered params for cond '{ct}' (sub={issc}).")
    def _render_action_parameters(self,ad:Dict,pf:ctk.CTkFrame,sr:int):# (Same)
        px="act_";logger.debug(f"Render action params type:{ad.get('type')},data:{ad}");
        for w in list(pf.winfo_children()):gi=w.grid_info();if gi and gi.get("row",-1)>=sr:w.destroy()
        ktr=[k for k in self.detail_widgets if k.startswith(px)];for k in ktr:self.detail_widgets.pop(k);self.detail_optionmenu_vars.pop(f"{k}_var",None)
        at=ad.get("type");cr=sr;def add_pe(k,dv,l=None,r=None,p=None,itb=False):nonlocal cr;row=r if r is not None else cr;_lbl=l if l else k.replace("_"," ").capitalize()+":";ctk.CTkLabel(pf,text=_lbl).grid(row=row,column=0,padx=5,pady=2,sticky="nw"if itb else"w");
        if itb:w=ctk.CTkTextbox(pf,h=60,wrap="word");w.insert("0.0",str(ad.get(k,dv)));w.bind("<FocusOut>",lambda e:self._set_dirty_status(True));else:w=ctk.CTkEntry(pf,ph=p if p else str(dv));w.insert(0,str(ad.get(k,dv)));w.bind("<KeyRelease>",lambda e:self._set_dirty_status(True));
        w.grid(row=row,column=1,padx=5,pady=2,sticky="ew");self.detail_widgets[f"{px}{k}"]=w;if r is None:cr+=1;return w
        def add_po(k,dv,vs,l=None,r=None):nonlocal cr;row=r if r is not None else cr;_lbl=l if l else k.replace("_"," ").capitalize()+":";ctk.CTkLabel(pf,text=_lbl).grid(row=row,column=0,padx=5,pady=2,sticky="w");
        v=ctk.StringVar(value=str(ad.get(k,dv)));m=ctk.CTkOptionMenu(pf,variable=v,values=vs,command=lambda c:self._set_dirty_status(True));m.grid(row=row,column=1,padx=5,pady=2,sticky="ew");self.detail_widgets[f"{px}{key}"]=m;self.detail_optionmenu_vars[f"{px}{key}_var"]=v;if r is None:cr+=1;return m
        r_names=[""]+[r.get("name","")for r in self.profile_data.get("regions",[])if r.get("name")]
        if at=="click":add_po("target_relation","center_of_region",CLICK_TARGET_RELATIONS);add_po("target_region","",r_names,lbl="Target Region:");add_pe("x",0,ph="Abs/Rel X");add_pe("y",0,ph="Abs/Rel Y");add_po("button","left",CLICK_BUTTONS);add_pe("clicks",1);add_pe("interval",0.0);add_pe("pyautogui_pause_before",0.0,lbl="Pause Before(s):")
        elif at=="type_text":add_pe("text","",istb=True);add_pe("interval",0.0);add_pe("pyautogui_pause_before",0.0,lbl="Pause Before(s):")
        elif at=="press_key":add_pe("key","enter",ph="e.g. enter or ctrl,c");add_pe("pyautogui_pause_before",0.0,lbl="Pause Before(s):")
        elif at=="log_message":add_pe("message","Rule triggered",istb=True);add_po("level","INFO",LOG_LEVELS)
        logger.debug(f"Rendered params for action type '{at}'.")

    def _get_condition_parameters_from_ui(self, ct: str, is_sub_condition: bool = False) -> Optional[Dict[str, Any]]: # MODIFIED
        prefix = "subcond_" if is_sub_condition else "cond_"
        params: Dict[str, Any] = {"type": ct}; all_params_valid = True; L=logger; V = self._validate_and_get_widget_value; PBGR = self._parse_bgr_string
        L.debug(f"Getting UI params for cond type: {ct}(sub={is_sub_condition}), prefix: {prefix}")
        
        def get_param(key:str, field_name:str, target_type:type, default_val:Any, **kwargs_for_validation) -> None:
            nonlocal all_params_valid # Allow modification of outer scope flag
            val, is_valid = V(f"{prefix}{key}", field_name, target_type, default_val, **kwargs_for_validation)
            if not is_valid: all_params_valid = False
            # Only add to params if valid, or if we want to store even invalid attempts (for now, only valid)
            # If not valid, _validate_and_get_widget_value returns default_val, which might be fine to store if not critical.
            # However, if a required field is invalid, all_params_valid will be False.
            # For BGR, it might return a default list or None.
            if key == "expected_bgr": # Special handling for BGR parsed value
                bgr_str_val, is_str_valid = V(f"{prefix}{key}", field_name, str, default_val if isinstance(default_val, str) else "0,0,0")
                if not is_str_valid: all_params_valid = False; params[key] = [0,0,0] # Default BGR on string fail
                else:
                    parsed_bgr = PBGR(bgr_str_val, field_name)
                    if parsed_bgr is None: all_params_valid = False; params[key] = [0,0,0] if "pixel" in ct else ([128,128,128] if "avg" in ct else [0,0,255])
                    else: params[key] = parsed_bgr
            else:
                params[key] = val # Store the returned value (could be default if validation failed but allowed default)

        if ct=="pixel_color":
            get_param("relative_x","Rel X",int,0,required=True); get_param("relative_y","Rel Y",int,0,required=True)
            get_param("expected_bgr","Exp BGR",str,"0,0,0",required=True); get_param("tolerance","Tolerance",int,0,min_val=0,max_val=255,required=True)
        elif ct=="average_color_is":
            get_param("expected_bgr","Exp BGR",str,"128,128,128",required=True); get_param("tolerance","Tolerance",int,10,min_val=0,max_val=255,required=True)
        elif ct=="template_match_found":
            # Template name is from OptionMenu, filename resolved from it.
            sel_tpl_name_var = self.detail_optionmenu_vars.get(f"{prefix}template_name_var")
            sel_tpl_name = sel_tpl_name_var.get() if sel_tpl_name_var else ""
            if not sel_tpl_name: L.warning(f"Template Name for '{ct}' not selected."); all_params_valid = False; params["template_filename"] = ""
            else:
                actual_fn = next((t.get("filename","") for t in self.profile_data.get("templates",[]) if t.get("name")==sel_tpl_name), "")
                if not actual_fn: L.warning(f"No filename for tpl name '{sel_tpl_name}'."); all_params_valid = False
                params["template_filename"] = actual_fn
            get_param("min_confidence","Min Conf",float,0.8,min_val=0.0,max_val=1.0,required=True)
            get_param("capture_as","Capture As",str,"",allow_empty_string=True,required=False)
        elif ct=="ocr_contains_text":
            get_param("text_to_find","Text to Find",str,"",allow_empty_string=False,required=True)
            # Checkbox value directly from var
            case_sensitive_var = self.detail_optionmenu_vars.get(f"{prefix}case_sensitive_var")
            params["case_sensitive"] = case_sensitive_var.get() if case_sensitive_var and isinstance(case_sensitive_var, tk.BooleanVar) else False
            get_param("min_ocr_confidence","Min OCR Conf",float,70.0,min_val=0.0,max_val=100.0,required=False) # Optional
            get_param("capture_as","Capture As",str,"",allow_empty_string=True,required=False)
        elif ct=="dominant_color_matches":
            get_param("expected_bgr","Exp BGR",str,"0,0,255",required=True)
            get_param("tolerance","Tolerance",int,10,min_val=0,max_val=255,required=True)
            get_param("check_top_n_dominant","Check Top N",int,1,min_val=1,required=True)
            get_param("min_percentage","Min Perc",float,5.0,min_val=0.0,max_val=100.0,required=True)
        
        if not all_params_valid: L.error(f"Validation failed for one or more parameters of condition '{ct}' (sub={issc}). Returning None."); return None
        L.debug(f"Collected valid cond params (sub={issc}) from UI:{params}"); return params

    def _get_action_parameters_from_ui(self, at: str) -> Optional[Dict[str, Any]]: # MODIFIED to use new validation
        prefix = "act_"; params: Dict[str, Any] = {"type": at}; all_params_valid = True; L=logger;V=self._validate_and_get_widget_value;DOV=self.detail_optionmenu_vars
        L.debug(f"Get UI params action:{at}")
        def get_param(key:str,fn:str,tt:type,dv:Any,**kw):nonlocal all_params_valid;val,is_v=V(f"{prefix}{key}",fn,tt,dv,**kw);if not is_v:all_params_valid=False;return val
        
        if at=="click":
            params["target_relation"]=DOV.get(f"{prefix}target_relation_var",tk.StringVar()).get() # Assumed valid choice
            params["target_region"]=DOV.get(f"{prefix}target_region_var",tk.StringVar()).get() # Optional, can be empty
            params["x"]=get_param("x","X Coord/Offset",str,"0",allow_empty_string=True,required=False) 
            params["y"]=get_param("y","Y Coord/Offset",str,"0",allow_empty_string=True,required=False)
            params["button"]=DOV.get(f"{prefix}button_var",tk.StringVar()).get()
            params["clicks"]=get_param("clicks","Num Clicks",str,"1",allow_empty_string=True,required=False) # Keep as str for ActionExecutor
            params["interval"]=get_param("interval","Click Interval",str,"0.0",allow_empty_string=True,required=False)
            params["pyautogui_pause_before"]=get_param("pyautogui_pause_before","Pause Before",str,"0.0",allow_empty_string=True,required=False)
        elif at=="type_text":
            params["text"]=V(f"{prefix}{key}","Text to Type",str,"",allow_empty_string=True,required=False)[0] # Directly get, allow empty
            params["interval"]=get_param("interval","Type Interval",str,"0.0",allow_empty_string=True,required=False)
            params["pyautogui_pause_before"]=get_param("pyautogui_pause_before","Pause Before",str,"0.0",allow_empty_string=True,required=False)
        elif at=="press_key":
            params["key"]=get_param("key","Key(s) to Press",str,"enter",allow_empty_string=False,required=True)
            params["pyautogui_pause_before"]=get_param("pyautogui_pause_before","Pause Before",str,"0.0",allow_empty_string=True,required=False)
        elif at=="log_message":
            params["message"]=V(f"{prefix}{key}","Log Message",str,"Rule triggered",allow_empty_string=True,required=False)[0]
            params["level"]=DOV.get(f"{prefix}level_var",tk.StringVar()).get() # Assumed valid choice
        
        if not all_params_valid: L.error(f"Validation failed for one or more parameters of action '{at}'. Returning None."); return None
        L.debug(f"Collected valid action params from UI:{params}"); return params


    # --- Apply Changes Methods (Modified to use new validation returns) ---
    def _apply_region_changes(self): # MODIFIED for validation
        if self.selected_region_index is None: logger.warning("Apply Region: No region selected."); return
        rl:List[Dict]=self.profile_data["regions"];crd=rl[self.selected_region_index];on=crd.get("name","Unk");logger.info(f"Applying changes to region '{on}'.")
        V=self._validate_and_get_widget_value
        nn,nv=V(self.detail_widgets["name"],"Region Name",str,on,allow_empty_string=False,required=True)
        nx,xv=V(self.detail_widgets["x"],"X",int,crd.get("x",0),required=True)
        ny,yv=V(self.detail_widgets["y"],"Y",int,crd.get("y",0),required=True)
        nw,wv=V(self.detail_widgets["width"],"Width",int,crd.get("width",1),min_val=1,required=True)
        nh,hv=V(self.detail_widgets["height"],"Height",int,crd.get("height",1),min_val=1,required=True)
        if not(nv and xv and yv and wv and hv):logger.error(f"Apply Region '{on}' aborted: validation errors.");return # Errors shown by validator
        crd.update({"name":nn,"x":nx,"y":ny,"width":nw,"height":nh});logger.info(f"Region '{on}' updated to '{nn}'.");self._set_dirty_status(True);self._populate_specific_list_frame("region",self.regions_list_scroll_frame,self.profile_data.get("regions",[]),lambda i,x:i.get("name",f"Region {x+1}"),self.btn_remove_region,"region");self._update_details_panel(crd,"region");messagebox.showinfo("Region Updated",f"Region '{nn}' updated.")
    def _apply_template_changes(self): # MODIFIED for validation
        if self.selected_template_index is None: logger.warning("Apply Template: No tpl selected."); return
        tl:List[Dict]=self.profile_data["templates"];ctd=tl[self.selected_template_index];on=ctd.get("name","Unk");logger.info(f"Applying changes to tpl '{on}'.")
        nn,nv=self._validate_and_get_widget_value(self.detail_widgets["template_name"],"Template Name",str,on,allow_empty_string=False,required=True)
        if not nv:return
        if any(i!=self.selected_template_index and t.get("name")==nn for i,t in enumerate(tl)):messagebox.showerror("Name Error",f"Name '{nn}' exists.");logger.warning(f"Apply Template: Name '{nn}' collision.");return
        ctd["name"]=nn;logger.info(f"Tpl '{on}' name to '{nn}'.");self._set_dirty_status(True);self._populate_specific_list_frame("template",self.templates_list_scroll_frame,self.profile_data.get("templates",[]),lambda i,x:f"{i.get('name',f'Tpl {x+1}')}({i.get('filename','N/A')})",self.btn_remove_template,"template");self._update_details_panel(ctd,"template");messagebox.showinfo("Tpl Updated",f"Tpl '{nn}' updated.")
    def _apply_rule_changes(self): # MODIFIED to use validation returns
        if self.selected_rule_index is None or not self.profile_data: logger.warning("Apply Rule: No rule selected."); return
        # ... (rest of method remains same as previous version, relying on _get_X_params methods to return None on validation failure) ...
        rule_list: List[Dict]=self.profile_data["rules"]; current_rule_data_orig=rule_list[self.selected_rule_index]; old_name=current_rule_data_orig.get("name","Unknown")
        logger.info(f"Attempting to apply changes to rule '{old_name}'.")
        temp_rule_data = copy.deepcopy(current_rule_data_orig) # Work on copy
        
        new_name, name_valid = self._validate_and_get_widget_value(self.detail_widgets["rule_name"], "Rule Name", str, old_name, allow_empty_string=False, required=True)
        if not name_valid: return # Abort if name invalid
        new_default_region = self.detail_optionmenu_vars["rule_region"].get()
        temp_rule_data["name"] = new_name; temp_rule_data["region"] = new_default_region if new_default_region else ""

        condition_data_to_save = {}; is_compound_in_ui = "logical_operator" in self.detail_optionmenu_vars 
        if is_compound_in_ui:
            condition_data_to_save["logical_operator"] = self.detail_optionmenu_vars["logical_operator"].get()
            saved_sub_conditions = []
            profile_sub_conditions = temp_rule_data.get("condition",{}).get("sub_conditions", [])
            all_subs_valid = True
            for idx, sub_cond_in_profile in enumerate(profile_sub_conditions):
                if self.selected_sub_condition_index == idx: # This sub-condition was actively being edited
                    sub_cond_type_var = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                    if sub_cond_type_var:
                        sub_cond_type_ui = sub_cond_type_var.get()
                        validated_sub_params = self._get_condition_parameters_from_ui(sub_cond_type_ui, is_sub_condition=True)
                        if validated_sub_params is None: all_subs_valid = False; break # Validation failed for this sub
                        saved_sub_conditions.append(validated_sub_params)
                    else: saved_sub_conditions.append(copy.deepcopy(sub_cond_in_profile)) # Should not happen
                else: saved_sub_conditions.append(copy.deepcopy(sub_cond_in_profile)) # Keep others as is
            if not all_subs_valid: logger.error(f"Validation failed for a sub-condition of rule '{new_name}'. Aborting rule save."); return
            condition_data_to_save["sub_conditions"] = saved_sub_conditions
        else: # Single condition
            cond_type_ui = self.detail_optionmenu_vars["condition_type"].get()
            validated_cond_params = self._get_condition_parameters_from_ui(cond_type_ui, is_sub_condition=False)
            if validated_cond_params is None: logger.error(f"Validation failed for single condition of rule '{new_name}'. Aborting rule save."); return
            condition_data_to_save = validated_cond_params
        temp_rule_data["condition"] = condition_data_to_save

        action_type_ui = self.detail_optionmenu_vars["action_type"].get()
        validated_action_params = self._get_action_parameters_from_ui(action_type_ui)
        if validated_action_params is None: logger.error(f"Validation failed for action of rule '{new_name}'. Aborting rule save."); return
        temp_rule_data["action"] = validated_action_params
        
        self.profile_data["rules"][self.selected_rule_index] = temp_rule_data # Commit validated changes
        logger.info(f"Rule '{old_name}' updated to '{new_name}'."); self._set_dirty_status(True)
        self._populate_specific_list_frame("rule",self.rules_list_scroll_frame,self.profile_data.get("rules",[]),lambda i,x:i.get("name",f"Rule {x+1}"),self.btn_remove_rule,"rule")
        self._update_details_panel(temp_rule_data,"rule"); messagebox.showinfo("Rule Updated",f"Rule '{new_name}' updated.")


    # --- List Item Management Methods (largely same) ---
    def _edit_region_coordinates_with_selector(self): # (Same)
        if self.selected_region_index is None: logger.warning("Edit Coords: No region."); return # ... (rest is same)
        if self._is_dirty:
            if not messagebox.askyesno("Save?","Save current changes before editing coords externally?"): logger.info("Edit coords cancelled (no save)."); return
            self._save_profile(); 
            if self._is_dirty: logger.info("Edit coords cancelled (save failed)."); return
        if not self.current_profile_path: messagebox.showerror("Error","Profile must be saved."); logger.error("Edit Coords: No profile path."); return
        logger.info(f"Launching RegionSelector for idx {self.selected_region_index} from {self.current_profile_path}..."); try:
            cm_sel=ConfigManager(self.current_profile_path,create_if_missing=False); sel_dlg=RegionSelectorWindow(master=self,config_manager=cm_sel); self.wait_window(sel_dlg) 
            if hasattr(sel_dlg,'saved_region_info') and sel_dlg.saved_region_info: logger.info(f"RegionSelector closed, region '{sel_dlg.saved_region_info['name']}' saved. Reloading."); self._load_profile_from_path(self.current_profile_path); self._set_dirty_status(True) 
            else: logger.info("RegionSelector closed, no changes or cancelled.")
        except Exception as e: logger.error(f"Error Edit Coords: {e}",exc_info=True); messagebox.showerror("Edit Coords Error",f"Error: {e}")
    def _add_region(self): # (Same)
        logger.info("Add Region."); P=self.profile_data;SP=self._save_profile_as;CP=self.current_profile_path;NP=self._new_profile;SD=self._set_dirty_status;L=logger.info;S=self._save_profile;ISD=self._is_dirty;MB=messagebox;LPFP=self._load_profile_from_path; if not P:NP(); if not CP:MB.showinfo("Save Required","Save profile before adding.");SP(); if not CP:L("Add Region cancelled: Not saved.");return
        if ISD: sc=MB.askyesno("Save Changes?","Save current changes before adding new region externally?"); L(f"Save prompt result: {sc}"); if sc: S(); if ISD:L("Add Region cancelled: Save failed.");return; else:L("Add Region cancelled by user (no save).");return
        try: cm_sel=ConfigManager(CP,create_if_missing=False);sel_dlg=RegionSelectorWindow(master=self,config_manager=cm_sel);L("Launching RegionSelector for new region...");self.wait_window(sel_dlg)
        if hasattr(sel_dlg,'saved_region_info')and sel_dlg.saved_region_info:L(f"RegionSelector closed, region '{sel_dlg.saved_region_info['name']}' saved. Reloading.");LPFP(CP);SD(True) 
        else:L("RegionSelector closed, no new region or cancelled.")
        except Exception as e:logger.error(f"Error Add Region: {e}",exc_info=True);MB.showerror("Add Region Error",f"Error: {e}")
    def _remove_selected_item(self,ln:str,ikl:str,sai:str,btd:ctk.CTkButton): # (Same)
        si=getattr(self,sai,None);PD=self.profile_data;L=logger;PSLF=self._populate_specific_list_frame;SD=self._set_dirty_status;UDP=self._update_details_panel;MBW=messagebox.showwarning; if si is not None and PD and ikl in PD:
            il:List=PD[ikl]; if 0<=si<len(il):ri=il.pop(si);L.info(f"Removed {ln} '{ri.get('name','N/A')}' idx {si}.");lw=getattr(self,f"{ln}s_list_scroll_frame");dcb_text_func=lambda item,idx:item.get("name",f"{ln.capitalize()} {idx+1}") if ln!="template" else f"{item.get('name',f'Template {idx+1}')} ({item.get('filename','N/A')})"; PSLF(ln,lw,PD.get(ikl,[]),dcb_text_func,btd,ln);SD(True);setattr(self,sai,None);btd.configure(state="disabled");UDP(None,"none");
            if ln=="template"and self.current_profile_path:fn_del=ri.get("filename");if fn_del:p_dir=os.path.dirname(self.current_profile_path);tfp=os.path.join(p_dir,"templates",fn_del);try:
                if os.path.exists(tfp):os.remove(tfp);L.info(f"Deleted template file: {tfp}");else:L.warning(f"Template file not found for del: {tfp}");except OSError as e_os:L.error(f"Error deleting template file '{tfp}': {e_os}",exc_info=True);MBW("File Deletion Error",f"Could not delete file:\n{fn_del}\n\nError: {e_os.strerror}")
            else:L.warning(f"Cannot remove {ln}: Invalid idx {si}.")
        else:L.warning(f"Cannot remove {ln}: No item selected/profile data missing.")
    def _remove_selected_region(self):self._remove_selected_item("region","regions","selected_region_index",self.btn_remove_region)
    def _remove_selected_template(self):self._remove_selected_item("template","templates","selected_template_index",self.btn_remove_template)
    def _remove_selected_rule(self):self._remove_selected_item("rule","rules","selected_rule_index",self.btn_remove_rule)
    def _add_template(self): # (Same)
        logger.info("Add Template.");PD=self.profile_data;CP=self.current_profile_path;NP=self._new_profile;SPA=self._save_profile_as;L=logger;S=self._save_profile;ISD=self._is_dirty;MB=messagebox;PSLF=self._populate_specific_list_frame;TLSF=self.templates_list_scroll_frame;BRT=self.btn_remove_template;SD=self._set_dirty_status; if not PD:NP(); if not CP:MB.showinfo("Save Required","Save profile before adding templates.");SPA(); if not CP:L.info("Add Template cancelled: Not saved.");return
        if ISD: if not MB.askyesno("Save Changes?","Save current profile changes before adding new template?"):L.info("Add Template cancelled by user.");return; S(); if ISD:L.info("Add Template cancelled: Save failed.");return
        sip=filedialog.askopenfilename(title="Select Template Image",filetypes=[("PNG","*.png"),("JPEG","*.jpg;*.jpeg"),("All","*.*")]); if not sip:L.info("Add Template: No image selected.");return
        tn=ctk.CTkInputDialog(text="Enter unique name for template:",title="Template Name").get_input(); if not tn or not tn.strip():L.info("Add Template: No valid name.");return; tn=tn.strip()
        if any(t.get("name")==tn for t in PD.get("templates",[])):MB.showerror("Name Error",f"Template name '{tn}' exists.");L.warning(f"Add Template: Name '{tn}' exists.");return
        p_dir=os.path.dirname(CP);ttd=os.path.join(p_dir,"templates"); try:
            os.makedirs(ttd,exist_ok=True);L.debug(f"Ensured templates dir: {ttd}"); base,ext=os.path.splitext(os.path.basename(sip)); sfb="".join(c if c.isalnum()or c in (' ','_','-')else'_'for c in tn).rstrip().replace(' ','_'); tfb=sfb;ctr=1;tfn=f"{tfb}{ext}";ftp=os.path.join(ttd,tfn); while os.path.exists(ftp):tfn=f"{tfb}_{ctr}{ext}";ftp=os.path.join(ttd,tfn);ctr+=1
            shutil.copy2(sip,ftp);L.info(f"Template image '{sip}' copied to '{ftp}'."); nt={"name":tn,"filename":tfn}; if"templates"not in PD:PD["templates"]=[]; PD["templates"].append(nt);L.info(f"Added new template: {nt}");PSLF("template",TLSF,PD.get("templates",[]),lambda i,x:f"{i.get('name',f'Tpl {x+1}')} ({i.get('filename','N/A')})",BRT,"template");SD(True);MB.showinfo("Template Added",f"Template '{tn}' added.")
        except Exception as e:L.error(f"Error adding template '{tn}': {e}",exc_info=True);MB.showerror("Add Template Error",f"Could not add template:\n{e}")
    def _add_new_rule(self): # (Same)
        logger.info("Add New Rule.");SD=self._set_dirty_status;PD=self.profile_data;NP=self._new_profile;L=logger;PSLF=self._populate_specific_list_frame;RLSF=self.rules_list_scroll_frame;BRR=self.btn_remove_rule; SD(True); if not PD:NP(); rn=ctk.CTkInputDialog(text="Enter name for new rule:",title="New Rule Name").get_input(); if not rn:L.info("Add New Rule: No name.");return
        nr={"name":rn,"region":"","condition":{"type":"always_true"},"action":{"type":"log_message","message":f"Rule '{rn}' triggered."}}; if"rules"not in PD:PD["rules"]=[]; PD["rules"].append(nr);L.info(f"Added new rule placeholder: {nr}");PSLF("rule",RLSF,PD.get("rules",[]),lambda i,x:i.get("name",f"Rule {x+1}"),BRR,"rule");SD(True)
    
    # --- Rule Structure & Sub-condition Editing ---
    def _on_rule_part_type_change(self, part_changed: str, new_type_selected: str): # (Same)
        logger.info(f"Rule's part '{part_changed}' UI type to: '{new_type_selected}'. Redrawing.");self._set_dirty_status(True);
        if self.selected_rule_index is None:logger.warning(f"Cannot change {part_changed} type, no rule selected.");return
        crd=self.profile_data["rules"][self.selected_rule_index];
        if part_changed=="condition":
            if self.selected_sub_condition_index is not None: # Editing a sub-condition's type
                if not self.sub_condition_params_frame: return;
                scs=crd.get("condition",{}).get("sub_conditions",[]);
                if 0<=self.selected_sub_condition_index<len(scs):scd_tu=scs[self.selected_sub_condition_index];
                if scd_tu.get("type")!=new_type_selected:logger.debug(f"Sub-cond type changing. Clearing old.");scd_tu.clear()
                scd_tu["type"]=new_type_selected;self._render_condition_parameters(scd_tu,self.sub_condition_params_frame,1,True)
            elif "logical_operator" not in crd.get("condition",{}): # Editing a single main condition's type
                if not self.condition_params_frame: return;cd_tu=crd.get("condition",{});
                if cd_tu.get("type")!=new_type_selected:logger.debug(f"Main cond type changing. Clearing old.");cd_tu.clear()
                cd_tu["type"]=new_type_selected;self._render_condition_parameters(cd_tu,self.condition_params_frame,2,False) # start_row=2 for single cond
        elif part_changed=="action": # Editing main action's type
            if not self.action_params_frame: return;ad_tu=crd.get("action",{});
            if ad_tu.get("type")!=new_type_selected:logger.debug(f"Action type changing. Clearing old.");ad_tu.clear()
            ad_tu["type"]=new_type_selected;self._render_action_parameters(ad_tu,self.action_params_frame,1) # start_row=1 for action
    def _populate_sub_conditions_list(self, sub_conditions_data: List[Dict]): # (Same)
        if not self.sub_conditions_list_frame: logger.warning("Populate sub-conds: frame None."); return
        for w in self.sub_conditions_list_frame.winfo_children(): w.destroy()
        self.selected_sub_condition_index=None; self.selected_sub_condition_item_widget=None
        if hasattr(self,'btn_remove_sub_condition') and self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled")
        for i,sc in enumerate(sub_conditions_data):
            s=f"#{i+1} T:{sc.get('type','N/A')}, R:{sc.get('region','Def')}"; cap=sc.get("capture_as"); if cap:s+=f", Capt:{cap}"
            ifc={}; item_f=self._create_clickable_list_item(self.sub_conditions_list_frame,s,lambda e=None,d=sc,x=i,ic=ifc:self._on_sub_condition_selected(d,x,ic.get("frame"))); ifc["frame"]=item_f
        logger.debug(f"Populated sub-conds list: {len(sub_conditions_data)} items.")
        if self.selected_sub_condition_index is None and self.sub_condition_params_frame:
            for w in self.sub_condition_params_frame.winfo_children():w.destroy(); ctk.CTkLabel(self.sub_condition_params_frame,text="Select sub-cond to edit.").pack(padx=5,pady=5)
    def _on_sub_condition_selected(self, scd:Dict,idx:int,iwf:Optional[ctk.CTkFrame]): # (Same)
        logger.info(f"Sub-cond selected. Idx:{idx}, Data:{str(scd)[:100]}");
        if iwf is None:logger.error(f"Sub-cond sel err: item_frame None for idx {idx}.");return
        self.selected_sub_condition_index=idx;self._highlight_selected_list_item("condition",iwf,True);
        if hasattr(self,'btn_remove_sub_condition') and self.btn_remove_sub_condition:self.btn_remove_sub_condition.configure(state="normal")
        if not self.sub_condition_params_frame:logger.error("Sub-cond params frame missing!");return
        for w in self.sub_condition_params_frame.winfo_children():w.destroy();self.sub_condition_params_frame.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(self.sub_condition_params_frame,text=f"Edit Sub-Cond #{idx+1} Type:").grid(row=0,column=0,padx=5,pady=2,sticky="w")
        sc_type_var=ctk.StringVar(value=scd.get("type","always_true"));self.detail_optionmenu_vars["subcond_condition_type_var"]=sc_type_var
        sc_type_menu=ctk.CTkOptionMenu(self.sub_condition_params_frame,variable=sc_type_var,values=CONDITION_TYPES,command=lambda c:self._on_rule_part_type_change("condition",c))
        sc_type_menu.grid(row=0,column=1,padx=5,pady=2,sticky="ew");self._render_condition_parameters(scd,self.sub_condition_params_frame,1,True);logger.debug(f"Rendered params for sel sub-cond idx {idx}.")
    def _add_sub_condition_to_rule(self): # (Same)
        if self.selected_rule_index is None: logger.warning("Add SubCond: No rule."); return;r=self.profile_data["rules"][self.selected_rule_index];c=r.get("condition",{});logger.info(f"Add sub-cond to rule '{r.get('name')}'.")
        if"logical_operator"not in c:logger.info(f"Rule '{r.get('name')}' single, convert to compound (AND).");c.pop("type",None);[c.pop(k,None)for k in list(c.keys())if k not in["logical_operator","sub_conditions"]];c["logical_operator"]="AND";c["sub_conditions"]=[]
        ns={"type":"always_true"};c["sub_conditions"].append(ns);r["condition"]=c;self._set_dirty_status(True);self._update_details_panel(r,"rule");logger.info(f"Added new sub-cond to rule '{r.get('name')}'.")
    def _remove_selected_sub_condition(self): # (Same)
        if self.selected_rule_index is None:logger.warning("Remove SubCond: No rule sel.");return;if self.selected_sub_condition_index is None:logger.warning("Remove SubCond: No sub-cond sel.");return
        r=self.profile_data["rules"][self.selected_rule_index];c=r.get("condition",{});s=c.get("sub_conditions");
        if s and isinstance(s,list)and 0<=self.selected_sub_condition_index<len(s):rem=s.pop(self.selected_sub_condition_index);logger.info(f"Removed sub-cond idx {self.selected_sub_condition_index} from '{r.get('name')}': {rem}");self._set_dirty_status(True);self._update_details_panel(r,"rule");self.selected_sub_condition_index=None;if hasattr(self,'btn_remove_sub_condition'):self.btn_remove_sub_condition.configure(state="disabled");self._highlight_selected_list_item("condition",None,True)
        else:logger.warning(f"Rule '{r.get('name')}' problem removing sub-cond at idx {self.selected_sub_condition_index}.")
    def _convert_condition_structure(self): # (Same)
        if self.selected_rule_index is None: logger.warning("Convert Cond: No rule selected."); return
        rule = self.profile_data["rules"][self.selected_rule_index]; condition_data = rule.get("condition", {}); rule_name = rule.get("name", "UnkRule")
        logger.info(f"Convert Cond Struct for rule '{rule_name}'. Current: {'Cmpd' if 'logical_operator' in condition_data else 'Single'}")
        is_compound = "logical_operator" in condition_data and isinstance(condition_data.get("sub_conditions"), list)
        if is_compound: 
            subs = condition_data.get("sub_conditions", [])
            if len(subs) > 1:
                if not messagebox.askyesno("Confirm", "Convert to single condition?\nOnly the first sub-condition will be kept. Others lost. Continue?"): logger.info("Conv Cmpd to Single cancelled."); return
            new_single_cond = copy.deepcopy(subs[0]) if subs else {"type": "always_true"}
            logger.info(f"Converting Cmpd to Single for '{rule_name}'. Using: {new_single_cond}"); rule["condition"] = new_single_cond
        else: 
            curr_single_cond = copy.deepcopy(condition_data); 
            if not curr_single_cond.get("type"): curr_single_cond = {"type": "always_true"}
            rule["condition"] = {"logical_operator": "AND", "sub_conditions": [curr_single_cond]}
            logger.info(f"Converting Single to Cmpd for '{rule_name}'. Wrapped: {curr_single_cond}")
        self._set_dirty_status(True); self._update_details_panel(rule, "rule"); logger.info(f"Cond struct for '{rule_name}' converted.")


if __name__ == "__main__": 
    from py_pixel_bot.core import config_manager as cm 
    from py_pixel_bot.core import logging_setup     
    cm.load_environment_variables(); logging_setup.setup_logging(); logging_setup.set_console_log_level(logging.DEBUG)
    app = MainAppWindow(); app.mainloop()