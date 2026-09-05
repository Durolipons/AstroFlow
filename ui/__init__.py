"""AstroFlow Kivy UI layer.

This package contains the graphical frontend. It imports *only* from
``core/`` for astrology logic -- never the other way around -- so the engine
stays UI-agnostic and can be reused from a CLI, web service, or a future
replacement UI.

Screens:
    HomeScreen      -- birth-data entry form
    ChartScreen     -- natal chart display (text; wheel graphics are a hook)
    ForecastScreen  -- progressions + solar arc + transits for a target date
"""

from .main import AstroFlowApp

__all__ = ["AstroFlowApp"]