import cv2
import numpy as np
import logging
import os
from dataclasses import dataclass

# Force YOLO into offline mode BEFORE it imports
os.environ['YOLO_OFFLINE'] = 'True'
os.environ['YOLO_VERBOSE'] = 'False'
os.environ['RAY_DISABLE_AUTO_CALLBACKS'] = '1'

try:
    from ultralytics import settings
    # Individually update settings to gracefully handle missing keys in different versions
    for key, value in {'sync': False, 'update_check': False}.items():
        try:
            settings.update({key: value})
        except Exception:
            pass
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass
class EggDetectionResult:
    """Result of egg detection on a single frame."""
    major_px: float
    minor_px: float
    ellipse: tuple
    contour: np.ndarray
    bbox_xyxy: np.ndarray = None

    @property
    def center(self):
        """Return (cx, cy) of the ellipse center."""
        return self.ellipse[0]

    @property
    def angle(self):
        """Return the ellipse rotation angle."""
        return self.ellipse[2]

    @property
    def ratio(self):
        """Return major/minor aspect ratio."""
        return self.major_px / self.minor_px if self.minor_px > 0 else 0


class EggDetector:
    """
    Detects eggs using YOLO for bounding box + Otsu threshold for contour.
    YOLO model is loaded ONCE via load_model() and reused for all detections.

    Pipeline (exact match to camera_calibration.py:49-107):
    1. YOLO detection -> bounding box
    2. Dynamic BB padding: max(bb_padding, int(dim * 0.15))
    3. GaussianBlur(gray, (3, 3), 0)
    4. Otsu threshold
    5. MORPH_CLOSE with 5x5 kernel, 1 iteration
    6. findContours(CHAIN_APPROX_NONE)
    7. fitEllipse() on largest contour
    8. major_px = max(w, h), minor_px = min(w, h)
    """

    def __init__(self, config):
        self.config = config
        self._model = None

    def load_model(self):
        """Load YOLO model. Called ONCE at startup."""
        model_path = self.config.model_path
        
        # Load PyTorch YOLO model
        try:
            from ultralytics import YOLO
            
            if self.config.cpu_threads > 0:
                import torch
                torch.set_num_threads(self.config.cpu_threads)
                logger.info(f"Limiting PyTorch to {self.config.cpu_threads} CPU cores.")
            
            logger.info(f"Loading YOLO model: {model_path}")
            self._model = YOLO(model_path, task='detect')
            logger.info("YOLO model loaded")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    @property
    def model_loaded(self):
        """Whether the YOLO model is loaded."""
        return self._model is not None

    def detect(self, frame):
        """
        Run full detection pipeline on a single frame.
        Frame should already be undistorted if lens calibration is active.
        Returns EggDetectionResult or None if no egg found.
        """
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        height, width = frame.shape[:2]

        # YOLO detection - Use native resolution (1280) to catch tiny eggs
        # If this is too slow on your hardware, we can drop to 640, 
        # but 1280 is needed for 10mm-20mm samples.
        results = self._model(
            frame, 
            conf=self.config.confidence_threshold, 
            imgsz=1280, 
            verbose=False
        )
        
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            return None
        
        box = results[0].boxes[0]
        bbox_xyxy = box.xyxy[0].cpu().numpy()
        
        return self._process_bbox(frame, bbox_xyxy)

    def detect_with_bbox(self, frame, bbox_xyxy):
        """
        Run the geometric pipeline (Otsu + Ellipse) using a known bounding box.
        Skips the heavy YOLO inference. Used for high-speed batch processing.
        """
        return self._process_bbox(frame, bbox_xyxy)

    def _process_bbox(self, frame, bbox_xyxy):
        """Internal helper to trace the egg outline within a bounding box."""
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox_xyxy)

        # Step 2: Adaptive BB padding
        bb_w = x2 - x1
        bb_h = y2 - y1
        
        # Scale padding based on object size - smaller objects need more focused padding
        # to avoid capturing too much background noise during Otsu thresholding.
        scale_limit = 100 # Threshold for 'small' objects
        padding_factor = 0.15 if bb_w > scale_limit else 0.08
        
        pad_x = max(8, int(bb_w * padding_factor)) # Use at least 8px for tiny ones
        pad_y = max(8, int(bb_h * padding_factor))
        x1_pad = max(0, x1 - pad_x)
        y1_pad = max(0, y1 - pad_y)
        x2_pad = min(width, x2 + pad_x)
        y2_pad = min(height, y2 + pad_y)

        # Step 3: Otsu threshold on padded ROI
        roi = frame[y1_pad:y2_pad, x1_pad:x2_pad]
        if roi.size == 0:
            return None
            
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, mask_roi = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Step 5: Morphological close
        kernel = np.ones((5, 5), np.uint8)
        mask_roi = cv2.morphologyEx(mask_roi, cv2.MORPH_CLOSE, kernel, iterations=1)

        # Map ROI mask back to full image coordinates
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[y1_pad:y2_pad, x1_pad:x2_pad] = mask_roi

        # Step 6: Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

        if not contours:
            return None

        cnt = max(contours, key=cv2.contourArea)

        if len(cnt) < 5:
            return None
            
        # Basic validation: ensure the contour isn't basically empty
        area = cv2.contourArea(cnt)
        
        # Shape Validation - COMPLETELY DISABLED for small sample testing
        # We will now trust the YOLO bounding box 100%
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0
        
        # Step 7: Fit ellipse
        ellipse = cv2.fitEllipse(cnt)
        (cx, cy), (w, h), angle = ellipse
        major_px = float(max(w, h))
        minor_px = float(min(w, h))
        ratio = major_px / minor_px if minor_px > 0 else 0
        
        logger.debug(f"ROI Processed: Area={area:.1f}, Ratio={ratio:.2f}, Sol={solidity:.2f}")

        return EggDetectionResult(
            major_px=major_px,
            minor_px=minor_px,
            ellipse=ellipse,
            contour=cnt,
            bbox_xyxy=bbox_xyxy # Carry over the bbox for potential reuse
        )
