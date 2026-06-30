"""Persistierte GUI-Einstellungen in settings.json neben der .exe / dem Skript."""

import json
from pathlib import Path

import config

_PATH = Path(config._BASE_DIR) / "settings.json"

_DEFAULTS = {
    "modbus_host": config.MODBUS_HOST,
    "modbus_port": config.MODBUS_PORT,
    "poll_interval": config.POLL_INTERVAL_SECONDS,
    "export_format": "xlsx",
}


def load() -> dict:
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def save(data: dict) -> None:
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
