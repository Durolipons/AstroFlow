"""Chart screen: interactive natal chart wheel + details panel.

The wheel (``ui/widgets/chart_wheel.py``) renders the natal chart as a
circular diagram; tapping a planet glyph or an aspect line shows its
interpretation in the details panel below. The full text report is one tap
away via the "Full report" button.

HOOK: replace the details panel with a side sheet on wide screens/tablets.
"""

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core.chart_store import save_chart
from core.interpretation import (
    aspect_detail_text,
    full_birth_report,
    planet_detail_text,
    sign_detail_text,
)
from core.models import BirthData, Chart
from ui.widgets.astro_clock import _copy_to_clipboard
from ui.widgets import SquareWheelHost  # noqa: F401 (KV factory)
from ui.widgets.chart_wheel import ChartWheel  # noqa: F401 (KV factory)


class ChartScreen(Screen):
    """Interactive natal chart: wheel + interpretation details."""

    chart_output = ObjectProperty(None)  # details text (wired by app.kv)
    chart_host = ObjectProperty(None)     # square host for the wheel
    wheel = ObjectProperty(None)         # ChartWheel (wired by app.kv)
    chart_status = ObjectProperty(None)   # save feedback label (wired by app.kv)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._birth_data: BirthData = None
        self._natal_chart: Chart = None
        self._font_size: float = 12.0

    def on_kv_post(self, base_widget):
        """Bind wheel selection events once the KV ids are wired."""
        if self.wheel is not None:
            self.wheel.bind(on_planet_selected=self._on_planet_picked)
            self.wheel.bind(on_sign_selected=self._on_sign_picked)
            self.wheel.bind(on_aspect_selected=self._on_aspect_picked)
        if self.chart_host is not None and self.wheel is not None:
            self.chart_host.wheel = self.wheel
            self.chart_host._sync_wheel()

    # -- called by HomeScreen ------------------------------------------------
    def set_birth_data(self, bd: BirthData) -> None:
        self._birth_data = bd

    def set_natal_chart(self, chart: Chart) -> None:
        self._natal_chart = chart
        if self.wheel is not None:
            self.wheel.set_chart(chart)
        self._render()

    # -- wheel callbacks -----------------------------------------------------
    def _on_planet_picked(self, _wheel, planet_name: str):
        if self._natal_chart and self.chart_output is not None:
            self.chart_output.text = planet_detail_text(self._natal_chart,
                                                        planet_name)

    def _on_aspect_picked(self, _wheel, aspect):
        if self.chart_output is not None:
            self.chart_output.text = aspect_detail_text(aspect)

    def _on_sign_picked(self, _wheel, sign_name: str):
        if self._natal_chart and self.chart_output is not None:
            self.chart_output.text = sign_detail_text(self._natal_chart,
                                                      sign_name)

    def copy_output(self, *_args):
        """Copy the interpretation text to the clipboard."""
        if self.chart_output is None:
            return False
        return _copy_to_clipboard(self.chart_output.text)

    # -- navigation ---------------------------------------------------------
    def go_to_forecast(self):
        forecast = self.manager.get_screen("forecast")
        forecast.set_birth_data(self._birth_data)
        forecast.generate_forecast()
        self.manager.current = "forecast"

    def go_to_vedic(self):
        """Switch to Vedic chart view."""
        vedic = self.manager.get_screen("vedic")
        vedic.set_birth_data(self._birth_data)
        vedic.calculate_and_show()
        self.manager.current = "vedic"

    def go_to_chinese(self):
        """Switch to Chinese chart view."""
        chinese = self.manager.get_screen("chinese")
        chinese.set_birth_data(self._birth_data)
        self.manager.current = "chinese"

    def go_home(self):
        self.manager.current = "home"

    def go_to_interpretations(self):
        self.manager.current = "interpretations"

    # -- database (save / load) ----------------------------------------------
    def go_to_database(self):
        """Open the Database panel, handing it the current birth data to save."""
        database = self.manager.get_screen("database")
        database.set_context_birth_data(self._birth_data)
        self.manager.current = "database"

    def save_current_chart(self):
        """Persist the current birth data to the chart store (one tap)."""
        if self._birth_data is None:
            self._set_status("No chart to save yet - generate one first.")
            return
        record = save_chart(self._birth_data)
        self._set_status(f'Saved "{record.name}".')

    def scale_font(self, delta: float):
        """Grow/shrink the interpretation text, clamped to 8..32sp."""
        self._font_size = min(32.0, max(8.0, self._font_size + delta))
        if self.chart_output is not None:
            self.chart_output.font_size = f"{self._font_size}sp"

    def _set_status(self, text: str):
        if self.chart_status is not None:
            self.chart_status.text = text

    def show_full_report(self):
        """Restore the full text report in the details panel."""
        self._render()

    # -- rendering ----------------------------------------------------------
    def _render(self):
        if self.chart_output is None or self._natal_chart is None:
            return
        self.chart_output.text = full_birth_report(self._natal_chart)