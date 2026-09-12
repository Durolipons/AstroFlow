# AstroFlow Content Databases — Design Plan

Two text corpora are planned. Both are *keyed text banks*: the engine computes
astrological facts (positions, houses, aspects, sky events) and looks up
professionally-written text for each fact. Reports are **composed** from these
atomic texts, which is what makes "all combinations" tractable.

Storage pattern: extend the existing `InterpretationLibrary`
(`core/interpretation_store.py`) — JSON-backed, git-versioned, editable in the
in-app Interpretations editor, covered by tests. SQLite can be added later for
query/coverage analytics without changing the authoring workflow.

---

## 1. Natal library (birth charts)

### Key design insight: house systems affect placement, not wording

`BirthData.house_system` is already plumbed through `swe.houses_ex` (Placidus,
Koch, Whole Sign, Equal, Regiomontanus, …). The house system changes *which*
house a planet falls in — but "Sun in the 7th house" reads the same no matter
which system put it there. **One text corpus therefore serves every house
system.** A future optional `house_system` qualifier can add nuance
(e.g. Whole-Sign-specific notes) without restructuring anything.

### Text categories

| Group | Key format | Count | Phase |
|---|---|---|---|
| `planet_sign` | `"Sun in Gemini"` | 11 × 12 = **132** (Sun..Mars hand-authored; Jupiter..Chiron element/modality frames) | 1 done |
| `planet_house` | `"Sun in house 7"` | 11 × 12 = **132** (planet verb + house arena) | 1 done |
| `sun_moon` | `"Sun Gemini · Moon Cancer"` | 12 × 12 = **144** (rotating openers; per-sign new-moon, per-element, per-modality relations) | 2 done |
| `aspect_pair` | `"Sun trine Saturn"` | 55 pairs × 9 types = **495** (pair theme + aspect flow + personal/outer family note) | 2 done |
| `angle_sign` | `"Ascendant in Sagittarius"`, `"MC in Leo"` | 24 (mask vs vocation lines) | 3 done |
| `planet_sign_retro` | `"Mercury retrograde"` | 11 (planet-specific review) | 3 done |
| `house_ruler` | `"ruler of 7 in house 6"` | 12 × 12 = **144** (cusp ruler + placed house, modern rulership) | 4 done |
| existing groups | `sign_text`, `planet_role`, `aspect_text` | 12 + 11 + 9 | done |

Phase 1–2 core corpus ≈ **~1,000 texts**. Every natal report composes:
`planet_role + planet_sign + planet_house (+ retro note) + aspect_pair × n +
sign/element balance + sun_moon blend`. A coverage tool lists unfilled keys so
authoring can proceed systematically; template sentences generated from the
existing atoms get humanized afterwards.

Schema is **additive**: the six existing groups stay exactly as they are
(editor UI + tests depend on them); new groups are new dict fields with
`default_interpretation_library()` factories, mirroring the current pattern.

---

## 2. Astro-Clock forecast library (generic current-sky)

The Astro-Clock is birth-chart-free: everything is keyed by *sky events*, not
natal placements. A new `core/forecast.py` scans the ephemeris (via the
existing `Ephemeris` wrapper) for events and buckets them by period:

| Event | Detection | Text keys |
|---|---|---|
| **Ingress** (body changes sign) | longitude crossing sign boundary (sample + bisect) | `forecast_ingress`: 11 × 12 = **132** (planet sky note + sign sky note) |
| **Station** (retro ⇄ direct) | speed sign change (sample + bisect) | `forecast_station`: 11 × 2 = **22** (planet-specific pause/resume) |
| **Currently retrograde** (ongoing state) | `PlanetPosition.is_retrograde` / speed < 0 at window start | `forecast_retrograde`: **9** (`"Mars retrograde forecast"`; Sun/Moon excluded) |
| **Sky aspect** (planet–planet, exact) | relative longitude crossing exact angle within orb | reuse `sky_aspect_text` (9) + optional per-pair 495 |
| **Lunation** (New / Full / quarters) | Sun–Moon elongation 0/90/180/270 | `forecast_phase`: **8** |
| **Eclipse** (solar / lunar passage) | near new/full + Moon near ecliptic plane (generic node proxy) | `eclipse_layer`: **3** generic lines (solar/lunar/none) — mention only; no sign/house meaning yet |
| Ambiance | current sign of Sun/Moon | reuse `sign_sky_note`, `planet_sky_note` |

Period rendering:
- **Weekly** — Moon sign changes, fast-body (Moon→Mars) ingresses + aspects,
  this week's lunation phase.
- **Monthly** — all ingresses/stations/lunations in the calendar month,
  slow-body (Jupiter→Pluto) sky aspects.
- **Yearly** — slow-body ingresses + all stations + lunations + the year's
  major transit-transit highlights (eclipses later, once node-based
  calculations are added — Moshier already provides the nodes).

The Astro-Clock gains a **Week / Month / Year** toggle that renders the
matched events with their texts, newest first, each with date + time.

### Implemented: `core/forecast.py` + sun-sign horoscopes

`core/forecast.py` implements the scanner described above and folds the sky
onto the 12 sun signs (whole-sign convention):

  * new `forecast_planet_in_sign` (11) + `forecast_sign_aspect` (44) groups
    give the per-planet *meaning* (`"Mars in your sign"`,
    `"Jupiter Trine your sign"`); `forecast_ingress`, `forecast_station`,
    `forecast_phase` and `sky_aspect_text` are reused for the rest.
  * `forecast_period / daily_forecast / weekly_forecast / monthly_forecast`
    scan the ephemeris window; `sun_sign_horoscope` maps events to a sign;
    `core.interpretation.sign_horoscope_text` composes copyable text.
  * period windows: Daily = 1 day, Weekly = 7 days, Monthly = the same
    day in the next calendar month (clamped when needed), and Yearly = the
    same date in the next calendar year (with leap-day clamping).
  * **Moon cycles are headline events**: `LunationEvent` carries the Moon's
    *sign* at the exact moment ("New Moon in Virgo") plus the major aspects
    the lunation makes to the other planets (`scan_lunation_aspects`,
    tightest orb first — e.g. "New Moon sextile Mars, orb 1.3°").
    `moon_state` gives the Moon's current 8-fold phase, its sign and its
    next sign change; `lunation_area_offset` folds each lunation onto the
    reader's whole-sign life area (1-12).  New editable groups:
    `forecast_lunation_in_sign` (4 x 12 = 48) and `forecast_lunation_area`
    (4 x 12 = 48); the composed report leads with MOON NOW / THIS LUNATION /
    YOUR MOON ANGLE / THE MOON'S JOURNEY before the planet sections.
  * the editable library groups power the wording, so astrologers can rewrite
    every meaning in the Interpretations screen without touching the engine.

---

## 3. Milestones

1. Extend `InterpretationLibrary` with the new groups (additive, tested) +
   editor categories.
2. Coverage tool: script/screen listing empty vs filled keys per group.
3. Author Phase 1 natal texts (planet_sign + planet_house = 240).
4. Build `core/forecast.py` event scanner + Week/Month/Year UI in the
   Astro-Clock; author `forecast_ingress`/`forecast_station`/`forecast_phase`.
5. Author Phase 2 (sun_moon 144, aspect_pair 495).
6. Phase 3 polish: retro notes (11 planet-specific), angle texts (24 mask vs
   vocation), rulers; **eclipse support done** (generic: \scan_eclipses\, \EclipsePeriod\, period wiring, \eclipse_layer\, SignHoroscope mention) — verified Mar 2025 lunar eclipse.

## 4. Verification baseline (what the corpus builds on)

The calculation engine was verified against independent sources for the
reference chart (Iain de Somerville, 1976-06-01 17:15 Harare): Swiss Ephemeris
recomputation (all 26 chart values within 0.05″), NASA JPL Horizons DE441
cross-check, timezone confirmation (CAT/UTC+2, no DST), and internal
consistency of aspects, house placements and Placidus cusp symmetry.
`_verify_report.py` in the repo root re-runs the comparison any time.
