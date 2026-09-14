"""Synastry panel: two birth-chart wheels with a center compatibility report.

Person A's wheel on the left, Person B's wheel on the right, and the
cross-chart interpretation report in the scrollable center panel. Both wheels
are live -- tapping a planet or aspect line surfaces its relationship-specific
interpretation from the editable synastry library.

HOOK: replace the side-by-side wheels with a bi-wheel overlay on small screens.
"""

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core import interpretation as interp
from core.chart_store import load_saved_charts
from core.interpretation import full_synastry_report
from core.models import BirthData, Chart
from ui.widgets.astro_clock import _copy_to_clipboard
from ui.widgets import SquareWheelHost  # noqa: F401 (KV factory)
from ui.widgets.chart_wheel import ChartWheel  # noqa: F401 (KV factory)


class SynastryScreen(Screen):
    """Two-wheel synastry panel with center compatibility report."""

    wheel_a = ObjectProperty(None)
    chart_host_a = ObjectProperty(None)
    wheel_b = ObjectProperty(None)
    chart_host_b = ObjectProperty(None)
    synastry_output = ObjectProperty(None)
    picker_a = ObjectProperty(None)
    picker_b = ObjectProperty(None)
    synastry_status = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._birth_a: BirthData = None
        self._birth_b: BirthData = None
        self._chart_a: Chart = None
        self._chart_b: Chart = None
        self._result = None
        self._font_size: float = 12.0

    def on_kv_post(self, base_widget):
        """Bind wheel selection events once the KV ids are wired."""
        if self.wheel_a is not None:
            self.wheel_a.bind(on_planet_selected=self._on_planet_a_picked)
            self.wheel_a.bind(on_aspect_selected=self._on_aspect_a_picked)
        if self.wheel_b is not None:
            self.wheel_b.bind(on_planet_selected=self._on_planet_b_picked)
            self.wheel_b.bind(on_aspect_selected=self._on_aspect_b_picked)
        if self.chart_host_a is not None and self.wheel_a is not None:
            self.chart_host_a.wheel = self.wheel_a
            self.chart_host_a._sync_wheel()
        if self.chart_host_b is not None and self.wheel_b is not None:
            self.chart_host_b.wheel = self.wheel_b
            self.chart_host_b._sync_wheel()
        self._refresh_pickers()

    def _refresh_pickers(self):
        """Populate both spinners from the saved-charts store."""
        charts = load_saved_charts()
        names = [c.name for c in charts]
        if self.picker_a is not None:
            self.picker_a.values = names
            if names:
                self.picker_a.text = names[0]
        if self.picker_b is not None:
            self.picker_b.values = names
            if names:
                self.picker_b.text = names[min(1, len(names) - 1)]

    def pick_chart_a(self, name: str):
        """Load Person A from the saved-charts store by display name."""
        for c in load_saved_charts():
            if c.name == name:
                self.set_person_a(c.birth_data)
                break

    def pick_chart_b(self, name: str):
        """Load Person B from the saved-charts store by display name."""
        for c in load_saved_charts():
            if c.name == name:
                self.set_person_b(c.birth_data)
                break

    def set_person_a(self, bd: BirthData) -> None:
        self._birth_a = bd
        self._render_status()

    def set_person_b(self, bd: BirthData) -> None:
        self._birth_b = bd
        self._render_status()

    def set_pair(self, bd_a: BirthData, bd_b: BirthData) -> None:
        self._birth_a = bd_a
        self._birth_b = bd_b
        self._render_status()

    def _on_planet_a_picked(self, _wheel, planet_name: str):
        if self._chart_a is not None and self.synastry_output is not None:
            self.synastry_output.text = interp.planet_detail_text(
                self._chart_a, planet_name)

    def _on_planet_b_picked(self, _wheel, planet_name: str):
        if self._chart_b is not None and self.synastry_output is not None:
            self.synastry_output.text = interp.planet_detail_text(
                self._chart_b, planet_name)

    def _on_aspect_a_picked(self, _wheel, aspect):
        if self.synastry_output is not None:
            self.synastry_output.text = interp.aspect_detail_text(aspect)

    def _on_aspect_b_picked(self, _wheel, aspect):
        if self.synastry_output is not None:
            self.synastry_output.text = interp.aspect_detail_text(aspect)

    def generate(self):
        """Compute synastry and render the center report."""
        ba = getattr(self, '_birth_a', None)
        bb = getattr(self, '_birth_b', None)
        if ba is None or bb is None:
            if self.synastry_output is not None:
                self.synastry_output.text = (
                    "Pick two charts (or load examples) to generate "
                    "the synastry report.")
            return
        self._result = full_synastry_report(ba, bb)
        if self.synastry_output is not None:
            self.synastry_output.text = self._result
        from core.chart import calculate_birth_chart
        self._chart_a = calculate_birth_chart(ba)
        self._chart_b = calculate_birth_chart(bb)
        if self.wheel_a is not None:
            self.wheel_a.set_chart(self._chart_a)
        if self.wheel_b is not None:
            self.wheel_b.set_chart(self._chart_b)
        self._render_status()

    def swap_sides(self):
        """Swap Person A <-> Person B."""
        ba = getattr(self, '_birth_a', None)
        bb = getattr(self, '_birth_b', None)
        ca = getattr(self, '_chart_a', None)
        cb = getattr(self, '_chart_b', None)
        self._birth_a, self._birth_b = bb, ba
        self._chart_a, self._chart_b = cb, ca
        if self.wheel_a is not None and self._chart_a is not None:
            self.wheel_a.set_chart(self._chart_a)
        if self.wheel_b is not None and self._chart_b is not None:
            self.wheel_b.set_chart(self._chart_b)
        if self._result is not None:
            self.generate()
        self._render_status()

    def copy_output(self, *_args):
        """Copy the center report to the clipboard."""
        if self.synastry_output is None:
            return False
        return _copy_to_clipboard(self.synastry_output.text)

    def scale_font(self, direction: int):
        """Bump the center report font size up or down."""
        self._font_size = max(8.0, min(28.0, self._font_size + direction * 2.0))
        if self.synastry_output is not None:
            self.synastry_output.font_size = f"{self._font_size:.0f}sp"

    def _render_status(self):
        if self.synastry_status is None:
            return
        a = getattr(self, '_birth_a', None)
        b = getattr(self, '_birth_b', None)
        a_name = a.name if a else "-"
        b_name = b.name if b else "-"
        self.synastry_status.text = f"A: {a_name}   |   B: {b_name}"

    def go_home(self):
        self.manager.current = "home"

    def go_to_database(self):
        self.manager.current = "database"

    def go_to_interpretations(self):
        self.manager.current = "interpretations"

    def go_to_chart(self):
        self.manager.current = "chart"
