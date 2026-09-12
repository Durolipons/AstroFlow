"""Ephemeris-driven astro-clock forecasts: Daily / Weekly / Monthly.

Everything here is *birth-chart free*: it derives from the current (or any
target) sky rather than a natal chart. The engine scans the ephemeris over a
window and produces four kinds of sky events:

  * ``IngressEvent``  -- a planet crosses a sign boundary ("enters Taurus").
  * ``StationEvent``  -- a planet turns retrograde or direct.
  * ``AspectEvent``   -- two moving planets come within an aspect orb; the
    event records when they *entered* the orb, when the aspect is *exact*,
    and when they *leave* the orb.
  * ``LunationEvent`` -- New / First Quarter / Full / Last Quarter Moon.

``ForecastPeriod`` is the event list for one window; ``sun_sign_horoscope``
then folds those events onto each zodiac sign using the **whole-sign**
convention (see ``SIGN_ASPECT_RELATIONS``) so a shareable per-sign
horoscope can be composed by ``core.interpretation``.

All times are UTC; the Swiss Ephemeris wrapper stays behind
``core.ephemeris`` (this module never imports ``swisseph`` directly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from . import aspects as A
from . import constants as C
from . import ephemeris as E
from .models import PlanetPosition

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Bodies scanned for ingresses/stations/aspects.  The two lunar nodes are
# skipped (they duplicate each other and creep <0.05°/day); Chiron is included
# and simply absent from samples when its data file is unavailable.
FORECAST_BODIES: Tuple[str, ...] = tuple(
    C.PLANETS[pid]
    for pid in (C.SUN, C.MOON, C.MERCURY, C.VENUS, C.MARS,
                C.JUPITER, C.SATURN, C.URANUS, C.NEPTUNE, C.PLUTO, C.CHIRON)
)

# Whole-sign mapping: if a planet sits `k` signs ahead of a sun sign, which
# major aspect does the planet make *to the sign*?  (Conjunction = planet in
# the sign itself, handled separately.)
SIGN_ASPECT_RELATIONS: Dict[int, str] = {
    2: "Sextile", 10: "Sextile",
    3: "Square", 9: "Square",
    4: "Trine", 8: "Trine",
    6: "Opposition",
}


# ---------------------------------------------------------------------------
# Sky event models
# ---------------------------------------------------------------------------
@dataclass
class IngressEvent:
    """A planet crossing a zodiac-sign boundary."""

    body: str
    time_utc: datetime
    enters_sign: str
    leaves_sign: str
    entering: bool = True      # False when retrograde slips back out


@dataclass
class StationEvent:
    """A planet turning retrograde or direct."""

    body: str
    time_utc: datetime
    going_retrograde: bool


@dataclass
class AspectEvent:
    """Two moving planets inside one aspect orb, timed at the boundaries."""

    body1: str
    body2: str
    type_name: str
    angle: float
    orb: float
    orb_in_time_utc: datetime      # when the pair entered the aspect's orb
    orb_out_time_utc: datetime     # when the pair leaves the orb
    exact_time_utc: Optional[datetime] = None  # best exact moment (or None)
    applying: bool = True          # always applying while inside the orb
@dataclass
class LunationAspect:
    """A major aspect a lunation makes to another planet."""

    body: str
    type_name: str
    orb: float


@dataclass
class LunationEvent:
    """A New / quarter / Full Moon (``sign`` = the Moon's sign at the moment)."""

    phase: str
    time_utc: datetime
    sign: str = ""
    aspects: List[LunationAspect] = field(default_factory=list)


@dataclass
class MoonState:
    """The Moon's current 8-fold phase, sign and next sign change."""

    phase: str
    sign: str
    next_ingress_utc: Optional[datetime] = None
    next_sign: Optional[str] = None


def _phase_from_elongation(el: float) -> str:
    """8-fold moon phase from the Sun->Moon elongation (degrees 0-360)."""
    names = ("New Moon", "Waxing Crescent Moon", "First Quarter Moon",
             "Waxing Gibbous Moon", "Full Moon", "Waning Gibbous Moon",
             "Last Quarter Moon", "Waning Crescent Moon")
    return names[int((el % 360.0) // 45.0) % 8]


def moon_state(ep: Optional[E.Ephemeris] = None,
               dt_utc: Optional[datetime] = None) -> Optional[MoonState]:
    """The Moon's phase + sign right now (or at ``dt_utc``), and its next ingress."""
    epi = ep or E.get_ephemeris()
    dt = dt_utc or datetime.now(timezone.utc)
    jd = epi.julian_day_ut(dt)
    try:
        sun = epi.planet_position(jd, C.SUN)
        moon = epi.planet_position(jd, C.MOON)
    except Exception:
        return None
    el = (moon.longitude - sun.longitude) % 360.0
    state = MoonState(phase=_phase_from_elongation(el), sign=moon.sign)
    # Next Moon ingress within 48 hours (Moon moves ~13 deg/day).
    horizon = dt + timedelta(hours=48)
    ingresses = scan_ingresses(dt, horizon, ep=epi, step_hours=1)
    for ev in ingresses:
        if ev.body == "Moon":
            state.next_ingress_utc = ev.time_utc
            state.next_sign = ev.enters_sign
            break
    return state


def lunation_area_offset(lunation_sign: str, sun_sign: str) -> int:
    """Which 1-12 life area a lunation in ``lunation_sign`` lands in for a
    reader whose sun sign is ``sun_sign`` (whole-sign: lunation sign = area 1)."""
    rel = (C.SIGNS.index(lunation_sign) - C.SIGNS.index(sun_sign)) % 12
    return rel + 1


def scan_lunation_aspects(lunation_time_utc: datetime,
                          ep: Optional[E.Ephemeris] = None,
                          orbs: Optional[dict] = None,
                          max_orb: float = 6.0) -> List[LunationAspect]:
    """Major aspects the lunation (Moon's position at the exact moment) makes
    to the other planets, sorted tightest-orb first."""
    epi = ep or E.get_ephemeris()
    jd = epi.julian_day_ut(lunation_time_utc)
    try:
        moon = epi.planet_position(jd, C.MOON)
    except Exception:
        return []
    out: List[LunationAspect] = []
    for pid in (C.MERCURY, C.VENUS, C.MARS, C.JUPITER, C.SATURN,
                C.URANUS, C.NEPTUNE, C.PLUTO, C.CHIRON):
        try:
            other = epi.planet_position(jd, pid)
        except Exception:
            continue
        sep = A.shortest_angular_distance(moon.longitude, other.longitude)
        for adef in C.MAJOR_ASPECTS:
            orb = float((orbs or {}).get(adef.name, adef.orb))
            orb = min(orb, max_orb)
            if orb > 0.0 and abs(sep - adef.angle) <= orb:
                out.append(LunationAspect(body=other.name,
                                          type_name=adef.name,
                                          orb=abs(sep - adef.angle)))
                break
    out.sort(key=lambda a: a.orb)
    return out


@dataclass
class ForecastPeriod:
    """All sky events found in one window."""

    label: str
    start_utc: datetime
    end_utc: datetime
    ingresses: List[IngressEvent] = field(default_factory=list)
    stations: List[StationEvent] = field(default_factory=list)
    aspects: List[AspectEvent] = field(default_factory=list)
    lunations: List[LunationEvent] = field(default_factory=list)
    moon_state: Optional[MoonState] = None
    eclipses: List[EclipsePeriod] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.ingresses.sort(key=lambda e: e.time_utc)
        self.stations.sort(key=lambda e: e.time_utc)
        self.aspects.sort(key=lambda e: e.orb_in_time_utc)
        self.lunations.sort(key=lambda e: e.time_utc)
        self.eclipses.sort(key=lambda e: e.peak_utc)

    @property
    def days(self) -> int:
        return max(1, round((self.end_utc - self.start_utc).total_seconds()
                            / 86400.0))


@dataclass
class SignAspect:
    """A planet aspecting one sun sign (whole-sign convention."""

    body: str
    aspect_type: str


@dataclass
class SignHoroscope:
    """Everything the engine knows about one sun sign in one period."""

    sign: str
    period: str
    window_start: datetime
    window_end: datetime
    planets_in_sign: List[PlanetPosition] = field(default_factory=list)
    sign_aspects: List[SignAspect] = field(default_factory=list)
    ingresses: List[IngressEvent] = field(default_factory=list)
    aspects: List[AspectEvent] = field(default_factory=list)
    stations: List[StationEvent] = field(default_factory=list)
    lunations: List[LunationEvent] = field(default_factory=list)
    moon_state: Optional[MoonState] = None
    moon_ingresses: List[IngressEvent] = field(default_factory=list)
    lunation_areas: Dict[int, int] = field(default_factory=dict)
    eclipses: List[EclipsePeriod] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Time helpers (no swisseph import: pure calendar arithmetic)
# ---------------------------------------------------------------------------
def _jd_to_utc(jd: float) -> datetime:
    """Convert a Julian Day (UT) to an aware UTC datetime."""
    return _EPOCH + timedelta(seconds=(jd - 2440587.5) * 86400.0)


def _today_utc_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Ephemeris sampling helpers
# ---------------------------------------------------------------------------
def _positions_at(ep: E.Ephemeris, dt_utc: datetime,
                  sidereal: bool = False) -> Dict[str, PlanetPosition]:
    """Positions for all forecast bodies at ``dt_utc`` (missing -> skipped)."""
    jd = ep.julian_day_ut(dt_utc)
    out: Dict[str, PlanetPosition] = {}
    for pid in (C.SUN, C.MOON, C.MERCURY, C.VENUS, C.MARS,
                C.JUPITER, C.SATURN, C.URANUS, C.NEPTUNE, C.PLUTO, C.CHIRON):
        try:
            pos = ep.planet_position(jd, pid, sidereal=sidereal)
        except Exception:
            # e.g. Chiron without its bundled .se1 file.
            continue
        out[pos.name] = pos
    return out


def _body_at_jd(ep: E.Ephemeris, jd: float, planet_id: int,
                sidereal: bool = False) -> Optional[PlanetPosition]:
    try:
        return ep.planet_position(jd, planet_id, sidereal=sidereal)
    except Exception:
        return None


def _bisect(f, jd_a: float, jd_b: float, iterations: int = 42) -> float:
    """Bisection root for a sign change of ``f`` in the open interval."""
    for _ in range(iterations):
        jd_m = (jd_a + jd_b) * 0.5
        if f(jd_a) * f(jd_m) <= 0.0:
            jd_b = jd_m
        else:
            jd_a = jd_m
    return (jd_a + jd_b) * 0.5


def _signed_to_target(lon: float, target: float) -> float:
    """Shortest signed arc (in (-180, 180]) from ``lon`` to ``target``."""
    d = (lon - target) % 360.0
    return d - 360.0 if d > 180.0 else d
# ---------------------------------------------------------------------------
# Event scanners (sample + bisection)
# ---------------------------------------------------------------------------
def scan_ingresses(start_utc: datetime, end_utc: datetime,
                    ep: Optional[E.Ephemeris] = None,
                    step_hours: int = 4) -> List[IngressEvent]:
    """Sign-boundary crossings by any forecast body in the window."""
    epi = ep or E.get_ephemeris()
    events: List[IngressEvent] = []
    step = timedelta(hours=step_hours)
    prev_dt = start_utc
    prev = _positions_at(epi, prev_dt)
    t = prev_dt + step
    while t <= end_utc:
        cur = _positions_at(epi, t)
        for name in set(prev) & set(cur):
            s_prev = prev[name].sign
            s_cur = cur[name].sign
            if s_prev == s_cur:
                continue
            idx_a = C.SIGNS.index(s_prev)
            idx_b = C.SIGNS.index(s_cur)
            fwd = ((idx_b - idx_a) % 12) == 1
            boundary = (
                (idx_b * 30.0) if fwd else (idx_a * 30.0)
            ) % 360.0
            jd_a = epi.julian_day_ut(prev_dt)
            jd_b = epi.julian_day_ut(t)

            def f_cross(jd: float) -> float:
                pos = _body_at_jd(epi, jd, prev[name].planet_id)
                return _signed_to_target(pos.longitude, boundary) if pos else 0.0

            root = _bisect(f_cross, jd_a, jd_b)
            events.append(IngressEvent(
                body=name, time_utc=_jd_to_utc(root),
                enters_sign=s_cur, leaves_sign=s_prev, entering=fwd,
            ))
        prev, prev_dt = cur, t
        t += step
    events.sort(key=lambda e: e.time_utc)
    return events


def scan_stations(start_utc: datetime, end_utc: datetime,
                   ep: Optional[E.Ephemeris] = None,
                   step_hours: int = 6) -> List[StationEvent]:
    """Retrograde/direct turnings by any forecast body in the window."""
    epi = ep or E.get_ephemeris()
    events: List[StationEvent] = []
    step = timedelta(hours=step_hours)
    prev_dt = start_utc
    prev = _positions_at(epi, prev_dt)
    t = prev_dt + step
    while t <= end_utc:
        cur = _positions_at(epi, t)
        for name in set(prev) & set(cur):
            sp, sc = prev[name].speed, cur[name].speed
            if sp * sc >= 0.0 or abs(sp) < 1e-12 and abs(sc) < 1e-12:
                continue
            jd_a = epi.julian_day_ut(prev_dt)
            jd_b = epi.julian_day_ut(t)

            def f_speed(jd: float) -> float:
                pos = _body_at_jd(epi, jd, prev[name].planet_id)
                return pos.speed if pos else 0.0

            root = _bisect(f_speed, jd_a, jd_b)
            events.append(StationEvent(
                body=name, time_utc=_jd_to_utc(root),
                going_retrograde=sc < 0,
            ))
        prev, prev_dt = cur, t
        t += step
    events.sort(key=lambda e: e.time_utc)
    return events


def _aspect_step_hours(window: timedelta) -> int:
    days = window.total_seconds() / 86400.0
    if days <= 2.0:
        return 2
    if days <= 10.0:
        return 4
    return 8


def _sep_dev(jd: float, ep: E.Ephemeris, pid1: int, pid2: int,
              angle: float) -> float:
    """Signed deviation (separation - angle) for one pair at a Julian Day."""
    p1 = _body_at_jd(ep, jd, pid1)
    p2 = _body_at_jd(ep, jd, pid2)
    if p1 is None or p2 is None:
        return 0.0
    sep = A.shortest_angular_distance(p1.longitude, p2.longitude)
    return sep - angle
def scan_planet_aspects(start_utc: datetime, end_utc: datetime,
                         ep: Optional[E.Ephemeris] = None,
                         orbs: Optional[dict] = None,
                         aspects: Optional[Sequence] = None,
                         step_hours: Optional[int] = None) -> List[AspectEvent]:
    """Planet-planet aspects with orb-entry/exit timing in the window.

    For each pair and major aspect the function tracks whether the pair is inside
    the aspect's orb and bisects the moment they cross the orb boundary (plus the
    exact moment whenever it falls between samples).
    """
    epi = ep or E.get_ephemeris()
    defs = list(aspects) if aspects else list(C.MAJOR_ASPECTS)
    hours = step_hours or _aspect_step_hours(end_utc - start_utc)
    step = timedelta(hours=hours)
    samples: List[Tuple[datetime, Dict[str, PlanetPosition]]] = []
    t = start_utc
    while t <= end_utc:
        samples.append((t, _positions_at(epi, t)))
        t += step

    events: List[AspectEvent] = []
    ids = {C.PLANETS[pid]: pid for pid in (C.SUN, C.MOON, C.MERCURY,
                                                 C.VENUS, C.MARS, C.JUPITER,
                                                 C.SATURN, C.URANUS, C.NEPTUNE,
                                                 C.PLUTO, C.CHIRON)}
    names = [n for n in ids if n in samples[0][1]]

    for k in range(len(names)):
        for kn in range(k + 1, len(names)):
            p1, p2 = names[k], names[kn]
            if p1 not in samples[0][1] or p2 not in samples[0][1]:
                continue
            pid1, pid2 = ids[p1], ids[p2]
            for adef in defs:
                orb = float((orbs or {}).get(adef.name, adef.orb))
                if orb <= 0.0:
                    continue
                state = "out"
                open_in = None
                exact = None
                prev_dt = None
                prev_dev = None
                for dt_s, pos in samples:
                    if p1 not in pos or p2 not in pos:
                        continue
                    sep = A.shortest_angular_distance(
                        pos[p1].longitude, pos[p2].longitude)
                    dev = sep - adef.angle
                    if prev_dev is not None and dev != 0.0 and prev_dev * dev < 0.0:
                        jd_prev = epi.julian_day_ut(prev_dt)
                        jd_now = epi.julian_day_ut(dt_s)
                        exact = _bisect(
                            lambda j: _sep_dev(j, epi, pid1, pid2, adef.angle),
                            jd_prev, jd_now)
                    jd_now = epi.julian_day_ut(dt_s)
                    inside = abs(dev) <= orb
                    if state == "out" and inside:
                        if prev_dt is not None:
                            jd_prev = epi.julian_day_ut(prev_dt)
                            entry = _bisect(
                                lambda j: abs(_sep_dev(j, epi, pid1, pid2, adef.angle)) - orb,
                                jd_prev, jd_now)
                            open_in = entry
                        else:
                            open_in = jd_now  # already inside orb at the window start
                        state = "in"
                    elif state == "in" and not inside:
                        jd_prev = epi.julian_day_ut(prev_dt)
                        out_jd = _bisect(
                            lambda j: abs(_sep_dev(j, epi, pid1, pid2, adef.angle)) - orb,
                            jd_prev, jd_now)
                        events.append(AspectEvent(
                            body1=p1, body2=p2, type_name=adef.name,
                            angle=adef.angle, orb=orb,
                            orb_in_time_utc=_jd_to_utc(open_in),
                            orb_out_time_utc=_jd_to_utc(out_jd),
                            exact_time_utc=_jd_to_utc(exact) if exact is not None else None,
                            applying=True,
                        ))
                        state = "out"
                        exact = None
                    prev_dt, prev_dev = dt_s, dev
                if state == "in":
                    events.append(AspectEvent(
                        body1=p1, body2=p2, type_name=adef.name,
                        angle=adef.angle, orb=orb,
                        orb_in_time_utc=_jd_to_utc(open_in),
                        orb_out_time_utc=end_utc,
                        exact_time_utc=_jd_to_utc(exact) if exact is not None else None,
                        applying=True,
                    ))
    events.sort(key=lambda e: e.orb_in_time_utc)
    return events
def scan_lunations(start_utc: datetime, end_utc: datetime,
                     ep: Optional[E.Ephemeris] = None,
                     step_hours: int = 4,
                     orbs: Optional[dict] = None) -> List[LunationEvent]:
    """New / First Quarter / Full / Last Quarter Moon moments in the window."""
    epi = ep or E.get_ephemeris()
    events: List[LunationEvent] = []
    step = timedelta(hours=step_hours)
    prev_dt = start_utc
    prev = _positions_at(epi, prev_dt)
    t = prev_dt + step
    while t <= end_utc:
        cur = _positions_at(epi, t)
        if "Sun" in prev and "Moon" in prev and "Sun" in cur and "Moon" in cur:
            el_prev = (prev["Moon"].longitude - prev["Sun"].longitude) % 360.0
            el_cur = (cur["Moon"].longitude - cur["Sun"].longitude) % 360.0
            bin_prev = int(el_prev // 90.0)
            bin_cur = int(el_cur // 90.0)
            if bin_prev != bin_cur:
                goes_forward = ((bin_cur - bin_prev) % 4) == 1
                boundary = (((bin_cur % 4) * 90.0) if goes_forward
                            else ((bin_prev % 4) * 90.0)) % 360.0
                jd_a = epi.julian_day_ut(prev_dt)
                jd_b = epi.julian_day_ut(t)
                phases = {0: "New Moon", 90: "First Quarter Moon",
                           180:"Full Moon",270:"Last Quarter Moon"}

                def f_el(jd: float) -> float:
                    sun = _body_at_jd(epi, jd, C.SUN)
                    moon = _body_at_jd(epi, jd, C.MOON)
                    if sun is None or moon is None:
                        return 0.0
                    el = (moon.longitude - sun.longitude) % 360.0
                    return _signed_to_target(el, boundary)

                root = _bisect(f_el, jd_a, jd_b)
                exact = _jd_to_utc(root)
                moon_pos = _body_at_jd(epi, root, C.MOON)
                events.append(LunationEvent(
                    phase=phases[int(boundary) % 360],
                    time_utc=exact,
                    sign=moon_pos.sign if moon_pos else "",
                    aspects=scan_lunation_aspects(exact, ep=epi, orbs=orbs),
                ))
        prev, prev_dt = cur, t
        t += step
    events.sort(key=lambda e: e.time_utc)
    return events

# ---------------------------------------------------------------------------
# Eclipse models (generic: no sign/house meaning yet)
# ---------------------------------------------------------------------------
@dataclass
class EclipsePeriod:
    """One eclipse passage through the target window.

    ``kind`` is one of ``"Solar Eclipse (New Moon)"`` or ``"Lunar Eclipse (Full Moon)"``.
    Times are approximate UTC windows around the event; ``intensity`` is a
    conservative, qualitative estimate (``"deep"`` / ``"partial"`` / ``"shallow"``)
    derived from how close the geometry is to a true node-aligned eclipse.
    """
    kind: str
    start_utc: datetime
    peak_utc: datetime
    end_utc: datetime
    intensity: str = "shallow"


@dataclass
class EclipseWindow:
    """Generic eclipse scan result for one window."""

    periods: List[EclipsePeriod] = field(default_factory=list)


def _moon_elongation(ep: E.Ephemeris, jd: float) -> Optional[float]:
    """Apparent Sun->Moon ecliptic elongation in degrees (0..360)."""
    sun = _body_at_jd(ep, jd, C.SUN)
    moon = _body_at_jd(ep, jd, C.MOON)
    if sun is None or moon is None:
        return None
    return (moon.longitude - sun.longitude) % 360.0


def _moon_latitude(ep: E.Ephemeris, jd: float) -> Optional[float]:
    """Moon's ecliptic latitude in degrees (apparent) at ``jd``."""
    moon = _body_at_jd(ep, jd, C.MOON)
    return moon.latitude if moon is not None else None


def _node_proximity_approx(moon_lat: float) -> float:
    """Approximate how close the Moon is to an ecliptic node.

    True node position requires the lunar-node ephemeris; here we approximate
    a node passage by the Moon crossing the ecliptic (latitude near zero),
    because eclipses only occur when the Moon is both near a node *and* in
    the right elongation. This gives a coarse "near node" signal suitable for
    a generic ``shallow``/``partial``/``deep`` intensity estimate.
    """
    return abs(moon_lat)


def _eclipse_depth(elong: float, moon_lat: float) -> float:
    """Lower = closer to a true eclipse geometry (0 = perfect).

    Combines two necessary conditions:
    * elongation near 0 (solar) or 180 (lunar), and
    * Moon near the ecliptic plane (node passage).
    """
    if elong is None:
        return 180.0
    el = elong % 360.0
    # Distance from the nearest of new moon (0 deg) or full moon (180 deg).
    gap_from_new = min(el, 360.0 - el)
    gap_from_full = abs(el - 180.0)
    closest = min(gap_from_new, gap_from_full)
    lat_gap = abs(moon_lat) if moon_lat is not None else 90.0
    # Elongation dominates: a true eclipse must be very close to new or full.
    el_term = min(closest * 2.0, 180.0)  # nearly linear near 0; saturate near 180
    # Latitude term: closer to the ecliptic = closer to a node-aligned event.
    lat_term = min(lat_gap, 90.0)
    # Weight elongation much more heavily; latitude is a secondary filter.
    return el_term + 0.25 * lat_term


def _eclipse_peak(jd: float, ep: E.Ephemeris) -> Tuple[datetime,
                                                         Optional[float],
                                                         Optional[float],
                                                         float]:
    """Peak geometry at ``jd``: UTC, elongation, moon latitude, depth.

    Returns real UTC always; elongation/latitude may be ``None`` if the Sun or
    Moon cannot be computed, in which case ``depth`` is set to a non-eclipse
    value so the scanner can continue safely.
    """
    dt = _jd_to_utc(jd)
    elong = _moon_elongation(ep, jd)
    mlat = _moon_latitude(ep, jd)
    if elong is None or mlat is None:
        return dt, elong, mlat, 90.0
    return dt, elong, mlat, _eclipse_depth(elong, mlat)

def scan_eclipses(start_utc: datetime, end_utc: datetime,
                  ep: Optional[E.Ephemeris] = None) -> EclipseWindow:
    """Find eclipse passages through ``start_utc``..``end_utc``.

    A solar-eclipse passage is detected when Sun and Moon are in near-conjunction
    and the Moon is near the ecliptic (node), i.e. a new-moon event close enough to
    the shadow line to matter. A lunar-eclipse passage is detected when Sun and Moon
    are in near-opposition and the Moon is near the ecliptic.

    Returns an ``EclipseWindow`` whose ``periods`` are sorted by ``peak_utc``.
    """
    epi = ep or E.get_ephemeris()
    step_hours = 3
    step = timedelta(hours=step_hours)
    t = start_utc
    samples: List[Tuple[datetime, Optional[float], Optional[float], float]] = []
    while t <= end_utc:
        dt, elong, mlat, depth = _eclipse_peak(epi.julian_day_ut(t), epi)
        samples.append((dt, elong, mlat, depth))
        t += step

    # -- identify passages where depth dips below the eclipse threshold -------
    threshold = 9.0  # degrees of combined geometry error; conservative
    passages: List[List[Tuple[datetime, Optional[float], Optional[float],
                                  float]]] = []
    cur: List[Tuple[datetime, Optional[float], Optional[float], float]] = []
    for sample in samples:
        if sample[3] < threshold:
            cur.append(sample)
        else:
            if cur:
                passages.append(cur)
            cur = []
    if cur:
        passages.append(cur)

    out: List[EclipsePeriod] = []
    for passage in passages:
        best = min(passage, key=lambda s: s[3])
        peak_dt, elong, mlat, depth = best
        if elong is None or mlat is None:
            continue
        elong = elong % 360.0
        # -- classify ----------------------------------------------------------
        if elong < 90.0 or elong > 270.0:
            # near new moon --> solar-eclipse passage candidate
            kind = "Solar Eclipse (New Moon)"
            near_node = _node_proximity_approx(mlat) < 2.0
        else:
            # near full moon --> lunar-eclipse passage candidate
            kind = "Lunar Eclipse (Full Moon)"
            near_node = _node_proximity_approx(mlat) < 2.0

        # -- intensity ---------------------------------------------------------
        if near_node and depth < 3.0:
            intensity = "deep"
        elif depth < 6.0:
            intensity = "partial"
        else:
            intensity = "shallow"

        # -- time window around peak (a few hours either side) ---------------
        span = timedelta(hours=3.0)
        out.append(EclipsePeriod(
            kind=kind,
            start_utc=peak_dt - span,
            peak_utc=peak_dt,
            end_utc=peak_dt + span,
            intensity=intensity,
        ))

    out.sort(key=lambda p: p.peak_utc)
    return EclipseWindow(periods=out)


def forecast_period(start_utc: datetime, end_utc: datetime,
                    ep: Optional[E.Ephemeris] = None,
                    orbs: Optional[dict] = None,
                    label: Optional[str] = None) -> ForecastPeriod:
    """Scan a full window and return every sky event it contains."""
    epi = ep or E.get_ephemeris()
    days = max(1.0, (end_utc - start_utc).total_seconds() / 86400.0)
    period = ForecastPeriod(
        label=label or f"{days:.0f} days",
        start_utc=start_utc, end_utc=end_utc,
        ingresses=scan_ingresses(start_utc, end_utc, ep=epi),
        stations=scan_stations(start_utc, end_utc, ep=epi),
        aspects=scan_planet_aspects(start_utc, end_utc, ep=epi, orbs=orbs),
        lunations=scan_lunations(start_utc, end_utc, ep=epi, orbs=orbs),
        moon_state=moon_state(ep=epi, dt_utc=start_utc),
        eclipses=scan_eclipses(start_utc, end_utc, ep=epi).periods,
    )
    return period


def daily_forecast(day_utc: Optional[datetime] = None,
                    ep: Optional[E.Ephemeris] = None,
                    orbs: Optional[dict] = None) -> ForecastPeriod:
    """Forecast for one day (midnight-to-midnight UTC.."""
    start = (day_utc or _today_utc_start()).replace(hour=0, minute=0,
                                             second=0, microsecond=0)
    return forecast_period(start, start + timedelta(days=1), ep=ep, orbs=orbs,
                            label="Daily")


def calendar_forecast(period: str,
                      start_utc: Optional[datetime] = None,
                      ep: Optional[E.Ephemeris] = None,
                      orbs: Optional[dict] = None) -> ForecastPeriod:
    """Forecast one calendar day, week, month, or year from ``start_utc``.

    Month and year windows preserve the selected day when possible and clamp
    it to the last valid day when the destination month is shorter.
    """
    start = (start_utc or _today_utc_start()).replace(
        hour=0, minute=0, second=0, microsecond=0)
    normalized = period.strip().lower()
    if normalized == "day":
        end = start + timedelta(days=1)
        label = "Daily"
    elif normalized == "week":
        end = start + timedelta(days=7)
        label = "Weekly"
    elif normalized == "month":
        year = start.year + (start.month // 12)
        month = (start.month % 12) + 1
        day = start.day
        while True:
            try:
                end = start.replace(year=year, month=month, day=day)
                break
            except ValueError:
                day -= 1
        label = "Monthly"
    elif normalized == "year":
        try:
            end = start.replace(year=start.year + 1)
        except ValueError:
            end = start.replace(year=start.year + 1, day=28)
        label = "Yearly"
    else:
        raise ValueError("Forecast period must be Day, Week, Month, or Year")
    return forecast_period(start, end, ep=ep, orbs=orbs, label=label)


def weekly_forecast(day_utc: Optional[datetime] = None,
                     ep: Optional[E.Ephemeris] = None,
                     orbs: Optional[dict] = None) -> ForecastPeriod:
    """Forecast for the next seven days."""
    start = (day_utc or _today_utc_start()).replace(hour=0, minute=0,
                                             second=0, microsecond=0)
    return forecast_period(start, start + timedelta(days=7), ep=ep, orbs=orbs,
                            label="Weekly")


def monthly_forecast(day_utc: Optional[datetime] = None,
                      ep: Optional[E.Ephemeris] = None,
                      orbs: Optional[dict] = None) -> ForecastPeriod:
    """Forecast for the next thirty days."""
    start = (day_utc or _today_utc_start()).replace(hour=0, minute=0,
                                             second=0, microsecond=0)
    return forecast_period(start, start + timedelta(days=30), ep=ep, orbs=orbs,
                            label="Monthly")
# ---------------------------------------------------------------------------
# Whole-sign sun-sign mapping
# ---------------------------------------------------------------------------
def sign_aspects_for(sign_name: str,
                     positions: Optional[Dict[str, PlanetPosition]] = None,
                     ep: Optional[E.Ephemeris] = None,
                     ref_utc: Optional[datetime] = None,
                    ) -> Tuple[List[PlanetPosition], List[SignAspect]]:
    """Map bodies onto one sun sign (whole-sign reading).

    Returns ``(in_sign, aspects)`` where ``in_sign`` lists bodies whose sign
    equals ``sign_name`` and ``aspects`` lists bodies making a major aspect to it.
    """
    if positions is None:
        epi = ep or E.get_ephemeris()
        positions = _positions_at(epi, ref_utc or _today_utc_start())
    i = C.SIGNS.index(sign_name)
    in_sign: List[PlanetPosition] = []
    aspects_list: List[SignAspect] = []
    for body in FORECAST_BODIES:
        pos = positions.get(body)
        if pos is None:
            continue
        rel = (C.SIGNS.index(pos.sign) - i) % 12
        if rel == 0:
            in_sign.append(pos)
        elif rel in SIGN_ASPECT_RELATIONS:
            aspects_list.append(SignAspect(body=body,
                                          aspect_type=SIGN_ASPECT_RELATIONS[rel]))
    in_sign.sort(key=lambda p: (C.SIGNS.index(p.sign), p.name))
    return in_sign, aspects_list


def sun_sign_horoscope(period: ForecastPeriod, sign_name: str,
                        ep: Optional[E.Ephemeris] = None) -> SignHoroscope:

    """Fold a period's sky events onto one sun sign."""

    epi = ep or E.get_ephemeris()
    in_sign, sign_aspects = sign_aspects_for(
        sign_name, ep=epi, ref_utc=period.start_utc)
    touching = [e for e in period.ingresses
                  if e.enters_sign == sign_name or e.leaves_sign == sign_name]
    moon_moves = [e for e in period.ingresses if e.body == "Moon"]
    areas = {}
    for idx, lu in enumerate(period.lunations):
        if lu.sign:
            areas[idx] = lunation_area_offset(lu.sign, sign_name)
    return SignHoroscope(
        sign=sign_name, period=period.label,
        window_start=period.start_utc, window_end=period.end_utc,
        planets_in_sign=in_sign, sign_aspects=sign_aspects,
        ingresses=touching, aspects=period.aspects,
        stations=period.stations, lunations=period.lunations,
        moon_state=period.moon_state, moon_ingresses=moon_moves,
        lunation_areas=areas, eclipses=period.eclipses,
    )