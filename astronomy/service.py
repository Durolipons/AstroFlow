"""High-level astronomy service and backend registry."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple

from core import constants as C
from core.models import Location

from .backends import DE441KernelBackend, HorizonsBackend
from .models import AstronomySnapshot
from .timebase import build_time_context


class AstronomyService:
    """Backend chooser and snapshot cache."""

    def __init__(self, backends: Optional[Dict[str, object]] = None) -> None:
        self._backends = backends or {
            "horizons": HorizonsBackend(),
            "de441": DE441KernelBackend(),
        }
        self._cache: Dict[Tuple, AstronomySnapshot] = {}

    def available_backends(self):
        return tuple(self._backends)

    def get_backend(self, name: str):
        try:
            return self._backends[name]
        except KeyError as exc:
            raise ValueError(
                f"Unknown astronomy backend {name!r}; choose one of {sorted(self._backends)}"
            ) from exc

    def build_time_context(self, moment_utc: datetime):
        return build_time_context(moment_utc)

    def fetch_snapshot(
        self,
        backend_name: str,
        moment_utc: datetime,
        observer: Optional[Location] = None,
        body_ids: Optional[Iterable[int]] = None,
        use_cache: bool = True,
    ) -> AstronomySnapshot:
        body_key = tuple(body_ids) if body_ids else tuple(C.DEFAULT_PLANET_IDS)
        observer_key = (
            round(observer.latitude, 6),
            round(observer.longitude, 6),
            round(observer.altitude, 2),
        ) if observer else (0.0, 0.0, 0.0)
        time_context = self.build_time_context(moment_utc)
        time_key = time_context.jd_tdb or time_context.jd_utc
        cache_key = (backend_name, round(time_key, 8), observer_key, body_key)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]

        backend = self.get_backend(backend_name)
        snapshot = backend.fetch_snapshot(moment_utc, observer=observer, body_ids=body_ids)
        self._cache[cache_key] = snapshot
        return snapshot


_DEFAULT_SERVICE = AstronomyService()


def get_default_service() -> AstronomyService:
    """Shared default service."""
    return _DEFAULT_SERVICE
