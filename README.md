<div align="center">

# 💡 GleamBLEled

**Desktop GUI controller for Bluetooth LED strips**  
Works with ELK-BLEDOM, QHM, LEDBLE, SP110E and compatible BLE RGB controllers

[![GitHub release (latest)](https://img.shields.io/github/v/release/OlehHavrilko/GleamBLEled?style=for-the-badge&logo=github&label=Latest+Release)](https://github.com/OlehHavrilko/GleamBLEled/releases/latest)
[![Download Windows](https://img.shields.io/badge/⬇_Download-Windows_.exe-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/OlehHavrilko/GleamBLEled/releases/latest/download/GleamBLEled-windows.exe)
[![Download Linux](https://img.shields.io/badge/⬇_Download-Linux_binary-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/OlehHavrilko/GleamBLEled/releases/latest/download/GleamBLEled-linux)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)

</div>

---

## ⬇️ Download

> **No Python required** — click to download the binary for your platform:

| Platform | Direct Download | Notes |
|----------|----------------|-------|
| 🪟 Windows | [**GleamBLEled-windows.exe**](https://github.com/OlehHavrilko/GleamBLEled/releases/latest/download/GleamBLEled-windows.exe) | Windows 10/11 x64 — just double-click |
| 🐧 Linux | [**GleamBLEled-linux**](https://github.com/OlehHavrilko/GleamBLEled/releases/latest/download/GleamBLEled-linux) | Ubuntu 22.04+ x64 — `chmod +x` then run |

👉 **[All releases →](https://github.com/OlehHavrilko/GleamBLEled/releases)**

---

## ✨ Features

- 🔍 **Auto-discovery** — scans and connects to your LED controller on startup, no manual setup
- 🎨 **Full RGB control** — hex input, color palette picker, R/G/B sliders with live preview
- 💡 **Brightness** slider (0–100 %)
- ⚡ **Effects** — Breathing, Color cycle, Strobe with speed control
- 📡 **Notify sync** — reads the current color/state from the device on connect
- 🔄 **Auto-reconnect** — 5 attempts × 5 s after unexpected disconnect
- 🪟 **Device picker dialog** — lists all found controllers with signal-strength bars (████)
- 🔬 **Deep scan + probe** — identifies unknown BLE devices by sending a test command
- 💾 **Persistent config** — remembers last device, color, and brightness between sessions

---

## 🎮 Supported Devices

| Device name | Confidence |
|-------------|-----------|
| `ELK-BLEDOM` | ✅ Confirmed (MAC `FF:FF:10:69:5B:2A`) |
| `QHM-*` | ✅ Name match |
| `LEDBLE`, `LEDNET`, `LEDBLUE` | ✅ Name match |
| `SP110E` | ✅ Name match |
| `TRIONES`, `ZENGGE`, `MELK` | ✅ Name match |
| Any device with service `FFF0` / `FFD5` / `FFE5` | 🟡 UUID match |
| Unknown BLE device | 🔬 Probe via deep scan |

---

## 🚀 Run from Source

```bash
# Python 3.11+ required
git clone https://github.com/OlehHavrilko/GleamBLEled.git
cd GleamBLEled
pip install -r requirements.txt
python main.py
```

**Linux** — make sure BlueZ is installed:
```bash
sudo apt install bluetooth bluez
sudo systemctl enable --now bluetooth
```

---

## 🔨 Build Yourself

```bash
# Linux
bash build_linux.sh

# Windows
build_windows.bat
```

Output binary lands in `dist/`.

---

## 📁 Project Structure

```
GleamBLEled/
├── main.py                    # Entry point
├── app/
│   ├── ble/
│   │   ├── controller.py      # BleakClient wrapper, notify subscription
│   │   ├── scanner.py         # GleamScanner — 3-level device detection
│   │   └── protocol.py        # ELK-BLEDOM frame builder & parser
│   ├── ui/
│   │   ├── app.py             # Main window — status bar, auto-connect, reconnect
│   │   └── device_picker.py   # Device picker modal dialog
│   ├── models.py              # AppState, RememberedDevice dataclasses
│   ├── constants.py           # Scan timeouts, UUIDs, device name hints
│   ├── config.py              # JSON config persistence
│   └── utils.py               # rssi_to_bars, apply_brightness, hex/rgb helpers
└── GleamBLEled.spec           # PyInstaller build spec
```

---

## ⚙️ Config File

Located at `~/.config/gleambled/config.json` (Linux) or `%APPDATA%\GleamBLEled\config.json` (Windows):

```json
{
  "last_device": {
    "address": "FF:FF:10:69:5B:2A",
    "name": "ELK-BLEDOM",
    "write_uuid": "0000fff3-0000-1000-8000-00805f9b34fb",
    "confidence": "name"
  },
  "last_color": [255, 128, 0],
  "brightness": 0.8
}
```

---

<div align="center">
Made with Python · <a href="https://github.com/OlehHavrilko/GleamBLEled/issues">Report an issue</a>
</div>
