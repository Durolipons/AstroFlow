"""Data models for the AstroFlow engine.

These dataclasses are plain Python objects (no ``swisseph`` dependency) so
they can travel anywhere: in-memory between UI screens, to JSON/Pickle for
profiles, or rendered by the interpretation layer.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

# A timezone can be a zoneinfo.ZoneInfo (preferred) or a plain tzinfo offset.
TzInfo = Union["zoneinfo.ZoneInfo", timezone]


@dataclass
class Location:
    """Geographic birth / event location."""

    latitude: float            # degrees, positive north
    longitude: float           # degrees, positive east
    altitude: float = 0.0      # meters above sea level
    name: str = ""             # free-form place name (e.g. "London")
    country: str = ""          # country name (e.g. "United Kingdom")


@dataclass
class BirthData:
    """Everything needed to compute a natal chart."""

    name: str
    birth_datetime: datetime   # local wall-clock time (naive or aware)
    location: Location
    timezone: Optional[TzInfo] = None          # used if birth_datetime is naive
    house_system: str = "P"                    # single char, e.g. "P" Placidus
    sidereal_mode: Optional[str] = None        # e.g. "Fagan/Bradley" | None → tropical

    # -- derived helpers ---------------------------------------------------
    def as_utc(self) -> datetime:
        """Return the birth moment normalized to UTC.

        Naive datetimes are interpreted in ``self.timezone`` (UTC fallback).
        """
        dt = self.birth_datetime
        if dt.tzinfo is None:
            tz = self.timezone if self.timezone is not None else timezone.utc
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(timezone.utc)


@dataclass
class PlanetPosition:
    """One body's ecliptic position at one moment in time."""

    planet_id: int
    name: str
    longitude: float           # ecliptic longitude, 0..360
    speed: float               # degrees/day (negative = retrograde)
    latitude: float = 0.0      # ecliptic latitude
    distance: float = 0.0      # AU (or arc-seconds for stars)
    house: Optional[int] = None
    sign: str = ""
    sign_degree: float = 0.0   # 0..30 within the sign
    is_retrograde: bool = False

    @property
    def motion(self) -> str:
        """Human-readable motion label: direct / retrograde / stationary."""
        if abs(self.speed) < 0.0001:
            return "stationary"
        return "retrograde" if self.speed < 0 else "direct"


@dataclass
class House:
    """One house cusp."""

    number: int
    longitude: float           # ecliptic longitude of the cusp, 0..360
    sign: str = ""
    sign_degree: float = 0.0


@dataclass
class Aspect:
    """One aspect between two points."""

    planet1_name: str          # e.g. "Transit Saturn" or "Saturn" or "Sun"
    planet2_name: str
    type_name: str             # e.g. "Conjunction"
    angle: float               # exact aspect angle (0/30/45/60/90/120/135/150/180)
    orb: float                 # actual deviation from the exact angle
    separation: float          # actual angular separation in 0..180
    symbol: str = ""
    applying: bool = True

    @property
    def kind(self) -> str:
        """applying / separating / exact for display."""
        if abs(self.orb) < 0.05:
            return "exact"
        return "applying" if self.applying else "separating"


@dataclass
class Chart:
    """A generic chart: natal, progressed, solar-arc directed or transit."""

    chart_type: str                 # "Natal", "Secondary Progression", "Solar Arc", "Transits"
    birth_data: BirthData
    target_title: str               # free-form description of the computed moment
    positions: List[PlanetPosition] = field(default_factory=list)
    houses: List[House] = field(default_factory=list)
    angles: Dict[str, float] = field(default_factory=dict)   # name -> longitude
    aspects: List[Aspect] = field(default_factory=list)
    sidereal: bool = False
    ayanamsa: float = 0.0
    notes: List[str] = field(default_factory=list)


@dataclass
class SolarArcResult:
    """Solar arc direction: the arc plus the directed chart."""

    arc: float                      # degrees (progressed Sun - natal Sun)
    chart: Chart
    progressed_sun: PlanetPosition
    natal_sun: PlanetPosition


@dataclass
class TransitForecast:
    """A transit forecast for one moment."""

    birth_chart: Chart
    transit_chart: Chart            # positions of the outer/current sky
    aspects: List[Aspect]           # transit -> natal aspect list
    target_utc: datetime


def find_position(chart: Chart, name: str) -> Optional[PlanetPosition]:
    """Helper: locate a PlanetPosition in a chart by display name."""
    for p in chart.positions:
        if p.name == name:
            return p
    return None