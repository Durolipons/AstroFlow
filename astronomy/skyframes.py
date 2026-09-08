"""Pure-Python sky frame helpers (no Astropy required).

These coordinate helpers keep the observer-centred planetarium view and the
Milky Way texture mapping working when Astropy is not installed (e.g. on
lightweight mobile targets such as Huawei phones, where Astropy is often too
heavy).  They use the standard low-precision IAU approximations:

* Greenwich Mean Sidereal Time (IAU 1982)
* Equatorial <-> horizontal (alt-az) conversions
* Equatorial <-> Galactic conversions (north galactic pole, epoch J2000)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional, Tuple

_J2000_JD = 2451545.0
_UNIX_EPOCH_JD = 2440587.5
_SECONDS_PER_DAY = 86400.0

# North galactic pole / galactic node (J2000), used by radec_to_galactic().
GALACTIC_NGP_RA_DEG = 192.8595
GALACTIC_NGP_DEC_DEG = 27.1283
GALACTIC_NODE_LONGITUDE_DEG = 32.932


def julian_day_for(dt: Optional[datetime] = None) -> float:
    """UTC datetime (or now) as a Julian day number."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    else:
        from .timebase import ensure_utc

        dt = ensure_utc(dt)
    return _UNIX_EPOCH_JD + (dt.timestamp() / _SECONDS_PER_DAY)


def gmst_degrees(jd: float) -> float:
    """Greenwich Mean Sidereal Time in degrees (IAU 1982, low precision)."""
    days = jd - _J2000_JD
    centuries = days / 36525.0
    gmst = (
        280.46061837
        + 360.98564736629 * days
        + 0.000387933 * centuries * centuries
        - (centuries ** 3) / 38710000.0
    )
    return gmst % 360.0


def local_sidereal_degrees(jd: float, longitude_degrees: float) -> float:
    """Local Mean Sidereal Time for an east-positive longitude."""
    return (gmst_degrees(jd) + longitude_degrees) % 360.0


def radec_to_altaz(
    ra_hours: float,
    dec_degrees: float,
    latitude_degrees: float,
    longitude_degrees: float,
    jd: float,
) -> Tuple[float, float]:
    """Convert equatorial to horizontal (azimuth from north, altitude)."""
    ha = (math.radians(local_sidereal_degrees(jd, longitude_degrees)) - math.radians((ra_hours % 24.0) * 15.0)) % math.tau
    lat = math.radians(latitude_degrees)
    dec = math.radians(dec_degrees)

    sin_alt = (math.sin(lat) * math.sin(dec)) + (math.cos(lat) * math.cos(dec) * math.cos(ha))
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt = math.degrees(math.asin(sin_alt))
    cos_alt = math.sqrt(max(0.0, 1.0 - (sin_alt * sin_alt)))

    az_sin = (-math.cos(dec) * math.sin(ha)) / max(cos_alt, 1e-12)
    az_cos = (math.sin(dec) - (math.sin(lat) * sin_alt)) / max(cos_alt * math.cos(lat), 1e-12)
    azimuth = math.degrees(math.atan2(az_sin, az_cos)) % 360.0
    return azimuth, alt


def altaz_to_radec(
    azimuth_degrees: float,
    altitude_degrees: float,
    latitude_degrees: float,
    longitude_degrees: float,
    jd: float,
) -> Tuple[float, float]:
    """Convert horizontal to equatorial (returns ra hours, dec degrees)."""
    az = math.radians(azimuth_degrees % 360.0)
    alt = math.radians(max(-90.0, min(90.0, altitude_degrees)))
    lat = math.radians(latitude_degrees)

    sin_dec = (math.sin(lat) * math.sin(alt)) + (math.cos(lat) * math.cos(alt) * math.cos(az))
    sin_dec = max(-1.0, min(1.0, sin_dec))
    dec = math.degrees(math.asin(sin_dec))
    cos_dec = math.sqrt(max(0.0, 1.0 - (sin_dec * sin_dec)))

    ha_sin = (-math.cos(alt) * math.sin(az)) / max(cos_dec, 1e-12)
    ha_cos = (
        (math.sin(alt) * math.cos(lat)) - (math.cos(alt) * math.sin(lat) * math.cos(az))
    ) / max(cos_dec, 1e-12)
    ha_deg = math.degrees(math.atan2(ha_sin, ha_cos)) % 360.0

    lst = local_sidereal_degrees(jd, longitude_degrees)
    ra_deg = (lst - ha_deg) % 360.0
    return ra_deg / 15.0, dec


def radec_to_galactic(ra_hours: float, dec_degrees: float) -> Tuple[float, float]:
    """Equatorial (J2000) to galactic longitude/latitude, both in degrees."""
    ra = math.radians((ra_hours % 24.0) * 15.0)
    dec = math.radians(dec_degrees)
    ra0 = math.radians(GALACTIC_NGP_RA_DEG)
    dec0 = math.radians(GALACTIC_NGP_DEC_DEG)
    delta_ra = ra - ra0

    sin_b = (math.sin(dec0) * math.sin(dec)) + (math.cos(dec0) * math.cos(dec) * math.cos(delta_ra))
    sin_b = max(-1.0, min(1.0, sin_b))
    latitude = math.degrees(math.asin(sin_b))

    y = math.sin(delta_ra)
    x = (math.cos(delta_ra) * math.sin(dec0)) - (math.tan(dec) * math.cos(dec0))
    longitude = (GALACTIC_NODE_LONGITUDE_DEG - math.degrees(math.atan2(x, y))) % 360.0
    return longitude, latitude


def altaz_to_galactic(
    azimuth_degrees: float,
    altitude_degrees: float,
    latitude_degrees: float,
    longitude_degrees: float,
    jd: float,
) -> Tuple[float, float]:
    """Horizontal (observer) to galactic longitude/latitude."""
    ra_hours, dec_degrees = altaz_to_radec(
        azimuth_degrees,
        altitude_degrees,
        latitude_degrees,
        longitude_degrees,
        jd,
    )
    return radec_to_galactic(ra_hours, dec_degrees)


def observer_time_from_metadata(metadata: Optional[dict]):
    """Build an astropy ``Time`` from sky-scene observer metadata.

    Prefers the Julian-day entry (no string parsing pitfalls); falls back to
    the ISO UTC string, which may carry a ``+00:00`` offset that astropy's
    string parser rejects on its own. Returns None when nothing usable is
    available or astropy is missing.
    """
    try:
        from astropy.time import Time
    except ImportError:
        return None

    jd_raw = metadata.get("observer_jd_utc") if metadata else None
    if jd_raw not in (None, ""):
        try:
            return Time(float(jd_raw), format="jd", scale="utc")
        except (TypeError, ValueError):
            pass

    raw = metadata.get("observer_utc") if metadata else None
    if isinstance(raw, datetime):
        return Time(raw, scale="utc")
    if isinstance(raw, str) and raw:
        try:
            return Time(datetime.fromisoformat(raw), scale="utc")
        except ValueError:
            pass
    return None