"""Kivy host widget for the live sky panel (canvas-rendered).

All drawing goes through Kivy's canvas instructions, which is GLES2-safe and
therefore works on Huawei/Android phones.  The separate immediate-mode
OpenGL renderer in ``astronomy.opengl`` is retired: ``set_use_opengl`` always
keeps the canvas path active.
"""

from __future__ import annotations

import math

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import (
    Color,
    Ellipse,
    Fbo,
    InstructionGroup,
    Line,
    Mesh,
    Rectangle,
    StencilPop,
    StencilPush,
    StencilUse,
)
from kivy.graphics.texture import Texture
from kivy.logger import Logger
from kivy.properties import ObjectProperty
from kivy.uix.widget import Widget

from ..catalogs import ConstellationLabel, ConstellationLine, StarRecord
from ..milky_way import milky_way_texture
from ..models import AstronomySnapshot
from ..opengl import SkyRenderer
from ..planet_textures import planet_sprite_texture
from ..skyframes import altaz_to_galactic, julian_day_for


class SkyViewportWidget(Widget):
    """Widget that hosts the separate OpenGL renderer."""

    renderer = ObjectProperty(None)
    _POINTER_BUTTONS = {"", "left", "middle", "right"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.renderer = SkyRenderer()
        self.last_render_error = ""
        self._overlay_instruction_count = 0
        self._overlay_label_count = 0
        self._label_texture_cache = {}
        self._milky_way_mesh_cache = {}
        self._milky_way_texture = None
        self._gl_supported = bool(self.renderer.opengl_available)
        self._use_gl_callback = False
        self._gl_fbo = None
        self._gl_rect = None
        self._pending_gl_validation_frames = 0
        self._rendering_gl = False
        self._gl_surface_group = InstructionGroup()
        self.canvas.add(self._gl_surface_group)
        self._overlay_group = InstructionGroup()
        self.canvas.after.add(self._overlay_group)
        self._overlay_trigger = Clock.create_trigger(self._refresh_overlay, 0)
        self.bind(size=self._on_geometry_changed, pos=self._on_geometry_changed)
        self._frame_event = None
        self.set_use_opengl(self.renderer.config.use_opengl_renderer)
        Clock.schedule_once(self._request_initial_render, 0)

    def on_parent(self, *_args):
        if self.parent is None:
            self._stop_frame_loop()
            self._destroy_gl_surface()

    def _ensure_gl_surface(self):
        width, height = self._scene_size()
        if width <= 0 or height <= 0:
            return
        size = (width, height)
        if self._gl_fbo is not None and tuple(map(int, self._gl_fbo.size)) == size:
            if self._gl_rect is not None:
                self._gl_rect.pos = self.pos
                self._gl_rect.size = self.size
            return
        self._destroy_gl_surface()
        self._gl_fbo = Fbo(size=size, with_stencilbuffer=False)
        self._gl_surface_group.clear()
        self._gl_surface_group.add(Color(1.0, 1.0, 1.0, 1.0))
        self._gl_rect = Rectangle(
            texture=self._gl_fbo.texture,
            pos=self.pos,
            size=self.size,
            tex_coords=(0, 1, 1, 1, 1, 0, 0, 0),
        )
        self._gl_surface_group.add(self._gl_rect)

    def _destroy_gl_surface(self):
        self._gl_surface_group.clear()
        self._gl_rect = None
        self._gl_fbo = None

    def _start_frame_loop(self):
        return

    def _stop_frame_loop(self):
        if self._frame_event is not None:
            self._frame_event.cancel()
            self._frame_event = None

    def set_use_opengl(self, enabled: bool) -> bool:
        """Retired renderer switch.

        The separate immediate-mode OpenGL renderer is kept for reference only
        and is never enabled: it cannot run on GLES2 targets (Huawei/Android)
        and it duplicated the Kivy canvas renderer.  Everything renders through
        the Kivy canvas now.
        """
        if self._use_gl_callback:
            self._use_gl_callback = False
            self._stop_frame_loop()
            self._destroy_gl_surface()
            self._pending_gl_validation_frames = 0
        self.request_render()
        return False

    @property
    def opengl_available(self) -> bool:
        return self._gl_supported

    def _request_initial_render(self, *_args):
        self.request_render()

    def _on_geometry_changed(self, *_args):
        if self._use_gl_callback:
            self._ensure_gl_surface()
        self.request_render()

    def request_render(self):
        if self._use_gl_callback:
            self._ensure_gl_surface()
            self._render_gl()
            self._validate_gl_surface_if_needed()
        if self.canvas is not None:
            self.canvas.ask_update()
        self._overlay_trigger()

    def _tick(self, *_args):
        self.request_render()

    def _refresh_overlay(self, *_args):
        try:
            width, height = self._scene_size()
            scene = self.renderer.build_scene(width, height)
            self._redraw_overlay(
                scene,
                labels_only=self._use_gl_callback,
                include_texture=scene.metadata.get("milky_way_mode") == "texture",
            )
        except Exception:
            Logger.exception("SkyViewportWidget overlay refresh failed")

    def _render_gl(self, *_args):
        if not self._use_gl_callback:
            return
        try:
            if self._gl_fbo is None:
                self._ensure_gl_surface()
            if self._gl_fbo is None:
                return
            if self._rendering_gl:
                return
            self._rendering_gl = True
            width, height = self._scene_size()
            self._gl_fbo.bind()
            try:
                self.renderer.draw(width, height, viewport_x=0, viewport_y=0)
            finally:
                self._gl_fbo.release()
            self.last_render_error = ""
        except Exception as exc:
            self.last_render_error = str(exc)
            Clock.schedule_once(lambda _dt, reason=str(exc): self._fallback_to_kivy(reason), 0)
            Logger.exception("SkyViewportWidget render failed")
        finally:
            self._rendering_gl = False

    def _fallback_to_kivy(self, reason: str):
        self.last_render_error = f"{reason}; switched to Kivy fallback."
        self.set_use_opengl(False)

    def _validate_gl_surface_if_needed(self):
        if not self._use_gl_callback or self._pending_gl_validation_frames <= 0:
            return
        scene = self.get_scene()
        self._pending_gl_validation_frames -= 1
        if not self._scene_has_visible_content(scene):
            return
        if self._gl_surface_appears_blank():
            self._fallback_to_kivy("OpenGL surface rendered blank output")

    def _scene_has_visible_content(self, scene) -> bool:
        if scene is None:
            return False
        return bool(
            scene.stars
            or scene.planets
            or scene.constellation_lines
            or scene.planet_trails
            or scene.horizon_line is not None
            or scene.dome_line is not None
        )

    def _gl_surface_appears_blank(self) -> bool:
        if self._gl_fbo is None or getattr(self._gl_fbo, "texture", None) is None:
            return False
        texture = self._gl_fbo.texture
        width = int(getattr(texture, "width", 0) or 0)
        height = int(getattr(texture, "height", 0) or 0)
        if width <= 0 or height <= 0:
            return False
        try:
            buf = texture.pixels
        except Exception:
            Logger.exception("SkyViewportWidget could not inspect OpenGL surface pixels")
            return False
        if not buf:
            return True
        clear_rgb = (4, 8, 20)
        stride = width * 4
        sample_step_x = max(1, width // 24)
        sample_step_y = max(1, height // 16)
        non_background = 0
        total = 0
        for y in range(0, height, sample_step_y):
            row_offset = y * stride
            for x in range(0, width, sample_step_x):
                total += 1
                index = row_offset + (x * 4)
                r = buf[index]
                g = buf[index + 1]
                b = buf[index + 2]
                a = buf[index + 3]
                if a <= 8:
                    continue
                if abs(r - clear_rgb[0]) <= 10 and abs(g - clear_rgb[1]) <= 10 and abs(b - clear_rgb[2]) <= 10:
                    continue
                non_background += 1
                if non_background >= 6:
                    return False
        return total > 0 and non_background < 6

    def _redraw_overlay(self, scene, labels_only=False, include_texture=False):
        self._overlay_group.clear()
        self._overlay_instruction_count = 0
        self._overlay_label_count = 0

        if scene is None:
            return

        # Clip every overlay instruction to the widget bounds: great-circle
        # lines (equator, horizon, zodiac ring) now keep all their visible
        # samples and run past the edges, so they must not bleed over
        # neighbouring widgets.
        self._overlay_group.add(StencilPush())
        self._overlay_group.add(Color(1, 1, 1, 1))
        self._overlay_group.add(
            Rectangle(
                pos=(self.x - 2, self.y - 2),
                size=(self.width + 4, self.height + 4),
            )
        )
        # Enable the stencil test so subsequent drawing is clipped to the
        # rectangle we just drew into the stencil buffer.
        self._overlay_group.add(StencilUse())

        if include_texture:
            self._draw_milky_way_texture(scene)

        if not labels_only:
            self._draw_overlay_background(scene)

            for line in self._iter_overlay_lines(scene):
                if len(line.points) < 2:
                    continue
                # Great circles (horizon, equator, zodiac) may have multiple
                # visible segments - draw each one so the line reads as a
                # complete arc, not a single fragment.
                segments = line.metadata.get("segments") or [line.points]
                for segment in segments:
                    if len(segment) < 2:
                        continue
                    points = []
                    for x, y in segment:
                        points.extend([self.x + x, self.y + y])
                    glow_rgba = self._line_glow_rgba(line)
                    if glow_rgba is not None:
                        self._overlay_group.add(Color(*glow_rgba))
                        self._overlay_group.add(
                            Line(
                                points=points,
                                width=max(1.5, line.width + self._line_width_bias(line) + 2.0),
                                close=line.closed,
                            )
                        )
                    self._overlay_group.add(Color(*self._line_rgba(line)))
                    self._overlay_group.add(
                        Line(
                            points=points,
                            width=max(1.0, line.width + self._line_width_bias(line)),
                            close=line.closed,
                        )
                    )
                    self._overlay_instruction_count += 1

            glyph_scale = self._glyph_scale()
            for point in scene.stars:
                radius = max(1.1, point.radius * glyph_scale)
                glow_radius = radius * 2.2
                glow_r, glow_g, glow_b = point.color
                self._overlay_group.add(Color(glow_r, glow_g, glow_b, 0.22))
                self._overlay_group.add(
                    Ellipse(
                        pos=(self.x + point.x - glow_radius, self.y + point.y - glow_radius),
                        size=(glow_radius * 2.0, glow_radius * 2.0),
                    )
                )
                self._overlay_group.add(Color(*point.color, 0.95))
                core_radius = max(1.25, radius * 0.82)
                self._overlay_group.add(
                    Ellipse(
                        pos=(self.x + point.x - core_radius, self.y + point.y - core_radius),
                        size=(core_radius * 2.0, core_radius * 2.0),
                    )
                )
                self._overlay_instruction_count += 1

        self._draw_planet_sprites(scene.planets)
        for label in self._iter_overlay_labels(scene):
            self._draw_overlay_label(label)

        self._overlay_group.add(StencilPop())

    def _draw_milky_way_texture(self, scene):
        texture = self._ensure_milky_way_texture()
        if texture is None:
            return
        vertices, indices = self._milky_way_mesh(scene)
        if not vertices or not indices:
            return
        alpha = 0.58 if self._use_gl_callback else 0.72
        self._overlay_group.add(Color(1.0, 1.0, 1.0, alpha))
        self._overlay_group.add(
            Mesh(
                vertices=vertices,
                indices=indices,
                texture=texture,
                mode="triangles",
            )
        )
        self._overlay_instruction_count += 1

    def _ensure_milky_way_texture(self) -> Texture | None:
        if self._milky_way_texture is None:
            try:
                self._milky_way_texture = milky_way_texture(
                    path=self.renderer.config.milky_way_texture_path,
                )
            except Exception:
                Logger.exception("SkyViewportWidget failed to build Milky Way texture")
                return None
        return self._milky_way_texture

    def _draw_planet_sprites(self, planets):
        glyph_scale = self._glyph_scale()
        for point in planets:
            texture = planet_sprite_texture(point.name, point.color, point.glyph)
            sprite_size = max(
                11.0,
                point.radius * (6.4 if point.name == "Saturn" else 5.2) * glyph_scale,
            )
            self._overlay_group.add(Color(1.0, 1.0, 1.0, 0.96))
            self._overlay_group.add(
                Rectangle(
                    texture=texture,
                    pos=(self.x + point.x - (sprite_size * 0.5), self.y + point.y - (sprite_size * 0.5)),
                    size=(sprite_size, sprite_size),
                )
            )
            self._overlay_instruction_count += 1

    def _milky_way_mesh(self, scene):
        """Build the Milky Way dome mesh in *angular* space.

        The dome is sampled on a degree-space grid over the current view cone
        (a high-resolution sphere section - "2K sphere" style), so:

        * the texture tracks the stars **exactly** - vertex positions use the
          same rectilinear maths as ``project_altaz``, eliminating the
          background/foreground parallax slip a quantised screen-space grid
          produced;
        * zooming in raises the dome's effective sampling density, so the
          texture keeps holding its native resolution at any zoom;
        * UVs use the pure-Python galactic mapping (no astropy on the
          per-frame path, which matters for lightweight phone targets).
        """
        camera = self.renderer.camera
        metadata = scene.metadata
        cache_key = (
            int(scene.width),
            int(scene.height),
            round(camera.view_azimuth_degrees, 4),
            round(camera.view_altitude_degrees, 4),
            round(camera.fov_degrees, 4),
            metadata.get("observer_latitude", ""),
            metadata.get("observer_longitude", ""),
            metadata.get("observer_altitude", ""),
            metadata.get("observer_jd_utc", ""),
        )
        cached = self._milky_way_mesh_cache.get(cache_key)
        if cached is not None:
            return cached

        columns = 36
        rows = 20
        fov = max(35.0, camera.fov_degrees)
        aspect = float(scene.width) / max(1.0, float(scene.height))
        tan_vertical = math.tan(math.radians(fov) / 2.0)
        tan_horizontal = tan_vertical * aspect
        half_vertical_degrees = fov / 2.0
        half_horizontal_degrees = math.degrees(math.atan(tan_horizontal))

        try:
            jd = float(metadata.get("observer_jd_utc", "") or julian_day_for())
        except (TypeError, ValueError):
            jd = julian_day_for()
        observer_latitude = float(metadata.get("observer_latitude", "0.0") or 0.0)
        observer_longitude = float(metadata.get("observer_longitude", "0.0") or 0.0)

        # 1% overdraw around the widget so triangle rasterisation never leaves
        # a seam at the borders.
        overdraw = 1.01
        vertices = []
        grid = []
        vertex_index = 0
        for row in range(rows + 1):
            row_fraction = row / rows
            relative_altitude = half_vertical_degrees - (
                2.0 * half_vertical_degrees * row_fraction
            )
            world_altitude = max(
                -89.5, min(89.5, camera.view_altitude_degrees + relative_altitude)
            )
            actual_relative_altitude = world_altitude - camera.view_altitude_degrees
            ny = math.tan(math.radians(actual_relative_altitude)) / tan_vertical
            y = (scene.height * 0.5) * (1.0 + ny * overdraw)
            row_indices = []
            for col in range(columns + 1):
                col_fraction = col / columns
                relative_azimuth = -half_horizontal_degrees + (
                    2.0 * half_horizontal_degrees * col_fraction
                )
                world_azimuth = (camera.view_azimuth_degrees + relative_azimuth) % 360.0
                nx = math.tan(math.radians(relative_azimuth)) / tan_horizontal
                x = (scene.width * 0.5) * (1.0 + nx * overdraw)
                galactic_longitude, galactic_latitude = altaz_to_galactic(
                    world_azimuth,
                    world_altitude,
                    observer_latitude,
                    observer_longitude,
                    jd,
                )
                u, v = self._milky_way_uv_from_galactic(galactic_longitude, galactic_latitude)
                vertices.extend([self.x + x, self.y + y, u, v])
                row_indices.append(vertex_index)
                vertex_index += 1
            grid.append(row_indices)

        indices = []
        for row in range(rows):
            for col in range(columns):
                top_left = grid[row][col]
                top_right = grid[row][col + 1]
                bottom_left = grid[row + 1][col]
                bottom_right = grid[row + 1][col + 1]
                indices.extend(
                    [top_left, bottom_left, top_right, top_right, bottom_left, bottom_right]
                )

        self._milky_way_mesh_cache = {cache_key: (vertices, indices)}
        return vertices, indices

    def _milky_way_uv_from_galactic(self, longitude_deg: float, latitude_deg: float):
        """Map galactic (l, b) to texture (u, v).

        The bundled NASA WISE full-sky panorama is an equirectangular
        galactic map with the galactic centre near the horizontal middle and
        +b toward the top.  The offsets are configurable via the
        SkySceneConfig.milky_way_* settings so a different panorama asset can
        be aligned without code changes.
        """
        config = self.renderer.config
        longitude = longitude_deg % 360.0
        if config.milky_way_reverse_longitude:
            longitude = (360.0 - longitude) % 360.0
        longitude_center = float(config.milky_way_longitude_center)
        u = (longitude / 360.0 + longitude_center) % 1.0
        v = 1.0 - ((latitude_deg + 90.0) / 180.0)
        if config.milky_way_flip_v:
            v = 1.0 - v
        return u, max(0.0, min(1.0, v))

    def _draw_overlay_background(self, scene):
        width = max(1.0, float(scene.width))
        height = max(1.0, float(scene.height))
        strips = [
            (0.00, 0.22, (0.05, 0.09, 0.16, 0.18)),
            (0.22, 0.45, (0.04, 0.07, 0.14, 0.14)),
            (0.45, 0.72, (0.03, 0.05, 0.11, 0.10)),
            (0.72, 1.00, (0.02, 0.03, 0.09, 0.08)),
        ]
        for start, end, rgba in strips:
            self._overlay_group.add(Color(*rgba))
            self._overlay_group.add(
                Rectangle(
                    pos=(self.x, self.y + (height * start)),
                    size=(width, max(1.0, height * (end - start))),
                )
            )
        if scene.horizon_line is not None and scene.horizon_line.points:
            horizon_y = sum(point[1] for point in scene.horizon_line.points) / len(scene.horizon_line.points)
            glow_height = max(20.0, min(height * 0.12, 64.0))
            self._overlay_group.add(Color(0.14, 0.26, 0.44, 0.18))
            self._overlay_group.add(
                Rectangle(
                    pos=(self.x, self.y + horizon_y - glow_height),
                    size=(width, glow_height * 2.0),
                )
            )

    def _line_rgba(self, line):
        layer = line.metadata.get("layer", "")
        if layer == "horizon":
            return (0.22, 0.84, 0.52, 0.95)
        if layer == "milky-way":
            band = line.metadata.get("band", "")
            alpha = 0.14 if band == "milky-way-core" else 0.08
            return (*line.color, alpha)
        if layer == "equator":
            return (*line.color, 0.92)
        if layer == "zodiac-sectors":
            return (*line.color, 0.76)
        if layer == "zodiac-ring":
            return (*line.color, 0.46)
        if layer == "zodiac-boundaries":
            return (*line.color, 0.60)
        if layer == "dome":
            return (0.34, 0.42, 0.74, 0.72)
        if layer == "planet-trails":
            return (0.92, 0.74, 0.34, 0.68)
        if layer == "aspect-lines":
            return (*line.color, 0.82)
        if layer == "constellation-boundaries":
            return (*line.color, 0.18)
        # Constellation stick lines connect stars into recognizable shapes.
        return (0.55, 0.65, 0.98, 0.42)

    def _line_width_bias(self, line):
        layer = line.metadata.get("layer", "")
        if layer == "horizon":
            return 0.8
        if layer == "milky-way":
            return 3.0
        if layer == "equator":
            return 0.7
        if layer == "zodiac-sectors":
            return 0.8
        if layer == "zodiac-ring":
            return 0.3
        if layer == "zodiac-boundaries":
            return 0.4
        if layer == "dome":
            return 0.5
        if layer == "aspect-lines":
            return 0.4
        if layer == "constellation-boundaries":
            return 1.4
        return 0.16

    def _line_glow_rgba(self, line):
        layer = line.metadata.get("layer", "")
        if layer == "horizon":
            return (0.24, 0.90, 0.58, 0.20)
        if layer == "milky-way":
            return (*line.color, 0.06)
        if layer == "equator":
            return (*line.color, 0.18)
        if layer == "zodiac-sectors":
            return (*line.color, 0.16)
        if layer == "zodiac-ring":
            return (*line.color, 0.10)
        if layer == "zodiac-boundaries":
            return (*line.color, 0.10)
        if layer == "aspect-lines":
            return (*line.color, 0.22)
        if layer == "planet-trails":
            return (0.96, 0.82, 0.42, 0.12)
        if layer == "constellation-boundaries":
            return (*line.color, 0.05)
        return None

    def _iter_overlay_labels(self, scene):
        for label in scene.star_labels:
            yield label
        for label in scene.planet_labels:
            yield label
        for label in scene.aspect_labels:
            yield label
        for label in scene.horizon_labels:
            yield label
        for label in scene.zodiac_labels:
            yield label
        for label in scene.constellation_labels:
            yield label

    def _label_texture(self, text, color, font_size):
        cache_key = (text, tuple(round(component, 3) for component in color), font_size)
        if cache_key in self._label_texture_cache:
            return self._label_texture_cache[cache_key]
        label = CoreLabel(text=text, font_size=font_size, color=color)
        label.refresh()
        texture = label.texture
        self._label_texture_cache[cache_key] = texture
        return texture

    def _glyph_scale(self) -> float:
        """Scale fixed-size overlay glyphs with the viewport height.

        Label fonts (24-36 px) and sprite sizes were tuned for desktop-height
        panels; on short-wide panels they dominated the view and made the sky
        feel "zoomed in".
        """
        height = float(self.height) if self.height and self.height > 0 else 640.0
        return max(0.55, min(1.15, height / 640.0))

    def _font_size_for_label(self, label):
        layer = label.metadata.get("layer", "")
        scale = self._glyph_scale()
        if layer == "constellation-labels":
            size = 24
        elif layer == "horizon-labels":
            size = 32
        elif layer == "zodiac-labels":
            size = 34
        elif layer == "aspect-labels":
            size = 28
        elif label.priority >= 4:
            size = 30
        else:
            size = 24
        return max(11, int(round(size * scale)))

    def _draw_overlay_label(self, label):
        layer = label.metadata.get("layer", "")
        font_size = self._font_size_for_label(label)
        if layer == "constellation-labels":
            rgba = (label.color[0], label.color[1], label.color[2], 0.45)
        else:
            rgba = (label.color[0], label.color[1], label.color[2], 0.96)
        shadow = self._label_texture(label.text, (0.08, 0.10, 0.14, 0.92), font_size)
        texture = self._label_texture(label.text, rgba, font_size)
        shadow_pos = (self.x + label.x + 1.0, self.y + label.y - 1.0)
        text_pos = (self.x + label.x, self.y + label.y)
        backdrop = (0.03, 0.04, 0.08, 0.52)
        if layer == "planet-labels":
            backdrop = (label.color[0] * 0.20, label.color[1] * 0.18, label.color[2] * 0.18, 0.62)
        elif layer == "aspect-labels":
            backdrop = (label.color[0] * 0.16, label.color[1] * 0.16, label.color[2] * 0.18, 0.58)
        elif layer == "constellation-labels":
            backdrop = (0.10, 0.12, 0.22, 0.56)
        elif layer == "horizon-labels":
            backdrop = (0.08, 0.16, 0.12, 0.60)
        elif layer == "zodiac-labels":
            backdrop = (0.12, 0.10, 0.18, 0.62)
        self._overlay_group.add(Color(*backdrop))
        self._overlay_group.add(
            Rectangle(
                pos=(text_pos[0] - 5.0, text_pos[1] - 4.0),
                size=(texture.size[0] + 10.0, texture.size[1] + 8.0),
            )
        )
        self._overlay_group.add(Color(1.0, 1.0, 1.0, 1.0))
        self._overlay_group.add(Rectangle(texture=shadow, pos=shadow_pos, size=shadow.size))
        self._overlay_group.add(Rectangle(texture=texture, pos=text_pos, size=texture.size))
        self._overlay_instruction_count += 1
        self._overlay_label_count += 1

    def _iter_overlay_lines(self, scene):
        if scene.dome_line is not None:
            yield scene.dome_line
        for line in scene.milky_way_lines:
            yield line
        if scene.equatorial_line is not None:
            yield scene.equatorial_line
        for line in scene.zodiac_lines:
            yield line
        for line in scene.aspect_lines:
            yield line
        for line in scene.constellation_boundaries:
            yield line
        for line in scene.constellation_lines:
            yield line
        for line in scene.planet_trails:
            yield line
        if scene.horizon_line is not None:
            yield scene.horizon_line

    def load_star_catalog(self, records):
        self.renderer.load_star_catalog(records)
        self.request_render()

    def load_constellation_lines(self, records):
        self.renderer.load_constellation_lines(records)
        self.request_render()

    def load_constellation_labels(self, records):
        self.renderer.load_constellation_labels(records)
        self.request_render()

    def load_constellation_boundaries(self, records):
        self.renderer.load_constellation_boundaries(records)
        self.request_render()

    def set_snapshot(self, snapshot: AstronomySnapshot):
        self.renderer.set_snapshot(snapshot)
        self.request_render()

    def zoom(self, factor: float):
        self.renderer.zoom_by(factor)
        self.request_render()

    def rotate(self, delta_degrees: float):
        self.renderer.rotate_by(delta_degrees)
        self.request_render()

    def pan(self, delta_ra_hours: float, delta_dec_degrees: float):
        self.renderer.pan_by(delta_ra_hours, delta_dec_degrees)
        self.request_render()

    def reset_view(self):
        self.renderer.reset_view()
        self.request_render()

    def _scene_size(self):
        width = int(self.width)
        height = int(self.height)
        if width > 0 and height > 0:
            return width, height
        fallback_width, fallback_height = Window.size
        return max(1, int(fallback_width)), max(1, int(fallback_height))

    def _render_region(self):
        width = int(self.width)
        height = int(self.height)
        if width > 0 and height > 0:
            window_x, window_y = self.to_window(self.x, self.y, initial=False, relative=False)
            return (
                max(0, int(window_x)),
                max(0, int(window_y)),
                width,
                height,
            )
        fallback_width, fallback_height = self._scene_size()
        return 0, 0, fallback_width, fallback_height

    def get_scene(self):
        width, height = self._scene_size()
        return self.renderer.build_scene(width, height)

    def set_layer_option(self, name: str, enabled: bool):
        self.renderer.set_layer_option(name, enabled)
        self.request_render()

    def toggle_layer_option(self, name: str) -> bool:
        enabled = self.renderer.toggle_layer_option(name)
        self.request_render()
        return enabled

    def get_layer_option(self, name: str) -> bool:
        return self.renderer.get_layer_option(name)

    def get_buffers(self):
        width, height = self._scene_size()
        return self.renderer.get_buffers(width, height)

    @property
    def using_opengl(self) -> bool:
        return self._use_gl_callback

    def on_touch_down(self, touch):
        button = getattr(touch, "button", "")
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if button == "scrollup":
            self.zoom(1.1)
            return True
        if button == "scrolldown":
            self.zoom(0.9)
            return True
        if button in self._POINTER_BUTTONS:
            touch.ud["sky_anchor"] = touch.pos
            touch.ud["sky_button"] = button or "left"
            if hasattr(touch, "grab"):
                touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        grab_current = getattr(touch, "grab_current", None)
        anchor = touch.ud.get("sky_anchor")
        if grab_current is not self and anchor is None and not self.collide_point(*touch.pos):
            return super().on_touch_move(touch)
        if anchor is None:
            return super().on_touch_move(touch)
        dx = touch.pos[0] - anchor[0]
        dy = touch.pos[1] - anchor[1]
        button = touch.ud.get("sky_button", "left")
        if button in {"", "left", "middle"}:
            # "Grab the sky" dragging: the look direction moves opposite to
            # the drag so the sky follows the finger, with the drag speed
            # matched to the displayed field of view (the horizontal span
            # grows with the widget aspect ratio).
            fov = max(35.0, self.renderer.camera.fov_degrees)
            aspect = float(self.width) / max(1.0, float(self.height))
            horizontal_span = 2.0 * math.degrees(
                math.atan(math.tan(math.radians(fov) / 2.0) * aspect)
            )
            degrees_per_pixel_x = horizontal_span / max(120.0, float(self.width))
            degrees_per_pixel_y = fov / max(120.0, float(self.height))
            self.pan(-(dx * degrees_per_pixel_x) / 15.0, -(dy * degrees_per_pixel_y))
        elif button == "right":
            self.rotate(dx * 0.2)
        touch.ud["sky_anchor"] = touch.pos
        return True

    def on_touch_up(self, touch):
        if touch.ud.get("sky_anchor") is None and getattr(touch, "grab_current", None) is not self:
            return super().on_touch_up(touch)
        touch.ud.pop("sky_anchor", None)
        touch.ud.pop("sky_button", None)
        if hasattr(touch, "ungrab"):
            touch.ungrab(self)
        return True
