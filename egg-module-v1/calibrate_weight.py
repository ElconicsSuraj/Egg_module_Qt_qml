"""
Weight Scale Calibration Script
Run this on the Raspberry Pi when the plate changes and tare alone doesn't fix readings.

Steps:
  1. Run this script
  2. Follow the prompts
  3. Copy the printed reference_unit value into engine.py line 95
"""

import sys
import time

try:
    from hx711py.hx711 import HX711
except ImportError:
    try:
        from hx711 import HX711
    except ImportError:
        print("ERROR: hx711 library not found.")
        sys.exit(1)

DT  = 5
SCK = 6

KNOWN_WEIGHT_G = 100  # grams — change this to whatever known weight you'll use

hx = HX711(DT, SCK)

# Set reference unit to 1 so we get raw ADC values
hx.set_reference_unit(1)
hx.reset()

print("\n=== WEIGHT CALIBRATION ===")
print(f"Using known weight: {KNOWN_WEIGHT_G} g")
print("\nStep 1: Remove ALL weight from the scale (plate only, no egg).")
input("Press ENTER when plate is empty and stable...")

hx.tare()
print("Tared. Zero set.")

print(f"\nStep 2: Place your {KNOWN_WEIGHT_G}g known weight ON the plate.")
input("Press ENTER when weight is placed and stable...")

print("Reading raw values (10 samples)...")
time.sleep(1)

readings = []
for i in range(10):
    val = hx.get_value(5)
    readings.append(val)
    print(f"  Sample {i+1}: {val:.0f}")
    time.sleep(0.3)

raw_avg = sum(readings) / len(readings)
print(f"\nAverage raw value: {raw_avg:.0f}")

# reference_unit = raw / weight_in_grams
# Engine uses negative value — check sign of raw_avg
ref_unit = raw_avg / KNOWN_WEIGHT_G
print(f"\nCalculated reference_unit: {ref_unit:.1f}")

# The engine uses a negative reference unit; preserve sign
print(f"\n>>> UPDATE engine.py line 95 to:")
print(f"        self.hx.set_reference_unit({ref_unit:.0f})")
print("\nVerifying with the new reference unit...")

hx.set_reference_unit(ref_unit)
time.sleep(0.5)

print(f"\nWith {KNOWN_WEIGHT_G}g on scale, reading should show ~{KNOWN_WEIGHT_G}g:")
for i in range(5):
    w = hx.get_weight(5)
    print(f"  Reading: {w:.1f} g")
    time.sleep(0.5)

print("\nCalibration complete. Update engine.py with the value above.")
