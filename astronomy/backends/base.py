"""Common backend interface."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from core.models import Location

from ..models import AstronomySnapshot
from ..timebase import build_time_context


class BackendUnavailableError(RuntimeError):
    """Raised when an optional astronomy backend cannot serve a request."""


class AstronomyBackend:
    """Base class for astronomy providers."""

    name = "base"

    def build_time_context(self, moment_utc: datetime):
        return build_time_context(moment_utc)

    def available_bodies(self) -> Iterable[int]:
        raise NotImplementedError

    def fetch_snapshot(
        self,
        moment_utc: datetime,
        observer: Optional[Location] = None,
        body_ids: Optional[Iterable[int]] = None,
    ) -> AstronomySnapshot:
        raise NotImplementedError
