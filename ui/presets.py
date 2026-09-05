"""Famous-people birth-data presets for testing AstroFlow.

Each preset carries well-documented birth data (dates, times and places are
the classic Rodden-rated records used to verify astrology software). Loading a
preset fills the entire Home-screen form, so one tap produces a reproducible
chart.

Coordinates are city-centre values; timezones are IANA names (the bundled
``tzdata`` resolves the correct historical UTC offset for old birth dates).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    """One famous-person test fixture."""

    name: str          # person's name (goes into the Name field)
    date: str          # "YYYY-MM-DD" local birth date
    time: str          # "HH:MM" local birth time (24h)
    latlon: str        # "lat, lon" birth place
    timezone: str      # IANA zone name
    place: str         # human-readable birth place (for the popup row)

    @property
    def row_text(self) -> str:
        """Text shown in the preset-selection list."""
        return f"{self.name} — {self.place} ({self.date} {self.time})"


PRESETS = [
    Preset(
        name="Albert Einstein",
        date="1879-03-14", time="11:30",
        latlon="48.4011, 9.9876",
        timezone="Europe/Berlin",
        place="Ulm, Germany",
    ),
    Preset(
        name="Elvis Presley",
        date="1935-01-08", time="04:35",
        latlon="34.2576, -88.7034",
        timezone="America/Chicago",
        place="Tupelo, Mississippi, USA",
    ),
    Preset(
        name="Marilyn Monroe",
        date="1926-06-01", time="09:30",
        latlon="34.0522, -118.2437",
        timezone="America/Los_Angeles",
        place="Los Angeles, California, USA",
    ),
    Preset(
        name="John F. Kennedy",
        date="1917-05-29", time="15:00",
        latlon="42.3324, -71.1213",
        timezone="America/New_York",
        place="Brookline, Massachusetts, USA",
    ),
    Preset(
        name="Winston Churchill",
        date="1874-11-30", time="01:30",
        latlon="51.8414, -1.3598",
        timezone="Europe/London",
        place="Woodstock (Blenheim Palace), England",
    ),
]


def get_preset(name: str):
    """Return the ``Preset`` whose person name matches (case-insensitive)."""
    for p in PRESETS:
        if p.name.lower() == name.lower():
            return p
    return None
