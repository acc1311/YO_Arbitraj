#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Universal Log Parser
Suportă: ADIF (.adi/.adif), Cabrillo (.log), CSV (.csv), JSON (YO Log PRO nativ)
"""

import re
import csv
import json
import io
import os
import datetime
from core.contests import freq_to_band

# ── QSO dataclass (dict cu câmpuri normalizate) ──────────────────────────────
# Câmpuri standard după parse:
#   callsign, freq, band, mode, rst_s, rst_r,
#   date (YYYY-MM-DD), time (HH:MM), exchange, note,
#   dxcc, serial, locator
#   _source_line  (nr linie original, pt rapoarte)
#   _raw          (linia brută)

def empty_qso():
    return {
        "callsign": "", "freq": "", "band": "", "mode": "",
        "rst_s": "", "rst_r": "", "date": "", "time": "",
        "exchange": "", "note": "", "dxcc": "", "serial": "",
        "locator": "", "_source_line": 0, "_raw": "",
    }


# ═══════════════════════════════════════════════════════════════════
#  ADIF
# ═══════════════════════════════════════════════════════════════════
def _adif_field(tag, text):
    """Extrage valoarea unui câmp ADIF <TAG:LEN>VALUE."""
    pattern = re.compile(r'<' + re.escape(tag) + r':(\d+)(?::[^>]*)?>([^<]*)', re.IGNORECASE)
    m = pattern.search(text)
    if m:
        length = int(m.group(1))
        return m.group(2)[:length].strip()
    return ""

def parse_adif(text, filename=""):
    """Parsează un fișier ADIF. Returnează (qsos, errors)."""
    qsos = []
    errors = []
    # Elimină header ADIF (tot ce e înainte de <EOH>)
    eoh = re.search(r'<EOH>', text, re.IGNORECASE)
    body = text[eoh.end():] if eoh else text

    records = re.split(r'<EOR>', body, flags=re.IGNORECASE)
    for line_no, rec in enumerate(records, 1):
        rec = rec.strip()
        if not rec:
            continue
        q = empty_qso()
        q["_source_line"] = line_no
        q["_raw"] = rec[:120]

        q["callsign"] = _adif_field("CALL", rec).upper()
        q["freq"]     = _adif_field("FREQ", rec)          # MHz în ADIF
        q["band"]     = _adif_field("BAND", rec).lower()
        q["mode"]     = _adif_field("MODE", rec).upper()
        q["rst_s"]    = _adif_field("RST_SENT", rec)
        q["rst_r"]    = _adif_field("RST_RCVD", rec)
        q["note"]     = _adif_field("COMMENT", rec) or _adif_field("NOTES", rec)
        q["dxcc"]     = _adif_field("DXCC", rec) or _adif_field("COUNTRY", rec)
        q["locator"]  = _adif_field("GRIDSQUARE", rec).upper()
        q["exchange"] = _adif_field("STX_STRING", rec) or _adif_field("SRX_STRING", rec)
        q["serial"]   = _adif_field("STX", rec)

        # Frecvență MHz → kHz
        if q["freq"]:
            try:
                q["freq"] = str(round(float(q["freq"]) * 1000, 1))
            except ValueError:
                pass

        # Bandă din frecvență dacă lipsește
        if not q["band"] and q["freq"]:
            q["band"] = freq_to_band(q["freq"]) or ""

        # Dată: YYYYMMDD → YYYY-MM-DD
        raw_date = _adif_field("QSO_DATE", rec)
        if raw_date and len(raw_date) == 8:
            q["date"] = "{}-{}-{}".format(raw_date[:4], raw_date[4:6], raw_date[6:8])
        else:
            q["date"] = raw_date

        # Oră: HHMMSS sau HHMM → HH:MM
        raw_time = _adif_field("TIME_ON", rec)
        if raw_time and len(raw_time) >= 4:
            q["time"] = "{}:{}".format(raw_time[:2], raw_time[2:4])
        else:
            q["time"] = raw_time

        if q["callsign"]:
            qsos.append(q)
        elif rec.strip():
            errors.append({"line": line_no, "type": "MISSING_CALL",
                           "message": "QSO fără indicativ (ADIF)", "raw": rec[:80]})

    return qsos, errors


# ═══════════════════════════════════════════════════════════════════
#  CABRILLO
# ═══════════════════════════════════════════════════════════════════
CAB_FREQ_BAND = {
    "1800": "160m", "3500": "80m", "3600": "80m", "7000": "40m",
    "7100": "40m", "10100": "30m", "14000": "20m", "14100": "20m",
    "18068": "17m", "21000": "15m", "24890": "12m", "28000": "10m",
    "50": "6m", "144": "2m", "432": "70cm", "1296": "23cm",
}

def _cab_band(freq_str):
    """Estimează banda din frecvența Cabrillo (poate fi kHz sau MHz)."""
    try:
        f = float(freq_str)
    except (ValueError, TypeError):
        return freq_str.lower()
    # Cabrillo folosește kHz
    b = freq_to_band(f)
    if b:
        return b
    # fallback: încearcă MHz
    return freq_to_band(f * 1000) or freq_str.lower()

def parse_cabrillo(text, filename=""):
    """Parsează Cabrillo 2.0/3.0. Returnează (qsos, errors, header_info)."""
    qsos = []
    errors = []
    header = {}

    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue

        up = line.upper()

        # Header
        if up.startswith("START-OF-LOG"):
            continue
        if up.startswith("END-OF-LOG"):
            break
        if ":" in line and not up.startswith("QSO:"):
            key, _, val = line.partition(":")
            header[key.strip().upper()] = val.strip()
            continue

        if not up.startswith("QSO:"):
            continue

        parts = line.split()
        # QSO: freq mode date time mycall sent_rst sent_exch theircall rcvd_rst rcvd_exch
        # Minimum 9 fields after QSO:
        if len(parts) < 9:
            errors.append({"line": line_no, "type": "CAB_SHORT_QSO",
                           "message": "Linie QSO Cabrillo incompletă ({} câmpuri)".format(len(parts)),
                           "raw": raw_line[:100]})
            continue

        q = empty_qso()
        q["_source_line"] = line_no
        q["_raw"] = raw_line[:120]

        try:
            q["freq"] = parts[1]
            q["band"] = _cab_band(parts[1])
            q["mode"] = parts[2].upper()
            # date: YYYY-MM-DD
            raw_d = parts[3]
            if len(raw_d) == 8 and raw_d.isdigit():
                q["date"] = "{}-{}-{}".format(raw_d[:4], raw_d[4:6], raw_d[6:8])
            else:
                q["date"] = raw_d
            # time: HHMM → HH:MM
            raw_t = parts[4]
            if len(raw_t) == 4 and raw_t.isdigit():
                q["time"] = "{}:{}".format(raw_t[:2], raw_t[2:4])
            else:
                q["time"] = raw_t

            # mycall (parts[5]) ignorat — e indicativul stației care a trimis
            q["rst_s"]    = parts[6] if len(parts) > 6 else ""
            q["exchange"] = parts[7] if len(parts) > 7 else ""
            q["callsign"] = parts[8].upper() if len(parts) > 8 else ""
            q["rst_r"]    = parts[9] if len(parts) > 9 else ""
            if len(parts) > 10:
                q["note"] = " ".join(parts[10:])
        except IndexError as e:
            errors.append({"line": line_no, "type": "CAB_PARSE_ERR",
                           "message": str(e), "raw": raw_line[:100]})
            continue

        if q["callsign"]:
            qsos.append(q)
        else:
            errors.append({"line": line_no, "type": "MISSING_CALL",
                           "message": "QSO Cabrillo fără indicativ", "raw": raw_line[:100]})

    return qsos, errors, header


# ═══════════════════════════════════════════════════════════════════
#  CSV
# ═══════════════════════════════════════════════════════════════════
CSV_FIELD_MAP = {
    # Variante posibile de header CSV → câmp intern
    "call": "callsign", "callsign": "callsign", "indicativ": "callsign",
    "freq": "freq", "frequency": "freq", "frecventa": "freq", "frecvență": "freq",
    "band": "band", "banda": "band", "bandă": "band",
    "mode": "mode", "mod": "mode",
    "rst_s": "rst_s", "rst sent": "rst_s", "rst_sent": "rst_s",
    "rst_r": "rst_r", "rst recv": "rst_r", "rst_rcvd": "rst_r",
    "date": "date", "data": "date",
    "time": "time", "ora": "time", "oră": "time",
    "note": "note", "nota": "note", "notă": "note", "comment": "note",
    "exchange": "exchange", "schimb": "exchange",
    "locator": "locator", "grid": "locator",
    "dxcc": "dxcc", "country": "dxcc", "tara": "dxcc", "țară": "dxcc",
    "serial": "serial",
}

def parse_csv(text, filename=""):
    """Parsează CSV cu detecție automată de separator și header. Returnează (qsos, errors)."""
    qsos = []
    errors = []

    # Detectare separator
    sample = text[:2048]
    sep = ","
    for s in [",", ";", "\t", "|"]:
        if s in sample:
            sep = s
            break

    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=sep)
        headers_raw = reader.fieldnames or []
    except Exception as e:
        return [], [{"line": 1, "type": "CSV_PARSE_ERR",
                     "message": "Nu pot citi CSV: {}".format(e), "raw": ""}]

    # Map header → câmp intern
    col_map = {}
    for h in (headers_raw or []):
        key = h.strip().lower().replace(" ", "_")
        if key in CSV_FIELD_MAP:
            col_map[h] = CSV_FIELD_MAP[key]

    for line_no, row in enumerate(reader, 2):
        q = empty_qso()
        q["_source_line"] = line_no
        q["_raw"] = str(dict(row))[:120]

        for csv_col, internal in col_map.items():
            val = (row.get(csv_col) or "").strip()
            q[internal] = val

        # Fallback: dacă nu s-a mapat nimic, încearcă pozițional
        if not q["callsign"] and headers_raw:
            row_vals = list(row.values())
            if row_vals:
                q["callsign"] = (row_vals[0] or "").strip().upper()

        # Normalizare
        q["callsign"] = q["callsign"].upper()
        q["mode"] = q["mode"].upper()

        # Banda din frecvență dacă lipsește
        if not q["band"] and q["freq"]:
            q["band"] = freq_to_band(q["freq"]) or ""

        # Dată: acceptă YYYYMMDD, YYYY-MM-DD, DD.MM.YYYY
        d = q["date"]
        if d and "-" not in d and "." not in d and len(d) == 8:
            q["date"] = "{}-{}-{}".format(d[:4], d[4:6], d[6:8])
        elif d and "." in d:
            parts = d.split(".")
            if len(parts) == 3 and len(parts[0]) == 2:
                q["date"] = "{}-{}-{}".format(parts[2], parts[1], parts[0])

        # Oră: HHMM → HH:MM
        t = q["time"].replace(":", "")
        if len(t) >= 4:
            q["time"] = "{}:{}".format(t[:2], t[2:4])

        if q["callsign"]:
            qsos.append(q)
        else:
            errors.append({"line": line_no, "type": "MISSING_CALL",
                           "message": "Rând CSV fără indicativ", "raw": q["_raw"]})

    return qsos, errors


# ═══════════════════════════════════════════════════════════════════
#  JSON (YO Log PRO nativ)
# ═══════════════════════════════════════════════════════════════════
JSON_FIELD_MAP = {
    "call": "callsign", "callsign": "callsign", "indicativ": "callsign",
    "freq": "freq", "frequency": "freq",
    "band": "band", "mode": "mode",
    "rst_s": "rst_s", "rst_r": "rst_r",
    "date": "date", "time": "time",
    "note": "note", "exchange": "exchange",
    "locator": "locator", "dxcc": "dxcc", "serial": "serial",
    # YO Log PRO specifice
    "rst": "rst_s", "points": "_points",
}

def parse_json(text, filename=""):
    """Parsează JSON nativ YO Log PRO. Returnează (qsos, errors)."""
    qsos = []
    errors = []

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [], [{"line": 1, "type": "JSON_PARSE_ERR",
                     "message": "JSON invalid: {}".format(e), "raw": ""}]

    # Suportă: listă directă sau dict cu cheie "log"/"qsos"
    if isinstance(data, dict):
        records = data.get("log") or data.get("qsos") or data.get("data") or []
    elif isinstance(data, list):
        records = data
    else:
        return [], [{"line": 1, "type": "JSON_FORMAT_ERR",
                     "message": "Format JSON nerecunoscut", "raw": ""}]

    for line_no, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            errors.append({"line": line_no, "type": "JSON_RECORD_ERR",
                           "message": "Înregistrare JSON nu este dict", "raw": str(rec)[:80]})
            continue

        q = empty_qso()
        q["_source_line"] = line_no
        q["_raw"] = str(rec)[:120]

        for k, v in rec.items():
            mapped = JSON_FIELD_MAP.get(k.lower().strip())
            if mapped and mapped != "_points":
                q[mapped] = str(v).strip() if v is not None else ""

        # Normalizări
        q["callsign"] = q["callsign"].upper()
        q["mode"] = q["mode"].upper()

        if not q["band"] and q["freq"]:
            q["band"] = freq_to_band(q["freq"]) or ""

        # Dată YO Log PRO: poate fi ISO sau YYYYMMDD
        d = q["date"]
        if d and len(d) == 8 and d.isdigit():
            q["date"] = "{}-{}-{}".format(d[:4], d[4:6], d[6:8])

        t = q["time"].replace(":", "")
        if len(t) >= 4:
            q["time"] = "{}:{}".format(t[:2], t[2:4])

        if q["callsign"]:
            qsos.append(q)
        else:
            errors.append({"line": line_no, "type": "MISSING_CALL",
                           "message": "Înregistrare JSON fără indicativ", "raw": q["_raw"]})

    return qsos, errors


# ═══════════════════════════════════════════════════════════════════
#  DISPATCHER principal
# ═══════════════════════════════════════════════════════════════════
def parse_file(filepath):
    """
    Detectează automat formatul și parsează fișierul.
    Returnează: {
        "qsos": [...],
        "errors": [...],
        "format": "adi"|"cabrillo"|"csv"|"json",
        "header": {...},   # doar Cabrillo
        "callsign": str,   # din header Cabrillo sau filename
        "filename": str,
        "total": int,
    }
    """
    result = {
        "qsos": [], "errors": [], "format": "unknown",
        "header": {}, "callsign": "", "filename": os.path.basename(filepath),
        "total": 0,
    }

    try:
        # Încearcă UTF-8, fallback latin-1
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1250"):
            try:
                with open(filepath, "r", encoding=enc) as f:
                    text = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            result["errors"].append({"line": 0, "type": "ENCODING_ERR",
                                     "message": "Nu pot citi fișierul (encoding necunoscut)", "raw": ""})
            return result
    except Exception as e:
        result["errors"].append({"line": 0, "type": "FILE_ERR",
                                 "message": str(e), "raw": ""})
        return result

    ext = os.path.splitext(filepath)[1].lower()
    text_up = text[:1024].upper()

    # Detecție format
    if ext in (".adi", ".adi") or "<CALL:" in text_up or "<EOH>" in text_up:
        result["format"] = "adi"
        qsos, errors = parse_adif(text, filepath)
        result["qsos"], result["errors"] = qsos, errors

    elif ext == ".log" or "START-OF-LOG" in text_up or "QSO:" in text_up:
        result["format"] = "cabrillo"
        qsos, errors, header = parse_cabrillo(text, filepath)
        result["qsos"], result["errors"], result["header"] = qsos, errors, header
        result["callsign"] = header.get("CALLSIGN", "")

    elif ext == ".json" or (text.strip().startswith("{") or text.strip().startswith("[")):
        result["format"] = "json"
        qsos, errors = parse_json(text, filepath)
        result["qsos"], result["errors"] = qsos, errors

    elif ext == ".csv" or "," in text[:200] or ";" in text[:200]:
        result["format"] = "csv"
        qsos, errors = parse_csv(text, filepath)
        result["qsos"], result["errors"] = qsos, errors

    else:
        # Încearcă toate formatele
        for fmt, fn in [("adi", parse_adif), ("cabrillo", None),
                        ("csv", parse_csv), ("json", parse_json)]:
            if fmt == "cabrillo":
                q, e, h = parse_cabrillo(text, filepath)
            else:
                q, e = fn(text, filepath)
                h = {}
            if q:
                result["format"] = fmt
                result["qsos"] = q
                result["errors"] = e
                if fmt == "cabrillo":
                    result["header"] = h
                break
        else:
            result["errors"].append({"line": 0, "type": "FORMAT_UNKNOWN",
                                     "message": "Format fișier nerecunoscut", "raw": ""})

    # Callsign din filename dacă nu s-a găsit în header
    if not result["callsign"]:
        base = os.path.splitext(os.path.basename(filepath))[0]
        result["callsign"] = base.upper()

    result["total"] = len(result["qsos"])
    return result
