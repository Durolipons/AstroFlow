# AstroFlow — Astrologer's Manual

A practical, screen-by-screen guide to using AstroFlow in your daily practice.
No technical knowledge is required for anything in this manual.

---

## Contents

1. [Getting started](#1-getting-started)
2. [The Home screen — entering birth data](#2-the-home-screen--entering-birth-data)
3. [The Astro-Clock — the sky right now](#3-the-astro-clock--the-sky-right-now)
4. [Tapping the wheel — reading about anything](#4-tapping-the-wheel--reading-about-anything)
5. [The Chart screen — the natal chart](#5-the-chart-screen--the-natal-chart)
6. [The Forecast screen — progressions, solar arc, transits](#6-the-forecast-screen)
7. [Making the wording your own — the Interpretation Library](#7-making-the-wording-your-own--the-interpretation-library)
8. [Copying text for blogs and posts](#8-copying-text-for-blogs-and-posts)
9. [Where your data lives](#9-where-your-data-lives)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Getting started

Start the application:

```
python run_app.py
```

A window opens showing the **Home screen**: the birth-data form on the left
and the **Astro-Clock** (a live clock with the current sky) on the right.
Everything works offline; the only optional network use is the rare-place
city search, which you must switch on yourself.

### Choosing a house system and zodiac

At the bottom of the birth-data form you will find two dropdowns:

* **House system** — Placidus (default), Koch, Whole Sign, Equal, Campanus,
  Regiomontanus and more. Choose the one you practise with; the houses and
  angles (ASC, MC) are recalculated the moment you change it.
* **Zodiac** — Tropical (default) or Sidereal. In sidereal mode an additional
  ayanamsa dropdown appears (Lahiri, Fagan/Bradley and others).

---

## 2. The Home screen — entering birth data

1. **Name** — optional; it labels the chart report.
2. **Date and time** — the *local* birth time, as recorded on the birth
   certificate. AstroFlow converts it to Universal Time using the location's
   timezone automatically.
3. **Location** — the fastest way is the **city search box**: type at least
   two letters and pick a result. Latitude, longitude, timezone and place
   name are filled in one click.
   * If the place is not listed, type the coordinates yourself (decimal
     degrees; south and west as minus, e.g. `-0.1`).
   * For rare places, tick **"Online search (rare places)"** and search again.
4. **Generate Chart** — creates the natal chart and opens the Chart screen.

You can also start from an **example preset** (well-known charts with verified
birth data) if you just want to explore.

> **Tip — the Astro-Clock follows this location.** The current-sky wheel on
> the right uses the same place (or your device location, where available),
> so set the location first and the Astro-Clock immediately shows the sky
> above *you*.

---

## 3. The Astro-Clock — the sky right now

The Astro-Clock panel shows:

* the current **date and time** (updates every second),
* the **place** the sky is calculated for,
* a **live chart wheel of the sky right now** — the planets where they are
  at this moment, the zodiac ring around them, the houses as they fall at
  this place and time, and the aspect lines between moving planets.

This is a *transit* wheel, not a birth chart: it answers "what is the sky
doing today, here?". The readings it gives are written accordingly — they
never mention natal placements, houses of a birth chart, or "your birth
Saturn". They describe general sky weather.

---

## 4. Tapping the wheel — reading about anything

Both wheels (Astro-Clock and natal chart) are fully interactive. **Tap any
glyph** and a reading appears in the panel beside the wheel:

| Tap on | Astro-Clock shows | Chart screen shows |
| --- | --- | --- |
| **A planet glyph** (☉ ☽ ☿ ♀ ♂ ♃ ♄ ♅ ♆ ♇ ☊ ⚷) | Where the planet is right now, its sign and motion, what it rules, a "Right now:" note, and its closest contacts with other planets today | The natal placement: sign, degree, house, motion, its role in the life, and every aspect it makes |
| **A zodiac sign glyph** (♈ – ♓) | The sign's element and modality, keywords, a "Right now:" sky note, and which planets are currently travelling through it | The sign's keywords, which natal planets sit in it, and which house cusps fall in it |
| **An aspect line** | The two planets, the exact angle, the orb, and what this aspect is doing in today's sky | The same geometry plus the natal interpretation of the aspect |

The selected item is highlighted with an amber ring (planets and signs) or a
thicker line (aspects). Tap empty space on the wheel to clear the selection.

The reading stays in the panel until you tap something else, so you can work
through a chart one tap at a time during a consultation.

---

## 5. The Chart screen — the natal chart

Reached automatically after **Generate Chart**. It shows the natal wheel
(figure) and the full text report (interpretation) side by side.

* **The wheel** — planets at their natal positions inside the element-coloured
  zodiac ring, house cusp lines, ASC/MC axis, and aspect lines coloured by
  family (trines/sextiles blue-green, squares/oppositions red, conjunctions
  violet, minor aspects grey). Tap anything to read about it (see above).
* **The report panel** — starts with the full text report: header data, a
  table of planetary positions with sign, degree, house and motion, angles,
  house cusps and every aspect with its orb. When you tap the wheel, the
  panel switches to that item's interpretation; press **Full report** to
  bring the complete text back.

Buttons: **Full report** (restore the report), **Forecast →** (next screen),
**Interpretations** (edit wording), **Home**.

---

## 6. The Forecast screen

Set a **target date** (the year/month/day fields) and press
**Generate forecast**. For that date AstroFlow calculates and reports:

* **Secondary progressions** — the progressed planets (one day for a year),
  their signs and aspects.
* **Solar arc directions** — the solar-arc arc added to every natal point
  and angle, with the resulting contacts.
* **Transits** — the transiting planets against the natal chart, with the
  transit-to-natal aspects listed by strength.

The **Loaded chart** box reminds you whose chart the forecast is for. Use
**← Chart** to go back.

---

## 7. Making the wording your own — the Interpretation Library

Every reading AstroFlow produces is stored in an editable library, so you can
replace the built-in phrasing with your own voice. Open it with the
**Interpretations** button (available on the Home, Chart and Forecast screens).

### The six text groups

| Group (dropdown label) | Library field | What it controls |
| --- | --- | --- |
| **Sun sign keywords** | `sign_text` | The keyword line for each sign, used in sign and planet readings |
| **Aspect keywords** | `aspect_text` | The verb describing each natal aspect ("flows easily…") |
| **Planet roles** | `planet_role` | The "Rules:" / role line for each planet |
| **Sky aspect wording** | `sky_aspect_text` | The verb used for aspects in the Astro-Clock ("…keeps the day moving smoothly") |
| **Sky planet notes** | `planet_sky_note` | The "Right now:" line per planet in the Astro-Clock |
| **Sign sky notes** | `sign_sky_note` | The "Right now:" line per sign in the Astro-Clock |

### Editing an entry

1. Pick the **Category** dropdown, then the **Entry** dropdown. The current
   text loads into the large editor below (the **Key** field shows the entry's
   name — a planet, sign or aspect name).
2. Rewrite the text in the editor. Multi-line wording is fine.
3. Press **Save**. The change is written to your library file and takes
   effect **immediately** — the next tap anywhere in the app already uses
   your wording. Nothing needs restarting.

Notes:

* **Renaming a key**: type a new name into the Key field and Save — the entry
  is moved to the new name. (Renaming is rarely useful; keys must match the
  names AstroFlow uses, e.g. planet names, sign names, "Trine".)
* **Reload** discards unsaved edits and re-reads the file from disk.
* **Restore defaults** replaces the *whole* library with the built-in text.
  Your own wording in *all* groups is lost — export a copy of your file first
  if you want to keep any of it (see the next section).
* Blank text is refused; the status line at the bottom tells you why a save
  did not happen.

---

## 8. Copying text for blogs and posts

Both reading panels (Astro-Clock readout and the Chart screen's report panel)
are ordinary selectable text fields:

1. **Click and drag** (or double-click a word) to select the text you want.
2. Press **Ctrl+C** (Cmd+C on macOS) — or right-click and use Copy.
3. Paste into your blog, post or client notes.

The full natal report on the Chart screen can be copied the same way, so a
complete consultation write-up is a couple of keystrokes away.

---

## 9. Where your data lives

| Data | Location |
| --- | --- |
| Your edited interpretation wording | `interpretations.json` inside your AstroFlow user folder (shown on the Interpretations screen; per OS user) |
| City database | bundled with the app (`core/data/cities.json`) |
| Ephemeris data | built into the app; optional Swiss files in `core/ephe/` |

Back up (or share with another machine) simply by copying
`interpretations.json`.

---

## 10. Troubleshooting

| Symptom | What to do |
| --- | --- |
| **Planets/zodiac show letters instead of glyphs** (e.g. "Su", "Ar") | A font with the astrological Unicode block was not found. On Windows, Segoe UI Symbol provides it; ensure system fonts are installed. |
| **Chart looks wrong for a famous person** | Check the birth time is *local clock time* and the location's timezone came from the city database. Presets are pre-verified if in doubt. |
| **City not found** | Type coordinates directly, or enable "Online search (rare places)". |
| **Timezone looks suspicious after online search** | Online geocoding estimates the timezone from the nearest bundled city — verify manually for critical charts. |
| **My wording disappeared** | Someone pressed Restore defaults. Re-open `interpretations.json` from your backup (or re-type); defaults can always be re-edited. |
| **The wheel is too small** | Enlarge the window; the wheel scales to the square of its panel. |

---

*Happy charting! For the technical side — architecture, calculation methods,
extending the engine — see the [Developer Guide](DEVELOPER_GUIDE.md).*
