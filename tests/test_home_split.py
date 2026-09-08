"""Home screen chart-data / Astro-Clock split divider tests."""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _build_app():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    # Several ticks: the SDL resize lands asynchronously and each layout
    # trigger fires on the frame after the geometry it reacts to.
    for _ in range(5):
        Clock.tick()
    return sm, sm.get_screen("home")


class FakeTouch:
    """Minimal duck-typed touch for driving widget handlers directly."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.grab_current = None

    def grab(self, widget):
        self.grab_current = widget

    def ungrab(self, widget):
        self.grab_current = None


def test_home_split_divider_present_and_wired():
    _sm, home = _build_app()
    assert home.chart_split == 0.56
    divider = home.chart_divider
    assert divider is not None
    assert divider.orientation == "vertical"
    assert home.split_row is not None
    assert home.form_scroll is not None

    # The divider is wired to THIS screen's split. Behavioural check: Kivy's
    # WeakProxy wrappers make `owner is home` identity unreliable.
    start = home.chart_split
    divider.owner.adjust_split(30)
    assert home.chart_split > start


def test_home_split_drag_moves_columns():
    _sm, home = _build_app()
    divider = home.chart_divider
    start = home.chart_split
    astro_start = home.astro_clock.parent.width

    # Drag right: the chart-data column grows, the Astro-Clock gives up room.
    touch = FakeTouch(divider.center_x, divider.center_y)
    assert divider.on_touch_down(touch) is True
    touch.x = divider.center_x + 60
    touch.pos = (touch.x, touch.y)
    assert divider.on_touch_move(touch) is True
    divider.on_touch_up(touch)
    for _ in range(3):
        Clock.tick()

    assert home.chart_split > start
    assert home.astro_clock.parent.width < astro_start

    # Drag back left well past the origin: the column shrinks again.
    grown = home.chart_split
    touch2 = FakeTouch(divider.center_x, divider.center_y)
    divider.on_touch_down(touch2)
    touch2.x = divider.center_x - 200
    touch2.pos = (touch2.x, touch2.y)
    divider.on_touch_move(touch2)
    divider.on_touch_up(touch2)
    for _ in range(3):
        Clock.tick()
    assert home.chart_split < grown


def test_home_split_clamps():
    _sm, home = _build_app()
    divider = home.chart_divider

    touch = FakeTouch(divider.center_x, divider.center_y)
    divider.on_touch_down(touch)
    touch.x = divider.center_x + 100000.0
    touch.pos = (touch.x, touch.y)
    divider.on_touch_move(touch)
    divider.on_touch_up(touch)
    assert home.chart_split == 0.75

    touch2 = FakeTouch(divider.center_x, divider.center_y)
    divider.on_touch_down(touch2)
    touch2.x = divider.center_x - 100000.0
    touch2.pos = (touch2.x, touch2.y)
    divider.on_touch_move(touch2)
    divider.on_touch_up(touch2)
    assert home.chart_split == 0.25


def test_home_split_updates_column_widths():
    _sm, home = _build_app()
    home.set_chart_split(0.7)
    for _ in range(3):
        Clock.tick()

    row = home.split_row
    flexible = row.width - home.chart_divider.width - row.spacing * 2
    assert abs(home.form_scroll.width - 0.7 * flexible) < 1.5
    assert abs(home.astro_clock.parent.width - 0.3 * flexible) < 1.5


def test_panel_divider_cursors_match_orientation():
    from ui.widgets.astro_clock import PanelDivider

    assert PanelDivider.CURSORS["horizontal"] == "size_ns"
    assert PanelDivider.CURSORS["vertical"] == "size_we"
