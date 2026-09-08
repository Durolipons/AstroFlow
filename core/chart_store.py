"""Persistent storage for user-saved birth charts.

UI-agnostic: writes a JSON list of chart records (``charts.json``) into the
Kivy ``user_data_dir``. The access pattern (configure / load / save / delete /
path + in-memory cache) mirrors ``core.interpretation_store`` so both stores
behave consistently and stay UI-free.

Only ``BirthData`` is persisted -- natal charts are recomputed deterministically
from it on load, which keeps the file tiny and avoids shipping stale ephemeris
output.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from .models import BirthData


def _default_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".astroflow", "charts.json")


_PATH: str = _default_path()
_CACHE: Optional[List["SavedChart"]] = None


@dataclass
class SavedChart:
    """One persisted birth-data record with bookkeeping fields."""

    id: str
    name: str
    created: str                          # ISO-8601 UTC creation timestamp
    data: dict                            # serialized BirthData (from to_dict)

    @property
    def birth_data(self) -> BirthData:
        """Reconstruct the live ``BirthData`` from the stored mapping."""
        return BirthData.from_dict(self.data)

    def summary(self) -> str:
        """One-line human summary for list views."""
        bd = self.birth_data
        loc = bd.location
        place = loc.name or f"{loc.latitude:+.2f}, {loc.longitude:+.2f}"
        return f"{bd.birth_datetime:%Y-%m-%d %H:%M}  {place}"


def configure_chart_store(path: Optional[str]) -> None:
    """Set the active charts JSON file and clear any cached records."""
    global _PATH, _CACHE
    _PATH = path or _default_path()
    _CACHE = None


def chart_store_path() -> str:
    """Return the path currently used for the saved-charts file."""
    return _PATH


def load_saved_charts() -> List[SavedChart]:
    """Load all saved charts from disk (cached for the process lifetime)."""
    global _CACHE
    if _CACHE is not None:
        return list(_CACHE)

    charts: List[SavedChart] = []
    if os.path.exists(_PATH):
        try:
            with open(_PATH, encoding="utf-8") as handle:
                raw = json.load(handle)
        except (json.JSONDecodeError, OSError):
            raw = []
        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict) and "id" in entry and "data" in entry:
                    charts.append(_entry_to_chart(entry))
    charts.sort(key=lambda c: c.created, reverse=True)
    _CACHE = charts
    return list(_CACHE)


def save_chart(birth_data: BirthData, override_name: Optional[str] = None) -> SavedChart:
    """Persist (or update) a birth chart.

    Deduplication is by name: saving a name that already exists overwrites that
    record (keeping its id/created stamp) rather than creating a duplicate.
    Returns the record that was saved.
    """
    charts = load_saved_charts()
    name = (override_name or "").strip() or (birth_data.name or "Unnamed")
    now = datetime.now(timezone.utc).isoformat()

    target_idx = _index_by_name(charts, name)
    serialized = birth_data.to_dict()
    if target_idx is not None:
        existing = charts[target_idx]
        existing.data = serialized
        existing.name = name
        if not existing.created:
            existing.created = now
        result = existing
    else:
        result = SavedChart(
            id=uuid.uuid4().hex,
            name=name,
            created=now,
            data=serialized,
        )
        charts.append(result)

    _persist(charts)
    return result


def find_chart(chart_id: str) -> Optional[SavedChart]:
    """Look up a single chart by id (from the cache)."""
    for chart in load_saved_charts():
        if chart.id == chart_id:
            return chart
    return None


def delete_chart(chart_id: str) -> bool:
    """Delete a chart by id. Returns True if something was removed."""
    charts = load_saved_charts()
    remaining = [c for c in charts if c.id != chart_id]
    if len(remaining) == len(charts):
        return False
    _persist(remaining)
    return True


def clear_chart_store() -> None:
    """Delete every saved chart and reset the cache (used mainly by tests)."""
    global _CACHE
    _CACHE = []
    try:
        if os.path.exists(_PATH):
            os.remove(_PATH)
    except OSError:
        pass

# --------------------------------------------------------------------------- #
# internals
# --------------------------------------------------------------------------- #
def _entry_to_chart(entry: dict) -> SavedChart:
    name = entry.get("name") or entry.get("data", {}).get("name") or "Unnamed"
    return SavedChart(
        id=entry.get("id", uuid.uuid4().hex),
        name=name,
        created=entry.get("created", ""),
        data=entry.get("data", {}),
    )


def _index_by_name(charts: List[SavedChart], name: str) -> Optional[int]:
    lowered = name.strip().lower()
    if not lowered:
        return None
    for i, c in enumerate(charts):
        if c.name.strip().lower() == lowered:
            return i
    return None


def _persist(charts: List[SavedChart]) -> None:
    """Write the chart list to disk and refresh the in-memory cache."""
    global _CACHE
    folder = os.path.dirname(_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    payload = [
        {"id": c.id, "name": c.name, "created": c.created, "data": c.data}
        for c in charts
    ]
    with open(_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
    _CACHE = list(charts)

