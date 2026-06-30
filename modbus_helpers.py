"""
Hilfsfunktionen fuer die Modbus-Kommunikation mit dem JUMO AQUIS touch.

Wichtig: Der JUMO AQUIS touch S/P kodiert Float-Werte im IEEE-754-Format,
vertauscht dabei aber die beiden 16-Bit-Worte (Register x und x+1) im
Vergleich zum Standard-Layout vieler Compiler. Siehe Kapitel 2.6.2 der
JUMO Schnittstellenbeschreibung Modbus.

Modbus-Float-Format (so kommt es vom Geraet):
  Register x   -> Byte 3, Byte 4   (niedrigwertiger Teil der Mantisse)
  Register x+1 -> Byte 1, Byte 2   (Vorzeichen, Exponent, hoher Mantisse-Teil)

Um daraus einen "normalen" IEEE754-Float (Byte1 Byte2 Byte3 Byte4) zu
bekommen, muessen die beiden 16-Bit-Worte vertauscht werden.
"""

import struct
import logging
from datetime import datetime
from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)


def connect(host: str, port: int) -> ModbusTcpClient:
    """Baut eine Modbus/TCP-Verbindung auf und gibt den Client zurueck."""
    client = ModbusTcpClient(host, port=port, timeout=5)
    if not client.connect():
        raise ConnectionError(f"Konnte nicht zu {host}:{port} verbinden")
    return client


def read_float(client: ModbusTcpClient, address: int, unit_id: int) -> float | None:
    """
    Liest einen Float-Wert (2 Register) vom JUMO AQUIS touch.

    Gibt None zurueck, wenn die Anfrage fehlschlaegt (z.B. Modbus-Fehlercode).
    Gibt die JUMO-Fehlercodes (1e37 .. 8e37, siehe Kapitel 2.8.2) unveraendert
    zurueck, damit der Aufrufer entscheiden kann, wie damit umgegangen wird.
    """
    try:
        result = client.read_holding_registers(address, count=2, device_id=unit_id)
    except Exception as exc:
        logger.warning("Modbus-Lesefehler bei Adresse 0x%04X: %s", address, exc)
        return None

    if result.isError():
        logger.warning("Modbus meldet Fehler bei Adresse 0x%04X: %s", address, result)
        return None

    regs = result.registers  # [register_x, register_x+1]
    # JUMO liefert: Register x = Byte3,Byte4 / Register x+1 = Byte1,Byte2
    # -> wir muessen die beiden 16-Bit-Worte vertauschen, um auf das
    #    Standard-IEEE754-Byte-Layout (Byte1 Byte2 Byte3 Byte4) zu kommen.
    word_x, word_x1 = regs[0], regs[1]
    raw_bytes = struct.pack(">HH", word_x1, word_x)
    value = struct.unpack(">f", raw_bytes)[0]
    return value


def read_device_datetime(client: ModbusTcpClient, address: int, unit_id: int) -> datetime | None:
    """
    Liest Datum und Uhrzeit vom Geraet als 6 aufeinanderfolgende Holding Registers:
      [Jahr, Monat, Tag, Stunde, Minute, Sekunde] jeweils als uint16

    Die Basisadresse (address) muss aus der JUMO Schnittstellenbeschreibung
    entnommen werden (Kapitel Systemparameter / Datum & Uhrzeit).

    Gibt ein naive datetime-Objekt zurueck (Geraete-Lokalzeit, keine UTC-Konvertierung).
    Gibt None zurueck bei Lesefehler oder unplausiblen Werten.
    """
    try:
        result = client.read_holding_registers(address, count=6, device_id=unit_id)
    except Exception as exc:
        logger.warning("Modbus-Fehler beim Lesen der Geraetezeit (0x%04X): %s", address, exc)
        return None

    if result.isError():
        logger.warning("Geraetezeit-Lesefehler (0x%04X): %s", address, result)
        return None

    year, month, day, hour, minute, second = result.registers
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError as exc:
        logger.warning("Ungueltiger Datums-/Zeitwert vom Geraet (%s): %s", result.registers, exc)
        return None


# JUMO-Fehlercodes bei ungueltigen Float-Messwerten (Kapitel 2.8.2)
JUMO_FLOAT_ERROR_CODES = {
    1.0e37: "Messbereichsunterschreitung",
    2.0e37: "Messbereichsueberschreitung",
    3.0e37: "kein gueltiger Eingangswert",
    4.0e37: "Division durch Null",
    5.0e37: "Mathematikfehler",
    6.0e37: "Ungueltige Kompensationstemperatur",
    7.0e37: "Ungueltiger Float-Wert",
    8.0e37: "Integrator oder Statistik zerstoert",
}


def decode_jumo_error(value: float) -> str | None:
    """Prueft, ob ein gelesener Float-Wert einem JUMO-Fehlercode entspricht."""
    if value is None:
        return None
    for code, meaning in JUMO_FLOAT_ERROR_CODES.items():
        # JUMO-Fehlercodes sind grosse Zahlen (>= 1e37); kleine Toleranz beim Vergleich
        if abs(value - code) < (code * 1e-6):
            return meaning
    return None
