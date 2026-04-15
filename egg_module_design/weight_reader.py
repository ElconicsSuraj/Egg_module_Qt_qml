from hx711 import HX711
import RPi.GPIO as GPIO
import time
import sys

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

DT = 5
SCK = 6

hx = HX711(DT, SCK)
hx.set_reading_format("MSB", "MSB")

referenceUnit = -840
hx.set_reference_unit(referenceUnit)

print("Remove weight...", flush=True)
time.sleep(2)

hx.reset()
hx.tare()

print("Scale Ready", flush=True)

while True:
    try:
        val = hx.get_weight(10)

        if abs(val) < 1:
            val = 0

        val = (round(val))

        print(val, flush=True)

        hx.power_down()
        hx.power_up()

        time.sleep(0.3)

    except KeyboardInterrupt:
        GPIO.cleanup()
        sys.exit()
