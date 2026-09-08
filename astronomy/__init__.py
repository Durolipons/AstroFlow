"""Astronomy extensions for AstroFlow.

This package runs alongside the existing astrology engine. It does not replace
or restructure the Swiss Ephemeris workflow; instead it provides:

* time normalization helpers
* pluggable JPL-backed astronomy data providers
* adapters that convert astronomy output into display-compatible chart data
* a separate OpenGL sky renderer hosted by Kivy
"""

from .config import AstronomyRuntimeConfig, DE441KernelConfig, SkySceneConfig, load_runtime_config
from .models import AstronomySnapshot, AstronomyTimeContext, BodyState, SkyScene
from .service import AstronomyService, get_default_service
from .validation import (
    CatalogValidationResult,
    KernelValidationResult,
    validate_de441_kernel_file,
    validate_star_catalog_file,
)

__all__ = [
    "AstronomyService",
    "AstronomyRuntimeConfig",
    "AstronomySnapshot",
    "AstronomyTimeContext",
    "BodyState",
    "CatalogValidationResult",
    "DE441KernelConfig",
    "KernelValidationResult",
    "SkyScene",
    "SkySceneConfig",
    "get_default_service",
    "load_runtime_config",
    "validate_de441_kernel_file",
    "validate_star_catalog_file",
]
