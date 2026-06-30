"""
Konfiguration fuer den JUMO AQUIS touch 304 Logger.

Alle Werte hier anpassen, bevor poller.py gestartet wird.
"""

import os
import sys

# Basisverzeichnis: im gebundelten .exe-Modus (PyInstaller) liegt sys.executable
# im Dist-Ordner; dort liegen auch die Datendateien.  Im Skript-Modus ist es das
# Verzeichnis dieser Datei.
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Modbus/TCP Verbindung ---
MODBUS_HOST = "223.223.223.1"   # IP-Adresse des AQUIS touch -> anpassen!
MODBUS_PORT = 502            # ist beim AQUIS touch fest auf 502 eingestellt
MODBUS_UNIT_ID = 255         # Unit-ID ist bei Modbus/TCP am AQUIS touch fest auf 255

# --- Polling ---
POLL_INTERVAL_SECONDS = 10   # wie oft gepollt wird

# --- Speicherung ---
DB_PATH = os.path.join(_BASE_DIR, "jumo_data.sqlite3")

# --- Logging ---
LOG_DIR = os.path.join(_BASE_DIR, "logs")   # Unterordner neben der .exe / dem Skript
LOG_BACKUP_DAYS = 30                         # wie viele Tages-Logfiles aufbewahrt werden

# --- Gemessene Werte ---
# Identifiziert am Geraet:
#   IN5 (Temperatureingang) = Temperatur des Mediums (Sensor des
#       Leitfaehigkeitsfuehlers selbst)
#   IN9 (Analyseeingang)    = Leitfaehigkeit
#
# Beide haben dasselbe Speicherschema in der DB (wert_kompensiert /
# wert_unkompensiert / fehler), nur die Modbus-Adressen unterscheiden
# sich je nach Eingangstyp:
#   - Temperatureingaenge (IN4/IN5): Kapitel 7.2.14 "Temperatureingaenge"
#       wert_kompensiert  = Temperaturmesswert (0x16BD bei IN5)
#       wert_unkompensiert = Sensorwiderstand in Ohm (0x16C1 bei IN5)
#   - Analyseeingaenge (IN7-IN10): Kapitel 7.2.12 "Analyseeingaenge"
#       wert_kompensiert  = Messwert kompensiert (0x1651 bei IN9)
#       wert_unkompensiert = Messwert unkompensiert / Rohwert (0x1649 bei IN9)
MESSWERTE = [
    {
        "name": "temperatur_medium",
        "addr_kompensiert": 0x16BD,
        "addr_unkompensiert": 0x16C1,  # Sensorwiderstand in Ohm, nicht Temperatur
    },
    {
        "name": "leitfaehigkeit",
        "addr_kompensiert": 0x1651,
        "addr_unkompensiert": 0x1649,
    },
]
