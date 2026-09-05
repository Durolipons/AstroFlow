"""Astro-Clock widget.

The Astro-Clock shows the current time and a live chart wheel for the current
sky. It is UI-only; the astrology calculations still live in ``core/``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout

from core.cities import nearest_city
from core.interpretation import sky_aspect_text, sky_planet_text, sky_sign_text
from core.models import BirthData, Location
from core.transits import transit_chart
from ui.widgets.chart_wheel import ChartWheel  # noqa: F401 (KV factory)


def _copy_to_clipboard(text: str) -> bool:
    """Copy ``text`` to the system clipboard. Returns True on success."""
    if not text:
        return False
    try:
        from kivy.core.clipboard import Clipboard
    except Exception:
        return False
    Clipboard.copy(text)
    return True


class SquareWheelHost(AnchorLayout):
    """Keeps the chart wheel square and centered inside its panel."""

    wheel = ObjectProperty(None)

    def __init__(self, **kwargs):
        kwargs.setdefault("anchor_x", "center")
        kwargs.setdefault("anchor_y", "center")
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.05, 0.06, 0.08, 1)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[12])
        self.bind(size=self._sync_wheel, pos=self._sync_wheel)
        self.bind(size=self._sync_bg, pos=self._sync_bg)

    def on_kv_post(self, base_widget):
        self._sync_wheel()

    def _sync_bg(self, *_args):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _sync_wheel(self, *_args):
        wheel = self.wheel
        if wheel is None:
            return
        side = min(self.width, self.height)
        if side <= 0:
            return
        wheel.size_hint = (None, None)
        wheel.size = (side, side)


class AstroClock(BoxLayout):
    """Live current-time panel with a transit chart wheel."""

    time_label = ObjectProperty(None)
    location_label = ObjectProperty(None)
    location_button = ObjectProperty(None)
    location_status = ObjectProperty(None)
    wheel_host = ObjectProperty(None)
    wheel = ObjectProperty(None)
    readout_label = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._refresh_event = None
        self._last_chart_minute = None
        self._profile = self._default_profile()
        self._device_location_enabled = False
        self._device_location_available = False
        self._device_location_error = ""
        self._device_location: Optional[Location] = None
        self._pending_chart = None
        super().__init__(**kwargs)

    def on_parent(self, *_args):
        if self.parent is None and self._refresh_event is not None:
            self._refresh_event.cancel()
            self._refresh_event = None

    def on_kv_post(self, base_widget):
        self._refresh_now()
        self._maybe_start_device_location()
        if self._refresh_event is None:
            self._refresh_event = Clock.schedule_interval(self._refresh_now, 1.0)
        self._sync_panel()
        self._flush_pending_chart()
        self._bind_wheel_events()

    def _bind_wheel_events(self):
        """Forward wheel taps to the panel's readout label."""
        if self.wheel is not None:
            self.wheel.bind(on_planet_selected=self._on_wheel_planet)
            self.wheel.bind(on_sign_selected=self._on_wheel_sign)
            self.wheel.bind(on_aspect_selected=self._on_wheel_aspect)

    def _on_wheel_planet(self, _wheel, planet_name):
        """Show general current-sky text for a planet tapped on the wheel."""
        chart = self.wheel.chart if self.wheel is not None else None
        if chart is None or self.readout_label is None:
            return
        self.readout_label.text = sky_planet_text(chart, planet_name)

    def _on_wheel_aspect(self, _wheel, aspect):
        """Show general current-sky text for an aspect tapped on the wheel."""
        if self.readout_label is None:
            return
        self.readout_label.text = sky_aspect_text(aspect)

    def _on_wheel_sign(self, _wheel, sign_name):
        """Show general current-sky text for a sign tapped on the wheel."""
        chart = self.wheel.chart if self.wheel is not None else None
        if chart is None or self.readout_label is None:
            return
        self.readout_label.text = sky_sign_text(chart, sign_name)

    def copy_readout(self, *_args):
        """Copy the readout text to the clipboard (for blogs and posts)."""
        if self.readout_label is None:
            return False
        return _copy_to_clipboard(self.readout_label.text)

    def set_profile(self, birth_data: BirthData) -> None:
        """Optionally use a caller-provided profile for the current sky wheel."""
        self._profile = birth_data
        self._last_chart_minute = None
        self._refresh_now()

    def toggle_device_location(self) -> None:
        """Switch the Astro-Clock between chart location and device GPS."""
        if self._device_location_enabled:
            self._device_location_enabled = False
            self._device_location_error = ""
            self._refresh_now()
            return
        self._device_location_enabled = True
        if not self._maybe_start_device_location():
            self._device_location_enabled = False
        self._refresh_now()

    def set_device_location(
        self,
        latitude: float,
        longitude: float,
        altitude: float = 0.0,
        label: str = "",
    ) -> None:
        """Inject a device-location fix (useful for GPS callbacks and tests)."""
        self._device_location_enabled = True
        self._device_location_available = True
        self._device_location = Location(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            name=label,
        )
        self._device_location_error = ""
        self._last_chart_minute = None
        self._refresh_now()

    def _default_profile(self) -> BirthData:
        """Build a neutral profile for the live wheel when none is supplied."""
        return BirthData(
            name="Current Sky",
            birth_datetime=datetime.now(timezone.utc),
            location=Location(latitude=0.0, longitude=0.0, name="Greenwich"),
            house_system="P",
        )

    def _refresh_now(self, *_args):
        now_local = datetime.now().astimezone()
        now_utc = now_local.astimezone(timezone.utc)
        if self.time_label is not None:
            self.time_label.text = (
                f"Local: {now_local:%Y-%m-%d %H:%M:%S}\n"
                f"UTC:   {now_utc:%Y-%m-%d %H:%M:%S}"
            )
        active = self._active_location()
        if self.location_label is not None:
            label = active.name.strip() if active.name else ""
            coords = f"{active.latitude:+.4f}, {active.longitude:+.4f}"
            if label:
                self.location_label.text = f"Location: {label}\n{coords}"
            else:
                self.location_label.text = f"Location: {coords}"
        if self.location_button is not None:
            if self._device_location_enabled:
                self.location_button.text = "Use chart location"
            else:
                self.location_button.text = "Use device location"
        if self.location_status is not None:
            if self._device_location_enabled:
                if self._device_location_available:
                    self.location_status.text = "GPS active"
                elif self._device_location_error:
                    self.location_status.text = self._device_location_error
                else:
                    self.location_status.text = "Waiting for GPS fix..."
            else:
                self.location_status.text = "Using chart location"

        chart_minute = (now_utc.year, now_utc.month, now_utc.day, now_utc.hour, now_utc.minute)
        if chart_minute != self._last_chart_minute:
            self._last_chart_minute = chart_minute
            profile = self._profile
            location = self._active_location()
            profile = BirthData(
                name=profile.name,
                birth_datetime=now_utc,
                location=location,
                timezone=profile.timezone,
                house_system=profile.house_system,
                sidereal_mode=profile.sidereal_mode,
            )
            self._queue_wheel_chart(transit_chart(profile, now_utc))

    def _active_location(self) -> Location:
        if self._device_location_enabled and self._device_location is not None:
            return self._device_location
        return self._profile.location

    def _maybe_start_device_location(self) -> bool:
        if not self._device_location_enabled:
            return False

        try:
            from plyer import gps
        except Exception:
            self._device_location_error = "GPS unavailable on this platform."
            self._device_location_available = False
            return False

        if self._device_location_available:
            return True

        try:
            try:
                from kivy.utils import platform
            except Exception:
                platform = ""
            if platform == "android":
                try:
                    from android.permissions import Permission, request_permissions

                    request_permissions(
                        [
                            Permission.ACCESS_FINE_LOCATION,
                            Permission.ACCESS_COARSE_LOCATION,
                        ]
                    )
                except Exception:
                    pass
            gps.configure(
                on_location=self._on_gps_location,
                on_status=self._on_gps_status,
            )
            gps.start(minTime=1000, minDistance=0)
            self._device_location_error = ""
            return True
        except Exception as exc:
            self._device_location_error = f"GPS unavailable: {exc}"
            self._device_location_available = False
            return False

    def _on_gps_location(self, **kwargs):
        latitude = kwargs.get("lat")
        longitude = kwargs.get("lon")
        if latitude is None or longitude is None:
            return
        altitude = kwargs.get("altitude", 0.0) or 0.0
        label = ""
        city = nearest_city(latitude, longitude)
        if city is not None:
            label = city.label
        self.set_device_location(latitude, longitude, altitude=altitude, label=label)

    def _on_gps_status(self, _status_type, status):
        self._device_location_error = str(status)
        self._device_location_available = False

    def _queue_wheel_chart(self, chart) -> None:
        self._pending_chart = chart
        self._flush_pending_chart()

    def _flush_pending_chart(self, *_args) -> None:
        if self._pending_chart is None or self.wheel is None:
            return
        if self.wheel.width < 32 or self.wheel.height < 32:
            Clock.schedule_once(self._flush_pending_chart, 0)
            return
        chart = self._pending_chart
        self._pending_chart = None
        self.wheel.set_chart(chart)

    def _sync_panel(self) -> None:
        if self.wheel_host is not None:
            if self.wheel_host.wheel is None and self.wheel is not None:
                self.wheel_host.wheel = self.wheel
            self.wheel_host._sync_wheel()
