"""Sky dome projection helpers."""

from __future__ import annotations

import math
from typing import Optional, Tuple

from .camera import SkyCamera


def project_radec(
    ra_hours: float,
    dec_degrees: float,
    camera: SkyCamera,
    width: float,
    height: float,
) -> Optional[Tuple[float, float]]:
    """Project equatorial coordinates into 2D viewport space."""
    if width <= 0 or height <= 0:
        return None

    ra_offset_deg = ((ra_hours - camera.center_ra_hours) * 15.0 + 180.0) % 360.0 - 180.0
    dec_offset_deg = dec_degrees - camera.center_dec_degrees
    x = ra_offset_deg / 180.0
    y = dec_offset_deg / 90.0

    angle = math.radians(camera.rotation_degrees)
    xr = (x * math.cos(angle)) - (y * math.sin(angle))
    yr = (x * math.sin(angle)) + (y * math.cos(angle))

    radius_sq = (xr * xr) + (yr * yr)
    if radius_sq > 1.44:
        return None

    scale = min(width, height) * 0.45 * camera.zoom
    screen_x = (width / 2.0) + (xr * scale)
    screen_y = (height / 2.0) + (yr * scale)
    return screen_x, screen_y


def project_altaz(
    azimuth_degrees: float,
    altitude_degrees: float,
    camera: SkyCamera,
    width: float,
    height: float,
    cull_occluded: bool = True,
    keep_extreme: bool = False,
) -> Optional[Tuple[float, float]]:
    """Project observer-relative alt/az coordinates into a look-direction view.

    When ``cull_occluded`` is False, points behind the camera (``cam_z <= 0``)
    are still projected — they appear on the opposite side of the view, which
    lets great-circle rings (ecliptic, zodiac) be drawn as complete closed
    loops instead of being clipped at the horizon.

    When ``keep_extreme`` is True, points that would project far outside the
    view (``abs(nx) > 3`` or ``abs(ny) > 3``) are still returned.  This lets
    great-circle rings be drawn as complete closed loops even when part of the
    ring dips below the horizon.
    """
    if width <= 0 or height <= 0:
        return None

    target = _altaz_vector(azimuth_degrees, altitude_degrees)
    forward, right, up = camera_basis(camera)

    cam_x = _dot(target, right)
    cam_y = _dot(target, up)
    cam_z = _dot(target, forward)
    if cull_occluded and cam_z <= 0.01:
        return None

    aspect = width / height
    tan_half_vertical = math.tan(math.radians(camera.fov_degrees) / 2.0)
    tan_half_horizontal = tan_half_vertical * aspect
    # Use abs(cam_z) so behind-camera points project to the opposite side
    # of the view rather than producing a divide-by-zero / wild coordinates.
    depth = cam_z if cam_z > 0.01 else 0.01
    nx = cam_x / (depth * tan_half_horizontal)
    ny = cam_y / (depth * tan_half_vertical)
    if not keep_extreme and (abs(nx) > 3.0 or abs(ny) > 3.0):
        return None

    screen_x = (width * 0.5) * (1.0 + nx)
    screen_y = (height * 0.5) * (1.0 + ny)
    return screen_x, screen_y


def screen_to_altaz(
    screen_x: float,
    screen_y: float,
    camera: SkyCamera,
    width: float,
    height: float,
) -> Tuple[float, float]:
    """Inverse-project a screen point to a local-sky azimuth/altitude."""
    direction = screen_to_view_vector(screen_x, screen_y, camera, width, height)
    return vector_to_altaz(direction)


def screen_to_view_vector(
    screen_x: float,
    screen_y: float,
    camera: SkyCamera,
    width: float,
    height: float,
):
    """Inverse-project a screen point into the local ENU view vector."""
    forward, right, up = camera_basis(camera)
    aspect = width / height
    tan_half_vertical = math.tan(math.radians(camera.fov_degrees) / 2.0)
    tan_half_horizontal = tan_half_vertical * aspect
    nx = ((screen_x / width) * 2.0) - 1.0
    ny = ((screen_y / height) * 2.0) - 1.0
    cam_vector = _normalize((nx * tan_half_horizontal, ny * tan_half_vertical, 1.0))
    return _normalize(
        (
            right[0] * cam_vector[0] + up[0] * cam_vector[1] + forward[0] * cam_vector[2],
            right[1] * cam_vector[0] + up[1] * cam_vector[1] + forward[1] * cam_vector[2],
            right[2] * cam_vector[0] + up[2] * cam_vector[1] + forward[2] * cam_vector[2],
        )
    )


def camera_basis(camera: SkyCamera):
    """Return forward, right, and up vectors for the current view."""
    forward = _altaz_vector(camera.view_azimuth_degrees, camera.view_altitude_degrees)
    up_reference = (0.0, 0.0, 1.0)
    if abs(_dot(forward, up_reference)) > 0.98:
        up_reference = (0.0, 1.0, 0.0)
    right = _normalize(_cross(forward, up_reference))
    up = _normalize(_cross(right, forward))
    return forward, right, up


def vector_to_altaz(vector) -> Tuple[float, float]:
    """Convert a local ENU vector into azimuth/altitude."""
    x, y, z = _normalize(vector)
    azimuth = math.degrees(math.atan2(x, y)) % 360.0
    altitude = math.degrees(math.asin(max(-1.0, min(1.0, z))))
    return azimuth, altitude


def _altaz_vector(azimuth_degrees: float, altitude_degrees: float):
    azimuth = math.radians(azimuth_degrees % 360.0)
    altitude = math.radians(max(-90.0, min(90.0, altitude_degrees)))
    horizontal = math.cos(altitude)
    return (
        horizontal * math.sin(azimuth),
        horizontal * math.cos(azimuth),
        math.sin(altitude),
    )


def _dot(a, b) -> float:
    return (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2])


def _cross(a, b):
    return (
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    )


def _normalize(vector):
    length = math.sqrt(_dot(vector, vector))
    if length <= 1e-8:
        return (1.0, 0.0, 0.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)
