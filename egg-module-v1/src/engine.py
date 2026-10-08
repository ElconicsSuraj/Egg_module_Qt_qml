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

from src.drivers.candling import CandlingLED
from src.drivers.heartbeat import HeartbeatSensorDriver

logger = logging.getLogger(__name__)

# Standardized import for hardware
try:
    from src.drivers.hx711 import HX711
    HAS_HARDWARE = True
except Exception as e:
    logger.warning(f"Hardware import failed (running in simulated/no-hardware mode): {e}")
    HAS_HARDWARE = False


class EggModuleEngine:
    """
    Core logic engine for the Egg Module.
    Handles AI loops, camera management, weight sensor, candling LED, and heartbeat screening.
    """
    def __init__(self, callback_metrics, callback_image, callback_heartbeat=None):
        self._running = True
        self.callback_metrics = callback_metrics
        self.callback_image = callback_image
        self.callback_heartbeat = callback_heartbeat or (lambda: None)
        
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

        # Load-cell gravimetric calibration state
        self.weight_cal_status = "Idle"     # "Idle" | "Taring" | "AwaitingLoad" | "Sampling" | "Done" | "Error"
        self._weight_cal_known_g = 0.0
        self._weight_cal_ref_unit = None

        self._tare_requested = False
        self._session_entries = []
        self._cal_buffer = []
        self._cal_known_l = 0.0
        self._cal_known_w = 0.0

        # Shared state between camera and inference threads
        self._latest_frame = None
        self._latest_inference = None
        self._inference_lock = threading.Lock()

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
                # Load persisted gravimetric calibration if available; else use hard-coded default
                import json as _json
                _weight_cal_path = os.path.join(
                    os.path.dirname(self.config.calibration_file), "weight_calibration.json"
                )
                _default_ref_unit = -840
                if os.path.exists(_weight_cal_path):
                    try:
                        with open(_weight_cal_path) as _f:
                            _wc = _json.load(_f)
                        _default_ref_unit = _wc.get("reference_unit", _default_ref_unit)
                        logger.info(f"Load-cell: loaded persisted reference_unit={_default_ref_unit} from {_weight_cal_path}")
                    except Exception as _e:
                        logger.warning(f"Could not read weight_calibration.json: {_e}")
                self.hx.set_reference_unit(_default_ref_unit)
                self.hx.tare()
            except Exception as e:
                logger.error(f"Hardware init failed: {e}")
                self.hx = None

        self.candling_led = CandlingLED(pin=self.config.candling_led_pin)
        self.candling_state = False

        self.heartbeat_driver = HeartbeatSensorDriver(
            sensor_pin=self.config.heartbeat_sensor_pin,
            led_pin=self.config.heartbeat_led_pin
        )

        # --- Start Threads ---
        threading.Thread(target=self._camera_loop, daemon=True).start()
        threading.Thread(target=self._inference_loop, daemon=True).start()
        threading.Thread(target=self._weight_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_notify_loop, daemon=True).start()

    def toggle_candling(self):
        self.candling_state = self.candling_led.toggle()
        return self.candling_state

    def start_heartbeat_screening(self):
        self.heartbeat_driver.start()

    def stop_heartbeat_screening(self):
        self.heartbeat_driver.stop()

    def stop(self):
        self._running = False
        if hasattr(self, "heartbeat_driver"):
            self.heartbeat_driver.cleanup()
        if hasattr(self, "candling_led"):
            self.candling_led.cleanup()
        if self.camera:
            self.camera.release()

    def _heartbeat_notify_loop(self):
        while self._running:
            if self.heartbeat_driver.active:
                self.callback_heartbeat()
            time.sleep(0.05)

    def _camera_loop(self):
        """Fast loop: captures frames and pushes to UI at camera rate (~30fps).
        Does NOT run YOLO — draws overlay from the last inference result."""
        while self._running:
            ret, frame = self.camera.read_frame_latest()
            connected = ret and frame is not None
            if connected != self.camera_connected:
                self.camera_connected = connected

            if not connected:
                time.sleep(0.05)
                continue

            self._latest_frame = frame

            # Draw overlay using last known inference result (non-blocking)
            df = frame.copy()
            with self._inference_lock:
                m = self._latest_inference
            if m and not m.get("is_hand", False):
                self.overlay.draw_egg(df, m["result"])

            rgb = cv2.cvtColor(df, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            self.latest_qimage = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
            self.callback_image()

            time.sleep(0.033)  # ~30 fps cap

    def _inference_loop(self):
        """Slow loop: runs YOLO inference and updates metrics at model speed."""
        frame_count = 0
        while self._running:
            frame = self._latest_frame
            if frame is None:
                time.sleep(0.05)
                continue

            m = self.measurement_engine.measure_frame(frame)
            self.measurement_engine.update_state(m)

            with self._inference_lock:
                self._latest_inference = m

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

            frame_count += 1
            if frame_count % 3 == 0:
                self.callback_metrics()

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

    # ------------------------------------------------------------------
    # Load-Cell Gravimetric Calibration
    # ------------------------------------------------------------------
    def start_weight_calibration(self, known_weight_g: float):
        """
        Initiate a two-phase gravimetric calibration of the HX711 load cell.
        Phase 1: Tare (empty plate).
        Phase 2: Apply traceable mass, acquire raw ADC samples, derive reference_unit.
        """
        self._weight_cal_known_g = known_weight_g
        self._weight_cal_ref_unit = None
        threading.Thread(target=self._weight_cal_sequence, daemon=True).start()

    def _weight_cal_sequence(self):
        """Background thread: tare → wait for UI confirmation → sample → persist."""
        import json

        if not self.hx:
            self.weight_cal_status = "Error: No load-cell hardware detected."
            self.callback_metrics()
            return

        # --- Phase 1: Tare (empty plate) ---
        self.weight_cal_status = "Taring"
        self.callback_metrics()
        try:
            self.hx.set_reference_unit(1)   # raw ADC mode
            self.hx.tare()
        except Exception as exc:
            self.weight_cal_status = f"Error: Tare failed — {exc}"
            self.callback_metrics()
            return

        # --- Phase 2: Await known mass placement (UI signals via flag) ---
        self.weight_cal_status = "AwaitingLoad"
        self.callback_metrics()

        # Spin-wait until the UI sets the flag
        while self.weight_cal_status == "AwaitingLoad":
            time.sleep(0.1)

        if self.weight_cal_status != "Sampling":
            return  # User cancelled

        # --- Phase 3: Acquire raw ADC samples ---
        time.sleep(1.0)  # Allow load to stabilise
        raw_readings = []
        for _ in range(15):
            try:
                raw_readings.append(self.hx.get_value(5))
            except Exception:
                pass
            time.sleep(0.3)

        if len(raw_readings) < 5:
            self.weight_cal_status = "Error: Insufficient ADC samples. Check sensor wiring."
            self.callback_metrics()
            return

        raw_avg = sum(raw_readings) / len(raw_readings)
        ref_unit = raw_avg / self._weight_cal_known_g
        self._weight_cal_ref_unit = ref_unit

        # Apply immediately to live HX711 instance
        try:
            self.hx.set_reference_unit(ref_unit)
            self.hx.tare()  # Re-zero with correct scale factor
        except Exception as exc:
            self.weight_cal_status = f"Error: Apply failed — {exc}"
            self.callback_metrics()
            return

        # Persist to sidecar file alongside calibration_data.json
        try:
            cal_dir = os.path.dirname(self.config.calibration_file)
            weight_cal_path = os.path.join(cal_dir, "weight_calibration.json")
            payload = {
                "reference_unit": round(ref_unit, 4),
                "known_weight_g": self._weight_cal_known_g,
                "raw_avg_adc": round(raw_avg, 2),
                "sample_count": len(raw_readings),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            with open(weight_cal_path, "w") as fh:
                json.dump(payload, fh, indent=2)
            logger.info(f"Load-cell calibration saved → reference_unit={ref_unit:.2f}  ({weight_cal_path})")
        except Exception as exc:
            logger.warning(f"Could not persist weight calibration: {exc}")

        self.weight_cal_status = "Done"
        self.callback_metrics()
