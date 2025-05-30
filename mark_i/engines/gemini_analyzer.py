import logging
import time
import json  # For parsing JSON responses from Gemini
from typing import Optional, Dict, Any, Union, List  # Added List for safety settings type

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, SafetySetting, HarmCategory  # More specific imports

# from google.generativeai.types import BlockedPromptException, StopCandidateException # Specific exceptions if needed

from PIL import Image  # For converting NumPy array to PIL Image for Gemini SDK
import cv2  # For BGR to RGB conversion before creating PIL Image
import numpy as np

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.gemini_analyzer")

# Default safety settings - Defined using the SDK's preferred types
# These aim to block harmful content at a medium threshold.
DEFAULT_SAFETY_SETTINGS: List[SafetySetting] = [
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]
# Note: Some older SDK versions might expect a list of dicts. If issues arise,
# the dictionary format shown in ADR-008 might be a fallback.
# e.g., {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}

# Default generation config (can be customized per query if needed)
DEFAULT_GENERATION_CONFIG = GenerationConfig(
    # temperature=0.7, # Example: Controls randomness, higher is more creative
    # top_p=1.0,
    # top_k=1,
    # max_output_tokens=2048, # Model-dependent default, can be overridden
    # stop_sequences=[] # Sequences that will stop generation
)


class GeminiAnalyzer:
    """
    Handles all communication with the Google Gemini API for advanced visual understanding
    and text-based generation/NLU tasks.
    Responsible for sending image data and/or prompts, and parsing responses.
    """

    def __init__(self, api_key: str, default_model_name: str = "gemini-1.5-flash-latest"):
        """
        Initializes the GeminiAnalyzer.

        Args:
            api_key: The Google Gemini API key.
            default_model_name: The default Gemini model to use for queries
                                (e.g., "gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-pro" for text).
        """
        self.api_key = api_key
        self.default_model_name = default_model_name
        self.client_initialized = False
        self.safety_settings = DEFAULT_SAFETY_SETTINGS
        self.generation_config = DEFAULT_GENERATION_CONFIG

        if not self.api_key:
            logger.critical("GeminiAnalyzer: API key is MISSING. Gemini features will be non-functional.")
            # No point in trying to configure genai if no key.
            return

        try:
            genai.configure(api_key=self.api_key)
            self.client_initialized = True
            logger.info(f"GeminiAnalyzer initialized. Default model: '{self.default_model_name}'. API client configured.")
            logger.debug(f"Using safety settings: {self.safety_settings}")
            logger.debug(f"Using generation config: {self.generation_config}")
        except Exception as e:
            self.client_initialized = False  # Ensure it's false on failure
            logger.critical(f"GeminiAnalyzer: CRITICAL FAILURE to configure Gemini API client: {e}. Gemini features will be disabled.", exc_info=True)

    def query_vision_model(
        self,
        image_data: Optional[np.ndarray],  # BGR NumPy array, can be None for text-only prompts
        prompt: str,
        model_name_override: Optional[str] = None,
        custom_generation_config: Optional[GenerationConfig] = None,
        custom_safety_settings: Optional[List[SafetySetting]] = None,
    ) -> Dict[str, Any]:
        """
        Queries a Gemini model (vision or text) with an optional image and a prompt.

        Args:
            image_data: Optional. The image (NumPy array in BGR format) for multimodal queries.
                        If None, assumes a text-only prompt for a text-capable model.
            prompt: The text prompt to send.
            model_name_override: Optional specific Gemini model name to use, overriding the default.
            custom_generation_config: Optional GenerationConfig to override defaults for this query.
            custom_safety_settings: Optional List of SafetySettings to override defaults for this query.


        Returns:
            A dictionary containing the outcome:
            {
                "status": "success" | "error_api" | "error_client" | "error_input" |
                          "blocked_prompt" | "blocked_response" | "error_parsing_response",
                "text_content": "Full text response from Gemini, or None if error/no text.",
                "json_content": {parsed JSON object if response was valid JSON, else None},
                "error_message": "Error details if status indicates an error, else None.",
                "model_used": "model_name_actually_queried",
                "latency_ms": 1234, # Duration of the API call attempt
                "raw_gemini_response": response_object # The raw response from genai SDK for debugging
            }
        """
        start_time = time.perf_counter()
        model_to_use = model_name_override if model_name_override else self.default_model_name

        result: Dict[str, Any] = {
            "status": "error_client",  # Default to client error if not initialized
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

        if not prompt and image_data is None:  # Must have at least a prompt or an image
            result["status"] = "error_input"
            result["error_message"] = "Input error: Both prompt and image_data cannot be empty/None for a query."
            logger.error(f"{log_prefix}: {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        if image_data is not None:
            if not isinstance(image_data, np.ndarray) or image_data.size == 0:
                result["status"] = "error_input"
                result["error_message"] = "Input error: Provided image_data is invalid (empty or not NumPy array)."
                logger.error(f"{log_prefix}: {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result
            if image_data.ndim != 3 or image_data.shape[2] != 3:
                result["status"] = "error_input"
                result["error_message"] = f"Input error: Provided image_data is not a 3-channel (BGR) image. Shape: {image_data.shape}"
                logger.error(f"{log_prefix}: {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

        pil_image_for_sdk: Optional[Image.Image] = None
        contents: List[Union[str, Image.Image]] = []

        if prompt:
            contents.append(prompt)

        if image_data is not None:
            try:
                # Convert BGR (OpenCV) to RGB, then to PIL Image for Gemini SDK
                img_rgb = cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
                pil_image_for_sdk = Image.fromarray(img_rgb)
                contents.append(pil_image_for_sdk)
                logger.debug(f"{log_prefix}: Prepared image (Size: {pil_image_for_sdk.width}x{pil_image_for_sdk.height}) for API call.")
            except Exception as e_img_prep:
                result["status"] = "error_input"
                result["error_message"] = f"Error preparing image for Gemini: {e_img_prep}"
                logger.error(f"{log_prefix}: {result['error_message']}", exc_info=True)
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

        if not contents:  # Should be caught by earlier check but defensive
            result["status"] = "error_input"
            result["error_message"] = "Input error: No content (prompt or image) to send to Gemini."
            logger.error(f"{log_prefix}: {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        prompt_summary_for_log = (prompt[:70] + "...") if prompt and len(prompt) > 73 else prompt
        logger.info(f"{log_prefix}: Sending query. Prompt summary: '{prompt_summary_for_log}'. Image present: {image_data is not None}.")

        try:
            gen_config = custom_generation_config if custom_generation_config else self.generation_config
            safety_settings_to_use = custom_safety_settings if custom_safety_settings else self.safety_settings

            model_instance = genai.GenerativeModel(model_name=model_to_use, generation_config=gen_config, safety_settings=safety_settings_to_use)

            # Use stream=False for a single, complete response object.
            # This makes parsing simpler than handling streaming chunks.
            api_response = model_instance.generate_content(contents, stream=False)
            result["raw_gemini_response"] = api_response  # Store for debugging

            # Check for prompt blocking first (might be on main response or in feedback)
            if hasattr(api_response, "prompt_feedback") and api_response.prompt_feedback and api_response.prompt_feedback.block_reason:
                result["status"] = "blocked_prompt"
                block_reason_val = api_response.prompt_feedback.block_reason
                # HarmCategory enum has .name, integer value might also be returned by API
                block_reason_name = block_reason_val.name if hasattr(block_reason_val, "name") else str(block_reason_val)
                safety_ratings_str = str(api_response.prompt_feedback.safety_ratings) if api_response.prompt_feedback.safety_ratings else "N/A"
                result["error_message"] = f"Prompt blocked by API. Reason: {block_reason_name}. Safety ratings: {safety_ratings_str}"
                logger.warning(f"{log_prefix}: {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            # Check candidates for content and finish reason
            if not api_response.candidates:
                result["status"] = "error_api"  # Or blocked_prompt if reason available elsewhere
                result["error_message"] = "No candidates in Gemini response. The prompt might have been blocked without explicit feedback, or another API issue occurred."
                logger.warning(f"{log_prefix}: {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            first_candidate = api_response.candidates[0]
            finish_reason_val = getattr(first_candidate, "finish_reason", None)  # Handle if attr missing
            finish_reason_name = finish_reason_val.name if hasattr(finish_reason_val, "name") else str(finish_reason_val)

            # FinishReason enum: UNSPECIFIED, STOP, MAX_TOKENS, SAFETY, RECITATION, OTHER
            is_normal_stop = finish_reason_name == "STOP"

            if not is_normal_stop:
                result["status"] = "blocked_response"  # Treat non-STOP as a form of block/failure
                safety_ratings_str = str(first_candidate.safety_ratings) if hasattr(first_candidate, "safety_ratings") and first_candidate.safety_ratings else "N/A"
                result["error_message"] = f"Response generation did not finish normally. Reason: {finish_reason_name}. Safety ratings: {safety_ratings_str}"
                # Try to get text even if blocked, it might have partial info or error details
                if hasattr(first_candidate, "content") and first_candidate.content and hasattr(first_candidate.content, "parts") and first_candidate.content.parts:
                    text_parts = [part.text for part in first_candidate.content.parts if hasattr(part, "text")]
                    result["text_content"] = "".join(text_parts) if text_parts else None
                logger.warning(f"{log_prefix}: {result['error_message']}. Partial text (if any): {result.get('text_content', '')[:100]}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            # Successful response processing
            if hasattr(first_candidate, "content") and first_candidate.content and hasattr(first_candidate.content, "parts") and first_candidate.content.parts:
                text_parts = [part.text for part in first_candidate.content.parts if hasattr(part, "text")]
                result["text_content"] = "".join(text_parts).strip() if text_parts else ""  # Ensure strip for clean JSON parsing
            else:
                result["text_content"] = ""  # Ensure it's empty string not None if no parts
                logger.warning(f"{log_prefix}: Normal stop, but no content parts found in the first candidate.")

            if result["text_content"]:
                try:
                    # Attempt to parse the entire text content as JSON
                    # Gemini often wraps its JSON in ```json ... ``` markdown.
                    # Basic stripping of common markdown for JSON:
                    cleaned_text_for_json = result["text_content"]
                    if cleaned_text_for_json.startswith("```json"):
                        cleaned_text_for_json = cleaned_text_for_json[7:]
                    if cleaned_text_for_json.startswith("```"):  # Simpler ``` case
                        cleaned_text_for_json = cleaned_text_for_json[3:]
                    if cleaned_text_for_json.endswith("```"):
                        cleaned_text_for_json = cleaned_text_for_json[:-3]
                    cleaned_text_for_json = cleaned_text_for_json.strip()

                    result["json_content"] = json.loads(cleaned_text_for_json)
                    logger.debug(f"{log_prefix}: Response successfully parsed as JSON.")
                except json.JSONDecodeError:
                    logger.debug(f"{log_prefix}: Response text content is not valid JSON. Text (snippet): '{result['text_content'][:100].replace(chr(10), ' ')}...'")
                    result["json_content"] = None  # Ensure it's None if not valid JSON
                except Exception as e_json:  # Catch any other error during JSON processing
                    logger.warning(f"{log_prefix}: Error attempting to parse text_content as JSON: {e_json}", exc_info=True)
                    result["json_content"] = None
            else:  # No text content
                result["json_content"] = None

            result["status"] = "success"
            result["error_message"] = None
            text_snippet = (result["text_content"][:100].replace(chr(10), " ") + "...") if result["text_content"] else "None"
            logger.info(f"{log_prefix}: Query successful. Response text snippet: '{text_snippet}'. JSON detected: {result['json_content'] is not None}.")

        except genai.types.BlockedPromptException as e_blocked_prompt_ex:  # SDK might raise this directly
            result["status"] = "blocked_prompt"
            result["error_message"] = f"Gemini API: Prompt was blocked. Details from SDK: {e_blocked_prompt_ex}"
            logger.warning(f"{log_prefix}: {result['error_message']}")
            result["raw_gemini_response"] = e_blocked_prompt_ex  # Store exception if it has info
        except genai.types.StopCandidateException as e_stop_candidate_ex:
            result["status"] = "blocked_response"
            result["error_message"] = f"Gemini API: Response generation stopped by candidate. Details: {e_stop_candidate_ex}"
            logger.warning(f"{log_prefix}: {result['error_message']}")
            result["raw_gemini_response"] = e_stop_candidate_ex
        except Exception as e_api:  # Catch other google.api_core.exceptions or genai SDK errors
            result["status"] = "error_api"
            error_type_name = type(e_api).__name__
            # Check for specific known exception types for more granular error messages
            if "PermissionDenied" in error_type_name:
                result["error_message"] = f"Gemini API Permission Denied: {e_api}. Check API key validity and project permissions."
            elif "ResourceExhausted" in error_type_name:
                result["error_message"] = f"Gemini API Resource Exhausted (Quota likely exceeded): {e_api}."
            elif "DeadlineExceeded" in error_type_name:
                result["error_message"] = f"Gemini API Deadline Exceeded (Timeout): {e_api}."
            elif "ServiceUnavailable" in error_type_name:
                result["error_message"] = f"Gemini API Service Unavailable: {e_api}. The service might be temporarily down or overloaded."
            elif "InvalidArgument" in error_type_name:  # e.g. bad model name, invalid image format for model
                result["error_message"] = f"Gemini API Invalid Argument: {e_api}. Check model name, prompt/image format, or other parameters."
            else:
                result["error_message"] = f"Gemini API call failed ({error_type_name}): {e_api}"
            logger.error(f"{log_prefix}: API call failed. Error: {result['error_message']}", exc_info=True)
            result["raw_gemini_response"] = str(e_api)  # Store string form of error

        result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        logger.debug(f"{log_prefix}: Query finished. Final Status: {result['status']}. Latency: {result['latency_ms']}ms.")
        return result
