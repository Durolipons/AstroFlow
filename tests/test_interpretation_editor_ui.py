"""UI tests for the Interpretation Library editor screen.

These run against an ISOLATED library file (tmp_path) so the astrologer's
real ``interpretations.json`` is never touched by the test suite.
"""

import json
import os

import pytest

os.environ.setdefault("KIVY_LOG_LEVEL", "error")

from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402

from core.interpretation import sky_planet_text  # noqa: E402
from core.interpretation_store import (  # noqa: E402
    configure_interpretation_library,
    interpretation_library_path,
    load_interpretation_library,
)
from ui.main import AstroFlowApp  # noqa: E402


@pytest.fixture()
def editor_screen(tmp_path):
    original = interpretation_library_path()
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    sm.transition.duration = 0
    for _ in range(6):
        Clock.tick()
    screen = sm.get_screen("interpretations")
    isolated = str(tmp_path / "lib.json")
    # Re-point the library at an isolated file AFTER the app wired the real
    # user path, then drop the screen's cached copy of the real library.
    configure_interpretation_library(isolated)
    screen.reload_library()
    try:
        yield screen, isolated
    finally:
        configure_interpretation_library(original)


def test_editor_screen_builds_with_all_categories(editor_screen):
    screen, _ = editor_screen
    assert screen.category_spinner is not None
    labels = list(screen.category_spinner.values)
    for label in ("Sun sign keywords", "Aspect keywords", "Planet roles",
                  "Sky aspect wording", "Sky planet notes",
                  "Sign sky notes"):
        assert label in labels
    # an entry is pre-selected and its text loaded into the editor
    assert screen.entry_spinner.text in screen.entry_spinner.values
    assert screen.key_input.text == screen.entry_spinner.text


def test_editor_sky_categories_map_to_library_fields(editor_screen):
    screen, _ = editor_screen
    screen.select_category("Sky planet notes")
    assert screen._category == "planet_sky_note"
    assert "Sun" in screen.entry_spinner.values
    assert screen.value_input.text

    screen.select_category("Sign sky notes")
    assert screen._category == "sign_sky_note"
    assert "Aries" in screen.entry_spinner.values

    screen.select_category("Sky aspect wording")
    assert screen._category == "sky_aspect_text"
    assert "Trine" in screen.entry_spinner.values


def test_editor_save_persists_and_engine_uses_it(editor_screen):
    screen, path = editor_screen
    screen.select_category("Sky planet notes")
    screen.select_entry("Sun")
    assert screen._selected_key == "Sun"

    screen.value_input.text = "the astrologer's own words"
    screen.save_entry()

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["planet_sky_note"]["Sun"] == "the astrologer's own words"

    # the interpretation engine picks the new wording up immediately
    from datetime import datetime, timezone

    from core.chart import calculate_birth_chart
    from core.models import BirthData, Location
    chart = calculate_birth_chart(
        BirthData(
            name="T",
            birth_datetime=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            location=Location(latitude=51.5, longitude=-0.1),
        )
    )
    assert "the astrologer's own words" in sky_planet_text(chart, "Sun")


def test_editor_restore_defaults_reverts_edits(editor_screen):
    screen, path = editor_screen
    screen.select_category("Sign sky notes")
    screen.select_entry("Aries")
    screen.value_input.text = "temporarily changed"
    screen.save_entry()
    assert load_interpretation_library().sign_sky_note["Aries"] == \
        "temporarily changed"

    screen.restore_defaults()
    lib = load_interpretation_library()
    assert lib.sign_sky_note["Aries"] == (
        "the sky pushes for bold starts and quick decisions")


def test_editor_rejects_blank_text(editor_screen):
    screen, _ = editor_screen
    screen.value_input.text = "   "
    screen.save_entry()
    assert "cannot be blank" in screen.status_label.text.lower()


def test_editor_shows_new_natal_categories(editor_screen):
    """New natal combination categories appear in the spinner."""
    screen, _ = editor_screen
    labels = list(screen.category_spinner.values)
    for label in ("Planet in sign", "Planet in house", "Sun / Moon blend",
                  "Planet-pair aspect", "Angle in sign", "Retrograde note"):
        assert label in labels


def test_editor_shows_new_forecast_categories(editor_screen):
    """New Astro-Clock forecast categories appear in the spinner."""
    screen, _ = editor_screen
    labels = list(screen.category_spinner.values)
    for label in ("Forecast ingress", "Forecast station", "Forecast lunation"):
        assert label in labels


def test_editor_planet_sign_category_loads_entries(editor_screen):
    """Selecting 'Planet in sign' populates the entry spinner with planet-sign keys."""
    screen, _ = editor_screen
    screen.select_category("Planet in sign")
    assert screen._category == "planet_sign"
    assert "Sun in Gemini" in screen.entry_spinner.values
    assert "Moon in Cancer" in screen.entry_spinner.values
    assert screen.value_input.text  # default text loaded


def test_editor_forecast_phase_category_loads_entries(editor_screen):
    """Selecting 'Forecast lunation' populates the entry spinner with phase keys."""
    screen, _ = editor_screen
    screen.select_category("Forecast lunation")
    assert screen._category == "forecast_phase"
    assert "Full Moon" in screen.entry_spinner.values
    assert "New Moon" in screen.entry_spinner.values
    assert screen.value_input.text  # default text loaded
