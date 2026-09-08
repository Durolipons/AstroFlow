"""Cached Milky Way environment texture helpers."""

from __future__ import annotations

import math
import os

from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture

_TEXTURE_CACHE = {}


def milky_way_texture(path: str = "", width: int = 512, height: int = 256) -> Texture:
    """Return a cached Milky Way texture, preferring a real panorama asset."""
    normalized_path = os.path.abspath(path) if path else ""
    if normalized_path and os.path.exists(normalized_path):
        key = ("asset", normalized_path)
        if key in _TEXTURE_CACHE:
            return _TEXTURE_CACHE[key]
        image = CoreImage(normalized_path)
        texture = image.texture
        texture.wrap = "repeat"
        _TEXTURE_CACHE[key] = texture
        return texture

    key = ("procedural", int(width), int(height))
    if key in _TEXTURE_CACHE:
        return _TEXTURE_CACHE[key]

    width = max(32, int(width))
    height = max(16, int(height))
    pixels = bytearray(width * height * 4)
    for y in range(height):
        v = y / max(1, height - 1)
        latitude = 90.0 - (v * 180.0)
        lat_abs = abs(latitude)
        for x in range(width):
            u = x / max(1, width - 1)
            longitude = (u * 360.0) % 360.0
            brightness = _milky_way_brightness(longitude, latitude)
            color = _milky_way_color(longitude, latitude, brightness)
            index = (y * width + x) * 4
            pixels[index] = int(max(0, min(255, color[0] * 255.0)))
            pixels[index + 1] = int(max(0, min(255, color[1] * 255.0)))
            pixels[index + 2] = int(max(0, min(255, color[2] * 255.0)))
            alpha = brightness * (0.88 - min(0.24, lat_abs / 420.0))
            pixels[index + 3] = int(max(0, min(255, alpha * 255.0)))

    texture = Texture.create(size=(width, height), colorfmt="rgba")
    texture.wrap = "repeat"
    texture.blit_buffer(bytes(pixels), colorfmt="rgba", bufferfmt="ubyte")
    _TEXTURE_CACHE[key] = texture
    return texture


def _milky_way_brightness(longitude: float, latitude: float) -> float:
    center = _gaussian_longitude(longitude, 0.0, 22.0, 1.0)
    sagittarius = _gaussian_longitude(longitude, 12.0, 16.0, 0.55)
    cygnus = _gaussian_longitude(longitude, 80.0, 24.0, 0.48)
    vela = _gaussian_longitude(longitude, 265.0, 28.0, 0.34)
    anti_center = _gaussian_longitude(longitude, 180.0, 30.0, 0.18)

    plane_sigma = 8.0 + (14.0 * center) + (8.0 * cygnus) + (5.0 * vela)
    plane = math.exp(-((latitude / plane_sigma) ** 2))
    halo = math.exp(-((latitude / 26.0) ** 2)) * (0.18 + anti_center)
    dark_lane = math.exp(-((latitude / 2.0) ** 2)) * (0.15 + center * 0.22)

    brightness = (plane * (0.42 + center + sagittarius + cygnus + vela)) + halo - dark_lane
    return max(0.0, min(1.0, brightness))


def _milky_way_color(longitude: float, latitude: float, brightness: float):
    warm_core = _gaussian_longitude(longitude, 0.0, 35.0, 1.0)
    cool_arm = _gaussian_longitude(longitude, 90.0, 48.0, 0.7) + _gaussian_longitude(longitude, 270.0, 48.0, 0.7)
    latitude_tint = max(0.0, 1.0 - (abs(latitude) / 70.0))

    base_r = 0.24 + brightness * (0.46 + warm_core * 0.20)
    base_g = 0.28 + brightness * (0.48 + latitude_tint * 0.08)
    base_b = 0.38 + brightness * (0.56 + cool_arm * 0.18)
    return (
        min(1.0, base_r),
        min(1.0, base_g),
        min(1.0, base_b),
    )


def _gaussian_longitude(longitude: float, center: float, sigma: float, amplitude: float) -> float:
    delta = ((longitude - center + 180.0) % 360.0) - 180.0
    return amplitude * math.exp(-((delta / sigma) ** 2))
