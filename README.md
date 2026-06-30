# JUMO AQUIS touch 304 -- Modbus Logger & Export-Tool

Liest die 4 Analyseeingänge (IN7-IN10) live per Modbus/TCP aus dem JUMO
AQUIS touch, schreibt sie kontinuierlich mit Zeitstempel in eine lokale
SQLite-Datenbank, und exportiert frei wählbare Zeiträume als CSV/XLSX.

## Wichtige Einschränkung

Per Modbus können nur **aktuelle Live-Werte** gelesen werden, keine
historischen Daten aus dem internen Recorder/Ringpuffer des Geräts. Das
heißt: Export ist nur für Zeiträume möglich, die **nach dem Start von
`poller.py`** liegen. Alles davor ist nicht verfügbar (außer über separaten
USB-Export am Gerät selbst, der hier nicht abgedeckt ist).

## Setup

```bash
pip install -r requirements.txt --break-system-packages
```

In `config.py` anpassen:
- `MODBUS_HOST` -- IP-Adresse des AQUIS touch
- `POLL_INTERVAL_SECONDS` -- wie oft gepollt wird (Standard: 10s)
- `DB_PATH` -- wo die SQLite-Datei liegen soll

## Gemessene Werte

Das Tool loggt zwei Werte, identifiziert am Gerät:

- **`leitfaehigkeit`** -- IN9 (Analyseeingang), kompensierter Leitfähigkeitswert
- **`temperatur_medium`** -- IN5 (Temperatureingang), Temperatur des im
  Leitfähigkeitssensor integrierten Temperaturfühlers

Beide Werte landen in der gleichen Tabellenstruktur (`wert_kompensiert`,
`wert_unkompensiert`, `fehler`). Beim `temperatur_medium`-Eintrag ist
`wert_unkompensiert` kein Temperaturwert, sondern der Sensorwiderstand
in Ohm (zum Debuggen, z.B. Kabelbruch erkennen) -- der eigentliche
Temperaturwert steht in `wert_kompensiert`.

Falls sich am Gerät etwas ändert (anderer Sensor, andere Eingangs-
Zuordnung), einfach die Adressen in `config.py` unter `MESSWERTE`
anpassen.

Im Export tauchen `IN4_Temp` und `IN5_Temp` als eigene Zeilen/Spalten
auf -- bei diesen beiden ist die Spalte "kompensiert" der eigentliche
Temperaturwert (°C oder °F, je nach Geräteeinstellung) und die Spalte
"unkompensiert" der Sensorwiderstand in Ohm (nützlich zum Debuggen,
z.B. um einen Kabelbruch zu erkennen -- kein echter Messwert).

## Polling starten (Live-Aufzeichnung)

```bash
python3 poller.py
```

Läuft als Endlosschleife, bis mit Strg+C beendet. Für Dauerbetrieb als
systemd-Service einrichten, z.B.:

```ini
# /etc/systemd/system/jumo-poller.service
[Unit]
Description=JUMO AQUIS touch Modbus Poller
After=network.target

[Service]
Type=simple
WorkingDirectory=/pfad/zu/jumo_logger
ExecStart=/usr/bin/python3 poller.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Dann:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now jumo-poller
```

## Daten exportieren

Interaktiv:
```bash
python3 export.py
```

Oder direkt mit Argumenten:
```bash
python3 export.py --von "2026-06-01 00:00" --bis "2026-06-30 23:59" --format xlsx
```

Erzeugt eine Datei mit einer Zeile pro Zeitstempel und je 3 Spalten pro
Eingang (kompensierter Wert, unkompensierter Rohwert, Fehlertext falls
vorhanden).

## Dateien

- `config.py` -- alle Einstellungen
- `modbus_helpers.py` -- Verbindung & JUMO-spezifische Float-Dekodierung
  (Byte-Reihenfolge ist beim AQUIS touch vertauscht gegenüber Standard-IEEE754)
- `storage.py` -- SQLite-Schema und Lese-/Schreibfunktionen
- `poller.py` -- Hintergrunddienst zum kontinuierlichen Auslesen
- `export.py` -- CLI zum Exportieren eines Zeitraums als CSV/XLSX
