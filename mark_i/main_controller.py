import logging
import threading
import time
from typing import Dict, Any, Optional, Set
import os

from mark_i.core.config_manager import ConfigManager
from mark_i.engines.capture_engine import CaptureEngine
from mark_i.engines.analysis_engine import AnalysisEngine
from mark_i.engines.rules_engine import RulesEngine
from mark_i.engines.action_executor import ActionExecutor
from mark_i.engines.gemini_decision_module import GeminiDecisionModule  # For NLU tasks

# Standardized logger for this module
from mark_i.core.logging_setup import APP_ROOT_LOGGER_NAME

logger = logging.getLogger(f"{APP_ROOT_LOGGER_NAME}.main_controller")


class MainController:
    """
    Orchestrates the main bot operation loop: Capture -> Analyze (selectively) -> Evaluate Rules -> Act.
    Runs the monitoring loop in a separate thread.
    """

    def __init__(self, profile_name_or_path: str):
        """
        Initializes the MainController.

        Args:
            profile_name_or_path: The name or path of the profile to load.
        """
        logger.info(f"Initializing MainController with profile: '{profile_name_or_path}'")

        try:
            self.config_manager = ConfigManager(profile_name_or_path)
        except FileNotFoundError:
            logger.critical(f"MainController: Profile file '{profile_name_or_path}' not found. Cannot initialize.")
            raise  # Re-raise for CLI or caller to handle
        except ValueError as e_val:  # Handles JSONDecodeError from ConfigManager
            logger.critical(f"MainController: Profile file '{profile_name_or_path}' is invalid: {e_val}. Cannot initialize.")
            raise
        except IOError as e_io:  # Handles other read errors
            logger.critical(f"MainController: IO error loading profile '{profile_name_or_path}': {e_io}. Cannot initialize.")
            raise

        profile_data = self.config_manager.get_profile_data()

        settings = profile_data.get("settings", {})
        ocr_command = settings.get("tesseract_cmd_path")
        ocr_config = settings.get("tesseract_config_custom", "")
        self.dominant_colors_k = settings.get("analysis_dominant_colors_k", 3)
        if not isinstance(self.dominant_colors_k, int) or self.dominant_colors_k <= 0:
            logger.warning(f"Invalid 'analysis_dominant_colors_k' ({self.dominant_colors_k}). Defaulting to 3.")
            self.dominant_colors_k = 3

        self.capture_engine = CaptureEngine()
        self.analysis_engine = AnalysisEngine(ocr_command=ocr_command, ocr_config=ocr_config)
        self.action_executor = ActionExecutor(self.config_manager)

        # Initialize GeminiDecisionModule if Gemini API key is available
        self.gemini_decision_module: Optional[GeminiDecisionModule] = None
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            # GeminiAnalyzer for GDM uses the same key and default model from settings
            gemini_analyzer_for_gdm = GeminiAnalyzer(api_key=gemini_api_key, default_model_name=self.config_manager.get_setting("gemini_default_model_name", "gemini-1.5-flash-latest"))
            if gemini_analyzer_for_gdm.client_initialized:
                self.gemini_decision_module = GeminiDecisionModule(
                    gemini_analyzer=gemini_analyzer_for_gdm, action_executor=self.action_executor, config_manager=self.config_manager  # GDM needs CM for region context
                )
                logger.info("MainController: GeminiDecisionModule initialized for NLU tasks.")
            else:
                logger.warning("MainController: GeminiAnalyzer for GeminiDecisionModule failed initialization. NLU tasks may fail.")
        else:
            logger.warning("MainController: GEMINI_API_KEY not found. GeminiDecisionModule not initialized. NLU tasks ('gemini_perform_task') will be skipped or fail.")

        # RulesEngine is initialized here, passing the optional GeminiDecisionModule
        self.rules_engine = RulesEngine(self.config_manager, self.analysis_engine, self.action_executor, gemini_decision_module=self.gemini_decision_module)  # Pass it here

        self.monitoring_interval = settings.get("monitoring_interval_seconds", 1.0)
        if not isinstance(self.monitoring_interval, (int, float)) or self.monitoring_interval <= 0:
            logger.warning(f"Invalid 'monitoring_interval_seconds' ({self.monitoring_interval}). Defaulting to 1.0s.")
            self.monitoring_interval = 1.0

        self.regions_to_monitor = profile_data.get("regions", [])

        if not self.regions_to_monitor:
            logger.warning(f"Profile '{profile_name_or_path}' has no regions defined. Bot runtime might be limited.")
        else:
            logger.info(f"MainController will monitor {len(self.regions_to_monitor)} regions every {self.monitoring_interval:.2f} seconds.")

        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        logger.info(f"MainController initialized successfully for profile: '{self.config_manager.get_profile_path()}'.")

    def _perform_monitoring_cycle(self):
        """
        Performs a single cycle of capturing, selectively analyzing, and rule evaluation.
        """
        if not self.regions_to_monitor:
            logger.debug("No regions configured to monitor in this cycle. Skipping.")
            return

        all_region_data: Dict[str, Dict[str, Any]] = {}
        logger.info(f"----- Starting new monitoring cycle (Interval: {self.monitoring_interval:.2f}s) -----")

        for region_spec in self.regions_to_monitor:
            region_name = region_spec.get("name")
            if not region_name:
                logger.warning(f"Skipping region due to missing name in spec: {region_spec}")
                continue

            logger.debug(f"Processing region: '{region_name}'")
            captured_image_bgr = self.capture_engine.capture_region(region_spec)
            region_data_packet: Dict[str, Any] = {"image": captured_image_bgr}

            if captured_image_bgr is not None:
                logger.debug(f"Image captured for region '{region_name}'. Shape: {captured_image_bgr.shape}")
                required_analyses: Set[str] = self.rules_engine.get_analysis_requirements_for_region(region_name)
                logger.debug(f"Region '{region_name}': Required pre-emptive analyses: {required_analyses or 'None'}")

                if "average_color" in required_analyses:
                    avg_color = self.analysis_engine.analyze_average_color(captured_image_bgr, region_name_context=region_name)
                    region_data_packet["average_color"] = avg_color
                    # logger.debug(f"Rgn '{region_name}': AvgColor: {avg_color}") # Logged by AnalysisEngine
                if "ocr" in required_analyses:
                    ocr_result = self.analysis_engine.ocr_extract_text(captured_image_bgr, region_name_context=region_name)
                    region_data_packet["ocr_analysis_result"] = ocr_result
                    # logger.debug(f"Rgn '{region_name}': OCR performed.") # Logged by AnalysisEngine
                if "dominant_color" in required_analyses:
                    dominant_colors_result = self.analysis_engine.analyze_dominant_colors(captured_image_bgr, num_colors=self.dominant_colors_k, region_name_context=region_name)
                    region_data_packet["dominant_colors_result"] = dominant_colors_result
                    # logger.debug(f"Rgn '{region_name}': DomColor (k={self.dominant_colors_k}) performed.") # Logged by AnalysisEngine
            else:
                logger.warning(f"Image capture failed for region '{region_name}'. No analysis performed.")
                region_data_packet["average_color"] = None
                region_data_packet["ocr_analysis_result"] = None
                region_data_packet["dominant_colors_result"] = None

            all_region_data[region_name] = region_data_packet
            logger.debug(f"Data collected for rgn '{region_name}'. Keys: {list(region_data_packet.keys())}")

        if all_region_data:
            logger.debug(f"Passing data for {len(all_region_data)} region(s) to RulesEngine.")
            self.rules_engine.evaluate_rules(all_region_data)
        else:
            logger.info("No region data collected. Skipping rule evaluation.")

        logger.info("----- Monitoring cycle finished -----")

    def run_monitoring_loop(self):
        """
        Continuously monitors regions, analyzes, and acts based on rules.
        This method is intended to be run in a separate thread.
        """
        profile_display_name = os.path.basename(self.config_manager.get_profile_path() or "UnspecifiedProfile")
        logger.info(f"Monitoring loop started for profile '{profile_display_name}'. Interval: {self.monitoring_interval:.2f}s.")
        cycle_count = 0
        try:
            while not self._stop_event.is_set():
                cycle_count += 1
                logger.debug(f"Monitoring loop - Cycle #{cycle_count} starting...")
                cycle_start_time = time.perf_counter()

                self._perform_monitoring_cycle()

                cycle_end_time = time.perf_counter()
                elapsed_time = cycle_end_time - cycle_start_time
                logger.debug(f"Monitoring loop - Cycle #{cycle_count} completed in {elapsed_time:.3f}s.")

                wait_time = self.monitoring_interval - elapsed_time
                if wait_time > 0:
                    logger.debug(f"Monitoring loop - Cycle #{cycle_count}: Waiting for {wait_time:.3f}s.")
                    interrupted_during_wait = self._stop_event.wait(timeout=wait_time)
                    if interrupted_during_wait:
                        logger.info("Monitoring loop: Stop event received during wait.")
                        break
                else:
                    logger.warning(f"Monitoring loop - Cycle #{cycle_count}: Took {elapsed_time:.3f}s (>= interval {self.monitoring_interval:.2f}s). Next cycle immediate.")
                    if self._stop_event.is_set():
                        logger.info("Monitoring loop: Stop event detected after long cycle.")
                        break
        except Exception as e:
            logger.critical("Critical error in monitoring loop. Terminating.", exc_info=True)
        finally:
            logger.info(f"Monitoring loop for '{profile_display_name}' stopped after {cycle_count} cycle(s).")

    def start(self):
        """Starts the monitoring loop in a new thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Monitoring loop already running. Start command ignored.")
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self.run_monitoring_loop, daemon=True)
        self._monitor_thread.name = f"MonitoringThread-{os.path.basename(self.config_manager.get_profile_path() or 'NewProfile')}"
        logger.info(f"Starting monitoring thread: {self._monitor_thread.name}")
        self._monitor_thread.start()

    def stop(self):
        """Signals the monitoring loop to stop and waits for the thread to join."""
        if not self._monitor_thread or not self._monitor_thread.is_alive():
            logger.info("Monitoring loop not running or already stopped.")
            return

        logger.info(f"Attempting to stop monitoring thread: {self._monitor_thread.name}...")
        self._stop_event.set()
        join_timeout = self.monitoring_interval + 5.0
        logger.debug(f"Waiting up to {join_timeout:.1f}s for monitoring thread to join...")
        self._monitor_thread.join(timeout=join_timeout)

        if self._monitor_thread.is_alive():
            logger.warning(f"Monitoring thread {self._monitor_thread.name} did not stop in {join_timeout:.1f}s. May be stuck.")
        else:
            logger.info(f"Monitoring thread {self._monitor_thread.name} successfully stopped and joined.")
        self._monitor_thread = None
