#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj — Main Window
Fereastra principală a aplicației de arbitraj.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from core.contests import list_contests, CONTESTS
from core.parser   import parse_file
from core.validator import validate_log
from core.crosscheck import cross_check
from core.scorer    import score_log, build_ranking
from export.reporter import export_csv, export_html, export_txt, export_json

# ── Culori temă ──────────────────────────────────────────────────
BG       = "#1e2a38"
BG2      = "#253447"
BG3      = "#2e3f55"
FG       = "#e8edf3"
ACCENT   = "#2e75b6"
ACCENT2  = "#4a9de0"
GREEN    = "#2ecc71"
RED      = "#e74c3c"
ORANGE   = "#f39c12"
YELLOW   = "#f1c40f"
GRAY     = "#7f8c8d"
WHITE    = "#ffffff"
FONT     = ("Consolas", 10)
FONT_B   = ("Consolas", 10, "bold")
FONT_H   = ("Arial", 11, "bold")
FONT_T   = ("Arial", 14, "bold")

STATUS_COLORS = {
    "ok":          GREEN,
    "warning":     YELLOW,
    "error":       RED,
    "duplicate":   ORANGE,
    "unconfirmed": GRAY,
}

class YOArbitrajApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YO Arbitraj v1.0 — Arbitraj Concursuri Radioamatori")
        self.configure(bg=BG)
        self.resizable(True, True)

        # Stare internă
        self.loaded_logs   = {}   # {callsign: parse_result}
        self.score_results = {}
        self.val_results   = {}
        self.cc_result     = None
        self.ranking       = []
        self.contest_id    = tk.StringVar(value="maraton")
        self.tolerance_var = tk.IntVar(value=3)

        self._setup_geometry()
        self._build_ui()
        self._apply_style()

    def _setup_geometry(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = min(1360, int(sw * 0.94))
        h  = min(860,  int(sh * 0.90))
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        self.geometry("{}x{}+{}+{}".format(w, h, x, y))
        self.minsize(960, 600)

    # ── ttk Style ────────────────────────────────────────────────
    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".",             background=BG,  foreground=FG,
                         font=FONT,      fieldbackground=BG2)
        style.configure("TFrame",        background=BG)
        style.configure("TLabel",        background=BG,  foreground=FG,  font=FONT)
        style.configure("TLabelframe",   background=BG,  foreground=ACCENT2)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT2, font=FONT_H)
        style.configure("TButton",       background=ACCENT, foreground=WHITE,
                         font=FONT_B,   relief="flat", padding=(8,4))
        style.map("TButton",
                  background=[("active", ACCENT2), ("pressed", BG3)],
                  foreground=[("active", WHITE)])
        style.configure("Green.TButton", background=GREEN,  foreground=BG)
        style.configure("Red.TButton",   background=RED,    foreground=WHITE)
        style.configure("TCombobox",     background=BG2, foreground=FG,
                         fieldbackground=BG2, selectbackground=ACCENT)
        style.configure("TSpinbox",      background=BG2, foreground=FG,
                         fieldbackground=BG2)
        style.configure("TNotebook",     background=BG)
        style.configure("TNotebook.Tab", background=BG3, foreground=FG,
                         padding=(12, 5), font=FONT_B)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT), ("active", BG2)],
                  foreground=[("selected", WHITE)])
        # Treeview
        style.configure("Treeview",      background=BG2, foreground=FG,
                         fieldbackground=BG2, font=FONT,
                         rowheight=22)
        style.configure("Treeview.Heading", background=BG3, foreground=ACCENT2,
                         font=FONT_B)
        style.map("Treeview", background=[("selected", ACCENT)])

        # Tag-uri treeview
        for tag, color in STATUS_COLORS.items():
            self.option_add("*Treeview.{}.background".format(tag), color)

    # ════════════════════════════════════════════════════════════
    #  BUILD UI
    # ════════════════════════════════════════════════════════════
    def _build_ui(self):
        # ── Top bar ──
        top = tk.Frame(self, bg=ACCENT, height=48)
        top.pack(fill=tk.X, side=tk.TOP)
        tk.Label(top, text="🏆 YO ARBITRAJ v1.0",
                 font=("Arial", 14, "bold"), bg=ACCENT, fg=WHITE,
                 padx=16).pack(side=tk.LEFT, pady=8)
        tk.Label(top, text="Arbitraj profesional pentru concursuri de radioamatori YO",
                 font=("Arial", 9), bg=ACCENT, fg="#dce8f5").pack(side=tk.LEFT, pady=8)

        # ── Status bar ──
        self.status_var = tk.StringVar(value="Gata. Importați unul sau mai multe log-uri pentru arbitraj.")
        sb = tk.Label(self, textvariable=self.status_var,
                      bg=BG3, fg=ACCENT2, font=("Consolas", 9),
                      anchor="w", padx=10)
        sb.pack(side=tk.BOTTOM, fill=tk.X)

        # ── Main paned ──
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # LEFT panel
        left = ttk.Frame(paned, width=300)
        paned.add(left, weight=0)
        self._build_left(left)

        # RIGHT notebook
        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        self._build_right(right)

    # ── LEFT panel ──────────────────────────────────────────────
    def _build_left(self, parent):
        # Concurs
        cf = ttk.LabelFrame(parent, text="⚙ Configurare")
        cf.pack(fill=tk.X, padx=6, pady=4)

        ttk.Label(cf, text="Concurs:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        contests = [v["name"] for k,v in CONTESTS.items()]
        self.contest_combo = ttk.Combobox(cf, values=contests, state="readonly", width=22)
        self.contest_combo.set(CONTESTS["maraton"]["name"])
        self.contest_combo.grid(row=0, column=1, padx=6, pady=3, sticky="ew")
        self.contest_combo.bind("<<ComboboxSelected>>", self._on_contest_change)

        ttk.Label(cf, text="Toleranță ±min:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Spinbox(cf, from_=1, to=10, textvariable=self.tolerance_var,
                    width=5).grid(row=1, column=1, sticky="w", padx=6)

        # Log-uri încărcate
        lf = ttk.LabelFrame(parent, text="📂 Log-uri Importate")
        lf.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        cols = ("callsign", "qsos", "format", "status")
        self.log_tree = ttk.Treeview(lf, columns=cols, show="headings", height=8)
        self.log_tree.heading("callsign", text="Indicativ")
        self.log_tree.heading("qsos",     text="QSO")
        self.log_tree.heading("format",   text="Format")
        self.log_tree.heading("status",   text="Status")
        self.log_tree.column("callsign", width=90)
        self.log_tree.column("qsos",     width=50, anchor="center")
        self.log_tree.column("format",   width=60, anchor="center")
        self.log_tree.column("status",   width=70, anchor="center")
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=vsb.set)
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_tree.bind("<<TreeviewSelect>>", self._on_log_select)

        # Butoane import
        bf = ttk.Frame(parent)
        bf.pack(fill=tk.X, padx=6, pady=2)

        ttk.Button(bf, text="📂 Import Log",
                   command=self._import_log).pack(fill=tk.X, pady=2)
        ttk.Button(bf, text="🗑 Șterge Selectat",
                   command=self._remove_log, style="Red.TButton").pack(fill=tk.X, pady=2)
        ttk.Button(bf, text="🗑 Șterge Toate",
                   command=self._remove_all).pack(fill=tk.X, pady=2)

        ttk.Separator(parent, orient="horizontal").pack(fill=tk.X, padx=6, pady=4)

        # Butoane arbitraj
        af = ttk.LabelFrame(parent, text="▶ Acțiuni Arbitraj")
        af.pack(fill=tk.X, padx=6, pady=4)

        ttk.Button(af, text="✔ Validează Log-uri",
                   command=self._run_validation).pack(fill=tk.X, pady=2, padx=4)
        ttk.Button(af, text="🔀 Cross-Check (2 log-uri)",
                   command=self._run_crosscheck).pack(fill=tk.X, pady=2, padx=4)
        ttk.Button(af, text="📊 Calculează Scor",
                   command=self._run_scoring).pack(fill=tk.X, pady=2, padx=4)
        ttk.Button(af, text="🏁 Arbitraj Complet",
                   command=self._run_all, style="Green.TButton").pack(fill=tk.X, pady=4, padx=4)

        # Export
        ef = ttk.LabelFrame(parent, text="📤 Export Raport")
        ef.pack(fill=tk.X, padx=6, pady=4)

        row = ttk.Frame(ef)
        row.pack(fill=tk.X, padx=4, pady=2)
        ttk.Button(row, text="HTML", command=lambda: self._export("html"), width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="CSV",  command=lambda: self._export("csv"),  width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="TXT",  command=lambda: self._export("txt"),  width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="JSON", command=lambda: self._export("json"), width=8).pack(side=tk.LEFT, padx=2)

    # ── RIGHT notebook ───────────────────────────────────────────
    def _build_right(self, parent):
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Log Viewer
        self.tab_log = ttk.Frame(self.nb)
        self.nb.add(self.tab_log, text="📋 Log QSO-uri")
        self._build_log_tab(self.tab_log)

        # Tab 2: Validare
        self.tab_val = ttk.Frame(self.nb)
        self.nb.add(self.tab_val, text="✔ Validare")
        self._build_val_tab(self.tab_val)

        # Tab 3: Cross-Check
        self.tab_cc = ttk.Frame(self.nb)
        self.nb.add(self.tab_cc, text="🔀 Cross-Check")
        self._build_cc_tab(self.tab_cc)

        # Tab 4: Scor
        self.tab_score = ttk.Frame(self.nb)
        self.nb.add(self.tab_score, text="📊 Scor & Clasament")
        self._build_score_tab(self.tab_score)

    # ── Tab Log ──────────────────────────────────────────────────
    def _build_log_tab(self, parent):
        # Filtru
        ff = ttk.Frame(parent)
        ff.pack(fill=tk.X, padx=6, pady=4)
        ttk.Label(ff, text="Log:").pack(side=tk.LEFT)
        self.log_sel_var = tk.StringVar()
        self.log_sel_cb = ttk.Combobox(ff, textvariable=self.log_sel_var,
                                        state="readonly", width=14)
        self.log_sel_cb.pack(side=tk.LEFT, padx=4)
        self.log_sel_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_log_tab())

        ttk.Label(ff, text="Bandă:").pack(side=tk.LEFT, padx=(12,0))
        self.band_filter = ttk.Combobox(ff, values=["Toate"], state="readonly", width=7)
        self.band_filter.set("Toate")
        self.band_filter.pack(side=tk.LEFT, padx=4)
        self.band_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_log_tab())

        ttk.Label(ff, text="Status:").pack(side=tk.LEFT, padx=(8,0))
        self.stat_filter = ttk.Combobox(ff, values=["Toate","ok","warning","error","duplicate"],
                                          state="readonly", width=10)
        self.stat_filter.set("Toate")
        self.stat_filter.pack(side=tk.LEFT, padx=4)
        self.stat_filter.bind("<<ComboboxSelected>>", lambda e: self._refresh_log_tab())

        self.qso_count_lbl = ttk.Label(ff, text="")
        self.qso_count_lbl.pack(side=tk.RIGHT, padx=10)

        # Treeview QSO
        cols = ("#", "call", "band", "mode", "date", "time",
                "rst_s", "rst_r", "exchange", "points", "status")
        widths = (40, 100, 60, 55, 90, 60, 55, 55, 80, 55, 80)
        self.qso_tree = ttk.Treeview(parent, columns=cols, show="headings")
        headers = ("#","Indicativ","Bandă","Mod","Data","Ora","RST S","RST R","Schimb","Pct","Status")
        for col, hdr, w in zip(cols, headers, widths):
            self.qso_tree.heading(col, text=hdr,
                command=lambda c=col: self._sort_qso_tree(c))
            self.qso_tree.column(col, width=w, anchor="center" if w < 90 else "w")

        vsb = ttk.Scrollbar(parent, orient="vertical",   command=self.qso_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal",  command=self.qso_tree.xview)
        self.qso_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.qso_tree.pack(side=tk.TOP,    fill=tk.BOTH, expand=True, padx=4)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Culori tag-uri
        self.qso_tree.tag_configure("ok",        background="#1b3a2a", foreground=GREEN)
        self.qso_tree.tag_configure("warning",   background="#3a3000", foreground=YELLOW)
        self.qso_tree.tag_configure("error",     background="#3a1515", foreground=RED)
        self.qso_tree.tag_configure("duplicate", background="#3a2500", foreground=ORANGE)
        self.qso_tree.tag_configure("unconfirmed", background="#2a2a2a", foreground=GRAY)

    # ── Tab Validare ─────────────────────────────────────────────
    def _build_val_tab(self, parent):
        # Sumar
        self.val_summary = tk.Text(parent, height=6, bg=BG2, fg=FG,
                                    font=("Consolas", 10), state="disabled",
                                    relief="flat", padx=10, pady=6)
        self.val_summary.pack(fill=tk.X, padx=6, pady=4)

        ttk.Separator(parent).pack(fill=tk.X, padx=6)

        # Treeview erori
        cols = ("qso", "call", "type", "message", "severity", "field")
        self.val_tree = ttk.Treeview(parent, columns=cols, show="headings")
        widths = (50, 100, 150, 450, 80, 70)
        headers = ("#QSO", "Indicativ", "Tip Eroare", "Mesaj", "Severitate", "Câmp")
        for col, hdr, w in zip(cols, headers, widths):
            self.val_tree.heading(col, text=hdr)
            self.val_tree.column(col, width=w, anchor="w" if w > 80 else "center")

        vsb = ttk.Scrollbar(parent, orient="vertical",  command=self.val_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.val_tree.xview)
        self.val_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.val_tree.pack(fill=tk.BOTH, expand=True, padx=4)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.val_tree.tag_configure("ERROR",   background="#3a1515", foreground=RED)
        self.val_tree.tag_configure("WARNING", background="#3a3000", foreground=YELLOW)
        self.val_tree.tag_configure("INFO",    background="#1b2a3a", foreground=ACCENT2)

    # ── Tab Cross-Check ──────────────────────────────────────────
    def _build_cc_tab(self, parent):
        # Selector loguri A/B
        sf = ttk.Frame(parent)
        sf.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(sf, text="Log A (principal):").pack(side=tk.LEFT)
        self.cc_a = ttk.Combobox(sf, state="readonly", width=16)
        self.cc_a.pack(side=tk.LEFT, padx=4)
        ttk.Label(sf, text="Log B (confirmare):").pack(side=tk.LEFT, padx=(16,0))
        self.cc_b = ttk.Combobox(sf, state="readonly", width=16)
        self.cc_b.pack(side=tk.LEFT, padx=4)
        ttk.Button(sf, text="▶ Rulează Cross-Check",
                   command=self._run_crosscheck).pack(side=tk.LEFT, padx=16)

        # Sumar
        self.cc_summary = tk.Text(parent, height=5, bg=BG2, fg=FG,
                                   font=("Consolas", 10), state="disabled",
                                   relief="flat", padx=10, pady=6)
        self.cc_summary.pack(fill=tk.X, padx=6, pady=4)

        # Treeview rezultate
        cols = ("idx", "call_a", "band", "date", "time", "status", "issue")
        self.cc_tree = ttk.Treeview(parent, columns=cols, show="headings")
        widths = (50, 100, 60, 90, 60, 120, 400)
        headers = ("#", "Indicativ A", "Bandă", "Data", "Ora", "Status", "Detaliu")
        for col, hdr, w in zip(cols, headers, widths):
            self.cc_tree.heading(col, text=hdr)
            self.cc_tree.column(col, width=w, anchor="w" if w > 80 else "center")

        vsb = ttk.Scrollbar(parent, orient="vertical",  command=self.cc_tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.cc_tree.xview)
        self.cc_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.cc_tree.pack(fill=tk.BOTH, expand=True, padx=4)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        self.cc_tree.tag_configure("confirmed",   background="#1b3a2a", foreground=GREEN)
        self.cc_tree.tag_configure("unconfirmed", background="#3a1515", foreground=RED)
        self.cc_tree.tag_configure("busted_call", background="#3a2000", foreground=ORANGE)
        self.cc_tree.tag_configure("busted_band", background="#3a2000", foreground=ORANGE)
        self.cc_tree.tag_configure("busted_time", background="#3a2800", foreground=YELLOW)

    # ── Tab Scor ─────────────────────────────────────────────────
    def _build_score_tab(self, parent):
        # Sumar scor
        self.score_summary = tk.Text(parent, height=8, bg=BG2, fg=FG,
                                      font=("Consolas", 10), state="disabled",
                                      relief="flat", padx=10, pady=6)
        self.score_summary.pack(fill=tk.X, padx=6, pady=4)

        ttk.Separator(parent).pack(fill=tk.X, padx=6)
        ttk.Label(parent, text="Clasament:", font=FONT_H).pack(anchor="w", padx=8, pady=4)

        # Treeview clasament
        cols = ("pos", "call", "total", "valid", "errors", "dups", "pts", "mult", "score")
        self.rank_tree = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        widths = (40, 110, 70, 70, 60, 60, 70, 80, 100)
        headers = ("#", "Indicativ", "Total QSO", "Valide", "Erori", "Dup.", "Pct QSO", "Mult.", "SCOR")
        for col, hdr, w in zip(cols, headers, widths):
            self.rank_tree.heading(col, text=hdr)
            self.rank_tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.rank_tree.yview)
        self.rank_tree.configure(yscrollcommand=vsb.set)
        self.rank_tree.pack(fill=tk.BOTH, expand=True, padx=4)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.rank_tree.tag_configure("gold",   background="#3a3200", foreground=YELLOW)
        self.rank_tree.tag_configure("silver", background="#2a2a2a", foreground="#c0c0c0")
        self.rank_tree.tag_configure("bronze", background="#2a1a00", foreground="#cd7f32")

    # ════════════════════════════════════════════════════════════
    #  ACTIONS
    # ════════════════════════════════════════════════════════════
    def _set_status(self, msg, color=None):
        self.status_var.set(msg)
        if color:
            for w in self.winfo_children():
                if isinstance(w, tk.Label) and w.cget("textvariable") == str(self.status_var):
                    w.configure(fg=color)

    def _on_contest_change(self, event=None):
        name = self.contest_combo.get()
        for k, v in CONTESTS.items():
            if v["name"] == name:
                self.contest_id.set(k)
                break

    def _on_log_select(self, event=None):
        sel = self.log_tree.selection()
        if sel:
            call = self.log_tree.item(sel[0])["values"][0]
            self.log_sel_var.set(call)
            self._refresh_log_tab()

    def _import_log(self):
        files = filedialog.askopenfilenames(
            title="Selectați log-uri pentru import",
            filetypes=[
                ("Toate log-urile", "*.adi *.adif *.log *.csv *.json"),
                ("ADIF",      "*.adi *.adif"),
                ("Cabrillo",  "*.log"),
                ("CSV",       "*.csv"),
                ("JSON",      "*.json"),
                ("Toate",     "*.*"),
            ]
        )
        for fp in files:
            self._set_status("Se importa: {}...".format(os.path.basename(fp)))
            self.update_idletasks()
            try:
                result = parse_file(fp)
                call   = result["callsign"] or os.path.splitext(os.path.basename(fp))[0].upper()
                if call in self.loaded_logs:
                    if not messagebox.askyesno("Duplicat",
                            "Log-ul {} exista deja. Il inlocuiti?".format(call)):
                        continue
                self.loaded_logs[call] = result
                errs = len(result["errors"])
                status = "⚠️ erori" if errs else "✅ OK"
                # Update log tree
                for item in self.log_tree.get_children():
                    if self.log_tree.item(item)["values"][0] == call:
                        self.log_tree.delete(item)
                self.log_tree.insert("", "end", values=(
                    call, result["total"], result["format"].upper(), status
                ))
                self._set_status(
                    "OK {}: {} QSO-uri importate ({})".format(call, result["total"], result["format"].upper())
                    + (" - {} erori de import".format(errs) if errs else "")
                )
            except Exception as e:
                messagebox.showerror("Eroare import", str(e))
        self._update_combos()

    def _remove_log(self):
        sel = self.log_tree.selection()
        if not sel:
            return
        for item in sel:
            call = self.log_tree.item(item)["values"][0]
            self.loaded_logs.pop(call, None)
            self.score_results.pop(call, None)
            self.val_results.pop(call, None)
            self.log_tree.delete(item)
        self._update_combos()

    def _remove_all(self):
        if not messagebox.askyesno("Confirmare", "Ștergeți toate log-urile?"):
            return
        self.loaded_logs.clear()
        self.score_results.clear()
        self.val_results.clear()
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)
        self._update_combos()

    def _update_combos(self):
        calls = list(self.loaded_logs.keys())
        self.log_sel_cb["values"] = calls
        self.cc_a["values"]       = calls
        self.cc_b["values"]       = calls
        if calls:
            if not self.log_sel_var.get() in calls:
                self.log_sel_var.set(calls[0])
            if not self.cc_a.get() in calls:
                self.cc_a.set(calls[0])
            if len(calls) > 1 and not self.cc_b.get() in calls:
                self.cc_b.set(calls[1])

    # ── Validare ─────────────────────────────────────────────────
    def _run_validation(self):
        if not self.loaded_logs:
            messagebox.showwarning("Atenție", "Importați cel puțin un log!")
            return
        self.val_results.clear()
        for item in self.val_tree.get_children():
            self.val_tree.delete(item)

        contest_id = self.contest_id.get()
        total_err = total_warn = 0

        for call, pr in self.loaded_logs.items():
            vr = validate_log(pr["qsos"], contest_id, call)
            self.val_results[call] = vr
            total_err  += vr["error_count"]
            total_warn += vr["warning_count"]

            for e in vr["errors"]:
                d = e.to_dict()
                tag = d["severity"]
                self.val_tree.insert("", "end", tags=(tag,), values=(
                    d["qso_idx"]+1, "{}:{}".format(call, d["callsign"]),
                    d["type"], d["message"], d["severity"], d.get("field","")
                ))

        # Sumar
        lines = ["=== SUMAR VALIDARE ===\n"]
        for call, vr in self.val_results.items():
            lines.append(
                "  {:<14} Total:{:4d}".format(call, vr['valid_count']+vr['error_count']+vr['warning_count'])
                + "  Valide:{:4d}  Erori:{:3d}  Avertismente:{:3d}".format(vr['valid_count'], vr['error_count'], vr['warning_count'])
            )
        self.val_summary.configure(state="normal")
        self.val_summary.delete("1.0", "end")
        self.val_summary.insert("end", "\n".join(lines))
        self.val_summary.configure(state="disabled")

        self._set_status("Validare completa: {} erori, {} avertismente".format(total_err, total_warn))
        self.nb.select(self.tab_val)
        self._refresh_log_tab()

    # ── Cross-check ──────────────────────────────────────────────
    def _run_crosscheck(self):
        call_a = self.cc_a.get()
        call_b = self.cc_b.get()
        if not call_a or not call_b:
            messagebox.showwarning("Atenție", "Selectați ambele log-uri A și B!")
            return
        if call_a == call_b:
            messagebox.showwarning("Atenție", "Log-urile A și B trebuie să fie diferite!")
            return

        tol = self.tolerance_var.get()
        pr_a = self.loaded_logs[call_a]
        pr_b = self.loaded_logs[call_b]

        self.cc_result = cross_check(
            pr_a["qsos"], pr_b["qsos"], call_a, call_b, tol
        )
        st = self.cc_result["stats"]

        # Sumar
        txt = (
            "Cross-Check: {} vs {}  |  Toleranta: +/-{} min\n".format(call_a, call_b, tol)
            + "Total QSO in A: {}  |  Confirmate: {}  |  Neconfirmate: {}\n".format(st["total_a"], st["confirmed"], st["unconfirmed"])
            + "Indicativ gresit: {}  |  Banda gresita: {}  |  Timp gresit: {}".format(st["busted_call"], st["busted_band"], st["busted_time"])
        )
        self.cc_summary.configure(state="normal")
        self.cc_summary.delete("1.0", "end")
        self.cc_summary.insert("end", txt)
        self.cc_summary.configure(state="disabled")

        # Treeview
        for item in self.cc_tree.get_children():
            self.cc_tree.delete(item)
        for idx_a, detail in self.cc_result["details"].items():
            q = pr_a["qsos"][idx_a]
            status = detail["status"]
            self.cc_tree.insert("", "end", tags=(status,), values=(
                idx_a+1, detail["callsign_a"], detail["band_a"],
                detail["date_a"], detail["time_a"],
                status.upper(), detail.get("issue","")
            ))

        self._set_status(
            "Cross-Check {} vs {}: {} confirmate, {} neconfirmate".format(call_a, call_b, st["confirmed"], st["unconfirmed"])
        )
        self.nb.select(self.tab_cc)

    # ── Scoring ──────────────────────────────────────────────────
    def _run_scoring(self):
        if not self.loaded_logs:
            messagebox.showwarning("Atenție", "Importați cel puțin un log!")
            return
        contest_id = self.contest_id.get()
        self.score_results.clear()

        for call, pr in self.loaded_logs.items():
            vr  = self.val_results.get(call)
            qso_flags = vr["qso_flags"] if vr else None
            cc  = self.cc_result if self.cc_result else None

            sr = score_log(
                pr["qsos"], contest_id,
                station_callsign=call,
                qso_flags=qso_flags,
                cross_check_results=cc,
            )
            self.score_results[call] = sr

        self.ranking = build_ranking(list(self.score_results.values()))

        # Sumar primul log
        first_call = list(self.score_results.keys())[0]
        sr = self.score_results[first_call]
        txt = (
            "=== SCOR: {} - {} ===\n".format(sr["callsign"], sr["contest_name"])
            + "Total QSO: {}  Valide: {}  Erori: {}  Duplicate: {}\n".format(sr["total_qsos"], sr["valid_qsos"], sr["error_qsos"], sr["duplicate_qsos"])
            + "Puncte QSO: {}  x  Multiplicatori: {}\n".format(sr["qso_points"], sr["multipliers"])
            + "SCOR FINAL: {} \n".format(sr["total_score"])
            + "Per banda: " + "  ".join(
                "{}:{}pct/{}qso".format(b, d["points"], d["qsos"])
                for b, d in sorted(sr["per_band"].items())
            )
        )
        self.score_summary.configure(state="normal")
        self.score_summary.delete("1.0", "end")
        self.score_summary.insert("end", txt)
        self.score_summary.configure(state="disabled")

        # Clasament
        for item in self.rank_tree.get_children():
            self.rank_tree.delete(item)
        tag_map = {1: "gold", 2: "silver", 3: "bronze"}
        for r in self.ranking:
            tag = tag_map.get(r["position"], "")
            self.rank_tree.insert("", "end", tags=(tag,) if tag else (), values=(
                "#{}".format(r["position"]), r["callsign"],
                r["total_qsos"], r["valid_qsos"], r["error_qsos"],
                r["duplicate_qsos"], r["qso_points"],
                r["multipliers"], r["total_score"]
            ))

        self._set_status("Scor calculat: {} participanti clasati".format(len(self.ranking)))
        self.nb.select(self.tab_score)
        self._refresh_log_tab()

    # ── Arbitraj complet ─────────────────────────────────────────
    def _run_all(self):
        self._run_validation()
        if len(self.loaded_logs) >= 2:
            calls = list(self.loaded_logs.keys())
            self.cc_a.set(calls[0])
            self.cc_b.set(calls[1])
            self._run_crosscheck()
        self._run_scoring()
        self._set_status("✅ Arbitraj complet finalizat!")

    # ── Log tab refresh ──────────────────────────────────────────
    def _refresh_log_tab(self):
        for item in self.qso_tree.get_children():
            self.qso_tree.delete(item)

        call = self.log_sel_var.get()
        if not call or call not in self.loaded_logs:
            return

        pr = self.loaded_logs[call]
        vr = self.val_results.get(call, {})
        sr = self.score_results.get(call, {})

        qso_flags = vr.get("qso_flags", {})
        breakdown = {b["idx"]: b for b in sr.get("breakdown", [])}

        band_flt = self.band_filter.get()
        stat_flt = self.stat_filter.get()

        bands_seen = set()
        count = 0
        for i, q in enumerate(pr["qsos"]):
            flag = qso_flags.get(i, "ok")
            pts  = breakdown.get(i, {}).get("points", "—")

            band = q.get("band","")
            bands_seen.add(band)

            if band_flt != "Toate" and band != band_flt:
                continue
            if stat_flt != "Toate" and flag != stat_flt:
                continue

            self.qso_tree.insert("", "end", tags=(flag,), values=(
                i+1, q.get("callsign",""), band, q.get("mode",""),
                q.get("date",""), q.get("time",""),
                q.get("rst_s",""), q.get("rst_r",""),
                q.get("exchange",""), pts, flag
            ))
            count += 1

        # Update filtru benzi
        all_bands = ["Toate"] + sorted(bands_seen)
        self.band_filter["values"] = all_bands

        self.qso_count_lbl.configure(
            text="{}/{} QSO-uri".format(count, len(pr["qsos"]))
        )

    def _sort_qso_tree(self, col):
        """Sortare coloană în treeview."""
        data = [(self.qso_tree.set(child, col), child)
                for child in self.qso_tree.get_children("")]
        try:
            data.sort(key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
        except Exception:
            data.sort()
        for idx, (val, child) in enumerate(data):
            self.qso_tree.move(child, "", idx)

    # ── Export ───────────────────────────────────────────────────
    def _export(self, fmt):
        if not self.score_results and not self.val_results:
            messagebox.showwarning("Atenție", "Rulați mai întâi arbitrajul!")
            return

        call = self.log_sel_var.get() or (list(self.score_results.keys())[0] if self.score_results else None)
        if not call:
            messagebox.showwarning("Atenție", "Selectați un log!")
            return

        ext_map = {"html": ".html", "csv": ".csv", "txt": ".txt", "json": ".json"}
        fp = filedialog.asksaveasfilename(
            defaultextension=ext_map.get(fmt, ".txt"),
            initialfile="Arbitraj_{}_{}".format(call, self.contest_id.get()),
            filetypes=[(fmt.upper(), "*{}".format(ext_map.get(fmt, "")))])
        if not fp:
            return

        sr = self.score_results.get(call, {})
        vr = self.val_results.get(call, {})

        try:
            if fmt == "html":
                export_html(sr, vr, fp, self.cc_result, self.ranking)
            elif fmt == "csv":
                export_csv(sr, vr, fp)
            elif fmt == "txt":
                export_txt(sr, vr, fp)
            elif fmt == "json":
                export_json(sr, vr, fp)
            self._set_status("Raport exportat: {}".format(fp))
            import webbrowser
            if fmt == "html" and messagebox.askyesno("Export", "Deschideți raportul în browser?"):
                webbrowser.open("file://{}".format(os.path.abspath(fp)))
        except Exception as e:
            messagebox.showerror("Eroare export", str(e))
