"""Vedic astrology report generation for AstroFlow.

This module generates human-readable Vedic astrology reports from
computed VedicChart data.
"""

from typing import List

from . import constants as C
from . import utils
from .interpretation_store import load_interpretation_library
from .vedic import VedicChart


def _library():
    return load_interpretation_library()


def vedic_chart_report(chart: VedicChart) -> str:
    """Generate a full Vedic astrology chart report."""
    lib = _library()
    lines: List[str] = []
    bd = chart.birth_data

    lines.append("=" * 64)
    lines.append("* VEDIC ASTROLOGY CHART (JYOTISH) *")
    lines.append("=" * 64)
    name = bd.name or '(unnamed)'
    lines.append(f"Name        : {name}")
    lines.append(f"Born (local): {bd.birth_datetime:%Y-%m-%d %H:%M}")
    lines.append(f"Location    : {bd.location.latitude:+.4f}, {bd.location.longitude:+.4f}")
    lines.append(f"Ayanamsa    : {chart.ayanamsa:.4f} degrees (Lahiri)")
    lines.append("")
    jyotish_note = lib.vedic_glossary.get("Jyotish")
    if jyotish_note:
        lines.append(f"A note for English readers: {jyotish_note}")
        lines.append("")

    # Moon Nakshatra
    lines.append("MOON NAKSHATRA")
    lines.append("-" * 40)
    nak_gloss = lib.vedic_glossary.get("Nakshatra")
    if nak_gloss:
        lines.append(f"  ({nak_gloss})")
    mn = chart.moon_nakshatra
    if mn:
        nakshatra_desc = lib.nakshatra_text.get(mn["name"], "")
        mn_name = mn['name']
        mn_pada = mn['pada']
        mn_ruler = mn['ruler']
        mn_symbol = mn['symbol']
        lines.append(f"Nakshatra: {mn_name} (Pada {mn_pada})")
        lines.append(f"Ruler: {mn_ruler}")
        lines.append(f"Symbol: {mn_symbol}")
        pada_gloss = lib.vedic_glossary.get("Pada")
        if pada_gloss:
            lines.append(f"  ({pada_gloss})")
        if nakshatra_desc:
            lines.append("")
            lines.append(nakshatra_desc)
    lines.append("")

    # Sun Nakshatra
    lines.append("SUN NAKSHATRA")
    lines.append("-" * 40)
    sn = chart.sun_nakshatra
    if sn:
        nakshatra_desc = lib.nakshatra_text.get(sn["name"], "")
        sn_name = sn['name']
        sn_pada = sn['pada']
        sn_ruler = sn['ruler']
        lines.append(f"Nakshatra: {sn_name} (Pada {sn_pada})")
        lines.append(f"Ruler: {sn_ruler}")
        if nakshatra_desc:
            lines.append("")
            lines.append(nakshatra_desc)
    lines.append("")

    # Vimshottari Dasha
    lines.append("VIMSHOTTARI DASHA")
    lines.append("-" * 40)
    dasha_gloss = lib.vedic_glossary.get("Vimshottari Dasha")
    if dasha_gloss:
        lines.append(f"  ({dasha_gloss})")
    lines.append(f"Birth Dasha: {chart.dasha_ruler}")
    lines.append(f"Balance: {chart.dasha_balance:.2f} years")
    lines.append("")
    lines.append("Dasha Sequence:")
    for period in chart.dasha_periods:
        dasha_desc = lib.dasha_text.get(f"{period['planet']} Dasha", "")
        dosha = lib.planet_dosha.get(period['planet'], "")
        p_planet = period['planet']
        p_years = period['years']
        line = f"  {p_planet}: {p_years} years"
        if dosha:
            # Keep the line compact: only the "X dosha (...)" head.
            line += f" - {dosha.split(' - ')[0]}"
        lines.append(line)
        if dasha_desc:
            lines.append(f"    {dasha_desc}")
    lines.append("")

    # Planets in Signs (Sidereal)
    lines.append("PLANETS (SIDEREAL)")
    lines.append("-" * 40)
    sid_gloss = lib.vedic_glossary.get("Sidereal")
    if sid_gloss:
        lines.append(f"  ({sid_gloss})")
    for pos in chart.positions:
        house = pos.house if pos.house else "-"
        meaning = C.VEDIC_HOUSE_SIGNIFICATIONS.get(pos.house, "")
        description = f" ({meaning})" if meaning else ""
        lines.append(
            f"{pos.name:<12} {utils.format_longitude(pos.longitude):<24} "
            f"house {house:>2}{description}  {pos.motion}"
        )
    lines.append("")

    # Vedic Aspects
    lines.append("VEDIC ASPECTS (GRAHA DRISHTI)")
    lines.append("-" * 40)
    drishti_gloss = lib.vedic_glossary.get("Drishti")
    if drishti_gloss:
        lines.append(f"  ({drishti_gloss})")
    if chart.vedic_aspects:
        for aspect in chart.vedic_aspects:
            lines.append(f"  {aspect.planet1} aspects {aspect.planet2} ({aspect.aspect_type}, {aspect.house_separation}th house)")
    else:
        lines.append("  No major Vedic aspects found.")
    lines.append("")

    # House Significations
    lines.append("HOUSE SIGNIFICATIONS")
    lines.append("-" * 40)
    for house_num, meaning in C.VEDIC_HOUSE_SIGNIFICATIONS.items():
        lines.append(f"  House {house_num:>2}: {meaning}")
    lines.append("")

    # Plain-English glossary for the Vedic words used above.
    lines += ["GLOSSARY - VEDIC WORDS IN PLAIN ENGLISH", "-" * 40]
    for term in ("Jyotish", "Ayanamsa", "Sidereal", "Nakshatra", "Pada",
                 "Rashi", "Graha", "Drishti", "Vimshottari Dasha", "Dasha",
                 "Mahadasha", "Antardasha", "Rahu", "Ketu", "Lagna",
                 "Gochara", "Benefic", "Malefic", "Guru", "Dharma", "Karma",
                 "Ayurveda", "Dosha", "Vata", "Pitta", "Kapha"):
        text = lib.vedic_glossary.get(term)
        if text:
            lines.append(f"  {term} - {text}")
    lines.append("")

    # Notes
    if chart.notes:
        lines.append("NOTES")
        lines.append("-" * 40)
        for note in chart.notes:
            lines.append(f"  {note}")

    return "\n".join(lines)


def nakshatra_detail(chart: VedicChart, planet_name: str = "Moon") -> str:
    """Generate detailed nakshatra information for a planet."""
    lib = _library()
    lines: List[str] = []

    if planet_name == "Moon":
        nak = chart.moon_nakshatra
    else:
        nak = chart.sun_nakshatra

    if not nak:
        return f"No nakshatra data available for {planet_name}."

    nakshatra_desc = lib.nakshatra_text.get(nak["name"], "")
    nak_name = nak['name']
    nak_pada = nak['pada']
    nak_ruler = nak['ruler']
    nak_symbol = nak['symbol']
    lines.append(f"{planet_name.upper()} IN {nak_name.upper()}")
    lines.append("=" * 40)
    lines.append(f"Pada: {nak_pada} of 4")
    lines.append(f"Ruling Planet: {nak_ruler}")
    lines.append(f"Symbol: {nak_symbol}")
    nak_gloss = lib.vedic_glossary.get("Nakshatra")
    if nak_gloss:
        lines.append(f"({nak_gloss})")
    pada_gloss = lib.vedic_glossary.get("Pada")
    if pada_gloss:
        lines.append(f"({pada_gloss})")
    lines.append("")
    if nakshatra_desc:
        lines.append(nakshatra_desc)

    return "\n".join(lines)
