"""Data models for the AstroFlow engine.

These dataclasses are plain Python objects (no ``swisseph`` dependency) so
they can travel anywhere: in-memory between UI screens, to JSON/Pickle for
profiles, or rendered by the interpretation layer.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Union

# A timezone can be a zoneinfo.ZoneInfo (preferred) or a plain tzinfo offset.
TzInfo = Union["zoneinfo.ZoneInfo", timezone]

# Matches a "+HH:MM" / "-HH:MM" UTC offset (as an alternative to float hours).
_OFFSET_RE = re.compile(r"^([+-])(\d{1,2}):(\d{2})$")


def parse_timezone(tz_text: Optional[str]) -> TzInfo:
    """Resolve a timezone from an IANA name or a UTC-offset string.

    Accepts the same inputs the Home form accepts:
      * an IANA zone name  (e.g. "Europe/Berlin", "America/New_York")
      * a UTC offset in hours (e.g. "5.5", "-4", "0")
      * a "+HH:MM" / "-HH:MM" offset
      * "UTC" / "" / None (-> UTC)

    Returns a ``tzinfo`` suitable for attaching to a ``datetime``.
    """
    text = (tz_text or "").strip() or "UTC"
    if text == "UTC":
        return timezone.utc
    # IANA zone names (e.g. "Europe/London") -- zoneinfo rejects offsets like 5.5.
    try:
        import zoneinfo
        return zoneinfo.ZoneInfo(text)
    except Exception:
        pass
    try:
        return timezone(timedelta(hours=float(text)))
    except (ValueError, TypeError):
        pass
    match = _OFFSET_RE.match(text)
    if match:
        sign = 1.0 if match.group(1) == "+" else -1.0
        hours = int(match.group(2))
        minutes = int(match.group(3))
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    return timezone.utc


def _timezone_to_text(tz) -> str:
    """Render a tzinfo as an IANA name, a UTC-offset-in-hours string, or "UTC"."""
    if tz is None:
        return "UTC"
    key = getattr(tz, "key", None)
    if key:
        return key
    off = tz.utcoffset(None)
    if off is None:
        return "UTC"
    hours = off.total_seconds() / 3600.0
    if hours == 0:
        return "UTC"
    return f"{hours:g}"


@dataclass
class Location:
    """Geographic birth / event location."""

    latitude: float            # degrees, positive north
    longitude: float           # degrees, positive east
    altitude: float = 0.0      # meters above sea level
    name: str = ""             # free-form place name (e.g. "London")
    country: str = ""          # country name (e.g. "United Kingdom")

    def to_dict(self) -> dict:
        """Serialize the location to a JSON-compatible mapping."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "name": self.name,
            "country": self.country,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Location":
        """Rebuild a Location from a serialized mapping."""
        data = data or {}
        return cls(
            latitude=data["latitude"],
            longitude=data["longitude"],
            altitude=data.get("altitude", 0.0),
            name=data.get("name", ""),
            country=data.get("country", ""),
        )


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

    # -- serialization -----------------------------------------------------
    @property
    def timezone_text(self) -> str:
        """Timezone of the birth moment as text (IANA name or UTC offset)."""
        return _timezone_to_text(self.timezone or self.birth_datetime.tzinfo)

    def to_dict(self) -> dict:
        """Serialize the birth data to a JSON-compatible mapping.

        The local wall-clock time is stored without a tzinfo and the timezone is
        stored separately, so the value round-trips regardless of the system
        zone database. Only ``BirthData`` is persisted -- natal charts are
        recomputed from it on load.
        """
        return {
            "name": self.name,
            "birth_datetime": self.birth_datetime.replace(tzinfo=None).isoformat(sep=" "),
            "timezone": self.timezone_text,
            "location": self.location.to_dict(),
            "house_system": self.house_system,
            "sidereal_mode": self.sidereal_mode,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "BirthData":
        """Rebuild a ``BirthData`` from a serialized mapping."""
        data = data or {}
        dt = datetime.fromisoformat(data["birth_datetime"])
        tz = parse_timezone(data.get("timezone") or "UTC")
        aware = dt.replace(tzinfo=tz)
        location = Location.from_dict(data.get("location"))
        return cls(
            name=data.get("name", "Native"),
            birth_datetime=aware,
            location=location,
            timezone=None,           # the aware datetime already carries the tz
            house_system=data.get("house_system", "P"),
            sidereal_mode=data.get("sidereal_mode"),
        )


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