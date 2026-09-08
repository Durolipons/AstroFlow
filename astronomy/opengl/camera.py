"""Camera state for the sky renderer.

The camera has two complementary vocabularies that are kept in sync by the
renderer's navigation helpers:

* ``view_azimuth_degrees`` / ``view_altitude_degrees`` / ``fov_degrees`` --
  the planetarium look direction used by the observer-centred alt/az
  projection (the runtime path).
* ``center_ra_hours`` / ``center_dec_degrees`` / ``zoom`` /
  ``rotation_degrees`` -- the celestial-chart fields used only by
  ``project_radec`` as a navigable fallback when no observer location/time
  is available (e.g. headless preview scenes).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SkyCamera:
    """User-controllable camera parameters.

    ``fov_degrees`` is the *vertical* field of view of the planetarium view;
    the horizontal span grows with the widget aspect ratio. The 60-degree
    default keeps the dome feeling large ("standing in a planetarium", not
    "looking through the wrong end of a telescope"): objects are big enough
    to space out naturally and the rectilinear edge stretch stays tame.
    """

    center_ra_hours: float = 0.0
    center_dec_degrees: float = 0.0
    zoom: float = 1.0
    rotation_degrees: float = 0.0
    view_azimuth_degrees: float = 120.0
    view_altitude_degrees: float = 0.0
    fov_degrees: float = 60.0

    def clamp(self) -> None:
        self.center_ra_hours %= 24.0
        self.center_dec_degrees = max(-89.0, min(89.0, self.center_dec_degrees))
        self.zoom = max(0.25, min(8.0, self.zoom))
        self.rotation_degrees %= 360.0
        self.view_azimuth_degrees %= 360.0
        self.view_altitude_degrees = max(-89.0, min(89.0, self.view_altitude_degrees))
        self.fov_degrees = max(35.0, min(150.0, self.fov_degrees))
