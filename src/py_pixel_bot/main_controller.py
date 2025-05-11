import logging
import threading
import time
import os 

from .engines.capture_engine import CaptureEngine
from .engines.analysis_engine import AnalysisEngine
from .engines.rules_engine import RulesEngine 

logger = logging.getLogger(__name__)

class MainController:
    def __init__(self, config: dict, 
                 capture_engine: CaptureEngine, 
                 analysis_engine: AnalysisEngine, 
                 rules_engine: RulesEngine):
        self.config = config 
        self.capture_engine = capture_engine
        self.analysis_engine = analysis_engine
        self.rules_engine = rules_engine 
        
        self._running = False
        self._monitor_thread = None
        self._stop_event = threading.Event()
        
        settings = self.config.get("settings", {})
        self.monitoring_interval = float(settings.get("monitoring_interval_seconds", 1.0))
        self.regions_to_monitor = self.config.get("regions", []) 
        logger.info(f"MainController initialized. Interval: {self.monitoring_interval}s. Regions: {len(self.regions_to_monitor)}")

    def _monitoring_loop(self):
        logger.info(f"Monitoring loop started in thread: {threading.current_thread().name}")
        try:
            while not self._stop_event.is_set():
                loop_start_time = time.perf_counter()
                logger.debug("--- Loop Iteration Start ---")
                current_iteration_analysis_results_with_images = {} 
                if not self.regions_to_monitor:
                    logger.debug("No regions configured.")
                    self._stop_event.wait(timeout=self.monitoring_interval)
                    continue
                for region_spec in self.regions_to_monitor:
                    region_name = region_spec.get("name")
                    if not region_name: logger.warning(f"Skipping region with no name: {region_spec}"); continue
                    logger.debug(f"Processing region: '{region_name}'")
                    region_data_packet = {"capture_error": True, "region_spec": region_spec, "captured_image": None}
                    current_iteration_analysis_results_with_images[region_name] = region_data_packet
                    captured_image = self.capture_engine.capture_region(
                        region_spec.get("x",0), region_spec.get("y",0),
                        region_spec.get("width",1), region_spec.get("height",1)
                    )
                    if captured_image is None: logger.warning(f"Capture failed for region: '{region_name}'."); continue
                    region_data_packet["capture_error"] = False
                    region_data_packet["captured_image"] = captured_image
                    region_data_packet["captured_image_shape"] = captured_image.shape
                    avg_color = self.analysis_engine.analyze_average_color(captured_image)
                    if avg_color is not None: region_data_packet["average_color"] = avg_color
                    ocr_text = self.analysis_engine.ocr_extract_text(captured_image)
                    if ocr_text is not None: region_data_packet["ocr_text"] = ocr_text
                    logger.debug(f"General analysis complete for region: '{region_name}'.")
                if current_iteration_analysis_results_with_images:
                    self.rules_engine.evaluate_rules(current_iteration_analysis_results_with_images)
                else: logger.debug("No region data generated.")
                logger.debug("--- Loop Iteration End ---")
                loop_duration = time.perf_counter() - loop_start_time
                sleep_time = self.monitoring_interval - loop_duration
                if sleep_time > 0: self._stop_event.wait(timeout=sleep_time)
                else:
                    if self.monitoring_interval > 0: logger.warning(f"Loop iteration ({loop_duration:.3f}s) exceeded interval ({self.monitoring_interval:.3f}s).")
                    if not self._stop_event.is_set(): time.sleep(0.001)
        except Exception as e:
            logger.critical(f"Critical error in monitoring loop thread: {e}", exc_info=True)
        finally:
            self._running = False
            logger.info(f"Monitoring loop thread ({threading.current_thread().name}) terminated.")

    def start_monitoring(self):
        if self._running: logger.warning("Monitoring is already running."); return
        logger.info("Starting monitoring thread...")
        self._stop_event.clear()
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.name = "MonitoringThread"
        self._monitor_thread.start()
        logger.info(f"Monitoring thread '{self._monitor_thread.name}' started.")

    def stop_monitoring(self):
        if not self._running and not (self._monitor_thread and self._monitor_thread.is_alive()):
            logger.info("Monitoring not running or thread already stopped."); return
        logger.info("Attempting to stop monitoring thread...")
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            join_timeout = self.monitoring_interval + 2.0 
            self._monitor_thread.join(timeout=join_timeout) 
            if self._monitor_thread.is_alive(): logger.warning(f"Monitoring thread did not stop gracefully within {join_timeout}s.")
            else: logger.info("Monitoring thread stopped successfully.")
        else: logger.info("Monitoring thread not alive/initialized when stop called.")
        self._running = False
        
    def is_running(self) -> bool:
        if self._monitor_thread and not self._monitor_thread.is_alive() and self._running:
            logger.warning("is_running: _running True but thread not alive. Correcting state.")
            self._running = False 
        return self._running

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent 
    if str(project_src_dir) not in sys.path: sys.path.insert(0, str(project_src_dir))
    from py_pixel_bot.core.config_manager import load_environment_variables, ConfigManager
    from py_pixel_bot.core.logging_setup import setup_logging
    class MockEngine:
        def __init__(self, name="MockEngine"): self._name=name; self._logger=logging.getLogger(f"py_pixel_bot.test.{self._name}"); self._logger.info(f"{self._name} initialized (mock).")
    class MockCaptureEngine(MockEngine):
        def capture_region(self,x,y,w,h): self._logger.info(f"MockCapture: Capturing {w}x{h} at ({x},{y})"); import numpy as np; return np.full((h,w,3),[x%256,y%256,(x+y)%256],dtype=np.uint8)
    class MockAnalysisEngine(MockEngine):
        def analyze_average_color(self,img): avg_c=(10,20,30); self._logger.info(f"MockAnalysis: AvgColor->{avg_c}"); return avg_c
        def ocr_extract_text(self,img,lang='eng'): text="mock text"; self._logger.info(f"MockAnalysis: OCR->'{text}'"); return text
    class MockActionExecutor(MockEngine):
         def execute_action(self, action_spec, analysis_results_for_triggering_region=None, target_region_info=None): self._logger.info(f"[MockActionExecutor] Action: {action_spec.get('type')}")
    class MockRulesEngine:
        def __init__(self, action_executor, config_manager, analysis_engine): self._logger=logging.getLogger("py_pixel_bot.test.MockRulesEngine"); self._logger.info("MockRulesEngine init.")
        def evaluate_rules(self, iteration_analysis_results_with_images): self._logger.info(f"MockRulesEngine.evaluate_rules called with regions: {list(iteration_analysis_results_with_images.keys())}")
    load_environment_variables(); setup_logging()
    test_logger_mc = logging.getLogger("py_pixel_bot.main_controller_test"); test_logger_mc.info("--- MainController Test Start ---")
    dummy_profile = {"settings":{"monitoring_interval_seconds":0.3},"regions":[{"name":"tr1","x":1,"y":1,"w":1,"h":1}],"rules":[]}
    mock_config_mgr_for_rules = ConfigManager(profile_name="dummy_test_profile.json"); mock_config_mgr_for_rules.config_data = dummy_profile # Inject data
    controller = MainController(dummy_profile, MockCaptureEngine(), MockAnalysisEngine(), MockRulesEngine(MockActionExecutor(), mock_config_mgr_for_rules, MockAnalysisEngine()))
    controller.start_monitoring(); test_logger_mc.info(f"Controller started. is_running: {controller.is_running()}")
    try: time.sleep(1.0) 
    except KeyboardInterrupt: test_logger_mc.info("Test interrupted.")
    finally: test_logger_mc.info("Stopping controller..."); controller.stop_monitoring()
    test_logger_mc.info(f"Controller stopped. is_running: {controller.is_running()}"); time.sleep(0.2) 
    test_logger_mc.info("--- MainController Test End ---")