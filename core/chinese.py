"""Chinese astrology calculations for AstroFlow.

This module provides Chinese astrology computations including:
- Chinese Zodiac animal signs (12 animals)
- Five Elements (Wu Xing)
- Yin-Yang polarities
- BaZi (Four Pillars of Destiny)

The Chinese zodiac is based on the Chinese lunar calendar, with each year
represented by an animal sign and one of five elements.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from . import constants as C
from . import utils
from .models import BirthData


# ---------------------------------------------------------------------------
# Chinese Zodiac Animal Calculations
# ---------------------------------------------------------------------------

def chinese_zodiac_animal(year: int) -> str:
    """Return the Chinese zodiac animal for a given year.

    The Chinese zodiac cycle repeats every 12 years.
    1900 = Rat, 1901 = Ox, etc.
    """
    idx = (year - C.CHINESE_ZODIAC_BASE_YEAR) % 12
    return C.CHINESE_ZODIAC_ANIMALS[idx]


def chinese_zodiac_element(year: int) -> str:
    """Return the Chinese element for a given year.

    The elements cycle every 10 years (5 elements x 2 polarities).
    Each element appears in both Yang and Yin forms.
    """
    idx = (year - C.CHINESE_ZODIAC_BASE_YEAR) % 10
    return C.HEAVENLY_STEM_PROPERTIES[C.HEAVENLY_STEMS[idx]]["element"]


def chinese_zodiac_polarity(year: int) -> str:
    """Return the Yin-Yang polarity for a given year."""
    idx = (year - C.CHINESE_ZODIAC_BASE_YEAR) % 10
    return C.HEAVENLY_STEM_PROPERTIES[C.HEAVENLY_STEMS[idx]]["polarity"]


def chinese_year_stem(year: int) -> str:
    """Return the Heavenly Stem for a given year."""
    idx = (year - C.CHINESE_ZODIAC_BASE_YEAR) % 10
    return C.HEAVENLY_STEMS[idx]


def chinese_year_branch(year: int) -> str:
    """Return the Earthly Branch for a given year."""
    idx = (year - C.CHINESE_ZODIAC_BASE_YEAR) % 12
    return C.EARTHLY_BRANCHES[idx]

# ---------------------------------------------------------------------------
# BaZi (Four Pillars of Destiny) Calculations
# ---------------------------------------------------------------------------

# The Chinese lunar new year typically falls between Jan 21 and Feb 20
# For simplicity, we use the year-based calculation
# A more precise implementation would use the actual lunar new year dates

# Approximate lunar new year dates (month, day) for common years
# This is a simplified approach - a full implementation would use
# the actual Chinese calendar calculations
LUNAR_NEW_YEAR_DATES = {
    2020: (1, 25), 2021: (2, 12), 2022: (2, 1), 2023: (1, 22),
    2024: (2, 10), 2025: (1, 29), 2026: (2, 17), 2027: (2, 6),
    2028: (1, 26), 2029: (2, 13), 2030: (2, 3), 2031: (1, 23),
}


def _lunar_new_year(year: int) -> Tuple[int, int]:
    """Return the (month, day) of Chinese New Year for a given year.

    Uses known dates for recent years, approximates for others.
    """
    if year in LUNAR_NEW_YEAR_DATES:
        return LUNAR_NEW_YEAR_DATES[year]
    # Approximate: Chinese New Year falls between Jan 21 and Feb 20
    # This is a rough approximation
    return (2, 4)  # Default approximation


def chinese_lunar_year(date: datetime) -> int:
    """Return the Chinese lunar year for a given date.

    If the date is before Chinese New Year, it belongs to the previous year.
    """
    month, day = _lunar_new_year(date.year)
    new_year = datetime(date.year, month, day, tzinfo=date.tzinfo)
    if date < new_year:
        return date.year - 1
    return date.year


def bazi_year_pillar(year: int) -> Dict[str, str]:
    """Calculate the Year Pillar (Heavenly Stem and Earthly Branch)."""
    stem = chinese_year_stem(year)
    branch = chinese_year_branch(year)
    return {
        "stem": stem,
        "branch": branch,
        "stem_element": C.HEAVENLY_STEM_PROPERTIES[stem]["element"],
        "stem_polarity": C.HEAVENLY_STEM_PROPERTIES[stem]["polarity"],
        "branch_animal": C.EARTHLY_BRANCH_ANIMAL[branch],
        "branch_element": C.EARTHLY_BRANCH_ELEMENTS[branch],
    }


def bazi_month_pillar(year: int, month: int) -> Dict[str, str]:
    """Calculate the Month Pillar.

    The month branch is fixed by the lunar month.
    The month stem is derived from the year stem.
    """
    # Month branches start from Yin (Tiger) for the first lunar month
    month_branch_idx = (month - 1) % 12
    branch = C.EARTHLY_BRANCHES[month_branch_idx]

    # Month stem is derived from year stem
    year_stem_idx = (year - C.CHINESE_ZODIAC_BASE_YEAR) % 10
    month_stem_idx = (year_stem_idx % 5) * 2 + month_branch_idx
    month_stem_idx = month_stem_idx % 10
    stem = C.HEAVENLY_STEMS[month_stem_idx]

    return {
        "stem": stem,
        "branch": branch,
        "stem_element": C.HEAVENLY_STEM_PROPERTIES[stem]["element"],
        "stem_polarity": C.HEAVENLY_STEM_PROPERTIES[stem]["polarity"],
        "branch_animal": C.EARTHLY_BRANCH_ANIMAL[branch],
        "branch_element": C.EARTHLY_BRANCH_ELEMENTS[branch],
    }


def bazi_day_pillar(jd: float) -> Dict[str, str]:
    """Calculate the Day Pillar from Julian Day.

    The day pillar cycles every 60 days.
    """
    # Reference: January 1, 1900 = Jia-Zi day (stem 0, branch 0)
    ref_jd = 2415020.5  # Jan 1, 1900
    days_since = int(jd - ref_jd)
    stem_idx = days_since % 10
    branch_idx = days_since % 12
    stem = C.HEAVENLY_STEMS[stem_idx]
    branch = C.EARTHLY_BRANCHES[branch_idx]

    return {
        "stem": stem,
        "branch": branch,
        "stem_element": C.HEAVENLY_STEM_PROPERTIES[stem]["element"],
        "stem_polarity": C.HEAVENLY_STEM_PROPERTIES[stem]["polarity"],
        "branch_animal": C.EARTHLY_BRANCH_ANIMAL[branch],
        "branch_element": C.EARTHLY_BRANCH_ELEMENTS[branch],
    }


def bazi_hour_pillar(day_stem_idx: int, hour: int) -> Dict[str, str]:
    """Calculate the Hour Pillar.

    The hour branch is determined by the time of day.
    The hour stem is derived from the day stem.
    """
    # Hour branches: 23-1=Zi, 1-3=Chou, 3-5=Yin, etc.
    hour_branch_idx = (hour + 1) // 2 % 12
    branch = C.EARTHLY_BRANCHES[hour_branch_idx]

    # Hour stem is derived from day stem
    hour_stem_idx = (day_stem_idx % 5) * 2 + hour_branch_idx
    hour_stem_idx = hour_stem_idx % 10
    stem = C.HEAVENLY_STEMS[hour_stem_idx]

    return {
        "stem": stem,
        "branch": branch,
        "stem_element": C.HEAVENLY_STEM_PROPERTIES[stem]["element"],
        "stem_polarity": C.HEAVENLY_STEM_PROPERTIES[stem]["polarity"],
        "branch_animal": C.EARTHLY_BRANCH_ANIMAL[branch],
        "branch_element": C.EARTHLY_BRANCH_ELEMENTS[branch],
    }

# ---------------------------------------------------------------------------
# Chinese Chart Data
# ---------------------------------------------------------------------------

@dataclass
class ChineseChart:
    """A Chinese astrology chart with all computed data."""
    birth_data: BirthData
    year_animal: str
    year_element: str
    year_polarity: str
    year_character: str
    bazi: Dict[str, Dict[str, str]]  # Four pillars
    element_counts: Dict[str, int]
    dominant_element: str
    notes: List[str] = field(default_factory=list)


def calculate_chinese_chart(birth_data: BirthData) -> ChineseChart:
    """Calculate a complete Chinese astrology chart.

    Args:
        birth_data: The native\'s birth data.

    Returns:
        A ChineseChart with all computed Chinese astrology data.
    """
    dt = birth_data.birth_datetime
    year = chinese_lunar_year(dt)

    # Year pillar
    year_animal = chinese_zodiac_animal(year)
    year_element = chinese_zodiac_element(year)
    year_polarity = chinese_zodiac_polarity(year)
    year_character = C.CHINESE_ZODIAC_CHARACTERS[year_animal]

    # Four Pillars (BaZi)
    year_pillar = bazi_year_pillar(year)
    month_pillar = bazi_month_pillar(year, dt.month)

    # Calculate Julian Day for day pillar
    from . import ephemeris as E
    ep = E.get_ephemeris()
    jd = ep.julian_day_ut(birth_data.as_utc())
    day_pillar = bazi_day_pillar(jd)

    # Hour pillar
    day_stem_idx = C.HEAVENLY_STEMS.index(day_pillar["stem"])
    hour_pillar = bazi_hour_pillar(day_stem_idx, dt.hour)

    bazi = {
        "year": year_pillar,
        "month": month_pillar,
        "day": day_pillar,
        "hour": hour_pillar,
    }

    # Count elements
    element_counts = {elem: 0 for elem in C.CHINESE_ELEMENTS}
    for pillar in bazi.values():
        stem_elem = pillar["stem_element"]
        branch_elem = pillar["branch_element"]
        element_counts[stem_elem] = element_counts.get(stem_elem, 0) + 1
        element_counts[branch_elem] = element_counts.get(branch_elem, 0) + 1

    # Find dominant element
    dominant_element = max(element_counts, key=element_counts.get)

    chart = ChineseChart(
        birth_data=birth_data,
        year_animal=year_animal,
        year_element=year_element,
        year_polarity=year_polarity,
        year_character=year_character,
        bazi=bazi,
        element_counts=element_counts,
        dominant_element=dominant_element,
    )

    chart.notes.append(f"Chinese zodiac: {year_polarity} {year_element} {year_animal}")
    chart.notes.append(f"Dominant element: {dominant_element}")
    best_matches = ", ".join(C.CHINESE_ZODIAC_COMPATIBILITY[year_animal])
    chart.notes.append(f"Best compatibility: {best_matches}")

    return chart
