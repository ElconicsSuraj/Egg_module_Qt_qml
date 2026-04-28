import logging
import time
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import sys
import os
import threading
import cv2
from fastapi.responses import StreamingResponse

# Ensure project root is on path so 'src' package resolves
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.constants import Config
from src.core.camera import CameraManager
from src.core.detector import EggDetector
from src.core.calibration import CalibrationManager, MultiCalibrationEntry
from src.core.measurement import EggMeasurement
from src.utils.overlay import DisplayOverlay

logger = logging.getLogger(__name__)

# --- Global State ---
app_state = {
    "latest_frame_bytes": None,
    "running": False,
    "camera_lock": threading.Lock()
}

def camera_background_thread():
    """Continuously reads from the camera to provide a live feed for the UI."""
    camera = app_state.get("camera")
    engine = app_state.get("measurement_engine")
    overlay = app_state.get("overlay")
    
    while app_state.get("running"):
        frame = None
        if not app_state["camera_lock"].locked():
            with app_state["camera_lock"]:
                ret, frame_raw = camera.read_frame_latest(max_skip=5)
                if ret and frame_raw is not None:
                    frame = frame_raw.copy()
        
        if frame is not None:
            # AI logic OUTSIDE the lock to prevent API hangs
            measurement = engine.measure_frame(frame)
            engine.update_state(measurement)
            
            display_frame = frame.copy()
            now = time.time()
            
            if measurement:
                result = measurement["result"]
                if not engine._settled:
                    elapsed = now - engine._first_detect_t if engine._first_detect_t else 0
                    remaining = max(0, engine._settle_delay_s - elapsed)
                    cv2.putText(display_frame, f"Place egg... {remaining:.1f}s",
                                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                else:
                    overlay.draw_egg(display_frame, result)
            
            _, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            app_state["latest_frame_bytes"] = buffer.tobytes()
            
        time.sleep(0.01) # Maximize throughput for live edge feedback

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    config = Config()
    config.setup_logging()

    detector = EggDetector(config)
    detector.load_model()

    cal_mgr = CalibrationManager(config)
    cal_data = cal_mgr.load()

    camera = CameraManager(config)
    if not camera.open():
        logger.error("Could not open camera on startup!")
    else:
        logger.info(f"Camera opened: {camera.resolution}")
        if cal_data.has_lens:
            camera.set_lens_calibration(cal_data.camera_matrix, cal_data.dist_coeffs)
        if cal_data.has_homography:
            camera.set_homography(cal_data.homography)

    overlay = DisplayOverlay(config)
    measurement_engine = EggMeasurement(config, detector, camera, cal_data, overlay)

    app_state["config"] = config
    app_state["detector"] = detector
    app_state["cal_mgr"] = cal_mgr
    app_state["cal_data"] = cal_data
    app_state["camera"] = camera
    app_state["overlay"] = overlay
    app_state["measurement_engine"] = measurement_engine
    
    # Start live background thread
    app_state["running"] = True
    bg_thread = threading.Thread(target=camera_background_thread, daemon=True)
    bg_thread.start()
    
    logger.info("=" * 60)
    logger.info("API OFFLINE MODE: READY")
    logger.info("Try this in Postman: http://127.0.0.1:8000/measure")
    logger.info("=" * 60)
    
    yield
    # --- Shutdown ---
    app_state["running"] = False
    if app_state.get("camera"):
        app_state["camera"].release()


app = FastAPI(title="Egg Measurement API", lifespan=lifespan)

# --- Pydantic Models ---
class CalibrationRequest(BaseModel):
    known_length_mm: float = Field(..., gt=20, lt=150, description="Physical length of the reference egg in mm (must be between 20 and 150)")
    known_width_mm: float = Field(..., gt=20, lt=150, description="Physical width of the reference egg in mm (must be between 20 and 150)")

class MeasurementResponse(BaseModel):
    length_mm: float
    breadth_mm: float
    confidence_score: float

class CalibrationResponse(BaseModel):
    success: bool
    message: str
    pixel_to_mm_length: float = 0.0
    pixel_to_mm_width: float = 0.0

# --- Endpoints ---

@app.get("/measure", response_model=MeasurementResponse)
def measure_egg():
    """
    On-demand measurement endpoint.
    Takes a batch of frames of the current egg, calculates statistics, and returns the result.
    """
    camera = app_state["camera"]
    engine = app_state["measurement_engine"]
    
    if not camera or not camera.is_open:
        raise HTTPException(status_code=500, detail="Camera not initialized or failed to open.")

    # Clear lingering history
    engine._reset_session()
    
    # We will attempt to collect a full batch of successful frames.
    # We will timeout after max_attempts if an egg isn't found consistently.
    max_attempts = engine.config.measure_max_attempts
    batch_size = engine.config.batch_size
    valid_frames = 0
    local_batch_l = []
    local_batch_w = []
    
    # Temporarily lock the camera from the background thread to take perfect frames
    bbox_xyxy = None
    
    with app_state["camera_lock"]:
        # Frame 1: Full detection to find the egg and its bounding box
        # Use latest frame (buffer flushing) for real-time response
        ret, frame = camera.read_frame_latest(max_skip=5)
        if ret and frame is not None:
            measurement = engine.measure_frame(frame)
            if measurement:
                bbox_xyxy = measurement["result"].bbox_xyxy
                local_batch_l.append(measurement["length_mm"])
                local_batch_w.append(measurement["width_mm"])
                valid_frames = 1
        
        if bbox_xyxy is not None:
            # Frames 2 to BATCH_SIZE: High-speed BBox-locked processing (Skips YOLO)
            for _ in range(max_attempts - 1):
                if valid_frames >= batch_size:
                    break
                    
                # Use latest frame (buffer flushing) for real-time response
                ret, frame = camera.read_frame_latest(max_skip=5)
                if not ret or frame is None:
                    continue
                    
                # Use the fast measurement engine method
                measurement = engine.measure_frame_with_bbox(frame, bbox_xyxy)
                if measurement:
                    local_batch_l.append(measurement["length_mm"])
                    local_batch_w.append(measurement["width_mm"])
                    valid_frames += 1
                    
                    if valid_frames >= batch_size:
                        break
                # No sleep here - we want maximum capture speed while egg is steady
        else:
            # Fallback (Slow loop) if YOLO failed on frame 1
            for _ in range(max_attempts):
                # Use latest frame (buffer flushing) for real-time response
                ret, frame = camera.read_frame_latest(max_skip=5)
                if not ret or frame is None:
                    continue
                measurement = engine.measure_frame(frame)
                if measurement:
                    local_batch_l.append(measurement["length_mm"])
                    local_batch_w.append(measurement["width_mm"])
                    valid_frames += 1
                    if valid_frames >= batch_size:
                        break
        
    if valid_frames < batch_size:
        raise HTTPException(status_code=400, detail=f"Could not detect egg consistently for {batch_size} frames. Ensure egg is placed properly.")

    # Calculate statistics using the same IQR logic as the live stream
    l_arr = np.array(local_batch_l)
    w_arr = np.array(local_batch_w)

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

    avg_std = (std_l + std_w) / 2.0
    stability_score = max(0.0, min(100.0, 100.0 - (avg_std * 30.0)))
    
    ratio = measurement["result"].ratio # Use the last frame's ratio
    ratio_score = 100.0
    if ratio < 1.25:
        ratio_score = max(0.0, 100.0 - ((1.25 - ratio) * 200))
    elif ratio > 1.45:
        ratio_score = max(0.0, 100.0 - ((ratio - 1.45) * 200))

    conf_score = round(0.8 * stability_score + 0.2 * ratio_score, 1)
    
    return MeasurementResponse(
        length_mm=round(final_l, 1),
        breadth_mm=round(final_w, 1),
        confidence_score=conf_score
    )

@app.post("/calibrate", response_model=CalibrationResponse)
def calibrate_egg(req: CalibrationRequest):
    """
    Calibrates the system using an egg of known dimensions.
    Takes 20 frames, calculates PTM, and saves to media/calibration_data.json
    """
    camera = app_state["camera"]
    detector = app_state["detector"]
    cal_mgr = app_state["cal_mgr"]
    engine = app_state["measurement_engine"]
    
    if not camera or not camera.is_open:
        raise HTTPException(status_code=500, detail="Camera not initialized")

    measurements = []
    max_attempts = 50
    
    # Warmup
    time.sleep(1)
    
    with app_state["camera_lock"]:
        for _ in range(max_attempts):
            ret, frame = camera.read_undistorted_frame()
            if not ret or frame is None:
                time.sleep(0.05)
                continue
                
            result = detector.detect(frame)
            if result is not None:
                measurements.append((result.major_px, result.minor_px))
                if len(measurements) >= 20: # Use 20 frames for calibration too
                    break
            time.sleep(0.05)

    if len(measurements) < 10:
        raise HTTPException(status_code=400, detail=f"Failed to detect reference egg consistently. Only got {len(measurements)} valid frames.")

    # Process and filter
    filtered, removed = cal_mgr.filter_outliers_iqr(measurements)
    
    if len(filtered) < 5:
        raise HTTPException(status_code=400, detail="Calibration failed: Too many inconsistent frames.")
        
    cal_data = cal_mgr.compute_calibration(filtered, req.known_length_mm, req.known_width_mm)
    
    # Save it explicitly to persist
    stats = {
        "frames_captured": len(measurements), "frames_used": len(filtered),
        "outliers_removed": removed,
        "major_px_mean": round(cal_data["avg_major_px"], 2),
        "major_px_std": round(cal_data["std_major_px"], 2),
        "minor_px_mean": round(cal_data["avg_minor_px"], 2),
        "minor_px_std": round(cal_data["std_minor_px"], 2),
    }
    reference = {"known_length_mm": req.known_length_mm, "known_width_mm": req.known_width_mm}
    cal_mgr.save(cal_data, stats, reference, None) # Skipping verification payload
    
    # --- Update Multi-Egg Library (Cumulative - Production only) ---
    if app_state["config"].enable_auto_egg_mode:
        library = cal_mgr.load_library()
        label = f"{req.known_length_mm}x{req.known_width_mm}mm"
        
        entry = MultiCalibrationEntry(
            label=label,
            known_length_mm=req.known_length_mm,
            known_width_mm=req.known_width_mm,
            avg_major_px=cal_data["avg_major_px"],
            avg_minor_px=cal_data["avg_minor_px"],
            pixel_to_mm_length=cal_data["pixel_to_mm_length"],
            pixel_to_mm_width=cal_data["pixel_to_mm_width"],
            frames_used=len(filtered)
        )
        library.upsert(entry)
        cal_mgr.save_library(library)
        logger.info(f"API Library Update: '{label}' registered.")

    # Reload engine configuration
    new_cal = cal_mgr.load()
    app_state["cal_data"] = new_cal
    engine.cal_data = new_cal

    return CalibrationResponse(
        success=True,
        message=f"Calibrated successfully. Auto-mode: {app_state['config'].enable_auto_egg_mode}",
        pixel_to_mm_length=cal_data["pixel_to_mm_length"],
        pixel_to_mm_width=cal_data["pixel_to_mm_width"]
    )

@app.get("/calibration/library")
def get_library():
    """Returns the list of all registered calibration entries in the multi-egg library."""
    cal_mgr = app_state["cal_mgr"]
    library = cal_mgr.load_library()
    
    # Convert entries to dicts for JSON response
    entries = []
    for entry in library.entries:
        entries.append({
            "label": entry.label,
            "known_length_mm": entry.known_length_mm,
            "known_width_mm": entry.known_width_mm,
            "avg_major_px": entry.avg_major_px,
            "avg_minor_px": entry.avg_minor_px,
            "pixel_to_mm_length": entry.pixel_to_mm_length,
            "pixel_to_mm_width": entry.pixel_to_mm_width,
            "timestamp": entry.timestamp if hasattr(entry, 'timestamp') else None
        })
    
    return {
        "status": "success",
        "count": len(entries),
        "entries": entries,
        "mode": "auto_interpolation" if app_state["config"].enable_auto_egg_mode else "single_point"
    }

@app.delete("/calibration/library")
def clear_library():
    """Resets the generic calibration library (Factory Reset)."""
    cal_mgr = app_state["cal_mgr"]
    engine = app_state["measurement_engine"]
    
    # Create empty library and save
    from src.core.calibration import MultiCalibrationLibrary
    empty_library = MultiCalibrationLibrary()
    cal_mgr.save_library(empty_library)
    
    # Force reload in engine
    new_cal = cal_mgr.load()
    app_state["cal_data"] = new_cal
    engine.cal_data = new_cal
    
    logger.warning("Calibration Library RESET via API.")
    return {"status": "success", "message": "Multi-egg library has been cleared. System reverted to single-point calibration."}

def frame_generator():
    """Yields frames for the MJPEG stream."""
    while True:
        frame_bytes = app_state.get("latest_frame_bytes")
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.03)

@app.get("/video_feed")
def video_feed():
    """
    Continuous MJPEG video stream showing the camera feed with the AI overlay.
    Use this inside an HTML <img> tag on your UI.
    Example: <img src="http://localhost:8000/video_feed" />
    """
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    import uvicorn
    # Enable running the script directly via `python src/api.py`
    config = Config()
    uvicorn.run("src.api:app", host="0.0.0.0", port=config.api_port, reload=False)
