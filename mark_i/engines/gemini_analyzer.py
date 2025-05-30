# Correcting the import for Content based on common patterns or assuming it's available at top level
# This is speculative; the actual location depends on the google-generativeai SDK version.
# If this still fails, 'Content' might need to be 'Any' or its true location found.
import logging
import time
import json
from typing import Optional, Dict, Any, Union, List, Tuple
import os

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold
from google.generativeai.types import BlockedPromptException, StopCandidateException
# Try importing Content from google.generativeai directly
try:
    from google.generativeai import Content
    logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_analyzer") # Define logger earlier
    logger.debug("Imported 'Content' from 'google.generativeai'")
except ImportError:
    logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_analyzer")
    logger.warning("'Content' type not found in 'google.generativeai.types' or 'google.generativeai'. Using 'Any'.")
    Content = Any # Fallback if direct import fails

from google.api_core import exceptions as google_api_exceptions

from PIL import Image
import cv2
import numpy as np

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
# Logger definition moved up to handle Content import logging

try:
    from google.generativeai.types import Part
    logger.debug("Imported 'Part' from 'google.generativeai.types'")
except ImportError:
    try:
        from google.generativeai import Part
        logger.debug("Imported 'Part' from 'google.generativeai'")
    except ImportError:
        logger.warning("'Part' type not found. Using 'Any' for type hints involving 'Part'.")
        Part = Any

DEFAULT_SAFETY_SETTINGS_DATA: List[Dict[str, Any]] = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
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
            logger.critical("GeminiAnalyzer CRITICAL ERROR: API key is missing or invalid.")
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
                logger.debug("Constructed SafetySetting objects.")
            else:
                logger.error("'SafetySetting' class not found. Safety settings may not be applied.")
            self.client_initialized = True
            logger.info(f"GeminiAnalyzer initialized. Default model: '{self.default_model_name}'. Client configured.")
            if self.safety_settings and hasattr(self.safety_settings[0], 'harm_category') and hasattr(self.safety_settings[0].harm_category, 'name'): # Check if valid
                 logger.debug(f"Using safety settings: {[(s.harm_category.name, s.threshold.name) for s in self.safety_settings]}") # type: ignore
            else: logger.warning("Default safety settings list is empty, None or malformed.")
            logger.debug(f"Using default generation config: {self.generation_config}")
        except Exception as e:
            self.client_initialized = False
            logger.critical(f"GeminiAnalyzer CRITICAL FAILURE: Could not configure API client: {e}.", exc_info=True)

    def _validate_and_prepare_api_input(
        self, prompt: str, image_data: Optional[np.ndarray], log_prefix: str
    ) -> Tuple[Optional[List[Union[str, Image.Image]]], Optional[Dict[str, Any]]]:
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            error_msg = "Input error: Prompt cannot be empty or just whitespace."
            logger.error(f"{log_prefix}: {error_msg}")
            return None, {"status": "error_input", "error_message": error_msg}

        pil_image_for_sdk: Optional[Image.Image] = None
        if image_data is not None:
            if not isinstance(image_data, np.ndarray) or image_data.size == 0:
                error_msg = "Input error: Provided image_data is invalid (empty or not NumPy array)."
                logger.error(f"{log_prefix}: {error_msg}")
                return None, {"status": "error_input", "error_message": error_msg}
            if image_data.ndim != 3 or image_data.shape[2] != 3:
                error_msg = f"Input error: Provided image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}"
                logger.error(f"{log_prefix}: {error_msg}")
                return None, {"status": "error_input", "error_message": error_msg}
            try:
                img_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
                pil_image_for_sdk = Image.fromarray(img_rgb)
                logger.debug(f"{log_prefix}: Prepared image (Size: {pil_image_for_sdk.width}x{pil_image_for_sdk.height}) for API call.")
            except Exception as e_img_prep:
                error_msg = f"Error preparing image for Gemini: {e_img_prep}"
                logger.error(f"{log_prefix}: {error_msg}", exc_info=True)
                return None, {"status": "error_input", "error_message": error_msg}

        api_contents: List[Union[str, Image.Image]] = [prompt]
        if pil_image_for_sdk:
            api_contents.append(pil_image_for_sdk)
        return api_contents, None

    def _execute_sdk_call(
        self, model_instance: genai.GenerativeModel, api_contents: List[Union[str, Image.Image]], log_prefix: str
    ) -> Tuple[Optional[Content], Optional[Dict[str, Any]]]: # type: ignore # Content might be Any
        try:
            api_sdk_response: Content = model_instance.generate_content(api_contents, stream=False) # type: ignore
            return api_sdk_response, None
        except BlockedPromptException as e_bp:
            error_msg = f"Gemini SDK: Prompt blocked. {e_bp}"
            logger.warning(f"{log_prefix}: {error_msg}")
            return None, {"status": "blocked_prompt", "error_message": error_msg, "raw_gemini_response": str(e_bp)}
        except StopCandidateException as e_sc:
            error_msg = f"Gemini SDK: Candidate generation stopped (likely due to safety settings). {e_sc}"
            logger.warning(f"{log_prefix}: {error_msg}")
            return None, {"status": "blocked_response", "error_message": error_msg, "raw_gemini_response": str(e_sc)}
        except google_api_exceptions.PermissionDenied as e_perm:
            error_msg = f"Gemini API Permission Denied: {e_perm}. Check API key and project IAM permissions."
            logger.error(f"{log_prefix}: {error_msg}", exc_info=True)
            return None, {"status": "error_api", "error_message": error_msg, "raw_gemini_response": str(e_perm)}
        except google_api_exceptions.ResourceExhausted as e_quota:
            error_msg = f"Gemini API Resource Exhausted (Quota likely): {e_quota}."
            logger.error(f"{log_prefix}: {error_msg}", exc_info=True)
            return None, {"status": "error_api", "error_message": error_msg, "raw_gemini_response": str(e_quota)}
        except google_api_exceptions.DeadlineExceeded as e_timeout:
            error_msg = f"Gemini API Deadline Exceeded (Timeout): {e_timeout}."
            logger.error(f"{log_prefix}: {error_msg}", exc_info=True)
            return None, {"status": "error_api", "error_message": error_msg, "raw_gemini_response": str(e_timeout)}
        except google_api_exceptions.ServiceUnavailable as e_service:
            error_msg = f"Gemini API Service Unavailable: {e_service}. Try again later."
            logger.error(f"{log_prefix}: {error_msg}", exc_info=True)
            return None, {"status": "error_api", "error_message": error_msg, "raw_gemini_response": str(e_service)}
        except google_api_exceptions.InvalidArgument as e_invalid_arg:
            error_msg = f"Gemini API Invalid Argument: {e_invalid_arg}. Check model name, prompt/image format, or other parameters."
            logger.error(f"{log_prefix}: {error_msg}", exc_info=True)
            return None, {"status": "error_api", "error_message": error_msg, "raw_gemini_response": str(e_invalid_arg)}
        except Exception as e_general_api:
            error_msg = f"Gemini API call failed ({type(e_general_api).__name__}): {e_general_api}"
            logger.error(f"{log_prefix}: API call failed. Error: {error_msg}", exc_info=True)
            return None, {"status": "error_api", "error_message": error_msg, "raw_gemini_response": str(e_general_api)}

    def _process_sdk_response(self, api_sdk_response: Optional[Content], log_prefix: str) -> Dict[str, Any]: # type: ignore
        processed_result: Dict[str, Any] = {
            "status": "error_api", "text_content": None, "json_content": None,
            "error_message": "Failed to process SDK response or response was None.",
            "raw_gemini_response": str(api_sdk_response) if api_sdk_response else "None"
        }
        if api_sdk_response is None: return processed_result
        processed_result["raw_gemini_response"] = str(api_sdk_response)

        if hasattr(api_sdk_response, "prompt_feedback") and api_sdk_response.prompt_feedback and api_sdk_response.prompt_feedback.block_reason:
            processed_result["status"] = "blocked_prompt"; block_reason = api_sdk_response.prompt_feedback.block_reason
            processed_result["error_message"] = (f"Prompt blocked by API. Reason: {block_reason.name if hasattr(block_reason,'name') else str(block_reason)}. Ratings: {api_sdk_response.prompt_feedback.safety_ratings}")
            logger.warning(f"{log_prefix}: {processed_result['error_message']}"); return processed_result
        if not api_sdk_response.candidates:
            processed_result["error_message"] = "No candidates in Gemini response."; logger.warning(f"{log_prefix}: {processed_result['error_message']}"); return processed_result

        first_candidate = api_sdk_response.candidates[0]; finish_reason_val = getattr(first_candidate, "finish_reason", None)
        is_normal_stop = finish_reason_val is not None and ((hasattr(finish_reason_val, 'name') and finish_reason_val.name.upper() == "STOP") or (isinstance(finish_reason_val, str) and finish_reason_val.upper() == "STOP"))

        if not is_normal_stop and finish_reason_val is not None:
            processed_result["status"] = "blocked_response"; safety_ratings_str = str(getattr(first_candidate, "safety_ratings", "N/A"))
            processed_result["error_message"] = f"Response generation stopped. Reason: {getattr(finish_reason_val,'name', str(finish_reason_val))}. Safety: {safety_ratings_str}"
            logger.warning(f"{log_prefix}: {processed_result['error_message']}")
            if hasattr(first_candidate, "content") and first_candidate.content and first_candidate.content.parts: processed_result["text_content"] = "".join(part.text for part in first_candidate.content.parts if hasattr(part, "text")).strip() # type: ignore
            return processed_result
        if finish_reason_val is None and not hasattr(first_candidate, "content"):
            processed_result["error_message"] = "Response candidate had no finish_reason and no content."; logger.warning(f"{log_prefix}: {processed_result['error_message']}"); return processed_result

        processed_result["status"] = "success"; processed_result["error_message"] = None
        if hasattr(first_candidate, "content") and first_candidate.content and first_candidate.content.parts: processed_result["text_content"] = "".join(part.text for part in first_candidate.content.parts if hasattr(part, "text")).strip() # type: ignore
        else: processed_result["text_content"] = ""; logger.info(f"{log_prefix}: Successful response (STOP) but no text parts.") if is_normal_stop else None

        if processed_result["text_content"]:
            text_for_json = processed_result["text_content"]
            if text_for_json.startswith("```json"): text_for_json = text_for_json[7:]
            elif text_for_json.startswith("```"): text_for_json = text_for_json[3:]
            if text_for_json.endswith("```"): text_for_json = text_for_json[:-3]
            text_for_json = text_for_json.strip()
            try: processed_result["json_content"] = json.loads(text_for_json); logger.debug(f"{log_prefix}: Response parsed as JSON.")
            except json.JSONDecodeError: logger.debug(f"{log_prefix}: Response not valid JSON. Snippet: '{processed_result['text_content'][:150].replace(os.linesep, ' ')}...'"); processed_result["json_content"] = None
        else: processed_result["json_content"] = None
        if processed_result["status"] == "success": logger.info(f"{log_prefix}: Query processing successful. Text snippet: '{str(processed_result['text_content'])[:100].replace(os.linesep, ' ')}...'. JSON: {processed_result['json_content'] is not None}.")
        return processed_result

    def query_vision_model(
        self, prompt: str, image_data: Optional[np.ndarray] = None, model_name_override: Optional[str] = None,
        custom_generation_config: Optional[GenerationConfig] = None, custom_safety_settings: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        start_time = time.perf_counter(); model_to_use = model_name_override if model_name_override else self.default_model_name
        log_prefix = f"GeminiQuery (Model: '{model_to_use}')"
        result: Dict[str, Any] = {"status": "error_client", "text_content": None, "json_content": None, "error_message": "Client not initialized.", "model_used": model_to_use, "latency_ms": 0, "raw_gemini_response": None}
        if not self.client_initialized: logger.error(f"{log_prefix}: {result['error_message']}"); result["latency_ms"] = int((time.perf_counter() - start_time) * 1000); return result

        api_contents, input_error_result = self._validate_and_prepare_api_input(prompt, image_data, log_prefix)
        if input_error_result: result.update(input_error_result); result["latency_ms"] = int((time.perf_counter() - start_time) * 1000); return result

        prompt_summary = (prompt[:150].replace(os.linesep, " ") + "...") if len(prompt) > 153 else prompt.replace(os.linesep, " ")
        logger.info(f"{log_prefix}: Sending query. Prompt: '{prompt_summary}'. Image: {image_data is not None}.")
        effective_gen_config = custom_generation_config if custom_generation_config else self.generation_config
        effective_safety_settings = custom_safety_settings if custom_safety_settings is not None else self.safety_settings
        if effective_safety_settings is None: logger.warning(f"{log_prefix}: No safety settings; API defaults apply."); effective_safety_settings = []
        model_instance = genai.GenerativeModel(model_name=model_to_use, generation_config=effective_gen_config, safety_settings=effective_safety_settings) # type: ignore
        sdk_response, sdk_error_result = self._execute_sdk_call(model_instance, api_contents or [], log_prefix)
        if sdk_error_result: result.update(sdk_error_result)
        else: result.update(self._process_sdk_response(sdk_response, log_prefix))
        result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        logger.info(f"{log_prefix}: Query finished. Status: '{result['status']}'. Latency: {result['latency_ms']}ms.")
        return result