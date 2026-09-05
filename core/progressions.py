"""Secondary progressions and solar arc directions.

Secondary progressions (day-for-a-year):
    progressed_jd = natal_jd + (target_jd - natal_jd) / 365.2425

i.e. the planet positions exactly one ephemeris day after birth symbolise
the state one solar year into life. Progressed house cusps / angles are
computed from the progressed sidereal time at the birth location.

Solar arc directions:
    arc = progressed_Sun - natal_Sun   (mod 360)
    directed_point = natal_point + arc (mod 360)

Both methods produce a full ``Chart`` so the aspect engine and the
interpretation layer can be applied unchanged.
"""

from datetime import datetime
from typing import List, Optional, Tuple

from . import aspects as A
from . import constants as C
from . import ephemeris as E
from . import utils
from .chart import _assign_houses, house_of_longitude
from .models import BirthData, Chart, House, PlanetPosition, SolarArcResult

# Length of the tropical year used to convert ephemeris days <-> life years.
SOLAR_YEAR_DAYS = 365.2425


def progressed_jd(natal_jd: float, target_jd: float) -> float:
    """Map a target (life) moment to the 'progressed' ephemeris moment."""
    return natal_jd + (target_jd - natal_jd) / SOLAR_YEAR_DAYS


def secondary_progressions(
    birth_data: BirthData,
    target_date_ut: datetime,
    ephe: Optional[E.Ephemeris] = None,
) -> Chart:
    """Compute the secondary progressed chart for ``target_date_ut``.

    Progressed planets, houses and angles all come from the progressed
    ephemeris moment; aspects are computed between progressed planets.
    """
    ep = ephe or E.get_ephemeris()
    sidereal = birth_data.sidereal_mode is not None

    natal_jd = ep.julian_day_ut(birth_data.as_utc())
    pjd = progressed_jd(natal_jd, ep.julian_day_ut(target_date_ut))

    positions = ep.planet_positions(pjd, sidereal=sidereal)
    houses, angles = ep.houses(
        pjd,
        birth_data.location.latitude,
        birth_data.location.longitude,
        hsys=birth_data.house_system,
        sidereal=sidereal,
    )
    _assign_houses(positions, [h.longitude for h in houses])
    aspects = A.find_aspects_between(positions)

    return Chart(
        chart_type="Secondary Progression",
        birth_data=birth_data,
        target_title=f"Progressed for {target_date_ut:%Y-%m-%d}",
        positions=positions,
        houses=houses,
        angles=angles,
        aspects=aspects,
        sidereal=sidereal,
        ayanamsa=ep.ayanamsa(pjd) if sidereal else 0.0,
    )


def _natal_chart(
    birth_data: BirthData, ephe: E.Ephemeris
) -> Tuple[Chart, bool]:
    """Compute the natal chart lazily inside solar arc (avoids import cycle)."""
    from .chart import calculate_birth_chart  # local import avoids a cycle

    return calculate_birth_chart(birth_data, ephe=ephe), birth_data.sidereal_mode is not None


def solar_arc_directions(
    birth_data: BirthData,
    target_date_ut: datetime,
    ephe: Optional[E.Ephemeris] = None,
) -> SolarArcResult:
    """Direct the natal chart by the solar arc to ``target_date_ut``.

    The arc equals ``progressed Sun - natal Sun`` (mod 360). Every natal
    position -- including the four angles -- is shifted by the arc.
    """
    ep = ephe or E.get_ephemeris()
    natal_chart, sidereal = _natal_chart(birth_data, ep)
    prog = secondary_progressions(birth_data, target_date_ut, ep)

    natal_sun = next(p for p in natal_chart.positions if p.planet_id == C.SUN)
    prog_sun = next(p for p in prog.positions if p.planet_id == C.SUN)
    arc = (prog_sun.longitude - natal_sun.longitude) % 360.0

    directed: List[PlanetPosition] = []
    for p in natal_chart.positions:
        new_lon = (p.longitude + arc) % 360.0
        directed.append(
            PlanetPosition(
                planet_id=p.planet_id,
                name=p.name,
                longitude=new_lon,
                speed=p.speed,               # natal motion retained
                latitude=p.latitude,
                distance=p.distance,
                sign=utils.sign_of(new_lon),
                sign_degree=utils.degree_in_sign(new_lon),
                is_retrograde=p.is_retrograde,
                house=None,                  # reassigned below
            )
        )

    # House cusps and angles are also directed by the same arc.
    natal_cusps = [h.longitude for h in natal_chart.houses]
    directed_cusps = [(lon + arc) % 360.0 for lon in natal_cusps]
    _assign_houses(directed, directed_cusps)

    directed_houses = [
        House(
            number=h.number,
            longitude=(h.longitude + arc) % 360.0,
            sign=utils.sign_of((h.longitude + arc) % 360.0),
            sign_degree=utils.degree_in_sign((h.longitude + arc) % 360.0),
        )
        for h in natal_chart.houses
    ]
    directed_angles = {
        name: (lon + arc) % 360.0 for name, lon in natal_chart.angles.items()
    }

    aspects = A.find_aspects_between(directed)

    chart = Chart(
        chart_type="Solar Arc",
        birth_data=birth_data,
        target_title=f"Solar Arc directed to {target_date_ut:%Y-%m-%d}",
        positions=directed,
        houses=directed_houses,
        angles=directed_angles,
        aspects=aspects,
        sidereal=sidereal,
        ayanamsa=natal_chart.ayanamsa,
    )
    chart.notes.append(f"Solar arc = {arc:.3f} deg")

    return SolarArcResult(
        arc=arc,
        chart=chart,
        progressed_sun=prog_sun,
        natal_sun=natal_sun,
    )