"""
Egg Measurement System — Single Entry Point.
All settings are read from .env file — no command-line arguments needed.

Usage:
    python src/main.py

Set CALIBRATION_MODE in .env:
    scale   = Normal egg calibration (default)
    lens    = Checkerboard lens calibration
    verify  = Verify existing calibration
    measure = Live egg measurement (Desktop UI mode)
    api     = Live API service for frontend integration
"""

import sys
import os

# Ensure project root is on path so 'src' package resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import cv2
import numpy as np
import logging

from src.config.constants import Config
from src.core.camera import CameraManager
from src.core.detector import EggDetector
from src.core.calibration import CalibrationManager, MultiCalibrationEntry
from src.core.lens import LensCalibrator
from src.core.measurement import EggMeasurement
from src.utils.overlay import DisplayOverlay

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Calibration-specific helper functions (not duplicated elsewhere)
# ---------------------------------------------------------

def live_preview(detector, camera, overlay, config, target_l=None, target_w=None):
    """
    Show live camera feed with egg detection overlay.
    Shows estimated dimensions based on previous calibration for "smart validation".
    """
    logger.info("Starting Live Preview")
    logger.info("  [SPACE] = Start calibration capture")
    logger.info("  [Q]     = Quit sequence")

    # Load existing calibration for the "estimate" display
    from src.core.calibration import CalibrationManager
    cal_mgr = CalibrationManager(config)
    existing_cal = cal_mgr.load()

    while True:
        ret, frame = camera.read_frame_latest(max_skip=5)
        if not ret or frame is None:
            time.sleep(0.1)
            continue

        display = frame.copy()
        result = detector.detect(frame)
        h, w = display.shape[:2]

        # Draw status bar at bottom
        overlay.draw_status(display, "SPACE=Calibrate  Q=Quit", camera.has_lens_calibration)

        if result:
            overlay.draw_egg(display, result)
            
            # --- Smart Estimation Logic (Production Safety Feature) ---
            est_l, est_w = None, None
            if config.enable_auto_egg_mode and existing_cal.has_scale:
                est_l = result.major_px * existing_cal.pixel_to_mm_length
                est_w = result.minor_px * existing_cal.pixel_to_mm_width
                
                # Header showing estimation
                cv2.rectangle(display, (0, 0), (w, 65), (30, 30, 30), -1)
                cv2.putText(display, f"Estimating: {est_l:.1f}x{est_w:.1f}mm", 
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 200, 0), 2)
                
                if target_l and target_w:
                    diff_l = abs(est_l - target_l) / target_l
                    diff_w = abs(est_w - target_w) / target_w
                    max_diff = max(diff_l, diff_w)
                    
                    if config.enable_calibration_check:
                        if max_diff < 0.12:
                            match_text = "MATCH ✓"
                            match_color = (0, 255, 0)
                        elif max_diff < 0.25:
                            match_text = "MISMATCH: Height changed? ⚠"
                            match_color = (0, 165, 255)
                        else:
                            match_text = "SEVERE MISMATCH: Wrong Egg? ✖"
                            match_color = (0, 0, 255)
                            
                        cv2.putText(display, f"Target: {target_l}x{target_w}mm", 
                                    (w - 290, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
                        cv2.putText(display, match_text, 
                                    (w - 290, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.65, match_color, 2)
            else:
                # Basic Preview Mode (Development)
                cv2.putText(display, f"Raw Size: {result.major_px:.0f}x{result.minor_px:.0f}px", 
                            (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                if target_l:
                    cv2.putText(display, f"Calibrating for: {target_l}mm", 
                                (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        else:
            cv2.putText(display, "No egg detected - position egg in frame",
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        if config.show_diagnostic_circle and existing_cal.has_scale:
            avg_ptm = (existing_cal.pixel_to_mm_length + existing_cal.pixel_to_mm_width) / 2
            overlay.draw_diagnostic_circle(display, avg_ptm)

        cv2.imshow("Calibration - Live Preview", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            cv2.destroyAllWindows()
            return True
        elif key == ord('q'):
            cv2.destroyAllWindows()
            return False


def capture_multi_frame(detector, camera, overlay, num_frames, label="Capturing",
                        show_live=True, target_l=None, target_w=None):
    """
    Capture multiple frames and measure egg in each.
    Returns list of (major_px, minor_px) tuples.
    """
    measurements = []
    missed = 0
    header_h = 60 if target_l else 40

    logger.info(f"{label}: batch capture started ({num_frames} frames expected)")

    while len(measurements) < num_frames:
        ret, frame = camera.read_undistorted_frame()
        if not ret or frame is None:
            time.sleep(0.01)
            continue
        
        display = frame.copy()
        result = detector.detect(frame)
        h, w = display.shape[:2]

        if result:
            measurements.append((result.major_px, result.minor_px))
            if show_live:
                overlay.draw_egg(display, result)
        else:
            missed += 1
            if missed > num_frames * 3:
                logger.warning("Capture abandoned: too many missed detections.")
                break

        if show_live:
            # Banner
            cv2.rectangle(display, (0, 0), (w, header_h), (20, 20, 20), -1)
            cv2.putText(display, 
                        f"{label}: {len(measurements)}/{num_frames} frames", 
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            if target_l and target_w:
                cv2.putText(display, f"Target: {target_l}x{target_w}mm", 
                            (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

            cv2.imshow("Capture Sequence", display)
            cv2.waitKey(1)

    logger.info(f"Batch capture complete: {len(measurements)} successfully measured, {missed} missed.")
    return measurements


def verify_calibration(detector, camera, overlay, cal_mgr, cal_data,
                       known_length_mm, known_width_mm, num_frames):
    """Verify calibration by re-measuring the same egg with new frames."""
    logger.info("VERIFICATION: Starting secondary measurement phase...")

    measurements = capture_multi_frame(
        detector, camera, overlay, num_frames, 
        label="Verifying", target_l=known_length_mm, target_w=known_width_mm
    )

    if len(measurements) < 5:
        logger.error("Verification failed: Insufficient frames captured for statistical analysis.")
        return None

    filtered, removed = cal_mgr.filter_outliers_iqr(measurements)
    logger.info(f"Statistical Filter: Removed {removed} frame anomalies.")

    majors = np.array([m[0] for m in filtered])
    minors = np.array([m[1] for m in filtered])

    measured_length_mm = np.mean(majors) * cal_data["pixel_to_mm_length"]
    measured_width_mm = np.mean(minors) * cal_data["pixel_to_mm_width"]

    length_error_pct = abs(measured_length_mm - known_length_mm) / known_length_mm * 100
    width_error_pct = abs(measured_width_mm - known_width_mm) / known_width_mm * 100

    # IMPROVED: Also calculate absolute errors (target < 0.5mm)
    length_error_abs = abs(measured_length_mm - known_length_mm)
    width_error_abs = abs(measured_width_mm - known_width_mm)

    return {
        "measured_length_mm": float(round(measured_length_mm, 2)),
        "measured_width_mm": float(round(measured_width_mm, 2)),
        "known_length_mm": float(known_length_mm),
        "known_width_mm": float(known_width_mm),
        "length_error_pct": float(round(length_error_pct, 3)),
        "width_error_pct": float(round(width_error_pct, 3)),
        "length_error_abs_mm": float(round(length_error_abs, 2)),
        "width_error_abs_mm": float(round(width_error_abs, 2)),
        "frames_used": len(filtered),
        # IMPROVED: Check both percentage (for stability) and absolute (for accuracy)
        "passed": bool(
            length_error_pct < 1.0 and width_error_pct < 1.0 and
            length_error_abs < 0.5 and width_error_abs < 0.5
        ),
    }


def print_verification(v):
    """Print verification results."""
    logger.info("--- VERIFICATION PERFORMANCE ---")
    logger.info(f"  Target Ref: L={v['known_length_mm']:.2f}mm, W={v['known_width_mm']:.2f}mm")
    logger.info(f"  Measured:   L={v['measured_length_mm']:.2f}mm, W={v['measured_width_mm']:.2f}mm")
    logger.info(f"  Abs Error:  L={v.get('length_error_abs_mm', 0):.2f}mm, W={v.get('width_error_abs_mm', 0):.2f}mm")
    logger.info(f"  Pct Error:  L={v['length_error_pct']:.2f}%, W={v['width_error_pct']:.2f}%")

    if v["passed"]:
        logger.info("VERIFICATION PASSED: Sub-millimeter error targets achieved.")
    else:
        logger.warning("VERIFICATION FAILED: Error exceeds industrial tolerance of 0.5mm.")
        logger.warning("Recommendation: Run lens calibration or optimize lighting uniformity.")


# ---------------------------------------------------------
# Mode runners
# ---------------------------------------------------------


def run_measure(config):
    """Run live egg measurement mode."""
    cal_mgr = CalibrationManager(config)
    cal_data = cal_mgr.load()

    if not cal_data.has_scale:
        logger.error("Measurement aborted: No calibration file detected. Run [CALIBRATION_MODE=scale] first.")
        return

    logger.info(f"Active Calibration: PTM_L={cal_data.pixel_to_mm_length:.6f}, PTM_W={cal_data.pixel_to_mm_width:.6f}")
    logger.info(f"Advanced Features: Lens Correction = {'ON' if cal_data.has_lens else 'OFF'}")

    # Load YOLO model ONCE
    detector = EggDetector(config)
    detector.load_model()

    # Open camera
    with CameraManager(config) as camera:
        if not camera.open():
            logger.error("Hardware error: Camera device failed to initialize.")
            return

        logger.info(f"Hardware Status: Camera initialized at {camera.resolution}")

        # Set lens calibration if available
        if cal_data.has_lens:
            camera.set_lens_calibration(cal_data.camera_matrix, cal_data.dist_coeffs)
            
        if cal_data.has_homography:
            camera.set_homography(cal_data.homography)

        # Create overlay and measurement
        overlay = DisplayOverlay(config)
        measurement = EggMeasurement(config, detector, camera, cal_data, overlay)

        # Run live measurement loop
        measurement.run()


def run_calibrate(config):
    """Run calibration mode (scale/lens/verify based on CALIBRATION_MODE)."""
    mode = config.calibration_mode.lower()
    logger.info(f"System Mode: {mode.upper()} INITIALIZED")

    # Shared objects — created ONCE
    cal_mgr = CalibrationManager(config)
    overlay = DisplayOverlay(config)

    with CameraManager(config) as camera:
        if not camera.open():
            logger.error("Hardware error: Could not open any camera device for calibration.")
            return

        logger.info(f"Camera stream active at {camera.resolution}")

        # Load existing lens calibration
        existing_cal = cal_mgr.load()
        if existing_cal.has_lens:
            camera.set_lens_calibration(existing_cal.camera_matrix, existing_cal.dist_coeffs)
            logger.info("Configuration: Lens calibration loaded from disk.")
            
        if existing_cal.has_homography:
            camera.set_homography(existing_cal.homography)
            logger.info("Configuration: Perspective homography loaded from disk.")

        # --- LENS CALIBRATION MODE ---
        if mode == "lens":
            lens_cal = LensCalibrator(config, camera)
            lens_data = lens_cal.run()
            if lens_data is not None:
                cal_mgr.save_lens_only(lens_data)
                camera.set_lens_calibration(
                    np.array(lens_data["camera_matrix"], dtype=np.float64),
                    np.array(lens_data["dist_coeffs"], dtype=np.float64),
                )
                logger.info("Lens calibration completed. Use mode=scale for physical units.")
            return

        # Scale/Verify/Multi modes need the YOLO detector
        detector = EggDetector(config)
        detector.load_model()

        if mode in ("multi", "multi_scale"):
            run_multi_calibrate_session(config, detector, camera, cal_mgr, overlay)
            return

        elif mode == "verify":
            known_length = float(input("\nEnter KNOWN egg LENGTH (mm): "))
            known_width = float(input("Enter KNOWN egg WIDTH (mm): "))
            
            verification = verify_calibration(
                detector, camera, overlay, cal_mgr, existing_cal,
                known_length, known_width, config.num_verify_frames,
            )
            if verification:
                print_verification(verification)
            return
        
        else:
            # Default: Single point scale calibration
            run_calibration_sequence(detector, camera, overlay, config, cal_mgr)
            return

    logger.info("=== CALIBRATION TASK COMPLETED ===")

def run_calibration_sequence(detector, camera, overlay, config, cal_mgr):
    """Core logic for a single egg calibration sequence."""
    print("\n" + "=" * 50)
    print("Enter the KNOWN dimensions of the reference egg:")
    print("=" * 50)
    try:
        target_l = float(input("  LENGTH (mm): "))
        target_w = float(input("  WIDTH  (mm): "))
    except ValueError:
        print("ERROR: Invalid input!")
        return False, 0, 0, None, []

    logger.info("Action Required: Place this egg and press [SPACE] in preview.")
    if not live_preview(detector, camera, overlay, config, target_l, target_w):
        return False, 0, 0, None, []

    # Capture
    measurements = capture_multi_frame(
        detector, camera, overlay, config.num_calibration_frames, 
        label="Calibrating", target_l=target_l, target_w=target_w
    )
    if len(measurements) < 10:
        logger.error("Insufficient frames captured (10 minimum required).")
        return False, 0, 0, None, []

    # Filter & Compute
    filtered, removed = cal_mgr.filter_outliers_iqr(measurements)
    cal_data = cal_mgr.compute_calibration(filtered, target_l, target_w)

    # Verify
    logger.info("Verification readiness: Keep egg steady and press [SPACE].")
    if live_preview(detector, camera, overlay, config, target_l, target_w):
        verification = verify_calibration(
            detector, camera, overlay, cal_mgr, cal_data,
            target_l, target_w, config.num_verify_frames,
        )
        if verification: print_verification(verification)
    else:
        verification = None

    # Save
    stats = {
        "frames_captured": len(measurements), "frames_used": len(filtered),
        "major_px_mean": round(cal_data["avg_major_px"], 2),
        "minor_px_mean": round(cal_data["avg_minor_px"], 2),
    }
    reference = {"known_length_mm": target_l, "known_width_mm": target_w}
    cal_mgr.save(cal_data, stats, reference, verification)
    
    # Auto-Update library if enabled
    if config.enable_auto_egg_mode:
        library = cal_mgr.load_library()
        label = f"{target_l}x{target_w}mm"
        entry = MultiCalibrationEntry(
            label=label, known_length_mm=target_l, known_width_mm=target_w,
            avg_major_px=cal_data["avg_major_px"], avg_minor_px=cal_data["avg_minor_px"],
            pixel_to_mm_length=cal_data["pixel_to_mm_length"],
            pixel_to_mm_width=cal_data["pixel_to_mm_width"],
            frames_used=len(filtered)
        )
        library.upsert(entry)
        cal_mgr.save_library(library)
        logger.info(f"Library Update: '{label}' registered.")

    return True, target_l, target_w, cal_data, filtered

def run_multi_calibrate_session(config, detector, camera, cal_mgr, overlay):
    """Looping session for generic N-egg calibration."""
    logger.info("=== STARTING GENERIC MULTI-EGG SESSION ===")
    egg_count = 0
    while True:
        egg_count += 1
        print(f"\n>>>> CALIBRATING REFERENCE EGG #{egg_count}")
        success, _, _, _, _ = run_calibration_sequence(detector, camera, overlay, config, cal_mgr)
        
        ans = input("\nCalibrate another egg in this session? (y/n): ").lower()
        if ans != 'y': break
    logger.info(f"SESSION COMPLETE: {egg_count} eggs processed.")


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def run_api(config):
    """Run the FastAPI service."""
    logger.info("--- API SERVICE INITIALIZING ---")
    logger.info(f"Target Port: {config.api_port}")
    logger.info(f"Local Documentation: http://localhost:{config.api_port}/docs")
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=config.api_port, log_level="info")

def main():
    config = Config()
    config.setup_logging()

    mode = config.calibration_mode.lower()

    if mode == "api":
        run_api(config)
    elif mode.startswith("measure"):
        run_measure(config)
    elif mode in ("scale", "dual_scale", "lens", "verify", "multi", "multi_scale") or mode.startswith("calibrate"):
        run_calibrate(config)
    else:
        # Default fallback
        run_api(config)


if __name__ == "__main__":
    main()
