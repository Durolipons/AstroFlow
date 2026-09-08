"""Dedicated live sky screen backed by the new astronomy layer."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Thread

from astronomy import load_runtime_config, validate_de441_kernel_file, validate_star_catalog_file
from astronomy.models import AstronomySnapshot, BodyState, EclipticCoordinates, Vector3
from astronomy.timebase import build_time_context
from kivy.clock import Clock
from kivy.properties import ObjectProperty
from kivy.uix.screenmanager import Screen

from astronomy.backends import BackendUnavailableError
from astronomy.kivy import SkyPanel  # noqa: F401 (KV factory)
from astronomy.kivy.sky_widget import SkyViewportWidget  # noqa: F401 (KV factory)
from astronomy.service import get_default_service
from core.models import BirthData, Location


class SkyScreen(Screen):
    """Standalone astronomy-only sky panel."""

    sky_panel = ObjectProperty(None)
    backend_button = ObjectProperty(None)
    play_button = ObjectProperty(None)
    status_label = ObjectProperty(None)
    time_label = ObjectProperty(None)
    kernel_label = ObjectProperty(None)
    scene_label = ObjectProperty(None)

    def __init__(self, **kwargs):
        self._config = load_runtime_config()
        self._profile = self._default_profile()
        self._backend_name = self._config.sky.default_backend
        self._refresh_event = None
        self._animation_event = None
        self._service = get_default_service()
        self._request_key = None
        self._display_time_utc = datetime.now(timezone.utc)
        self._animation_enabled = self._config.sky.auto_play
        self._animation_step_minutes = max(1.0, self._config.sky.animation_step_minutes)
        self._animation_speed_multiplier = max(0.25, self._config.sky.animation_speed_multiplier)
        self._realtime_animation = self._config.sky.realtime_animation
        self._base_snapshot = None
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self._sync_controls()
        self._sync_kernel_status()
        self._sync_catalog_status()
        self._apply_preview_snapshot(self._display_time_utc, "Waiting for live astronomy data.")

    def on_parent(self, *_args):
        if self.parent is None:
            self._stop_timers()

    def on_pre_enter(self, *_args):
        self._display_time_utc = datetime.now(timezone.utc)
        self._start_timers()
        self.refresh_snapshot()

    def on_leave(self, *_args):
        self._stop_timers()

    def _default_profile(self):
        return BirthData(
            name="Current Sky",
            birth_datetime=datetime.now(timezone.utc),
            location=Location(latitude=51.4779, longitude=0.0, name="Greenwich"),
        )

    def set_profile(self, birth_data: BirthData):
        self._profile = birth_data
        if self.manager is not None and self.manager.current == self.name:
            self.refresh_snapshot()

    def set_astronomy_service(self, service):
        self._service = service

    def cycle_backend(self):
        self._backend_name = "de441" if self._backend_name == "horizons" else "horizons"
        self._sync_controls()
        self._sync_kernel_status()
        self.refresh_snapshot()

    def refresh_snapshot(self, *_args):
        target_utc = self._display_time_utc
        backend_name = self._backend_name
        self._request_key = (backend_name, target_utc.replace(second=0, microsecond=0).isoformat())
        self._sync_controls(target_utc)
        if self.sky_panel is not None and self.sky_panel.get_scene() is None:
            self._apply_preview_snapshot(target_utc, "Preparing sky preview.")
        worker = Thread(
            target=self._load_snapshot_worker,
            args=(self._request_key, backend_name, target_utc, self._profile.location),
            daemon=True,
        )
        worker.start()

    def _load_snapshot_worker(self, request_key, backend_name, now_utc, observer):
        failures = []
        fallback_order = [backend_name] + [
            candidate
            for candidate in ("de441", "horizons")
            if candidate != backend_name
        ]
        for candidate in fallback_order:
            try:
                snapshot = self._service.fetch_snapshot(
                    candidate,
                    now_utc,
                    observer=observer,
                )
            except (BackendUnavailableError, ValueError) as exc:
                failures.append(f"{candidate}: {exc}")
                continue
            if candidate != backend_name:
                snapshot = AstronomySnapshot(
                    time=snapshot.time,
                    bodies=snapshot.bodies,
                    observer=snapshot.observer,
                    backend_name=snapshot.backend_name,
                    metadata={
                        **snapshot.metadata,
                        "requested_backend": backend_name,
                        "fallback_backend": candidate,
                    },
                )
            Clock.schedule_once(lambda _dt, snap=snapshot: self._apply_snapshot(request_key, snap), 0)
            return
        preview = self._preview_snapshot(now_utc, backend_name="preview")
        message = "Live astronomy unavailable; showing preview sky. " + " | ".join(failures)
        Clock.schedule_once(
            lambda _dt, snap=preview, msg=message: self._apply_preview_result(request_key, snap, msg),
            0,
        )

    def _preview_snapshot(self, now_utc, backend_name="preview"):
        location = self._profile.location
        return AstronomySnapshot(
            time=build_time_context(now_utc),
            bodies=[],
            observer={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "altitude": location.altitude,
            },
            backend_name=backend_name,
            metadata={"preview": "true"},
        )

    def _apply_preview_snapshot(self, now_utc, status_message: str):
        if self.sky_panel is None:
            return
        preview = self._preview_snapshot(now_utc)
        self._base_snapshot = preview
        self.sky_panel.set_snapshot(preview)
        self.sky_panel.request_render()
        self._update_scene_summary(status_message)

    def _apply_snapshot(self, request_key, snapshot):
        if request_key != self._request_key:
            return
        self._base_snapshot = snapshot
        if self.sky_panel is not None:
            self.sky_panel.set_snapshot(snapshot)
            self.sky_panel.request_render()
            scene = self.sky_panel.get_scene()
        else:
            scene = None
        if scene is None or self._scene_is_empty(scene):
            self._apply_preview_snapshot(snapshot.time.utc_datetime, "Live scene was empty; showing preview sky.")
            return
        requested_backend = snapshot.metadata.get("requested_backend")
        fallback_backend = snapshot.metadata.get("fallback_backend")
        if requested_backend and fallback_backend and fallback_backend != requested_backend:
            status_message = (
                f"Loaded {len(snapshot.bodies)} bodies from {fallback_backend} "
                f"(fallback from {requested_backend})."
            )
        else:
            status_message = f"Loaded {len(snapshot.bodies)} bodies from {snapshot.backend_name}."
        self._update_scene_summary(status_message)

    def _apply_preview_result(self, request_key, snapshot, message: str):
        if request_key != self._request_key:
            return
        self._base_snapshot = snapshot
        if self.sky_panel is not None:
            self.sky_panel.set_snapshot(snapshot)
            self.sky_panel.request_render()
        self._update_scene_summary(message)

    def _apply_error(self, request_key, message: str):
        if request_key != self._request_key:
            return
        self._apply_preview_snapshot(self._display_time_utc, message)

    def _scene_is_empty(self, scene) -> bool:
        return (
            not scene.stars
            and not scene.planets
            and scene.horizon_line is None
            and scene.dome_line is None
        )

    def _update_scene_summary(self, status_message: str):
        if self.status_label is not None:
            # The sky panel renders exclusively through the Kivy canvas
            # (GLES2-safe) since the legacy immediate-mode OpenGL renderer
            # cannot run on Huawei/Android targets.
            self.status_label.text = f"{status_message} [Kivy renderer]"
        if self.sky_panel is None or self.scene_label is None:
            return
        panel_error = self.sky_panel.get_last_error()
        if panel_error:
            self.scene_label.text = f"Render issue: {panel_error}"
            return
        scene = self.sky_panel.get_scene()
        if scene is None:
            self.scene_label.text = "Sky preview unavailable."
            return
        self.scene_label.text = (
            f"Bright stars {scene.metadata['star_count']} | "
            f"Planets {scene.metadata['planet_count']} | "
            f"Aspects {scene.metadata.get('aspect_count', '0')} | "
            f"Zodiac {scene.metadata.get('zodiac_label_count', '0')} | "
            f"Milky Way {scene.metadata.get('milky_way_count', '0')} | "
            f"Equator {'yes' if scene.equatorial_line is not None else 'no'} | "
            f"Horizon {'yes' if scene.horizon_line is not None else 'no'} | "
            f"Dome {'yes' if scene.dome_line is not None else 'no'}"
        )

    def _sync_controls(self, now_utc=None):
        labels = {
            "horizons": "Backend: JPL Horizons",
            "de441": "Backend: DE441 kernel",
        }
        if self.backend_button is not None:
            self.backend_button.text = labels[self._backend_name]
        if self.play_button is not None:
            self.play_button.text = "Pause" if self._animation_enabled else "Play"
        if self.time_label is not None:
            stamp = now_utc or self._display_time_utc
            if self._realtime_animation:
                speed_text = f"{self._animation_speed_multiplier:g}x realtime"
            else:
                speed_text = f"{self._animation_step_minutes:g}m / tick"
            self.time_label.text = (
                f"UTC {stamp:%Y-%m-%d %H:%M:%S}\n"
                f"Observer: {self._profile.location.name or 'custom'} | {speed_text}"
            )

    def _sync_kernel_status(self):
        if self.kernel_label is None:
            return
        if self._backend_name != "de441":
            self.kernel_label.text = "Kernel: inactive while Horizons is selected."
            return
        report = validate_de441_kernel_file()
        if hasattr(self._service, "get_backend"):
            try:
                backend = self._service.get_backend("de441")
            except Exception:
                backend = None
            if backend is not None and hasattr(backend, "validate_kernel"):
                try:
                    report = backend.validate_kernel()
                except Exception as exc:
                    self.kernel_label.text = f"Kernel issue: {exc}"
                    return
        prefix = "Kernel OK" if report.valid else "Kernel issue"
        self.kernel_label.text = f"{prefix}: {report.messages[0]}"

    def _sync_catalog_status(self):
        if self.status_label is None:
            return
        config = self._config.sky
        report = validate_star_catalog_file(
            config.star_catalog_path,
            catalog_format=config.star_catalog_format or None,
            chunk_size=config.lazy_chunk_size,
        )
        prefix = "Catalog OK" if report.valid else "Catalog issue"
        self.status_label.text = f"{prefix}: {report.messages[0]}"

    def _start_timers(self):
        if self._refresh_event is None:
            interval = max(1.0, self._config.sky.refresh_interval_seconds)
            self._refresh_event = Clock.schedule_interval(self.refresh_snapshot, interval)
        if self._animation_enabled and self._animation_event is None:
            interval = max(0.25, self._config.sky.animation_interval_seconds)
            self._animation_event = Clock.schedule_interval(self._advance_animation, interval)

    def _stop_timers(self):
        if self._refresh_event is not None:
            self._refresh_event.cancel()
            self._refresh_event = None
        if self._animation_event is not None:
            self._animation_event.cancel()
            self._animation_event = None

    def toggle_animation(self):
        self._animation_enabled = not self._animation_enabled
        if self._animation_enabled:
            self._start_timers()
        elif self._animation_event is not None:
            self._animation_event.cancel()
            self._animation_event = None
        self._sync_controls()

    def faster_animation(self):
        if self._realtime_animation:
            self._animation_speed_multiplier = min(64.0, self._animation_speed_multiplier * 2.0)
        else:
            self._animation_step_minutes = min(1440.0, self._animation_step_minutes * 2.0)
        self._sync_controls()

    def slower_animation(self):
        if self._realtime_animation:
            self._animation_speed_multiplier = max(0.25, self._animation_speed_multiplier / 2.0)
        else:
            self._animation_step_minutes = max(1.0, self._animation_step_minutes / 2.0)
        self._sync_controls()

    def jump_to_now(self):
        self._display_time_utc = datetime.now(timezone.utc)
        self.refresh_snapshot()

    def _advance_animation(self, *_args):
        dt = float(_args[0]) if _args else 0.0
        if self._realtime_animation:
            step_seconds = max(0.25, dt or self._config.sky.animation_interval_seconds)
            self._display_time_utc = self._display_time_utc + timedelta(
                seconds=step_seconds * self._animation_speed_multiplier
            )
        else:
            self._display_time_utc = self._display_time_utc + timedelta(
                minutes=self._animation_step_minutes
            )
        if self._base_snapshot is None or self.sky_panel is None:
            self.refresh_snapshot()
            return
        self.sky_panel.set_snapshot(self._animated_snapshot(self._base_snapshot, self._display_time_utc))
        self.sky_panel.request_render()
        self._sync_controls(self._display_time_utc)
        self._refresh_scene_labels_only()

    def reset_view(self):
        if self.sky_panel is not None:
            self.sky_panel.reset_view()
            self._refresh_scene_labels_only()

    def show_view_menu(self):
        """Open a popup with tickable checkboxes for each sky layer."""
        if self.sky_panel is None:
            return
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button
        from kivy.uix.checkbox import CheckBox
        from kivy.uix.label import Label
        from kivy.uix.popup import Popup
        from kivy.uix.scrollview import ScrollView

        layers = [
            ("constellations", "Constellations"),
            ("constellation_labels", "Constellation Labels"),
            ("constellation_boundaries", "Constellation Boundaries"),
            ("horizon", "Horizon"),
            ("equator", "Celestial Equator"),
            ("zodiac", "Zodiac Ring"),
            ("milky_way", "Milky Way"),
            ("planet_labels", "Planet Labels"),
            ("planet_trails", "Planet Trails"),
            ("aspects", "Aspects"),
        ]

        content = BoxLayout(orientation="vertical", spacing=6, padding=12)
        scroll = ScrollView(do_scroll_x=False, size_hint=(1, 0.92))
        rows = BoxLayout(
            orientation="vertical",
            spacing=10,
            padding=(0, 4),
            size_hint_y=None,
        )
        rows.bind(minimum_height=rows.setter("height"))

        for option, label in layers:
            row = BoxLayout(
                orientation="horizontal",
                spacing=12,
                size_hint_y=None,
                height=40,
            )
            checkbox = CheckBox(
                active=self.sky_panel.get_layer_option(option),
                size_hint=(None, None),
                size=(40, 40),
            )
            checkbox.bind(
                active=lambda cb, val, opt=option: self._set_layer(opt, val)
            )
            row.add_widget(checkbox)
            row.add_widget(
                Label(
                    text=label,
                    halign="left",
                    valign="middle",
                    color=(0.92, 0.93, 0.97, 1),
                )
            )
            rows.add_widget(row)

        scroll.add_widget(rows)
        content.add_widget(scroll)

        buttons = BoxLayout(
            orientation="horizontal",
            spacing=10,
            size_hint=(1, 0.08),
        )
        buttons.add_widget(Label(text=""))
        close_btn = Button(
            text="Close",
            size_hint=(None, None),
            size=(100, 38),
        )
        buttons.add_widget(close_btn)
        content.add_widget(buttons)

        popup = Popup(
            title="Sky View Layers",
            title_color=(0.9, 0.92, 0.96, 1),
            content=content,
            size_hint=(0.5, 0.7),
            auto_dismiss=True,
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _set_layer(self, layer_name: str, enabled: bool):
        if self.sky_panel is None:
            return
        self.sky_panel.set_layer_option(layer_name, enabled)
        self.sky_panel.request_render()
        self._refresh_scene_labels_only()

    def _refresh_scene_labels_only(self):
        self._update_scene_summary(self.status_label.text if self.status_label is not None else "")

    def _animated_snapshot(self, snapshot: AstronomySnapshot, target_utc: datetime) -> AstronomySnapshot:
        delta_days = (target_utc - snapshot.time.utc_datetime).total_seconds() / 86400.0
        bodies = []
        for body in snapshot.bodies:
            geocentric = body.geocentric
            if (
                geocentric is not None
                and body.velocity is not None
                and geocentric.units == "au"
                and body.velocity.units == "au/day"
            ):
                geocentric = Vector3(
                    x=geocentric.x + (body.velocity.x * delta_days),
                    y=geocentric.y + (body.velocity.y * delta_days),
                    z=geocentric.z + (body.velocity.z * delta_days),
                    units=geocentric.units,
                )
            ecliptic = body.ecliptic
            if ecliptic is not None:
                ecliptic = EclipticCoordinates(
                    longitude_degrees=(
                        ecliptic.longitude_degrees
                        + (ecliptic.longitude_rate_deg_per_day * delta_days)
                    ) % 360.0,
                    latitude_degrees=ecliptic.latitude_degrees,
                    radius_au=ecliptic.radius_au,
                    longitude_rate_deg_per_day=ecliptic.longitude_rate_deg_per_day,
                )
            bodies.append(
                replace(
                    body,
                    geocentric=geocentric,
                    ecliptic=ecliptic,
                    metadata={**body.metadata, "animated": "true"},
                )
            )
        return replace(
            snapshot,
            time=build_time_context(target_utc),
            bodies=bodies,
            metadata={
                **snapshot.metadata,
                "animated": "true",
                "base_snapshot_time": snapshot.time.utc_datetime.isoformat(),
            },
        )

    def go_home(self):
        self.manager.current = "home"
