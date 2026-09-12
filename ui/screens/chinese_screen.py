"""Chinese astrology chart screen for AstroFlow.

Displays a Chinese zodiac chart with BaZi (Four Pillars), element balance,
and Chinese astrology interpretations.
"""

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core.chinese import calculate_chinese_chart
from core.chinese_interpretation import chinese_chart_report, chinese_zodiac_detail
from core.models import BirthData
from ui.widgets.astro_clock import _copy_to_clipboard


class ChineseChartScreen(Screen):
    """Chinese astrology chart display screen."""

    chart_output = ObjectProperty(None)
    chart_status = ObjectProperty(None)
    bazi_chart = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._birth_data: BirthData = None
        self._chinese_chart = None
        self._font_size: float = 12.0

    def set_birth_data(self, bd: BirthData) -> None:
        self._birth_data = bd

    def on_enter(self, *args):
        """Called when the screen becomes visible. Calculate and display the chart."""
        if self._birth_data is not None:
            self.calculate_and_show()

    def calculate_and_show(self):
        """Calculate the Chinese chart and display it."""
        if self._birth_data is None:
            return
        self._chinese_chart = calculate_chinese_chart(self._birth_data)
        if self.bazi_chart is not None:
            self.bazi_chart.chart_data = self._chinese_chart
        self._render()

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

    def go_to_vedic(self):
        """Switch to Vedic chart view."""
        vedic_screen = self.manager.get_screen("vedic")
        vedic_screen.set_birth_data(self._birth_data)
        vedic_screen.calculate_and_show()
        self.manager.current = "vedic"

    def go_to_interpretations(self):
        self.manager.current = "interpretations"

    def scale_font(self, delta: float):
        self._font_size = min(32.0, max(8.0, self._font_size + delta))
        if self.chart_output is not None:
            self.chart_output.font_size = f"{self._font_size}sp"

    def show_full_report(self):
        self._render()

    def _render(self):
        if self.chart_output is None or self._chinese_chart is None:
            return
        self.chart_output.text = chinese_chart_report(self._chinese_chart)
