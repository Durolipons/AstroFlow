from datetime import datetime, timedelta, timezone

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
from core.models import BirthData, Chart, House, Location, PlanetPosition, SolarArcResult, TransitForecast
from core.synthesis import analyze_chart, analyze_forecast


def _birth_data() -> BirthData:
    return BirthData(
        name="Synthesis Native",
        birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1, name="London"),
        house_system="P",
    )


def _planet(
    name: str,
    longitude: float,
    house: int | None,
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


def _houses() -> list[House]:
    return [
        House(
            number=index + 1,
            longitude=float(index * 30),
            sign=utils.sign_of(float(index * 30)),
            sign_degree=0.0,
        )
        for index in range(12)
    ]


def _chart(
    positions: list[PlanetPosition],
    *,
    chart_type: str = "Natal",
    target_title: str = "Birth Chart",
    angles: dict[str, float] | None = None,
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
        houses=_houses(),
        angles=chart_angles,
        aspects=A.find_aspects_between(positions),
    )


def test_weighted_balances_are_deterministic_and_tie_stable():
    chart = _chart(
        [
            _planet("Sun", 5, 1),
            _planet("Moon", 185, 7),
            _planet("Mercury", 15, 1),
            _planet("Venus", 195, 7),
        ],
        angles={
            "Ascendant": 240.0,
            "MC": 300.0,
            "Descendant": 60.0,
            "IC": 120.0,
        },
    )

    first = analyze_chart(chart)
    second = analyze_chart(chart)

    assert [item.label for item in first.element_balance] == [
        "Air", "Fire", "Earth", "Water",
    ]
    assert [item.label for item in first.element_balance] == [
        item.label for item in second.element_balance
    ]
    assert first.element_balance[0].rank == 1
    assert first.element_balance[1].rank == 1
    assert first.element_balance[0].tied is True
    assert first.element_balance[1].tied is True
    assert first.element_balance[0].score == 4.0
    assert first.element_balance[1].score == 4.0
    assert "Ascendant in Sagittarius" in first.element_balance[1].contributors
    assert "MC in Aquarius" in first.element_balance[0].contributors


def test_sparse_chart_keeps_missing_buckets_and_no_patterns():
    chart = _chart([_planet("Sun", 10, 1)], angles={})

    synthesis = analyze_chart(chart)

    assert synthesis.chart_ruler == ""
    assert synthesis.element_balance[0].label == "Fire"
    assert synthesis.element_balance[0].score == 2.0
    assert any(item.label == "Earth" and item.missing for item in synthesis.element_balance)
    assert synthesis.supportive_aspects == []
    assert synthesis.challenging_aspects == []
    assert synthesis.aspect_patterns == []


def test_planet_prominence_uses_angularity_chart_ruler_and_angle_contacts():
    chart = _chart(
        [
            _planet("Mars", 274, 10),
            _planet("Sun", 42, 2),
            _planet("Moon", 97, 4),
            _planet("Mercury", 75, 3),
        ],
        angles={
            "Ascendant": 0.0,
            "MC": 275.0,
            "Descendant": 180.0,
            "IC": 95.0,
        },
    )

    synthesis = analyze_chart(chart)
    top = synthesis.planet_prominence[0]

    assert top.planet == "Mars"
    assert top.angular_house is True
    assert top.is_chart_ruler is True
    assert "MC" in top.angle_contacts


def test_retrogrades_and_supportive_challenging_aspects_are_ranked():
    chart = _chart(
        [
            _planet("Mercury", 10, 1, speed=0.8, retrograde=True),
            _planet("Jupiter", 130, 5),
            _planet("Mars", 100, 4),
            _planet("Venus", 190, 7),
        ]
    )

    synthesis = analyze_chart(chart)

    assert synthesis.retrograde_planets == ("Mercury",)
    assert any(
        aspect.type_name == "Trine"
        and {aspect.planet1, aspect.planet2} == {"Mercury", "Jupiter"}
        for aspect in synthesis.supportive_aspects
    )
    assert synthesis.challenging_aspects[0].type_name in {"Square", "Opposition"}
    assert any(
        aspect.type_name == "Square"
        and {aspect.planet1, aspect.planet2} == {"Mars", "Venus"}
        for aspect in synthesis.challenging_aspects
    )
    assert any(
        aspect.type_name == "Opposition"
        and {aspect.planet1, aspect.planet2} == {"Mercury", "Venus"}
        for aspect in synthesis.challenging_aspects
    )


def test_repeated_twelve_letter_theme_is_ranked_from_sign_house_angle_and_ruler():
    chart = _chart(
        [
            _planet("Sun", 10, 1),
            _planet("Mars", 15, 1, retrograde=True),
            _planet("Mercury", 70, 3),
        ],
        angles={
            "Ascendant": 0.0,
            "MC": 270.0,
            "Descendant": 180.0,
            "IC": 90.0,
        },
    )

    synthesis = analyze_chart(chart)
    top = synthesis.twelve_letter_themes[0]

    assert top.index == 1
    assert top.label == "identity"
    assert "Sun in Aries" in top.contributors
    assert "Mars in house 1" in top.contributors
    assert "Ascendant in Aries" in top.contributors
    assert "Chart ruler is Mars" in top.contributors
    assert any("Mars" in item for item in top.retrograde_contributors)


def test_stellium_grand_trine_and_t_square_are_detected_conservatively():
    chart = _chart(
        [
            _planet("Sun", 10, 1),
            _planet("Mercury", 14, 1),
            _planet("Venus", 18, 1),
            _planet("Moon", 130, 5),
            _planet("Jupiter", 250, 9),
            _planet("Mars", 100, 4),
            _planet("Saturn", 190, 7),
            _planet("Pluto", 280, 10),
        ]
    )

    synthesis = analyze_chart(chart)
    patterns = synthesis.aspect_patterns

    assert any(
        pattern.pattern_type == "stellium"
        and pattern.scope == "sign"
        and pattern.sign == "Aries"
        and pattern.planets == ("Mercury", "Sun", "Venus")
        for pattern in patterns
    )
    assert any(
        pattern.pattern_type == "stellium"
        and pattern.scope == "house"
        and pattern.house == 1
        for pattern in patterns
    )
    assert any(
        pattern.pattern_type == "grand_trine"
        and {"Sun", "Moon", "Jupiter"} == set(pattern.planets)
        for pattern in patterns
    )
    assert any(
        pattern.pattern_type == "t_square"
        and pattern.focal_planet == "Saturn"
        and {"Mars", "Saturn", "Pluto"} == set(pattern.planets)
        for pattern in patterns
    )


def test_house_trinity_balance_uses_house_groups():
    chart = _chart(
        [
            _planet("Sun", 10, 1),
            _planet("Moon", 130, 5),
            _planet("Jupiter", 250, 9),
            _planet("Mercury", 50, 2),
        ]
    )

    synthesis = analyze_chart(chart)
    top = synthesis.house_trinity_balance[0]

    assert top.label == "Dharma"
    assert top.houses == (1, 5, 9)
    assert top.score == 5.0


def test_forecast_synthesis_covers_progressions_solar_arcs_transits_and_period_sky():
    natal = _chart(
        [
            _planet("Sun", 10, 1),
            _planet("Moon", 100, 4),
            _planet("Mars", 280, 10),
            _planet("Mercury", 70, 3),
            _planet("Venus", 190, 7),
        ]
    )
    progressed = _chart(
        [
            _planet("Sun", 130, 5),
            _planet("Moon", 160, 6),
            _planet("Mars", 10, 1),
            _planet("Mercury", 250, 9),
        ],
        chart_type="Secondary Progression",
        target_title="Progressed for 2030-01-01",
    )
    solar_arc_chart = _chart(
        [
            _planet("Sun", 100, 4),
            _planet("Mars", 190, 7),
            _planet("Venus", 310, 11),
            _planet("Mercury", 10, 1),
        ],
        chart_type="Solar Arc",
        target_title="Solar Arc directed to 2030-01-01",
    )
    solar_arc = SolarArcResult(
        arc=30.0,
        chart=solar_arc_chart,
        progressed_sun=_planet("Sun", 40, 2),
        natal_sun=_planet("Sun", 10, 1),
    )
    transit_chart = _chart(
        [
            _planet("Mercury", 10, 1, retrograde=True),
            _planet("Jupiter", 130, 5),
            _planet("Saturn", 100, 4),
        ],
        chart_type="Transits",
        target_title="Transits for 2030-01-01",
    )
    transit = TransitForecast(
        birth_chart=natal,
        transit_chart=transit_chart,
        aspects=A.find_aspects_between_charts(
            transit_chart.positions,
            natal.positions,
        ),
        target_utc=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    sign_horoscope = SignHoroscope(
        sign="Aries",
        period="Monthly",
        window_start=datetime(2030, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2030, 1, 31, tzinfo=timezone.utc),
        planets_in_sign=[_planet("Mercury", 10, 1, retrograde=True)],
        sign_aspects=[SignAspect(body="Jupiter", aspect_type="Trine")],
        ingresses=[
            IngressEvent(
                body="Venus",
                time_utc=datetime(2030, 1, 5, tzinfo=timezone.utc),
                enters_sign="Aries",
                leaves_sign="Pisces",
                entering=True,
            )
        ],
        stations=[
            StationEvent(
                body="Mercury",
                time_utc=datetime(2030, 1, 3, tzinfo=timezone.utc),
                going_retrograde=True,
            )
        ],
        lunations=[
            LunationEvent(
                phase="Full Moon",
                time_utc=datetime(2030, 1, 10, tzinfo=timezone.utc),
                sign="Libra",
                aspects=[LunationAspect(body="Mars", type_name="Opposition", orb=0.5)],
            )
        ],
        moon_state=MoonState(
            phase="Waxing Crescent Moon",
            sign="Aries",
            next_ingress_utc=datetime(2030, 1, 2, tzinfo=timezone.utc),
            next_sign="Taurus",
        ),
        lunation_areas={0: 7},
        eclipses=[
            EclipsePeriod(
                kind="Lunar Eclipse (Full Moon)",
                start_utc=datetime(2030, 1, 9, tzinfo=timezone.utc),
                peak_utc=datetime(2030, 1, 10, tzinfo=timezone.utc),
                end_utc=datetime(2030, 1, 10, tzinfo=timezone.utc) + timedelta(hours=6),
                intensity="deep",
            )
        ],
    )

    synthesis = analyze_forecast(
        natal,
        progressed,
        solar_arc,
        transit,
        sign_horoscope,
    )

    assert synthesis.progression_themes
    assert synthesis.solar_arc_themes
    assert synthesis.transit_themes
    assert synthesis.period_sky_themes
    assert any(theme.type_name == "Placement" for theme in synthesis.progression_themes)
    assert any(theme.type_name == "Opposition" for theme in synthesis.solar_arc_themes)
    assert any(theme.retrograde for theme in synthesis.transit_themes)
    assert any(theme.type_name == "Eclipse" for theme in synthesis.period_sky_themes)
    assert any(
        theme.peak_utc == datetime(2030, 1, 1, tzinfo=timezone.utc)
        for theme in synthesis.progression_themes
        if theme.type_name == "Placement"
    )
    assert {theme.source for theme in synthesis.highlights} >= {
        "progression", "solar_arc", "transit", "period_sky",
    }
