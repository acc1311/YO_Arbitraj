#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YO Arbitraj v1.0 — Arbitraj Profesional pentru Concursuri de Radioamatori YO
Developed by: Ardei Constantin-Cătălin (YO8ACR)
Email: yo8acr@gmail.com

Usage:
    python main.py

Requirements:
    Python 3.6+, Tkinter (included with Python)
    Optional: pyinstaller (for .exe build)
"""

import sys
import os

# Adaugă directorul proiectului în path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows DPI fix
try:
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
except Exception:
    pass

def main():
    from ui.main_window import YOArbitrajApp
    app = YOArbitrajApp()
    app.mainloop()

if __name__ == "__main__":
    main()
