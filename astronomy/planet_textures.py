"""Cached textured planet sprite helpers."""

from __future__ import annotations

import math

from kivy.graphics.texture import Texture

_SPRITE_CACHE = {}


def planet_sprite_texture(
    name: str,
    color: tuple[float, float, float],
    glyph: str = "",
    size: int = 96,
) -> Texture:
    """Return a cached sprite texture for a planet-like sky point."""
    normalized_size = max(32, int(size))
    cache_key = (
        name,
        tuple(round(channel, 4) for channel in color),
        glyph,
        normalized_size,
    )
    if cache_key in _SPRITE_CACHE:
        return _SPRITE_CACHE[cache_key]

    pixels = bytearray(normalized_size * normalized_size * 4)
    center = (normalized_size - 1) * 0.5
    radius = center * 0.88
    highlight_x = center - (radius * 0.32)
    highlight_y = center + (radius * 0.26)
    lower_name = (name or "").strip().lower()

    for y in range(normalized_size):
        for x in range(normalized_size):
            dx = x - center
            dy = y - center
            distance = math.hypot(dx, dy)
            nx = dx / max(radius, 1.0)
            ny = dy / max(radius, 1.0)
            index = ((y * normalized_size) + x) * 4

            rgba = _planet_pixel(
                lower_name,
                color,
                x,
                y,
                dx,
                dy,
                nx,
                ny,
                distance,
                radius,
                highlight_x,
                highlight_y,
            )
            pixels[index] = rgba[0]
            pixels[index + 1] = rgba[1]
            pixels[index + 2] = rgba[2]
            pixels[index + 3] = rgba[3]

    texture = Texture.create(size=(normalized_size, normalized_size), colorfmt="rgba")
    texture.wrap = "clamp_to_edge"
    texture.blit_buffer(bytes(pixels), colorfmt="rgba", bufferfmt="ubyte")
    _SPRITE_CACHE[cache_key] = texture
    return texture


def _planet_pixel(
    name: str,
    color: tuple[float, float, float],
    x: int,
    y: int,
    dx: float,
    dy: float,
    nx: float,
    ny: float,
    distance: float,
    radius: float,
    highlight_x: float,
    highlight_y: float,
) -> tuple[int, int, int, int]:
    base_rgb = color
    alpha = 0.0

    if name == "saturn":
        ring_radius = math.hypot(nx / 1.28, ny / 0.58)
        if 0.74 <= ring_radius <= 1.22:
            ring_fade = 1.0 - min(1.0, abs(ring_radius - 0.98) / 0.24)
            ring_alpha = ring_fade * max(0.0, 1.0 - (abs(ny) / 1.15))
            ring_rgb = _mix(color, (0.98, 0.90, 0.72), 0.48)
            return _rgba_bytes(ring_rgb, ring_alpha * 0.64)

    if distance <= radius:
        edge_fade = max(0.0, 1.0 - (distance / max(radius, 1.0)) ** 1.9)
        limb_shadow = max(0.0, min(1.0, 0.58 + (nx * 0.42)))
        highlight = math.exp(
            -(
                ((x - highlight_x) / max(radius * 0.48, 1.0)) ** 2
                + ((y - highlight_y) / max(radius * 0.42, 1.0)) ** 2
            )
        )
        texture_rgb = base_rgb
        texture_mix = 0.0

        if name == "jupiter":
            bands = 0.5 + 0.5 * math.sin((ny * 5.6 + 0.15) * math.pi)
            texture_rgb = _mix(base_rgb, (0.96, 0.82, 0.56), bands * 0.34)
            texture_mix = 0.10
        elif name == "mars":
            polar = math.exp(-(((ny + 0.52) / 0.18) ** 2))
            texture_rgb = _mix(base_rgb, (1.0, 0.88, 0.78), polar * 0.24)
        elif name == "moon":
            maria = 0.5 + 0.5 * math.sin((nx * 4.0 - ny * 3.0) * math.pi)
            texture_rgb = _mix(base_rgb, (0.70, 0.74, 0.82), maria * 0.20)
            texture_mix = 0.14
        elif name == "sun":
            corona = math.exp(-((distance / max(radius * 1.05, 1.0)) ** 2))
            texture_rgb = _mix(base_rgb, (1.0, 0.96, 0.72), corona * 0.28)
            texture_mix = 0.20
        elif name == "venus":
            texture_rgb = _mix(base_rgb, (0.98, 0.92, 0.82), 0.12)
        elif name == "mercury":
            texture_rgb = _mix(base_rgb, (0.88, 0.82, 0.72), 0.08)
        elif name == "neptune":
            texture_rgb = _mix(base_rgb, (0.70, 0.84, 1.0), 0.12)
        elif name == "uranus":
            texture_rgb = _mix(base_rgb, (0.82, 0.96, 1.0), 0.14)

        lit_rgb = _mix(texture_rgb, (1.0, 1.0, 1.0), highlight * 0.30)
        lit_rgb = _mix(lit_rgb, (0.05, 0.06, 0.08), texture_mix)
        lit_rgb = tuple(_clamp01(channel * limb_shadow + edge_fade * 0.12) for channel in lit_rgb)
        alpha = 0.85 + edge_fade * 0.15
        return _rgba_bytes(lit_rgb, alpha)

    halo = math.exp(-(((distance - radius) / max(radius * 0.28, 1.0)) ** 2))
    if halo <= 0.01:
        return (0, 0, 0, 0)
    halo_rgb = _mix(base_rgb, (1.0, 1.0, 1.0), 0.18)
    return _rgba_bytes(halo_rgb, halo * (0.24 if name != "sun" else 0.38))


def _mix(first: tuple[float, float, float], second: tuple[float, float, float], amount: float):
    blend = _clamp01(amount)
    return tuple(
        _clamp01((start * (1.0 - blend)) + (end * blend))
        for start, end in zip(first, second)
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _rgba_bytes(rgb: tuple[float, float, float], alpha: float) -> tuple[int, int, int, int]:
    return (
        int(_clamp01(rgb[0]) * 255.0),
        int(_clamp01(rgb[1]) * 255.0),
        int(_clamp01(rgb[2]) * 255.0),
        int(_clamp01(alpha) * 255.0),
    )
