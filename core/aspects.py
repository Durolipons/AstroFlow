"""Aspect detection logic (UI-agnostic).

Aspects are computed purely from ecliptic longitudes + speeds, so this
module works for natal-natal, transit-natal, and progressed-natal charts
alike. Orbs follow ``constants.ALL_ASPECTS`` and can be tightened per call.
"""

from typing import Iterable, List, Optional

from . import constants as C, utils
from .models import Aspect, PlanetPosition


def shortest_angular_distance(a: float, b: float) -> float:
    """Minimal separation between two longitudes, in 0..180 degrees."""
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def shortest_signed_difference(a: float, b: float) -> float:
    """Signed separation (b - a) mapped into the open interval (-180, 180]."""
    diff = (b - a) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def is_applying(
    lon1: float,
    speed1: float,
    lon2: float,
    speed2: float,
    aspect_angle: float,
) -> bool:
    """True if bodies 1 and 2 are moving *toward* their exact aspect.

    Uses the relative longitudinal velocity projected on the shortest arc
    toward the aspect angle. A positive product ``d * rel_speed < 0`` means
    the separation distance is shrinking, i.e. the aspect is applying.
    """
    sd = shortest_signed_difference(lon1, lon2)
    # Pick the signed target (e.g. +120 if sd is positive, -120 otherwise)
    # so the near-wrap region around 180 behaves correctly.
    target = aspect_angle if sd >= 0 else -aspect_angle
    d = sd - target
    rel = speed2 - speed1
    if abs(d) < 1e-9:
        return False  # already exact -> treated separately elsewhere
    return d * rel < 0


def find_aspects_between(
    points: Iterable[PlanetPosition],
    planets: Optional[List[str]] = None,
    orbs: Optional[dict] = None,
    aspects_defs: Optional[List[C.AspectDef]] = None,
) -> List[Aspect]:
    """Find aspects between all pairs inside one list of positions.

    Args:
        points: PlanetPosition objects.
        planets: optional filter of body names to compare.
        orbs: optional per-aspect-name orb overrides (e.g. {'Conjunction': 10}).
        aspects_defs: subset of aspect definitions to consider.

    Returns:
        A list of Aspect objects sorted by absolute orb (tightest first).
    """
    pts = [p for p in points if planets is None or p.name in planets]
    defs = aspects_defs or C.ALL_ASPECTS
    result: List[Aspect] = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            p, q = pts[i], pts[j]
            sep = shortest_angular_distance(p.longitude, q.longitude)
            for adef in defs:
                orb_limit = (orbs or {}).get(adef.name, adef.orb)
                deviation = sep - adef.angle
                if abs(deviation) <= orb_limit:
                    result.append(
                        Aspect(
                            planet1_name=p.name,
                            planet2_name=q.name,
                            type_name=adef.name,
                            angle=adef.angle,
                            orb=deviation,
                            separation=sep,
                            symbol=adef.symbol,
                            applying=is_applying(
                                p.longitude, p.speed, q.longitude, q.speed,
                                adef.angle,
                            ),
                        )
                    )
    result.sort(key=lambda a: abs(a.orb))
    return result


def find_aspects_between_charts(
    outer_points: Iterable[PlanetPosition],
    natal_points: Iterable[PlanetPosition],
    orbs: Optional[dict] = None,
    aspects_defs: Optional[List[C.AspectDef]] = None,
    suffix: str = "transit",
) -> List[Aspect]:
    """Find aspects from ``outer_points`` (transits/progressions) to natal.

    The first list is treated as the 'active' sky (its names get a
    ``({suffix})`` prefix — e.g. "Saturn (transit)" or, with
    ``suffix="prog"", "Saturn (prog)"), the second as the static
    natal chart. Each outer body can aspect every natal body in turn.
    """
    defs = aspects_defs or C.ALL_ASPECTS
    result: List[Aspect] = []
    for outer in outer_points:
        for natal in natal_points:
            sep = shortest_angular_distance(outer.longitude, natal.longitude)
            for adef in defs:
                orb_limit = (orbs or {}).get(adef.name, adef.orb)
                deviation = sep - adef.angle
                if abs(deviation) <= orb_limit:
                    result.append(
                        Aspect(
                            planet1_name=f"{outer.name} ({suffix})",
                            planet2_name=natal.name,
                            type_name=adef.name,
                            angle=adef.angle,
                            orb=deviation,
                            separation=sep,
                            symbol=adef.symbol,
                            applying=is_applying(
                                outer.longitude, outer.speed,
                                natal.longitude, natal.speed,
                                adef.angle,
                            ),
                        )
                    )
    result.sort(key=lambda a: abs(a.orb))
    return result