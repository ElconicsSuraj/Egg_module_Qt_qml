import os
import sys
import time

print("Checking environment...")
import cv2
print(f"OpenCV version: {cv2.__version__}")

try:
    import torch
    print(f"Torch version: {torch.__version__}")
except ImportError:
    print("Torch NOT found")

try:
    from ultralytics import YOLO
    print("Ultralytics found")
except ImportError:
    print("Ultralytics NOT found")

print("\nTesting component initialization...")

# Test 1: Config
print("1. Loading Config...")
from ai_engine.src.config.constants import Config
AI_ENGINE_ROOT = os.path.join(os.getcwd(), "ai_engine")
env_path = os.path.join(AI_ENGINE_ROOT, ".env")
config = Config(env_path)
config.model_path = os.path.join(AI_ENGINE_ROOT, "media", "best_final.pt")
print("   Config loaded.")

# Test 2: Detector
print("2. Initializing Detector...")
from ai_engine.src.core.detector import EggDetector
detector = EggDetector(config)
print("   Detector initialized.")
print("3. Loading Model (This might take time)...")
start = time.time()
try:
    detector.load_model()
    print(f"   Model loaded in {time.time() - start:.2f}s")
except Exception as e:
    print(f"   Model load failed: {e}")

# Test 3: Camera
print("4. Initializing Camera...")
from ai_engine.src.core.camera import CameraManager
camera = CameraManager(config)
print("   Camera Manager initialized.")
print("5. Opening Camera...")
start = time.time()
if camera.open():
    print(f"   Camera opened in {time.time() - start:.2f}s")
    camera.release()
else:
    print(f"   Camera open FAILED in {time.time() - start:.2f}s")

# Test 4: Hardware (HX711)
print("6. Testing HX711...")
try:
    from hx711 import HX711
    print("   HX711 class imported.")
    print("7. Initializing HX711 sensor (Pins 5, 6)...")
    hx = HX711(5, 6)
    print("   HX711 initialized.")
    print("8. Taring HX711 (Will hang if not connected!)...")
    # We will use a thread with timeout for this test
    import threading
    def do_tare():
        hx.tare()
        print("   Tare complete.")
    
    t = threading.Thread(target=do_tare)
    t.start()
    t.join(timeout=5)
    if t.is_alive():
        print("   TARE HANGED (Timeout 5s). This is likely the cause.")
    else:
        print("   Tare finished successfully.")
except Exception as e:
    print(f"   HX711 Test Failed: {e}")

print("\n--- Diagnostic Complete ---")
