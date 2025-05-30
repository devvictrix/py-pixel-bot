import logging
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import json
import copy
import time 
from typing import Optional, Dict, Any, List, Union, Callable

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk, ImageDraw, UnidentifiedImageError, ImageFont

from mark_i.generation.strategy_planner import StrategyPlanner, IntermediatePlan, IntermediatePlanStep
from mark_i.generation.profile_generator import ProfileGenerator, DEFAULT_CONDITION_STRUCTURE_PG, DEFAULT_ACTION_STRUCTURE_PG
# Import the new SubImageSelectorWindow
from mark_i.ui.gui.generation.sub_image_selector_window import SubImageSelectorWindow # NEW
from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.core.config_manager import ConfigManager
# RegionSelectorWindow might not be needed if SubImageSelector handles all selection on images
# from mark_i.ui.gui.region_selector import RegionSelectorWindow 
from mark_i.core.capture_engine import CaptureEngine

from mark_i.ui.gui.gui_config import (
    CONDITION_TYPES as ALL_CONDITION_TYPES_FROM_CONFIG,
    ACTION_TYPES as ALL_ACTION_TYPES_FROM_CONFIG,
    UI_PARAM_CONFIG, OPTIONS_CONST_MAP
)
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.generation.profile_creation_wizard")

# ... (PAGE constants and other constants as before) ...
PAGE_GOAL_INPUT = 0; PAGE_PLAN_REVIEW = 1; PAGE_STEP_DEFINE_REGION = 2; PAGE_STEP_DEFINE_LOGIC = 3; PAGE_FINAL_REVIEW_SAVE = 4
WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH = 600; WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT = 380 # Adjusted
CANDIDATE_BOX_COLORS = ["#FF00FF", "#00FFFF", "#FFFF00", "#F08080", "#90EE90", "#ADD8E6", "#FFC0CB", "#E6E6FA"]
SELECTED_CANDIDATE_BOX_COLOR = "lime green"; FONT_PATH_PRIMARY = "arial.ttf"; FONT_PATH_FALLBACK = "DejaVuSans.ttf"


class ProfileCreationWizardWindow(ctk.CTkToplevel): # Content from previous response, with _handle_capture_template_for_step implemented
    # ... (__init__ and all other methods as in the previous response, up to _handle_ai_refine_element) ...
    # --- START OF COPIED/UNCHANGED METHODS FROM PREVIOUS FULL WIZARD RESPONSE ---
    def __init__(self, master: Any, main_app_instance: Any):
        super().__init__(master)
        self.main_app_instance = main_app_instance
        self.title("AI Profile Creator Wizard")
        self.transient(master); self.grab_set(); self.attributes("-topmost", True)
        self.geometry("1050x850"); self.minsize(950, 750)
        self.protocol("WM_DELETE_WINDOW", self._on_close_wizard)
        if not hasattr(self.main_app_instance, 'gemini_analyzer_instance') or \
           not self.main_app_instance.gemini_analyzer_instance or \
           not self.main_app_instance.gemini_analyzer_instance.client_initialized:
            messagebox.showerror("Critical API Error", "Gemini API client not initialized.", parent=self)
            self.after(100, self.destroy); return
        self.strategy_planner = StrategyPlanner(gemini_analyzer=self.main_app_instance.gemini_analyzer_instance)
        self.profile_generator = ProfileGenerator(gemini_analyzer=self.main_app_instance.gemini_analyzer_instance, config_manager=self.main_app_instance.config_manager)
        self.capture_engine = CaptureEngine()
        self.current_page_index: int = PAGE_GOAL_INPUT; self.intermediate_plan: Optional[IntermediatePlan] = None
        self.current_full_context_pil: Optional[Image.Image] = None; self.current_full_context_np: Optional[np.ndarray] = None
        self.user_goal_text: str = ""; self.generated_profile_name_base: str = "ai_generated_profile"
        self.current_plan_step_data: Optional[IntermediatePlanStep] = None; self.current_step_region_name: Optional[str] = None
        self.current_step_region_coords: Optional[Dict[str, int]] = None; self.current_step_region_image_np: Optional[np.ndarray] = None
        self.current_step_region_image_pil_for_display: Optional[Image.Image] = None; self._temp_suggested_region_coords: Optional[Dict[str,int]] = None
        self.suggested_condition_for_step: Optional[Dict[str, Any]] = None; self.suggested_action_for_step: Optional[Dict[str, Any]] = None
        self.element_to_refine_desc_for_step: Optional[str] = None; self.refined_element_candidates: List[Dict[str, Any]] = []
        self.selected_candidate_box_index: Optional[int] = None; self.confirmed_element_for_action: Optional[Dict[str, Any]] = None
        self._current_step_temp_var_name_for_gemini_element: Optional[str] = None
        self.main_content_frame = ctk.CTkFrame(self, fg_color="transparent"); self.main_content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        self.main_content_frame.grid_rowconfigure(0, weight=1); self.main_content_frame.grid_columnconfigure(0, weight=1)
        self.navigation_frame = ctk.CTkFrame(self, height=60, fg_color=("gray80", "gray20"), corner_radius=0); self.navigation_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        self.navigation_frame.grid_columnconfigure(0, weight=1); self.navigation_frame.grid_columnconfigure(4, weight=1)
        self.btn_cancel = ctk.CTkButton(self.navigation_frame, text="Cancel Generation", command=self._on_close_wizard, width=160, fg_color="firebrick1", hover_color="firebrick3"); self.btn_cancel.grid(row=0, column=1, padx=(20,5), pady=10, sticky="w")
        self.btn_next = ctk.CTkButton(self.navigation_frame, text="Next >", command=self._go_to_next_page, width=130, font=ctk.CTkFont(weight="bold")); self.btn_next.grid(row=0, column=3, padx=(5,20), pady=10, sticky="e")
        self.btn_previous = ctk.CTkButton(self.navigation_frame, text="< Previous", command=self._go_to_previous_page, width=130); self.btn_previous.grid(row=0, column=2, padx=5, pady=10, sticky="e")
        self._page_frames_cache: Dict[int, ctk.CTkFrame] = {}
        self.step_logic_detail_widgets = {}; self.step_logic_optionmenu_vars = {}; self.step_logic_param_widgets_and_defs = []; self.step_logic_controlling_widgets = {}; self.step_logic_widget_prefix = ""
        try: self.overlay_font = ImageFont.truetype(FONT_PATH_PRIMARY, 11)
        except IOError:
            try: self.overlay_font = ImageFont.truetype(FONT_PATH_FALLBACK, 11)
            except IOError: self.overlay_font = ImageFont.load_default(); logger.warning("Arial/DejaVuSans fonts not found for overlays.")
        self._show_current_page(); logger.info("ProfileCreationWizardWindow initialized."); self.after(150, self._center_window)
    def _center_window(self): self.update_idletasks(); master = self.master; x_pos=0; y_pos=0; if master and master.winfo_exists(): x_pos = master.winfo_x() + (master.winfo_width()//2) - (self.winfo_width()//2); y_pos = master.winfo_y() + (master.winfo_height()//2) - (self.winfo_height()//2); self.geometry(f"+{max(0,x_pos)}+{max(0,y_pos)}")
        else: self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}"); self.lift(); self.focus_force()
    def _clear_main_content_frame(self):
        for widget in self.main_content_frame.winfo_children(): widget.destroy()
        self.step_logic_detail_widgets.clear(); self.step_logic_optionmenu_vars.clear(); self.step_logic_param_widgets_and_defs.clear(); self.step_logic_controlling_widgets.clear()
    def _update_navigation_buttons_state(self):
        self.btn_previous.configure(state="disabled"); self.btn_next.configure(state="normal")
        if self.current_page_index == PAGE_GOAL_INPUT: self.btn_next.configure(text="Generate Plan >")
        elif self.current_page_index == PAGE_PLAN_REVIEW: self.btn_previous.configure(state="normal"); self.btn_next.configure(text="Start Building Profile >", state="normal" if self.intermediate_plan else "disabled")
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION: self.btn_previous.configure(state="normal"); self.btn_next.configure(text="Confirm Region & Define Logic >", state="normal" if self.current_step_region_name and self.current_step_region_coords else "disabled")
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC: self.btn_previous.configure(state="normal"); is_last = (self.profile_generator.current_plan_step_index >= len(self.intermediate_plan or []) -1) if self.intermediate_plan else True; self.btn_next.configure(text="Finish & Review Profile >" if is_last else "Confirm Logic & Next Step >")
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE: self.btn_previous.configure(state="normal"); self.btn_next.configure(text="Save Profile & Close")
    def _show_current_page(self):
        self._clear_main_content_frame(); setup_method = {PAGE_GOAL_INPUT: self._setup_page_goal_input, PAGE_PLAN_REVIEW: self._setup_page_plan_review, PAGE_STEP_DEFINE_REGION: self._setup_page_step_define_region, PAGE_STEP_DEFINE_LOGIC: self._setup_page_step_define_logic, PAGE_FINAL_REVIEW_SAVE: self._setup_page_final_review_save}.get(self.current_page_index)
        if setup_method: setup_method()
        else: ctk.CTkLabel(self.main_content_frame, text=f"Error: Page {self.current_page_index}").pack()
        self._update_navigation_buttons_state(); self.focus_set()
    def _setup_page_goal_input(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Step 1 - Define Your Automation Goal", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0,20), anchor="w")
        ctk.CTkLabel(page_frame, text="Describe the task Mark-I should learn and automate in detail:", anchor="w").pack(fill="x", pady=(5,2))
        self.goal_textbox = ctk.CTkTextbox(page_frame, height=180, wrap="word", font=ctk.CTkFont(size=13)); self.goal_textbox.pack(fill="x", pady=(0,15))
        self.goal_textbox.insert("0.0", self.user_goal_text or "Example: Open MyApp, log in, navigate to Reports, run Monthly Sales, then export as PDF.")
        context_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); context_frame.pack(fill="x", pady=(10,5))
        ctk.CTkLabel(context_frame, text="Optional: Initial Visual Context (helps AI):", anchor="w").pack(fill="x", pady=(0,5))
        btn_frame = ctk.CTkFrame(context_frame, fg_color="transparent"); btn_frame.pack(fill="x", pady=(0,5))
        ctk.CTkButton(btn_frame, text="Capture Full Screen", command=self._capture_full_screen_context, width=180).pack(side="left", padx=(0,10))
        ctk.CTkButton(btn_frame, text="Load Image from File", command=self._load_image_context, width=180).pack(side="left", padx=10)
        self.context_image_preview_label = ctk.CTkLabel(context_frame, text="No context image.", height=150, fg_color=("gray85","gray25"), corner_radius=6); self.context_image_preview_label.pack(fill="x", pady=(10,0))
        self._update_context_image_preview(); self.goal_textbox.focus_set(); logger.debug("Page Goal Input UI setup.")
    def _capture_full_screen_context(self):
        logger.info("Capturing full screen for context..."); try:
            self.attributes("-alpha", 0.0); self.lower(); self.update_idletasks(); time.sleep(0.3); img_pil = ImageGrab.grab(all_screens=True); self.attributes("-alpha", 1.0); self.lift(); self.focus_set()
            if img_pil: self.current_full_context_pil = img_pil.convert("RGB"); img_np_rgb = np.array(self.current_full_context_pil); self.current_full_context_np = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR); self.profile_generator.set_current_visual_context(self.current_full_context_np); logger.info(f"Full screen captured (Size: {img_pil.width}x{img_pil.height}).")
            else: self.current_full_context_pil = self.current_full_context_np = None; self.profile_generator.set_current_visual_context(None); logger.error("Full screen capture failed (ImageGrab None).")
        except Exception as e: self.current_full_context_pil = self.current_full_context_np = None; self.profile_generator.set_current_visual_context(None); logger.error(f"Error capturing full screen: {e}", exc_info=True); _ = self.attributes("-alpha", 1.0); self.lift() if self.winfo_exists() else None
        self._update_context_image_preview()
    def _load_image_context(self):
        filepath = filedialog.askopenfilename(title="Select Context Image", filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")], parent=self)
        if filepath:
            try: img_pil = Image.open(filepath); self.current_full_context_pil = img_pil.convert("RGB"); img_np_rgb = np.array(self.current_full_context_pil); self.current_full_context_np = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR); self.profile_generator.set_current_visual_context(self.current_full_context_np); logger.info(f"Context image loaded: '{filepath}' (Size: {img_pil.width}x{img_pil.height}).")
            except Exception as e: self.current_full_context_pil = self.current_full_context_np = None; self.profile_generator.set_current_visual_context(None); logger.error(f"Error loading context image: {e}", exc_info=True)
        self._update_context_image_preview()
    def _update_context_image_preview(self):
        if not hasattr(self, 'context_image_preview_label') or not self.context_image_preview_label: return
        if self.current_full_context_pil: img_copy = self.current_full_context_pil.copy(); preview_max_w, preview_max_h = 350, 200; img_copy.thumbnail((preview_max_w, preview_max_h), Image.Resampling.LANCZOS); ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=(img_copy.width, img_copy.height)); self.context_image_preview_label.configure(image=ctk_img, text=f"Context: {self.current_full_context_pil.width}x{self.current_full_context_pil.height} (Loaded)", height=img_copy.height + 10)
        else: self.context_image_preview_label.configure(image=None, text="No context image selected.", height=150)
    def _setup_page_plan_review(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Step 2 - Review Automation Plan", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0,15), anchor="w")
        if self.intermediate_plan:
            ctk.CTkLabel(page_frame, text="Gemini has proposed the following high-level steps:", font=ctk.CTkFont(size=14)).pack(anchor="w", pady=(5,5))
            plan_display_frame = ctk.CTkScrollableFrame(page_frame, height=450, fg_color=("gray92", "gray28")); plan_display_frame.pack(fill="both", expand=True, pady=(0,10))
            for i, step in enumerate(self.intermediate_plan):
                step_text = f"Step {step.get('step_id', i+1)}: {step.get('description', 'N/A')}"; hint = step.get('suggested_element_type_hint'); inputs = step.get('required_user_input_for_step', [])
                if hint or inputs: step_text += f"\n  (AI Hint: Element='{hint or 'N/A'}'. User inputs: {inputs or 'None'})"
                ctk.CTkLabel(plan_display_frame, text=step_text, wraplength=self.winfo_width() - 100, anchor="w", justify="left", font=ctk.CTkFont(size=13)).pack(fill="x", pady=4, padx=5)
        else: ctk.CTkLabel(page_frame, text="Error: No plan generated. Go back & refine goal.").pack(pady=20)
        logger.debug("Page Plan Review UI setup.")
    def _setup_page_step_define_region(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.current_plan_step_data = self.profile_generator.get_current_plan_step()
        if not self.current_plan_step_data: ctk.CTkLabel(page_frame, text="Error: No current plan step data.").pack(); return
        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1); step_desc = self.current_plan_step_data.get('description', 'N/A')
        header_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); header_frame.pack(fill="x", pady=(0,5))
        ctk.CTkLabel(header_frame, text=f"Step {step_id}.A: Define Region for Task", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", anchor="w")
        ctk.CTkLabel(page_frame, text=f"Task: \"{step_desc}\"", wraplength=self.winfo_width()-20, justify="left", font=ctk.CTkFont(size=14)).pack(anchor="w", pady=(0,10), fill="x")
        self.region_step_context_display_label = ctk.CTkLabel(page_frame, text="Loading screen context...", fg_color=("gray90", "gray25"), corner_radius=6); self.region_step_context_display_label.pack(fill="both", expand=True, pady=(0,10))
        self.display_current_full_context_with_optional_overlay(label_widget=self.region_step_context_display_label)
        controls_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); controls_frame.pack(fill="x", pady=(5,10))
        self.btn_ai_suggest_region = ctk.CTkButton(controls_frame, text="AI Suggest Region", command=self._handle_ai_suggest_region, width=160); self.btn_ai_suggest_region.pack(side="left", padx=(0,10))
        self.btn_draw_region_manually = ctk.CTkButton(controls_frame, text="Draw/Adjust Manually", command=self._handle_draw_region_manually, width=180); self.btn_draw_region_manually.pack(side="left", padx=5)
        name_frame = ctk.CTkFrame(controls_frame, fg_color="transparent"); name_frame.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(name_frame, text="Region Name:").pack(side="left")
        self.current_step_region_name_entry = ctk.CTkEntry(name_frame, placeholder_text=f"e.g., step{step_id}_target_area"); self.current_step_region_name_entry.pack(side="left", fill="x", expand=True)
        if self.current_step_region_name: self.current_step_region_name_entry.insert(0, self.current_step_region_name)
        self._update_navigation_buttons_state(); logger.debug(f"Page Step Define Region UI setup for step {step_id}.")
    def display_current_full_context_with_optional_overlay(self, label_widget: ctk.CTkLabel, overlay_box: Optional[List[int]] = None, box_color="red"):
        if not label_widget or not label_widget.winfo_exists(): return
        if not self.current_full_context_pil: label_widget.configure(text="No screen context image.", image=None); return
        img_display = self.current_full_context_pil.copy()
        if overlay_box and len(overlay_box) == 4:
            try:
                draw = ImageDraw.Draw(img_display, "RGBA"); x,y,w,h = overlay_box; fill = box_color + "50" if box_color!=SELECTED_CANDIDATE_BOX_COLOR else None
                draw.rectangle([x,y,x+w,y+h], outline=box_color, width=3, fill=fill)
                if box_color == SELECTED_CANDIDATE_BOX_COLOR: cx,cy=x+w//2,y+h//2; draw.line([(cx-5,cy),(cx+5,cy)],fill=box_color,width=2); draw.line([(cx,cy-5),(cx,cy+5)],fill=box_color,width=2)
            except Exception as e: logger.error(f"Error drawing overlay {overlay_box}: {e}")
        max_w,max_h = WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH,WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT; thumb = img_display.copy(); thumb.thumbnail((max_w,max_h), Image.Resampling.LANCZOS); dw,dh=thumb.size
        ctk_img = ctk.CTkImage(light_image=thumb,dark_image=thumb,size=(dw,dh)); label_widget.configure(image=ctk_img,text="",width=dw,height=dh)
    def _handle_ai_suggest_region(self):
        if not self.current_plan_step_data: return
        logger.info(f"User req AI region suggestion: {self.current_plan_step_data.get('description')}")
        self.btn_ai_suggest_region.configure(text="AI Suggesting...", state="disabled"); self.btn_draw_region_manually.configure(state="disabled"); self.update_idletasks()
        suggestion = self.profile_generator.suggest_region_for_step(self.current_plan_step_data)
        self.btn_ai_suggest_region.configure(text="AI Suggest Region", state="normal"); self.btn_draw_region_manually.configure(state="normal")
        if suggestion and suggestion.get("box"):
            box = suggestion["box"]; self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label, box, "orange")
            name_hint = suggestion.get("suggested_region_name_hint", f"step{self.current_plan_step_data.get('step_id')}_ai_region"); self.current_step_region_name_entry.delete(0, tk.END); self.current_step_region_name_entry.insert(0, name_hint)
            self._temp_suggested_region_coords = {"x": box[0], "y": box[1], "width": box[2], "height": box[3]}; self.current_step_region_coords = self._temp_suggested_region_coords; self.current_step_region_defined = True
            messagebox.showinfo("AI Suggestion", f"AI suggests highlighted region (named '{name_hint}').\nReasoning: {suggestion.get('reasoning', 'N/A')}\nVerify, edit name, then 'Confirm Region'. Or, draw manually.", parent=self)
        else: self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label); messagebox.showwarning("AI Suggestion Failed", "AI could not suggest a region. Define manually.", parent=self)
        self._update_navigation_buttons_state()
    def _handle_draw_region_manually(self):
        if not self.current_plan_step_data: return
        logger.info(f"User opted to draw region manually for: {self.current_plan_step_data.get('description')}")
        self.attributes("-alpha", 0.0); self.lower(); self.update_idletasks(); time.sleep(0.2)
        capture_pil = self.current_full_context_pil
        if not capture_pil: temp_np = self.capture_engine.capture_region({"x":0,"y":0,"width":self.winfo_screenwidth(), "height":self.winfo_screenheight()}); capture_pil = Image.fromarray(cv2.cvtColor(temp_np, cv2.COLOR_BGR2RGB)) if temp_np is not None else None
        self.attributes("-alpha", 1.0); self.lift(); self.focus_set()
        if not capture_pil: messagebox.showerror("Capture Error", "Failed to get screen image for manual region selection.", parent=self); return
        temp_cm = ConfigManager(None, create_if_missing=True) # Dummy CM for RegionSelector
        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1); initial_name = self.current_step_region_name_entry.get() or (self._temp_suggested_region_coords and self.current_plan_step_data.get('suggested_region_name_hint')) or f"step{step_id}_manual_region"
        # Pass current coords if they exist (from AI suggestion or previous draw)
        existing_data_for_selector = {"name": initial_name, **(self.current_step_region_coords if self.current_step_region_defined else self._temp_suggested_region_coords or copy.deepcopy(DEFAULT_REGION_STRUCTURE_PG))}

        selector = RegionSelectorWindow(master=self, config_manager_for_saving_path_only=temp_cm, existing_region_data=existing_data_for_selector, direct_image_input_pil=capture_pil)
        self.wait_window(selector) # Modal
        if hasattr(selector, 'saved_region_info') and selector.saved_region_info:
            cr = selector.saved_region_info; self.current_step_region_name = cr["name"]; self.current_step_region_coords = {k: cr[k] for k in ["x","y","width","height"]}; self.current_step_region_defined = True
            self.current_step_region_name_entry.delete(0, tk.END); self.current_step_region_name_entry.insert(0, self.current_step_region_name)
            box_to_draw = [self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']]
            self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label, box_to_draw, SELECTED_CANDIDATE_BOX_COLOR)
            logger.info(f"User manually defined/confirmed region '{self.current_step_region_name}' at {self.current_step_region_coords}")
        else: logger.info("Manual region definition cancelled or no region saved.")
        self._update_navigation_buttons_state()
    def _confirm_and_add_current_step_region(self) -> bool:
        if not self.current_step_region_defined or not self.current_step_region_coords: messagebox.showerror("Error", "No region defined/confirmed.", parent=self); return False
        region_name = self.current_step_region_name_entry.get().strip()
        if not region_name: messagebox.showerror("Input Error", "Region Name empty.", parent=self); self.current_step_region_name_entry.focus(); return False
        
        # Check for duplicate region names in the *profile being generated*
        existing_regions_in_draft = self.profile_generator.generated_profile_data.get("regions", [])
        if any(r.get("name") == region_name for r in existing_regions_in_draft):
            if not messagebox.askyesno("Name Conflict", f"A region named '{region_name}' already exists in the profile being generated. Overwrite/use this name (replacing any previous definition with this name)?", parent=self):
                self.current_step_region_name_entry.focus(); return False
            else: # Remove existing region with this name from draft before adding new one
                self.profile_generator.generated_profile_data["regions"] = [r for r in existing_regions_in_draft if r.get("name") != region_name]
        
        step_desc = self.current_plan_step_data.get('description', 'N/A') if self.current_plan_step_data else 'N/A'
        region_data_to_add = {"name": region_name, **self.current_step_region_coords, "comment": f"For AI Gen Step: {step_desc}"}
        
        if self.profile_generator.add_region_definition(region_data_to_add):
            self.current_step_region_name = region_name # Update wizard's state
            # Crop the region image for the next step (Define Logic)
            if self.current_full_context_np is not None and self.current_step_region_coords:
                x,y,w,h = self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']
                img_h_full, img_w_full = self.current_full_context_np.shape[:2]
                # Clamp coordinates to be within the full context image, robustly
                x_clamped = max(0, x); y_clamped = max(0, y)
                x2_clamped = min(img_w_full, x + w); y2_clamped = min(img_h_full, y + h)
                w_clamped = x2_clamped - x_clamped; h_clamped = y2_clamped - y_clamped

                if w_clamped > 0 and h_clamped > 0:
                    self.current_step_region_image_np = self.current_full_context_np[y_clamped:y2_clamped, x_clamped:x2_clamped]
                    self.current_step_region_image_pil_for_display = Image.fromarray(cv2.cvtColor(self.current_step_region_image_np, cv2.COLOR_BGR2RGB))
                    logger.info(f"Cropped region image '{region_name}' (shape: {self.current_step_region_image_np.shape}) set for logic definition step.")
                else:
                    self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
                    logger.error(f"Failed to crop a valid (non-zero area) region image for '{region_name}' from full context. Original Coords: {self.current_step_region_coords}, Clamped w/h: {w_clamped}x{h_clamped}")
                    messagebox.showerror("Crop Error", "The defined region resulted in an invalid (zero area) crop. Please check coordinates relative to screen context.", parent=self)
                    return False # Cannot proceed without a valid region image for next step
            else:
                self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
                logger.warning("No full context image available to crop from for current step's region. Logic suggestions will be impaired.")
            self._temp_suggested_region_coords = None # Clear temporary AI suggestion
            return True
        return False # add_region_definition failed (shouldn't with current PG logic if data is good)
    
    def _setup_page_final_review_save(self): # As before
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Final Review & Save Profile", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0,15), anchor="w")
        profile_summary_textbox = ctk.CTkTextbox(page_frame, height=450, wrap="word", state="disabled", font=ctk.CTkFont(family="Courier New", size=11)); profile_summary_textbox.pack(fill="both", expand=True, pady=(0,10))
        data = self.profile_generator.get_generated_profile_data()
        try: text = json.dumps(data, indent=2); profile_summary_textbox.configure(state="normal"); profile_summary_textbox.delete("0.0", "end"); profile_summary_textbox.insert("0.0", text); profile_summary_textbox.configure(state="disabled")
        except Exception as e: profile_summary_textbox.configure(state="normal"); profile_summary_textbox.delete("0.0", "end"); profile_summary_textbox.insert("0.0", f"Error displaying profile: {e}"); profile_summary_textbox.configure(state="disabled")
        name_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); name_frame.pack(fill="x", pady=(10,5))
        ctk.CTkLabel(name_frame, text="Profile Filename:").pack(side="left", padx=(0,5))
        self.profile_filename_entry = ctk.CTkEntry(name_frame, placeholder_text=self.generated_profile_name_base); self.profile_filename_entry.pack(side="left", expand=True, fill="x"); self.profile_filename_entry.insert(0, self.generated_profile_name_base)
        logger.debug("Page Final Review UI setup.")

    def _on_close_wizard(self, event=None, was_saved=False): # As before
        if not was_saved and messagebox.askokcancel("Cancel Generation?", "Discard this profile and close wizard?", parent=self, icon=messagebox.WARNING): logger.info("AI Profile Wizard cancelled (unsaved)."); self.destroy()
        elif was_saved: logger.info("AI Profile Wizard closing (saved)."); self.destroy()

    # --- END OF COPIED/UNCHANGED METHODS ---
    # --- PAGE_STEP_DEFINE_LOGIC and its helpers (Implementation Focus from previous response, further detailed) ---

    def _setup_page_step_define_logic(self): # As in previous response, with minor stability checks
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")
        page_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.current_plan_step_data = self.profile_generator.get_current_plan_step()
        if not self.current_plan_step_data or not self.current_step_region_name or self.current_step_region_image_pil_for_display is None:
            ctk.CTkLabel(page_frame, text="Error: Critical data missing (step, region name, or region image).\nPlease go back to define the region for this task step first.", wraplength=self.winfo_width()-30, justify="left").pack(pady=20)
            self.btn_next.configure(state="disabled"); self._update_navigation_buttons_state(); return

        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1)
        step_desc = self.current_plan_step_data.get('description', 'N/A')

        header_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); header_frame.pack(fill="x", pady=(0,5))
        ctk.CTkLabel(header_frame, text=f"Step {step_id}.B: Define Logic for Region '{self.current_step_region_name}'", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", anchor="w")
        ctk.CTkLabel(page_frame, text=f"Task: \"{step_desc}\"", wraplength=self.winfo_width()-20, justify="left").pack(anchor="w", pady=(0,10), fill="x")

        main_logic_area = ctk.CTkFrame(page_frame, fg_color="transparent"); main_logic_area.pack(fill="both", expand=True)
        main_logic_area.grid_columnconfigure(0, weight=3, minsize=400); main_logic_area.grid_columnconfigure(1, weight=2, minsize=350)
        main_logic_area.grid_rowconfigure(0, weight=1)

        visual_panel = ctk.CTkFrame(main_logic_area, fg_color=("gray90", "gray25")); visual_panel.grid(row=0, column=0, sticky="nsew", padx=(0,5))
        visual_panel.grid_rowconfigure(1, weight=1); visual_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(visual_panel, text=f"Context: Region '{self.current_step_region_name}' (Click image to select element)", font=ctk.CTkFont(size=12)).pack(pady=(5,2), anchor="w", padx=5)
        self.step_logic_region_image_label = ctk.CTkLabel(visual_panel, text="Region image...", height=WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT - 70); self.step_logic_region_image_label.pack(fill="both", expand=True, padx=5, pady=5)
        self.step_logic_region_image_label.bind("<Button-1>", self._on_region_image_click_for_element_selection)
        
        element_interaction_frame = ctk.CTkFrame(visual_panel, fg_color="transparent"); element_interaction_frame.pack(fill="x", pady=5, padx=5)
        self.element_refine_entry = ctk.CTkEntry(element_interaction_frame, placeholder_text="Element description (e.g., 'login button')"); self.element_refine_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.btn_refine_element = ctk.CTkButton(element_interaction_frame, text="AI Find Element", command=self._handle_ai_refine_element, width=120, state="disabled"); self.btn_refine_element.pack(side="left", padx=(0,5))
        self.btn_capture_template_for_step = ctk.CTkButton(element_interaction_frame, text="Use Template Instead", command=self._handle_capture_template_for_step, width=160, state="disabled"); self.btn_capture_template_for_step.pack(side="left")

        params_panel_outer = ctk.CTkFrame(main_logic_area, fg_color="transparent"); params_panel_outer.grid(row=0, column=1, sticky="nsew", padx=(5,0))
        params_panel_outer.grid_rowconfigure(0, weight=1); params_panel_outer.grid_columnconfigure(0, weight=1)
        self.params_panel_scrollable = ctk.CTkScrollableFrame(params_panel_outer, label_text="Configure Step Logic (AI Suggested / Manual)"); self.params_panel_scrollable.pack(fill="both", expand=True)
        self.params_panel_scrollable.grid_columnconfigure(1, weight=1)
        self.step_logic_condition_frame = ctk.CTkFrame(self.params_panel_scrollable, fg_color="transparent"); self.step_logic_condition_frame.pack(fill="x", pady=(5,15), padx=5); self.step_logic_condition_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.step_logic_condition_frame, text="STEP CONDITION:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))
        self.step_logic_action_frame = ctk.CTkFrame(self.params_panel_scrollable, fg_color="transparent"); self.step_logic_action_frame.pack(fill="x", pady=(10,5), padx=5); self.step_logic_action_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.step_logic_action_frame, text="STEP ACTION:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))

        self.suggested_condition_for_step = None; self.suggested_action_for_step = None; self.element_to_refine_desc_for_step = None
        self.refined_element_candidates = []; self.selected_candidate_box_index = None; self.confirmed_element_for_action = None
        self._current_step_temp_var_name_for_gemini_element = f"_ai_gen_step{step_id}_elem"

        self._display_current_step_region_image_with_candidates()
        self.after(100, self._trigger_ai_logic_suggestion_for_step)
        self._update_navigation_buttons_state(); logger.debug(f"Page Step Define Logic UI setup for step {step_id}.")

    # _trigger_ai_logic_suggestion_for_step, _render_step_logic_editors,
    # _on_wizard_logic_type_change, _render_dynamic_params_in_wizard_subframe,
    # _update_step_logic_conditional_visibility, _apply_step_logic_conditional_visibility,
    # _handle_ai_refine_element, _display_current_step_region_image_with_candidates,
    # _on_region_image_click_for_element_selection, _update_action_params_with_selected_element,
    # _clear_action_target_params
    # These methods are assumed to be as in the previous response. The main change is now in:
    # _get_current_step_logic_from_ui and the _go_to_next_page handler for this page.
    # _handle_capture_template_for_step still needs full implementation.

    def _handle_capture_template_for_step(self): # Implementation Focus
        if not self.current_step_region_image_pil_for_display or not self.current_step_region_name:
            messagebox.showerror("Error", "Region image not available for template capture.", parent=self); return

        element_desc_for_template = self.element_to_refine_desc_for_step or self.current_plan_step_data.get('description', 'step_element')[:20]
        default_template_name = f"tpl_{self.current_step_region_name}_{element_desc.replace(' ','_').lower()}"
        sane_default_template_name = "".join(c if c.isalnum() else "_" for c in default_template_name)
        if len(sane_default_template_name) > 50 : sane_default_template_name = sane_default_template_name[:50]


        template_name_dialog = ctk.CTkInputDialog(text=f"Enter unique name for this new template (for element '{element_desc_for_template}'):", title="New Template Name")
        template_name = template_name_dialog.get_input()
        if not template_name or not template_name.strip(): logger.info("Template capture cancelled: No name."); return
        template_name = template_name.strip()

        if any(t.get("name") == template_name for t in self.profile_generator.generated_profile_data.get("templates", [])):
            messagebox.showerror("Name Conflict", f"A template named '{template_name}' already exists.", parent=self); return

        logger.info(f"Initiating template capture from region '{self.current_step_region_name}' for template '{template_name}'")
        
        # Use SubImageSelectorWindow
        self.attributes("-alpha", 0.5) # Dim wizard slightly
        sub_selector = SubImageSelectorWindow(master=self, image_to_select_from_pil=self.current_step_region_image_pil_for_display, title=f"Select Area for Template '{template_name}'")
        self.wait_window(sub_selector) # Modal
        self.attributes("-alpha", 1.0) # Restore wizard
        
        selected_template_coords = sub_selector.get_selected_coords() # Returns (x,y,w,h) relative to region image, or None

        if selected_template_coords:
            x_rel, y_rel, w_rel, h_rel = selected_template_coords
            
            # Crop the template from the original numpy region image
            if self.current_step_region_image_np is not None and w_rel > 0 and h_rel > 0:
                template_image_np = self.current_step_region_image_np[y_rel : y_rel+h_rel, x_rel : x_rel+w_rel]
                
                # Save the template image file
                # This requires profile to be saved first to know its directory.
                # If main profile isn't saved, AI Gen Wizard needs its own temp dir or way to hold images.
                # For now, assume main_app_instance.current_profile_path is set (wizard launched after profile open/save)
                # OR profile_generator needs a method to stage unsaved templates.

                # Let's assume for now we need a saved profile context.
                # The GUI wizard should ideally only be active if a base profile context for saving exists.
                # If self.main_app_instance.current_profile_path is None, this will be an issue.
                # Fallback: store in a temporary location and remind user, or disallow template capture.

                profile_base_path = self.main_app_instance.config_manager.get_profile_base_path()
                if not profile_base_path:
                    # This happens if the MainAppWindow has no profile loaded or saved.
                    # The AI Profile Creator should ideally create a *new in-memory profile* first,
                    # and then user saves it at the END. Templates need a place to go.
                    # Simplification: save to a temporary "ai_gen_templates" in project logs or similar.
                    # Or, better: The ProfileCreationWizard should have its own temporary ConfigManager
                    # that it uses to build up the profile, including templates. When user clicks "Save Profile",
                    # that ConfigManager instance is asked to save to a user-chosen location.

                    # For this iteration: save relative to where Mark-I is run if no profile path.
                    # This is NOT ideal for production.
                    profile_dir_for_templates = self.main_app_instance.config_manager.profiles_base_dir # Use default profiles dir as fallback
                    logger.warning(f"No current profile path set in MainApp. Saving template to default profiles sub-directory for now: {profile_dir_for_templates}")
                    if not os.path.exists(os.path.join(profile_dir_for_templates, "templates")):
                        os.makedirs(os.path.join(profile_dir_for_templates, "templates"), exist_ok=True)
                else:
                    profile_dir_for_templates = profile_base_path


                sane_filename_base = "".join(c if c.isalnum() else "_" for c in template_name).lower()
                template_filename = f"{sane_filename_base}.png"
                
                # Ensure unique filename in the target templates directory for this profile generation session
                # by checking against self.profile_generator.generated_profile_data["templates"]
                existing_filenames = [t.get("filename") for t in self.profile_generator.generated_profile_data.get("templates", [])]
                count = 1
                temp_fn_to_check = template_filename
                while temp_fn_to_check in existing_filenames:
                    temp_fn_to_check = f"{sane_filename_base}_{count}.png"
                    count += 1
                template_filename = temp_fn_to_check
                
                # The actual save path depends on where the *final profile* will be saved.
                # For now, let ProfileGenerator just store metadata and NP array.
                # The actual file saving should happen when the *profile* is saved.
                # This means ProfileGenerator needs to hold onto the image data.
                # OR, we save to a temporary path and copy later.
                # For simplicity now, let's assume we save it relative to the current config_manager's profile path if available.
                # This part needs a robust solution for unsaved main profiles.

                # Let's assume ProfileGenerator handles staging template images internally if profile not saved
                # and returns the chosen filename.
                
                template_metadata = {
                    "name": template_name,
                    "filename": template_filename, # This filename is now relative to the profile's templates dir
                    "comment": f"Template for '{element_desc}' in region '{self.current_step_region_name}'. Captured by user.",
                    "_image_data_np_for_save": template_image_np # Store NP data for PG to save later
                }

                if self.profile_generator.add_template_definition(template_metadata): # PG should handle storing this data
                    logger.info(f"Template '{template_name}' (filename: {template_filename}) metadata and image data staged for profile.")
                    # Update UI: condition type to template_match_found, action to click center_of_last_match
                    cond_type_var = self.step_logic_optionmenu_vars.get("step_cond_type_var")
                    if cond_type_var: cond_type_var.set("template_match_found"); self._on_wizard_logic_type_change("condition", "template_match_found")
                    self.after(50, lambda: self._attempt_set_template_name_in_ui(template_name))

                    act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
                    if act_type_var: act_type_var.set("click"); self._on_wizard_logic_type_change("action", "click")
                    self.after(100, lambda: self._set_click_action_params_for_template(template_name)) # New helper
                    messagebox.showinfo("Template Staged", f"Template '{template_name}' captured and will be saved with the profile.", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to add template metadata for '{template_name}'.", parent=self)
            else:
                messagebox.showerror("Template Capture Error", "Could not capture a valid template image from the selection.", parent=self)
        else:
            logger.info("Template capture from sub-image selector cancelled by user.")


    # ... (_get_parameters_from_ui_wizard_scoped, _attempt_set_template_name_in_ui, _update_action_params_with_selected_element, _clear_action_target_params - as before) ...
    # ... (_go_to_next_page (with its call to _get_current_step_logic_from_ui), _go_to_previous_page - as before with previous iteration's logic) ...
    def _attempt_set_template_name_in_ui(self, template_name_to_set: str): # As before
        widget_key = "step_cond_template_name"; tk_var = self.step_logic_optionmenu_vars.get(f"{widget_key}_var"); widget = self.step_logic_detail_widgets.get(widget_key)
        if tk_var and isinstance(tk_var, tk.StringVar) and widget and isinstance(widget, ctk.CTkOptionMenu):
            new_opts = [""] + [t.get("name","") for t in self.profile_generator.generated_profile_data.get("templates",[]) if t.get("name")]
            widget.configure(values=new_opts); tk_var.set(template_name_to_set) if template_name_to_set in new_opts else logger.warning(f"Newly added template '{template_name_to_set}' not in dropdown.")
        else: logger.warning(f"Could not find/set template_name dropdown for '{template_name_to_set}'.")

    def _set_click_action_params_for_template(self, template_name: str): # New helper
        """Sets action UI to click the center_of_last_match for a newly captured template."""
        target_relation_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var")
        if target_relation_var and isinstance(target_relation_var, tk.StringVar):
            target_relation_var.set("center_of_last_match")
            # Trigger conditional visibility update
            tr_param_def = next((pdef for pdef in UI_PARAM_CONFIG.get("actions",{}).get("click",[]) if pdef["id"] == "target_relation"), None)
            if tr_param_def: self._update_step_logic_conditional_visibility(tr_param_def, "center_of_last_match")
            logger.info(f"Action UI updated to target 'center_of_last_match' for template '{template_name}'.")
        else: logger.warning("Wizard: Could not find target_relation_var for click action to set for template.")
        # Clear gemini element variable if it was set
        gemini_var_entry = self.step_logic_detail_widgets.get("step_act_gemini_element_variable")
        if gemini_var_entry and isinstance(gemini_var_entry, ctk.CTkEntry): gemini_var_entry.delete(0, tk.END)
        self.confirmed_element_for_action = None # Clear any visually confirmed element


    def _get_current_step_logic_from_ui(self) -> Optional[Tuple[Dict[str,Any], Dict[str,Any]]]: # As before
        log_prefix = f"PG.GetStepLogicUI (StepID: {self.current_plan_step_data.get('step_id') if self.current_plan_step_data else 'N/A'})"
        cond_type_var = self.step_logic_optionmenu_vars.get("step_cond_type_var"); act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
        if not cond_type_var or not act_type_var: logger.error(f"{log_prefix}: Crit err: Cond/Act type UI selectors MIA."); return None
        cond_type = cond_type_var.get(); act_type = act_type_var.get()
        condition_params = self._get_parameters_from_ui_wizard_scoped("conditions", cond_type, "step_cond_")
        if condition_params is None: logger.error(f"{log_prefix}: Validation fail Cond params."); messagebox.showerror("Input Error", f"Invalid Cond params for '{cond_type}'.", parent=self); return None
        action_params = self._get_parameters_from_ui_wizard_scoped("actions", act_type, "step_act_")
        if action_params is None: logger.error(f"{log_prefix}: Validation fail Act params."); messagebox.showerror("Input Error", f"Invalid Act params for '{act_type}'.", parent=self); return None
        if self.confirmed_element_for_action and action_params.get("type") == "click" and action_params.get("gemini_element_variable") == self._current_step_temp_var_name_for_gemini_element:
            box_data = self.confirmed_element_for_action["value"]["box"]; src_reg_name = self.confirmed_element_for_action["_source_region_for_capture_"]
            src_reg_cfg = self.main_app_instance.config_manager.get_region_config(src_reg_name) # Use main app's CM for global region defs
            if not src_reg_cfg: # If source region not in main config, try PG's draft (if region was just defined in wizard)
                 src_reg_cfg = next((r for r in self.profile_generator.generated_profile_data.get("regions",[]) if r.get("name") == src_reg_name), None)

            if src_reg_cfg:
                abs_x = src_reg_cfg['x'] + box_data[0] + (box_data[2] // 2 if "center" in action_params.get("target_relation","center") else 0)
                abs_y = src_reg_cfg['y'] + box_data[1] + (box_data[3] // 2 if "center" in action_params.get("target_relation","center") else 0)
                action_params["target_relation"] = "absolute"; action_params["x"] = str(abs_x); action_params["y"] = str(abs_y)
                action_params.pop("gemini_element_variable", None); action_params.pop("target_region", None) # Clean up
                logger.info(f"{log_prefix}: Converted Gemini elem click to absolute ({abs_x},{abs_y}).")
            else: logger.error(f"{log_prefix}: Cannot find src rgn '{src_reg_name}' to convert Gemini click to absolute. Action may fail or use wrong context.");
        return condition_params, action_params

    def _go_to_next_page(self): # Updated logic for PAGE_STEP_DEFINE_LOGIC
        logger.debug(f"Next button clicked. Current page index: {self.current_page_index}")
        if self.current_page_index == PAGE_GOAL_INPUT:
            self.user_goal_text = self.goal_textbox.get("0.0", "end-1c").strip()
            if not self.user_goal_text: messagebox.showerror("Input Error", "Please describe goal.", parent=self); return
            loading_label = ctk.CTkLabel(self.main_content_frame, text="AI generating plan...", font=ctk.CTkFont(size=16)); loading_label.pack(pady=10); self.update_idletasks() # Use main_content_frame
            self.intermediate_plan = self.strategy_planner.generate_intermediate_plan(self.user_goal_text, self.current_full_context_np)
            if self.intermediate_plan and len(self.intermediate_plan) > 0:
                self.profile_generator.start_profile_generation(self.intermediate_plan, f"AI-Gen for: {self.user_goal_text[:70]}", initial_full_screen_context_np=self.current_full_context_np)
                self.current_page_index = PAGE_PLAN_REVIEW
                if self.current_page_index == PAGE_STEP_DEFINE_REGION: self.profile_generator.advance_to_next_plan_step(); self._reset_step_specific_state()
            else: messagebox.showerror("AI Plan Failed", "Could not generate plan. Try rephrasing goal or check logs.", parent=self); self._show_current_page(); return
        elif self.current_page_index == PAGE_PLAN_REVIEW:
            if not self.intermediate_plan: messagebox.showerror("Error", "No plan.", parent=self); return
            if self.profile_generator.advance_to_next_plan_step(): self.current_page_index = PAGE_STEP_DEFINE_REGION; self._reset_step_specific_state()
            else: messagebox.showerror("Error", "Plan empty/invalid.", parent=self)
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            if self._confirm_and_add_current_step_region(): self.current_page_index = PAGE_STEP_DEFINE_LOGIC
            else: return 
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC:
            logic_tuple = self._get_current_step_logic_from_ui()
            if logic_tuple:
                confirmed_condition, confirmed_action = logic_tuple
                current_step = self.profile_generator.get_current_plan_step()
                if current_step and self.current_step_region_name:
                    base_rule_name = f"Rule_Step{current_step.get('step_id')}_{current_step.get('description', 'Task')[:15].replace(' ','_').replace("'", "")}"
                    rule_name_to_add = base_rule_name; count = 1
                    while any(r.get("name") == rule_name_to_add for r in self.profile_generator.generated_profile_data.get("rules",[])): rule_name_to_add = f"{base_rule_name}_{count}"; count += 1
                    rule_to_add = {"name": rule_name_to_add, "region": self.current_step_region_name, "condition": confirmed_condition, "action": confirmed_action, "comment": f"AI Gen for: {current_step.get('description')}"}
                    if self.profile_generator.add_rule_definition(rule_to_add): logger.info(f"Rule '{rule_name_to_add}' added for step {current_step.get('step_id')}.")
                    else: messagebox.showerror("Error", f"Failed to add rule for step {current_step.get('step_id')}.", parent=self); return
                else: messagebox.showerror("Internal Error", "Missing step data or region name when adding rule.", parent=self); return
                if self.profile_generator.advance_to_next_plan_step(): self.current_page_index = PAGE_STEP_DEFINE_REGION; self._reset_step_specific_state()
                else: self.current_page_index = PAGE_FINAL_REVIEW_SAVE
            else: return # Validation failed in _get_current_step_logic_from_ui
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE: self._save_generated_profile(); return 
        self._show_current_page()

    def _go_to_previous_page(self): # As before
        logger.debug(f"Previous button clicked. Current page: {self.current_page_index}"); current_pg_idx = self.profile_generator.current_plan_step_index
        if self.current_page_index == PAGE_PLAN_REVIEW: self.current_page_index = PAGE_GOAL_INPUT
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            if current_pg_idx == 0 : self.current_page_index = PAGE_PLAN_REVIEW; self.profile_generator.current_plan_step_index = -1
            elif current_pg_idx > 0: self.profile_generator.current_plan_step_index -= 1; self._load_state_for_current_pg_step(); self.current_page_index = PAGE_STEP_DEFINE_LOGIC
            else: self.current_page_index = PAGE_PLAN_REVIEW
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC: self.current_page_index = PAGE_STEP_DEFINE_REGION # Go to current step's REGION page
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE:
            if self.intermediate_plan and len(self.intermediate_plan) > 0:
                if self.profile_generator.current_plan_step_index >= len(self.intermediate_plan): self.profile_generator.current_plan_step_index = len(self.intermediate_plan) - 1
                if self.profile_generator.current_plan_step_index >=0 : self._load_state_for_current_pg_step(); self.current_page_index = PAGE_STEP_DEFINE_LOGIC
                else: self.current_page_index = PAGE_PLAN_REVIEW
            else: self.current_page_index = PAGE_GOAL_INPUT
        self._show_current_page()

    def _reset_step_specific_state(self): # As before
        self.current_step_region_name = None; self.current_step_region_coords = None; self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
        self.current_step_region_defined = False; self._temp_suggested_region_coords = None
        self.suggested_condition_for_step = None; self.suggested_action_for_step = None; self.element_to_refine_desc_for_step = None
        self.refined_element_candidates = []; self.selected_candidate_box_index = None; self.confirmed_element_for_action = None
        if hasattr(self, 'element_refine_entry') and self.element_refine_entry: self.element_refine_entry.delete(0, tk.END)
        logger.debug("Wizard: Step-specific state variables reset.")

    def _load_state_for_current_pg_step(self): # As before
        self.current_plan_step_data = self.profile_generator.get_current_plan_step()
        if not self.current_plan_step_data: self._reset_step_specific_state(); return
        step_id = self.current_plan_step_data.get("step_id", self.profile_generator.current_plan_step_index + 1); logger.info(f"Wizard: Loading/re-evaluating state for Step ID {step_id}.")
        potential_rule_name_prefix = f"Rule_Step{step_id}"; found_rule = next((r for r in self.profile_generator.generated_profile_data.get("rules",[]) if r.get("name","").startswith(potential_rule_name_prefix)), None)
        if found_rule:
            self.current_step_region_name = found_rule.get("region")
            if self.current_step_region_name:
                region_cfg = next((r for r in self.profile_generator.generated_profile_data.get("regions",[]) if r.get("name") == self.current_step_region_name), None)
                if region_cfg: self.current_step_region_coords = {k: region_cfg[k] for k in ["x","y","width","height"]}; self.current_step_region_defined = True
                    if self.current_full_context_np is not None and self.current_step_region_coords:
                        x,y,w,h = self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']
                        img_h_f, img_w_f = self.current_full_context_np.shape[:2]; x,y=max(0,x),max(0,y); x2,y2=min(img_w_f,x+w),min(img_h_f,y+h); w,h=x2-x,y2-y
                        if w > 0 and h > 0: self.current_step_region_image_np = self.current_full_context_np[y:y2,x:x2]; self.current_step_region_image_pil_for_display = Image.fromarray(cv2.cvtColor(self.current_step_region_image_np, cv2.COLOR_BGR2RGB))
            self.suggested_condition_for_step = copy.deepcopy(found_rule.get("condition")); self.suggested_action_for_step = copy.deepcopy(found_rule.get("action"))
            self.confirmed_element_for_action = None; self.selected_candidate_box_index = None; self.refined_element_candidates = [] # Element refinement state is not persisted this way
            return
        self._reset_step_specific_state()