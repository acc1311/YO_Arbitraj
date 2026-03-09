#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Reporter
Generează rapoarte de arbitraj în formate: CSV, HTML, TXT.
(PDF prin HTML → wkhtmltopdf sau webbrowser print, opțional)
"""

import csv
import io
import os
import datetime
import json
from core.contests import CONTESTS

_NOW = lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


# ═══════════════════════════════════════════════════════════════════
#  CSV EXPORT
# ═══════════════════════════════════════════════════════════════════
def export_csv(score_result, validation_result, filepath):
    """Exportă raportul complet în CSV."""
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")

        # Header general
        w.writerow(["YO ARBITRAJ — Raport", _NOW()])
        w.writerow([])
        w.writerow(["Concurs",    score_result.get("contest_name", "")])
        w.writerow(["Indicativ",  score_result.get("callsign", "")])
        w.writerow(["Total QSO",  score_result.get("total_qsos", 0)])
        w.writerow(["QSO valide", score_result.get("valid_qsos", 0)])
        w.writerow(["Erori",      score_result.get("error_qsos", 0)])
        w.writerow(["Duplicate",  score_result.get("duplicate_qsos", 0)])
        w.writerow(["Puncte QSO", score_result.get("qso_points", 0)])
        w.writerow(["Multiplicatori", score_result.get("multipliers", 0)])
        w.writerow(["SCOR FINAL", score_result.get("total_score", 0)])
        w.writerow([])

        # Tabel QSO-uri
        w.writerow(["#", "Indicativ", "Bandă", "Mod", "Data", "Ora",
                    "RST S", "RST R", "Schimb", "Puncte", "Status"])
        for b in score_result.get("breakdown", []):
            w.writerow([
                b["idx"]+1, b["callsign"], b["band"], b["mode"],
                b["date"], b["time"], b["rst_s"], b["rst_r"],
                b["exchange"], b["points"], b["status"]
            ])
        w.writerow([])

        # Erori validare
        if validation_result:
            w.writerow(["ERORI VALIDARE"])
            w.writerow(["#QSO", "Indicativ", "Tip", "Mesaj", "Severitate"])
            for e in validation_result.get("errors", []):
                if hasattr(e, "to_dict"):
                    d = e.to_dict()
                else:
                    d = e
                w.writerow([d["qso_idx"]+1, d["callsign"], d["type"],
                             d["message"], d["severity"]])

    return filepath


# ═══════════════════════════════════════════════════════════════════
#  HTML EXPORT
# ═══════════════════════════════════════════════════════════════════
_STATUS_COLORS = {
    "ok":          "#d4edda",
    "warning":     "#fff3cd",
    "error":       "#f8d7da",
    "duplicate":   "#fce4ec",
    "unconfirmed": "#e0e0e0",
}
_STATUS_LABELS = {
    "ok":          "✅ OK",
    "warning":     "⚠️ Avertisment",
    "error":       "❌ Eroare",
    "duplicate":   "🔁 Duplicat",
    "unconfirmed": "❓ Neconfirmat",
}

def export_html(score_result, validation_result, filepath,
                cross_check_result=None, ranking=None):
    """Exportă raportul complet în HTML (print-ready)."""

    call    = score_result.get("callsign", "—")
    contest = score_result.get("contest_name", "—")
    now_str = _NOW()

    # ── Per-bandă tabel ──
    per_band_rows = ""
    for band, bd in sorted(score_result.get("per_band", {}).items()):
        per_band_rows += f"""
        <tr>
          <td>{band}</td>
          <td>{bd['qsos']}</td>
          <td>{bd['points']}</td>
        </tr>"""

    # ── QSO breakdown ──
    qso_rows = ""
    for b in score_result.get("breakdown", []):
        bg  = _STATUS_COLORS.get(b["status"], "#fff")
        lbl = _STATUS_LABELS.get(b["status"], b["status"])
        qso_rows += f"""
        <tr style="background:{bg}">
          <td>{b['idx']+1}</td>
          <td><b>{b['callsign']}</b></td>
          <td>{b['band']}</td>
          <td>{b['mode']}</td>
          <td>{b['date']}</td>
          <td>{b['time']}</td>
          <td>{b['rst_s']}</td>
          <td>{b['rst_r']}</td>
          <td>{b['exchange']}</td>
          <td><b>{b['points']}</b></td>
          <td>{lbl}</td>
        </tr>"""

    # ── Erori validare ──
    err_rows = ""
    if validation_result:
        for e in validation_result.get("errors", []):
            d = e.to_dict() if hasattr(e, "to_dict") else e
            sev_color = {"ERROR": "#f8d7da", "WARNING": "#fff3cd", "INFO": "#d1ecf1"}.get(d["severity"], "#fff")
            err_rows += f"""
            <tr style="background:{sev_color}">
              <td>{d['qso_idx']+1}</td>
              <td>{d['callsign']}</td>
              <td>{d['type']}</td>
              <td>{d['message']}</td>
              <td>{d['severity']}</td>
              <td>{d.get('field','')}</td>
            </tr>"""

    # ── Cross-check ──
    cc_section = ""
    if cross_check_result:
        st = cross_check_result.get("stats", {})
        cc_section = f"""
        <h2>Cross-Check</h2>
        <table>
          <tr><th>Total A</th><th>Confirmate</th><th>Neconfirmate</th>
              <th>Indicativ greșit</th><th>Bandă greșită</th><th>Timp greșit</th></tr>
          <tr>
            <td>{st.get('total_a',0)}</td>
            <td style="color:green"><b>{st.get('confirmed',0)}</b></td>
            <td style="color:red">{st.get('unconfirmed',0)}</td>
            <td style="color:orange">{st.get('busted_call',0)}</td>
            <td style="color:orange">{st.get('busted_band',0)}</td>
            <td style="color:orange">{st.get('busted_time',0)}</td>
          </tr>
        </table>"""

    # ── Clasament ──
    rank_section = ""
    if ranking:
        rank_rows = "".join(f"""
            <tr>
              <td><b>#{r['position']}</b></td>
              <td><b>{r['callsign']}</b></td>
              <td>{r['valid_qsos']}</td>
              <td>{r['qso_points']}</td>
              <td>{r['multipliers']}</td>
              <td style="font-size:1.1em;color:#1a3a5c"><b>{r['total_score']}</b></td>
            </tr>""" for r in ranking)
        rank_section = f"""
        <h2>Clasament Final</h2>
        <table>
          <tr><th>#</th><th>Indicativ</th><th>QSO Valide</th>
              <th>Puncte QSO</th><th>Multiplicatori</th><th>SCOR</th></tr>
          {rank_rows}
        </table>"""

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<title>YO Arbitraj — Raport {call}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 13px; margin: 20px; color: #1a1a1a; }}
  h1 {{ background: #1a3a5c; color: white; padding: 10px 16px; border-radius: 4px; }}
  h2 {{ color: #2e75b6; border-bottom: 2px solid #2e75b6; padding-bottom: 4px; margin-top: 28px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th {{ background: #1a3a5c; color: white; padding: 7px 10px; text-align: left; font-size: 12px; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid #ddd; }}
  tr:hover {{ filter: brightness(0.95); }}
  .summary-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }}
  .summary-box {{ background: #f2f5f8; border-left: 4px solid #2e75b6; padding: 10px 18px;
                  border-radius: 4px; min-width: 150px; }}
  .summary-box .val {{ font-size: 1.8em; font-weight: bold; color: #1a3a5c; }}
  .summary-box .lbl {{ font-size: 0.85em; color: #555; }}
  .score-final {{ background: #1a3a5c; color: white; font-size: 1.4em;
                  padding: 12px 20px; border-radius: 6px; display: inline-block; margin: 8px 0; }}
  @media print {{
    .no-print {{ display: none; }}
    h1 {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    th {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>

<h1>🏆 YO Arbitraj — Raport de Arbitraj</h1>
<p>Generat: {now_str} | Concurs: <b>{contest}</b> | Indicativ: <b>{call}</b></p>

<h2>Sumar</h2>
<div class="summary-grid">
  <div class="summary-box"><div class="val">{score_result.get('total_qsos',0)}</div><div class="lbl">Total QSO</div></div>
  <div class="summary-box"><div class="val" style="color:green">{score_result.get('valid_qsos',0)}</div><div class="lbl">QSO Valide</div></div>
  <div class="summary-box"><div class="val" style="color:red">{score_result.get('error_qsos',0)}</div><div class="lbl">Erori</div></div>
  <div class="summary-box"><div class="val" style="color:#e65100">{score_result.get('duplicate_qsos',0)}</div><div class="lbl">Duplicate</div></div>
  <div class="summary-box"><div class="val">{score_result.get('qso_points',0)}</div><div class="lbl">Puncte QSO</div></div>
  <div class="summary-box"><div class="val">{score_result.get('multipliers',0)}</div><div class="lbl">Multiplicatori</div></div>
</div>
<div class="score-final">SCOR FINAL: {score_result.get('total_score',0)}</div>

<h2>Per Bandă</h2>
<table>
  <tr><th>Bandă</th><th>QSO</th><th>Puncte</th></tr>
  {per_band_rows}
</table>

<h2>Log QSO-uri ({len(score_result.get('breakdown',[]))} înregistrări)</h2>
<table>
  <tr><th>#</th><th>Indicativ</th><th>Bandă</th><th>Mod</th><th>Data</th><th>Ora</th>
      <th>RST S</th><th>RST R</th><th>Schimb</th><th>Puncte</th><th>Status</th></tr>
  {qso_rows}
</table>

<h2>Erori Validare ({len(validation_result.get('errors', [])) if validation_result else 0})</h2>
<table>
  <tr><th>#QSO</th><th>Indicativ</th><th>Tip</th><th>Mesaj</th><th>Severitate</th><th>Câmp</th></tr>
  {err_rows if err_rows else '<tr><td colspan="6" style="color:green">✅ Nicio eroare</td></tr>'}
</table>

{cc_section}
{rank_section}

<hr>
<p style="color:#888;font-size:11px">YO Arbitraj v1.0 — Developed by YO8ACR | yo8acr@gmail.com</p>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filepath


# ═══════════════════════════════════════════════════════════════════
#  TXT EXPORT (simplu, print-friendly)
# ═══════════════════════════════════════════════════════════════════
def export_txt(score_result, validation_result, filepath):
    lines = []
    SEP = "=" * 70
    sep = "-" * 70

    lines += [SEP, "  YO ARBITRAJ — RAPORT DE ARBITRAJ", SEP]
    lines += ["  Generat:   {}".format(_NOW())]
    lines += ["  Concurs:   {}".format(score_result.get("contest_name", "-"))]
    lines += ["  Indicativ: {}".format(score_result.get("callsign", "-"))]
    lines += [sep]
    lines += ["  Total QSO:        {}".format(score_result.get("total_qsos", 0))]
    lines += ["  QSO Valide:       {}".format(score_result.get("valid_qsos", 0))]
    lines += ["  Erori:            {}".format(score_result.get("error_qsos", 0))]
    lines += ["  Duplicate:        {}".format(score_result.get("duplicate_qsos", 0))]
    lines += ["  Puncte QSO:       {}".format(score_result.get("qso_points", 0))]
    lines += ["  Multiplicatori:   {}".format(score_result.get("multipliers", 0))]
    lines += ["  SCOR FINAL:       {}".format(score_result.get("total_score", 0))]
    lines += [SEP, ""]

    # Per bandă
    lines += ["PER BANDĂ:", sep]
    lines += ["  {:<8} {:>6} {:>8}".format("Banda", "QSO", "Puncte")]
    lines += [sep]
    for band, bd in sorted(score_result.get("per_band", {}).items()):
        lines += ["  {:<8} {:>6} {:>8}".format(band, bd['qsos'], bd['points'])]
    lines += [""]

    # Erori
    errs = validation_result.get("errors", []) if validation_result else []
    if errs:
        lines += ["ERORI VALIDARE:", sep]
        for e in errs:
            d = e.to_dict() if hasattr(e, "to_dict") else e
            lines += ["  [{:7}] QSO#{:4d} {:<12} {:<20} {}".format(d['severity'], d['qso_idx']+1, d['callsign'], d['type'], d['message'])]
        lines += [""]

    lines += [SEP, "  YO Arbitraj v1.0 — YO8ACR | yo8acr@gmail.com", SEP]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return filepath


def export_json(score_result, validation_result, filepath):
    """Exportă datele complete în JSON pentru procesare ulterioară."""
    out = {
        "generated": _NOW(),
        "score":     score_result,
        "validation": {
            "errors": [
                (e.to_dict() if hasattr(e, "to_dict") else e)
                for e in (validation_result.get("errors", []) if validation_result else [])
            ]
        }
    }
    # Convertim seturile în liste (JSON serializabil)
    if "multiplier_set" in out["score"]:
        out["score"]["multiplier_set"] = list(out["score"]["multiplier_set"])

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    return filepath
