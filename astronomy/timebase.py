"""Time normalization helpers for astronomy providers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import AstronomyTimeContext

_J2000 = datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc)
_UNIX_EPOCH_JD = 2440587.5
_SECONDS_PER_DAY = 86400.0


def ensure_utc(dt: datetime) -> datetime:
    """Normalize a datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def julian_day_utc(dt: datetime) -> float:
    """UTC datetime -> Julian day."""
    dt_utc = ensure_utc(dt)
    timestamp = dt_utc.timestamp()
    return _UNIX_EPOCH_JD + (timestamp / _SECONDS_PER_DAY)


def _fallback_delta_t_seconds(dt_utc: datetime) -> float:
    """Coarse Delta-T estimate used when Astropy is unavailable.

    The adapter and UI scaffolding only need a stable time context. Precision
    providers should prefer Astropy when installed.
    """
    years_from_j2000 = (ensure_utc(dt_utc) - _J2000).total_seconds() / (365.25 * _SECONDS_PER_DAY)
    return 69.184 + (0.002 * years_from_j2000)


def build_time_context(dt: datetime) -> AstronomyTimeContext:
    """Create UTC / TT / TDB / JD representations for one moment."""
    dt_utc = ensure_utc(dt)

    try:
        from astropy.time import Time
    except ImportError:
        delta_t = _fallback_delta_t_seconds(dt_utc)
        tt_dt = dt_utc + timedelta(seconds=delta_t)
        return AstronomyTimeContext(
            source_datetime_utc=dt_utc,
            utc_datetime=dt_utc,
            tt_datetime=tt_dt,
            tdb_datetime=tt_dt,
            jd_utc=julian_day_utc(dt_utc),
            jd_tt=julian_day_utc(tt_dt),
            jd_tdb=julian_day_utc(tt_dt),
            delta_t_seconds=delta_t,
            metadata={"provider": "fallback", "astropy": "unavailable"},
        )

    t_utc = Time(dt_utc, scale="utc")
    t_tt = t_utc.tt
    t_tdb = t_utc.tdb
    tt_dt = t_tt.to_datetime(leap_second_strict="silent")
    tdb_dt = t_tdb.to_datetime(leap_second_strict="silent")
    if tt_dt.tzinfo is None:
        tt_dt = tt_dt.replace(tzinfo=timezone.utc)
    if tdb_dt.tzinfo is None:
        tdb_dt = tdb_dt.replace(tzinfo=timezone.utc)
    delta_t = float((t_tt.jd - t_utc.jd) * _SECONDS_PER_DAY)
    return AstronomyTimeContext(
        source_datetime_utc=dt_utc,
        utc_datetime=dt_utc,
        tt_datetime=tt_dt,
        tdb_datetime=tdb_dt,
        jd_utc=float(t_utc.jd),
        jd_tt=float(t_tt.jd),
        jd_tdb=float(t_tdb.jd),
        delta_t_seconds=delta_t,
        metadata={"provider": "astropy", "astropy": "available"},
    )
