import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class DisplayOverlay:
    """
    Handles all OpenCV drawing operations: contours, ellipses,
    axis lines, text, progress bars, center zone guides.
    """

    def __init__(self, config):
        self.config = config

    def draw_egg(self, display, result, color_bgr=None):
        """
        Draw egg detection overlay: contour, ellipse, axis lines, center dot.
        color_bgr: Custom BGR color tuple. If None, uses default green (0, 255, 0) for stability.
        Returns (major_px, minor_px).
        """
        if color_bgr is None:
            color_bgr = (0, 255, 0)  # Default: green (stable)
        
        ellipse_color = color_bgr
        contour_color = (color_bgr[0], color_bgr[1], min(255, color_bgr[2] + 50))  # Lighter for contrast
        line_contour = (200, 200, 200) if color_bgr == (150, 150, 150) else (0, 255, 255)  # Adapt to gray
        
        (cx, cy), (w, h), angle = result.ellipse

        # Contour + ellipse (convert to int32 for drawing if needed)
        draw_cnt = np.array(result.contour, dtype=np.int32)
        cv2.drawContours(display, [draw_cnt], -1, line_contour, 2)
        cv2.ellipse(display, result.ellipse, ellipse_color, 3)

        # Compute angle for axis drawing
        if w > h:
            angle_rad = np.deg2rad(angle)
        else:
            angle_rad = np.deg2rad(angle + 90)

        maj = result.major_px
        mn = result.minor_px

        # Length line (blue)
        dx = np.cos(angle_rad) * maj / 2
        dy = np.sin(angle_rad) * maj / 2
        cv2.line(display,
                 (int(cx - dx), int(cy - dy)),
                 (int(cx + dx), int(cy + dy)),
                 (255, 0, 0), 3)

        # Width line (red)
        dx = np.sin(angle_rad) * mn / 2
        dy = -np.cos(angle_rad) * mn / 2
        cv2.line(display,
                 (int(cx - dx), int(cy - dy)),
                 (int(cx + dx), int(cy + dy)),
                 (0, 0, 255), 3)

        # Center dot
        cv2.circle(display, (int(cx), int(cy)), 5, (255, 255, 255), -1)

        return result.major_px, result.minor_px

    def draw_measurements(self, display, length_mm, width_mm, major_px, minor_px,
                          in_center=True):
        """Draw measurement text overlay."""
        cv2.putText(display, f"Length: {length_mm:.2f} mm ({major_px:.0f}px)",
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        cv2.putText(display, f"Width:  {width_mm:.2f} mm ({minor_px:.0f}px)",
                    (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(display, f"Ratio:  {major_px / minor_px:.3f}",
                    (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if not in_center:
            cv2.putText(display, "MOVE EGG TO CENTER",
                        (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

    def draw_center_zone(self, display, width, height, in_center):
        """Draw center zone rectangle guide."""
        zone = self.config.center_zone
        zone_x1 = int(width * (1 - zone) / 2)
        zone_y1 = int(height * (1 - zone) / 2)
        zone_x2 = int(width - zone_x1)
        zone_y2 = int(height - zone_y1)

        color = (0, 255, 0) if in_center else (0, 165, 255)
        cv2.rectangle(display, (zone_x1, zone_y1), (zone_x2, zone_y2), color, 2)

    def draw_progress_bar(self, display, progress):
        """Draw capture progress bar at bottom of frame."""
        h = display.shape[0]
        bar_w = display.shape[1] - 40
        cv2.rectangle(display, (20, h - 30),
                      (20 + int(bar_w * progress), h - 15), (0, 255, 0), -1)
        cv2.rectangle(display, (20, h - 30),
                      (20 + bar_w, h - 15), (200, 200, 200), 1)

    def draw_status(self, display, text, has_lens=False):
        """Draw status bar text at bottom."""
        h = display.shape[0]
        lens_tag = "LENS:ON" if has_lens else "LENS:OFF"
        cv2.putText(display, f"{text}  [{lens_tag}]",
                    (20, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def draw_capture_status(self, display, frame_num, total, result):
        """Draw capture progress overlay during multi-frame capture."""
        if result is not None:
            cv2.putText(display,
                        f"CAPTURING {frame_num}/{total}  L:{result.major_px:.0f}px W:{result.minor_px:.0f}px",
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display,
                        f"CAPTURING {frame_num}/{total}  (no egg)",
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    def is_in_center_zone(self, cx, cy, width, height):
        """Check if a point (cx, cy) is within the center zone."""
        zone = self.config.center_zone
        zone_x1 = int(width * (1 - zone) / 2)
        zone_y1 = int(height * (1 - zone) / 2)
        zone_x2 = int(width - zone_x1)
        zone_y2 = int(height - zone_y1)
        return zone_x1 <= cx <= zone_x2 and zone_y1 <= cy <= zone_y2

    def draw_diagnostic_circle(self, display, pixel_per_mm):
        """
        Draw a thin circle at the center representing a physical radius.
        Used for IoT team accuracy diagnostics at different locations.
        """
        if not self.config.show_diagnostic_circle:
            return

        h, w = display.shape[:2]
        center = (w // 2, h // 2)
        radius_px = int(self.config.diagnostic_circle_radius_mm / pixel_per_mm)

        # Draw the circle (thin light gray)
        cv2.circle(display, center, radius_px, (180, 180, 180), 1)

        # Draw a small label with the diameter
        diameter_cm = (self.config.diagnostic_circle_radius_mm * 2) / 10.0
        label = f"DIAG ZONE: {diameter_cm:.1f}cm"
        cv2.putText(display, label, (center[0] - 80, center[1] + radius_px + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
