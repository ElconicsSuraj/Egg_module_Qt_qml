import time
import math
import random
import threading
import logging

logger = logging.getLogger(__name__)

class HeartbeatSensorDriver:
    """
    Driver for Egg Heartbeat/Pulse Sensor Module connected to Raspberry Pi GPIO.
    - Sensor Signal Input: Configurable GPIO (default: 22) or ADC input.
    - Heartbeat Indicator LED: Configurable GPIO (default: 27).
    - Performs background signal filtering, pulse detection, IBI (Inter-Beat Interval),
      and BPM calculation without blocking the Qt UI thread.
    - Drives the LED on detected pulse spikes and guarantees LED is turned OFF on exit.
    """

    def __init__(self, sensor_pin: int = 22, led_pin: int = 27):
        self.sensor_pin = sensor_pin
        self.led_pin = led_pin
        self.active = False

        self._thread = None
        self._lock = threading.Lock()

        # Output states exposed to backend/UI
        self.bpm = 0.0
        self.status = "Stopped"  # "Detecting Signal...", "Heartbeat Detected", "No Signal", "Stopped"
        self.signal_quality = "DISCONNECTED"  # "STRONG", "WEAK", "DISCONNECTED"
        self.pulse_detected = False
        self.raw_signal = 0.0

        # Hardware handle
        self._lgpio = None
        self._chip_handle = None
        self._available = False

        # Signal processing state
        self._recent_beat_times = []
        self._last_pulse_time = 0.0
        self._pulse_duration_s = 0.12  # LED flash duration on peak (120ms)
        self._led_on_time = 0.0

        self._init_hardware()

    def _init_hardware(self):
        try:
            import lgpio
            self._lgpio = lgpio
            self._chip_handle = lgpio.gpiochip_open(0)
            
            # Claim sensor pin as input with pull-down
            try:
                lgpio.gpio_claim_input(self._chip_handle, self.sensor_pin, lgpio.SET_PULL_DOWN)
            except Exception:
                lgpio.gpio_claim_input(self._chip_handle, self.sensor_pin)

            # Claim LED pin as output
            lgpio.gpio_claim_output(self._chip_handle, self.led_pin)
            lgpio.gpio_write(self._chip_handle, self.led_pin, 0)
            self._available = True
            logger.info(f"Heartbeat Hardware initialized: Sensor GPIO {self.sensor_pin}, LED GPIO {self.led_pin}")
        except Exception as e:
            logger.warning(f"Heartbeat GPIO hardware init skipped (running simulated mode): {e}")
            self._available = False

    def start(self):
        """Starts background sensor sampling and heartbeat detection thread."""
        with self._lock:
            if self.active:
                return
            self.active = True
            self.status = "Detecting Signal..."
            self.signal_quality = "WEAK"
            self.bpm = 0.0
            self.pulse_detected = False
            self._recent_beat_times.clear()
            self._last_pulse_time = 0.0

            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            logger.info("Heartbeat screening started")

    def stop(self):
        """Stops background sensor monitoring and turns LED OFF."""
        with self._lock:
            self.active = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        self._set_led(False)
        self.pulse_detected = False
        self.status = "Stopped"
        self.signal_quality = "DISCONNECTED"
        logger.info("Heartbeat screening stopped & LED turned OFF")

    def _set_led(self, state: bool):
        if self._available and self._chip_handle is not None:
            try:
                self._lgpio.gpio_write(self._chip_handle, self.led_pin, 1 if state else 0)
            except Exception as e:
                logger.error(f"Failed to set Heartbeat LED GPIO {self.led_pin}: {e}")

    def _monitor_loop(self):
        """
        Non-blocking background monitoring loop.
        Processes sensor input at ~100Hz (10ms interval).
        """
        sample_rate_hz = 100
        dt = 1.0 / sample_rate_hz

        # Adaptive thresholding and peak detection
        baseline = 500.0
        alpha = 0.05
        peak_threshold = 40.0
        last_high = False
        
        sim_phase = 0.0
        sim_base_bpm = 138.0  # Typical avian embryo heartbeat (~130-150 BPM)

        while self.active:
            now = time.time()
            signal_val = 0.0

            if self._available and self._chip_handle is not None:
                try:
                    # Read digital pulse / high-speed pin level
                    raw_bit = self._lgpio.gpio_read(self._chip_handle, self.sensor_pin)
                    signal_val = 800.0 if raw_bit == 1 else 200.0
                except Exception as e:
                    logger.debug(f"Read error on GPIO {self.sensor_pin}: {e}")
                    signal_val = 200.0
            else:
                # Simulated realistic PPG egg heartbeat signal waveform
                sim_phase += (2.0 * math.pi * (sim_base_bpm / 60.0)) * dt
                # ECG/PPG cardiac pulse wave curve (systolic peak + dicrotic notch)
                pulse_wave = (
                    math.pow(max(0, math.sin(sim_phase)), 8) * 400.0 +
                    math.pow(max(0, math.sin(sim_phase + 0.4)), 4) * 120.0
                )
                noise = random.uniform(-15.0, 15.0)
                signal_val = 200.0 + pulse_wave + noise

            self.raw_signal = signal_val

            # Moving average baseline update
            baseline = (1.0 - alpha) * baseline + alpha * signal_val
            ac_signal = signal_val - baseline

            is_peak = ac_signal > peak_threshold

            # Peak rising edge detection
            pulse_trigger = False
            if is_peak and not last_high:
                time_since_last = now - self._last_pulse_time
                # Min refractory period corresponding to ~220 BPM max (0.27s)
                if time_since_last > 0.27:
                    pulse_trigger = True
                    self._last_pulse_time = now
                    self._led_on_time = now
                    self._recent_beat_times.append(now)
                    # Keep last 10 beat timestamps
                    if len(self._recent_beat_times) > 10:
                        self._recent_beat_times.pop(0)

            last_high = is_peak

            # Calculate BPM from recent inter-beat intervals (IBIs)
            if len(self._recent_beat_times) >= 3:
                intervals = [
                    self._recent_beat_times[i] - self._recent_beat_times[i - 1]
                    for i in range(1, len(self._recent_beat_times))
                ]
                avg_interval = sum(intervals) / len(intervals)
                if 0.25 <= avg_interval <= 1.2:  # Valid 50 - 240 BPM range
                    calc_bpm = 60.0 / avg_interval
                    self.bpm = round(calc_bpm, 1)
                    self.status = "Heartbeat Detected"
                    self.signal_quality = "STRONG"
                else:
                    self.status = "Signal Irregular"
                    self.signal_quality = "WEAK"
            else:
                self.status = "Detecting Signal..."
                self.signal_quality = "WEAK"

            # Check LED flash timing on peak
            if now - self._led_on_time <= self._pulse_duration_s:
                self.pulse_detected = True
                self._set_led(True)
            else:
                self.pulse_detected = False
                self._set_led(False)

            time.sleep(dt)

        # Cleanup on loop exit
        self._set_led(False)

    def cleanup(self):
        """Clean up GPIO resources."""
        self.stop()
        if self._available and self._chip_handle is not None:
            try:
                self._lgpio.gpio_write(self._chip_handle, self.led_pin, 0)
                self._lgpio.gpiochip_close(self._chip_handle)
            except Exception:
                pass
            self._chip_handle = None
            self._available = False
