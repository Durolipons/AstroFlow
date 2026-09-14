"""Tests for the I Ching engine and database."""
import random

import pytest

from core import iching as IC
from core import iching_interpretation as IP


@pytest.fixture(scope="module")
def db():
    return IC.Database()


def test_database_complete(db):
    assert len(db.hexagrams) == 64
    for h in db.hexagrams.values():
        assert len(h["lines"]) == 6
        assert len(h["binary"]) == 6
        assert h["judgment"] and h["image"]
        for l in h["lines"]:
            assert l["text"] and l["commentary"]
            assert l["value"] in (7, 8)


def test_unique_binaries(db):
    assert len({h["binary"] for h in db.hexagrams.values()}) == 64
    assert len({h["number"] for h in db.hexagrams.values()}) == 64


def test_cast_values_valid():
    for method in ("coins", "yarrow"):
        r = IC.cast(method, rng=random.Random(1))
        assert len(r["values"]) == 6
        assert all(v in (6, 7, 8, 9) for v in r["values"])
    with pytest.raises(ValueError):
        IC.cast("d64")


def test_binary_and_transform():
    # all young lines: secondary = primary
    r = IC.cast("coins", rng=random.Random(0))
    values = [7] * 6
    assert IC.values_to_binary(values) == "111111"
    assert IC.transform("111111", []) == "111111"
    # old yang at line 1 flips to yin
    assert IC.transform("111111", [1]) == "011111"
    # moving positions detected correctly
    assert IC.moving_positions([9, 7, 8, 8, 6, 7]) == [1, 5]


def test_reading_resolution(db):
    values = [9, 8, 8, 8, 8, 7]  # old yang line 1, young yang line 6
    res = IC.reading({"method": "coins", "values": values}, db)
    assert res["moving"] == [1]
    # primary: 100001 = hexagram 27 (I / Corners of the Mouth)
    assert res["primary"]["number"] == 27
    # secondary: 000001 = hexagram 23 (Po / Splitting Apart)
    assert res["secondary"]["number"] == 23


def test_reading_no_moving(db):
    res = IC.reading({"method": "coins", "values": [7, 8, 7, 8, 7, 8]}, db)
    assert res["moving"] == []
    assert res["secondary"] is None


def test_report_contains_sections(db):
    values = [6, 7, 7, 9, 8, 8]  # moving lines 1 and 4
    res = IC.reading({"method": "coins", "values": values}, db)
    report = IP.iching_report(res, question="What should I focus on?")
    for needle in ("I CHING DIVINATION", "What should I focus on?",
                   "THE JUDGMENT", "THE IMAGE", "MOVING LINES",
                   "TRANSFORM INTO"):
        assert needle in report, f"missing section: {needle}"
    assert "Hexagram" in report


def test_patch_records_present(db):
    # Gap-filled passages from the Bollingen extract must be in the database.
    assert "Thunder and lightning" in db.by_number(21)["image"]
    assert "Success through smallness" in db.by_number(56)["judgment"]
    l5 = db.lines_of(20)[5]
    assert "Contemplation of my life" in l5["text"]
