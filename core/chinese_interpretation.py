"""Chinese astrology report generation for AstroFlow.

This module generates human-readable Chinese astrology reports from
computed ChineseChart data.
"""

from typing import List

from . import constants as C
from .chinese import ChineseChart
from .interpretation_store import load_interpretation_library


def _library():
    return load_interpretation_library()


def chinese_chart_report(chart: ChineseChart) -> str:
    """Generate a full Chinese astrology chart report."""
    lib = _library()
    lines: List[str] = []
    bd = chart.birth_data

    lines.append("=" * 64)
    lines.append("* CHINESE ASTROLOGY CHART *")
    lines.append("=" * 64)
    name = bd.name or '(unnamed)'
    lines.append(f"Name        : {name}")
    lines.append(f"Born (local): {bd.birth_datetime:%Y-%m-%d %H:%M}")
    lines.append(f"Location    : {bd.location.latitude:+.4f}, {bd.location.longitude:+.4f}")
    lines.append("")

    # Year Animal
    lines.append("CHINESE ZODIAC")
    lines.append("-" * 40)
    zodiac_desc = lib.chinese_zodiac.get(chart.year_animal, "")
    lines.append(f"Year Animal: {chart.year_animal} ({chart.year_character})")
    lines.append(f"Element: {chart.year_element}")
    lines.append(f"Polarity: {chart.year_polarity}")
    lines.append("")
    if zodiac_desc:
        lines.append(zodiac_desc)
    lines.append("")

    # Element description
    elem_desc = lib.chinese_element.get(chart.year_element, "")
    if elem_desc:
        lines.append(f"{chart.year_element.upper()} ELEMENT")
        lines.append("-" * 40)
        lines.append(elem_desc)
        lines.append("")

    # Polarity description
    polarity_desc = lib.yin_yang.get(chart.year_polarity, "")
    if polarity_desc:
        lines.append(f"{chart.year_polarity.upper()} ENERGY")
        lines.append("-" * 40)
        lines.append(polarity_desc)
        lines.append("")

    # BaZi Four Pillars
    lines.append("BAZI (FOUR PILLARS OF DESTINY)")
    lines.append("-" * 40)
    pillar_names = {"year": "Year", "month": "Month", "day": "Day", "hour": "Hour"}
    for pillar_key, pillar_name in pillar_names.items():
        pillar = chart.bazi[pillar_key]
        p_stem = pillar['stem']
        p_branch = pillar['branch']
        p_stem_pol = pillar['stem_polarity']
        p_stem_elem = pillar['stem_element']
        p_branch_animal = pillar['branch_animal']
        p_branch_elem = pillar['branch_element']
        lines.append(f"  {pillar_name} Pillar: {p_stem}-{p_branch}")
        lines.append(f"    Stem: {p_stem_pol} {p_stem_elem} ({p_stem})")
        lines.append(f"    Branch: {p_branch_animal} - {p_branch_elem} ({p_branch})")
    lines.append("")

    # Element Balance
    lines.append("ELEMENT BALANCE")
    lines.append("-" * 40)
    for elem, count in chart.element_counts.items():
        bar = "█" * count + "░" * (4 - count)
        lines.append(f"  {elem:<6} {bar} ({count})")
    lines.append("")
    lines.append(f"Dominant Element: {chart.dominant_element}")
    lines.append("")

    # Compatibility
    lines.append("COMPATIBILITY")
    lines.append("-" * 40)
    best_matches = C.CHINESE_ZODIAC_COMPATIBILITY.get(chart.year_animal, [])
    matches_str = ", ".join(best_matches)
    lines.append(f"Best matches: {matches_str}")
    lines.append("")

    # Notes
    if chart.notes:
        lines.append("NOTES")
        lines.append("-" * 40)
        for note in chart.notes:
            lines.append(f"  {note}")

    return "\n".join(lines)


def chinese_zodiac_detail(chart: ChineseChart) -> str:
    """Generate detailed Chinese zodiac animal information."""
    lib = _library()
    lines: List[str] = []

    zodiac_desc = lib.chinese_zodiac.get(chart.year_animal, "")
    traits = C.CHINESE_ZODIAC_TRAITS.get(chart.year_animal, "")

    lines.append(f"{chart.year_animal.upper()} ({chart.year_character})")
    lines.append("=" * 40)
    lines.append(f"Element: {chart.year_element}")
    lines.append(f"Polarity: {chart.year_polarity}")
    lines.append("")
    if traits:
        lines.append(f"Traits: {traits}")
        lines.append("")
    if zodiac_desc:
        lines.append(zodiac_desc)
        lines.append("")

    # Compatibility
    best_matches = C.CHINESE_ZODIAC_COMPATIBILITY.get(chart.year_animal, [])
    matches_str = ", ".join(best_matches)
    lines.append(f"Best compatibility: {matches_str}")

    return "\n".join(lines)
