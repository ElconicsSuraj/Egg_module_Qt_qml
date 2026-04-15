import json
import os
import time
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class MultiCalibrationEntry:
    """A profile for a specific 'Golden Egg' used in the library."""
    label: str
    known_length_mm: float
    known_width_mm: float
    avg_major_px: float
    avg_minor_px: float
    pixel_to_mm_length: float
    pixel_to_mm_width: float
    frames_used: int
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    def to_dict(self):
        return {
            "label": self.label,
            "known_length_mm": self.known_length_mm,
            "known_width_mm": self.known_width_mm,
            "avg_major_px": round(self.avg_major_px, 2),
            "avg_minor_px": round(self.avg_minor_px, 2),
            "pixel_to_mm_length": round(self.pixel_to_mm_length, 8),
            "pixel_to_mm_width": round(self.pixel_to_mm_width, 8),
            "frames_used": self.frames_used,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class MultiCalibrationLibrary:
    """Manages a collection of Golden Egg profiles for Auto-Egg Calibration."""
    def __init__(self, entries: List[MultiCalibrationEntry] = None):
        self.entries = entries or []

    def find_nearest_entry(self, major_px: float, minor_px: float) -> Optional[MultiCalibrationEntry]:
        """Find the Golden Egg closest to the current detection in pixel space."""
        if not self.entries:
            return None
        
        best_dist = float('inf')
        best_match = None
        
        for entry in self.entries:
            # Euclidean distance in pixel space
            dist = np.sqrt((major_px - entry.avg_major_px)**2 + (minor_px - entry.avg_minor_px)**2)
            if dist < best_dist:
                best_dist = dist
                best_match = entry
        return best_match

    def interpolate_factors(self, major_px: float, minor_px: float):
        """
        Calculates precise PTM factors using linear interpolation across all library entries.
        Works for 1 to N eggs. Extrapolates using edge values if egg is out of range.
        """
        if not self.entries:
            return None, None
        
        if len(self.entries) == 1:
            return self.entries[0].pixel_to_mm_length, self.entries[0].pixel_to_mm_width
            
        # Sort by pixel size (required for np.interp)
        sorted_l = sorted(self.entries, key=lambda x: x.avg_major_px)
        sorted_w = sorted(self.entries, key=lambda x: x.avg_minor_px)
        
        # Project PTM-Length based on Major Axis
        px_majors = [e.avg_major_px for e in sorted_l]
        ptm_ls = [e.pixel_to_mm_length for e in sorted_l]
        ptm_l = float(np.interp(major_px, px_majors, ptm_ls))
        
        # Project PTM-Width based on Minor Axis
        px_minors = [e.avg_minor_px for e in sorted_w]
        ptm_ws = [e.pixel_to_mm_width for e in sorted_w]
        ptm_w = float(np.interp(minor_px, px_minors, ptm_ws))
        
        return ptm_l, ptm_w

    def upsert(self, entry: MultiCalibrationEntry):
        """Update existing egg profile (by label) or add new one."""
        for i, existing in enumerate(self.entries):
            if existing.label == entry.label:
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def to_dict(self):
        return [e.to_dict() for e in self.entries]

    def __len__(self):
        return len(self.entries)


@dataclass
class CalibrationData:
    """Loaded calibration data."""
    pixel_to_mm_length: float = None
    pixel_to_mm_width: float = None
    camera_matrix: np.ndarray = None
    dist_coeffs: np.ndarray = None
    homography: np.ndarray = None
    homography_ptm: float = None
    avg_major_px: float = 0.0
    avg_minor_px: float = 0.0
    pipeline_version: int = None
    
    # Store library reference for lookup
    multi_cal_library: Optional[MultiCalibrationLibrary] = None

    @property
    def has_scale(self):
        return self.pixel_to_mm_length is not None or (self.multi_cal_library and len(self.multi_cal_library) > 0)

    @property
    def pixel_to_mm_avg(self):
        if self.pixel_to_mm_length is not None and self.pixel_to_mm_width is not None:
            return (self.pixel_to_mm_length + self.pixel_to_mm_width) / 2
        return None

    @property
    def has_lens(self):
        return self.camera_matrix is not None

    @property
    def has_homography(self):
        return self.homography is not None


class CalibrationManager:
    """
    Handles calibration data: loading, saving, computing scale factors,
    IQR filtering, and verification.
    """

    def __init__(self, config):
        self.config = config

    def multi_cal_filepath(self):
        return self.config.calibration_file.replace(".json", "_multi_library.json")

    def load_library(self) -> MultiCalibrationLibrary:
        """Load the Multi-Egg library from disk."""
        path = self.multi_cal_filepath()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    # Handle both flat list format and nested dict format
                    if isinstance(data, dict) and "entries" in data:
                        entry_list = data["entries"]
                    elif isinstance(data, list):
                        entry_list = data
                    else:
                        entry_list = []
                    
                    entries = []
                    for d in entry_list:
                        if isinstance(d, dict):
                            entries.append(MultiCalibrationEntry.from_dict(d))
                    return MultiCalibrationLibrary(entries)
            except Exception as e:
                logger.error(f"Failed to load multi-cal library: {e}")
        return MultiCalibrationLibrary()

    def save_library(self, library: MultiCalibrationLibrary):
        """Save the Multi-Egg library to disk."""
        path = self.multi_cal_filepath()
        with open(path, "w") as f:
            json.dump(library.to_dict(), f, indent=2)
        logger.info(f"Multi-Egg library updated: {path}")

    def load(self):
        """
        Load calibration from JSON file.
        Returns CalibrationData with None fields if file missing.
        """
        filepath = self.config.calibration_file
        camera_matrix = None
        dist_coeffs = None
        ptm_l = None
        ptm_w = None
        homography = None
        homography_ptm = None
        avg_maj = 0.0
        avg_min = 0.0
        pipeline_ver = None

        # Load Multi-Egg Library
        multi_lib = self.load_library()

        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                data = json.load(f)

            # Check pipeline version
            pipeline_ver = data.get("pipeline_version", 1)
            if pipeline_ver < self.config.pipeline_version:
                logger.warning(
                    f"Calibration was created with pipeline v{pipeline_ver} "
                    f"(current: v{self.config.pipeline_version}). "
                    "Recalibrate for best accuracy."
                )

            # Scale calibration
            if data.get("version", 1) >= 2 and "pixel_to_mm_length" in data:
                ptm_l = data["pixel_to_mm_length"]
                ptm_w = data["pixel_to_mm_width"]

                # Load stats if available
                if "stats" in data:
                    avg_maj = data["stats"].get("major_px_mean", 0.0)
                    avg_min = data["stats"].get("minor_px_mean", 0.0)
            elif "pixel_to_mm" in data:
                avg = data["pixel_to_mm"]
                ptm_l = avg
                ptm_w = avg

            if "lens" in data and data["lens"] is not None:
                camera_matrix = np.array(data["lens"]["camera_matrix"], dtype=np.float64)
                dist_coeffs = np.array(data["lens"]["dist_coeffs"], dtype=np.float64)

            if "homography" in data and data["homography"] is not None:
                homography = np.array(data["homography"], dtype=np.float64)

            homography_ptm = data.get("homography_ptm", None)

            homography_ptm = data.get("homography_ptm", None)

        # Try legacy calibration.json for scale
        if ptm_l is None:
            legacy = "calibration.json"
            if filepath != legacy and os.path.exists(legacy):
                with open(legacy, "r") as f:
                    data = json.load(f)
                avg = data.get("pixel_to_mm", None)
                if avg:
                    ptm_l = avg
                    ptm_w = avg

        cal = CalibrationData(
            pixel_to_mm_length=ptm_l,
            pixel_to_mm_width=ptm_w,
            camera_matrix=camera_matrix,
            dist_coeffs=dist_coeffs,
            homography=homography,
            homography_ptm=homography_ptm,
            avg_major_px=avg_maj,
            avg_minor_px=avg_min,
            pipeline_version=pipeline_ver,
            multi_cal_library=multi_lib
        )

        if cal.has_scale:
            logger.info(f"Calibration loaded: PTM_L={ptm_l:.6f}, PTM_W={ptm_w:.6f}")
        if cal.has_lens:
            logger.info("Lens calibration loaded")

        return cal

    def save(self, cal_data, stats, reference, verification, lens_data=None):
        """
        Save calibration data to JSON. Preserves existing lens and dual data if not provided.
        """
        filepath = self.config.calibration_file

        # Load existing data to preserve lens section
        existing_lens = None
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                existing = json.load(f)
            existing_lens = existing.get("lens", None)

        data = {
            "version": 3,
            "pipeline_version": self.config.pipeline_version,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pixel_to_mm_length": cal_data["pixel_to_mm_length"],
            "pixel_to_mm_width": cal_data["pixel_to_mm_width"],
            "pixel_to_mm_avg": cal_data["pixel_to_mm_avg"],
            "stats": stats,
            "reference_egg": reference,
            "verification": verification,
            "lens": lens_data if lens_data is not None else existing_lens,
            "homography": cal_data.get("homography", None),
            "homography_ptm": cal_data.get("homography_ptm", None),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Calibration saved to: {filepath}")


    def save_lens_only(self, lens_data):
        """Save lens calibration data, preserving existing scale calibration."""
        filepath = self.config.calibration_file

        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                data = json.load(f)
        else:
            data = {"version": 3, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}

        data["lens"] = lens_data
        if "homography" in lens_data:
            data["homography"] = lens_data["homography"]
        data["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Lens calibration saved to: {filepath}")

    @staticmethod
    def filter_outliers_iqr(measurements):
        """
        Remove outlier measurements using IQR method.
        Returns (filtered_measurements, num_removed).
        """
        if len(measurements) < 4:
            return measurements, 0

        majors = np.array([m[0] for m in measurements])
        minors = np.array([m[1] for m in measurements])

        q1_maj, q3_maj = np.percentile(majors, [25, 75])
        iqr_maj = q3_maj - q1_maj
        low_maj = q1_maj - 1.5 * iqr_maj
        high_maj = q3_maj + 1.5 * iqr_maj

        q1_min, q3_min = np.percentile(minors, [25, 75])
        iqr_min = q3_min - q1_min
        low_min = q1_min - 1.5 * iqr_min
        high_min = q3_min + 1.5 * iqr_min

        filtered = [
            m for m in measurements
            if low_maj <= m[0] <= high_maj and low_min <= m[1] <= high_min
        ]

        num_removed = len(measurements) - len(filtered)
        return filtered, num_removed

    @staticmethod
    def compute_calibration(filtered_measurements, known_length_mm, known_width_mm):
        """Compute pixel-to-mm calibration factors from filtered measurements."""
        majors = np.array([m[0] for m in filtered_measurements])
        minors = np.array([m[1] for m in filtered_measurements])

        avg_major = np.mean(majors)
        avg_minor = np.mean(minors)
        std_major = np.std(majors)
        std_minor = np.std(minors)

        pixel_to_mm_length = known_length_mm / avg_major
        pixel_to_mm_width = known_width_mm / avg_minor
        pixel_to_mm_avg = (pixel_to_mm_length + pixel_to_mm_width) / 2

        return {
            "pixel_to_mm_length": float(pixel_to_mm_length),
            "pixel_to_mm_width": float(pixel_to_mm_width),
            "pixel_to_mm_avg": float(pixel_to_mm_avg),
            "avg_major_px": float(avg_major),
            "avg_minor_px": float(avg_minor),
            "std_major_px": float(std_major),
            "std_minor_px": float(std_minor),
        }
