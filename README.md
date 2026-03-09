# YO Arbitraj v1.0

**Arbitraj profesional pentru concursuri de radioamatori YO**

[![Build EXE](https://github.com/acc1311/YO_Arbitraj/actions/workflows/build.yml/badge.svg)](https://github.com/acc1311/YO_Arbitraj/actions/workflows/build.yml)

Developed by: **Ardei Constantin-Cătălin (YO8ACR)** | yo8acr@gmail.com

---

## Descărcare EXE

**Cea mai simplă metodă:** mergeți la [Releases](../../releases) și descărcați `YO_Arbitraj_v1.0.exe`

Nu necesită Python instalat. Rulați direct pe Windows 7/8/10/11.

---

## Funcții

| Funcție | Detalii |
|---|---|
| **Import universal** | ADIF, Cabrillo 2.0/3.0, CSV, JSON (YO Log PRO nativ) |
| **Validare QSO** | RST, dată/oră, indicativ, bandă, mod, județ, duplicate |
| **Cross-Check** | Comparare două loguri, fereastră ±3 min configurabilă |
| **Scoring** | Calcul scor conform regulilor fiecărui concurs YO |
| **Clasament** | Clasament automat după scor final |
| **Export raport** | HTML (print-ready), CSV, TXT, JSON |

## Concursuri suportate

- Maraton Ion Creangă
- Ștafeta Radioamatorilor
- YO DX HF Contest
- YO VHF Contest
- Field Day
- Sprint Contest

---

## Rulare din sursă

```bash
# Nu sunt necesare pachete externe
python main.py
```

Cerințe: Python 3.6+, Tkinter (inclus cu Python)

---

## Build EXE local

```bash
pip install pyinstaller
pyinstaller build/build.spec
# EXE apare in: dist/YO_Arbitraj_v1.0.exe
```

## Build automat (GitHub Actions)

La fiecare push pe `master`, GitHub construiește automat EXE-ul.
Îl găsiți în **Actions → ultima rulare → Artifacts → YO_Arbitraj_v1.0_Windows_x64**

Pentru a crea un Release public cu EXE descărcabil:
```bash
git tag v1.0
git push origin v1.0
```
EXE apare automat la **Releases**.

---

## Structura repo

```
yo_arbitraj/
├── .github/workflows/build.yml  # Build automat EXE + Release
├── main.py                       # Entry point
├── core/
│   ├── contests.py               # Reguli concursuri YO
│   ├── parser.py                 # Import ADIF/Cabrillo/CSV/JSON
│   ├── validator.py              # Validare RST/date/ore/duplicate
│   ├── crosscheck.py             # Comparare loguri ±N minute
│   └── scorer.py                 # Scor + clasament
├── ui/
│   └── main_window.py            # GUI Tkinter dark theme
├── export/
│   └── reporter.py               # Export HTML/CSV/TXT/JSON
├── tests/
│   └── test_core.py              # 31 unit tests
├── build/
│   └── build.spec                # PyInstaller spec
└── requirements.txt
```

---

## Formate de import

| Format | Extensii | Note |
|---|---|---|
| ADIF | `.adi` `.adif` | Standard internațional, orice program de logging |
| Cabrillo | `.log` | 2.0 și 3.0, auto-detectat |
| CSV | `.csv` | Separator auto-detectat: `,` `;` `\t` `\|` |
| JSON | `.json` | YO Log PRO nativ și format generic |

---

73 de YO8ACR!
