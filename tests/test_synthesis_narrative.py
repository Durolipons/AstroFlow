"""Tests for the poetic whole-chart synthesis narrative composer.

These cover ``core.interpretation.natal_poetic_synthesis``,
``personal_forecast_poetic_synthesis`` and ``sun_sign_poetic_synthesis``:
deterministic prose, graceful behaviour on sparse charts, section omission,
mythic-analogy usage, all-data-family contribution, library-driven
customization, and their integration into the bundled full-report entry
points.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core import aspects as A
from core import constants as C
from core import utils
from core.forecast import (
    EclipsePeriod,
    IngressEvent,
    LunationAspect,
    LunationEvent,
    MoonState,
    SignAspect,
    SignHoroscope,
    StationEvent,
)
from core.interpretation import (
    birth_interpretation,
    chart_report,
    full_birth_report,
    full_forecast_report,
    natal_poetic_synthesis,
    personal_forecast_poetic_synthesis,
    progression_interpretation,
    sign_horoscope_text,
    solar_arc_interpretation,
    sun_sign_poetic_synthesis,
    transit_interpretation,
)
from core.interpretation_store import (
    configure_interpretation_library,
    default_interpretation_library,
    save_interpretation_library,
)
from core.models import BirthData, Chart, House, Location, PlanetPosition, SolarArcResult, TransitForecast


@pytest.fixture()
def isolated_library(tmp_path):
    path = tmp_path / "interpretations.json"
    configure_interpretation_library(str(path))
    yield path
    configure_interpretation_library(None)


def _birth_data() -> BirthData:
    return BirthData(
        name="Narrative Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1, name="London"),
        house_system="P",
    )


def _planet(
    name: str,
    longitude: float,
    house,
    speed: float = 1.0,
    retrograde: bool = False,
) -> PlanetPosition:
    ids = {value: key for key, value in C.PLANETS.items()}
    lon = longitude % 360.0
    return PlanetPosition(
        planet_id=ids.get(name, 999),
        name=name,
        longitude=lon,
        speed=-abs(speed) if retrograde else abs(speed),
        house=house,
        sign=utils.sign_of(lon),
        sign_degree=utils.degree_in_sign(lon),
        is_retrograde=retrograde,
    )


def _natural_houses():
    """House cusps aligned with the natural zodiac (house N -> sign N)."""
    return [
        House(
            number=index + 1,
            longitude=float(index * 30),
            sign=utils.sign_of(float(index * 30)),
            sign_degree=0.0,
        )
        for index in range(12)
    ]


def _rotated_houses(offset_signs: int):
    """House cusps rotated away from the natural zodiac association."""
    return [
        House(
            number=index + 1,
            longitude=float(((index + offset_signs) % 12) * 30),
            sign=utils.sign_of(float(((index + offset_signs) % 12) * 30)),
            sign_degree=0.0,
        )
        for index in range(12)
    ]


def _chart(
    positions,
    *,
    houses=None,
    chart_type: str = "Natal",
    target_title: str = "Birth Chart",
    angles=None,
) -> Chart:
    chart_angles = angles if angles is not None else {
        "Ascendant": 0.0,
        "MC": 270.0,
        "Descendant": 180.0,
        "IC": 90.0,
    }
    return Chart(
        chart_type=chart_type,
        birth_data=_birth_data(),
        target_title=target_title,
        positions=positions,
        houses=houses if houses is not None else _natural_houses(),
        angles=chart_angles,
        aspects=A.find_aspects_between(positions),
    )


def _rich_natal_chart() -> Chart:
    """A chart exercising every data family the synthesis engine scores:
    element/modality balance, all four house trinities, planet prominence
    (angular chart ruler), supportive + challenging aspects, a T-square
    pattern, several twelve-letter themes, and a retrograde planet.
    """
    return _chart(
        [
            _planet("Sun", 5, 1),       # Aries, house 1 (angular, ruler=Mars)
            _planet("Moon", 95, 4),      # Cancer, house 4 (moksha, roots)
            _planet("Mercury", 8, 1),    # sextile Sun
            _planet("Venus", 185, 7),    # Libra, house 7 (kama, partnership)
            _planet("Mars", 185, 7),     # chart ruler, square Sun, opposite Moon
            _planet("Jupiter", 65, 3),
            _planet("Saturn", 125, 5, retrograde=True),
        ]
    )


# ---------------------------------------------------------------------------
# Deterministic prose
# ---------------------------------------------------------------------------

def test_natal_poetic_synthesis_is_deterministic():
    chart = _rich_natal_chart()
    first = natal_poetic_synthesis(chart)
    second = natal_poetic_synthesis(chart)
    assert first == second
    assert len(first) > 0


def test_personal_forecast_poetic_synthesis_is_deterministic():
    natal = _rich_natal_chart()
    progressed = _chart(
        [_planet("Sun", 40, 2), _planet("Moon", 160, 6), _planet("Mars", 10, 1)],
        chart_type="Secondary Progression",
        target_title="Progressed for 2030-01-01",
    )
    solar_arc_chart = _chart(
        [_planet("Sun", 100, 4), _planet("Mars", 190, 7)],
        chart_type="Solar Arc",
        target_title="Solar Arc directed to 2030-01-01",
    )
    solar_arc = SolarArcResult(
        arc=30.0,
        chart=solar_arc_chart,
        progressed_sun=_planet("Sun", 40, 2),
        natal_sun=_planet("Sun", 5, 1),
    )
    transit_chart = _chart(
        [_planet("Jupiter", 130, 5), _planet("Saturn", 8, 1, retrograde=True)],
        chart_type="Transits",
        target_title="Transits for 2030-01-01",
    )
    transit = TransitForecast(
        birth_chart=natal,
        transit_chart=transit_chart,
        aspects=A.find_aspects_between_charts(transit_chart.positions, natal.positions),
        target_utc=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )

    first = personal_forecast_poetic_synthesis(natal, progressed, solar_arc, transit)
    second = personal_forecast_poetic_synthesis(natal, progressed, solar_arc, transit)
    assert first == second
    assert len(first) > 0


def test_sun_sign_poetic_synthesis_is_deterministic():
    first = sun_sign_poetic_synthesis("Aries")
    second = sun_sign_poetic_synthesis("Aries")
    assert first == second


# ---------------------------------------------------------------------------
# Sparse charts
# ---------------------------------------------------------------------------

def test_sparse_chart_still_produces_grounded_text_without_error():
    chart = _chart([_planet("Sun", 10, 1)], angles={})
    text = natal_poetic_synthesis(chart)
    assert text  # never crashes, never empty
    assert "Sun" in text
    # No invented Ascendant/ruler claim when the chart has no angles.
    assert "Rising in" not in text


def test_completely_empty_chart_degrades_gracefully():
    bd = _birth_data()
    chart = Chart(
        chart_type="Natal",
        birth_data=bd,
        target_title="Birth Chart",
        positions=[],
        houses=[],
        angles={},
        aspects=[],
    )
    text = natal_poetic_synthesis(chart)
    assert isinstance(text, str)
    # A closing invitation must still be produced even with zero facts.
    assert text.strip() != ""


# ---------------------------------------------------------------------------
# Section omission
# ---------------------------------------------------------------------------

def test_currents_are_omitted_without_supporting_data():
    lib = default_interpretation_library()
    # Only a Sun in house 1; house cusps rotated away from the natural
    # zodiac so "roots" (house 4 / Cancer) and "partnership" (house 7 /
    # Libra) get no cusp-alignment score, and no Moon/Venus/Mars means no
    # planet-based contribution either.
    chart = _chart(
        [_planet("Sun", 5, 1)],
        houses=_rotated_houses(4),
        angles={},
    )

    text = natal_poetic_synthesis(chart)

    identity_heading = lib.synthesis_section_headings["core_identity"]
    emotional_heading = lib.synthesis_section_headings["emotional_landscape"]
    relationship_heading = lib.synthesis_section_headings["relationships"]

    assert identity_heading in text
    assert emotional_heading not in text
    assert relationship_heading not in text


def test_forecast_story_now_is_omitted_from_natal_only_synthesis():
    lib = default_interpretation_library()
    chart = _rich_natal_chart()
    text = natal_poetic_synthesis(chart)
    forecast_heading = lib.synthesis_section_headings["forecast_bridge"]
    assert forecast_heading not in text


def test_forecast_story_now_appears_for_personal_forecast_synthesis():
    lib = default_interpretation_library()
    natal = _rich_natal_chart()
    progressed = _chart(
        [_planet("Sun", 40, 2), _planet("Mars", 10, 1)],
        chart_type="Secondary Progression",
        target_title="Progressed for 2030-01-01",
    )
    solar_arc_chart = _chart(
        [_planet("Sun", 100, 4)],
        chart_type="Solar Arc",
        target_title="Solar Arc directed to 2030-01-01",
    )
    solar_arc = SolarArcResult(
        arc=30.0,
        chart=solar_arc_chart,
        progressed_sun=_planet("Sun", 40, 2),
        natal_sun=_planet("Sun", 5, 1),
    )
    transit_chart = _chart(
        [_planet("Jupiter", 130, 5)],
        chart_type="Transits",
        target_title="Transits for 2030-01-01",
    )
    transit = TransitForecast(
        birth_chart=natal,
        transit_chart=transit_chart,
        aspects=A.find_aspects_between_charts(transit_chart.positions, natal.positions),
        target_utc=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )

    text = personal_forecast_poetic_synthesis(natal, progressed, solar_arc, transit)
    forecast_heading = lib.synthesis_section_headings["forecast_bridge"]
    assert forecast_heading in text


def test_sun_sign_synthesis_omits_story_now_without_horoscope_and_includes_it_with_one():
    lib = default_interpretation_library()
    forecast_heading = lib.synthesis_section_headings["forecast_bridge"]

    bare = sun_sign_poetic_synthesis("Taurus")
    assert forecast_heading not in bare

    horo = SignHoroscope(
        sign="Taurus",
        period="Monthly",
        window_start=datetime(2030, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2030, 1, 31, tzinfo=timezone.utc),
        planets_in_sign=[_planet("Mercury", 40, None)],
    )
    enriched = sun_sign_poetic_synthesis("Taurus", horo)
    assert forecast_heading in enriched
    assert "Mercury" in enriched


# ---------------------------------------------------------------------------
# Mythic data usage
# ---------------------------------------------------------------------------

def test_natal_synthesis_uses_accessible_non_fatalistic_mythic_analogy():
    chart = _rich_natal_chart()
    text = natal_poetic_synthesis(chart)
    # Chart ruler is Mars (Aries ascendant) -> Ares analogy expected.
    assert "Ares" in text
    assert "never a fixed fate" in text


def test_sun_sign_synthesis_uses_mythic_analogy_for_ruler():
    text = sun_sign_poetic_synthesis("Pisces")
    assert "Poseidon" in text
    assert "never a fixed fate" in text


# ---------------------------------------------------------------------------
# All data-family contribution
# ---------------------------------------------------------------------------

def test_natal_synthesis_names_dominant_facts_from_every_data_family():
    chart = _rich_natal_chart()
    text = natal_poetic_synthesis(chart)

    # Element / modality balance.
    assert "Fire" in text
    assert "Cardinal" in text
    # All four house trinities.
    assert "Dharma" in text
    assert "Moksha" in text
    assert "Kama" in text
    assert "Artha" in text
    # Planet prominence / chart ruler.
    assert "Mars" in text and "chart ruler" in text
    # Supportive + challenging aspects.
    assert "sextile" in text or "trine" in text
    assert "square" in text or "opposition" in text
    # Twelve-letter themes.
    assert "identity" in text
    assert "roots" in text
    assert "partnership" in text
    # Retrograde planets.
    assert "retrograde" in text


# ---------------------------------------------------------------------------
# Customization (editable library wording flows through)
# ---------------------------------------------------------------------------

def test_custom_library_wording_flows_into_natal_synthesis(isolated_library):
    library = default_interpretation_library()
    library.synthesis_section_headings["chart_overview"] = "CUSTOM OPENING HEADING"
    library.synthesis_conclusions["agency_close"] = "CUSTOM AGENCY CLOSING LINE"
    library.planetary_archetypal_imagery["Mars"] = "CUSTOM MARS IMAGERY"
    save_interpretation_library(library)

    chart = _rich_natal_chart()
    text = natal_poetic_synthesis(chart)

    assert "CUSTOM OPENING HEADING" in text
    assert "CUSTOM AGENCY CLOSING LINE" in text
    assert "CUSTOM MARS IMAGERY" in text


def test_custom_library_wording_flows_into_sun_sign_synthesis(isolated_library):
    library = default_interpretation_library()
    # Sentence-case, since the composer lower-cases a leading word to fit
    # mid-sentence after a colon/lead-in — matching how an astrologer would
    # actually author this text in the editor.
    library.synthesis_strengths["resilience"] = "a wholly custom strength phrase is here for testing."
    save_interpretation_library(library)

    text = sun_sign_poetic_synthesis("Aries")
    assert "wholly custom strength phrase is here for testing" in text


# ---------------------------------------------------------------------------
# Full report integration
# ---------------------------------------------------------------------------

def test_full_birth_report_prepends_synthesis_and_keeps_technical_body():
    chart = _rich_natal_chart()

    technical_body = chart_report(chart) + "\n\n" + birth_interpretation(chart)
    report = full_birth_report(chart)

    assert report.startswith(natal_poetic_synthesis(chart))
    assert report.endswith(technical_body)
    assert report.count("\nPLANETS\n") == 1


def test_sign_horoscope_text_uses_sun_sign_synthesis_once():
    horo = SignHoroscope(
        sign="Aries",
        period="Weekly",
        window_start=datetime(2030, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2030, 1, 8, tzinfo=timezone.utc),
        planets_in_sign=[_planet("Mars", 5, None)],
        sign_aspects=[SignAspect(body="Jupiter", aspect_type="Trine")],
        ingresses=[
            IngressEvent(
                body="Mercury",
                time_utc=datetime(2030, 1, 2, 12, tzinfo=timezone.utc),
                enters_sign="Aries",
                leaves_sign="Pisces",
            )
        ],
        moon_state=MoonState(
            phase="Waxing Crescent Moon",
            sign="Taurus",
            next_ingress_utc=datetime(2030, 1, 1, 18, tzinfo=timezone.utc),
            next_sign="Gemini",
        ),
    )

    synthesis = sun_sign_poetic_synthesis("Aries", horo)
    text = sign_horoscope_text(horo)

    assert "Forecast dates: 1 January 2030 to 7 January 2030 (UTC)" in text
    assert "This week" in text
    assert text.count(synthesis) == 1
    assert text.count("PLANETS IN YOUR SIGN") == 1
    assert text.count("ASPECTS TO YOUR SIGN") == 1


def test_full_forecast_report_embeds_sign_details_once_and_keeps_body():
    natal = _rich_natal_chart()
    progressed = _chart(
        [_planet("Sun", 40, 2), _planet("Mars", 10, 1)],
        chart_type="Secondary Progression",
        target_title="Progressed for 2030-01-01",
    )
    solar_arc_chart = _chart(
        [_planet("Sun", 100, 4)],
        chart_type="Solar Arc",
        target_title="Solar Arc directed to 2030-01-01",
    )
    solar_arc = SolarArcResult(
        arc=30.0,
        chart=solar_arc_chart,
        progressed_sun=_planet("Sun", 40, 2),
        natal_sun=_planet("Sun", 5, 1),
    )
    transit_chart = _chart(
        [_planet("Jupiter", 130, 5)],
        chart_type="Transits",
        target_title="Transits for 2030-01-01",
    )
    transit = TransitForecast(
        birth_chart=natal,
        transit_chart=transit_chart,
        aspects=A.find_aspects_between_charts(
            transit_chart.positions, natal.positions),
        target_utc=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    horo = SignHoroscope(
        sign="Aries",
        period="Monthly",
        window_start=datetime(2030, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2030, 1, 31, tzinfo=timezone.utc),
        planets_in_sign=[_planet("Mercury", 5, None)],
    )

    report = full_forecast_report(
        natal, progressed, solar_arc, transit, sign_horoscope=horo,
    )
    synthesis = personal_forecast_poetic_synthesis(
        natal, progressed, solar_arc, transit, horo,
    )
    sign_details = sign_horoscope_text(
        horo, include_introduction=False, transit=transit,
    )
    technical_body = "\n".join([
        chart_report(progressed),
        "",
        progression_interpretation(progressed),
        "",
        "=" * 64,
        solar_arc_interpretation(solar_arc),
        "",
        "=" * 64,
        chart_report(transit.transit_chart),
        "",
        transit_interpretation(transit),
    ])

    assert report.startswith(synthesis)
    assert report.count(sign_details) == 1
    assert report.count("PLANETS IN YOUR SIGN") == 1
    assert report.count("ASPECTS TO YOUR SIGN") == 1
    assert report.count("* PERSONAL FORECAST DETAILS *") == 1
    assert report.endswith(technical_body)
