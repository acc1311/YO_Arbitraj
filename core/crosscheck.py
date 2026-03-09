#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Cross-Check Engine
Compară două loguri și determină QSO-urile confirmate / neconfirmate.
Fereastră de toleranță: ±N minute (implicit 3).
"""

import datetime
from collections import defaultdict

TOLERANCE_MINUTES = 3   # default; poate fi suprascris la apel

# ── Parsare timestamp ────────────────────────────────────────────
def _parse_dt(qso):
    """Returnează datetime din câmpurile date+time ale unui QSO, sau None."""
    d = qso.get("date", "").strip()
    t = qso.get("time", "").strip()
    if not d or not t:
        return None
    # Asigurăm HH:MM
    t_clean = t.replace(":", "")
    if len(t_clean) < 4:
        return None
    t_fmt = "{}:{}".format(t_clean[:2], t_clean[2:4])
    try:
        return datetime.datetime.strptime("{} {}".format(d, t_fmt), "%Y-%m-%d %H:%M")
    except ValueError:
        return None


# ── Normalizare bandă ────────────────────────────────────────────
def _norm_band(band):
    return (band or "").lower().strip()


# ── Normalizare mod ──────────────────────────────────────────────
MODE_GROUPS = {
    "SSB": {"SSB", "USB", "LSB", "AM", "FM"},
    "CW":  {"CW"},
    "DIGI": {"FT8", "FT4", "RTTY", "PSK31", "JT65", "DIGI"},
}
def _norm_mode(mode):
    m = (mode or "").upper().strip()
    for group, members in MODE_GROUPS.items():
        if m in members:
            return group
    return m


# ════════════════════════════════════════════════════════════════
#  CROSS-CHECK PRINCIPAL
# ════════════════════════════════════════════════════════════════
def cross_check(log_a, log_b, call_a, call_b, tolerance_min=TOLERANCE_MINUTES):
    """
    Compară log_a (lista QSO) cu log_b.

    log_a = QSO-urile stației A — căutăm în B QSO-uri care să confirme pe A.
    log_b = QSO-urile stației B — căutăm confirmări pentru A.
    call_a, call_b = indicativele stațiilor.

    Returnează:
    {
        "confirmed":    [idx_in_a, ...],
        "unconfirmed":  [idx_in_a, ...],
        "busted_call":  [(idx_a, idx_b, found_call), ...],   # indicativ greșit
        "busted_band":  [(idx_a, idx_b), ...],               # bandă greșită
        "busted_time":  [(idx_a, idx_b, delta_min), ...],    # timp în afara ferestrei
        "details":      {idx_a: detail_dict},
        "stats": {
            "total_a": int, "confirmed": int, "unconfirmed": int,
            "busted_call": int, "busted_band": int, "busted_time": int,
        }
    }
    """
    result = {
        "confirmed":   [],
        "unconfirmed": [],
        "busted_call": [],
        "busted_band": [],
        "busted_time": [],
        "details":     {},
        "stats":       {},
    }

    call_a_up = call_a.upper()
    call_b_up = call_b.upper()

    # Indexăm log_b după indicativul stației A (cum apare în log_b = stația B l-a lucrat pe A)
    # Structură: {call_upper: [qso_b_idx, ...]}
    b_by_call = defaultdict(list)
    for i, q in enumerate(log_b):
        b_by_call[q["callsign"].upper()].append(i)

    tol = datetime.timedelta(minutes=tolerance_min)

    for idx_a, q_a in enumerate(log_a):
        # q_a: înregistrarea din logul A — A a lucrat B
        # Căutăm în log_b înregistrări unde B a lucrat A (callsign == call_a)
        detail = {
            "callsign_a": q_a["callsign"],
            "band_a":     q_a["band"],
            "mode_a":     q_a["mode"],
            "date_a":     q_a["date"],
            "time_a":     q_a["time"],
            "status":     "unconfirmed",
            "match_idx_b": None,
            "issue":       "",
        }

        # Stația B căuta după indicativul A
        candidates_b = b_by_call.get(call_a_up, [])

        dt_a = _parse_dt(q_a)
        band_a = _norm_band(q_a["band"])
        mode_a = _norm_mode(q_a["mode"])

        best_match = None
        best_delta = None

        for idx_b in candidates_b:
            q_b = log_b[idx_b]
            # B trebuie să fi lucrat A pe aceeași bandă
            band_b = _norm_band(q_b["band"])
            mode_b = _norm_mode(q_b["mode"])
            dt_b   = _parse_dt(q_b)

            # Verificare bandă
            if band_a and band_b and band_a != band_b:
                continue  # bandă diferită, nu e candidat

            # Verificare timp
            if dt_a and dt_b:
                delta = abs(dt_a - dt_b)
                if delta > tol:
                    continue  # în afara ferestrei
                if best_delta is None or delta < best_delta:
                    best_match = idx_b
                    best_delta = delta
            else:
                # Fără timestamp, acceptăm dacă banda e ok
                if best_match is None:
                    best_match = idx_b
                    best_delta = datetime.timedelta(0)

        if best_match is not None:
            result["confirmed"].append(idx_a)
            detail["status"]     = "confirmed"
            detail["match_idx_b"] = best_match
            if best_delta:
                detail["delta_min"] = round(best_delta.total_seconds() / 60, 1)
        else:
            # Nu am găsit confirmare — verificăm de ce
            issue = "Nicio înregistrare în log-ul contrar"

            # Verificare: există în B cu call_a dar bandă greșită?
            for idx_b in candidates_b:
                q_b = log_b[idx_b]
                band_b = _norm_band(q_b["band"])
                dt_b   = _parse_dt(q_b)
                if band_a != band_b:
                    result["busted_band"].append((idx_a, idx_b))
                    issue = "Bandă diferită: A={}, B={}".format(band_a, band_b)
                    detail["status"] = "busted_band"
                    detail["match_idx_b"] = idx_b
                    break
                if dt_a and dt_b:
                    delta = abs(dt_a - dt_b)
                    if delta > tol:
                        result["busted_time"].append((idx_a, idx_b, round(delta.total_seconds()/60, 1)))
                        issue = "Diferență timp {} min (>{} min)".format(round(delta.total_seconds()/60,1), tolerance_min)
                        detail["status"] = "busted_time"
                        detail["match_idx_b"] = idx_b
                        break

            # Verificare: există log_b cu indicativ similar (busted call)?
            # Căutare fuzzy: primele 3 caractere identice
            if detail["status"] == "unconfirmed":
                call_a3 = call_a_up[:3]
                for idx_b, q_b in enumerate(log_b):
                    if q_b["callsign"].upper()[:3] == call_a3 and q_b["callsign"].upper() != call_a_up:
                        band_b = _norm_band(q_b["band"])
                        dt_b   = _parse_dt(q_b)
                        if band_a and band_b and band_a != band_b:
                            continue
                        if dt_a and dt_b and abs(dt_a - dt_b) > tol:
                            continue
                        result["busted_call"].append((idx_a, idx_b, q_b["callsign"]))
                        issue = "Posibil indicativ greșit: în log B apare '{}'".format(q_b['callsign'])
                        detail["status"] = "busted_call"
                        detail["match_idx_b"] = idx_b
                        break

            if detail["status"] == "unconfirmed":
                result["unconfirmed"].append(idx_a)
            detail["issue"] = issue

        result["details"][idx_a] = detail

    result["stats"] = {
        "total_a":    len(log_a),
        "confirmed":  len(result["confirmed"]),
        "unconfirmed":len(result["unconfirmed"]),
        "busted_call":len(result["busted_call"]),
        "busted_band":len(result["busted_band"]),
        "busted_time":len(result["busted_time"]),
        "tolerance_min": tolerance_min,
    }

    return result


def cross_check_all(logs, tolerance_min=TOLERANCE_MINUTES):
    """
    Cross-check pentru N loguri simultan (ex: toți participanții la un concurs).
    logs = [{"callsign": str, "qsos": [...]}, ...]
    Returnează matrice de rezultate.
    """
    n = len(logs)
    matrix = {}

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            key = "{}_vs_{}".format(logs[i]['callsign'], logs[j]['callsign'])
            matrix[key] = cross_check(
                logs[i]["qsos"], logs[j]["qsos"],
                logs[i]["callsign"], logs[j]["callsign"],
                tolerance_min
            )

    # Sumar per stație
    summary = {}
    for i, log in enumerate(logs):
        call = log["callsign"]
        confirmed_total   = 0
        unconfirmed_total = 0
        for j in range(n):
            if i == j:
                continue
            key = "{}_vs_{}".format(call, logs[j]['callsign'])
            if key in matrix:
                s = matrix[key]["stats"]
                confirmed_total   += s["confirmed"]
                unconfirmed_total += s["unconfirmed"]
        summary[call] = {
            "total":       len(log["qsos"]),
            "confirmed":   confirmed_total,
            "unconfirmed": unconfirmed_total,
        }

    return {"matrix": matrix, "summary": summary}
