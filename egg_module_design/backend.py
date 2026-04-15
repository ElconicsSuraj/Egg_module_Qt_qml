import sys
import os
import re
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
import threading
import time
import cv2
import numpy as np

try:
    from hx711 import HX711
    HAS_HARDWARE = True
except Exception as e:
    print(f"[WARNING] Hardware not available: {e}")
    HAS_HARDWARE = False

from PySide6.QtCore import QObject, Signal, Property, Slot
from PySide6.QtGui import QImage

# Define the isolated AI engine path
AI_ENGINE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_engine")
sys.path.insert(0, AI_ENGINE_ROOT)

from src.config.constants import Config
from src.core.camera import CameraManager
from src.core.detector import EggDetector
from src.core.calibration import CalibrationManager
from src.core.measurement import EggMeasurement
from src.utils.overlay import DisplayOverlay

class EggModuleBackend(QObject):
    updateMetrics = Signal()
    imageChanged = Signal()
    calSessionCountChanged = Signal()
    calSessionTargetChanged = Signal()
    wifiListChanged = Signal()
    wifiStatusChanged = Signal()

    def __init__(self):
        super().__init__()

        # --- Placeholder Values ---
        self._weight = 0.0
        self._length = "0.0 mm"
        self._breadth = "0.0 mm"
        self._confidence = "0%"
        self._latest_qimage = QImage()
        self._running = True

        # Smart Guide State
        self._camera_connected = False
        self._is_egg_detected = False
        self._is_centered = False
        self._is_settled = False

        # Calibration State
        self._is_calibrating = False
        self._cal_progress = 0
        self._cal_status = "Ready"
        self._last_cal_result = ""
        
        # Session State
        self._cal_session_target = 1
        self._cal_session_count = 0
        self._session_entries = []
        self._tare_requested = False

        # Wi-Fi State
        self._wifi_list = []
        self._wifi_status = "Idle"

        # --- AI Engine Init ---
        env_path = os.path.join(AI_ENGINE_ROOT, ".env")
        self.config = Config(env_path)
        
        # Point to media folder inside ai_engine
        self.config.model_path = os.path.join(AI_ENGINE_ROOT, "media", "best_final.pt")
        self.config.calibration_file = os.path.join(AI_ENGINE_ROOT, "media", "calibration_data.json")
        
        self.detector = EggDetector(self.config)
        self.detector.load_model()
        self.cal_mgr = CalibrationManager(self.config)
        self.cal_data = self.cal_mgr.load()
        self.camera = CameraManager(self.config)
        self.camera.open()
        self.overlay = DisplayOverlay(self.config)
        self.engine = EggMeasurement(self.config, self.detector, self.camera, self.cal_data, self.overlay)

        # Calibration Buffering
        self._cal_buffer = []
        self._cal_known_l = 0.0
        self._cal_known_w = 0.0

        # --- Hardware Init (Optional) ---
        if HAS_HARDWARE:
            self.hx = HX711(5, 6)
            self.hx.set_reference_unit(-840)
            self.hx.tare()

        # --- Start Threads ---
        threading.Thread(target=self._ai_loop, daemon=True).start()
        threading.Thread(target=self._weight_loop, daemon=True).start()

    def _ai_loop(self):
        while self._running:
            ret, frame = self.camera.read_frame_latest()
            
            # --- Camera Connectivity Check ---
            connected = ret and frame is not None
            if connected != self._camera_connected:
                self._camera_connected = connected

            if not connected:
                time.sleep(0.1)
                continue

            # --- Process Frame ---
            m = self.engine.measure_frame(frame)
            self.engine.update_state(m)
            
            # --- Calibration Logic ---
            if self._is_calibrating and m is not None and not m.get("is_hand", False):
                if m.get("in_center", False):
                    # Robustness: Wait for egg to be settled/stable before capturing
                    if self._is_settled:
                        self._cal_buffer.append((m["major_px"], m["minor_px"]))
                        self._cal_progress = int((len(self._cal_buffer) / self.config.num_calibration_frames) * 100)
                        self._cal_status = f"Capturing: {len(self._cal_buffer)}/{self.config.num_calibration_frames}"
                        
                        if len(self._cal_buffer) >= self.config.num_calibration_frames:
                            self._finish_calibration()
                    else:
                        self._cal_status = "Stabilizing Egg..."
                else:
                    self._cal_status = "Place in Center"
            
            # Update detection flags for Smart Guide
            detected = m is not None and not m.get("is_hand", False)
            centered = m.get("in_center", False) if detected else False
            
            if detected != self._is_egg_detected or centered != self._is_centered:
                self._is_egg_detected = detected
                self._is_centered = centered
            
            if self.engine._settled != self._is_settled:
                self._is_settled = self.engine._settled
            
            if not detected:
                self._length, self._breadth, self._confidence = "0.0 mm", "0.0 mm", "0%"
            else:
                stable = self.engine.get_stable_metrics()
                if stable:
                    self._length = f"{stable['length_mm']:.1f} mm"
                    self._breadth = f"{stable['breadth_mm']:.1f} mm"
                    self._confidence = f"{stable['confidence_score']:.0f}%"

            # UI Frame
            df = frame.copy()
            if m and not m.get("is_hand", False): 
                self.overlay.draw_egg(df, m["result"])
            rgb = cv2.cvtColor(df, cv2.COLOR_BGR2RGB)
            self._latest_qimage = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1]*3, QImage.Format_RGB888).copy()

            # --- 6. End of Loop Signal ---
            # Throttling: Emit metrics every 3 frames (~10Hz) to reduce UI overhead
            # while keeping the video feed at maximum possible framerate.
            if not hasattr(self, "_frame_count"): self._frame_count = 0
            self._frame_count += 1
            
            self.imageChanged.emit()
            if self._frame_count % 3 == 0:
                self.updateMetrics.emit()
                
            time.sleep(0.01) # Reduce wait to let AI loop drive the speed

    @Slot()
    def tareScale(self):
        """Triggers a tare operation in the background weight thread."""
        self._tare_requested = True
        self._cal_status = "Taring Scale..."
        self.updateMetrics.emit()

    def _weight_loop(self):
        while self._running:
            if self._tare_requested:
                if HAS_HARDWARE:
                    try:
                        self.hx.tare()
                    except Exception as e:
                        print(f"[RECOVERABLE] Tare failed: {e}")
                self._tare_requested = False
                self._weight = 0.0
                self._cal_status = "Scale Zeroed"
                self.updateMetrics.emit()

            if HAS_HARDWARE:
                try:
                    val = self.hx.get_weight(5)
                    self._weight = round(val, 2)
                    self.hx.power_down(); self.hx.power_up()
                except Exception as e:
                    pass
            else:
                self._weight = 88.56 if self._length != "0.0 mm" else 0.0
            
            self.updateMetrics.emit()
            time.sleep(0.5)

    # --- Properties for QML ---
    @Property(float, notify=updateMetrics)
    def weight(self): return self._weight
    @Property(str, notify=updateMetrics)
    def length(self): return self._length
    @Property(str, notify=updateMetrics)
    def breadth(self): return self._breadth
    @Property(str, notify=updateMetrics)
    def confidence(self): return self._confidence

    # --- Smart Guide Properties ---
    @Property(bool, notify=updateMetrics)
    def cameraConnected(self): return self._camera_connected
    @Property(bool, notify=updateMetrics)
    def isEggDetected(self): return self._is_egg_detected
    @Property(bool, notify=updateMetrics)
    def isCentered(self): return self._is_centered
    @Property(bool, notify=updateMetrics)
    def isSettled(self): return self._is_settled
    @Property(bool, notify=updateMetrics)
    def isCalibrating(self): return self._is_calibrating
    @Property(int, notify=updateMetrics)
    def calibrationProgress(self): return self._cal_progress
    @Property(str, notify=updateMetrics)
    def calStatus(self): return self._cal_status
    @Property(str, notify=updateMetrics)
    def lastCalResult(self): return self._last_cal_result
    @Property(int, notify=calSessionTargetChanged)
    def calSessionTarget(self): return self._cal_session_target
    @Property(int, notify=calSessionCountChanged)
    def calSessionCount(self): return self._cal_session_count

    @Property(list, notify=wifiListChanged)
    def wifiList(self): return self._wifi_list

    @Property(str, notify=wifiStatusChanged)
    def wifiStatus(self): return self._wifi_status

    @Slot(int)
    def startNewSession(self, targetCount):
        self._cal_session_target = targetCount
        self._cal_session_count = 0
        self._session_entries = []
        self.calSessionTargetChanged.emit()
        self.calSessionCountChanged.emit()
        self._cal_status = "Session Started"
        self.updateMetrics.emit()

    @Slot(float, float)
    def startAutoCalibration(self, knownL, knownW):
        self._cal_known_l = knownL
        self._cal_known_w = knownW
        self._cal_buffer = []
        self._is_calibrating = True
        self._cal_progress = 0
        self._cal_status = f"Egg {self._cal_session_count + 1}: Place in Center"
        self.updateMetrics.emit()

    def _finish_calibration(self):
        self._is_calibrating = False
        self._cal_status = "Analyzing Egg..."
        self.updateMetrics.emit()
        try:
            filtered, removed = self.cal_mgr.filter_outliers_iqr(self._cal_buffer)
            res = self.cal_mgr.compute_calibration(filtered, self._cal_known_l, self._cal_known_w)
            from src.core.calibration import MultiCalibrationEntry
            label = f"Egg_{int(self._cal_known_l)}x{int(self._cal_known_w)}"
            entry = MultiCalibrationEntry(
                label=label,
                known_length_mm=self._cal_known_l,
                known_width_mm=self._cal_known_w,
                avg_major_px=res["avg_major_px"],
                avg_minor_px=res["avg_minor_px"],
                pixel_to_mm_length=res["pixel_to_mm_length"],
                pixel_to_mm_width=res["pixel_to_mm_width"],
                frames_used=len(filtered)
            )
            self._session_entries.append(entry)
            self._cal_session_count = len(self._session_entries)
            self.calSessionCountChanged.emit()
            self._last_cal_result = f"Successfully captured {label} ({self._cal_session_count} of {self._cal_session_target})"
            self._cal_status = "Capture Complete"
        except Exception as e:
            self._cal_status = "Capture Error"
            self._last_cal_result = f"Error: {str(e)}"
        self.updateMetrics.emit()

    @Slot()
    def saveSession(self):
        try:
            library = self.cal_mgr.load_library()
            library.entries = self._session_entries
            self.cal_mgr.save_library(library)
            self.cal_data = self.cal_mgr.load()
            self.engine.cal_data = self.cal_data
            self._cal_status = "Library Updated"
            self._last_cal_result = f"Session complete. {len(self._session_entries)} eggs saved."
        except Exception as e:
            self._cal_status = f"Save Error: {str(e)}"
        self.updateMetrics.emit()

    @Slot(result=str)
    def checkSessionProgress(self):
        if self._cal_session_count < self._cal_session_target:
            return f"You only captured {self._cal_session_count} eggs, but targeted {self._cal_session_target}.\nSave anyway?"
        return "OK"

    @Slot(float, float, result=str)
    def validateCalibration(self, knownL, knownW):
        last_m = self.engine._last_measurement
        if last_m is None or last_m.get("is_hand", False):
            return "No valid egg detected for validation."
        est_l, est_w = self.engine._calculate_mm(last_m["major_px"], last_m["minor_px"])
        diff_l = abs(est_l - knownL)
        diff_w = abs(est_w - knownW)
        if diff_l > 5.0 or diff_w > 5.0:
            return f"Warning: AI thinks this egg is {est_l:.1f}x{est_w:.1f}mm.\nAre you sure about {knownL}x{knownW}mm?"
        return "OK"

    def _xml_escape(self, value):
        return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

    def _is_open_auth(self, authentication):
        return "open" in (authentication or "").lower()

    def _xml_authentication_value(self, authentication):
        auth = (authentication or "").lower()
        if "wpa3" in auth:
            return "WPA3SAE"
        if "wpa2" in auth:
            return "WPA2PSK"
        if "wpa" in auth:
            return "WPAPSK"
        return "WPA2PSK"

    def _xml_encryption_value(self, encryption):
        enc = (encryption or "").lower()
        if "tkip" in enc:
            return "TKIP"
        if "none" in enc:
            return "none"
        return "AES"

    def _create_profile_xml(self, ssid, password, authentication, encryption, open_network):
        escaped_ssid = self._xml_escape(ssid)
        if open_network:
            return f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{escaped_ssid}</name>
  <SSIDConfig>
    <SSID>
      <name>{escaped_ssid}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>open</authentication>
        <encryption>none</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
    </security>
  </MSM>
</WLANProfile>
'''

        escaped_password = self._xml_escape(password)
        auth_value = self._xml_authentication_value(authentication)
        encryption_value = self._xml_encryption_value(encryption)
        return f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>{escaped_ssid}</name>
  <SSIDConfig>
    <SSID>
      <name>{escaped_ssid}</name>
    </SSID>
  </SSIDConfig>
  <connectionType>ESS</connectionType>
  <connectionMode>auto</connectionMode>
  <MSM>
    <security>
      <authEncryption>
        <authentication>{auth_value}</authentication>
        <encryption>{encryption_value}</encryption>
        <useOneX>false</useOneX>
      </authEncryption>
      <sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{escaped_password}</keyMaterial>
      </sharedKey>
    </security>
  </MSM>
</WLANProfile>
'''

    def _parse_windows_networks(self, output):
        ssid_re = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.*)\s*$", re.IGNORECASE)
        auth_re = re.compile(r"^\s*Authentication\s*:\s*(.*)\s*$", re.IGNORECASE)
        encryption_re = re.compile(r"^\s*Encryption\s*:\s*(.*)\s*$", re.IGNORECASE)
        signal_re = re.compile(r"^\s*Signal\s*:\s*(\d+)%\s*$", re.IGNORECASE)

        current = None
        parsed = []

        def flush_current():
            nonlocal current
            if not current:
                return
            name = (current.get("ssid") or "").strip()
            if name and name.lower() != "hidden network":
                current["ssid"] = name
                current["openNetwork"] = self._is_open_auth(current.get("authentication", ""))
                current["connected"] = False
                parsed.append(current)
            current = None

        for line in output.splitlines():
            trimmed = line.strip()

            m = ssid_re.match(trimmed)
            if m:
                flush_current()
                current = {
                    "ssid": m.group(1).strip(),
                    "authentication": "Unknown",
                    "encryption": "Unknown",
                    "signal": 0,
                    "openNetwork": False,
                    "connected": False,
                }
                continue

            if not current:
                continue

            m = auth_re.match(trimmed)
            if m:
                current["authentication"] = m.group(1).strip() or "Unknown"
                continue

            m = encryption_re.match(trimmed)
            if m:
                current["encryption"] = m.group(1).strip() or "Unknown"
                continue

            m = signal_re.match(trimmed)
            if m:
                try:
                    current["signal"] = int(m.group(1))
                except ValueError:
                    current["signal"] = 0
                continue

        flush_current()

        by_ssid = {}
        for net in parsed:
            ssid = net["ssid"]
            if ssid not in by_ssid or net["signal"] > by_ssid[ssid]["signal"]:
                by_ssid[ssid] = net

        return sorted(by_ssid.values(), key=lambda n: n.get("signal", 0), reverse=True)

    def _current_connected_ssid_windows(self):
        import subprocess

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            creationflags=creation_flags,
            timeout=6,
        )
        if result.returncode != 0:
            return ""

        state_re = re.compile(r"^\s*State\s*:\s*(.*)\s*$", re.IGNORECASE)
        ssid_re = re.compile(r"^\s*SSID\s*:\s*(.*)\s*$", re.IGNORECASE)

        state = ""
        ssid = ""
        for line in result.stdout.splitlines():
            trimmed = line.strip()
            if trimmed.lower().startswith("bssid"):
                continue

            m = state_re.match(trimmed)
            if m:
                state = m.group(1).strip()
                continue

            m = ssid_re.match(trimmed)
            if m:
                ssid = m.group(1).strip()

        if "connected" in state.lower():
            return ssid
        return ""

    def _refresh_connected_flags(self):
        connected_ssid = ""
        if os.name == 'nt':
            try:
                connected_ssid = self._current_connected_ssid_windows()
            except Exception:
                connected_ssid = ""

        for net in self._wifi_list:
            if isinstance(net, dict):
                net["connected"] = bool(connected_ssid and net.get("ssid") == connected_ssid)
        return connected_ssid

    @Slot()
    def scanWifi(self):
        """Scans for real Wi-Fi networks with metadata (signal/security/connected)."""
        if self._wifi_status == "Scanning":
            return

        self._wifi_status = "Scanning"
        self.wifiStatusChanged.emit()

        def do_scan():
            networks = []
            scan_error = ""
            try:
                import subprocess

                if os.name == 'nt':
                    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    result = subprocess.run(
                        ["netsh", "wlan", "show", "networks", "mode=bssid"],
                        capture_output=True,
                        text=True,
                        creationflags=creation_flags,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        networks = self._parse_windows_networks(result.stdout)
                        connected_ssid = self._current_connected_ssid_windows()
                        for net in networks:
                            net["connected"] = bool(connected_ssid and net.get("ssid") == connected_ssid)
                    else:
                        msg = (result.stdout or "").strip() or (result.stderr or "").strip()
                        lowered = msg.lower()
                        if "location permission" in lowered:
                            scan_error = "Error: Enable Windows Location permission for WLAN scan"
                        elif "requires elevation" in lowered or "administrator" in lowered:
                            scan_error = "Error: Run app as Administrator for Wi-Fi scan"
                        elif msg:
                            scan_error = f"Error: {msg.splitlines()[-1]}"
                        else:
                            scan_error = "Error: Failed to scan networks"
                else:
                    result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"], capture_output=True, text=True)
                    if result.returncode == 0:
                        unique = {line.strip() for line in result.stdout.split('\n') if line.strip()}
                        networks = [
                            {
                                "ssid": ssid,
                                "authentication": "Unknown",
                                "encryption": "Unknown",
                                "signal": 0,
                                "openNetwork": False,
                                "connected": False,
                            }
                            for ssid in sorted(unique, key=lambda v: v.lower())
                        ]
                    else:
                        scan_error = "Error: Failed to scan networks"

            except Exception as e:
                scan_error = f"Error: {e}"
                print(f"[WIFI ERROR] Scan failed: {e}")

            self._wifi_list = networks
            self._wifi_status = scan_error if scan_error else "Idle"
            self.wifiListChanged.emit()
            self.wifiStatusChanged.emit()

        threading.Thread(target=do_scan, daemon=True).start()

    @Slot(str, str)
    def connectToWifi(self, ssid, password):
        """Connects to Wi-Fi network using scanned security metadata."""
        if not ssid:
            self._wifi_status = "Error: Please select a Wi-Fi network"
            self.wifiStatusChanged.emit()
            return

        self._wifi_status = "Connecting"
        self.wifiStatusChanged.emit()

        def do_connect():
            temp_name = None
            try:
                import subprocess
                import tempfile

                if os.name == 'nt':
                    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

                    selected = next((n for n in self._wifi_list if isinstance(n, dict) and n.get("ssid") == ssid), None)
                    authentication = selected.get("authentication", "") if selected else ""
                    encryption = selected.get("encryption", "") if selected else ""
                    open_network = bool(selected.get("openNetwork", False)) if selected else False

                    if not open_network and not password:
                        self._wifi_status = "Error: Password is required"
                        self.wifiStatusChanged.emit()
                        return

                    # replace existing profile for this SSID
                    subprocess.run(
                        ["netsh", "wlan", "delete", "profile", f"name={ssid}"],
                        capture_output=True,
                        text=True,
                        creationflags=creation_flags,
                        timeout=6,
                    )

                    profile_xml = self._create_profile_xml(ssid, password or "", authentication, encryption, open_network)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as f:
                        f.write(profile_xml.encode('utf-8'))
                        temp_name = f.name

                    add_res = subprocess.run(
                        ["netsh", "wlan", "add", "profile", f"filename={temp_name}", "user=current"],
                        capture_output=True,
                        text=True,
                        creationflags=creation_flags,
                        timeout=10,
                    )
                    if add_res.returncode != 0:
                        msg = (add_res.stderr or "").strip() or (add_res.stdout or "").strip()
                        self._wifi_status = "Error: Failed to add Wi-Fi profile" if not msg else f"Error: {msg}"
                        self.wifiStatusChanged.emit()
                        return

                    subprocess.run(
                        ["netsh", "wlan", "disconnect"],
                        capture_output=True,
                        text=True,
                        creationflags=creation_flags,
                        timeout=6,
                    )

                    conn_res = subprocess.run(
                        ["netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}"],
                        capture_output=True,
                        text=True,
                        creationflags=creation_flags,
                        timeout=10,
                    )
                    if conn_res.returncode != 0:
                        msg = (conn_res.stderr or "").strip() or (conn_res.stdout or "").strip()
                        self._wifi_status = "Error: Connection failed" if not msg else f"Error: {msg}"
                        self._refresh_connected_flags()
                        self.wifiListChanged.emit()
                        self.wifiStatusChanged.emit()
                        return

                    connected = False
                    for _ in range(8):
                        if self._current_connected_ssid_windows() == ssid:
                            connected = True
                            break
                        time.sleep(0.7)

                    self._refresh_connected_flags()
                    self.wifiListChanged.emit()
                    self._wifi_status = "Connected" if connected else "Error: Connection not confirmed"
                else:
                    if password:
                        result = subprocess.run(["sudo", "nmcli", "dev", "wifi", "connect", ssid, "password", password], capture_output=True, text=True)
                    else:
                        result = subprocess.run(["sudo", "nmcli", "dev", "wifi", "connect", ssid], capture_output=True, text=True)
                    self._wifi_status = "Connected" if result.returncode == 0 else "Error: Connection failed"

            except Exception as e:
                self._wifi_status = f"Error: {str(e)}"
            finally:
                if temp_name:
                    try:
                        os.remove(temp_name)
                    except Exception:
                        pass
                self.wifiStatusChanged.emit()

        threading.Thread(target=do_connect, daemon=True).start()
