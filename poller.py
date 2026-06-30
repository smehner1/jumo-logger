"""
Polling-Dienst fuer den JUMO AQUIS touch 304.

Kann als Hintergrund-Thread (PollerThread) oder direkt per CLI gestartet werden:
    python3 poller.py
"""

import logging
import signal
import threading
from datetime import datetime

import config
import storage
from logging_setup import setup_logging
from modbus_helpers import connect, read_float, decode_jumo_error, read_device_datetime

logger = logging.getLogger(__name__)


class PollerThread(threading.Thread):
    """
    Liest Modbus-Messwerte im Hintergrund und schreibt sie in SQLite.

    status_callback(event, data) wird aus dem Thread heraus aufgerufen:
      ("connected",  {"host": str, "port": int})
      ("reading",    {"zeitstempel": str, "readings": {name: (wert, fehler)}})
      ("error",      {"message": str})
      ("stopped",    {})
    """

    def __init__(self, host, port, unit_id, poll_interval, messwerte, db_path,
                 status_callback=None):
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.poll_interval = poll_interval
        self.messwerte = messwerte
        self.db_path = db_path
        self.status_callback = status_callback

    def stop(self):
        self._stop_event.set()

    def run(self):
        conn = storage.get_connection(self.db_path)
        client = None

        while not self._stop_event.is_set():
            try:
                if client is None:
                    client = connect(self.host, self.port)
                    logger.info("Verbunden mit %s:%s", self.host, self.port)
                    self._notify("connected", {"host": self.host, "port": self.port})

                self._poll_once(client, conn)

            except ConnectionError as exc:
                logger.error("Verbindungsfehler: %s", exc)
                self._notify("error", {"message": str(exc)})
                client = None
            except Exception as exc:
                logger.exception("Unerwarteter Fehler: %s", exc)
                self._notify("error", {"message": str(exc)})
                client = None

            self._stop_event.wait(self.poll_interval)

        if client:
            client.close()
        conn.close()
        self._notify("stopped", {})
        logger.info("Polling beendet.")

    def _poll_once(self, client, conn):
        # Zeitstempel vom Geraet lesen (falls DEVICE_TIME_BASE_ADDR gesetzt),
        # sonst PC-Lokalzeit. Kein UTC -- Zeitzone des Geraets / PCs wird direkt verwendet.
        ts = None
        if config.DEVICE_TIME_BASE_ADDR is not None:
            dt = read_device_datetime(client, config.DEVICE_TIME_BASE_ADDR, self.unit_id)
            if dt is not None:
                ts = dt.isoformat()
            else:
                logger.warning("Geraetezeit nicht lesbar -- Fallback auf PC-Lokalzeit")
        if ts is None:
            ts = datetime.now().isoformat()
        readings = {}

        for entry in self.messwerte:
            name = entry["name"]
            wert_komp = read_float(client, entry["addr_kompensiert"], self.unit_id)
            wert_unkomp = read_float(client, entry["addr_unkompensiert"], self.unit_id)

            fehler = None
            if wert_komp is None and wert_unkomp is None:
                fehler = "Modbus-Leseanfrage fehlgeschlagen"
            else:
                jumo_fehler = decode_jumo_error(wert_komp) if wert_komp is not None else None
                if jumo_fehler:
                    fehler = f"JUMO-Fehlercode: {jumo_fehler}"

            storage.insert_reading(
                conn,
                eingang=name,
                wert_kompensiert=wert_komp,
                wert_unkompensiert=wert_unkomp,
                fehler=fehler,
                zeitstempel=ts,
            )
            readings[name] = (wert_komp, fehler)

            if fehler:
                logger.warning("%s: %s", name, fehler)
            else:
                logger.info("%s: %.4f", name, wert_komp)

        self._notify("reading", {"zeitstempel": ts, "readings": readings})

    def _notify(self, event_type, data):
        if self.status_callback:
            try:
                self.status_callback(event_type, data)
            except Exception:
                pass


def main() -> None:
    setup_logging(console=True)

    thread = PollerThread(
        host=config.MODBUS_HOST,
        port=config.MODBUS_PORT,
        unit_id=config.MODBUS_UNIT_ID,
        poll_interval=config.POLL_INTERVAL_SECONDS,
        messwerte=config.MESSWERTE,
        db_path=config.DB_PATH,
    )

    def handle_shutdown(signum, frame):
        logger.info("Beende Polling (Signal %s)...", signum)
        thread.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    if hasattr(signal, "SIGTERM"):  # nicht auf Windows verfuegbar
        signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(
        "Starte Polling von %s:%s, Intervall=%ss, DB=%s",
        config.MODBUS_HOST, config.MODBUS_PORT,
        config.POLL_INTERVAL_SECONDS, config.DB_PATH,
    )
    thread.start()
    thread.join()


if __name__ == "__main__":
    main()
