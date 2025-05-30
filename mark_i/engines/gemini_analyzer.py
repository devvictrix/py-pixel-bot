import logging
import time
import json 
from typing import Optional, Dict, Any, Union, List # Ensure Any is imported for the fallback
import os 

import google.generativeai as genai
# Adjusted imports: Removed 'Part' from here as it causes an ImportError
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold 
from google.generativeai.types import BlockedPromptException, StopCandidateException 

from PIL import Image 
import cv2 
import numpy as np

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_analyzer")

# Attempt to import Part for type hinting, fallback to Any
try:
    from google.generativeai.types import Part # Try the original location first
    logger.debug("Imported 'Part' from 'google.generativeai.types'")
except ImportError:
    try:
        from google.generativeai import Part # Try from top level of the package
        logger.debug("Imported 'Part' from 'google.generativeai'")
    except ImportError:
        logger.warning("'Part' type not found in 'google.generativeai.types' or 'google.generativeai'. Using 'Any' for type hints involving 'Part'. This might indicate an SDK version issue.")
        Part = Any # Fallback to Any if Part cannot be imported for type hinting

DEFAULT_SAFETY_SETTINGS_DATA: List[Dict[str, Any]] = [ 
    {
        "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    },
    {
        "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    },
    {
        "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    },
    {
        "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    },
]

DEFAULT_GENERATION_CONFIG = GenerationConfig()


class GeminiAnalyzer:
    def __init__(self, api_key: str, default_model_name: str = "gemini-1.5-flash-latest"):
        self.api_key = api_key
        self.default_model_name = default_model_name
        self.client_initialized = False
        
        self.safety_settings_data = DEFAULT_SAFETY_SETTINGS_DATA
        self.safety_settings: Optional[List[Any]] = None 

        self.generation_config = DEFAULT_GENERATION_CONFIG

        if not self.api_key or not isinstance(self.api_key, str):
            logger.critical("GeminiAnalyzer CRITICAL ERROR: API key is missing or invalid. Gemini features will be non-functional.")
            return

        try:
            genai.configure(api_key=self.api_key)
            
            self.safety_settings = []
            if hasattr(genai, "SafetySetting"):
                SafetySettingClass = genai.SafetySetting
                for ss_data in self.safety_settings_data:
                    self.safety_settings.append(
                        SafetySettingClass(harm_category=ss_data["category"], threshold=ss_data["threshold"])
                    )
                logger.debug("Constructed SafetySetting objects using genai.SafetySetting.")
            else:
                logger.error("Class 'SafetySetting' not found via 'genai.SafetySetting'. Safety settings may not be correctly applied. This indicates a potential SDK version mismatch or unexpected structure.")

            self.client_initialized = True
            logger.info(f"GeminiAnalyzer initialized. Default model: '{self.default_model_name}'. API client configured successfully.")
            if self.safety_settings: 
                safety_settings_log = []
                for s_obj in self.safety_settings:
                    cat_name = getattr(getattr(s_obj, 'harm_category', None), 'name', str(getattr(s_obj, 'harm_category', 'UnknownCategory')))
                    thr_name = getattr(getattr(s_obj, 'threshold', None), 'name', str(getattr(s_obj, 'threshold', 'UnknownThreshold')))
                    safety_settings_log.append((cat_name, thr_name))
                logger.debug(f"Using safety settings: {safety_settings_log}")
            else:
                logger.warning("Default safety settings list is empty or None. API will use its own defaults for safety.")
            logger.debug(f"Using default generation config: {self.generation_config}")

        except Exception as e:
            self.client_initialized = False 
            logger.critical(f"GeminiAnalyzer CRITICAL FAILURE: Could not configure Gemini API client with provided key: {e}. Gemini features will be disabled.", exc_info=True)

    def query_vision_model(
        self,
        prompt: str,
        image_data: Optional[np.ndarray] = None, 
        model_name_override: Optional[str] = None,
        custom_generation_config: Optional[GenerationConfig] = None,
        custom_safety_settings: Optional[List[Any]] = None, 
    ) -> Dict[str, Any]:
        start_time = time.perf_counter()
        model_to_use = model_name_override if model_name_override else self.default_model_name

        result: Dict[str, Any] = {
            "status": "error_client",
            "text_content": None,
            "json_content": None,
            "error_message": "Gemini API client not initialized (e.g., missing or invalid API key).",
            "model_used": model_to_use,
            "latency_ms": 0,
            "raw_gemini_response": None,
        }
        log_prefix = f"GeminiQuery (Model: '{model_to_use}')"

        if not self.client_initialized:
            logger.error(f"{log_prefix}: {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            result["status"] = "error_input"
            result["error_message"] = "Input error: Prompt cannot be empty or just whitespace."
            logger.error(f"{log_prefix}: {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        pil_image_for_sdk: Optional[Image.Image] = None
        if image_data is not None:
            if not isinstance(image_data, np.ndarray) or image_data.size == 0:
                result["status"] = "error_input"
                result["error_message"] = "Input error: Provided image_data is invalid (empty or not NumPy array)."
            elif image_data.ndim != 3 or image_data.shape[2] != 3:
                result["status"] = "error_input"
                result["error_message"] = f"Input error: Provided image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}"
            else:
                try:
                    img_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
                    pil_image_for_sdk = Image.fromarray(img_rgb)
                    logger.debug(f"{log_prefix}: Prepared image (Size: {pil_image_for_sdk.width}x{pil_image_for_sdk.height}) for API call.")
                except Exception as e_img_prep:
                    result["status"] = "error_input"
                    result["error_message"] = f"Error preparing image for Gemini: {e_img_prep}"
                    logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)

            if result["status"] == "error_input":
                logger.error(
                    f"{log_prefix}: {result['error_message']}" if "error_message" in result and result["error_message"] else f"{log_prefix}: Image preparation failed with unspecified error."
                )
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result
        
        # Changed type hint for api_contents as Part import is problematic
        api_contents: List[Union[str, Image.Image]] = [prompt] 
        if pil_image_for_sdk:
            api_contents.append(pil_image_for_sdk) 

        prompt_summary_for_log = (prompt[:150].replace(os.linesep, " ") + "...") if len(prompt) > 153 else prompt.replace(os.linesep, " ")
        logger.info(f"{log_prefix}: Sending query. Prompt summary: '{prompt_summary_for_log}'. Image provided: {pil_image_for_sdk is not None}.")

        try:
            effective_gen_config = custom_generation_config if custom_generation_config else self.generation_config
            effective_safety_settings = custom_safety_settings if custom_safety_settings is not None else self.safety_settings
            
            if effective_safety_settings is None: 
                 logger.warning(f"{log_prefix}: No safety settings provided or default construction failed; API defaults will apply.")
                 effective_safety_settings = [] 

            model_instance = genai.GenerativeModel(model_name=model_to_use, generation_config=effective_gen_config, safety_settings=effective_safety_settings)

            api_sdk_response = model_instance.generate_content(api_contents, stream=False)
            result["raw_gemini_response"] = str(api_sdk_response) 

            if hasattr(api_sdk_response, "prompt_feedback") and api_sdk_response.prompt_feedback and api_sdk_response.prompt_feedback.block_reason:
                result["status"] = "blocked_prompt"
                block_reason = api_sdk_response.prompt_feedback.block_reason
                result["error_message"] = (
                    f"Prompt blocked by API. Reason: {block_reason.name if hasattr(block_reason,'name') else str(block_reason)}. Ratings: {api_sdk_response.prompt_feedback.safety_ratings}"
                )
                logger.warning(f"{log_prefix}: {result['error_message']}")
            elif not api_sdk_response.candidates:
                result["status"] = "error_api" 
                result["error_message"] = "No candidates in Gemini response. Prompt might have been silently blocked or another API error occurred."
                logger.warning(f"{log_prefix}: {result['error_message']}")
            else:
                first_candidate = api_sdk_response.candidates[0]
                finish_reason_val = getattr(first_candidate, "finish_reason", None)

                is_normal_stop = False
                if finish_reason_val is not None:
                    finish_reason_str = ""
                    if hasattr(finish_reason_val, 'name'): 
                        finish_reason_str = finish_reason_val.name.upper()
                    elif isinstance(finish_reason_val, str):
                        finish_reason_str = finish_reason_val.upper()
                    is_normal_stop = (finish_reason_str == "STOP")

                if not is_normal_stop and finish_reason_val is not None: 
                    result["status"] = "blocked_response"
                    safety_ratings_str = str(getattr(first_candidate, "safety_ratings", "N/A"))
                    result["error_message"] = (
                        f"Response generation stopped. Reason: {getattr(finish_reason_val,'name', str(finish_reason_val))}. Safety: {safety_ratings_str}"
                    )
                    logger.warning(f"{log_prefix}: {result['error_message']}")
                    if hasattr(first_candidate, "content") and first_candidate.content and first_candidate.content.parts:
                        result["text_content"] = "".join(part.text for part in first_candidate.content.parts if hasattr(part, "text")).strip()
                elif finish_reason_val is None and not hasattr(first_candidate, "content"): 
                    result["status"] = "error_api"
                    result["error_message"] = "Response candidate had no finish_reason and no content. API error or unexpected state."
                    logger.warning(f"{log_prefix}: {result['error_message']}")
                else: 
                    result["status"] = "success"
                    if hasattr(first_candidate, "content") and first_candidate.content and first_candidate.content.parts:
                        result["text_content"] = "".join(part.text for part in first_candidate.content.parts if hasattr(part, "text")).strip()
                    else:
                        result["text_content"] = ""
                        if is_normal_stop: 
                            logger.info(f"{log_prefix}: Successful response (STOP) but no text parts in candidate content.")

                    if result["text_content"]:
                        text_for_json = result["text_content"]
                        if text_for_json.startswith("```json"):
                            text_for_json = text_for_json[7:]
                        elif text_for_json.startswith("```"):
                            text_for_json = text_for_json[3:]
                        if text_for_json.endswith("```"):
                            text_for_json = text_for_json[:-3]
                        text_for_json = text_for_json.strip()
                        try:
                            result["json_content"] = json.loads(text_for_json)
                            logger.debug(f"{log_prefix}: Response successfully parsed as JSON.")
                        except json.JSONDecodeError:
                            logger.debug(f"{log_prefix}: Response text content is not valid JSON. Snippet: '{result['text_content'][:150].replace(os.linesep, ' ')}...'")
                            result["json_content"] = None
                    else:
                        result["json_content"] = None

                    if result["status"] == "success": 
                        logger.info(
                            f"{log_prefix}: Query successful. Text snippet: '{result['text_content'][:100].replace(os.linesep, ' ')}...'. JSON detected: {result['json_content'] is not None}."
                        )
        except BlockedPromptException as e_bp:
            result["status"] = "blocked_prompt"
            result["error_message"] = f"Gemini SDK: Prompt blocked. {e_bp}"
            result["raw_gemini_response"] = str(e_bp)
            logger.warning(f"{log_prefix}: {result['error_message']}")
        except StopCandidateException as e_sc: 
            result["status"] = "blocked_response"
            result["error_message"] = f"Gemini SDK: Candidate generation stopped (likely due to safety settings). {e_sc}"
            result["raw_gemini_response"] = str(e_sc)
            logger.warning(f"{log_prefix}: {result['error_message']}")
        except google_api_exceptions.PermissionDenied as e_perm:
            result["status"] = "error_api"
            result["error_message"] = f"Gemini API Permission Denied: {e_perm}. Check API key and project IAM permissions."
            result["raw_gemini_response"] = str(e_perm)
            logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)
        except google_api_exceptions.ResourceExhausted as e_quota:
            result["status"] = "error_api"
            result["error_message"] = f"Gemini API Resource Exhausted (Quota likely): {e_quota}."
            result["raw_gemini_response"] = str(e_quota)
            logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)
        except google_api_exceptions.DeadlineExceeded as e_timeout:
            result["status"] = "error_api"
            result["error_message"] = f"Gemini API Deadline Exceeded (Timeout): {e_timeout}."
            result["raw_gemini_response"] = str(e_timeout)
            logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)
        except google_api_exceptions.ServiceUnavailable as e_service:
            result["status"] = "error_api"
            result["error_message"] = f"Gemini API Service Unavailable: {e_service}. Try again later."
            result["raw_gemini_response"] = str(e_service)
            logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)
        except google_api_exceptions.InvalidArgument as e_invalid_arg: 
            result["status"] = "error_api"
            result["error_message"] = f"Gemini API Invalid Argument: {e_invalid_arg}. Check model name, prompt/image format, or other parameters."
            result["raw_gemini_response"] = str(e_invalid_arg)
            logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)
        except Exception as e_general_api: 
            result["status"] = "error_api"
            result["error_message"] = f"Gemini API call failed ({type(e_general_api).__name__}): {e_general_api}"
            result["raw_gemini_response"] = str(e_general_api)
            logger.error(f"{log_prefix}: API call failed. Error: {result['error_message']}", exc_info=True)

        result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"{log_prefix}: Query finished. Final Status: '{result['status']}'. Latency: {result['latency_ms']}ms.")
        return result