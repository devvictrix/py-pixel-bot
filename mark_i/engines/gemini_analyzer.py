import logging
import time
import json  # For parsing JSON responses from Gemini
from typing import Optional, Dict, Any, Union, List
import os  # For os.linesep for log formatting

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, SafetySetting, HarmCategory, Part  # More specific imports
from google.generativeai.types import BlockedPromptException, StopCandidateException  # For specific error handling
from google.api_core import exceptions as google_api_exceptions  # For more granular API error handling


from PIL import Image  # For converting NumPy array to PIL Image for Gemini SDK
import cv2  # For BGR to RGB conversion before creating PIL Image
import numpy as np

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_analyzer")

# Default safety settings for Gemini API calls.
# These aim to block potentially harmful content at a medium threshold.
DEFAULT_SAFETY_SETTINGS: List[SafetySetting] = [
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]

# Default generation configuration for Gemini API calls.
# These can be overridden on a per-query basis if needed.
DEFAULT_GENERATION_CONFIG = GenerationConfig(
    # temperature=0.7, # Example: Controls randomness (0.0-1.0). Higher is more creative.
    # top_p=1.0,       # Example: Nucleus sampling.
    # top_k=1,         # Example: Limits selection to top K tokens.
    # max_output_tokens=2048, # Model-dependent default, can be specified.
    # stop_sequences=[]  # Sequences that will stop generation.
)


class GeminiAnalyzer:
    """
    Handles all communication with the Google Gemini API.
    It is responsible for sending prompts (text-only or multimodal with images)
    to specified Gemini models, parsing the responses, and handling API errors.
    This module is used by RulesEngine (for gemini_vision_query),
    GeminiDecisionModule (for NLU and step-specific visual analysis),
    and StrategyPlanner/ProfileGenerator (for AI Profile Generation).
    """

    def __init__(self, api_key: str, default_model_name: str = "gemini-1.5-flash-latest"):
        """
        Initializes the GeminiAnalyzer.

        Args:
            api_key: The Google Gemini API key. Must not be None or empty.
            default_model_name: The default Gemini model to use for queries if not overridden
                                (e.g., "gemini-1.5-flash-latest", "gemini-1.5-pro-latest",
                                 or a text-specific model like "gemini-pro" for text-only tasks).
        """
        self.api_key = api_key
        self.default_model_name = default_model_name
        self.client_initialized = False
        self.safety_settings = DEFAULT_SAFETY_SETTINGS
        self.generation_config = DEFAULT_GENERATION_CONFIG

        if not self.api_key or not isinstance(self.api_key, str):
            logger.critical("GeminiAnalyzer CRITICAL ERROR: API key is missing or invalid. Gemini features will be non-functional.")
            # Do not attempt to configure genai without a valid key.
            return

        try:
            genai.configure(api_key=self.api_key)
            self.client_initialized = True
            logger.info(f"GeminiAnalyzer initialized. Default model: '{self.default_model_name}'. API client configured successfully.")
            # Log safety settings and generation config more clearly
            safety_settings_log = [(s.harm_category.name, s.threshold.name) for s in self.safety_settings if hasattr(s.harm_category, "name") and hasattr(s.threshold, "name")]
            logger.debug(f"Using default safety settings: {safety_settings_log}")
            logger.debug(f"Using default generation config: {self.generation_config}")
        except Exception as e:
            self.client_initialized = False  # Ensure state is false on any configuration failure
            logger.critical(f"GeminiAnalyzer CRITICAL FAILURE: Could not configure Gemini API client with provided key: {e}. Gemini features will be disabled.", exc_info=True)

    def query_vision_model(
        self,
        prompt: str,
        image_data: Optional[np.ndarray] = None,  # BGR NumPy array
        model_name_override: Optional[str] = None,
        custom_generation_config: Optional[GenerationConfig] = None,
        custom_safety_settings: Optional[List[SafetySetting]] = None,
    ) -> Dict[str, Any]:
        """
        Queries a Gemini model with a text prompt and an optional image.
        Handles both multimodal and potentially text-only model interactions.

        Args:
            prompt: The text prompt to send. Mandatory.
            image_data: Optional. The image (NumPy array in BGR format) for multimodal queries.
                        If None, a text-only prompt is assumed.
            model_name_override: Optional specific Gemini model name to use.
            custom_generation_config: Optional GenerationConfig to override defaults.
            custom_safety_settings: Optional List of SafetySettings to override defaults.

        Returns:
            A dictionary containing the outcome with detailed status and data.
            See TECHNICAL_DESIGN.MD Section 10.2 for the full structure.
            Key status values: "success", "error_api", "error_client", "error_input",
                               "blocked_prompt", "blocked_response", "error_parsing_response".
        """
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

        api_contents: List[Union[str, Image.Image, Part]] = [prompt]  # Prompt is always part of contents
        if pil_image_for_sdk:
            api_contents.append(pil_image_for_sdk)  # Append image if it's a multimodal query

        prompt_summary_for_log = (prompt[:150].replace(os.linesep, " ") + "...") if len(prompt) > 153 else prompt.replace(os.linesep, " ")
        logger.info(f"{log_prefix}: Sending query. Prompt summary: '{prompt_summary_for_log}'. Image provided: {pil_image_for_sdk is not None}.")

        try:
            effective_gen_config = custom_generation_config if custom_generation_config else self.generation_config
            effective_safety_settings = custom_safety_settings if custom_safety_settings else self.safety_settings

            model_instance = genai.GenerativeModel(model_name=model_to_use, generation_config=effective_gen_config, safety_settings=effective_safety_settings)

            api_sdk_response = model_instance.generate_content(api_contents, stream=False)
            result["raw_gemini_response"] = str(api_sdk_response)  # Store string representation for simpler logging

            if hasattr(api_sdk_response, "prompt_feedback") and api_sdk_response.prompt_feedback and api_sdk_response.prompt_feedback.block_reason:
                result["status"] = "blocked_prompt"
                block_reason = api_sdk_response.prompt_feedback.block_reason
                result["error_message"] = (
                    f"Prompt blocked by API. Reason: {block_reason.name if hasattr(block_reason,'name') else str(block_reason)}. Ratings: {api_sdk_response.prompt_feedback.safety_ratings}"
                )
                logger.warning(f"{log_prefix}: {result['error_message']}")
            elif not api_sdk_response.candidates:
                result["status"] = "error_api"  # Or potentially "blocked_prompt" if that's how SDK signals it
                result["error_message"] = "No candidates in Gemini response. Prompt might have been silently blocked or another API error occurred."
                logger.warning(f"{log_prefix}: {result['error_message']}")
            else:
                first_candidate = api_sdk_response.candidates[0]
                # Use getattr for finish_reason as its presence might vary or be None
                finish_reason_val = getattr(first_candidate, "finish_reason", None)

                # SDK uses HarmCategory.HarmCategory.STOP or string "STOP"
                is_normal_stop = (isinstance(finish_reason_val, HarmCategory) and finish_reason_val == HarmCategory.STOP) or (
                    isinstance(finish_reason_val, str) and finish_reason_val.upper() == "STOP"
                )

                if not is_normal_stop and finish_reason_val is not None:  # If not normal stop and reason is present
                    result["status"] = "blocked_response"
                    safety_ratings_str = str(getattr(first_candidate, "safety_ratings", "N/A"))
                    result["error_message"] = (
                        f"Response generation stopped. Reason: {finish_reason_val.name if hasattr(finish_reason_val,'name') else str(finish_reason_val)}. Safety: {safety_ratings_str}"
                    )
                    logger.warning(f"{log_prefix}: {result['error_message']}")
                    if hasattr(first_candidate, "content") and first_candidate.content and first_candidate.content.parts:
                        result["text_content"] = "".join(part.text for part in first_candidate.content.parts if hasattr(part, "text")).strip()
                elif finish_reason_val is None and not hasattr(first_candidate, "content"):  # No finish reason and no content, likely error
                    result["status"] = "error_api"
                    result["error_message"] = "Response candidate had no finish_reason and no content. API error or unexpected state."
                    logger.warning(f"{log_prefix}: {result['error_message']}")
                else:  # Normal STOP or cases where content might still be present
                    result["status"] = "success"
                    if hasattr(first_candidate, "content") and first_candidate.content and first_candidate.content.parts:
                        result["text_content"] = "".join(part.text for part in first_candidate.content.parts if hasattr(part, "text")).strip()
                    else:
                        result["text_content"] = ""
                        if is_normal_stop:  # Only log as info if it was a normal stop but no text
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

                    if result["status"] == "success":  # Re-check status as it might have changed
                        logger.info(
                            f"{log_prefix}: Query successful. Text snippet: '{result['text_content'][:100].replace(os.linesep, ' ')}...'. JSON detected: {result['json_content'] is not None}."
                        )

        except BlockedPromptException as e_bp:
            result["status"] = "blocked_prompt"
            result["error_message"] = f"Gemini SDK: Prompt blocked. {e_bp}"
            result["raw_gemini_response"] = str(e_bp)
            logger.warning(f"{log_prefix}: {result['error_message']}")
        except StopCandidateException as e_sc:  # This often means content was blocked by safety
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
