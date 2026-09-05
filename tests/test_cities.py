"""City-database and geocoder tests."""

import json
import os

import pytest

from core.cities import City, load_cities, nearest_city, search_cities
from core.geocoder import CompositeLookup, LocalCitiesLookup, NominatimLookup
from core.utils import distance_km


# ---------------------------------------------------------------------------
# Data file integrity
# ---------------------------------------------------------------------------
def test_data_file_exists():
    path = os.path.join(os.path.dirname(__file__), "..", "core", "data", "cities.json")
    assert os.path.isfile(path)


def test_data_loads_and_is_non_empty():
    cities = load_cities()
    assert len(cities) > 1000  # we bundled ~2000


def test_data_records_are_valid():
    cities = load_cities()
    assert len(cities) >= 1000
    for c in cities:
        assert c.name, "city has no name"
        assert c.timezone, "city has no timezone"
        assert -90 <= c.latitude <= 90, f"bad lat for {c.name}"
        assert -180 <= c.longitude <= 180, f"bad lon for {c.name}"


def test_data_has_multiple_countries():
    cities = load_cities()
    countries = {c.country for c in cities}
    assert len(countries) > 50


# ---------------------------------------------------------------------------
# search_cities
# ---------------------------------------------------------------------------
def test_search_exact_city():
    results = search_cities("London")
    assert any(c.name == "London" for c in results)


def test_search_is_case_insensitive():
    lower = search_cities("london")
    upper = search_cities("LONDON")
    assert [c.name for c in lower] == [c.name for c in upper]


def test_search_prefix_ranked_first():
    results = search_cities("san")
    # San Francisco / San Diego etc. should appear before non-prefix matches.
    assert results, "no results for 'san'"
    assert results[0].name.lower().startswith("san")


def test_search_empty_query_returns_population_ranked():
    results = search_cities("", limit=10)
    assert len(results) == 10
    # First result should be among the most populous (Shanghai / Beijing).
    assert results[0].population >= 10_000_000


def test_search_limits_results():
    results = search_cities("a", limit=5)
    assert len(results) <= 5


# ---------------------------------------------------------------------------
# nearest_city
# ---------------------------------------------------------------------------
def test_nearest_city_london():
    city = nearest_city(51.5074, -0.1278)
    assert city is not None
    assert city.name == "London"


def test_nearest_city_respects_max_km():
    # London coords, but only allow 1 km → should still find London itself.
    assert nearest_city(51.5074, -0.1278, max_km=1.0) is not None
    # A point in the middle of the Atlantic with a tiny radius → None.
    assert nearest_city(0.0, -30.0, max_km=10.0) is None


def test_nearest_city_tokyo():
    # Central Tokyo. The nearest DB entry may be a special ward (Shinjuku,
    # Nakano, …) rather than the "Tokyo" entry itself, so assert the timezone.
    city = nearest_city(35.6812, 139.7671)
    assert city is not None
    assert city.timezone == "Asia/Tokyo"


# ---------------------------------------------------------------------------
# distance_km
# ---------------------------------------------------------------------------
def test_distance_km_same_point():
    assert distance_km(51.5, -0.1, 51.5, -0.1) == pytest.approx(0.0, abs=1e-6)


def test_distance_km_london_to_paris():
    # London → Paris is roughly 340 km.
    d = distance_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert 300 < d < 400


# ---------------------------------------------------------------------------
# Geocoder backends
# ---------------------------------------------------------------------------
def test_local_lookup_search():
    lookup = LocalCitiesLookup()
    results = lookup.search("Paris")
    assert any(c.name == "Paris" for c in results)


def test_local_lookup_reverse():
    lookup = LocalCitiesLookup()
    city = lookup.reverse(48.8566, 2.3522)  # Paris
    assert city is not None
    assert city.name == "Paris"


def test_composite_lookup_uses_local_first():
    """CompositeLookup with a local hit must NOT call the online backend."""
    class ExplodingOnline:
        """Raises if ever called — proves local-first behavior."""
        def search(self, query, limit=5):
            raise AssertionError("online backend should not be called")
        def reverse(self, lat, lon):
            raise AssertionError("online backend should not be called")

    lookup = CompositeLookup(LocalCitiesLookup(), ExplodingOnline())
    results = lookup.search("Berlin")
    assert any(c.name == "Berlin" for c in results)


def test_composite_lookup_falls_back_to_online():
    """When local returns nothing, the online backend is consulted."""
    class FakeOnline:
        def search(self, query, limit=5):
            return [City(name="Xylotown", country="XX", latitude=1.0,
                         longitude=2.0, timezone="UTC")]
        def reverse(self, lat, lon):
            return None

    class EmptyLocal:
        def search(self, query, limit=5):
            return []
        def reverse(self, lat, lon):
            return None

    lookup = CompositeLookup(EmptyLocal(), FakeOnline())
    results = lookup.search("anything")
    assert results and results[0].name == "Xylotown"


def test_nominatim_lookup_class_exists():
    """NominatimLookup can be instantiated (network call is not made here)."""
    lookup = NominatimLookup()
    assert lookup.user_agent
    assert lookup.timeout > 0


# ---------------------------------------------------------------------------
# HomeScreen combined-field parsing (unit-level, no Kivy needed)
# ---------------------------------------------------------------------------
class _F:
    def __init__(self, text=""):
        self.text = text


def _make_home():
    from ui.screens.home_screen import HomeScreen
    # Build a real HomeScreen but only use its _parse_latlon / _build_birth_data.
    home = HomeScreen.__new__(HomeScreen)
    home.date_input = _F("2000-01-01")
    home.time_input = _F("12:00")
    home.latlon_input = _F("51.5, -0.13")
    home.tz_input = _F("Europe/London")
    home.name_input = _F("")
    home.house_spinner = _F()
    home.house_spinner.text = "Placidus"
    home.sidereal_spinner = _F()
    home.sidereal_spinner.text = "Tropical (default)"
    home._status = ""
    return home


def test_parse_latlon_comma():
    home = _make_home()
    home.latlon_input.text = "48.8566, 2.3522"
    assert home._parse_latlon() == (48.8566, 2.3522)


def test_parse_latlon_spaces():
    home = _make_home()
    home.latlon_input.text = "51.5 -0.13"
    lat, lon = home._parse_latlon()
    assert lat == 51.5 and lon == -0.13


def test_parse_latlon_too_few_parts():
    home = _make_home()
    home.latlon_input.text = "51.5"
    assert home._parse_latlon() == (None, None)


def test_build_birth_data_combined_fields():
    home = _make_home()
    home.date_input.text = "2000-06-15"
    home.time_input.text = "14:30"
    home.latlon_input.text = "48.8566, 2.3522"
    home.tz_input.text = "Europe/Paris"
    bd = home._build_birth_data()
    assert bd.birth_datetime.year == 2000
    assert bd.birth_datetime.month == 6
    assert bd.birth_datetime.day == 15
    assert bd.birth_datetime.hour == 14
    assert bd.birth_datetime.minute == 30
    assert bd.location.latitude == 48.8566
    assert bd.location.longitude == 2.3522


def test_build_birth_data_date_with_slashes():
    home = _make_home()
    home.date_input.text = "2000/06/15"
    bd = home._build_birth_data()
    assert (bd.birth_datetime.year, bd.birth_datetime.month, bd.birth_datetime.day) == (2000, 6, 15)


def test_build_birth_data_invalid_date_raises():
    home = _make_home()
    home.date_input.text = "not-a-date"
    import pytest
    with pytest.raises(ValueError):
        home._build_birth_data()


# ---------------------------------------------------------------------------
# Famous-people presets
# ---------------------------------------------------------------------------
def test_presets_exist():
    from ui.presets import PRESETS
    assert len(PRESETS) >= 5
    names = {p.name for p in PRESETS}
    assert "Albert Einstein" in names
    assert "Winston Churchill" in names


def test_preset_records_are_well_formed():
    from ui.presets import PRESETS
    for p in PRESETS:
        assert p.date.count("-") == 2, f"bad date {p.date!r}"
        assert ":" in p.time, f"bad time {p.time!r}"
        lat, lon = p.latlon.split(",")
        assert -90 <= float(lat) <= 90
        assert -180 <= float(lon) <= 180
        assert "/" in p.timezone  # IANA-style zone name
        assert p.place  # non-empty


def test_get_preset_case_insensitive():
    from ui.presets import get_preset
    assert get_preset("albert einstein") is not None
    assert get_preset("ALBERT EINSTEIN") is not None
    assert get_preset("Nobody Real") is None


def test_city_select_does_not_overwrite_name():
    """BUG REGRESSION: selecting a city must not touch the Name field."""
    from ui.widgets.city_search import CitySearch
    from ui.main import AstroFlowApp
    import os
    os.environ["KIVY_LOG_LEVEL"] = "error"

    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")
    home.name_input.text = "Jane Doe"

    # Find the CitySearch instance and dispatch a selection.
    found = []

    def walk(w):
        if isinstance(w, CitySearch):
            found.append(w)
        for c in w.children:
            walk(c)

    walk(home)
    from core.cities import search_cities
    found[0].dispatch("on_city_selected", search_cities("london")[0])

    assert home.name_input.text == "Jane Doe", "name must not change"
    assert "," in home.latlon_input.text  # lat/lon were filled


def test_pick_preset_fills_all_fields():
    """Loading a preset fills name, date, time, lat/lon and timezone."""
    from ui.presets import get_preset
    from ui.main import AstroFlowApp
    import os
    os.environ["KIVY_LOG_LEVEL"] = "error"

    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")

    home._pick_preset(get_preset("Marilyn Monroe"))
    assert home.name_input.text == "Marilyn Monroe"
    assert home.date_input.text == "1926-06-01"
    assert home.time_input.text == "09:30"
    lat, lon = home.latlon_input.text.split(",")
    assert 34.0 < float(lat) < 34.1
    assert -118.3 < float(lon) < -118.2
    assert home.tz_input.text == "America/Los_Angeles"


def test_pick_preset_dismisses_popup():
    """BUG REGRESSION: the preset popup must close after a selection."""
    from ui.presets import get_preset
    from ui.main import AstroFlowApp
    import os
    os.environ["KIVY_LOG_LEVEL"] = "error"

    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")
    home.show_presets()
    assert home._presets_popup is not None

    home._pick_preset(get_preset("Elvis Presley"))
    assert home._presets_popup is None, "popup was not dismissed"


def test_generate_chart_screen_renders_text():
    """BUG REGRESSION: 'Generate Chart' must not lead to a blank page."""
    from ui.presets import get_preset
    from ui.main import AstroFlowApp
    import os
    os.environ["KIVY_LOG_LEVEL"] = "error"

    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")
    chart_scr = sm.get_screen("chart")

    # The KV binding chart_output: chart_output must be in place.
    assert chart_scr.chart_output is not None, "chart_output not bound"

    home._pick_preset(get_preset("Marilyn Monroe"))
    home.generate_chart()

    assert sm.current == "chart"
    text = chart_scr.chart_output.text
    assert len(text) > 200, "chart screen is blank"
    assert "Marilyn Monroe" in text
    assert "NATAL" in text.upper()


def test_forecast_screen_renders_text():
    """BUG REGRESSION: forecast screen must not be blank either."""
    from ui.presets import get_preset
    from ui.main import AstroFlowApp
    import os
    os.environ["KIVY_LOG_LEVEL"] = "error"

    app = AstroFlowApp()
    sm = app.build()
    home = sm.get_screen("home")
    forecast_scr = sm.get_screen("forecast")

    assert forecast_scr.forecast_output is not None, "forecast_output not bound"

    home._pick_preset(get_preset("Winston Churchill"))
    fc_scr = sm.get_screen("forecast")
    fc_scr.set_birth_data(home._build_birth_data())
    fc_scr.generate_forecast()

    assert len(fc_scr.forecast_output.text) > 200, "forecast screen is blank"