"""
Taeglich rotierendes Logging fuer den JUMO AQUIS Logger.

Dateinamen-Format: logs/YYYY-MM-DD_logfile.txt
Rotation: Mitternacht (Systemzeit), neue Datei beim naechsten Log-Eintrag.
Aufbewahrung: LOG_BACKUP_DAYS Tage, aeltere Dateien werden automatisch geloescht.
"""

import logging
import sys
from datetime import datetime
from logging.handlers import BaseRotatingHandler
from pathlib import Path

import config

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class DailyFileHandler(BaseRotatingHandler):
    """
    Oeffnet taeglich eine neue Log-Datei nach dem Schema YYYY-MM-DD_logfile.txt.

    Die Rotation erfolgt beim ersten Log-Eintrag nach Mitternacht -- nicht
    per Timer, da das einfacher und robuster in einer GUI-Applikation ist.
    Alter als LOG_BACKUP_DAYS Tage werden beim Rotieren automatisch geloescht.
    """

    def __init__(self, log_dir: Path, backup_count: int = 30):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._backup_count = backup_count
        self._current_date = ""
        super().__init__(
            filename=str(self._path_for_today()),
            mode="a",
            encoding="utf-8",
            delay=False,
        )

    def _path_for_today(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        self._current_date = today
        return self._log_dir / f"{today}_logfile.txt"

    def shouldRollover(self, record) -> bool:
        return datetime.now().strftime("%Y-%m-%d") != self._current_date

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        self.baseFilename = str(self._path_for_today())
        self.stream = self._open()
        self._delete_old_logs()

    def _delete_old_logs(self):
        logs = sorted(self._log_dir.glob("????-??-??_logfile.txt"))
        for old in logs[: -self._backup_count]:
            old.unlink(missing_ok=True)


def setup_logging(console: bool = True) -> None:
    """
    Richtet den Root-Logger ein.

    console=True  -- gibt zusaetzlich auf stdout aus (sinnvoll fuer CLI-Start)
    console=False -- nur Datei (sinnvoll fuer GUI/windowed-EXE ohne Konsolenfenster)
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()  # verhindert doppelte Handler bei mehrfachem Aufruf

    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = DailyFileHandler(
        log_dir=Path(config.LOG_DIR),
        backup_count=config.LOG_BACKUP_DAYS,
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(fmt)
        root.addHandler(stream_handler)
