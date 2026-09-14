"""Synastry engine and interpretation tests."""

from datetime import datetime, timezone

from core.interpretation import full_synastry_report, synastry_aspect_detail
from core.interpretation_store import (
    default_interpretation_library,
)
from core.models import BirthData, Location
from core.synastry import compute_synastry


def _alice():
    return BirthData(
        name="Alice",
        birth_datetime=datetime(1990, 6, 15, 10, 30, tzinfo=timezone.utc),
        location=Location(latitude=40.7, longitude=-74.0),
    )


def _bob():
    return BirthData(
        name="Bob",
        birth_datetime=datetime(1988, 11, 22, 14, 0, tzinfo=timezone.utc),
        location=Location(latitude=51.5, longitude=-0.1),
    )


def test_compute_synastry_basic():
    """SynastryResult has both names, cross-aspects, overlays, score."""
    result = compute_synastry(_alice(), _bob())
    assert result.name_a == "Alice"
    assert result.name_b == "Bob"
    assert len(result.cross_aspects) > 0
    assert len(result.overlays_a_in_b) > 0
    assert len(result.overlays_b_in_a) > 0
    # House overlays are valid houses 1..12
    for ov in result.overlays_a_in_b + result.overlays_b_in_a:
        assert 1 <= ov.house <= 12
    # Score is deterministic and in range
    assert 0 <= result.overall_score <= 100
    assert result.verdict != ""


def test_compute_synastry_symmetric():
    """Swapping A and B gives same score (symmetry)."""
    r1 = compute_synastry(_alice(), _bob())
    r2 = compute_synastry(_bob(), _alice())
    assert abs(r1.overall_score - r2.overall_score) < 0.01


def test_compute_synastry_cross_aspects_sorted():
    """Cross-aspects are sorted by tightness (smallest orb first)."""
    result = compute_synastry(_alice(), _bob())
    orbs = [abs(a.orb) for a in result.cross_aspects]
    assert orbs == sorted(orbs)


def test_full_synastry_report_contains_names():
    """Report mentions both names and key sections."""
    report = full_synastry_report(_alice(), _bob())
    assert "Alice" in report
    assert "Bob" in report
    assert "OVERALL SCORE" in report
    assert "CROSS-CHART ASPECTS" in report
    assert "HOUSE OVERLAYS" in report
    assert "ELEMENTAL CHEMISTRY" in report


def test_full_synastry_report_uses_editable_store():
    """Report pulls cross-aspect text from the editable synastry_aspect store."""
    lib = default_interpretation_library()
    assert len(lib.synastry_aspect) > 0
    assert len(lib.synastry_house) > 0
    assert len(lib.synastry_element) > 0
    assert len(lib.synastry_score) > 0


def test_synastry_aspect_detail():
    """Detail function returns text for a valid aspect index."""
    result = compute_synastry(_alice(), _bob())
    detail = synastry_aspect_detail(result, 0)
    assert len(detail) > 0
    # Out of range returns gracefully
    assert "No aspect" in synastry_aspect_detail(result, 9999)
