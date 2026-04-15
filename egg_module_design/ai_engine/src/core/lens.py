import logging

logger = logging.getLogger(__name__)


class LensCalibrator:
    """
    Interactive checkerboard lens calibration.
    Handles corner detection, coverage tracking, and camera matrix computation.
    Used by calibration entry point only.
    """

    def __init__(self, config, camera):
        self.config = config
        self.camera = camera

    def run(self, square_size_mm=None):
        """
        Interactive checkerboard calibration loop.
        Returns lens calibration dict or None if cancelled/insufficient captures.
        """
        if square_size_mm is None:
            square_size_mm = self.config.default_square_size_mm

        cb_size = self.config.checkerboard_size

        logger.info("LENS CALIBRATION: Sequence Initialized")
        logger.info(f"Target: {cb_size[0]}x{cb_size[1]} checkerboard corners")
        logger.info(f"Capture Target: {self.config.min_lens_images} frames minimum")
        logger.info("Controls: [SPACE] to capture, [Q] to finish")

        # Prepare 3D object points
        objp = np.zeros((cb_size[0] * cb_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:cb_size[0], 0:cb_size[1]].T.reshape(-1, 2)
        objp *= square_size_mm

        obj_points = []
        img_points = []
        image_size = None
        capture_count = 0

        # Coverage tracking (3x3 grid)
        coverage = np.zeros((3, 3), dtype=int)

        while True:
            # Use latest frame (buffer flushing) for real-time response during lens calibration
            ret, frame = self.camera.read_frame_latest(max_skip=5)
            if not ret or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            image_size = (gray.shape[1], gray.shape[0])
            display = frame.copy()

            # Find checkerboard corners
            flags = (cv2.CALIB_CB_ADAPTIVE_THRESH +
                     cv2.CALIB_CB_NORMALIZE_IMAGE +
                     cv2.CALIB_CB_FAST_CHECK)
            found, corners = cv2.findChessboardCorners(gray, cb_size, flags)

            if found:
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                cv2.drawChessboardCorners(display, cb_size, corners_refined, found)
                cv2.putText(display,
                            f"CORNERS FOUND - Press SPACE to capture ({capture_count} saved)",
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.putText(display,
                            f"Move checkerboard into view ({capture_count} saved)",
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # Draw coverage grid
            grid_h, grid_w = 3, 3
            cell_w = image_size[0] // grid_w
            cell_h = image_size[1] // grid_h
            for r in range(grid_h):
                for c in range(grid_w):
                    x = c * cell_w
                    y = r * cell_h
                    color = (0, 100, 0) if coverage[r][c] > 0 else (50, 50, 50)
                    cv2.rectangle(display, (x + 2, y + 2),
                                  (x + cell_w - 2, y + cell_h - 2), color, 1)
                    if coverage[r][c] > 0:
                        cv2.putText(display, str(coverage[r][c]),
                                    (x + 10, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                    (0, 200, 0), 1)

            status = f"Captures: {capture_count}/{self.config.min_lens_images}  SPACE=Capture  Q=Done"
            cv2.putText(display, status,
                        (20, display.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (200, 200, 200), 1)

            cv2.imshow("Lens Calibration - Checkerboard", display)

            key = cv2.waitKey(30) & 0xFF # Increased timeout for better key detection
            
            if key == ord(' ') or key == 13: # Support SPACE or ENTER
                if found:
                    obj_points.append(objp)
                    img_points.append(corners_refined)
                    capture_count += 1
                    
                    # Flash effect on capture
                    display[:, :, 1] = 255 
                    cv2.imshow("Lens Calibration - Checkerboard", display)
                    cv2.waitKey(100)

                    # Update coverage
                    for corner in corners_refined.reshape(-1, 2):
                        col = min(int(corner[0] / image_size[0] * grid_w), grid_w - 1)
                        row = min(int(corner[1] / image_size[1] * grid_h), grid_h - 1)
                        coverage[row][col] += 1

                    logger.info(f"Capture: Frame {capture_count}/{self.config.min_lens_images} successfully saved.")
                else:
                    logger.warning("Capture Failed: Checkerboard corners not detected in this frame.")

            elif key == ord('q') or key == 27: # Support Q or ESC
                logger.info("Sequence Terminated: Finalizing calibration data...")
                break

        cv2.destroyAllWindows()

        if capture_count < self.config.min_lens_images:
            logger.error(f"Calibration Aborted: {capture_count} images is below the required threshold of {self.config.min_lens_images}.")
            return None

        # Compute calibration
        logger.info(f"Processing: Calculating camera matrix from {capture_count} image samples...")
        ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            obj_points, img_points, image_size, None, None
        )

        # Per-image reprojection errors
        total_error = 0
        for i in range(len(obj_points)):
            projected, _ = cv2.projectPoints(
                obj_points[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs
            )
            error = cv2.norm(img_points[i], projected, cv2.NORM_L2) / len(projected)
            total_error += error

        avg_error = total_error / len(obj_points)

        logger.info("--- LENS CALIBRATION METRICS ---")
        logger.info(f"  Reprojection Error: {avg_error:.4f} px (Industrial Target: < 0.5)")
        logger.info(f"  Effective Samples:  {capture_count}")

        if avg_error > 0.5:
            logger.warning(f"Accuracy Alert: Reprojection error {avg_error:.4f} exceeds target threshold.")

        uncovered = np.sum(coverage == 0)
        if uncovered > 0:
            logger.warning(f"Coverage Alert: {uncovered} grid sectors had no calibration samples.")

        # Compute homography for bird's-eye view (High Precision)
        homography = None
        if self.config.high_precision and len(img_points) > 0:
            # Use the corners from the last successful capture to define the ground plane
            # We map them to a centered grid in the image
            src_pts = img_points[-1].reshape(-1, 2)
            
            # Define target points: a perfect grid centered in the frame
            w, h = image_size
            grid_w = (cb_size[0] - 1) * square_size_mm
            grid_h = (cb_size[1] - 1) * square_size_mm
            
            # Scale grid to fit ~half the image height
            target_scale = (h * 0.5) / grid_h
            
            dst_pts = []
            start_x = (w - grid_w * target_scale) / 2
            start_y = (h - grid_h * target_scale) / 2
            
            for r in range(cb_size[1]):
                for c in range(cb_size[0]):
                    dst_pts.append([start_x + c * square_size_mm * target_scale,
                                   start_y + r * square_size_mm * target_scale])
            
            dst_pts = np.array(dst_pts, dtype=np.float32)
            homography, _ = cv2.findHomography(src_pts, dst_pts)
            
            # Geometric scale: Exactly 1.0 / target_scale
            homography_ptm = 1.0 / target_scale

        return {
            "camera_matrix": camera_matrix.tolist(),
            "dist_coeffs": dist_coeffs.tolist(),
            "homography": homography.tolist() if homography is not None else None,
            "homography_ptm": homography_ptm if homography is not None else None,
            "reprojection_error": float(avg_error),
            "image_size": list(image_size),
            "num_images": capture_count,
            "square_size_mm": float(square_size_mm),
        }
