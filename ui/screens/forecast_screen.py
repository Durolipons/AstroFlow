"""Forecast screen: progressions + solar arc + transits.

The user picks a target date (defaults to today). The screen asks the engine
for secondary progressions, solar arc directions, and transit-to-natal
aspects, then renders the combined report via ``core.interpretation``.

HOOK: add date-range scanning to surface the strongest transit aspects across
a week or month instead of a single day.
"""

from datetime import datetime, timezone

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core.aspects import find_aspects_between_charts
from core.chart import calculate_birth_chart
from core import forecast
from core.models import BirthData
from core.progressions import secondary_progressions, solar_arc_directions
from core.transits import transits_to_natal
from core.interpretation import (
    aspect_detail_text,
    full_forecast_report,
    planet_detail_text,
    sign_detail_text,
    transit_aspect_detail,
    transit_planet_detail,
)
from ui.widgets.astro_clock import _copy_to_clipboard
from ui.widgets import SquareWheelHost  # noqa: F401 (KV factory)
from ui.widgets.chart_wheel import ChartWheel  # noqa: F401 (KV factory)


class ForecastScreen(Screen):
    """Forecast display for a user-chosen target date."""

    forecast_output = ObjectProperty(None)  # TextInput (wired by app.kv)
    summary_label = ObjectProperty(None)
    target_year = ObjectProperty(None)
    target_month = ObjectProperty(None)
    target_day = ObjectProperty(None)
    target_hour = ObjectProperty(None)
    target_minute = ObjectProperty(None)
    date_source = ObjectProperty(None)
    forecast_period = ObjectProperty(None)
    chart_host = ObjectProperty(None)     # square host for the wheel
    wheel = ObjectProperty(None)          # ChartWheel (wired by app.kv)

    def __init__(self, **kwargs):
        self._birth_data: BirthData = None
        self._natal_chart = None
        self._transit = None
        self._prog = None
        self._arc = None
        self._overlay_mode = "Transits"
        self._last_report: str = ""
        self._font_size: float = 13.0
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self._sync_summary()
        self._default_to_now()
        if self.wheel is not None:
            self.wheel.bind(on_planet_selected=self._on_planet_picked)
            self.wheel.bind(on_sign_selected=self._on_sign_picked)
            self.wheel.bind(on_aspect_selected=self._on_aspect_picked)
        if self.chart_host is not None and self.wheel is not None:
            self.chart_host.wheel = self.wheel
            self.chart_host._sync_wheel()

    # -- called by ChartScreen ----------------------------------------------
    def set_birth_data(self, bd: BirthData) -> None:
        self._birth_data = bd
        self._sync_summary()
        if self.date_source is None or self.date_source.text == "Now":
            self._default_to_now()
        # Pre-render the natal wheel (plain single ring) as soon as a
        # birth chart is loaded; the transit overlay appears on generate.
        self._natal_chart = None
        self._transit = None
        self._prog = None
        self._arc = None
        try:
            self._natal_chart = calculate_birth_chart(bd)
        except Exception:
            self._natal_chart = None
        if self.wheel is not None and self._natal_chart is not None:
            self.wheel.set_chart(self._natal_chart)
            self.wheel.clear_overlay()
        # Auto-render the forecast report so the screen isn't blank when the
        # user navigates here from the Chart screen's "Forecast ->" button.
        self.generate_forecast()

    def _default_to_now(self) -> None:
        """Fill the target-date fields with the current UTC date/time."""
        now = datetime.now(timezone.utc)
        if self.target_year:
            self.target_year.text = str(now.year)
        if self.target_month:
            self.target_month.text = str(now.month)
        if self.target_day:
            self.target_day.text = str(now.day)
        if self.target_hour:
            self.target_hour.text = str(now.hour)
        if self.target_minute:
            self.target_minute.text = str(now.minute)

    # -- navigation ---------------------------------------------------------
    def go_to_chart(self):
        if self._birth_data is not None:
            chart = self.manager.get_screen("chart")
            chart.set_birth_data(self._birth_data)
        self.manager.current = "chart"

    def go_home(self):
        self.manager.current = "home"

    def go_to_interpretations(self):
        self.manager.current = "interpretations"

    # -- generation ---------------------------------------------------------
    def generate_now(self):
        """Set the target date to right now (UTC) and generate immediately."""
        self._default_to_now()
        self.generate_forecast()

    def set_date_source(self, source: str) -> None:
        """Apply the selected target-date source."""
        if source == "Now":
            self._default_to_now()

    def generate_forecast(self):
        """Parse the target date and render the full forecast report."""
        if self._birth_data is None:
            self._set_output("No birth data. Please enter it on the Home screen first.")
            return
        if self.date_source is not None and self.date_source.text == "Now":
            self._default_to_now()
        try:
            year = int(self.target_year.text.strip())
            month = int(self.target_month.text.strip())
            day = int(self.target_day.text.strip())
            hour = int(self.target_hour.text.strip()) if (
                self.target_hour and self.target_hour.text.strip()) else 12
            minute = int(self.target_minute.text.strip()) if (
                self.target_minute and self.target_minute.text.strip()) else 0
            target = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        except (ValueError, AttributeError) as exc:
            self._set_output(f"Invalid target date: {exc}")
            return

        # All calculations are delegated to the engine.
        prog = secondary_progressions(self._birth_data, target)
        arc = solar_arc_directions(self._birth_data, target)
        transit = transits_to_natal(self._birth_data, target)

        self._transit = transit
        self._natal_chart = transit.birth_chart
        self._prog = prog
        self._arc = arc

        period_name = (
            self.forecast_period.text
            if self.forecast_period is not None else "Day"
        )
        period = forecast.calendar_forecast(period_name, target)
        natal_sun = next(
            (position for position in self._natal_chart.positions
             if position.name == "Sun"),
            None,
        )
        horoscope = None
        if natal_sun is not None:
            horoscope = forecast.sun_sign_horoscope(period, natal_sun.sign)
        report = full_forecast_report(
            self._natal_chart,
            prog,
            arc,
            transit,
            sign_horoscope=horoscope,
        )
        self._last_report = report
        self._set_output(report)

        # Bi-wheel: natal inside; the outer ring follows the Overlay mode
        # (Transits / Progressions / Solar Arc / Off).
        self._apply_overlay()

    # -- overlay toggle ------------------------------------------------------
    def set_overlay_mode(self, mode: str) -> None:
        """Switch the outer ring: Transits / Progressions / Solar Arc / Off."""
        self._overlay_mode = mode
        self._apply_overlay()

    def _apply_overlay(self) -> None:
        """Put the currently selected overlay chart on the wheel."""
        if self.wheel is None or self._natal_chart is None:
            return
        self.wheel.set_chart(self._natal_chart)
        mode = self._overlay_mode
        if mode == "Transits" and self._transit is not None:
            self.wheel.set_overlay(
                self._transit.transit_chart, self._transit.aspects,
                suffix="transit")
        elif mode == "Progressions" and self._prog is not None:
            pa = find_aspects_between_charts(
                self._prog.positions, self._natal_chart.positions,
                suffix="prog")
            self.wheel.set_overlay(self._prog, pa, suffix="prog")
        elif mode == "Solar Arc" and self._arc is not None:
            aa = find_aspects_between_charts(
                self._arc.chart.positions, self._natal_chart.positions,
                suffix="arc")
            self.wheel.set_overlay(self._arc.chart, aa, suffix="arc")
        else:
            self.wheel.clear_overlay()

    # -- wheel taps ---------------------------------------------------------
    def _on_planet_picked(self, _wheel, planet_name: str):
        if self.forecast_output is None:
            return
        if planet_name.endswith("(transit)") and self._transit is not None:
            base = planet_name[: -len("(transit)")].strip()
            self.forecast_output.text = transit_planet_detail(
                self._transit.transit_chart, base,
                natal_aspects=self._transit.aspects)
        elif planet_name.endswith("(prog)") and self._prog is not None:
            base = planet_name[: -len("(prog)")].strip()
            self.forecast_output.text = planet_detail_text(self._prog, base)
        elif planet_name.endswith("(arc)") and self._arc is not None:
            base = planet_name[: -len("(arc)")].strip()
            self.forecast_output.text = planet_detail_text(
                self._arc.chart, base)
        elif self._natal_chart is not None:
            self.forecast_output.text = planet_detail_text(
                self._natal_chart, planet_name)

    def _on_sign_picked(self, _wheel, sign_name: str):
        if self._natal_chart is not None and self.forecast_output is not None:
            self.forecast_output.text = sign_detail_text(
                self._natal_chart, sign_name)

    def _on_aspect_picked(self, _wheel, aspect):
        if self.forecast_output is None:
            return
        if aspect.planet1_name.endswith("(transit)"):
            self.forecast_output.text = transit_aspect_detail(aspect)
        else:
            self.forecast_output.text = aspect_detail_text(aspect)

    # -- rendering ----------------------------------------------------------
    def show_full_report(self):
        """Restore the full text report after a wheel tap."""
        if self._last_report:
            self._set_output(self._last_report)

    def copy_output(self, *_args):
        """Copy the forecast report text to the clipboard."""
        if self.forecast_output is None:
            return False
        return _copy_to_clipboard(self.forecast_output.text)

    def scale_font(self, delta: float):
        """Grow/shrink the forecast report text, clamped to 8..32sp."""
        self._font_size = min(32.0, max(8.0, self._font_size + delta))
        if self.forecast_output is not None:
            self.forecast_output.font_size = f"{self._font_size}sp"

    def _set_output(self, text: str) -> None:
        if self.forecast_output:
            self.forecast_output.text = text

    def _sync_summary(self) -> None:
        if self.summary_label is None:
            return
        if self._birth_data is None:
            self.summary_label.text = "No birth chart loaded."
            return
        bd = self._birth_data
        loc = bd.location
        place = loc.name.strip() if loc.name else f"{loc.latitude:+.4f}, {loc.longitude:+.4f}"
        self.summary_label.text = (
            f"Using chart for {bd.name or 'Native'}\n"
            f"{bd.birth_datetime:%Y-%m-%d %H:%M}\n"
            f"{place}"
        )