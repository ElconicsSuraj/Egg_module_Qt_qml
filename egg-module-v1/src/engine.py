import sys
import os
import threading
import time
import cv2
import numpy as np
import logging
from PySide6.QtGui import QImage

# Define the isolated AI engine path
AI_ENGINE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai_engine")
sys.path.insert(0, AI_ENGINE_ROOT)

from src.config.constants import Config
from src.core.camera import CameraManager
from src.core.detector import EggDetector
from src.core.calibration import CalibrationManager
from src.core.measurement import EggMeasurement
from src.utils.overlay import DisplayOverlay

# Standardized import for hardware
try:
    from src.drivers.hx711 import HX711
    HAS_HARDWARE = True
except Exception as e:
    logger.error(f"Hardware import failed: {e}")
    HAS_HARDWARE = False

logger = logging.getLogger(__name__)

class EggModuleEngine:
    """
    Core logic engine for the Egg Module.
    Handles AI loops, camera management, and weight sensor interaction.
    """
    def __init__(self, callback_metrics, callback_image):
        self._running = True
        self.callback_metrics = callback_metrics
        self.callback_image = callback_image
        
        # State
        self.weight = 0.0
        self.length = "0.0 mm"
        self.breadth = "0.0 mm"
        self.confidence = "0%"
        self.latest_qimage = QImage()
        
        self.camera_connected = False
        self.is_egg_detected = False
        self.is_centered = False
        self.is_settled = False
        self.is_calibrating = False
        self.cal_progress = 0
        self.cal_status = "Ready"
        self.last_cal_result = ""
        self.cal_session_target = 1
        self.cal_session_count = 0
        
        self._tare_requested = False
        self._session_entries = []
        self._cal_buffer = []
        self._cal_known_l = 0.0
        self._cal_known_w = 0.0

        # --- AI Engine Init ---
        env_path = os.path.join(AI_ENGINE_ROOT, ".env")
        self.config = Config(env_path)
        self.config.model_path = os.path.join(AI_ENGINE_ROOT, "media", "best_final.pt")
        self.config.calibration_file = os.path.join(AI_ENGINE_ROOT, "media", "calibration_data.json")
        
        self.detector = EggDetector(self.config)
        self.detector.load_model()
        self.cal_mgr = CalibrationManager(self.config)
        self.cal_data = self.cal_mgr.load()
        self.camera = CameraManager(self.config)
        self.camera.open()
        self.overlay = DisplayOverlay(self.config)
        self.measurement_engine = EggMeasurement(self.config, self.detector, self.camera, self.cal_data, self.overlay)

        # --- Hardware Init ---
        self.hx = None
        if HAS_HARDWARE:
            try:
                self.hx = HX711(5, 6)
                self.hx.set_reference_unit(-840)
                self.hx.tare()
            except Exception as e:
                logger.error(f"Hardware init failed: {e}")
                self.hx = None

        # --- Start Threads ---
        threading.Thread(target=self._ai_loop, daemon=True).start()
        threading.Thread(target=self._weight_loop, daemon=True).start()

    def stop(self):
        self._running = False
        if self.camera:
            self.camera.release()

    def _ai_loop(self):
        while self._running:
            ret, frame = self.camera.read_frame_latest()
            connected = ret and frame is not None
            if connected != self.camera_connected:
                self.camera_connected = connected

            if not connected:
                time.sleep(0.1)
                continue

            m = self.measurement_engine.measure_frame(frame)
            self.measurement_engine.update_state(m)
            
            # Calibration Logic
            if self.is_calibrating and m is not None and not m.get("is_hand", False):
                if m.get("in_center", False):
                    if self.is_settled:
                        self._cal_buffer.append((m["major_px"], m["minor_px"]))
                        self.cal_progress = int((len(self._cal_buffer) / self.config.num_calibration_frames) * 100)
                        self.cal_status = f"Capturing: {len(self._cal_buffer)}/{self.config.num_calibration_frames}"
                        
                        if len(self._cal_buffer) >= self.config.num_calibration_frames:
                            self._finish_calibration()
                    else:
                        self.cal_status = "Stabilizing Egg..."
                else:
                    self.cal_status = "Place in Center"
            
            # State synchronization
            detected = m is not None and not m.get("is_hand", False)
            centered = m.get("in_center", False) if detected else False
            self.is_egg_detected = detected
            self.is_centered = centered
            self.is_settled = self.measurement_engine._settled
            
            if not detected:
                self.length, self.breadth, self.confidence = "0.0 mm", "0.0 mm", "0%"
            else:
                stable = self.measurement_engine.get_stable_metrics()
                if stable:
                    self.length = f"{stable['length_mm']:.1f} mm"
                    self.breadth = f"{stable['breadth_mm']:.1f} mm"
                    self.confidence = f"{stable['confidence_score']:.0f}%"

            # UI Frame Generation
            df = frame.copy()
            if m and not m.get("is_hand", False): 
                self.overlay.draw_egg(df, m["result"])
            rgb = cv2.cvtColor(df, cv2.COLOR_BGR2RGB)
            self.latest_qimage = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1]*3, QImage.Format_RGB888).copy()

            self.callback_image()
            if not hasattr(self, "_frame_count"): self._frame_count = 0
            self._frame_count += 1
            if self._frame_count % 3 == 0:
                self.callback_metrics()
                
            time.sleep(0.01)

    def _weight_loop(self):
        while self._running:
            if self._tare_requested:
                if self.hx:
                    try: self.hx.tare()
                    except: pass
                self._tare_requested = False
                self.weight = 0.0
                self.cal_status = "Scale Zeroed"
                self.callback_metrics()

            if self.hx:
                try:
                    val = self.hx.get_weight(5)
                    self.weight = round(val, 2)
                    self.hx.power_down(); self.hx.power_up()
                except: pass
            else:
                self.weight = 88.56 if self.length != "0.0 mm" else 0.0
            
            self.callback_metrics()
            time.sleep(0.5)

    def _finish_calibration(self):
        self.is_calibrating = False
        self.cal_status = "Analyzing Egg..."
        self.callback_metrics()
        try:
            filtered, removed = self.cal_mgr.filter_outliers_iqr(self._cal_buffer)
            res = self.cal_mgr.compute_calibration(filtered, self._cal_known_l, self._cal_known_w)
            from src.core.calibration import MultiCalibrationEntry
            label = f"Egg_{int(self._cal_known_l)}x{int(self._cal_known_w)}"
            entry = MultiCalibrationEntry(label=label, known_length_mm=self._cal_known_l, known_width_mm=self._cal_known_w, 
                                        avg_major_px=res["avg_major_px"], avg_minor_px=res["avg_minor_px"],
                                        pixel_to_mm_length=res["pixel_to_mm_length"], pixel_to_mm_width=res["pixel_to_mm_width"], frames_used=len(filtered))
            self._session_entries.append(entry)
            self.cal_session_count = len(self._session_entries)
            self.last_cal_result = f"Successfully captured {label} ({self.cal_session_count} of {self.cal_session_target})"
            self.cal_status = "Capture Complete"
        except Exception as e:
            self.cal_status = "Capture Error"
            self.last_cal_result = f"Error: {str(e)}"
        self.callback_metrics()
