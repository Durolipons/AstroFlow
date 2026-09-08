"""Separate OpenGL renderer for the live sky panel."""

from __future__ import annotations

import math
from typing import Iterable, Optional, Tuple

from ..catalogs import (
    ConstellationLine,
    StarRecord,
    DEFAULT_MAX_STAR_RECORDS,
    builtin_bright_star_catalog,
    load_catalog,
    load_constellation_boundaries,
    load_constellation_labels,
    load_constellation_lines,
)
from ..config import SkySceneConfig, load_runtime_config
from ..models import AstronomySnapshot, SkyLine
from ..scene import build_sky_scene
from .camera import SkyCamera

# ---------------------------------------------------------------------------
# Legacy immediate-mode OpenGL renderer.
#
# The sky panel always renders through the Kivy canvas (see
# SkyViewportWidget).  Immediate-mode OpenGL (glBegin/glEnd/glVertex2f)
# cannot run on GLES2 targets such as Huawei/Android phones, so these
# symbols are imported lazily and only if someone explicitly calls
# SkyRenderer.draw() - which the sky panel never does any more.
# ---------------------------------------------------------------------------
_OPENGL_AVAILABLE = False
_OPENGL_IMPORT_ATTEMPTED = False

_OPENGL_INTERFACE = (
    "GL_BLEND",
    "GL_COLOR_BUFFER_BIT",
    "GL_DEPTH_TEST",
    "GL_LINE_SMOOTH",
    "GL_LINE_LOOP",
    "GL_LINE_STRIP",
    "GL_MODELVIEW",
    "GL_ONE",
    "GL_ONE_MINUS_SRC_ALPHA",
    "GL_POINT_SMOOTH",
    "GL_POINTS",
    "GL_PROJECTION",
    "GL_SCISSOR_TEST",
    "GL_SRC_ALPHA",
    "GL_TRIANGLE_FAN",
    "GL_TRIANGLE_STRIP",
    "glBegin",
    "glBlendFunc",
    "glClear",
    "glClearColor",
    "glColor4f",
    "glDisable",
    "glEnable",
    "glEnd",
    "glLineWidth",
    "glLoadIdentity",
    "glMatrixMode",
    "glOrtho",
    "glPointSize",
    "glScissor",
    "glVertex2f",
    "glViewport",
)


def _ensure_opengl() -> bool:
    """Import the legacy OpenGL symbols once, on the first draw() call."""
    global _OPENGL_AVAILABLE, _OPENGL_IMPORT_ATTEMPTED
    if _OPENGL_IMPORT_ATTEMPTED:
        return _OPENGL_AVAILABLE
    _OPENGL_IMPORT_ATTEMPTED = True
    try:
        from OpenGL import GL as _gl_module

        for _name in _OPENGL_INTERFACE:
            globals()[_name] = getattr(_gl_module, _name)
        _OPENGL_AVAILABLE = True
    except (ImportError, AttributeError):
        _OPENGL_AVAILABLE = False
    return _OPENGL_AVAILABLE


class SkyRenderer:
    """Owns OpenGL draw state and scene data."""

    def __init__(self, config: Optional[SkySceneConfig] = None) -> None:
        self.config = config or load_runtime_config().sky
        self.camera = SkyCamera()
        self._snapshot: Optional[AstronomySnapshot] = None
        self.catalog_warning = ""
        self._stars = self._load_star_catalog_records()
        self._constellation_lines = load_constellation_lines(
            path=self.config.constellation_path or None,
        )
        self._constellation_labels = load_constellation_labels(
            path=self.config.constellation_label_path or None,
        )
        self._constellation_boundaries = load_constellation_boundaries(
            path=self.config.constellation_boundary_path or None,
        )
        self._frame_counter = 0
        self._last_scene = None
        self._scene_cache = {}
        self._layer_options = {
            "constellations": self.config.show_constellations,
            "constellation_labels": self.config.show_constellation_labels,
            "constellation_boundaries": self.config.show_constellation_boundaries,
            "horizon": self.config.show_horizon,
            "equator": self.config.show_equator,
            "zodiac": self.config.show_zodiac,
            "dome": self.config.show_dome,
            "milky_way": self.config.show_milky_way,
            "planet_labels": self.config.show_planet_labels,
            "planet_trails": self.config.show_planet_trails,
            "aspects": self.config.show_aspects,
        }

    @property
    def opengl_available(self) -> bool:
        return _OPENGL_AVAILABLE

    def _star_limit(self) -> int:
        return min(DEFAULT_MAX_STAR_RECORDS, max(1, self.config.lod_star_limit))

    def _load_star_catalog_records(self, records: Iterable[StarRecord] = ()) -> list[StarRecord]:
        try:
            self.catalog_warning = ""
            return load_catalog(
                records,
                path=self.config.star_catalog_path or None,
                catalog_format=self.config.star_catalog_format or None,
                max_magnitude=self.config.max_star_magnitude,
                chunk_size=self.config.lazy_chunk_size,
                max_records=self._star_limit(),
            )
        except (FileNotFoundError, ValueError) as exc:
            self.catalog_warning = str(exc)
            fallback_records = list(records) if records else builtin_bright_star_catalog()
            return load_catalog(
                fallback_records,
                path=None,
                catalog_format=None,
                max_magnitude=self.config.max_star_magnitude,
                chunk_size=self.config.lazy_chunk_size,
                include_builtin=False,
                max_records=self._star_limit(),
            )

    def load_star_catalog(self, records: Iterable[StarRecord]) -> None:
        self._stars = self._load_star_catalog_records(records)
        self._scene_cache.clear()

    def load_constellation_lines(self, records: Iterable[ConstellationLine]) -> None:
        self._constellation_lines = load_constellation_lines(
            records,
            path=self.config.constellation_path or None,
        )
        self._scene_cache.clear()

    def load_constellation_labels(self, records) -> None:
        self._constellation_labels = list(records)
        self._scene_cache.clear()

    def load_constellation_boundaries(self, records: Iterable[ConstellationLine]) -> None:
        self._constellation_boundaries = [line for line in records if line.boundary]
        self._scene_cache.clear()

    def set_snapshot(self, snapshot: Optional[AstronomySnapshot]) -> None:
        self._snapshot = snapshot
        self._scene_cache.clear()

    def set_layer_option(self, name: str, enabled: bool) -> None:
        if name not in self._layer_options:
            raise ValueError(f"Unknown sky layer option: {name}")
        self._layer_options[name] = bool(enabled)
        self._scene_cache.clear()

    def toggle_layer_option(self, name: str) -> bool:
        self.set_layer_option(name, not self._layer_options[name])
        return self._layer_options[name]

    def get_layer_option(self, name: str) -> bool:
        return self._layer_options[name]

    def _camera_key(self) -> Tuple[float, float, float, float]:
        return (
            round(self.camera.view_azimuth_degrees, 4),
            round(self.camera.view_altitude_degrees, 4),
            round(self.camera.fov_degrees, 4),
            round(self.camera.rotation_degrees, 4),
        )

    def _scene_cache_key(self, width: int, height: int):
        snapshot_key = None
        if self._snapshot is not None:
            snapshot_key = (
                round(self._snapshot.time.jd_tdb or self._snapshot.time.jd_utc, 8),
                self._snapshot.backend_name,
            )
        layer_key = tuple(sorted(self._layer_options.items()))
        return width, height, snapshot_key, self._camera_key(), layer_key

    def build_scene(self, width: int, height: int):
        cache_key = self._scene_cache_key(width, height)
        if cache_key in self._scene_cache:
            self._last_scene = self._scene_cache[cache_key]
            return self._last_scene

        scene = build_sky_scene(
            width=width,
            height=height,
            camera=self.camera,
            snapshot=self._snapshot,
            stars=self._stars,
            constellation_lines=self._constellation_lines,
            constellation_labels=self._constellation_labels,
            constellation_boundaries=self._constellation_boundaries,
            show_constellations=self._layer_options["constellations"],
            show_constellation_labels=self._layer_options["constellation_labels"],
            show_constellation_boundaries=self._layer_options["constellation_boundaries"],
            show_horizon=self._layer_options["horizon"],
            show_horizon_labels=self.config.show_horizon_labels,
            show_equator=self._layer_options["equator"],
            show_zodiac=self._layer_options["zodiac"],
            show_dome=self._layer_options["dome"],
            show_milky_way=self._layer_options["milky_way"],
            show_star_names=self.config.show_star_names,
            show_planet_labels=self._layer_options["planet_labels"],
            show_planet_trails=self._layer_options["planet_trails"],
            show_aspects=self._layer_options["aspects"],
            max_star_magnitude=self.config.max_star_magnitude,
            lod_star_limit=self.config.lod_star_limit,
        )
        self._last_scene = scene
        self._scene_cache[cache_key] = scene
        # Keep the camera-keyed cache bounded while dragging: one entry per
        # distinct camera position, scenes are cheap to rebuild now.
        while len(self._scene_cache) > 12:
            self._scene_cache.pop(next(iter(self._scene_cache)), None)
        return scene

    def get_buffers(self, width: int, height: int):
        scene = self.build_scene(width, height)
        return {batch.layer: batch for batch in scene.batches}

    def zoom_by(self, factor: float) -> None:
        self.camera.fov_degrees /= max(0.1, factor)
        self.camera.zoom *= factor
        self.camera.clamp()
        self._scene_cache.clear()

    def pan_by(self, delta_ra_hours: float, delta_dec_degrees: float) -> None:
        # Update both camera vocabularies so navigation behaves identically in
        # the planetarium path (view_*) and the celestial-chart fallback
        # (center_*) used when no observer location/time is available.
        self.camera.view_azimuth_degrees += delta_ra_hours * 15.0
        self.camera.view_altitude_degrees += delta_dec_degrees
        self.camera.center_ra_hours += delta_ra_hours
        self.camera.center_dec_degrees += delta_dec_degrees
        self.camera.clamp()
        self._scene_cache.clear()

    def rotate_by(self, delta_degrees: float) -> None:
        self.camera.view_azimuth_degrees += delta_degrees
        self.camera.center_ra_hours += delta_degrees / 15.0
        self.camera.clamp()
        self._scene_cache.clear()

    def reset_view(self) -> None:
        self.camera = SkyCamera()
        self._scene_cache.clear()

    def draw(self, width: int, height: int, viewport_x: int = 0, viewport_y: int = 0) -> None:
        self._frame_counter += 1
        if width <= 0 or height <= 0 or not _ensure_opengl():
            return
        scene = self.build_scene(width, height)

        glViewport(int(viewport_x), int(viewport_y), int(width), int(height))
        glEnable(GL_SCISSOR_TEST)
        glScissor(int(viewport_x), int(viewport_y), int(width), int(height))
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_LINE_SMOOTH)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0.0, float(width), 0.0, float(height), -1.0, 1.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glClearColor(0.015, 0.03, 0.08, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        self._draw_background(scene, width, height)

        for line in self._iter_visible_lines(scene):
            self._draw_line(line)
        self._draw_points(scene.stars)
        self._draw_points(scene.planets)
        glDisable(GL_SCISSOR_TEST)

    def _draw_points(self, points):
        if not points:
            return
        glBlendFunc(GL_SRC_ALPHA, GL_ONE)
        for point in points:
            color = self._boost_point_color(point.color, point.metadata.get("layer", ""))
            is_planet = point.metadata.get("layer") == "planets"
            glow_radius = max(6.0, point.radius * (3.5 if is_planet else 2.9))
            core_radius = max(2.6, point.radius * (1.85 if is_planet else 1.45))
            self._draw_disc(point.x, point.y, glow_radius, color, 0.42 if is_planet else 0.30)
            self._draw_disc(point.x, point.y, core_radius, color, 0.95)
            if is_planet:
                self._draw_disc(point.x, point.y, max(1.8, core_radius * 0.52), (1.0, 0.99, 0.92), 0.95)
            else:
                self._draw_disc(point.x, point.y, max(1.1, core_radius * 0.40), (1.0, 1.0, 1.0), 0.85)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _draw_line(self, line: Optional[SkyLine]) -> None:
        if line is None or not line.points:
            return
        width = max(1.0, line.width + self._line_width_bias(line))
        glow_alpha = self._line_glow_alpha(line)
        if glow_alpha > 0.0:
            glow_color = line.color
            self._emit_line(line, (glow_color[0], glow_color[1], glow_color[2], glow_alpha), width + 2.8)
        self._emit_line(line, self._line_rgba(line), width)

    def _draw_lines(self, lines):
        for line in lines:
            self._draw_line(line)

    def _emit_line(self, line: SkyLine, rgba, width: float) -> None:
        glColor4f(*rgba)
        glLineWidth(width)
        glBegin(GL_LINE_LOOP if line.closed else GL_LINE_STRIP)
        for x, y in line.points:
            glVertex2f(x, y)
        glEnd()

    def _iter_visible_lines(self, scene):
        seen = set()
        for line in [
            scene.dome_line,
            *scene.milky_way_lines,
            scene.equatorial_line,
            *scene.zodiac_lines,
            *scene.aspect_lines,
            *scene.constellation_boundaries,
            *scene.constellation_lines,
            *scene.planet_trails,
            scene.horizon_line,
        ]:
            if line is None or not line.points:
                continue
            signature = (
                line.closed,
                tuple((round(x, 2), round(y, 2)) for x, y in line.points),
            )
            if signature in seen:
                continue
            seen.add(signature)
            yield line

    def _line_rgba(self, line: SkyLine) -> Tuple[float, float, float, float]:
        layer = line.metadata.get("layer", "")
        if layer == "horizon":
            return (0.34, 0.96, 0.60, 0.96)
        if layer == "milky-way":
            band = line.metadata.get("band", "")
            alpha = 0.16 if band == "milky-way-core" else 0.10
            return (*line.color, alpha)
        if layer == "equator":
            return (*line.color, 0.92)
        if layer == "zodiac-sectors":
            return (*line.color, 0.82)
        if layer == "zodiac-ring":
            return (*line.color, 0.46)
        if layer == "zodiac-boundaries":
            return (*line.color, 0.66)
        if layer == "dome":
            return (0.52, 0.62, 0.92, 0.78)
        if layer == "planet-trails":
            return (1.0, 0.82, 0.36, 0.82)
        if layer == "aspect-lines":
            kind = line.metadata.get("kind", "")
            alpha = 0.96 if kind == "exact" else 0.90 if kind == "applying" else 0.82
            return (*line.color, alpha)
        if layer == "constellation-boundaries":
            return (*line.color, 0.18)
        return (0.72, 0.82, 1.0, 0.76)

    def _line_width_bias(self, line: SkyLine) -> float:
        layer = line.metadata.get("layer", "")
        if layer == "horizon":
            return 1.1
        if layer == "milky-way":
            return 3.4
        if layer == "equator":
            return 0.9
        if layer == "zodiac-sectors":
            return 1.0
        if layer == "zodiac-ring":
            return 0.4
        if layer == "zodiac-boundaries":
            return 0.6
        if layer == "dome":
            return 0.8
        if layer == "aspect-lines":
            return 0.6
        if layer == "constellation-boundaries":
            return 2.6
        return 0.45

    def _line_glow_alpha(self, line: SkyLine) -> float:
        layer = line.metadata.get("layer", "")
        if layer == "horizon":
            return 0.20
        if layer == "milky-way":
            return 0.06
        if layer == "equator":
            return 0.16
        if layer == "zodiac-sectors":
            return 0.18
        if layer == "zodiac-ring":
            return 0.10
        if layer == "zodiac-boundaries":
            return 0.12
        if layer == "aspect-lines":
            return 0.24
        if layer == "planet-trails":
            return 0.12
        if layer == "constellation-boundaries":
            return 0.14
        return 0.0

    def _boost_point_color(self, color: Tuple[float, float, float], layer: str) -> Tuple[float, float, float]:
        floor = 0.82 if layer == "planets" else 0.76
        return tuple(max(floor, min(1.0, channel * 1.35)) for channel in color)

    def _draw_background(self, scene, width: int, height: int) -> None:
        horizon_y = height * 0.38
        if scene.horizon_line is not None and scene.horizon_line.points:
            horizon_y = sum(point[1] for point in scene.horizon_line.points) / len(scene.horizon_line.points)

        self._draw_vertical_strip(width, 0.0, height, (0.008, 0.012, 0.05, 1.0), (0.04, 0.07, 0.16, 1.0))
        self._draw_vertical_strip(width, 0.0, max(0.0, horizon_y * 0.45), (0.07, 0.10, 0.19, 1.0), (0.10, 0.15, 0.25, 1.0))
        self._draw_vertical_strip(width, max(0.0, horizon_y * 0.45), max(0.0, horizon_y), (0.10, 0.15, 0.25, 1.0), (0.14, 0.21, 0.34, 1.0))
        glow_half_height = max(40.0, min(height * 0.14, 90.0))
        self._draw_vertical_strip(
            width,
            max(0.0, horizon_y - glow_half_height),
            min(float(height), horizon_y + glow_half_height),
            (0.14, 0.26, 0.44, 0.0),
            (0.20, 0.34, 0.56, 0.30),
        )
        self._draw_vertical_strip(
            width,
            min(float(height), horizon_y + glow_half_height),
            min(float(height), horizon_y + (glow_half_height * 2.2)),
            (0.12, 0.20, 0.36, 0.18),
            (0.06, 0.09, 0.16, 0.0),
        )

    def _draw_vertical_strip(self, width: float, y0: float, y1: float, bottom_rgba, top_rgba) -> None:
        if y1 <= y0:
            return
        glBegin(GL_TRIANGLE_STRIP)
        glColor4f(*bottom_rgba)
        glVertex2f(0.0, y0)
        glVertex2f(width, y0)
        glColor4f(*top_rgba)
        glVertex2f(0.0, y1)
        glVertex2f(width, y1)
        glEnd()

    def _draw_disc(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        color: Tuple[float, float, float],
        alpha: float,
        segments: int = 18,
    ) -> None:
        glColor4f(color[0], color[1], color[2], alpha)
        glBegin(GL_TRIANGLE_FAN)
        glVertex2f(center_x, center_y)
        for index in range(segments + 1):
            angle = (math.tau * index) / segments
            glVertex2f(
                center_x + (math.cos(angle) * radius),
                center_y + (math.sin(angle) * radius),
            )
        glEnd()
