#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Unit Tests
Testează parser-ul, validatorul și cross-check-ul.
Rulare: python -m pytest tests/ -v
        sau: python tests/test_core.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.parser    import parse_adif, parse_cabrillo, parse_csv, parse_json
from core.validator import validate_log, find_duplicates
from core.crosscheck import cross_check
from core.scorer    import score_log, build_ranking
from core.contests  import freq_to_band, guess_dxcc, is_valid_county


# ═══════════════════════════════════════════════════════════════════
#  PARSER TESTS
# ═══════════════════════════════════════════════════════════════════
class TestADIF(unittest.TestCase):

    SAMPLE_ADIF = """
ADIF Export
<EOH>
<CALL:6>YO8RJU <BAND:3>40m <MODE:3>SSB <QSO_DATE:8>20240315
<TIME_ON:4>1430 <RST_SENT:2>59 <RST_RCVD:2>59 <COMMENT:2>NT <EOR>
<CALL:5>LZ1AB <BAND:3>80m <MODE:2>CW <QSO_DATE:8>20240315
<TIME_ON:6>143500 <RST_SENT:3>599 <RST_RCVD:3>599 <EOR>
<EOR>
"""
    def test_basic_parse(self):
        qsos, errors = parse_adif(self.SAMPLE_ADIF)
        self.assertEqual(len(qsos), 2)
        self.assertEqual(qsos[0]["callsign"], "YO8RJU")
        self.assertEqual(qsos[0]["band"], "40m")
        self.assertEqual(qsos[0]["mode"], "SSB")
        self.assertEqual(qsos[0]["date"], "2024-03-15")
        self.assertEqual(qsos[0]["time"], "14:30")

    def test_cw_qso(self):
        qsos, errors = parse_adif(self.SAMPLE_ADIF)
        self.assertEqual(qsos[1]["callsign"], "LZ1AB")
        self.assertEqual(qsos[1]["mode"], "CW")
        self.assertEqual(qsos[1]["rst_s"], "599")

    def test_empty_record_ignored(self):
        qsos, errors = parse_adif(self.SAMPLE_ADIF)
        self.assertEqual(len(qsos), 2)  # 3rd <EOR> este gol

    def test_no_eoh(self):
        adif = "<CALL:5>YO1AB <BAND:3>20m <MODE:3>SSB <QSO_DATE:8>20240101 <TIME_ON:4>1200 <EOR>"
        qsos, errors = parse_adif(adif)
        self.assertEqual(len(qsos), 1)


class TestCabrillo(unittest.TestCase):

    SAMPLE_CAB = """START-OF-LOG: 3.0
CALLSIGN: YO8RJU
CONTEST: MARATON ION CREANGA
QSO: 7043 SSB 2024-03-15 1430 YO8RJU 59 NT YO4BXX 59 IS
QSO: 14200 SSB 2024-03-15 1445 YO8RJU 59 NT YO2BBB 59 TM
QSO: 3720 CW 2024-03-15 1500 YO8RJU 599 NT DL1ABC 599 0
END-OF-LOG:
"""
    def test_header(self):
        qsos, errors, header = parse_cabrillo(self.SAMPLE_CAB)
        self.assertEqual(header.get("CALLSIGN"), "YO8RJU")

    def test_qso_count(self):
        qsos, errors, header = parse_cabrillo(self.SAMPLE_CAB)
        self.assertEqual(len(qsos), 3)

    def test_qso_fields(self):
        qsos, errors, header = parse_cabrillo(self.SAMPLE_CAB)
        self.assertEqual(qsos[0]["callsign"], "YO4BXX")
        self.assertEqual(qsos[0]["mode"],     "SSB")
        self.assertEqual(qsos[0]["rst_s"],    "59")
        self.assertEqual(qsos[0]["exchange"], "NT")
        self.assertEqual(qsos[0]["date"],     "2024-03-15")
        self.assertEqual(qsos[0]["time"],     "14:30")

    def test_band_detection(self):
        qsos, errors, header = parse_cabrillo(self.SAMPLE_CAB)
        self.assertEqual(qsos[0]["band"], "40m")
        self.assertEqual(qsos[1]["band"], "20m")
        self.assertEqual(qsos[2]["band"], "80m")


class TestCSV(unittest.TestCase):

    SAMPLE_CSV = """callsign,band,mode,date,time,rst_s,rst_r,exchange
YO8RJU,40m,SSB,2024-03-15,14:30,59,59,NT
LZ1AB,20m,CW,2024-03-15,15:00,599,599,
"""
    def test_basic(self):
        qsos, errors = parse_csv(self.SAMPLE_CSV)
        self.assertEqual(len(qsos), 2)
        self.assertEqual(qsos[0]["callsign"], "YO8RJU")
        self.assertEqual(qsos[0]["band"],     "40m")

    def test_semicolon_sep(self):
        csv_semi = "callsign;band;mode\nYO8RJU;40m;SSB\n"
        qsos, errors = parse_csv(csv_semi)
        self.assertEqual(len(qsos), 1)

    def test_date_formats(self):
        csv_txt = "callsign,band,mode,date,time\nYO1AB,80m,SSB,20240315,1430\n"
        qsos, errors = parse_csv(csv_txt)
        self.assertEqual(qsos[0]["date"], "2024-03-15")
        self.assertEqual(qsos[0]["time"], "14:30")


class TestJSON(unittest.TestCase):

    SAMPLE_JSON = """[
  {"call": "YO8RJU", "band": "40m", "mode": "SSB",
   "date": "2024-03-15", "time": "14:30",
   "rst_s": "59", "rst_r": "59", "exchange": "NT"},
  {"call": "LZ1AB", "band": "20m", "mode": "CW",
   "date": "2024-03-15", "time": "15:00",
   "rst_s": "599", "rst_r": "599"}
]"""
    def test_basic(self):
        qsos, errors = parse_json(self.SAMPLE_JSON)
        self.assertEqual(len(qsos), 2)
        self.assertEqual(qsos[0]["callsign"], "YO8RJU")

    def test_dict_wrapper(self):
        js = '{"log": [{"call": "YO1AB", "band": "80m", "mode": "SSB", "date": "2024-03-15", "time": "10:00"}]}'
        qsos, errors = parse_json(js)
        self.assertEqual(len(qsos), 1)

    def test_invalid_json(self):
        qsos, errors = parse_json("{invalid}")
        self.assertEqual(len(qsos), 0)
        self.assertTrue(any(e["type"] == "JSON_PARSE_ERR" for e in errors))


# ═══════════════════════════════════════════════════════════════════
#  VALIDATOR TESTS
# ═══════════════════════════════════════════════════════════════════
class TestValidator(unittest.TestCase):

    def _make_qso(self, **kwargs):
        base = {
            "callsign": "YO8RJU", "band": "40m", "mode": "SSB",
            "date": "2024-03-15", "time": "14:30",
            "rst_s": "59", "rst_r": "59", "exchange": "NT",
            "freq": "7043", "note": "", "dxcc": "", "serial": "",
            "locator": "", "_source_line": 1, "_raw": ""
        }
        base.update(kwargs)
        return base

    def test_valid_qso(self):
        vr = validate_log([self._make_qso()])
        self.assertEqual(vr["error_count"], 0)
        self.assertEqual(vr["warning_count"], 0)

    def test_bad_callsign(self):
        vr = validate_log([self._make_qso(callsign="INVALID$$")])
        self.assertTrue(any(e.err_type == "BAD_CALL" for e in vr["errors"]))

    def test_bad_rst_ssb(self):
        vr = validate_log([self._make_qso(rst_s="599", mode="SSB")])
        self.assertTrue(any(e.err_type == "BAD_RST" for e in vr["errors"]))

    def test_good_rst_cw(self):
        vr = validate_log([self._make_qso(rst_s="599", rst_r="599", mode="CW")])
        self.assertEqual(vr["warning_count"], 0)

    def test_bad_date(self):
        vr = validate_log([self._make_qso(date="1990-01-01")])
        self.assertTrue(any(e.err_type == "BAD_DATE" for e in vr["errors"]))

    def test_bad_time(self):
        vr = validate_log([self._make_qso(time="99:99")])
        self.assertTrue(any(e.err_type == "BAD_TIME" for e in vr["errors"]))

    def test_duplicate(self):
        q1 = self._make_qso(callsign="LZ1AB")
        q2 = self._make_qso(callsign="LZ1AB")
        vr = validate_log([q1, q2])
        self.assertIn("duplicate_groups", vr)
        self.assertTrue(len(vr["duplicate_groups"]) > 0)

    def test_invalid_county(self):
        vr = validate_log([self._make_qso(exchange="XX")], contest_id="maraton")
        self.assertTrue(any(e.err_type == "BAD_COUNTY" for e in vr["errors"]))


# ═══════════════════════════════════════════════════════════════════
#  CROSS-CHECK TESTS
# ═══════════════════════════════════════════════════════════════════
class TestCrossCheck(unittest.TestCase):

    def _q(self, call, band, date="2024-03-15", time="14:30"):
        return {
            "callsign": call, "band": band, "mode": "SSB",
            "date": date, "time": time,
            "rst_s": "59", "rst_r": "59", "exchange": "NT",
            "freq": "", "note": "", "dxcc": "", "serial": "",
            "locator": "", "_source_line": 1, "_raw": ""
        }

    def test_confirmed(self):
        # A a lucrat B; B a lucrat A — confirmare
        log_a = [self._q("YO8RJU", "40m")]  # A i-a lucrat pe YO8RJU (dar YO8RJU e A, nu B)
        # log_a are callsign=YO8RJU (cel pe care A l-a lucrat)
        # Reformulat corect: A=YO8ACR a lucrat pe YO8RJU
        log_a = [{"callsign": "YO8RJU", "band": "40m", "mode": "SSB",
                  "date": "2024-03-15", "time": "14:30",
                  "rst_s":"59","rst_r":"59","exchange":"NT",
                  "freq":"","note":"","dxcc":"","serial":"","locator":"",
                  "_source_line":1,"_raw":""}]
        log_b = [{"callsign": "YO8ACR", "band": "40m", "mode": "SSB",
                  "date": "2024-03-15", "time": "14:31",
                  "rst_s":"59","rst_r":"59","exchange":"BC",
                  "freq":"","note":"","dxcc":"","serial":"","locator":"",
                  "_source_line":1,"_raw":""}]
        result = cross_check(log_a, log_b, "YO8ACR", "YO8RJU", tolerance_min=3)
        self.assertEqual(len(result["confirmed"]), 1)
        self.assertEqual(len(result["unconfirmed"]), 0)

    def test_time_out_of_window(self):
        log_a = [{"callsign": "YO8RJU", "band": "40m", "mode": "SSB",
                  "date": "2024-03-15", "time": "14:30",
                  "rst_s":"59","rst_r":"59","exchange":"NT",
                  "freq":"","note":"","dxcc":"","serial":"","locator":"",
                  "_source_line":1,"_raw":""}]
        log_b = [{"callsign": "YO8ACR", "band": "40m", "mode": "SSB",
                  "date": "2024-03-15", "time": "14:40",  # 10 min diferență
                  "rst_s":"59","rst_r":"59","exchange":"BC",
                  "freq":"","note":"","dxcc":"","serial":"","locator":"",
                  "_source_line":1,"_raw":""}]
        result = cross_check(log_a, log_b, "YO8ACR", "YO8RJU", tolerance_min=3)
        self.assertEqual(len(result["confirmed"]), 0)

    def test_unconfirmed(self):
        log_a = [{"callsign": "YO8RJU", "band": "40m", "mode": "SSB",
                  "date": "2024-03-15", "time": "14:30",
                  "rst_s":"59","rst_r":"59","exchange":"NT",
                  "freq":"","note":"","dxcc":"","serial":"","locator":"",
                  "_source_line":1,"_raw":""}]
        log_b = []  # B nu are niciun QSO
        result = cross_check(log_a, log_b, "YO8ACR", "YO8RJU", tolerance_min=3)
        self.assertEqual(len(result["unconfirmed"]), 1)


# ═══════════════════════════════════════════════════════════════════
#  SCORER TESTS
# ═══════════════════════════════════════════════════════════════════
class TestScorer(unittest.TestCase):

    def _make_qsos(self):
        base = {
            "mode": "SSB", "date": "2024-03-15", "time": "14:30",
            "rst_s": "59", "rst_r": "59", "freq": "7043",
            "note": "", "dxcc": "", "serial": "", "locator": "",
            "_source_line": 1, "_raw": ""
        }
        return [
            {**base, "callsign": "YO4BXX", "band": "40m", "exchange": "IS"},
            {**base, "callsign": "YO2BBB", "band": "80m", "exchange": "TM"},
            {**base, "callsign": "LZ1AB",  "band": "20m", "exchange": ""},
        ]

    def test_per_qso_scoring(self):
        qsos = self._make_qsos()
        sr = score_log(qsos, "stafeta", "YO8RJU")
        self.assertEqual(sr["valid_qsos"], 3)
        self.assertEqual(sr["qso_points"], 6)   # 3 × 2 pct

    def test_ranking(self):
        qsos = self._make_qsos()
        sr1 = score_log(qsos, "stafeta", "YO8RJU")
        sr2 = score_log(qsos[:2], "stafeta", "YO4BXX")
        ranking = build_ranking([sr1, sr2])
        self.assertEqual(ranking[0]["callsign"], "YO8RJU")
        self.assertEqual(ranking[0]["position"], 1)

    def test_duplicate_not_scored(self):
        qsos = self._make_qsos()
        qsos.append({**qsos[0], "callsign": "YO4BXX"})  # duplicat
        flags = {0: "ok", 1: "ok", 2: "ok", 3: "duplicate"}
        sr = score_log(qsos, "stafeta", "YO8RJU", qso_flags=flags)
        self.assertEqual(sr["duplicate_qsos"], 1)
        self.assertEqual(sr["valid_qsos"], 3)


# ═══════════════════════════════════════════════════════════════════
#  UTILITY TESTS
# ═══════════════════════════════════════════════════════════════════
class TestUtils(unittest.TestCase):

    def test_freq_to_band(self):
        self.assertEqual(freq_to_band(7043), "40m")
        self.assertEqual(freq_to_band(14200), "20m")
        self.assertEqual(freq_to_band(3725), "80m")
        self.assertIsNone(freq_to_band(9999))

    def test_guess_dxcc(self):
        self.assertEqual(guess_dxcc("YO8RJU"), "Romania")
        self.assertEqual(guess_dxcc("DL1ABC"), "Germany")
        self.assertEqual(guess_dxcc("G3ABC"),  "England")

    def test_is_valid_county(self):
        self.assertTrue(is_valid_county("NT"))
        self.assertTrue(is_valid_county("B"))
        self.assertFalse(is_valid_county("XX"))
        self.assertFalse(is_valid_county("ZZ"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
