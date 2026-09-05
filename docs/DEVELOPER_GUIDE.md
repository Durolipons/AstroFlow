# AstroFlow — Developer Guide

For anyone working on the AstroFlow codebase: architecture, engine internals,
the chart wheel's rendering model, the interpretation library, testing, and
the hard-won Kivy pitfalls to avoid.

---

## Contents

1. [Design principles](#1-design-principles)
2. [Module map](#2-module-map)
3. [Engine internals (core/)](#3-engine-internals-core)
4. [The interpretation library](#4-the-interpretation-library)
5. [The chart wheel (ui/widgets/chart_wheel.py)](#5-the-chart-wheel)
6. [Kivy pitfalls learned the hard way](#6-kivy-pitfalls-learned-the-hard-way)
7. [Testing](#7-testing)
8. [Extending AstroFlow](#8-extending-astroflow)

---

## 1. Design principles

1. **`core/` never imports Kivy.** The engine is UI-agnostic and reusable
   from a CLI, a web service, or tests. The dependency arrow only ever points
   from `ui/` to `core/`.
2. **The engine computes; the UI renders; interpretation is data.** No
   calculation logic in `interpretation.py`, no UI logic in `core/`, and all
   user-facing wording lives in the JSON-backed library — never hardcoded in
   screens.
3. **Geometry is shared between drawing and hit-testing.** `ChartWheel`
   computes one `_layout` dict used by both the canvas draw and the tap
   hit-test, so what you see is exactly what you can tap.
4. **Tests run headless.** The Kivy-based tests build the real app offscreen
   and assert on widget state and rendered pixels; the engine tests are pure
   pytest with no display at all.

## 2. Module map

### Engine (`core/`)

| Module | Responsibility |
| --- | --- |
| `ephemeris.py` | pyswisseph wrapper: JD conversion, planet longitudes, houses, sidereal modes; falls back to the Moshier ephemeris when no `.se1` files are present |
| `constants.py` | Planet IDs/names, `SIGNS`, `ELEMENTS`, `MODALITIES`, aspect definitions + orbs, house systems, ayanamsas |
| `models.py` | Dataclasses: `Location`, `BirthData`, `PlanetPosition`, `HouseCusp`, `Aspect`, `Chart`, `TransitForecast`, `SolarArcResult` |
| `chart.py` | `calculate_birth_chart()`: planets → houses → angles → aspects |
| `aspects.py` | Generic angular-separation aspect detection with per-aspect orbs |
| `progressions.py` | Secondary progressions and solar-arc directions |
| `transits.py` | `transit_chart()` (sky now) and transit-to-natal aspects |
| `interpretation.py` | All report/read text: `chart_report`, `full_birth_report`, `planet_detail_text`, `aspect_detail_text`, `sign_detail_text`, and the `sky_*` family for the Astro-Clock |
| `interpretation_store.py` | `InterpretationLibrary` dataclass + JSON load/save/caching (see §4) |
| `cities.py` / `geocoder.py` | Bundled city DB search + nearest lookup; optional Nominatim composite |

### UI (`ui/`)

| Module | Responsibility |
| --- | --- |
| `main.py` | `AstroFlowApp`: builds the `ScreenManager`, configures the library path to the Kivy user dir, fixes window sizing after startup |
| `app.kv` | All layout; ids map 1:1 to `ObjectProperty` fields on the screens |
| `widgets/chart_wheel.py` | The interactive wheel (see §5) |
| `widgets/astro_clock.py` | `AstroClock` panel: 1-second clock, location handling, refresh loop, sky readings on tap |
| `widgets/city_search.py` | Debounced search dropdown over the city DB |
| `screens/home_screen.py` | Birth-data form, presets, city search, online geocode toggle |
| `screens/chart_screen.py` | Natal wheel + report panel; wheel-tap → natal text |
| `screens/forecast_screen.py` | Target-date forecast generation |
| `screens/interpretation_editor.py` | The six-group library editor |

## 3. Engine internals (core/)

### Data flow

```
BirthData ──calculate_birth_chart()──▶ Chart
                                          │
              ┌───────────────────────────┼─────────────────────────┐
              ▼                           ▼                         ▼
     chart_report()              transit_chart(now)        progressions/solar arc
  (full text report)            (sky-now Chart)                (Forecast screen)
```

`Chart` carries everything downstream code needs: `positions` (each with
sign, longitude, house, motion), `houses`, `angles` (dict incl. ASC/MC),
`aspects`, `birth_data`, and sidereal metadata.

### Conventions worth knowing

* **Longitudes are tropical ecliptic longitudes in degrees** unless the chart
  is sidereal, in which case `chart.ayanamsa` records the offset that was
  applied. Always normalise with `% 360.0` before comparing.
* `utils.sign_of(deg)` and `utils.sign_index(deg)` are the canonical way to
  get a sign from a longitude — never reimplement the 30° bucketing.
* Aspect detection is one shared function (`aspects.py`) used by natal,
  progressed and transit paths, so orbs behave identically everywhere.
* Progression math: `progressed_jd = natal_jd + (target_jd − natal_jd) / 365.2425`
  (1 day = 1 year). Solar arc: `arc = progressed_Sun − natal_Sun`, added to
  every natal point *and* angle.

---

## 4. The interpretation library

All user-facing wording lives in `InterpretationLibrary`
(`core/interpretation_store.py`) — a dataclass of six `Dict[str, str]` groups:

| Field | Keys | Used by |
| --- | --- | --- |
| `sign_text` | sign names | sign + planet readings |
| `aspect_text` | aspect type names | natal aspect readings |
| `planet_role` | planet names | role lines everywhere |
| `sky_aspect_text` | aspect type names | Astro-Clock aspect readings |
| `planet_sky_note` | planet names | Astro-Clock "Right now:" lines |
| `sign_sky_note` | sign names | Astro-Clock sign "Right now:" lines |

Storage and lifecycle:

* `load_interpretation_library()` returns the active library, caching it per
  path. `configure_interpretation_library(path)` re-points and clears the
  cache — the app calls it in `build()` with the Kivy `user_data_dir`.
* `save_interpretation_library()` writes pretty-printed JSON (sorted keys,
  `ensure_ascii=True`) and refreshes the cache, which is why editor saves
  take effect on the very next reading.
* `from_dict`/`to_dict` merge *per key*, so a user file that predates a new
  group still loads (missing groups keep their defaults) — never break this
  when adding a new group. To add one: default factory → dataclass field →
  `from_dict` tuple → `to_dict` → `_CATEGORY_LABELS` in the editor → tests.

Two voices, strictly separated in `interpretation.py`:

* **Natal voice** (`planet_detail_text`, `aspect_detail_text`,
  `sign_detail_text`) — may reference houses and natal placements.
* **Sky voice** (`sky_planet_text`, `sky_aspect_text`, `sky_sign_text`) —
  for the Astro-Clock; must never mention natal placements or houses.
  `tests/test_sky_text.py` enforces this with string assertions, so keep new
  sky wording free of "natal"/"house".

## 5. The chart wheel

`ui/widgets/chart_wheel.py` renders the wheel as immediate-mode Kivy graphics
and doubles as the tap controller.

### Rendering model (important!)

* All wheel art goes into **`self._art_canvas`** — a dedicated
  `kivy.graphics.Canvas` added to the widget's canvas *before* anything else.
  `_redraw()` clears only this sub-canvas. **Never call `self.canvas.clear()`**:
  `Widget.add_widget()` embeds child canvases inside the parent's canvas, so
  clearing the parent canvas detaches any child canvas permanently.
* A plain `Widget`'s canvas draws in the **parent/window coordinate system**,
  so every draw block opens with `PushMatrix(); Translate(self.x, self.y, 0)`
  and closes with `PopMatrix()`. All geometry is widget-local; the translate
  maps it onto the screen.
* **Text (glyphs, numbers) is blitted, not labeled.** `_text_texture()`
  rasterises a string once into a cached GL texture via `CoreLabel`
  (using `glyph_font_path()` — a system font covering the astrological
  Unicode block, e.g. Segoe UI Symbol) and `_redraw()` places
  `Rectangle(texture=…)`s on the art canvas. Child `Label` widgets do **not**
  follow a plain `Widget` across render contexts (screen, export, projector) —
  that was the cause of the "invisible glyphs" bug. Keep it this way.
* The zodiac wedges are 12×12 `Triangle` instructions (standard `vPosition`
  format, tinted by `Color`) rather than a raw `Mesh` — a `Mesh` without an
  explicit `fmt` gets its vertex pairs misread as texture coordinates and
  the fan degenerates. If you reintroduce `Mesh`, pass an explicit `fmt`.

### Layout + hit-testing

`_prepare()` computes one `_layout` dict in local coordinates: ring radii
(`R * 0.86` inner, `0.93` sign labels, `0.64` planet glyph centres,
`0.60` aspect endpoints), sign/house/planet/aspect/angle dicts, each with
screen positions. `_handle_tap()` consumes the same dict:

1. planet glyphs (16 px), 2. sign glyphs (16 px), 3. aspect lines (7 px from
segment), 4. else clear selection. Selections are mutually exclusive
(`_sel_planet` / `_sel_sign` / `_sel_aspect`) and dispatch
`on_planet_selected` / `on_sign_selected` / `on_aspect_selected`.

Screens bind these events: `chart_screen.py` → natal text,
`astro_clock.py` → sky text. Redraws are triggered via a
`Clock.schedule_once` trigger (coalesced) on size/pos changes and
`set_chart()`.

### The Astro-Clock

`AstroClock` re-queues a fresh `transit_chart()` every minute
(`_last_chart_minute` guard), feeds it to the wheel via `_flush_pending_chart`
(deferring until the wheel has a real size), and updates the clock label every
second. Readings go to `readout_label` (a readonly `TextInput` so text is
selectable/copyable).

---

## 6. Kivy pitfalls learned the hard way

Pitfalls that cost real debugging time — the code comments reference these:

1. **`self.canvas.clear()` detaches child canvases.** Use a dedicated
   sub-canvas for redrawable art (§5).
2. **Plain-widget canvas coordinates are parent/window coordinates.** Always
   bracket drawing with `Translate(self.pos)`.
3. **`Mesh` without `fmt` misparses 2-float vertices** as `(x, y, u, v)` —
   the "wedges triangulating to the bottom-left" bug.
4. **`export_as_image()` renders only the widget's own canvas subtree** —
   it includes nested child canvases, but it is the wrong tool for verifying
   child *widgets'* appearance; assert on a root/framebuffer export or on
   widget state instead.
5. **`Label.minimum_height` doesn't exist** (that's a `TextInput` property);
   a wrapping `Label` sizes with `height: self.texture_size[1]`.
6. **KV does not accept multi-line list values** — keep `values: [...]` on
   one line.
7. **Window sizing in `build()` is too early** — the root stays 100×100 and
   every child collapses; set the size in `on_start`/a scheduled callback
   (see `AstroFlowApp._fix_window_size`).
8. **Headless UI tests must `Clock.tick()` a few times** before asserting on
   layout — properties and deferred redraws only settle after ticks.
9. **`stop_touch_app` doesn't exist; it's `stopTouchApp`** — silent import
   errors in probes cost time; prefer small assertions over probe scripts.

## 7. Testing

```bash
pytest tests/ -v                  # everything (engine + UI)
pytest tests/test_wheel.py -v     # one area
```

* **Pure engine tests** (no Kivy import): aspects, chart (real Sun-sign
  checks), progressions, transits, cities/geocoder, interpretation store.
* **UI tests** set `KIVY_LOG_LEVEL=error`, build the real app offscreen
  (`Window.size = …`, several `Clock.tick()`s), and assert on widget state or
  pixel data: wheel centring/glyph ink, tap dispatch, Astro-Clock readouts,
  and the interpretation editor end-to-end.
* The editor UI tests **re-point the library to a `tmp_path` file** after the
  app is built and restore the original path in a `finally` block — the real
  user `interpretations.json` is never touched by the suite. Follow this
  pattern for any test that saves user data.
* UI tests open (and close) real windows; run them locally with a display.

## 8. Extending AstroFlow

* **New interpretation group:** checklist in §4.
* **New tap target on the wheel:** add positions in `_prepare()`, a hit-test
  branch + registered event in `ChartWheel`, a highlight draw, then bind in
  both `chart_screen.py` and `astro_clock.py` (natal voice vs sky voice — §4).
* **New screen:** class in `ui/screens/` + `<Rule>` in `app.kv` + register in
  `main.py` + wire ids to `ObjectProperty`s. Layout tests (see
  `test_chart_screen_layout.py`) assert the ids resolve after `build()`.
* **Deeper city data:** replace `core/data/cities.json` with a larger
  GeoNames extract; the loader is column-mapping based.
* **Full Swiss precision:** drop `.se1` files into `core/ephe/`.

See [README.md](README.md) for setup, running and platform notes, and the
[Astrologer's Manual](ASTROLOGER_MANUAL.md) for the user-facing behaviour the
UI tests encode.
