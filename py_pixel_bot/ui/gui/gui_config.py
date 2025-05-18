import logging

logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_PROFILE_STRUCTURE = {
    "profile_description": "New Profile",
    "settings": {
        "monitoring_interval_seconds": 1.0,
        "analysis_dominant_colors_k": 3,
        "tesseract_cmd_path": None,
        "tesseract_config_custom": "",
        "gemini_default_model_name": "gemini-1.5-flash-latest" # Added for v4.0.0
    },
    "regions": [],
    "templates": [],
    "rules": [],
}
MAX_PREVIEW_WIDTH = 200
MAX_PREVIEW_HEIGHT = 150

CONDITION_TYPES = [
    "pixel_color",
    "average_color_is",
    "template_match_found",
    "ocr_contains_text",
    "dominant_color_matches",
    "gemini_vision_query", # Added for v4.0.0
    "always_true"
]
ACTION_TYPES = ["click", "type_text", "press_key", "log_message"]
LOGICAL_OPERATORS = ["AND", "OR"]
CLICK_TARGET_RELATIONS = ["center_of_region", "center_of_last_match", "absolute", "relative_to_region"]
CLICK_BUTTONS = ["left", "middle", "right"]
LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Data-driven UI Parameter Configuration
UI_PARAM_CONFIG = {
    "conditions": {
        "pixel_color": [
            {"id": "relative_x", "label": "Relative X:", "widget": "entry", "type": int, "default": 0, "required": True, "placeholder": "0"},
            {"id": "relative_y", "label": "Relative Y:", "widget": "entry", "type": int, "default": 0, "required": True, "placeholder": "0"},
            {"id": "expected_bgr", "label": "Expected BGR:", "widget": "entry", "type": "bgr_string", "default": "0,0,0", "required": True, "placeholder": "B,G,R"},
            {"id": "tolerance", "label": "Tolerance:", "widget": "entry", "type": int, "default": 0, "required": True, "min_val": 0, "max_val": 255, "placeholder": "0"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ],
        "average_color_is": [
            {"id": "expected_bgr", "label": "Expected BGR:", "widget": "entry", "type": "bgr_string", "default": "128,128,128", "required": True, "placeholder": "B,G,R"},
            {"id": "tolerance", "label": "Tolerance:", "widget": "entry", "type": int, "default": 10, "required": True, "min_val": 0, "max_val": 255, "placeholder": "10"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ],
        "template_match_found": [
            {"id": "template_name", "label": "Template Name:", "widget": "optionmenu_dynamic", "options_source": "templates", "default": "", "required": True},
            {"id": "min_confidence", "label": "Min Confidence:", "widget": "entry", "type": float, "default": 0.8, "required": True, "min_val": 0.0, "max_val": 1.0, "placeholder": "0.8"},
            {"id": "capture_as", "label": "Capture Details As:", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "Optional var name"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ],
        "ocr_contains_text": [
            {"id": "text_to_find", "label": "Text to Find (CSV for OR):", "widget": "entry", "type": str, "default": "", "required": True, "placeholder": "keyword1,keyword2"},
            {"id": "case_sensitive", "label": "Case Sensitive", "widget": "checkbox", "type": bool, "default": False},
            {
                "id": "min_ocr_confidence",
                "label": "Min OCR Confidence:",
                "widget": "entry",
                "type": float,
                "default": 70.0,
                "required": False, 
                "allow_empty_string": True, 
                "min_val": 0.0,
                "max_val": 100.0,
                "placeholder": "e.g., 70.0 (optional)",
            },
            {"id": "capture_as", "label": "Capture Text As:", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "Optional var name"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ],
        "dominant_color_matches": [
            {"id": "expected_bgr", "label": "Expected BGR:", "widget": "entry", "type": "bgr_string", "default": "0,0,255", "required": True, "placeholder": "B,G,R"},
            {"id": "tolerance", "label": "Tolerance:", "widget": "entry", "type": int, "default": 10, "required": True, "min_val": 0, "max_val": 255, "placeholder": "10"},
            {"id": "check_top_n_dominant", "label": "Check Top N:", "widget": "entry", "type": int, "default": 1, "required": True, "min_val": 1, "placeholder": "1"},
            {"id": "min_percentage", "label": "Min Percentage:", "widget": "entry", "type": float, "default": 5.0, "required": True, "min_val": 0.0, "max_val": 100.0, "placeholder": "5.0"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ],
        "gemini_vision_query": [ 
            {"id": "prompt", "label": "Gemini Prompt:", "widget": "textbox", "type": str, "default": "Describe this image.", "required": True, "placeholder": "e.g., Is there a login button visible?", "height": 120}, # Added height
            {"id": "expected_response_contains", "label": "Response Contains (CSV for OR):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., login,error"},
            {"id": "case_sensitive_response_check", "label": "Case Sensitive Check", "widget": "checkbox", "type": bool, "default": False},
            {"id": "expected_response_json_path", "label": "JSON Path (Basic Dot Notation):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., data.items.0.name"},
            {"id": "expected_json_value", "label": "Expected JSON Value (String):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "Value at JSON path"},
            {"id": "capture_as", "label": "Capture Response As:", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "var_name_for_gemini_output"},
            {"id": "model_name", "label": "Gemini Model (Override):", "widget": "entry", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "e.g., gemini-1.5-pro-latest"},
            {"id": "region", "label": "Target Region (Override):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False},
        ],
        "always_true": [
            {"id": "region", "label": "Target Region (Override - Optional):", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False}
        ],
    },
    "actions": {
        "click": [
            {"id": "target_relation", "label": "Target Relation:", "widget": "optionmenu_static", "options_const_key": "CLICK_TARGET_RELATIONS", "default": "center_of_region", "required": True},
            {"id": "target_region", "label": "Target Region:", "widget": "optionmenu_dynamic", "options_source": "regions", "default": "", "required": False}, 
            {"id": "x", "label": "X Coord/Offset:", "widget": "entry", "type": str, "default": "0", "required": False, "allow_empty_string": True, "placeholder": "Abs/Rel X or {var}"}, 
            {"id": "y", "label": "Y Coord/Offset:", "widget": "entry", "type": str, "default": "0", "required": False, "allow_empty_string": True, "placeholder": "Abs/Rel Y or {var}"}, 
            {"id": "button", "label": "Button:", "widget": "optionmenu_static", "options_const_key": "CLICK_BUTTONS", "default": "left", "required": True},
            {"id": "clicks", "label": "Num Clicks:", "widget": "entry", "type": str, "default": "1", "required": False, "allow_empty_string": True, "placeholder": "Number or {var}"},
            {"id": "interval", "label": "Click Interval (s):", "widget": "entry", "type": str, "default": "0.0", "required": False, "allow_empty_string": True, "placeholder": "Seconds or {var}"},
            {
                "id": "pyautogui_pause_before",
                "label": "Pause Before (s):",
                "widget": "entry",
                "type": str,
                "default": "0.0",
                "required": False,
                "allow_empty_string": True,
                "placeholder": "Seconds or {var}",
            },
        ],
        "type_text": [
            {"id": "text", "label": "Text to Type:", "widget": "textbox", "type": str, "default": "", "required": False, "allow_empty_string": True, "placeholder": "Text to type or {var}", "height": 80}, # Added height
            {"id": "interval", "label": "Typing Interval (s):", "widget": "entry", "type": str, "default": "0.0", "required": False, "allow_empty_string": True, "placeholder": "Seconds or {var}"},
            {
                "id": "pyautogui_pause_before",
                "label": "Pause Before (s):",
                "widget": "entry",
                "type": str,
                "default": "0.0",
                "required": False,
                "allow_empty_string": True,
                "placeholder": "Seconds or {var}",
            },
        ],
        "press_key": [
            {"id": "key", "label": "Key(s) to Press (CSV for hotkey):", "widget": "entry", "type": str, "default": "enter", "required": True, "placeholder": "e.g., enter or ctrl,c or {var}"},
            {
                "id": "pyautogui_pause_before",
                "label": "Pause Before (s):",
                "widget": "entry",
                "type": str,
                "default": "0.0",
                "required": False,
                "allow_empty_string": True,
                "placeholder": "Seconds or {var}",
            },
        ],
        "log_message": [
            {
                "id": "message",
                "label": "Log Message:",
                "widget": "textbox", # Changed to textbox for potentially longer messages
                "type": str,
                "default": "Rule triggered",
                "required": False,
                "allow_empty_string": True,
                "placeholder": "Log message or {var}",
                "height": 80 # Added height
            },
            {"id": "level", "label": "Log Level:", "widget": "optionmenu_static", "options_const_key": "LOG_LEVELS", "default": "INFO", "required": True},
        ],
    },
}
OPTIONS_CONST_MAP = {
    "CLICK_TARGET_RELATIONS": CLICK_TARGET_RELATIONS,
    "CLICK_BUTTONS": CLICK_BUTTONS,
    "LOG_LEVELS": LOG_LEVELS,
}