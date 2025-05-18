import logging
import time
import json
from typing import Optional, Dict, Any, Union

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
# Removed direct import of SafetySetting, HarmCategory from google.generativeai.types

from PIL import Image
import cv2 # For BGR to RGB conversion
import numpy as np

logger = logging.getLogger(__name__)

# Default safety settings - Attempt to define using genai module attributes.
# If this fails, we will fall back to a dictionary format or let the SDK use its defaults.
DEFAULT_SAFETY_SETTINGS_TYPED = []
DEFAULT_SAFETY_SETTINGS_DICT = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
EFFECTIVE_SAFETY_SETTINGS = [] # This will be populated in __init__

try:
    # Check if the types are available directly under genai module for the installed SDK version
    if hasattr(genai, 'SafetySetting') and hasattr(genai, 'HarmCategory'):
        logger.info("Found genai.SafetySetting and genai.HarmCategory. Using typed safety settings.")
        DEFAULT_SAFETY_SETTINGS_TYPED = [
            genai.SafetySetting(harm_category=genai.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold="BLOCK_MEDIUM_AND_ABOVE"),
            genai.SafetySetting(harm_category=genai.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold="BLOCK_MEDIUM_AND_ABOVE"),
            genai.SafetySetting(harm_category=genai.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold="BLOCK_MEDIUM_AND_ABOVE"),
            genai.SafetySetting(harm_category=genai.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold="BLOCK_MEDIUM_AND_ABOVE"),
        ]
        EFFECTIVE_SAFETY_SETTINGS = DEFAULT_SAFETY_SETTINGS_TYPED
    else:
        # Fallback for older versions or different structuring: try importing from google.ai.generativelanguage (proto types)
        # This is a common location for these enums.
        try:
            from google.ai.generativelanguage import SafetySetting as ProtoSafetySetting
            from google.ai.generativelanguage import HarmCategory as ProtoHarmCategory
            logger.info("Found SafetySetting and HarmCategory in google.ai.generativelanguage (protos). Using proto typed safety settings.")
            DEFAULT_SAFETY_SETTINGS_TYPED = [
                ProtoSafetySetting(category=ProtoHarmCategory.HARM_CATEGORY_HARASSMENT, threshold=ProtoSafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                ProtoSafetySetting(category=ProtoHarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=ProtoSafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                ProtoSafetySetting(category=ProtoHarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=ProtoSafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                ProtoSafetySetting(category=ProtoHarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=ProtoSafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
            ]
            EFFECTIVE_SAFETY_SETTINGS = DEFAULT_SAFETY_SETTINGS_TYPED
        except ImportError:
            logger.warning("Could not import SafetySetting/HarmCategory from genai or google.ai.generativelanguage. Will attempt dictionary format for safety settings.")
            EFFECTIVE_SAFETY_SETTINGS = DEFAULT_SAFETY_SETTINGS_DICT
except Exception as e_safety_setup: # Catch any other unexpected error during safety setup
    logger.error(f"Unexpected error during safety settings definition: {e_safety_setup}. Falling back to dictionary format or SDK defaults.", exc_info=True)
    EFFECTIVE_SAFETY_SETTINGS = DEFAULT_SAFETY_SETTINGS_DICT


# Default generation config
DEFAULT_GENERATION_CONFIG = GenerationConfig(
    # Examples:
    # temperature=0.7,
    # max_output_tokens=2048, # Default varies by model
)


class GeminiAnalyzer:
    """
    Handles all communication with the Google Gemini API for advanced visual understanding.
    Responsible for sending image data and prompts, and parsing responses.
    """

    def __init__(self, api_key: str, default_model_name: str = "gemini-1.5-flash-latest"):
        """
        Initializes the GeminiAnalyzer.

        Args:
            api_key: The Google Gemini API key.
            default_model_name: The default Gemini model to use (e.g., "gemini-1.5-flash-latest").
        """
        self.api_key = api_key
        self.default_model_name = default_model_name
        self.client_initialized = False
        self.safety_settings_to_use = EFFECTIVE_SAFETY_SETTINGS # Use the globally determined effective settings

        if not self.api_key:
            logger.error("GeminiAnalyzer: API key is missing. Gemini features will be disabled.")
            return

        try:
            genai.configure(api_key=self.api_key)
            self.client_initialized = True
            logger.info(f"GeminiAnalyzer initialized. Default model: '{self.default_model_name}'. API client configured.")
            if not self.safety_settings_to_use: # If EFFECTIVE_SAFETY_SETTINGS ended up empty
                logger.warning("No specific safety settings could be constructed; SDK will use its defaults.")
            elif self.safety_settings_to_use == DEFAULT_SAFETY_SETTINGS_DICT:
                 logger.info("Using dictionary format for safety settings passed to Gemini model.")
            else:
                 logger.info("Using typed object format for safety settings passed to Gemini model.")


        except Exception as e:
            logger.error(f"GeminiAnalyzer: Failed to configure Gemini API client: {e}", exc_info=True)

    def query_vision_model(
        self, image_data: np.ndarray, prompt: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Queries a Gemini vision model with an image and a prompt.

        Args:
            image_data: The image (NumPy array in BGR format).
            prompt: The text prompt to send with the image.
            model_name: Optional specific Gemini model name to use, overriding the default.

        Returns:
            A dictionary containing the outcome:
            {
                "status": "success" | "error" | "blocked_prompt" | "blocked_response",
                "text_content": "Full text response from Gemini, or None.",
                "json_content": {parsed JSON object if applicable, else None},
                "error_message": "Error details if status is 'error', else None",
                "model_used": "model_name_actually_queried",
                "latency_ms": 1234
            }
        """
        start_time = time.perf_counter()
        model_to_use = model_name if model_name else self.default_model_name
        result: Dict[str, Any] = {
            "status": "error",
            "text_content": None,
            "json_content": None,
            "error_message": "Unknown error",
            "model_used": model_to_use,
            "latency_ms": 0,
        }

        if not self.client_initialized:
            result["error_message"] = "Gemini API client not initialized (e.g., missing API key)."
            logger.error("query_vision_model: Attempted to query but client not initialized.")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        if image_data is None or image_data.size == 0:
            result["error_message"] = "Image data is None or empty."
            logger.error(f"query_vision_model for model '{model_to_use}': {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        if image_data.ndim != 3 or image_data.shape[2] != 3:
            result["error_message"] = f"Image data is not a valid BGR image. Shape: {image_data.shape}"
            logger.error(f"query_vision_model for model '{model_to_use}': {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        if not prompt:
            result["error_message"] = "Prompt cannot be empty."
            logger.error(f"query_vision_model for model '{model_to_use}': {result['error_message']}")
            result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
            return result

        try:
            pil_image = Image.fromarray(cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB))
            logger.info(
                f"Querying Gemini model '{model_to_use}'. Prompt (summary): '{prompt[:70].replace(chr(10), ' ')}...'. "
                f"Image size: {pil_image.width}x{pil_image.height}"
            )

            model_instance_args = {
                "model_name": model_to_use,
                "generation_config": DEFAULT_GENERATION_CONFIG
            }
            if self.safety_settings_to_use: # Only pass safety_settings if we have some defined
                model_instance_args["safety_settings"] = self.safety_settings_to_use
            else:
                logger.warning(f"No effective safety settings defined for model '{model_to_use}'. SDK defaults will apply.")


            model_instance = genai.GenerativeModel(**model_instance_args)
            
            contents = [prompt, pil_image]
            # Use stream=False for a single, complete response object.
            response = model_instance.generate_content(contents, stream=False)

            # Check for prompt blocking first (if available in response structure for non-streaming)
            # For non-streaming, prompt_feedback might be present on the main response object.
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                result["status"] = "blocked_prompt"
                block_reason_name = response.prompt_feedback.block_reason.name if hasattr(response.prompt_feedback.block_reason, 'name') else str(response.prompt_feedback.block_reason)
                safety_ratings_str = str(response.prompt_feedback.safety_ratings) if response.prompt_feedback.safety_ratings else "N/A"
                result["error_message"] = (
                    f"Prompt blocked by API. Reason: {block_reason_name}. "
                    f"Safety ratings: {safety_ratings_str}"
                )
                logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            # Check candidates for content and finish reason
            if not response.candidates:
                 result["status"] = "error" 
                 result["error_message"] = "No candidates in response. The prompt might have been blocked, or another API issue occurred."
                 logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
                 result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                 return result

            first_candidate = response.candidates[0]
            finish_reason_name = "UNKNOWN"
            if hasattr(first_candidate, 'finish_reason'):
                if hasattr(first_candidate.finish_reason, 'name'): # Enum-like
                    finish_reason_name = first_candidate.finish_reason.name
                else: # String or int
                    finish_reason_name = str(first_candidate.finish_reason)
            
            # For some SDK versions/models, finish_reason might be an int: 0=Unspecified, 1=Stop, 2=Max Tokens, 3=Safety, 4=Recitation, 5=Other
            # We primarily care if it's NOT "STOP" (or 1 if it's int).
            is_normal_stop = (finish_reason_name == "STOP") or (finish_reason_name == "1")


            if not is_normal_stop: 
                result["status"] = "blocked_response" # Treat non-STOP as a form of block/failure
                safety_ratings_str = str(first_candidate.safety_ratings) if hasattr(first_candidate, 'safety_ratings') and first_candidate.safety_ratings else 'N/A'
                result["error_message"] = (
                    f"Response generation did not finish normally. Reason: {finish_reason_name}. "
                    f"Safety ratings: {safety_ratings_str}"
                )
                # Try to get text even if blocked, it might have partial info or error details
                if hasattr(first_candidate, 'content') and first_candidate.content and hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                    text_parts = [part.text for part in first_candidate.content.parts if hasattr(part, 'text')]
                    result["text_content"] = "".join(text_parts) if text_parts else None
                logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            # Successful response processing
            if hasattr(first_candidate, 'content') and first_candidate.content and hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                text_parts = [part.text for part in first_candidate.content.parts if hasattr(part, 'text')]
                result["text_content"] = "".join(text_parts) if text_parts else None
            else: 
                result["text_content"] = None
                logger.warning(f"Gemini query for model '{model_to_use}': Normal stop, but no content parts found in the first candidate.")


            if result["text_content"]:
                try:
                    potential_json = json.loads(result["text_content"])
                    result["json_content"] = potential_json
                    logger.debug(f"Gemini response for model '{model_to_use}' successfully parsed as JSON.")
                except json.JSONDecodeError:
                    logger.debug(f"Gemini response for model '{model_to_use}' is not valid JSON. Text content: '{result['text_content'][:100].replace(chr(10), ' ')}...'")
                    result["json_content"] = None

            result["status"] = "success"
            result["error_message"] = None
            text_snippet = (result["text_content"][:100].replace(chr(10), ' ') + "...") if result["text_content"] else "None"
            logger.info(f"Gemini query for model '{model_to_use}' successful. Response snippet: '{text_snippet}'.")

        # More specific exceptions from the SDK can be caught here
        except genai.types.BlockedPromptException as e_blocked_prompt: # In case it's raised despite prompt_feedback check
            result["status"] = "blocked_prompt"
            result["error_message"] = f"Gemini API: Prompt was blocked by exception. Details: {e_blocked_prompt}"
            logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
        except genai.types.StopCandidateException as e_stop_candidate: 
            result["status"] = "blocked_response" 
            result["error_message"] = f"Gemini API: Response generation stopped unexpectedly by exception. Details: {e_stop_candidate}"
            logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
        # Catch other google.api_core.exceptions which might indicate issues like auth, quota, etc.
        except Exception as e: 
            error_type = type(e).__name__
            # Check for specific API core exceptions if possible, e.g., from google.api_core.exceptions
            # For example, if 'google.api_core.exceptions.PermissionDenied' etc.
            if "PermissionDenied" in error_type:
                result["error_message"] = f"Gemini API Permission Denied: {e}. Check API key and project permissions."
            elif "ResourceExhausted" in error_type:
                result["error_message"] = f"Gemini API Resource Exhausted (Quota likely exceeded): {e}."
            elif "DeadlineExceeded" in error_type:
                result["error_message"] = f"Gemini API Deadline Exceeded (Timeout): {e}."
            else:
                result["error_message"] = f"Gemini API call failed ({error_type}): {e}"
            
            logger.error(f"Gemini query for model '{model_to_use}' failed. Error: {result['error_message']}", exc_info=True)

        result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        logger.debug(f"Gemini query for model '{model_to_use}' completed. Status: {result['status']}. Latency: {result['latency_ms']}ms.")
        return result

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s')
    TEST_API_KEY = os.getenv("GEMINI_API_KEY_TEST") 
    if not TEST_API_KEY:
        print("GEMINI_API_KEY_TEST environment variable not set. Skipping GeminiAnalyzer direct test.")
        exit()
    
    dummy_image_np = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.putText(dummy_image_np, "Hello", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
    
    analyzer = GeminiAnalyzer(api_key=TEST_API_KEY, default_model_name="gemini-1.5-flash-latest") # Using flash for basic tests

    print("\n--- Test 1: Basic query ---")
    if analyzer.client_initialized:
        response1 = analyzer.query_vision_model(dummy_image_np, "Describe this image briefly.")
        print(f"Response 1: {response1}")
    else:
        print("Skipping Test 1, client not initialized (API key issue?).")

    print("\n--- Test 2: Query with JSON expectation (simulated) ---")
    if analyzer.client_initialized:
        response2 = analyzer.query_vision_model(dummy_image_np, "Describe this image as JSON with a 'description' key and a 'color_of_text' key.")
        print(f"Response 2: {response2}")
    else:
        print("Skipping Test 2, client not initialized.")

    print("\n--- Test 3: Query with empty image ---")
    response3 = analyzer.query_vision_model(np.array([]), "This should fail due to empty image.")
    print(f"Response 3 (empty image): {response3}")

    print("\n--- Test 4: Query with empty prompt ---")
    if analyzer.client_initialized: # Client check is important here
        response4 = analyzer.query_vision_model(dummy_image_np, "")
        print(f"Response 4 (empty prompt): {response4}")
    else:
        print("Skipping Test 4, client not initialized.")
        
    print("\n--- Test 5: Uninitialized client test (e.g. bad API key format during configure) ---")
    analyzer_no_key = GeminiAnalyzer(api_key="INVALID_KEY_FORMAT_SHORT") # Pass an obviously bad key
    response5 = analyzer_no_key.query_vision_model(dummy_image_np, "This should also fail due to client not initialized.")
    print(f"Response 5 (bad key init): {response5}")

    print("\n--- Test 6: Test with a different model override ---")
    if analyzer.client_initialized:
        # Make sure 'gemini-1.0-pro' is a valid model you can access; otherwise, this specific test might fail on model not found.
        # For this general test, using flash again to ensure it runs if pro isn't set up for key.
        response6 = analyzer.query_vision_model(dummy_image_np, "Is there text in this image?", model_name="gemini-1.5-flash-latest") # or "gemini-pro-vision" if accessible
        print(f"Response 6 (model override to flash): {response6}")
    else:
        print("Skipping Test 6, client not initialized.")