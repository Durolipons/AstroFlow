"""Configuration helpers for the astronomy extension layer."""

from __future__ import annotations

import os
from dataclasses import dataclass


def default_star_catalog_path() -> str:
    return os.path.join(os.path.dirname(__file__), "data", "bright_stars.json")


def default_milky_way_texture_path() -> str:
    """Prefer the highest-resolution WISE panorama present in the data folder.

    The dome samples the texture at its native resolution, so dropping a
    2048- or 4096-wide export of PIA15482 into ``astronomy/data`` upgrades the
    milky way sharpness with no code changes (same image, same alignment).
    """
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    for name in (
        "wise_full_sky_pia15482_4096.jpg",
        "wise_full_sky_pia15482_2048.jpg",
        "wise_full_sky_pia15482_1024.jpg",
    ):
        candidate = os.path.join(data_dir, name)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(data_dir, "wise_full_sky_pia15482_1024.jpg")


def _read_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _read_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class DE441KernelConfig:
    """Runtime kernel-file configuration."""

    path: str = ""
    env_var: str = "ASTROFLOW_DE441_KERNEL"

    @classmethod
    def from_env(cls) -> "DE441KernelConfig":
        return cls(path=os.environ.get("ASTROFLOW_DE441_KERNEL", ""))


@dataclass(frozen=True)
class SkySceneConfig:
    """Renderer and sky-screen settings for the minimal astrology helper."""

    default_backend: str = "horizons"
    star_catalog_path: str = ""
    star_catalog_format: str = ""
    milky_way_texture_path: str = ""
    milky_way_longitude_center: float = 0.5
    milky_way_reverse_longitude: bool = False
    milky_way_flip_v: bool = False
    constellation_path: str = ""
    constellation_label_path: str = ""
    constellation_boundary_path: str = ""
    animation_step_minutes: float = 10.0
    animation_interval_seconds: float = 1.0
    animation_speed_multiplier: float = 1.0
    refresh_interval_seconds: float = 30.0
    realtime_animation: bool = True
    auto_play: bool = False
    use_opengl_renderer: bool = False
    max_star_magnitude: float = 4.8
    lod_star_limit: int = 512
    lazy_chunk_size: int = 2048
    show_constellations: bool = True
    show_constellation_labels: bool = True
    show_constellation_boundaries: bool = True
    show_horizon: bool = True
    show_horizon_labels: bool = True
    show_equator: bool = True
    show_zodiac: bool = True
    show_dome: bool = True
    show_milky_way: bool = True
    show_grid: bool = False
    show_star_names: bool = False
    show_planet_labels: bool = True
    show_planet_trails: bool = False
    show_aspects: bool = True

    @classmethod
    def from_env(cls) -> "SkySceneConfig":
        default_backend = os.environ.get("ASTROFLOW_SKY_BACKEND", "horizons").strip().lower()
        if default_backend not in {"horizons", "de441"}:
            default_backend = "horizons"
        return cls(
            default_backend=default_backend,
            star_catalog_path=os.environ.get("ASTROFLOW_STAR_CATALOG", default_star_catalog_path()),
            star_catalog_format=os.environ.get("ASTROFLOW_STAR_CATALOG_FORMAT", ""),
            milky_way_texture_path=os.environ.get(
                "ASTROFLOW_MILKY_WAY_TEXTURE",
                default_milky_way_texture_path(),
            ),
            milky_way_longitude_center=_read_float("ASTROFLOW_MILKY_WAY_LONGITUDE_CENTER", 0.5),
            milky_way_reverse_longitude=_read_bool("ASTROFLOW_MILKY_WAY_REVERSE_LONGITUDE", False),
            milky_way_flip_v=_read_bool("ASTROFLOW_MILKY_WAY_FLIP_V", False),
            constellation_path=os.environ.get("ASTROFLOW_CONSTELLATIONS", ""),
            constellation_label_path=os.environ.get("ASTROFLOW_CONSTELLATION_LABELS", ""),
            constellation_boundary_path=os.environ.get("ASTROFLOW_CONSTELLATION_BOUNDARIES", ""),
            animation_step_minutes=_read_float("ASTROFLOW_SKY_ANIMATION_STEP_MINUTES", 10.0),
            animation_interval_seconds=_read_float("ASTROFLOW_SKY_ANIMATION_INTERVAL_SECONDS", 1.0),
            animation_speed_multiplier=_read_float("ASTROFLOW_SKY_ANIMATION_SPEED", 1.0),
            refresh_interval_seconds=_read_float("ASTROFLOW_SKY_REFRESH_SECONDS", 30.0),
            realtime_animation=_read_bool("ASTROFLOW_SKY_REALTIME_ANIMATION", True),
            auto_play=_read_bool("ASTROFLOW_SKY_AUTOPLAY", False),
            use_opengl_renderer=_read_bool("ASTROFLOW_SKY_USE_OPENGL", False),
            max_star_magnitude=_read_float("ASTROFLOW_SKY_MAX_STAR_MAG", 4.8),
            lod_star_limit=_read_int("ASTROFLOW_SKY_LOD_STAR_LIMIT", 512),
            lazy_chunk_size=_read_int("ASTROFLOW_SKY_LAZY_CHUNK_SIZE", 2048),
            show_constellations=_read_bool("ASTROFLOW_SKY_SHOW_CONSTELLATIONS", True),
            show_constellation_labels=_read_bool("ASTROFLOW_SKY_SHOW_CONSTELLATION_LABELS", True),
            show_constellation_boundaries=_read_bool("ASTROFLOW_SKY_SHOW_CONSTELLATION_BOUNDARIES", True),
            show_horizon=_read_bool("ASTROFLOW_SKY_SHOW_HORIZON", True),
            show_horizon_labels=_read_bool("ASTROFLOW_SKY_SHOW_HORIZON_LABELS", True),
            show_equator=_read_bool("ASTROFLOW_SKY_SHOW_EQUATOR", True),
            show_zodiac=_read_bool("ASTROFLOW_SKY_SHOW_ZODIAC", True),
            show_dome=_read_bool("ASTROFLOW_SKY_SHOW_DOME", True),
            show_milky_way=_read_bool("ASTROFLOW_SKY_SHOW_MILKY_WAY", True),
            show_grid=_read_bool("ASTROFLOW_SKY_SHOW_GRID", False),
            show_star_names=_read_bool("ASTROFLOW_SKY_SHOW_STAR_NAMES", False),
            show_planet_labels=_read_bool("ASTROFLOW_SKY_SHOW_PLANET_LABELS", True),
            show_planet_trails=_read_bool("ASTROFLOW_SKY_SHOW_PLANET_TRAILS", False),
            show_aspects=_read_bool("ASTROFLOW_SKY_SHOW_ASPECTS", True),
        )


@dataclass(frozen=True)
class AstronomyRuntimeConfig:
    """Top-level astronomy runtime config."""

    de441: DE441KernelConfig
    sky: SkySceneConfig


def load_runtime_config() -> AstronomyRuntimeConfig:
    """Read astronomy configuration from the environment."""
    return AstronomyRuntimeConfig(
        de441=DE441KernelConfig.from_env(),
        sky=SkySceneConfig.from_env(),
    )
