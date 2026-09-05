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

from core.models import BirthData
from core.progressions import secondary_progressions, solar_arc_directions
from core.transits import transits_to_natal
from core.interpretation import full_forecast_report


class ForecastScreen(Screen):
    """Forecast display for a user-chosen target date."""

    forecast_output = ObjectProperty(None)  # TextInput (wired by app.kv)
    summary_label = ObjectProperty(None)
    target_year = ObjectProperty(None)
    target_month = ObjectProperty(None)
    target_day = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._birth_data: BirthData = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self._sync_summary()

    # -- called by ChartScreen ----------------------------------------------
    def set_birth_data(self, bd: BirthData) -> None:
        self._birth_data = bd
        self._sync_summary()
        # Default the target date to "today" (UTC).
        now = datetime.now(timezone.utc)
        if self.target_year:
            self.target_year.text = str(now.year)
        if self.target_month:
            self.target_month.text = str(now.month)
        if self.target_day:
            self.target_day.text = str(now.day)

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
    def generate_forecast(self):
        """Parse the target date and render the full forecast report."""
        if self._birth_data is None:
            self._set_output("No birth data. Please enter it on the Home screen first.")
            return
        try:
            year = int(self.target_year.text.strip())
            month = int(self.target_month.text.strip())
            day = int(self.target_day.text.strip())
            target = datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
        except (ValueError, AttributeError) as exc:
            self._set_output(f"Invalid target date: {exc}")
            return

        # All calculations are delegated to the engine.
        prog = secondary_progressions(self._birth_data, target)
        arc = solar_arc_directions(self._birth_data, target)
        transit = transits_to_natal(self._birth_data, target)

        report = full_forecast_report(prog, arc, transit)
        self._set_output(report)

    # -- rendering ----------------------------------------------------------
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