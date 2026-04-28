import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from src.engine import EggModuleEngine
from ui.bridge import EggModuleBridge
from ui.image_provider import StreamImageProvider

def main():
    app = QApplication(sys.argv)
    engine = QQmlApplicationEngine()

    # Initialize Engine (Logic & Hardware)
    # We pass placeholders for callbacks that will be set by the bridge
    antz_engine = EggModuleEngine(callback_metrics=lambda: None, callback_image=lambda: None)

    # Initialize Bridge (UI Connector)
    antz_bridge = EggModuleBridge(antz_engine)
    
    # Register properties to QML
    engine.rootContext().setContextProperty("antzBackend", antz_bridge)
    # Protect from GC
    engine.antz_bridge = antz_bridge

    # Register Image Provider for Video Feed
    image_provider = StreamImageProvider(antz_engine)
    engine.addImageProvider("vision", image_provider)

    # Add components folder to QML import path
    qml_dir = os.path.join(os.path.dirname(__file__), "ui")
    engine.addImportPath(os.path.join(qml_dir, "components"))

    # Load Main QML
    engine.load(os.path.join(qml_dir, "main.qml"))

    if not engine.rootObjects():
        sys.exit(-1)

    exit_code = app.exec()
    antz_engine.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
