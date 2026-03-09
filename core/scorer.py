#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Scorer
Calculează scorul final per concurs și generează clasamentul.
"""

import math
from collections import defaultdict
from core.contests import CONTESTS, guess_dxcc, is_valid_county

# ── Locator → coordonate ─────────────────────────────────────────
def locator_to_latlon(locator):
    """Convertește locator Maidenhead 4 sau 6 caractere în (lat, lon)."""
    loc = locator.upper().strip()
    if len(loc) < 4:
        return None, None
    try:
        lon = (ord(loc[0]) - ord('A')) * 20 - 180
        lat = (ord(loc[1]) - ord('A')) * 10 - 90
        lon += (int(loc[2])) * 2
        lat += (int(loc[3])) * 1
        if len(loc) >= 6:
            lon += (ord(loc[4]) - ord('A') + 0.5) / 12
            lat += (ord(loc[5]) - ord('A') + 0.5) / 24
        else:
            lon += 1.0
            lat += 0.5
        return lat, lon
    except (IndexError, ValueError):
        return None, None

def haversine_km(lat1, lon1, lat2, lon2):
    """Distanța Haversine în km între două puncte geografice."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return round(2 * R * math.asin(math.sqrt(a)))


# ════════════════════════════════════════════════════════════════
#  SCORER per concurs
# ════════════════════════════════════════════════════════════════

def _points_per_qso(q, contest, station_locator=""):
    """Calculează punctele pentru un singur QSO."""
    mode = contest.get("scoring_mode", "none")

    if mode == "none":
        return 0

    if mode in ("per_qso", "maraton", "sprint"):
        return contest.get("points_per_qso", 1)

    if mode == "per_band":
        # Puncte diferite per bandă (se poate extinde cu dict)
        return contest.get("points_per_qso", 1)

    if mode == "distance":
        # Puncte = km rotunjit la 1 km
        loc_their = q.get("locator", "").strip()
        loc_mine  = station_locator or ""
        if loc_their and loc_mine:
            la1, lo1 = locator_to_latlon(loc_mine)
            la2, lo2 = locator_to_latlon(loc_their)
            if la1 and la2:
                km = haversine_km(la1, lo1, la2, lo2)
                return max(1, km)
        return 1  # fallback

    return contest.get("points_per_qso", 1)


def _multipliers(qsos_valid, contest, qso_flags):
    """
    Calculează multiplicatorii pentru logul validat.
    Returnează (multiplier_count, multiplier_set).
    """
    mode = contest.get("multiplier", "none")
    mults = set()

    for i, q in enumerate(qsos_valid):
        if qso_flags.get(i) in ("error", "duplicate"):
            continue

        if mode == "county":
            exch = q.get("exchange", "").strip().upper()
            if is_valid_county(exch):
                mults.add(exch)

        elif mode == "dxcc_band":
            dxcc  = guess_dxcc(q["callsign"])
            band  = q.get("band", "").lower()
            if dxcc and band:
                mults.add(f"{dxcc}:{band}")

        elif mode == "locator_field":
            loc = q.get("locator", "").upper()
            if len(loc) >= 4:
                mults.add(loc[:4])  # field = primele 4 caractere

        elif mode == "none":
            pass

    return len(mults), mults


def score_log(qsos, contest_id, station_callsign="", station_locator="",
              qso_flags=None, cross_check_results=None):
    """
    Calculează scorul complet al unui log.

    qso_flags: dict {idx: "ok"|"error"|"warning"|"duplicate"} din Validator
    cross_check_results: rezultatul din CrossCheck (opțional — reduce QSO-urile neconfirmate)

    Returnează: {
        "contest_id":   str,
        "contest_name": str,
        "callsign":     str,
        "total_qsos":   int,
        "valid_qsos":   int,
        "error_qsos":   int,
        "duplicate_qsos": int,
        "unconfirmed_qsos": int,  # din cross-check
        "qso_points":   int,
        "multipliers":  int,
        "multiplier_set": set,
        "total_score":  int,
        "per_band":     {band: {"qsos": int, "points": int}},
        "breakdown":    [{idx, callsign, band, mode, points, status}, ...],
        "penalties":    int,   # puncte penalizate (neconfirmate, erori)
    }
    """
    contest = CONTESTS.get(contest_id)
    if not contest:
        return {"error": f"Concurs necunoscut: {contest_id}"}

    if qso_flags is None:
        qso_flags = {i: "ok" for i in range(len(qsos))}

    # QSO-uri neconfirmate din cross-check
    unconfirmed_set = set()
    if cross_check_results:
        for idx in cross_check_results.get("unconfirmed", []):
            unconfirmed_set.add(idx)
        for idx_a, idx_b in cross_check_results.get("busted_band", []):
            unconfirmed_set.add(idx_a)
        for idx_a, idx_b, _ in cross_check_results.get("busted_time", []):
            unconfirmed_set.add(idx_a)
        for idx_a, idx_b, call in cross_check_results.get("busted_call", []):
            unconfirmed_set.add(idx_a)

    qso_points    = 0
    valid_qsos    = 0
    error_qsos    = 0
    dup_qsos      = 0
    per_band      = defaultdict(lambda: {"qsos": 0, "points": 0})
    breakdown     = []
    penalties     = 0

    for i, q in enumerate(qsos):
        flag   = qso_flags.get(i, "ok")
        status = flag

        # Penalizare cross-check
        if i in unconfirmed_set and flag == "ok":
            status = "unconfirmed"

        if flag in ("error", "duplicate") or status == "unconfirmed":
            if flag == "error":   error_qsos += 1
            if flag == "duplicate": dup_qsos += 1
            pts = 0
        else:
            pts = _points_per_qso(q, contest, station_locator)
            qso_points += pts
            valid_qsos += 1

        band = q.get("band", "?").lower()
        per_band[band]["qsos"]   += 1
        per_band[band]["points"] += pts

        breakdown.append({
            "idx":      i,
            "callsign": q.get("callsign", ""),
            "band":     band,
            "mode":     q.get("mode", ""),
            "date":     q.get("date", ""),
            "time":     q.get("time", ""),
            "exchange": q.get("exchange", ""),
            "rst_s":    q.get("rst_s", ""),
            "rst_r":    q.get("rst_r", ""),
            "points":   pts,
            "status":   status,
        })

    # Multiplicatori (doar pe QSO-urile valide)
    mult_count, mult_set = _multipliers(qsos, contest, qso_flags)

    # Scor total
    scoring_mode = contest.get("scoring_mode", "none")
    if scoring_mode == "none":
        total_score = valid_qsos
    elif mult_count > 0:
        total_score = qso_points * mult_count
    else:
        total_score = qso_points

    return {
        "contest_id":       contest_id,
        "contest_name":     contest["name"],
        "callsign":         station_callsign,
        "total_qsos":       len(qsos),
        "valid_qsos":       valid_qsos,
        "error_qsos":       error_qsos,
        "duplicate_qsos":   dup_qsos,
        "unconfirmed_qsos": len(unconfirmed_set),
        "qso_points":       qso_points,
        "multipliers":      mult_count,
        "multiplier_set":   mult_set,
        "total_score":      total_score,
        "per_band":         dict(per_band),
        "breakdown":        breakdown,
        "penalties":        penalties,
    }


def build_ranking(scores_list):
    """
    Construiește clasamentul din lista de score_log results.
    scores_list = [score_result, ...]
    Returnează lista sortată descrescător după total_score.
    """
    valid = [s for s in scores_list if "error" not in s]
    ranked = sorted(valid, key=lambda s: s["total_score"], reverse=True)

    result = []
    for pos, s in enumerate(ranked, 1):
        result.append({
            "position":       pos,
            "callsign":       s["callsign"],
            "contest_name":   s["contest_name"],
            "total_qsos":     s["total_qsos"],
            "valid_qsos":     s["valid_qsos"],
            "error_qsos":     s["error_qsos"],
            "duplicate_qsos": s["duplicate_qsos"],
            "qso_points":     s["qso_points"],
            "multipliers":    s["multipliers"],
            "total_score":    s["total_score"],
        })
    return result
