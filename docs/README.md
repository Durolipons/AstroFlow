# AstroFlow

A cross-platform astrology application with a **pure-Python astrology engine**
(`core/`) and a **Kivy UI** (`ui/`). Runs on Windows, macOS, Linux, Android, and
Huawei devices.

> **Documentation index**
>
> * [Astrologer's Manual](ASTROLOGER_MANUAL.md) — how to use the app, screen by screen
> * [Developer Guide](DEVELOPER_GUIDE.md) — architecture, engine internals, testing

## Architecture

```
AstroFlow/
├── core/            # UI-agnostic astrology engine (no Kivy imports)
│   ├── ephemeris.py       Swiss Ephemeris (pyswisseph) wrapper
│   ├── chart.py           Birth chart: planets, houses, angles, aspects
│   ├── progressions.py    Secondary progressions + solar arc directions
│   ├── transits.py        Transit positions + transit-to-natal aspects
│   ├── aspects.py         Generic aspect detection with orbs
│   ├── interpretation.py  Plain-text report generation (natal + current sky)
│   ├── interpretation_store.py Editable JSON-backed interpretation library
│   ├── constants.py       Planet IDs, signs, aspects, house systems
│   ├── models.py          Dataclasses (BirthData, Chart, Aspect, …)
│   ├── utils.py           Math + formatting helpers
│   ├── cities.py          Bundled city database + search / nearest lookup
│   ├── geocoder.py        Optional external geocoding (Nominatim) + composite
│   ├── data/
│   │   └── cities.json    ~2,000 major cities (name, country, lat, lon, tz)
│   └── ephe/              Bundled Swiss Ephemeris data (seas_18.se1 — Chiron)
├── ui/              # Kivy frontend (calls core/, never the reverse)
│   ├── main.py            App entry point + ScreenManager
│   ├── app.kv             Kivy layout for all screens
│   ├── presets.py         Example birth-data presets
│   ├── widgets/
│   │   ├── astro_clock.py   Live clock + current-sky chart wheel panel
│   │   ├── chart_wheel.py   Interactive chart wheel (tappable glyphs)
│   │   └── city_search.py   Searchable city dropdown widget
│   └── screens/
│       ├── home_screen.py            Birth-data entry form (split with Astro-Clock)
│       ├── chart_screen.py           Natal chart display
│       ├── forecast_screen.py        Progressions + solar arc + transits
│       └── interpretation_editor.py  Editable interpretation library UI
├── docs/            # This documentation
├── tests/           # pytest test suite
├── run_app.py       Convenience launcher
└── requirements.txt
```

The engine and UI are **strictly separated**: `core/` contains no Kivy imports,
so the engine can be reused from a CLI, web service, or a future replacement UI.

## Setup

### Python version

Use **Python 3.10** (the only version with ready-made binary wheels for both
`pyswisseph` and `Kivy` among the interpreters on this machine).

```bash
# Create + activate a virtual environment
py -3.10 -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Swiss Ephemeris data files

The engine works out-of-the-box using pyswisseph's built-in **Moshier**
ephemeris (~0.1″ precision, 3000 BC – 3000 AD). The asteroid data file for
**Chiron** (`seas_18.se1`) is bundled in `core/ephe/` and auto-discovered at
startup, so all 13 chart bodies (Sun–Pluto, the lunar nodes and Chiron) are
computed fully offline. For full Swiss Ephemeris precision on the planets as
well, drop the official `sepl_*.se1` files into the same folder — the wrapper
picks up any `.se1`/`.seas` files it finds there automatically. If Chiron's
file is absent it is skipped gracefully and the chart report notes which
bodies could not be computed.

> **Licensing:** Swiss Ephemeris data files (including the bundled
> `seas_18.se1`) come from the Swiss Ephemeris project and are distributed
> under the AGPL (or a paid professional licence from Astrodienst); bundling
> them makes AstroFlow distribute under compatible terms.

## Running

```bash
python run_app.py
# or
python -m ui.main
```

The UI lets you:

1. Enter birth data (date, time, location, house system, sidereal mode).
2. Generate and view the natal chart.
3. Pick a target date and generate progressions, solar arc, and transits.
4. Watch a live Astro-Clock panel beside the chart input form, with the
   current sky drawn on an interactive wheel.
5. Tap planets, zodiac signs and aspect lines on either wheel to read
   interpretations — natal text on the Chart screen, general current-sky
   text on the Astro-Clock.
6. Edit interpretation wording inside the app and save it to your local
   profile.

## City lookup

The Home screen includes a **searchable city dropdown** backed by a bundled
database of ~2,000 major cities/towns (`core/data/cities.json`).

* **Search by name** — type at least two characters; results are ranked by
  prefix match then population. Selecting a city fills latitude, longitude,
  IANA timezone and the place name in one click.
* **Search by coordinates** — the "Find city from lat/lon" button reverse-geocodes
  the entered coordinates to the nearest city in the database.

### Optional online geocoding

For places not in the bundled database, enable the **"Online search (rare places)"**
checkbox. This adds an optional lookup via OpenStreetMap's **Nominatim** service
(free, no API key, uses the Python standard library — no new dependency). The
local database is always tried first; the network is only queried on a miss, and
any network failure falls back gracefully so the app stays fully offline unless
you opt in.

> **Timezone note:** Nominatim returns a name and coordinates but *not* an IANA
> timezone, so externally-geocoded results estimate the timezone from the nearest
> bundled city. Verify the timezone for critical charts.

To regenerate `core/data/cities.json` from the latest GeoNames data, download
`cities15000.zip` from https://download.geonames.org/export/dump/ and filter it to
the desired columns (`name, country, lat, lon, timezone, population`).

## Testing

```bash
pytest tests/ -v
```

Covers aspect detection, birth-chart calculation (real Sun-sign checks),
progression date math, solar-arc geometry, transit structure, Chiron ephemeris
support (bundled data + graceful skip when absent), the bundled city
database (integrity + search + nearest lookup), geocoder composition, the
interpretation library and sky text, the interactive wheel (centring, glyph
rendering, tap dispatch) and the interpretation editor UI.

## Calculation methods

| Feature | Method |
| --- | --- |
| Planet positions | `swe.calc_ut` (Swiss Ephemeris) |
| Houses / angles | `swe.houses_ex` (Placidus, Koch, Whole Sign, …) |
| Sidereal zodiac | `swe.set_sid_mode` + `SEFLG_SIDEREAL` (Lahiri, Fagan/Bradley, …) |
| Secondary progressions | 1 ephemeris day = 1 year: `progressed_jd = natal_jd + (target_jd − natal_jd) / 365.2425` |
| Solar arc | `arc = progressed_Sun − natal_Sun`; add to all natal points + angles |
| Transits | Current sky vs. natal longitudes, standard aspect orbs |

## Platform notes

- **Windows / macOS / Linux:** runs directly via Kivy.
- **Android:** build with `buildozer` / `python-for-android` (Kivy supports this).
- **Huawei:** standard Android (APK) builds work on Huawei devices that support
  Android apps. *HarmonyOS NEXT* no longer runs Android APKs, so a native
  HarmonyOS build would require a separate toolchain (out of scope here).

## Interpretation library

AstroFlow stores all of its wording in a JSON-backed interpretation library so
astrologers can rewrite the text in their own voice without touching code.

- The engine loads the active library from the Kivy user profile
  (`interpretations.json`); each OS user gets their own editable copy.
- The **Interpretation Editor** screen (Interpretations button) manages six
  groups: sign keywords, aspect keywords, planet roles, sky aspect wording,
  sky planet notes and sign sky notes.
- Saved edits take effect immediately — the next tapped reading already uses
  the new wording.

See the [Astrologer's Manual](ASTROLOGER_MANUAL.md) for a walkthrough and the
[Developer Guide](DEVELOPER_GUIDE.md) for the storage format.

## Future hooks

- **Chart wheel graphics:** richer overlays or denser label styles on the wheel.
- **Date-range scanning:** surface the strongest transit aspects across a week
  or month (stubbed in `ForecastScreen`).
- **Chart storage / profiles:** `BirthData` and `Chart` are dataclasses, so
  JSON or pickle serialization is trivial to add.
- **Richer city data:** swap in a larger GeoNames extract (e.g. `cities50000`)
  for smaller towns, or add a spatial index (KD-tree) for faster nearest-lookup.
