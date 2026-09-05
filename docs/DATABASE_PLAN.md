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
| `planet_sign` | `"Sun in Gemini"` | 10 × 12 = **120** | 1 |
| `planet_house` | `"Sun in house 7"` | 10 × 12 = **120** | 1 |
| `planet_sign_retro` | `"Mercury retrograde in Taurus"` | 10 | 3 |
| `sun_moon` | `"Sun Gemini · Moon Cancer"` | 12 × 12 = **144** | 2 |
| `aspect_pair` | `"Sun trine Saturn"` (node pairs included) | 66 pairs × 9 types = **594** | 2 |
| `angle_sign` | `"Ascendant in Sagittarius"`, `"MC in Leo"` | 24 | 3 |
| `house_ruler` | `"ruler of 7 (Venus) in house 6"` | 12 × 12 = 144 | 4 |
| existing groups | `sign_text`, `planet_role`, `aspect_text` | 12 + 10 + 9 | done |

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
| **Ingress** (body changes sign) | longitude crossing sign boundary (sample + bisect) | `forecast_ingress`: 10 × 12 = **120** |
| **Station** (retro ⇄ direct) | speed sign change (sample + bisect) | `forecast_station`: 10 × 2 = **20** |
| **Sky aspect** (planet–planet, exact) | relative longitude crossing exact angle within orb | reuse `sky_aspect_text` (9) + optional per-pair 594 |
| **Lunation** (New / Full / quarters) | Sun–Moon elongation 0/90/180/270 | `forecast_phase`: **8** |
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

---

## 3. Milestones

1. Extend `InterpretationLibrary` with the new groups (additive, tested) +
   editor categories.
2. Coverage tool: script/screen listing empty vs filled keys per group.
3. Author Phase 1 natal texts (planet_sign + planet_house = 240).
4. Build `core/forecast.py` event scanner + Week/Month/Year UI in the
   Astro-Clock; author `forecast_ingress`/`forecast_station`/`forecast_phase`.
5. Author Phase 2 (sun_moon 144, aspect_pair 594).
6. Phase 3 polish: retro notes, angle texts, rulers, eclipse support.

## 4. Verification baseline (what the corpus builds on)

The calculation engine was verified against independent sources for the
reference chart (Iain de Somerville, 1976-06-01 17:15 Harare): Swiss Ephemeris
recomputation (all 26 chart values within 0.05″), NASA JPL Horizons DE441
cross-check, timezone confirmation (CAT/UTC+2, no DST), and internal
consistency of aspects, house placements and Placidus cusp symmetry.
`_verify_report.py` in the repo root re-runs the comparison any time.
