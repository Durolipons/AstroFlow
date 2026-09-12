"""Vedic (Jyotish) astrology calculations for AstroFlow.

This module provides Vedic astrology computations including:
- Nakshatra (lunar mansion) calculations
- Vimshottari Dasha (planetary period) calculations
- Vedic aspects (Graha Drishti)
- Vedic chart data (sidereal positions with ayanamsa)

The module uses the existing Swiss Ephemeris wrapper for planetary positions
and applies Vedic-specific calculations on top.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import constants as C
from . import ephemeris as E
from . import utils
from .models import BirthData, PlanetPosition


# ---------------------------------------------------------------------------
# Nakshatra Calculations
# ---------------------------------------------------------------------------

# Each nakshatra spans 13\xb020' (13.333... degrees)
NAKSHATRA_SPAN = 360.0 / 27.0  # 13.333... degrees


def nakshatra_index(longitude: float) -> int:
    """Return the 0-based nakshatra index for a given sidereal longitude."""
    return int(utils.norm360(longitude) / NAKSHATRA_SPAN) % 27


def nakshatra_name(longitude: float) -> str:
    """Return the nakshatra name for a given sidereal longitude."""
    return C.NAKSHATRA_NAMES[nakshatra_index(longitude)]


def nakshatra_pada(longitude: float) -> int:
    """Return the pada (quarter) within the nakshatra (1-4)."""
    within = utils.norm360(longitude) % NAKSHATRA_SPAN
    return int(within / (NAKSHATRA_SPAN / 4.0)) + 1


def nakshatra_ruler(longitude: float) -> str:
    """Return the ruling planet of the nakshatra for a given longitude."""
    return C.NAKSHATRA_RULERS[nakshatra_index(longitude)]


def nakshatra_info(longitude: float) -> Dict[str, any]:
    """Return complete nakshatra information for a given sidereal longitude."""
    idx = nakshatra_index(longitude)
    return {
        "name": C.NAKSHATRA_NAMES[idx],
        "ruler": C.NAKSHATRA_RULERS[idx],
        "pada": nakshatra_pada(longitude),
        "symbol": C.NAKSHATRA_SYMBOLS.get(C.NAKSHATRA_NAMES[idx], ""),
        "index": idx,
    }

# ---------------------------------------------------------------------------
# Vimshottari Dasha Calculations
# ---------------------------------------------------------------------------

def vimshottari_dasha_balance(moon_longitude: float) -> Tuple[str, float]:
    """Calculate the remaining balance of the current dasha at birth.

    Args:
        moon_longitude: Sidereal longitude of the Moon in degrees.

    Returns:
        Tuple of (dasha_ruler, remaining_years) where remaining_years is
        the years left in the current dasha period.
    """
    nak_idx = nakshatra_index(moon_longitude)
    nak_ruler = C.NAKSHATRA_RULERS[nak_idx]
    total_years = C.VIMSHOTTARI_DASHA_YEARS[nak_ruler]

    # Calculate how far through the nakshatra the Moon is
    within_nakshatra = utils.norm360(moon_longitude) % NAKSHATRA_SPAN
    fraction_traversed = within_nakshatra / NAKSHATRA_SPAN
    fraction_remaining = 1.0 - fraction_traversed

    remaining_years = total_years * fraction_remaining
    return nak_ruler, remaining_years


def vimshottari_dasha_sequence(start_ruler: str) -> List[str]:
    """Generate the full Vimshottari dasha sequence starting from a ruler.

    Args:
        start_ruler: The ruling planet of the birth nakshatra.

    Returns:
        List of planet names in dasha order.
    """
    order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    start_idx = order.index(start_ruler)
    return order[start_idx:] + order[:start_idx]


def vimshottari_dasha_periods(start_ruler: str, birth_jd: float) -> List[Dict[str, any]]:
    """Calculate all Vimshottari dasha periods for a birth chart.

    Args:
        start_ruler: The ruling planet of the birth nakshatra.
        birth_jd: Julian day of birth.

    Returns:
        List of dicts with planet, start_jd, end_jd, years for each dasha.
    """
    full_order = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    start_idx = full_order.index(start_ruler)
    ordered = full_order[start_idx:] + full_order[:start_idx]

    periods = []
    current_jd = birth_jd
    for planet in ordered:
        years = C.VIMSHOTTARI_DASHA_YEARS[planet]
        days = years * 365.25
        end_jd = current_jd + days
        periods.append({
            "planet": planet,
            "start_jd": current_jd,
            "end_jd": end_jd,
            "years": years,
        })
        current_jd = end_jd

    return periods


def current_dasha(birth_jd: float, moon_longitude: float, target_jd: float) -> Dict[str, any]:
    """Find the current Vimshottari dasha at a given time.

    Args:
        birth_jd: Julian day of birth.
        moon_longitude: Sidereal longitude of the Moon at birth.
        target_jd: Julian day to find the dasha for.

    Returns:
        Dict with planet, start_jd, end_jd, years, progress (0-1).
    """
    ruler, _ = vimshottari_dasha_balance(moon_longitude)
    periods = vimshottari_dasha_periods(ruler, birth_jd)

    for period in periods:
        if period["start_jd"] <= target_jd < period["end_jd"]:
            span = period["end_jd"] - period["start_jd"]
            progress = (target_jd - period["start_jd"]) / span
            return {**period, "progress": progress}

    # If beyond the 120-year cycle, wrap around
    cycle_days = C.VIMSHOTTARI_TOTAL_YEARS * 365.25
    cycles = (target_jd - birth_jd) / cycle_days
    wrapped_jd = birth_jd + (cycles % 1.0) * cycle_days
    return current_dasha(birth_jd, moon_longitude, wrapped_jd)

# ---------------------------------------------------------------------------
# Vedic Aspects (Graha Drishti)
# ---------------------------------------------------------------------------

@dataclass
class VedicAspect:
    """A Vedic aspect between two planets."""
    planet1: str
    planet2: str
    house_separation: int
    aspect_type: str  # "full" or "special"
    strength: float = 1.0  # Aspect strength (0-1)


def find_vedic_aspects(positions: List[PlanetPosition]) -> List[VedicAspect]:
    """Find Vedic aspects (Graha Drishti) between planets.

    In Vedic astrology, planets aspect specific houses from their position:
    - All planets aspect the 7th house
    - Mars aspects the 4th and 8th houses (in addition to 7th)
    - Jupiter aspects the 5th and 9th houses (in addition to 7th)
    - Saturn aspects the 3rd and 10th houses (in addition to 7th)
    - Rahu/Ketu aspect the 5th and 9th houses (in addition to 7th)
    """
    aspects = []
    planet_houses = {}
    for pos in positions:
        if pos.house is not None:
            planet_houses[pos.name] = pos.house

    for pos in positions:
        if pos.name not in C.VEDIC_ASPECT_HOUSES:
            continue
        if pos.house is None:
            continue

        source_house = pos.house
        for aspect_house_offset in C.VEDIC_ASPECT_HOUSES[pos.name]:
            target_house = ((source_house + aspect_house_offset - 1) % 12) + 1
            for other_pos in positions:
                if other_pos.name == pos.name or other_pos.house is None:
                    continue
                if other_pos.house == target_house:
                    aspects.append(VedicAspect(
                        planet1=pos.name,
                        planet2=other_pos.name,
                        house_separation=aspect_house_offset,
                        aspect_type="special" if aspect_house_offset != 7 else "full",
                    ))
    return aspects

# ---------------------------------------------------------------------------
# Vedic Chart Data
# ---------------------------------------------------------------------------

@dataclass
class VedicChart:
    """A Vedic astrology chart with all computed data."""
    birth_data: BirthData
    positions: List[PlanetPosition]
    houses: List
    angles: Dict[str, float]
    ayanamsa: float
    moon_nakshatra: Dict[str, any]
    sun_nakshatra: Dict[str, any]
    dasha_ruler: str
    dasha_balance: float
    dasha_periods: List[Dict[str, any]]
    vedic_aspects: List[VedicAspect]
    notes: List[str] = field(default_factory=list)
    
    @property
    def planets(self) -> List[PlanetPosition]:
        """Return positions as planets (for compatibility with chart widgets)."""
        return self.positions


def calculate_vedic_chart(birth_data: BirthData, ephe: Optional[E.Ephemeris] = None) -> VedicChart:
    """Calculate a complete Vedic astrology chart.

    Args:
        birth_data: The native\'s birth data.
        ephe: optional custom Ephemeris wrapper.

    Returns:
        A VedicChart with all computed Vedic data.
    """
    ep = ephe or E.get_ephemeris()

    # Use sidereal mode (Lahiri ayanamsa is standard for Vedic)
    sidereal_mode = birth_data.sidereal_mode or "Lahiri"
    ep.set_sidereal_mode(sidereal_mode)

    jd_ut = ep.julian_day_ut(birth_data.as_utc())

    # Calculate sidereal positions
    positions = ep.planet_positions(
        jd_ut, sidereal=True,
        topocentric=(birth_data.location.longitude,
                     birth_data.location.latitude,
                     birth_data.location.altitude)
        if birth_data.location.altitude else None,
    )

    # Calculate houses (Whole Sign is traditional in Vedic, but support others)
    houses, angles = ep.houses(
        jd_ut,
        birth_data.location.latitude,
        birth_data.location.longitude,
        hsys=birth_data.house_system,
        sidereal=True,
    )

    # Assign houses to positions
    from .chart import _assign_houses
    _assign_houses(positions, [h.longitude for h in houses])

    # Calculate ayanamsa
    ayanamsa = ep.ayanamsa(jd_ut)

    # Find Moon and Sun positions for nakshatra
    moon_pos = next((p for p in positions if p.name == "Moon"), None)
    sun_pos = next((p for p in positions if p.name == "Sun"), None)

    moon_nakshatra = nakshatra_info(moon_pos.longitude) if moon_pos else {}
    sun_nakshatra = nakshatra_info(sun_pos.longitude) if sun_pos else {}

    # Calculate Vimshottari Dasha
    if moon_pos:
        dasha_ruler, dasha_balance = vimshottari_dasha_balance(moon_pos.longitude)
        dasha_periods = vimshottari_dasha_periods(dasha_ruler, jd_ut)
    else:
        dasha_ruler = "Unknown"
        dasha_balance = 0.0
        dasha_periods = []

    # Calculate Vedic aspects
    vedic_aspects = find_vedic_aspects(positions)

    chart = VedicChart(
        birth_data=birth_data,
        positions=positions,
        houses=houses,
        angles=angles,
        ayanamsa=ayanamsa,
        moon_nakshatra=moon_nakshatra,
        sun_nakshatra=sun_nakshatra,
        dasha_ruler=dasha_ruler,
        dasha_balance=dasha_balance,
        dasha_periods=dasha_periods,
        vedic_aspects=vedic_aspects,
    )

    chart.notes.append(f"Vedic chart calculated with {sidereal_mode} ayanamsa.")
    chart.notes.append(f"Ayanamsa: {ayanamsa:.4f} degrees")
    nakshatra_name = moon_nakshatra.get('name', 'Unknown')
    chart.notes.append(f"Moon nakshatra: {nakshatra_name}")

    return chart
