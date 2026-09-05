"""Interactive natal chart wheel.

Draws the natal chart as a circular wheel on a Kivy canvas:

  * outer zodiac ring, colour-coded by element, with sign abbreviations
  * house cusp lines + house numbers
  * planet markers (two-letter glyphs) at their ecliptic longitudes
  * aspect lines between planets, colour-coded by aspect family
  * ASC / MC axis

Interaction: tap a planet glyph, a zodiac sign glyph or an aspect line to
select it. The widget dispatches ``on_planet_selected(planet_name)``,
``on_sign_selected(sign_name)`` and ``on_aspect_selected(aspect)`` so the
enclosing screen can show interpretive text (see ``core.interpretation``).

Geometry helpers are module-level pure functions so they can be unit-tested
without a running app.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Optional

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Canvas, Color, Ellipse, Line, PushMatrix, PopMatrix,
                           Rectangle, Translate, Triangle)
from kivy.uix.widget import Widget

from core import constants as C


# ---------------------------------------------------------------------------
# Pure geometry helpers (no Kivy state — unit-testable)
# ---------------------------------------------------------------------------
def lon_to_angle(lon: float) -> float:
    """Ecliptic longitude -> screen angle in RADIANS.

    Traditional wheel: 0 deg Aries at the 9 o'clock position (left) and
    longitudes increase counter-clockwise. The returned value is
    ``radians(180 + lon)`` (not normalised to [0, 2π)); ``cos``/``sin`` in
    :func:`point_on_circle` are periodic, so 0 deg Aries left, 0 deg Cancer up
    and 0 deg Capricorn down.
    """
    return math.radians(180.0 + (lon % 360.0))


def point_on_circle(cx: float, cy: float, r: float, lon: float):
    """(x, y) on a circle of radius ``r`` at ecliptic longitude ``lon``."""
    a = lon_to_angle(lon)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def seg_distance(px: float, py: float,
                 x1: float, y1: float, x2: float, y2: float) -> float:
    """Distance from point (px, py) to the segment (x1, y1)-(x2, y2)."""
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


# ---------------------------------------------------------------------------
# Colours / glyphs
# ---------------------------------------------------------------------------
ELEMENT_COLORS = {
    "Fire": (0.85, 0.38, 0.28),
    "Earth": (0.42, 0.68, 0.36),
    "Air": (0.85, 0.78, 0.34),
    "Water": (0.34, 0.55, 0.85),
}

ASPECT_COLORS = {
    "Conjunction": (0.55, 0.35, 0.80),
    "Opposition": (0.90, 0.28, 0.24),
    "Square": (0.90, 0.28, 0.24),
    "Trine": (0.25, 0.60, 0.90),
    "Sextile": (0.25, 0.70, 0.55),
}
MINOR_ASPECT_COLOR = (0.55, 0.55, 0.58)

PLANET_ABBR = {
    C.SUN: "Su", C.MOON: "Mo", C.MERCURY: "Me", C.VENUS: "Ve", C.MARS: "Ma",
    C.JUPITER: "Ju", C.SATURN: "Sa", C.URANUS: "Ur", C.NEPTUNE: "Ne",
    C.PLUTO: "Pl", C.MEAN_NODE: "Nd", C.TRUE_NODE: "Nd", C.CHIRON: "Ch",
}

# Unicode astrological glyphs. These need a system font that actually
# contains them (Segoe UI Symbol / Apple Symbols / DejaVu Sans / Noto).
PLANET_GLYPH = {
    C.SUN: "\u2609",          # ☉
    C.MOON: "\u263d",         # ☽
    C.MERCURY: "\u263f",      # ☿
    C.VENUS: "\u2640",        # ♀
    C.MARS: "\u2642",         # ♂
    C.JUPITER: "\u2643",      # ♃
    C.SATURN: "\u2644",       # ♄
    C.URANUS: "\u2645",       # ♅
    C.NEPTUNE: "\u2646",      # ♆
    C.PLUTO: "\u2647",        # ♇
    C.MEAN_NODE: "\u260a",    # ☊
    C.TRUE_NODE: "\u260a",    # ☊
    C.CHIRON: "\u26b7",       # ⚷
}

# Zodiac glyphs, indexed like C.SIGNS (Aries -> Pisces).
SIGN_GLYPH = [
    "\u2648", "\u2649", "\u264a", "\u264b", "\u264c", "\u264d",
    "\u264e", "\u264f", "\u2650", "\u2651", "\u2652", "\u2653",
]

_FONT_CANDIDATES = [
    # Windows (Segoe UI Symbol covers the astrological block).
    r"C:\Windows\Fonts\seguisym.ttf",
    # macOS.
    "/System/Library/Fonts/Apple Symbols.ttf",
    "/System/Library/Fonts/Supplemental/Apple Symbols.ttf",
    # Linux desktop fonts that include the block.
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansSymbols-Regular.ttf",
]

_glyph_font = None
_font_known = False


def glyph_font_path():
    """Return a system font that contains the astrological glyphs, or None.

    The result is cached so label creation stays cheap.
    """
    global _glyph_font, _font_known
    if _font_known:
        return _glyph_font
    _font_known = True
    windir = os.environ.get("WINDIR", r"C:\Windows")
    for cand in ([os.path.join(windir, "Fonts", "seguisym.ttf")]
                 if sys.platform == "win32" else []) + _FONT_CANDIDATES:
        if os.path.isfile(cand):
            _glyph_font = cand
            return _glyph_font
    return None
PLANET_COLOR = (0.16, 0.22, 0.42)
SELECT_COLOR = (1.00, 0.72, 0.10)


class ChartWheel(Widget):
    """Interactive circular natal chart.

    Attach a chart with :meth:`set_chart`; tap planets, zodiac sign glyphs or
    aspect lines to select. Dispatches ``on_planet_selected(planet_name)``,
    ``on_sign_selected(sign_name)`` and ``on_aspect_selected(aspect)``.
    """

    def __init__(self, **kwargs):
        for ev in ("on_planet_selected", "on_sign_selected",
                   "on_aspect_selected"):
            self.register_event_type(ev)
        super().__init__(**kwargs)

        self.chart = None
        self._layout = None                 # computed geometry (shared w/ hit-test)
        self._sel_planet: Optional[str] = None
        self._sel_aspect: Optional[int] = None
        self._sel_sign: Optional[str] = None
        self._trigger = None

        # All wheel art (rings, wedges, aspect lines AND glyph text) is drawn
        # into a dedicated sub-canvas of our own canvas; redraws clear ONLY
        # this sub-canvas. Text is rasterised into cached GL textures and
        # blitted as rectangles (see _text_texture): a child-widget label
        # layer does not follow the wheel in every render context, which was
        # the cause of invisible glyphs. Also never call self.canvas.clear():
        # add_widget() embeds child canvases inside the parent's canvas, so
        # clearing it would detach any child widget's canvas.
        self._art_canvas = Canvas()
        self.canvas.add(self._art_canvas)
        self._text_tex_cache = {}

        self.bind(size=self._on_resize, pos=self._on_resize)

    # -- events -------------------------------------------------------------
    def on_planet_selected(self, planet_name: str):
        """Event: a planet glyph was tapped."""

    def on_sign_selected(self, sign_name):
        """Event: a zodiac sign glyph was tapped."""

    def on_aspect_selected(self, aspect):
        """Event: an aspect line was tapped."""

    # -- public -------------------------------------------------------------
    def set_chart(self, chart) -> None:
        """Attach a ``core.models.Chart``; prepare layout + redraw."""
        self.chart = chart
        self._sel_planet = None
        self._sel_aspect = None
        self._sel_sign = None
        # Prepare synchronously so taps/queries work immediately; the
        # scheduled redraw re-runs after the layout pass settles sizes.
        self._prepare()
        self._schedule_redraw()

    def clear_selection(self) -> None:
        self._sel_planet = None
        self._sel_aspect = None
        self._sel_sign = None
        self._schedule_redraw()

    # -- internals: scheduling ---------------------------------------------
    def _on_resize(self, *_args):
        self._schedule_redraw()

    def _schedule_redraw(self, *_args):
        if self._trigger is not None:
            self._trigger.cancel()
        self._trigger = Clock.schedule_once(self._do_redraw, 0)

    def _do_redraw(self, *_args):
        self._prepare()
        self._redraw()

    def _prepare(self):
        """Compute shared geometry for drawing + hit-testing."""
        chart = self.chart
        if chart is None:
            self._layout = None
            return

        # Geometry is computed in local widget coordinates.
        cx, cy = self.width / 2.0, self.height / 2.0
        R = max(10.0, min(self.width, self.height) / 2.0 - 8.0)
        r_in = R * 0.86          # zodiac band inner edge
        r_sign = R * 0.93        # sign labels
        r_house = R * 0.80       # house numbers
        r_planet = R * 0.64      # planet glyph centre
        r_aspect = R * 0.60      # aspect line endpoints
        r_line_in = R * 0.18     # house / angle lines inner end

        # Signs (ring segments + labels).
        signs = []
        for i, name in enumerate(C.SIGNS):
            x, y = point_on_circle(cx, cy, r_sign, i * 30.0 + 15.0)
            signs.append({"name": name, "abbr": C.SIGNS_SHORT[i],
                          "glyph": SIGN_GLYPH[i],
                          "color": ELEMENT_COLORS[C.ELEMENTS[name]],
                          "start": i * 30.0, "x": x, "y": y})

        # House cusps + numbers.
        cusps, houses = [], []
        hlist = list(chart.houses)
        for i, h in enumerate(hlist):
            x1, y1 = point_on_circle(cx, cy, r_line_in, h.longitude)
            x2, y2 = point_on_circle(cx, cy, r_in, h.longitude)
            cusps.append({"number": h.number, "lon": h.longitude,
                          "x1": x1, "y1": y1, "x2": x2, "y2": y2})
            nxt = hlist[(i + 1) % 12].longitude
            delta = (nxt - h.longitude) % 360.0
            hx, hy = point_on_circle(cx, cy, r_house, h.longitude + delta / 2.0)
            houses.append({"number": h.number, "x": hx, "y": hy})

        # Planets (glyph centre uses a collision-adjusted display angle).
        min_gap = 9.0
        prev = None
        planets = []
        for p in sorted(chart.positions, key=lambda p: p.longitude):
            disp = p.longitude
            if prev is not None and (disp - prev) % 360.0 < min_gap:
                disp = prev + min_gap
            prev = disp
            gx, gy = point_on_circle(cx, cy, r_planet, disp)
            planets.append({"name": p.name,
                            "abbr": PLANET_ABBR.get(p.planet_id, "??"),
                            "glyph": PLANET_GLYPH.get(p.planet_id, ""),
                            "lon": p.longitude, "x": gx, "y": gy,
                            "retro": p.is_retrograde})

        # Aspect line segments (true longitudes).
        by_name = {p.name: p for p in chart.positions}
        aspects = []
        for a in chart.aspects:
            pa, pb = by_name.get(a.planet1_name), by_name.get(a.planet2_name)
            if pa is None or pb is None:
                continue
            x1, y1 = point_on_circle(cx, cy, r_aspect, pa.longitude)
            x2, y2 = point_on_circle(cx, cy, r_aspect, pb.longitude)
            aspects.append({"aspect": a, "x1": x1, "y1": y1,
                            "x2": x2, "y2": y2})

        # Angles (ASC / MC lines).
        angles = []
        for name in ("Ascendant", "MC"):
            lon = chart.angles.get(name)
            if lon is None:
                continue
            xi, yi = point_on_circle(cx, cy, r_line_in, lon)
            xo, yo = point_on_circle(cx, cy, r_in, lon)
            angles.append({"name": name, "lon": lon,
                           "x1": xi, "y1": yi, "x2": xo, "y2": yo})

        self._layout = {"cx": cx, "cy": cy, "R": R, "r_in": r_in,
                        "signs": signs, "cusps": cusps, "houses": houses,
                        "planets": planets, "aspects": aspects,
                        "angles": angles}

    def _redraw(self):
        # Clear only the wheel-art sub-canvas; NEVER self.canvas (that would
        # detach any child canvas embedded inside it).
        self._art_canvas.clear()
        lay = self._layout
        if lay is None or lay["R"] <= 12:
            return
        cx, cy, R = lay["cx"], lay["cy"], lay["R"]

        with self._art_canvas:
            # Canvas instructions for a plain Widget are drawn in the parent's
            # (or window's) coordinate system, so we push a translate by our own
            # position to make all coords below widget-local. This keeps the wheel
            # centered no matter where the widget sits on screen (e.g. inside the
            # Astro-Clock panel). The tap hit-test and the label layer already use
            # local coordinates, so everything now lines up.
            PushMatrix()
            Translate(self.x, self.y, 0)
            # 1) Filled zodiac wedges (colour = element; the selected sign
            #    wedge is highlighted instead).
            for sign in lay["signs"]:
                start = sign["start"]
                if self._sel_sign == sign["name"]:
                    Color(SELECT_COLOR[0], SELECT_COLOR[1],
                          SELECT_COLOR[2], 0.85)
                else:
                    col = sign["color"]
                    Color(col[0], col[1], col[2], 0.42)
                steps = 12
                for s in range(steps):
                    x1, y1 = point_on_circle(
                        cx, cy, R, start + 30.0 * s / steps)
                    x2, y2 = point_on_circle(
                        cx, cy, R, start + 30.0 * (s + 1) / steps)
                    # Triangle uses the standard vPosition vertex format that
                    # Kivy's default shader understands, so a plain Color
                    # instruction tints it. (A raw Mesh would need an explicit
                    # fmt matching the shader's vPosition/vTexCoords0.)
                    Triangle(points=[cx, cy, x1, y1, x2, y2])

            # 2) Ring outlines + degree ticks.
            Color(0.20, 0.20, 0.24, 1)
            Line(circle=(cx, cy, R), width=1.2)
            Line(circle=(cx, cy, lay["r_in"]), width=1.2)
            for d in range(0, 360, 10):
                x1, y1 = point_on_circle(cx, cy, R, d)
                x2, y2 = point_on_circle(cx, cy, lay["r_in"], d)
                Line(points=[x1, y1, x2, y2], width=0.7)

            # 3) House cusp lines.
            Color(0.45, 0.45, 0.52, 1)
            for c in lay["cusps"]:
                Line(points=[c["x1"], c["y1"], c["x2"], c["y2"]], width=1)

            # 4) ASC / MC axis (heavier).
            for ang in lay["angles"]:
                Color(0.10, 0.10, 0.14, 1)
                Line(points=[ang["x1"], ang["y1"], ang["x2"], ang["y2"]],
                     width=1.8)

            # 5) Aspect lines.
            for i, a in enumerate(lay["aspects"]):
                asp = a["aspect"]
                col = ASPECT_COLORS.get(asp.type_name, MINOR_ASPECT_COLOR)
                Color(col[0], col[1], col[2], 1)
                Line(points=[a["x1"], a["y1"], a["x2"], a["y2"]],
                     width=2.4 if self._sel_aspect == i else 1.1)

            # 6) Planet ticks + glyph circles.
            for p in lay["planets"]:
                x1, y1 = point_on_circle(cx, cy, lay["r_in"], p["lon"])
                x2, y2 = point_on_circle(cx, cy, R * 0.70, p["lon"])
                Color(0.30, 0.30, 0.36, 1)
                Line(points=[x1, y1, x2, y2], width=1)
                Color(PLANET_COLOR[0], PLANET_COLOR[1], PLANET_COLOR[2], 1)
                Ellipse(pos=(p["x"] - 13, p["y"] - 13), size=(26, 26))
                if self._sel_planet == p["name"]:
                    Color(SELECT_COLOR[0], SELECT_COLOR[1], SELECT_COLOR[2], 1)
                    Line(circle=(p["x"], p["y"], 17), width=2)

            # 7) Glyphs and small labels, drawn as cached text textures so they
            #    land on the same canvas as the art (child-widget layers do
            #    not track the wheel in every render context).
            astro_font = glyph_font_path()
            Color(1, 1, 1, 1)

            def blit(text, x, y, size_px, color, astro=False):
                tex = self._text_texture(text, size_px, color, astro)
                if tex is not None:
                    Rectangle(texture=tex,
                              pos=(x - tex.width / 2, y - tex.height / 2),
                              size=(tex.width, tex.height))

            for s in lay["signs"]:
                blit(s["glyph"] if astro_font else s["abbr"],
                     s["x"], s["y"], 14, (0.88, 0.89, 0.94, 1), astro=True)
            for h in lay["houses"]:
                blit(str(h["number"]), h["x"], h["y"], 10,
                     (0.62, 0.64, 0.72, 1))
            for ang in lay["angles"]:
                blit(ang["name"][:3].upper(),
                     (ang["x1"] + ang["x2"]) / 2, (ang["y1"] + ang["y2"]) / 2,
                     10, (0.90, 0.91, 0.96, 1))
            for p in lay["planets"]:
                blit(p["glyph"] if astro_font else p["abbr"],
                     p["x"], p["y"], 14, (1, 1, 1, 1), astro=True)
                if p["retro"]:
                    blit("R", p["x"], p["y"] - 16, 8, (1, 0.55, 0.4, 1))

            PopMatrix()

    # -- glyph textures -------------------------------------------------------
    def _text_texture(self, text, size_px, color, astro=False):
        """Rasterise ``text`` once into a cached GL texture.

        Text is drawn as textured rectangles on the art canvas instead of
        child ``Label`` widgets so it renders exactly where the wheel art
        renders, in every context (onscreen, export, projector).
        """
        key = (text, size_px, color, astro)
        tex = self._text_tex_cache.get(key)
        if tex is None:
            kw = dict(text=text, font_size=size_px, color=color)
            if astro:
                font = glyph_font_path()
                if font is not None:
                    kw["font_name"] = font
            lbl = CoreLabel(**kw)
            lbl.refresh()
            tex = lbl.texture
            self._text_tex_cache[key] = tex
        return tex

    # -- interaction ---------------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self._layout is None:
            return False
        return self._handle_tap(touch.x - self.x, touch.y - self.y)

    def _handle_tap(self, px: float, py: float) -> bool:
        """Hit-test a tap; select planet / sign / aspect, dispatch, redraw."""
        lay = self._layout
        # 1) planet glyphs (16 px around each centre)
        for p in lay["planets"]:
            if math.hypot(px - p["x"], py - p["y"]) <= 16:
                self._sel_planet = p["name"]
                self._sel_sign = None
                self._sel_aspect = None
                self._redraw()
                self.dispatch("on_planet_selected", p["name"])
                return True
        # 2) aspect lines (7 px from the segment)
        for i, a in enumerate(lay["aspects"]):
            if seg_distance(px, py, a["x1"], a["y1"], a["x2"], a["y2"]) <= 7:
                self._sel_aspect = i
                self._sel_planet = None
                self._sel_sign = None
                self._redraw()
                self.dispatch("on_aspect_selected", a["aspect"])
                return True
        # 3) zodiac band (between the inner ring and the rim) -> sign wedge.
        #    Screen angle is radians(180 + lon), so invert: lon = deg - 180.
        r = math.hypot(px - lay["cx"], py - lay["cy"])
        if lay["r_in"] < r <= lay["R"]:
            ang = math.degrees(math.atan2(py - lay["cy"], px - lay["cx"]))
            lon = (ang - 180.0) % 360.0
            sign = lay["signs"][int(lon // 30.0) % 12]
            self._sel_sign = sign["name"]
            self._sel_planet = None
            self._sel_aspect = None
            self._redraw()
            self.dispatch("on_sign_selected", sign["name"])
            return True
        # 4) empty space -> clear selection
        if (self._sel_planet is not None or self._sel_aspect is not None
                or self._sel_sign is not None):
            self.clear_selection()
        return False