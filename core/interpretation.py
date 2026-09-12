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

from datetime import timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from . import constants as C
from . import synthesis as S
from . import utils
from .models import Aspect, Chart, PlanetPosition, SolarArcResult, TransitForecast
from .interpretation_store import (
    InterpretationLibrary,
    _default_aspect_text,
    _default_aspect_pair_text,
    _default_house_ruler_text,
    _default_planet_house_text,
    _default_planet_role,
    _default_planet_sign_text,
    _default_sign_text,
    _default_sun_moon_text,
    _house_ruler_sentence,
    load_interpretation_library,
    previous_default_aspect_pair_value,
    previous_default_planet_house_value,
    previous_default_sun_moon_value,
    sign_ruler,
)
from .forecast import EclipsePeriod, SignHoroscope

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


def sign_forecast(sign: str, period: str) -> str:
    """General social-media-ready evergreen forecast text for one sign.

    ``period`` is ``Daily``, ``Monthly`` or ``Yearly``.  These static lines
    live alongside the ephemeris-driven ``sign_horoscope_text`` reports.
    """
    key = f"{sign} · {period}"
    return _library().sign_forecast.get(
        key, f"{sign} — a {period.lower()} of steady growth ahead")


_PERIOD_OPENINGS = {
    "Daily": "Today",
    "Weekly": "This week",
    "Monthly": "This month",
    "Yearly": "Over the next year",
}


def forecast_date_range(horo) -> str:
    """Return the forecast's inclusive reader-facing UTC date range."""
    last_moment = horo.window_end - timedelta(microseconds=1)
    start_text = f"{horo.window_start.day} {horo.window_start:%B %Y}"
    end_text = f"{last_moment.day} {last_moment:%B %Y}"
    if horo.window_start.date() == last_moment.date():
        return start_text
    return f"{start_text} to {end_text}"


def _is_forecast_retrograde(pos) -> bool:
    """True when a forecast-sky position is currently retrograde."""
    return bool(
        getattr(pos, "is_retrograde", False) or getattr(pos, "speed", 0.0) < 0.0
    )


def _forecast_retrograde_note(planet_name: str, lib: InterpretationLibrary) -> str:
    """Look up the ongoing-retrograde state text for one planet."""
    return lib.forecast_retrograde.get(f"{planet_name} retrograde forecast", "")


def _forecast_retrograde_positions(horo) -> list:
    """Planets currently retrograde inside ``horo.planets_in_sign``."""
    return [p for p in (getattr(horo, "planets_in_sign", None) or [])
            if _is_forecast_retrograde(p)]


def _format_forecast_fact(horo, lib: InterpretationLibrary) -> List[str]:
    """Select the most useful calculated themes for a concise introduction."""
    facts: List[str] = []
    if horo.eclipses:
        eclipse = horo.eclipses[0]
        facts.append(
            f"A {eclipse.kind.lower()} on "
            f"{eclipse.peak_utc.day} {eclipse.peak_utc:%B} "
            "marks the deepest turning point in this window."
        )
    if horo.lunations:
        lunation = horo.lunations[0]
        sign = f" in {lunation.sign}" if lunation.sign else ""
        area = horo.lunation_areas.get(0)
        area_text = f", illuminating your area {area}," if area else ""
        facts.append(
            f"The {lunation.phase.lower()}{sign}{area_text} brings a natural "
            "moment to begin, recognise, adjust, or release."
        )
    if horo.planets_in_sign:
        retros = _forecast_retrograde_positions(horo)
        planet = retros[0] if retros else horo.planets_in_sign[0]
        note = lib.forecast_planet_in_sign.get(
            f"{planet.name} in your sign", ""
        )
        facts.append(note or f"{planet.name} in your sign makes this personal.")
        if retros:
            retro_note = _forecast_retrograde_note(retros[0].name, lib)
            facts.append(
                retro_note
                or f"{retros[0].name} is currently retrograde, inviting review."
            )
    elif horo.sign_aspects:
        aspect = horo.sign_aspects[0]
        key = f"{aspect.body} {aspect.aspect_type} your sign"
        facts.append(lib.forecast_sign_aspect.get(key, key + "."))
    if horo.ingresses:
        ingress = horo.ingresses[0]
        action = "enters" if ingress.enters_sign == horo.sign else "leaves"
        sign = ingress.enters_sign if action == "enters" else ingress.leaves_sign
        facts.append(
            f"{ingress.body} {action} {sign} on "
            f"{ingress.time_utc.day} {ingress.time_utc:%B}, "
            "changing the tone around you."
        )
    if horo.stations:
        station = horo.stations[0]
        direction = "retrograde" if station.going_retrograde else "direct"
        key = f"{station.body} stations {direction}"
        facts.append(lib.forecast_station.get(
            key,
            f"{key.capitalize()} on "
            f"{station.time_utc.day} {station.time_utc:%B}, "
            "inviting a change of pace.",
        ))
    if horo.aspects:
        aspect = next(
            (item for item in horo.aspects if item.exact_time_utc is not None),
            horo.aspects[0],
        )
        verb = lib.sky_aspect_text.get(aspect.type_name, "meet in the sky")
        facts.append(
            f"{aspect.body1} and {aspect.body2} {verb}, setting a wider "
            "background rhythm."
        )
    return facts


def forecast_introduction_text(
    horo, transit: Optional[TransitForecast] = None
) -> str:
    """Synthesize a friendly, fact-grounded opening for a sign forecast."""
    lib = _library()
    period = horo.period if horo.period in _PERIOD_OPENINGS else "Daily"
    opening = lib.forecast_period_intro.get(
        period,
        f"{_PERIOD_OPENINGS[period]} opens with an invitation to notice "
        "what is changing and choose your response with care.",
    )
    evergreen = lib.sign_forecast.get(f"{horo.sign} · {period}", "")
    facts = _format_forecast_fact(horo, lib)
    if transit is not None and transit.aspects:
        aspect = transit.aspects[0]
        transiting = aspect.planet1_name.replace(" (transit)", "").strip()
        key = (
            f"{transiting} {aspect.type_name} "
            f"natal {aspect.planet2_name}"
        )
        transit_note = lib.transit_natal.get(key)
        if transit_note:
            facts.insert(0, transit_note)
    limit = {"Daily": 2, "Weekly": 3, "Monthly": 4, "Yearly": 5}[period]
    if not facts:
        facts.append(lib.forecast_quiet.get(
            period,
            "The quieter sky leaves room to listen inwardly and strengthen "
            "what is already growing.",
        ))
    invitation = lib.forecast_invitation.get(period, "")
    paragraphs = [
        f"{opening} For {horo.sign}, {evergreen}" if evergreen else opening,
        " ".join(facts[:limit]),
    ]
    if invitation:
        paragraphs.append(invitation)
    transition = lib.forecast_transition.get(period, "")
    if transition:
        paragraphs.append(transition)
    return "\n\n".join(paragraphs)


def sign_horoscope_text(
    horo,
    include_introduction: bool = True,
    transit: Optional[TransitForecast] = None,
) -> str:
    """Compose a copy-paste-able horoscope for one sign from the engine.

    ``horo`` is a ``core.forecast.SignHoroscope`` produced by
    ``core.forecast.sun_sign_horoscope``.  Every line is either an ephemeris
    fact (times/dates) or a library text from the forecast groups, so the
    wording the astrologer edits in the Interpretations screen is exactly
    what ends up in the post.
    """
    lib = _library()
    sign = horo.sign
    lines = [
        RULE,
        f"* {sign.upper()} — {horo.period.upper()} ASTRO-CLOCK HOROSCOPE *",
        RULE,
        f"Forecast dates: {forecast_date_range(horo)} (UTC)",
        "",
    ]
    if include_introduction:
        synthesis = sun_sign_poetic_synthesis(sign, horo)
        lines += [
            _PERIOD_OPENINGS.get(horo.period, "Today"),
            "",
            synthesis,
            "",
        ]
    lines.append("MOON NOW")
    if horo.moon_state is not None:
        ms = horo.moon_state
        line = f"  - The Moon is {ms.phase.lower().replace(' moon', '')} in {ms.sign}."
        lines.append(line)
        phase_note = lib.forecast_phase.get(ms.phase)
        if phase_note:
            lines.append(f"      {phase_note}")
        if ms.next_ingress_utc is not None and ms.next_sign:
            lines.append(
                f"  - The Moon changes signs — enters {ms.next_sign} at "
                f"{ms.next_ingress_utc:%Y-%m-%d %H:%M} UTC.")
    else:
        lines.append("  - Moon state unavailable for this window.")

    lines += ["", "THIS LUNATION"]
    if horo.lunations:
        for idx, lu in enumerate(horo.lunations):
            sign_word = f" in {lu.sign}" if lu.sign else ""
            lines.append(
                f"  - {lu.phase}{sign_word} on {lu.time_utc:%Y-%m-%d %H:%M} UTC")
            note = lib.forecast_lunation_in_sign.get(
                f"{lu.phase} in {lu.sign}") if lu.sign else None
            if note:
                lines.append(f"      {note}")
            phase_note = lib.forecast_phase.get(lu.phase)
            if phase_note:
                lines.append(f"      {phase_note}")
            if lu.aspects:
                for la in lu.aspects[:2]:
                    lines.append(
                        f"      The {lu.phase.lower()} {la.type_name.lower()} "
                        f"{la.body} (orb {la.orb:.1f}°).")
            area = horo.lunation_areas.get(idx)
            if area and lu.sign:
                area_note = lib.forecast_lunation_area.get(
                    f"{lu.phase} in area {area}")
                lines.append(f"      YOUR MOON ANGLE: falls in your "
                             f"area {area}.")
                if area_note:
                    lines.append(f"      {area_note}")
    else:
        lines.append("  - No lunation moments in this window.")

    lines += ["", "THE MOON'S JOURNEY (sign changes this window)"]
    if horo.moon_ingresses:
        for ev in horo.moon_ingresses:
            lines.append(
                f"  - Moon enters {ev.enters_sign} at "
                f"{ev.time_utc:%Y-%m-%d %H:%M} UTC")
    else:
        lines.append("  - The Moon stays in one sign this window.")

    snapshot_date = f"{horo.window_start.day} {horo.window_start:%B %Y}"
    lines += ["", f"PLANETS IN YOUR SIGN (as of {snapshot_date})"]
    if horo.planets_in_sign:
        by_name = {getattr(p, "name", ""): p for p in horo.planets_in_sign}
        for pos in horo.planets_in_sign:
            key = f"{pos.name} in your sign"
            text = lib.forecast_planet_in_sign.get(key, key)
            retro_tag = " (retrograde)" if _is_forecast_retrograde(pos) else ""
            lines.append(
                f"  - {pos.name} in {pos.sign}{retro_tag} "
                f"({utils.format_dms(pos.sign_degree)}): {text}")
            if _is_forecast_retrograde(pos):
                retro_note = _forecast_retrograde_note(pos.name, lib)
                if retro_note:
                    lines.append(f"      [Retrograde] {retro_note}")
    else:
        lines.append("  - No planets are currently transiting your sign.")

    lines += ["", f"ASPECTS TO YOUR SIGN (as of {snapshot_date})"]
    if horo.sign_aspects:
        retro_by_name = {
            getattr(p, "name", ""): p for p in horo.planets_in_sign
        } if horo.planets_in_sign else {}
        for sa in horo.sign_aspects:
            key = f"{sa.body} {sa.aspect_type} your sign"
            text = lib.forecast_sign_aspect.get(key, key)
            aspecting = retro_by_name.get(sa.body)
            retro_tag = (
                " (retrograde)"
                if aspecting is not None and _is_forecast_retrograde(aspecting)
                else ""
            )
            lines.append(
                f"  - {sa.body} {sa.aspect_type} your sign{retro_tag}: {text}")
            if retro_tag:
                retro_note = _forecast_retrograde_note(sa.body, lib)
                if retro_note:
                    lines.append(f"      [Retrograde] {retro_note}")
    else:
        lines.append("  - No major aspects reach your sign in this window.")

    lines += ["", "RETROGRADES NOW (planets currently retrograde)"]
    current_retros = _forecast_retrograde_positions(horo)
    if current_retros:
        for pos in current_retros:
            note = _forecast_retrograde_note(pos.name, lib)
            lines.append(
                f"  - {pos.name} retrograde in {pos.sign} "
                f"(as of {snapshot_date})")
            if note:
                lines.append(f"      {note}")
    else:
        lines.append("  - No planets retrograde in your sign focus this window.")

    lines += ["", "INGRESSES (entering / leaving your sign)"]
    if horo.ingresses:
        for ev in horo.ingresses:
            retro_tag = " (retrograde)" if not ev.entering else ""
            if ev.enters_sign == sign:
                focus = f"{ev.body} enters {ev.enters_sign}{retro_tag}"
                note_key = f"{ev.body} enters {ev.enters_sign}"
            else:
                focus = f"{ev.body} leaves {ev.leaves_sign}{retro_tag}"
                note_key = f"{ev.body} enters {ev.enters_sign}"
            lines.append(
                f"  - {focus} at {ev.time_utc:%Y-%m-%d %H:%M} UTC")
            note = lib.forecast_ingress.get(note_key)
            if note:
                lines.append(f"      {note}")
    else:
        lines.append("  - No ingresses touch your sign in this window.")

    lines += ["", "SKY ASPECTS (this window, all signs)"]
    if horo.aspects:
        for asp in horo.aspects:
            exact = (f", exact {asp.exact_time_utc:%m-%d %H:%M}"
                     if asp.exact_time_utc else "")
            lines.append(
                f"  - {asp.body1} {asp.type_name} {asp.body2}: "
                f"in orb {asp.orb_in_time_utc:%m-%d %H:%M} to "
                f"{asp.orb_out_time_utc:%m-%d %H:%M}{exact} UTC")
            verb = lib.sky_aspect_text.get(asp.type_name)
            if verb:
                lines.append(f"      {verb}.")
    else:
        lines.append("  - No major aspects inside their orbs this window.")

    lines += ["", "ECLIPSES (this window)"]
    if horo.eclipses:
        layer = lib.eclipse_layer
        for ep in horo.eclipses:
            if ep.kind.lower().startswith("solar"):
                note_key = "eclipse.generic.solar"
            elif ep.kind.lower().startswith("lunar"):
                note_key = "eclipse.generic.lunar"
            else:
                note_key = None
            lines.append(
                f"  - {ep.kind} on {ep.peak_utc:%Y-%m-%d %H:%M} UTC "
                f"({ep.intensity})."
            )
            if note_key and note_key in layer:
                lines.append(f"      {layer[note_key]}")
    else:
        if "eclipse.generic.none" in lib.eclipse_layer:
            lines.append(f"  - {lib.eclipse_layer['eclipse.generic.none']}")
        else:
            lines.append("  - No eclipse passages in this window.")

    lines += ["", "STATIONS"]
    if horo.stations:
        for st in horo.stations:
            going = "retrograde" if st.going_retrograde else "direct"
            key = f"{st.body} stations {going}"
            note = lib.forecast_station.get(key)
            lines.append(f"  - {key} on {st.time_utc:%Y-%m-%d %H:%M} UTC")
            if note:
                lines.append(f"      {note}")
    else:
        lines.append("  - No planet stations in this window.")

    lines += ["", "LUNATIONS"]
    if horo.lunations:
        for lu in horo.lunations:
            lines.append(f"  - {lu.phase} on {lu.time_utc:%Y-%m-%d %H:%M} UTC")
            note = lib.forecast_phase.get(lu.phase)
            if note:
                lines.append(f"      {note}")
    else:
        lines.append("  - No lunation moments in this window.")

    lines += [
        "",
        "* General sky weather for this window — not tied to any birth chart. *",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Low-level formatting helpers
# ---------------------------------------------------------------------------
def planet_line(pos: PlanetPosition) -> str:
    """One table row for a planetary position."""
    house = pos.house if pos.house else "-"
    house_text = C.WESTERN_HOUSE_SIGNIFICATIONS.get(pos.house, "")
    house_label = f"house {house:>2}"
    if house_text:
        house_label += f" ({house_text})"
    name_w = (pos.name + " " * 12)[:12]
    return (f"{name_w} {utils.format_longitude(pos.longitude):<24} "
            f"{house_label}  {pos.motion}")


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
        meaning = C.WESTERN_HOUSE_SIGNIFICATIONS.get(h.number, "")
        description = f" - {meaning}" if meaning else ""
        lines.append(
            f"H{h.number:<3} {utils.format_longitude(h.longitude)}{description}"
        )

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


def _default_planet_sign_value(planet_name: str, sign: str) -> str:
    """The shipped (reference-grounded) default for a planet-sign pair."""
    return _default_planet_sign_text().get(
        f"{planet_name} in {sign}",
        f"{_default_planet_role().get(planet_name, planet_name)} "
        f"in {sign}")


def _planet_sign_text(planet_name: str, sign: str) -> str:
    """Look up per-planet-in-sign text.

    Returns the stored value unless it is a stale pre-upgrade default
    (the old auto-generated template contained the marker phrase
    ``" expresses through "``); stale entries are upgraded to the
    shipped reference-grounded default. Explicit user customizations
    always win.
    """
    lib = _library()
    key = f"{planet_name} in {sign}"
    stored = lib.planet_sign.get(key)
    if stored is None:
        return _default_planet_sign_value(planet_name, sign)
    if " expresses through " in stored:
        # Stale auto-generated default from before the reference-grounded
        # rewrite — upgrade it rather than echo the old template.
        return _default_planet_sign_value(planet_name, sign)
    # Live propagation: when the user rewrites a sign's character text,
    # reflect it in every planet-in-sign line for that sign.
    if lib.sign_text.get(sign) != _default_sign_text().get(sign):
        role = lib.planet_role.get(planet_name, planet_name)
        return f"{role} — expressed through {sign}'s {lib.sign_text[sign]}"
    # User has explicitly customized this entry (or it is the current default)
    return stored


def _default_planet_house_value(planet_name: str, house: int) -> str:
    """The shipped default for a planet-house combination."""
    stored = _default_planet_house_text().get(
        f"{planet_name} in house {house}")
    if stored is not None:
        return stored
    role = _default_planet_role().get(planet_name, planet_name)
    role_cap = role[0].upper() + role[1:]
    return (f"{role_cap} — its outlet is house {house}")


def _planet_house_text(planet_name: str, house: Optional[int]) -> str:
    """Look up per-planet-in-house text, with staleness-aware fallback."""
    if not house:
        return ""
    lib = _library()
    key = f"{planet_name} in house {house}"
    stored = lib.planet_house.get(key)
    if stored is None:
        return _default_planet_house_value(planet_name, house)
    if "finds its outlet in" in stored:
        # Stale pre-upgrade default — upgrade to the shipped text.
        return _default_planet_house_value(planet_name, house)
    if stored == previous_default_planet_house_value(planet_name, house):
        # Shipped default from before the arena/verb enrichment — upgrade
        # it; genuine user edits (even one character different) win.
        return _default_planet_house_value(planet_name, house)
    return stored


def _retrograde_note(planet_name: str, sign: str = "") -> str:
    """Look up sign-specific retrograde qualifier text, if any."""
    lib = _library()
    if sign:
        text = lib.planet_sign_retro.get(
            f"{planet_name} retrograde in {sign}", "")
        if text:
            return text
    return lib.planet_sign_retro.get(f"{planet_name} retrograde", "")


def _default_aspect_pair_value(planet1: str, planet2: str, aspect_type: str) -> str:
    """The shipped (reference-grounded) default for a planet-pair aspect."""
    key = f"{planet1} {aspect_type.lower()} {planet2}"
    default = _default_aspect_pair_text().get(key)
    if default is not None:
        return default
    roles = _default_planet_role()
    aspects = _default_aspect_text()
    verb = aspects.get(aspect_type, f"{aspect_type} contact")
    role1 = roles.get(planet1, planet1)
    role2 = roles.get(planet2, planet2)
    return f"{role1} {verb} {role2}"


def _aspect_pair_text(planet1: str, planet2: str, aspect_type: str) -> str:
    """Look up per-pair aspect text, with staleness-aware fallback."""
    lib = _library()
    key = f"{planet1} {aspect_type.lower()} {planet2}"
    stored = lib.aspect_pair.get(key)
    if stored is None:
        return _default_aspect_pair_value(planet1, planet2, aspect_type)
    if " & " in stored:
        # Stale pre-upgrade default (old role texts joined with " & ") —
        # upgrade it to the shipped reference-grounded line.
        return _default_aspect_pair_value(planet1, planet2, aspect_type)
    if stored == previous_default_aspect_pair_value(
            planet1, planet2, aspect_type):
        # Shipped default from before the family-note enrichment — upgrade
        # it; genuine user edits (even one character different) win.
        return _default_aspect_pair_value(planet1, planet2, aspect_type)
    return stored


def _default_angle_sign_value(angle: str, sign: str) -> str:
    """Compute the shipped default for an angle-sign combination."""
    keywords = _default_sign_text().get(sign, sign)
    if angle == "MC":
        return (f"{angle} in {sign}: your public standing grows through "
                f"{sign}'s {keywords}")
    return f"{angle} in {sign}: you meet the world with {sign}'s {keywords}"


def _angle_sign_text(angle: str, sign: str) -> str:
    """Look up angle-in-sign text, with staleness-aware fallback."""
    lib = _library()
    key = f"{angle} in {sign}"
    stored = lib.angle_sign.get(key)
    keywords = lib.sign_text.get(sign, sign)
    if angle == "MC":
        current = (f"{angle} in {sign}: your public standing grows through "
                   f"{sign}'s {keywords}")
    else:
        current = (f"{angle} in {sign}: you meet the world with "
                   f"{sign}'s {keywords}")
    if stored is None:
        return current
    if stored == _default_angle_sign_value(angle, sign):
        return current
    if "you present yourself to the world" in stored:
        # Older shipped default shared one line for both angles —
        # upgrade it; genuine user edits win.
        return current
    return stored


def _sun_moon_text(sun_sign: str, moon_sign: str) -> str:
    """Look up the Sun/Moon blend, upgrading stale pre-rewrite entries."""
    lib = _library()
    key = f"Sun {sun_sign} · Moon {moon_sign}"
    stored = lib.sun_moon.get(key)
    if stored is None:
        return _default_sun_moon_text().get(key, "")
    if "blend across these two signs" in stored:
        # Stale pre-upgrade default — upgrade to the shipped blend text.
        return _default_sun_moon_text().get(key, stored)
    if stored == previous_default_sun_moon_value(sun_sign, moon_sign):
        # Shipped default from before the opener rotation / per-sign
        # blends — upgrade it; genuine user edits win.
        return _default_sun_moon_text().get(key, stored)
    return stored


def _default_house_ruler_value(ruled_house: int, placed_house: int) -> str:
    """The shipped default for a ruled-house/placed-house combination."""
    stored = _default_house_ruler_text().get(
        f"ruler of {ruled_house} in house {placed_house}")
    if stored is not None:
        return stored
    return f"Ruler of house {ruled_house} in house {placed_house}"


def _house_ruler_text(
    ruled_house: int, ruler: str, placed_house: Optional[int],
    co_ruler: str = "",
) -> str:
    """Look up the house-ruler line, resolving the stored generic wording.

    The library stores one template per (ruled, placed) pair; the actual
    ruler planet for *this* chart is composed in so the editor's wording
    is exactly what the report shows.
    """
    lib = _library()
    key = f"ruler of {ruled_house} in house {placed_house}"
    stored = lib.house_ruler.get(key)
    if stored is None:
        return _house_ruler_sentence(ruled_house, ruler, placed_house,
                                     co_ruler)
    return _house_ruler_sentence(ruled_house, ruler, placed_house, co_ruler) \
        if stored == _default_house_ruler_text().get(key) else stored.replace(
            "{ruler}", ruler) if "{ruler}" in stored else stored


def house_rulers(chart: Chart) -> List[str]:
    """Compute one house-ruler line per house from cusp signs + placements.

    The ruler of each house cusp's sign (modern rulership) is located by
    its natal house; classical co-rulers (Mars/Saturn/Jupiter) are noted.
    """
    from .interpretation_store import _SIGN_CO_RULERS

    by_name = {p.name: p for p in chart.positions}
    lines: List[str] = []
    for house in chart.houses:
        cusp_sign = utils.sign_of(house.longitude)
        ruler = sign_ruler(cusp_sign)
        if not ruler:
            continue
        pos = by_name.get(ruler)
        placed = pos.house if pos is not None else None
        co = _SIGN_CO_RULERS.get(cusp_sign, "")
        lines.append(_house_ruler_text(house.number, ruler, placed, co))
    return lines


def birth_interpretation(chart: Chart) -> str:
    """Full natal interpretation composed from the combination libraries."""
    lib = _library()
    lines: List[str] = []

    # --- Sun / Moon blend ---
    sun = next((p for p in chart.positions if p.name == "Sun"), None)
    moon = next((p for p in chart.positions if p.name == "Moon"), None)
    if sun and moon:
        blend_key = f"Sun {sun.sign} · Moon {moon.sign}"
        blend = lib.sun_moon.get(blend_key, "")
        if blend:
            lines += [blend, ""]

    # --- Angle placements ---
    angle_lines: List[str] = []
    for angle_name in ("Ascendant", "MC"):
        lon = chart.angles.get(angle_name)
        if lon is not None:
            sign = utils.sign_of(lon)
            angle_lines.append(_angle_sign_text(angle_name, sign))
    if angle_lines:
        lines += angle_lines + [""]

    # --- Retrograde summary ---
    retro_planets = [p.name for p in chart.positions
                     if p.motion == "retrograde"]
    n_retro = len(retro_planets)
    lines += ["", "RETROGRADE SUMMARY", ""]
    if n_retro == 0:
        lines.append(
            "No natal planets are retrograde - energies tend to express "
            "outwardly and life skills develop through direct experience.")
    elif n_retro >= 4:
        lines.append(
            f"{n_retro} retrograde planets ({', '.join(retro_planets)}) - "
            "a complex, reflective nature that turns inward and forges its "
            "own path, sometimes feeling alienated from the mainstream.")
    else:
        lines.append(
            f"{n_retro} retrograde planet(s) ({', '.join(retro_planets)}) - "
            "those functions turn inward, possessing extraordinary depth and "
            "independence though they may lack confidence in themselves.")

    # --- Planet placements ---
    for pos in chart.positions:
        parts: List[str] = []
        placement = _planet_sign_text(pos.name, pos.sign)
        house_txt = _planet_house_text(pos.name, pos.house)
        retro = _retrograde_note(pos.name, pos.sign) if pos.motion == "retrograde" else ""
        parts.append(placement)
        if house_txt:
            parts.append(house_txt)
        if retro:
            parts.append(retro)
        lines.append(". ".join(parts) + ".")

    # --- House rulers ---
    ruler_lines = house_rulers(chart)
    if ruler_lines:
        lines += ["", "HOUSE RULERS", ""]
        lines.extend(ruler_lines)

    # --- Aspects ---
    if chart.aspects:
        lines += ["", "ASPECTS", ""]
        for asp in chart.aspects:
            pair = _aspect_pair_text(asp.planet1_name, asp.planet2_name, asp.type_name)
            lines.append(f"{asp.planet1_name} {asp.symbol} {asp.planet2_name} "
                         f"({asp.kind} orb {abs(asp.orb):.2f}°): {pair}")

    return "\n".join(lines)


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
    """Review of the transit-natal aspects for a target date.

    Each aspect prints its exact geometry (orb + applying/separating) and
    then the reference-grounded note from the ``transit_natal`` library
    group.  When the transiting planet is retrograde, a ``(retrograde)``
    tag is appended to the aspect line and a sign-specific retrograde
    qualifier from ``planet_sign_retro`` is shown beneath it, because a
    retrograde transit revisits and reviews the territory it has already
    crossed (Forrest, The Inner Sky ch. 7).
    """
    lib = _library()
    lines = [
        f"Transit forecast for {forecast.target_utc:%Y-%m-%d} (UTC):",
        "",
    ]
    transit_pos = {}
    tc = getattr(forecast, "transit_chart", None)
    if tc is not None:
        for pp in getattr(tc, "positions", []):
            transit_pos[pp.name] = pp
    if not forecast.aspects:
        lines.append("No major transit aspects to the natal chart within "
                     "the default orbs today.")
    for asp in forecast.aspects[:20]:  # keep reports readable
        t_name = asp.planet1_name.replace(" (transit)", "").strip()
        t_pos = transit_pos.get(t_name)
        is_retro = t_pos is not None and getattr(t_pos, "is_retrograde", False)
        retro_tag = " (retrograde)" if is_retro else ""
        lines.append(
            f"{asp.planet1_name} {asp.type_name} {asp.planet2_name} "
            f"(orb {abs(asp.orb):.2f}\u00b0, {asp.kind}){retro_tag}")
        note = lib.transit_natal.get(
            f"{t_name} {asp.type_name} natal {asp.planet2_name}")
        if note:
            lines.append(f"   {note}")
        else:
            fallback = interpret_aspect(asp)
            lines.append("   " + fallback.split("\n", 1)[-1].strip())
        if is_retro and t_pos is not None:
            r_note = lib.planet_sign_retro.get(
                f"{t_name} retrograde in {t_pos.sign}", "")
            if not r_note:
                r_note = _forecast_retrograde_note(t_name, lib)
            if r_note:
                lines.append(f"   [Retrograde] {r_note}")
    if transit_pos:
        current = sorted(
            (name for name, pos in transit_pos.items()
             if _is_forecast_retrograde(pos)))
        if current:
            lines += ["", "RETROGRADES NOW (transiting planets retrograde):"]
            for name in current:
                note = _forecast_retrograde_note(name, lib)
                lines.append(f"  - {name} retrograde")
                if note:
                    lines.append(f"      {note}")
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
# Poetic whole-chart synthesis narrative
#
# This turns the ranked, structured facts from ``core.synthesis`` into
# reusable prose. Every sentence is built from an actual chart fact (a
# sign, house, planet, aspect, pattern, or timing theme) combined with an
# editable phrase drawn from ``InterpretationLibrary``; nothing here
# invents biography or guarantees an outcome. Sections are only produced
# when the underlying data supports them, so a sparse chart yields a
# shorter, still fully grounded, synthesis.
#
# These syntheses are wired into the full Western birth/forecast report
# bundles and the standalone Sun-sign horoscope text, but intentionally do
# not alter the Vedic/Chinese report paths or the chart-wheel tap detail
# panels.
# ---------------------------------------------------------------------------

# Occasional, accessible mythic analogies for planetary rulers. Used sparingly
# (never as a substitute for the archetypal imagery library) and always
# framed as one optional lens rather than a literal or fatalistic claim.
_MYTH_NAMES: Dict[str, str] = {
    "Sun": "Apollo", "Moon": "Artemis", "Mercury": "Hermes", "Venus": "Aphrodite",
    "Mars": "Ares", "Jupiter": "Zeus", "Saturn": "Cronus", "Uranus": "Ouranos",
    "Neptune": "Poseidon", "Pluto": "Hades",
}

# Maps a dominant element/modality/resource-trinity label to one of the
# ``synthesis_strengths`` keys so the Gifts section names a strength that is
# actually supported by that data family.
_ELEMENT_STRENGTH_KEY: Dict[str, str] = {
    "Fire": "resilience", "Earth": "integrity", "Air": "discernment", "Water": "imagination",
}
_MODALITY_STRENGTH_KEY: Dict[str, str] = {
    "Cardinal": "renewal", "Fixed": "devotion", "Mutable": "adaptability",
}

# Which planets, twelve-letter archetype index and house-trinity key feed
# each "current" inside the Strongest Currents section. Indices/keys follow
# ``core.synthesis.TWELVE_LETTER_ARCHETYPES`` / ``HOUSE_TRINITIES`` exactly.
_CURRENT_SLOTS: Tuple[Tuple[str, Tuple[str, ...], int, str], ...] = (
    ("core_identity", ("Sun",), 1, "dharma"),
    ("emotional_landscape", ("Moon",), 4, "moksha"),
    ("relationships", ("Venus", "Mars"), 7, "kama"),
)

# Fixed narrative order. The second item is the bridge key (from
# ``synthesis_narrative_bridges``) used to lead into that slot — but only
# when the immediately preceding slot in this order is also present, so a
# skipped section never leaves a mismatched transition sentence behind.
_SLOT_ORDER: Tuple[Tuple[str, Optional[str]], ...] = (
    ("chart_overview", None),
    ("core_identity", "overview_to_identity"),
    ("emotional_landscape", "identity_to_emotions"),
    ("relationships", "emotions_to_relationships"),
    ("gifts", "relationships_to_strengths"),
    ("growth_path", "strengths_to_growth"),
    ("forecast_bridge", "growth_to_forecast"),
    ("closing", "forecast_to_closing"),
)

_FORECAST_POLARITY_KEY: Dict[str, str] = {
    "supportive": "supportive_window",
    "challenging": "turning_point",
    "mixed": "renewal",
    "neutral": "slow_build",
}


def _lower_first(text: str) -> str:
    """Lowercase just the first character, so a phrase can follow a colon."""
    return text[:1].lower() + text[1:] if text else text


def _top_rank(items: Sequence, allow_zero: bool = False) -> List:
    """Return every item tied for the lead score in an already-ranked list.

    ``core.synthesis`` returns every family pre-sorted best-first, so the
    lead score is simply ``items[0].score``. Zero-score (missing) buckets
    are excluded by default so absent data never gets named as "dominant".
    """
    if not items:
        return []
    lead_score = items[0].score
    if not allow_zero and lead_score <= 0:
        return []
    return [item for item in items if abs(item.score - lead_score) <= 1e-9]


def _find_planet(items: Sequence, name: str):
    return next((item for item in items if item.planet == name), None)


def _theme_by_index(items: Sequence, index: int):
    return next((item for item in items if item.index == index), None)


def _trinity_by_key(items: Sequence, key: str):
    return next((item for item in items if item.key == key), None)


def _opening_portrait_paragraphs(
    chart_synth: S.ChartSynthesis, lib: InterpretationLibrary,
) -> List[str]:
    """Ascendant, chart ruler, Sun/Moon and dominant element/modality."""
    imagery = lib.planetary_archetypal_imagery
    sentences: List[str] = []

    asc = chart_synth.ascendant_sign
    ruler = chart_synth.chart_ruler
    if asc:
        ruler_clause = ""
        if ruler:
            ruler_image = imagery.get(ruler, "")
            myth = _MYTH_NAMES.get(ruler, "")
            myth_clause = (
                f" In myth this is sometimes pictured through {myth} — one "
                "accessible lens among many, never a fixed fate."
            ) if myth else ""
            ruler_clause = (
                f" Its ruler, {ruler}, colours how that meeting unfolds."
                f"{myth_clause} {ruler_image}"
            )
        sentences.append(
            f"Rising in {asc}, this chart first meets the world through "
            f"{asc}'s way of moving forward.{ruler_clause}"
        )

    sun = _find_planet(chart_synth.planet_prominence, "Sun")
    if sun is not None:
        house_txt = f" in house {sun.house}" if sun.house else ""
        img = imagery.get("Sun", "")
        sentences.append(
            f"At its centre sits the Sun in {sun.sign}{house_txt}. {img}".strip()
        )

    moon = _find_planet(chart_synth.planet_prominence, "Moon")
    if moon is not None:
        house_txt = f" in house {moon.house}" if moon.house else ""
        img = imagery.get("Moon", "")
        sentences.append(
            f"The Moon in {moon.sign}{house_txt} keeps this portrait honest "
            f"about feeling. {img}".strip()
        )

    dom_element = _top_rank(chart_synth.element_balance)
    dom_modality = _top_rank(chart_synth.modality_balance)
    clauses: List[str] = []
    if dom_element:
        clauses.append(f"an emphasis of {' and '.join(f.label for f in dom_element)}")
    if dom_modality:
        clauses.append(
            f"a {' and '.join(f.label for f in dom_modality)} way of acting on it"
        )
    if clauses:
        sentences.append("Across the whole chart, there is " + " with ".join(clauses) + ".")

    return sentences


def _current_paragraphs(
    planets: Tuple[str, ...],
    twelve_index: int,
    trinity_key: str,
    chart_synth: S.ChartSynthesis,
) -> List[str]:
    """One "current" (identity / emotional / relational) inside the chart."""
    sentences: List[str] = []

    theme = _theme_by_index(chart_synth.twelve_letter_themes, twelve_index)
    if theme is not None and theme.score > 0:
        sentences.append(
            f"The chart repeats the note of {theme.label} — through "
            f"{theme.sign} and {theme.ruler} — often enough that it reads "
            "as a real current, not a passing detail."
        )

    trinity = _trinity_by_key(chart_synth.house_trinity_balance, trinity_key)
    if trinity is not None and not trinity.missing:
        houses = ", ".join(str(h) for h in trinity.houses)
        sentences.append(
            f"The houses of {trinity.label} ({houses}) carry some of that "
            "weight in lived, practical terms."
        )

    supportive = [
        a for a in chart_synth.supportive_aspects
        if a.planet1 in planets or a.planet2 in planets
    ]
    if supportive:
        top = supportive[0]
        sentences.append(
            f"A {top.type_name.lower()} between {top.planet1} and "
            f"{top.planet2} (orb {abs(top.orb):.1f}\u00b0) lets this current "
            "move without much friction."
        )

    challenging = [
        a for a in chart_synth.challenging_aspects
        if a.planet1 in planets or a.planet2 in planets
    ]
    if challenging:
        top = challenging[0]
        sentences.append(
            f"A tighter {top.type_name.lower()} between {top.planet1} and "
            f"{top.planet2} (orb {abs(top.orb):.1f}\u00b0) keeps it from ever "
            "feeling automatic."
        )

    patterns = [
        p for p in chart_synth.aspect_patterns
        if any(name in p.planets for name in planets)
    ]
    if patterns:
        top = patterns[0]
        label = top.pattern_type.replace("_", " ")
        sentences.append(
            f"It also anchors a {label} with {', '.join(top.planets)}, one "
            "of the chart's more structural signatures."
        )

    retro = [name for name in planets if name in chart_synth.retrograde_planets]
    if retro:
        sentences.append(
            f"{' and '.join(retro)} moves retrograde here, so this current "
            "often works through review and re-approach rather than a "
            "single forward push."
        )

    return sentences


def _gifts_paragraphs(
    chart_synth: S.ChartSynthesis, lib: InterpretationLibrary,
) -> List[str]:
    strengths = lib.synthesis_strengths
    sentences: List[str] = []

    dom_element = _top_rank(chart_synth.element_balance)
    if dom_element:
        label = dom_element[0].label
        text = strengths.get(_ELEMENT_STRENGTH_KEY.get(label, ""), "")
        if text:
            sentences.append(
                f"With {label} strongest across the chart, {_lower_first(text)}"
            )

    dom_modality = _top_rank(chart_synth.modality_balance)
    if dom_modality:
        label = dom_modality[0].label
        text = strengths.get(_MODALITY_STRENGTH_KEY.get(label, ""), "")
        if text:
            sentences.append(f"A {label} approach to life means {_lower_first(text)}")

    if chart_synth.supportive_aspects:
        top = chart_synth.supportive_aspects[0]
        text = strengths.get("heart", "")
        if text:
            sentences.append(
                f"The {top.type_name.lower()} linking {top.planet1} and "
                f"{top.planet2} is a quiet but real resource: {_lower_first(text)}"
            )

    artha = _trinity_by_key(chart_synth.house_trinity_balance, "artha")
    if artha is not None and not artha.missing:
        text = strengths.get("devotion", "")
        if text:
            houses = ", ".join(str(h) for h in artha.houses)
            sentences.append(
                f"The houses of {artha.label} ({houses}) show where steady "
                f"effort already pays off: {_lower_first(text)}"
            )

    if chart_synth.chart_ruler:
        ruler_prom = _find_planet(
            chart_synth.planet_prominence, chart_synth.chart_ruler
        )
        if ruler_prom is not None and ruler_prom.angular_house:
            text = strengths.get("integrity", "")
            if text:
                sentences.append(
                    f"Because {chart_synth.chart_ruler} (your chart ruler) "
                    f"sits in an angular house, {_lower_first(text)}"
                )

    return sentences


def _growth_paragraphs(
    chart_synth: S.ChartSynthesis, lib: InterpretationLibrary,
) -> List[str]:
    growth = lib.synthesis_growth_language
    sentences: List[str] = []

    if chart_synth.challenging_aspects:
        top = chart_synth.challenging_aspects[0]
        text = growth.get("tender_edge", "")
        if text:
            sentences.append(
                f"The {top.type_name.lower()} between {top.planet1} and "
                f"{top.planet2} (orb {abs(top.orb):.1f}\u00b0) is this "
                f"chart's clearest growth edge: {_lower_first(text)}"
            )
        reframe = growth.get("compassionate_reframe", "")
        if reframe:
            sentences.append(reframe)

    if chart_synth.retrograde_planets:
        text = growth.get("self_trust", "")
        if text:
            sentences.append(
                f"With {', '.join(chart_synth.retrograde_planets)} "
                f"retrograde at birth, {_lower_first(text)}"
            )

    t_squares = [p for p in chart_synth.aspect_patterns if p.pattern_type == "t_square"]
    if t_squares:
        top = t_squares[0]
        text = growth.get("integration", "")
        if text:
            sentences.append(
                f"The T-square among {', '.join(top.planets)} (focal "
                f"{top.focal_planet}) asks for integration rather than a "
                f"winner: {_lower_first(text)}"
            )

    missing_families = [
        fact for fact in (
            list(chart_synth.element_balance)
            + list(chart_synth.modality_balance)
            + list(chart_synth.house_trinity_balance)
        )
        if fact.missing
    ]
    if missing_families:
        first = missing_families[0]
        text = growth.get("becoming", "")
        if text:
            sentences.append(
                f"{first.label} shows no direct emphasis yet, and that is "
                f"not a lack: {_lower_first(text)}"
            )

    if not sentences:
        text = growth.get("timing", "")
        if text:
            sentences.append(text)

    return sentences


def _closing_paragraphs(
    chart_synth: S.ChartSynthesis, lib: InterpretationLibrary, has_forecast: bool,
) -> List[str]:
    conclusions = lib.synthesis_conclusions
    sentences: List[str] = []

    agency = conclusions.get("agency_close", "")
    if agency:
        sentences.append(agency)

    if chart_synth.challenging_aspects:
        tender = conclusions.get("tender_close", "")
        if tender:
            sentences.append(tender)
    else:
        affirming = conclusions.get("affirming_close", "")
        if affirming:
            sentences.append(affirming)

    if has_forecast:
        cyclical = conclusions.get("cyclical_close", "")
        if cyclical:
            sentences.append(cyclical)

    next_step = conclusions.get("next_step_close", "")
    if next_step:
        sentences.append(next_step)

    return sentences


def _story_now_paragraphs(
    forecast_synth: S.ForecastSynthesis,
    sign_horoscope: Optional[SignHoroscope],
    lib: InterpretationLibrary,
) -> List[str]:
    """Current progressions/solar-arc/transit (+ optional sky) highlights."""
    forecast_lib = lib.forecast_synthesis
    sentences: List[str] = []
    used_texts: set = set()

    intro = forecast_lib.get("current_weather", "")
    if intro:
        sentences.append(intro)
        used_texts.add(intro)

    for theme in forecast_synth.highlights[:2]:
        key = _FORECAST_POLARITY_KEY.get(theme.polarity, "slow_build")
        text = forecast_lib.get(key, "")
        when = f" around {theme.peak_utc:%d %B %Y}" if theme.peak_utc else ""
        source_label = theme.source.replace("_", " ")
        sentence = f"Through {source_label}, {theme.label}{when} stands out."
        if text and text not in used_texts:
            sentence += f" {text}"
            used_texts.add(text)
        sentences.append(sentence)

    if sign_horoscope is not None:
        if sign_horoscope.eclipses:
            eclipse = sign_horoscope.eclipses[0]
            text = forecast_lib.get("turning_point", "")
            sentence = (
                f"The wider sky adds a {eclipse.kind.lower()} near "
                f"{eclipse.peak_utc:%d %B %Y}, a shared marker rather than "
                "a personal one."
            )
            if text and text not in used_texts:
                sentence += f" {text}"
                used_texts.add(text)
            sentences.append(sentence)
        elif sign_horoscope.lunations:
            lunation = sign_horoscope.lunations[0]
            text = forecast_lib.get("slow_build", "")
            sentence = (
                f"A {lunation.phase.lower()} near "
                f"{lunation.time_utc:%d %B %Y} adds background rhythm to "
                "this window."
            )
            if text and text not in used_texts:
                sentence += f" {text}"
                used_texts.add(text)
            sentences.append(sentence)

    if sign_horoscope is not None:
        current_retros = _forecast_retrograde_positions(sign_horoscope)
        if current_retros:
            names = ", ".join(p.name for p in current_retros)
            retro_text = forecast_lib.get("retrograde_window", "")
            sentence = (
                f"The wider sky also has {names} retrograde in this window, "
                "favouring review over push."
            )
            if retro_text and retro_text not in used_texts:
                sentence += f" {retro_text}"
                used_texts.add(retro_text)
            sentences.append(sentence)

    integration = forecast_lib.get("integration_note", "")
    if integration and integration not in used_texts:
        sentences.append(integration)

    return sentences


def _sun_sign_opening_paragraphs(sign: str, lib: InterpretationLibrary) -> List[str]:
    element = C.ELEMENTS.get(sign, "")
    modality = C.MODALITIES.get(sign, "")
    ruler = S.SIGN_RULERS.get(sign, "")
    keywords = _sign_keywords(sign)
    sentences = [f"{sign} carries {keywords}."]
    if ruler:
        imagery = lib.planetary_archetypal_imagery.get(ruler, "")
        myth = _MYTH_NAMES.get(ruler, "")
        myth_clause = (
            f" In myth this is sometimes pictured through {myth} — one "
            "accessible lens, never a fixed fate."
        ) if myth else ""
        sentences.append(f"Its ruling planet is {ruler}.{myth_clause} {imagery}".strip())
    if element and modality:
        sentences.append(
            f"As a {modality} {element} sign, it tends to blend that "
            f"{element.lower()} instinct with a {modality.lower()} rhythm "
            "of action."
        )
    return sentences


def _sun_sign_gifts_paragraphs(sign: str, lib: InterpretationLibrary) -> List[str]:
    strengths = lib.synthesis_strengths
    element = C.ELEMENTS.get(sign, "")
    modality = C.MODALITIES.get(sign, "")
    sentences: List[str] = []
    text = strengths.get(_ELEMENT_STRENGTH_KEY.get(element, ""), "")
    if text:
        sentences.append(f"For {sign}, {_lower_first(text)}")
    text2 = strengths.get(_MODALITY_STRENGTH_KEY.get(modality, ""), "")
    if text2:
        sentences.append(text2)
    return sentences


def _sun_sign_story_paragraphs(
    sign_horoscope: SignHoroscope, lib: InterpretationLibrary,
) -> List[str]:
    forecast_lib = lib.forecast_synthesis
    sentences: List[str] = []

    intro = forecast_lib.get("current_weather", "")
    if intro:
        sentences.append(intro)

    if sign_horoscope.eclipses:
        eclipse = sign_horoscope.eclipses[0]
        text = forecast_lib.get("turning_point", "")
        sentence = (
            f"A {eclipse.kind.lower()} peaks near "
            f"{eclipse.peak_utc:%d %B %Y}."
        )
        if text:
            sentence += f" {text}"
        sentences.append(sentence)
    elif sign_horoscope.lunations:
        lunation = sign_horoscope.lunations[0]
        text = forecast_lib.get("slow_build", "")
        sign_note = f" in {lunation.sign}" if lunation.sign else ""
        sentence = (
            f"A {lunation.phase.lower()}{sign_note} lands near "
            f"{lunation.time_utc:%d %B %Y}."
        )
        if text:
            sentence += f" {text}"
        sentences.append(sentence)

    if sign_horoscope.planets_in_sign:
        retros = _forecast_retrograde_positions(sign_horoscope)
        planet = retros[0] if retros else sign_horoscope.planets_in_sign[0]
        text = forecast_lib.get("supportive_window", "")
        sentence = (
            f"{planet.name} is currently moving through "
            f"{sign_horoscope.sign} itself, making this window feel more "
            "personal."
        )
        if _is_forecast_retrograde(planet):
            sentence = (
                f"{planet.name} is currently retrograde in "
                f"{sign_horoscope.sign}, making this window feel more "
                "personal and more inward."
            )
            retro_text = forecast_lib.get("retrograde_window", "")
            if retro_text:
                sentence += f" {retro_text}"
        if text:
            sentence += f" {text}"
        sentences.append(sentence)
    elif sign_horoscope.sign_aspects:
        aspect = sign_horoscope.sign_aspects[0]
        text = forecast_lib.get("supportive_window", "")
        sentence = (
            f"{aspect.body} makes a {aspect.aspect_type.lower()} to "
            f"{sign_horoscope.sign} this window."
        )
        if text:
            sentence += f" {text}"
        sentences.append(sentence)

    integration = forecast_lib.get("integration_note", "")
    if integration:
        sentences.append(integration)

    return sentences


def _assemble_synthesis(
    slots: Dict[str, List[str]], lib: InterpretationLibrary,
) -> str:
    """Join present slots, in ``_SLOT_ORDER``, with adjacency-aware bridges."""
    blocks: List[str] = []
    prev_index: Optional[int] = None
    for index, (key, bridge_key) in enumerate(_SLOT_ORDER):
        paragraphs = slots.get(key)
        if not paragraphs:
            continue
        paragraphs = list(paragraphs)
        if bridge_key and prev_index == index - 1:
            bridge_text = lib.synthesis_narrative_bridges.get(bridge_key, "")
            if bridge_text:
                paragraphs = [bridge_text] + paragraphs
        heading = lib.synthesis_section_headings.get(
            key, key.replace("_", " ").title()
        )
        blocks.append(heading + "\n" + " ".join(paragraphs))
        prev_index = index
    return "\n\n".join(blocks)


def _natal_slots(chart_synth: S.ChartSynthesis, lib: InterpretationLibrary) -> Dict[str, List[str]]:
    slots: Dict[str, List[str]] = {}

    opening = _opening_portrait_paragraphs(chart_synth, lib)
    if opening:
        slots["chart_overview"] = opening

    for key, planets, twelve_index, trinity_key in _CURRENT_SLOTS:
        paragraphs = _current_paragraphs(planets, twelve_index, trinity_key, chart_synth)
        if paragraphs:
            slots[key] = paragraphs

    gifts = _gifts_paragraphs(chart_synth, lib)
    if gifts:
        slots["gifts"] = gifts

    growth = _growth_paragraphs(chart_synth, lib)
    if growth:
        slots["growth_path"] = growth

    return slots


def natal_poetic_synthesis(chart: Chart) -> str:
    """Compose a reusable, source-grounded poetic synthesis of one chart.

    Draws entirely on ``core.synthesis.analyze_chart`` (which itself scores
    every data family — elements, modalities, house trinities, planet
    prominence, aspects, aspect patterns and twelve-letter themes) and the
    editable wording in ``InterpretationLibrary``. Sections that have no
    supporting facts are simply omitted, so the same function works for a
    richly-aspected chart and a very sparse one.
    """
    lib = _library()
    chart_synth = S.analyze_chart(chart)
    slots = _natal_slots(chart_synth, lib)
    closing = _closing_paragraphs(chart_synth, lib, has_forecast=False)
    if closing:
        slots["closing"] = closing
    return _assemble_synthesis(slots, lib)


def personal_forecast_poetic_synthesis(
    natal_chart: Chart,
    progressed_chart: Chart,
    solar_arc: SolarArcResult,
    transit_forecast: TransitForecast,
    sign_horoscope: Optional[SignHoroscope] = None,
) -> str:
    """Poetic synthesis for a personal forecast: natal foundation + timing.

    Rebuilds the same natal portrait/currents/gifts/growth-edges as
    ``natal_poetic_synthesis`` and then adds a "Story Now" section woven
    from ``core.synthesis.analyze_forecast`` (progressions, solar arc and
    transits), optionally deepened with a ``SignHoroscope`` for shared
    period-sky events such as eclipses or lunations.
    """
    lib = _library()
    chart_synth = S.analyze_chart(natal_chart)
    forecast_synth = S.analyze_forecast(
        natal_chart, progressed_chart, solar_arc, transit_forecast, sign_horoscope,
    )
    slots = _natal_slots(chart_synth, lib)
    story = _story_now_paragraphs(forecast_synth, sign_horoscope, lib)
    if story:
        slots["forecast_bridge"] = story
    closing = _closing_paragraphs(chart_synth, lib, has_forecast=True)
    if closing:
        slots["closing"] = closing
    return _assemble_synthesis(slots, lib)


def sun_sign_poetic_synthesis(
    sign: str, sign_horoscope: Optional[SignHoroscope] = None,
) -> str:
    """Enrichable poetic synthesis for a bare Sun sign.

    With no ``sign_horoscope`` this stays to the sign's own archetype
    (element, modality, ruling planet). Passing a ``SignHoroscope`` enriches
    it with a "Story Now" section built from that window's real events.
    """
    lib = _library()
    slots: Dict[str, List[str]] = {}

    opening = _sun_sign_opening_paragraphs(sign, lib)
    if opening:
        slots["chart_overview"] = opening

    gifts = _sun_sign_gifts_paragraphs(sign, lib)
    if gifts:
        slots["gifts"] = gifts

    if sign_horoscope is not None:
        story = _sun_sign_story_paragraphs(sign_horoscope, lib)
        if story:
            slots["forecast_bridge"] = story

    closing = [
        text for text in (
            lib.synthesis_conclusions.get("affirming_close", ""),
            lib.synthesis_conclusions.get("next_step_close", ""),
        ) if text
    ]
    if closing:
        slots["closing"] = closing

    return _assemble_synthesis(slots, lib)


# ---------------------------------------------------------------------------
# Complete report bundles (used by the UI)
# ---------------------------------------------------------------------------
def full_birth_report(chart: Chart) -> str:
    """Natal report: synthesis first, then the full technical body."""
    return "\n\n".join((
        natal_poetic_synthesis(chart),
        chart_report(chart),
        birth_interpretation(chart),
    ))


def _technical_forecast_report_body(
    prog: Chart, arc: SolarArcResult, transit: TransitForecast,
) -> str:
    """Existing detailed forecast body, kept structurally unchanged."""
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


def full_forecast_report(
    natal_chart: Chart,
    prog: Chart,
    arc: SolarArcResult,
    transit: TransitForecast,
    sign_horoscope: Optional[SignHoroscope] = None,
) -> str:
    """Forecast report: synthesis first, then sign-sky and technical detail."""
    sections = [
        personal_forecast_poetic_synthesis(
            natal_chart, prog, arc, transit, sign_horoscope,
        ),
    ]
    if sign_horoscope is not None:
        sections.extend([
            "",
            sign_horoscope_text(
                sign_horoscope,
                include_introduction=False,
                transit=transit,
            ),
            "",
            "=" * 64,
            "* PERSONAL FORECAST DETAILS *",
            "=" * 64,
            "",
        ])
    else:
        sections.append("")
    sections.append(_technical_forecast_report_body(prog, arc, transit))
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
    house_text = C.WESTERN_HOUSE_SIGNIFICATIONS.get(pos.house, "")
    house_description = f" ({house_text})" if house_text else ""
    lines = [
        f"{pos.name.upper()}",
        f"{utils.format_longitude(pos.longitude)} — "
        f"house {house}{house_description} — {pos.motion}",
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


def transit_planet_detail(chart: Chart, planet_name: str,
                          natal_aspects=None) -> str:
    """Detail text for one *transiting* planet (forecast bi-wheel tap).

    Shows the planet's current-sky position and, when ``natal_aspects``
    (the ``TransitForecast.aspects`` list) is given, its tightest
    contacts with the natal chart using the editable ``transit_natal``
    library wording.
    """
    pos = next((p for p in chart.positions if p.name == planet_name), None)
    if pos is None:
        return f"No planet named {planet_name!r} in the transit sky."

    lines = [
        f"{pos.name.upper()} — transiting",
        f"{utils.format_longitude(pos.longitude)} — {pos.sign} — {pos.motion}",
    ]
    role = _planet_role(pos.name)
    if role:
        lines += ["", f"Transiting theme: {role}."]
    note = _library().planet_sky_note.get(pos.name)
    if note:
        lines.append(f"Right now: {note}.")
    if _is_forecast_retrograde(pos):
        retro_note = _forecast_retrograde_note(pos.name, _library())
        lines.append(
            retro_note
            or f"{pos.name} is currently retrograde: favour review over push.")

    if natal_aspects:
        lib = _library()
        mine = [a for a in natal_aspects
                if a.planet1_name.replace(" (transit)", "").strip()
                == planet_name]
        mine.sort(key=lambda a: abs(a.orb))
        if mine:
            lines += ["", "Tightest contacts with the natal chart:"]
            for a in mine[:6]:
                lines.append(
                    f"  {a.planet1_name} {a.type_name} {a.planet2_name} "
                    f"(orb {abs(a.orb):.2f}\u00b0, {a.kind})")
                t_note = lib.transit_natal.get(
                    f"{planet_name} {a.type_name} natal {a.planet2_name}")
                if t_note:
                    lines.append(f"     {t_note}")
    return "\n".join(lines)


def transit_aspect_detail(aspect: Aspect) -> str:
    """Detail text for one transit-to-natal aspect (bi-wheel line tap)."""
    t_name = aspect.planet1_name.replace(" (transit)", "").strip()
    lines = [
        f"{aspect.planet1_name} {aspect.type_name} {aspect.planet2_name}",
        f"exact angle {aspect.angle:.0f}\u00b0 — orb "
        f"{abs(aspect.orb):.2f}\u00b0 ({aspect.kind})",
    ]
    note = _library().transit_natal.get(
        f"{t_name} {aspect.type_name} natal {aspect.planet2_name}")
    if note:
        lines += ["", note]
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


# ---------------------------------------------------------------------------
# Elemental Analysis
# ---------------------------------------------------------------------------

def element_balance(chart: Chart) -> Dict[str, int]:
    """Count planets in each element.

    Returns:
        Dict mapping element name to count of planets in that element.
    """
    counts = {"Fire": 0, "Earth": 0, "Air": 0, "Water": 0}
    for pos in chart.positions:
        element = C.ELEMENTS.get(pos.sign, "")
        if element:
            counts[element] += 1
    return counts


def modality_balance(chart: Chart) -> Dict[str, int]:
    """Count planets in each modality.

    Returns:
        Dict mapping modality name to count of planets in that modality.
    """
    counts = {"Cardinal": 0, "Fixed": 0, "Mutable": 0}
    for pos in chart.positions:
        modality = C.MODALITIES.get(pos.sign, "")
        if modality:
            counts[modality] += 1
    return counts


def element_analysis_text(chart: Chart) -> str:
    """Generate a detailed elemental analysis report."""
    lib = _library()
    lines: List[str] = []
    counts = element_balance(chart)
    total = sum(counts.values())

    lines.append("ELEMENTAL ANALYSIS")
    lines.append("=" * 40)
    lines.append("")

    # Element counts
    lines.append("Element Distribution:")
    for element, count in counts.items():
        bar = "\u2588" * count + "\u2591" * (10 - count)
        pct = (count / total * 100) if total > 0 else 0
        lines.append(f"  {element:<6} {bar} {count} ({pct:.0f}%)")
    lines.append("")

    # Dominant elements
    max_count = max(counts.values()) if counts else 0
    dominant = [e for e, c in counts.items() if c == max_count and c > 0]

    for elem in dominant:
        desc = lib.element_balance.get(f"dominant_{elem.lower()}", "")
        if desc:
            lines.append(f"Dominant {elem}:")
            lines.append(f"  {desc}")
            lines.append("")

        keywords = lib.element_keywords.get(elem, "")
        qualities = C.ELEMENT_QUALITIES.get(elem, "")
        strengths = C.ELEMENT_STRENGTHS.get(elem, "")
        challenges = C.ELEMENT_CHALLENGES.get(elem, "")
        growth = C.ELEMENT_GROWTH.get(elem, "")

        if keywords:
            lines.append(f"  Keywords: {keywords}")
        if qualities:
            lines.append(f"  Qualities: {qualities}")
        if strengths:
            lines.append(f"  Strengths: {strengths}")
        if challenges:
            lines.append(f"  Challenges: {challenges}")
        if growth:
            lines.append(f"  Growth path: {growth}")
        lines.append("")

    # Missing elements
    for elem in counts:
        if counts[elem] == 0:
            desc = lib.element_balance.get(f"missing_{elem.lower()}", "")
            if desc:
                lines.append(f"Missing {elem}:")
                lines.append(f"  {desc}")
                lines.append("")

    # Element expression for each planet
    lines.append("Element Expression:")
    for pos in chart.positions:
        element = C.ELEMENTS.get(pos.sign, "")
        if element and pos.sign in C.ELEMENT_EXPRESSION.get(element, {}):
            expr = C.ELEMENT_EXPRESSION[element][pos.sign]
            lines.append(f"  {pos.name} in {pos.sign}: {expr}")

    return "\n".join(lines)


def modality_analysis_text(chart: Chart) -> str:
    """Generate a detailed modality analysis report."""
    lib = _library()
    lines: List[str] = []
    counts = modality_balance(chart)
    total = sum(counts.values())

    lines.append("MODALITY ANALYSIS")
    lines.append("=" * 40)
    lines.append("")

    # Modality counts
    lines.append("Modality Distribution:")
    for modality, count in counts.items():
        bar = "\u2588" * count + "\u2591" * (10 - count)
        pct = (count / total * 100) if total > 0 else 0
        lines.append(f"  {modality:<10} {bar} {count} ({pct:.0f}%)")
    lines.append("")

    # Dominant modalities
    max_count = max(counts.values()) if counts else 0
    dominant = [m for m, c in counts.items() if c == max_count and c > 0]

    for mod in dominant:
        desc = lib.modality_balance.get(f"dominant_{mod.lower()}", "")
        if desc:
            lines.append(f"Dominant {mod}:")
            lines.append(f"  {desc}")
            lines.append("")

        keywords = C.MODALITY_KEYWORDS.get(mod, "")
        qualities = C.MODALITY_QUALITIES.get(mod, "")
        strengths = C.MODALITY_STRENGTHS.get(mod, "")
        challenges = C.MODALITY_CHALLENGES.get(mod, "")
        growth = C.MODALITY_GROWTH.get(mod, "")

        if keywords:
            lines.append(f"  Keywords: {keywords}")
        if qualities:
            lines.append(f"  Qualities: {qualities}")
        if strengths:
            lines.append(f"  Strengths: {strengths}")
        if challenges:
            lines.append(f"  Challenges: {challenges}")
        if growth:
            lines.append(f"  Growth path: {growth}")
        lines.append("")

    # Missing modalities
    for mod in counts:
        if counts[mod] == 0:
            desc = lib.modality_balance.get(f"missing_{mod.lower()}", "")
            if desc:
                lines.append(f"Missing {mod}:")
                lines.append(f"  {desc}")
                lines.append("")

    # Modality expression for each planet
    lines.append("Modality Expression:")
    for pos in chart.positions:
        modality = C.MODALITIES.get(pos.sign, "")
        if modality and pos.sign in C.MODALITY_EXPRESSION.get(modality, {}):
            expr = C.MODALITY_EXPRESSION[modality][pos.sign]
            lines.append(f"  {pos.name} in {pos.sign}: {expr}")

    return "\n".join(lines)