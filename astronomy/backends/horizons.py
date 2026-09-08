"""Online JPL Horizons backend."""

from __future__ import annotations

from math import atan2, degrees, hypot, sqrt
from typing import Dict, Iterable, Optional

from core import constants as C
from core.models import Location

from ..models import (
    AstronomySnapshot,
    BodyState,
    EclipticCoordinates,
    EquatorialCoordinates,
    Vector3,
)
from .base import AstronomyBackend, BackendUnavailableError

_HORIZONS_IDS: Dict[int, str] = {
    C.SUN: "10",
    C.MOON: "301",
    C.MERCURY: "199",
    C.VENUS: "299",
    C.MARS: "499",
    C.JUPITER: "599",
    C.SATURN: "699",
    C.URANUS: "799",
    C.NEPTUNE: "899",
    C.PLUTO: "999",
    # Chiron (2060) is a small body (comet/asteroid), so Horizons
    # requires the small-body target type flag.
    C.CHIRON: "2060",
}


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _table_value(row, *names: str, default: float = 0.0) -> float:
    for name in names:
        if name in row.colnames:
            return _to_float(row[name], default=default)
    return default


def _vector_from_row(row, x_name: str, y_name: str, z_name: str, units: str = "au") -> Vector3:
    return Vector3(
        x=_table_value(row, x_name),
        y=_table_value(row, y_name),
        z=_table_value(row, z_name),
        units=units,
    )


class HorizonsBackend(AstronomyBackend):
    """Fetch body states from the online Horizons service."""

    name = "horizons"

    def available_bodies(self) -> Iterable[int]:
        return tuple(_HORIZONS_IDS)

    def _import_client(self):
        try:
            from astroquery.jplhorizons import Horizons
        except ImportError as exc:
            raise BackendUnavailableError(
                "astroquery is not installed; add astroquery to use the Horizons backend."
            ) from exc
        return Horizons

    def _observer_location(self, observer: Optional[Location]):
        if observer is None:
            return "500@399"
        return {
            "lon": observer.longitude,
            "lat": observer.latitude,
            "elevation": observer.altitude / 1000.0,
            "body": 399,
        }

    def fetch_snapshot(
        self,
        moment_utc,
        observer: Optional[Location] = None,
        body_ids: Optional[Iterable[int]] = None,
    ) -> AstronomySnapshot:
        Horizons = self._import_client()
        time_context = self.build_time_context(moment_utc)
        selected_ids = tuple(body_ids) if body_ids else tuple(_HORIZONS_IDS)
        bodies = []

        for body_id in selected_ids:
            horizon_id = _HORIZONS_IDS.get(body_id)
            if horizon_id is None:
                continue

            # Chiron is asteroid/comet 2060 -> use small-body Horizons id_type
            # 'smallbody' id_type;  the major bodies use the default lookup.
            id_type = 'smallbody' if body_id == C.CHIRON else None
            vectors_query = Horizons(
                id=horizon_id, id_type=id_type,
                location='500@10', epochs=time_context.jd_tdb,
            )
            geo_vectors_query = Horizons(
                id=horizon_id, id_type=id_type,
                location='500@399', epochs=time_context.jd_tdb,
            )
            ephem_query = Horizons(
                id=horizon_id,
                id_type=id_type,
                location=self._observer_location(observer),
                epochs=time_context.jd_tdb,
            )

            helio_row = vectors_query.vectors()[0]
            geo_row = geo_vectors_query.vectors()[0]
            eph_row = ephem_query.ephemerides()[0]

            vx = _table_value(geo_row, "vx")
            vy = _table_value(geo_row, "vy")
            vz = _table_value(geo_row, "vz")
            helio = _vector_from_row(helio_row, "x", "y", "z")
            geocentric = _vector_from_row(geo_row, "x", "y", "z")
            velocity = Vector3(vx, vy, vz, units="au/day")

            ra_hours = _table_value(eph_row, "RA", default=0.0) / 15.0
            dec_deg = _table_value(eph_row, "DEC", default=0.0)
            distance = _table_value(eph_row, "delta", "Delta")
            lon = _table_value(eph_row, "ObsEclLon", "EclLon", default=0.0)
            lat = _table_value(eph_row, "ObsEclLat", "EclLat", default=0.0)
            lon_rate = _table_value(eph_row, "dRA*cosD", default=0.0)

            if not lon and not lat:
                lon = degrees(atan2(geocentric.y, geocentric.x)) % 360.0
                lat = degrees(atan2(geocentric.z, hypot(geocentric.x, geocentric.y)))
                distance = sqrt((geocentric.x ** 2) + (geocentric.y ** 2) + (geocentric.z ** 2))

            bodies.append(
                BodyState(
                    body_id=body_id,
                    name=C.PLANETS[body_id],
                    heliocentric=helio,
                    geocentric=geocentric,
                    velocity=velocity,
                    equatorial=EquatorialCoordinates(
                        ra_hours=ra_hours,
                        dec_degrees=dec_deg,
                        distance_au=distance,
                    ),
                    ecliptic=EclipticCoordinates(
                        longitude_degrees=lon % 360.0,
                        latitude_degrees=lat,
                        radius_au=distance,
                        longitude_rate_deg_per_day=lon_rate,
                    ),
                    metadata={
                        "backend": self.name,
                        "horizons_id": horizon_id,
                    },
                )
            )

        return AstronomySnapshot(
            time=time_context,
            bodies=bodies,
            observer={
                "latitude": observer.latitude if observer else 0.0,
                "longitude": observer.longitude if observer else 0.0,
                "altitude": observer.altitude if observer else 0.0,
            },
            backend_name=self.name,
            metadata={"source": "NASA JPL Horizons"},
        )
