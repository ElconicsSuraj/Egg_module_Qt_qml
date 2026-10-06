# Egg Module — Raspberry Pi 5 Setup Guide

Full setup from fresh Raspberry Pi OS to running the Egg Module application.

---

## 1. Hardware Connections

### GPIO Pinout (BCM numbering)

```
Raspberry Pi 5 — 40-pin Header
                                    
  3.3V  [ 1] [ 2]  5V            HX711 VCC → Pin 1 (3.3V) or Pin 2 (5V)
  GPIO2 [ 3] [ 4]  5V
  GPIO3 [ 5] [ 6]  GND           HX711 GND → Pin 6 (GND)
  GPIO4 [ 7] [ 8]  GPIO14
   GND  [ 9] [10]  GPIO15
 GPIO17 [11] [12]  GPIO18        Candling LED (+) → Pin 11 (GPIO 17)
 GPIO27 [13] [14]  GND           Heartbeat LED (+) → Pin 13 (GPIO 27)
 GPIO22 [15] [16]  GPIO23        Heartbeat Sensor Signal → Pin 15 (GPIO 22)
  3.3V  [17] [18]  GPIO24
 GPIO10 [19] [20]  GND
  GPIO9 [21] [22]  GPIO25
 GPIO11 [23] [24]  GPIO8
   GND  [25] [26]  GPIO7
  GPIO0 [27] [28]  GPIO1
  GPIO5 [29] [30]  GND           HX711 SCK → Pin 29 (GPIO 5)
  GPIO6 [31] [32]  GPIO12        HX711 DT  → Pin 31 (GPIO 6)
 GPIO13 [33] [34]  GND
 GPIO19 [35] [36]  GPIO16
 GPIO26 [37] [38]  GPIO20
   GND  [39] [40]  GPIO21
```

### Component Wiring Table

| Component         | Component Pin | Pi Pin (Physical) | GPIO (BCM) |
|-------------------|--------------|-------------------|------------|
| HX711 Weight Sensor | VCC        | Pin 2 (5V)        | —          |
|                   | GND          | Pin 6 (GND)       | —          |
|                   | DT (DOUT)    | Pin 31            | GPIO 6     |
|                   | SCK (PD_SCK) | Pin 29            | GPIO 5     |
| Candling LED      | Anode (+)    | Pin 11            | GPIO 17    |
|                   | Cathode (-)  | Pin 6 (GND) via 330Ω resistor | — |
| Heartbeat Sensor  | VCC          | Pin 17 (3.3V)     | —          |
|                   | GND          | Pin 9 (GND)       | —          |
|                   | Signal OUT   | Pin 15            | GPIO 22    |
| Heartbeat LED     | Anode (+)    | Pin 13            | GPIO 27    |
|                   | Cathode (-)  | Pin 14 (GND) via 330Ω resistor | — |
| USB Camera        | USB          | Any USB port      | —          |

> **Note:** Always use a 330Ω resistor in series with each LED to limit current.

---

## 2. Raspberry Pi 5 OS Setup

Flash **Raspberry Pi OS (64-bit, Bookworm)** using Raspberry Pi Imager.

Enable SSH, set username/password, and connect to your network during flashing.

After first boot, update the system:

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 3. Enable GPIO Access

Add your user to the `gpio` group so the app can access hardware without `sudo`:

```bash
sudo usermod -a -G gpio $USER
sudo reboot
```

---

## 4. Install System Dependencies

```bash
sudo apt install -y \
    python3-lgpio \
    python3-pip \
    python3-venv \
    libgl1 \
    libglib2.0-0 \
    libxcb-cursor0 \
    libxcb-xinerama0 \
    libxkbcommon-x11-0 \
    v4l-utils \
    git
```

---

## 5. Clone the Repository

```bash
cd ~
git clone -b testing https://github.com/ElconicsSuraj/Egg_module_Qt_qml.git
cd Egg_module_Qt_qml/egg-module-v1
```

---

## 6. Create Virtual Environment & Install Python Packages

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install lgpio
```

> **Note:** PySide6 and ultralytics may take 10–20 minutes to install on Pi 5 ARM64.

---

## 7. Configure Environment

The `.env` file is in `ai_engine/`. Defaults work for most setups.
To change camera index or GPIO pins, edit the file:

```bash
nano ai_engine/.env
```

Available GPIO overrides (add to `.env` if you need different pins):

```
CANDLING_LED_PIN=17
HEARTBEAT_SENSOR_PIN=22
HEARTBEAT_LED_PIN=27
CAMERA_INDEX=0
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
```

---

## 8. Verify Camera

Check that the USB camera is detected:

```bash
ls /dev/video*
v4l2-ctl --list-devices
```

If no camera shows at `/dev/video0`, try unplugging and replugging the USB camera, then check again.

---

## 9. Run the Application

```bash
cd ~/Egg_module_Qt_qml/egg-module-v1
source venv/bin/activate
python main.py
```

The UI opens on the HDMI display. To run on every boot, see step 10.

---

## 10. Auto-start on Boot (Optional)

Create a systemd service:

```bash
sudo nano /etc/systemd/system/egg-module.service
```

Paste the following (replace `pi` with your username if different):

```ini
[Unit]
Description=Egg Module Application
After=graphical.target

[Service]
User=pi
WorkingDirectory=/home/pi/Egg_module_Qt_qml/egg-module-v1
ExecStart=/home/pi/Egg_module_Qt_qml/egg-module-v1/venv/bin/python main.py
Restart=on-failure
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority

[Install]
WantedBy=graphical.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable egg-module.service
sudo systemctl start egg-module.service
```

---

## 11. Update to Latest Code

```bash
cd ~/Egg_module_Qt_qml/egg-module-v1
git pull origin testing
source venv/bin/activate
python main.py
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `GPIO busy` | Previous run didn't clean up GPIO | `sudo reboot` |
| `HX711 sensor not ready (timeout)` | HX711 not connected or wrong pins | Check DT→Pin31, SCK→Pin29 wiring |
| `No module named 'PySide6'` | venv not activated | `source venv/bin/activate` |
| `Could not open any camera` | USB camera not detected | Run `ls /dev/video*`, replug camera |
| No display (SSH session) | Qt opens window on HDMI, not SSH | Connect a monitor or use VNC |
