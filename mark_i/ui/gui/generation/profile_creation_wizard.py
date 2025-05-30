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

# Project-specific imports
from mark_i.generation.strategy_planner import StrategyPlanner, IntermediatePlan, IntermediatePlanStep
from mark_i.generation.profile_generator import ProfileGenerator, DEFAULT_CONDITION_STRUCTURE_PG, DEFAULT_ACTION_STRUCTURE_PG
from mark_i.ui.gui.generation.sub_image_selector_window import SubImageSelectorWindow # For template capture
from mark_i.engines.gemini_analyzer import GeminiAnalyzer # For type hinting
from mark_i.core.config_manager import ConfigManager, TEMPLATES_SUBDIR_NAME # For type hinting & constant
from mark_i.ui.gui.region_selector import RegionSelectorWindow # For manual region definition on full screen
from mark_i.core.capture_engine import CaptureEngine # For taking screenshots

from mark_i.ui.gui.gui_config import (
    CONDITION_TYPES as ALL_CONDITION_TYPES_FROM_CONFIG,
    ACTION_TYPES as ALL_ACTION_TYPES_FROM_CONFIG,
    UI_PARAM_CONFIG, OPTIONS_CONST_MAP
)
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.generation.profile_creation_wizard")

# --- Wizard Page Constants ---
PAGE_GOAL_INPUT = 0
PAGE_PLAN_REVIEW = 1
PAGE_STEP_DEFINE_REGION = 2
PAGE_STEP_DEFINE_LOGIC = 3
PAGE_FINAL_REVIEW_SAVE = 4

# --- UI Appearance Constants ---
WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH = 600 
WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT = 380 
CANDIDATE_BOX_COLORS = ["#FF00FF", "#00FFFF", "#FFFF00", "#F08080", "#90EE90", "#ADD8E6", "#FFC0CB", "#E6E6FA"] # Magenta, Cyan, Yellow, etc.
SELECTED_CANDIDATE_BOX_COLOR = "lime green"
FONT_PATH_PRIMARY = "arial.ttf" 
FONT_PATH_FALLBACK = "DejaVuSans.ttf" # Common Linux fallback for PIL ImageFont

class ProfileCreationWizardWindow(ctk.CTkToplevel):
    """
    A wizard-style window to guide the user through AI-assisted profile creation.
    It interacts with StrategyPlanner to get a plan from a user goal,
    and then with ProfileGenerator to iteratively define profile elements
    (regions, rules) for each step of the plan, with AI suggestions for
    regions, conditions, actions, and visual element refinement.
    Includes functionality for template capture during the process.
    """
    def __init__(self, master: Any, main_app_instance: Any): # main_app_instance is MainAppWindow
        super().__init__(master)
        self.main_app_instance = main_app_instance
        self.title("AI Profile Creator Wizard")
        self.transient(master); self.grab_set(); self.attributes("-topmost", True)
        self.geometry("1100x850"); self.minsize(950, 750)
        self.protocol("WM_DELETE_WINDOW", self._on_close_wizard)

        # --- Backend Components Initialization ---
        if not hasattr(self.main_app_instance, 'gemini_analyzer_instance') or \
           not self.main_app_instance.gemini_analyzer_instance or \
           not self.main_app_instance.gemini_analyzer_instance.client_initialized:
            logger.critical("ProfileCreationWizard: GeminiAnalyzer not available or not initialized in MainApp. Cannot proceed.")
            messagebox.showerror("Critical API Error", "Gemini API client is not properly initialized.\nPlease ensure your GEMINI_API_KEY is correctly set in .env and the application was restarted.", parent=self)
            self.after(100, self.destroy) # Schedule destroy after error messagebox shown
            return
            
        self.strategy_planner = StrategyPlanner(gemini_analyzer=self.main_app_instance.gemini_analyzer_instance)
        # ProfileGenerator now needs a ConfigManager instance that it can use to resolve paths for template saving later.
        # The wizard should build up a profile in memory using its own PG instance.
        # The main_app_instance.config_manager might point to an *existing* loaded profile, which is not what we want for a *new* AI-gen profile.
        # So, PG gets a *new* ConfigManager instance that starts empty or with defaults.
        self.profile_generator_cm = ConfigManager(None, create_if_missing=True) # CM for the profile being generated
        self.profile_generator = ProfileGenerator(
            gemini_analyzer=self.main_app_instance.gemini_analyzer_instance,
            config_manager=self.profile_generator_cm # Use its own CM
        )
        self.capture_engine = CaptureEngine()

        # --- Wizard State Variables ---
        self.current_page_index: int = PAGE_GOAL_INPUT
        self.intermediate_plan: Optional[IntermediatePlan] = None
        
        self.current_full_context_pil: Optional[Image.Image] = None # Full screen/app PIL image
        self.current_full_context_np: Optional[np.ndarray] = None   # Full screen/app NumPy BGR image
        
        self.user_goal_text: str = "" # Stores the user's initial goal
        self.generated_profile_name_base: str = "ai_generated_profile" # Default base name

        # State specific to the current plan step being defined
        self.current_plan_step_data: Optional[IntermediatePlanStep] = None
        self.current_step_region_name: Optional[str] = None
        self.current_step_region_coords: Optional[Dict[str, int]] = None # {"x":_, "y":_, "width":_, "height":_} relative to full context
        self.current_step_region_image_np: Optional[np.ndarray] = None # Cropped NumPy BGR image of the defined region
        self.current_step_region_image_pil_for_display: Optional[Image.Image] = None # PIL version for CTkImage display
        self._temp_suggested_region_coords: Optional[Dict[str,int]] = None # AI suggested region box, before user confirmation

        # State for AI suggestions and user confirmations on the Define Logic page
        self.suggested_condition_for_step: Optional[Dict[str, Any]] = None
        self.suggested_action_for_step: Optional[Dict[str, Any]] = None
        self.element_to_refine_desc_for_step: Optional[str] = None # Text desc of element needing refinement
        self.refined_element_candidates: List[Dict[str, Any]] = [] # List of {"box": [x,y,w,h], "label_suggestion":...}
        self.selected_candidate_box_index: Optional[int] = None # Index in refined_element_candidates
        self.confirmed_element_for_action: Optional[Dict[str, Any]] = None # Data of the visually selected element for action
        self._current_step_temp_var_name_for_gemini_element: Optional[str] = None # Temp var name for ActionExecutor

        # --- UI Frames Setup ---
        self.main_content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        self.main_content_frame.grid_rowconfigure(0, weight=1); self.main_content_frame.grid_columnconfigure(0, weight=1)

        self.navigation_frame = ctk.CTkFrame(self, height=60, fg_color=("gray80", "gray20"), corner_radius=0)
        self.navigation_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        self.navigation_frame.grid_columnconfigure(0, weight=1); self.navigation_frame.grid_columnconfigure(4, weight=1) # Spacers
        self.btn_cancel = ctk.CTkButton(self.navigation_frame, text="Cancel & Close Wizard", command=self._on_close_wizard, width=180, fg_color="firebrick1", hover_color="firebrick3")
        self.btn_cancel.grid(row=0, column=1, padx=(20,5), pady=10, sticky="w")
        self.btn_next = ctk.CTkButton(self.navigation_frame, text="Next >", command=self._go_to_next_page, width=140, font=ctk.CTkFont(weight="bold"))
        self.btn_next.grid(row=0, column=3, padx=(5,20), pady=10, sticky="e")
        self.btn_previous = ctk.CTkButton(self.navigation_frame, text="< Previous Step", command=self._go_to_previous_page, width=140)
        self.btn_previous.grid(row=0, column=2, padx=5, pady=10, sticky="e")
        
        # For dynamic parameter editing on PAGE_STEP_DEFINE_LOGIC page
        self.step_logic_detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        self.step_logic_optionmenu_vars: Dict[str, Union[tk.StringVar, tk.BooleanVar]] = {}
        self.step_logic_param_widgets_and_defs: List[Dict[str, Any]] = [] # For conditional visibility
        self.step_logic_controlling_widgets: Dict[str, Union[ctk.CTkOptionMenu, ctk.CTkCheckBox]] = {}
        self.step_logic_widget_prefix: str = "" # Stores current prefix ("step_cond_" or "step_act_")

        try: self.overlay_font = ImageFont.truetype(FONT_PATH_PRIMARY, 11)
        except IOError:
            try: self.overlay_font = ImageFont.truetype(FONT_PATH_FALLBACK, 11)
            except IOError: self.overlay_font = ImageFont.load_default(); logger.warning("Arial/DejaVuSans fonts not found for image overlays, using PIL default.")

        self._show_current_page() # Display the initial page (Goal Input)
        logger.info("ProfileCreationWizardWindow initialized and Goal Input page shown.")
        self.after(150, self._center_window) # Center window after it's drawn

    def _center_window(self): # Unchanged
        self.update_idletasks(); master = self.master
        if master and master.winfo_exists(): x = master.winfo_x() + (master.winfo_width()//2) - (self.winfo_width()//2); y = master.winfo_y() + (master.winfo_height()//2) - (self.winfo_height()//2); self.geometry(f"+{max(0,x)}+{max(0,y)}")
        else: self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        self.lift(); self.focus_force()

    def _clear_main_content_frame(self): # Unchanged
        for widget in self.main_content_frame.winfo_children(): widget.destroy()
        self.step_logic_detail_widgets.clear(); self.step_logic_optionmenu_vars.clear(); self.step_logic_param_widgets_and_defs.clear(); self.step_logic_controlling_widgets.clear()

    def _update_navigation_buttons_state(self): # Unchanged
        self.btn_previous.configure(state="disabled"); self.btn_next.configure(state="normal")
        if self.current_page_index == PAGE_GOAL_INPUT: self.btn_next.configure(text="Generate Plan >")
        elif self.current_page_index == PAGE_PLAN_REVIEW: self.btn_previous.configure(state="normal"); self.btn_next.configure(text="Start Building Profile >", state="normal" if self.intermediate_plan else "disabled")
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION: self.btn_previous.configure(state="normal"); self.btn_next.configure(text="Confirm Region & Define Logic >", state="normal" if self.current_step_region_name and self.current_step_region_coords else "disabled")
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC: self.btn_previous.configure(state="normal"); is_last = (self.profile_generator.current_plan_step_index >= len(self.intermediate_plan or []) -1) if self.intermediate_plan else True; self.btn_next.configure(text="Finish & Review Profile >" if is_last else "Confirm Logic & Next Step >")
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE: self.btn_previous.configure(state="normal"); self.btn_next.configure(text="Save Profile & Close")

    def _show_current_page(self): # Unchanged
        self._clear_main_content_frame(); setup_method = {PAGE_GOAL_INPUT: self._setup_page_goal_input, PAGE_PLAN_REVIEW: self._setup_page_plan_review, PAGE_STEP_DEFINE_REGION: self._setup_page_step_define_region, PAGE_STEP_DEFINE_LOGIC: self._setup_page_step_define_logic, PAGE_FINAL_REVIEW_SAVE: self._setup_page_final_review_save}.get(self.current_page_index)
        if setup_method: setup_method()
        else: ctk.CTkLabel(self.main_content_frame, text=f"Error: Page {self.current_page_index}").pack()
        self._update_navigation_buttons_state(); self.focus_set()

    def _setup_page_goal_input(self): # Unchanged
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

    def _capture_full_screen_context(self): # Unchanged
        logger.info("Capturing full screen for context..."); try:
            self.attributes("-alpha", 0.0); self.lower(); self.update_idletasks(); time.sleep(0.3); img_pil = ImageGrab.grab(all_screens=True); self.attributes("-alpha", 1.0); self.lift(); self.focus_set()
            if img_pil: self.current_full_context_pil = img_pil.convert("RGB"); img_np_rgb = np.array(self.current_full_context_pil); self.current_full_context_np = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR); self.profile_generator.set_current_visual_context(self.current_full_context_np); logger.info(f"Full screen captured (Size: {img_pil.width}x{img_pil.height}).")
            else: self.current_full_context_pil = self.current_full_context_np = None; self.profile_generator.set_current_visual_context(None); logger.error("Full screen capture failed (ImageGrab None).")
        except Exception as e: self.current_full_context_pil = self.current_full_context_np = None; self.profile_generator.set_current_visual_context(None); logger.error(f"Error capturing full screen: {e}", exc_info=True); _ = self.attributes("-alpha", 1.0); self.lift() if self.winfo_exists() else None
        self._update_context_image_preview()

    def _load_image_context(self): # Unchanged
        filepath = filedialog.askopenfilename(title="Select Context Image", filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")], parent=self)
        if filepath:
            try: img_pil = Image.open(filepath); self.current_full_context_pil = img_pil.convert("RGB"); img_np_rgb = np.array(self.current_full_context_pil); self.current_full_context_np = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR); self.profile_generator.set_current_visual_context(self.current_full_context_np); logger.info(f"Context image loaded: '{filepath}' (Size: {img_pil.width}x{img_pil.height}).")
            except Exception as e: self.current_full_context_pil = self.current_full_context_np = None; self.profile_generator.set_current_visual_context(None); logger.error(f"Error loading context image: {e}", exc_info=True)
        self._update_context_image_preview()

    def _update_context_image_preview(self): # Unchanged
        if not hasattr(self, 'context_image_preview_label') or not self.context_image_preview_label: return
        if self.current_full_context_pil: img_copy = self.current_full_context_pil.copy(); preview_max_w, preview_max_h = 350, 200; img_copy.thumbnail((preview_max_w, preview_max_h), Image.Resampling.LANCZOS); ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=(img_copy.width, img_copy.height)); self.context_image_preview_label.configure(image=ctk_img, text=f"Context: {self.current_full_context_pil.width}x{self.current_full_context_pil.height} (Loaded)", height=img_copy.height + 10)
        else: self.context_image_preview_label.configure(image=None, text="No context image selected.", height=150)

    def _setup_page_plan_review(self): # Unchanged
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

    def _setup_page_step_define_region(self): # Unchanged
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

    def display_current_full_context_with_optional_overlay(self, label_widget: ctk.CTkLabel, overlay_box: Optional[List[int]] = None, box_color="red"): # Unchanged
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

    def _handle_ai_suggest_region(self): # Unchanged
        if not self.current_plan_step_data: return
        logger.info(f"User req AI region suggestion: {self.current_plan_step_data.get('description')}")
        self.btn_ai_suggest_region.configure(text="AI Suggesting...", state="disabled"); self.btn_draw_region_manually.configure(state="disabled"); self.update_idletasks()
        suggestion = self.profile_generator.suggest_region_for_step(self.current_plan_step_data)
        self.btn_ai_suggest_region.configure(text="AI Suggest Region", state="normal"); self.btn_draw_region_manually.configure(state="normal")
        if suggestion and suggestion.get("box"):
            box = suggestion["box"]; self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label, box, "orange")
            name_hint = suggestion.get("suggested_region_name_hint", f"step{self.current_plan_step_data.get('step_id')}_ai_region"); self.current_step_region_name_entry.delete(0, tk.END); self.current_step_region_name_entry.insert(0, name_hint)
            self._temp_suggested_region_coords = {"x": box[0], "y": box[1], "width": box[2], "height": box[3]}; self.current_step_region_coords = self._temp_suggested_region_coords; self.current_step_region_defined = True # Mark as defined for nav button state
            messagebox.showinfo("AI Suggestion", f"AI suggests highlighted region (named '{name_hint}').\nReasoning: {suggestion.get('reasoning', 'N/A')}\nVerify, edit name, then 'Confirm Region'. Or, draw manually.", parent=self)
        else: self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label); messagebox.showwarning("AI Suggestion Failed", "AI could not suggest a region. Define manually.", parent=self)
        self._update_navigation_buttons_state()

    def _handle_draw_region_manually(self): # Unchanged
        if not self.current_plan_step_data: return
        logger.info(f"User opted to draw region manually for: {self.current_plan_step_data.get('description')}")
        self.attributes("-alpha", 0.0); self.lower(); self.update_idletasks(); time.sleep(0.2)
        capture_pil = self.current_full_context_pil
        if not capture_pil: temp_np = self.capture_engine.capture_region({"x":0,"y":0,"width":self.winfo_screenwidth(), "height":self.winfo_screenheight()}); capture_pil = Image.fromarray(cv2.cvtColor(temp_np, cv2.COLOR_BGR2RGB)) if temp_np is not None else None
        self.attributes("-alpha", 1.0); self.lift(); self.focus_set()
        if not capture_pil: messagebox.showerror("Capture Error", "Failed to get screen image for manual region selection.", parent=self); return
        temp_cm = ConfigManager(None, create_if_missing=True)
        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1); initial_name = self.current_step_region_name_entry.get() or (self._temp_suggested_region_coords and self.current_plan_step_data.get('suggested_region_name_hint')) or f"step{step_id}_manual_region"
        existing_data = {"name": initial_name, **(self.current_step_region_coords if self.current_step_region_defined else self._temp_suggested_region_coords or copy.deepcopy(DEFAULT_REGION_STRUCTURE_PG))}
        selector = RegionSelectorWindow(master=self, config_manager_for_saving_path_only=temp_cm, existing_region_data=existing_data, direct_image_input_pil=capture_pil)
        self.wait_window(selector)
        if hasattr(selector, 'saved_region_info') and selector.saved_region_info:
            cr = selector.saved_region_info; self.current_step_region_name = cr["name"]; self.current_step_region_coords = {k: cr[k] for k in ["x","y","width","height"]}; self.current_step_region_defined = True
            self.current_step_region_name_entry.delete(0, tk.END); self.current_step_region_name_entry.insert(0, self.current_step_region_name)
            box_to_draw = [self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']]
            self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label, box_to_draw, SELECTED_CANDIDATE_BOX_COLOR)
        self._update_navigation_buttons_state()

    def _confirm_and_add_current_step_region(self) -> bool: # Unchanged
        if not self.current_step_region_defined or not self.current_step_region_coords: messagebox.showerror("Error", "No region defined/confirmed.", parent=self); return False
        region_name = self.current_step_region_name_entry.get().strip()
        if not region_name: messagebox.showerror("Input Error", "Region Name empty.", parent=self); self.current_step_region_name_entry.focus(); return False
        existing_regions_in_draft = self.profile_generator.generated_profile_data.get("regions", [])
        if any(r.get("name") == region_name for r in existing_regions_in_draft):
            if not messagebox.askyesno("Name Conflict", f"Region '{region_name}' already exists. Overwrite/use it?", parent=self): self.current_step_region_name_entry.focus(); return False
            else: self.profile_generator.generated_profile_data["regions"] = [r for r in existing_regions_in_draft if r.get("name") != region_name]
        step_desc = self.current_plan_step_data.get('description', 'N/A') if self.current_plan_step_data else 'N/A'
        region_data_to_add = {"name": region_name, **self.current_step_region_coords, "comment": f"For AI Gen Step: {step_desc}"}
        if self.profile_generator.add_region_definition(region_data_to_add):
            self.current_step_region_name = region_name
            if self.current_full_context_np is not None and self.current_step_region_coords:
                x,y,w,h = self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']
                img_h_full, img_w_full = self.current_full_context_np.shape[:2]; x_c,y_c = max(0, x), max(0, y); x2_c,y2_c = min(img_w_full, x + w), min(img_h_full, y + h); w_c,h_c = x2_c - x_c, y2_c - y_c
                if w_c > 0 and h_c > 0: self.current_step_region_image_np = self.current_full_context_np[y_c:y2_c, x_c:x2_c]; self.current_step_region_image_pil_for_display = Image.fromarray(cv2.cvtColor(self.current_step_region_image_np, cv2.COLOR_BGR2RGB)); logger.info(f"Cropped region image '{region_name}'.")
                else: self.current_step_region_image_np = self.current_step_region_image_pil_for_display = None; logger.error(f"Failed to crop valid region image '{region_name}'."); messagebox.showerror("Crop Error", "Defined region resulted in invalid crop.", parent=self); return False
            else: self.current_step_region_image_np = self.current_step_region_image_pil_for_display = None; logger.warning("No full context image to crop from.")
            self._temp_suggested_region_coords = None; return True
        return False
        
    def _setup_page_final_review_save(self): # Unchanged
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Final Review & Save Profile", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0,15), anchor="w")
        profile_summary_textbox = ctk.CTkTextbox(page_frame, height=450, wrap="word", state="disabled", font=ctk.CTkFont(family="Courier New", size=11)); profile_summary_textbox.pack(fill="both", expand=True, pady=(0,10))
        data = self.profile_generator.get_generated_profile_data(); default_desc = data.get("profile_description", self.user_goal_text[:100] or "AI Generated Profile"); data["profile_description"] = default_desc
        try: text = json.dumps(data, indent=2); profile_summary_textbox.configure(state="normal"); profile_summary_textbox.delete("0.0", "end"); profile_summary_textbox.insert("0.0", text); profile_summary_textbox.configure(state="disabled")
        except Exception as e: profile_summary_textbox.configure(state="normal"); profile_summary_textbox.delete("0.0", "end"); profile_summary_textbox.insert("0.0", f"Error: {e}"); profile_summary_textbox.configure(state="disabled")
        name_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); name_frame.pack(fill="x", pady=(10,5))
        ctk.CTkLabel(name_frame, text="Profile Filename:").pack(side="left", padx=(0,5))
        self.profile_filename_entry = ctk.CTkEntry(name_frame, placeholder_text=self.generated_profile_name_base); self.profile_filename_entry.pack(side="left", expand=True, fill="x"); self.profile_filename_entry.insert(0, self.generated_profile_name_base)
        logger.debug("Page Final Review UI setup.")

    def _on_close_wizard(self, event=None, was_saved=False): # Unchanged
        if not was_saved and messagebox.askokcancel("Cancel Profile Generation?", "Discard this profile and close wizard?", parent=self, icon=messagebox.WARNING): logger.info("AI Profile Wizard cancelled (unsaved)."); self.destroy()
        elif was_saved: logger.info("AI Profile Wizard closing (saved)."); self.destroy()
    
    def _display_current_step_region_image_with_candidates(self, candidate_boxes: Optional[List[Dict[str,Any]]] = None, selected_box_idx: Optional[int] = None): # Unchanged
        if not hasattr(self, 'step_logic_region_image_label') or not self.step_logic_region_image_label or not self.step_logic_region_image_label.winfo_exists(): return
        if not self.current_step_region_image_pil_for_display: self.step_logic_region_image_label.configure(text="No image for current step's region.", image=None); return
        img_pil_to_draw_on = self.current_step_region_image_pil_for_display.copy(); draw = ImageDraw.Draw(img_pil_to_draw_on, "RGBA")
        if candidate_boxes:
            for i, candidate in enumerate(candidate_boxes):
                box = candidate.get("box");
                if box and len(box) == 4:
                    color = SELECTED_CANDIDATE_BOX_COLOR if i == selected_box_idx else CANDIDATE_BOX_COLORS[i % len(CANDIDATE_BOX_COLORS)]; fill_color = color + "40"; x,y,w,h = box
                    draw.rectangle([x,y, x+w, y+h], outline=color, width=2, fill=fill_color if i != selected_box_idx else None)
                    if i == selected_box_idx: cx,cy=x+w//2,y+h//2; draw.line([(cx-6,cy),(cx+6,cy)],fill=color,width=3); draw.line([(cx,cy-6),(cx,cy+6)],fill=color,width=3)
                    label_text = str(i + 1); text_x, text_y = x + 3, y + 1
                    try: draw.text((text_x-1,text_y-1),label_text,font=self.overlay_font,fill="white"); draw.text((text_x+1,text_y-1),label_text,font=self.overlay_font,fill="white"); draw.text((text_x-1,text_y+1),label_text,font=self.overlay_font,fill="white"); draw.text((text_x+1,text_y+1),label_text,font=self.overlay_font,fill="white"); draw.text((text_x,text_y),label_text,font=self.overlay_font,fill=color)
                    except Exception: draw.text((text_x,text_y),label_text,fill=color) # Fallback
        max_w,max_h = WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH-50, WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT-50; thumb = img_pil_to_draw_on.copy(); thumb.thumbnail((max_w,max_h), Image.Resampling.LANCZOS); dw,dh=thumb.size
        ctk_img = ctk.CTkImage(light_image=thumb,dark_image=thumb,size=(dw,dh)); self.step_logic_region_image_label.configure(image=ctk_img,text="",width=dw,height=dh)
        self.step_logic_region_image_label.photo_image_scale_factor = self.current_step_region_image_pil_for_display.width / float(dw) if dw > 0 else 1.0

    def _on_region_image_click_for_element_selection(self, event): # Unchanged
        if not self.refined_element_candidates or not hasattr(self.step_logic_region_image_label, 'photo_image_scale_factor'): return
        scale = getattr(self.step_logic_region_image_label, 'photo_image_scale_factor', 1.0); click_x_orig, click_y_orig = int(event.x*scale), int(event.y*scale)
        newly_selected_idx = next((i for i,c in enumerate(self.refined_element_candidates) if c.get("box") and (c["box"][0]<=click_x_orig<c["box"][0]+c["box"][2]) and (c["box"][1]<=click_y_orig<c["box"][1]+c["box"][3])), None)
        if newly_selected_idx is not None and newly_selected_idx != self.selected_candidate_box_index: self.selected_candidate_box_index = newly_selected_idx; self._display_current_step_region_image_with_candidates(self.refined_element_candidates, self.selected_candidate_box_index); self._update_action_params_with_selected_element()
        elif newly_selected_idx is None and self.selected_candidate_box_index is not None: self.selected_candidate_box_index = None; self._display_current_step_region_image_with_candidates(self.refined_element_candidates, None); self._clear_action_target_params()

    def _update_action_params_with_selected_element(self): # Unchanged
        if self.selected_candidate_box_index is None or not self.refined_element_candidates or self.selected_candidate_box_index >= len(self.refined_element_candidates): self.confirmed_element_for_action = None; return
        sel_cand = self.refined_element_candidates[self.selected_candidate_box_index]
        self.confirmed_element_for_action = {"value": {"box": sel_cand["box"], "found": True, "element_label": sel_cand.get("label_suggestion", self.element_to_refine_desc_for_step or "AI Element")}, "_source_region_for_capture_": self.current_step_region_name}
        logger.info(f"Element confirmed for action: Label='{self.confirmed_element_for_action['value']['element_label']}', Box={self.confirmed_element_for_action['value']['box']}")
        act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
        if act_type_var: act_type_var.set("click"); self._on_wizard_logic_type_change("action", "click"); self.after(50, self._set_click_action_params_for_selected_element)

    def _set_click_action_params_for_selected_element(self): # Unchanged
        rel_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var"); gem_var_entry = self.step_logic_detail_widgets.get("step_act_gemini_element_variable")
        if rel_var: rel_var.set("center_of_gemini_element"); tr_pdef = next((p for p in UI_PARAM_CONFIG["actions"]["click"] if p["id"]=="target_relation"),None);_ = self._update_step_logic_conditional_visibility(tr_pdef,"center_of_gemini_element") if tr_pdef else None
        if gem_var_entry and isinstance(gem_var_entry,ctk.CTkEntry): gem_var_entry.delete(0,tk.END); gem_var_entry.insert(0, self._current_step_temp_var_name_for_gemini_element or "_wizard_sel_elem_")
        logger.debug(f"Wizard: Click action UI params set for visually selected element (var: {self._current_step_temp_var_name_for_gemini_element}).")

    def _clear_action_target_params(self): # Unchanged
        self.confirmed_element_for_action = None; act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
        if act_type_var and act_type_var.get() == "click":
            rel_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var"); gem_var_entry = self.step_logic_detail_widgets.get("step_act_gemini_element_variable")
            if rel_var: rel_var.set("center_of_region")
            if gem_var_entry and isinstance(gem_var_entry,ctk.CTkEntry): gem_var_entry.delete(0,tk.END)
            tr_pdef = next((p for p in UI_PARAM_CONFIG["actions"]["click"] if p["id"]=="target_relation"),None);_ = self._update_step_logic_conditional_visibility(tr_pdef,"center_of_region") if tr_pdef else None
        logger.debug("Cleared action target parameters in UI.")

    def _attempt_set_template_name_in_ui(self, template_name_to_set: str): # Unchanged
        widget_key="step_cond_template_name"; tk_var=self.step_logic_optionmenu_vars.get(f"{widget_key}_var"); widget=self.step_logic_detail_widgets.get(widget_key)
        if tk_var and isinstance(tk_var,tk.StringVar) and widget and isinstance(widget,ctk.CTkOptionMenu):
            new_opts=[""]+[t.get("name","") for t in self.profile_generator.generated_profile_data.get("templates",[]) if t.get("name")]
            widget.configure(values=new_opts);_ = tk_var.set(template_name_to_set) if template_name_to_set in new_opts else logger.warning(f"New template '{template_name_to_set}' not in dropdown.")
        else: logger.warning(f"Could not find/set template_name dropdown for '{template_name_to_set}'.")

    def _set_click_action_params_for_template(self, template_name: str): # Unchanged
        target_relation_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var")
        if target_relation_var and isinstance(target_relation_var, tk.StringVar): target_relation_var.set("center_of_last_match"); tr_pdef=next((p for p in UI_PARAM_CONFIG["actions"]["click"] if p["id"]=="target_relation"),None);_ = self._update_step_logic_conditional_visibility(tr_pdef,"center_of_last_match") if tr_pdef else None; logger.info(f"Action UI set to click 'center_of_last_match' for template '{template_name}'.")
        gem_var_entry=self.step_logic_detail_widgets.get("step_act_gemini_element_variable");_ = gem_var_entry.delete(0,tk.END) if gem_var_entry and isinstance(gem_var_entry,ctk.CTkEntry) else None; self.confirmed_element_for_action=None

    def _get_parameters_from_ui_wizard_scoped(self, param_group_key: str, item_subtype: str, widget_prefix: str) -> Optional[Dict[str, Any]]: # Unchanged
        params: Dict[str,Any]={"type":item_subtype}; all_ok=True; param_defs=UI_PARAM_CONFIG.get(param_group_key,{}).get(item_subtype,[])
        if not param_defs and item_subtype!="always_true": return params
        for p_def in param_defs:
            p_id,lbl_err,target_type,def_val,is_req_def = p_def["id"],p_def["label"].rstrip(":"),p_def["type"],p_def.get("default",""),p_def.get("required",False)
            w_key=f"{widget_prefix}{p_id}"; widget=self.step_logic_detail_widgets.get(w_key); tk_var=self.step_logic_optionmenu_vars.get(f"{w_key}_var")
            is_vis= widget.winfo_ismapped() if widget and widget.winfo_exists() else False; eff_req = is_req_def and is_vis
            if not is_vis and not eff_req: continue
            if widget is None and not isinstance(tk_var, tk.BooleanVar):
                if eff_req: logger.error(f"Wizard GetParams: Widget for required '{lbl_err}' not found."); all_ok=False
                params[p_id]=def_val; continue
            val_args={"required":eff_req,"allow_empty_string":p_def.get("allow_empty_string",target_type==str),"min_val":p_def.get("min_val"),"max_val":p_def.get("max_val")}
            val,valid = validate_and_get_widget_value(widget,tk_var,lbl_err,target_type,def_val,**val_args)
            if not valid: all_ok=False; val=def_val 
            if target_type=="list_str_csv": params[p_id]=[s.strip() for s in val.split(',')] if isinstance(val,str) and val.strip() else ([] if not def_val or not isinstance(def_val,list) else def_val)
            else: params[p_id]=val
            if p_id=="template_name" and param_group_key=="conditions":
                s_tpl_name=val; params["template_filename"] = ""
                if s_tpl_name: fname=next((t.get("filename","") for t in self.profile_generator.generated_profile_data.get("templates",[]) if t.get("name")==s_tpl_name),""); params["template_filename"]=fname; _ = (messagebox.showerror("Internal Error",f"Filename for template '{s_tpl_name}' missing.",parent=self),all_ok:=False) if not fname and eff_req else None
                elif eff_req: messagebox.showerror("Input Error",f"'{lbl_err}' required.",parent=self);all_ok=False
                if "template_name" in params: del params["template_name"]
        if item_subtype=="always_true" and param_group_key=="conditions":
            region_pdef=next((pd for pd in param_defs if pd["id"]=="region"),None)
            if region_pdef: val,_ = validate_and_get_widget_value(self.step_logic_detail_widgets.get(f"{widget_prefix}region"),self.step_logic_optionmenu_vars.get(f"{widget_prefix}region_var"),"Region",str,"",required=False);_ = params.update({"region":val}) if val else None
        return params if all_ok else None

    def _go_to_next_page(self): # Unchanged
        logger.debug(f"Next clicked. Current page: {self.current_page_index}")
        if self.current_page_index == PAGE_GOAL_INPUT:
            self.user_goal_text = self.goal_textbox.get("0.0", "end-1c").strip();
            if not self.user_goal_text: messagebox.showerror("Input Error", "Describe goal.", parent=self); return
            loading_lbl = ctk.CTkLabel(self.main_content_frame, text="AI generating plan...", font=ctk.CTkFont(size=16)); loading_lbl.pack(pady=10); self.update_idletasks()
            self.intermediate_plan = self.strategy_planner.generate_intermediate_plan(self.user_goal_text, self.current_full_context_np)
            if self.intermediate_plan and len(self.intermediate_plan) > 0: self.profile_generator.start_profile_generation(self.intermediate_plan, f"AI-Gen for: {self.user_goal_text[:70]}", initial_full_screen_context_np=self.current_full_context_np); self.current_page_index = PAGE_PLAN_REVIEW; self._reset_step_specific_state()
            else: messagebox.showerror("AI Plan Failed", "Could not generate plan.", parent=self); self._show_current_page(); return
        elif self.current_page_index == PAGE_PLAN_REVIEW:
            if not self.intermediate_plan: messagebox.showerror("Error", "No plan.", parent=self); return
            if self.profile_generator.advance_to_next_plan_step(): self.current_page_index = PAGE_STEP_DEFINE_REGION; self._reset_step_specific_state()
            else: messagebox.showerror("Error", "Plan empty/invalid.", parent=self)
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            if self._confirm_and_add_current_step_region(): self.current_page_index = PAGE_STEP_DEFINE_LOGIC
            else: return 
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC:
            logic = self._get_current_step_logic_from_ui()
            if logic:
                cond, act = logic; step = self.profile_generator.get_current_plan_step()
                if step and self.current_step_region_name:
                    base_name = f"Rule_S{step.get('step_id')}_{step.get('description','T')[:15].replace(' ','_').replace("'", "")}"; rule_name=base_name; c=1
                    while any(r.get("name")==rule_name for r in self.profile_generator.generated_profile_data.get("rules",[])): rule_name=f"{base_name}_{c}";c+=1
                    rule_add = {"name":rule_name, "region":self.current_step_region_name, "condition":cond, "action":act, "comment":f"AI Gen for: {step.get('description')}"}
                    if self.profile_generator.add_rule_definition(rule_add): logger.info(f"Rule '{rule_name}' added for step {step.get('step_id')}.")
                    else: messagebox.showerror("Error", f"Failed to add rule for step {step.get('step_id')}.",parent=self); return
                else: messagebox.showerror("Internal Error", "Missing step data or region name.",parent=self); return
                if self.profile_generator.advance_to_next_plan_step(): self.current_page_index = PAGE_STEP_DEFINE_REGION; self._reset_step_specific_state()
                else: self.current_page_index = PAGE_FINAL_REVIEW_SAVE
            else: return 
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE: self._save_generated_profile(); return 
        self._show_current_page()

    def _go_to_previous_page(self): # Unchanged
        logger.debug(f"Previous clicked. Current: {self.current_page_index}"); cur_pg_idx = self.profile_generator.current_plan_step_index
        if self.current_page_index == PAGE_PLAN_REVIEW: self.current_page_index = PAGE_GOAL_INPUT
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            if cur_pg_idx == 0 : self.current_page_index = PAGE_PLAN_REVIEW; self.profile_generator.current_plan_step_index = -1
            elif cur_pg_idx > 0: self.profile_generator.current_plan_step_index -= 1; self._load_state_for_current_pg_step(); self.current_page_index = PAGE_STEP_DEFINE_LOGIC
            else: self.current_page_index = PAGE_PLAN_REVIEW
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC: self.current_page_index = PAGE_STEP_DEFINE_REGION
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE:
            if self.intermediate_plan and len(self.intermediate_plan)>0:
                if self.profile_generator.current_plan_step_index >= len(self.intermediate_plan): self.profile_generator.current_plan_step_index = len(self.intermediate_plan)-1
                if self.profile_generator.current_plan_step_index >=0: self._load_state_for_current_pg_step(); self.current_page_index = PAGE_STEP_DEFINE_LOGIC
                else: self.current_page_index = PAGE_PLAN_REVIEW
            else: self.current_page_index = PAGE_GOAL_INPUT
        self._show_current_page()

    def _reset_step_specific_state(self): # Unchanged
        self.current_step_region_name=None; self.current_step_region_coords=None; self.current_step_region_image_np=None; self.current_step_region_image_pil_for_display=None
        self.current_step_region_defined=False; self._temp_suggested_region_coords=None; self.suggested_condition_for_step=None; self.suggested_action_for_step=None
        self.element_to_refine_desc_for_step=None; self.refined_element_candidates=[]; self.selected_candidate_box_index=None; self.confirmed_element_for_action=None
        if hasattr(self,'element_refine_entry') and self.element_refine_entry and self.element_refine_entry.winfo_exists(): self.element_refine_entry.delete(0,tk.END)
        logger.debug("Wizard: Step-specific state variables reset.")

    def _load_state_for_current_pg_step(self): # Unchanged
        self.current_plan_step_data = self.profile_generator.get_current_plan_step()
        if not self.current_plan_step_data: self._reset_step_specific_state(); return
        step_id = self.current_plan_step_data.get("step_id", self.profile_generator.current_plan_step_index + 1); logger.info(f"Wizard: Loading/re-evaluating state for Step ID {step_id}.")
        rule_prefix = f"Rule_Step{step_id}"; rule = next((r for r in self.profile_generator.generated_profile_data.get("rules",[]) if r.get("name","").startswith(rule_prefix)),None)
        if rule:
            self.current_step_region_name = rule.get("region")
            if self.current_step_region_name:
                r_cfg = next((r for r in self.profile_generator.generated_profile_data.get("regions",[]) if r.get("name")==self.current_step_region_name),None)
                if r_cfg: self.current_step_region_coords = {k:r_cfg[k] for k in ["x","y","width","height"]}; self.current_step_region_defined=True
                    if self.current_full_context_np is not None and self.current_step_region_coords:
                        x,y,w,h = map(self.current_step_region_coords.get, ["x","y","width","height"]); img_h_f,img_w_f=self.current_full_context_np.shape[:2]; x,y=max(0,x),max(0,y); x2,y2=min(img_w_f,x+w),min(img_h_f,y+h); w,h=x2-x,y2-y
                        if w>0 and h>0: self.current_step_region_image_np=self.current_full_context_np[y:y2,x:x2]; self.current_step_region_image_pil_for_display=Image.fromarray(cv2.cvtColor(self.current_step_region_image_np, cv2.COLOR_BGR2RGB))
            self.suggested_condition_for_step=copy.deepcopy(rule.get("condition")); self.suggested_action_for_step=copy.deepcopy(rule.get("action"))
            self.confirmed_element_for_action=None; self.selected_candidate_box_index=None; self.refined_element_candidates=[]
            return
        self._reset_step_specific_state()

    def _save_generated_profile(self): # Updated to get profile name from entry at save time
        logger.info("Save Profile button on final review page.")
        filename_base = self.profile_filename_entry.get().strip();
        if not filename_base: messagebox.showerror("Filename Missing", "Please enter filename.", parent=self); return
        # Update profile_description in the data just before saving
        current_data = self.profile_generator.get_generated_profile_data()
        current_data["profile_description"] = f"AI-Generated for goal: {self.user_goal_text[:120]}" if self.user_goal_text else "AI-Generated Profile"
        self.profile_generator.generated_profile_data = current_data # Update PG's internal copy

        default_save_dir = self.main_app_instance.config_manager.profiles_base_dir # Use main app CM's profile dir
        initial_filename = f"{filename_base}.json" # Use user-entered name
        filepath = tk.filedialog.asksaveasfilename(title="Save AI-Generated Profile As", initialdir=default_save_dir, initialfile=initial_filename, defaultextension=".json", filetypes=[("JSON","*.json"),("All","*.*")], parent=self)
        if filepath:
            # ProfileGenerator uses its own ConfigManager instance to save its generated_profile_data
            # The path used by PG's CM will be set to 'filepath' by its save_current_profile method.
            success = self.profile_generator.save_generated_profile(filepath)
            if success:
                messagebox.showinfo("Profile Saved", f"AI-Generated profile saved to:\n{filepath}", parent=self)
                if messagebox.askyesno("Open in Editor?", "Open the new profile in the main editor?", parent=self): self.main_app_instance._load_profile_from_path(filepath)
                self._on_close_wizard(was_saved=True)
            else: messagebox.showerror("Save Failed", "Could not save profile. Check logs.", parent=self)
        else: logger.info("Profile save dialog cancelled.")