"""Tests for the minimal astrology helper renderer."""

from datetime import datetime, timezone

from astronomy.catalogs import ConstellationLine, StarRecord
from astronomy.config import SkySceneConfig
from astronomy.models import AstronomySnapshot, BodyState, EclipticCoordinates, EquatorialCoordinates, Vector3
from astronomy.opengl.renderer import SkyRenderer
from astronomy.timebase import build_time_context
from core import constants as C


def _snapshot():
    return AstronomySnapshot(
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


def test_renderer_builds_minimal_layers_and_cache():
    renderer = SkyRenderer(
        config=SkySceneConfig(
            show_planet_labels=True,
            show_planet_trails=True,
            max_star_magnitude=3.5,
        )
    )
    # The runtime default fov is now 60 degrees; these scenes were calibrated
    # against the wide 100-degree field, so pin it explicitly.
    renderer.camera.fov_degrees = 100.0
    renderer.load_star_catalog(
        [
            StarRecord("Alpha", 5.0, 20.0, 1.0, "A0V"),
            StarRecord("Beta", 5.2, 21.0, 2.0, "G2V"),
            StarRecord("Gamma", 5.5, 22.0, 3.0, "M1III"),
        ]
    )
    renderer.load_constellation_lines([ConstellationLine("Test", "Alpha", "Beta")])
    renderer.set_snapshot(_snapshot())

    scene1 = renderer.build_scene(800, 600)
    scene2 = renderer.build_scene(800, 600)
    buffers = renderer.get_buffers(800, 600)

    assert scene1 is scene2
    assert len(scene1.stars) > 0
    assert len(scene1.planet_labels) == 1
    assert any(line.name == "Test" for line in scene1.constellation_lines)
    assert len(scene1.constellation_labels) > 0
    assert len(scene1.constellation_boundaries) > 0
    assert scene1.metadata["milky_way_mode"] == "texture"
    assert scene1.metadata["milky_way_texture_source"] == "asset"
    assert len(scene1.planet_trails) == 1
    assert scene1.planets[0].glyph
    assert scene1.planets[0].metadata["retrograde"] == "true"
    assert "stars" in buffers
    assert len(buffers["stars"].vertices) == len(scene1.stars) * 2
    assert scene1.horizon_line is not None
    assert scene1.dome_line is None


def test_renderer_applies_zoom_lod_to_visible_star_density():
    renderer = SkyRenderer(
        config=SkySceneConfig(
            max_star_magnitude=4.8,
            lod_star_limit=80,
            show_milky_way=False,
        )
    )
    renderer.load_star_catalog(
        [
            StarRecord(f"Star {index:02d}", 0.0 + (index * 0.02), 0.0 + (index * 0.05), 1.0 + (index * 0.02), "A0V")
            for index in range(80)
        ]
    )
    renderer.camera.fov_degrees = 140.0
    wide_scene = renderer.build_scene(800, 600)

    renderer.camera.fov_degrees = 45.0
    renderer._scene_cache.clear()
    zoom_scene = renderer.build_scene(800, 600)

    assert len(wide_scene.stars) < len(zoom_scene.stars)
    assert int(wide_scene.metadata["culled_by_lod"]) > 0
    assert int(zoom_scene.metadata["visible_star_limit"]) >= int(wide_scene.metadata["visible_star_limit"])


def test_renderer_uses_curated_star_limit_and_simple_toggles():
    renderer = SkyRenderer(
        config=SkySceneConfig(
            show_planet_labels=False,
            show_planet_trails=False,
            show_constellations=False,
            show_horizon=True,
            show_dome=True,
            max_star_magnitude=1.5,
        )
    )
    renderer.camera.fov_degrees = 100.0
    renderer.load_star_catalog(
        [
        StarRecord("S1", 5.0, 20.0, 1.0, "A0V"),
        StarRecord("S2", 5.2, 21.0, 1.2, "A0V"),
        StarRecord("S3", 5.5, 22.0, 1.4, "A0V"),
        StarRecord("S4", 6.0, 25.0, 1.6, "A0V"),
        ]
    )
    renderer.load_constellation_lines([ConstellationLine("Test", "S1", "S2")])
    renderer.set_snapshot(_snapshot())

    scene = renderer.build_scene(800, 600)
    assert all(star.magnitude <= 1.5 for star in scene.stars)
    assert len(scene.constellation_lines) == 0

    renderer.toggle_layer_option("planet_labels")
    renderer.toggle_layer_option("planet_trails")
    renderer.toggle_layer_option("constellations")
    scene2 = renderer.build_scene(800, 600)
    assert len(scene2.planet_labels) == 1
    assert len(scene2.planet_trails) == 1
    assert len(scene2.constellation_lines) > 0


def test_renderer_can_toggle_equator_and_aspect_overlays():
    renderer = SkyRenderer(
        config=SkySceneConfig(
            show_equator=False,
            show_zodiac=False,
            show_aspects=False,
            show_planet_labels=True,
            max_star_magnitude=3.5,
        )
    )
    renderer.camera.fov_degrees = 100.0
    renderer.set_snapshot(
        AstronomySnapshot(
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
    )

    scene = renderer.build_scene(800, 600)
    assert scene.equatorial_line is None
    assert len(scene.zodiac_lines) == 0
    assert len(scene.aspect_lines) == 0

    renderer.toggle_layer_option("equator")
    renderer.toggle_layer_option("zodiac")
    renderer.toggle_layer_option("aspects")
    scene2 = renderer.build_scene(800, 600)

    assert scene2.equatorial_line is not None
    assert len(scene2.zodiac_lines) > 0
    assert len(scene2.aspect_lines) == 1


def test_renderer_can_toggle_rich_constellation_and_milky_way_layers():
    renderer = SkyRenderer(
        config=SkySceneConfig(
            show_constellation_labels=False,
            show_constellation_boundaries=False,
            show_milky_way=False,
        )
    )
    renderer.camera.fov_degrees = 100.0
    renderer.set_snapshot(_snapshot())

    scene = renderer.build_scene(800, 600)
    assert len(scene.constellation_labels) == 0
    assert len(scene.constellation_boundaries) == 0
    assert scene.metadata["milky_way_mode"] == "off"

    renderer.toggle_layer_option("constellation_labels")
    renderer.toggle_layer_option("constellation_boundaries")
    renderer.toggle_layer_option("milky_way")
    scene2 = renderer.build_scene(800, 600)

    assert len(scene2.constellation_labels) > 0
    assert len(scene2.constellation_boundaries) > 0
    assert scene2.metadata["milky_way_mode"] == "texture"


def test_renderer_falls_back_to_builtin_catalog_when_configured_path_is_missing():
    renderer = SkyRenderer(
        config=SkySceneConfig(
            star_catalog_path=r"C:\missing\bright-stars.json",
            max_star_magnitude=3.5,
        )
    )
    renderer.camera.fov_degrees = 100.0

    scene = renderer.build_scene(800, 600)

    assert len(scene.stars) > 0
    assert "not found" in renderer.catalog_warning


def test_renderer_camera_controls_change_planetarium_view():
    renderer = SkyRenderer(config=SkySceneConfig())
    original = (
        renderer.camera.view_azimuth_degrees,
        renderer.camera.view_altitude_degrees,
        renderer.camera.fov_degrees,
    )

    renderer.zoom_by(2.0)
    renderer.pan_by(3.0, 20.0)
    renderer.rotate_by(45.0)

    current = (
        renderer.camera.view_azimuth_degrees,
        renderer.camera.view_altitude_degrees,
        renderer.camera.fov_degrees,
    )
    assert current != original
    assert renderer.camera.view_altitude_degrees == 20.0
    assert renderer.camera.fov_degrees < original[2]
