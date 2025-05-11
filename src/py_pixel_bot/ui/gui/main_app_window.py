import logging
import tkinter as tk 
from tkinter import filedialog, messagebox
import os
import json 
import copy 
import shutil 
from typing import Optional, Dict, Any, List, Callable, Union, Tuple

import customtkinter as ctk
from PIL import Image 

from py_pixel_bot.core.config_manager import ConfigManager
from py_pixel_bot.ui.gui.region_selector import RegionSelectorWindow 

logger = logging.getLogger(__name__)
APP_ROOT_LOGGER_NAME = "py_pixel_bot" # For consistency if used by other loggers

DEFAULT_PROFILE_STRUCTURE = {
    "profile_description": "New Profile",
    "settings": {"monitoring_interval_seconds": 1.0, "analysis_dominant_colors_k": 3},
    "regions": [], 
    "templates": [], 
    "rules": []
}
MAX_PREVIEW_WIDTH = 200
MAX_PREVIEW_HEIGHT = 150

CONDITION_TYPES = ["pixel_color", "average_color_is", "template_match_found", "ocr_contains_text", "dominant_color_matches", "always_true"]
ACTION_TYPES = ["click", "type_text", "press_key", "log_message"]
LOGICAL_OPERATORS = ["AND", "OR"]
CLICK_TARGET_RELATIONS = ["center_of_region", "center_of_last_match", "absolute", "relative_to_region"]
CLICK_BUTTONS = ["left", "middle", "right"]
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

class MainAppWindow(ctk.CTk):
    """
    Main application window for the PyPixelBot Profile Editor GUI.
    Manages profile loading, saving, and editing of all components.
    """
    def __init__(self, initial_profile_path: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        logger.info("Initializing MainAppWindow...")
        self.title("PyPixelBot Profile Editor")
        self.geometry("1350x800") 

        ctk.set_appearance_mode("System") 

        self.current_profile_path: Optional[str] = None
        self.profile_data: Dict[str, Any] = self._get_default_profile_structure()
        self._is_dirty: bool = False 
        
        self.selected_region_index: Optional[int] = None
        self.selected_template_index: Optional[int] = None
        self.selected_rule_index: Optional[int] = None
        self.selected_sub_condition_index: Optional[int] = None 
        self.selected_sub_condition_item_widget: Optional[ctk.CTkFrame] = None

        self.detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {} 
        self.detail_optionmenu_vars: Dict[str, tk.StringVar] = {} 
        self.template_preview_image_label: Optional[ctk.CTkLabel] = None
        self.sub_conditions_list_frame: Optional[ctk.CTkScrollableFrame] = None
        self.condition_params_frame: Optional[ctk.CTkFrame] = None 
        self.action_params_frame: Optional[ctk.CTkFrame] = None
        self.sub_condition_params_frame: Optional[ctk.CTkFrame] = None
        self.btn_convert_condition: Optional[ctk.CTkButton] = None
        self.btn_remove_sub_condition: Optional[ctk.CTkButton] = None # Ensure this is initialized

        self._setup_ui()

        if initial_profile_path:
            logger.info(f"Attempting to load initial profile: {initial_profile_path}")
            self._load_profile_from_path(initial_profile_path)
        else:
            self._populate_ui_from_profile_data() 
            self._set_dirty_status(False) 
            self.label_current_profile_path.configure(text="Path: New Profile (unsaved)")

        self.protocol("WM_DELETE_WINDOW", self._on_close_window) 
        logger.info("MainAppWindow fully initialized.")

    # --- Helper methods (_get_default_profile_structure, _create_clickable_list_item, _highlight_selected_list_item, _clear_details_panel_content) ---
    def _get_default_profile_structure(self) -> Dict[str, Any]: return copy.deepcopy(DEFAULT_PROFILE_STRUCTURE)
    def _create_clickable_list_item(self, parent_frame: ctk.CTkScrollableFrame, text: str, on_click_callback: Callable): # (Same)
        item_frame = ctk.CTkFrame(parent_frame, fg_color="transparent", corner_radius=0); item_frame.pack(fill="x", pady=1, padx=1)
        label = ctk.CTkLabel(item_frame, text=text, anchor="w", cursor="hand2"); label.pack(side="left", fill="x", expand=True, padx=5, pady=2)
        label.bind("<Button-1>", lambda e, cb=on_click_callback: cb()); item_frame.bind("<Button-1>", lambda e, cb=on_click_callback: cb())
        return item_frame
    def _highlight_selected_list_item(self, list_name: str, new_selected_widget: Optional[ctk.CTkFrame], is_sub_list: bool = False): # (Same)
        attr_name = f"selected_{'sub_' if is_sub_list else ''}{list_name}_item_widget"
        old_selected_widget = getattr(self, attr_name, None)
        if old_selected_widget and old_selected_widget.winfo_exists(): old_selected_widget.configure(fg_color="transparent")
        if new_selected_widget and new_selected_widget.winfo_exists(): new_selected_widget.configure(fg_color=("#DBDBDB", "#2B2B2B")); setattr(self, attr_name, new_selected_widget)
        else: setattr(self, attr_name, None)
    def _clear_details_panel_content(self): # (Same)
        for widget in self.details_panel_content_frame.winfo_children(): widget.destroy()
        self.detail_widgets.clear(); self.detail_optionmenu_vars.clear()
        if self.template_preview_image_label: self.template_preview_image_label.destroy(); self.template_preview_image_label = None
        if self.sub_conditions_list_frame: self.sub_conditions_list_frame.destroy(); self.sub_conditions_list_frame = None
        if self.condition_params_frame: self.condition_params_frame.destroy(); self.condition_params_frame = None
        if self.action_params_frame: self.action_params_frame.destroy(); self.action_params_frame = None
        if self.sub_condition_params_frame: self.sub_condition_params_frame.destroy(); self.sub_condition_params_frame = None
        logger.debug("Cleared details panel content.")

    # --- UI Setup (_setup_ui, _setup_left_panel, _setup_center_panel, _setup_right_panel) ---
    # (These are largely the same)
    def _setup_ui(self): # (Same)
        logger.debug("Setting up UI..."); self.menu_bar=tk.Menu(self); self.config(menu=self.menu_bar); fm=tk.Menu(self.menu_bar,tearoff=0); self.menu_bar.add_cascade(label="File",menu=fm); fm.add_command(label="New",command=self._new_profile,accel="Ctrl+N"); fm.add_command(label="Open",command=self._open_profile,accel="Ctrl+O"); fm.add_separator(); fm.add_command(label="Save",command=self._save_profile,accel="Ctrl+S"); fm.add_command(label="Save As",command=self._save_profile_as,accel="Ctrl+Shift+S"); fm.add_separator();fm.add_command(label="Exit",command=self._on_close_window); self.bind_all("<Control-s>",lambda e:self._save_profile());self.bind_all("<Control-Shift-S>",lambda e:self._save_profile_as());self.bind_all("<Control-o>",lambda e:self._open_profile());self.bind_all("<Control-n>",lambda e:self._new_profile()); self.grid_columnconfigure(0,weight=1,minsize=300);self.grid_columnconfigure(1,weight=2,minsize=350);self.grid_columnconfigure(2,weight=2,minsize=400);self.grid_rowconfigure(0,weight=1); self.left_panel=ctk.CTkFrame(self,cr=0);self.left_panel.grid(row=0,column=0,sticky="nsew",padx=(0,2),pady=0);self._setup_left_panel(); self.center_panel=ctk.CTkFrame(self,cr=0);self.center_panel.grid(row=0,column=1,sticky="nsew",padx=(0,2),pady=0);self._setup_center_panel(); self.right_panel=ctk.CTkFrame(self,cr=0);self.right_panel.grid(row=0,column=2,sticky="nsew",pady=0);self._setup_right_panel(); logger.debug("UI setup complete.")
    def _setup_left_panel(self): # (Same)
        self.left_panel.grid_columnconfigure(0,weight=1); cr=0; pif=ctk.CTkFrame(self.left_panel);pif.grid(row=cr,column=0,sticky="new",padx=10,pady=10);pif.grid_columnconfigure(1,weight=1);cr+=1; ctk.CTkLabel(pif,text="Desc:").grid(row=0,column=0,padx=5,pady=5,sticky="w");self.entry_profile_desc=ctk.CTkEntry(pif,placeholder_text="Desc");self.entry_profile_desc.grid(row=0,column=1,padx=5,pady=5,sticky="ew");self.entry_profile_desc.bind("<KeyRelease>",lambda e:self._set_dirty_status(True)); ctk.CTkLabel(pif,text="Interval:").grid(row=1,column=0,padx=5,pady=5,sticky="w");self.entry_monitor_interval=ctk.CTkEntry(pif,placeholder_text="1.0");self.entry_monitor_interval.grid(row=1,column=1,padx=5,pady=5,sticky="ew");self.entry_monitor_interval.bind("<KeyRelease>",lambda e:self._set_dirty_status(True)); ctk.CTkLabel(pif,text="Dom K:").grid(row=2,column=0,padx=5,pady=5,sticky="w");self.entry_dominant_k=ctk.CTkEntry(pif,placeholder_text="3");self.entry_dominant_k.grid(row=2,column=1,padx=5,pady=5,sticky="ew");self.entry_dominant_k.bind("<KeyRelease>",lambda e:self._set_dirty_status(True)); self.label_current_profile_path=ctk.CTkLabel(pif,text="Path: None",anchor="w",wraplength=300);self.label_current_profile_path.grid(row=3,column=0,columnspan=2,padx=5,pady=(5,0),sticky="ew"); rsf=ctk.CTkFrame(self.left_panel);rsf.grid(row=cr,column=0,sticky="nsew",padx=10,pady=10);rsf.grid_columnconfigure(0,weight=1);rsf.grid_rowconfigure(1,weight=1);cr+=1; ctk.CTkLabel(rsf,text="Regions",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,pady=(0,5),sticky="w");self.regions_list_scroll_frame=ctk.CTkScrollableFrame(rsf,label_text="");self.regions_list_scroll_frame.grid(row=1,column=0,sticky="nsew",padx=0,pady=0); rbf=ctk.CTkFrame(rsf,fg_color="transparent");rbf.grid(row=2,column=0,pady=(5,0),sticky="ew");ctk.CTkButton(rbf,text="Add",command=self._add_region).pack(side="left",padx=2);self.btn_remove_region=ctk.CTkButton(rbf,text="Remove",command=self._remove_selected_region,state="disabled");self.btn_remove_region.pack(side="left",padx=2); tsf=ctk.CTkFrame(self.left_panel);tsf.grid(row=cr,column=0,sticky="nsew",padx=10,pady=10);tsf.grid_columnconfigure(0,weight=1);tsf.grid_rowconfigure(1,weight=1);cr+=1; ctk.CTkLabel(tsf,text="Templates",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,pady=(0,5),sticky="w");self.templates_list_scroll_frame=ctk.CTkScrollableFrame(tsf,label_text="");self.templates_list_scroll_frame.grid(row=1,column=0,sticky="nsew",padx=0,pady=0); tbf=ctk.CTkFrame(tsf,fg_color="transparent");tbf.grid(row=2,column=0,pady=(5,0),sticky="ew");ctk.CTkButton(tbf,text="Add",command=self._add_template).pack(side="left",padx=2);self.btn_remove_template=ctk.CTkButton(tbf,text="Remove",command=self._remove_selected_template,state="disabled");self.btn_remove_template.pack(side="left",padx=2); self.left_panel.grid_rowconfigure(1,weight=1);self.left_panel.grid_rowconfigure(2,weight=1)
    def _setup_center_panel(self): # (Same)
        self.center_panel.grid_columnconfigure(0,weight=1);self.center_panel.grid_rowconfigure(1,weight=1); ctk.CTkLabel(self.center_panel,text="Rules",font=ctk.CTkFont(size=16,weight="bold")).grid(row=0,column=0,padx=10,pady=10,sticky="w"); self.rules_list_scroll_frame=ctk.CTkScrollableFrame(self.center_panel,label_text="");self.rules_list_scroll_frame.grid(row=1,column=0,sticky="nsew",padx=10,pady=5); rbf2=ctk.CTkFrame(self.center_panel,fg_color="transparent");rbf2.grid(row=2,column=0,pady=10,sticky="ew");ctk.CTkButton(rbf2,text="Add Rule",command=self._add_new_rule).pack(side="left",padx=5);self.btn_remove_rule=ctk.CTkButton(rbf2,text="Remove Rule",command=self._remove_selected_rule,state="disabled");self.btn_remove_rule.pack(side="left",padx=5)
    def _setup_right_panel(self): # (Same)
        self.right_panel.grid_columnconfigure(0,weight=1);self.right_panel.grid_rowconfigure(0,weight=1); self.details_panel_scroll_frame=ctk.CTkScrollableFrame(self.right_panel,label_text="Selected Item Details");self.details_panel_scroll_frame.pack(padx=10,pady=10,fill="both",expand=True); self.details_panel_content_frame=ctk.CTkFrame(self.details_panel_scroll_frame,fg_color="transparent");self.details_panel_content_frame.pack(fill="both",expand=True); self.label_details_placeholder=ctk.CTkLabel(self.details_panel_content_frame,text="Select an item.",wraplength=280);self.label_details_placeholder.pack(padx=10,pady=10,anchor="center")

    # --- Core Profile Management & UI Sync/State Methods ---
    def _new_profile(self,event=None):logger.info("New Profile");self._set_dirty_status(False);S=self._prompt_save_if_dirty();logger.debug(f"Prompt save:{S}");if S:self.current_profile_path=None;self.profile_data=self._get_default_profile_structure();self._populate_ui_from_profile_data();self._set_dirty_status(False);self.label_current_profile_path.configure(text="Path:New(unsaved)");logger.info("New profile created.");else:logger.info("New profile cancelled.")
    def _open_profile(self,event=None):logger.info("Open Profile");if not self._prompt_save_if_dirty():logger.info("Open cancelled.");return;fp=filedialog.askopenfilename(title="Open",defaultextension=".json",filetypes=[("JSON","*.json"),("All","*.*")]);logger.info(f"Filepath:{fp}");if fp:self._load_profile_from_path(fp);else:logger.info("Open dialog cancelled.")
    def _load_profile_from_path(self,fp:str):logger.info(f"Loading:{fp}");try:cm=ConfigManager(fp);self.profile_data=cm.get_profile_data();self.current_profile_path=cm.get_profile_path();self._populate_ui_from_profile_data();self._set_dirty_status(False);self.label_current_profile_path.configure(text=f"Path:{self.current_profile_path}");logger.info(f"Loaded:{self.current_profile_path}");except Exception as e:logger.error(f"Failed load '{fp}':{e}",exc_info=True);messagebox.showerror("Load Error",f"Could not load:{fp}\n\nError:{e}")
    def _save_profile(self,event=None):logger.info("Save Profile");P=self.current_profile_path;D=self.profile_data;U=self._update_profile_data_from_ui;CM=ConfigManager;SD=self._set_dirty_status;I=logger.info;E=logger.error;MBE=messagebox.showerror;SA=self._save_profile_as;if P:try:U();CM.save_profile_data_to_path(P,D);SD(False);I(f"Saved:{P}");except Exception as e:E(f"Failed save'{P}':{e}",exc_info=True);MBE("Save Error",f"Could not save:{P}\n\nError:{e}");else:logger.debug("No path, Save As...");SA()
    def _save_profile_as(self,event=None):logger.info("Save Profile As");U=self._update_profile_data_from_ui;P=self.current_profile_path;L=self.label_current_profile_path;SP=self._save_profile;I=logger.info;U();infn=os.path.basename(P)if P else "new.json";fp=filedialog.asksaveasfilename(title="Save As",defaultextension=".json",filetypes=[("JSON","*.json"),("All","*.*")],initialfile=infn);if fp:self.current_profile_path=fp;L.configure(text=f"Path:{self.current_profile_path}");SP();else:I("Save As cancelled.")
    def _populate_ui_from_profile_data(self):logger.debug("Populating UI...");EPD=self.entry_profile_desc;S=self.profile_data.get("settings",{});EMI=self.entry_monitor_interval;EDK=self.entry_dominant_k;PSLF=self._populate_specific_list_frame;RLSF=self.regions_list_scroll_frame;PDGR=self.profile_data.get("regions",[]);BRR=self.btn_remove_region;TLSF=self.templates_list_scroll_frame;PDGT=self.profile_data.get("templates",[]);BRT=self.btn_remove_template;RLSF2=self.rules_list_scroll_frame;PDGR2=self.profile_data.get("rules",[]);BRR2=self.btn_remove_rule;UDP=self._update_details_panel; EPD.delete(0,tk.END);EPD.insert(0,self.profile_data.get("profile_description","")); EMI.delete(0,tk.END);EMI.insert(0,str(S.get("monitoring_interval_seconds",1.0)));EDK.delete(0,tk.END);EDK.insert(0,str(S.get("analysis_dominant_colors_k",3))); PSLF("region",RLSF,PDGR,lambda i,x:i.get("name",f"Region {x+1}"),BRR,"region");PSLF("template",TLSF,PDGT,lambda i,x:f"{i.get('name',f'Template {x+1}')} ({i.get('filename','N/A')})",BRT,"template");PSLF("rule",RLSF2,PDGR2,lambda i,x:i.get("name",f"Rule {x+1}"),BRR2,"rule"); UDP(None,"none");logger.debug("UI population complete.")
    def _populate_specific_list_frame(self,ltn:str,fw:ctk.CTkScrollableFrame,id:List[Dict],dtcb:Callable,btm:ctk.CTkButton,lstfn_attr:str): 
        for w in fw.winfo_children():w.destroy(); setattr(self,f"selected_{lstfn_attr}_item_widget",None);setattr(self,f"selected_{lstfn_attr}_index",None);
        if btm:btm.configure(state="disabled");
        for i,item_d in enumerate(id):display_text=dtcb(item_d,i);item_f=ctk.CTkFrame(fw,fg_color="transparent",corner_radius=0);item_f.pack(fill="x",pady=1,padx=1);lbl=ctk.CTkLabel(item_f,text=display_text,anchor="w",cursor="hand2");lbl.pack(side="left",fill="x",expand=True,padx=5,pady=2);lbl.bind("<Button-1>",lambda e,n=lstfn_attr,d=item_d,x=i,f=item_f:self._on_item_selected(n,d,x,f));item_f.bind("<Button-1>",lambda e,n=lstfn_attr,d=item_d,x=i,f=item_f:self._on_item_selected(n,d,x,f))
    def _update_profile_data_from_ui(self): # MODIFIED to use _validate_and_get_widget_value for settings
        if not self.profile_data: self.profile_data = self._get_default_profile_structure()
        logger.debug("Updating profile_data (settings) from UI input fields...")
        # Profile description is free text, no strict validation here beyond what _validate_and_get_widget_value does for string
        desc_val, desc_valid = self._validate_and_get_widget_value(self.entry_profile_desc, "Profile Description", str, default_val=DEFAULT_PROFILE_STRUCTURE["profile_description"], allow_empty_string=True)
        if desc_valid: self.profile_data["profile_description"] = desc_val # Only update if valid (though str always is here)
        
        settings = self.profile_data.get("settings", {})
        interval_val, is_valid_interval = self._validate_and_get_widget_value(self.entry_monitor_interval, "Monitoring Interval", float, default_val=DEFAULT_PROFILE_STRUCTURE["settings"]["monitoring_interval_seconds"], min_val=0.01)
        if is_valid_interval: settings["monitoring_interval_seconds"] = interval_val
        else: logger.warning(f"Monitoring Interval not updated due to validation error for input: '{self.entry_monitor_interval.get()}'.")

        k_val, is_valid_k = self._validate_and_get_widget_value(self.entry_dominant_k, "Dominant K", int, default_val=DEFAULT_PROFILE_STRUCTURE["settings"]["analysis_dominant_colors_k"], min_val=1, max_val=20) # Max 20 for k-means sanity
        if is_valid_k: settings["analysis_dominant_colors_k"] = k_val
        else: logger.warning(f"Dominant K not updated due to validation error for input: '{self.entry_dominant_k.get()}'.")

        self.profile_data["settings"] = settings
        logger.debug(f"Profile_data (settings) updated from UI. Current: {settings}")
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
            if hasattr(self,'btn_remove_sub_condition') and self.btn_remove_sub_condition: self.btn_remove_sub_condition.configure(state="disabled") # Ensure defined before use
            row_idx=0;ctk.CTkLabel(self.details_panel_content_frame,text="Rule Name:").grid(row=row_idx,column=0,sticky="w",padx=5,pady=2);self.detail_widgets["rule_name"]=ctk.CTkEntry(self.details_panel_content_frame);self.detail_widgets["rule_name"].insert(0,item_data.get("name",""));self.detail_widgets["rule_name"].grid(row=row_idx,column=1,sticky="ew",padx=5,pady=2);row_idx+=1
            ctk.CTkLabel(self.details_panel_content_frame,text="Default Region:").grid(row=row_idx,column=0,sticky="w",padx=5,pady=2);r_names=[""]+[r.get("name","")for r in self.profile_data.get("regions",[])if r.get("name")];self.detail_optionmenu_vars["rule_region"]=ctk.StringVar(value=item_data.get("region",""));r_menu=ctk.CTkOptionMenu(self.details_panel_content_frame,variable=self.detail_optionmenu_vars["rule_region"],values=r_names,command=lambda c:self._set_dirty_status(True));r_menu.grid(row=row_idx,column=1,sticky="ew",padx=5,pady=2);row_idx+=1
            cond_data=copy.deepcopy(item_data.get("condition",{}));act_data=copy.deepcopy(item_data.get("action",{}))
            cond_outer_f=ctk.CTkFrame(self.details_panel_content_frame);cond_outer_f.grid(row=row_idx,column=0,columnspan=2,sticky="new",pady=(10,0));cond_outer_f.grid_columnconfigure(0,weight=1);row_idx+=1
            cond_hdr_f=ctk.CTkFrame(cond_outer_f,fg_color="transparent");cond_hdr_f.pack(fill="x",padx=5);ctk.CTkLabel(cond_hdr_f,text="CONDITION",font=ctk.CTkFont(weight="bold")).pack(side="left",anchor="w")
            is_compound="logical_operator"in cond_data and isinstance(cond_data.get("sub_conditions"),list)
            btn_text = "Convert to Single" if is_compound else "Convert to Compound"
            # Store button ref if not exists, then configure
            if not hasattr(self, 'btn_convert_condition') or self.btn_convert_condition is None:
                self.btn_convert_condition = ctk.CTkButton(cond_hdr_f,text=btn_text,command=self._convert_condition_structure,width=160)
                self.btn_convert_condition.pack(side="right",padx=(0,5))
            else: # Button exists, just update text
                self.btn_convert_condition.configure(text=btn_text)
            
            self.condition_params_frame=ctk.CTkFrame(cond_outer_f,fg_color="transparent");self.condition_params_frame.pack(fill="x",expand=True,padx=5,pady=(0,5));self.condition_params_frame.grid_columnconfigure(1,weight=1)
            self._render_rule_condition_editor(cond_data)
            act_outer_f=ctk.CTkFrame(self.details_panel_content_frame);act_outer_f.grid(row=row_idx,column=0,columnspan=2,sticky="new",pady=(10,0));act_outer_f.grid_columnconfigure(0,weight=1);row_idx+=1;ctk.CTkLabel(act_outer_f,text="ACTION",font=ctk.CTkFont(weight="bold")).pack(anchor="w",padx=5);self.action_params_frame=ctk.CTkFrame(act_outer_f,fg_color="transparent");self.action_params_frame.pack(fill="x",expand=True,padx=5,pady=(0,5));self.action_params_frame.grid_columnconfigure(1,weight=1);ctk.CTkLabel(self.action_params_frame,text="Action Type:").grid(row=0,column=0,sticky="w",padx=5,pady=2);i_act_type=str(act_data.get("type","log_message"));self.detail_optionmenu_vars["action_type"]=ctk.StringVar(value=i_act_type);act_type_menu=ctk.CTkOptionMenu(self.action_params_frame,variable=self.detail_optionmenu_vars["action_type"],values=ACTION_TYPES,command=lambda choice:self._on_rule_part_type_change("action",choice));act_type_menu.grid(row=0,column=1,sticky="ew",padx=5,pady=2);self._render_action_parameters(act_data,self.action_params_frame,start_row=1)
            ctk.CTkButton(self.details_panel_content_frame,text="Apply Rule Changes",command=self._apply_rule_changes).grid(row=row_idx,column=0,columnspan=2,pady=(20,5))
        elif item_data: details_text=json.dumps(item_data,indent=2);tb=ctk.CTkTextbox(self.details_panel_content_frame,wrap="word",height=500);tb.pack(fill="both",expand=True,padx=5,pady=5);tb.insert("0.0",details_text);tb.configure(state="disabled");logger.debug(f"Details for {item_type}(JSON):{str(item_data)[:100]}")
        else: self.label_details_placeholder = ctk.CTkLabel(self.details_panel_content_frame, text="Select an item.", wraplength=250); self.label_details_placeholder.pack(padx=10, pady=10, anchor="center"); logger.debug("Details panel cleared.")


    # --- Input Validation Helpers ---
    def _validate_and_get_widget_value(
        self, widget_key_or_widget: Union[str, ctk.CTkEntry, ctk.CTkTextbox, ctk.CTkOptionMenu, ctk.CTkCheckBox],
        field_name_for_error: str, target_type: type, default_value: Any,
        allow_empty_string: bool = False, 
        min_val: Optional[Union[int, float]] = None, max_val: Optional[Union[int, float]] = None,
        required: bool = True # If true and allow_empty_string is false, empty is an error
    ) -> Tuple[Any, bool]:
        """
        Safely gets value, performs type conversion and validation.
        Returns (converted_value, is_valid_bool).
        If not valid, converted_value is default_value (or original problematic string if no default).
        Shows messagebox on validation error.
        """
        value_str: Optional[str] = None; raw_value: Any = None; widget_key: str
        L=logger; MBE=messagebox.showerror

        if isinstance(widget_key_or_widget, str): widget = self.detail_widgets.get(widget_key_or_widget); widget_key = widget_key_or_widget
        else: widget = widget_key_or_widget; widget_key = next((k for k,v in self.detail_widgets.items() if v == widget), f"unknown_widget_for_{field_name_for_error}")
        
        if widget is None: L.error(f"Val Error for '{field_name_for_error}': Widget '{widget_key}' not found."); MBE("Internal Error",f"Widget for '{field_name_for_error}' missing."); return default_value, False

        if isinstance(widget,(ctk.CTkEntry,ctk.CTkTextbox)): value_str=widget.get("0.0",tk.END).strip() if isinstance(widget,ctk.CTkTextbox)else widget.get(); raw_value=value_str
        elif isinstance(widget,ctk.CTkOptionMenu): var_k=next((k for k,v in self.detail_widgets.items()if v==widget and k.endswith("_var")),f"{widget_key}_var");sv=self.detail_optionmenu_vars.get(var_k);
        if sv:value_str=sv.get();raw_value=value_str;else:L.error(f"Val Error '{field_name_for_error}': StringVar for OptMenu '{widget_key}' missing.");return default_value,False
        elif isinstance(widget,ctk.CTkCheckBox):var_k=next((k for k,v in self.detail_widgets.items()if v==widget and k.endswith("_var")),f"{widget_key}_var");bv=self.detail_optionmenu_vars.get(var_k);
        if bv and isinstance(bv,tk.BooleanVar):raw_value=bv.get();else:L.error(f"Val Error '{field_name_for_error}': BoolVar for CheckBox '{widget_key}' missing.");return default_value,False
        else:L.error(f"Val Error '{field_name_for_error}': Unsupported widget type '{type(widget)}'.");return default_value,False

        current_value_for_default = value_str if value_str is not None else raw_value # Use for default if conversion fails

        if target_type == str:
            final_val = value_str if value_str is not None else ""
            if required and not allow_empty_string and not final_val.strip():
                L.warning(f"Val Fail '{field_name_for_error}': Input empty. Val:'{final_val}'");MBE("Input Error",f"'{field_name_for_error}' cannot be empty.");return default_value,False
            return final_val,True

        if target_type == bool:
            if isinstance(raw_value,bool):return raw_value,True
            if value_str is not None:
                if value_str.lower()=='true':return True,True
                if value_str.lower()=='false':return False,True
            L.warning(f"Val Fail '{field_name_for_error}':Cannot convert '{raw_value}' to bool.");MBE("Input Error",f"Invalid bool for '{field_name_for_error}'.Use True/False.");return default_value,False
        
        # Numeric types
        if value_str is None or not value_str.strip(): # Empty string for number
            if required: L.warning(f"Val Fail '{field_name_for_error}':Numeric input empty.");MBE("Input Error",f"'{field_name_for_error}' needs a number.");return default_value,False
            return default_value, True # Optional and empty, use default

        try:
            num_val:Union[int,float]
            if target_type==int:num_val=int(value_str)
            elif target_type==float:num_val=float(value_str)
            else:L.error(f"Val Error:Unexpected target_type {target_type} for num.");return default_value,False
            if min_val is not None and num_val<min_val:L.warning(f"Val Fail '{field_name_for_error}':Val {num_val}<min {min_val}.");MBE("Input Error",f"'{field_name_for_error}' must be >= {min_val}.");return default_value,False
            if max_val is not None and num_val>max_val:L.warning(f"Val Fail '{field_name_for_error}':Val {num_val}>max {max_val}.");MBE("Input Error",f"'{field_name_for_error}' must be <= {max_val}.");return default_value,False
            L.debug(f"Val success '{field_name_for_error}':'{value_str}' to {num_val}.");return num_val,True
        except(ValueError,TypeError):L.warning(f"Val Fail '{field_name_for_error}':Cannot convert '{value_str}' to {target_type.__name__}.");MBE("Input Error",f"'{field_name_for_error}' must be {target_type.__name__}.");return default_value,False

    def _parse_bgr_string(self, bgr_s: str, field_name: str) -> Optional[List[int]]: # NEW
        if not isinstance(bgr_s,str):logger.warning(f"Val '{field_name}':BGR not str ('{bgr_s}').");messagebox.showerror("Input Error",f"'{field_name}' must be B,G,R str.");return None
        parts=bgr_s.split(','); L=logger; MBE=messagebox.showerror
        if len(parts)!=3:L.warning(f"Val '{field_name}':BGR str '{bgr_s}' not 3 parts.");MBE("Input Error",f"'{field_name}' must be 3 B,G,R numbers.");return None
        try:
            vals=[int(p.strip())for p in parts];
            if not all(0<=v<=255 for v in vals):L.warning(f"Val '{field_name}':BGR vals '{vals}' out of 0-255.");MBE("Input Error",f"'{field_name}' BGR vals 0-255.");return None
            L.debug(f"Parsed BGR str '{bgr_s}' to {vals} for '{field_name}'.");return vals
        except ValueError:L.warning(f"Val '{field_name}':BGR str '{bgr_s}' non-int.");MBE("Input Error",f"'{field_name}' BGR vals must be int.");return None
        
    # --- Parameter Rendering & Collection (largely same, relies on new validation) ---
    def _render_condition_parameters(self,cd:Dict,pf:ctk.CTkFrame,sr:int,issc:bool=False):# (Same render logic)
        px="subcond_"if issc else"cond_";logger.debug(f"Render cond(sub={issc})params type:{cd.get('type')},prefix:{px},data:{cd}");
        for w in list(pf.winfo_children()):gi=w.grid_info();if gi and gi.get("row",-1)>=sr:w.destroy()
        ktr=[k for k in self.detail_widgets if k.startswith(px)];for k in ktr:self.detail_widgets.pop(k);self.detail_optionmenu_vars.pop(f"{k}_var",None)
        ct=cd.get("type");cr=sr;def add_pe(k,dv,l=None,r=None,p=None,itb=False):nonlocal cr;row=r if r is not None else cr;_l=l if l else k.replace("_"," ").capitalize()+":";ctk.CTkLabel(pf,text=_l).grid(row=row,column=0,padx=5,pady=2,sticky="nw"if itb else"w");
        if itb:w=ctk.CTkTextbox(pf,h=60,wrap="word");w.insert("0.0",str(cd.get(k,dv)));w.bind("<FocusOut>",lambda e:self._set_dirty_status(True));else:w=ctk.CTkEntry(pf,ph=p if p else str(dv));w.insert(0,str(cd.get(k,dv)));w.bind("<KeyRelease>",lambda e:self._set_dirty_status(True));
        w.grid(row=row,column=1,padx=5,pady=2,sticky="ew");self.detail_widgets[f"{px}{k}"]=w;if r is None:cr+=1;return w
        def add_po(k,dv,vs,l=None,r=None):nonlocal cr;row=r if r is not None else cr;_l=l if l else k.replace("_"," ").capitalize()+":";ctk.CTkLabel(pf,text=_l).grid(row=row,column=0,padx=5,pady=2,sticky="w");
        v=ctk.StringVar(value=str(cd.get(k,dv)));m=ctk.CTkOptionMenu(pf,variable=v,values=vs,command=lambda c:self._set_dirty_status(True));m.grid(row=row,column=1,padx=5,pady=2,sticky="ew");self.detail_widgets[f"{px}{k}"]=m;self.detail_optionmenu_vars[f"{px}{key}_var"]=v;if r is None:cr+=1;return m
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

    def _get_condition_parameters_from_ui(self, ct: str, is_sub_condition: bool = False) -> Optional[Dict[str, Any]]: # MODIFIED to use new validation
        prefix = "subcond_" if is_sub_condition else "cond_"
        params: Dict[str, Any] = {"type": ct}; all_valid = True; L=logger; V = self._validate_and_get_widget_value; PBGR = self._parse_bgr_string
        L.debug(f"Getting UI params for cond type: {ct}(sub={is_sub_condition})")
        def get_val(key:str,fn:str,tt:type,dv:Any,**kw): nonlocal all_valid; val,is_v=V(f"{prefix}{key}",fn,tt,dv,**kw); if not is_v:all_valid=False; return val
        def get_bgr(key:str,fn:str,ds:str): nonlocal all_valid;bs_val,is_s_v=V(f"{prefix}{key}",fn,str,ds);pbgr=PBGR(bs_val,fn)if is_s_v else None;if pbgr is None:all_valid=False;return pbgr if pbgr else ([0,0,0] if "pixel" in ct else [128,128,128] if "avg" in ct else [0,0,255]) # default based on type
        
        if ct=="pixel_color":params["relative_x"]=get_val("relative_x","Rel X",int,0,required=True);params["relative_y"]=get_val("relative_y","Rel Y",int,0,required=True);params["expected_bgr"]=get_bgr("expected_bgr","Exp BGR","0,0,0");params["tolerance"]=get_val("tolerance","Tolerance",int,0,min_val=0,max_val=255,required=True)
        elif ct=="average_color_is":params["expected_bgr"]=get_bgr("expected_bgr","Exp BGR","128,128,128");params["tolerance"]=get_val("tolerance","Tolerance",int,10,min_val=0,max_val=255,required=True)
        elif ct=="template_match_found":
            sel_tpl_name_var=self.detail_optionmenu_vars.get(f"{prefix}template_name_var",tk.StringVar());sel_tpl_name=sel_tpl_name_var.get();afn="";
            if not sel_tpl_name: L.warning(f"Template Name for '{ct}' not selected."); all_valid=False # Required
            else:
                for t in self.profile_data.get("templates",[]):
                    if t.get("name")==sel_tpl_name:afn=t.get("filename","");break
                if not afn: L.warning(f"No filename for tpl name '{sel_tpl_name}'."); all_valid=False
            params["template_filename"]=afn;params["min_confidence"]=get_val("min_confidence","Min Conf",float,0.8,min_val=0.0,max_val=1.0,required=True);params["capture_as"]=get_val("capture_as","Capture As",str,"",allow_empty_string=True,required=False)
        elif ct=="ocr_contains_text":params["text_to_find"]=get_val("text_to_find","Text to Find",str,"",allow_empty_string=False,required=True);params["case_sensitive"]=get_val("case_sensitive","Case Sensitive",bool,False,required=False);params["min_ocr_confidence"]=get_val("min_ocr_confidence","Min OCR Conf",float,70.0,min_val=0.0,max_val=100.0,required=False);params["capture_as"]=get_val("capture_as","Capture As",str,"",allow_empty_string=True,required=False)
        elif ct=="dominant_color_matches":params["expected_bgr"]=get_bgr("expected_bgr","Exp BGR","0,0,255");params["tolerance"]=get_val("tolerance","Tolerance",int,10,min_val=0,max_val=255,required=True);params["check_top_n_dominant"]=get_val("check_top_n_dominant","Check Top N",int,1,min_val=1,required=True);params["min_percentage"]=get_val("min_percentage","Min Perc",float,5.0,min_val=0.0,max_val=100.0,required=True)
        
        if not all_valid: L.error(f"Validation failed for cond '{ct}' (sub={issc})."); return None
        L.debug(f"Collected valid cond params (sub={issc}) from UI:{params}"); return params

    def _get_action_parameters_from_ui(self, at: str) -> Optional[Dict[str, Any]]: # MODIFIED to use new validation
        prefix = "act_"; params: Dict[str, Any] = {"type": at}; all_valid = True; L=logger;V=self._validate_and_get_widget_value;DOV=self.detail_optionmenu_vars
        L.debug(f"Get UI params action:{at}")
        def get_val(key:str,fn:str,tt:type,dv:Any,**kw):nonlocal all_valid;val,is_v=V(f"{prefix}{key}",fn,tt,dv,**kw);if not is_v:all_valid=False;return val
        
        r_names=[""]+[r.get("name","")for r in self.profile_data.get("regions",[])if r.get("name")]
        if at=="click":
            params["target_relation"]=DOV.get(f"{prefix}target_relation_var",tk.StringVar()).get()
            params["target_region"]=DOV.get(f"{prefix}target_region_var",tk.StringVar()).get()
            # Coords are strings for variables, ActionExecutor will try to parse later if needed
            params["x"]=get_val("x","X Coord/Offset",str,"0",allow_empty_string=True,required=False) 
            params["y"]=get_val("y","Y Coord/Offset",str,"0",allow_empty_string=True,required=False)
            params["button"]=DOV.get(f"{prefix}button_var",tk.StringVar()).get()
            params["clicks"]=get_val("clicks","Num Clicks",str,"1",allow_empty_string=True,required=False) # String for var
            params["interval"]=get_val("interval","Click Interval",str,"0.0",allow_empty_string=True,required=False) # String for var
            params["pyautogui_pause_before"]=get_val("pyautogui_pause_before","Pause Before",str,"0.0",allow_empty_string=True,required=False) # String for var
        elif at=="type_text":params["text"]=V(f"{prefix}text","Text to Type",str,"",allow_empty_string=True,required=False)[0];params["interval"]=get_val("interval","Type Interval",str,"0.0",allow_empty_string=True,required=False);params["pyautogui_pause_before"]=get_val("pyautogui_pause_before","Pause Before",str,"0.0",allow_empty_string=True,required=False)
        elif at=="press_key":params["key"]=get_val("key","Key(s) to Press",str,"enter",allow_empty_string=False,required=True);params["pyautogui_pause_before"]=get_val("pyautogui_pause_before","Pause Before",str,"0.0",allow_empty_string=True,required=False)
        elif at=="log_message":params["message"]=V(f"{prefix}message","Log Message",str,"Rule triggered",allow_empty_string=True,required=False)[0];params["level"]=DOV.get(f"{prefix}level_var",tk.StringVar()).get()
        
        if not all_valid: L.error(f"Validation failed for action '{at}'."); return None
        L.debug(f"Collected valid action params from UI:{params}"); return params


    # --- Apply Changes Methods (Modified to use new validation returns) ---
    def _apply_region_changes(self): # MODIFIED
        if self.selected_region_index is None: logger.warning("Apply Region: No region selected."); return
        rl:List[Dict]=self.profile_data["regions"];crd=rl[self.selected_region_index];on=crd.get("name","Unk");logger.info(f"Applying changes to region '{on}'.")
        V=self._validate_and_get_widget_value
        nn,nv=V("name","Region Name",str,on,allow_empty_string=False);nx,xv=V("x","X",int,crd.get("x",0),required=True);ny,yv=V("y","Y",int,crd.get("y",0),required=True);nw,wv=V("width","Width",int,crd.get("width",1),min_val=1,required=True);nh,hv=V("height","Height",int,crd.get("height",1),min_val=1,required=True)
        if not(nv and xv and yv and wv and hv):logger.error(f"Apply Region '{on}' aborted: validation errors.");return
        crd.update({"name":nn,"x":nx,"y":ny,"width":nw,"height":nh});logger.info(f"Region '{on}' updated to '{nn}'.");self._set_dirty_status(True);self._populate_specific_list_frame("region",self.regions_list_scroll_frame,self.profile_data.get("regions",[]),lambda i,x:i.get("name",f"Region {x+1}"),self.btn_remove_region,"region");self._update_details_panel(crd,"region");messagebox.showinfo("Region Updated",f"Region '{nn}' updated.")
    def _apply_template_changes(self): # MODIFIED
        if self.selected_template_index is None: logger.warning("Apply Template: No tpl selected."); return
        tl:List[Dict]=self.profile_data["templates"];ctd=tl[self.selected_template_index];on=ctd.get("name","Unk");logger.info(f"Applying changes to tpl '{on}'.")
        nn,nv=self._validate_and_get_widget_value("template_name","Template Name",str,on,allow_empty_string=False)
        if not nv:return
        if any(i!=self.selected_template_index and t.get("name")==nn for i,t in enumerate(tl)):messagebox.showerror("Name Error",f"Name '{nn}' exists.");logger.warning(f"Apply Template: Name '{nn}' collision.");return
        ctd["name"]=nn;logger.info(f"Tpl '{on}' name to '{nn}'.");self._set_dirty_status(True);self._populate_specific_list_frame("template",self.templates_list_scroll_frame,self.profile_data.get("templates",[]),lambda i,x:f"{i.get('name',f'Tpl {x+1}')}({i.get('filename','N/A')})",self.btn_remove_template,"template");self._update_details_panel(ctd,"template");messagebox.showinfo("Tpl Updated",f"Tpl '{nn}' updated.")

    def _apply_rule_changes(self): # MODIFIED to use validation returns
        if self.selected_rule_index is None or not self.profile_data: logger.warning("Apply Rule: No rule selected."); return
        rule_list: List[Dict]=self.profile_data["rules"]; current_rule_data_orig=rule_list[self.selected_rule_index]; old_name=current_rule_data_orig.get("name","Unknown")
        logger.info(f"Attempting to apply changes to rule '{old_name}'.")
        
        # Work on a deep copy to only commit if all validations pass
        temp_rule_data = copy.deepcopy(current_rule_data_orig)

        new_name, name_valid = self._validate_and_get_widget_value(self.detail_widgets["rule_name"], "Rule Name", str, old_name, allow_empty_string=False)
        if not name_valid: return
        new_default_region = self.detail_optionmenu_vars["rule_region"].get()
        temp_rule_data["name"] = new_name; temp_rule_data["region"] = new_default_region if new_default_region else ""

        condition_data_to_save = {} # This will hold the fully validated condition
        is_compound_in_ui = "logical_operator" in self.detail_optionmenu_vars 
        
        if is_compound_in_ui:
            condition_data_to_save["logical_operator"] = self.detail_optionmenu_vars["logical_operator"].get()
            saved_sub_conditions = []
            # Iterate through sub-conditions currently in profile_data for this rule,
            # if one was selected and edited, its parameters are fetched from UI.
            # This assumes sub-conditions list itself (add/remove) modified profile_data directly.
            profile_sub_conditions = temp_rule_data.get("condition",{}).get("sub_conditions", [])
            for idx, sub_cond_in_profile in enumerate(profile_sub_conditions):
                if self.selected_sub_condition_index == idx: # This is the one being edited in UI
                    sub_cond_type_var = self.detail_optionmenu_vars.get("subcond_condition_type_var")
                    if sub_cond_type_var:
                        sub_cond_type_ui = sub_cond_type_var.get()
                        validated_sub_params = self._get_condition_parameters_from_ui(sub_cond_type_ui, is_sub_condition=True)
                        if validated_sub_params is None: logger.error(f"Validation failed for sub-condition #{idx} of rule '{new_name}'. Aborting rule save."); return
                        saved_sub_conditions.append(validated_sub_params)
                    else: # Should not happen if UI is consistent
                        logger.error(f"Sub-condition #{idx} selected but its type UI element not found. Using original data."); saved_sub_conditions.append(copy.deepcopy(sub_cond_in_profile))
                else: # Not the selected one, keep its data from profile_data
                    saved_sub_conditions.append(copy.deepcopy(sub_cond_in_profile))
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
        
        # All validations passed, commit temp_rule_data to actual profile_data
        self.profile_data["rules"][self.selected_rule_index] = temp_rule_data
        logger.info(f"Rule '{old_name}' updated to '{new_name}' with validated params."); self._set_dirty_status(True)
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
            if self.selected_sub_condition_index is not None:
                if not self.sub_condition_params_frame:return;scs=crd.get("condition",{}).get("sub_conditions",[]);
                if 0<=self.selected_sub_condition_index<len(scs):scd_tu=scs[self.selected_sub_condition_index];
                if scd_tu.get("type")!=new_type_selected:logger.debug(f"Sub-cond type changing. Clearing old.");scd_tu.clear()
                scd_tu["type"]=new_type_selected;self._render_condition_parameters(scd_tu,self.sub_condition_params_frame,1,True)
            elif "logical_operator" not in crd.get("condition",{}): 
                if not self.condition_params_frame:return;cd_tu=crd.get("condition",{});
                if cd_tu.get("type")!=new_type_selected:logger.debug(f"Main cond type changing. Clearing old.");cd_tu.clear()
                cd_tu["type"]=new_type_selected;self._render_condition_parameters(cd_tu,self.condition_params_frame,2,False)
        elif part_changed=="action":
            if not self.action_params_frame:return;ad_tu=crd.get("action",{});
            if ad_tu.get("type")!=new_type_selected:logger.debug(f"Action type changing. Clearing old.");ad_tu.clear()
            ad_tu["type"]=new_type_selected;self._render_action_parameters(ad_tu,self.action_params_frame,1)
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