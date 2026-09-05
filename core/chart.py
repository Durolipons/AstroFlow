"""Birth chart calculation.

Builds a full natal chart: planetary positions, house cusps, the four key
angles (Ascendant / MC / Descendant / IC), and intra-chart aspects.

House assignment follows the classic "in which sign-from-cusp does the
longitude fall" rule and delegates every ephemeris computation to
``core.ephemeris``.
"""

from datetime import datetime
from typing import List, Optional

from . import aspects as A
from . import constants as C
from . import ephemeris as E
from . import utils
from .models import BirthData, Chart, House, PlanetPosition


def house_of_longitude(longitude: float, cusps: List[float]) -> Optional[int]:
    """Return the house number containing ``longitude`` (cusps 1..12).

    The segment between cusp i and cusp i+1 (mod 360, going forward) is
    house i+1. Handles wrap-around across 0° Aries correctly.
    """
    lon = utils.norm360(longitude)
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if start <= end:
            if start <= lon < end:
                return i + 1
        else:  # segment crosses 0° Aries
            if lon >= start or lon < end:
                return i + 1
    return None


def _assign_houses(positions: List[PlanetPosition], cusps: List[float]) -> None:
    """Mutate each position's ``house`` field based on the cusp list."""
    for p in positions:
        p.house = house_of_longitude(p.longitude, cusps)


def calculate_birth_chart(
    birth_data: BirthData,
    ephe: Optional[E.Ephemeris] = None,
) -> Chart:
    """Compute the full natal chart for ``birth_data``.

    Args:
        birth_data: the native's birth data (time, place, zodiac settings).
        ephe: optional custom Ephemeris wrapper (mostly for tests).

    Returns:
        A Chart with chart_type == "Natal".
    """
    ep = ephe or E.get_ephemeris()
    sidereal = birth_data.sidereal_mode is not None

    jd_ut = ep.julian_day_ut(birth_data.as_utc())

    positions = ep.planet_positions(
        jd_ut, sidereal=sidereal,
        topocentric=(birth_data.location.longitude,
                     birth_data.location.latitude,
                     birth_data.location.altitude)
        if birth_data.location.altitude else None,
    )
    houses, angles = ep.houses(
        jd_ut,
        birth_data.location.latitude,
        birth_data.location.longitude,
        hsys=birth_data.house_system,
        sidereal=sidereal,
    )
    _assign_houses(positions, [h.longitude for h in houses])

    aspects = A.find_aspects_between(positions)

    ayanamsa = ep.ayanamsa(jd_ut) if sidereal else 0.0

    chart = Chart(
        chart_type="Natal",
        birth_data=birth_data,
        target_title="Birth Chart",
        positions=positions,
        houses=houses,
        angles=angles,
        aspects=aspects,
        sidereal=sidereal,
        ayanamsa=ayanamsa,
    )
    chart.notes.append(
        "Swiss Ephemeris + Moshier fallback unless .se1 files are provided."
    )
    return chart