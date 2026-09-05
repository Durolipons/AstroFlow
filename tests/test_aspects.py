"""Aspect detection tests."""

import pytest

from core.aspects import (
    find_aspects_between,
    find_aspects_between_charts,
    is_applying,
    shortest_angular_distance,
)
from core.models import PlanetPosition


def _pos(name, lon, speed=0.0):
    return PlanetPosition(planet_id=0, name=name, longitude=lon, speed=speed)



def test_shortest_angular_distance():
    assert shortest_angular_distance(10,  20,) == pytest.approx(10)
    assert shortest_angular_distance(350,  10,) == pytest.approx(20)
    assert shortest_angular_distance(10,  190,) == pytest.approx(180)
    assert shortest_angular_distance(90,  270,) == pytest.approx(180)

def test_is_applying():
    # Body2 moves toward Body1 while Body1 is faster; gap shrinks.
    assert is_applying(0,  2,  4,  1,  0,)is True

def test_is_applying_separating():
    assert is_applying(0,  1,  4,  2,  0,)is False

def test_find_aspects_between_detects_trine():
    pts = [_pos("Sun",0), _pos("Moon",120), _pos("Mars",40)]
    aspects = find_aspects_between(pts)
    assert len(aspects) == 1
    assert aspects[0].type_name == "Trine"
    assert aspects[0].planet1_name == "Sun"

def test_find_aspects_between_respects_orb():
    pts = [_pos("Sun",0), _pos("Venus",156)]
    assert find_aspects_between(pts) == []
    pts2 = [_pos("Sun",0), _pos("Venus",151)]
    aspects = find_aspects_between(pts2)
    assert aspects[0].type_name == "Quincunx"

def test_cross_chart_aspects():
    natal = [_pos("Mars",25)]
    trans = [_pos("Saturn",27)]
    aspects = find_aspects_between_charts(trans, natal)
    assert len(aspects) == 1
    assert aspects[0].type_name == "Conjunction"
    assert aspects[0].planet1_name.endswith("(transit)")
