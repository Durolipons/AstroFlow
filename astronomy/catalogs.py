"""Star catalogs and constellation overlays for the sky renderer."""

from __future__ import annotations

import csv
import json
import os
import pickle
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

DEFAULT_MAX_STAR_RECORDS = 512


@dataclass(frozen=True)
class StarRecord:
    """Star record normalized for the sky renderer."""

    name: str
    ra_hours: float
    dec_degrees: float
    magnitude: float
    spectral_type: str = ""
    catalog: str = "custom"
    catalog_id: str = ""


@dataclass(frozen=True)
class ConstellationLine:
    """One line between two named stars."""

    constellation: str
    start_star: str
    end_star: str
    boundary: bool = False


@dataclass(frozen=True)
class ConstellationLabel:
    """Anchor for a constellation name."""

    constellation: str
    text: str
    ra_hours: float
    dec_degrees: float


def spectral_color(spectral_type: str) -> Tuple[float, float, float]:
    """Approximate star color by spectral class."""
    spectral_type = (spectral_type or "").strip().upper()
    if not spectral_type:
        return (1.0, 1.0, 1.0)
    families = {
        "O": (0.62, 0.74, 1.0),
        "B": (0.72, 0.80, 1.0),
        "A": (0.86, 0.90, 1.0),
        "F": (0.97, 0.97, 1.0),
        "G": (1.0, 0.96, 0.82),
        "K": (1.0, 0.84, 0.62),
        "M": (1.0, 0.72, 0.56),
    }
    return families.get(spectral_type[:1], (1.0, 1.0, 1.0))


def _builtin_star_catalog_path() -> str:
    return os.path.join(os.path.dirname(__file__), "data", "bright_stars.json")


def _builtin_fallback_star_catalog() -> List[StarRecord]:
    return [
        StarRecord("Sirius", 6.7525, -16.7161, -1.46, "A1V", "builtin", "HIP32349"),
        StarRecord("Canopus", 6.3992, -52.6957, -0.74, "A9II", "builtin", "HIP30438"),
        StarRecord("Arcturus", 14.2610, 19.1825, -0.05, "K1.5III", "builtin", "HIP69673"),
        StarRecord("Vega", 18.6156, 38.7837, 0.03, "A0V", "builtin", "HIP91262"),
        StarRecord("Capella", 5.2782, 45.9980, 0.08, "G8III", "builtin", "HIP24608"),
        StarRecord("Rigel", 5.2423, -8.2016, 0.12, "B8Ia", "builtin", "HIP24436"),
        StarRecord("Betelgeuse", 5.9195, 7.4070, 0.42, "M1Ia", "builtin", "HIP27989"),
        StarRecord("Altair", 19.8464, 8.8683, 0.77, "A7V", "builtin", "HIP97649"),
        StarRecord("Aldebaran", 4.5987, 16.5093, 0.86, "K5III", "builtin", "HIP21421"),
        StarRecord("Spica", 13.4199, -11.1614, 0.98, "B1III", "builtin", "HIP65474"),
    ]


def builtin_bright_star_catalog() -> List[StarRecord]:
    """Load the bundled bright-star catalog used by the sky panel."""
    try:
        rows = _load_json_rows(_builtin_star_catalog_path())
        stars = []
        for row in rows:
            if isinstance(row, StarRecord):
                stars.append(row)
            else:
                stars.append(_normalize_star_record(dict(row), "json"))
        return _dedupe_stars(stars + _zodiac_anchor_stars())
    except Exception:
        return _dedupe_stars(_builtin_fallback_star_catalog() + _zodiac_anchor_stars())


def builtin_constellation_lines() -> List[ConstellationLine]:
    """A compact set of recognizable constellation skeletons."""
    return [
        ConstellationLine("Orion", "Betelgeuse", "Bellatrix"),
        ConstellationLine("Orion", "Betelgeuse", "Alnilam"),
        ConstellationLine("Orion", "Bellatrix", "Mintaka"),
        ConstellationLine("Orion", "Mintaka", "Alnilam"),
        ConstellationLine("Orion", "Alnilam", "Alnitak"),
        ConstellationLine("Orion", "Alnilam", "Saiph"),
        ConstellationLine("Orion", "Saiph", "Rigel"),
        ConstellationLine("Ursa Major", "Dubhe", "Merak"),
        ConstellationLine("Ursa Major", "Merak", "Phecda"),
        ConstellationLine("Ursa Major", "Phecda", "Megrez"),
        ConstellationLine("Ursa Major", "Megrez", "Alioth"),
        ConstellationLine("Ursa Major", "Alioth", "Mizar"),
        ConstellationLine("Ursa Major", "Mizar", "Alkaid"),
        ConstellationLine("Summer Triangle", "Vega", "Deneb"),
        ConstellationLine("Summer Triangle", "Deneb", "Altair"),
        ConstellationLine("Summer Triangle", "Altair", "Vega"),
        ConstellationLine("Scorpius", "Antares", "Shaula"),
        ConstellationLine("Lyra", "Vega", "Sheliak"),
        ConstellationLine("Lyra", "Vega", "Sulafat"),
        ConstellationLine("Cygnus", "Deneb", "Sadr"),
        ConstellationLine("Cygnus", "Sadr", "Albireo"),
        ConstellationLine("Aquila", "Altair", "Tarazed"),
        ConstellationLine("Aquila", "Altair", "Alshain"),
        ConstellationLine("Cassiopeia", "Schedar", "Caph"),
        ConstellationLine("Cassiopeia", "Schedar", "Gamma Cassiopeiae"),
        ConstellationLine("Cassiopeia", "Gamma Cassiopeiae", "Ruchbah"),
        ConstellationLine("Cassiopeia", "Ruchbah", "Segin"),
        ConstellationLine("Pegasus", "Markab", "Scheat"),
        ConstellationLine("Pegasus", "Scheat", "Algenib"),
        ConstellationLine("Pegasus", "Algenib", "Enif"),
        *_zodiac_constellation_lines(),
    ]


def builtin_constellation_labels() -> List[ConstellationLabel]:
    return [
        ConstellationLabel("Orion", "Orion", 5.6, -1.0),
        ConstellationLabel("Ursa Major", "Ursa Major", 12.3, 56.0),
        ConstellationLabel("Summer Triangle", "Summer Triangle", 19.7, 31.0),
        ConstellationLabel("Lyra", "Lyra", 18.7, 36.0),
        ConstellationLabel("Cygnus", "Cygnus", 20.4, 40.0),
        ConstellationLabel("Aquila", "Aquila", 19.7, 2.0),
        ConstellationLabel("Cassiopeia", "Cassiopeia", 0.9, 59.0),
        ConstellationLabel("Pegasus", "Pegasus", 22.8, 20.0),
        ConstellationLabel("Crux", "Crux", 12.7, -60.0),
        *_zodiac_constellation_labels(),
    ]


def builtin_constellation_boundaries() -> List[ConstellationLine]:
    return [
        ConstellationLine("Orion", "Bellatrix", "Betelgeuse", boundary=True),
        ConstellationLine("Orion", "Betelgeuse", "Rigel", boundary=True),
        ConstellationLine("Orion", "Rigel", "Saiph", boundary=True),
        ConstellationLine("Orion", "Saiph", "Bellatrix", boundary=True),
        ConstellationLine("Ursa Major", "Dubhe", "Alkaid", boundary=True),
        ConstellationLine("Ursa Major", "Alkaid", "Merak", boundary=True),
        ConstellationLine("Pegasus", "Markab", "Scheat", boundary=True),
        ConstellationLine("Pegasus", "Scheat", "Algenib", boundary=True),
        ConstellationLine("Pegasus", "Algenib", "Enif", boundary=True),
        ConstellationLine("Pegasus", "Enif", "Markab", boundary=True),
        *_zodiac_constellation_boundaries(),
    ]


def _zodiac_anchor_stars() -> List[StarRecord]:
    return [
        StarRecord("Sheratan", 1.9107, 20.8080, 2.64, "A5V", "builtin", "HIP8903"),
        StarRecord("Mesarthim", 1.8926, 19.2939, 3.88, "B9V", "builtin", "HIP8832"),
        StarRecord("Botein", 2.4211, 19.9011, 4.35, "K2III", "builtin", "HIP11484"),
        StarRecord("Alcyone", 3.7914, 24.1051, 2.85, "B7III", "builtin", "HIP17702"),
        StarRecord("Ain", 4.4769, 19.1804, 3.53, "K0III", "builtin", "HIP20889"),
        StarRecord("Wasat", 7.3354, 21.9823, 3.53, "F0IV", "builtin", "HIP35550"),
        StarRecord("Tejat", 6.3827, 22.5136, 2.87, "M3III", "builtin", "HIP30343"),
        StarRecord("Acubens", 8.9748, 11.8577, 4.26, "A5V", "builtin", "HIP44066"),
        StarRecord("Asellus Borealis", 8.7214, 21.4685, 4.67, "A1IV", "builtin", "HIP42806"),
        StarRecord("Asellus Australis", 8.7448, 18.1542, 3.94, "K0III", "builtin", "HIP42911"),
        StarRecord("Altarf", 8.2753, 9.1856, 3.53, "K4III", "builtin", "HIP40526"),
        StarRecord("Adhafera", 10.2782, 23.4173, 3.43, "F0III", "builtin", "HIP50335"),
        StarRecord("Algieba", 10.3329, 19.8415, 2.08, "K1III", "builtin", "HIP50583"),
        StarRecord("Rasalas", 9.8794, 26.0069, 3.85, "K2III", "builtin", "HIP48455"),
        StarRecord("Zosma", 11.2373, 20.5237, 2.56, "A4V", "builtin", "HIP54872"),
        StarRecord("Chort", 11.2351, 15.4298, 3.34, "K0III", "builtin", "HIP54879"),
        StarRecord("Porrima", 12.6943, -1.4494, 2.74, "F0V", "builtin", "HIP61941"),
        StarRecord("Zaniah", 11.8449, -0.6670, 3.89, "A2V", "builtin", "HIP57757"),
        StarRecord("Heze", 13.5782, -0.5958, 3.38, "A1IV", "builtin", "HIP66249"),
        StarRecord("Acrab", 16.0906, -19.8055, 2.56, "B1V", "builtin", "HIP78820"),
        StarRecord("Dschubba", 16.0056, -22.6217, 2.29, "B0.3IV", "builtin", "HIP78401"),
        StarRecord("Jabbah", 16.3515, -19.4607, 2.89, "B2V", "builtin", "HIP80331"),
        StarRecord("Lesath", 17.5127, -37.2958, 2.70, "B2IV", "builtin", "HIP85696"),
        StarRecord("Sargas", 17.6219, -42.9978, 1.86, "F1II", "builtin", "HIP86228"),
        StarRecord("Ascella", 19.0435, -29.8801, 2.59, "F2IV", "builtin", "HIP93506"),
        StarRecord("Kaus Media", 18.3499, -29.8281, 2.72, "K1III", "builtin", "HIP89931"),
        StarRecord("Alnasl", 18.0968, -30.4241, 2.98, "B9.5III", "builtin", "HIP88635"),
        StarRecord("Dabih", 20.3502, -14.7814, 3.05, "K0II", "builtin", "HIP100345"),
        StarRecord("Nashira", 21.6682, -16.6623, 3.69, "B9.5V", "builtin", "HIP106985"),
        StarRecord("Deneb Algedi", 21.7840, -16.1273, 2.85, "A7III", "builtin", "HIP107556"),
        StarRecord("Algedi", 20.3009, -12.5449, 3.58, "G3III", "builtin", "HIP100064"),
        StarRecord("Sadalmelik", 22.0964, -0.3199, 2.95, "G2Ib", "builtin", "HIP109074"),
        StarRecord("Sadalsuud", 21.5259, -5.5712, 2.87, "G0Ib", "builtin", "HIP106278"),
        StarRecord("Skat", 22.9108, -15.8208, 3.27, "A3V", "builtin", "HIP112961"),
        StarRecord("Albali", 20.7946, -9.4958, 3.77, "F2IV", "builtin", "HIP102618"),
        StarRecord("Alrescha", 2.0341, 2.7638, 3.82, "A2IV", "builtin", "HIP9487"),
        StarRecord("Kullat Nunu", 1.5247, 15.3458, 3.62, "G7III", "builtin", "HIP7097"),
        StarRecord("Gamma Piscium", 23.2861, 3.2823, 3.69, "G8III", "builtin", "HIP114971"),
        StarRecord("Omega Piscium", 23.9885, 6.8633, 4.01, "K1III", "builtin", "HIP118268"),
    ]


def _zodiac_constellation_lines() -> List[ConstellationLine]:
    return [
        ConstellationLine("Aries", "Hamal", "Sheratan"),
        ConstellationLine("Aries", "Sheratan", "Mesarthim"),
        ConstellationLine("Aries", "Sheratan", "Botein"),
        ConstellationLine("Taurus", "Elnath", "Alcyone"),
        ConstellationLine("Taurus", "Alcyone", "Aldebaran"),
        ConstellationLine("Taurus", "Aldebaran", "Ain"),
        ConstellationLine("Gemini", "Castor", "Pollux"),
        ConstellationLine("Gemini", "Pollux", "Wasat"),
        ConstellationLine("Gemini", "Wasat", "Alhena"),
        ConstellationLine("Gemini", "Wasat", "Tejat"),
        ConstellationLine("Cancer", "Asellus Borealis", "Acubens"),
        ConstellationLine("Cancer", "Acubens", "Asellus Australis"),
        ConstellationLine("Cancer", "Asellus Australis", "Altarf"),
        ConstellationLine("Leo", "Rasalas", "Adhafera"),
        ConstellationLine("Leo", "Adhafera", "Algieba"),
        ConstellationLine("Leo", "Algieba", "Regulus"),
        ConstellationLine("Leo", "Algieba", "Zosma"),
        ConstellationLine("Leo", "Zosma", "Chort"),
        ConstellationLine("Leo", "Chort", "Denebola"),
        ConstellationLine("Virgo", "Vindemiatrix", "Zaniah"),
        ConstellationLine("Virgo", "Zaniah", "Porrima"),
        ConstellationLine("Virgo", "Porrima", "Spica"),
        ConstellationLine("Virgo", "Spica", "Heze"),
        ConstellationLine("Libra", "Zubenelgenubi", "Zubeneschamali"),
        ConstellationLine("Libra", "Zubeneschamali", "Spica"),
        ConstellationLine("Scorpius", "Acrab", "Dschubba"),
        ConstellationLine("Scorpius", "Dschubba", "Jabbah"),
        ConstellationLine("Scorpius", "Dschubba", "Antares"),
        ConstellationLine("Scorpius", "Antares", "Lesath"),
        ConstellationLine("Scorpius", "Lesath", "Shaula"),
        ConstellationLine("Scorpius", "Shaula", "Sargas"),
        ConstellationLine("Sagittarius", "Nunki", "Ascella"),
        ConstellationLine("Sagittarius", "Ascella", "Kaus Media"),
        ConstellationLine("Sagittarius", "Kaus Media", "Kaus Australis"),
        ConstellationLine("Sagittarius", "Kaus Australis", "Alnasl"),
        ConstellationLine("Capricornus", "Dabih", "Algedi"),
        ConstellationLine("Capricornus", "Algedi", "Nashira"),
        ConstellationLine("Capricornus", "Nashira", "Deneb Algedi"),
        ConstellationLine("Aquarius", "Sadalmelik", "Sadalsuud"),
        ConstellationLine("Aquarius", "Sadalsuud", "Albali"),
        ConstellationLine("Aquarius", "Sadalsuud", "Skat"),
        ConstellationLine("Pisces", "Kullat Nunu", "Alrescha"),
        ConstellationLine("Pisces", "Alrescha", "Gamma Piscium"),
        ConstellationLine("Pisces", "Gamma Piscium", "Omega Piscium"),
        ConstellationLine("Pisces", "Omega Piscium", "Fomalhaut"),
    ]


def _zodiac_constellation_labels() -> List[ConstellationLabel]:
    return [
        ConstellationLabel("Aries", "Aries", 2.0, 20.0),
        ConstellationLabel("Taurus", "Taurus", 4.4, 17.0),
        ConstellationLabel("Gemini", "Gemini", 7.2, 24.0),
        ConstellationLabel("Cancer", "Cancer", 8.8, 18.0),
        ConstellationLabel("Leo", "Leo", 10.8, 18.0),
        ConstellationLabel("Virgo", "Virgo", 13.1, 1.0),
        ConstellationLabel("Libra", "Libra", 15.0, -12.0),
        ConstellationLabel("Scorpius", "Scorpius", 16.8, -29.0),
        ConstellationLabel("Sagittarius", "Sagittarius", 18.7, -29.0),
        ConstellationLabel("Capricornus", "Capricornus", 21.0, -15.0),
        ConstellationLabel("Aquarius", "Aquarius", 21.8, -8.0),
        ConstellationLabel("Pisces", "Pisces", 0.9, 8.0),
    ]


def _zodiac_constellation_boundaries() -> List[ConstellationLine]:
    return [
        ConstellationLine("Aries", "Hamal", "Mesarthim", boundary=True),
        ConstellationLine("Aries", "Mesarthim", "Botein", boundary=True),
        ConstellationLine("Aries", "Botein", "Hamal", boundary=True),
        ConstellationLine("Taurus", "Elnath", "Alcyone", boundary=True),
        ConstellationLine("Taurus", "Alcyone", "Aldebaran", boundary=True),
        ConstellationLine("Taurus", "Aldebaran", "Ain", boundary=True),
        ConstellationLine("Taurus", "Ain", "Elnath", boundary=True),
        ConstellationLine("Gemini", "Castor", "Pollux", boundary=True),
        ConstellationLine("Gemini", "Pollux", "Tejat", boundary=True),
        ConstellationLine("Gemini", "Tejat", "Alhena", boundary=True),
        ConstellationLine("Gemini", "Alhena", "Castor", boundary=True),
        ConstellationLine("Cancer", "Asellus Borealis", "Acubens", boundary=True),
        ConstellationLine("Cancer", "Acubens", "Asellus Australis", boundary=True),
        ConstellationLine("Cancer", "Asellus Australis", "Altarf", boundary=True),
        ConstellationLine("Cancer", "Altarf", "Asellus Borealis", boundary=True),
        ConstellationLine("Leo", "Rasalas", "Adhafera", boundary=True),
        ConstellationLine("Leo", "Adhafera", "Regulus", boundary=True),
        ConstellationLine("Leo", "Regulus", "Chort", boundary=True),
        ConstellationLine("Leo", "Chort", "Denebola", boundary=True),
        ConstellationLine("Leo", "Denebola", "Zosma", boundary=True),
        ConstellationLine("Leo", "Zosma", "Rasalas", boundary=True),
        ConstellationLine("Virgo", "Vindemiatrix", "Zaniah", boundary=True),
        ConstellationLine("Virgo", "Zaniah", "Porrima", boundary=True),
        ConstellationLine("Virgo", "Porrima", "Spica", boundary=True),
        ConstellationLine("Virgo", "Spica", "Heze", boundary=True),
        ConstellationLine("Virgo", "Heze", "Vindemiatrix", boundary=True),
        ConstellationLine("Libra", "Zubenelgenubi", "Zubeneschamali", boundary=True),
        ConstellationLine("Libra", "Zubeneschamali", "Spica", boundary=True),
        ConstellationLine("Libra", "Spica", "Zubenelgenubi", boundary=True),
        ConstellationLine("Scorpius", "Acrab", "Dschubba", boundary=True),
        ConstellationLine("Scorpius", "Dschubba", "Antares", boundary=True),
        ConstellationLine("Scorpius", "Antares", "Shaula", boundary=True),
        ConstellationLine("Scorpius", "Shaula", "Sargas", boundary=True),
        ConstellationLine("Scorpius", "Sargas", "Acrab", boundary=True),
        ConstellationLine("Sagittarius", "Nunki", "Ascella", boundary=True),
        ConstellationLine("Sagittarius", "Ascella", "Kaus Australis", boundary=True),
        ConstellationLine("Sagittarius", "Kaus Australis", "Alnasl", boundary=True),
        ConstellationLine("Sagittarius", "Alnasl", "Nunki", boundary=True),
        ConstellationLine("Capricornus", "Dabih", "Algedi", boundary=True),
        ConstellationLine("Capricornus", "Algedi", "Nashira", boundary=True),
        ConstellationLine("Capricornus", "Nashira", "Deneb Algedi", boundary=True),
        ConstellationLine("Capricornus", "Deneb Algedi", "Dabih", boundary=True),
        ConstellationLine("Aquarius", "Sadalmelik", "Sadalsuud", boundary=True),
        ConstellationLine("Aquarius", "Sadalsuud", "Skat", boundary=True),
        ConstellationLine("Aquarius", "Skat", "Albali", boundary=True),
        ConstellationLine("Aquarius", "Albali", "Sadalmelik", boundary=True),
        ConstellationLine("Pisces", "Kullat Nunu", "Alrescha", boundary=True),
        ConstellationLine("Pisces", "Alrescha", "Gamma Piscium", boundary=True),
        ConstellationLine("Pisces", "Gamma Piscium", "Omega Piscium", boundary=True),
        ConstellationLine("Pisces", "Omega Piscium", "Kullat Nunu", boundary=True),
    ]


def _dedupe_stars(records: Iterable[StarRecord]) -> List[StarRecord]:
    merged: Dict[str, StarRecord] = {}
    for record in records:
        merged[record.name] = record
    return list(merged.values())


def _detect_format(path: str, explicit_format: Optional[str] = None) -> str:
    if explicit_format:
        return explicit_format.strip().lower()
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".csv": "csv",
        ".tsv": "tsv",
        ".json": "json",
        ".bin": "binary",
        ".pkl": "binary",
        ".pickle": "binary",
    }
    return mapping.get(ext, "csv")


def _first(mapping: Dict[str, object], *names: str):
    for name in names:
        if name in mapping and mapping[name] not in (None, ""):
            return mapping[name]
    return None


def _float_value(mapping: Dict[str, object], *names: str, scale: float = 1.0) -> float:
    value = _first(mapping, *names)
    if value is None:
        raise ValueError(f"Missing one of required numeric fields: {names}")
    return float(value) * scale


def _normalize_star_record(mapping: Dict[str, object], source: str) -> StarRecord:
    ra_hours = _first(mapping, "ra_hours", "raHour", "ra")
    if ra_hours is None:
        ra_degrees = _first(mapping, "ra_degrees", "ra_deg", "radeg", "RAdeg", "raj2000")
        if ra_degrees is None:
            raise ValueError("Missing RA field in star record.")
        ra_hours = float(ra_degrees) / 15.0
    else:
        ra_hours = float(ra_hours)

    dec_degrees = _float_value(mapping, "dec_degrees", "dec_deg", "dec", "DEdeg", "dej2000")
    magnitude = float(_first(mapping, "magnitude", "mag", "vmag", "Vmag", "vtmag", "btmag") or 0.0)
    spectral = str(_first(mapping, "spectral_type", "sptype", "spectral", "SpType") or "")
    name = str(
        _first(mapping, "name", "proper_name", "proper", "label", "hip_name", "tyc_name")
        or _first(mapping, "hip", "HIP", "tyc", "TYC", "id")
        or "Unnamed Star"
    )
    catalog_id = str(_first(mapping, "catalog_id", "hip", "HIP", "tyc", "TYC", "id") or "")
    catalog = str(_first(mapping, "catalog", "catalog_name", "source") or source)
    return StarRecord(
        name=name.strip(),
        ra_hours=ra_hours,
        dec_degrees=dec_degrees,
        magnitude=magnitude,
        spectral_type=spectral.strip(),
        catalog=catalog.strip().lower(),
        catalog_id=catalog_id.strip(),
    )


def _normalize_line_record(mapping: Dict[str, object]) -> ConstellationLine:
    return ConstellationLine(
        constellation=str(_first(mapping, "constellation", "iau_name", "name") or "").strip(),
        start_star=str(_first(mapping, "start_star", "start", "star1") or "").strip(),
        end_star=str(_first(mapping, "end_star", "end", "star2") or "").strip(),
        boundary=str(_first(mapping, "boundary", "is_boundary") or "").strip().lower() in {"1", "true", "yes"},
    )


def _normalize_label_record(mapping: Dict[str, object]) -> ConstellationLabel:
    ra_hours = _first(mapping, "ra_hours", "ra")
    if ra_hours is None:
        ra_hours = float(_float_value(mapping, "ra_degrees", "ra_deg", "radeg")) / 15.0
    return ConstellationLabel(
        constellation=str(_first(mapping, "constellation", "iau_name", "name") or "").strip(),
        text=str(_first(mapping, "text", "label", "constellation") or "").strip(),
        ra_hours=float(ra_hours),
        dec_degrees=_float_value(mapping, "dec_degrees", "dec_deg", "dec"),
    )


def _load_table_rows(path: str, delimiter: str) -> List[Dict[str, object]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def _load_json_rows(path: str) -> List[Dict[str, object]]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        if "stars" in payload:
            return list(payload["stars"])
        if "items" in payload:
            return list(payload["items"])
    if isinstance(payload, list):
        return list(payload)
    raise ValueError("Unsupported JSON star catalog payload.")


def _load_binary_rows(path: str):
    with open(path, "rb") as handle:
        payload = pickle.load(handle)
    if isinstance(payload, dict):
        if "stars" in payload:
            return list(payload["stars"])
        if "items" in payload:
            return list(payload["items"])
    if isinstance(payload, list):
        return list(payload)
    raise ValueError("Unsupported binary star catalog payload.")


def iter_star_catalog_chunks(
    path: str,
    catalog_format: Optional[str] = None,
    chunk_size: int = 2048,
    max_magnitude: Optional[float] = None,
) -> Iterator[List[StarRecord]]:
    """Yield star records in chunks for large external catalogs."""
    fmt = _detect_format(path, catalog_format)
    if fmt == "csv":
        rows = _load_table_rows(path, ",")
    elif fmt == "tsv":
        rows = _load_table_rows(path, "\t")
    elif fmt == "json":
        rows = _load_json_rows(path)
    elif fmt == "binary":
        rows = _load_binary_rows(path)
    else:
        raise ValueError(f"Unsupported star catalog format: {fmt}")

    chunk: List[StarRecord] = []
    for row in rows:
        if isinstance(row, StarRecord):
            star = row
        else:
            star = _normalize_star_record(dict(row), fmt)
        if max_magnitude is not None and star.magnitude > max_magnitude:
            continue
        chunk.append(star)
        if len(chunk) >= max(1, chunk_size):
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def load_star_catalog(
    path: str,
    catalog_format: Optional[str] = None,
    max_magnitude: Optional[float] = None,
    chunk_size: int = 2048,
    max_records: int = DEFAULT_MAX_STAR_RECORDS,
) -> List[StarRecord]:
    stars: List[StarRecord] = []
    for chunk in iter_star_catalog_chunks(
        path,
        catalog_format=catalog_format,
        chunk_size=chunk_size,
        max_magnitude=max_magnitude,
    ):
        stars.extend(chunk)
        if len(stars) > max_records:
            raise ValueError(
                f"Star catalog exceeds the curated limit of {max_records} records."
            )
    return _dedupe_stars(stars)


def load_star_catalog_csv(path: str) -> List[StarRecord]:
    return load_star_catalog(path, catalog_format="csv")


def load_constellation_lines_file(path: str, catalog_format: Optional[str] = None) -> List[ConstellationLine]:
    fmt = _detect_format(path, catalog_format)
    if fmt == "csv":
        rows = _load_table_rows(path, ",")
    elif fmt == "tsv":
        rows = _load_table_rows(path, "\t")
    elif fmt == "json":
        rows = _load_json_rows(path)
    else:
        raise ValueError(f"Unsupported constellation format: {fmt}")
    return [_normalize_line_record(dict(row)) for row in rows]


def load_constellation_labels_file(path: str, catalog_format: Optional[str] = None) -> List[ConstellationLabel]:
    fmt = _detect_format(path, catalog_format)
    if fmt == "csv":
        rows = _load_table_rows(path, ",")
    elif fmt == "tsv":
        rows = _load_table_rows(path, "\t")
    elif fmt == "json":
        rows = _load_json_rows(path)
    else:
        raise ValueError(f"Unsupported constellation label format: {fmt}")
    return [_normalize_label_record(dict(row)) for row in rows]


def load_catalog(
    records: Iterable[StarRecord] = (),
    path: Optional[str] = None,
    catalog_format: Optional[str] = None,
    max_magnitude: Optional[float] = None,
    include_builtin: bool = True,
    chunk_size: int = 2048,
    max_records: int = DEFAULT_MAX_STAR_RECORDS,
) -> List[StarRecord]:
    """Load the active star catalog."""
    merged = list(builtin_bright_star_catalog()) if include_builtin else []
    if path:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Star catalog file not found: {path}")
        merged.extend(
            load_star_catalog(
                path,
                catalog_format=catalog_format,
                max_magnitude=max_magnitude,
                chunk_size=chunk_size,
                max_records=max_records,
            )
        )
    merged.extend(list(records))
    if max_magnitude is not None:
        merged = [record for record in merged if record.magnitude <= max_magnitude]
    if len(merged) > max_records:
        merged = sorted(merged, key=lambda record: record.magnitude)[:max_records]
    return _dedupe_stars(merged)


def load_constellation_lines(
    records: Iterable[ConstellationLine] = (),
    path: Optional[str] = None,
    catalog_format: Optional[str] = None,
    include_builtin: bool = True,
) -> List[ConstellationLine]:
    merged = list(builtin_constellation_lines()) if include_builtin else []
    if path:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Constellation file not found: {path}")
        merged.extend(load_constellation_lines_file(path, catalog_format=catalog_format))
    merged.extend(list(records))
    return merged


def load_constellation_labels(
    records: Iterable[ConstellationLabel] = (),
    path: Optional[str] = None,
    catalog_format: Optional[str] = None,
    include_builtin: bool = True,
) -> List[ConstellationLabel]:
    merged = list(builtin_constellation_labels()) if include_builtin else []
    if path:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Constellation label file not found: {path}")
        merged.extend(load_constellation_labels_file(path, catalog_format=catalog_format))
    merged.extend(list(records))
    return merged


def load_constellation_boundaries(
    records: Iterable[ConstellationLine] = (),
    path: Optional[str] = None,
    catalog_format: Optional[str] = None,
    include_builtin: bool = True,
) -> List[ConstellationLine]:
    merged = list(builtin_constellation_boundaries()) if include_builtin else []
    if path:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Constellation boundary file not found: {path}")
        merged.extend(load_constellation_lines_file(path, catalog_format=catalog_format))
    merged.extend(list(records))
    return [line for line in merged if line.boundary]


def generate_star_batches(stars: Sequence[StarRecord], batch_size: int = 4096) -> List[List[StarRecord]]:
    """Chunk stars for GPU-oriented batching."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    return [
        list(stars[index:index + batch_size])
        for index in range(0, len(stars), batch_size)
    ]
