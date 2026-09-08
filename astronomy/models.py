"""Shared astronomy data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Vector3:
    """Cartesian vector."""

    x: float
    y: float
    z: float
    units: str = "au"


@dataclass(frozen=True)
class EquatorialCoordinates:
    """Right ascension / declination pair."""

    ra_hours: float
    dec_degrees: float
    distance_au: float = 0.0


@dataclass(frozen=True)
class EclipticCoordinates:
    """Ecliptic longitude / latitude pair."""

    longitude_degrees: float
    latitude_degrees: float
    radius_au: float = 0.0
    longitude_rate_deg_per_day: float = 0.0


@dataclass(frozen=True)
class AstronomyTimeContext:
    """Same moment expressed in multiple astronomical time systems."""

    source_datetime_utc: datetime
    utc_datetime: datetime
    tt_datetime: Optional[datetime]
    tdb_datetime: Optional[datetime]
    jd_utc: float
    jd_tt: Optional[float]
    jd_tdb: Optional[float]
    delta_t_seconds: Optional[float] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BodyState:
    """High-precision state for one body at one time."""

    body_id: int
    name: str
    heliocentric: Optional[Vector3] = None
    geocentric: Optional[Vector3] = None
    velocity: Optional[Vector3] = None
    equatorial: Optional[EquatorialCoordinates] = None
    ecliptic: Optional[EclipticCoordinates] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AstronomySnapshot:
    """Bundle of body states for one instant."""

    time: AstronomyTimeContext
    bodies: List[BodyState]
    observer: Dict[str, float] = field(default_factory=dict)
    backend_name: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def body_map(self) -> Dict[int, BodyState]:
        """Convenience lookup keyed by Swiss-compatible integer id."""
        return {body.body_id: body for body in self.bodies}


@dataclass(frozen=True)
class SkyPoint:
    """Projected point in the sky viewport."""

    name: str
    x: float
    y: float
    magnitude: float = 0.0
    radius: float = 1.0
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    label: str = ""
    glyph: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkyLine:
    """Projected polyline for sky overlays."""

    name: str
    points: List[Tuple[float, float]]
    color: Tuple[float, float, float] = (0.6, 0.6, 0.9)
    closed: bool = False
    width: float = 1.0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkyLabel:
    """Projected label anchor."""

    text: str
    x: float
    y: float
    color: Tuple[float, float, float] = (0.9, 0.9, 0.95)
    priority: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkyBatch:
    """Flat arrays that can be uploaded to GPU buffers."""

    layer: str
    vertices: List[float]
    colors: List[float]
    sizes: List[float] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkyScene:
    """All projected layers required by the OpenGL sky renderer."""

    width: int
    height: int
    generated_at_utc: datetime
    stars: List[SkyPoint] = field(default_factory=list)
    planets: List[SkyPoint] = field(default_factory=list)
    star_labels: List[SkyLabel] = field(default_factory=list)
    planet_labels: List[SkyLabel] = field(default_factory=list)
    aspect_labels: List[SkyLabel] = field(default_factory=list)
    constellation_labels: List[SkyLabel] = field(default_factory=list)
    horizon_labels: List[SkyLabel] = field(default_factory=list)
    zodiac_labels: List[SkyLabel] = field(default_factory=list)
    aspect_lines: List[SkyLine] = field(default_factory=list)
    milky_way_lines: List[SkyLine] = field(default_factory=list)
    constellation_lines: List[SkyLine] = field(default_factory=list)
    constellation_boundaries: List[SkyLine] = field(default_factory=list)
    zodiac_lines: List[SkyLine] = field(default_factory=list)
    altitude_grid_lines: List[SkyLine] = field(default_factory=list)
    dome_grid_lines: List[SkyLine] = field(default_factory=list)
    planet_trails: List[SkyLine] = field(default_factory=list)
    horizon_line: Optional[SkyLine] = None
    equatorial_line: Optional[SkyLine] = None
    dome_line: Optional[SkyLine] = None
    batches: List[SkyBatch] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
