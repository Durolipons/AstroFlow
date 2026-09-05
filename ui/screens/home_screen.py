"""Home screen: birth-data entry form.

The user fills in name, birth date/time, location, and zodiac settings, then
presses "Generate Chart". The screen builds a ``BirthData`` and asks the
parent ``ScreenManager`` to show the ``ChartScreen``.

NOTE: All astrology logic lives in ``core/``; this screen only collects input
and hands a ``BirthData`` object to the engine.

Combined fields (parsed on submit):
    date_input   -- "YYYY-MM-DD"  (also accepts "YYYY/MM/DD" or "YYYY MM DD")
    time_input   -- "HH:MM"       (also accepts "HH MM")
    latlon_input -- "lat, lon"    (also accepts "lat lon")
"""

import re
from datetime import datetime, timezone, timedelta

from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from core import chart as core_chart
from core.models import BirthData, Location
from core import constants as C
from core.geocoder import CompositeLookup, LocalCitiesLookup, NominatimLookup
from ui.widgets import AstroClock, CitySearch  # noqa: F401 (KV factory)


class HomeScreen(Screen):
    """Birth-data entry form.

    Layout (defined in ``app.kv``):
        Name, combined date/time/location fields, a city search dropdown just
        above the lat/lon field, a "Find city" button, house-system spinner,
        an online-search toggle, and a "Generate Chart" button.
    """

    # These ids are wired up by app.kv.
    name_input = ObjectProperty(None)
    date_input = ObjectProperty(None)
    time_input = ObjectProperty(None)
    latlon_input = ObjectProperty(None)
    tz_input = ObjectProperty(None)
    house_spinner = ObjectProperty(None)
    sidereal_spinner = ObjectProperty(None)
    status_label = ObjectProperty(None)
    city_search = ObjectProperty(None)
    astro_clock = ObjectProperty(None)

    def on_city_selected(self, _widget, city):
        """Callback from the CitySearch widget: fill lat/lon/tz from a city.

        NOTE: deliberately does NOT touch ``name_input`` -- the Name field is
        the person the chart is for, not the birth place.
        """
        self.latlon_input.text = f"{city.latitude}, {city.longitude}"
        self.tz_input.text = city.timezone
        self._set_status("")
        self._sync_astro_clock_profile()

    def find_city_from_coords(self):
        """Reverse-geocode the entered lat/lon into a city name."""
        lat, lon = self._parse_latlon()
        if lat is None:
            return

        # Build a lookup: local-only unless the user opted into online search.
        online = getattr(self, "online_active", False)
        lookup = (
            CompositeLookup(LocalCitiesLookup(), NominatimLookup())
            if online
            else LocalCitiesLookup()
        )
        city = lookup.reverse(lat, lon)
        if city is None:
            self._set_status("No city found near those coordinates.")
            return
        self.on_city_selected(self.city_search, city)

    def toggle_online(self, active):
        """Called by the online-search checkbox in the KV layout."""
        self.online_active = active

    # -- famous-people presets ---------------------------------------------
    def show_presets(self):
        """Open a popup listing famous people with complete birth data."""
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.button import Button

        from ui.presets import PRESETS

        layout = BoxLayout(orientation="vertical", spacing=2,
                           size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))

        for preset in PRESETS:
            btn = Button(
                text=preset.row_text,
                size_hint_y=None, height=36,
                halign="left", valign="middle",
            )
            btn.bind(size=lambda b, s: b.setter("text_size")(b, s))
            btn.bind(on_release=lambda _b, p=preset: self._pick_preset(p))
            layout.add_widget(btn)

        scroll = ScrollView(do_scroll_x=False, bar_width=8)
        scroll.add_widget(layout)

        self._presets_popup = Popup(
            title="Load a famous chart (test preset)",
            content=scroll,
            size_hint=(0.85, 0.6),
        )
        self._presets_popup.open()

    def _pick_preset(self, preset):
        """Fill every form field from a ``Preset`` (called from the popup)."""
        self.name_input.text = preset.name
        self.date_input.text = preset.date
        self.time_input.text = preset.time
        self.latlon_input.text = preset.latlon
        self.tz_input.text = preset.timezone
        self._set_status(f"Loaded preset: {preset.name} — {preset.place}")
        self._sync_astro_clock_profile()
        # Close the popup so the user can press "Generate Chart" right away.
        if getattr(self, "_presets_popup", None) is not None:
            self._presets_popup.dismiss()
            self._presets_popup = None

    def go_to_interpretations(self):
        """Open the interpretation editor screen."""
        self.manager.current = "interpretations"

    def generate_chart(self):
        """Validate the form, build a BirthData, compute the natal chart."""
        try:
            bd = self._build_birth_data()
        except ValueError as exc:
            self._set_status(f"Error: {exc}")
            return

        # Compute the natal chart (delegated entirely to the engine).
        natal = core_chart.calculate_birth_chart(bd)
        self._sync_astro_clock_profile(bd)

        # Stash the birth data + chart on the chart screen and switch to it.
        chart_screen = self.manager.get_screen("chart")
        chart_screen.set_birth_data(bd)
        chart_screen.set_natal_chart(natal)
        self.manager.current = "chart"

    def on_kv_post(self, base_widget):
        self._sync_astro_clock_profile()

    # -- parsing helpers ----------------------------------------------------
    def _parse_latlon(self):
        """Parse the combined lat/lon field. Returns (lat, lon) or (None, None)."""
        text = self.latlon_input.text.strip()
        parts = [p for p in re.split(r"[,\s]+", text) if p]
        if len(parts) < 2:
            self._set_status("Enter latitude and longitude (e.g. 51.5, -0.13).")
            return None, None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            self._set_status("Invalid latitude/longitude numbers.")
            return None, None

    # -- internals ----------------------------------------------------------
    def _build_birth_data(self) -> BirthData:
        """Parse the form fields into a ``BirthData``."""
        name = self.name_input.text.strip() or "Native"

        # Date: "YYYY-MM-DD" (also "/" or space separated).
        date_parts = re.split(r"[/\-\s]+", self.date_input.text.strip())
        if len(date_parts) != 3:
            raise ValueError("Date must be YYYY-MM-DD (e.g. 2000-01-01).")
        year, month, day = (int(p) for p in date_parts)

        # Time: "HH:MM" (also space separated).
        time_parts = re.split(r"[:\s]+", self.time_input.text.strip())
        if len(time_parts) != 2:
            raise ValueError("Time must be HH:MM (e.g. 12:00).")
        hour, minute = (int(p) for p in time_parts)

        lat, lon = self._parse_latlon()
        if lat is None:
            raise ValueError("Invalid latitude/longitude.")

        tz_text = self.tz_input.text.strip()

        # Timezone: accept a UTC offset in hours (e.g. "5.5" or "-4") or a
        # named IANA zone. Fall back to UTC when blank.
        tz = timezone.utc
        if tz_text:
            try:
                offset_hours = float(tz_text)
                tz = timezone(timedelta(hours=offset_hours))
            except ValueError:
                # Try an IANA zone name.
                try:
                    import zoneinfo
                    tz = zoneinfo.ZoneInfo(tz_text)
                except Exception:
                    raise ValueError(
                        f"Unrecognized timezone {tz_text!r}. "
                        "Use a UTC offset (e.g. -5) or IANA name (e.g. US/Eastern)."
                    )

        # House system: spinner text -> single-char code.
        house_label = self.house_spinner.text
        house_system = C.HOUSE_SYSTEMS.get(house_label, "P")

        # Sidereal mode: "Tropical (default)" -> None, otherwise the label.
        sidereal_label = self.sidereal_spinner.text
        sidereal_mode = None
        if sidereal_label and "Tropical" not in sidereal_label:
            sidereal_mode = sidereal_label

        birth_dt = datetime(year, month, day, hour, minute, tzinfo=tz)
        location = Location(latitude=lat, longitude=lon, name="")

        return BirthData(
            name=name,
            birth_datetime=birth_dt,
            location=location,
            house_system=house_system,
            sidereal_mode=sidereal_mode,
        )

    def _set_status(self, text: str) -> None:
        if self.status_label:
            self.status_label.text = text

    def _sync_astro_clock_profile(self, birth_data: BirthData = None) -> None:
        """Keep the Astro-Clock aligned with the current form location."""
        if self.astro_clock is None:
            return
        bd = birth_data
        if bd is None:
            try:
                bd = self._build_birth_data()
            except ValueError:
                return
        self.astro_clock.set_profile(bd)