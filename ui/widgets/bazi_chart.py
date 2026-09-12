"""Chinese BaZi (Four Pillars) chart widget for AstroFlow.

Renders a traditional BaZi chart with four pillar columns (Year, Month, Day,
Hour). Each column shows:
* the pillar title at the top,
* the Heavenly Stem (with its element color tile),
* the zodiac animal emoji in the middle,
* the Earthly Branch (with its element color tile) at the bottom.

The layout scales with the widget size and, when they are available, a system
CJK font and an emoji font are registered so the Han characters and zodiac
animal glyphs render instead of Kivy's default tofu boxes (Roboto has no CJK
coverage).
"""
from __future__ import annotations

import os

from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.graphics import Color, Line, Rectangle
from kivy.properties import ObjectProperty
from kivy.uix.label import Label
from kivy.uix.widget import Widget

# Element colors (traditional Chinese five elements).
ELEMENT_COLORS = {
    "Wood": (0.2, 0.6, 0.3, 1),
    "Fire": (0.9, 0.2, 0.1, 1),
    "Earth": (0.7, 0.6, 0.3, 1),
    "Metal": (0.8, 0.8, 0.85, 1),
    "Water": (0.2, 0.3, 0.6, 1),
}

PILLAR_NAMES = ["Year", "Month", "Day", "Hour"]

STEM_CHAR = {
    "Jia": "\u7532", "Yi": "\u4E59", "Bing": "\u4E19", "Ding": "\u4E01",
    "Wu": "\u620A",   # Ganzhi coordinate note: 戊 not 戌 (the Xu branch).
    "Ji": "\u5DF1", "Geng": "\u5E9A", "Xin": "\u8F9B",
    "Ren": "\u58EC", "Gui": "\u7678",
}

BRANCH_CHAR = {
    "Zi": "\u5B50", "Chou": "\u4E11", "Yin": "\u5BC5", "Mao": "\u536F",
    "Chen": "\u8FB0", "Si": "\u5DF3", "Wu": "\u5348", "Wei": "\u672A",
    "Shen": "\u7533", "You": "\u9149", "Xu": "\u620C", "Hai": "\u4EA5",
}

ANIMAL_EMOJI = {
    "Rat": "\U0001F401", "Ox": "\U0001F402", "Tiger": "\U0001F405",
    "Rabbit": "\U0001F407", "Dragon": "\U0001F409", "Snake": "\U0001F40D",
    "Horse": "\U0001F40E", "Goat": "\U0001F410", "Monkey": "\U0001F412",
    "Rooster": "\U0001F413", "Dog": "\U0001F415", "Pig": "\U0001F416",
}

_CJK_FONT = None
_EMOJI_FONT = None


def _first_existing(paths):
    for path in paths:
        if path and os.path.isfile(path):
            return path
    return None


def _register(name, path):
    if not path:
        return None
    try:
        LabelBase.register(name=name, fn_regular=path)
        return name
    except Exception:  # pragma: no cover - defensive, Kivy font loading
        return None


def cjk_font_name() -> str:
    """Return the name of a registered CJK-capable font, or None."""
    global _CJK_FONT
    if _CJK_FONT is not None:
        return _CJK_FONT or None
    windir = os.environ.get("WINDIR", r"C:\Windows")
    path = _first_existing([
        os.path.join(windir, "Fonts", "msyh.ttc"),
        os.path.join(windir, "Fonts", "msyh.ttf"),
        os.path.join(windir, "Fonts", "simsun.ttc"),
        os.path.join(windir, "Fonts", "simhei.ttf"),
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ])
    _CJK_FONT = _register("AstroCJK", path) or False
    return _CJK_FONT or None


def emoji_font_name() -> str:
    """Return the name of a registered emoji-capable font, or None."""
    global _EMOJI_FONT
    if _EMOJI_FONT is not None:
        return _EMOJI_FONT or None
    windir = os.environ.get("WINDIR", r"C:\Windows")
    path = _first_existing([
        os.path.join(windir, "Fonts", "seguiemj.ttf"),
        os.path.join(windir, "Fonts", "segoeui.ttf"),
        "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    ])
    _EMOJI_FONT = _register("AstroEmoji", path) or False
    return _EMOJI_FONT or None
class BaZiChart(Widget):
    """Four-pillar Chinese BaZi chart."""

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
        # ``chart_data`` can be assigned from constructor kwargs, before Kivy
        # has created the canvas; defer in that case.
        if self.canvas is None:
            Clock.schedule_once(lambda *_: self._safe_draw(), 0)
            return
        self._draw()

    def _label(self, text, cx, cy, w, h, font_size, color, font=None):
        kw = dict(
            text=text, font_size=font_size, color=color,
            size=(w, h), pos=(cx - w / 2.0, cy - h / 2.0),
            halign="center", valign="middle", size_hint=(None, None),
        )
        if font:
            kw["font_name"] = font
        label = Label(**kw)
        label.bind(size=label.setter("text_size"))
        self.add_widget(label)
        return label

    def _draw(self):
        self.canvas.clear()
        w, h = self.size
        if not w or not h:
            return
        x, y = self.pos
        if not self.chart_data:
            return
        # Drop labels from any previous draw so repeated redraws (resize, data
        # refresh) never stack duplicate glyphs on top of each other.
        for child in list(self.children):
            self.remove_widget(child)

        with self.canvas:
            Color(0.98, 0.96, 0.92, 1)
            Rectangle(pos=(x, y), size=(w, h))

        pw = w / 4.0
        # Vertical bands (fractions of h): title / stem / animal / branch.
        title_cy = y + h * 0.90
        stem_cy = y + h * 0.71
        animal_cy = y + h * 0.44
        branch_cy = y + h * 0.17

        cjk = cjk_font_name()
        emoji = emoji_font_name()

        for i, pillar_key in enumerate(["year", "month", "day", "hour"]):
            pillar = self.chart_data.bazi.get(pillar_key)
            if not pillar:
                continue
            stem = pillar.get("stem", "")
            branch = pillar.get("branch", "")
            animal = pillar.get("branch_animal", "")
            stem_elem = pillar.get("stem_element", "Earth")
            branch_elem = pillar.get("branch_element", "Earth")
            stem_color = ELEMENT_COLORS.get(stem_elem, (0.5, 0.5, 0.5, 1))
            branch_color = ELEMENT_COLORS.get(branch_elem, (0.5, 0.5, 0.5, 1))
            px = x + i * pw + pw / 2.0

            with self.canvas:
                Color(*stem_color[:3], 0.12)
                Rectangle(pos=(px - pw / 2.0 + 8, y + h * 0.55),
                          size=(pw - 16, h * 0.32))
                Color(*branch_color[:3], 0.12)
                Rectangle(pos=(px - pw / 2.0 + 8, y + h * 0.02),
                          size=(pw - 16, h * 0.32))
                Color(0.3, 0.2, 0.1, 1)
                Line(points=[px - pw / 2.0 + 8, y + h * 0.55,
                             px + pw / 2.0 - 8, y + h * 0.55], width=1)

            big_font = max(13.0, min(pw * 0.19, h * 0.22))
            title_font = max(9.0, pw * 0.08)
            animal_font = max(14.0, h * 0.26)

            self._label(
                STEM_CHAR.get(stem, stem), px, stem_cy,
                pw * 0.8, big_font * 1.25, big_font,
                (0.15, 0.1, 0.05, 1), font=cjk)
            self._label(
                BRANCH_CHAR.get(branch, branch), px, branch_cy,
                pw * 0.8, big_font * 1.25, big_font,
                (0.15, 0.1, 0.05, 1), font=cjk)
            if animal and animal in ANIMAL_EMOJI:
                self._label(
                    ANIMAL_EMOJI[animal], px, animal_cy,
                    animal_font * 1.3, animal_font * 1.1, animal_font,
                    (0.2, 0.15, 0.1, 1), font=emoji)
            self._label(
                PILLAR_NAMES[i], px, title_cy,
                pw * 0.6, title_font * 1.5, title_font,
                (0.3, 0.25, 0.2, 1))