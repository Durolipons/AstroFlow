"""Offline DE441 kernel backend."""

from __future__ import annotations

import os
from math import atan2, degrees, hypot
from typing import Dict, Iterable, Optional, Tuple

from core import constants as C
from core.models import Location

from ..config import DE441KernelConfig
from ..models import (
    AstronomySnapshot,
    BodyState,
    EclipticCoordinates,
    EquatorialCoordinates,
    Vector3,
)
from ..validation import validate_de441_kernel_file
from .base import AstronomyBackend, BackendUnavailableError

_AU_IN_KM = 149597870.7
_BODY_TARGET_CODES = {
    C.SUN: 10,
    C.MOON: 301,
    C.MERCURY: 199,
    C.VENUS: 299,
    C.MARS: 499,
    C.JUPITER: 599,
    C.SATURN: 699,
    C.URANUS: 799,
    C.NEPTUNE: 899,
    C.PLUTO: 999,
}


def _to_vector3(values, units: str) -> Vector3:
    return Vector3(
        x=float(values[0]),
        y=float(values[1]),
        z=float(values[2]),
        units=units,
    )


def _subtract_vectors(left, right):
    return tuple(float(a) - float(b) for a, b in zip(left, right))


def _scale_vector(values, factor: float):
    return tuple(float(value) * factor for value in values)


def _vector_magnitude(values) -> float:
    x, y, z = values
    return float((x * x + y * y + z * z) ** 0.5)


def _wrap_degrees(value: float) -> float:
    return value % 360.0


def _angle_delta(end: float, start: float) -> float:
    return ((end - start + 180.0) % 360.0) - 180.0


class DE441KernelBackend(AstronomyBackend):
    """Offline backend driven by a JPL DE441 SPK kernel."""

    name = "de441"

    def __init__(self, kernel_path: Optional[str] = None) -> None:
        self.kernel_path = kernel_path or DE441KernelConfig.from_env().path
        self._kernel = None
        self._parents = None

    def validate_kernel(self):
        return validate_de441_kernel_file(self.kernel_path)

    def available_bodies(self) -> Iterable[int]:
        return tuple(_BODY_TARGET_CODES)

    def _import_dependencies(self):
        try:
            from jplephem.spk import SPK
        except ImportError as exc:
            raise BackendUnavailableError(
                "jplephem is not installed; add jplephem to use the DE441 backend."
            ) from exc

        try:
            from astropy import units as u
            from astropy.coordinates import EarthLocation, GCRS, GeocentricTrueEcliptic, ICRS, SkyCoord
            from astropy.coordinates import CartesianRepresentation
            from astropy.time import Time
        except ImportError as exc:
            raise BackendUnavailableError(
                "astropy is not installed; add astropy to use the DE441 backend."
            ) from exc

        return (
            SPK,
            Time,
            SkyCoord,
            ICRS,
            CartesianRepresentation,
            GeocentricTrueEcliptic,
            EarthLocation,
            GCRS,
            u,
        )

    def _load_kernel(self):
        if self._kernel is not None:
            return self._kernel
        if not self.kernel_path:
            raise BackendUnavailableError(
                "DE441 kernel path is not configured. Set ASTROFLOW_DE441_KERNEL or pass kernel_path."
            )
        if not os.path.isfile(self.kernel_path):
            raise BackendUnavailableError(
                f"DE441 kernel file not found: {self.kernel_path}"
            )
        (
            SPK,
            _Time,
            _SkyCoord,
            _ICRS,
            _CartesianRepresentation,
            _GeocentricTrueEcliptic,
            _EarthLocation,
            _GCRS,
            _u,
        ) = self._import_dependencies()
        self._kernel = SPK.open(self.kernel_path)
        return self._kernel

    def _parent_segments(self):
        if self._parents is not None:
            return self._parents
        kernel = self._load_kernel()
        parents = {}
        for segment in kernel.segments:
            parents[segment.target] = segment
        self._parents = parents
        return parents

    def _segment_state(self, segment, jd_tdb: float):
        position_km, velocity_km_per_day = segment.compute_and_differentiate(jd_tdb)
        return tuple(position_km), tuple(velocity_km_per_day)

    def _state_to_barycenter(
        self,
        target_code: int,
        jd_tdb: float,
        cache: Dict[int, Tuple[Tuple[float, float, float], Tuple[float, float, float]]],
    ):
        if target_code in cache:
            return cache[target_code]
        if target_code == 0:
            cache[target_code] = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
            return cache[target_code]

        parents = self._parent_segments()
        try:
            segment = parents[target_code]
        except KeyError as exc:
            raise BackendUnavailableError(
                f"DE441 kernel is missing a segment path for target {target_code}."
            ) from exc

        parent_position, parent_velocity = self._state_to_barycenter(
            segment.center, jd_tdb, cache
        )
        offset_position, offset_velocity = self._segment_state(segment, jd_tdb)
        state = (
            tuple(float(a) + float(b) for a, b in zip(parent_position, offset_position)),
            tuple(float(a) + float(b) for a, b in zip(parent_velocity, offset_velocity)),
        )
        cache[target_code] = state
        return state

    def _vector_to_coords(self, vector_au, jd_tdb: float, observer: Optional[Location] = None):
        (
            _SPK,
            Time,
            SkyCoord,
            ICRS,
            CartesianRepresentation,
            GeocentricTrueEcliptic,
            EarthLocation,
            GCRS,
            u,
        ) = self._import_dependencies()

        time = Time(jd_tdb, format="jd", scale="tdb")
        rep = CartesianRepresentation(vector_au[0] * u.au, vector_au[1] * u.au, vector_au[2] * u.au)
        coord = SkyCoord(rep, frame=ICRS())
        equatorial_coord = coord
        if observer is not None:
            location = EarthLocation.from_geodetic(
                lon=observer.longitude * u.deg,
                lat=observer.latitude * u.deg,
                height=observer.altitude * u.m,
            )
            obs_position, _obs_velocity = location.get_gcrs_posvel(time)
            gcrs = coord.transform_to(GCRS(obstime=time))
            equatorial_coord = SkyCoord(gcrs.cartesian - obs_position, frame=GCRS(obstime=time))
        ecliptic = coord.transform_to(GeocentricTrueEcliptic(equinox=time))
        return (
            EquatorialCoordinates(
                ra_hours=float(equatorial_coord.ra.hour),
                dec_degrees=float(equatorial_coord.dec.deg),
                distance_au=float(equatorial_coord.distance.au),
            ),
            EclipticCoordinates(
                longitude_degrees=_wrap_degrees(float(ecliptic.lon.deg)),
                latitude_degrees=float(ecliptic.lat.deg),
                radius_au=float(ecliptic.distance.au),
            ),
        )

    def _fallback_coords(self, vector_au):
        x, y, z = vector_au
        lon = _wrap_degrees(degrees(atan2(y, x)))
        lat = degrees(atan2(z, hypot(x, y)))
        distance = _vector_magnitude(vector_au)
        ra = lon / 15.0
        return (
            EquatorialCoordinates(
                ra_hours=ra,
                dec_degrees=lat,
                distance_au=distance,
            ),
            EclipticCoordinates(
                longitude_degrees=lon,
                latitude_degrees=lat,
                radius_au=distance,
            ),
        )

    def _coords_for_vector(self, vector_au, jd_tdb: float, observer: Optional[Location] = None):
        try:
            return self._vector_to_coords(vector_au, jd_tdb, observer=observer)
        except BackendUnavailableError:
            raise
        except Exception:
            return self._fallback_coords(vector_au)

    def _longitude_rate(self, vector_au, velocity_au_per_day, jd_tdb: float) -> float:
        _base_equatorial, base_ecliptic = self._coords_for_vector(vector_au, jd_tdb)
        next_vector = tuple(
            float(position) + float(velocity)
            for position, velocity in zip(vector_au, velocity_au_per_day)
        )
        _next_equatorial, next_ecliptic = self._coords_for_vector(next_vector, jd_tdb + 1.0)
        return _angle_delta(
            next_ecliptic.longitude_degrees,
            base_ecliptic.longitude_degrees,
        )

    def _body_state(self, body_id: int, jd_tdb: float, cache, observer: Optional[Location]):
        target_code = _BODY_TARGET_CODES[body_id]
        body_position_km, body_velocity_km_per_day = self._state_to_barycenter(target_code, jd_tdb, cache)
        earth_position_km, earth_velocity_km_per_day = self._state_to_barycenter(399, jd_tdb, cache)
        sun_position_km, _sun_velocity_km_per_day = self._state_to_barycenter(10, jd_tdb, cache)

        heliocentric_km = _subtract_vectors(body_position_km, sun_position_km)
        geocentric_km = _subtract_vectors(body_position_km, earth_position_km)
        geocentric_velocity_km_per_day = _subtract_vectors(body_velocity_km_per_day, earth_velocity_km_per_day)

        heliocentric_au = _scale_vector(heliocentric_km, 1.0 / _AU_IN_KM)
        geocentric_au = _scale_vector(geocentric_km, 1.0 / _AU_IN_KM)
        velocity_au_per_day = _scale_vector(geocentric_velocity_km_per_day, 1.0 / _AU_IN_KM)

        equatorial, ecliptic = self._coords_for_vector(geocentric_au, jd_tdb, observer=observer)
        ecliptic = EclipticCoordinates(
            longitude_degrees=ecliptic.longitude_degrees,
            latitude_degrees=ecliptic.latitude_degrees,
            radius_au=ecliptic.radius_au,
            longitude_rate_deg_per_day=self._longitude_rate(geocentric_au, velocity_au_per_day, jd_tdb),
        )

        return BodyState(
            body_id=body_id,
            name=C.PLANETS[body_id],
            heliocentric=_to_vector3(heliocentric_au, "au"),
            geocentric=_to_vector3(geocentric_au, "au"),
            velocity=_to_vector3(velocity_au_per_day, "au/day"),
            equatorial=equatorial,
            ecliptic=ecliptic,
            metadata={
                "backend": self.name,
                "kernel_path": self.kernel_path,
                "target_code": str(target_code),
                "timescale": "tdb",
                "equatorial_origin": "observer" if observer is not None else "geocenter",
            },
        )

    def fetch_snapshot(
        self,
        moment_utc,
        observer: Optional[Location] = None,
        body_ids: Optional[Iterable[int]] = None,
    ) -> AstronomySnapshot:
        kernel = self._load_kernel()
        time_context = self.build_time_context(moment_utc)
        jd_tdb = time_context.jd_tdb
        if jd_tdb is None:
            raise BackendUnavailableError("Unable to compute TDB Julian date for DE441 lookup.")

        selected = tuple(body_ids) if body_ids else tuple(self.available_bodies())
        cache = {}
        try:
            comments = kernel.comments().strip()
        except Exception:
            comments = ""

        bodies = [self._body_state(body_id, jd_tdb, cache, observer) for body_id in selected]
        return AstronomySnapshot(
            time=time_context,
            bodies=bodies,
            observer={
                "latitude": observer.latitude if observer else 0.0,
                "longitude": observer.longitude if observer else 0.0,
                "altitude": observer.altitude if observer else 0.0,
            },
            backend_name=self.name,
            metadata={
                "source": "JPL DE441 kernel",
                "kernel_path": self.kernel_path,
                "kernel_comment": comments[:240],
            },
        )
