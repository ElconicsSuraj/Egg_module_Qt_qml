import cv2
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)


class EggMeasurement:
    """
    Live egg measurement with calibrated camera.
    Provides continuous measurement with center zone guidance.
    Uses shared EggDetector instance (single model load).
    """

    def __init__(self, config, detector, camera, cal_data, overlay):
        self.config = config
        self.detector = detector
        self.camera = camera
        self.cal_data = cal_data  # CalibrationData object
        self.overlay = overlay

        # State management
        self._last_measurement = None
        self._settled = False
        self._settle_start_time = None
        self._active_cal_label = "Single-Pt"
        self._window_size = config.draw_window_size

        # Simple settle + batch approach
        self._settle_delay_s   = config.settle_delay_s 
        self._batch_size       = config.batch_size    
        self._first_detect_t   = None   # time egg was first detected
        self._last_detect_t    = None   # time of most recent detection
        self._loss_timeout_s   = config.egg_loss_timeout_s
        self._batch_l          = []     # accumulates length readings
        self._batch_w          = []     # accumulates width readings
        self._result_length    = None   # last published average
        self._result_width     = None
        # self._settled          = False  # True once settle delay has passed (moved to state management)
        self._confidence_score = 0.0
    @property
    def is_visible(self):
        """True only if egg has been consistently detected past the settle delay."""
        return self._settled

    def _is_hand_detected(self, result, frame_height, frame_width):
        """
        Detect if measurement looks like hand+egg interference.
        Hand patterns: too elongated, off-center in weird way, wrong aspect ratio.
        Returns True if likely hand interference, False if clean egg detection.
        """
        # Check aspect ratio: eggs are ~1.35, hands are much more elongated (1.8+)
        if result.ratio > 1.85:
            logger.debug(f"Hand signal: ratio={result.ratio:.2f} (too elongated)")
            return True
        
        # Check contour roughness: hands have sharp angles, eggs are smooth
        if len(result.contour) > 1800:  # Allow for higher resolution detail
            logger.debug(f"Hand signal: contour too complex ({len(result.contour)} points)")
            return True
        
        # Check if contour is far off-center (hand pulls detection sideways)
        cx, cy = result.center
        img_cx, img_cy = frame_width / 2.0, frame_height / 2.0
        edge_distance_x = abs(cx - img_cx) / frame_width
        edge_distance_y = abs(cy - img_cy) / frame_height
        
        if edge_distance_x > 0.40 or edge_distance_y > 0.40: # far from center
            logger.debug(f"Hand signal: detection far off-center (x={edge_distance_x:.2f}, y={edge_distance_y:.2f})")
            return True
        
        return False

    def measure_frame(self, frame):
        """Standard measure: runs full YOLO detection."""
        result = self.detector.detect(frame)
        if result is None:
            return None
        return self._calculate_mm_full(frame, result)
    
    def measure_frame_raw(self, frame):
        """
        Get raw detection without MM calculation.
        Used for immediate visual feedback during settle phase.
        """
        result = self.detector.detect(frame)
        if result is None:
            return None
        return result

    def measure_frame_with_bbox(self, frame, bbox_xyxy):
        """Optimized measure: skips YOLO, uses pre-detected BBox."""
        result = self.detector.detect_with_bbox(frame, bbox_xyxy)
        if result is None:
            return None
        return self._calculate_mm_full(frame, result)

    def _calculate_mm(self, major_px, minor_px):
        """
        Convert pixel dimensions to millimeters using either multi-cal library
        (Linear Interpolated Auto-Egg) or fallback to single-point PTM.
        """
        ptm_l = self.cal_data.pixel_to_mm_length
        ptm_w = self.cal_data.pixel_to_mm_width
        self._active_cal_label = "Single-Pt"

        # Auto-Egg Calibration: Check if master flag is ON and we have a library
        if self.config.enable_auto_egg_mode and self.cal_data.multi_cal_library:
            library = self.cal_data.multi_cal_library
            if len(library) > 0:
                # Use interpolation for generic N-egg support (IoT Team Requirement)
                int_l, int_w = library.interpolate_factors(major_px, minor_px)
                if int_l and int_w:
                    ptm_l, ptm_w = int_l, int_w
                    nearest = library.find_nearest_entry(major_px, minor_px)
                    self._active_cal_label = f"Auto:{nearest.label}"

        return major_px * ptm_l, minor_px * ptm_w

    def _calculate_mm_full(self, frame, result):
        """Internal mm conversion math (High-Precision Interpolation or Legacy Fallback)."""

        # 1. Resolve base PTM (Interpolated vs Fallback)
        length_mm, width_mm = self._calculate_mm(result.major_px, result.minor_px)
        
        # We'll use these as the final outputs unless legacy logic modification is needed
        stable_l = length_mm
        stable_w = width_mm

        # 2. Determine if we skip legacy height/parallax logic
        # In Generic Multi-Egg mode, the library ALREADY accounts for height/size.
        if not (self.config.enable_auto_egg_mode and self.cal_data.multi_cal_library and len(self.cal_data.multi_cal_library) > 0):
            # --- LEGACY FALLBACK LOGIC ---
            base_ptm_l = length_mm / result.major_px if result.major_px > 0 else self.cal_data.pixel_to_mm_length
            base_ptm_w = width_mm / result.minor_px if result.minor_px > 0 else self.cal_data.pixel_to_mm_width
            
            # Camera-Height-Based Scaling (Relative to Calibration Egg)
            if self.config.use_height_compensation and self.cal_data.avg_minor_px > 0:
                # 1. Estimate height of the original calibration egg
                ref_egg_width_mm = self.cal_data.avg_minor_px * base_ptm_w
                ref_egg_height_mm = ref_egg_width_mm * self.config.egg_height_ratio
                ref_midpoint_dist = self.config.camera_height_mm - (ref_egg_height_mm / 2.0)
                
                # 2. Estimate height of the currently detected egg
                curr_egg_width_mm = result.minor_px * base_ptm_w
                curr_egg_height_mm = curr_egg_width_mm * self.config.egg_height_ratio
                curr_midpoint_dist = self.config.camera_height_mm - (curr_egg_height_mm / 2.0)
                
                # 3. Calculate relative adjustment
                distance_ratio = curr_midpoint_dist / ref_midpoint_dist
                
                ptm_y = base_ptm_l * distance_ratio
                ptm_x = base_ptm_w * distance_ratio
                
                logger.debug(f"Height comp: ratio={distance_ratio:.4f}")
            elif self.config.high_precision and self.cal_data.avg_minor_px > 0:
                # Empirical Volume-Aware Perspective Correction
                ref_radius_px = self.cal_data.avg_minor_px / 2.0
                current_radius_px = result.minor_px / 2.0
                radius_diff_mm = (current_radius_px - ref_radius_px) * base_ptm_w
                correction = 1.0 - (radius_diff_mm * self.config.perspective_coeff)
                
                ptm_y = base_ptm_l * correction
                ptm_x = base_ptm_w * correction
            else:
                ptm_y = base_ptm_l
                ptm_x = base_ptm_w

            # Rotation-aware interpolation
            angle_rad = np.deg2rad(result.angle)
            ptm_major = np.sqrt((np.sin(angle_rad) * ptm_x)**2 + (np.cos(angle_rad) * ptm_y)**2)
            ptm_minor = np.sqrt((np.cos(angle_rad) * ptm_x)**2 + (np.sin(angle_rad) * ptm_y)**2)
            
            stable_l = result.major_px * ptm_major * self.config.length_scale_factor
            stable_w = result.minor_px * ptm_minor + self.config.width_bias_mm

            # Radial Perspective Correction (Corrects for 'fisheye' expansion at edges)
            height, width = frame.shape[:2]
            cx, cy = result.center
            r_norm = np.sqrt((cx - width/2)**2 + (cy - height/2)**2) / np.sqrt((width/2)**2 + (height/2)**2)
            perspective_factor = 1.0 - (self.config.radial_perspective_correction * (r_norm ** 2))
            
            stable_l *= perspective_factor
            stable_w *= perspective_factor

        # 3. Final Metadata Prep
        height, width = frame.shape[:2]
        cx, cy = result.center
        in_center = self.overlay.is_in_center_zone(cx, cy, width, height)

        return {
            "length_mm": stable_l,
            "width_mm": stable_w,
            "raw_length_mm": length_mm,
            "raw_width_mm": width_mm,
            "major_px": result.major_px,
            "minor_px": result.minor_px,
            "ratio": result.ratio,
            "in_center": in_center,
            "result": result,
            "is_high_precision": self.config.high_precision,
            "is_visible": self._settled,
            "is_hand": self._is_hand_detected(result, height, width)
        }

    def get_stable_metrics(self):
        """
        Returns the latest stable measurement result along with the dynamic confidence score.
        Used by external backends (API/GUI) to get settled data.
        """
        if not self._settled or self._result_length is None:
            return None
            
        return {
            "length_mm": self._result_length,
            "breadth_mm": self._result_width,
            "confidence_score": self._confidence_score
        }

    def _calculate_confidence_score(self, std_l, std_w, ratio, contour_len):
        """Internal logic for Dynamic Industrial Scoring."""
        avg_std = (std_l + std_w) / 2.0
        base_ceiling = self.config.confidence_ceiling
        
        # 1. Stability Penalty
        stability_loss = (avg_std * self.config.confidence_strictness) + ((avg_std ** 2) * 100.0)
        stability_score = max(0.0, min(base_ceiling, base_ceiling - stability_loss))
        
        # 2. Shape Quality Penalty
        ratio_deviation = abs(ratio - 1.35)
        shape_score = max(0.0, 100.0 - (ratio_deviation * 80.0))
        
        # 3. Contour Noise Penalty
        noise_penalty = 0
        if contour_len > 800:
            noise_penalty = min(15, (contour_len - 800) // 30)
            
        # 85% Stability / 15% Shape
        raw_conf = (0.85 * stability_score) + (0.15 * shape_score) - noise_penalty
        return round(max(0.0, min(base_ceiling, raw_conf)), 1)

    def update_state(self, measurement):
        """Internal helper to update the stabilization state (shared by CLI and API)."""
        now = time.time()
        self._last_measurement = measurement  # Preserve for validation/access
        
        if measurement is None:
            # Handle egg loss timeout
            if self._last_detect_t and (now - self._last_detect_t) > self._loss_timeout_s:
                if self._first_detect_t is not None:
                    logger.info("Egg removed — reset.")
                self._reset_session()
            return

        if measurement.get("is_hand", False):
            logger.debug("Hand detected - ignoring for stabilization.")
            # We don't reset_session here, we just don't update timestamps or buffers
            # This keeps the last 'settled' measurement visible if it was already stable
            return

        # Anomaly Detection (Sudden jump = hand/shadow)
        raw_l = measurement["raw_length_mm"]
        is_anomaly = False
        if len(self._batch_l) > 0:
            if abs(raw_l - np.median(self._batch_l)) > 5.0:
                is_anomaly = True
        elif self._result_length is not None:
            if abs(raw_l - self._result_length) > 5.0:
                is_anomaly = True

        if is_anomaly:
            logger.warning("Interruption detected! Restarting stabilization...")
            self._reset_session()
            self._first_detect_t = now
            return

        # Regular Progress
        self._last_detect_t = now
        if self._first_detect_t is None:
            self._first_detect_t = now
            logger.info("Egg Detection: Stabilizing measurements...")

        elapsed = now - self._first_detect_t
        if not self._settled:
            # Populating buffers even during settlement for stability check
            self._batch_l.append(measurement["length_mm"])
            self._batch_w.append(measurement["width_mm"])
            
            if len(self._batch_l) > 10:
                self._batch_l.pop(0)
                self._batch_w.pop(0)

            # Smart settlement: settle faster if measurements are very stable
            if elapsed >= self._settle_delay_s:
                self._settled = True
                self.calculate_batch_results(measurement["result"].ratio, len(measurement["result"].contour))
                self._batch_l.clear()
                self._batch_w.clear()
                logger.info(f"Measurement settled (after {elapsed:.2f}s).")
            elif elapsed >= self._settle_delay_s * 0.5:
                # Check if half-settled and measurements very stable (std < 0.3mm)
                if len(self._batch_l) >= 5:
                    std_l = np.std(self._batch_l[-5:])
                    std_w = np.std(self._batch_w[-5:])
                    if std_l < 0.3 and std_w < 0.3:
                        self._settled = True
                        self.calculate_batch_results(measurement["result"].ratio, len(measurement["result"].contour))
                        self._batch_l.clear()
                        self._batch_w.clear()
                        logger.info(f"Early settlement: stable after {elapsed:.2f}s (std_l={std_l:.3f}, std_w={std_w:.3f})")
        else:
            # Already settled: collect batch and update results
            self._batch_l.append(measurement["length_mm"])
            self._batch_w.append(measurement["width_mm"])
            
            if len(self._batch_l) >= self.config.batch_size:
                self.calculate_batch_results(measurement["result"].ratio, len(measurement["result"].contour))
                self._batch_l.clear()
                self._batch_w.clear()

    def calculate_batch_results(self, ratio=1.35, contour_len=400):
        """Compute the average dimensions and confidence score from the current batch."""
        if not self._batch_l:
            return
            
        l_arr = np.array(self._batch_l)
        w_arr = np.array(self._batch_w)

        # Filter outliers
        q1_l, q3_l = np.percentile(l_arr, [25, 75])
        iqr_l = q3_l - q1_l
        lower_l, upper_l = q1_l - 1.5 * iqr_l, q3_l + 1.5 * iqr_l
        
        q1_w, q3_w = np.percentile(w_arr, [25, 75])
        iqr_w = q3_w - q1_w
        lower_w, upper_w = q1_w - 1.5 * iqr_w, q3_w + 1.5 * iqr_w
        
        valid = (l_arr >= lower_l) & (l_arr <= upper_l) & (w_arr >= lower_w) & (w_arr <= upper_w)
        
        if np.sum(valid) >= 5:
            final_l = np.mean(l_arr[valid])
            final_w = np.mean(w_arr[valid])
            std_l = np.std(l_arr[valid])
            std_w = np.std(w_arr[valid])
        else:
            final_l = np.median(l_arr)
            final_w = np.median(w_arr)
            std_l = np.std(l_arr)
            std_w = np.std(w_arr)

        self._result_length = round(final_l, 1)
        self._result_width  = round(final_w, 1)
        self._confidence_score = self._calculate_confidence_score(std_l, std_w, ratio, contour_len)


    def _reset_session(self):
        """Reset all batch/settle state when egg is removed."""
        self._first_detect_t = None
        self._last_detect_t  = None
        self._batch_l.clear()
        self._batch_w.clear()
        # self._history_l.clear() # Removed as per new init
        # self._history_w.clear() # Removed as per new init
        self._settled        = False
        self._result_length  = None
        self._result_width   = None
        self._confidence_score = 0.0
        self._active_cal_label = "Single-Pt" # Reset calibration label

    def run(self):
        """
        Main live measurement loop.
        Logic:
          1. Get LATEST frame from camera (flush buffer for real-time response)
          2. Wait 1.5s settle delay after egg first appears (ignores hand noise).
          3. After settle, collect 20 frames and publish their average.
          4. Repeat every 20 frames while egg is present.
          5. Reset when egg is removed for > 0.5s.
        S = Save result, Q = Quit.
        """
        import os
        from datetime import datetime

        logger.info("--- LIVE EGG MONITORING ---")
        logger.info(f"Operation: Measurements will stabilize {self._settle_delay_s}s after egg detection.")
        logger.info(f"Real-time mode: Using latest camera frame (buffer flushing enabled)")
        logger.info("Controls: [S] Save Image | [T] Save Log | [Q] Quit")

        while True:
            # CRITICAL: Get LATEST frame, not buffered old frame
            # This eliminates the 3+ second delay when hand/egg moves
            ret, frame = self.camera.read_frame_latest(max_skip=5)
            if not ret or frame is None:
                continue

            height, width = frame.shape[:2]
            display = frame.copy()
            now = time.time()

            measurement = self.measure_frame(frame)
            self.update_state(measurement)
            detected = measurement is not None

            # Always draw diagnostic circle
            if self.config.show_diagnostic_circle:
                avg_ptm = (self.cal_data.pixel_to_mm_length + self.cal_data.pixel_to_mm_width) / 2
                self.overlay.draw_diagnostic_circle(display, avg_ptm)

            banner_text = None
            banner_color = (0, 0, 0) # Default black

            if detected:
                result = measurement["result"]
                
                if not self._settled:
                    # --- CLEAN SCREEN DURING SETTLING ---
                    # Do NOT draw any overlay while hand/egg is settling.
                    # This hides the hand detection from the user for a clean UX.
                    # Just show a simple text hint at the bottom so user knows its working.
                    elapsed = now - self._first_detect_t if self._first_detect_t else 0
                    remaining = max(0, self._settle_delay_s - elapsed)
                    curr_l = measurement["length_mm"]
                    curr_w = measurement["width_mm"]
                    banner_text = f"Stabilizing {remaining:.1f}s... (Live: {curr_l:.1f}x{curr_w:.1f})"
                    banner_color = (120, 80, 0) # Darker Amber for settling
                else:
                    # Only show the green overlay after stable detection (settled)
                    self.overlay.draw_egg(display, result)
                    
                if self._settled:
                    self._batch_l.append(measurement["length_mm"])
                    self._batch_w.append(measurement["width_mm"])

                    if len(self._batch_l) >= self._batch_size:
                        self.calculate_batch_results(result.ratio, len(result.contour))

                        # Print JSON-like dict exactly as requested
                        output_dict = {
                            "length_mm": float(self._result_length),
                            "breadth_mm": float(self._result_width),
                            "confidence_score": float(self._confidence_score)
                        }
                        
                        import json
                        logger.info(f"Measurement Output: {json.dumps(output_dict)}")

                        self._batch_l.clear()
                        self._batch_w.clear()

                # Show green banner if result available
                if self._result_length is not None:
                    banner_text = f"L={self._result_length}mm   B={self._result_width}mm"
                    banner_color = (0, 80, 0) # Green for result
                elif self._settled:
                    # Collecting — show progress AND current live mm
                    curr_l = measurement["length_mm"]
                    curr_w = measurement["width_mm"]
                    banner_text = f"Collecting {len(self._batch_l)}/{self._batch_size} (Live: {curr_l:.1f}x{curr_w:.1f})"
                    banner_color = (0, 100, 100) # Yellow-Teal for collecting

            # --- RENDER DISPLAY ---
            if banner_text:
                # Background bar
                cv2.rectangle(display, (0, 0), (width, 55), banner_color, -1)
                # Main text
                cv2.putText(display, banner_text, (20, 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 3)
                # Calibration Label
                cv2.putText(display, f"Source: {self._active_cal_label}", (width - 220, 38),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            if not detected:
                # No egg detected
                if self._last_detect_t and (now - self._last_detect_t) > self._loss_timeout_s:
                    if self._first_detect_t is not None:
                        logger.info("Egg removed — reset.")
                    self._reset_session()
                
                cv2.rectangle(display, (0, 0), (width, 55), (0, 0, 120), -1)
                cv2.putText(display, "SEARCHING FOR EGG...",
                            (20, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Status bar
            status = "S=Save Image  T=Save Text  Q=Quit"
            if self.config.high_precision:
                status += "  [HP]"
            self.overlay.draw_status(display, status, self.camera.has_lens_calibration)

            cv2.imshow("Egg Measurement", display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('t'):
                if self._result_length is not None:
                    # Keep track of the M number
                    if not hasattr(self, "_test_counter"):
                        self._test_counter = 1
                    
                    # Store in the txt format exactly as requested
                    log_line = f"M{self._test_counter},length_mm={self._result_length}, breadth_mm={self._result_width}\n"
                    
                    # Append strictly to the txt file from config
                    with open(self.config.measurement_log_file, "a") as f:
                        f.write(log_line)
                        
                    logger.info(f"Saved text: {log_line.strip()}")
                    self._test_counter += 1
                else:
                    logger.info("No result yet — wait for green banner.")
            elif key == ord('s'):
                if self._result_length is not None:
                    output_dir = "saved_images"
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    filepath = os.path.join(output_dir, f"egg_{timestamp}.jpg")
                    cv2.imwrite(filepath, display)
                    pos = "CENTER" if (measurement and measurement["in_center"]) else "OFF-CENTER"
                    logger.info(f"Saved: {filepath} | L={self._result_length}mm  W={self._result_width}mm  [{pos}]")
                else:
                    logger.info("No result yet — wait for green banner.")

        cv2.destroyAllWindows()
        logger.info("Done!")
