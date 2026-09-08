"""Tests for small curated star catalog loading and validation."""

import json
from astronomy.catalogs import (
    DEFAULT_MAX_STAR_RECORDS,
    builtin_bright_star_catalog,
    builtin_constellation_boundaries,
    builtin_constellation_labels,
    builtin_constellation_lines,
    load_star_catalog,
    spectral_color,
)
from astronomy.validation import validate_star_catalog_file


def test_external_catalog_loaders_support_small_csv_tsv_and_json(tmp_path):
    csv_path = tmp_path / "stars.csv"
    csv_path.write_text(
        "name,ra_hours,dec_degrees,magnitude,spectral_type,catalog_id\n"
        "CSV Star,1.5,2.0,1.2,G2V,HIP1\n",
        encoding="utf-8",
    )

    tsv_path = tmp_path / "stars.tsv"
    tsv_path.write_text(
        "name\tra_deg\tdec_deg\tmag\tsptype\tcatalog_id\n"
        "TSV Star\t30.0\t-10.0\t2.5\tK0III\tTYC1\n",
        encoding="utf-8",
    )

    json_path = tmp_path / "stars.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "name": "JSON Star",
                    "ra_hours": 3.0,
                    "dec_degrees": 5.0,
                    "magnitude": 0.5,
                    "spectral_type": "B1V",
                }
            ]
        ),
        encoding="utf-8",
    )

    csv_stars = load_star_catalog(str(csv_path))
    tsv_stars = load_star_catalog(str(tsv_path))
    json_stars = load_star_catalog(str(json_path))

    assert csv_stars[0].name == "CSV Star"
    assert abs(tsv_stars[0].ra_hours - 2.0) < 1e-9
    assert json_stars[0].spectral_type == "B1V"
    assert len(builtin_bright_star_catalog()) >= 80
    assert len(builtin_bright_star_catalog()) <= DEFAULT_MAX_STAR_RECORDS
    zodiac_stars = {star.name for star in builtin_bright_star_catalog()}
    assert {"Hamal", "Sheratan", "Acubens", "Algieba", "Porrima", "Sadalmelik", "Alrescha"} <= zodiac_stars
    zodiac_lines = [line for line in builtin_constellation_lines() if line.constellation in {"Aries", "Leo", "Sagittarius"}]
    assert len(zodiac_lines) >= 10
    zodiac_labels = {label.constellation for label in builtin_constellation_labels()}
    assert {"Aries", "Cancer", "Capricornus", "Pisces"} <= zodiac_labels
    zodiac_boundaries = [line for line in builtin_constellation_boundaries() if line.constellation == "Leo"]
    assert len(zodiac_boundaries) >= 4
    assert validate_star_catalog_file(None).valid is True


def test_catalog_validation_rejects_oversized_catalogs(tmp_path):
    path = tmp_path / "many-stars.json"
    payload = [
        {
            "name": f"Star {index}",
            "ra_hours": (index % 24),
            "dec_degrees": float((index % 80) - 40),
            "magnitude": float(index % 6),
            "spectral_type": "G2V",
        }
        for index in range(DEFAULT_MAX_STAR_RECORDS + 1)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_star_catalog_file(str(path), catalog_format="json", chunk_size=32)

    assert report.valid is False
    assert "curated bright-star limit" in report.messages[0]
    assert spectral_color("M2III") == (1.0, 0.72, 0.56)
