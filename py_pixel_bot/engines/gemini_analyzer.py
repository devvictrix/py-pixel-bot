import logging
import os
import time
import json
from typing import Optional, Dict, Any, Union

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, SafetySetting, HarmCategory  # For safety settings
from PIL import Image
import cv2  # For BGR to RGB conversion
import numpy as np

logger = logging.getLogger(__name__)

# Default safety settings - adjust as needed.
# Blocking too aggressively might hinder some UI analysis tasks,
# but unblocking too much has risks if arbitrary screen content is sent.
DEFAULT_SAFETY_SETTINGS = [
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold="BLOCK_MEDIUM_AND_ABOVE"),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold="BLOCK_MEDIUM_AND_ABOVE"),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold="BLOCK_MEDIUM_AND_ABOVE"),
    SafetySetting(harm_category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold="BLOCK_MEDIUM_AND_ABOVE"),
]

# Default generation config - can be overridden if needed
DEFAULT_GENERATION_CONFIG = GenerationConfig(
    # temperature=0.9, # Example: for more creative, less deterministic. For analysis, lower might be better.
    # top_p=1,
    # top_k=1,
    # max_output_tokens=2048, # Default is 2048 for gemini-pro-vision, 8192 for 1.5 flash/pro
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

        if not self.api_key:
            logger.error("GeminiAnalyzer: API key is missing. Gemini features will be disabled.")
            return

        try:
            genai.configure(api_key=self.api_key)
            self.client_initialized = True
            logger.info(f"GeminiAnalyzer initialized. Default model: '{self.default_model_name}'. API client configured.")
        except Exception as e:
            logger.error(f"GeminiAnalyzer: Failed to configure Gemini API client: {e}", exc_info=True)
            # API key might be invalid format or other genai.configure issues.

    def query_vision_model(self, image_data: np.ndarray, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]:
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
            logger.info(f"Querying Gemini model '{model_to_use}'. Prompt (summary): '{prompt[:70].replace(chr(10), ' ')}...'. " f"Image size: {pil_image.width}x{pil_image.height}")

            model = genai.GenerativeModel(model_name=model_to_use, safety_settings=DEFAULT_SAFETY_SETTINGS, generation_config=DEFAULT_GENERATION_CONFIG)

            # For vision models, the content is typically a list: [prompt_string, image_object]
            # Some models might prefer images first or specific structuring.
            # The SDK handles a list of parts for `generate_content`.
            contents = [prompt, pil_image]
            response = model.generate_content(contents)  # type: ignore

            # Check for prompt blocking
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                result["status"] = "blocked_prompt"
                result["error_message"] = f"Prompt blocked by API. Reason: {response.prompt_feedback.block_reason.name}. " f"Safety ratings: {response.prompt_feedback.safety_ratings}"
                logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            # Check for response blocking (safety)
            # A candidate might not exist if the prompt was blocked outright.
            if not response.candidates:
                result["status"] = "error"  # Or blocked_response, but this state means no valid candidate
                result["error_message"] = "No candidates in response. Prompt might have been blocked without detailed feedback or other API issue."
                logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            first_candidate = response.candidates[0]
            if first_candidate.finish_reason.name != "STOP":  # e.g., SAFETY, RECITATION, MAX_TOKENS, OTHER
                result["status"] = "blocked_response"  # Treat non-STOP as a form of block/failure
                result["error_message"] = (
                    f"Response generation did not finish normally. Reason: {first_candidate.finish_reason.name}. "
                    f"Safety ratings: {first_candidate.safety_ratings if first_candidate.safety_ratings else 'N/A'}"
                )
                # Try to get text even if blocked, it might have partial info or error details
                if first_candidate.content and first_candidate.content.parts:
                    text_parts = [part.text for part in first_candidate.content.parts if hasattr(part, "text")]
                    result["text_content"] = "".join(text_parts) if text_parts else None
                logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
                result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
                return result

            # Successful response processing
            if first_candidate.content and first_candidate.content.parts:
                # Concatenate text from all parts that have text
                text_parts = [part.text for part in first_candidate.content.parts if hasattr(part, "text")]
                result["text_content"] = "".join(text_parts) if text_parts else None
            else:  # Should not happen if finish_reason is STOP, but guard
                result["text_content"] = None

            if result["text_content"]:
                try:
                    # Attempt to parse as JSON if the text content seems like it might be JSON
                    # A more robust check might involve trying to parse only if prompt explicitly asked for JSON.
                    # For now, always attempt if text_content is present.
                    potential_json = json.loads(result["text_content"])
                    result["json_content"] = potential_json
                    logger.debug(f"Gemini response for model '{model_to_use}' successfully parsed as JSON.")
                except json.JSONDecodeError:
                    # Not an error if it's not JSON, just means json_content remains None
                    logger.debug(f"Gemini response for model '{model_to_use}' is not valid JSON. Text content: '{result['text_content'][:100]}...'")
                    result["json_content"] = None  # Explicitly set to None

            result["status"] = "success"
            result["error_message"] = None  # Clear any default error message
            text_snippet = (result["text_content"][:100].replace(chr(10), " ") + "...") if result["text_content"] else "None"
            logger.info(f"Gemini query for model '{model_to_use}' successful. Response snippet: '{text_snippet}'.")

        except genai.types.BlockedPromptException as e_blocked_prompt:
            result["status"] = "blocked_prompt"
            result["error_message"] = f"Gemini API: Prompt was blocked. Details: {e_blocked_prompt}"
            logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
        except genai.types.StopCandidateException as e_stop_candidate:  # Should be caught by finish_reason check now
            result["status"] = "blocked_response"  # Or error depending on finish_reason
            result["error_message"] = f"Gemini API: Response generation stopped unexpectedly. Details: {e_stop_candidate}"
            logger.warning(f"Gemini query for model '{model_to_use}': {result['error_message']}")
        except Exception as e:  # Catch other google.api_core.exceptions and general errors
            # More specific exceptions from google.api_core.exceptions could be caught here
            # e.g., ResourceExhausted, PermissionDenied, InvalidArgument, DeadlineExceeded, InternalServerError
            error_type = type(e).__name__
            result["error_message"] = f"Gemini API call failed ({error_type}): {e}"
            logger.error(f"Gemini query for model '{model_to_use}' failed. Error: {result['error_message']}", exc_info=True)
            # Do not log the full exception 'e' to logs if it might contain sensitive info from API response/request

        result["latency_ms"] = int((time.perf_counter() - start_time) * 1000)
        logger.debug(f"Gemini query for model '{model_to_use}' completed. Status: {result['status']}. Latency: {result['latency_ms']}ms.")
        return result


if __name__ == "__main__":
    # This basic test requires a GEMINI_API_KEY environment variable to be set.
    # And a sample image file (e.g., 'sample_image.png') in the same directory.
    # For a real test, you'd integrate with ConfigManager to get the API key.

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s")

    # --- Configuration for Test ---
    TEST_API_KEY = os.getenv("GEMINI_API_KEY_TEST")  # Use a separate test key if possible
    if not TEST_API_KEY:
        print("GEMINI_API_KEY_TEST environment variable not set. Skipping GeminiAnalyzer direct test.")
        exit()

    # Create a dummy image for testing
    dummy_image_np = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.putText(dummy_image_np, "Hello", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)  # Yellow text on black

    # --- Test Scenarios ---
    analyzer = GeminiAnalyzer(api_key=TEST_API_KEY, default_model_name="gemini-1.5-flash-latest")

    print("\n--- Test 1: Basic query ---")
    if analyzer.client_initialized:
        response1 = analyzer.query_vision_model(dummy_image_np, "Describe this image briefly.")
        print(f"Response 1: {response1}")
    else:
        print("Skipping Test 1, client not initialized.")

    print("\n--- Test 2: Query with JSON expectation (simulated) ---")
    if analyzer.client_initialized:
        # This prompt is unlikely to return actual JSON unless the model is very specifically tuned or instructed.
        # This tests the JSON parsing attempt.
        response2 = analyzer.query_vision_model(dummy_image_np, "Describe this image as JSON with a 'description' key.")
        print(f"Response 2: {response2}")
    else:
        print("Skipping Test 2, client not initialized.")

    print("\n--- Test 3: Query with empty image ---")
    response3 = analyzer.query_vision_model(np.array([]), "This should fail.")
    print(f"Response 3: {response3}")

    print("\n--- Test 4: Query with empty prompt ---")
    if analyzer.client_initialized:
        response4 = analyzer.query_vision_model(dummy_image_np, "")
        print(f"Response 4: {response4}")
    else:
        print("Skipping Test 4, client not initialized.")

    print("\n--- Test 5: Uninitialized client test (e.g. bad API key initially) ---")
    analyzer_no_key = GeminiAnalyzer(api_key="")  # Pass empty API key
    response5 = analyzer_no_key.query_vision_model(dummy_image_np, "This should also fail due to no key.")
    print(f"Response 5 (no key): {response5}")
