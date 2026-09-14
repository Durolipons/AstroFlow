"""Two-chart synastry (relationship compatibility) engine.

UI-agnostic: takes two ``BirthData`` objects, computes both natal charts,
finds cross-chart aspects (A planet -> B planet), maps house overlays
(where A's planets fall in B's houses and vice-versa), compares elemental
temperaments, and rolls a deterministic 0..100 compatibility score.

Cross aspects are labelled ``"Venus (A)"`` vs ``"Mars (B)"`` so the
center-panel report and wheel taps can tell whose planet is whose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import aspects as A
from . import constants as C
from . import ephemeris as E
from .chart import calculate_birth_chart, house_of_longitude
from .models import Aspect, BirthData, Chart


SYNASTRY_BODIES: Tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron",
)

_SYNASTRY_WEIGHTS: Dict[str, float] = {
    "Trine": 3.0, "Sextile": 2.0, "Conjunction": 1.5,
    "Opposition": -2.0, "Square": -2.0, "Quincunx": -1.0,
    "Semisextile": 0.5, "Semisquare": -0.5, "Sesquiquadrate": -0.5,
}

_BONUS_PAIRS = {
    frozenset(("Sun", "Moon")): 2.0,
    frozenset(("Venus", "Mars")): 2.0,
    frozenset(("Venus", "Venus")): 1.5,
    frozenset(("Mars", "Mars")): 1.0,
    frozenset(("Sun", "Sun")): 1.5,
    frozenset(("Moon", "Moon")): 1.5,
}
_SOFTENERS = {"Venus", "Jupiter"}
_HARDENERS = {"Saturn", "Mars", "Pluto"}


@dataclass
class HouseOverlay:
    """One planet of partner X falling in a house of partner Y."""

    planet: str
    from_side: str          # "A" or "B"
    house: int              # 1..12 in the *other* chart
    house_sign: str = ""
    longitude: float = 0.0


@dataclass
class ScoreBreakdown:
    harmony: float = 0.0
    tension: float = 0.0
    chemistry: float = 0.0
    total: float = 0.0


@dataclass
class SynastryResult:
    """Everything the center-panel report needs."""

    chart_a: Chart
    chart_b: Chart
    name_a: str
    name_b: str
    cross_aspects: List[Aspect] = field(default_factory=list)
    overlays_a_in_b: List[HouseOverlay] = field(default_factory=list)
    overlays_b_in_a: List[HouseOverlay] = field(default_factory=list)
    element_counts_a: Dict[str, int] = field(default_factory=dict)
    element_counts_b: Dict[str, int] = field(default_factory=dict)
    breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    overall_score: float = 0.0
    verdict: str = ""









def _strip_side(name: str) -> str:
    if name.endswith(" (A)"):
        return name[: -len(" (A)")].strip()
    if name.endswith(" (B)"):
        return name[: -len(" (B)")].strip()
    return name


def _planet_positions(chart: Chart) -> list:
    return [p for p in chart.positions if p.name in SYNASTRY_BODIES]


def compute_synastry(
    birth_a: BirthData,
    birth_b: BirthData,
    ephe: Optional[E.Ephemeris] = None,
) -> SynastryResult:
    """Compute the full synastry comparison of two birth records."""
    chart_a = calculate_birth_chart(birth_a, ephe=ephe)
    chart_b = calculate_birth_chart(birth_b, ephe=ephe)

    pts_a = _planet_positions(chart_a)
    pts_b = _planet_positions(chart_b)

    raw = A.find_aspects_between_charts(pts_a, pts_b, suffix="A")
    for asp in raw:
        if not asp.planet2_name.endswith(" (B)"):
            asp.planet2_name = f"{asp.planet2_name} (B)"

    cusps_a = [h.longitude for h in chart_a.houses]
    cusps_b = [h.longitude for h in chart_b.houses]
    signs_a = [h.sign for h in chart_a.houses]
    signs_b = [h.sign for h in chart_b.houses]

    overlays_a_in_b: List[HouseOverlay] = []
    for p in pts_a:
        house = house_of_longitude(p.longitude, cusps_b) if cusps_b else None
        if house is None:
            continue
        overlays_a_in_b.append(HouseOverlay(
            planet=p.name, from_side="A", house=house,
            house_sign=signs_b[house - 1] if signs_b else "",
            longitude=p.longitude))
    overlays_b_in_a: List[HouseOverlay] = []
    for p in pts_b:
        house = house_of_longitude(p.longitude, cusps_a) if cusps_a else None
        if house is None:
            continue
        overlays_b_in_a.append(HouseOverlay(
            planet=p.name, from_side="B", house=house,
            house_sign=signs_a[house - 1] if signs_a else "",
            longitude=p.longitude))

    breakdown, overall, verdict = _score(raw)
    return SynastryResult(
        chart_a=chart_a, chart_b=chart_b,
        name_a=birth_a.name or "Person A",
        name_b=birth_b.name or "Person B",
        cross_aspects=raw,
        overlays_a_in_b=overlays_a_in_b,
        overlays_b_in_a=overlays_b_in_a,
        element_counts_a=_element_counts(chart_a),
        element_counts_b=_element_counts(chart_b),
        breakdown=breakdown, overall_score=overall, verdict=verdict)


def _element_counts(chart: Chart) -> Dict[str, int]:
    counts = {"Fire": 0, "Earth": 0, "Air": 0, "Water": 0}
    for p in chart.positions:
        if p.name not in SYNASTRY_BODIES:
            continue
        el = C.ELEMENTS.get(p.sign)
        if el in counts:
            counts[el] += 1
    return counts


def _score(aspects: List[Aspect]) -> Tuple[ScoreBreakdown, float, str]:
    orb_limit = {a.name: a.orb for a in C.ALL_ASPECTS}
    harmony = 0.0
    tension = 0.0
    chemistry = 0.0
    for asp in aspects:
        base = _SYNASTRY_WEIGHTS.get(asp.type_name, 0.0)
        p1 = _strip_side(asp.planet1_name)
        p2 = _strip_side(asp.planet2_name)
        if asp.type_name == "Conjunction":
            if p1 in _SOFTENERS or p2 in _SOFTENERS:
                base = 2.5
            elif p1 in _HARDENERS and p2 in _HARDENERS:
                base = -1.5
            else:
                base = 1.5
        limit = orb_limit.get(asp.type_name, 8.0) or 8.0
        tightness = max(0.0, 1.0 - abs(asp.orb) / limit)
        weighted = base * (0.4 + 0.6 * tightness)
        if weighted >= 0:
            harmony += weighted
        else:
            tension += -weighted
        bonus = _BONUS_PAIRS.get(frozenset((p1, p2)), 0.0)
        if bonus and asp.type_name in (
                "Conjunction", "Trine", "Sextile", "Opposition"):
            chemistry += bonus * (0.4 + 0.6 * tightness)
    total = harmony - tension + chemistry
    overall = max(0.0, min(100.0, 50.0 + total * 2.0))
    if overall >= 80:
        verdict = "Exceptional bond"
    elif overall >= 65:
        verdict = "Harmonious"
    elif overall >= 50:
        verdict = "Workable with growth"
    elif overall >= 35:
        verdict = "Challenging"
    else:
        verdict = "Volatile"
    return (ScoreBreakdown(harmony=round(harmony, 2),
                           tension=round(tension, 2),
                           chemistry=round(chemistry, 2),
                           total=round(total, 2)),
            round(overall, 1), verdict)

