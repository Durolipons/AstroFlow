"""Vedic astrology chart screen for AstroFlow.

Displays a Vedic chart with nakshatras, dasha information, and
Vedic-specific interpretations alongside the standard Western chart.
"""

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core.chart_store import save_chart
from core.models import BirthData
from core.vedic import calculate_vedic_chart
from core.vedic_interpretation import vedic_chart_report, nakshatra_detail
from ui.widgets import SquareWheelHost
from ui.widgets.chart_wheel import ChartWheel
from ui.widgets.astro_clock import _copy_to_clipboard


class VedicChartScreen(Screen):
    """Vedic astrology chart display screen."""

    chart_output = ObjectProperty(None)
    chart_host = ObjectProperty(None)
    wheel = ObjectProperty(None)
    chart_status = ObjectProperty(None)
    south_indian_chart = ObjectProperty(None)
    view_toggle = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._birth_data: BirthData = None
        self._vedic_chart = None
        self._font_size: float = 12.0
        self._show_south_indian = True  # Default to South Indian view

    def on_kv_post(self, base_widget):
        """Bind wheel selection events once the KV ids are wired."""
        if self.wheel is not None:
            self.wheel.bind(on_planet_selected=self._on_planet_picked)
            self.wheel.bind(on_sign_selected=self._on_sign_picked)
        if self.chart_host is not None and self.wheel is not None:
            self.chart_host.wheel = self.wheel
            self.chart_host._sync_wheel()

    def toggle_view(self):
        """Toggle between South Indian and Western wheel views."""
        self._show_south_indian = not self._show_south_indian
        if self.view_toggle is not None:
            self.view_toggle.text = "Western" if self._show_south_indian else "South Indian"
        self._update_chart_visibility()

    def _update_chart_visibility(self):
        """Show/hide chart widgets based on current view."""
        if self.south_indian_chart is not None:
            self.south_indian_chart.opacity = 1 if self._show_south_indian else 0
            self.south_indian_chart.disabled = not self._show_south_indian
        if self.chart_host is not None:
            self.chart_host.opacity = 0 if self._show_south_indian else 1
            self.chart_host.disabled = self._show_south_indian

    def set_birth_data(self, bd: BirthData) -> None:
        self._birth_data = bd

    def calculate_and_show(self):
        """Calculate the Vedic chart and display it."""
        if self._birth_data is None:
            return
        self._vedic_chart = calculate_vedic_chart(self._birth_data)
        if self.wheel is not None:
            # Create a Chart-like object for the wheel
            from core.models import Chart
            chart = Chart(
                chart_type="Vedic",
                birth_data=self._birth_data,
                target_title="Vedic Chart",
                positions=self._vedic_chart.positions,
                houses=self._vedic_chart.houses,
                angles=self._vedic_chart.angles,
                aspects=[],
                sidereal=True,
                ayanamsa=self._vedic_chart.ayanamsa,
            )
            self.wheel.set_chart(chart)
        if self.south_indian_chart is not None:
            self.south_indian_chart.chart_data = self._vedic_chart
        self._update_chart_visibility()
        self._render()

    def _on_planet_picked(self, _wheel, planet_name: str):
        if self._vedic_chart and self.chart_output is not None:
            self.chart_output.text = nakshatra_detail(self._vedic_chart, planet_name)

    def _on_sign_picked(self, _wheel, sign_name: str):
        if self._vedic_chart and self.chart_output is not None:
            from core.interpretation import sign_detail_text
            # Create a Chart-like object for sign detail
            from core.models import Chart
            chart = Chart(
                chart_type="Vedic",
                birth_data=self._birth_data,
                target_title="Vedic Chart",
                positions=self._vedic_chart.positions,
                houses=self._vedic_chart.houses,
                angles=self._vedic_chart.angles,
                aspects=[],
                sidereal=True,
                ayanamsa=self._vedic_chart.ayanamsa,
            )
            self.chart_output.text = sign_detail_text(chart, sign_name)

    def copy_output(self, *_args):
        if self.chart_output is None:
            return False
        return _copy_to_clipboard(self.chart_output.text)

    def go_home(self):
        self.manager.current = "home"

    def go_to_chart(self):
        """Switch to Western chart view."""
        chart_screen = self.manager.get_screen("chart")
        chart_screen.set_birth_data(self._birth_data)
        from core.chart import calculate_birth_chart
        chart = calculate_birth_chart(self._birth_data)
        chart_screen.set_natal_chart(chart)
        self.manager.current = "chart"

    def go_to_chinese(self):
        """Switch to Chinese chart view."""
        chinese_screen = self.manager.get_screen("chinese")
        chinese_screen.set_birth_data(self._birth_data)
        self.manager.current = "chinese"

    def go_to_interpretations(self):
        self.manager.current = "interpretations"

    def scale_font(self, delta: float):
        self._font_size = min(32.0, max(8.0, self._font_size + delta))
        if self.chart_output is not None:
            self.chart_output.font_size = f"{self._font_size}sp"

    def show_full_report(self):
        self._render()

    def _render(self):
        if self.chart_output is None or self._vedic_chart is None:
            return
        self.chart_output.text = vedic_chart_report(self._vedic_chart)
