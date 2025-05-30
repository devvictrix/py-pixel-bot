import logging
import abc
from typing import Dict, List, Any, Optional, Tuple, Callable

import numpy as np
import cv2  # For template loading if needed by an evaluator directly

from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.gemini_analyzer import GeminiAnalyzer

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.engines.condition_evaluators")


class ConditionEvaluationResult:
    def __init__(self, met: bool, captured_value: Optional[Any] = None, template_match_info: Optional[Dict[str, Any]] = None):
        self.met = met
        self.captured_value = captured_value
        self.template_match_info = template_match_info


class ConditionEvaluator(abc.ABC):
    def __init__(
        self,
        analysis_engine: AnalysisEngine,
        template_loader_func: Callable[[str, str], Optional[np.ndarray]],
        gemini_analyzer_instance: Optional[GeminiAnalyzer],
        config_settings_getter_func: Callable[[str, Any], Any],
    ):
        self.analysis_engine = analysis_engine
        self._load_template_image_for_rule = template_loader_func
        self.gemini_analyzer_for_query = gemini_analyzer_instance
        self._get_config_setting = config_settings_getter_func

    def _get_pre_analyzed_data(
        self,
        region_data_packet: Dict[str, Any],
        image_np_bgr: Optional[np.ndarray], # This can be None
        data_key_name: str,
        analysis_func: Callable[..., Optional[Any]],
        *args_for_analysis_func: Any,
        log_prefix: str,
    ) -> Optional[Any]:
        data = region_data_packet.get(data_key_name)
        if data is not None:
            # logger.debug(f"{log_prefix}: Using pre-analyzed data for '{data_key_name}'.")
            return data

        # If data is None (not pre-analyzed), perform on-demand analysis.
        # The analysis_func should be able to handle None image_np_bgr if that's a valid input for it.
        # args_for_analysis_func should contain the image (which might be None).
        logger.debug(f"{log_prefix}: Data for '{data_key_name}' not pre-analyzed. Performing on-demand analysis.")
        try:
            data = analysis_func(*args_for_analysis_func)
        except Exception as e_analysis: # pragma: no cover
            logger.error(f"{log_prefix}: On-demand analysis for '{data_key_name}' failed: {e_analysis}", exc_info=True)
            data = None
        
        if image_np_bgr is None and data is None and data_key_name != "always_true": # Log if analysis failed/returned None with no image
             logger.warning(f"{log_prefix}: On-demand analysis for '{data_key_name}' attempted with no image, result is None.")
        return data


    @abc.abstractmethod
    def evaluate(
        self,
        spec: Dict[str, Any],
        region_name: str,
        region_data_packet: Dict[str, Any],
        rule_name_for_context: str,
    ) -> ConditionEvaluationResult:
        pass


class PixelColorEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'pixel_color' (Eval)"
        image_np_bgr = region_data_packet.get("image")
        condition_met = False
        if image_np_bgr is not None:
            rel_x = spec.get("relative_x", 0)
            rel_y = spec.get("relative_y", 0)
            exp_bgr = spec.get("expected_bgr")
            tol = spec.get("tolerance", 0)
            if exp_bgr is not None:
                condition_met = self.analysis_engine.analyze_pixel_color(image_np_bgr, rel_x, rel_y, exp_bgr, tol, region_name_context=f"{rule_name_for_context}/{region_name}")
        else:
            logger.warning(f"{log_prefix}: Image data missing for region. Cannot evaluate.")
        return ConditionEvaluationResult(met=condition_met)


class AverageColorEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'average_color_is' (Eval)"
        image_np_bgr = region_data_packet.get("image")
        condition_met = False
        avg_color_data = self._get_pre_analyzed_data(
            region_data_packet, image_np_bgr, "average_color", self.analysis_engine.analyze_average_color, image_np_bgr, f"{rule_name_for_context}/{region_name}", log_prefix=log_prefix
        )
        exp_bgr = spec.get("expected_bgr")
        tol = spec.get("tolerance", 10)
        if avg_color_data is not None and exp_bgr is not None:
            if isinstance(exp_bgr, list) and len(exp_bgr) == 3 and all(isinstance(c, int) for c in exp_bgr) and isinstance(tol, int):
                condition_met = bool(np.all(np.abs(np.array(avg_color_data) - np.array(exp_bgr)) <= tol)) # Ensure Python bool
                logger.log(logging.INFO if condition_met else logging.DEBUG, f"{log_prefix}: Result={condition_met}. ActualAvg={avg_color_data}, Expected={exp_bgr}, Tol={tol}")
            else: # pragma: no cover
                logger.warning(f"{log_prefix}: Invalid 'expected_bgr' or 'tolerance' in spec: {spec}")
        return ConditionEvaluationResult(met=condition_met)


class TemplateMatchEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'template_match_found' (Eval)"
        image_np_bgr = region_data_packet.get("image")
        condition_met = False
        captured_value = None
        match_info_for_rule_engine: Optional[Dict[str, Any]] = {"found": False}

        tpl_filename = spec.get("template_filename")
        min_conf = float(spec.get("min_confidence", 0.8))

        if image_np_bgr is not None and tpl_filename:
            template_image_np = self._load_template_image_for_rule(tpl_filename, rule_name_for_context)
            if template_image_np is not None:
                match_result = self.analysis_engine.match_template(
                    image_np_bgr, template_image_np, min_conf, region_name_context=f"{rule_name_for_context}/{region_name}", template_name_context=tpl_filename
                )
                if match_result:
                    condition_met = True
                    match_info_for_rule_engine = {"found": True, **match_result, "matched_region_name": region_name}
                    if spec.get("capture_as"):
                        captured_value = {"value": match_result, "_source_region_for_capture_": region_name}
            # else: logger already warns about template load failure
        else:
            if image_np_bgr is None: # pragma: no cover
                logger.warning(f"{log_prefix}: Image data missing for region.")
            if not tpl_filename: # pragma: no cover
                logger.warning(f"{log_prefix}: Template filename missing in spec.")

        return ConditionEvaluationResult(met=condition_met, captured_value=captured_value, template_match_info=match_info_for_rule_engine)


class OcrContainsTextEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'ocr_contains_text' (Eval)"
        image_np_bgr = region_data_packet.get("image")
        condition_met = False
        captured_value = None

        ocr_analysis_data = self._get_pre_analyzed_data(
            region_data_packet, image_np_bgr, "ocr_analysis_result", self.analysis_engine.ocr_extract_text, image_np_bgr, f"{rule_name_for_context}/{region_name}", log_prefix=log_prefix
        )

        if ocr_analysis_data and "text" in ocr_analysis_data:
            ocr_text = ocr_analysis_data.get("text", "")
            ocr_confidence = ocr_analysis_data.get("average_confidence", 0.0)

            text_to_find_param = spec.get("text_to_find")
            case_sensitive_search = spec.get("case_sensitive", False)
            min_ocr_conf_str = spec.get("min_ocr_confidence")

            texts_to_find_list_raw = (
                [s.strip() for s in text_to_find_param.split(",")]
                if isinstance(text_to_find_param, str)
                else [str(s).strip() for s in text_to_find_param] if isinstance(text_to_find_param, list) else []
            )
            # Filter out any truly empty strings from the list after stripping
            texts_to_find_list = [s for s in texts_to_find_list_raw if s]


            min_ocr_conf_float = float(min_ocr_conf_str) if min_ocr_conf_str and str(min_ocr_conf_str).strip() else None

            if texts_to_find_list: # Only proceed if there are non-empty strings to find
                processed_ocr_text = ocr_text if case_sensitive_search else ocr_text.lower()
                text_match_found = any((s_find if case_sensitive_search else s_find.lower()) in processed_ocr_text for s_find in texts_to_find_list)

                if text_match_found and (min_ocr_conf_float is None or ocr_confidence >= min_ocr_conf_float):
                    condition_met = True
                    if spec.get("capture_as"):
                        captured_value = {"value": ocr_text, "_source_region_for_capture_": region_name}
                    logger.info(f"{log_prefix}: MATCHED. Text '{texts_to_find_list}' found. OCR Conf: {ocr_confidence:.1f}%.")
                elif text_match_found:  # Confidence condition failed
                    logger.debug(f"{log_prefix}: Text found, but OCR confidence {ocr_confidence:.1f}% < min {min_ocr_conf_float}%.")
                else:  # Text not found
                    logger.debug(f"{log_prefix}: Text '{texts_to_find_list}' NOT found in OCR output.")
            else:
                logger.warning(f"{log_prefix}: 'text_to_find' is empty or contains only whitespace after processing. Condition fails.")
        elif ocr_analysis_data is None and image_np_bgr is not None: # pragma: no cover
            logger.warning(f"{log_prefix}: OCR analysis failed or returned no data, but image was present.")
        elif image_np_bgr is None: # pragma: no cover
            logger.warning(f"{log_prefix}: Image data missing for region.")

        return ConditionEvaluationResult(met=condition_met, captured_value=captured_value)


class DominantColorEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'dominant_color_matches' (Eval)"
        image_np_bgr = region_data_packet.get("image")
        condition_met = False

        num_colors_k = self._get_config_setting("analysis_dominant_colors_k", 3)
        dominant_colors_data = self._get_pre_analyzed_data(
            region_data_packet, image_np_bgr, "dominant_colors_result", self.analysis_engine.analyze_dominant_colors,
            image_np_bgr, num_colors_k, f"{rule_name_for_context}/{region_name}", log_prefix=log_prefix
        )

        if isinstance(dominant_colors_data, list):
            exp_bgr = spec.get("expected_bgr")
            tol = spec.get("tolerance", 10)
            top_n = spec.get("check_top_n_dominant", 1)
            min_perc = spec.get("min_percentage", 0.0)

            if isinstance(exp_bgr, list) and len(exp_bgr) == 3 and all(isinstance(c, int) for c in exp_bgr):
                for dom_color_info in dominant_colors_data[: min(top_n, len(dominant_colors_data))]:
                    if (
                        isinstance(dom_color_info.get("bgr_color"), list)
                        and np.all(np.abs(np.array(dom_color_info["bgr_color"]) - np.array(exp_bgr)) <= tol)
                        and dom_color_info.get("percentage", 0.0) >= min_perc
                    ):
                        condition_met = True
                        logger.info(f"{log_prefix}: MATCHED. Dominant BGR {dom_color_info['bgr_color']} (Perc: {dom_color_info.get('percentage',0):.1f}%) matches {exp_bgr} within tolerance {tol}.")
                        break
                if not condition_met: # pragma: no cover
                    logger.debug(f"{log_prefix}: No dominant color within top {top_n} matched {exp_bgr} (Tol: {tol}, MinPerc: {min_perc}%). All dom colors: {dominant_colors_data}")
            else: # pragma: no cover
                logger.warning(f"{log_prefix}: Invalid 'expected_bgr' spec: {exp_bgr}")
        elif dominant_colors_data is None and image_np_bgr is not None: # pragma: no cover
            logger.warning(f"{log_prefix}: Dominant color analysis failed or returned no data, but image was present.")
        elif image_np_bgr is None: # pragma: no cover
            logger.warning(f"{log_prefix}: Image data missing for region.")

        return ConditionEvaluationResult(met=condition_met)


class GeminiVisionQueryEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'gemini_vision_query' (Eval)"
        image_np_bgr = region_data_packet.get("image")
        condition_met = False
        captured_value = None

        if self.gemini_analyzer_for_query and image_np_bgr is not None:
            prompt_str = spec.get("prompt")
            model_override = spec.get("model_name")
            if prompt_str:
                gemini_response = self.gemini_analyzer_for_query.query_vision_model(prompt=prompt_str, image_data=image_np_bgr, model_name_override=model_override)
                if gemini_response["status"] == "success":
                    resp_text_content = gemini_response.get("text_content", "") or ""
                    resp_json_content = gemini_response.get("json_content")

                    exp_text_contains_param = spec.get("expected_response_contains")
                    case_sensitive_text_check = spec.get("case_sensitive_response_check", False)
                    exp_texts_list_raw = (
                        [s.strip() for s in exp_text_contains_param.split(",")]
                        if isinstance(exp_text_contains_param, str)
                        else [str(s).strip() for s in exp_text_contains_param] if isinstance(exp_text_contains_param, list) else []
                    )
                    exp_texts_list = [s for s in exp_texts_list_raw if s] # Filter out empty strings

                    text_condition_part_met = not exp_texts_list or any(
                        (s_find if case_sensitive_text_check else s_find.lower()) in (resp_text_content if case_sensitive_text_check else resp_text_content.lower()) for s_find in exp_texts_list
                    )

                    json_path_str = spec.get("expected_response_json_path")
                    expected_json_val_str = spec.get("expected_json_value")
                    json_condition_part_met = True
                    extracted_json_value_for_capture = None

                    if json_path_str and isinstance(json_path_str, str) and resp_json_content is not None:
                        current_json_node = resp_json_content
                        path_is_valid = True
                        try:
                            for key_or_index in json_path_str.strip(".").split("."): # pragma: no branch
                                if isinstance(current_json_node, dict):
                                    current_json_node = current_json_node[key_or_index]
                                elif isinstance(current_json_node, list) and key_or_index.isdigit():
                                    current_json_node = current_json_node[int(key_or_index)]
                                else:
                                    path_is_valid = False
                                    break
                            if path_is_valid:
                                extracted_json_value_for_capture = current_json_node
                        except (KeyError, IndexError, TypeError): # pragma: no cover
                            path_is_valid = False
                        if not path_is_valid: # pragma: no cover
                            json_condition_part_met = False
                        elif expected_json_val_str is not None and str(current_json_node) != expected_json_val_str: # pragma: no cover
                            json_condition_part_met = False
                    elif json_path_str and resp_json_content is None: # pragma: no cover
                        json_condition_part_met = False # Path specified but no JSON to search

                    if text_condition_part_met and json_condition_part_met:
                        condition_met = True
                        if spec.get("capture_as"):
                            if json_path_str and extracted_json_value_for_capture is not None:
                                captured_value = {"value": extracted_json_value_for_capture, "_source_region_for_capture_": region_name}
                            elif resp_json_content is not None:
                                captured_value = {"value": resp_json_content, "_source_region_for_capture_": region_name}
                            else:
                                captured_value = {"value": resp_text_content, "_source_region_for_capture_": region_name}
                        logger.info(f"{log_prefix}: MATCHED. TextCondMet={text_condition_part_met}, JsonCondMet={json_condition_part_met}. Resp snippet: '{resp_text_content[:70]}...'")
                    else: # pragma: no cover
                        logger.debug(
                            f"{log_prefix}: Gemini query conditions NOT MET. TextCondMet={text_condition_part_met}, JsonCondMet={json_condition_part_met}. Resp snippet: '{resp_text_content[:70]}...'"
                        )

                else:  # Gemini query failed # pragma: no cover
                    logger.warning(f"{log_prefix}: Gemini query failed. Status: {gemini_response['status']}, Error: {gemini_response.get('error_message')}")
            else:  # Prompt missing # pragma: no cover
                logger.warning(f"{log_prefix}: 'prompt' missing in spec.")
        else:  # Analyzer or image missing # pragma: no cover
            if not self.gemini_analyzer_for_query:
                logger.error(f"{log_prefix}: GeminiAnalyzer (for query) not available.")
            if image_np_bgr is None:
                logger.warning(f"{log_prefix}: Image data missing for region.")

        return ConditionEvaluationResult(met=condition_met, captured_value=captured_value)


class AlwaysTrueEvaluator(ConditionEvaluator):
    def evaluate(self, spec: Dict, region_name: str, region_data_packet: Dict, rule_name_for_context: str) -> ConditionEvaluationResult:
        log_prefix = f"R '{rule_name_for_context}', Rgn '{region_name}', Cond 'always_true' (Eval)"
        logger.debug(f"{log_prefix}: Condition is 'always_true', returning True.")
        return ConditionEvaluationResult(met=True)