# AstroFlow

A cross-platform astrology application with a pure-Python astrology engine
(`core/`) and a Kivy UI (`ui/`).

## Documentation

All documentation now lives in the [`docs/`](docs/) folder:

| Document | Audience |
| --- | --- |
| [docs/README.md](docs/README.md) | Project overview: architecture, setup, running, calculation methods |
| [docs/ASTROLOGER_MANUAL.md](docs/ASTROLOGER_MANUAL.md) | **Instruction manual for astrologers** - screen-by-screen usage, editing the interpretation library, copying text for blogs |
| [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | **Detailed documentation for developers**: engine internals, chart-wheel rendering model, interpretation library, testing strategy, extension recipes, Kivy pitfalls |

## Quick start

```bash
py -3.10 -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python run_app.py
```

Requires **Python 3.10** (ready-made wheels for `pyswisseph` + Kivy). Works
out of the box offline; see [docs/README.md](docs/README.md) for the optional
Swiss Ephemeris data files and online geocoding.
