"""Optional external geocoding (forward + reverse) for rare / new places.

The bundled ``core.cities`` database covers ~2,000 major places and is always
used first (offline, instant). When a place is *not* in the local DB, an
optional online geocoder can be consulted. The default implementation uses
OpenStreetMap's Nominatim service (free, no API key) via the standard library
— no extra dependency.

Online lookups are OFF by default and only used when explicitly enabled, so
the app stays fully offline unless the user opts in.

NOTE: Nominatim returns a name + lat/lon but NOT an IANA timezone, so the
timezone of an externally-geocoded result is estimated from the nearest
bundled city and should be verified by the user.
"""

import json
import urllib.parse
import urllib.request
from typing import List, Optional, Protocol

from .cities import City, nearest_city, search_cities


class GeoLookup(Protocol):
    """Interface for a place lookup backend."""

    def search(self, query: str, limit: int = 5) -> List[City]:
        """Forward geocode a name query into a list of candidates."""
        ...

    def reverse(self, lat: float, lon: float) -> Optional[City]:
        """Reverse geocode a coordinate into the nearest named place."""
        ...


class LocalCitiesLookup:
    """Offline lookup against the bundled city database."""

    def search(self, query: str, limit: int = 5) -> List[City]:
        return search_cities(query, limit=limit)

    def reverse(self, lat: float, lon: float) -> Optional[City]:
        # Within 500 km of a known city; otherwise we genuinely don't know.
        return nearest_city(lat, lon, max_km=500.0)


class NominatimLookup:
    """Online lookup via OpenStreetMap Nominatim (free, no API key).

    Usage policy: https://operations.osmfoundation.org/policies/nominatim/
    — max 1 request/second, provide a valid User-Agent, no heavy use.
    """

    SEARCH_URL = "https://nominatim.openstreetmap.org/search"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

    def __init__(self, user_agent: str = "AstroFlow/0.1 (student project)",
                 timeout: float = 5.0):
        self.user_agent = user_agent
        self.timeout = timeout

    def _fetch(self, url: str) -> Optional[list | dict]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            # Any network/parse failure → graceful offline fallback.
            return None

    def search(self, query: str, limit: int = 5) -> List[City]:
        params = urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": limit, "addressdetails": 1}
        )
        data = self._fetch(f"{self.SEARCH_URL}?{params}")
        if not isinstance(data, list):
            return []
        results = []
        for item in data:
            try:
                results.append(self._item_to_city(item))
            except (KeyError, ValueError, TypeError):
                continue
        return results

    def reverse(self, lat: float, lon: float) -> Optional[City]:
        params = urllib.parse.urlencode(
            {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1}
        )
        data = self._fetch(f"{self.REVERSE_URL}?{params}")
        if not isinstance(data, dict):
            return None
        try:
            return self._item_to_city(data)
        except (KeyError, ValueError, TypeError):
            return None

    def _item_to_city(self, item: dict) -> City:
        """Convert a Nominatim result into a ``City`` (timezone estimated)."""
        name = item.get("display_name", "").split(",")[0].strip()
        lat = float(item["lat"])
        lon = float(item["lon"])
        address = item.get("address", {})
        country = address.get("country", "")
        # Nominatim does not return a timezone: estimate from the nearest
        # bundled city. Flagged as approximate for the user to verify.
        tz = "UTC"
        nearest = nearest_city(lat, lon)
        if nearest:
            tz = nearest.timezone
        return City(
            name=name, country=country, latitude=lat, longitude=lon,
            timezone=tz, population=0,
        )


class CompositeLookup:
    """Try the local DB first; only consult the online backend on a miss.

    Network errors in the online backend are swallowed so the app degrades
    gracefully to offline behaviour.
    """

    def __init__(self, local: GeoLookup = None, online: GeoLookup = None):
        self.local = local or LocalCitiesLookup()
        self.online = online  # may be None → local-only

    def search(self, query: str, limit: int = 5) -> List[City]:
        local_results = self.local.search(query, limit=limit)
        if local_results:
            return local_results
        if self.online is not None:
            online_results = self.online.search(query, limit=limit)
            if online_results:
                return online_results
        return []

    def reverse(self, lat: float, lon: float) -> Optional[City]:
        local_result = self.local.reverse(lat, lon)
        if local_result is not None:
            return local_result
        if self.online is not None:
            online_result = self.online.reverse(lat, lon)
            if online_result is not None:
                return online_result
        return None