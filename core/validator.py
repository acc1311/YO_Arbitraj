#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Validator
Verifică fiecare QSO individual: RST, date/oră, bandă, mod, duplicate, exchange.
"""

import re
import datetime
from collections import defaultdict
from core.contests import RST_RANGES, is_valid_county, CONTESTS, BANDS_ALL

# ── Severitate erori ─────────────────────────────────────────────
SEV_ERROR   = "ERROR"    # QSO eliminat din scoring
SEV_WARNING = "WARNING"  # QSO păstrat, scor redus sau notă
SEV_INFO    = "INFO"     # Informație, fără penalizare

class ValidationError:
    def __init__(self, qso_idx, callsign, err_type, message, severity=SEV_ERROR, field=""):
        self.qso_idx  = qso_idx
        self.callsign = callsign
        self.err_type = err_type
        self.message  = message
        self.severity = severity
        self.field    = field

    def to_dict(self):
        return {
            "qso_idx":  self.qso_idx,
            "callsign": self.callsign,
            "type":     self.err_type,
            "message":  self.message,
            "severity": self.severity,
            "field":    self.field,
        }

    def __repr__(self):
        return f"[{self.severity}] QSO#{self.qso_idx} {self.callsign}: {self.message}"


# ── Validare RST ─────────────────────────────────────────────────
def _valid_rst(rst_str, mode):
    """Verifică RST pentru modul dat. Returnează (ok, message)."""
    rst = rst_str.strip()
    if not rst:
        return False, "RST lipsă"

    mode_up = mode.upper()
    lo, hi = RST_RANGES.get(mode_up, RST_RANGES.get("SSB", (11, 59)))

    # Acceptă RST ca număr întreg
    try:
        val = int(rst)
    except ValueError:
        return False, f"RST '{rst}' nu este numeric"

    if val < lo or val > hi:
        return False, f"RST '{rst}' în afara intervalului {lo}–{hi} pentru {mode_up}"

    # Verificare cifre individuale
    rst_s = str(val)
    if len(rst_s) == 2:  # SSB: readability(1-5) tone(1-9)
        r, t = int(rst_s[0]), int(rst_s[1])
        if r < 1 or r > 5:
            return False, f"RST readability '{r}' invalid (1-5)"
        if t < 1 or t > 9:
            return False, f"RST tone '{t}' invalid (1-9)"
    elif len(rst_s) == 3:  # CW: r(1-5) t(1-9) s(1-9)
        r, t, s = int(rst_s[0]), int(rst_s[1]), int(rst_s[2])
        if r < 1 or r > 5:
            return False, f"RST readability '{r}' invalid (1-5)"
        if t < 1 or t > 9:
            return False, f"RST tone '{t}' invalid (1-9)"
        if s < 1 or s > 9:
            return False, f"RST strength '{s}' invalid (1-9)"

    return True, ""


# ── Validare dată ────────────────────────────────────────────────
def _valid_date(date_str):
    """Verifică data în format YYYY-MM-DD."""
    d = date_str.strip()
    if not d:
        return False, "Dată lipsă"
    try:
        dt = datetime.datetime.strptime(d, "%Y-%m-%d")
        # Dată rezonabilă: 2000-01-01 — astăzi+1
        if dt.year < 2000 or dt > datetime.datetime.now() + datetime.timedelta(days=1):
            return False, f"Dată suspectă: {d}"
        return True, ""
    except ValueError:
        return False, f"Format dată invalid: '{d}' (așteptat YYYY-MM-DD)"


# ── Validare oră ─────────────────────────────────────────────────
def _valid_time(time_str):
    """Verifică ora în format HH:MM."""
    t = time_str.strip()
    if not t:
        return False, "Oră lipsă"
    try:
        datetime.datetime.strptime(t, "%H:%M")
        return True, ""
    except ValueError:
        return False, f"Format oră invalid: '{t}' (așteptat HH:MM)"


# ── Validare indicativ ───────────────────────────────────────────
_CALL_RE = re.compile(
    r'^[A-Z0-9]{1,3}[0-9][A-Z]{1,4}(/[A-Z0-9]+)?$', re.IGNORECASE
)

def _valid_callsign(call):
    if not call:
        return False, "Indicativ lipsă"
    if not _CALL_RE.match(call.upper()):
        return False, f"Indicativ suspect: '{call}'"
    return True, ""


# ── Validare bandă/mod pentru concurs ───────────────────────────
def _valid_band_mode(band, mode, contest_id):
    contest = CONTESTS.get(contest_id, {})
    allowed_bands = contest.get("allowed_bands", BANDS_ALL)
    allowed_modes = contest.get("allowed_modes", [])

    errors = []
    if band and allowed_bands and band.lower() not in [b.lower() for b in allowed_bands]:
        errors.append(f"Bandă '{band}' nepermisă în {contest.get('name', contest_id)}")
    if mode and allowed_modes and mode.upper() not in [m.upper() for m in allowed_modes]:
        errors.append(f"Mod '{mode}' nepermis în {contest.get('name', contest_id)}")
    return errors


# ── Detectare duplicate ──────────────────────────────────────────
def find_duplicates(qsos):
    """
    Găsește duplicate: același indicativ + bandă (ignora modul și ora).
    Returnează dict: {(callsign, band): [idx1, idx2, ...]}
    """
    seen = defaultdict(list)
    for i, q in enumerate(qsos):
        key = (q["callsign"].upper(), q["band"].lower())
        seen[key].append(i)
    return {k: v for k, v in seen.items() if len(v) > 1}


# ════════════════════════════════════════════════════════════════
#  VALIDATOR PRINCIPAL
# ════════════════════════════════════════════════════════════════
def validate_log(qsos, contest_id=None, station_callsign=""):
    """
    Validează toate QSO-urile dintr-un log.
    Returnează: {
        "errors": [ValidationError, ...],
        "duplicate_groups": {...},
        "valid_count": int,
        "error_count": int,
        "warning_count": int,
        "qso_flags": {idx: "ok"|"error"|"warning"|"duplicate"},
    }
    """
    all_errors = []
    qso_flags  = {}

    for i, q in enumerate(qsos):
        q_errors = []

        # 1. Indicativ
        ok, msg = _valid_callsign(q.get("callsign", ""))
        if not ok:
            q_errors.append(ValidationError(i, q.get("callsign","?"), "BAD_CALL", msg, SEV_ERROR, "callsign"))

        # Indicator: stația nu poate lucra cu ea însăși
        if station_callsign and q.get("callsign","").upper() == station_callsign.upper():
            q_errors.append(ValidationError(i, q["callsign"], "SELF_QSO",
                "QSO cu propriul indicativ", SEV_ERROR, "callsign"))

        # 2. RST
        mode = q.get("mode", "SSB")
        for field, label in [("rst_s", "RST trimis"), ("rst_r", "RST primit")]:
            rst = q.get(field, "")
            if rst:
                ok, msg = _valid_rst(rst, mode)
                if not ok:
                    q_errors.append(ValidationError(i, q.get("callsign","?"),
                        "BAD_RST", f"{label}: {msg}", SEV_WARNING, field))
            else:
                q_errors.append(ValidationError(i, q.get("callsign","?"),
                    "MISSING_RST", f"{label} lipsă", SEV_WARNING, field))

        # 3. Dată
        ok, msg = _valid_date(q.get("date", ""))
        if not ok:
            q_errors.append(ValidationError(i, q.get("callsign","?"),
                "BAD_DATE", msg, SEV_ERROR, "date"))

        # 4. Oră
        ok, msg = _valid_time(q.get("time", ""))
        if not ok:
            q_errors.append(ValidationError(i, q.get("callsign","?"),
                "BAD_TIME", msg, SEV_WARNING, "time"))

        # 5. Bandă și mod (dacă concurs specificat)
        if contest_id:
            band_mode_errs = _valid_band_mode(q.get("band",""), q.get("mode",""), contest_id)
            for msg in band_mode_errs:
                q_errors.append(ValidationError(i, q.get("callsign","?"),
                    "BAD_BAND_MODE", msg, SEV_ERROR, "band"))

        # 6. Exchange (județ) pentru concursuri care îl cer
        if contest_id:
            contest = CONTESTS.get(contest_id, {})
            if contest.get("exchange") == "county":
                exch = q.get("exchange", "").strip().upper()
                if not exch:
                    q_errors.append(ValidationError(i, q.get("callsign","?"),
                        "MISSING_EXCHANGE", "Schimb (județ) lipsă", SEV_WARNING, "exchange"))
                elif not is_valid_county(exch):
                    q_errors.append(ValidationError(i, q.get("callsign","?"),
                        "BAD_COUNTY", f"Județ invalid: '{exch}'", SEV_WARNING, "exchange"))

        # Setare flag
        has_error   = any(e.severity == SEV_ERROR   for e in q_errors)
        has_warning = any(e.severity == SEV_WARNING  for e in q_errors)
        if has_error:
            qso_flags[i] = "error"
        elif has_warning:
            qso_flags[i] = "warning"
        else:
            qso_flags[i] = "ok"

        all_errors.extend(q_errors)

    # Detectare duplicate
    dup_groups = find_duplicates(qsos)
    for key, indices in dup_groups.items():
        call, band = key
        for idx in indices[1:]:  # primul e "câștigătorul", restul sunt duplicate
            if qso_flags.get(idx) != "error":
                qso_flags[idx] = "duplicate"
            all_errors.append(ValidationError(
                idx, call, "DUPLICATE",
                f"Duplicat pe {band} (apare în QSO #{indices[0]+1} și #{idx+1})",
                SEV_ERROR, "callsign"
            ))

    error_count   = sum(1 for e in all_errors if e.severity == SEV_ERROR)
    warning_count = sum(1 for e in all_errors if e.severity == SEV_WARNING)
    valid_count   = sum(1 for f in qso_flags.values() if f == "ok")

    return {
        "errors":           all_errors,
        "duplicate_groups": dup_groups,
        "valid_count":      valid_count,
        "error_count":      error_count,
        "warning_count":    warning_count,
        "qso_flags":        qso_flags,
    }
