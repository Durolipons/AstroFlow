"""A searchable city dropdown widget for Kivy.

A search box with a fixed-height scrolling results panel beneath it. As the
user types, the panel filters the bundled city database; tapping a result
fires ``on_city_selected`` with the chosen ``core.cities.City``.

The widget uses a FIXED height (not proportional) so the results panel is
always visible and scrollable.

HOOK: to style the result rows (flags, population, etc.) override
``_build_row_text``.
"""

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from core.cities import City, search_cities
from core.geocoder import LocalCitiesLookup


class CitySearch(BoxLayout):
    """Searchable city dropdown (search box over a fixed-height results panel).

    Dispatches ``on_city_selected(city)`` when the user picks a result.
    """

    def __init__(self, lookup=None, **kwargs):
        # Fixed total height: search box (36) + results panel (150).
        super().__init__(orientation="vertical", spacing=4,
                         size_hint_y=None, height=186, **kwargs)
        self.register_event_type("on_city_selected")
        self.lookup = lookup or LocalCitiesLookup()
        self._results: list[City] = []
        self._trigger = None

        self.search_box = TextInput(
            hint_text="Search city (e.g. London)…",
            multiline=False, size_hint_y=None, height=36,
        )
        self.search_box.bind(text=self._on_text)
        self.add_widget(self.search_box)

        # Results panel: fixed 150px height, internally scrollable.
        self._list_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=2,
        )
        self._list_layout.bind(minimum_height=self._list_layout.setter("height"))

        scroll = ScrollView(size_hint_y=None, height=150,
                            do_scroll_x=False, bar_width=8)
        scroll.add_widget(self._list_layout)
        self.add_widget(scroll)

        # Show an initial, population-ranked list.
        self._update_results(search_cities("", limit=50))

    def on_city_selected(self, city: City):
        """Event: a city was selected (override / bind in KV)."""
        pass

    # -- internal ---------------------------------------------------------
    def _on_text(self, _instance, _value):
        # Debounce slightly so we don't filter on every keystroke.
        if self._trigger is not None:
            self._trigger.cancel()
        self._trigger = Clock.schedule_once(self._apply_filter, 0.15)

    def _apply_filter(self, _dt):
        query = self.search_box.text.strip()
        if not query:
            self._update_results(search_cities("", limit=50))
            return
        # Local DB first; if empty and an online backend exists, ask it.
        results = search_cities(query, limit=50)
        if not results and hasattr(self.lookup, "search"):
            try:
                results = self.lookup.search(query, limit=10)
            except Exception:
                results = []
        self._update_results(results)

    def _update_results(self, results):
        self._results = results
        layout = self._list_layout
        layout.clear_widgets()
        for city in results:
            btn = Button(
                text=self._build_row_text(city),
                size_hint_y=None, height=30,
                halign="left", valign="middle",
            )
            btn.bind(size=lambda b, s: b.setter("text_size")(b, s))
            btn.bind(on_release=lambda _b, c=city: self._select(c))
            layout.add_widget(btn)

    def _build_row_text(self, city: City) -> str:
        return city.label

    def _select(self, city: City):
        self.search_box.text = city.label
        self.dispatch("on_city_selected", city)