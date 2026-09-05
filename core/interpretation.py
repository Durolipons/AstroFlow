"""Plain-text interpretation generation for charts and forecasts.

This layer turns computed ``Chart`` / ``TransitForecast`` objects into
readable reports. It contains NO calculation logic and NO UI logic; every
value is pre-computed by the engine. Templates are intentionally simple so
GitHub Copilot / future work can expand them (see ``_SIGN_TEXT`` and
``_ASPECT_TEXT``) without touching the engine.

Hooks for future expansion (marked with ``# HOOK:``):
  * pluggable interpretation backends (LLM, local NLP, JSON templates),
  * multi-language template dictionaries.
"""

from typing import List, Optional

from . import constants as C
from . import utils
from .models import Aspect, Chart, PlanetPosition, SolarArcResult, TransitForecast
from .interpretation_store import (
    InterpretationLibrary,
    load_interpretation_library,
)

# ASCII-art / unicode separators -------------------------------------------------
RULE = "-" * 64


_DEFAULT_ASPECT_VERB = "brings influence between two energies"


def _library() -> InterpretationLibrary:
    return load_interpretation_library()


def _sign_keywords(sign: str) -> str:
    return _library().sign_text.get(sign, "self-expression")


def _aspect_verb(aspect_type: str) -> str:
    return _library().aspect_text.get(aspect_type, _DEFAULT_ASPECT_VERB)


def _planet_role(name: str) -> str:
    return _library().planet_role.get(name, "")


# ---------------------------------------------------------------------------
# Low-level formatting helpers
# ---------------------------------------------------------------------------
def planet_line(pos: PlanetPosition) -> str:
    """One table row for a planetary position."""
    house = pos.house if pos.house else "-"
    name_w = (pos.name + " " * 12)[:12]
    return (f"{name_w} {utils.format_longitude(pos.longitude):<24} "
            f"house {house:>2}  {pos.motion}")


def angle_line(name: str, lon: float) -> str:
    return f"{name:<12} {utils.format_longitude(lon)}"


def aspect_line(asp: Aspect, indent: int = 0) -> str:
    pad = " " * indent
    orb_str = f"{asp.orb:+6.2f}\u00b0"
    return (f"{pad}{asp.planet1_name:<22} {asp.symbol} {asp.planet2_name:<12} "
            f"{asp.kind:<10} orb {orb_str}")


def _verb_for(aspect_type: str) -> str:
    return _aspect_verb(aspect_type)
# ---------------------------------------------------------------------------
# Chart text reports
# ---------------------------------------------------------------------------
def chart_report(chart: Chart) -> str:
    """Full human-readable dump of any Chart (natal/progressed/directed)."""
    bd = chart.birth_data
    lines: List[str] = [
        RULE,
        f"* ASTROFLOW {chart.chart_type.upper()} *",
        RULE,
        f"Name        : {bd.name or '(unnamed)'}",
        f"Born (local): {bd.birth_datetime:%Y-%m-%d %H:%M}",
        f"Location    : {bd.location.latitude:+.4f}, {bd.location.longitude:+.4f} "
        f"(alt {bd.location.altitude:g} m)",
        f"Zodiac      : {'Sidereal (' + bd.sidereal_mode + ')' if chart.sidereal else 'Tropical'}",
        f"Houses      : {bd.house_system}",
        f"Target      : {chart.target_title}",
        f"Ayanamsa    : {chart.ayanamsa:9.4f} deg"
        if chart.sidereal else "Ayanamsa    : 0.0 (tropical)",
        "",
        "PLANETS",
        RULE,
    ]
    lines.extend(planet_line(p) for p in chart.positions)

    lines += ["", "ANGLES", RULE]
    lines.extend(angle_line(name, lon) for name, lon in chart.angles.items())

    lines += ["", "HOUSES", RULE]
    for h in chart.houses:
        lines.append(f"H{h.number:<3} {utils.format_longitude(h.longitude)}")

    lines += ["", "ASPECTS", RULE]
    if chart.aspects:
        lines.extend(aspect_line(a) for a in chart.aspects)
    else:
        lines.append("(none within configured orbs)")

    if chart.notes:
        lines += ["", "NOTES", RULE]
        lines.extend(f"- {n}" for n in chart.notes)
    return "\n".join(lines)


def interpret_aspect(asp: Aspect) -> str:
    """Turn one Aspect object into an interpretive sentence."""
    role2 = _planet_role(asp.planet2_name)
    header = (f"{asp.planet1_name} {asp.type_name} {asp.planet2_name} "
              f"(orb {abs(asp.orb):.2f}\u00b0, {asp.kind})")
    if role2:
        body = (f"Aspects your natal {asp.planet2_name} ({role2}), and "
                f"{_verb_for(asp.type_name)}.")
    else:
        body = f"The contact with natal {asp.planet2_name} {_verb_for(asp.type_name)}."
    return f"{header}\n   {body}"


def birth_interpretation(chart: Chart) -> str:
    """Natal interpretation (currently a compact sun-sign write-up)."""
    return natal_sun_text(chart)


def progression_interpretation(prog: Chart) -> str:
    """Sentence-by-sentence review of the progressed chart's new aspects."""
    when = prog.target_title.split("for ")[-1]
    lines = [f"Secondary progressions for {when}:", ""]
    if not prog.aspects:
        lines.append("No major progressed aspects within the default orbs "
                     "for this date.")
    for asp in prog.aspects[:12]:  # keep reports readable
        lines.append(interpret_aspect(asp))
    return "\n".join(lines)


def solar_arc_interpretation(result: SolarArcResult) -> str:
    """Interpretation of a solar arc direction result."""
    arc_deg = result.arc
    directed = result.chart
    lines = [
        f"Solar Arc at target date: arc = {arc_deg:.2f}\u00b0",
        f"(progressed Sun {utils.format_longitude(result.progressed_sun.longitude)} "
        f"- natal Sun {utils.format_longitude(result.natal_sun.longitude)})",
        "",
        "Directed chart highlights:",
    ]
    if directed.aspects:
        lines.extend(f"  {interpret_aspect(a)}" for a in directed.aspects[:10])
    else:
        lines.append("  No directed aspects within the default orbs.")
    return "\n".join(lines)


def transit_interpretation(forecast: TransitForecast) -> str:
    """Review of the transit-natal aspects for a target date."""
    lines = [
        f"Transit forecast for {forecast.target_utc:%Y-%m-%d} (UTC):",
        "",
    ]
    if not forecast.aspects:
        lines.append("No major transit aspects to the natal chart within "
                     "the default orbs today.")
    for asp in forecast.aspects[:20]:  # keep reports readable
        lines.append(interpret_aspect(asp))
    return "\n".join(lines)
def natal_sun_text(chart: Chart) -> str:
    """A short, friendly write-up of the natal Sun placement."""
    sun = next((p for p in chart.positions if p.name == "Sun"), None)
    if sun is None:
        return ""
    keywords = _sign_keywords(sun.sign)
    return (f"Your Sun is in {sun.sign}: {keywords}. "
            f"In the natal chart it sits in house {sun.house or '?'}, "
            f"colouring how your identity expresses itself in daily life.")
# ---------------------------------------------------------------------------
# Complete report bundles (used by the UI)
# ---------------------------------------------------------------------------
def full_birth_report(chart: Chart) -> str:
    """Natal report: full data dump + interpretation."""
    return chart_report(chart) + "\n\n" + birth_interpretation(chart)


def full_forecast_report(prog: Chart, arc: SolarArcResult,
                         transit: TransitForecast) -> str:
    """Forecast report: progressions + solar arc + transits."""
    sections = [
        chart_report(prog),
        "",
        progression_interpretation(prog),
        "",
        "=" * 64,
        solar_arc_interpretation(arc),
        "",
        "=" * 64,
        chart_report(transit.transit_chart),
        "",
        transit_interpretation(transit),
    ]
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Chart-wheel detail text (one planet / one aspect)
# HOOK: these feed the interactive chart wheel's details panel.
# ---------------------------------------------------------------------------
def planet_detail_text(chart: Chart, planet_name: str) -> str:
    """Interpretive text for one planet placement (for the chart wheel)."""
    pos = next((p for p in chart.positions if p.name == planet_name), None)
    if pos is None:
        return f"No placement named {planet_name!r} in this chart."

    house = pos.house if pos.house else "-"
    lines = [
        f"{pos.name.upper()}",
        f"{utils.format_longitude(pos.longitude)} — house {house} — {pos.motion}",
    ]
    role = _planet_role(pos.name)
    if role:
        lines += ["", f"Theme: {role}."]

    mine = [a for a in chart.aspects
            if pos.name in (a.planet1_name, a.planet2_name)]
    if mine:
        lines += ["", "Aspects made by this planet:"]
        for a in mine:
            lines.append("  " + interpret_aspect(a).replace("\n", "\n  "))
    else:
        lines += ["", "No aspects within the default orbs."]
    return "\n".join(lines)


def aspect_detail_text(aspect: Aspect) -> str:
    """Interpretive text for one aspect (for the chart wheel)."""
    p1, p2 = aspect.planet1_name, aspect.planet2_name
    lines = [
        f"{p1} {aspect.type_name} {p2}",
        f"exact angle {aspect.angle:.0f}\u00b0 — orb {abs(aspect.orb):.2f}\u00b0 ({aspect.kind})",
    ]
    roles = [f"{n}: {_planet_role(n)}" for n in (p1, p2) if _planet_role(n)]
    if roles:
        lines += ["", *roles]
    lines += ["",
              f"This {aspect.type_name.lower()} between {p1} and {p2} "
              f"{_verb_for(aspect.type_name)}."]
    return "\n".join(lines)


_DEFAULT_SKY_ASPECT_VERB = "shapes the tone of the day between the two"


def sky_aspect_text(aspect: Aspect) -> str:
    """General current-sky text for an aspect between two moving planets.

    Used by the Astro-Clock, whose wheel shows the sky right now rather than
    any birth chart: the wording never refers to natal placements.
    """
    p1, p2 = aspect.planet1_name, aspect.planet2_name
    verb = (_library().sky_aspect_text.get(aspect.type_name)
            or _DEFAULT_SKY_ASPECT_VERB)
    lines = [
        f"{p1} {aspect.type_name} {p2} — in today's sky",
        f"exact angle {aspect.angle:.0f}\u00b0 — orb {abs(aspect.orb):.2f}\u00b0 "
        f"({aspect.kind})",
    ]
    roles = [f"{n}: {_planet_role(n)}" for n in (p1, p2) if _planet_role(n)]
    if roles:
        lines += ["", *roles]
    lines += ["",
              f"Today this {aspect.type_name.lower()} {verb}.",
              "General sky weather — not tied to any birth chart."]
    return "\n".join(lines)


def sky_planet_text(chart: Chart, planet_name: str) -> str:
    """General current-sky text for one planet (for the Astro-Clock wheel)."""
    pos = next((p for p in chart.positions if p.name == planet_name), None)
    if pos is None:
        return f"No planet named {planet_name!r} in the current sky."

    lines = [
        f"{pos.name.upper()} — {utils.format_longitude(pos.longitude)}",
        f"{pos.sign} — {pos.motion}",
    ]
    role = _planet_role(pos.name)
    if role:
        lines += ["", f"Rules: {role}."]
    note = _library().planet_sky_note.get(pos.name)
    if note:
        lines.append(f"Right now: {note}.")

    mine = [a for a in chart.aspects
            if pos.name in (a.planet1_name, a.planet2_name)]
    if mine:
        lines += ["", "Closest sky contacts right now:"]
        for a in mine:
            lines.append("  " + sky_aspect_text(a).replace("\n", "\n  "))
    else:
        lines += ["", "No close contacts with other planets today."]
    return "\n".join(lines)


def sky_sign_text(chart: Chart, sign_name: str) -> str:
    """General current-sky text for a zodiac sign (for the Astro-Clock wheel).

    Describes the sign itself and which moving planets sit in it right now;
    never refers to a birth chart.
    """
    if sign_name not in C.SIGNS:
        return f"No zodiac sign named {sign_name!r}."
    element = C.ELEMENTS.get(sign_name, "")
    modality = C.MODALITIES.get(sign_name, "")
    lines = [f"{sign_name.upper()} — the sky through this sign"]
    if element or modality:
        lines.append(f"{element} / {modality}".strip())
    keywords = _library().sign_text.get(sign_name)
    if keywords:
        lines.append(f"Keywords: {keywords}.")
    note = _library().sign_sky_note.get(sign_name)
    if note:
        lines += ["", f"Right now: {note}."]

    here = [p.name for p in chart.positions if p.sign == sign_name]
    if here:
        lines += ["", "Currently here: " + ", ".join(here) + "."]
        for p in here:
            role = _planet_role(p)
            if role:
                lines.append(f"  {p}: {role}")
    else:
        lines += ["", f"No planets currently in {sign_name}."]
    lines += ["", "General sky weather — not tied to any birth chart."]
    return "\n".join(lines)


def sign_detail_text(chart: Chart, sign_name: str) -> str:
    """Natal-chart text for a zodiac sign tapped on the wheel."""
    if sign_name not in C.SIGNS:
        return f"No zodiac sign named {sign_name!r}."
    element = C.ELEMENTS.get(sign_name, "")
    modality = C.MODALITIES.get(sign_name, "")
    lines = [f"{sign_name.upper()} — natal chart",
             f"{element} / {modality}"]
    keywords = _library().sign_text.get(sign_name)
    if keywords:
        lines.append(f"Keywords: {keywords}.")

    inside = [p for p in chart.positions if p.sign == sign_name]
    if inside:
        lines += ["", f"Planets in {sign_name}:"]
        for p in inside:
            line = f"  {p.name} — {utils.format_longitude(p.longitude)}"
            role = _planet_role(p.name)
            if role:
                line += f" ({role})"
            lines.append(line)
    else:
        lines += ["", f"No natal planets in {sign_name}."]

    cusp_houses = [h.number for h in chart.houses
                   if utils.sign_of(h.longitude) == sign_name]
    if cusp_houses:
        names = ", ".join(f"{n}" for n in cusp_houses)
        lines += ["", f"House cusp(s) in {sign_name}: {names} — the areas of "
                      f"life where this sign's energy is focused."]
    return "\n".join(lines)