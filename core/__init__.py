"""AstroFlow core engine.

This package is the UI-agnostic astrology engine. It contains *no* Kivy
import -- every module here can be imported, tested, and reused from plain
Python, a CLI, a web service, or any future UI.

Public entry points for consumers:
    core.ephemeris      -- Swiss Ephemeris wrapper (only module importing swisseph)
    core.chart          -- birth chart calculation
    core.chart_store    -- JSON-backed saved-birth-chart database
    core.progressions   -- secondary progressions + solar arc directions
    core.synthesis      -- structured whole-chart and forecast synthesis
    core.transits       -- transit positions + aspects to the natal chart
    core.aspects        -- generic aspect detection
    core.interpretation -- plain-text report generation
    core.interpretation_store -- editable JSON-backed interpretation library
"""

from . import (
    aspects,
    chart,
    chart_store,
    constants,
    ephemeris,
    interpretation,
    interpretation_store,
    models,
    progressions,
    synthesis,
    transits,
    utils,
)

__all__ = [
    "aspects",
    "chart",
    "chart_store",
    "constants",
    "ephemeris",
    "interpretation",
    "interpretation_store",
    "models",
    "progressions",
    "synthesis",
    "transits",
    "utils",
]

__version__ = "0.1.0"
