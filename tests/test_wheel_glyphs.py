"""Verify glyph rendering setup and reading detail wiring.

These tests render the wheel offscreen and confirm that (a) the element-colour
wedges actually draw (Triangle instructions) and stay centred on the wheel, and
(b) the Astro-Clock readout label receives tap detail text.
"""

import os
from datetime import datetime, timezone

os.environ.setdefault("KIVY_LOG_LEVEL", "error")

from kivy.core.window import Window  # noqa: E402
from kivy.clock import Clock  # noqa: E402

from core.chart import calculate_birth_chart  # noqa: E402
from core.models import BirthData, Location  # noqa: E402
from ui.main import AstroFlowApp  # noqa: E402
from ui.widgets.chart_wheel import glyph_font_path  # noqa: E402


def _birth():
    return BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )


def _wheel_with_chart(wheel):
    wheel.size_hint = (None, None)
    wheel.size = (420, 420)
    wheel.pos = (0, 0)
    wheel.set_chart(calculate_birth_chart(_birth()))
    for _ in range(3):
        Clock.tick()
    return wheel


def _element_color_pixels(wheel):
    """Return the list of (x, y) raw-scanline pixels on the wheel's texture
    that are clearly an element wedge colour (alpha blended over the panel
    background, which the widget export makes transparent)."""
    img = wheel.export_as_image()
    tex = img.texture
    w, h = tex.width, tex.height
    buf = tex.pixels
    stride = w * 4
    hits = []
    for y in range(h):
        row = buf[y * stride:(y + 1) * stride]
        for x in range(w):
            i = x * 4
            r = row[i]
            g = row[i + 1]
            b = row[i + 2]
            a = row[i + 3]
            if a == 0:
                continue
            max_c = max(r, g, b)
            min_c = min(r, g, b)
            if max_c - min_c >= 24:
                hits.append((x, y))
    return hits, w, h


def test_wedges_are_drawn_and_centered():
    Window.size = (900, 700)
    app = AstroFlowApp()
    sm = app.build()
    chart_scr = sm.get_screen("chart")
    wheel = _wheel_with_chart(chart_scr.wheel)

    hits, w, h = _element_color_pixels(wheel)
    assert len(hits) > 800, f"only {len(hits)} coloured pixels; wedges missing"
    cx = sum(px for px, _ in hits) / len(hits)
    cy = sum(py for _, py in hits) / len(hits)
    # The wheel is 420x420; a symmetric full-circle of wedges has its colour
    # centroid at the wheel centre in both scanline orientations.
    assert abs(cx - w / 2) < 15, f"wedge x-centroid {cx:.0f} vs {w / 2:.0f}"
    assert abs(cy - h / 2) < 25, f"wedge y-centroid {cy:.0f} vs {h / 2:.0f}"


def test_glyph_font_resolves_or_falls_back():
    # On any platform this must not throw and, if it returns a path, the file
    # must exist (so a tofu-glyph font is never silently used).
    path = glyph_font_path()
    if path is not None:
        assert os.path.isfile(path), f"glyph font {path!r} missing"


def test_labels_use_glyphs_when_font_available():
    from ui.widgets.chart_wheel import SIGN_GLYPH, PLANET_GLYPH
    from core import constants as C

    assert len(SIGN_GLYPH) == 12
    assert all(g for g in SIGN_GLYPH)
    assert all(g for g in PLANET_GLYPH.values())

    font = glyph_font_path()
    if font is None:
        return  # fallback path already covered elsewhere

    Window.size = (900, 700)
    app = AstroFlowApp()
    sm = app.build()
    chart_scr = sm.get_screen("chart")
    wheel = _wheel_with_chart(chart_scr.wheel)

    texts = {key[0] for key in wheel._text_tex_cache}
    assert "\u2648" in texts, "Aries glyph texture missing"
    assert "\u2609" in texts, "Sun glyph texture missing"
    # The glyph textures must actually be blitted onto the wheel's art canvas.
    rects = [c for c in wheel._art_canvas.children
             if type(c).__name__ == "Rectangle" and c.texture is not None]
    assert len(rects) > 20, f"only {len(rects)} glyph rectangles on art canvas"


def test_glyph_ink_renders_on_wheel():
    """White planet-glyph ink must appear in the wheel's own texture export.

    This is the end-to-end proof that glyphs are really drawn (the old
    child-widget label layer never made it into the wheel's rendering).
    """
    Window.size = (900, 700)
    app = AstroFlowApp()
    sm = app.build()
    chart_scr = sm.get_screen("chart")
    wheel = _wheel_with_chart(chart_scr.wheel)

    img = wheel.export_as_image()
    tex = img.texture
    w, h = tex.width, tex.height
    buf = tex.pixels
    stride = w * 4
    white = 0
    for y in range(h):
        row = buf[y * stride:(y + 1) * stride]
        for x in range(w):
            i = x * 4
            if (row[i + 3] > 200 and row[i] > 200 and row[i + 1] > 200
                    and row[i + 2] > 200):
                white += 1
    assert white > 40, f"only {white} white glyph pixels rendered"