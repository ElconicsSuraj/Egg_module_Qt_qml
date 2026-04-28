import cv2
import numpy as np
import logging
import os

logger = logging.getLogger(__name__)


class CameraManager:
    """
    Manages camera lifecycle: open, read, undistort, release.
    Lens undistortion uses pre-computed remap maps for speed.
    """

    def __init__(self, config):
        self.config = config
        self._cap = None
        self._camera_index = -1
        self._camera_matrix = None
        self._dist_coeffs = None
        self._homography = None
        self._map1 = None
        self._map2 = None

    def open(self, preferred_index=None):
        """
        Try to open a camera, testing multiple indices.
        Returns True if successful.
        """
        idx = preferred_index if preferred_index is not None else self.config.camera_index
        for try_idx in [idx, 0, 1, 2]:
            # Use DSHOW on Windows for better stability
            backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
            cap = cv2.VideoCapture(try_idx, backend)
            
            if cap.isOpened():
                # Set resolution BEFORE reading first frame
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
                
                # Lock settings (Try to disable Auto-Focus and Auto-Exposure for metrology)
                # Note: Some USB cameras (IPEVO) require these to be set to specific values
                cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
                # cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1) # Generally 1 or 0 is manual
                
                # Flush buffer (read a few frames)
                for _ in range(5):
                    ret, frame = cap.read()
                    
                if ret and frame is not None:
                    self._cap = cap
                    self._camera_index = try_idx
                    actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    logger.info(f"Camera {try_idx} opened: {actual_w}x{actual_h}")
                    return True
                cap.release()
        logger.error("Could not open any camera")
        return False

    @property
    def is_open(self):
        return self._cap is not None and self._cap.isOpened()

    @property
    def camera_index(self):
        return self._camera_index

    @property
    def resolution(self):
        """Return (width, height) of current camera."""
        if self._cap is None:
            return (0, 0)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    @property
    def has_lens_calibration(self):
        return self._camera_matrix is not None

    @property
    def has_homography(self):
        return self._homography is not None

    def set_lens_calibration(self, camera_matrix, dist_coeffs):
        """
        Store lens calibration and pre-compute undistortion maps.
        Uses cv2.initUndistortRectifyMap for fast remap.
        """
        self._camera_matrix = camera_matrix
        self._dist_coeffs = dist_coeffs
        w, h = self.resolution
        if w > 0 and h > 0:
            self._map1, self._map2 = cv2.initUndistortRectifyMap(
                camera_matrix, dist_coeffs, None, camera_matrix,
                (w, h), cv2.CV_16SC2
            )
            logger.info("Undistortion maps computed")

    def set_homography(self, homography):
        """Store homography matrix for bird's-eye view projection."""
        self._homography = homography
        logger.info("Homography matrix stored")

    def read_frame(self):
        """Read a raw frame from camera. Returns (success, frame)."""
        if self._cap is None:
            return False, None
        return self._cap.read()

    def read_frame_latest(self, max_skip=5):
        """
        Read the LATEST frame from camera, skipping old buffered frames.
        This is critical for real-time response - prevents 3+ second delays.
        
        When YOLO takes 340ms but camera captures at ~30fps (33ms per frame),
        the buffer accumulates ~10 old frames. This method drains the queue
        and returns only the newest frame.
        
        Args:
            max_skip: Maximum frames to skip looking for latest (default: 5)
        
        Returns:
            (success, frame_undistorted) - The latest available frame with lens correction applied
        """
        ret, frame = self._cap.read()
        if not ret:
            return ret, frame
        
        # Try to read a few more frames to get the latest
        # (non-blocking, will fail when buffer empty)
        for _ in range(max_skip):
            ret_new, frame_new = self._cap.read()
            if ret_new:
                frame = frame_new  # Keep newest
            else:
                break  # Done reading buffer
        
        # Apply undistortion to the latest frame
        if ret and frame is not None:
            frame = self.undistort(frame)
            if self.config.high_precision and self._homography is not None:
                frame = self.warp_perspective(frame)
        
        return ret, frame if frame is not None else None

    def read_undistorted_frame(self):
        """Read frame with lens correction (and homography if enabled) applied."""
        # Periodically re-enforce hardware locks to fight IPEVO firmware resets
        if hasattr(self, '_frame_count'):
            self._frame_count += 1
            if self._frame_count % 100 == 0:
                self.force_lock_settings()
        else:
            self._frame_count = 1

        ret, frame = self.read_frame()
        if ret and frame is not None:
            frame = self.undistort(frame)
            if self.config.high_precision and self._homography is not None:
                frame = self.warp_perspective(frame)
        return ret, frame

    def warp_perspective(self, frame):
        """Apply homography warp to get bird's-eye view."""
        if self._homography is not None:
            w, h = self.resolution
            if w > 0 and h > 0 and frame is not None and frame.size > 0:
                return cv2.warpPerspective(frame, self._homography, (w, h))
        return frame

    def undistort(self, frame):
        """Apply lens undistortion to a frame. Uses fast remap if maps available."""
        if self._map1 is not None and self._map2 is not None:
            return cv2.remap(frame, self._map1, self._map2, cv2.INTER_LINEAR)
        elif self._camera_matrix is not None and self._dist_coeffs is not None:
            return cv2.undistort(frame, self._camera_matrix, self._dist_coeffs)
        return frame

    def force_lock_settings(self):
        """Aggressively disable auto-focus and auto-exposure."""
        if self._cap is not None:
            # For IPEVO, we must set these multiple times
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            # Re-read focus current to 'trap' it
            focus = self._cap.get(cv2.CAP_PROP_FOCUS)
            self._cap.set(cv2.CAP_PROP_FOCUS, focus)
            
    def release(self):
        """Release camera resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
