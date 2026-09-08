"""Tests for the offline DE441 backend."""

from datetime import datetime, timezone

import pytest

from astronomy.backends import BackendUnavailableError
from astronomy.backends.de441 import DE441KernelBackend
from core import constants as C
from core.models import Location

_AU_IN_KM = 149597870.7


class _FakeSegment:
    def __init__(self, center, target, position_km, velocity_km_per_day):
        self.center = center
        self.target = target
        self._position = tuple(position_km)
        self._velocity = tuple(velocity_km_per_day)

    def compute_and_differentiate(self, _jd_tdb):
        return self._position, self._velocity


class _FakeKernel:
    def __init__(self, segments):
        self.segments = list(segments)

    def comments(self):
        return "FAKE DE441 TEST KERNEL"


def test_de441_backend_requires_configured_kernel_path():
    backend = DE441KernelBackend(kernel_path="")
    with pytest.raises(BackendUnavailableError):
        backend.fetch_snapshot(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc))


def test_de441_backend_resolves_recursive_segments_into_body_states():
    backend = DE441KernelBackend(kernel_path="C:\\fake\\de441.bsp")
    backend._kernel = _FakeKernel(
        [
            _FakeSegment(0, 10, (100.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
            _FakeSegment(0, 3, (200.0, 0.0, 0.0), (20.0, 0.0, 0.0)),
            _FakeSegment(3, 399, (1.0, 0.0, 0.0), (0.1, 0.0, 0.0)),
            _FakeSegment(3, 301, (3.0, 0.0, 0.0), (0.3, 0.0, 0.0)),
            _FakeSegment(0, 1, (50.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
            _FakeSegment(1, 199, (4.0, 0.0, 0.0), (0.4, 0.0, 0.0)),
        ]
    )

    snapshot = backend.fetch_snapshot(
        datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc),
        observer=Location(latitude=51.5, longitude=0.0, altitude=10.0, name="Greenwich"),
        body_ids=[C.MERCURY, C.MOON, C.SUN],
    )

    mercury = next(body for body in snapshot.bodies if body.body_id == C.MERCURY)
    moon = next(body for body in snapshot.bodies if body.body_id == C.MOON)
    sun = next(body for body in snapshot.bodies if body.body_id == C.SUN)

    assert abs(mercury.geocentric.x - ((54.0 - 201.0) / _AU_IN_KM)) < 1e-15
    assert abs(mercury.heliocentric.x - ((54.0 - 100.0) / _AU_IN_KM)) < 1e-15
    assert mercury.metadata["target_code"] == "199"
    assert mercury.metadata["equatorial_origin"] == "observer"
    assert mercury.equatorial is not None
    assert mercury.ecliptic is not None
    assert abs(moon.geocentric.x - (2.0 / _AU_IN_KM)) < 1e-15
    assert abs(sun.geocentric.x - ((100.0 - 201.0) / _AU_IN_KM)) < 1e-15
    assert snapshot.time.jd_tdb is not None
    assert abs(snapshot.time.jd_tdb - snapshot.time.jd_utc) > 0.0
    assert snapshot.metadata["source"] == "JPL DE441 kernel"
    assert snapshot.metadata["kernel_path"].endswith("de441.bsp")


def test_de441_backend_uses_last_matching_segment_for_a_target():
    backend = DE441KernelBackend(kernel_path="C:\\fake\\de441.bsp")
    backend._kernel = _FakeKernel(
        [
            _FakeSegment(0, 10, (100.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
            _FakeSegment(0, 3, (200.0, 0.0, 0.0), (20.0, 0.0, 0.0)),
            _FakeSegment(3, 399, (1.0, 0.0, 0.0), (0.1, 0.0, 0.0)),
            _FakeSegment(0, 1, (50.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
            _FakeSegment(1, 199, (1.0, 0.0, 0.0), (0.1, 0.0, 0.0)),
            _FakeSegment(1, 199, (4.0, 0.0, 0.0), (0.4, 0.0, 0.0)),
        ]
    )

    snapshot = backend.fetch_snapshot(
        datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc),
        body_ids=[C.MERCURY],
    )
    mercury = snapshot.bodies[0]
    assert abs(mercury.heliocentric.x - ((54.0 - 100.0) / _AU_IN_KM)) < 1e-15
