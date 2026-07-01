"""
Export-Tool fuer geloggte JUMO AQUIS touch Messwerte.

Interaktiv im Terminal:
    python3 export.py

Oder direkt mit Argumenten:
    python3 export.py --von "2026-06-01 00:00" --bis "2026-06-30 23:59" --format xlsx

Exportiert die Zeitreihen als CSV oder XLSX, eine Spalte pro Eingang,
jeweils nur der kompensierte Messwert.
"""

import argparse
import csv
import sys
from datetime import datetime
from collections import defaultdict

import config
import storage


def parse_datetime_input(text: str) -> datetime:
    """Parst flexible Datums-/Zeiteingaben als naive Lokalzeit."""
    text = text.strip()
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Konnte Datum/Zeit nicht erkennen: '{text}'. "
        "Beispiele: '2026-06-01', '2026-06-01 14:30'"
    )


def _group_rows_by_cycle(rows, tolerance_seconds=None):
    """
    Gruppiert DB-Zeilen in Polling-Zyklen per Toleranzfenster.

    Aufeinanderfolgende Zeilen deren Zeitstempel weniger als `tolerance_seconds`
    auseinanderliegen, landen im selben Zyklus. Damit ueberstehen auch Zyklen,
    die eine Sekundengrenze schneiden, die Pivotierung korrekt.

    Gibt (pivot_dict, eingaenge_set) zurueck:
      pivot_dict: {cycle_ts_str: {eingang: wert_kompensiert}}
    """
    if tolerance_seconds is None:
        # Fest 2 Sekunden: beide Sensoren eines Zyklus haben denselben Timestamp
        # (Diff = 0s), der naechste Zyklus liegt mindestens polling_interval entfernt.
        tolerance_seconds = 2

    pivot = defaultdict(dict)
    eingaenge = set()
    prev_dt = None
    cycle_ts = None

    for row in rows:
        dt = datetime.fromisoformat(row["zeitstempel"]).replace(tzinfo=None)
        eingang = row["eingang"]
        eingaenge.add(eingang)

        if prev_dt is None or (dt - prev_dt).total_seconds() > tolerance_seconds:
            cycle_ts = dt.replace(microsecond=0).isoformat()

        prev_dt = dt
        # Letzter Wert gewinnt, falls ein Eingang mehrfach im selben Zyklus auftaucht.
        pivot[cycle_ts][eingang] = row["wert_kompensiert"]

    return pivot, eingaenge


def fetch_pivoted(von_iso: str, bis_iso: str):
    """
    Liest Rohdaten aus der DB und pivotiert sie per Toleranzfenster.

    Gibt (zeitstempel_liste, pivot_dict, eingaenge_liste) zurueck.
    """
    rows = storage.query_range(config.DB_PATH, von_iso, bis_iso)
    pivot, eingaenge = _group_rows_by_cycle(rows)
    zeitstempel_sortiert = sorted(pivot.keys())
    eingaenge_sortiert = sorted(eingaenge)
    return zeitstempel_sortiert, pivot, eingaenge_sortiert


def _split_ts(ts: str) -> tuple[str, str]:
    dt = datetime.fromisoformat(ts)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def export_csv(path: str, zeitstempel, pivot, eingaenge) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["datum", "uhrzeit"] + list(eingaenge))
        for ts in zeitstempel:
            datum, uhrzeit = _split_ts(ts)
            row = [datum, uhrzeit] + [pivot[ts].get(e) for e in eingaenge]
            writer.writerow(row)


def export_xlsx(path: str, zeitstempel, pivot, eingaenge) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Messwerte"

    ws.append(["Datum", "Uhrzeit"] + list(eingaenge))

    for ts in zeitstempel:
        datum, uhrzeit = _split_ts(ts)
        ws.append([datum, uhrzeit] + [pivot[ts].get(e) for e in eingaenge])

    for i in range(1, len(["Datum", "Uhrzeit"] + list(eingaenge)) + 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = 18

    wb.save(path)


def run(von_text: str, bis_text: str, fmt: str, output_path: str | None) -> str:
    von_dt = parse_datetime_input(von_text)
    bis_dt = parse_datetime_input(bis_text)

    if von_dt > bis_dt:
        raise ValueError("'von' liegt nach 'bis' -- bitte Reihenfolge pruefen.")

    von_iso = von_dt.isoformat()
    bis_iso = bis_dt.isoformat()

    zeitstempel, pivot, eingaenge = fetch_pivoted(von_iso, bis_iso)

    if not zeitstempel:
        print(
            f"Keine Daten im Zeitraum {von_text} bis {bis_text} gefunden.\n"
            "Hinweis: Nur Daten exportierbar, die seit Start von poller.py aufgezeichnet wurden."
        )
        return ""

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"export_{stamp}.{fmt}"

    if fmt == "csv":
        export_csv(output_path, zeitstempel, pivot, eingaenge)
    elif fmt == "xlsx":
        export_xlsx(output_path, zeitstempel, pivot, eingaenge)
    else:
        raise ValueError(f"Unbekanntes Format: {fmt}")

    print(f"{len(zeitstempel)} Zeitpunkte exportiert nach: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Exportiert geloggte JUMO AQUIS touch Messwerte als CSV/XLSX."
    )
    parser.add_argument("--von", help="Start (z.B. '2026-06-01' oder '2026-06-01 14:30')")
    parser.add_argument("--bis", help="Ende (z.B. '2026-06-30' oder '2026-06-30 23:59')")
    parser.add_argument("--format", choices=["csv", "xlsx"], default="xlsx")
    parser.add_argument("--output", help="Ausgabedateiname (optional)")
    args = parser.parse_args()

    von_text = args.von or input("Von (z.B. 2026-06-01 oder 2026-06-01 14:30): ").strip()
    bis_text = args.bis or input("Bis (z.B. 2026-06-30 oder 2026-06-30 23:59): ").strip()

    try:
        run(von_text, bis_text, args.format, args.output)
    except ValueError as exc:
        print(f"Fehler: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
