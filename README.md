# JUMO AQUIS Logger

A lightweight Modbus/TCP data logger for the **JUMO AQUIS touch S/P** (and compatible AQUIS touch 304) with a tkinter GUI, live plot, SQLite storage, and CSV/XLSX export.

> **Note:** Modbus only exposes live values — no access to the device's internal recorder/ring buffer. Logged data starts from the moment the poller is running.

---

## Features

- **Live polling** — reads compensated values from configured Modbus inputs at a configurable interval
- **SQLite storage** — append-only, survives restarts; database sits next to the executable
- **Live plot** — embedded matplotlib chart (last 30 minutes), auto-refreshes every 10 s
- **Export** — pivot table (one column per input, compensated value only) as CSV or XLSX, selectable date range
- **Daily rotating logs** — `logs/YYYY-MM-DD_logfile.txt`, 30-day retention
- **Windows EXE** — single-file build via GitHub Actions, no Python required on the target machine

---

## Quick start (macOS / Linux)

```bash
pip install pipenv          # once
pipenv install
pipenv run python gui.py
```

Requires system Tcl/Tk for your Python version (`brew install python-tk@3.13` on macOS + Homebrew).

---

## Configuration

Edit [`config.py`](config.py) before first use:

```python
MODBUS_HOST          = "223.223.223.1"   # IP address of the JUMO device
POLL_INTERVAL_SECONDS = 10               # polling cadence in seconds
LOG_BACKUP_DAYS      = 30               # how many daily log files to keep
```

IP address and poll interval can also be changed at runtime from the GUI without editing the file.

### Adding or changing inputs

Each entry in `MESSWERTE` maps a name to two Modbus register addresses. The addresses are device-specific — consult the JUMO Modbus interface description, chapter 7.2.12 (analysis inputs IN7–IN10) and 7.2.14 (temperature inputs IN4/IN5).

```python
MESSWERTE = [
    {"name": "leitfaehigkeit",    "addr_kompensiert": 0x1651, "addr_unkompensiert": 0x1649},
    {"name": "temperatur_medium", "addr_kompensiert": 0x16BD, "addr_unkompensiert": 0x16C1},
]
```

---

## Modbus float encoding

The JUMO AQUIS touch stores floats in a byte-swapped IEEE 754 layout: register *x* carries the **low word** (bytes 3–4), register *x+1* the **high word** (bytes 1–2). `modbus_helpers.py` handles the swap transparently.

---

## Build Windows EXE

The GitHub Actions workflow [`.github/workflows/build_windows.yml`](.github/workflows/build_windows.yml) builds a self-contained single-file EXE on a `windows-latest` runner.

1. Push this repository to GitHub
2. **Actions → Build Windows EXE → Run workflow**
3. Download the `JumoLogger-Windows` artifact (~3 min build time)

No Python installation required on the target Windows machine. The SQLite database and log files are written to the same folder as the EXE.

---

## Project structure

```
├── config.py           device and logging configuration
├── modbus_helpers.py   Modbus/TCP connection, JUMO float decoding
├── storage.py          SQLite schema and queries
├── poller.py           background polling thread (PollerThread)
├── export.py           CSV / XLSX pivot export
├── logging_setup.py    daily rotating file logger
├── gui.py              tkinter GUI entry point
└── jumo_logger.spec    PyInstaller build spec (Windows EXE)
```

---

## Dependencies

| Package | Purpose |
|---|---|
| [pymodbus](https://github.com/pymodbus-dev/pymodbus) ≥ 3.13 | Modbus/TCP client |
| [openpyxl](https://openpyxl.readthedocs.io) ≥ 3.1 | XLSX export |
| [matplotlib](https://matplotlib.org) ≥ 3.9 | embedded live plot |
| tkinter | GUI (stdlib, requires system Tcl/Tk) |
| sqlite3 | storage (stdlib) |
