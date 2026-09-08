"""Tests for astronomy runtime configuration helpers."""

from astronomy.config import default_milky_way_texture_path, default_star_catalog_path, load_runtime_config


def test_runtime_config_defaults_to_curated_bright_star_catalog(monkeypatch):
    monkeypatch.delenv("ASTROFLOW_STAR_CATALOG", raising=False)
    monkeypatch.delenv("ASTROFLOW_MILKY_WAY_TEXTURE", raising=False)

    config = load_runtime_config()

    assert config.sky.star_catalog_path == default_star_catalog_path()
    assert config.sky.milky_way_texture_path == default_milky_way_texture_path()


def test_runtime_config_reads_environment(monkeypatch):
    monkeypatch.setenv("ASTROFLOW_DE441_KERNEL", r"C:\kernels\de441.bsp")
    monkeypatch.setenv("ASTROFLOW_SKY_BACKEND", "de441")
    monkeypatch.setenv("ASTROFLOW_STAR_CATALOG", r"C:\data\stars.csv")
    monkeypatch.setenv("ASTROFLOW_STAR_CATALOG_FORMAT", "csv")
    monkeypatch.setenv("ASTROFLOW_MILKY_WAY_TEXTURE", r"C:\data\wise.jpg")
    monkeypatch.setenv("ASTROFLOW_CONSTELLATIONS", r"C:\data\constellations.csv")
    monkeypatch.setenv("ASTROFLOW_CONSTELLATION_LABELS", r"C:\data\constellation_labels.json")
    monkeypatch.setenv("ASTROFLOW_CONSTELLATION_BOUNDARIES", r"C:\data\constellation_boundaries.csv")
    monkeypatch.setenv("ASTROFLOW_SKY_ANIMATION_STEP_MINUTES", "30")
    monkeypatch.setenv("ASTROFLOW_SKY_ANIMATION_INTERVAL_SECONDS", "2")
    monkeypatch.setenv("ASTROFLOW_SKY_ANIMATION_SPEED", "4")
    monkeypatch.setenv("ASTROFLOW_SKY_REFRESH_SECONDS", "45")
    monkeypatch.setenv("ASTROFLOW_SKY_REALTIME_ANIMATION", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_AUTOPLAY", "true")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_CONSTELLATIONS", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_CONSTELLATION_LABELS", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_CONSTELLATION_BOUNDARIES", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_HORIZON", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_EQUATOR", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_ZODIAC", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_DOME", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_MILKY_WAY", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_PLANET_LABELS", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_PLANET_TRAILS", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_SHOW_ASPECTS", "false")
    monkeypatch.setenv("ASTROFLOW_SKY_MAX_STAR_MAG", "3.2")
    monkeypatch.setenv("ASTROFLOW_SKY_LOD_STAR_LIMIT", "120")
    monkeypatch.setenv("ASTROFLOW_SKY_LAZY_CHUNK_SIZE", "512")

    config = load_runtime_config()

    assert config.de441.path.endswith("de441.bsp")
    assert config.sky.default_backend == "de441"
    assert config.sky.star_catalog_path.endswith("stars.csv")
    assert config.sky.star_catalog_format == "csv"
    assert config.sky.milky_way_texture_path.endswith("wise.jpg")
    assert config.sky.constellation_path.endswith("constellations.csv")
    assert config.sky.constellation_label_path.endswith("constellation_labels.json")
    assert config.sky.constellation_boundary_path.endswith("constellation_boundaries.csv")
    assert config.sky.animation_step_minutes == 30.0
    assert config.sky.animation_interval_seconds == 2.0
    assert config.sky.animation_speed_multiplier == 4.0
    assert config.sky.refresh_interval_seconds == 45.0
    assert config.sky.realtime_animation is False
    assert config.sky.auto_play is True
    assert config.sky.use_opengl_renderer is False
    assert config.sky.show_constellations is False
    assert config.sky.show_constellation_labels is False
    assert config.sky.show_constellation_boundaries is False
    assert config.sky.show_horizon is False
    assert config.sky.show_horizon_labels is True
    assert config.sky.show_equator is False
    assert config.sky.show_zodiac is False
    assert config.sky.show_dome is False
    assert config.sky.show_milky_way is False
    assert config.sky.show_grid is False
    assert config.sky.show_star_names is False
    assert config.sky.show_planet_labels is False
    assert config.sky.show_planet_trails is False
    assert config.sky.show_aspects is False
    assert config.sky.max_star_magnitude == 3.2
    assert config.sky.lod_star_limit == 120
    assert config.sky.lazy_chunk_size == 512
