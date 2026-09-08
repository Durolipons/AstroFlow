"""Astro-Clock widget.

The Astro-Clock shows the current time and a live chart wheel for the current
sky. It is UI-only; the astrology calculations still live in ``core/``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Thread
from typing import Optional, Tuple

from astronomy.adapters import SwissCompatAdapter
from astronomy.backends import BackendUnavailableError
from astronomy.service import get_default_service
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    OptionProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.widget import Widget

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


# Bounds for the readout/wheel split (see PanelDivider / set_readout_height).
MIN_READOUT_HEIGHT = 44.0   # keep at least one comfortable line of text
MIN_WHEEL_HEIGHT = 140.0    # keep the wheel large enough to stay readable


class PanelDivider(Widget):
    """Draggable divider between two panels.

    ``orientation`` picks the bar direction and the drag axis:

    * ``horizontal`` (default) — a horizontal bar: dragging up/down resizes
      vertically, e.g. the Astro-Clock's readout vs. its live wheel.
    * ``vertical`` — a vertical bar: dragging left/right resizes horizontally,
      e.g. the Home screen's chart-data column vs. the Astro-Clock.

    While dragging, the divider calls ``owner.adjust_split(delta)`` with the
    pixel delta along the drag axis; the owner converts it into its own layout
    property and applies any clamps. Hovering shows a resize cursor that
    matches the drag axis so the affordance is discoverable.
    """

    orientation = OptionProperty("horizontal", options=["horizontal", "vertical"])
    owner = ObjectProperty(None)
    hovered = BooleanProperty(False)

    # Resize cursors per orientation: up/down for a horizontal bar, left/right
    # for a vertical one — never a 4-way cursor, only one axis is draggable.
    CURSORS = {"horizontal": "size_ns", "vertical": "size_we"}
    CURSOR_DEFAULT = "arrow"

    def __init__(self, **kwargs):
        self._last_drag_pos = None
        self._dragging = False
        self._hover_bound = False
        self._cursor_active = False
        super().__init__(**kwargs)
        with self.canvas:
            Color(0.16, 0.18, 0.24, 1)
            self._well = Rectangle(pos=self.pos, size=self.size)
            self._grip_color = Color(rgba=(0.34, 0.36, 0.44, 1))
            self._bar = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)
        self.bind(orientation=self._sync_canvas)
        self.bind(hovered=self._refresh_grip)

    # -- visuals -------------------------------------------------------------
    def _sync_canvas(self, *_args):
        self._well.pos = self.pos
        self._well.size = self.size
        if self.orientation == "vertical":
            self._bar.pos = (self.center_x - 1, self.y + 4)
            self._bar.size = (2, self.height - 8)
        else:
            self._bar.pos = (self.x + 4, self.center_y - 1)
            self._bar.size = (self.width - 8, 2)

    def _refresh_grip(self, *_args):
        self._grip_color.rgba = (
            (0.62, 0.66, 0.74, 1) if self.hovered else (0.34, 0.36, 0.44, 1)
        )

    # -- mouse-over affordance -------------------------------------------------
    def on_parent(self, _widget, _parent):
        """Track the mouse while attached; release the tracker on removal."""
        if self.parent is None:
            self._unbind_hover()
        else:
            self._bind_hover()

    def _bind_hover(self):
        if self._hover_bound:
            return
        try:
            from kivy.core.window import Window  # local import (headless-safe)
        except Exception:
            return
        Window.bind(mouse_pos=self._on_mouse_pos)
        self._hover_bound = True

    def _unbind_hover(self):
        if self._cursor_active:
            # Widget removed while the pointer was over it: undo the cursor.
            self._cursor_active = False
            window = self.get_root_window()
            if window is not None:
                try:
                    window.set_system_cursor(self.CURSOR_DEFAULT)
                except Exception:
                    pass
        if not self._hover_bound:
            return
        try:
            from kivy.core.window import Window

            Window.unbind(mouse_pos=self._on_mouse_pos)
        except Exception:
            pass
        self._hover_bound = False

    def _on_mouse_pos(self, _window, pos):
        # Every layout between the Window and this divider is a plain
        # BoxLayout/Screen, so the whole tree shares one coordinate space
        # (the Home screen's RelativeLayout origin sits at window (0, 0)).
        # ``Window.mouse_pos`` can therefore be hit-tested directly.
        self._set_hovered(self.collide_point(*pos))

    def _set_hovered(self, inside: bool) -> None:
        new_state = inside or self._dragging
        if new_state == self.hovered:
            return
        self.hovered = new_state
        window = self.get_root_window()
        try:
            if new_state:
                self._cursor_active = True
                if window is not None:
                    window.set_system_cursor(self.CURSORS[self.orientation])
            elif self._cursor_active:
                self._cursor_active = False
                if window is not None:
                    # Restore unconditionally when leaving. Kivy keeps no
                    # public record of the active cursor, so tracking our own
                    # state is the only reliable way to undo our change —
                    # relying on a read-back left the cursor stuck permanently.
                    window.set_system_cursor(self.CURSOR_DEFAULT)
        except Exception:
            pass  # cursor changes are cosmetic; never break interaction

    # -- dragging ---------------------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        touch.grab(self)
        self._dragging = True
        self._last_drag_pos = (touch.x, touch.y)
        self._set_hovered(True)
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self or self.owner is None:
            return super().on_touch_move(touch)
        # Report the per-event INCREMENT, not the offset from the touch-down
        # point: the owner adds each increment to its current value, so
        # passing full offsets would compound and make the divider fly.
        last_x, last_y = self._last_drag_pos or (touch.x, touch.y)
        if self.orientation == "vertical":
            delta = touch.x - last_x
        else:
            delta = touch.y - last_y
        self._last_drag_pos = (touch.x, touch.y)
        self.owner.adjust_split(delta)
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._dragging = False
            self._last_drag_pos = None
            self._set_hovered(False)
            return True
        return super().on_touch_up(touch)


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
    source_button = ObjectProperty(None)
    source_status = ObjectProperty(None)
    wheel_host = ObjectProperty(None)
    wheel = ObjectProperty(None)
    readout_row = ObjectProperty(None)
    readout_label = ObjectProperty(None)
    split_divider = ObjectProperty(None)
    font_down_button = ObjectProperty(None)
    font_up_button = ObjectProperty(None)
    readout_height = NumericProperty(72.0)

    def __init__(self, **kwargs):
        self._refresh_event = None
        self._last_chart_minute = None
        self._profile = self._default_profile()
        self._device_location_enabled = False
        self._device_location_available = False
        self._device_location_error = ""
        self._device_location: Optional[Location] = None
        self._data_source = "swiss"
        self._font_size: float = 12.0
        self._astronomy_service = get_default_service()
        self._astronomy_request_key = None
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
        self._sync_source_controls()
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

    # -- panel scaling ---------------------------------------------------------
    def scale_font(self, delta: float) -> None:
        """Grow/shrink the readout text, clamped to 8..32sp."""
        self._font_size = min(32.0, max(8.0, self._font_size + delta))
        if self.readout_label is not None:
            self.readout_label.font_size = f"{self._font_size}sp"

    def set_readout_height(self, height: float) -> None:
        """Set the readout row height, clamped so the wheel stays usable.

        Called by the divider while it is dragged; the wheel host keeps
        whatever vertical room the readout does not take.
        """
        low, high = self._split_bounds()
        self.readout_height = min(high, max(low, height))

    def _split_bounds(self) -> Tuple[float, float]:
        """Return the (min, max) readout heights for the current size."""
        fixed = 0.0
        n_children = 0
        for child in self.children:
            n_children += 1
            if child is self.readout_row:
                continue
            if child.size_hint_y is None:
                fixed += child.height
        available = self.height - self.padding[1] - self.padding[3]
        if n_children > 1:
            available -= self.spacing * (n_children - 1)
        return (
            MIN_READOUT_HEIGHT,
            max(MIN_READOUT_HEIGHT, available - fixed - MIN_WHEEL_HEIGHT),
        )

    def adjust_split(self, delta: float) -> None:
        """Divider callback: move the readout/wheel boundary by ``delta`` px.

        The readout sits *above* the divider, so the boundary follows the
        pointer: dragging up (positive delta) shrinks the readout and grows
        the wheel below it.
        """
        self.set_readout_height(self.readout_height - delta)

    def set_profile(self, birth_data: BirthData) -> None:
        """Optionally use a caller-provided profile for the current sky wheel."""
        self._profile = birth_data
        self._last_chart_minute = None
        self._refresh_now()

    def set_astronomy_service(self, service) -> None:
        """Allow tests or higher layers to inject a custom astronomy service."""
        self._astronomy_service = service

    def cycle_data_source(self) -> None:
        order = ("swiss", "horizons", "de441")
        next_index = (order.index(self._data_source) + 1) % len(order)
        self.set_data_source(order[next_index])

    def set_data_source(self, name: str) -> None:
        if name not in {"swiss", "horizons", "de441"}:
            raise ValueError("AstroClock data source must be swiss, horizons, or de441.")
        self._data_source = name
        self._last_chart_minute = None
        if self.source_status is not None:
            self.source_status.text = ""
        self._sync_source_controls()
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
            location=Location(latitude=51.4779, longitude=0.0, name="Greenwich"),
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
        self._sync_source_controls()

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
            self._refresh_chart(profile, now_utc)

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

    def _refresh_chart(self, profile: BirthData, now_utc: datetime) -> None:
        if self._data_source == "swiss":
            self._queue_wheel_chart(transit_chart(profile, now_utc))
            return

        base_chart = transit_chart(profile, now_utc)
        request_key = (
            self._data_source,
            now_utc.replace(second=0, microsecond=0).isoformat(),
            round(profile.location.latitude, 4),
            round(profile.location.longitude, 4),
        )
        self._astronomy_request_key = request_key
        if self.source_status is not None:
            self.source_status.text = f"Loading {self._source_label(self._data_source)}..."

        worker = Thread(
            target=self._load_astronomy_chart_worker,
            args=(request_key, base_chart, profile.location),
            daemon=True,
        )
        worker.start()

    def _build_astronomy_chart(self, base_chart, observer, backend_name: str):
        snapshot = self._astronomy_service.fetch_snapshot(
            backend_name,
            base_chart.birth_data.birth_datetime,
            observer=observer,
        )
        return SwissCompatAdapter.build_display_chart(
            base_chart,
            snapshot,
            target_title=f"{base_chart.target_title} [{self._source_label(backend_name)}]",
        )

    def _load_astronomy_chart_worker(self, request_key, base_chart, observer):
        try:
            chart = self._build_astronomy_chart(base_chart, observer, request_key[0])
        except (BackendUnavailableError, ValueError) as exc:
            message = str(exc)
            Clock.schedule_once(
                lambda _dt, msg=message: self._apply_astronomy_error(request_key, msg), 0
            )
            return
        Clock.schedule_once(
            lambda _dt, built_chart=chart: self._apply_astronomy_chart(request_key, built_chart), 0
        )

    def _apply_astronomy_chart(self, request_key, chart):
        if request_key != self._astronomy_request_key:
            return
        self._queue_wheel_chart(chart)
        if self.source_status is not None:
            self.source_status.text = f"Using {self._source_label(request_key[0])}."

    def _apply_astronomy_error(self, request_key, message: str):
        if request_key != self._astronomy_request_key:
            return
        if self.source_status is not None:
            self.source_status.text = message
        if self.readout_label is not None:
            self.readout_label.text = message

    def _sync_source_controls(self):
        if self.source_button is not None:
            self.source_button.text = f"Ephemeris: {self._source_label(self._data_source)}"
        if self.source_status is not None:
            if self._data_source == "swiss" and (
                not self.source_status.text or "Swiss Ephemeris" not in self.source_status.text
            ):
                self.source_status.text = "Using Swiss Ephemeris."
            elif self._data_source != "swiss" and not self.source_status.text:
                self.source_status.text = f"Ready to query {self._source_label(self._data_source)}."

    @staticmethod
    def _source_label(name: str) -> str:
        labels = {
            "swiss": "Swiss",
            "horizons": "JPL Horizons",
            "de441": "DE441",
        }
        return labels[name]
