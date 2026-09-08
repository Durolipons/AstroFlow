"""Tests for projected sky-scene generation."""

from datetime import datetime, timezone

from astronomy.catalogs import (
    StarRecord,
    builtin_bright_star_catalog,
    builtin_constellation_boundaries,
    builtin_constellation_labels,
    builtin_constellation_lines,
)
from astronomy.models import AstronomySnapshot, BodyState, EclipticCoordinates, EquatorialCoordinates, Vector3
from astronomy.opengl.camera import SkyCamera
from astronomy.scene import build_sky_scene
from astronomy.opengl.projection import project_altaz
from astronomy.timebase import build_time_context
from core import constants as C


def test_build_sky_scene_includes_minimal_helper_layers():
    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[
            BodyState(
                body_id=C.MARS,
                name="Mars",
                geocentric=Vector3(0.291851, 1.08893, 0.410424, units="au"),
                velocity=Vector3(-0.0015, 0.0006, 0.0002, units="au/day"),
                equatorial=EquatorialCoordinates(ra_hours=5.0, dec_degrees=20.0, distance_au=1.2),
                ecliptic=EclipticCoordinates(
                    longitude_degrees=120.0,
                    latitude_degrees=1.0,
                    radius_au=1.2,
                    longitude_rate_deg_per_day=-0.5,
                ),
            )
        ],
        observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
        backend_name="de441",
    )

    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=120.0, fov_degrees=100.0),
        snapshot=snapshot,
        stars=builtin_bright_star_catalog(),
        constellation_lines=builtin_constellation_lines(),
        constellation_labels=builtin_constellation_labels(),
        constellation_boundaries=builtin_constellation_boundaries(),
        show_constellation_labels=True,
        show_constellation_boundaries=True,
        show_milky_way=True,
        show_planet_labels=True,
        show_planet_trails=True,
        max_star_magnitude=3.5,
    )

    assert scene.dome_line is None
    assert scene.horizon_line is not None
    assert scene.equatorial_line is not None
    assert len(scene.stars) > 0
    assert len(scene.planets) == 1
    assert len(scene.constellation_lines) > 0
    assert len(scene.constellation_labels) > 0
    assert len(scene.constellation_boundaries) > 0
    assert len(scene.zodiac_lines) > 0
    assert len(scene.zodiac_labels) > 0
    assert scene.metadata["milky_way_mode"] == "texture"
    assert scene.metadata["milky_way_texture_source"] == "asset"
    assert scene.metadata["milky_way_count"] == "1"
    assert len(scene.horizon_labels) >= 1
    assert {label.text for label in scene.horizon_labels} <= {"N", "E", "S", "W"}
    assert len(scene.altitude_grid_lines) == 0
    assert len(scene.dome_grid_lines) == 0
    assert len(scene.planet_trails) > 0
    assert len(scene.star_labels) > 0
    assert len(scene.planet_labels) == 1
    assert scene.planets[0].glyph
    assert scene.metadata["planet_count"] == "1"
    assert scene.metadata["zodiac_line_count"] != "0"


def test_build_sky_scene_uses_zoom_lod_for_star_and_label_density():
    stars = [
        StarRecord(f"Star {index:02d}", (index % 20) * 0.03, -20.0 + (index * 0.6), 1.0 + (index * 0.03), "A0V")
        for index in range(60)
    ]
    wide_scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(fov_degrees=140.0),
        snapshot=AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={},
            backend_name="preview",
        ),
        stars=stars,
        show_milky_way=False,
        show_constellation_labels=False,
        show_constellation_boundaries=False,
    )
    zoom_scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(fov_degrees=45.0),
        snapshot=AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={},
            backend_name="preview",
        ),
        stars=stars,
        show_milky_way=False,
        show_constellation_labels=False,
        show_constellation_boundaries=False,
    )

    assert len(wide_scene.stars) < len(zoom_scene.stars)
    assert int(wide_scene.metadata["culled_by_lod"]) > 0
    assert len(wide_scene.star_labels) <= len(zoom_scene.star_labels)


def test_build_sky_scene_can_disable_rich_overlay_layers():
    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=120.0),
        snapshot=AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        ),
        stars=builtin_bright_star_catalog(),
        show_constellation_labels=False,
        show_constellation_boundaries=False,
        show_milky_way=False,
        show_zodiac=False,
    )

    assert len(scene.constellation_labels) == 0
    assert len(scene.constellation_boundaries) == 0
    assert len(scene.zodiac_lines) == 0
    assert len(scene.zodiac_labels) == 0
    assert scene.metadata["milky_way_mode"] == "off"


def test_build_sky_scene_projects_equator_and_major_aspect_overlays():
    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[
            BodyState(
                body_id=C.MARS,
                name="Mars",
                equatorial=EquatorialCoordinates(ra_hours=5.0, dec_degrees=20.0, distance_au=1.2),
                ecliptic=EclipticCoordinates(
                    longitude_degrees=120.0,
                    latitude_degrees=1.0,
                    radius_au=1.2,
                    longitude_rate_deg_per_day=-0.5,
                ),
            ),
            BodyState(
                body_id=C.VENUS,
                name="Venus",
                equatorial=EquatorialCoordinates(ra_hours=5.8, dec_degrees=18.0, distance_au=0.8),
                ecliptic=EclipticCoordinates(
                    longitude_degrees=180.0,
                    latitude_degrees=0.8,
                    radius_au=0.8,
                    longitude_rate_deg_per_day=1.1,
                ),
            ),
        ],
        observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
        backend_name="de441",
    )

    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=120.0, fov_degrees=100.0),
        snapshot=snapshot,
        stars=builtin_bright_star_catalog(),
        show_aspects=True,
        show_equator=True,
    )

    assert scene.equatorial_line is not None
    assert len(scene.aspect_lines) == 1
    assert len(scene.aspect_labels) == 1
    assert scene.metadata["aspect_count"] == "1"


def test_build_sky_scene_removes_circular_dome_boundary():
    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[],
        observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
        backend_name="preview",
    )

    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=0.0),
        snapshot=snapshot,
        stars=builtin_bright_star_catalog(),
        show_horizon=True,
        show_dome=True,
    )

    assert scene.dome_line is None
    assert scene.horizon_line is not None


def test_horizon_line_spans_full_width_at_center():
    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=0.0),
        snapshot=AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        ),
    )

    assert scene.horizon_line is not None
    assert scene.horizon_line.points[0][0] < 10.0
    assert scene.horizon_line.points[-1][0] > 790.0
    assert all(abs(point[1] - 300.0) < 0.5 for point in scene.horizon_line.points)


def test_horizon_labels_show_cardinal_directions():
    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=0.0),
        snapshot=AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        ),
        show_horizon=True,
        show_horizon_labels=True,
    )

    labels = {label.text for label in scene.horizon_labels}
    assert "N" in labels


def test_zodiac_overlay_builds_sign_sectors_and_labels():
    scene = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=120.0, fov_degrees=100.0),
        snapshot=AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        ),
        show_zodiac=True,
    )

    assert any(line.metadata.get("layer") == "zodiac-sectors" for line in scene.zodiac_lines)
    assert any(label.metadata.get("layer") == "zodiac-labels" for label in scene.zodiac_labels)


def test_project_altaz_places_objects_above_and_below_horizon():
    camera = SkyCamera(view_azimuth_degrees=0.0)
    above = project_altaz(0.0, 30.0, camera, 800, 600)
    below = project_altaz(0.0, -30.0, camera, 800, 600)

    assert above is not None
    assert below is not None
    assert above[1] > 300.0
    assert below[1] < 300.0


def test_project_altaz_tracks_camera_yaw_across_view():
    camera = SkyCamera(view_azimuth_degrees=0.0)
    center = project_altaz(0.0, 20.0, camera, 800, 600)
    right = project_altaz(20.0, 20.0, camera, 800, 600)
    camera.view_azimuth_degrees = 20.0
    recentered = project_altaz(20.0, 20.0, camera, 800, 600)

    assert center is not None
    assert right is not None
    assert recentered is not None
    assert center[0] == 400.0
    assert right[0] > center[0]
    assert abs(recentered[0] - 400.0) < 0.5


def test_observer_time_from_metadata_parses_iso_offset_strings():
    from astropy.time import Time

    from astronomy.skyframes import observer_time_from_metadata

    # Exact shape produced by build_sky_scene metadata - astropy's string
    # parser rejects the "+00:00" suffix, the helper must not.
    metadata = {"observer_utc": "2026-09-06T16:24:54.350958+00:00"}
    parsed = observer_time_from_metadata(metadata)
    assert parsed is not None
    expected = Time(datetime.fromisoformat(metadata["observer_utc"]), scale="utc")
    assert abs(parsed.jd - expected.jd) < 1e-6

    # Julian-day metadata is preferred when present.
    jd_metadata = {"observer_jd_utc": str(expected.jd), "observer_utc": metadata["observer_utc"]}
    from_jd = observer_time_from_metadata(jd_metadata)
    assert from_jd is not None
    assert abs(from_jd.jd - expected.jd) < 1e-6

    # Missing metadata yields None instead of raising.
    assert observer_time_from_metadata({}) is None
    assert observer_time_from_metadata(None) is None


def test_frame_cache_eviction_never_drops_the_active_frame():
    from astronomy.scene import _FrameCache

    cache = _FrameCache(limit=2)
    first = cache.frame(("a",))
    first["entry"] = 1
    assert cache.frame(("a",)) is first

    # Cycle past the limit and re-request keys in a mixed order: eviction must
    # never remove the dict that is about to be returned (a shared FIFO order
    # list once raised KeyError here).
    cache.frame(("b",))
    third = cache.frame(("c",))          # evicts "a"
    reused = cache.frame(("b",))         # existing key re-request
    fourth = cache.frame(("d",))         # evicts "b"
    fifth = cache.frame(("e",))          # evicts "c"
    again = cache.frame(("d",))          # re-request existing key

    assert third is not None
    assert reused is cache.frame(("b",)) or "b" not in cache.store  # never raises
    assert fourth is cache.frame(("d",)) or fourth is again
    assert fifth is not None
    assert len(cache.store) <= 2


def test_dome_projector_shares_frame_cache_between_rebuilds():
    from astronomy.scene import (
        _DomeProjector,
        _build_observer_frame,
        _observer_frame_key,
    )

    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[],
        observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
        backend_name="preview",
    )
    frame = _build_observer_frame(snapshot)
    camera = SkyCamera(view_azimuth_degrees=120.0)

    first = _DomeProjector(snapshot, frame, 800, 600, camera)
    first.request_equatorial(5.0, 20.0)
    first.request_ecliptic(45.0, 0.0)
    first.flush()
    az1, alt1 = first.altaz(5.0, 20.0)
    assert az1 is not None

    # A second projector for the same observer frame must reuse the shared
    # cache (no new transforms) and produce identical dome coordinates.
    second = _DomeProjector(snapshot, frame, 800, 600, camera)
    assert second.frame_key == _observer_frame_key(snapshot)
    az2, alt2 = second.altaz(5.0, 20.0)
    assert (az2, alt2) == (az1, alt1)
    ra_hours, dec_degrees = second.equatorial_from_ecliptic(45.0, 0.0)
    assert 0.0 <= ra_hours < 24.0
    assert -30.0 <= dec_degrees <= 30.0


def test_camera_yaw_shifts_shared_stars_left_on_screen():
    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[],
        observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
        backend_name="preview",
    )
    stars = builtin_bright_star_catalog()

    first = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=120.0, fov_degrees=100.0),
        snapshot=snapshot,
        stars=stars,
    )
    second = build_sky_scene(
        width=800,
        height=600,
        camera=SkyCamera(view_azimuth_degrees=125.0, fov_degrees=100.0),
        snapshot=snapshot,
        stars=stars,
    )

    first_positions = {star.name: (star.x, star.y) for star in first.stars}
    second_positions = {star.name: (star.x, star.y) for star in second.stars}
    common = set(first_positions) & set(second_positions)
    assert len(common) >= 5
    # Turning the view east (azimuth +5) must shift the shared stars west.
    moved_left = sum(
        1 for name in common if second_positions[name][0] < first_positions[name][0]
    )
    assert moved_left >= len(common) - 2
