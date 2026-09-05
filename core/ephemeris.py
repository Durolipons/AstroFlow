"""Swiss Ephemeris wrapper.

This is the ONLY module in the project that imports ``swisseph``. Everything
else in ``core/`` talks to this thin, well-documented API, so the ephemeris
backend could be swapped for another implementation with minimal blast radius.

Key design notes:
  * All computations use UNIVERSAL TIME (UT) internally. Callers convert
    local wall-clock datetimes to UTC via ``BirthData.as_utc()``.
  * If no Swiss Ephemeris data files (``.se1``) are present, pyswisseph
    silently falls back to the built-in Moshier ephemeris, which covers
    planets with ~0.1" precision for 3000 BC - 3000 AD -- plenty for the
    default feature set. Drop the official files into ``core/ephe/`` to get
    full-precision Swiss Ephemeris output.
  * Sidereal calculations use the ``SEFLG_SIDEREAL`` flag per call; the
    ayanamsha mode is selected with ``swe.set_sid_mode``.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import swisseph as swe  # the one and only swisseph import

from . import constants as C, utils
from .models import House, PlanetPosition

# Data files that belong to the Swiss Ephemeris distribution.
_EPHEMERIS_FILE_SUFFIXES = (".se1", ".seas")


class Ephemeris:
    """Thin, stateful wrapper around the Swiss Ephemeris C API."""

    def __init__(
        self,
        ephe_path: Optional[str] = None,
        sidereal_mode: Optional[str] = None,
    ) -> None:
        self.ephe_path: Optional[str] = None
        self._sidereal_mode: Optional[str] = None
        self._topo_cache: Optional[Tuple[float, float, float]] = None
        if ephe_path:
            self.set_ephe_path(ephe_path)
        if sidereal_mode:
            self.set_sidereal_mode(sidereal_mode)

    # -- configuration -----------------------------------------------------
    def set_ephe_path(self, path: str) -> None:
        """Point Swiss Ephemeris at a directory of ``.se1`` data files.

        Only honored when the directory actually contains ephemeris files
        (so an empty or missing dir keeps the Moshier fallback active).
        """
        if not os.path.isdir(path):
            # Keep the safe built-in fallback.
            self.ephe_path = None
            return
        has_files = any(
            f.lower().endswith(_EPHEMERIS_FILE_SUFFIXES)
            for f in os.listdir(path)
        )
        if not has_files:
            self.ephe_path = None
            return
        self.ephe_path = path
        swe.set_ephe_path(path)

    def set_sidereal_mode(self, name: str) -> None:
        """Pick an ayanamsha from ``constants.SIDEREAL_MODES``."""
        if name not in C.SIDEREAL_MODES:
            raise ValueError(
                f"Unknown sidereal mode {name!r}; choose one of "
                f"{sorted(C.SIDEREAL_MODES)}"
            )
        swe.set_sid_mode(getattr(swe, C.SIDEREAL_MODES[name]))
        self._sidereal_mode = name

    def configure(
        self,
        ephe_path: Optional[str] = None,
        sidereal_mode: Optional[str] = None,
    ) -> None:
        """Reconfigure at runtime (used when the user changes settings)."""
        if ephe_path is not None:
            self.set_ephe_path(ephe_path)
        if sidereal_mode is not None:
            self.set_sidereal_mode(sidereal_mode)

    @property
    def sidereal_mode(self) -> Optional[str]:
        return self._sidereal_mode

    def version(self) -> str:
        """Return the Swiss Ephemeris library version string."""
        return swe.version

    # -- time --------------------------------------------------------------
    @staticmethod
    def julian_day_ut(dt_ut: datetime) -> float:
        """Convert a UTC datetime to a Julian Day number (UT)."""
        if dt_ut.tzinfo is None:
            dt_ut = dt_ut.replace(tzinfo=timezone.utc)
        dt_ut = dt_ut.astimezone(timezone.utc)
        fraction = (
            dt_ut.hour
            + dt_ut.minute / 60.0
            + dt_ut.second / 3600.0
            + dt_ut.microsecond / 3_600_000_000.0
        )
        return swe.julday(dt_ut.year, dt_ut.month, dt_ut.day, fraction)
    def delta_t(self, jd_ut: float) -> float:
        """Return Delta T (TT - UT) in days for the given UT Julian day."""
        return swe.deltat(jd_ut)

    def sidereal_time(self, jd_ut: float) -> float:
        """Return apparent sidereal time in degrees (0..360)."""
        return swe.sidtime(jd_ut)

    def ayanamsa(self, jd_ut: float) -> float:
        """Return the current ayanamsha in degrees for the set sidereal mode."""
        return swe.get_ayanamsa_ut(jd_ut)

    # -- planetary positions ----------------------------------------------
    def planet_position(
        self,
        jd_ut: float,
        planet_id: int,
        sidereal: bool = False,
        topocentric: Optional[Tuple[float, float, float]] = None,
        speed: bool = True,
    ) -> PlanetPosition:
        """Compute a single body's ecliptic position at ``jd_ut``.

        Args:
            jd_ut: Julian day, universal time.
            planet_id: Swiss Ephemeris body id (``swe.SUN``, ``swe.MOON``...).
            sidereal: if True, subtracts the configured ayanamsha.
            topocentric: optional (longitude, latitude, altitude) observer.
            speed: if True, request longitudinal speed (used for retrogrades).
        """
        flags = swe.FLG_SPEED if speed else 0
        if sidereal:
            flags |= swe.FLG_SIDEREAL
        if topocentric is not None:
            lon, lat, alt = topocentric
            if self._topo_cache != (lon, lat, alt):
                swe.set_topo(lon, lat, alt)
                self._topo_cache = (lon, lat, alt)
            flags |= swe.FLG_TOPOCTR

        xx, _rf = swe.calc_ut(jd_ut, planet_id, flags)
        lon, lat, dist, lon_speed, _lat_speed, _dist_speed = xx

        name = C.PLANETS.get(planet_id, f"Body#{planet_id}")
        lon = utils.norm360(lon)
        return PlanetPosition(
            planet_id=planet_id,
            name=name,
            longitude=lon,
            speed=lon_speed,
            latitude=lat,
            distance=dist,
            sign=utils.sign_of(lon),
            sign_degree=utils.degree_in_sign(lon),
            is_retrograde=lon_speed < 0,
        )

    def planet_positions(
        self,
        jd_ut: float,
        planet_ids: Optional[List[int]] = None,
        sidereal: bool = False,
        topocentric: Optional[Tuple[float, float, float]] = None,
        speed: bool = True,
        include_chiron: bool = False,
    ) -> List[PlanetPosition]:
        """Compute several bodies for the same moment."""
        ids = list(planet_ids) if planet_ids else list(C.DEFAULT_PLANET_IDS)
        if include_chiron and C.CHIRON not in ids:
            ids.append(C.CHIRON)
        return [
            self.planet_position(jd_ut, pid, sidereal=sidereal,
                                 topocentric=topocentric, speed=speed)
            for pid in ids
        ]

    # -- houses & angles ---------------------------------------------------
    def houses(
        self,
        jd_ut: float,
        latitude: float,
        longitude: float,
        hsys: str = "P",
        sidereal: bool = False,
    ) -> Tuple[List[House], Dict[str, float]]:
        """Compute 12 house cusps and the four main angles.

        Returns:
            (houses, angles) where ``angles`` is a dict with keys
            Ascendant / MC / Descendant / IC (ecliptic longitudes).
        """
        flags = swe.FLG_SIDEREAL if sidereal else 0
        cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude,
                                     hsys.encode("ascii"), flags)

        houses = [
            House(
                number=i + 1,
                longitude=utils.norm360(cusps[i]),
                sign=utils.sign_of(cusps[i]),
                sign_degree=utils.degree_in_sign(cusps[i]),
            )
            for i in range(12)
        ]

        asc = utils.norm360(ascmc[0])
        mc = utils.norm360(ascmc[1])
        angles = {
            "Ascendant": asc,
            "MC": mc,
            "Descendant": utils.norm360(asc + 180.0),
            "IC": utils.norm360(mc + 180.0),
        }
        return houses, angles

    # -- fixed stars -------------------------------------------------------
    def fixed_star(
        self,
        name: str,
        jd_ut: float,
        sidereal: bool = False,
    ) -> PlanetPosition:
        """Compute a fixed star's ecliptic position by name (e.g. 'Sirius')."""
        flags = swe.FLG_SIDEREAL if sidereal else 0
        xx, stnam, _rf = swe.fixstar_ut(name, jd_ut, flags)
        lon = utils.norm360(xx[0])
        return PlanetPosition(
            planet_id=-1,
            name=stnam,
            longitude=lon,
            speed=xx[3],
            latitude=xx[1],
            distance=xx[2],
            sign=utils.sign_of(lon),
            sign_degree=utils.degree_in_sign(lon),
            is_retrograde=False,
        )


# ---------------------------------------------------------------------------
# Default global instance (the Swiss Ephemeris library is process-global, so
# a single shared wrapper is the natural usage pattern).
# ---------------------------------------------------------------------------
_EPHEMERIS = Ephemeris()


def get_ephemeris() -> Ephemeris:
    """Return the shared default wrapper instance."""
    return _EPHEMERIS