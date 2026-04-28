"""
Multi-Technique Egg Shape Extractor
Uses multiple CV techniques to get EXACT oval shape of egg
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EggShapeExtractor:
    """Extract egg oval shape using multiple complementary techniques"""

    def __init__(self, config):
        self.config = config

    def extract_egg_shape(self, frame, roi_coords=None):
        """
        Extract egg shape using multiple techniques and return best result.

        Returns:
            ellipse: (center, (major, minor), angle)
            contour: The actual contour points
            confidence: 0-1 score indicating quality
        """

        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # === TECHNIQUE 1: OTSU THRESHOLDING (Most robust) ===
        logger.debug("[T1] Otsu Thresholding...")
        _, mask_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Morphology: Close small holes, open background noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask_otsu = cv2.morphologyEx(mask_otsu, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask_otsu = cv2.morphologyEx(mask_otsu, cv2.MORPH_OPEN, kernel, iterations=1)

        contours_otsu = cv2.findContours(mask_otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]

        # === TECHNIQUE 2: ADAPTIVE THRESHOLDING (Handles lighting variation) ===
        logger.debug("[T2] Adaptive Thresholding...")
        mask_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY_INV, 21, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_adapt = cv2.morphologyEx(mask_adapt, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours_adapt = cv2.findContours(mask_adapt, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]

        # === TECHNIQUE 3: CANNY + MORPHOLOGY (Edge-based) ===
        logger.debug("[T3] Canny Edge Detection...")
        blurred = cv2.GaussianBlur(gray, (5, 5), 1)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours_canny = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]

        # === TECHNIQUE 4: LAPLACIAN (Gradient-based) ===
        logger.debug("[T4] Laplacian Detection...")
        laplacian = cv2.Laplacian(gray, cv2.CV_32F)
        laplacian = np.abs(laplacian)
        laplacian = cv2.normalize(laplacian, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, mask_laplacian = cv2.threshold(laplacian, 50, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_laplacian = cv2.morphologyEx(mask_laplacian, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours_laplacian = cv2.findContours(mask_laplacian, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]

        # === EXTRACT ELLIPSES FROM ALL TECHNIQUES ===
        logger.debug("[EXTRACTION] Fitting ellipses from all techniques...")
        results = []

        for name, contours in [
            ("OTSU", contours_otsu),
            ("ADAPTIVE", contours_adapt),
            ("CANNY", contours_canny),
            ("LAPLACIAN", contours_laplacian)
        ]:
            if not contours:
                logger.debug(f"  {name}: No contours")
                continue

            # Get largest contour
            cnt = max(contours, key=cv2.contourArea)

            if len(cnt) < 5:
                logger.debug(f"  {name}: Contour too small")
                continue

            # Convex hull (eggs are convex)
            cnt = cv2.convexHull(cnt)

            # Smooth contour
            cnt_smooth = self._smooth_contour(cnt)

            try:
                # Fit ellipse
                ellipse = cv2.fitEllipse(cnt_smooth)
                (cx, cy), (major, minor), angle = ellipse

                # Calculate quality metrics
                confidence = self._calculate_confidence(cnt_smooth, ellipse)

                results.append({
                    'name': name,
                    'ellipse': ellipse,
                    'contour': cnt_smooth,
                    'confidence': confidence,
                    'major': major,
                    'minor': minor,
                    'mask': None
                })

                logger.debug(f"  {name}: L={major:.1f}px W={minor:.1f}px (conf={confidence:.2f})")

            except Exception as e:
                logger.debug(f"  {name}: Fitting failed - {e}")
                continue

        if not results:
            logger.debug("NO VALID ELLIPSE FOUND")
            return None, None, 0

        # === SELECT BEST RESULT ===
        best = max(results, key=lambda x: x['confidence'])
        logger.debug(f"BEST: {best['name']} (confidence={best['confidence']:.2f})")

        return best['ellipse'], best['contour'], best['confidence']

    def _smooth_contour(self, contour, strength=1.0):
        """Smooth contour using multiple passes"""

        if len(contour) < 5:
            return contour

        # Structural smoothing
        epsilon = 0.001 * cv2.arcLength(contour, True)
        cnt = cv2.approxPolyDP(contour.astype(np.float32), epsilon, True)

        # Gaussian smoothing
        try:
            from scipy.ndimage import gaussian_filter1d
            pts = cnt.reshape(-1, 2)
            sigma = 2.0 * strength
            x_smooth = gaussian_filter1d(pts[:, 0], sigma, mode='wrap')
            y_smooth = gaussian_filter1d(pts[:, 1], sigma, mode='wrap')
            cnt = np.stack([x_smooth, y_smooth], axis=1).reshape(-1, 1, 2).astype(np.float32)
        except:
            pass

        return cnt

    def _calculate_confidence(self, contour, ellipse):
        """Calculate confidence score (0-1) of ellipse fit"""

        (cx, cy), (major, minor), angle = ellipse

        # Metric 1: Aspect ratio should be egg-like (2:1 to 1.2:1)
        ratio = major / minor if minor > 0 else 0
        ratio_score = 1.0 if 1.2 <= ratio <= 2.5 else 0.3

        # Metric 2: Contour points should be close to ellipse
        pts = contour.reshape(-1, 2)
        ellipse_pts = cv2.ellipse2Poly((int(cx), int(cy)),
                                       (int(major/2), int(minor/2)),
                                       int(angle), 0, 360, 10)

        ellipse_contour = cv2.contourArea(ellipse_pts)
        actual_contour = cv2.contourArea(contour)

        if actual_contour > 0:
            area_score = min(ellipse_contour, actual_contour) / max(ellipse_contour, actual_contour)
        else:
            area_score = 0

        # Metric 3: Circularity (perfect circle = 1.0)
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            circularity = (4 * np.pi * actual_contour) / (perimeter ** 2)
            circularity_score = min(circularity, 1.0)  # Cap at 1.0
        else:
            circularity_score = 0

        # Combined confidence
        confidence = 0.3 * ratio_score + 0.4 * area_score + 0.3 * circularity_score

        return float(confidence)

    def visualize_all_techniques(self, frame):
        """Visualize all 4 techniques side-by-side"""

        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Create 2x2 grid
        h, w = gray.shape
        grid = np.zeros((h*2, w*2, 3), dtype=np.uint8)

        techniques = [
            ("OTSU", self._otsu_mask(gray)),
            ("ADAPTIVE", self._adaptive_mask(gray)),
            ("CANNY", self._canny_mask(gray)),
            ("LAPLACIAN", self._laplacian_mask(gray))
        ]

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for (row, col), (name, mask) in zip(positions, techniques):
            # Convert mask to BGR
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            grid[row*h:(row+1)*h, col*w:(col+1)*w] = mask_bgr

            # Add label
            cv2.putText(grid, name, (col*w + 10, row*h + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        return grid

    def _otsu_mask(self, gray):
        """Otsu thresholding"""
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

    def _adaptive_mask(self, gray):
        """Adaptive thresholding"""
        mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 21, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return mask

    def _canny_mask(self, gray):
        """Canny edge detection"""
        blurred = cv2.GaussianBlur(gray, (5, 5), 1)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        return edges

    def _laplacian_mask(self, gray):
        """Laplacian edge detection"""
        laplacian = cv2.Laplacian(gray, cv2.CV_32F)
        laplacian = np.abs(laplacian)
        laplacian = cv2.normalize(laplacian, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, mask = cv2.threshold(laplacian, 50, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return mask
