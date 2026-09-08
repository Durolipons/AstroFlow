"""Build projected sky-scene layers for rendering."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from core import aspects as A
from core import constants as C
from core.models import PlanetPosition

from .catalogs import ConstellationLabel, ConstellationLine, StarRecord, spectral_color
from .models import AstronomySnapshot, EquatorialCoordinates, SkyBatch, SkyLabel, SkyLine, SkyPoint, SkyScene
from .opengl.camera import SkyCamera
from .opengl.projection import project_altaz, project_radec
from .skyframes import radec_to_altaz
from .timebase import julian_day_utc

_PLANET_GLYPHS = {
    "Sun": "\u2609",
    "Moon": "\u263d",
    "Mercury": "\u263f",
    "Venus": "\u2640",
    "Mars": "\u2642",
    "Jupiter": "\u2643",
    "Saturn": "\u2644",
    "Uranus": "\u2645",
    "Neptune": "\u2646",
    "Pluto": "\u2647",
    "Chiron": "\u26b7",
}

_MILKY_WAY_BAND_CACHE = None


def _star_radius(magnitude: float) -> float:
    return max(1.0, min(5.0, 4.8 - magnitude))


def _planet_radius(name: str) -> float:
    if name == "Sun":
        return 7.0
    if name == "Moon":
        return 6.5
    return 4.5


def _planet_color(name: str):
    colors = {
        "Sun": (1.0, 0.82, 0.24),
        "Moon": (0.82, 0.86, 0.94),
        "Mercury": (0.80, 0.74, 0.60),
        "Venus": (0.92, 0.84, 0.68),
        "Mars": (0.86, 0.36, 0.26),
        "Jupiter": (0.90, 0.66, 0.44),
        "Saturn": (0.89, 0.82, 0.55),
        "Uranus": (0.56, 0.84, 0.92),
        "Neptune": (0.36, 0.54, 0.92),
        "Pluto": (0.70, 0.64, 0.82),
        "Chiron": (0.72, 0.68, 0.95),
    }
    return colors.get(name, (0.95, 0.72, 0.20))


def _aspect_color(name: str):
    colors = {
        "Conjunction": (0.98, 0.82, 0.36),
        "Opposition": (0.96, 0.38, 0.42),
        "Trine": (0.38, 0.76, 0.98),
        "Square": (0.96, 0.58, 0.32),
        "Sextile": (0.44, 0.92, 0.72),
    }
    return colors.get(name, (0.84, 0.84, 0.92))


def _zodiac_color(sign_name: str):
    element = C.ELEMENTS.get(sign_name, "")
    if element == "Fire":
        return (0.98, 0.54, 0.24)
    if element == "Earth":
        return (0.80, 0.72, 0.36)
    if element == "Air":
        return (0.44, 0.82, 0.98)
    if element == "Water":
        return (0.36, 0.72, 0.92)
    return (0.78, 0.74, 0.96)


def _reference_star_labels(points: List[SkyPoint]) -> List[SkyLabel]:
    labels = []
    return labels


def _lod_star_budget(camera: SkyCamera, lod_star_limit: int) -> int:
    max_budget = max(24, min(int(lod_star_limit), 180))
    min_budget = min(max_budget, 32)
    zoom_fraction = max(0.0, min(1.0, (150.0 - camera.fov_degrees) / 115.0))
    budget = min_budget + ((max_budget - min_budget) * zoom_fraction)
    return max(24, min(int(lod_star_limit), int(round(budget))))


def _lod_label_budget(camera: SkyCamera, base_limit: int) -> int:
    if camera.fov_degrees <= 50.0:
        return max(base_limit, int(round(base_limit * 1.35)))
    if camera.fov_degrees <= 85.0:
        return base_limit
    if camera.fov_degrees <= 115.0:
        return max(4, int(round(base_limit * 0.75)))
    return max(3, int(round(base_limit * 0.5)))


def _reference_star_labels_for_camera(points: List[SkyPoint], camera: SkyCamera) -> List[SkyLabel]:
    labels = []
    if camera.fov_degrees <= 55.0:
        max_labels = 16
        magnitude_limit = 3.6
    elif camera.fov_degrees <= 80.0:
        max_labels = 12
        magnitude_limit = 3.0
    elif camera.fov_degrees <= 105.0:
        max_labels = 9
        magnitude_limit = 2.3
    else:
        max_labels = 6
        magnitude_limit = 1.4
    for point in sorted(points, key=lambda item: item.magnitude):
        if point.magnitude > magnitude_limit:
            continue
        labels.append(
            SkyLabel(
                text=point.name,
                x=point.x + 6.0,
                y=point.y + 4.0,
                color=point.color,
                priority=1,
                metadata={"layer": "reference-star-labels"},
            )
        )
        if len(labels) >= max_labels:
            break
    return labels


def _estimate_label_size(label: SkyLabel) -> Tuple[float, float]:
    layer = label.metadata.get("layer", "")
    if layer == "constellation-labels":
        font_size = 36.0
    elif layer == "zodiac-labels":
        font_size = 34.0
    elif layer == "horizon-labels":
        font_size = 32.0
    elif layer == "aspect-labels":
        font_size = 28.0
    elif label.priority >= 4:
        font_size = 30.0
    else:
        font_size = 24.0
    return max(26.0, (len(label.text) * font_size * 0.56) + 10.0), font_size + 6.0


def _labels_overlap(first, second) -> bool:
    return not (
        first[0] + first[2] <= second[0]
        or second[0] + second[2] <= first[0]
        or first[1] + first[3] <= second[1]
        or second[1] + second[3] <= first[1]
    )


def _declutter_labels(width: int, height: int, **groups: List[SkyLabel]):
    tagged = []
    group_names = list(groups)
    for group_index, group_name in enumerate(group_names):
        for item_index, label in enumerate(groups[group_name]):
            tagged.append((group_index, item_index, label))
    tagged.sort(key=lambda item: (-item[2].priority, item[0], item[2].y))

    accepted = {group_name: [] for group_name in group_names}
    occupied = []
    for group_index, item_index, label in tagged:
        label_width, label_height = _estimate_label_size(label)
        x = label.x
        y = label.y
        if x > width - 6.0 or y > height - 4.0:
            continue
        if x + label_width < 0.0 or y + label_height < 0.0:
            continue
        bounds = (x - 2.0, y - 2.0, label_width + 4.0, label_height + 4.0)
        if any(_labels_overlap(bounds, existing) for existing in occupied):
            continue
        occupied.append(bounds)
        accepted[group_names[group_index]].append((item_index, label))

    return {
        group_name: [label for _index, label in sorted(items, key=lambda item: item[0])]
        for group_name, items in accepted.items()
    }


def _limit_labels_for_lod(
    labels: List[SkyLabel],
    width: int,
    height: int,
    max_labels: int,
) -> List[SkyLabel]:
    if max_labels <= 0 or len(labels) <= max_labels:
        return labels
    center_x = width * 0.5
    center_y = height * 0.5
    ranked = sorted(
        labels,
        key=lambda label: (
            -label.priority,
            ((label.x - center_x) ** 2) + ((label.y - center_y) ** 2),
            label.text,
        ),
    )
    return ranked[:max_labels]


def _angle_delta(end: float, start: float) -> float:
    return ((end - start + 180.0) % 360.0) - 180.0


def _vector_to_equatorial(vector, snapshot: AstronomySnapshot) -> EquatorialCoordinates:
    try:
        from astropy import units as u
        from astropy.coordinates import CartesianRepresentation, ICRS, SkyCoord

        rep = CartesianRepresentation(vector[0] * u.au, vector[1] * u.au, vector[2] * u.au)
        coord = SkyCoord(rep, frame=ICRS())
        return EquatorialCoordinates(
            ra_hours=float(coord.ra.hour),
            dec_degrees=float(coord.dec.deg),
            distance_au=float(coord.distance.au),
        )
    except Exception:
        x, y, z = vector
        radius = float((x * x + y * y + z * z) ** 0.5)
        ra = (math.degrees(math.atan2(y, x)) % 360.0) / 15.0
        dec = math.degrees(math.atan2(z, math.hypot(x, y)))
        return EquatorialCoordinates(ra_hours=ra, dec_degrees=dec, distance_au=radius)


def _ecliptic_to_equatorial(
    longitude_degrees: float,
    latitude_degrees: float,
    snapshot: Optional[AstronomySnapshot],
) -> EquatorialCoordinates:
    if snapshot is not None:
        try:
            from astropy import units as u
            from astropy.coordinates import GeocentricTrueEcliptic, ICRS, SkyCoord
            from astropy.time import Time

            equinox = Time(snapshot.time.utc_datetime, scale="utc")
            coord = SkyCoord(
                lon=(longitude_degrees % 360.0) * u.deg,
                lat=latitude_degrees * u.deg,
                distance=1.0 * u.au,
                frame=GeocentricTrueEcliptic(equinox=equinox),
            ).transform_to(ICRS())
            return EquatorialCoordinates(
                ra_hours=float(coord.ra.hour),
                dec_degrees=float(coord.dec.deg),
                distance_au=float(coord.distance.au),
            )
        except Exception:
            pass

    return EquatorialCoordinates(
        ra_hours=(longitude_degrees % 360.0) / 15.0,
        dec_degrees=latitude_degrees,
        distance_au=1.0,
    )


def _build_observer_frame(snapshot: Optional[AstronomySnapshot]):
    if snapshot is None or not snapshot.observer:
        return None
    try:
        from astropy import units as u
        from astropy.coordinates import AltAz, EarthLocation
        from astropy.time import Time
    except ImportError:
        return None

    latitude = snapshot.observer.get("latitude", 0.0)
    longitude = snapshot.observer.get("longitude", 0.0)
    altitude = snapshot.observer.get("altitude", 0.0)
    time = Time(snapshot.time.utc_datetime, scale="utc")
    location = EarthLocation.from_geodetic(
        lon=longitude * u.deg,
        lat=latitude * u.deg,
        height=altitude * u.m,
    )
    return AltAz(obstime=time, location=location)


_FRAME_CACHE_LIMIT = 3


class _FrameCache:
    """Bounded per-observer-frame cache with FIFO eviction.

    Each cache owns its own eviction order so dropping an old frame from one
    cache can never disturb the other (a shared order list once let a
    just-created frame dict get evicted, raising a KeyError mid-build).
    """

    def __init__(self, limit: int = _FRAME_CACHE_LIMIT):
        self.limit = limit
        self.store: Dict[tuple, dict] = {}
        self.order: List[tuple] = []

    def frame(self, key: Optional[tuple]) -> dict:
        """Return the (fresh or existing) per-frame cache dict for ``key``."""
        if key is None:
            return {}
        if key not in self.store:
            self.store[key] = {}
            self.order.append(key)
            while len(self.order) > self.limit:
                self.store.pop(self.order.pop(0), None)
        return self.store[key]


_ALTAZ_FRAMES = _FrameCache()
_ECLIPTIC_FRAMES = _FrameCache()

# Equatorial-line sample longitudes (hours of RA at declination 0).
_EQUATOR_SAMPLES: Tuple[float, ...] = tuple(index / 4.0 for index in range(0, 97)) + (24.0,)


def _observer_frame_key(snapshot: Optional[AstronomySnapshot]) -> Optional[tuple]:
    """Stable cache key for an observer frame (time quantised to ~86 seconds)."""
    if snapshot is None or not snapshot.observer:
        return None
    try:
        return (
            round(float(snapshot.time.jd_utc), 3),
            round(float(snapshot.observer.get("latitude", 0.0)), 4),
            round(float(snapshot.observer.get("longitude", 0.0)), 4),
            round(float(snapshot.observer.get("altitude", 0.0)), 2),
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _equatorial_to_altaz(
    ra_hours: float,
    dec_degrees: float,
    snapshot: Optional[AstronomySnapshot],
    observer_frame,
) -> Optional[Tuple[float, float]]:
    """Observer-frame conversion only (no screen projection).

    Returns None when there is no observer location/time, in which case the
    caller falls back to the celestial-chart ``project_radec`` path.
    """
    if observer_frame is not None:
        try:
            from astropy import units as u
            from astropy.coordinates import ICRS, SkyCoord

            coord = SkyCoord(ra=ra_hours * 15.0 * u.deg, dec=dec_degrees * u.deg, frame=ICRS())
            altaz = coord.transform_to(observer_frame)
            return (float(altaz.az.deg), float(altaz.alt.deg))
        except Exception:
            pass
    if snapshot is not None and snapshot.observer:
        try:
            return radec_to_altaz(
                ra_hours,
                dec_degrees,
                float(snapshot.observer.get("latitude", 0.0)),
                float(snapshot.observer.get("longitude", 0.0)),
                snapshot.time.jd_utc,
            )
        except Exception:
            pass
    return None


def _batch_equatorial_to_altaz(
    ra_hours_list: List[float],
    dec_degrees_list: List[float],
    snapshot: Optional[AstronomySnapshot],
    observer_frame,
) -> List[Optional[Tuple[float, float]]]:
    """Vectorised ICRS -> AltAz for many points in one astropy call."""
    if observer_frame is not None:
        try:
            from astropy import units as u
            from astropy.coordinates import ICRS, SkyCoord

            coords = SkyCoord(
                ra=[(ra % 24.0) * 15.0 for ra in ra_hours_list] * u.deg,
                dec=list(dec_degrees_list) * u.deg,
                frame=ICRS(),
            )
            altaz = coords.transform_to(observer_frame)
            return [
                (float(az), float(alt))
                for az, alt in zip(altaz.az.deg.tolist(), altaz.alt.deg.tolist())
            ]
        except Exception:
            pass
    if snapshot is not None and snapshot.observer:
        latitude = float(snapshot.observer.get("latitude", 0.0))
        longitude = float(snapshot.observer.get("longitude", 0.0))
        jd = snapshot.time.jd_utc
        return [
            radec_to_altaz(ra, dec, latitude, longitude, jd)
            for ra, dec in zip(ra_hours_list, dec_degrees_list)
        ]
    return [None] * len(ra_hours_list)


def _batch_ecliptic_to_equatorial(
    longitude_list: List[float],
    latitude_list: List[float],
    snapshot: Optional[AstronomySnapshot],
) -> List[Tuple[float, float]]:
    """Vectorised ecliptic -> equatorial (same tiers as the single-point helper)."""
    if snapshot is not None:
        try:
            from astropy import units as u
            from astropy.coordinates import GeocentricTrueEcliptic, ICRS, SkyCoord
            from astropy.time import Time

            equinox = Time(snapshot.time.utc_datetime, scale="utc")
            coords = SkyCoord(
                lon=[lon % 360.0 for lon in longitude_list] * u.deg,
                lat=list(latitude_list) * u.deg,
                distance=[1.0] * len(longitude_list) * u.au,
                frame=GeocentricTrueEcliptic(equinox=equinox),
            )
            icrs = coords.transform_to(ICRS())
            return [
                (float(ra), float(dec))
                for ra, dec in zip(icrs.ra.hour.tolist(), icrs.dec.deg.tolist())
            ]
        except Exception:
            pass
    return [
        ((longitude % 360.0) / 15.0, latitude)
        for longitude, latitude in zip(longitude_list, latitude_list)
    ]


def _batch_vectors_to_equatorial(vectors, snapshot: Optional[AstronomySnapshot]):
    """Vectorised geocentric cartesian -> ICRS (ra hours, dec degrees)."""
    if vectors:
        try:
            from astropy import units as u
            from astropy.coordinates import CartesianRepresentation, ICRS, SkyCoord

            rep = CartesianRepresentation(
                x=[vector[0] for vector in vectors] * u.au,
                y=[vector[1] for vector in vectors] * u.au,
                z=[vector[2] for vector in vectors] * u.au,
            )
            coords = SkyCoord(rep, frame=ICRS())
            return [
                (float(ra), float(dec))
                for ra, dec in zip(coords.ra.hour.tolist(), coords.dec.deg.tolist())
            ]
        except Exception:
            pass
    results = []
    for vector in vectors:
        eq = _vector_to_equatorial(vector, snapshot)
        results.append((eq.ra_hours, eq.dec_degrees))
    return results


class _DomeProjector:
    """Cached, batched projection of sky positions onto the observer dome.

    The expensive observer-frame conversion (astropy ICRS -> AltAz) runs once
    per unique sky position per observer frame - batched into a single astropy
    transform per rebuild and shared across rebuilds - so camera navigation
    only re-runs the cheap screen projection. This is what keeps dragging the
    sky smooth instead of rebuilding hundreds of astropy transforms per frame.
    """

    def __init__(self, snapshot, observer_frame, width: int, height: int, camera: SkyCamera):
        self.snapshot = snapshot
        self.observer_frame = observer_frame
        self.width = width
        self.height = height
        self.camera = camera
        self.frame_key = _observer_frame_key(snapshot)
        self._altaz = _ALTAZ_FRAMES.frame(self.frame_key)
        self._ecliptic = _ECLIPTIC_FRAMES.frame(self.frame_key)
        self._vector_equatorial: Dict[tuple, Tuple[float, float]] = {}
        self._pending_equatorial: Dict[tuple, Tuple[float, float]] = {}
        self._pending_ecliptic: Dict[tuple, Tuple[float, float]] = {}
        self._pending_vectors: Dict[tuple, tuple] = {}
        self._has_observer = observer_frame is not None or (
            snapshot is not None and bool(snapshot.observer)
        )

    def request_equatorial(self, ra_hours: float, dec_degrees: float) -> None:
        if not self._has_observer:
            return
        ra = float(ra_hours) % 24.0
        dec = float(dec_degrees)
        key = (round(ra, 5), round(dec, 5))
        if key not in self._altaz and key not in self._pending_equatorial:
            self._pending_equatorial[key] = (ra, dec)

    def request_ecliptic(self, longitude_degrees: float, latitude_degrees: float) -> None:
        longitude = float(longitude_degrees) % 360.0
        latitude = float(latitude_degrees)
        key = (round(longitude, 4), round(latitude, 4))
        if key not in self._ecliptic and key not in self._pending_ecliptic:
            self._pending_ecliptic[key] = (longitude, latitude)

    def request_vector(self, vector) -> None:
        x, y, z = (float(vector[0]), float(vector[1]), float(vector[2]))
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key not in self._vector_equatorial and key not in self._pending_vectors:
            self._pending_vectors[key] = (x, y, z)

    def flush(self) -> None:
        """Convert every requested position in as few astropy calls as possible."""
        if self._pending_vectors:
            items = list(self._pending_vectors.items())
            converted = _batch_vectors_to_equatorial(
                [value for _, value in items], self.snapshot
            )
            for (key, _), eq in zip(items, converted):
                self._vector_equatorial[key] = eq
                self.request_equatorial(eq[0], eq[1])
            self._pending_vectors = {}
        if self._pending_ecliptic:
            items = list(self._pending_ecliptic.items())
            converted = _batch_ecliptic_to_equatorial(
                [value[0] for _, value in items],
                [value[1] for _, value in items],
                self.snapshot,
            )
            for (key, _), eq in zip(items, converted):
                self._ecliptic[key] = eq
                self.request_equatorial(eq[0], eq[1])
            self._pending_ecliptic = {}
        if self._pending_equatorial:
            items = list(self._pending_equatorial.items())
            converted = _batch_equatorial_to_altaz(
                [value[0] for _, value in items],
                [value[1] for _, value in items],
                self.snapshot,
                self.observer_frame,
            )
            for (key, _), az_alt in zip(items, converted):
                self._altaz[key] = az_alt
            self._pending_equatorial = {}


    def altaz(self, ra_hours: float, dec_degrees: float) -> Optional[Tuple[float, float]]:
        if not self._has_observer:
            return None
        ra = float(ra_hours) % 24.0
        dec = float(dec_degrees)
        key = (round(ra, 5), round(dec, 5))
        if key in self._altaz:
            return self._altaz[key]
        value = _equatorial_to_altaz(ra, dec, self.snapshot, self.observer_frame)
        self._altaz[key] = value
        return value

    def equatorial_from_ecliptic(self, longitude_degrees: float, latitude_degrees: float):
        longitude = float(longitude_degrees) % 360.0
        latitude = float(latitude_degrees)
        key = (round(longitude, 4), round(latitude, 4))
        if key in self._ecliptic:
            return self._ecliptic[key]
        value = _batch_ecliptic_to_equatorial([longitude], [latitude], self.snapshot)[0]
        self._ecliptic[key] = value
        return value

    def vector_equatorial(self, vector):
        x, y, z = (float(vector[0]), float(vector[1]), float(vector[2]))
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key in self._vector_equatorial:
            return self._vector_equatorial[key]
        value = _batch_vectors_to_equatorial([(x, y, z)], self.snapshot)[0]
        self._vector_equatorial[key] = value
        return value

    def project_altaz(self, azimuth_degrees: float, altitude_degrees: float, cull: bool = True, keep_extreme: bool = False):
        """Project observer alt/az directly to screen (bypasses equatorial conversion)."""
        return _project_view_altaz(
            azimuth_degrees, altitude_degrees, self.camera, self.width, self.height, cull=cull, keep_extreme=keep_extreme,
        )

    def project(self, ra_hours: float, dec_degrees: float, cull: bool = True):
        az_alt = self.altaz(ra_hours, dec_degrees)
        if az_alt is not None:
            return _project_view_altaz(
                az_alt[0], az_alt[1], self.camera, self.width, self.height, cull=cull
            )
        return project_radec(ra_hours, dec_degrees, self.camera, self.width, self.height)

    def project_ecliptic(self, longitude_degrees: float, latitude_degrees: float, cull: bool = True, keep_extreme: bool = False):
        ra_hours, dec_degrees = self.equatorial_from_ecliptic(
            longitude_degrees, latitude_degrees
        )
        az_alt = self.altaz(ra_hours, dec_degrees)
        if az_alt is not None:
            return _project_view_altaz(
                az_alt[0], az_alt[1], self.camera, self.width, self.height,
                cull=cull, keep_extreme=keep_extreme,
            )
        return project_radec(ra_hours, dec_degrees, self.camera, self.width, self.height)

    def project_vector(self, vector):
        ra_hours, dec_degrees = self.vector_equatorial(vector)
        return self.project(ra_hours, dec_degrees)


def _project_ecliptic_to_dome(
    longitude_degrees: float,
    latitude_degrees: float,
    snapshot: Optional[AstronomySnapshot],
    observer_frame,
    width: int,
    height: int,
    camera: SkyCamera,
    projector: Optional[_DomeProjector] = None,
):
    """Single-point ecliptic projection (scene builds use the batched projector)."""
    if projector is not None:
        return projector.project_ecliptic(longitude_degrees, latitude_degrees)
    coord = _ecliptic_to_equatorial(longitude_degrees, latitude_degrees, snapshot)
    return _project_equatorial_to_dome(
        coord.ra_hours,
        coord.dec_degrees,
        snapshot,
        observer_frame,
        width,
        height,
        camera,
    )


def _project_equatorial_to_dome(
    ra_hours: float,
    dec_degrees: float,
    snapshot: Optional[AstronomySnapshot],
    observer_frame,
    width: int,
    height: int,
    camera: SkyCamera,
    projector: Optional[_DomeProjector] = None,
):
    """Project equatorial coordinates through the observer-centred dome.

    Three tiers, in order of preference:

    1. Cached/batched observer-frame conversion (the runtime path - the
       projector converts every sky position once per observer frame).
    2. Pure-Python alt/az conversion (same planetarium feel, no Astropy
       required - important for lightweight/phone targets).
    3. Navigator-friendly celestial-chart fallback (used only when there is
       no observer location/time at all, e.g. headless previews).

    Each tier honours camera pan/zoom, so navigation always works.
    """
    if projector is not None:
        return projector.project(ra_hours, dec_degrees)
    az_alt = _equatorial_to_altaz(ra_hours, dec_degrees, snapshot, observer_frame)
    if az_alt is not None:
        return _project_view_altaz(az_alt[0], az_alt[1], camera, width, height)
    return project_radec(ra_hours, dec_degrees, camera, width, height)


def _project_view_altaz(
    azimuth_degrees: float,
    altitude_degrees: float,
    camera: SkyCamera,
    width: int,
    height: int,
    cull: bool = True,
    keep_extreme: bool = False,
):
    point = project_altaz(
        azimuth_degrees, altitude_degrees, camera, width, height,
        cull_occluded=cull, keep_extreme=keep_extreme,
    )
    if point is None:
        return None
    if not cull:
        # Line builders use this to keep polylines continuous past the widget
        # edges (the canvas is stencil-clipped at draw time).
        return point
    padding_x = width * 0.25
    padding_y = height * 0.25
    if point[0] < -padding_x or point[0] > width + padding_x:
        return None
    if point[1] < -padding_y or point[1] > height + padding_y:
        return None
    return point


def _visible_runs(
    projected: List[Optional[Tuple[float, float]]],
) -> List[Tuple[int, List[Tuple[float, float]]]]:
    """Split a per-sample projection list into contiguous visible runs.

    Unlike :func:`_longest_visible_segment` this keeps **every** visible run
    (not just the longest one), so great-circle lines render as complete arcs
    instead of a single fragment.
    """
    runs: List[Tuple[int, List[Tuple[float, float]]]] = []
    current: List[Tuple[float, float]] = []
    start = 0
    for index, point in enumerate(projected):
        if point is None:
            if len(current) >= 2:
                runs.append((start, current))
            current = []
            continue
        if not current:
            start = index
        current.append(point)
    if len(current) >= 2:
        runs.append((start, current))
    return runs


def _merge_wrapped_runs(
    runs: List[Tuple[int, List[Tuple[float, float]]]],
    total_samples: int,
) -> List[List[Tuple[float, float]]]:
    """Join head/tail runs that wrap around the sample seam (e.g. RA 24->0)."""
    point_runs = [points for _start, points in runs]
    if len(point_runs) >= 2 and runs[0][0] == 0 and (runs[-1][0] + len(runs[-1][1]) == total_samples):
        merged = point_runs[-1] + point_runs[0]
        return [merged] + point_runs[1:-1]
    return point_runs


def _sample_visible_altaz_arc(
    camera: SkyCamera,
    width: int,
    height: int,
    azimuth_samples: List[float],
    altitude_for_azimuth,
    wrap: bool = False,
    cull: bool = True,
) -> List[Tuple[float, float]]:
    samples = list(azimuth_samples)
    if wrap and samples:
        samples = samples + [samples[0] + 360.0]
    projected = [
        _project_view_altaz(
            azimuth,
            altitude_for_azimuth(azimuth % 360.0),
            camera,
            width,
            height,
            cull=cull,
        )
        for azimuth in samples
    ]
    if cull:
        return _longest_visible_segment(projected, wrap=wrap)
    runs = _visible_runs(projected)
    if wrap:
        runs = _merge_wrapped_runs(runs, len(projected))
    if not runs:
        return []
    return max(runs, key=len)


def _sample_visible_altaz_path(
    camera: SkyCamera,
    width: int,
    height: int,
    sample_values: List[float],
    coordinate_for_sample,
) -> List[Tuple[float, float]]:
    projected = []
    for sample in sample_values:
        azimuth, altitude = coordinate_for_sample(sample)
        projected.append(_project_view_altaz(azimuth, altitude, camera, width, height))
    return _longest_visible_segment(projected, wrap=False)


def _longest_visible_segment(points: List[Optional[Tuple[float, float]]], wrap: bool) -> List[Tuple[float, float]]:
    if not points:
        return []
    search_points = points + points[:-1] if wrap else points
    best = []
    current = []
    for point in search_points:
        if point is None:
            if len(current) > len(best):
                best = current[:]
            current = []
            continue
        if current and _distance_sq(current[-1], point) > 50000.0:
            if len(current) > len(best):
                best = current[:]
            current = [point]
            continue
        current.append(point)
    if len(current) > len(best):
        best = current[:]
    return best


def _distance_sq(first: Tuple[float, float], second: Tuple[float, float]) -> float:
    dx = first[0] - second[0]
    dy = first[1] - second[1]
    return (dx * dx) + (dy * dy)


def _build_horizon_line(camera: SkyCamera, width: int, height: int):
    """Build the horizon as a complete geometric circle.

    The horizon is the boundary of the visible hemisphere. In dome space it is
    always a circle; we sample it densely in 3D and project each point, then
    draw every contiguous visible run. This avoids the broken-segment look
    that came from sampling in alt/az (where behind-camera points return None).
    """
    # Sample the horizon circle densely in alt/az (altitude=0 for all azimuths).
    azimuth_samples = [float(a) for a in range(0, 361, 3)]
    projected = [
        _project_view_altaz(az, 0.0, camera, width, height, cull=False)
        for az in azimuth_samples
    ]
    runs = _visible_runs(projected)
    runs = _merge_wrapped_runs(runs, len(projected))
    segments = [points for points in runs if len(points) >= 2]
    if not segments:
        return None
    # Return the longest segment as the primary line (canvas backends handle a
    # single polyline best), but include all segments in metadata so the widget
    # can draw the complete horizon circle.
    longest = max(segments, key=len)
    return SkyLine(
        name="Horizon",
        points=longest,
        color=(0.18, 0.72, 0.40),
        width=1.8,
        metadata={"layer": "horizon", "segments": segments},
    )


def _build_equatorial_line(projector: _DomeProjector, width: int, height: int):
    """Build the celestial equator as a complete great-circle arc.

    The equator is a great circle tilted relative to the horizon. We sample
    it densely in RA, project every point, then return ALL contiguous visible
    runs (not just the longest) so the full arc above the horizon is drawn.
    """
    projected = [
        projector.project(ra_hours % 24.0, 0.0, cull=False)
        for ra_hours in _EQUATOR_SAMPLES
    ]
    runs = _merge_wrapped_runs(_visible_runs(projected), len(projected))
    segments = [points for points in runs if len(points) >= 2]
    if not segments:
        return None
    # Longest segment as the primary line; all segments in metadata.
    longest = max(segments, key=len)
    return SkyLine(
        name="Celestial Equator",
        points=longest,
        color=(0.72, 0.42, 0.94),
        width=1.5,
        metadata={"layer": "equator", "segments": segments},
    )


def _build_milky_way_lines(
    projector: _DomeProjector,
    width: int,
    height: int,
) -> List[SkyLine]:
    layers = _milky_way_band_samples()
    lines = []
    for layer_name, color, width_bias, equatorial_samples in layers:
        projected = []
        for ra_hours, dec_degrees in equatorial_samples:
            point = projector.project(ra_hours, dec_degrees)
            projected.append(point)
        points = _longest_visible_segment(projected, wrap=True)
        if len(points) < 2:
            continue
        lines.append(
            SkyLine(
                name=f"Milky Way {layer_name}",
                points=points,
                color=color,
                width=width_bias,
                metadata={"layer": "milky-way", "band": layer_name, "render_style": "cached-band"},
            )
        )
    return lines


def _milky_way_band_samples():
    global _MILKY_WAY_BAND_CACHE
    if _MILKY_WAY_BAND_CACHE is not None:
        return _MILKY_WAY_BAND_CACHE

    try:
        from astropy import units as u
        from astropy.coordinates import Galactic, ICRS, SkyCoord
    except ImportError:
        _MILKY_WAY_BAND_CACHE = [
            (
                "milky-way-core",
                (0.72, 0.78, 0.98),
                8.0,
                [
                    (18.0, -30.0),
                    (19.5, -20.0),
                    (20.5, -5.0),
                    (21.0, 10.0),
                    (22.0, 25.0),
                    (1.0, 45.0),
                    (4.0, 40.0),
                    (6.0, 20.0),
                    (7.0, 0.0),
                    (8.0, -20.0),
                    (9.0, -35.0),
                ],
            ),
        ]
        return _MILKY_WAY_BAND_CACHE

    layers = [
        ("milky-way-core", 0.0, (0.72, 0.78, 0.98), 8.0),
        ("milky-way-inner", 8.0, (0.58, 0.64, 0.92), 12.0),
        ("milky-way-outer", -8.0, (0.58, 0.64, 0.92), 12.0),
    ]
    cache = []
    for layer_name, latitude_deg, color, width_bias in layers:
        equatorial_samples = []
        for longitude_deg in range(0, 361, 6):
            coord = SkyCoord(
                l=(longitude_deg % 360.0) * u.deg,
                b=latitude_deg * u.deg,
                frame=Galactic(),
            ).transform_to(ICRS())
            equatorial_samples.append((float(coord.ra.hour), float(coord.dec.deg)))
        cache.append((layer_name, color, width_bias, equatorial_samples))
    _MILKY_WAY_BAND_CACHE = cache
    return _MILKY_WAY_BAND_CACHE


def _build_horizon_labels(camera: SkyCamera, width: int, height: int) -> List[SkyLabel]:
    directions = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}
    labels = []
    for text, azimuth in directions.items():
        point = _project_view_altaz(azimuth, 0.0, camera, width, height)
        if point is None:
            continue
        labels.append(
            SkyLabel(
                text=text,
                x=point[0],
                y=point[1] + 6.0,
                color=(0.24, 0.84, 0.52),
                priority=5,
                metadata={"layer": "horizon-labels", "direction": text},
            )
        )
    return labels


def _build_altitude_grid(camera: SkyCamera, width: int, height: int) -> List[SkyLine]:
    lines = []
    for altitude_deg in (15.0, 30.0, 45.0, 60.0, 75.0):
        points = _sample_visible_altaz_arc(
            camera,
            width,
            height,
            [float(azimuth) for azimuth in range(0, 361, 4)],
            lambda _azimuth: altitude_deg,
            wrap=True,
        )
        if len(points) < 2:
            continue
        lines.append(
            SkyLine(
                name=f"Altitude {int(altitude_deg)}",
                points=points,
                color=(0.22, 0.30, 0.44),
                metadata={"layer": "altitude-grid"},
            )
        )
    return lines


def _build_dome_grid(camera: SkyCamera, width: int, height: int) -> List[SkyLine]:
    lines = []
    for azimuth in (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0):
        points = _sample_visible_altaz_path(
            camera,
            width,
            height,
            [float(altitude) for altitude in range(-90, 91, 4)],
            lambda altitude: (azimuth, altitude),
        )
        if len(points) < 2:
            continue
        lines.append(
            SkyLine(
                name=f"Azimuth {int(azimuth)}",
                points=points,
                color=(0.22, 0.26, 0.36),
                metadata={"layer": "dome-grid"},
            )
        )
    return lines


def _build_visible_boundary(camera: SkyCamera, show_horizon: bool, show_dome: bool, width: int, height: int):
    horizon = _build_horizon_line(camera, width, height) if show_horizon else None
    dome = None
    return horizon, dome


def _snapshot_aspects(snapshot: AstronomySnapshot):
    positions = []
    for body in snapshot.bodies:
        if body.ecliptic is None:
            continue
        positions.append(
            PlanetPosition(
                planet_id=body.body_id,
                name=body.name,
                longitude=body.ecliptic.longitude_degrees % 360.0,
                speed=body.ecliptic.longitude_rate_deg_per_day,
                latitude=body.ecliptic.latitude_degrees,
                distance=body.ecliptic.radius_au,
                is_retrograde=body.ecliptic.longitude_rate_deg_per_day < 0.0,
            )
        )
    return A.find_aspects_between(positions, aspects_defs=C.MAJOR_ASPECTS)


def _build_aspect_overlays(snapshot: AstronomySnapshot, planets: List[SkyPoint]):
    visible_lookup = {point.name: point for point in planets}
    aspect_lines = []
    aspect_labels = []
    for aspect in _snapshot_aspects(snapshot):
        start = visible_lookup.get(aspect.planet1_name)
        end = visible_lookup.get(aspect.planet2_name)
        if start is None or end is None:
            continue
        if abs(aspect.orb) > 4.0:
            continue
        color = _aspect_color(aspect.type_name)
        midpoint_x = (start.x + end.x) * 0.5
        midpoint_y = (start.y + end.y) * 0.5
        aspect_lines.append(
            SkyLine(
                name=f"{aspect.planet1_name} {aspect.type_name} {aspect.planet2_name}",
                points=[(start.x, start.y), (end.x, end.y)],
                color=color,
                width=1.2 if aspect.applying else 1.0,
                metadata={
                    "layer": "aspect-lines",
                    "aspect": aspect.type_name,
                    "kind": aspect.kind,
                },
            )
        )
        aspect_labels.append(
            SkyLabel(
                text=aspect.symbol or aspect.type_name[0],
                x=midpoint_x + 4.0,
                y=midpoint_y + 4.0,
                color=color,
                priority=5,
                metadata={"layer": "aspect-labels", "aspect": aspect.type_name},
            )
        )
        if len(aspect_lines) >= 8:
            break
    return aspect_lines, aspect_labels


def _build_zodiac_overlays(
    projector: _DomeProjector,
    width: int,
    height: int,
):
    """Build the zodiac as a symbolic 360° ring.

    The zodiac ring is not an astronomically-precise ecliptic projection (which
    would be a great circle tilted ~23.5° to the equator, half below the horizon
    at any time, giving broken ~180° arcs).  Instead it is a symbolic ring that
    follows the same projection path as the horizon line: a complete 360° circle
    sampled in azimuth at a small altitude offset above the horizon.  This gives
    a clean closed loop with 12 coloured sectors, dividing lines, and sign
    labels — a sidereal astrological dial, not an ecliptic projection.
    """
    zodiac_lines = []
    zodiac_labels = []

    # Sample the ring at a small altitude offset above the horizon.  This
    # follows the same projection path as the horizon line, guaranteeing a
    # complete 360° loop that never breaks at the horizon.
    band_altitude = 8.0
    azimuth_samples = [float(a) for a in range(0, 361, 3)]
    ring_points = [
        projector.project_altaz(az, band_altitude, cull=False, keep_extreme=True)
        for az in azimuth_samples
    ]

    # The 12 signs divide the ring into equal 30° sectors.
    for index, sign_name in enumerate(C.SIGNS):
        start_az = float(index * 30)
        color = _zodiac_color(sign_name)

        # Sample this sign's arc (30° of azimuth) as a thick coloured band.
        arc_samples = [
            projector.project_altaz(start_az + (step * 2.5), band_altitude, cull=False, keep_extreme=True)
            for step in range(13)
        ]
        arc_points = [p for p in arc_samples if p is not None]
        if len(arc_points) >= 2:
            zodiac_lines.append(
                SkyLine(
                    name=sign_name,
                    points=arc_points,
                    color=color,
                    width=8.0,
                    metadata={"layer": "zodiac-sectors", "sign": sign_name},
                )
            )

        # Dividing line at the sign cusp: a short radial spoke from just below
        # the ring up to the ring itself.
        cusp_point = projector.project_altaz(start_az, band_altitude, cull=False, keep_extreme=True)
        inner_point = projector.project_altaz(start_az, band_altitude - 6.0, cull=False, keep_extreme=True)
        if cusp_point is not None and inner_point is not None:
            zodiac_lines.append(
                SkyLine(
                    name=f"{sign_name} boundary",
                    points=[inner_point, cusp_point],
                    color=color,
                    width=1.6,
                    metadata={"layer": "zodiac-boundaries", "sign": sign_name},
                )
            )

        # Sign label at the sector midpoint.
        mid_az = start_az + 15.0
        mid_point = projector.project_altaz(mid_az, band_altitude + 3.0, cull=False, keep_extreme=True)
        if mid_point is not None:
            zodiac_labels.append(
                SkyLabel(
                    text=f"{sign_name} {C.SIGNS_SYMBOLS[index]}",
                    x=mid_point[0],
                    y=mid_point[1],
                    color=color,
                    priority=4,
                    metadata={"layer": "zodiac-labels", "sign": sign_name},
                )
            )

    # The complete ring outline: a thin line tracing the full 360° loop.
    # With keep_extreme=True every sample projects to a valid screen point,
    # so the ring is drawn as one continuous closed loop (first point
    # repeated at the end).
    ring_valid = [p for p in ring_points if p is not None]
    if len(ring_valid) >= 2:
        ring_closed = ring_valid + [ring_valid[0]]
        zodiac_lines.append(
            SkyLine(
                name="Zodiac Ring",
                points=ring_closed,
                color=(0.62, 0.58, 0.96),
                width=1.1,
                metadata={"layer": "zodiac-ring"},
            )
        )

    return zodiac_lines, zodiac_labels


def _point_batch(layer: str, points: List[SkyPoint]) -> SkyBatch:
    vertices = []
    colors = []
    sizes = []
    for point in points:
        vertices.extend([point.x, point.y])
        colors.extend(list(point.color))
        sizes.append(point.radius)
    return SkyBatch(layer=layer, vertices=vertices, colors=colors, sizes=sizes)


def _line_batch(layer: str, lines: List[SkyLine]) -> SkyBatch:
    vertices = []
    colors = []
    sizes = []
    for line in lines:
        for x, y in line.points:
            vertices.extend([x, y])
            colors.extend(list(line.color))
            sizes.append(line.width)
    return SkyBatch(layer=layer, vertices=vertices, colors=colors, sizes=sizes)


def _planet_trails(
    projector: _DomeProjector,
    width: int,
    height: int,
) -> List[SkyLine]:
    trails = []
    for body in projector.snapshot.bodies:
        if body.geocentric is None or body.velocity is None:
            continue
        if body.geocentric.units != "au" or body.velocity.units != "au/day":
            continue
        trail_points = []
        for offset in (-0.4, -0.2, 0.0, 0.2, 0.4):
            vector = (
                body.geocentric.x + body.velocity.x * offset,
                body.geocentric.y + body.velocity.y * offset,
                body.geocentric.z + body.velocity.z * offset,
            )
            point = projector.project_vector(vector)
            if point is not None:
                trail_points.append(point)
        if len(trail_points) >= 2:
            trails.append(
                SkyLine(
                    name=f"{body.name} trail",
                    points=trail_points,
                    color=_planet_color(body.name),
                    width=1.2,
                    metadata={"layer": "planet-trails"},
                )
            )
    return trails


def build_sky_scene(
    width: int,
    height: int,
    camera: SkyCamera,
    snapshot: Optional[AstronomySnapshot] = None,
    stars: Iterable[StarRecord] = (),
    constellation_lines: Iterable[ConstellationLine] = (),
    constellation_labels: Iterable[ConstellationLabel] = (),
    constellation_boundaries: Iterable[ConstellationLine] = (),
    show_constellations: bool = True,
    show_constellation_labels: bool = False,
    show_constellation_boundaries: bool = False,
    show_horizon: bool = True,
    show_horizon_labels: bool = True,
    show_equator: bool = True,
    show_zodiac: bool = True,
    show_dome: bool = True,
    show_milky_way: bool = True,
    show_grid: bool = False,
    show_star_names: bool = False,
    show_planet_labels: bool = True,
    show_planet_trails: bool = True,
    show_aspects: bool = True,
    max_star_magnitude: float = 6.0,
    lod_star_limit: int = 3000,
) -> SkyScene:
    """Project an observer-centered sky sphere into a navigable planetarium view."""
    star_points: List[SkyPoint] = []
    star_labels: List[SkyLabel] = []
    star_lookup: Dict[str, SkyPoint] = {}
    observer_frame = _build_observer_frame(snapshot)
    projector = _DomeProjector(snapshot, observer_frame, width, height, camera)
    visible_star_limit = _lod_star_budget(camera, max(24, lod_star_limit))
    lod_culled_stars = 0
    ordered_stars = sorted(stars, key=lambda item: item.magnitude)

    # Queue every sky position up-front so the observer-frame conversion runs
    # as a couple of batched transforms per rebuild instead of hundreds of
    # per-point astropy calls - this is what keeps panning/zooming smooth.
    for star in ordered_stars:
        if star.magnitude <= max_star_magnitude:
            projector.request_equatorial(star.ra_hours, star.dec_degrees)
    if show_constellation_labels:
        for label in constellation_labels:
            projector.request_equatorial(label.ra_hours, label.dec_degrees)
    if snapshot is not None:
        for body in snapshot.bodies:
            if body.equatorial is not None:
                projector.request_equatorial(
                    body.equatorial.ra_hours, body.equatorial.dec_degrees
                )
    if show_equator:
        for ra_hours in _EQUATOR_SAMPLES:
            projector.request_equatorial(ra_hours, 0.0)
    if show_zodiac:
        # Pre-seed the ecliptic grid used by the ring/sector/spoke/label
        # builders so one batched transform covers the whole ring.
        for step in range(145):
            projector.request_ecliptic(step * 2.5, 0.0)
        for index in range(len(C.SIGNS)):
            start_longitude = float(index * 30)
            projector.request_ecliptic(start_longitude, -8.0)
            projector.request_ecliptic(start_longitude, 8.0)
            projector.request_ecliptic(start_longitude + 15.0, 6.5)
    if snapshot is not None and show_planet_trails:
        for body in snapshot.bodies:
            if body.geocentric is None or body.velocity is None:
                continue
            if body.geocentric.units != "au" or body.velocity.units != "au/day":
                continue
            for offset in (-0.4, -0.2, 0.0, 0.2, 0.4):
                projector.request_vector(
                    (
                        body.geocentric.x + body.velocity.x * offset,
                        body.geocentric.y + body.velocity.y * offset,
                        body.geocentric.z + body.velocity.z * offset,
                    )
                )
    projector.flush()

    for star in ordered_stars:
        if star.magnitude > max_star_magnitude:
            continue
        point = projector.project(
            star.ra_hours,
            star.dec_degrees,
        )
        if point is None:
            continue
        if len(star_points) >= visible_star_limit:
            lod_culled_stars += 1
            continue
        screen_point = SkyPoint(
            name=star.name,
            x=point[0],
            y=point[1],
            magnitude=star.magnitude,
            radius=_star_radius(star.magnitude),
            color=spectral_color(star.spectral_type),
            label=star.name if show_star_names else "",
            metadata={
                "layer": "stars",
                "catalog": star.catalog,
                "catalog_id": star.catalog_id,
                "spectral_type": star.spectral_type,
            },
        )
        star_points.append(screen_point)
        star_lookup[star.name] = screen_point
        if show_star_names:
            star_labels.append(
                SkyLabel(
                    text=star.name,
                    x=point[0] + 6.0,
                    y=point[1] + 4.0,
                    color=screen_point.color,
                    priority=1,
                    metadata={"layer": "star-labels"},
                )
            )

    projected_lines = []
    if show_constellations:
        for line in constellation_lines:
            start = star_lookup.get(line.start_star)
            end = star_lookup.get(line.end_star)
            if start is None or end is None:
                continue
            projected_lines.append(
                SkyLine(
                    name=line.constellation,
                    points=[(start.x, start.y), (end.x, end.y)],
                    color=(0.34, 0.44, 0.82),
                    metadata={"layer": "constellations"},
                )
            )

    projected_boundaries = []
    if show_constellation_boundaries:
        for line in constellation_boundaries:
            start = star_lookup.get(line.start_star)
            end = star_lookup.get(line.end_star)
            if start is None or end is None:
                continue
            projected_boundaries.append(
                SkyLine(
                    name=line.constellation,
                    points=[(start.x, start.y), (end.x, end.y)],
                    color=(0.66, 0.76, 0.98),
                    width=1.8,
                    metadata={"layer": "constellation-boundaries"},
                )
            )

    projected_constellation_labels = []
    if show_constellation_labels:
        for label in constellation_labels:
            point = projector.project(
                label.ra_hours,
                label.dec_degrees,
            )
            if point is None:
                continue
            projected_constellation_labels.append(
                SkyLabel(
                    text=label.text,
                    x=point[0],
                    y=point[1],
                    color=(0.58, 0.68, 0.96),
                    priority=3,
                    metadata={"layer": "constellation-labels", "constellation": label.constellation},
                )
            )

    planets = []
    planet_labels = []
    if snapshot is not None:
        for body in snapshot.bodies:
            if body.equatorial is None:
                continue
            point = projector.project(
                body.equatorial.ra_hours,
                body.equatorial.dec_degrees,
            )
            if point is None:
                continue
            retrograde = (
                body.ecliptic is not None and body.ecliptic.longitude_rate_deg_per_day < 0.0
            )
            glyph = _PLANET_GLYPHS.get(body.name, "")
            label_text = body.name if show_planet_labels else ""
            if retrograde and label_text:
                label_text += " Rx"
            planets.append(
                SkyPoint(
                    name=body.name,
                    x=point[0],
                    y=point[1],
                    magnitude=-2.0,
                    radius=_planet_radius(body.name),
                    color=_planet_color(body.name),
                    label=label_text,
                    glyph=glyph,
                    metadata={
                        "layer": "planets",
                        "retrograde": "true" if retrograde else "false",
                    },
                )
            )
            if show_planet_labels:
                label_prefix = f"{glyph} " if glyph else ""
                planet_labels.append(
                    SkyLabel(
                        text=label_prefix + label_text,
                        x=point[0] + 7.0,
                        y=point[1] + 5.0,
                        color=_planet_color(body.name),
                        priority=4,
                        metadata={"layer": "planet-labels"},
                    )
                )

    if not show_star_names:
        star_labels = _reference_star_labels_for_camera(star_points, camera)

    zodiac_lines = []
    zodiac_labels = []
    if show_zodiac:
        zodiac_lines, zodiac_labels = _build_zodiac_overlays(
            projector,
            width,
            height,
        )

    star_labels = _limit_labels_for_lod(
        star_labels,
        width,
        height,
        _lod_label_budget(camera, 14 if show_star_names else 12),
    )
    planet_labels = _limit_labels_for_lod(
        planet_labels,
        width,
        height,
        _lod_label_budget(camera, 10),
    )
    projected_constellation_labels = _limit_labels_for_lod(
        projected_constellation_labels,
        width,
        height,
        _lod_label_budget(camera, 14),
    )
    zodiac_labels = _limit_labels_for_lod(
        zodiac_labels,
        width,
        height,
        _lod_label_budget(camera, 8),
    )

    aspect_lines = []
    aspect_labels = []
    if snapshot is not None and show_aspects and len(planets) >= 2:
        aspect_lines, aspect_labels = _build_aspect_overlays(snapshot, planets)
    aspect_labels = _limit_labels_for_lod(aspect_labels, width, height, _lod_label_budget(camera, 8))

    horizon, dome = _build_visible_boundary(camera, show_horizon, show_dome, width, height)
    equator = (
        _build_equatorial_line(projector, width, height)
        if show_equator
        else None
    )
    milky_way_lines = []
    horizon_labels = (
        _build_horizon_labels(camera, width, height)
        if show_horizon and show_horizon_labels
        else []
    )
    altitude_grid_lines = _build_altitude_grid(camera, width, height) if show_grid else []
    dome_grid_lines = _build_dome_grid(camera, width, height) if show_grid else []
    trails = _planet_trails(projector, width, height) if snapshot and show_planet_trails else []
    filtered_labels = _declutter_labels(
        width,
        height,
        star_labels=star_labels,
        planet_labels=planet_labels,
        aspect_labels=aspect_labels,
        horizon_labels=horizon_labels,
        constellation_labels=projected_constellation_labels,
        zodiac_labels=zodiac_labels,
    )
    star_labels = filtered_labels["star_labels"]
    planet_labels = filtered_labels["planet_labels"]
    aspect_labels = filtered_labels["aspect_labels"]
    horizon_labels = filtered_labels["horizon_labels"]
    projected_constellation_labels = filtered_labels["constellation_labels"]
    zodiac_labels = filtered_labels["zodiac_labels"]

    batches = [
        _point_batch("stars", star_points),
        _point_batch("planets", planets),
        _line_batch("aspect-lines", aspect_lines),
        _line_batch("constellation-boundaries", projected_boundaries),
        _line_batch("constellation-lines", projected_lines),
        _line_batch("zodiac-lines", zodiac_lines),
        _line_batch("planet-trails", trails),
    ]
    if horizon is not None:
        batches.append(_line_batch("horizon", [horizon]))
    if equator is not None:
        batches.append(_line_batch("equator", [equator]))
    if dome is not None:
        batches.append(_line_batch("dome", [dome]))

    generated_at = snapshot.time.utc_datetime if snapshot is not None else datetime.now(timezone.utc)
    return SkyScene(
        width=width,
        height=height,
        generated_at_utc=generated_at,
        stars=star_points,
        planets=planets,
        star_labels=star_labels,
        planet_labels=planet_labels,
        aspect_labels=aspect_labels,
        constellation_labels=projected_constellation_labels,
        horizon_labels=horizon_labels,
        zodiac_labels=zodiac_labels,
        aspect_lines=aspect_lines,
        milky_way_lines=milky_way_lines,
        constellation_lines=projected_lines,
        constellation_boundaries=projected_boundaries,
        zodiac_lines=zodiac_lines,
        altitude_grid_lines=altitude_grid_lines,
        dome_grid_lines=dome_grid_lines,
        planet_trails=trails,
        horizon_line=horizon,
        equatorial_line=equator,
        dome_line=dome,
        batches=batches,
        metadata={
            "star_count": str(len(star_points)),
            "planet_count": str(len(planets)),
            "aspect_count": str(len(aspect_lines)),
            "milky_way_count": "1" if show_milky_way else "0",
            "milky_way_mode": "texture" if show_milky_way else "off",
            "milky_way_texture_source": "asset" if show_milky_way else "off",
            "constellation_line_count": str(len(projected_lines)),
            "constellation_boundary_count": str(len(projected_boundaries)),
            "zodiac_line_count": str(len(zodiac_lines)),
            "zodiac_label_count": str(len(zodiac_labels)),
            "grid_line_count": str(len(altitude_grid_lines) + len(dome_grid_lines)),
            "star_label_count": str(len(star_labels)),
            "planet_label_count": str(len(planet_labels)),
            "aspect_label_count": str(len(aspect_labels)),
            "constellation_label_count": str(len(projected_constellation_labels)),
            "horizon_label_count": str(len(horizon_labels)),
            "planet_trail_count": str(len(trails)),
            "visible_star_limit": str(visible_star_limit),
            "culled_by_lod": str(lod_culled_stars),
            "lod_profile": "zoom",
            "observer_latitude": str(snapshot.observer.get("latitude", 0.0)) if snapshot is not None else "0.0",
            "observer_longitude": str(snapshot.observer.get("longitude", 0.0)) if snapshot is not None else "0.0",
            "observer_altitude": str(snapshot.observer.get("altitude", 0.0)) if snapshot is not None else "0.0",
            "observer_utc": generated_at.isoformat(),
            "observer_jd_utc": str(snapshot.time.jd_utc) if snapshot is not None else str(julian_day_utc(generated_at)),
        },
    )
