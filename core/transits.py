"""Transit calculations.

A transit is the *current sky* (planets as they are located on some target
date) measured against the fixed natal chart. The engine exposes:

  * ``transit_positions`` -- raw sky positions on the target date,
  * ``transits_to_natal`` -- composite forecast: transit chart + aspects
    (computed with the standard aspect orbs against natal longitudes).
"""

from datetime import datetime, timezone
from typing import List, Optional

from . import aspects as A
from . import constants as C
from . import ephemeris as E
from . import utils
from .chart import _assign_houses
from .models import BirthData, Chart, TransitForecast


def transit_positions(
    target_date_ut: datetime,
    ephe: Optional[E.Ephemeris] = None,
    sidereal: bool = False,
) -> List:
    """Raw ecliptic positions of the planets on ``target_date_ut``."""
    ep = ephe or E.get_ephemeris()
    jd_ut = ep.julian_day_ut(target_date_ut)
    return ep.planet_positions(jd_ut, sidereal=sidereal)


def transit_chart(
    birth_data: BirthData,
    target_date_ut: datetime,
    ephe: Optional[E.Ephemeris] = None,
) -> Chart:
    """A 'transit chart' wheel: sky positions + transiting cusps/angles.

    House cusps are computed for the *birth location* at the transit time,
    which is the standard way forecasts assign transiting houses.
    """
    ep = ephe or E.get_ephemeris()
    sidereal = birth_data.sidereal_mode is not None
    jd_ut = ep.julian_day_ut(target_date_ut)

    positions = ep.planet_positions(jd_ut, sidereal=sidereal)
    houses, angles = ep.houses(
        jd_ut,
        birth_data.location.latitude,
        birth_data.location.longitude,
        hsys=birth_data.house_system,
        sidereal=sidereal,
    )
    _assign_houses(positions, [h.longitude for h in houses])

    chart = Chart(
        chart_type="Transits",
        birth_data=birth_data,
        target_title=f"Transits for {target_date_ut:%Y-%m-%d}",
        positions=positions,
        houses=houses,
        angles=angles,
        aspects=A.find_aspects_between(positions),
        sidereal=sidereal,
        ayanamsa=ep.ayanamsa(jd_ut) if sidereal else 0.0,
    )
    for missing_name in ep.last_missing:
        chart.notes.append(
            f"Ephemeris data unavailable for {missing_name}; position omitted."
        )
    return chart


def transits_to_natal(
    birth_data: BirthData,
    target_date_ut: datetime,
    ephe: Optional[E.Ephemeris] = None,
) -> TransitForecast:
    """Compute transit positions and every transit->natal aspect.

    Returns:
        A TransitForecast with:
          birth_chart  -- the (memorized) natal chart,
          transit_chart-- the current sky,
          aspects      -- transit-to-natal aspect pairs (tightest first).
    """
    from .chart import calculate_birth_chart  # local import avoids a cycle

    ep = ephe or E.get_ephemeris()
    natal = calculate_birth_chart(birth_data, ephe=ep)
    sky = transit_chart(birth_data, target_date_ut, ephe=ep)
    aspects = A.find_aspects_between_charts(sky.positions, natal.positions)

    return TransitForecast(
        birth_chart=natal,
        transit_chart=sky,
        aspects=aspects,
        target_utc=target_date_ut.astimezone(timezone.utc),
    )