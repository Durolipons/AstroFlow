"""Adapters that bridge astronomy output into the existing wheel model."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Dict

from core import aspects as A
from core import utils
from core.chart import _assign_houses
from core.models import Chart, PlanetPosition

from ..models import AstronomySnapshot, BodyState


class SwissCompatAdapter:
    """Convert astronomy snapshots into wheel-friendly chart objects."""

    @staticmethod
    def body_to_planet_position(body: BodyState, fallback: PlanetPosition) -> PlanetPosition:
        if body.ecliptic is None:
            return deepcopy(fallback)
        lon = body.ecliptic.longitude_degrees % 360.0
        return PlanetPosition(
            planet_id=fallback.planet_id,
            name=fallback.name,
            longitude=lon,
            speed=body.ecliptic.longitude_rate_deg_per_day,
            latitude=body.ecliptic.latitude_degrees,
            distance=body.ecliptic.radius_au,
            house=fallback.house,
            sign=utils.sign_of(lon),
            sign_degree=utils.degree_in_sign(lon),
            is_retrograde=body.ecliptic.longitude_rate_deg_per_day < 0,
        )

    @classmethod
    def merge_positions(cls, base_chart: Chart, snapshot: AstronomySnapshot):
        snapshot_bodies: Dict[int, BodyState] = snapshot.body_map()
        positions = []
        backend_ids = []

        for base_pos in base_chart.positions:
            body = snapshot_bodies.get(base_pos.planet_id)
            if body is None:
                positions.append(deepcopy(base_pos))
                continue
            backend_ids.append(base_pos.planet_id)
            positions.append(cls.body_to_planet_position(body, base_pos))

        return positions, backend_ids

    @classmethod
    def build_display_chart(
        cls,
        base_chart: Chart,
        snapshot: AstronomySnapshot,
        target_title: str = "",
    ) -> Chart:
        positions, backend_ids = cls.merge_positions(base_chart, snapshot)
        houses = deepcopy(base_chart.houses)
        house_cusps = [house.longitude for house in houses]
        _assign_houses(positions, house_cusps)

        notes = list(base_chart.notes)
        notes.append(f"Astronomy display source: {snapshot.backend_name}.")
        if backend_ids:
            notes.append(
                "DE441/Horizons positions applied for: "
                + ", ".join(pos.name for pos in positions if pos.planet_id in backend_ids)
                + "."
            )
        missing = [
            pos.name for pos in base_chart.positions
            if pos.planet_id not in snapshot.body_map()
        ]
        if missing:
            notes.append(
                "Swiss positions retained for unsupported bodies: " + ", ".join(missing) + "."
            )

        return Chart(
            chart_type=base_chart.chart_type,
            birth_data=base_chart.birth_data,
            target_title=target_title or base_chart.target_title,
            positions=positions,
            houses=houses,
            angles=dict(base_chart.angles),
            aspects=A.find_aspects_between(positions),
            sidereal=base_chart.sidereal,
            ayanamsa=base_chart.ayanamsa,
            notes=notes,
        )
