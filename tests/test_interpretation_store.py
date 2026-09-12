"""Editable interpretation library tests."""

from datetime import datetime, timezone

import pytest

from core import constants as C
from core.chart import calculate_birth_chart
from core.interpretation import birth_interpretation
from core.interpretation_store import (
    InterpretationLibrary,
    configure_interpretation_library,
    default_interpretation_library,
    load_interpretation_library,
    save_interpretation_library,
)
from core.models import BirthData, Location


@pytest.fixture()
def isolated_library(tmp_path):
    path = tmp_path / "interpretations.json"
    configure_interpretation_library(str(path))
    yield path
    configure_interpretation_library(None)


def _chart():
    bd = BirthData(
        name="T",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )
    return calculate_birth_chart(bd)


def test_library_round_trip(isolated_library):
    library = default_interpretation_library()
    library.aspect_text["Conjunction"] = "joins the voices"
    save_interpretation_library(library)

    loaded = load_interpretation_library()
    assert loaded.aspect_text["Conjunction"] == "joins the voices"


def test_birth_interpretation_uses_custom_sign_text(isolated_library):
    library = default_interpretation_library()
    library.sign_text["Capricorn"] = "grounded ambition in your own words"
    save_interpretation_library(library)

    text = birth_interpretation(_chart())
    assert "grounded ambition in your own words" in text


def test_new_groups_have_defaults():
    """All new combination/forecast groups ship with non-empty defaults."""
    lib = default_interpretation_library()
    assert len(lib.planet_sign) == 132
    assert len(lib.planet_house) == 132
    assert len(lib.sun_moon) == 144
    assert len(lib.aspect_pair) == 495
    assert len(lib.angle_sign) == 24
    assert len(lib.planet_sign_retro) == 132
    assert len(lib.house_ruler) == 144
    assert len(lib.forecast_ingress) == 132
    assert len(lib.forecast_station) == 22
    assert len(lib.forecast_phase) == 8
    assert len(lib.sign_forecast) == 48
    assert len(lib.forecast_planet_in_sign) == 11
    assert len(lib.forecast_sign_aspect) == 44
    assert len(lib.forecast_retrograde) == 9
    for planet in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn",
                   "Uranus", "Neptune", "Pluto", "Chiron"):
        assert lib.forecast_retrograde[f"{planet} retrograde forecast"]
    assert len(set(lib.forecast_retrograde.values())) == 9
    assert len(lib.forecast_lunation_in_sign) == 48
    assert len(lib.forecast_lunation_area) == 48
    # every phase has a meaning in every sign and every area
    for phase in ("New Moon", "First Quarter Moon", "Full Moon",
                  "Last Quarter Moon"):
        for sign in C.SIGNS:
            assert lib.forecast_lunation_in_sign[f"{phase} in {sign}"]
        for area in range(1, 13):
            assert lib.forecast_lunation_area[f"{phase} in area {area}"]
    assert len(lib.forecast_period_intro) == 4
    assert len(lib.forecast_transition) == 10
    assert len(lib.forecast_invitation) == 4
    assert len(lib.forecast_quiet) == 4
    assert len(lib.synthesis_section_headings) == 8
    assert len(lib.synthesis_narrative_bridges) == 7
    assert len(lib.planetary_archetypal_imagery) == 11
    assert len(lib.synthesis_strengths) == 8
    assert len(lib.synthesis_growth_language) == 8
    assert len(lib.forecast_synthesis) == 7
    assert len(lib.synthesis_conclusions) == 5
    for key in ("Daily", "Weekly", "Monthly", "Yearly", "lunation",
                "ingress", "station", "eclipse", "sign_focus", "sky_aspect"):
        assert lib.forecast_transition[key]
    # every sign has all four periods
    for sign in C.SIGNS:
        for period in ("Daily", "Weekly", "Monthly", "Yearly"):
            assert lib.sign_forecast[f"{sign} · {period}"]
    assert lib.synthesis_section_headings["chart_overview"] == \
        "Your chart at a glance"
    assert "living conversation" in lib.synthesis_narrative_bridges[
        "forecast_to_closing"]
    assert "hearth-fire" in lib.planetary_archetypal_imagery["Sun"]
    assert "agency" in lib.synthesis_growth_language["choice_point"].lower()
    assert "weather" in lib.forecast_synthesis["current_weather"].lower()
    assert "living pattern" in lib.synthesis_conclusions[
        "affirming_close"].lower()


def test_new_groups_round_trip(isolated_library):
    """Edited values in new groups persist through save/load."""
    library = default_interpretation_library()
    library.planet_sign["Sun in Gemini"] = "custom sun-gemini text"
    library.planet_house["Moon in house 4"] = "custom moon-house-4 text"
    library.sun_moon["Sun Aries · Moon Leo"] = "custom sun-moon blend"
    library.aspect_pair["Sun trine Jupiter"] = "custom aspect pair"
    library.angle_sign["Ascendant in Libra"] = "custom angle text"
    library.planet_sign_retro["Mercury retrograde"] = "custom retro note"
    library.house_ruler["ruler of 7 in house 6"] = "custom ruler text"
    library.forecast_ingress["Sun enters Aries"] = "custom ingress text"
    library.forecast_station["Mercury stations retrograde"] = "custom station text"
    library.forecast_phase["Full Moon"] = "custom full moon text"
    library.sign_forecast["Aries · Daily"] = "custom daily forecast"
    library.forecast_planet_in_sign["Mars in your sign"] = "custom in-sign"
    library.forecast_sign_aspect["Jupiter trine your sign"] = "custom sign aspect"
    library.forecast_lunation_in_sign["New Moon in Virgo"] = "custom lunation"
    library.forecast_lunation_area["New Moon in area 3"] = "custom area"
    library.eclipse_layer["eclipse.generic.solar"] = "custom eclipse note"
    library.transit_natal["Saturn Trine natal Sun"] = "custom transit"
    library.forecast_retrograde["Mars retrograde forecast"] = "custom retro forecast"
    library.forecast_period_intro["Weekly"] = "custom weekly opening"
    library.forecast_transition["Weekly"] = "custom weekly transition"
    library.forecast_transition["sign_focus"] = "custom sign-focus transition"
    library.forecast_invitation["Weekly"] = "custom weekly invitation"
    library.forecast_quiet["Weekly"] = "custom quiet week"
    library.synthesis_section_headings["chart_overview"] = "custom heading"
    library.synthesis_narrative_bridges["growth_to_forecast"] = \
        "custom bridge"
    library.planetary_archetypal_imagery["Saturn"] = "custom saturn image"
    library.synthesis_strengths["renewal"] = "custom strength"
    library.synthesis_growth_language["timing"] = "custom growth language"
    library.forecast_synthesis["integration_note"] = "custom synthesis note"
    library.synthesis_conclusions["agency_close"] = "custom conclusion"
    library.nakshatra_text["Ashwini"] = "custom nakshatra"
    library.dasha_text["Sun Dasha"] = "custom dasha"
    library.chinese_zodiac["Horse"] = "custom animal"
    library.chinese_element["Wood"] = "custom element"
    library.yin_yang["Yang"] = "custom polarity"
    library.vedic_glossary["Nakshatra"] = "custom gloss"
    library.planet_dosha["Sun"] = "custom dosha"
    save_interpretation_library(library)

    loaded = load_interpretation_library()
    assert loaded.planet_sign["Sun in Gemini"] == "custom sun-gemini text"
    assert loaded.planet_house["Moon in house 4"] == "custom moon-house-4 text"
    assert loaded.sun_moon["Sun Aries · Moon Leo"] == "custom sun-moon blend"
    assert loaded.aspect_pair["Sun trine Jupiter"] == "custom aspect pair"
    assert loaded.angle_sign["Ascendant in Libra"] == "custom angle text"
    assert loaded.planet_sign_retro["Mercury retrograde"] == "custom retro note"
    assert loaded.house_ruler["ruler of 7 in house 6"] == "custom ruler text"
    assert loaded.forecast_ingress["Sun enters Aries"] == "custom ingress text"
    assert loaded.forecast_station["Mercury stations retrograde"] == "custom station text"
    assert loaded.forecast_phase["Full Moon"] == "custom full moon text"
    assert loaded.sign_forecast["Aries · Daily"] == "custom daily forecast"
    assert loaded.forecast_planet_in_sign["Mars in your sign"] == "custom in-sign"
    assert loaded.forecast_sign_aspect["Jupiter trine your sign"] == \
        "custom sign aspect"
    assert loaded.forecast_lunation_in_sign["New Moon in Virgo"] == \
        "custom lunation"
    assert loaded.forecast_lunation_area["New Moon in area 3"] == "custom area"
    assert loaded.eclipse_layer["eclipse.generic.solar"] == "custom eclipse note"
    assert loaded.transit_natal["Saturn Trine natal Sun"] == "custom transit"
    assert loaded.forecast_retrograde["Mars retrograde forecast"] == \
        "custom retro forecast"
    assert loaded.forecast_period_intro["Weekly"] == "custom weekly opening"
    assert loaded.forecast_transition["Weekly"] == "custom weekly transition"
    assert loaded.forecast_transition["sign_focus"] == "custom sign-focus transition"
    assert loaded.forecast_invitation["Weekly"] == "custom weekly invitation"
    assert loaded.forecast_quiet["Weekly"] == "custom quiet week"
    assert loaded.synthesis_section_headings["chart_overview"] == \
        "custom heading"
    assert loaded.synthesis_narrative_bridges["growth_to_forecast"] == \
        "custom bridge"
    assert loaded.planetary_archetypal_imagery["Saturn"] == \
        "custom saturn image"
    assert loaded.synthesis_strengths["renewal"] == "custom strength"
    assert loaded.synthesis_growth_language["timing"] == \
        "custom growth language"
    assert loaded.forecast_synthesis["integration_note"] == \
        "custom synthesis note"
    assert loaded.synthesis_conclusions["agency_close"] == \
        "custom conclusion"
    assert loaded.nakshatra_text["Ashwini"] == "custom nakshatra"
    assert loaded.dasha_text["Sun Dasha"] == "custom dasha"
    assert loaded.chinese_zodiac["Horse"] == "custom animal"
    assert loaded.chinese_element["Wood"] == "custom element"
    assert loaded.yin_yang["Yang"] == "custom polarity"
    assert loaded.vedic_glossary["Nakshatra"] == "custom gloss"
    assert loaded.planet_dosha["Sun"] == "custom dosha"


def test_to_dict_includes_new_groups():
    """Serializing the library includes all new group keys."""
    lib = default_interpretation_library()
    data = lib.to_dict()
    for key in ("planet_sign", "planet_house", "sun_moon", "aspect_pair",
                "angle_sign", "planet_sign_retro", "house_ruler",
                "forecast_ingress",
                "forecast_station", "forecast_phase", "sign_forecast",
                "forecast_planet_in_sign", "forecast_sign_aspect",
                "forecast_lunation_in_sign", "forecast_lunation_area",
                "eclipse_layer", "transit_natal", "forecast_retrograde",
                "forecast_period_intro",
                "forecast_transition", "forecast_invitation",
                "forecast_quiet", "synthesis_section_headings",
                "synthesis_narrative_bridges",
                "planetary_archetypal_imagery", "synthesis_strengths",
                "synthesis_growth_language", "forecast_synthesis",
                "synthesis_conclusions", "nakshatra_text",
                "dasha_text", "vedic_glossary", "planet_dosha",
                "chinese_zodiac", "chinese_element", "yin_yang"):
        assert key in data
        assert isinstance(data[key], dict)
        assert len(data[key]) > 0


def test_synthesis_groups_merge_with_defaults():
    """Partial JSON overrides merge with new synthesis defaults."""
    library = InterpretationLibrary.from_dict({
        "synthesis_section_headings": {
            "chart_overview": "Custom overview heading",
        },
        "synthesis_narrative_bridges": {
            "growth_to_forecast": "Custom growth bridge",
        },
        "planetary_archetypal_imagery": {
            "Moon": "Custom moon image",
        },
        "synthesis_strengths": {
            "resilience": "Custom resilience note",
        },
        "synthesis_growth_language": {
            "timing": "Custom timing language",
        },
        "forecast_synthesis": {
            "renewal": "Custom renewal forecast",
        },
        "synthesis_conclusions": {
            "next_step_close": "Custom closing line",
        },
    })

    assert library.synthesis_section_headings["chart_overview"] == \
        "Custom overview heading"
    assert library.synthesis_section_headings["closing"] == \
        "Bringing the whole story together"
    assert library.synthesis_narrative_bridges["growth_to_forecast"] == \
        "Custom growth bridge"
    assert library.synthesis_narrative_bridges["overview_to_identity"]
    assert library.planetary_archetypal_imagery["Moon"] == \
        "Custom moon image"
    assert "threshold" in library.planetary_archetypal_imagery["Chiron"]
    assert library.synthesis_strengths["resilience"] == \
        "Custom resilience note"
    assert library.synthesis_strengths["renewal"]
    assert library.synthesis_growth_language["timing"] == \
        "Custom timing language"
    assert library.synthesis_growth_language["choice_point"]
    assert library.forecast_synthesis["renewal"] == \
        "Custom renewal forecast"
    assert library.forecast_synthesis["current_weather"]
    assert library.synthesis_conclusions["next_step_close"] == \
        "Custom closing line"
    assert library.synthesis_conclusions["affirming_close"]


def test_sign_forecast_helper(isolated_library):
    """The sign_forecast lookup helper composes the key and reads the library."""
    from core import interpretation

    text = interpretation.sign_forecast("Taurus", "Monthly")
    assert text.startswith("Taurus —")
    # Weekly now ships its own hand-written default, same as the other periods
    weekly = interpretation.sign_forecast("Aries", "Weekly")
    assert weekly.startswith("Aries —") and "this week" in weekly.lower()
    # a genuinely unknown period still falls back gracefully
    fallback = interpretation.sign_forecast("Aries", "Fortnightly")
    assert "Aries" in fallback and "fortnightly" in fallback.lower()


def test_forecast_default_migration_preserves_custom_text():
    old_default = "Aries — daily: small choices shape steady growth"
    custom = "My own Taurus forecast"

    library = InterpretationLibrary.from_dict({
        "sign_forecast": {
            "Aries · Daily": old_default,
            "Taurus · Daily": custom,
        }
    })

    assert library.sign_forecast["Aries · Daily"] != old_default
    assert library.sign_forecast["Taurus · Daily"] == custom
    assert library.sign_forecast["Aries · Weekly"]


def test_sign_texts_are_reference_grounded():
    """Sign character texts carry element/modality depth (corpus-grounded)."""
    lib = default_interpretation_library()
    for sign in C.SIGNS:
        text = lib.sign_text[sign]
        assert len(text) > 40, f"{sign} text should be richer than keywords"
    # element/modality framing appears in the enriched texts
    assert "cardinal-fire" in lib.sign_text["Aries"]
    assert "fixed water" in lib.sign_text["Scorpio"]


def test_planet_roles_are_sentence_grounded():
    """Planet roles describe function, not just label keywords."""
    lib = default_interpretation_library()
    for planet in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
                   "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"):
        assert len(lib.planet_role[planet]) > 30, planet


def test_personal_planet_sign_texts_are_hand_authored():
    """Sun..Mars in-sign entries are hand-authored (no template marker)."""
    lib = default_interpretation_library()
    for planet in ("Sun", "Moon", "Mercury", "Venus", "Mars"):
        for sign in C.SIGNS:
            text = lib.planet_sign[f"{planet} in {sign}"]
            assert " expresses through " not in text, f"{planet} in {sign}"
            assert len(text) > 40, f"{planet} in {sign}"


def test_outer_planet_sign_texts_use_element_modality_frames():
    """Jupiter..Chiron lines differ per sign and carry frame material."""
    lib = default_interpretation_library()
    jupiter_texts = {lib.planet_sign[f"Jupiter in {s}"] for s in C.SIGNS}
    assert len(jupiter_texts) == 12  # every line distinct
    assert "Faith burns bright" in lib.planet_sign["Jupiter in Aries"]
    assert "wound" in lib.planet_sign["Chiron in Virgo"].lower()


def test_stale_planet_sign_entries_upgrade_to_new_defaults(isolated_library):
    """Saved pre-upgrade template entries are upgraded on lookup."""
    from core import interpretation

    library = default_interpretation_library()
    library.planet_sign["Sun in Aries"] = (
        "core identity & vitality expresses through "
        "Aries's initiative, courage, directness")
    library.planet_sign["Moon in Cancer"] = (
        "user explicitly customized this line")
    save_interpretation_library(library)
    loaded = load_interpretation_library()
    # stale template text -> upgraded to the shipped default
    assert interpretation._planet_sign_text("Sun", "Aries") == (
        interpretation._default_planet_sign_value("Sun", "Aries"))
    assert "You meet life head-on" in loaded.planet_sign["Sun in Aries"] or \
        "head-on" in interpretation._planet_sign_text("Sun", "Aries")
    # explicit customization wins
    assert interpretation._planet_sign_text("Moon", "Cancer") == (
        "user explicitly customized this line")


def test_enriched_blends_aspects_and_houses_read_distinctly():
    """Enriched sun_moon / aspect_pair / planet_house defaults vary."""
    from core.interpretation_store import (
        _default_aspect_pair_text,
        _default_planet_house_text,
        _default_sun_moon_text,
    )

    blends = _default_sun_moon_text()
    assert len(blends) == 144
    # per-sign new-moon lines are distinct from the old generic line
    assert blends["Sun Aries · Moon Aries"] != blends["Sun Leo · Moon Leo"]
    assert "double courage" in blends["Sun Aries · Moon Aries"]
    assert "Double fire" in blends["Sun Aries · Moon Leo"]
    assert "Double cardinal" in blends["Sun Aries · Moon Cancer"]
    # rotating openers keep neighbouring blends from echoing each other
    heads = {blends[f"Sun Aries · Moon {s}"][:22] for s in C.SIGNS[:4]}
    assert len(heads) > 1

    pairs = _default_aspect_pair_text()
    assert len(pairs) == 495
    assert "two personal drives" in pairs["Sun conjunction Mercury"]
    assert "generational current" in pairs["Uranus conjunction Pluto"]
    assert "larger cycle presses" in pairs["Sun conjunction Pluto"]
    assert "intensified, inseparable" in pairs["Sun conjunction Moon"]

    houses = _default_planet_house_text()
    assert len(houses) == 132
    assert "shines through" in houses["Sun in house 10"]
    assert "feels through" in houses["Moon in house 4"]
    assert "arena of standing" in houses["Sun in house 10"]
    assert len({houses[f"Sun in house {h}"] for h in range(1, 13)}) == 12


def test_previous_shipped_defaults_upgrade_on_lookup(isolated_library):
    """Libraries saved with the older shipped wording upgrade cleanly."""
    from core import interpretation
    from core.interpretation_store import (
        previous_default_aspect_pair_value,
        previous_default_planet_house_value,
        previous_default_sun_moon_value,
    )

    library = default_interpretation_library()
    library.sun_moon["Sun Aries · Moon Leo"] = (
        previous_default_sun_moon_value("Aries", "Leo"))
    library.sun_moon["Sun Taurus · Moon Virgo"] = "my own blend wording"
    library.aspect_pair["Sun trine Jupiter"] = (
        previous_default_aspect_pair_value("Sun", "Jupiter", "Trine"))
    library.aspect_pair["Moon square Mars"] = "my own aspect wording"
    library.planet_house["Sun in house 10"] = (
        previous_default_planet_house_value("Sun", 10))
    library.planet_house["Moon in house 4"] = "my own house wording"
    save_interpretation_library(library)

    # older shipped wording upgrades to the enriched defaults
    assert interpretation._sun_moon_text("Aries", "Leo") == (
        interpretation._default_sun_moon_text()["Sun Aries · Moon Leo"])
    assert "Double fire" in interpretation._sun_moon_text("Aries", "Leo")
    assert interpretation._aspect_pair_text("Sun", "Jupiter", "Trine") == (
        interpretation._default_aspect_pair_value("Sun", "Jupiter", "Trine"))
    assert "larger cycle" in interpretation._aspect_pair_text(
        "Sun", "Jupiter", "Trine")
    assert interpretation._planet_house_text("Sun", 10) == (
        interpretation._default_planet_house_value("Sun", 10))
    assert "shines through" in interpretation._planet_house_text("Sun", 10)
    # genuine customizations win over the upgrade
    assert interpretation._sun_moon_text("Taurus", "Virgo") == (
        "my own blend wording")
    assert interpretation._aspect_pair_text("Moon", "Mars", "Square") == (
        "my own aspect wording")
    assert interpretation._planet_house_text("Moon", 4) == "my own house wording"


def test_angle_and_retro_defaults_are_planet_specific():
    """Angle lines differ by angle; retro lines differ by planet."""
    from core.interpretation_store import (
        _default_angle_sign_text,
        _default_planet_sign_retro_text,
    )

    angles = _default_angle_sign_text()
    assert len(angles) == 24
    assert "meet the world" in angles["Ascendant in Aries"]
    assert "public standing" in angles["MC in Aries"]
    assert angles["Ascendant in Leo"] != angles["MC in Leo"]

    retros = _default_planet_sign_retro_text()
    assert len(retros) == 132
    assert "inner-directed mind" in retros["Mercury retrograde in Aries"]
    assert "unique values" in retros["Venus retrograde in Taurus"]
    assert "inwardly expansive faith" in retros["Jupiter retrograde in Sagittarius"]
    assert len(set(retros.values())) == 132
    assert "retrograde in Aries" in retros["Mercury retrograde in Aries"]
    assert "cannot turn retrograde" in retros["Sun retrograde in Aries"]
    assert "cannot turn retrograde" in retros["Moon retrograde in Aries"]
    assert retros["Mercury retrograde in Aries"] != retros["Mercury retrograde in Taurus"]
    assert retros["Mercury retrograde in Aries"] != retros["Venus retrograde in Aries"]
    for planet in ("Sun", "Mercury", "Venus", "Mars", "Jupiter",
                    "Saturn", "Uranus", "Neptune", "Pluto", "Chiron", "Moon"):
        for sign in C.SIGNS:
            assert f"{planet} retrograde in {sign}" in retros


def test_forecast_ingress_and_station_vary_by_planet():
    """Ingress/station defaults name the planet's own sky role."""
    from core.interpretation_store import (
        _default_forecast_ingress_text,
        _default_forecast_station_text,
    )

    ingresses = _default_forecast_ingress_text()
    assert len(ingresses) == 132
    assert "redirects the drive and the fight" in ingresses["Mars enters Aries"]
    assert "opens a wider door of possibility" in ingresses["Jupiter enters Taurus"]
    assert ingresses["Mars enters Aries"] != ingresses["Venus enters Aries"]

    stations = _default_forecast_station_text()
    assert len(stations) == 22
    assert "quieter, second draft" in stations["Mercury stations retrograde"]
    assert "revised plan back into motion" in stations["Mercury stations direct"]
    assert "banks the fire" in stations["Mars stations retrograde"]


def test_older_angle_and_house_defaults_upgrade(isolated_library):
    """Pre-enrichment angle/house shipped wording upgrades on lookup."""
    from core import interpretation

    library = default_interpretation_library()
    library.angle_sign["Ascendant in Aries"] = (
        "Ascendant in Aries: you present yourself to the world "
        "with Aries's bold initiative")
    library.angle_sign["MC in Leo"] = "my own MC wording"
    save_interpretation_library(library)

    assert "meet the world" in interpretation._angle_sign_text(
        "Ascendant", "Aries")
    assert interpretation._angle_sign_text("MC", "Leo") == "my own MC wording"


def test_house_ruler_group_has_defaults_and_round_trips(isolated_library):
    """house_ruler ships 144 entries and persists edits."""
    lib = default_interpretation_library()
    assert len(lib.house_ruler) == 144
    assert "steering" in lib.house_ruler["ruler of 7 in house 6"]
    assert "stays home" in lib.house_ruler["ruler of 1 in house 1"]
    assert "co-ruler" in lib.house_ruler["ruler of 8 in house 12"]
    assert "Ruler of house 7 (Venus)" in lib.house_ruler["ruler of 7 in house 6"]

    library = default_interpretation_library()
    library.house_ruler["ruler of 7 in house 6"] = "custom ruler wording"
    save_interpretation_library(library)
    assert load_interpretation_library().house_ruler[
        "ruler of 7 in house 6"] == "custom ruler wording"


def test_house_rulers_resolve_per_chart(isolated_library):
    """house_rulers() resolves each cusp's ruler and placement."""
    from core import interpretation

    text = interpretation.birth_interpretation(_chart())
    assert "HOUSE RULERS" in text
    assert text.count("Ruler of house") == 12
    # cusp ruler + placed house both named, e.g. Mars ruling house 1
    assert "Ruler of house 1 (Mars) in house" in text

    # user-edited generic template keeps working with {ruler} placeholder
    library = default_interpretation_library()
    library.house_ruler["ruler of 1 in house 12"] = (
        "custom: {ruler} carries house 1 into house 12")
    save_interpretation_library(library)
    line = interpretation._house_ruler_text(1, "Mars", 12)
    assert line == "custom: Mars carries house 1 into house 12"



def test_transit_natal_defaults_cover_every_pair_and_aspect():
    """11 transiting x 11 natal x 9 aspects = 1089 distinct reference notes."""
    lib = default_interpretation_library()
    keys = list(lib.transit_natal)
    assert len(keys) == 11 * 11 * 9
    assert len(set(lib.transit_natal.values())) == len(keys)
    sample = lib.transit_natal["Saturn Trine natal Sun"]
    assert "natal Sun" in sample
    other = lib.transit_natal["Pluto Opposition natal Moon"]
    assert "natal Moon" in other
    assert sample != other


def test_transit_interpretation_uses_transit_natal_notes(isolated_library):
    """The forecast report pulls wording from the transit_natal group."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from core.interpretation import transit_interpretation

    forecast = SimpleNamespace(
        target_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        aspects=[SimpleNamespace(
            planet1_name="Saturn (transit)", planet2_name="Sun",
            type_name="Trine", orb=0.5, kind="applying",
        )],
    )
    text = transit_interpretation(forecast)
    expected = default_interpretation_library().transit_natal[
        "Saturn Trine natal Sun"]
    assert expected in text


def test_transit_interpretation_shows_retrograde(isolated_library):
    """A retrograde transit line carries a (retrograde) tag and a qualifier."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from core.interpretation import transit_interpretation

    forecast = SimpleNamespace(
        target_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        aspects=[SimpleNamespace(
            planet1_name="Mercury (transit)", planet2_name="Sun",
            type_name="Square", orb=1.2, kind="applying",
        )],
        transit_chart=SimpleNamespace(positions=[
            SimpleNamespace(name="Mercury", longitude=10.5,
                            sign="Aries", is_retrograde=True),
        ]),
    )
    text = transit_interpretation(forecast)
    assert "Mercury (transit) Square Sun" in text
    assert "(retrograde)" in text


def test_transit_planet_detail_lists_natal_contacts(isolated_library):
    """Transit planet tap text: sky position + natal contacts + notes."""
    from types import SimpleNamespace

    from core.interpretation import transit_planet_detail

    chart = SimpleNamespace(positions=[SimpleNamespace(
        name="Saturn", longitude=300.5, sign="Aquarius", motion="direct")],
        aspects=[])
    asp = SimpleNamespace(
        planet1_name="Saturn (transit)", planet2_name="Sun",
        type_name="Trine", orb=0.5, kind="applying")
    text = transit_planet_detail(chart, "Saturn", natal_aspects=[asp])
    assert "SATURN" in text
    assert "Aquarius" in text
    assert "Saturn (transit) Trine Sun" in text
    note = default_interpretation_library().transit_natal[
        "Saturn Trine natal Sun"]
    assert note in text


def test_transit_aspect_detail_uses_library(isolated_library):
    """Transit aspect-line tap text carries the library note + geometry."""
    from types import SimpleNamespace

    from core.interpretation import transit_aspect_detail

    asp = SimpleNamespace(
        planet1_name="Saturn (transit)", planet2_name="Sun",
        type_name="Trine", angle=120.0, orb=0.5, kind="applying")
    text = transit_aspect_detail(asp)
    assert "Saturn (transit) Trine Sun" in text
    assert "orb 0.50" in text
    note = default_interpretation_library().transit_natal[
        "Saturn Trine natal Sun"]
    assert note in text


def test_vedic_chinese_group_defaults_present():
    """Vedic + Chinese library groups exist with complete key sets."""
    from core import constants as C

    lib = default_interpretation_library()
    assert len(lib.nakshatra_text) == 27
    assert set(lib.nakshatra_text) == set(C.NAKSHATRA_NAMES)
    assert set(lib.dasha_text) == {
        f"{p} Dasha" for p in C.VIMSHOTTARI_DASHA_YEARS}
    assert set(lib.chinese_zodiac) == set(C.CHINESE_ZODIAC_COMPATIBILITY)
    assert set(lib.chinese_element) == {"Wood", "Fire", "Earth",
                                        "Metal", "Water"}


def test_natal_retrograde_summary(isolated_library):
    """birth_interpretation shows a RETROGRADE SUMMARY section."""
    from types import SimpleNamespace

    from core.interpretation import birth_interpretation

    chart = SimpleNamespace(
        positions=[
            SimpleNamespace(name="Sun", longitude=30.0, sign="Aries",
                            speed=1.0, motion="direct", house=None),
            SimpleNamespace(name="Mercury", longitude=20.0, sign="Aries",
                            speed=-0.5, motion="retrograde", house=1),
            SimpleNamespace(name="Venus", longitude=150.0, sign="Virgo",
                            speed=-0.3, motion="retrograde", house=6),
            SimpleNamespace(name="Mars", longitude=200.0, sign="Libra",
                            speed=0.8, motion="direct", house=7),
        ],
        houses=[],
        angles={"Ascendant": 45.0, "MC": 180.0},
        aspects=[],
        notes=[],
    )
    text = birth_interpretation(chart)
    assert "RETROGRADE SUMMARY" in text
    assert "2 retrograde planet(s)" in text


def test_natal_retrograde_summary_no_retrogrades(isolated_library):
    """A chart with no retrogrades states it plainly."""
    from types import SimpleNamespace

    from core.interpretation import birth_interpretation

    chart = SimpleNamespace(
        positions=[
            SimpleNamespace(name="Sun", longitude=30.0, sign="Aries",
                            speed=1.0, motion="direct", house=None),
            SimpleNamespace(name="Mercury", longitude=20.0, sign="Aries",
                            speed=1.5, motion="direct", house=1),
        ],
        houses=[],
        angles={"Ascendant": 45.0, "MC": 180.0},
        aspects=[],
        notes=[],
    )
    text = birth_interpretation(chart)
    assert "RETROGRADE SUMMARY" in text
    assert "No natal planets are retrograde" in text


def test_natal_retrograde_summary_four_or_more(isolated_library):
    """4+ retrogrades flags the alienated/independent pattern (Tracy Marks)."""
    from types import SimpleNamespace

    from core.interpretation import birth_interpretation

    chart = SimpleNamespace(
        positions=[
            SimpleNamespace(name=n, longitude=10.0 + i*10, sign="Aries",
                            speed=-0.2, motion="retrograde", house=i+1)
            for i, n in enumerate(["Mercury", "Venus", "Mars", "Jupiter"])],
        houses=[],
        angles={"Ascendant": 45.0, "MC": 180.0},
        aspects=[],
        notes=[],
    )
    text = birth_interpretation(chart)
    assert "RETROGRADE SUMMARY" in text
    assert "alienated" in text


def test_vedic_chinese_group_defaults_present():
    """Vedic + Chinese library groups exist with complete key sets."""
    from core import constants as C

    lib = default_interpretation_library()
    assert len(lib.nakshatra_text) == 27
    assert set(lib.nakshatra_text) == set(C.NAKSHATRA_NAMES)
    assert set(lib.dasha_text) == {
        f"{p} Dasha" for p in C.VIMSHOTTARI_DASHA_YEARS}
    assert set(lib.chinese_zodiac) == set(C.CHINESE_ZODIAC_COMPATIBILITY)
    assert set(lib.chinese_element) == {"Wood", "Fire", "Earth",
                                        "Metal", "Water"}
    assert set(lib.yin_yang) == {"Yin", "Yang"}
    assert all(isinstance(v, str) and v for v in lib.nakshatra_text.values())


def test_vedic_glossary_and_dosha_defaults():
    """Plain-English glossary + Ayurvedic dosha groups are complete."""
    lib = default_interpretation_library()
    core_terms = {"Jyotish", "Ayanamsa", "Sidereal", "Nakshatra", "Pada",
                  "Rashi", "Graha", "Drishti", "Vimshottari Dasha",
                  "Dasha", "Mahadasha", "Antardasha", "Rahu", "Ketu",
                  "Lagna", "Gochara", "Benefic", "Malefic", "Guru",
                  "Dharma", "Karma", "Ayurveda", "Dosha", "Vata",
                  "Pitta", "Kapha"}
    assert core_terms <= set(lib.vedic_glossary)
    assert "Pitris" in lib.vedic_glossary   # nakshatra deity glosses too
    assert set(lib.planet_dosha) == set(C.VIMSHOTTARI_DASHA_YEARS)
    assert lib.planet_dosha["Sun"].startswith("Pitta")
    assert lib.planet_dosha["Saturn"].startswith("Vata")
