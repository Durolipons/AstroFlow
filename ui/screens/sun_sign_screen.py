"""Sun-sign astro-clock forecasts screen.

Birth-chart free: the user picks a period (Daily / Weekly / Monthly), a start
date (defaults to today) and a sign, and the engine scans the ephemeris to
produce a per-sign horoscope composed from the interpretation library.  The
output is a selectable TextInput so the text can be copied straight into a
post (same workflow as the Forecast screen).
"""

from datetime import datetime, timezone

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from core import constants as C
from core import forecast
from core.interpretation import sign_horoscope_text


_PERIODS = ("Daily", "Weekly", "Monthly", "Yearly")


def _today() -> datetime:
    """Today's date in UTC, truncated to midnight."""
    return datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)


class SunSignForecastScreen(Screen):
    """Pick period + sign + start date and generate an ephemeris horoscope."""

    def __init__(self, **kwargs):
        self._font_size: float = 13.0
        super().__init__(**kwargs)
        self._build_layout()

    def _build_layout(self) -> None:
        root = BoxLayout(orientation="vertical", padding=10, spacing=8)

        title = Label(
            text="Sun-Sign Astro-Clock Forecasts",
            size_hint_y=None, height=dp(40), bold=True, font_size=18,
        )
        root.add_widget(title)

        # Controls row (built in Python so no app.kv change is needed).
        controls = BoxLayout(orientation="horizontal", size_hint_y=None,
                             height=dp(40), spacing=8)
        self.period_spinner = Spinner(text="Daily", values=list(_PERIODS),
                                      size_hint_x=1.0)
        self.sign_spinner = Spinner(text="Aries", values=list(C.SIGNS),
                                    size_hint_x=1.4)
        self.year_input = TextInput(text=str(_today().year),
                                    multiline=False, size_hint_x=0.9)
        self.month_input = TextInput(text=str(_today().month),
                                     multiline=False, size_hint_x=0.7)
        self.day_input = TextInput(text=str(_today().day),
                                   multiline=False, size_hint_x=0.7)
        run_button = Button(text="Generate", size_hint_x=1.2,
                            on_release=lambda _btn: self.generate())
        for widget in (Label(text="Period:"), self.period_spinner,
                       Label(text="Sign:"), self.sign_spinner,
                       Label(text="Year:"), self.year_input,
                       Label(text="Month:"), self.month_input,
                       Label(text="Day:"), self.day_input, run_button):
            controls.add_widget(widget)
        root.add_widget(controls)

        # Nav row
        nav = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(36), spacing=8)
        font_smaller = Button(
            text="A-", size_hint_x=None, width=dp(44),
            on_release=lambda _b: self.scale_font(-1))
        font_larger = Button(
            text="A+", size_hint_x=None, width=dp(44),
            on_release=lambda _b: self.scale_font(1))
        home = Button(text="Home", on_release=lambda _b: self.go_home())
        interpretation = Button(
            text="Interpretations",
            on_release=lambda _b: self.go_to_interpretations())
        nav.add_widget(font_smaller)
        nav.add_widget(font_larger)
        nav.add_widget(home)
        nav.add_widget(interpretation)
        root.add_widget(nav)

        # Output field (selectable -> Ctrl+C to copy)
        self.output_input = TextInput(
            text="Choose a period and a sign, then press Generate.",
            multiline=True, readonly=True,
            font_size=f"{self._font_size}sp",
            size_hint_y=None,
        )
        # Grow the TextInput to fit its content so the ScrollView has a
        # scrollable range and shows its right-side bar for long text.
        self.output_input.bind(
            minimum_height=self.output_input.setter("height")
        )
        # Right-side vertical scrollbar so long horoscopes stay scannable.
        sv = ScrollView(
            do_scroll_x=False,
            bar_width=40,
            bar_color=[0.45, 0.55, 0.85, 0.9],
            bar_inactive_color=[0.45, 0.55, 0.85, 0.35],
            scroll_type=["bars"],
        )
        sv.add_widget(self.output_input)
        root.add_widget(sv)

        self.add_widget(root)

    # -- rendering ----------------------------------------------------------
    def scale_font(self, delta: float) -> None:
        """Grow/shrink the horoscope text, clamped to 8..32sp."""
        self._font_size = min(32.0, max(8.0, self._font_size + delta))
        if self.output_input is not None:
            self.output_input.font_size = f"{self._font_size}sp"

    # -- generation ---------------------------------------------------------
    def generate(self) -> None:
        """Scan the chosen window and render one sign's horoscope."""
        period = self.period_spinner.text or "Daily"
        sign = self.sign_spinner.text or "Aries"
        try:
            start = datetime(int(self.year_input.text.strip()),
                             int(self.month_input.text.strip()),
                             int(self.day_input.text.strip()),
                             tzinfo=timezone.utc)
        except (ValueError, AttributeError) as exc:
            self._set_output(f"Invalid start date: {exc}")
            return

        try:
            period_obj = forecast.calendar_forecast(
                {
                    "Daily": "Day",
                    "Weekly": "Week",
                    "Monthly": "Month",
                    "Yearly": "Year",
                }[period],
                start,
            )
        except Exception as exc:  # pragma: no cover - defensive UI boundary
            self._set_output(f"Could not generate forecast: {exc}")
            return

        horo = forecast.sun_sign_horoscope(period_obj, sign)
        self._set_output(sign_horoscope_text(horo))

    # -- navigation ---------------------------------------------------------
    def go_home(self):
        self.manager.current = "home"

    def go_to_interpretations(self):
        self.manager.current = "interpretations"

    def _set_output(self, text: str) -> None:
        if self.output_input is not None:
            self.output_input.text = text