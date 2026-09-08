"""Database-screen UI tests: save, load, delete and example seeding.

The Database screen is a thin Kivy wrapper over ``core.chart_store``. These
tests build the real app (so the KV layout wires the ObjectProperties) but
redirect the chart store to a ``tmp_path`` file so no real user data changes.
"""

from datetime import datetime, timezone

from kivy.clock import Clock
from kivy.core.window import Window

from core.chart_store import (
    clear_chart_store,
    configure_chart_store,
    delete_chart,
    load_saved_charts,
)
from core.models import BirthData, Location
from ui.main import AstroFlowApp


def _birth_data() -> BirthData:
    return BirthData(
        name="Test Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5074, longitude=-0.1278, name="London, UK"),
        house_system="P",
    )


def _fresh_app(tmp_path):
    """Build the app and redirect its chart store to a throwaway file."""
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()          # build() configures the store to user_data_dir
    configure_chart_store(str(tmp_path / "charts.json"))  # override it
    clear_chart_store()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(3):
        Clock.tick()
    return app, sm


def test_database_screen_saves_context_chart(tmp_path):
    app, sm = _fresh_app(tmp_path)
    db = sm.get_screen("database")

    db.set_context_birth_data(_birth_data())
    db.save_current_chart()

    charts = load_saved_charts()
    assert len(charts) == 1
    assert charts[0].name == "Test Native"
    # The list re-rendered with at least one row (non-empty state).
    assert db.list_container is not None
    assert len(db.list_container.children) >= 1


def test_database_screen_load_chart_fills_home_form(tmp_path):
    app, sm = _fresh_app(tmp_path)
    db = sm.get_screen("database")
    home = sm.get_screen("home")

    # Save a chart straight into the store, then load it via the UI action.
    from core.chart_store import save_chart
    record = save_chart(_birth_data())

    db.load_chart(record)

    assert sm.current == "home"
    assert home.name_input.text == "Test Native"
    assert home.date_input.text == "2000-01-01"
    assert home.time_input.text == "12:00"
    assert home.latlon_input.text == "51.5074, -0.1278"


def test_database_screen_delete(tmp_path):
    app, sm = _fresh_app(tmp_path)
    db = sm.get_screen("database")

    first = _birth_data()
    second = _birth_data()
    second.name = "Second"
    from core.chart_store import save_chart
    keep = save_chart(first)
    save_chart(second)

    db.delete_chart(keep)

    remaining = load_saved_charts()
    assert len(remaining) == 1
    assert remaining[0].name == "Second"


def test_database_screen_seeds_examples(tmp_path):
    app, sm = _fresh_app(tmp_path)
    db = sm.get_screen("database")

    db.load_examples()

    charts = load_saved_charts()
    assert len(charts) == 5
    names = {c.name for c in charts}
    assert "Albert Einstein" in names
    assert "Elvis Presley" in names


def test_chart_screen_save_and_go_to_database(tmp_path):
    app, sm = _fresh_app(tmp_path)
    chart_scr = sm.get_screen("chart")
    db = sm.get_screen("database")

    chart_scr.set_birth_data(_birth_data())
    chart_scr.save_current_chart()
    assert len(load_saved_charts()) == 1
    assert "Saved" in chart_scr.chart_status.text

    chart_scr.go_to_database()
    assert sm.current == "database"
    assert db._context_bd is not None
    assert db._context_bd.name == "Test Native"


def test_chart_screen_save_without_data_shows_status(tmp_path):
    app, sm = _fresh_app(tmp_path)
    chart_scr = sm.get_screen("chart")
    chart_scr.save_current_chart()
    assert "No chart" in chart_scr.chart_status.text
    assert load_saved_charts() == []
