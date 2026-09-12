"""Regression tests for the Vedic and BaZi chart widgets + screens.

The charts were previously mis-rendered: the South-Indian sign grid used grid
coordinates 0..11 with a 4-column cell width (labels spilled far outside the
widget), the BaZi animal emoji was drawn below the widget, the BaZi redraw
stacked duplicate labels, and building any widget with ``chart_data=`` as a
constructor kwarg crashed on a missing canvas. All of those are covered here.
"""

import os
from datetime import datetime, timezone

os.environ.setdefault("KIVY_LOG_LEVEL", "error")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402

from core import constants as C  # noqa: E402
from core.chinese import calculate_chinese_chart  # noqa: E402
from core.models import BirthData, Location  # noqa: E402
from core.vedic import calculate_vedic_chart  # noqa: E402
from core.vedic_interpretation import vedic_chart_report  # noqa: E402
from ui.main import AstroFlowApp  # noqa: E402
from ui.widgets.bazi_chart import (  # noqa: E402
    ANIMAL_EMOJI,
    BRANCH_CHAR,
    STEM_CHAR,
    BaZiChart,
)
from ui.widgets.vedic_chart import (  # noqa: E402
    NorthIndianChart,
    SouthIndianChart,
)


def _birth():
    return BirthData(
        name="Test",
        birth_datetime=datetime(1990, 5, 15, 10, 30, tzinfo=timezone.utc),
        location=Location(latitude=51.5074, longitude=-0.1278, name="London"),
        timezone=timezone.utc,
    )


def _tick(n=4):
    for _ in range(n):
        Clock.tick()


def _assert_labels_inside(widget, tolerance=1.5):
    """Every drawn label must sit inside the widget borders."""
    wx0, wy0 = widget.pos
    wx1 = wx0 + widget.width
    wy1 = wy0 + widget.height
    assert len(widget.children) > 0, "chart drew no labels"
    for child in widget.children:
        x0, y0 = child.pos
        x1, y1 = x0 + child.width, y0 + child.height
        assert x0 >= wx0 - tolerance, (child.text, x0, wx0)
        assert y0 >= wy0 - tolerance, (child.text, y0, wy0)
        assert x1 <= wx1 + tolerance, (child.text, x1, wx1)
        assert y1 <= wy1 + tolerance, (child.text, y1, wy1)


def test_vedic_widgets_construct_with_inline_chart_data():
    """Constructor kwarg data used to crash on a missing canvas."""
    vc = calculate_vedic_chart(_birth())
    south = SouthIndianChart(chart_data=vc, size=(1168, 193))
    north = NorthIndianChart(chart_data=vc, size=(1168, 300))
    _tick()
    assert len(south.children) >= 24  # 12 signs + 12 house numbers
    assert len(north.children) >= 24


def test_south_indian_labels_all_inside_widget_bounds():
    vc = calculate_vedic_chart(_birth())
    chart = SouthIndianChart()
    chart.size = (1168, 193)
    chart.pos = (0, 0)
    chart.chart_data = vc
    _tick()
    texts = {child.text for child in chart.children}
    assert {"AR", "TA", "CP", "PI"} <= texts  # fixed signs present
    assert {"1", "12"} <= texts               # rotating house numbers present
    _assert_labels_inside(chart)


def test_bazi_labels_inside_bounds_and_redraw_is_idempotent():
    cc = calculate_chinese_chart(_birth())
    chart = BaZiChart()
    chart.size = (1168, 181)
    chart.pos = (16, 480)
    chart.chart_data = cc
    _tick()
    assert len(chart.children) == 16          # 4 pillars x 4 labels
    # Wu is the 戊 stem (U+620A), never the 戌 Xu branch (U+620C).
    assert STEM_CHAR["Wu"] == "\u620a"
    assert STEM_CHAR["Wu"] != BRANCH_CHAR["Xu"]
    assert ANIMAL_EMOJI  # animal glyph map is populated
    # Re-drawing (e.g. on a resize) must replace, not stack, the labels.
    chart.size = (1168, 300)
    _tick()
    assert len(chart.children) == 16
    _assert_labels_inside(chart)


def test_vedic_screen_renders_chart_and_toggles_western_view():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    sm.transition.duration = 0
    _tick()

    vedic = sm.get_screen("vedic")
    vedic.set_birth_data(_birth())
    vedic.calculate_and_show()
    sm.current = "vedic"
    _tick(8)

    sic = vedic.south_indian_chart
    assert sic is not None
    assert sic.width > 800                # full-width, not squeezed beside wheel
    assert sic.chart_data is not None
    _assert_labels_inside(sic)

    # South-Indian view is the default; Western wheel overlay is hidden.
    assert abs(sic.opacity - 1.0) < 1e-6
    assert abs(vedic.chart_host.opacity) < 1e-6

    vedic.toggle_view()
    _tick(2)
    assert abs(vedic.chart_host.opacity - 1.0) < 1e-6
    assert vedic.wheel.chart is not None  # wheel got the Vedic chart

    vedic.toggle_view()
    _tick(2)
    assert abs(sic.opacity - 1.0) < 1e-6


def test_chinese_screen_renders_bazi_chart_in_app():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    sm.transition.duration = 0
    _tick()

    chinese = sm.get_screen("chinese")
    chinese.set_birth_data(_birth())
    sm.current = "chinese"
    _tick(8)

    bc = chinese.bazi_chart
    assert bc is not None
    assert bc.height > 150               # tall enough for emoji + 2 glyph rows
    assert len(bc.children) == 16
    _assert_labels_inside(bc)


def test_vedic_report_explains_terms_for_english_readers():
    """The Vedic report glosses its Sanskrit/Ayurvedic words inline."""
    from core.vedic_interpretation import vedic_chart_report

    report = vedic_chart_report(calculate_vedic_chart(_birth()))
    assert "A note for English readers" in report
    assert "lunar mansions" in report          # nakshatra gloss
    assert "120-year" in report                # Vimshottari gloss
    assert "GLOSSARY - VEDIC WORDS IN PLAIN ENGLISH" in report
    assert "Pitta" in report and "Vata" in report   # dosha lines + glossary
    assert "Kapha" in report


def test_vedic_report_explains_planet_house_references():
    report = vedic_chart_report(calculate_vedic_chart(_birth()))

    assert "house " in report
    assert any(
        f"house {house:>2} ({meaning})" in report
        for house, meaning in C.VEDIC_HOUSE_SIGNIFICATIONS.items()
    )
