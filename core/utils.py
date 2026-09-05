"""Small math / formatting helpers shared by the engine."""

from typing import Tuple

from . import constants as C


def norm360(deg: float) -> float:
    """Normalize an angle into the inclusive-exclusive range [0, 360)."""
    return deg % 360.0


def sign_index(deg: float) -> int:
    """Return 0..11 for the zodiac sign containing ``deg``."""
    return int(norm360(deg) // 30) % 12


def sign_of(deg: float) -> str:
    """Return the sign name (e.g. 'Gemini') containing ``deg``."""
    return C.SIGNS[sign_index(deg)]


def degree_in_sign(deg: float) -> float:
    """Return the 0..30 degree within the sign."""
    return norm360(deg) % 30.0


def dms(deg: float) -> Tuple[int, int, float]:
    """Split a decimal degree into (degrees, minutes, seconds)."""
    deg = abs(float(deg))
    d = int(deg)
    minutes_full = (deg - d) * 60.0
    m = int(minutes_full)
    s = (minutes_full - m) * 60.0
    return d, m, s


def format_dms(deg: float, seconds: bool = True) -> str:
    """Format a decimal degree as e.g. "24°36'12\"" (sign stripped)."""
    d, m, s = dms(deg)
    if seconds:
        return f"{d}\u00b0{m:02d}'{s:04.1f}\""
    return f"{d}\u00b0{m:02d}'"


def format_longitude(deg: float, seconds: bool = True) -> str:
    """Format an ecliptic longitude nicely, e.g. `24°36'12" Gemini`."""
    sign = sign_of(deg)
    within = degree_in_sign(deg)
    return f"{format_dms(within, seconds=seconds)} {sign}"


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres (haversine)."""
    import math

    r = 6371.0  # mean Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))