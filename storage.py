"""
SQLite-Speicherung der Messwerte.

Tabelle 'messwerte':
  id              INTEGER PRIMARY KEY
  zeitstempel     TEXT (ISO 8601, UTC)
  eingang         TEXT  (z.B. "IN7")
  wert_kompensiert    REAL (NULL falls Fehler/ungueltig)
  wert_unkompensiert  REAL (NULL falls Fehler/ungueltig)
  fehler          TEXT (NULL wenn ok, sonst Fehlertext)
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messwerte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zeitstempel TEXT NOT NULL,
            eingang TEXT NOT NULL,
            wert_kompensiert REAL,
            wert_unkompensiert REAL,
            fehler TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zeitstempel
        ON messwerte (zeitstempel)
    """)
    conn.commit()
    return conn


def insert_reading(
    conn: sqlite3.Connection,
    eingang: str,
    wert_kompensiert: float | None,
    wert_unkompensiert: float | None,
    fehler: str | None,
    zeitstempel: str | None = None,
) -> None:
    if zeitstempel is None:
        zeitstempel = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO messwerte (zeitstempel, eingang, wert_kompensiert, wert_unkompensiert, fehler)
        VALUES (?, ?, ?, ?, ?)
        """,
        (zeitstempel, eingang, wert_kompensiert, wert_unkompensiert, fehler),
    )
    conn.commit()


def query_range(
    db_path: str, von_iso: str, bis_iso: str
) -> list[sqlite3.Row]:
    """Liest alle Messwerte im Zeitraum [von_iso, bis_iso] (ISO 8601 Strings)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT zeitstempel, eingang, wert_kompensiert, wert_unkompensiert, fehler
        FROM messwerte
        WHERE zeitstempel >= ? AND zeitstempel <= ?
        ORDER BY zeitstempel ASC, eingang ASC
        """,
        (von_iso, bis_iso),
    ).fetchall()
    conn.close()
    return rows
