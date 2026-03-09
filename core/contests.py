#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Contest Rules Engine
Reguli și configurații pentru concursurile YO suportate.
"""

BANDS_HF  = ["160m","80m","40m","30m","20m","17m","15m","12m","10m"]
BANDS_VHF = ["6m","2m"]
BANDS_UHF = ["70cm","23cm"]
BANDS_ALL = BANDS_HF + BANDS_VHF + BANDS_UHF

MODES_ALL = ["SSB","CW","DIGI","FT8","FT4","RTTY","AM","FM","PSK31","JT65"]

# RST valid ranges per mode
RST_RANGES = {
    "SSB": (11, 59), "AM": (11, 59), "FM": (11, 59),
    "CW":  (111, 599), "RTTY": (111, 599), "PSK31": (111, 599),
    "FT8": (111, 599), "FT4": (111, 599), "JT65": (111, 599),
    "DIGI":(111, 599),
}

CONTESTS = {
    "maraton": {
        "name": "Maraton Ion Creangă",
        "cabrillo_name": "MARATON ION CREANGA",
        "scoring_mode": "maraton",
        "points_per_qso": 1,
        "min_qso": 100,
        "allowed_bands": BANDS_HF + BANDS_VHF,
        "allowed_modes": MODES_ALL,
        "duration_hours": 24,
        "exchange": "county",          # schimb = județ
        "multiplier": "county",        # multiplicatori = județe unice
        "cross_check": True,
        "description": "Concurs național 24h, schimb județ, multiplicatori județe unice.",
    },
    "stafeta": {
        "name": "Ștafeta Radioamatorilor",
        "cabrillo_name": "STAFETA",
        "scoring_mode": "per_qso",
        "points_per_qso": 2,
        "min_qso": 50,
        "allowed_bands": BANDS_HF + BANDS_VHF,
        "allowed_modes": MODES_ALL,
        "duration_hours": 12,
        "exchange": "serial",
        "multiplier": "none",
        "cross_check": True,
        "description": "Concurs național 12h, schimb număr serial, 2 puncte/QSO.",
    },
    "yodxhf": {
        "name": "YO DX HF Contest",
        "cabrillo_name": "YO DX HF",
        "scoring_mode": "per_band",
        "points_per_qso": 1,
        "min_qso": 0,
        "allowed_bands": BANDS_HF,
        "allowed_modes": ["SSB", "CW"],
        "duration_hours": 24,
        "exchange": "county",
        "multiplier": "dxcc_band",     # multiplicatori DXCC per bandă
        "cross_check": True,
        "description": "Concurs DX HF 24h, SSB+CW, multiplicatori DXCC per bandă.",
    },
    "yovhf": {
        "name": "YO VHF Contest",
        "cabrillo_name": "YO VHF",
        "scoring_mode": "distance",
        "points_per_qso": 1,
        "min_qso": 0,
        "allowed_bands": ["6m", "2m", "70cm", "23cm"],
        "allowed_modes": ["SSB", "FM", "CW"],
        "duration_hours": 6,
        "exchange": "locator",
        "multiplier": "locator_field",
        "cross_check": True,
        "description": "Concurs VHF 6h, schimb locator, puncte = distanță km.",
    },
    "fieldday": {
        "name": "Field Day",
        "cabrillo_name": "FIELD DAY",
        "scoring_mode": "per_qso",
        "points_per_qso": 2,
        "min_qso": 0,
        "allowed_bands": BANDS_HF,
        "allowed_modes": MODES_ALL,
        "duration_hours": 24,
        "exchange": "county",
        "multiplier": "county",
        "cross_check": True,
        "description": "Field Day 24h, schimb județ, 2 puncte/QSO.",
    },
    "sprint": {
        "name": "Sprint Contest",
        "cabrillo_name": "SPRINT",
        "scoring_mode": "per_qso",
        "points_per_qso": 1,
        "min_qso": 0,
        "allowed_bands": BANDS_HF,
        "allowed_modes": ["SSB", "CW"],
        "duration_hours": 4,
        "exchange": "serial",
        "multiplier": "none",
        "cross_check": True,
        "description": "Sprint 4h, schimb număr serial, 1 punct/QSO.",
    },
}

YO_COUNTIES = [
    "AB","AR","AG","BC","BH","BN","BT","BV","BR","BZ",
    "CS","CL","CJ","CT","CV","DB","DJ","GL","GR","GJ",
    "HR","HD","IL","IS","IF","MM","MH","MS","NT","OT",
    "PH","SM","SJ","SB","SV","TR","TM","TL","VS","VL","VN",
    "B",   # București
]

DXCC_PREFIXES = {
    "YO": "Romania", "DL": "Germany", "G": "England", "F": "France",
    "I": "Italy", "SP": "Poland", "OK": "Czech Republic", "OM": "Slovakia",
    "HA": "Hungary", "9A": "Croatia", "S5": "Slovenia", "OE": "Austria",
    "HB9": "Switzerland", "PA": "Netherlands", "ON": "Belgium",
    "LY": "Lithuania", "YL": "Latvia", "ES": "Estonia",
    "OH": "Finland", "SM": "Sweden", "LA": "Norway", "OZ": "Denmark",
    "UA": "Russia", "UR": "Ukraine", "ER": "Moldova",
    "LZ": "Bulgaria", "SV": "Greece", "YU": "Serbia",
    "Z3": "North Macedonia", "E7": "Bosnia", "T9": "Bosnia",
    "4O": "Montenegro", "ZA": "Albania", "TA": "Turkey",
    "W": "USA", "K": "USA", "VE": "Canada", "JA": "Japan",
    "VK": "Australia", "ZL": "New Zealand", "PY": "Brazil",
    "LU": "Argentina", "CE": "Chile", "XE": "Mexico",
}

def get_contest(contest_id):
    """Returnează regulile concursului sau None dacă nu există."""
    return CONTESTS.get(contest_id)

def list_contests():
    """Returnează lista de concursuri disponibile."""
    return [(k, v["name"]) for k, v in CONTESTS.items()]

def guess_dxcc(callsign):
    """Estimează țara DXCC din prefix indicativ."""
    call = callsign.upper().strip()
    # Încearcă prefixe lungi mai întâi
    for length in (4, 3, 2, 1):
        prefix = call[:length]
        if prefix in DXCC_PREFIXES:
            return DXCC_PREFIXES[prefix]
    return "Unknown"

def is_valid_county(county):
    return county.upper() in YO_COUNTIES

def freq_to_band(freq_khz):
    """Convertește frecvența kHz în bandă."""
    try:
        f = float(freq_khz)
    except (ValueError, TypeError):
        return None
    if 1800 <= f <= 2000:   return "160m"
    if 3500 <= f <= 3800:   return "80m"
    if 7000 <= f <= 7200:   return "40m"
    if 10100 <= f <= 10150: return "30m"
    if 14000 <= f <= 14350: return "20m"
    if 18068 <= f <= 18168: return "17m"
    if 21000 <= f <= 21450: return "15m"
    if 24890 <= f <= 24990: return "12m"
    if 28000 <= f <= 29700: return "10m"
    if 50000 <= f <= 54000: return "6m"
    if 144000 <= f <= 146000: return "2m"
    if 430000 <= f <= 440000: return "70cm"
    if 1240000 <= f <= 1300000: return "23cm"
    return None
