from PySide6.QtCore import QObject, Signal, Property, Slot
from PySide6.QtGui import QImage

class EggModuleBridge(QObject):
    """
    UI Bridge for the Egg Module.
    Exposes properties and methods to the QML interface.
    Delegates hardware and AI logic to the engine.
    """
    updateMetrics = Signal()
    imageChanged = Signal()
    calSessionCountChanged = Signal()
    calSessionTargetChanged = Signal()

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        
        # Connect engine callbacks to signals
        self.engine.callback_metrics = self.updateMetrics.emit
        self.engine.callback_image = self.imageChanged.emit

    # --- Metrics Properties ---
    @Property(float, notify=updateMetrics)
    def weight(self): return self.engine.weight
    
    @Property(str, notify=updateMetrics)
    def length(self): return self.engine.length
    
    @Property(str, notify=updateMetrics)
    def breadth(self): return self.engine.breadth
    
    @Property(str, notify=updateMetrics)
    def confidence(self): return self.engine.confidence

    # --- Smart Guide Properties ---
    @Property(bool, notify=updateMetrics)
    def cameraConnected(self): return self.engine.camera_connected
    
    @Property(bool, notify=updateMetrics)
    def isEggDetected(self): return self.engine.is_egg_detected
    
    @Property(bool, notify=updateMetrics)
    def isCentered(self): return self.engine.is_centered
    
    @Property(bool, notify=updateMetrics)
    def isSettled(self): return self.engine.is_settled

    # --- Calibration Properties ---
    @Property(bool, notify=updateMetrics)
    def isCalibrating(self): return self.engine.is_calibrating
    
    @Property(int, notify=updateMetrics)
    def calibrationProgress(self): return self.engine.cal_progress
    
    @Property(str, notify=updateMetrics)
    def calStatus(self): return self.engine.cal_status
    
    @Property(str, notify=updateMetrics)
    def lastCalResult(self): return self.engine.last_cal_result
    
    @Property(int, notify=calSessionTargetChanged)
    def calSessionTarget(self): return self.engine.cal_session_target
    
    @Property(int, notify=calSessionCountChanged)
    def calSessionCount(self): return self.engine.cal_session_count

    # --- Slots ---
    @Slot()
    def tareScale(self):
        self.engine._tare_requested = True
        self.engine.cal_status = "Taring Scale..."
        self.updateMetrics.emit()

    @Slot(int)
    def startNewSession(self, targetCount):
        self.engine.cal_session_target = targetCount
        self.engine.cal_session_count = 0
        self.engine._session_entries = []
        self.calSessionTargetChanged.emit()
        self.calSessionCountChanged.emit()
        self.engine.cal_status = "Session Started"
        self.updateMetrics.emit()

    @Slot(float, float)
    def startAutoCalibration(self, knownL, knownW):
        self.engine._cal_known_l = knownL
        self.engine._cal_known_w = knownW
        self.engine._cal_buffer = []
        self.engine.is_calibrating = True
        self.engine.cal_progress = 0
        self.engine.cal_status = f"Egg {self.engine.cal_session_count + 1}: Place in Center"
        self.updateMetrics.emit()

    @Slot()
    def saveSession(self):
        try:
            library = self.engine.cal_mgr.load_library()
            library.entries = self.engine._session_entries
            self.engine.cal_mgr.save_library(library)
            self.engine.cal_data = self.engine.cal_mgr.load()
            self.engine.measurement_engine.cal_data = self.engine.cal_data
            self.engine.cal_status = "Library Updated"
            self.engine.last_cal_result = f"Session complete. {len(self.engine._session_entries)} eggs saved."
        except Exception as e:
            self.engine.cal_status = f"Save Error: {str(e)}"
        self.updateMetrics.emit()

    @Slot(result=str)
    def checkSessionProgress(self):
        if self.engine.cal_session_count < self.engine.cal_session_target:
            return f"You only captured {self.engine.cal_session_count} eggs, but targeted {self.engine.cal_session_target}.\nSave anyway?"
        return "OK"

    @Slot(float, float, result=str)
    def validateCalibration(self, knownL, knownW):
        last_m = self.engine.measurement_engine._last_measurement
        if last_m is None or last_m.get("is_hand", False):
            return "No valid egg detected for validation."
        est_l, est_w = self.engine.measurement_engine._calculate_mm(last_m["major_px"], last_m["minor_px"])
        if abs(est_l - knownL) > 5.0 or abs(est_w - knownW) > 5.0:
            return f"Warning: AI thinks this egg is {est_l:.1f}x{est_w:.1f}mm.\nAre you sure?"
        return "OK"
