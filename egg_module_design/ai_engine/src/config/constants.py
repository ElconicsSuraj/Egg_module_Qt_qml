import os
import logging
from dotenv import load_dotenv


class Config:
    """Loads all configuration from .env file with typed defaults."""

    def __init__(self, env_path=None):
        load_dotenv(env_path or ".env")

        # --- Core Paths (Usually in .env) ---
        self.model_path = os.getenv("MODEL_PATH", "media/best.pt")
        self.calibration_file = os.getenv("CALIBRATION_FILE", "media/calibration_data.json")
        self.calibration_mode = os.getenv("CALIBRATION_MODE", "measure")
        self.api_port = int(os.getenv("API_PORT", "8000"))

        # --- Hardware (Usually in .env) ---
        self.camera_index = int(os.getenv("CAMERA_INDEX", "0"))
        self.camera_width = int(os.getenv("CAMERA_WIDTH", "1280"))
        self.camera_height = int(os.getenv("CAMERA_HEIGHT", "720"))
        self.camera_height_mm = float(os.getenv("CAMERA_HEIGHT_MM", "300.0"))

        # --- Detection Pipeline (Sensible Defaults) ---
        self.confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
        self.bb_padding = int(os.getenv("BB_PADDING", "50"))
        self.pipeline_version = int(os.getenv("PIPELINE_VERSION", "3"))
        self.cpu_threads = int(os.getenv("CPU_THREADS", "0"))

        # --- Calibration Settings (Sensible Defaults) ---
        self.num_calibration_frames = int(os.getenv("NUM_CALIBRATION_FRAMES", "20"))
        self.num_verify_frames = int(os.getenv("NUM_VERIFY_FRAMES", "50"))
        self.warmup_seconds = int(os.getenv("WARMUP_SECONDS", "2"))
        self.enable_calibration_check = os.getenv("ENABLE_CALIBRATION_CHECK", "True").lower() == "true"
        self.enable_auto_egg_mode = os.getenv("ENABLE_AUTO_EGG_CALIBRATION", "False").lower() == "true"
        self.checkerboard_size = (
            int(os.getenv("CHECKERBOARD_COLS", "9")),
            int(os.getenv("CHECKERBOARD_ROWS", "7"))
        )
        self.min_lens_images = int(os.getenv("MIN_LENS_IMAGES", "10"))
        self.default_square_size_mm = float(os.getenv("DEFAULT_SQUARE_SIZE_MM", "25.0"))

        # --- Measurement Specs (Sensible Defaults) ---
        self.center_zone = float(os.getenv("CENTER_ZONE", "0.6"))
        self.settle_delay_s = float(os.getenv("SETTLE_DELAY_S", "2.0"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "1"))
        self.draw_window_size = int(os.getenv("DRAW_WINDOW_SIZE", "20"))
        self.egg_loss_timeout_s = float(os.getenv("EGG_LOSS_TIMEOUT_S", "0.5"))
        self.measure_max_attempts = int(os.getenv("MEASURE_MAX_ATTEMPTS", "50"))
        
        # --- Advanced Accuracy & Physics ---
        self.high_precision = os.getenv("HIGH_PRECISION", "true").lower() == "true"
        self.use_height_compensation = os.getenv("USE_HEIGHT_COMPENSATION", "true").lower() == "true"
        self.perspective_coeff = float(os.getenv("PERSPECTIVE_COEFF", "0.0025"))
        self.egg_height_ratio = float(os.getenv("EGG_HEIGHT_RATIO", "0.7"))
        self.x_axis_scale_factor = float(os.getenv("X_AXIS_SCALE_FACTOR", "0.985"))
        self.length_scale_factor = float(os.getenv("LENGTH_SCALE_FACTOR", "1.0"))
        self.width_bias_mm = float(os.getenv("WIDTH_BIAS_MM", "0.0"))
        self.radial_perspective_correction = float(os.getenv("RADIAL_PERSPECTIVE_CORRECTION", "0.03"))
        self.confidence_strictness = float(os.getenv("CONFIDENCE_STRICTNESS", "60.0"))
        self.confidence_ceiling = float(os.getenv("CONFIDENCE_CEILING", "97.5"))

        # --- UI & Logging ---
        self.show_diagnostic_circle = os.getenv("SHOW_DIAGNOSTIC_CIRCLE", "true").lower() == "true"
        self.diagnostic_circle_radius_mm = float(os.getenv("DIAGNOSTIC_CIRCLE_RADIUS_MM", "50.0"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.measurement_log_file = os.getenv("MEASUREMENT_LOG_FILE", "egg_measurements.txt")

    def setup_logging(self):
        """Configure logging based on config."""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
