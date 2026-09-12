"""Deterministic whole-chart synthesis and forecast ranking.

This module stays intentionally UI-independent. It turns natal, progressed,
solar-arc, transit, and period-sky inputs into ranked, structured facts that
another layer can later weave into narrative text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import aspects as A
from . import constants as C
from . import utils
from .forecast import SignHoroscope
from .models import Aspect, Chart, PlanetPosition, SolarArcResult, TransitForecast

PRINCIPAL_PLANETS: Tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
)
PATTERN_PLANETS: Tuple[str, ...] = PRINCIPAL_PLANETS + ("Chiron",)
LUMINARIES = {"Sun", "Moon"}
ANGULAR_HOUSES = {1, 4, 7, 10}
SUCCEDENT_HOUSES = {2, 5, 8, 11}
CADENT_HOUSES = {3, 6, 9, 12}
PRIMARY_ANGLES = ("Ascendant", "MC")
ALL_ANGLES = ("Ascendant", "MC", "Descendant", "IC")
SUPPORTIVE_ASPECTS = {"Trine", "Sextile"}
CHALLENGING_ASPECTS = {
    "Opposition", "Square", "Quincunx", "Semisquare", "Sesquiquadrate",
}
SIGN_RULERS: Dict[str, str] = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
    "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
    "Libra": "Venus", "Scorpio": "Pluto", "Sagittarius": "Jupiter",
    "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
}
TWELVE_LETTER_ARCHETYPES: Tuple[Tuple[int, str, str, str], ...] = (
    (1, "identity", "Aries", "Mars"),
    (2, "resources", "Taurus", "Venus"),
    (3, "communication", "Gemini", "Mercury"),
    (4, "roots", "Cancer", "Moon"),
    (5, "creativity", "Leo", "Sun"),
    (6, "craft", "Virgo", "Mercury"),
    (7, "partnership", "Libra", "Venus"),
    (8, "transformation", "Scorpio", "Pluto"),
    (9, "meaning", "Sagittarius", "Jupiter"),
    (10, "vocation", "Capricorn", "Saturn"),
    (11, "community", "Aquarius", "Uranus"),
    (12, "retreat", "Pisces", "Neptune"),
)
HOUSE_TRINITIES: Tuple[Tuple[str, str, Tuple[int, int, int]], ...] = (
    ("dharma", "Dharma", (1, 5, 9)),
    ("artha", "Artha", (2, 6, 10)),
    ("kama", "Kama", (3, 7, 11)),
    ("moksha", "Moksha", (4, 8, 12)),
)
_ASPECT_ORBS = {aspect.name: aspect.orb for aspect in C.ALL_ASPECTS}
_TARGET_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})$")


@dataclass
class BalanceFact:
    """One ranked balance bucket."""

    category: str
    key: str
    label: str
    score: float
    contributors: Tuple[str, ...] = ()
    houses: Tuple[int, ...] = ()
    missing: bool = False
    rank: int = 0
    tied: bool = False


@dataclass
class PlanetProminence:
    """How visually/structurally emphatic one planet is in the chart."""

    planet: str
    score: float
    house: Optional[int]
    sign: str
    is_chart_ruler: bool = False
    angular_house: bool = False
    angle_contacts: Tuple[str, ...] = ()
    luminary_aspects: Tuple[str, ...] = ()
    is_retrograde: bool = False
    rank: int = 0
    tied: bool = False


@dataclass
class AspectInsight:
    """One ranked natal aspect emphasis."""

    key: str
    planet1: str
    planet2: str
    type_name: str
    polarity: str
    score: float
    orb: float
    applying: bool
    separation: float
    involves_luminary: bool = False
    involves_chart_ruler: bool = False
    rank: int = 0
    tied: bool = False


@dataclass
class TwelveLetterTheme:
    """Repeated sign-house-ruler motif across the chart."""

    index: int
    label: str
    sign: str
    ruler: str
    score: float
    contributors: Tuple[str, ...] = ()
    retrograde_contributors: Tuple[str, ...] = ()
    rank: int = 0
    tied: bool = False


@dataclass
class AspectPatternFact:
    """Conservative aspect-pattern detection output."""

    pattern_type: str
    score: float
    planets: Tuple[str, ...]
    scope: str = ""
    sign: str = ""
    house: Optional[int] = None
    aspect_types: Tuple[str, ...] = ()
    focal_planet: str = ""
    rank: int = 0
    tied: bool = False


@dataclass
class ChartSynthesis:
    """Structured, ranked natal-chart synthesis data."""

    chart_type: str
    chart_ruler: str
    ascendant_sign: str
    mc_sign: str
    element_balance: List[BalanceFact]
    modality_balance: List[BalanceFact]
    house_trinity_balance: List[BalanceFact]
    planet_prominence: List[PlanetProminence]
    supportive_aspects: List[AspectInsight]
    challenging_aspects: List[AspectInsight]
    aspect_patterns: List[AspectPatternFact]
    twelve_letter_themes: List[TwelveLetterTheme]
    retrograde_planets: Tuple[str, ...]


@dataclass
class TimingTheme:
    """One ranked forecast theme."""

    source: str
    key: str
    label: str
    score: float
    polarity: str = "neutral"
    peak_utc: Optional[datetime] = None
    start_utc: Optional[datetime] = None
    end_utc: Optional[datetime] = None
    active_planets: Tuple[str, ...] = ()
    target_planet: str = ""
    type_name: str = ""
    sign: str = ""
    house: Optional[int] = None
    retrograde: bool = False
    applying: bool = False
    evidence: Tuple[str, ...] = ()
    rank: int = 0
    tied: bool = False


@dataclass
class ForecastSynthesis:
    """Structured, ranked timing themes across forecast families."""

    progression_themes: List[TimingTheme]
    solar_arc_themes: List[TimingTheme]
    transit_themes: List[TimingTheme]
    period_sky_themes: List[TimingTheme]
    highlights: List[TimingTheme]


def analyze_chart(chart: Chart) -> ChartSynthesis:
    """Build deterministic synthesis facts for a natal or natal-like chart."""
    asc_sign = _angle_sign(chart, "Ascendant")
    mc_sign = _angle_sign(chart, "MC")
    chart_ruler = SIGN_RULERS.get(asc_sign, "")
    aspects = _chart_aspects(chart)

    prominence = _planet_prominence(chart, chart_ruler, aspects)
    retrogrades = tuple(p.planet for p in prominence if p.is_retrograde)

    return ChartSynthesis(
        chart_type=chart.chart_type,
        chart_ruler=chart_ruler,
        ascendant_sign=asc_sign,
        mc_sign=mc_sign,
        element_balance=_weighted_sign_balance(chart, "element"),
        modality_balance=_weighted_sign_balance(chart, "modality"),
        house_trinity_balance=_house_trinity_balance(chart),
        planet_prominence=prominence,
        supportive_aspects=_aspect_insights(chart, chart_ruler, aspects, "supportive"),
        challenging_aspects=_aspect_insights(chart, chart_ruler, aspects, "challenging"),
        aspect_patterns=_detect_aspect_patterns(chart, aspects),
        twelve_letter_themes=_twelve_letter_themes(chart, chart_ruler),
        retrograde_planets=retrogrades,
    )


def analyze_forecast(
    natal_chart: Chart,
    progressed_chart: Chart,
    solar_arc: SolarArcResult,
    transit_forecast: TransitForecast,
    sign_horoscope: Optional[SignHoroscope] = None,
) -> ForecastSynthesis:
    """Rank timing themes from progressions, solar arcs, transits, and sky."""
    chart_ruler = SIGN_RULERS.get(_angle_sign(natal_chart, "Ascendant"), "")
    progression = _rank_timing_themes(_progression_themes(
        natal_chart, progressed_chart, chart_ruler
    ))
    solar_arc_themes = _rank_timing_themes(_solar_arc_themes(
        natal_chart, solar_arc, chart_ruler
    ))
    transit = _rank_timing_themes(_transit_themes(
        natal_chart, transit_forecast, chart_ruler
    ))
    sky = _rank_timing_themes(_period_sky_themes(sign_horoscope))

    highlights = _rank_timing_themes([
        replace(theme)
        for theme in progression + solar_arc_themes + transit + sky
    ])

    return ForecastSynthesis(
        progression_themes=progression,
        solar_arc_themes=solar_arc_themes,
        transit_themes=transit,
        period_sky_themes=sky,
        highlights=highlights,
    )


def _angle_sign(chart: Chart, angle_name: str) -> str:
    lon = chart.angles.get(angle_name)
    return utils.sign_of(lon) if lon is not None else ""


def _chart_aspects(chart: Chart) -> List[Aspect]:
    return list(chart.aspects) if chart.aspects else A.find_aspects_between(chart.positions)


def _round_score(score: float) -> float:
    return round(score, 6)


def _base_name(name: str) -> str:
    return name.split(" (", 1)[0]


def _aspect_orb_limit(type_name: str) -> float:
    return float(_ASPECT_ORBS.get(type_name, 1.0))


def _aspect_tightness(aspect: Aspect) -> float:
    limit = _aspect_orb_limit(aspect.type_name)
    if limit <= 0.0:
        return 0.0
    return max(0.0, (limit - abs(aspect.orb)) / limit)


def _is_retrograde(position: PlanetPosition) -> bool:
    return bool(position.is_retrograde or position.speed < 0.0)


def _planet_weight(name: str, include_minor: bool = False) -> float:
    if name in ("Sun", "Moon"):
        return 2.0
    if name in PRINCIPAL_PLANETS:
        return 1.0
    return 0.5 if include_minor else 0.0


def _body_importance(name: str) -> float:
    body = _base_name(name)
    if body in ("Sun", "Moon"):
        return 1.6
    if body in ("Mercury", "Venus", "Mars"):
        return 1.25
    if body in ("Jupiter", "Saturn"):
        return 1.0
    if body in ("Uranus", "Neptune", "Pluto"):
        return 0.8
    return 0.6


def _angle_bonus(angle_name: str, distance: float) -> float:
    if distance > 8.0:
        return 0.0
    primary = angle_name in PRIMARY_ANGLES
    if distance <= 3.0:
        return 2.5 if primary else 2.0
    if distance <= 5.0:
        return 1.5 if primary else 1.0
    return 0.75 if primary else 0.5


def _house_strength(house: Optional[int]) -> float:
    if house in ANGULAR_HOUSES:
        return 4.0
    if house in SUCCEDENT_HOUSES:
        return 2.0
    if house in CADENT_HOUSES:
        return 1.0
    return 0.0


def _aspect_polarity(type_name: str) -> str:
    if type_name in SUPPORTIVE_ASPECTS:
        return "supportive"
    if type_name in CHALLENGING_ASPECTS:
        return "challenging"
    if type_name == "Conjunction":
        return "mixed"
    return "neutral"


def _rank_items(
    items: Sequence[object],
    score_getter,
    sort_key_getter,
) -> List[object]:
    ordered = sorted(
        items,
        key=lambda item: (-score_getter(item), sort_key_getter(item)),
    )
    last_score: Optional[float] = None
    last_rank = 0
    for index, item in enumerate(ordered, start=1):
        score = score_getter(item)
        if last_score is not None and abs(score - last_score) <= 1e-9:
            setattr(item, "rank", last_rank)
            setattr(item, "tied", True)
            setattr(ordered[index - 2], "tied", True)
        else:
            last_rank = index
            setattr(item, "rank", index)
        last_score = score
    return list(ordered)


def _rank_balances(items: Sequence[BalanceFact]) -> List[BalanceFact]:
    return list(_rank_items(items, lambda item: item.score, lambda item: (item.label, item.key)))


def _rank_prominence(items: Sequence[PlanetProminence]) -> List[PlanetProminence]:
    return list(_rank_items(items, lambda item: item.score, lambda item: item.planet))


def _rank_aspects(items: Sequence[AspectInsight]) -> List[AspectInsight]:
    return list(_rank_items(
        items,
        lambda item: item.score,
        lambda item: (item.planet1, item.planet2, item.type_name),
    ))


def _rank_patterns(items: Sequence[AspectPatternFact]) -> List[AspectPatternFact]:
    return list(_rank_items(
        items,
        lambda item: item.score,
        lambda item: (item.pattern_type, item.scope, item.sign, item.house or 0, item.planets),
    ))


def _rank_themes(items: Sequence[TwelveLetterTheme]) -> List[TwelveLetterTheme]:
    return list(_rank_items(items, lambda item: item.score, lambda item: (item.index, item.label)))


def _rank_timing_themes(items: Sequence[TimingTheme]) -> List[TimingTheme]:
    return list(_rank_items(
        items,
        lambda item: item.score,
        lambda item: (
            item.source,
            item.label,
            item.key,
            item.peak_utc.isoformat() if item.peak_utc else "",
        ),
    ))


def _weighted_sign_balance(chart: Chart, dimension: str) -> List[BalanceFact]:
    if dimension == "element":
        labels = ("Fire", "Earth", "Air", "Water")
        resolver = C.ELEMENTS.get
        category = "element_balance"
    else:
        labels = ("Cardinal", "Fixed", "Mutable")
        resolver = C.MODALITIES.get
        category = "modality_balance"

    scores = {label: 0.0 for label in labels}
    contributors: Dict[str, List[str]] = {label: [] for label in labels}

    for pos in chart.positions:
        weight = _planet_weight(pos.name)
        if weight <= 0.0:
            continue
        label = resolver(pos.sign or utils.sign_of(pos.longitude), "")
        if not label:
            continue
        scores[label] += weight
        contributors[label].append(f"{pos.name} in {pos.sign}")

    for angle_name in PRIMARY_ANGLES:
        lon = chart.angles.get(angle_name)
        if lon is None:
            continue
        sign = utils.sign_of(lon)
        label = resolver(sign, "")
        if not label:
            continue
        scores[label] += 1.0
        contributors[label].append(f"{angle_name} in {sign}")

    facts = [
        BalanceFact(
            category=category,
            key=label.lower(),
            label=label,
            score=_round_score(scores[label]),
            contributors=tuple(sorted(contributors[label])),
            missing=scores[label] == 0.0,
        )
        for label in labels
    ]
    return _rank_balances(facts)


def _house_trinity_balance(chart: Chart) -> List[BalanceFact]:
    house_to_key: Dict[int, Tuple[str, str, Tuple[int, int, int]]] = {}
    for key, label, houses in HOUSE_TRINITIES:
        for house in houses:
            house_to_key[house] = (key, label, houses)

    scores = {key: 0.0 for key, _, _ in HOUSE_TRINITIES}
    contributors: Dict[str, List[str]] = {key: [] for key, _, _ in HOUSE_TRINITIES}

    for pos in chart.positions:
        if pos.house not in house_to_key:
            continue
        key, _, _ = house_to_key[pos.house]
        weight = _planet_weight(pos.name, include_minor=True)
        scores[key] += weight
        contributors[key].append(f"{pos.name} H{pos.house}")

    facts = [
        BalanceFact(
            category="house_trinity_balance",
            key=key,
            label=label,
            score=_round_score(scores[key]),
            contributors=tuple(sorted(contributors[key])),
            houses=houses,
            missing=scores[key] == 0.0,
        )
        for key, label, houses in HOUSE_TRINITIES
    ]
    return _rank_balances(facts)


def _planet_prominence(
    chart: Chart,
    chart_ruler: str,
    aspects: Sequence[Aspect],
) -> List[PlanetProminence]:
    luminary_map: Dict[str, List[Aspect]] = {pos.name: [] for pos in chart.positions}
    for aspect in aspects:
        p1 = _base_name(aspect.planet1_name)
        p2 = _base_name(aspect.planet2_name)
        if p2 in LUMINARIES and p1 in luminary_map:
            luminary_map[p1].append(aspect)
        if p1 in LUMINARIES and p2 in luminary_map:
            luminary_map[p2].append(aspect)

    items: List[PlanetProminence] = []
    for pos in chart.positions:
        score = _house_strength(pos.house)
        contacts: List[str] = []
        for angle_name in ALL_ANGLES:
            lon = chart.angles.get(angle_name)
            if lon is None:
                continue
            distance = A.shortest_angular_distance(pos.longitude, lon)
            bonus = _angle_bonus(angle_name, distance)
            if bonus > 0.0:
                score += bonus
                contacts.append(angle_name)
        if pos.name == chart_ruler:
            score += 3.0

        luminary_notes: List[str] = []
        for aspect in sorted(luminary_map.get(pos.name, []), key=lambda item: abs(item.orb)):
            other = _base_name(aspect.planet2_name)
            if other == pos.name:
                other = _base_name(aspect.planet1_name)
            luminary_notes.append(f"{aspect.type_name} {other}")
            score += 1.0 + _aspect_tightness(aspect)

        items.append(PlanetProminence(
            planet=pos.name,
            score=_round_score(score),
            house=pos.house,
            sign=pos.sign or utils.sign_of(pos.longitude),
            is_chart_ruler=pos.name == chart_ruler,
            angular_house=pos.house in ANGULAR_HOUSES,
            angle_contacts=tuple(sorted(set(contacts), key=ALL_ANGLES.index)),
            luminary_aspects=tuple(luminary_notes),
            is_retrograde=_is_retrograde(pos),
        ))

    return _rank_prominence(items)


def _aspect_insights(
    chart: Chart,
    chart_ruler: str,
    aspects: Sequence[Aspect],
    desired_polarity: str,
) -> List[AspectInsight]:
    by_name = {pos.name: pos for pos in chart.positions}
    items: List[AspectInsight] = []
    for aspect in aspects:
        polarity = _aspect_polarity(aspect.type_name)
        if polarity != desired_polarity:
            continue
        p1 = _base_name(aspect.planet1_name)
        p2 = _base_name(aspect.planet2_name)
        involves_luminary = p1 in LUMINARIES or p2 in LUMINARIES
        involves_chart_ruler = chart_ruler in (p1, p2)
        score = 2.0 + (_aspect_tightness(aspect) * 2.0)
        if involves_luminary:
            score += 1.0
        if involves_chart_ruler:
            score += 1.0
        for name in (p1, p2):
            if by_name.get(name) and by_name[name].house in ANGULAR_HOUSES:
                score += 0.5
        if aspect.applying:
            score += 0.25
        items.append(AspectInsight(
            key=f"{desired_polarity}:{p1}:{aspect.type_name}:{p2}",
            planet1=p1,
            planet2=p2,
            type_name=aspect.type_name,
            polarity=polarity,
            score=_round_score(score),
            orb=aspect.orb,
            applying=aspect.applying,
            separation=aspect.separation,
            involves_luminary=involves_luminary,
            involves_chart_ruler=involves_chart_ruler,
        ))
    return _rank_aspects(items)


def _twelve_letter_themes(chart: Chart, chart_ruler: str) -> List[TwelveLetterTheme]:
    by_name = {pos.name: pos for pos in chart.positions}
    themes: List[TwelveLetterTheme] = []

    for index, label, sign, ruler in TWELVE_LETTER_ARCHETYPES:
        score = 0.0
        contributors: List[str] = []
        retro: List[str] = []

        for pos in chart.positions:
            weight = _planet_weight(pos.name, include_minor=True)
            sign_match = (pos.sign or utils.sign_of(pos.longitude)) == sign
            house_match = pos.house == index
            if sign_match:
                score += weight
                note = f"{pos.name} in {sign}"
                contributors.append(note)
                if _is_retrograde(pos):
                    retro.append(note)
            if house_match:
                score += weight
                note = f"{pos.name} in house {index}"
                contributors.append(note)
                if _is_retrograde(pos):
                    retro.append(note)

        for angle_name in PRIMARY_ANGLES:
            lon = chart.angles.get(angle_name)
            if lon is None:
                continue
            angle_sign = utils.sign_of(lon)
            if angle_sign == sign:
                score += 1.0
                contributors.append(f"{angle_name} in {sign}")

        natural_house = next((house for house in chart.houses if house.number == index), None)
        if natural_house is not None:
            cusp_sign = utils.sign_of(natural_house.longitude)
            if cusp_sign == sign:
                score += 0.5
                contributors.append(f"H{index} cusp in {sign}")

        if chart_ruler == ruler and chart_ruler:
            score += 1.0
            contributors.append(f"Chart ruler is {chart_ruler}")

        ruler_pos = by_name.get(chart_ruler) if chart_ruler else None
        if ruler_pos is not None and ruler_pos.house == index:
            score += 1.0
            contributors.append(f"Chart ruler {chart_ruler} in house {index}")
            if _is_retrograde(ruler_pos):
                retro.append(f"Chart ruler {chart_ruler} in house {index}")

        themes.append(TwelveLetterTheme(
            index=index,
            label=label,
            sign=sign,
            ruler=ruler,
            score=_round_score(score),
            contributors=tuple(sorted(contributors)),
            retrograde_contributors=tuple(sorted(retro)),
        ))

    return _rank_themes(themes)


def _eligible_pattern_positions(chart: Chart) -> List[PlanetPosition]:
    return [pos for pos in chart.positions if pos.name in PATTERN_PLANETS]


def _major_aspect_map(aspects: Sequence[Aspect]) -> Dict[Tuple[str, str, str], Aspect]:
    mapping: Dict[Tuple[str, str, str], Aspect] = {}
    for aspect in aspects:
        p1 = _base_name(aspect.planet1_name)
        p2 = _base_name(aspect.planet2_name)
        if aspect.type_name not in {"Trine", "Square", "Opposition"}:
            continue
        key = tuple(sorted((p1, p2)) + [aspect.type_name])  # type: ignore[arg-type]
        mapping[key] = aspect
    return mapping


def _lookup_aspect(
    aspect_map: Dict[Tuple[str, str, str], Aspect],
    name1: str,
    name2: str,
    type_name: str,
) -> Optional[Aspect]:
    return aspect_map.get(tuple(sorted((name1, name2)) + [type_name]))  # type: ignore[arg-type]


def _detect_aspect_patterns(
    chart: Chart,
    aspects: Sequence[Aspect],
) -> List[AspectPatternFact]:
    items: List[AspectPatternFact] = []
    eligible = _eligible_pattern_positions(chart)
    aspect_map = _major_aspect_map(aspects)

    for sign in C.SIGNS:
        group = sorted([pos for pos in eligible if pos.sign == sign], key=lambda pos: pos.name)
        if len(group) >= 3:
            score = (len(group) * 2.0) + (0.5 * sum(1 for pos in group if pos.name in LUMINARIES))
            items.append(AspectPatternFact(
                pattern_type="stellium",
                score=_round_score(score),
                planets=tuple(pos.name for pos in group),
                scope="sign",
                sign=sign,
            ))

    for house in range(1, 13):
        group = sorted(
            [pos for pos in eligible if pos.house == house],
            key=lambda pos: pos.name,
        )
        if len(group) >= 3:
            score = (len(group) * 2.0) + (0.5 if house in ANGULAR_HOUSES else 0.0)
            items.append(AspectPatternFact(
                pattern_type="stellium",
                score=_round_score(score),
                planets=tuple(pos.name for pos in group),
                scope="house",
                house=house,
            ))

    for trio in combinations(eligible, 3):
        if len({C.ELEMENTS.get(pos.sign, "") for pos in trio}) != 1:
            continue
        pair_aspects = [
            _lookup_aspect(aspect_map, trio[0].name, trio[1].name, "Trine"),
            _lookup_aspect(aspect_map, trio[0].name, trio[2].name, "Trine"),
            _lookup_aspect(aspect_map, trio[1].name, trio[2].name, "Trine"),
        ]
        if any(aspect is None for aspect in pair_aspects):
            continue
        score = 6.0 + sum(_aspect_tightness(aspect) for aspect in pair_aspects if aspect) / 3.0 * 2.0
        score += 0.5 * sum(1 for pos in trio if pos.name in LUMINARIES)
        items.append(AspectPatternFact(
            pattern_type="grand_trine",
            score=_round_score(score),
            planets=tuple(sorted(pos.name for pos in trio)),
            aspect_types=("Trine", "Trine", "Trine"),
        ))

    seen_t_squares = set()
    for aspect in aspects:
        if aspect.type_name != "Opposition":
            continue
        a_name = _base_name(aspect.planet1_name)
        b_name = _base_name(aspect.planet2_name)
        a_pos = next((pos for pos in eligible if pos.name == a_name), None)
        b_pos = next((pos for pos in eligible if pos.name == b_name), None)
        if a_pos is None or b_pos is None:
            continue
        for focal in eligible:
            if focal.name in (a_name, b_name):
                continue
            sq1 = _lookup_aspect(aspect_map, a_name, focal.name, "Square")
            sq2 = _lookup_aspect(aspect_map, b_name, focal.name, "Square")
            if sq1 is None or sq2 is None:
                continue
            modalities = {
                C.MODALITIES.get(a_pos.sign, ""),
                C.MODALITIES.get(b_pos.sign, ""),
                C.MODALITIES.get(focal.sign, ""),
            }
            if len(modalities) != 1 or "" in modalities:
                continue
            key = (tuple(sorted((a_name, b_name))), focal.name)
            if key in seen_t_squares:
                continue
            seen_t_squares.add(key)
            score = 6.5 + (_aspect_tightness(aspect) + _aspect_tightness(sq1) + _aspect_tightness(sq2)) / 3.0 * 2.0
            score += 0.5 * sum(1 for name in (a_name, b_name, focal.name) if name in LUMINARIES)
            items.append(AspectPatternFact(
                pattern_type="t_square",
                score=_round_score(score),
                planets=tuple(sorted((a_name, b_name, focal.name))),
                aspect_types=("Opposition", "Square", "Square"),
                focal_planet=focal.name,
            ))

    return _rank_patterns(items)


def _chart_target_utc(chart: Chart) -> Optional[datetime]:
    match = _TARGET_DATE_RE.search(chart.target_title or "")
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _timing_theme_from_aspect(
    aspect: Aspect,
    source: str,
    source_chart: Chart,
    target_utc: Optional[datetime],
    chart_ruler: str,
    source_base: float,
) -> TimingTheme:
    positions = {pos.name: pos for pos in source_chart.positions}
    active_name = _base_name(aspect.planet1_name)
    target_name = _base_name(aspect.planet2_name)
    active = positions.get(active_name)
    score = source_base + (_aspect_tightness(aspect) * 2.25)
    score += _body_importance(active_name)
    score += _body_importance(target_name) * 0.5
    if aspect.applying:
        score += 0.25
    if active is not None and active.house in ANGULAR_HOUSES:
        score += 0.5
    if active_name == chart_ruler or target_name == chart_ruler:
        score += 0.75
    retrograde = _is_retrograde(active) if active is not None else False
    if retrograde:
        score += 0.25

    sign = active.sign if active is not None else ""
    evidence = []
    if sign:
        evidence.append(sign)
    if active is not None and active.house is not None:
        evidence.append(f"H{active.house}")
    evidence.append(aspect.kind)

    return TimingTheme(
        source=source,
        key=f"{source}:{active_name}:{aspect.type_name}:{target_name}",
        label=f"{active_name} {aspect.type_name} {target_name}",
        score=_round_score(score),
        polarity=_aspect_polarity(aspect.type_name),
        peak_utc=target_utc,
        active_planets=(active_name,),
        target_planet=target_name,
        type_name=aspect.type_name,
        sign=sign,
        house=active.house if active is not None else None,
        retrograde=retrograde,
        applying=aspect.applying,
        evidence=tuple(evidence),
    )


def _placement_timing_themes(
    chart: Chart,
    source: str,
    chart_ruler: str,
    target_utc: Optional[datetime],
    base_score: float,
) -> List[TimingTheme]:
    selected: List[str] = []
    for name in ("Moon", "Sun", chart_ruler):
        if name and name not in selected:
            selected.append(name)

    items: List[TimingTheme] = []
    by_name = {pos.name: pos for pos in chart.positions}
    for name in selected:
        pos = by_name.get(name)
        if pos is None:
            continue
        score = base_score + _body_importance(name) + (_house_strength(pos.house) / 2.0)
        if name == chart_ruler:
            score += 0.75
        if _is_retrograde(pos):
            score += 0.25
        evidence = [pos.sign or utils.sign_of(pos.longitude)]
        if pos.house is not None:
            evidence.append(f"H{pos.house}")
        items.append(TimingTheme(
            source=source,
            key=f"{source}:placement:{name}",
            label=f"{name} placement",
            score=_round_score(score),
            polarity="neutral",
            peak_utc=target_utc,
            active_planets=(name,),
            type_name="Placement",
            sign=pos.sign or utils.sign_of(pos.longitude),
            house=pos.house,
            retrograde=_is_retrograde(pos),
            evidence=tuple(evidence),
        ))
    return items


def _progression_themes(
    natal_chart: Chart,
    progressed_chart: Chart,
    chart_ruler: str,
) -> List[TimingTheme]:
    target_utc = _chart_target_utc(progressed_chart)
    aspects = A.find_aspects_between_charts(
        progressed_chart.positions,
        natal_chart.positions,
        suffix="prog",
    )
    items = [
        _timing_theme_from_aspect(
            aspect,
            source="progression",
            source_chart=progressed_chart,
            target_utc=target_utc,
            chart_ruler=chart_ruler,
            source_base=5.0,
        )
        for aspect in aspects
    ]
    items.extend(_placement_timing_themes(
        progressed_chart, "progression", chart_ruler, target_utc, 3.25
    ))
    return items


def _solar_arc_themes(
    natal_chart: Chart,
    solar_arc: SolarArcResult,
    chart_ruler: str,
) -> List[TimingTheme]:
    target_utc = _chart_target_utc(solar_arc.chart)
    aspects = A.find_aspects_between_charts(
        solar_arc.chart.positions,
        natal_chart.positions,
        suffix="arc",
    )
    items = [
        _timing_theme_from_aspect(
            aspect,
            source="solar_arc",
            source_chart=solar_arc.chart,
            target_utc=target_utc,
            chart_ruler=chart_ruler,
            source_base=5.5,
        )
        for aspect in aspects
    ]
    items.extend(_placement_timing_themes(
        solar_arc.chart, "solar_arc", chart_ruler, target_utc, 3.0
    ))
    items.append(TimingTheme(
        source="solar_arc",
        key="solar_arc:arc",
        label="Solar arc magnitude",
        score=_round_score(2.5 + min(3.0, solar_arc.arc / 60.0)),
        polarity="neutral",
        peak_utc=target_utc,
        active_planets=("Sun",),
        type_name="Arc",
        evidence=(f"{solar_arc.arc:.3f} deg",),
    ))
    return items


def _transit_themes(
    natal_chart: Chart,
    forecast: TransitForecast,
    chart_ruler: str,
) -> List[TimingTheme]:
    items = [
        _timing_theme_from_aspect(
            aspect,
            source="transit",
            source_chart=forecast.transit_chart,
            target_utc=forecast.target_utc,
            chart_ruler=chart_ruler,
            source_base=4.5,
        )
        for aspect in forecast.aspects
    ]
    by_name = {pos.name: pos for pos in forecast.transit_chart.positions}
    for name, pos in sorted(by_name.items()):
        if not _is_retrograde(pos):
            continue
        items.append(TimingTheme(
            source="transit",
            key=f"transit:retrograde:{name}",
            label=f"{name} retrograde",
            score=_round_score(3.25 + _body_importance(name)),
            polarity="mixed",
            peak_utc=forecast.target_utc,
            active_planets=(name,),
            type_name="Retrograde",
            sign=pos.sign,
            house=pos.house,
            retrograde=True,
            evidence=tuple(filter(None, [pos.sign, f"H{pos.house}" if pos.house else ""])),
        ))
    return items


def _period_sky_themes(sign_horoscope: Optional[SignHoroscope]) -> List[TimingTheme]:
    if sign_horoscope is None:
        return []

    items: List[TimingTheme] = []
    for eclipse in sign_horoscope.eclipses:
        items.append(TimingTheme(
            source="period_sky",
            key=f"period_sky:eclipse:{eclipse.kind}:{eclipse.peak_utc.isoformat()}",
            label=eclipse.kind,
            score=_round_score(6.0 + {
                "shallow": 0.5,
                "partial": 1.0,
                "deep": 1.5,
            }.get(eclipse.intensity, 0.5)),
            polarity="mixed",
            peak_utc=eclipse.peak_utc,
            start_utc=eclipse.start_utc,
            end_utc=eclipse.end_utc,
            type_name="Eclipse",
            sign=sign_horoscope.sign,
            evidence=(eclipse.intensity,),
        ))

    for idx, lunation in enumerate(sign_horoscope.lunations):
        area = sign_horoscope.lunation_areas.get(idx)
        items.append(TimingTheme(
            source="period_sky",
            key=f"period_sky:lunation:{idx}:{lunation.time_utc.isoformat()}",
            label=lunation.phase,
            score=_round_score(4.75 + min(1.5, 0.35 * len(lunation.aspects))),
            polarity="mixed",
            peak_utc=lunation.time_utc,
            active_planets=("Sun", "Moon"),
            type_name="Lunation",
            sign=lunation.sign,
            house=area,
            evidence=tuple(
                f"{aspect.body}:{aspect.type_name}" for aspect in lunation.aspects
            ),
        ))

    for station in sign_horoscope.stations:
        items.append(TimingTheme(
            source="period_sky",
            key=f"period_sky:station:{station.body}:{station.time_utc.isoformat()}",
            label=f"{station.body} station",
            score=_round_score(4.0 + _body_importance(station.body) + (0.25 if station.going_retrograde else 0.0)),
            polarity="mixed",
            peak_utc=station.time_utc,
            active_planets=(station.body,),
            type_name="Station",
            retrograde=station.going_retrograde,
            evidence=(("retrograde" if station.going_retrograde else "direct"),),
        ))

    for ingress in sign_horoscope.ingresses:
        items.append(TimingTheme(
            source="period_sky",
            key=f"period_sky:ingress:{ingress.body}:{ingress.time_utc.isoformat()}",
            label=f"{ingress.body} ingress",
            score=_round_score(3.0 + _body_importance(ingress.body) + (0.25 if not ingress.entering else 0.0)),
            polarity="neutral",
            peak_utc=ingress.time_utc,
            active_planets=(ingress.body,),
            type_name="Ingress",
            sign=ingress.enters_sign,
            evidence=(ingress.leaves_sign, ingress.enters_sign),
        ))

    for pos in sorted(sign_horoscope.planets_in_sign, key=lambda item: item.name):
        items.append(TimingTheme(
            source="period_sky",
            key=f"period_sky:occupancy:{pos.name}",
            label=f"{pos.name} in {sign_horoscope.sign}",
            score=_round_score(2.0 + _body_importance(pos.name)),
            polarity="neutral",
            peak_utc=sign_horoscope.window_start,
            active_planets=(pos.name,),
            type_name="Occupancy",
            sign=sign_horoscope.sign,
            retrograde=_is_retrograde(pos),
            evidence=(pos.sign or sign_horoscope.sign,),
        ))

    for sign_aspect in sorted(
        sign_horoscope.sign_aspects,
        key=lambda item: (item.body, item.aspect_type),
    ):
        items.append(TimingTheme(
            source="period_sky",
            key=f"period_sky:sign_aspect:{sign_aspect.body}:{sign_aspect.aspect_type}",
            label=f"{sign_aspect.body} {sign_aspect.aspect_type}",
            score=_round_score(1.75 + _body_importance(sign_aspect.body) * 0.5),
            polarity=_aspect_polarity(sign_aspect.aspect_type),
            peak_utc=sign_horoscope.window_start,
            active_planets=(sign_aspect.body,),
            type_name=sign_aspect.aspect_type,
            sign=sign_horoscope.sign,
        ))

    if sign_horoscope.moon_state is not None:
        evidence = [sign_horoscope.moon_state.sign]
        if sign_horoscope.moon_state.next_sign:
            evidence.append(sign_horoscope.moon_state.next_sign)
        items.append(TimingTheme(
            source="period_sky",
            key="period_sky:moon_state",
            label=sign_horoscope.moon_state.phase,
            score=1.5,
            polarity="neutral",
            peak_utc=sign_horoscope.window_start,
            end_utc=sign_horoscope.moon_state.next_ingress_utc,
            active_planets=("Moon",),
            type_name="MoonState",
            sign=sign_horoscope.moon_state.sign,
            evidence=tuple(evidence),
        ))

    return items
