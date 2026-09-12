"""Tests for the ephemeris-driven astro-clock forecast engine (core.forecast).

These validate the scan/bisection machinery against the real ephemeris:

  * period windows and labels (Daily / Weekly / Monthly),
  * ingress timing (Sun entering Aries ~20 Mar),
  * station detection over a wide window,
  * aspect orb enter / exact / leave consistency,
  * the whole-sign sun-sign mapping,
  * the composed sun-sign horoscope text.
"""

from datetime import datetime, timedelta, timezone

from core import constants as C
from core import forecast as F
from core import interpretation
from core.ephemeris import get_ephemeris
from core.models import PlanetPosition

_EPH = get_ephemeris()

_MAR1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
_JUN1 = datetime(2026, 6, 1, tzinfo=timezone.utc)
_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _sun_at(dt_utc):
    return _EPH.planet_position(
        _EPH.julian_day_ut(dt_utc), C.SUN).sign


def _pos(sign: str, name: str, lon: float = 0.0) -> PlanetPosition:
    return PlanetPosition(
        planet_id=0, name=name, longitude=lon, speed=0.5,
        sign=sign, sign_degree=10.0, is_retrograde=False)


def _planets_id(name: str) -> int:
    return {v: k for k, v in C.PLANETS.items()}[name]


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------
def test_period_windows_have_expected_bounds_and_labels():
    daily = F.daily_forecast(_MAR1)
    assert daily.days == 1
    assert daily.label == "Daily"
    assert (daily.end_utc - daily.start_utc).days == 1

    weekly = F.weekly_forecast(_MAR1)
    assert weekly.label == "Weekly"
    assert (weekly.end_utc - weekly.start_utc).days == 7

    monthly = F.monthly_forecast(_MAR1)
    assert monthly.label == "Monthly"
    assert (monthly.end_utc - monthly.start_utc).days == 30


def test_calendar_forecast_uses_day_week_month_and_year_boundaries(monkeypatch):
    captured = []

    def fake_period(start, end, ep=None, orbs=None, label=None):
        captured.append((start, end, label))
        return F.ForecastPeriod(label, start, end)

    monkeypatch.setattr(F, "forecast_period", fake_period)
    leap_day = datetime(2024, 2, 29, 18, 30, tzinfo=timezone.utc)

    F.calendar_forecast("Day", leap_day)
    F.calendar_forecast("Week", leap_day)
    F.calendar_forecast("Month", leap_day)
    F.calendar_forecast("Year", leap_day)

    assert captured[0] == (
        datetime(2024, 2, 29, tzinfo=timezone.utc),
        datetime(2024, 3, 1, tzinfo=timezone.utc),
        "Daily",
    )
    assert captured[1] == (
        datetime(2024, 2, 29, tzinfo=timezone.utc),
        datetime(2024, 3, 7, tzinfo=timezone.utc),
        "Weekly",
    )
    assert captured[2] == (
        datetime(2024, 2, 29, tzinfo=timezone.utc),
        datetime(2024, 3, 29, tzinfo=timezone.utc),
        "Monthly",
    )
    assert captured[3] == (
        datetime(2024, 2, 29, tzinfo=timezone.utc),
        datetime(2025, 2, 28, tzinfo=timezone.utc),
        "Yearly",
    )


def test_all_event_lists_are_time_sorted():
    period = F.monthly_forecast(_MAR1)
    for events in (period.ingresses, period.stations, period.lunations):
        times = [e.time_utc for e in events]
        assert times == sorted(times)
    orb_ins = [e.orb_in_time_utc for e in period.aspects]
    assert orb_ins == sorted(orb_ins)


def test_monthly_window_finds_events():
    period = F.monthly_forecast(_MAR1)
    # Moon crosses at least one sign boundary every month; there is always a
    # full or new Moon each month; major pairs aspect inside a month.
    assert any(e.body == "Moon" for e in period.ingresses)
    assert len(period.lunations) >= 1
    assert len(period.aspects) >= 10


# ---------------------------------------------------------------------------
# Ingress detection
# ---------------------------------------------------------------------------
def test_sun_aries_ingress_is_precise():
    period = F.monthly_forecast(datetime(2026, 3, 1, tzinfo=timezone.utc))
    event = next((e for e in period.ingresses
                  if e.body == "Sun" and e.enters_sign == "Aries"), None)
    assert event is not None
    # A minute to each side lands in the sign that flanked the boundary.
    assert _sun_at(event.time_utc - timedelta(minutes=1)) == "Pisces"
    assert _sun_at(event.time_utc + timedelta(minutes=1)) == "Aries"


def test_ingress_times_lie_inside_window():
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 3, 31, tzinfo=timezone.utc)
    for ev in F.monthly_forecast(start).ingresses:
        assert start <= ev.time_utc <= end


# ---------------------------------------------------------------------------
# Station detection
# ---------------------------------------------------------------------------
_WINDOW_START = _2024
_WINDOW_END = _2024.replace(month=10)  # 9 months, step 12h -> cheap but solid


def _year_stations():
    return F.scan_stations(_WINDOW_START, _WINDOW_END, step_hours=12)


def test_stations_detected_over_window():
    assert len(_year_stations()) >= 5  # several Mercury/outer-planet stations


def test_station_time_is_at_speed_sign_flip():
    events = _year_stations()
    assert events
    ev = events[0]
    jd = _EPH.julian_day_ut(ev.time_utc)
    pid = _planets_id(ev.body)
    before = _EPH.planet_position(jd - 1.0, pid).speed
    after = _EPH.planet_position(jd + 1.0, pid).speed
    assert before * after < 0.0
# ---------------------------------------------------------------------------
# Aspect scanning (orb enter / exact / leave)
# ---------------------------------------------------------------------------
def test_aspect_orb_times_are_consistent():
    period = F.monthly_forecast(_JUN1)
    assert period.aspects, "expected aspects in June 2026"
    for asp in period.aspects:
        assert asp.orb_in_time_utc <= asp.orb_out_time_utc
        if asp.exact_time_utc is None:
            continue
        assert asp.orb_in_time_utc <= asp.exact_time_utc <= asp.orb_out_time_utc
        jd = _EPH.julian_day_ut(asp.exact_time_utc)
        dev = F._sep_dev(jd, _EPH, _planets_id(asp.body1),
                         _planets_id(asp.body2), asp.angle)
        assert abs(dev) < 0.05, (asp.body1, asp.type_name, asp.body2, dev)


def test_aspect_entered_inside_window_when_not_at_start():
    """An aspect that is freshly entered (not in orb at window start) must
    carry an orb_in time strictly inside the window."""
    period = F.monthly_forecast(_JUN1)
    entered = [a for a in period.aspects
               if a.orb_in_time_utc > period.start_utc]
    assert entered, "expected at least one aspect to enter its orb mid-month"
    for asp in entered:
        assert period.start_utc < asp.orb_in_time_utc < period.end_utc


# ---------------------------------------------------------------------------
# Whole-sign mapping
# ---------------------------------------------------------------------------
def test_sign_aspects_for_uses_whole_sign():
    positions = {
        "Mars": _pos("Taurus", "Mars"),     # 1 ahead -> no major aspect
        "Jupiter": _pos("Cancer", "Jupiter"),  # 3 ahead -> square
        "Saturn": _pos("Leo", "Saturn"),    # 4 ahead -> trine
        "Venus": _pos("Aries", "Venus"),    # same sign -> in sign
        "Pluto": _pos("Libra", "Pluto"),    # 6 ahead -> opposition
        "Mercury": _pos("Gemini", "Mercury"),  # 2 ahead -> sextile
        "Uranus": _pos("Aquarius", "Uranus"),  # 10 ahead -> sextile
    }
    in_sign, aspects = F.sign_aspects_for("Aries", positions)
    assert [p.name for p in in_sign] == ["Venus"]
    kinds = {a.body: a.aspect_type for a in aspects}
    assert kinds["Jupiter"] == "Square"
    assert kinds["Saturn"] == "Trine"
    assert kinds["Pluto"] == "Opposition"
    assert kinds["Mercury"] == "Sextile"
    assert kinds["Uranus"] == "Sextile"
    assert "Mars" not in kinds


def test_sun_sign_horoscope_filters_ingresses():
    period = F.monthly_forecast(_MAR1)
    horo = F.sun_sign_horoscope(period, "Aries")
    for ev in horo.ingresses:
        assert ev.enters_sign == "Aries" or ev.leaves_sign == "Aries"


def test_sign_horoscope_text_composes_from_engine():
    period = F.monthly_forecast(_MAR1)
    horo = F.sun_sign_horoscope(period, "Aries")
    text = interpretation.sign_horoscope_text(horo)
    assert "ARIES" in text
    assert "MONTHLY" in text
    assert "ASTRO-CLOCK" in text
    assert "not tied to any birth chart" in text
    assert "PLANETS IN YOUR SIGN" in text
    assert "SKY ASPECTS" in text


def test_forecast_introductions_name_period_and_inclusive_dates():
    starts = datetime(2026, 3, 5, tzinfo=timezone.utc)
    expected = {
        "Daily": ("Today", starts + timedelta(days=1), "5 March 2026"),
        "Weekly": (
            "This week",
            starts + timedelta(days=7),
            "5 March 2026 to 11 March 2026",
        ),
        "Monthly": (
            "This month",
            datetime(2026, 4, 5, tzinfo=timezone.utc),
            "5 March 2026 to 4 April 2026",
        ),
        "Yearly": (
            "Over the next year",
            datetime(2027, 3, 5, tzinfo=timezone.utc),
            "5 March 2026 to 4 March 2027",
        ),
    }

    for period, (opening, end, date_range) in expected.items():
        horoscope = F.SignHoroscope("Aries", period, starts, end)
        text = interpretation.sign_horoscope_text(horoscope)
        assert opening in text
        assert f"Forecast dates: {date_range} (UTC)" in text


def test_quiet_forecast_introduction_remains_encouraging():
    start = datetime(2026, 3, 5, tzinfo=timezone.utc)
    horoscope = F.SignHoroscope(
        "Taurus", "Weekly", start, start + timedelta(days=7)
    )

    introduction = interpretation.forecast_introduction_text(horoscope)

    assert introduction
    assert "No major" not in introduction
    assert "quiet" in introduction.lower() or "space" in introduction.lower()


# ---------------------------------------------------------------------------
# Moon cycles: phase, sign, lunation meaning
# ---------------------------------------------------------------------------
def test_moon_state_reports_phase_sign_and_next_ingress():
    state = F.moon_state(dt_utc=datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert state is not None
    assert state.phase in ("New Moon", "Waxing Crescent Moon",
                           "First Quarter Moon", "Waxing Gibbous Moon",
                           "Full Moon", "Waning Gibbous Moon",
                           "Last Quarter Moon", "Waning Crescent Moon")
    assert state.sign in C.SIGNS
    assert state.next_sign in C.SIGNS
    assert state.next_ingress_utc is not None


def test_lunations_carry_their_sign():
    # The Virgo New Moon of 2026-09-11 (the Sun is in Virgo then).
    period = F.weekly_forecast(datetime(2026, 9, 10, tzinfo=timezone.utc))
    new_moon = next(lu for lu in period.lunations if lu.phase == "New Moon")
    assert new_moon.sign == "Virgo"
    # The Sun is at the Moon's longitude at a New Moon, so the lunation
    # sign must match the Sun's sign at that exact moment.
    jd = _EPH.julian_day_ut(new_moon.time_utc)
    assert _EPH.planet_position(jd, C.SUN).sign == new_moon.sign


def test_lunation_aspects_are_recorded_and_sorted():
    period = F.monthly_forecast(datetime(2026, 9, 1, tzinfo=timezone.utc))
    with_aspects = [lu for lu in period.lunations if lu.aspects]
    assert with_aspects, "expected at least one lunation aspecting a planet"
    for lu in with_aspects:
        orbs = [a.orb for a in lu.aspects]
        assert orbs == sorted(orbs)
        for a in lu.aspects:
            assert a.body in (*C.PLANETS.values(), "Chiron")
            assert a.type_name in {d.name for d in C.MAJOR_ASPECTS}


def test_lunation_area_offset_maps_whole_sign_areas():
    # A New Moon in Virgo: for Virgo readers it is area 1, for Taurus area 5.
    assert F.lunation_area_offset("Virgo", "Virgo") == 1
    assert F.lunation_area_offset("Virgo", "Taurus") == 5
    assert F.lunation_area_offset("Pisces", "Aries") == 12


def test_sun_sign_horoscope_includes_moon_state_and_areas():
    period = F.weekly_forecast(datetime(2026, 9, 10, tzinfo=timezone.utc))
    horo = F.sun_sign_horoscope(period, "Virgo")
    assert horo.moon_state is not None
    assert horo.moon_ingresses, "Moon must change signs within a week"
    for ev in horo.moon_ingresses:
        assert ev.body == "Moon"
    for idx, lu in enumerate(period.lunations):
        if lu.sign:
            assert horo.lunation_areas[idx] == F.lunation_area_offset(
                lu.sign, "Virgo")


def test_horoscope_text_leads_with_the_moon():
    period = F.weekly_forecast(datetime(2026, 9, 10, tzinfo=timezone.utc))
    text = interpretation.sign_horoscope_text(
        F.sun_sign_horoscope(period, "Virgo"))
    assert "MOON NOW" in text
    assert "The Moon is" in text
    assert "THIS LUNATION" in text
    assert "New Moon in Virgo" in text
    assert "YOUR MOON ANGLE" in text
    assert "THE MOON'S JOURNEY" in text
    # Taurus readers get a different whole-sign area for the same lunation.
    text_taurus = interpretation.sign_horoscope_text(
        F.sun_sign_horoscope(period, "Taurus"))
    assert "area 5" in text_taurus
    assert "area 1" not in text_taurus