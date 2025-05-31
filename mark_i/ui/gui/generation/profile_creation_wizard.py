import logging
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import json
import copy
import time
import threading
from typing import Optional, Dict, Any, List, Union, Callable, Tuple

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk, ImageDraw, UnidentifiedImageError, ImageFont, ImageGrab # Added ImageFont
import cv2

from mark_i.generation.strategy_planner import StrategyPlanner, IntermediatePlan, IntermediatePlanStep
from mark_i.generation.profile_generator import ProfileGenerator, DEFAULT_CONDITION_STRUCTURE_PG, DEFAULT_ACTION_STRUCTURE_PG
from mark_i.ui.gui.generation.sub_image_selector_window import SubImageSelectorWindow
from mark_i.engines.gemini_analyzer import GeminiAnalyzer
from mark_i.core.config_manager import ConfigManager, TEMPLATES_SUBDIR_NAME
from mark_i.ui.gui.region_selector import RegionSelectorWindow
from mark_i.engines.capture_engine import CaptureEngine

from mark_i.ui.gui.gui_config import (
    CONDITION_TYPES,
    ACTION_TYPES,
    UI_PARAM_CONFIG, OPTIONS_CONST_MAP
)
from mark_i.ui.gui.gui_utils import validate_and_get_widget_value

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.ui.gui.generation.profile_creation_wizard")

PAGE_GOAL_INPUT = 0
PAGE_PLAN_REVIEW = 1
PAGE_STEP_DEFINE_REGION = 2
PAGE_STEP_DEFINE_LOGIC = 3
PAGE_FINAL_REVIEW_SAVE = 4

WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH = 600
WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT = 380
CANDIDATE_BOX_COLORS = ["#FF00FF", "#00FFFF", "#FFFF00", "#F08080", "#90EE90", "#ADD8E6", "#FFC0CB", "#E6E6FA"]
SELECTED_CANDIDATE_BOX_COLOR = "lime green"
FONT_PATH_PRIMARY = "arial.ttf"
FONT_PATH_FALLBACK = "DejaVuSans.ttf"

USER_INPUT_PLACEHOLDER_PREFIX = "USER_INPUT_REQUIRED__"

class ProfileCreationWizardWindow(ctk.CTkToplevel):
    """
    A wizard-style window to guide the user through AI-assisted profile creation.
    It interacts with StrategyPlanner to get a plan from a user goal,
    and then with ProfileGenerator to iteratively define profile elements
    (regions, rules) for each step of the plan, with AI suggestions for
    regions, conditions, actions, and visual element refinement.
    Includes functionality for template capture during the process.
    Implements threading for long-running AI calls to keep GUI responsive.
    """
    def __init__(self, master: Any, main_app_instance: Any): # main_app_instance is MainAppWindow
        super().__init__(master)
        self.main_app_instance = main_app_instance
        self.title("AI Profile Creator Wizard")
        self.transient(master); self.grab_set(); self.attributes("-topmost", True)
        self.geometry("1100x850"); self.minsize(950, 750)
        self.protocol("WM_DELETE_WINDOW", self._on_close_wizard)
        self.user_cancelled_wizard = False
        self.newly_saved_profile_path: Optional[str] = None

        # --- Backend Components Initialization ---
        if not hasattr(self.main_app_instance, 'gemini_analyzer_instance') or \
           not self.main_app_instance.gemini_analyzer_instance or \
           not self.main_app_instance.gemini_analyzer_instance.client_initialized:
            logger.critical("ProfileCreationWizard: GeminiAnalyzer not available or not initialized in MainApp. Cannot proceed.")
            messagebox.showerror("Critical API Error", "Gemini API client is not properly initialized.\nPlease ensure your GEMINI_API_KEY is correctly set in .env and the application was restarted.", parent=self)
            self.after(100, self.destroy)
            return

        self.strategy_planner = StrategyPlanner(gemini_analyzer=self.main_app_instance.gemini_analyzer_instance)
        self.profile_generator_cm = ConfigManager(None, create_if_missing=True)
        self.profile_generator = ProfileGenerator(
            gemini_analyzer=self.main_app_instance.gemini_analyzer_instance,
            config_manager=self.profile_generator_cm
        )
        self.capture_engine = CaptureEngine()

        # --- Wizard State Variables ---
        self.current_page_index: int = PAGE_GOAL_INPUT
        self.intermediate_plan: Optional[IntermediatePlan] = None
        self.current_full_context_pil: Optional[Image.Image] = None
        self.current_full_context_np: Optional[np.ndarray] = None
        self.user_goal_text: str = ""
        self.generated_profile_name_base: str = "ai_generated_profile"

        self.current_plan_step_data: Optional[IntermediatePlanStep] = None
        self.current_step_region_name: Optional[str] = None
        self.current_step_region_coords: Optional[Dict[str, int]] = None
        self.current_step_region_defined_for_pg: bool = False

        self.current_step_region_image_np: Optional[np.ndarray] = None
        self.current_step_region_image_pil_for_display: Optional[Image.Image] = None

        self._temp_suggested_region_coords: Optional[Dict[str,int]] = None

        self.ui_suggested_condition_for_step: Optional[Dict[str, Any]] = None
        self.ui_suggested_action_for_step: Optional[Dict[str, Any]] = None
        self.ui_element_to_refine_desc: Optional[str] = None
        self.ui_refined_element_candidates: List[Dict[str, Any]] = []
        self.ui_selected_candidate_box_index: Optional[int] = None
        self.ui_confirmed_element_for_action: Optional[Dict[str, Any]] = None
        self._ui_current_step_temp_var_name: Optional[str] = None

        # UI Frames & Controls
        self.main_content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content_frame.pack(fill="both", expand=True, padx=15, pady=15)
        self.main_content_frame.grid_rowconfigure(0, weight=1); self.main_content_frame.grid_columnconfigure(0, weight=1)

        self.navigation_frame = ctk.CTkFrame(self, height=60, fg_color=("gray80", "gray20"), corner_radius=0)
        self.navigation_frame.pack(fill="x", side="bottom", padx=0, pady=0)
        self.navigation_frame.grid_columnconfigure(0, weight=1); self.navigation_frame.grid_columnconfigure(4, weight=1)
        self.btn_cancel = ctk.CTkButton(self.navigation_frame, text="Cancel & Close Wizard", command=self._on_close_wizard, width=180, fg_color="firebrick1", hover_color="firebrick3")
        self.btn_cancel.grid(row=0, column=1, padx=(20,5), pady=10, sticky="w")
        self.btn_next = ctk.CTkButton(self.navigation_frame, text="Next >", command=self._go_to_next_page, width=140, font=ctk.CTkFont(weight="bold"))
        self.btn_next.grid(row=0, column=3, padx=(5,20), pady=10, sticky="e")
        self.btn_previous = ctk.CTkButton(self.navigation_frame, text="< Previous Step", command=self._go_to_previous_page, width=140)
        self.btn_previous.grid(row=0, column=2, padx=5, pady=10, sticky="e")

        self.step_logic_detail_widgets: Dict[str, Union[ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkTextbox]] = {}
        self.step_logic_optionmenu_vars: Dict[str, Union[tk.StringVar, tk.BooleanVar]] = {}
        self.step_logic_param_widgets_and_defs: List[Dict[str, Any]] = []
        self.step_logic_controlling_widgets: Dict[str, Union[ctk.CTkOptionMenu, ctk.CTkCheckBox]] = {}
        self.step_logic_widget_prefix: str = ""

        self.loading_overlay = ctk.CTkFrame(self, fg_color=("black", "black"), corner_radius=0)
        self.loading_label_overlay = ctk.CTkLabel(self.loading_overlay, text="AI is thinking...", font=ctk.CTkFont(size=18, weight="bold"), text_color="white")
        self.loading_label_overlay.pack(expand=True)

        try: self.overlay_font = ImageFont.truetype(FONT_PATH_PRIMARY, 11)
        except IOError:
            try: self.overlay_font = ImageFont.truetype(FONT_PATH_FALLBACK, 11)
            except IOError: self.overlay_font = ImageFont.load_default(); logger.warning("Arial/DejaVuSans fonts not found for image overlays, using PIL default.")

        self._show_current_page()
        logger.info("ProfileCreationWizardWindow initialized and Goal Input page shown.")
        self.after(150, self._center_window)

    def _show_loading_overlay(self, message="AI is thinking..."):
        self.loading_label_overlay.configure(text=message)
        self.loading_overlay.place(in_=self.main_content_frame, relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_overlay.lift()
        self.update_idletasks()

    def _hide_loading_overlay(self):
        self.loading_overlay.place_forget()

    def _center_window(self):
        self.update_idletasks(); master = self.master
        if master and master.winfo_exists():
            x = master.winfo_x() + (master.winfo_width()//2) - (self.winfo_width()//2)
            y = master.winfo_y() + (master.winfo_height()//2) - (self.winfo_height()//2)
            self.geometry(f"+{max(0,x)}+{max(0,y)}")
        else:
            self.geometry(f"+{(self.winfo_screenwidth()-self.winfo_width())//2}+{(self.winfo_screenheight()-self.winfo_height())//2}")
        self.lift(); self.focus_force()

    def _clear_main_content_frame(self):
        for widget in self.main_content_frame.winfo_children(): widget.destroy()
        self.step_logic_detail_widgets.clear(); self.step_logic_optionmenu_vars.clear()
        self.step_logic_param_widgets_and_defs.clear(); self.step_logic_controlling_widgets.clear()

    def _update_navigation_buttons_state(self):
        self.btn_previous.configure(state="disabled"); self.btn_next.configure(state="normal")
        if self.current_page_index == PAGE_GOAL_INPUT:
            self.btn_next.configure(text="Generate Plan >")
        elif self.current_page_index == PAGE_PLAN_REVIEW:
            self.btn_previous.configure(state="normal")
            can_proceed_plan_review = bool(self.intermediate_plan and len(self.intermediate_plan) > 0)
            self.btn_next.configure(text="Start Building Profile >", state="normal" if can_proceed_plan_review else "disabled")
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            self.btn_previous.configure(state="normal")
            can_proceed_define_region = bool(hasattr(self, 'current_step_region_name_entry') and self.current_step_region_name_entry.get().strip() and self.current_step_region_coords)
            self.btn_next.configure(text="Confirm Region & Define Logic >", state="normal" if can_proceed_define_region else "disabled")
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC:
            self.btn_previous.configure(state="normal")
            is_last_step_in_plan = (self.profile_generator.current_plan_step_index >= len(self.intermediate_plan or []) -1) if self.intermediate_plan else True
            self.btn_next.configure(text="Finish & Review Profile >" if is_last_step_in_plan else "Confirm Logic & Next Step >")
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE:
            self.btn_previous.configure(state="normal")
            self.btn_next.configure(text="Save Profile & Close")

    def _show_current_page(self):
        self._clear_main_content_frame()
        if self.current_page_index == PAGE_GOAL_INPUT: self._setup_page_goal_input()
        elif self.current_page_index == PAGE_PLAN_REVIEW: self._setup_page_plan_review()
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION: self._setup_page_step_define_region()
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC: self._setup_page_step_define_logic()
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE: self._setup_page_final_review_save()
        else: ctk.CTkLabel(self.main_content_frame, text=f"Error: Unknown page index {self.current_page_index}").pack()
        self._update_navigation_buttons_state()
        self.focus_set()

    def _setup_page_goal_input(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Step 1 - Define Your Automation Goal", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0,20), anchor="w")
        ctk.CTkLabel(page_frame, text="Describe the task Mark-I should learn and automate in detail:", anchor="w").pack(fill="x", pady=(5,2))
        self.goal_textbox = ctk.CTkTextbox(page_frame, height=180, wrap="word", font=ctk.CTkFont(size=13)); self.goal_textbox.pack(fill="x", pady=(0,15))
        self.goal_textbox.insert("0.0", self.user_goal_text or "Example: Open MyApp, log in with username 'testuser' and password 'password123', navigate to the 'Reports' section, then click the 'Generate Monthly Sales Report' button, and finally save the downloaded report as 'Sales_Report_ThisMonth.pdf' to the Desktop.")
        context_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); context_frame.pack(fill="x", pady=(10,5))
        ctk.CTkLabel(context_frame, text="Optional: Initial Visual Context (helps AI understand the starting screen):", anchor="w").pack(fill="x", pady=(0,5))
        btn_frame = ctk.CTkFrame(context_frame, fg_color="transparent"); btn_frame.pack(fill="x", pady=(0,5))
        ctk.CTkButton(btn_frame, text="Capture Full Screen", command=self._capture_full_screen_context, width=180).pack(side="left", padx=(0,10))
        ctk.CTkButton(btn_frame, text="Load Image from File", command=self._load_image_context, width=180).pack(side="left", padx=10)
        self.context_image_preview_label = ctk.CTkLabel(context_frame, text="No context image.", height=150, fg_color=("gray85","gray25"), corner_radius=6); self.context_image_preview_label.pack(fill="x", pady=(10,0))
        self._update_context_image_preview(); self.goal_textbox.focus_set(); logger.debug("Page Goal Input UI setup.")

    def _capture_full_screen_context(self):
        logger.info("Capturing full screen for context...")
        try:
            self.attributes("-alpha", 0.0); self.lower(); self.update_idletasks(); time.sleep(0.3)
            img_pil = ImageGrab.grab(all_screens=True)
            self.attributes("-alpha", 1.0); self.lift(); self.focus_set()
            if img_pil:
                self.current_full_context_pil = img_pil.convert("RGB")
                img_np_rgb = np.array(self.current_full_context_pil)
                self.current_full_context_np = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
                self.profile_generator.set_current_visual_context(self.current_full_context_np)
                logger.info(f"Full screen captured (Size: {img_pil.width}x{img_pil.height}).")
            else:
                self.current_full_context_pil = self.current_full_context_np = None
                self.profile_generator.set_current_visual_context(None)
                logger.error("Full screen capture failed (ImageGrab None).")
        except Exception as e:
            self.current_full_context_pil = self.current_full_context_np = None
            self.profile_generator.set_current_visual_context(None)
            logger.error(f"Error capturing full screen: {e}", exc_info=True)
            if self.winfo_exists():
                self.attributes("-alpha", 1.0); self.lift()
        self._update_context_image_preview()

    def _load_image_context(self):
        filepath = filedialog.askopenfilename(title="Select Context Image", filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp")], parent=self)
        if filepath:
            try:
                img_pil = Image.open(filepath)
                self.current_full_context_pil = img_pil.convert("RGB")
                img_np_rgb = np.array(self.current_full_context_pil)
                self.current_full_context_np = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
                self.profile_generator.set_current_visual_context(self.current_full_context_np)
                logger.info(f"Context image loaded: '{filepath}' (Size: {img_pil.width}x{img_pil.height}).")
            except Exception as e:
                self.current_full_context_pil = self.current_full_context_np = None
                self.profile_generator.set_current_visual_context(None)
                logger.error(f"Error loading context image: {e}", exc_info=True)
        self._update_context_image_preview()

    def _update_context_image_preview(self):
        if not hasattr(self, 'context_image_preview_label') or not self.context_image_preview_label.winfo_exists(): return
        if self.current_full_context_pil:
            img_copy = self.current_full_context_pil.copy()
            preview_max_w, preview_max_h = 350, self.context_image_preview_label.winfo_reqheight() - 20
            preview_max_h = max(50, preview_max_h)
            img_copy.thumbnail((preview_max_w, preview_max_h), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=(img_copy.width, img_copy.height))
            self.context_image_preview_label.configure(image=ctk_img, text=f"Context: {self.current_full_context_pil.width}x{self.current_full_context_pil.height} (Loaded)", height=img_copy.height + 10)
        else:
            self.context_image_preview_label.configure(image=None, text="No context image selected.", height=150)

    def _setup_page_plan_review(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Step 2 - Review Automation Plan", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0,15), anchor="w")
        if self.intermediate_plan and len(self.intermediate_plan) > 0 :
            ctk.CTkLabel(page_frame, text="Gemini has proposed the following high-level steps to achieve your goal:", font=ctk.CTkFont(size=14)).pack(anchor="w", pady=(5,5))
            plan_display_frame = ctk.CTkScrollableFrame(page_frame, height=450, fg_color=("gray92", "gray28")); plan_display_frame.pack(fill="both", expand=True, pady=(0,10))
            for i, step in enumerate(self.intermediate_plan):
                step_id = step.get('step_id', i+1)
                desc = step.get('description', 'N/A')
                hint = step.get('suggested_element_type_hint')
                inputs_needed = step.get('required_user_input_for_step', [])

                step_text = f"Step {step_id}: {desc}"
                details_parts = []
                if hint: details_parts.append(f"Element Hint: '{hint}'")
                if inputs_needed: details_parts.append(f"User Inputs Required: {', '.join(inputs_needed)}")
                if details_parts: step_text += f"\n  ► AI Details: {'. '.join(details_parts)}"

                ctk.CTkLabel(plan_display_frame, text=step_text, wraplength=self.winfo_width() - 120, anchor="w", justify="left", font=ctk.CTkFont(size=13)).pack(fill="x", pady=(4,6), padx=5)
        elif self.intermediate_plan is None:
             ctk.CTkLabel(page_frame, text="Generating plan... Please wait or check previous step if an error occurred.", wraplength=self.winfo_width()-40).pack(pady=20)
        else:
             ctk.CTkLabel(page_frame, text="AI generated an empty plan. This might mean the goal was too vague, too complex for direct steps, or deemed unsafe. Please refine your goal on the previous page or consider creating the profile manually using the main editor.", wraplength=self.winfo_width()-40, justify="left").pack(pady=20)
        logger.debug("Page Plan Review UI setup.")

    def _setup_page_step_define_region(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=5, pady=5)
        if not self.current_plan_step_data:
            ctk.CTkLabel(page_frame, text="Error: No current plan step data available. Please go back to Plan Review.").pack(pady=20)
            self._update_navigation_buttons_state(); return

        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1)
        step_desc = self.current_plan_step_data.get('description', 'N/A')

        header_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); header_frame.pack(fill="x", pady=(0,5))
        ctk.CTkLabel(header_frame, text=f"Step {step_id}.A: Define Region for Task", font=ctk.CTkFont(size=18, weight="bold")).pack(side="left", anchor="w")
        ctk.CTkLabel(page_frame, text=f"Task: \"{step_desc}\"", wraplength=self.winfo_width()-20, justify="left", font=ctk.CTkFont(size=14)).pack(anchor="w", pady=(0,10), fill="x")

        self.region_step_context_display_label = ctk.CTkLabel(page_frame, text="Loading screen context...", fg_color=("gray90", "gray25"), corner_radius=6)
        self.region_step_context_display_label.pack(fill="both", expand=True, pady=(0,10))

        overlay_to_draw = self.current_step_region_coords if self.current_step_region_defined_for_pg else self._temp_suggested_region_coords
        overlay_color = SELECTED_CANDIDATE_BOX_COLOR if self.current_step_region_defined_for_pg and self.current_step_region_coords else "orange"
        self.display_current_full_context_with_optional_overlay(
            label_widget=self.region_step_context_display_label,
            overlay_box=[overlay_to_draw['x'],overlay_to_draw['y'],overlay_to_draw['width'],overlay_to_draw['height']] if overlay_to_draw else None,
            box_color=overlay_color
        )

        controls_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); controls_frame.pack(fill="x", pady=(5,10))
        self.btn_ai_suggest_region = ctk.CTkButton(controls_frame, text="AI Suggest Region", command=self._handle_ai_suggest_region_threaded, width=160)
        self.btn_ai_suggest_region.pack(side="left", padx=(0,10))
        self.btn_draw_region_manually = ctk.CTkButton(controls_frame, text="Draw/Adjust Manually", command=self._handle_draw_region_manually, width=180)
        self.btn_draw_region_manually.pack(side="left", padx=5)

        name_frame = ctk.CTkFrame(controls_frame, fg_color="transparent"); name_frame.pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(name_frame, text="Region Name:").pack(side="left")
        self.current_step_region_name_entry = ctk.CTkEntry(name_frame, placeholder_text=f"e.g., step{step_id}_target_area")
        self.current_step_region_name_entry.pack(side="left", fill="x", expand=True)
        if self.current_step_region_name:
            self.current_step_region_name_entry.insert(0, self.current_step_region_name)
        self.current_step_region_name_entry.bind("<KeyRelease>", lambda e: self._update_navigation_buttons_state())

        self._update_navigation_buttons_state()
        logger.debug(f"Page Step Define Region UI setup for step {step_id}.")

    def display_current_full_context_with_optional_overlay(self, label_widget: ctk.CTkLabel, overlay_box: Optional[List[int]] = None, box_color="red"):
        if not label_widget or not label_widget.winfo_exists(): return
        if not self.current_full_context_pil: label_widget.configure(text="No screen context image.", image=None); return
        img_display = self.current_full_context_pil.copy()
        if overlay_box and len(overlay_box) == 4:
            try:
                draw = ImageDraw.Draw(img_display, "RGBA"); x,y,w,h = overlay_box; fill = box_color + "50" if box_color!=SELECTED_CANDIDATE_BOX_COLOR else None
                draw.rectangle([x,y,x+w,y+h], outline=box_color, width=3, fill=fill)
                if box_color == SELECTED_CANDIDATE_BOX_COLOR: cx,cy=x+w//2,y+h//2; draw.line([(cx-6,cy),(cx+6,cy)],fill=box_color,width=2); draw.line([(cx,cy-6),(cx,cy+6)],fill=box_color,width=2)
            except Exception as e: logger.error(f"Error drawing overlay {overlay_box}: {e}")
        max_w,max_h = WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH,WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT; thumb = img_display.copy(); thumb.thumbnail((max_w,max_h), Image.Resampling.LANCZOS); dw,dh=thumb.size
        ctk_img = ctk.CTkImage(light_image=thumb,dark_image=thumb,size=(dw,dh)); label_widget.configure(image=ctk_img,text="",width=dw,height=dh)

    def _handle_ai_suggest_region_threaded(self):
        if not self.current_plan_step_data: return
        logger.info(f"User req AI region suggestion for step: {self.current_plan_step_data.get('description')}")
        self._show_loading_overlay("AI suggesting region...")
        self.btn_ai_suggest_region.configure(state="disabled"); self.btn_draw_region_manually.configure(state="disabled")

        thread = threading.Thread(target=self._perform_ai_suggest_region_in_thread, args=(self.current_plan_step_data,))
        thread.daemon = True
        thread.start()

    def _perform_ai_suggest_region_in_thread(self, plan_step_data_for_thread: IntermediatePlanStep):
        suggestion = None; error = None
        try:
            suggestion = self.profile_generator.suggest_region_for_step(plan_step_data_for_thread)
        except Exception as e:
            logger.error(f"Exception in AI suggest region thread: {e}", exc_info=True)
            error = e
        self.after(0, self._handle_ai_suggest_region_result, suggestion, error)

    def _handle_ai_suggest_region_result(self, suggestion: Optional[Dict[str,Any]], error: Optional[Exception]):
        self._hide_loading_overlay()
        self.btn_ai_suggest_region.configure(state="normal"); self.btn_draw_region_manually.configure(state="normal")
        if error:
            messagebox.showerror("AI Error", f"Error during AI region suggestion: {error}", parent=self)
            self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label)
            return

        if suggestion and suggestion.get("box"):
            box = suggestion["box"]; self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label, box, "orange")
            name_hint = suggestion.get("suggested_region_name_hint", f"step{self.current_plan_step_data.get('step_id','X')}_ai_region")
            self.current_step_region_name_entry.delete(0, tk.END); self.current_step_region_name_entry.insert(0, name_hint)
            self._temp_suggested_region_coords = {"x": box[0], "y": box[1], "width": box[2], "height": box[3]}
            self.current_step_region_coords = self._temp_suggested_region_coords
            self.current_step_region_name = name_hint
            self.current_step_region_defined_for_pg = False
            messagebox.showinfo("AI Suggestion", f"AI suggests highlighted region (named '{name_hint}').\nReasoning: {suggestion.get('reasoning', 'N/A')}\nAdjust name if needed, or draw manually, then 'Confirm Region'.", parent=self)
        else:
            self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label)
            messagebox.showwarning("AI Suggestion Failed", "AI could not suggest a region. Please define it manually.", parent=self)
        self._update_navigation_buttons_state()

    def _handle_draw_region_manually(self):
        if not self.current_plan_step_data: return
        logger.info(f"User opted to draw region manually for: {self.current_plan_step_data.get('description')}")
        self.attributes("-alpha", 0.0); self.lower(); self.update_idletasks(); time.sleep(0.2)
        capture_pil_for_selector = self.current_full_context_pil
        if not capture_pil_for_selector:
            temp_screen_np = self.capture_engine.capture_region({"name":"temp_fullscreen_selector", "x":0,"y":0,"width":self.winfo_screenwidth(), "height":self.winfo_screenheight()})
            capture_pil_for_selector = Image.fromarray(cv2.cvtColor(temp_screen_np, cv2.COLOR_BGR2RGB)) if temp_screen_np is not None else None
        self.attributes("-alpha", 1.0); self.lift(); self.focus_set()
        if not capture_pil_for_selector: messagebox.showerror("Capture Error", "Failed to get screen image for manual region selection.", parent=self); return

        temp_cm = ConfigManager(None, create_if_missing=True)
        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1)
        initial_name_for_selector = self.current_step_region_name_entry.get().strip() or \
                                  self.current_step_region_name or \
                                  (self._temp_suggested_region_coords and self.current_plan_step_data.get('suggested_region_name_hint')) or \
                                  f"step{step_id}_manual_region"

        initial_coords_for_selector = self.current_step_region_coords or self._temp_suggested_region_coords or copy.deepcopy(DEFAULT_REGION_STRUCTURE_PG)
        existing_data_for_selector = {"name": initial_name_for_selector, **initial_coords_for_selector}
        for k_coord, def_coord in DEFAULT_REGION_STRUCTURE_PG.items():
            if k_coord in ["x", "y", "width", "height"]: existing_data_for_selector.setdefault(k_coord, def_coord)

        selector = RegionSelectorWindow(master=self, config_manager_context=temp_cm, existing_region_data=existing_data_for_selector, direct_image_input_pil=capture_pil_for_selector)
        self.wait_window(selector)
        if hasattr(selector, 'saved_region_info') and selector.saved_region_info:
            cr = selector.saved_region_info
            self.current_step_region_name = cr["name"]
            self.current_step_region_coords = {k: cr[k] for k in ["x","y","width","height"]}
            self.current_step_region_defined_for_pg = False
            self.current_step_region_name_entry.delete(0, tk.END); self.current_step_region_name_entry.insert(0, self.current_step_region_name)
            box_to_draw = [self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']]
            self.display_current_full_context_with_optional_overlay(self.region_step_context_display_label, box_to_draw, SELECTED_CANDIDATE_BOX_COLOR)
            logger.info(f"User manually defined/confirmed region '{self.current_step_region_name}' at {self.current_step_region_coords}")
        else: logger.info("Manual region definition cancelled or no region saved.")
        self._update_navigation_buttons_state()

    def _confirm_and_add_current_step_region(self) -> bool:
        region_name_from_ui = self.current_step_region_name_entry.get().strip()
        if not region_name_from_ui: messagebox.showerror("Input Error", "Region Name cannot be empty.", parent=self); self.current_step_region_name_entry.focus(); return False
        if not self.current_step_region_coords: messagebox.showerror("Error", "No region coordinates defined/confirmed for this step.", parent=self); return False

        self.current_step_region_name = region_name_from_ui

        existing_regions_in_draft = self.profile_generator.generated_profile_data.get("regions", [])
        if any(r.get("name") == self.current_step_region_name for r in existing_regions_in_draft):
            if not messagebox.askyesno("Name Conflict", f"A region named '{self.current_step_region_name}' already exists in the profile being generated. Its definition will be updated with the current coordinates if you proceed. Continue?", parent=self):
                self.current_step_region_name_entry.focus(); return False
            else:
                self.profile_generator.generated_profile_data["regions"] = [r for r in existing_regions_in_draft if r.get("name") != self.current_step_region_name]

        step_desc = self.current_plan_step_data.get('description', 'N/A') if self.current_plan_step_data else 'N/A'
        region_data_to_add_to_pg = {"name": self.current_step_region_name, **self.current_step_region_coords, "comment": f"For AI Gen Step: {step_desc}"}

        if self.profile_generator.add_region_definition(region_data_to_add_to_pg):
            self.current_step_region_defined_for_pg = True
            if self.current_full_context_np is not None and self.current_step_region_coords:
                x,y,w,h = self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']
                img_h_full, img_w_full = self.current_full_context_np.shape[:2]
                x_clamped = max(0, x); y_clamped = max(0, y)
                x2_clamped = min(img_w_full, x + w); y2_clamped = min(img_h_full, y + h)
                w_clamped = x2_clamped - x_clamped; h_clamped = y2_clamped - y_clamped
                if w_clamped > 0 and h_clamped > 0:
                    self.current_step_region_image_np = self.current_full_context_np[y_clamped:y2_clamped, x_clamped:x2_clamped]
                    self.current_step_region_image_pil_for_display = Image.fromarray(cv2.cvtColor(self.current_step_region_image_np, cv2.COLOR_BGR2RGB))
                    logger.info(f"Cropped region image '{self.current_step_region_name}' (shape: {self.current_step_region_image_np.shape}) set for logic definition step.")
                else:
                    self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
                    logger.error(f"Failed to crop valid region image for '{self.current_step_region_name}'. Coords: {self.current_step_region_coords}, Clamped: {w_clamped}x{h_clamped}")
                    messagebox.showerror("Crop Error", "Defined region resulted in invalid crop.", parent=self); return False
            else:
                self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
                logger.warning("No full context image to crop from for current step's region.")
            self._temp_suggested_region_coords = None; return True
        return False

    def _setup_page_final_review_save(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent"); page_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(page_frame, text="AI Profile Creator: Final Review & Save Profile", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0,15), anchor="w")
        profile_summary_textbox = ctk.CTkTextbox(page_frame, height=450, wrap="word", state="disabled", font=ctk.CTkFont(family="Courier New", size=11)); profile_summary_textbox.pack(fill="both", expand=True, pady=(0,10))
        data = self.profile_generator.get_generated_profile_data()
        if self.user_goal_text: data["profile_description"] = f"AI-Generated for goal: {self.user_goal_text[:120]}"

        try:
            text = json.dumps(data, indent=2)
            profile_summary_textbox.configure(state="normal")
            profile_summary_textbox.delete("0.0", "end")
            profile_summary_textbox.insert("0.0", text)
            profile_summary_textbox.configure(state="disabled")
        except Exception as e:
            profile_summary_textbox.configure(state="normal")
            profile_summary_textbox.delete("0.0", "end")
            profile_summary_textbox.insert("0.0", f"Error displaying profile: {e}")
            profile_summary_textbox.configure(state="disabled")

        name_frame = ctk.CTkFrame(page_frame, fg_color="transparent"); name_frame.pack(fill="x", pady=(10,5))
        ctk.CTkLabel(name_frame, text="Profile Filename:").pack(side="left", padx=(0,5))
        self.profile_filename_entry = ctk.CTkEntry(name_frame, placeholder_text=self.generated_profile_name_base); self.profile_filename_entry.pack(side="left", expand=True, fill="x"); self.profile_filename_entry.insert(0, self.generated_profile_name_base)
        logger.debug("Page Final Review UI setup.")

    def _on_close_wizard(self, event=None, was_saved=False):
        if not was_saved and messagebox.askokcancel("Cancel Profile Generation?", "Discard this profile and close wizard?", parent=self, icon=messagebox.WARNING):
            logger.info("AI Profile Wizard cancelled (unsaved).")
            self.user_cancelled_wizard = True
            self.destroy()
        elif was_saved:
            logger.info("AI Profile Wizard closing (saved).")
            self.destroy()

    def _display_current_step_region_image_with_candidates(self, candidate_boxes: Optional[List[Dict[str,Any]]] = None, selected_box_idx: Optional[int] = None):
        if not hasattr(self, 'step_logic_region_image_label') or not self.step_logic_region_image_label.winfo_exists(): return
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
                    try:
                        draw.text((text_x-1,text_y-1),label_text,font=self.overlay_font,fill="white")
                        draw.text((text_x+1,text_y-1),label_text,font=self.overlay_font,fill="white")
                        draw.text((text_x-1,text_y+1),label_text,font=self.overlay_font,fill="white")
                        draw.text((text_x+1,text_y+1),label_text,font=self.overlay_font,fill="white")
                        draw.text((text_x,text_y),label_text,font=self.overlay_font,fill=color)
                    except Exception: draw.text((text_x,text_y),label_text,fill=color)
        max_w,max_h = WIZARD_SCREENSHOT_PREVIEW_MAX_WIDTH-50, WIZARD_SCREENSHOT_PREVIEW_MAX_HEIGHT-50; thumb = img_pil_to_draw_on.copy(); thumb.thumbnail((max_w,max_h), Image.Resampling.LANCZOS); dw,dh=thumb.size
        ctk_img = ctk.CTkImage(light_image=thumb,dark_image=thumb,size=(dw,dh)); self.step_logic_region_image_label.configure(image=ctk_img,text="",width=dw,height=dh)
        self.step_logic_region_image_label.photo_image_scale_factor_x = self.current_step_region_image_pil_for_display.width / float(dw) if dw > 0 else 1.0
        self.step_logic_region_image_label.photo_image_scale_factor_y = self.current_step_region_image_pil_for_display.height / float(dh) if dh > 0 else 1.0

    def _on_region_image_click_for_element_selection(self, event):
        if not self.ui_refined_element_candidates or not hasattr(self.step_logic_region_image_label, 'photo_image_scale_factor_x'): return
        scale_x = getattr(self.step_logic_region_image_label, 'photo_image_scale_factor_x', 1.0)
        scale_y = getattr(self.step_logic_region_image_label, 'photo_image_scale_factor_y', 1.0)
        click_x_orig, click_y_orig = int(event.x * scale_x), int(event.y * scale_y)

        newly_selected_idx = next((i for i,c in enumerate(self.ui_refined_element_candidates) if c.get("box") and (c["box"][0]<=click_x_orig<c["box"][0]+c["box"][2]) and (c["box"][1]<=click_y_orig<c["box"][1]+c["box"][3])), None)

        if newly_selected_idx is not None and newly_selected_idx != self.ui_selected_candidate_box_index:
            self.ui_selected_candidate_box_index = newly_selected_idx
            self._display_current_step_region_image_with_candidates(self.ui_refined_element_candidates, self.ui_selected_candidate_box_index)
            self._update_action_params_with_selected_element()
        elif newly_selected_idx is None and self.ui_selected_candidate_box_index is not None:
            self.ui_selected_candidate_box_index = None
            self._display_current_step_region_image_with_candidates(self.ui_refined_element_candidates, None)
            self._clear_action_target_params()

    def _update_action_params_with_selected_element(self):
        if self.ui_selected_candidate_box_index is None or not self.ui_refined_element_candidates or self.ui_selected_candidate_box_index >= len(self.ui_refined_element_candidates):
            self.ui_confirmed_element_for_action = None; return

        sel_cand = self.ui_refined_element_candidates[self.ui_selected_candidate_box_index]
        self.ui_confirmed_element_for_action = {
            "value": { "box": sel_cand["box"], "found": True, "element_label": sel_cand.get("label_suggestion", self.ui_element_to_refine_desc or "AI Element")},
            "_source_region_for_capture_": self.current_step_region_name
        }
        logger.info(f"Element confirmed for action: Label='{self.ui_confirmed_element_for_action['value']['element_label']}', Box={self.ui_confirmed_element_for_action['value']['box']} in region '{self.current_step_region_name}'")

        act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
        if act_type_var and isinstance(act_type_var, tk.StringVar):
            act_type_var.set("click")
            self._on_wizard_logic_type_change("action", "click")
            self.after(50, self._set_click_action_params_for_selected_element)

    def _set_click_action_params_for_selected_element(self):
        rel_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var")
        gem_var_entry = self.step_logic_detail_widgets.get("step_act_gemini_element_variable")

        if rel_var and isinstance(rel_var, tk.StringVar):
            rel_var.set("center_of_gemini_element")
            tr_pdef = next((p for p in UI_PARAM_CONFIG["actions"]["click"] if p["id"]=="target_relation"),None)
            if tr_pdef: self._update_step_logic_conditional_visibility(tr_pdef, "center_of_gemini_element")

        if gem_var_entry and isinstance(gem_var_entry,ctk.CTkEntry):
            gem_var_entry.delete(0,tk.END)
            gem_var_entry.insert(0, self._ui_current_step_temp_var_name or "_wizard_sel_elem_")
        logger.debug(f"Wizard: Click action UI params set for visually selected element (var: {self._ui_current_step_temp_var_name}).")

    def _clear_action_target_params(self):
        self.ui_confirmed_element_for_action = None
        act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
        if act_type_var and isinstance(act_type_var, tk.StringVar) and act_type_var.get() == "click":
            rel_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var")
            gem_var_entry = self.step_logic_detail_widgets.get("step_act_gemini_element_variable")
            if rel_var: rel_var.set("center_of_region")
            if gem_var_entry and isinstance(gem_var_entry,ctk.CTkEntry): gem_var_entry.delete(0,tk.END)

            tr_pdef = next((p for p in UI_PARAM_CONFIG["actions"]["click"] if p["id"]=="target_relation"),None)
            if tr_pdef: self._update_step_logic_conditional_visibility(tr_pdef, "center_of_region")
        logger.debug("Cleared action target parameters in UI after deselecting element.")

    def _attempt_set_template_name_in_ui(self, template_name_to_set: str):
        widget_key="step_cond_template_name"; tk_var=self.step_logic_optionmenu_vars.get(f"{widget_key}_var"); widget=self.step_logic_detail_widgets.get(widget_key)
        if tk_var and isinstance(tk_var,tk.StringVar) and widget and isinstance(widget,ctk.CTkOptionMenu):
            new_opts=[""]+[t.get("name","") for t in self.profile_generator.generated_profile_data.get("templates",[]) if t.get("name")]
            widget.configure(values=new_opts)
            if template_name_to_set in new_opts: tk_var.set(template_name_to_set)
            else: logger.warning(f"Newly added template '{template_name_to_set}' not found in dropdown options after repopulating. Options: {new_opts}")
        else: logger.warning(f"Could not find or set template_name dropdown for '{template_name_to_set}'.")

    def _set_click_action_params_for_template(self, template_name: str):
        target_relation_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var")
        if target_relation_var and isinstance(target_relation_var, tk.StringVar):
            target_relation_var.set("center_of_last_match")
            tr_pdef=next((p for p in UI_PARAM_CONFIG.get("actions",{}).get("click",[]) if p["id"]=="target_relation"),None)
            if tr_pdef: self._update_step_logic_conditional_visibility(tr_pdef,"center_of_last_match")
            logger.info(f"Action UI updated to target 'center_of_last_match' for template '{template_name}'.")
        else: logger.warning("Wizard: Could not find target_relation_var for click action to set for template.")
        gem_var_entry=self.step_logic_detail_widgets.get("step_act_gemini_element_variable");
        if gem_var_entry and isinstance(gem_var_entry,ctk.CTkEntry): gem_var_entry.delete(0,tk.END)
        self.ui_confirmed_element_for_action=None

    def _get_parameters_from_ui_wizard_scoped(self, param_group_key: str, item_subtype: str, widget_prefix: str) -> Optional[Dict[str, Any]]:
        params: Dict[str,Any]={"type":item_subtype}; all_ok=True; param_defs=UI_PARAM_CONFIG.get(param_group_key,{}).get(item_subtype,[])
        if not param_defs and item_subtype!="always_true": return params
        for p_def in param_defs:
            p_id,lbl_err,target_type,def_val,is_req_def = p_def["id"],p_def["label"].rstrip(":"),p_def["type"],p_def.get("default",""),p_def.get("required",False)
            w_key=f"{widget_prefix}{p_id}"; widget=self.step_logic_detail_widgets.get(w_key); tk_var=self.step_logic_optionmenu_vars.get(f"{w_key}_var")

            is_vis = False
            if widget and widget.winfo_exists(): is_vis = widget.winfo_ismapped()
            elif tk_var and isinstance(tk_var, tk.BooleanVar) and widget and widget.winfo_exists():
                is_vis = widget.winfo_ismapped()

            eff_req = is_req_def and is_vis

            if not is_vis and not eff_req: continue

            if widget is None and not isinstance(tk_var, tk.BooleanVar):
                if eff_req: logger.error(f"Wizard GetParams: UI Widget for required parameter '{lbl_err}' (ID: {p_id}) not found."); all_ok=False
                params[p_id]=def_val; continue

            val_args={"required":eff_req,"allow_empty_string":p_def.get("allow_empty_string",target_type==str),"min_val":p_def.get("min_val"),"max_val":p_def.get("max_val")}
            val,valid = validate_and_get_widget_value(widget,tk_var,lbl_err,target_type,def_val,**val_args)

            if not valid: all_ok=False; val=def_val

            if isinstance(val, str) and val.startswith(USER_INPUT_PLACEHOLDER_PREFIX):
                if eff_req:
                    messagebox.showerror("Input Required", f"Please provide a value for '{lbl_err}'. The placeholder '{val}' is not a valid input.", parent=self)
                    all_ok = False; val = def_val
                elif p_def.get("allow_empty_string", False): val = ""

            if target_type=="list_str_csv": params[p_id]=[s.strip() for s in val.split(',') if isinstance(val,str) and val.strip()] if isinstance(val,str) and val.strip() else ([] if not def_val or not isinstance(def_val,list) else def_val)
            else: params[p_id]=val

            if p_id=="template_name" and param_group_key=="conditions":
                s_tpl_name=val; params["template_filename"] = ""
                if s_tpl_name:
                    fname=next((t.get("filename","") for t in self.profile_generator.generated_profile_data.get("templates",[]) if t.get("name")==s_tpl_name),"")
                    params["template_filename"]=fname
                    if not fname and eff_req:
                        messagebox.showerror("Internal Error",f"Filename for selected template '{s_tpl_name}' could not be found in profile draft.",parent=self)
                        all_ok=False
                elif eff_req:
                    messagebox.showerror("Input Error",f"'{lbl_err}' (Template Name) is required for template_match_found condition.",parent=self)
                    all_ok=False
                if "template_name" in params: del params["template_name"]

        if item_subtype=="always_true" and param_group_key=="conditions":
            region_pdef_always_true = next((pd for pd in UI_PARAM_CONFIG.get("conditions",{}).get("always_true",[]) if pd["id"]=="region"),None)
            if region_pdef_always_true:
                region_val_at, _ = validate_and_get_widget_value(
                    self.step_logic_detail_widgets.get(f"{widget_prefix}region"),
                    self.step_logic_optionmenu_vars.get(f"{widget_prefix}region_var"),
                    "Region (for always_true)", str, "", required=False
                )
                if region_val_at: params["region"] = region_val_at

        return params if all_ok else None

    def _get_current_step_logic_from_ui(self) -> Optional[Tuple[Dict[str,Any], Dict[str,Any]]]:
        log_prefix = f"PG.GetStepLogicUI (StepID: {self.current_plan_step_data.get('step_id') if self.current_plan_step_data else 'N/A'})"
        cond_type_var = self.step_logic_optionmenu_vars.get("step_cond_type_var"); act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
        if not cond_type_var or not act_type_var: logger.error(f"{log_prefix}: Crit err: Cond/Act type UI selectors MIA."); return None

        cond_type = cond_type_var.get(); act_type = act_type_var.get()
        condition_params = self._get_parameters_from_ui_wizard_scoped("conditions", cond_type, "step_cond_")
        if condition_params is None:
            logger.error(f"{log_prefix}: Validation failed for Condition parameters of type '{cond_type}'."); return None

        action_params = self._get_parameters_from_ui_wizard_scoped("actions", act_type, "step_act_")
        if action_params is None:
            logger.error(f"{log_prefix}: Validation failed for Action parameters of type '{act_type}'."); return None

        if self.ui_confirmed_element_for_action and \
           action_params.get("type") == "click" and \
           action_params.get("gemini_element_variable") == self._ui_current_step_temp_var_name:

            box_data = self.ui_confirmed_element_for_action["value"]["box"]
            source_region_name_for_conversion = self.ui_confirmed_element_for_action["_source_region_for_capture_"]
            source_region_config_from_draft = next((r_cfg for r_cfg in self.profile_generator.generated_profile_data.get("regions", []) if r_cfg.get("name") == source_region_name_for_conversion), None)

            if source_region_config_from_draft:
                abs_screen_region_x = source_region_config_from_draft.get('x', 0)
                abs_screen_region_y = source_region_config_from_draft.get('y', 0)
                click_target_relation_in_ui_var = self.step_logic_optionmenu_vars.get("step_act_target_relation_var")
                click_target_relation_in_ui = click_target_relation_in_ui_var.get() if click_target_relation_in_ui_var else "center_of_gemini_element"

                if "center" in click_target_relation_in_ui.lower():
                    abs_click_x = abs_screen_region_x + box_data[0] + (box_data[2] // 2)
                    abs_click_y = abs_screen_region_y + box_data[1] + (box_data[3] // 2)
                else: abs_click_x = abs_screen_region_x + box_data[0]; abs_click_y = abs_screen_region_y + box_data[1]

                action_params["target_relation"] = "absolute"
                action_params["x"] = str(abs_click_x)
                action_params["y"] = str(abs_click_y)
                action_params.pop("gemini_element_variable", None); action_params.pop("target_region", None)
                logger.info(f"{log_prefix}: Converted Gemini elem click (var: {self._ui_current_step_temp_var_name}) to absolute ({abs_click_x},{abs_click_y}).")
            else:
                logger.error(f"{log_prefix}: Cannot find src rgn '{source_region_name_for_conversion}' to convert Gemini click to absolute. Action may fail.");
                messagebox.showerror("Internal Error", f"Source region '{source_region_name_for_conversion}' (for element click) not found.", parent=self)
                return None

        return condition_params, action_params

    def _go_to_next_page(self):
        logger.debug(f"Next button clicked. Current page index: {self.current_page_index}")
        if self.current_page_index == PAGE_GOAL_INPUT:
            self.user_goal_text = self.goal_textbox.get("0.0", "end-1c").strip();
            if not self.user_goal_text: messagebox.showerror("Input Error", "Please describe goal.", parent=self); return
            self._show_loading_overlay("AI generating plan..."); self.btn_next.configure(state="disabled")
            thread = threading.Thread(target=self._perform_generate_plan_in_thread, args=(self.user_goal_text, self.current_full_context_np))
            thread.daemon = True; thread.start()
        elif self.current_page_index == PAGE_PLAN_REVIEW:
            if not self.intermediate_plan: messagebox.showerror("Error", "No plan available to proceed.", parent=self); return
            if self.profile_generator.advance_to_next_plan_step():
                self.current_page_index = PAGE_STEP_DEFINE_REGION; self._reset_and_load_step_state()
            else: messagebox.showerror("Error", "Plan empty or issue advancing.", parent=self); self.current_page_index = PAGE_GOAL_INPUT
            self._show_current_page()
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            if self._confirm_and_add_current_step_region(): self.current_page_index = PAGE_STEP_DEFINE_LOGIC; self._show_current_page()
            else: return
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC:
            logic_tuple = self._get_current_step_logic_from_ui()
            if logic_tuple:
                confirmed_condition, confirmed_action = logic_tuple; current_step = self.profile_generator.get_current_plan_step()
                if current_step and self.current_step_region_name:
                    base_rule_name = f"Rule_Step{current_step.get('step_id')}_{current_step.get('description', 'Task')[:15].replace(' ','_').replace("'", "")}"
                    rule_name_to_add = base_rule_name; count = 1
                    while any(r.get("name") == rule_name_to_add for r in self.profile_generator.generated_profile_data.get("rules",[])): rule_name_to_add = f"{base_rule_name}_{count}"; count += 1
                    rule_to_add = {"name": rule_name_to_add, "region": self.current_step_region_name, "condition": confirmed_condition, "action": confirmed_action, "comment": f"AI Gen for: {current_step.get('description')}"}
                    if self.profile_generator.add_rule_definition(rule_to_add): logger.info(f"Rule '{rule_name_to_add}' added for step {current_step.get('step_id')}.")
                    else: messagebox.showerror("Error", f"Failed to add rule for step {current_step.get('step_id')}.", parent=self); return
                else: messagebox.showerror("Internal Error", "Missing step data or region name when adding rule.", parent=self); return
                if self.profile_generator.advance_to_next_plan_step(): self.current_page_index = PAGE_STEP_DEFINE_REGION; self._reset_and_load_step_state()
                else: self.current_page_index = PAGE_FINAL_REVIEW_SAVE
                self._show_current_page()
            else: return
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE: self._save_generated_profile(); return

    def _perform_generate_plan_in_thread(self, user_goal: str, context_np: Optional[np.ndarray]):
        plan = None; error = None
        try: plan = self.strategy_planner.generate_intermediate_plan(user_goal, context_np)
        except Exception as e: logger.error(f"Exception in AI generate plan thread: {e}", exc_info=True); error = e
        self.after(0, self._handle_generate_plan_result, plan, error)

    def _handle_generate_plan_result(self, plan: Optional[IntermediatePlan], error: Optional[Exception]):
        self._hide_loading_overlay(); self.btn_next.configure(state="normal")
        if error: messagebox.showerror("AI Plan Error", f"Error during AI plan generation: {error}", parent=self); return
        self.intermediate_plan = plan
        if self.intermediate_plan and len(self.intermediate_plan) > 0:
            self.profile_generator.start_profile_generation(self.intermediate_plan, f"AI-Gen for: {self.user_goal_text[:70]}", initial_full_screen_context_np=self.current_full_context_np)
            self.current_page_index = PAGE_PLAN_REVIEW
        elif self.intermediate_plan is not None and len(self.intermediate_plan) == 0:
            messagebox.showinfo("AI Plan", "AI generated an empty plan. This might mean the goal was too vague or complex. You can refine your goal or proceed to build manually if desired (though the wizard will end after this if no steps).", parent=self)
            self.current_page_index = PAGE_PLAN_REVIEW
        else:
            messagebox.showerror("AI Plan Failed", "Could not generate a plan. Try rephrasing your goal or check application logs.", parent=self)

        self._reset_and_load_step_state()
        self._show_current_page()

    def _go_to_previous_page(self):
        logger.debug(f"Previous button clicked. Current page: {self.current_page_index}")
        pg_current_step_idx = self.profile_generator.current_plan_step_index

        if self.current_page_index == PAGE_PLAN_REVIEW:
            self.current_page_index = PAGE_GOAL_INPUT
            self.intermediate_plan = None; self.profile_generator.intermediate_plan = None
            self.profile_generator.current_plan_step_index = -1
        elif self.current_page_index == PAGE_STEP_DEFINE_REGION:
            if pg_current_step_idx == 0 :
                self.current_page_index = PAGE_PLAN_REVIEW
                self.profile_generator.current_plan_step_index = -1
            elif pg_current_step_idx > 0:
                self.profile_generator.current_plan_step_index -= 1
                self.current_page_index = PAGE_STEP_DEFINE_LOGIC
            else: self.current_page_index = PAGE_PLAN_REVIEW
        elif self.current_page_index == PAGE_STEP_DEFINE_LOGIC:
            self.current_page_index = PAGE_STEP_DEFINE_REGION
        elif self.current_page_index == PAGE_FINAL_REVIEW_SAVE:
            if self.intermediate_plan and len(self.intermediate_plan) > 0:
                if pg_current_step_idx >= len(self.intermediate_plan):
                    self.profile_generator.current_plan_step_index = len(self.intermediate_plan) - 1

                self.current_page_index = PAGE_STEP_DEFINE_LOGIC if self.profile_generator.current_plan_step_index >=0 else PAGE_PLAN_REVIEW
            else:
                self.current_page_index = PAGE_GOAL_INPUT

        self._reset_and_load_step_state()
        self._show_current_page()

    def _reset_and_load_step_state(self):
        self.ui_suggested_condition_for_step = None; self.ui_suggested_action_for_step = None
        self.ui_element_to_refine_desc = None; self.ui_refined_element_candidates = []
        self.ui_selected_candidate_box_index = None; self.ui_confirmed_element_for_action = None
        if hasattr(self, 'element_refine_entry') and self.element_refine_entry and self.element_refine_entry.winfo_exists():
            self.element_refine_entry.delete(0, tk.END)

        self.current_plan_step_data = self.profile_generator.get_current_plan_step()
        if not self.current_plan_step_data:
            self.current_step_region_name = None; self.current_step_region_coords = None
            self.current_step_region_defined_for_pg = False
            self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
            self._temp_suggested_region_coords = None
            logger.debug("Wizard: No current plan step. All step-specific state cleared.")
            return

        step_id_from_plan = self.current_plan_step_data.get("step_id", self.profile_generator.current_plan_step_index + 1)
        logger.info(f"Wizard: Loading state for Step ID {step_id_from_plan} into UI.")

        if self.current_step_region_name and self.current_step_region_coords:
            self.current_step_region_defined_for_pg = any(r.get("name") == self.current_step_region_name for r in self.profile_generator.generated_profile_data.get("regions",[]))
            if self.current_step_region_defined_for_pg:
                if self.current_full_context_np is not None:
                    x,y,w,h = self.current_step_region_coords['x'], self.current_step_region_coords['y'], self.current_step_region_coords['width'], self.current_step_region_coords['height']
                    img_h_f, img_w_f = self.current_full_context_np.shape[:2]; x_c,y_c=max(0,x),max(0,y); x2_c,y2_c=min(img_w_f,x+w),min(img_h_f,y+h); w_c,h_c=x2_c-x_c,y2_c-y_c
                    if w_c > 0 and h_c > 0:
                        self.current_step_region_image_np = self.current_full_context_np[y_c:y2_c, x_c:x2_c]
                        self.current_step_region_image_pil_for_display = Image.fromarray(cv2.cvtColor(self.current_step_region_image_np, cv2.COLOR_BGR2RGB))
                    else: self.current_step_region_image_np = self.current_step_region_image_pil_for_display = None
            else:
                self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
        else:
            self.current_step_region_defined_for_pg = False
            self.current_step_region_image_np = None; self.current_step_region_image_pil_for_display = None
            self._temp_suggested_region_coords = None

        potential_rule_name_prefix = f"Rule_Step{step_id_from_plan}"
        found_rule_for_step = next((r for r in self.profile_generator.generated_profile_data.get("rules",[]) if r.get("name","").startswith(potential_rule_name_prefix)), None)

        if found_rule_for_step:
            self.ui_suggested_condition_for_step = copy.deepcopy(found_rule_for_step.get("condition"))
            self.ui_suggested_action_for_step = copy.deepcopy(found_rule_for_step.get("action"))
            self.ui_element_to_refine_desc = self.ui_suggested_action_for_step.get("target_description") if self.ui_suggested_action_for_step else None
        else:
            self.ui_suggested_condition_for_step = None; self.ui_suggested_action_for_step = None
            self.ui_element_to_refine_desc = None
        logger.debug(f"Wizard: State loaded for step {step_id_from_plan}. Region '{self.current_step_region_name}' defined in PG: {self.current_step_region_defined_for_pg}. Rule logic loaded: {found_rule_for_step is not None}")

    def _setup_page_step_define_logic(self):
        page_frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")
        page_frame.pack(fill="both", expand=True, padx=5, pady=5)

        if not self.current_plan_step_data or not self.current_step_region_name or self.current_step_region_image_pil_for_display is None:
            ctk.CTkLabel(page_frame, text="Error: Critical data missing (step, region name, or region image).\nPlease go back to define the region for this task step first.", wraplength=self.winfo_width()-30, justify="left").pack(pady=20)
            self.btn_next.configure(state="disabled"); self._update_navigation_buttons_state(); return

        step_id = self.current_plan_step_data.get('step_id', self.profile_generator.current_plan_step_index + 1)
        step_desc = self.current_plan_step_data.get('description', 'N/A')
        self._ui_current_step_temp_var_name = f"_ai_gen_step{step_id}_elem"

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
        self.btn_refine_element = ctk.CTkButton(element_interaction_frame, text="AI Find Element", command=self._handle_ai_refine_element_threaded, width=120, state="disabled"); self.btn_refine_element.pack(side="left", padx=(0,5))
        self.btn_capture_template_for_step = ctk.CTkButton(element_interaction_frame, text="Use Template Instead", command=self._handle_capture_template_for_step, width=160, state="disabled"); self.btn_capture_template_for_step.pack(side="left")

        params_panel_outer = ctk.CTkFrame(main_logic_area, fg_color="transparent"); params_panel_outer.grid(row=0, column=1, sticky="nsew", padx=(5,0))
        params_panel_outer.grid_rowconfigure(0, weight=1); params_panel_outer.grid_columnconfigure(0, weight=1)
        self.params_panel_scrollable = ctk.CTkScrollableFrame(params_panel_outer, label_text="Configure Step Logic (AI Suggested / Manual)"); self.params_panel_scrollable.pack(fill="both", expand=True)
        self.params_panel_scrollable.grid_columnconfigure(1, weight=1)

        self.step_logic_condition_frame = ctk.CTkFrame(self.params_panel_scrollable, fg_color="transparent"); self.step_logic_condition_frame.pack(fill="x", pady=(5,15), padx=5); self.step_logic_condition_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.step_logic_condition_frame, text="STEP CONDITION:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))

        self.step_logic_action_frame = ctk.CTkFrame(self.params_panel_scrollable, fg_color="transparent"); self.step_logic_action_frame.pack(fill="x", pady=(10,5), padx=5); self.step_logic_action_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self.step_logic_action_frame, text="STEP ACTION:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,5))

        self._display_current_step_region_image_with_candidates()

        if self.ui_suggested_condition_for_step and self.ui_suggested_action_for_step:
            logger.debug(f"Logic Page: Using pre-loaded/existing logic for step {step_id}.")
            self._render_step_logic_editors(
                self.ui_suggested_condition_for_step,
                self.ui_suggested_action_for_step,
                self.ui_element_to_refine_desc
            )
        else:
            self.after(100, self._trigger_ai_logic_suggestion_for_step_threaded)

        self._update_navigation_buttons_state(); logger.debug(f"Page Step Define Logic UI setup for step {step_id}.")

    def _trigger_ai_logic_suggestion_for_step_threaded(self):
        if not self.current_plan_step_data or self.current_step_region_image_np is None or not self.current_step_region_name:
            logger.warning("Cannot trigger AI logic suggestion: missing step data, region image, or region name.")
            self._render_step_logic_editors(copy.deepcopy(DEFAULT_CONDITION_STRUCTURE_PG), copy.deepcopy(DEFAULT_ACTION_STRUCTURE_PG), None)
            return
        self._show_loading_overlay("AI suggesting logic..."); self.btn_refine_element.configure(state="disabled"); self.btn_capture_template_for_step.configure(state="disabled")
        thread = threading.Thread(target=self._perform_ai_logic_suggestion_in_thread, args=(self.current_plan_step_data, self.current_step_region_image_np, self.current_step_region_name))
        thread.daemon = True; thread.start()

    def _perform_ai_logic_suggestion_in_thread(self, plan_step_data: IntermediatePlanStep, region_image_np: np.ndarray, region_name: str):
        suggestion_result = None; error = None
        try: suggestion_result = self.profile_generator.suggest_logic_for_step(plan_step_data, region_image_np, region_name)
        except Exception as e: logger.error(f"Exception in AI logic suggestion thread: {e}", exc_info=True); error = e
        self.after(0, self._handle_ai_logic_suggestion_result, suggestion_result, error)

    def _handle_ai_logic_suggestion_result(self, suggestion_result: Optional[Dict[str, Any]], error: Optional[Exception]):
        self._hide_loading_overlay()
        s_cond, s_act, el_ref_desc = copy.deepcopy(DEFAULT_CONDITION_STRUCTURE_PG), copy.deepcopy(DEFAULT_ACTION_STRUCTURE_PG), None
        if error: messagebox.showerror("AI Error", f"Error during AI logic suggestion: {error}.\nUsing default condition/action.", parent=self)
        elif suggestion_result:
            s_cond = suggestion_result.get("suggested_condition", s_cond); s_act = suggestion_result.get("suggested_action", s_act)
            el_ref_desc = suggestion_result.get("element_to_refine_description")
            self.ui_suggested_condition_for_step = copy.deepcopy(s_cond); self.ui_suggested_action_for_step = copy.deepcopy(s_act); self.ui_element_to_refine_desc = el_ref_desc
            messagebox.showinfo("AI Logic Suggestion", f"AI suggested a condition of type '{s_cond.get('type')}' and action '{s_act.get('type')}'.\nReasoning: {suggestion_result.get('reasoning', 'N/A')}", parent=self)
        else: messagebox.showwarning("AI Suggestion Failed", "AI could not suggest logic for this step. Please configure manually or use defaults.", parent=self)
        self._render_step_logic_editors(s_cond, s_act, el_ref_desc)

    def _render_step_logic_editors(self, condition_data: Dict[str,Any], action_data: Dict[str,Any], element_to_refine_description: Optional[str]):
        cond_type = str(condition_data.get("type", "always_true")); cond_type_var = ctk.StringVar(value=cond_type)
        ctk.CTkLabel(self.step_logic_condition_frame, text="Type:").grid(row=1, column=0, sticky="w", padx=(0,5), pady=2)
        cond_menu = ctk.CTkOptionMenu(self.step_logic_condition_frame, variable=cond_type_var, values=CONDITION_TYPES, command=lambda choice: self._on_wizard_logic_type_change("condition", choice))
        cond_menu.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.step_logic_optionmenu_vars["step_cond_type_var"] = cond_type_var; self.step_logic_detail_widgets["step_cond_type"] = cond_menu
        self._render_dynamic_params_in_wizard_subframe("conditions", cond_type, condition_data, self.step_logic_condition_frame, 2, "step_cond_")

        act_type = str(action_data.get("type", "log_message")); act_type_var = ctk.StringVar(value=act_type)
        ctk.CTkLabel(self.step_logic_action_frame, text="Type:").grid(row=1, column=0, sticky="w", padx=(0,5), pady=2)
        act_menu = ctk.CTkOptionMenu(self.step_logic_action_frame, variable=act_type_var, values=ACTION_TYPES, command=lambda choice: self._on_wizard_logic_type_change("action", choice))
        act_menu.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.step_logic_optionmenu_vars["step_act_type_var"] = act_type_var; self.step_logic_detail_widgets["step_act_type"] = act_menu
        self._render_dynamic_params_in_wizard_subframe("actions", act_type, action_data, self.step_logic_action_frame, 2, "step_act_")

        self.ui_element_to_refine_desc = element_to_refine_description
        if element_to_refine_description and hasattr(self, 'element_refine_entry'):
            self.element_refine_entry.delete(0, tk.END); self.element_refine_entry.insert(0, element_to_refine_description)
            self.btn_refine_element.configure(state="normal")
        elif hasattr(self, 'element_refine_entry'): self.element_refine_entry.delete(0, tk.END); self.btn_refine_element.configure(state="disabled")

        self.btn_capture_template_for_step.configure(state="normal")

    def _on_wizard_logic_type_change(self, part_key: str, new_type: str):
        self.main_app_instance._set_dirty_status(True)
        logger.debug(f"Wizard: Logic part '{part_key}' type changed to '{new_type}'. Re-rendering params.")
        target_frame = self.step_logic_condition_frame if part_key == "condition" else self.step_logic_action_frame
        param_group_for_config = "conditions" if part_key == "condition" else "actions"
        widget_prefix = "step_cond_" if part_key == "condition" else "step_act_"
        default_data_for_new_type = {"type": new_type}; new_type_param_defs = UI_PARAM_CONFIG.get(param_group_for_config, {}).get(new_type, [])
        if part_key == "condition":
            region_widget = self.step_logic_detail_widgets.get(f"{widget_prefix}region"); region_var = self.step_logic_optionmenu_vars.get(f"{widget_prefix}region_var")
            if region_widget and region_var and isinstance(region_var, tk.StringVar):
                current_region_val = region_var.get()
                if current_region_val and any(pdef.get("id") == "region" for pdef in new_type_param_defs): default_data_for_new_type["region"] = current_region_val
        self._render_dynamic_params_in_wizard_subframe(param_group_for_config, new_type, default_data_for_new_type, target_frame, 2, widget_prefix)

    def _render_dynamic_params_in_wizard_subframe(self, param_group_key: str, item_subtype: str, data_source: Dict[str, Any], parent_frame: ctk.CTkFrame, start_row: int, widget_prefix: str):
        for child_widget in list(parent_frame.winfo_children()):
            grid_info = child_widget.grid_info()
            if grid_info and grid_info.get("row", -1) >= start_row:
                widget_key_to_pop = None
                for wk, w_instance in self.step_logic_detail_widgets.items():
                    if w_instance == child_widget and wk.startswith(widget_prefix): widget_key_to_pop = wk; break
                if widget_key_to_pop: self.step_logic_detail_widgets.pop(widget_key_to_pop, None); self.step_logic_optionmenu_vars.pop(f"{widget_key_to_pop}_var", None)
                child_widget.destroy()

        self.step_logic_param_widgets_and_defs.clear(); self.step_logic_controlling_widgets.clear(); self.step_logic_widget_prefix = widget_prefix
        param_defs_for_subtype = UI_PARAM_CONFIG.get(param_group_key, {}).get(item_subtype, [])
        current_r = start_row
        if not param_defs_for_subtype and item_subtype not in ["always_true"]: ctk.CTkLabel(parent_frame,text=f"No params for '{item_subtype}'.", text_color="gray").grid(row=current_r,column=0,columnspan=2); return

        for p_def in param_defs_for_subtype:
            p_id, lbl_txt, w_type, d_type, def_val = p_def["id"], p_def["label"], p_def["widget"], p_def["type"], p_def.get("default", "")
            current_value_for_param = data_source.get(p_id, def_val); widget_full_key = f"{widget_prefix}{p_id}"
            label_widget = ctk.CTkLabel(parent_frame, text=lbl_txt); created_widget_instance = None
            if w_type == "entry":
                entry = ctk.CTkEntry(parent_frame, placeholder_text=str(p_def.get("placeholder",""))); display_value = ", ".join(map(str,current_value_for_param)) if d_type == "list_str_csv" and isinstance(current_value_for_param, list) else str(current_value_for_param); entry.insert(0, display_value); entry.bind("<KeyRelease>", lambda e: self.main_app_instance._set_dirty_status(True)); created_widget_instance = entry
            elif w_type == "textbox":
                textbox = ctk.CTkTextbox(parent_frame, height=p_def.get("height", 60), wrap="word"); textbox.insert("0.0", str(current_value_for_param)); textbox.bind("<FocusOut>", lambda e: self.main_app_instance._set_dirty_status(True)); created_widget_instance = textbox
            elif w_type.startswith("optionmenu"):
                options_list = []; src_key = p_def.get("options_source") if w_type == "optionmenu_dynamic" else p_def.get("options_const_key")
                if w_type == "optionmenu_dynamic" and src_key == "regions": options_list = [""] + [r.get("name","") for r in self.profile_generator.generated_profile_data.get("regions",[]) if r.get("name")]
                elif w_type == "optionmenu_dynamic" and src_key == "templates": options_list = [""] + [t.get("name","") for t in self.profile_generator.generated_profile_data.get("templates",[]) if t.get("name")]
                elif w_type == "optionmenu_static" and src_key: options_list = OPTIONS_CONST_MAP.get(src_key, [])
                if not options_list: options_list = [str(def_val)] if str(def_val) else [""]
                str_current_val = str(current_value_for_param); final_current_val_for_menu = str_current_val if str_current_val in options_list else (str(def_val) if str(def_val) in options_list else (options_list[0] if options_list else ""))
                tk_var = ctk.StringVar(value=final_current_val_for_menu); option_menu = ctk.CTkOptionMenu(parent_frame, variable=tk_var, values=options_list, command=lambda choice, p=p_def: self._update_step_logic_conditional_visibility(p, choice)); self.step_logic_optionmenu_vars[f"{widget_full_key}_var"] = tk_var; created_widget_instance = option_menu
                if any(other_pdef.get("condition_show",{}).get("field") == p_id for other_pdef in param_defs_for_subtype if other_pdef.get("condition_show")): self.step_logic_controlling_widgets[p_id] = created_widget_instance
            elif w_type == "checkbox":
                tk_bool_var = tk.BooleanVar(value=bool(current_value_for_param))
                checkbox = ctk.CTkCheckBox(parent_frame, text="", variable=tk_bool_var, command=lambda p=p_def, v=tk_bool_var: self._update_step_logic_conditional_visibility(p, v.get()))
                self.step_logic_optionmenu_vars[f"{widget_full_key}_var"] = tk_bool_var
                created_widget_instance = checkbox
                if any(other_pdef.get("condition_show",{}).get("field") == p_id for other_pdef in param_defs_for_subtype if other_pdef.get("condition_show")): self.step_logic_controlling_widgets[p_id] = created_widget_instance

            if created_widget_instance:
                self.step_logic_detail_widgets[widget_full_key] = created_widget_instance
                label_widget.grid(row=current_r, column=0, padx=(0,5), pady=2, sticky="nw" if w_type=="textbox" else "w")
                created_widget_instance.grid(row=current_r, column=1, padx=5, pady=2, sticky="ew")
                self.step_logic_param_widgets_and_defs.append({"widget": created_widget_instance, "label_widget": label_widget, "param_def": p_def}); current_r += 1
            else: label_widget.destroy()
        self._apply_step_logic_conditional_visibility()

    def _update_step_logic_conditional_visibility(self, changed_param_def_controller: Dict[str,Any], new_value_of_controller: Any):
        self.main_app_instance._set_dirty_status(True)
        logger.debug(f"Wizard: Controller '{changed_param_def_controller.get('id')}' for prefix '{self.step_logic_widget_prefix}' changed to '{new_value_of_controller}'. Re-evaluating visibility.")
        self._apply_step_logic_conditional_visibility()

    def _apply_step_logic_conditional_visibility(self):
        if not hasattr(self, 'step_logic_param_widgets_and_defs') or not hasattr(self, 'step_logic_controlling_widgets') or not hasattr(self, 'step_logic_widget_prefix'): return
        for item in self.step_logic_param_widgets_and_defs:
            widget_instance, label_widget_instance, param_definition = item["widget"], item["label_widget"], item["param_def"]
            visibility_config = param_definition.get("condition_show"); should_be_visible = True
            if visibility_config:
                controlling_field_id = visibility_config.get("field"); expected_values_for_visibility = visibility_config.get("values", [])
                controller_widget_instance = self.step_logic_controlling_widgets.get(controlling_field_id); current_controller_value = None
                if isinstance(controller_widget_instance, ctk.CTkOptionMenu): tk_var_for_controller = self.step_logic_optionmenu_vars.get(f"{self.step_logic_widget_prefix}{controlling_field_id}_var"); current_controller_value = tk_var_for_controller.get() if tk_var_for_controller else None
                elif isinstance(controller_widget_instance, ctk.CTkCheckBox): tk_var_for_controller = self.step_logic_optionmenu_vars.get(f"{self.step_logic_widget_prefix}{controlling_field_id}_var"); current_controller_value = tk_var_for_controller.get() if tk_var_for_controller else None; expected_values_for_visibility = [bool(v) for v in expected_values_for_visibility if isinstance(v,(str,int,bool))]
                elif isinstance(controller_widget_instance, ctk.CTkEntry): current_controller_value = controller_widget_instance.get()
                if current_controller_value is None or current_controller_value not in expected_values_for_visibility: should_be_visible = False
            if widget_instance and widget_instance.winfo_exists():
                is_currently_mapped = widget_instance.winfo_ismapped()
                if should_be_visible and not is_currently_mapped: widget_instance.grid(); _ = label_widget_instance.grid() if label_widget_instance and label_widget_instance.winfo_exists() and not label_widget_instance.winfo_ismapped() else None
                elif not should_be_visible and is_currently_mapped: widget_instance.grid_remove(); _ = label_widget_instance.grid_remove() if label_widget_instance and label_widget_instance.winfo_exists() and label_widget_instance.winfo_ismapped() else None

    def _handle_ai_refine_element_threaded(self):
        element_desc_to_refine = self.element_refine_entry.get().strip()
        if not element_desc_to_refine: messagebox.showwarning("Input Missing", "Enter element description to find.", parent=self); return
        if not self.current_step_region_image_np or not self.current_step_region_name: messagebox.showerror("Error", "Region image or name is missing for refinement.", parent=self); return
        self.ui_element_to_refine_desc = element_desc_to_refine
        self._show_loading_overlay(f"AI refining '{element_desc_to_refine[:30]}...'"); self.btn_refine_element.configure(state="disabled")
        thread = threading.Thread(target=self._perform_ai_refine_element_in_thread, args=(element_desc_to_refine, self.current_step_region_image_np, self.current_step_region_name))
        thread.daemon = True; thread.start()

    def _perform_ai_refine_element_in_thread(self, element_desc: str, region_image_np: np.ndarray, region_name: str):
        candidates = None; error = None
        try: candidates = self.profile_generator.refine_element_location(element_desc, region_image_np, region_name, task_rule_name_for_log="AI_Gen_Wizard_Refine")
        except Exception as e: logger.error(f"Exception in AI refine element thread: {e}", exc_info=True); error = e
        self.after(0, self._handle_ai_refine_element_result, candidates, error)

    def _handle_ai_refine_element_result(self, candidates: Optional[List[Dict[str, Any]]], error: Optional[Exception]):
        self._hide_loading_overlay(); self.btn_refine_element.configure(state="normal" if self.element_refine_entry.get().strip() else "disabled")
        if error: messagebox.showerror("AI Error", f"Error during AI element refinement: {error}", parent=self); return
        self.ui_refined_element_candidates = candidates if candidates else []; self.ui_selected_candidate_box_index = None; self._clear_action_target_params()
        if self.ui_refined_element_candidates: self._display_current_step_region_image_with_candidates(self.ui_refined_element_candidates, None); messagebox.showinfo("AI Element Candidates", f"AI found {len(self.ui_refined_element_candidates)} candidate(s). Click one on the image to select for action.", parent=self)
        else: self._display_current_step_region_image_with_candidates(None, None); messagebox.showwarning("AI Refinement", "AI could not find matching elements, or refinement failed.", parent=self)

    def _handle_capture_template_for_step(self):
        if not self.current_step_region_image_pil_for_display or not self.current_step_region_name: messagebox.showerror("Error", "Region image not available for template capture.", parent=self); return
        element_desc_for_template = self.ui_element_to_refine_desc or (self.current_plan_step_data.get('description', 'step_element')[:20] if self.current_plan_step_data else "step_element")
        default_template_name_base = f"tpl_{self.current_step_region_name}_{element_desc_for_template.replace(' ','_').lower()}"
        sane_default_template_name_base = "".join(c if c.isalnum() else "_" for c in default_template_name_base); sane_default_template_name_base = sane_default_template_name_base[:40] if len(sane_default_template_name_base) > 40 else sane_default_template_name_base
        count = 0; suggested_tpl_name = sane_default_template_name_base
        while any(t.get("name") == suggested_tpl_name for t in self.profile_generator.generated_profile_data.get("templates", [])): count += 1; suggested_tpl_name = f"{sane_default_template_name_base}_{count}"
        template_name_dialog = ctk.CTkInputDialog(text=f"Enter unique name for this new template:", title="New Template Name", entry_text=suggested_tpl_name)
        template_name_input = template_name_dialog.get_input()
        if not template_name_input or not template_name_input.strip(): logger.info("Template capture cancelled: No name."); return
        template_name = template_name_input.strip()
        if any(t.get("name") == template_name for t in self.profile_generator.generated_profile_data.get("templates", [])): messagebox.showerror("Name Conflict", f"A template named '{template_name}' already exists in this draft.", parent=self); return
        logger.info(f"Initiating template capture from region '{self.current_step_region_name}' for template '{template_name}'")
        self.attributes("-alpha", 0.5)
        sub_selector = SubImageSelectorWindow(master=self, image_to_select_from_pil=self.current_step_region_image_pil_for_display, title=f"Select Area for Template '{template_name}'")
        self.wait_window(sub_selector); self.attributes("-alpha", 1.0)
        selected_template_coords_xywh = sub_selector.get_selected_coords()
        if selected_template_coords_xywh:
            x_rel, y_rel, w_rel, h_rel = selected_template_coords_xywh
            if self.current_step_region_image_np is not None and w_rel > 0 and h_rel > 0:
                template_image_np_bgr = self.current_step_region_image_np[y_rel : y_rel+h_rel, x_rel : x_rel+w_rel]
                sane_filename_base_for_file = "".join(c if c.isalnum() else "_" for c in template_name).lower(); template_filename_base = f"{sane_filename_base_for_file}.png"
                existing_filenames_in_draft = [tpl.get("filename") for tpl in self.profile_generator.generated_profile_data.get("templates", [])]; final_template_filename = template_filename_base; fn_count = 1
                while final_template_filename in existing_filenames_in_draft: final_template_filename = f"{sane_filename_base_for_file}_{fn_count}.png"; fn_count += 1
                template_metadata = {"name": template_name, "filename": final_template_filename, "comment": f"Template for '{element_desc_for_template}' in region '{self.current_step_region_name}'. User captured.", "_image_data_np_for_save": template_image_np_bgr }
                if self.profile_generator.add_template_definition(template_metadata):
                    logger.info(f"Template '{template_name}' (filename: {final_template_filename}) metadata and image data staged for profile.")
                    cond_type_var = self.step_logic_optionmenu_vars.get("step_cond_type_var")
                    if cond_type_var: cond_type_var.set("template_match_found"); self._on_wizard_logic_type_change("condition", "template_match_found")
                    self.after(50, lambda: self._attempt_set_template_name_in_ui(template_name))
                    act_type_var = self.step_logic_optionmenu_vars.get("step_act_type_var")
                    if act_type_var: act_type_var.set("click"); self._on_wizard_logic_type_change("action", "click")
                    self.after(100, lambda: self._set_click_action_params_for_template(template_name))
                    messagebox.showinfo("Template Staged", f"Template '{template_name}' (filename '{final_template_filename}') captured.\nIt will be saved with the profile.", parent=self)
                else: messagebox.showerror("Error", f"Failed to add template metadata for '{template_name}'.", parent=self)
            else: messagebox.showerror("Template Capture Error", "Could not capture a valid template image from the selection.", parent=self)
        else: logger.info("Template capture from sub-image selector cancelled by user.")

    def _save_generated_profile(self):
        logger.info("Save Profile button clicked on final review page.")
        filename_base_from_ui = self.profile_filename_entry.get().strip();
        if not filename_base_from_ui: messagebox.showerror("Filename Missing", "Please enter a filename for the profile.", parent=self); return

        profile_data_for_saving = self.profile_generator.get_generated_profile_data()
        if self.user_goal_text: profile_data_for_saving["profile_description"] = f"AI-Generated for goal: {self.user_goal_text[:120]}"
        self.profile_generator.generated_profile_data["profile_description"] = profile_data_for_saving["profile_description"]

        default_save_dir = self.main_app_instance.config_manager.profiles_base_dir
        initial_filename_for_dialog = f"{filename_base_from_ui}.json"
        filepath_chosen_by_user = tk.filedialog.asksaveasfilename(title="Save AI-Generated Profile As", initialdir=default_save_dir, initialfile=initial_filename_for_dialog, defaultextension=".json", filetypes=[("JSON Profile","*.json"),("All files","*.*")], parent=self)

        if filepath_chosen_by_user:
            success = self.profile_generator.save_generated_profile(filepath_chosen_by_user)
            if success:
                messagebox.showinfo("Profile Saved", f"AI-Generated profile (and its templates) saved to:\n{filepath_chosen_by_user}", parent=self)
                self.newly_saved_profile_path = filepath_chosen_by_user
                if messagebox.askyesno("Open in Editor?", "Open the new profile in the main editor?", parent=self):
                    self.main_app_instance._load_profile_from_path(filepath_chosen_by_user)
                self._on_close_wizard(was_saved=True)
            else: messagebox.showerror("Save Failed", "Could not save profile or its templates. Please check logs for details.", parent=self)
        else: logger.info("Profile save dialog cancelled by user.")