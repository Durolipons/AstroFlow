"""City / place lookup backed by a bundled local database.

The database (``core/data/cities.json``) holds ~2,000 major cities/towns with
name, country, lat/lon, IANA timezone and population. It is loaded once and
cached. Two lookups are provided:

* ``search_cities`` — case-insensitive name/country search (the dropdown).
* ``nearest_city`` — great-circle nearest neighbour (the lat/long → city feature).

The module is UI-agnostic and contains no Kivy imports.
"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from .utils import distance_km

# Bundled data file (generated from GeoNames cities15000).
_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "cities.json")

_cities: Optional[List["City"]] = None


@dataclass
class City:
    """One place in the bundled database."""

    name: str
    country: str
    latitude: float
    longitude: float
    timezone: str        # IANA name, e.g. "Europe/London"
    population: int = 0

    @property
    def label(self) -> str:
        """Human-readable label for dropdowns, e.g. 'London, United Kingdom'."""
        if self.country:
            return f"{self.name}, {self.country}"
        return self.name


def load_cities() -> List[City]:
    """Load (and cache) the bundled city database."""
    global _cities
    if _cities is not None:
        return _cities
    with open(_DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    _cities = [
        City(
            name=c["name"],
            country=c["country"],
            latitude=c["lat"],
            longitude=c["lon"],
            timezone=c["tz"],
            population=c.get("pop", 0),
        )
        for c in raw
    ]
    return _cities


def search_cities(query: str, limit: int = 50) -> List[City]:
    """Case-insensitive search by city name or country.

    Prefix matches are ranked before substring matches; within each tier,
    higher population comes first. Returns up to ``limit`` results.
    """
    cities = load_cities()
    q = query.strip().lower()
    if not q:
        return cities[:limit]

    prefix, substring = [], []
    for c in cities:
        name_l = c.name.lower()
        country_l = c.country.lower()
        if name_l.startswith(q) or country_l.startswith(q):
            prefix.append(c)
        elif q in name_l or q in country_l:
            substring.append(c)

    def by_pop(c: City) -> int:
        return c.population

    prefix.sort(key=by_pop, reverse=True)
    substring.sort(key=by_pop, reverse=True)
    return (prefix + substring)[:limit]


def nearest_city(
    lat: float, lon: float, max_km: Optional[float] = None
) -> Optional[City]:
    """Return the closest city to ``(lat, lon)``.

    If ``max_km`` is given and the nearest city is farther than that, returns
    ``None`` instead.
    """
    cities = load_cities()
    if not cities:
        return None
    best: Optional[City] = None
    best_km = float("inf")
    for c in cities:
        d = distance_km(lat, lon, c.latitude, c.longitude)
        if d < best_km:
            best_km = d
            best = c
    if max_km is not None and best_km > max_km:
        return None
    return best