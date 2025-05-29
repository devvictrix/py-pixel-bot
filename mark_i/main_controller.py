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

logger = logging.getLogger(__name__)
# Ensure APP_ROOT_LOGGER_NAME is defined if used for hierarchical logging (e.g. in main or logging_setup)
# For now, assume __name__ resolves correctly under mark_i


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
        self.config_manager = ConfigManager(profile_name_or_path)  # This will load or raise error
        profile_data = self.config_manager.get_profile_data()  # Already validated by ConfigManager

        settings = profile_data.get("settings", {})
        ocr_command = settings.get("tesseract_cmd_path")  # Optional path to Tesseract
        ocr_config = settings.get("tesseract_config_custom", "")  # Custom Tesseract config string
        self.dominant_colors_k = settings.get("analysis_dominant_colors_k", 3)
        if not isinstance(self.dominant_colors_k, int) or self.dominant_colors_k <= 0:
            logger.warning(f"Invalid 'analysis_dominant_colors_k' ({self.dominant_colors_k}) in profile settings. Defaulting to 3.")
            self.dominant_colors_k = 3

        self.capture_engine = CaptureEngine()
        self.analysis_engine = AnalysisEngine(ocr_command=ocr_command, ocr_config=ocr_config)
        self.action_executor = ActionExecutor(self.config_manager)  # ActionExecutor might need ConfigManager for region data
        # RulesEngine is initialized here so it can parse dependencies from the loaded profile
        self.rules_engine = RulesEngine(self.config_manager, self.analysis_engine, self.action_executor)

        self.monitoring_interval = settings.get("monitoring_interval_seconds", 1.0)
        if not isinstance(self.monitoring_interval, (int, float)) or self.monitoring_interval <= 0:
            logger.warning(f"Invalid 'monitoring_interval_seconds' ({self.monitoring_interval}) in profile. Defaulting to 1.0s.")
            self.monitoring_interval = 1.0

        self.regions_to_monitor = profile_data.get("regions", [])

        if not self.regions_to_monitor:
            logger.warning(f"Profile '{profile_name_or_path}' has no regions defined to monitor. Bot may not perform many actions.")
        else:
            logger.info(f"MainController will monitor {len(self.regions_to_monitor)} regions every {self.monitoring_interval:.2f} seconds.")

        if self.dominant_colors_k > 0:
            logger.info(f"Dominant color analysis will use k={self.dominant_colors_k} if required by rules.")

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

        all_region_data: Dict[str, Dict[str, Any]] = {}  # Stores data for all processed regions this cycle
        logger.info(f"----- Starting new monitoring cycle (Interval: {self.monitoring_interval:.2f}s) -----")

        for region_spec in self.regions_to_monitor:
            region_name = region_spec.get("name")
            if not region_name:
                logger.warning(f"Skipping region due to missing name in spec: {region_spec}")
                continue

            logger.debug(f"Processing region: '{region_name}'")
            captured_image = self.capture_engine.capture_region(region_spec)
            # Always include the image (or None if capture failed) in the packet.
            # RulesEngine on-demand analyses (pixel, template) need this.
            region_data_packet: Dict[str, Any] = {"image": captured_image}

            if captured_image is not None:
                logger.debug(f"Image captured for region '{region_name}'. Shape: {captured_image.shape}")
                # Determine which analyses are needed for THIS region based on rules
                required_analyses: Set[str] = self.rules_engine.get_analysis_requirements_for_region(region_name)
                logger.debug(f"Region '{region_name}': Required pre-emptive analyses by rules: {required_analyses if required_analyses else 'None'}")

                # Perform analyses selectively
                if "average_color" in required_analyses:
                    avg_color = self.analysis_engine.analyze_average_color(captured_image)
                    region_data_packet["average_color"] = avg_color  # Store result (can be None if analysis failed)
                    logger.debug(f"Region '{region_name}': Performed average_color analysis (required). Result: {avg_color}")
                else:
                    logger.debug(f"Region '{region_name}': Skipped average_color analysis (not required by rules).")

                if "ocr" in required_analyses:
                    ocr_result = self.analysis_engine.ocr_extract_text(captured_image, region_name_context=region_name)
                    region_data_packet["ocr_analysis_result"] = ocr_result  # Store dict or None
                    # Logging for OCR result (text snippet, confidence) is done within analysis_engine
                    logger.debug(f"Region '{region_name}': Performed OCR analysis (required).")
                else:
                    logger.debug(f"Region '{region_name}': Skipped OCR analysis (not required by rules).")

                if "dominant_color" in required_analyses:
                    dominant_colors_result = self.analysis_engine.analyze_dominant_colors(
                        captured_image, num_colors=self.dominant_colors_k, region_name_context=region_name  # Use k from profile settings
                    )
                    region_data_packet["dominant_colors_result"] = dominant_colors_result  # Store list or None
                    # Logging for dominant colors is done within analysis_engine
                    logger.debug(f"Region '{region_name}': Performed dominant_color analysis (k={self.dominant_colors_k}) (required).")
                else:
                    logger.debug(f"Region '{region_name}': Skipped dominant_color analysis (not required by rules).")
            else:
                logger.warning(f"Image capture failed for region '{region_name}'. No analysis will be performed for this region in this cycle.")
                # Explicitly set keys to None if RulesEngine fallbacks might expect them,
                # though RulesEngine should also handle key absence.
                region_data_packet["average_color"] = None
                region_data_packet["ocr_analysis_result"] = None
                region_data_packet["dominant_colors_result"] = None

            all_region_data[region_name] = region_data_packet
            logger.debug(f"Finished data collection for region '{region_name}'. Packet keys: {list(region_data_packet.keys())}")

        if all_region_data:
            logger.debug(f"Passing data for {len(all_region_data)} region(s) to RulesEngine for evaluation.")
            self.rules_engine.evaluate_rules(all_region_data)
        else:
            # This might happen if all regions failed to capture or no regions were defined
            logger.info("No region data successfully collected in this cycle. Skipping rule evaluation.")

        logger.info("----- Monitoring cycle finished -----")

    def run_monitoring_loop(self):
        """
        Continuously monitors regions, analyzes, and acts based on rules.
        This method is intended to be run in a separate thread.
        """
        logger.info(f"Monitoring loop started for profile '{self.config_manager.get_profile_path()}'. Interval: {self.monitoring_interval:.2f}s.")
        cycle_count = 0
        try:
            while not self._stop_event.is_set():
                cycle_count += 1
                logger.debug(f"Monitoring loop - Cycle #{cycle_count} starting...")
                cycle_start_time = time.perf_counter()  # Use perf_counter for more precise timing

                self._perform_monitoring_cycle()

                cycle_end_time = time.perf_counter()
                elapsed_time = cycle_end_time - cycle_start_time
                logger.debug(f"Monitoring loop - Cycle #{cycle_count} completed in {elapsed_time:.3f}s.")

                wait_time = self.monitoring_interval - elapsed_time

                if wait_time > 0:
                    logger.debug(f"Monitoring loop - Cycle #{cycle_count}: Waiting for {wait_time:.3f}s before next cycle.")
                    # Wait on the stop_event, allowing interruption
                    # self._stop_event.wait(timeout=wait_time) # This would make the loop iterate only when stop_event is set or timeout
                    # For a fixed interval loop that can be stopped:
                    interrupted_during_wait = self._stop_event.wait(timeout=wait_time)
                    if interrupted_during_wait:  # True if event was set during wait
                        logger.info("Monitoring loop: Stop event received during wait period.")
                        break  # Exit loop immediately
                else:
                    logger.warning(
                        f"Monitoring loop - Cycle #{cycle_count}: Took {elapsed_time:.3f}s, which is longer than or equal to "
                        f"the configured interval of {self.monitoring_interval:.2f}s. Running next cycle immediately."
                    )
                    if self._stop_event.is_set():  # Check again if a long cycle allowed stop event
                        logger.info("Monitoring loop: Stop event detected after a long cycle.")
                        break

        except Exception as e:  # Catch any unexpected errors within the loop itself
            logger.critical("Critical unhandled error in monitoring loop. The loop will now terminate.", exc_info=True)
            # Depending on severity, might want to signal main application or attempt recovery if applicable
        finally:
            logger.info(f"Monitoring loop has been stopped after {cycle_count} cycle(s).")

    def start(self):
        """Starts the monitoring loop in a new thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Monitoring loop is already running. Start command ignored.")
            return

        self._stop_event.clear()  # Clear event in case it was set from a previous run
        self._monitor_thread = threading.Thread(target=self.run_monitoring_loop, daemon=True)
        # Daemon=True means thread will exit when main program exits
        # Consider daemon=False if explicit cleanup in thread is needed on main exit.
        # For now, daemon=True is simpler for Ctrl+C handling in CLI.
        self._monitor_thread.name = f"MonitoringThread-{os.path.basename(self.config_manager.get_profile_path() or 'NewProfile')}"

        logger.info(f"Starting monitoring thread: {self._monitor_thread.name}")
        self._monitor_thread.start()

    def stop(self):
        """Signals the monitoring loop to stop and waits for the thread to join."""
        if not self._monitor_thread or not self._monitor_thread.is_alive():
            logger.info("Monitoring loop is not running or already stopped. Stop command ignored.")
            return

        logger.info(f"Attempting to stop monitoring thread: {self._monitor_thread.name}...")
        self._stop_event.set()  # Signal the loop to stop

        # Wait for the thread to finish its current cycle and exit
        # A timeout is crucial to prevent indefinite blocking if the thread hangs.
        join_timeout = self.monitoring_interval + 5.0  # Give it interval + a bit extra grace period
        logger.debug(f"Waiting up to {join_timeout:.1f}s for monitoring thread to join...")
        self._monitor_thread.join(timeout=join_timeout)

        if self._monitor_thread.is_alive():
            logger.warning(f"Monitoring thread {self._monitor_thread.name} did not stop in the allocated time ({join_timeout:.1f}s). It might be stuck.")
        else:
            logger.info(f"Monitoring thread {self._monitor_thread.name} has successfully stopped and joined.")
        self._monitor_thread = None  # Clear the thread reference
