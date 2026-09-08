"""Astrological constants shared across the engine.

All planet IDs are plain integers that intentionally match the Swiss
Ephemeris enum values (``swe.SUN == 0`` ... ``swe.TRUE_NODE == 11``).
Keeping this module free of the ``swisseph`` import guarantees the rest of
the engine stays importable even before the C extension loads.
"""

from typing import Dict, List, NamedTuple

# ---------------------------------------------------------------------------
# Planet identifiers (Swiss Ephemeris enum values)
# ---------------------------------------------------------------------------
SUN = 0
MOON = 1
MERCURY = 2
VENUS = 3
MARS = 4
JUPITER = 5
SATURN = 6
URANUS = 7
NEPTUNE = 8
PLUTO = 9
MEAN_NODE = 10
TRUE_NODE = 11
CHIRON = 15

PLANETS: Dict[int, str] = {
    SUN: "Sun",
    MOON: "Moon",
    MERCURY: "Mercury",
    VENUS: "Venus",
    MARS: "Mars",
    JUPITER: "Jupiter",
    SATURN: "Saturn",
    URANUS: "Uranus",
    NEPTUNE: "Neptune",
    PLUTO: "Pluto",
    MEAN_NODE: "Mean Node",
    TRUE_NODE: "True Node",
    CHIRON: "Chiron",
}

# Default selection used for natal / progressed / transit charts.
DEFAULT_PLANET_IDS: List[int] = [
    SUN, MOON, MERCURY, VENUS, MARS,
    JUPITER, SATURN, URANUS, NEPTUNE, PLUTO,
    MEAN_NODE, TRUE_NODE, CHIRON,
]

# ---------------------------------------------------------------------------
# Zodiac signs
# ---------------------------------------------------------------------------
SIGNS: List[str] = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Glyphs (Unicode) to decorate reports (fall back to SIGNS if font lacks them).
SIGNS_SYMBOLS: List[str] = [
    "\u2648", "\u2649", "\u264a", "\u264b", "\u264c", "\u264d",
    "\u264e", "\u264f", "\u2650", "\u2651", "\u2652", "\u2653",
]

# Three-letter abbreviations, handy for compact tables.
SIGNS_SHORT: List[str] = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis",
]

ELEMENTS: Dict[str, str] = {
    "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
    "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
    "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
    "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water",
}

MODALITIES: Dict[str, str] = {
    "Aries": "Cardinal", "Cancer": "Cardinal", "Libra": "Cardinal", "Capricorn": "Cardinal",
    "Taurus": "Fixed", "Leo": "Fixed", "Scorpio": "Fixed", "Aquarius": "Fixed",
    "Gemini": "Mutable", "Virgo": "Mutable", "Sagittarius": "Mutable", "Pisces": "Mutable",
}

# ---------------------------------------------------------------------------
# Aspects
# ---------------------------------------------------------------------------
class AspectDef(NamedTuple):
    """Definition of one aspect type (name, exact angle, default orb)."""

    name: str
    angle: float      # exact angle in degrees
    orb: float        # default orb in degrees
    symbol: str       # unicode glyph / symbol
    major: bool = True


MAJOR_ASPECTS: List[AspectDef] = [
    AspectDef("Conjunction", 0.0, 8.0, "\u260c"),
    AspectDef("Opposition", 180.0, 8.0, "\u260d"),
    AspectDef("Trine", 120.0, 8.0, "\u25b3"),
    AspectDef("Square", 90.0, 8.0, "\u25a1"),
    AspectDef("Sextile", 60.0, 6.0, "\u26b9"),
]

MINOR_ASPECTS: List[AspectDef] = [
    AspectDef("Quincunx", 150.0, 2.0, "\u2a3f", major=False),
    AspectDef("Semisextile", 30.0, 2.0, "\u26ba", major=False),
    AspectDef("Semisquare", 45.0, 1.0, "\u2220", major=False),
    AspectDef("Sesquiquadrate", 135.0, 1.0, "\u2221", major=False),
]

ALL_ASPECTS: List[AspectDef] = MAJOR_ASPECTS + MINOR_ASPECTS

# ---------------------------------------------------------------------------
# House systems (single-char codes understood by Swiss Ephemeris)
# ---------------------------------------------------------------------------
HOUSE_SYSTEMS: Dict[str, str] = {
    "Placidus": "P",
    "Koch": "K",
    "Whole Sign": "W",
    "Equal (ASC)": "A",
    "Equal (MC)": "X",
    "Regiomontanus": "R",
    "Campanus": "C",
    "Porphyry": "O",
    "Alcabitus": "B",
    "Morinus": "M",
}

# ---------------------------------------------------------------------------
# Sidereal modes -> Swiss Ephemeris constant names (resolved against swisseph)
# ---------------------------------------------------------------------------
SIDEREAL_MODES: Dict[str, str] = {
    "Fagan/Bradley": "SIDM_FAGAN_BRADLEY",
    "Lahiri": "SIDM_LAHIRI",
    "Raman": "SIDM_RAMAN",
    "Krishnamurti": "SIDM_KRISHNAMURTI",
    "Surya Siddhanta": "SIDM_SURYASIDDHANTA",
    "True Citra": "SIDM_TRUE_CITRA",
    "True Mula": "SIDM_TRUE_MULA",
    "True Revati": "SIDM_TRUE_REVATI",
    "True Pushya": "SIDM_TRUE_PUSHYA",
    "J2000": "SIDM_J2000",
    "Hipparchos": "SIDM_HIPPARCHOS",
    "GalCent 0 Sag": "SIDM_GALCENT_0SAG",
    "Sunrise": "SIDM_GALCENT_RGILBRAND",
}