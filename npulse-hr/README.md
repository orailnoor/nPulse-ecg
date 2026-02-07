# nPulse HR - ECG Analyzer

Python tools for collecting and analyzing ECG data from nPulse BLE devices.

## Quick Start

### 1. Setup Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirement.txt
```

### 2. Install BLE Dependencies (for data collection)

```bash
pip install bleak
```

---

## Usage

### 📡 BLE Data Collection (Terminal)

Collect ECG data from your nPulse device:

```bash
source venv/bin/activate
python ble_collector.py
```

**Features:**
- Auto-scans for nPulse devices
- Configurable recording duration (default: 60 seconds)
- Auto-saves to `./files/` with timestamp
- Shows sample count in real-time

---

### 🌐 Web GUI (Browser Interface)

Analyze ECG data files and collect BLE data with real-time graphing:

```bash
source venv/bin/activate
python gui_app.py
```

Then open: **http://127.0.0.1:5000**

**Features:**

📡 **Real-Time Collection Tab:**
- Scan, connect, disconnect BLE devices
- Live ECG graph with all 3 sensors
- Real-time sample count and sampling rate
- Configurable recording duration
- Auto-save to `./files/`

📊 **File Analysis Tab:**
- Drag & drop file upload
- Browse existing files in `./files/`
- Heart rate analysis (Avg, Min, Max per sensor)
- Combined HR across all 3 sensors
- Interactive ECG plot visualization

---

### 📊 Command Line Analysis

Analyze a single file from terminal:

```bash
source venv/bin/activate
python ecg_processor.py files/your_data.txt
```

---

## Files

| File | Description |
|------|-------------|
| `ble_collector.py` | Terminal BLE data collector |
| `gui_app.py` | Web GUI (Flask) for analysis |
| `ble_handler.py` | BLE communication module |
| `ecg_processor.py` | ECG signal processing |
| `main.py` | Original terminal analysis script |
| `files/` | Directory for ECG data files |

---

## Data Format

ECG data files are CSV format with 3 sensor values per line:
```
1234,2345,3456
1235,2346,3457
...
```

---

## Requirements

- Python 3.8+
- macOS with Bluetooth for BLE collection
- See `requirement.txt` for Python packages