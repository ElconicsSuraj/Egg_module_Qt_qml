import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtGui import QImage
from backend import EggModuleBackend

class StreamImageProvider(QQuickImageProvider):
    def __init__(self, backend):
        super().__init__(QQuickImageProvider.Image)
        self.backend = backend

    def requestImage(self, id, size, requestedSize):
        if self.backend._latest_qimage.isNull():
            return QImage(640, 480, QImage.Format_RGB888) # Return black frame fallback
        return self.backend._latest_qimage

app = QApplication(sys.argv)
engine = QQmlApplicationEngine()

# Initialize unified AI + Hardware backend
print("--- Initializing Antz Backend ---")
antzBackend = EggModuleBackend()
engine.rootContext().setContextProperty("antzBackend", antzBackend)
# Protect from GC
engine.antzBackend = antzBackend
print(f"--- Backend Context Property Set: {antzBackend} ---")

# Register the Image Provider for the Video Feed
image_provider = StreamImageProvider(antzBackend)
engine.addImageProvider("vision", image_provider)

engine.setInitialProperties({'antzBackend': antzBackend})
engine.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.qml'))

if not engine.rootObjects():
    sys.exit(-1)

sys.exit(app.exec())

