from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtGui import QImage

class StreamImageProvider(QQuickImageProvider):
    def __init__(self, engine):
        super().__init__(QQuickImageProvider.Image)
        self.engine = engine

    def requestImage(self, id, size, requestedSize):
        if self.engine.latest_qimage.isNull():
            return QImage(640, 480, QImage.Format_RGB888) # Return black frame fallback
        return self.engine.latest_qimage
