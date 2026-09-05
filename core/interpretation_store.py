"""Editable interpretation library for AstroFlow.

The engine keeps its interpretation text in a small JSON-backed library so
professional astrologers can rewrite the wording in the UI without touching the
calculation code. The module is UI-agnostic: callers choose the storage path
and can use the same library from Kivy, CLI, or tests.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional


def _default_sign_text() -> Dict[str, str]:
    return {
        "Aries": "initiative, courage, directness",
        "Taurus": "steadiness, sensuality, patience",
        "Gemini": "curiosity, adaptability, communication",
        "Cancer": "nurturance, memory, emotional depth",
        "Leo": "creativity, warmth, self-expression",
        "Virgo": "precision, service, analysis",
        "Libra": "harmony, fairness, relationship",
        "Scorpio": "intensity, transformation, insight",
        "Sagittarius": "philosophy, optimism, exploration",
        "Capricorn": "ambition, discipline, endurance",
        "Aquarius": "innovation, independence, ideals",
        "Pisces": "empathy, imagination, intuition",
    }


def _default_aspect_text() -> Dict[str, str]:
    return {
        "Conjunction": "intensifies and fuses the two energies",
        "Opposition": "sets up a dynamic tension that needs balancing",
        "Trine": "flows easily and supports smooth expression",
        "Square": "creates friction that pushes for constructive action",
        "Sextile": "offers a helpful opportunity that needs a nudge",
        "Quincunx": "asks for subtle adjustment and re-orientation",
        "Semisextile": "gradually awakens a minor but useful awareness",
        "Semisquare": "produces mild irritation that signals fine-tuning",
        "Sesquiquadrate": "accumulates small frictions that demand review",
    }


def _default_planet_role() -> Dict[str, str]:
    return {
        "Sun": "core identity & vitality",
        "Moon": "emotional needs & instincts",
        "Mercury": "thinking, learning & communication",
        "Venus": "values, attraction & relating",
        "Mars": "drive, action & assertion",
        "Jupiter": "growth, optimism & opportunity",
        "Saturn": "structure, responsibility & limits",
        "Uranus": "change, freedom & originality",
        "Neptune": "dreams, imagination & transcendence",
        "Pluto": "power, transformation & regeneration",
    }


def _default_sky_aspect_text() -> Dict[str, str]:
    """Current-sky (general) phrasing for aspects between moving planets."""
    return {
        "Conjunction": "fuses the two energies while they travel together",
        "Opposition": "pulls between two poles that both want airtime today",
        "Trine": "flows easily and keeps the day moving smoothly",
        "Square": "adds productive friction that asks for action",
        "Sextile": "opens a small window of opportunity - take the nudge",
        "Quincunx": "asks for a small adjustment between unlike needs",
        "Semisextile": "quietly shifts the mood a half-step",
        "Semisquare": "sprinkles mild irritation that highlights fine-tuning",
        "Sesquiquadrate": "builds a low hum of tension worth reviewing",
    }


def _default_planet_sky_note() -> Dict[str, str]:
    """Per-planet note about what it rules in the general sky at the moment."""
    return {
        "Sun": "sets the day's vitality and focus",
        "Moon": "the fastest mover - its sign colours the mood of the hours",
        "Mercury": "shapes conversations, plans and errands",
        "Venus": "colours tastes, money and how people get along",
        "Mars": "fuels energy, drive and reactions",
        "Jupiter": "widens opportunities over weeks and months",
        "Saturn": "sets the slower structure and duties of the season",
        "Uranus": "stirs sudden change in the background",
        "Neptune": "dissolves boundaries in dreams and moods",
        "Pluto": "works beneath the surface across years",
    }


def _default_sign_sky_note() -> Dict[str, str]:
    return {
        "Aries": "the sky pushes for bold starts and quick decisions",
        "Taurus": "the sky favours steadiness, comfort and tangible results",
        "Gemini": "the sky is curious, chatty and easily distracted",
        "Cancer": "feelings run close to the surface; home matters",
        "Leo": "the sky wants warmth, play and self-expression",
        "Virgo": "details want sorting; useful, precise work flows",
        "Libra": "the sky leans toward balance, beauty and agreement",
        "Scorpio": "undercurrents run deep; truth and trust are themes",
        "Sagittarius": "the sky expands — travel, learning, big pictures",
        "Capricorn": "structure and long-game ambition get rewarded",
        "Aquarius": "ideas spark; the unusual and communal are favoured",
        "Pisces": "imagination and empathy dissolve the edges",
    }


@dataclass
class InterpretationLibrary:
    """Editable interpretation text grouped by topic."""

    sign_text: Dict[str, str] = field(default_factory=_default_sign_text)
    aspect_text: Dict[str, str] = field(default_factory=_default_aspect_text)
    planet_role: Dict[str, str] = field(default_factory=_default_planet_role)
    planet_sky_note: Dict[str, str] = field(default_factory=_default_planet_sky_note)
    sky_aspect_text: Dict[str, str] = field(default_factory=_default_sky_aspect_text)
    sign_sky_note: Dict[str, str] = field(default_factory=_default_sign_sky_note)
    sky_aspect_text: Dict[str, str] = field(
        default_factory=_default_sky_aspect_text)
    planet_sky_note: Dict[str, str] = field(
        default_factory=_default_planet_sky_note)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "InterpretationLibrary":
        """Create a library from loaded JSON, merging with defaults."""
        library = cls()
        if not isinstance(data, dict):
            return library

        for field_name in ("sign_text", "aspect_text", "planet_role",
                           "sky_aspect_text", "planet_sky_note",
                           "sign_sky_note"):
            incoming = data.get(field_name)
            if isinstance(incoming, dict):
                target = getattr(library, field_name)
                for key, value in incoming.items():
                    if isinstance(key, str) and isinstance(value, str):
                        target[key] = value
        return library

    def to_dict(self) -> dict:
        """Serialize the library to a JSON-compatible mapping."""
        return {
            "sign_text": dict(self.sign_text),
            "aspect_text": dict(self.aspect_text),
            "planet_role": dict(self.planet_role),
            "sky_aspect_text": dict(self.sky_aspect_text),
            "planet_sky_note": dict(self.planet_sky_note),
            "sign_sky_note": dict(self.sign_sky_note),
        }


_DEFAULT_LIBRARY_PATH = os.path.join(
    os.path.expanduser("~"),
    ".astroflow",
    "interpretations.json",
)
_LIBRARY_PATH = _DEFAULT_LIBRARY_PATH
_LIBRARY_CACHE: Optional[InterpretationLibrary] = None


def configure_interpretation_library(path: Optional[str]) -> None:
    """Set the active interpretation JSON file and clear any cached copy."""
    global _LIBRARY_PATH, _LIBRARY_CACHE
    _LIBRARY_PATH = path or _DEFAULT_LIBRARY_PATH
    _LIBRARY_CACHE = None


def interpretation_library_path() -> str:
    """Return the path currently used for the editable interpretation store."""
    return _LIBRARY_PATH


def default_interpretation_library() -> InterpretationLibrary:
    """Return a fresh library populated with AstroFlow's built-in defaults."""
    return InterpretationLibrary()


def load_interpretation_library(path: Optional[str] = None) -> InterpretationLibrary:
    """Load the editable interpretation library from disk.

    If the file does not exist, the built-in defaults are returned.
    """
    global _LIBRARY_CACHE
    active_path = path or _LIBRARY_PATH
    if _LIBRARY_CACHE is not None and active_path == _LIBRARY_PATH:
        return _LIBRARY_CACHE

    if not os.path.exists(active_path):
        library = default_interpretation_library()
        if active_path == _LIBRARY_PATH:
            _LIBRARY_CACHE = library
        return library

    with open(active_path, encoding="utf-8") as handle:
        raw = json.load(handle)
    library = InterpretationLibrary.from_dict(raw)
    if active_path == _LIBRARY_PATH:
        _LIBRARY_CACHE = library
    return library


def save_interpretation_library(
    library: InterpretationLibrary,
    path: Optional[str] = None,
) -> None:
    """Persist a library to disk and refresh the in-memory cache."""
    global _LIBRARY_CACHE
    active_path = path or _LIBRARY_PATH
    folder = os.path.dirname(active_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(active_path, "w", encoding="utf-8") as handle:
        json.dump(library.to_dict(), handle, indent=2, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
    if active_path == _LIBRARY_PATH:
        _LIBRARY_CACHE = library


def ensure_interpretation_library(path: Optional[str] = None) -> str:
    """Create the interpretation file with defaults if it does not exist."""
    active_path = path or _LIBRARY_PATH
    if not os.path.exists(active_path):
        save_interpretation_library(default_interpretation_library(), active_path)
    return active_path

