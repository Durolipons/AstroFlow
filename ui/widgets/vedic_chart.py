"""Vedic chart widgets for AstroFlow.

Renders the two traditional Indian chart styles:
* ``SouthIndianChart`` -- the fixed 4x4 grid where the zodiac signs never
  move and the houses rotate.
* ``NorthIndianChart`` -- the diamond layout with the Ascendant house always
  centered in the inner diamond.

Both widgets adapt to whatever size they are given (font sizes and label
positions scale with the widget), so they render correctly inside the screen
layout instead of assuming a large fixed canvas.
"""
from __future__ import annotations

import math

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import ObjectProperty
from kivy.uix.label import Label
from kivy.uix.widget import Widget

# Sign abbreviations, indexed like ``constants.SIGNS`` (Aries -> Pisces).
SIGN_ABBR = {
    0: "AR", 1: "TA", 2: "GE", 3: "CA", 4: "LE", 5: "VI",
    6: "LI", 7: "SC", 8: "SG", 9: "CP", 10: "AQ", 11: "PI",
}

# Common Vedic planet abbreviations.
PLANET_ABBR = {
    "Sun": "Su", "Moon": "Mo", "Mercury": "Me", "Venus": "Ve",
    "Mars": "Ma", "Jupiter": "Ju", "Saturn": "Sa",
    "Rahu": "Ra", "Ketu": "Ke",
}


class _VedicChartBase(Widget):
    """Shared behaviour for the Vedic chart widgets.

    The ``chart_data`` ObjectProperty may be assigned via constructor kwargs
    (e.g. ``SouthIndianChart(chart_data=chart)``); Kivy dispatches the
    ``on_chart_data`` callback at that moment, before the widget's canvas has
    been created. The first draw is deferred to the event loop in that case so
    constructing a widget with data can never crash.
    """

    chart_data = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._init_draw, 0)

    def _init_draw(self, *_args):
        self._safe_draw()
        self.bind(pos=self._on_change, size=self._on_change)

    def _on_change(self, *_args):
        self._safe_draw()

    def on_chart_data(self, *_args):
        self._safe_draw()

    def _safe_draw(self):
        if self.canvas is None:
            Clock.schedule_once(lambda *_: self._safe_draw(), 0)
            return
        self._draw()

    def _draw(self):  # pragma: no cover - abstract
        raise NotImplementedError

    def _label(self, text, cx, cy, w, h, font_size, color):
        """Add a centered label positioned relative to the widget."""
        label = Label(
            text=text, font_size=font_size, color=color,
            size=(w, h), pos=(cx - w / 2.0, cy - h / 2.0),
            halign="center", valign="middle", size_hint=(None, None),
        )
        label.bind(size=label.setter("text_size"))
        self.add_widget(label)
        return label


# South-Indian (rasi) chart: sign-cell positions on the fixed 4x4 grid,
# indexed by sign (0 = Aries at the top-left). Signs never move in a South
# Indian chart -- only the house numbers rotate with the Ascendant.
# Column 0..3 runs left to right, row 0..3 runs bottom to top:
#   Aries Taurus Gemini Cancer  <- top row
#   Pisces                Leo
#   Aquarius              Virgo
#   Capricorn Sagi Scorpio Libra
_SIGN_CELLS = {
    0: (0, 3),   1: (1, 3),   2: (2, 3),   3: (3, 3),
    4: (3, 2),   5: (3, 1),   6: (3, 0),   7: (2, 0),
    8: (1, 0),   9: (0, 0),  10: (0, 1),  11: (0, 2),
}


def _sign_index(longitude) -> int:
    """0-based zodiac sign index for an ecliptic longitude."""
    try:
        return int(float(longitude) % 360.0 / 30.0) % 12
    except (TypeError, ValueError):
        return 0


class SouthIndianChart(_VedicChartBase):
    """South-Indian (4x4 grid) Vedic chart."""

    def _draw(self):
        self.canvas.clear()
        w, h = self.size
        if not w or not h:
            return
        x, y = self.pos
        with self.canvas:
            Color(0.97, 0.94, 0.87, 1)
            Rectangle(pos=(x, y), size=(w, h))
        cw, ch = w / 4.0, h / 4.0
        with self.canvas:
            Color(0.3, 0.2, 0.1, 1)
            for i in range(1, 4):
                Line(points=[x + i * cw, y, x + i * cw, y + h], width=1.5)
                Line(points=[x, y + i * ch, x + w, y + i * ch], width=1.5)
            Color(0.2, 0.15, 0.1, 1)
            Line(points=[x, y, x + w, y, x + w, y + h, x, y + h, x, y],
                 width=2.5)
        for child in list(self.children):
            self.remove_widget(child)

        # House 1 is the Ascendant's sign; the other houses follow the signs.
        angles = getattr(self.chart_data, "angles", {}) or {}
        asc_sign = _sign_index(angles.get("Ascendant", 0))

        cell = min(cw, ch)
        sign_font = max(10.0, cell * 0.34)
        num_font = max(8.0, cell * 0.24)
        planet_font = max(9.0, cell * 0.26)

        def cell_center(sign_idx):
            col, row = _SIGN_CELLS[sign_idx % 12]
            return (x + col * cw + cw / 2.0, y + row * ch + ch / 2.0)

        # Fixed sign abbreviations in the top third of every cell, with the
        # rotating house number just beneath them.
        for sign_idx in range(12):
            cx, cy = cell_center(sign_idx)
            self._label(
                SIGN_ABBR[sign_idx], cx, cy - ch * 0.30,
                cw * 0.52, ch * 0.34, sign_font, (0.15, 0.1, 0.05, 1))
            house_num = (sign_idx - asc_sign) % 12 + 1
            self._label(
                str(house_num), cx, cy - ch * 0.02,
                cw * 0.34, ch * 0.26, num_font, (0.4, 0.3, 0.2, 1))

        # Planets are listed by rasi (sign) in the lower half of their cell.
        planets_by_sign = {}
        for p in getattr(self.chart_data, "planets", []):
            if not (p and hasattr(p, "longitude")):
                continue
            sidx = _sign_index(p.longitude)
            planets_by_sign.setdefault(
                sidx, []).append(PLANET_ABBR.get(p.name, p.name[:2]))

        for sign_idx, symbols in planets_by_sign.items():
            cx, cy = cell_center(sign_idx)
            n = len(symbols)
            pitch = cw * 0.24
            start_x = cx - pitch * (n - 1) / 2.0
            for j, symbol in enumerate(symbols):
                self._label(
                    symbol, start_x + j * pitch, cy + ch * 0.28,
                    cw * 0.22, ch * 0.26, planet_font, (0.05, 0.05, 0.05, 1))


class NorthIndianChart(_VedicChartBase):
    """North-Indian (diamond) Vedic chart."""

    def _draw(self):
        self.canvas.clear()
        w, h = self.size
        if not w or not h:
            return
        x, y = self.pos
        cx, cy = x + w / 2.0, y + h / 2.0
        outer = min(w, h) / 2.0 - 8
        inner = outer * 0.5
        with self.canvas:
            Color(0.97, 0.94, 0.87, 1)
            Rectangle(pos=(x, y), size=(w, h))
            Color(0.25, 0.18, 0.1, 1)
            Line(points=[cx, cy - outer, cx + outer, cy,
                         cx, cy + outer, cx - outer, cy, cx, cy - outer],
                 width=2)
            Color(0.35, 0.28, 0.18, 1)
            Line(points=[cx, cy - inner, cx + inner, cy,
                         cx, cy + inner, cx - inner, cy, cx, cy - inner],
                 width=1.5)
        for child in list(self.children):
            self.remove_widget(child)

        size = min(w, h)
        sign_font = max(9.0, size * 0.045)
        num_font = max(8.0, size * 0.032)

        for i in range(12):
            angle = math.radians(90 - i * 30)
            mid_r = (outer + inner) / 2.0
            mx = cx + mid_r * math.cos(angle)
            my = cy + mid_r * math.sin(angle)
            self._label(
                SIGN_ABBR[i], mx, my - sign_font * 1.1,
                sign_font * 2.8, sign_font * 1.5,
                sign_font, (0.15, 0.1, 0.05, 1))
            inner_r = inner * 0.35
            ix = cx + inner_r * math.cos(angle)
            iy = cy + inner_r * math.sin(angle)
            self._label(
                str(i + 1), ix, iy,
                num_font * 2.0, num_font * 1.5,
                num_font, (0.4, 0.3, 0.2, 1))

        planets_by_house = {}
        for p in getattr(self.chart_data, "planets", []):
            if not hasattr(p, "house"):
                continue
            house = p.house % 12
            if house == 0:
                house = 12
            planets_by_house.setdefault(
                house, []).append(PLANET_ABBR.get(p.name, p.name[:2]))

        planet_font = max(9.0, size * 0.034)
        for house, symbols in planets_by_house.items():
            angle = math.radians(90 - (house - 1) * 30)
            base_r = inner + (outer - inner) * 0.26
            step_r = min((outer - inner) * 0.14, 16.0)
            n = len(symbols)
            start_r = base_r - step_r * (n - 1) / 2.0
            for j, symbol in enumerate(symbols):
                radius = start_r + j * step_r
                px = cx + radius * math.cos(angle)
                py = cy + radius * math.sin(angle)
                self._label(
                    symbol, px, py,
                    planet_font * 2.4, planet_font * 1.5,
                    planet_font, (0.05, 0.05, 0.05, 1))