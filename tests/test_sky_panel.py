"""Tests for the standalone astronomy sky panel wiring."""

from datetime import datetime, timezone

from astronomy import KernelValidationResult
from astronomy.backends import BackendUnavailableError
from astronomy.kivy.sky_widget import SkyViewportWidget
from astronomy.models import (
    AstronomySnapshot,
    BodyState,
    EclipticCoordinates,
    EquatorialCoordinates,
)
from astronomy.timebase import build_time_context
from kivy.clock import Clock
from kivy.core.window import Window

from core import constants as C
from core.models import BirthData, Location
from ui.main import AstroFlowApp


def test_sky_screen_is_registered_and_hosted():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    assert sky is not None
    assert sky.sky_panel is not None
    assert sky.sky_panel.viewport is not None
    assert hasattr(sky.sky_panel.viewport, "renderer")


def test_home_screen_can_open_sky_panel_with_current_profile():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    home = sm.get_screen("home")
    home.name_input.text = "Sky User"
    home.date_input.text = "2001-02-03"
    home.time_input.text = "04:05"
    home.latlon_input.text = "10.0, 20.0"
    home.tz_input.text = "0"

    home.go_to_sky()
    sky = sm.get_screen("sky")
    assert sm.current == "sky"
    assert sky._profile.name == "Sky User"
    assert sky._profile.location.latitude == 10.0


def test_sky_panel_viewport_accepts_astronomy_snapshot():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    snapshot = AstronomySnapshot(
        time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
        bodies=[
            BodyState(
                body_id=C.MARS,
                name="Mars",
                equatorial=EquatorialCoordinates(ra_hours=5.0, dec_degrees=20.0, distance_au=1.2),
                ecliptic=EclipticCoordinates(
                    longitude_degrees=120.0,
                    latitude_degrees=1.0,
                    radius_au=1.2,
                    longitude_rate_deg_per_day=0.5,
                ),
            )
        ],
        backend_name="de441",
    )
    sky.sky_panel.set_snapshot(snapshot)
    assert sky.sky_panel.viewport.renderer._snapshot.backend_name == "de441"
    assert sky.sky_panel.using_opengl() is False


def test_sky_screen_animation_and_kernel_status_controls():
    class FakeBackend:
        def validate_kernel(self):
            return KernelValidationResult(
                path=r"C:\kernels\de441.bsp",
                valid=True,
                exists=True,
                readable=True,
                segment_count=42,
                messages=["DE441 kernel validated."],
            )

    class FakeService:
        def get_backend(self, name):
            assert name == "de441"
            return FakeBackend()

    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    sky.set_astronomy_service(FakeService())
    sky._backend_name = "de441"
    sky._animation_enabled = False
    sky._animation_speed_multiplier = 2.0
    sky._realtime_animation = True
    sky._display_time_utc = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    sky.refresh_snapshot = lambda *_args: None
    sky._base_snapshot = sky._preview_snapshot(sky._display_time_utc)

    sky._sync_kernel_status()
    assert "Kernel OK" in sky.kernel_label.text

    sky.toggle_animation()
    assert sky._animation_enabled is True
    assert sky.play_button.text == "Pause"

    sky._advance_animation(2.0)
    assert sky._display_time_utc == datetime(2024, 5, 1, 12, 0, 4, tzinfo=timezone.utc)
    assert sky.sky_panel.viewport.renderer._snapshot.metadata["animated"] == "true"


def test_sky_screen_layer_toggles_update_renderer_state():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    sky._display_time_utc = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    sky.sky_panel.set_snapshot(
        AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="de441",
        )
    )

    sky.sky_panel.set_layer_option("planet_trails", True)
    sky.sky_panel.set_layer_option("constellations", False)
    sky.sky_panel.set_layer_option("constellation_labels", False)
    sky.sky_panel.set_layer_option("constellation_boundaries", False)
    sky.sky_panel.set_layer_option("equator", False)
    sky.sky_panel.set_layer_option("zodiac", False)
    sky.sky_panel.set_layer_option("milky_way", False)
    sky.sky_panel.set_layer_option("aspects", False)

    assert sky.sky_panel.get_layer_option("planet_trails") is True
    assert sky.sky_panel.get_layer_option("constellations") is False
    assert sky.sky_panel.get_layer_option("constellation_labels") is False
    assert sky.sky_panel.get_layer_option("constellation_boundaries") is False
    assert sky.sky_panel.get_layer_option("equator") is False
    assert sky.sky_panel.get_layer_option("zodiac") is False
    assert sky.sky_panel.get_layer_option("milky_way") is False
    assert sky.sky_panel.get_layer_option("aspects") is False


def test_sky_screen_uses_preview_scene_when_live_backends_fail():
    class FailingService:
        def fetch_snapshot(self, backend_name, moment_utc, observer=None, body_ids=None, use_cache=True):
            raise BackendUnavailableError(f"{backend_name} unavailable")

        def get_backend(self, name):
            raise BackendUnavailableError(f"{name} unavailable")

    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    sky.set_astronomy_service(FailingService())
    sky._backend_name = "de441"
    sky._display_time_utc = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    request_key = ("de441", "2024-05-01T12:00:00+00:00")
    sky._request_key = request_key

    sky._load_snapshot_worker(request_key, "de441", sky._display_time_utc, sky._profile.location)
    Clock.tick()

    scene = sky.sky_panel.get_scene()
    assert scene is not None
    assert len(scene.stars) > 0
    assert scene.horizon_line is not None
    assert scene.dome_line is None
    assert sky.sky_panel.viewport.renderer._snapshot.backend_name == "preview"
    assert "preview sky" in sky.status_label.text.lower()
    assert "kivy renderer" in sky.status_label.text.lower()


def test_sky_viewport_builds_scene_before_layout_has_real_size():
    Window.size = (1200, 780)
    widget = SkyViewportWidget()
    widget.size = (0, 0)
    widget.set_snapshot(
        AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        )
    )

    scene = widget.get_scene()

    assert scene is not None
    assert len(scene.stars) > 0
    assert scene.horizon_line is not None
    assert scene.dome_line is None


def test_sky_viewport_render_uses_valid_region_before_layout():
    Window.size = (1200, 780)
    widget = SkyViewportWidget()
    widget.size = (0, 0)
    widget._use_gl_callback = True

    calls = []

    def fake_draw(width, height, viewport_x=0, viewport_y=0):
        calls.append((width, height, viewport_x, viewport_y))

    widget.renderer.draw = fake_draw
    widget._render_gl()

    assert calls
    width, height, viewport_x, viewport_y = calls[-1]
    assert width > 0
    assert height > 0
    assert viewport_x == 0
    assert viewport_y == 0


def test_sky_viewport_builds_overlay_instructions_from_scene():
    Window.size = (1200, 780)
    widget = SkyViewportWidget()
    widget.size = (776, 304)
    widget.set_snapshot(
        AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        )
    )

    widget.request_render()
    Clock.tick()

    assert widget._overlay_instruction_count > 0
    assert widget._overlay_label_count > 0
    assert widget.using_opengl is False


def test_sky_viewport_builds_cached_milky_way_mesh():
    Window.size = (1200, 780)
    widget = SkyViewportWidget()
    widget.size = (776, 304)
    widget.set_snapshot(
        AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        )
    )

    scene = widget.get_scene()
    vertices, indices = widget._milky_way_mesh(scene)
    vertices2, indices2 = widget._milky_way_mesh(scene)

    assert vertices
    assert indices
    assert vertices == vertices2
    assert indices == indices2


def test_sky_viewport_request_render_refreshes_overlay_without_gl_callback():
    Window.size = (1200, 780)
    widget = SkyViewportWidget()
    widget.size = (776, 304)
    widget.set_snapshot(
        AstronomySnapshot(
            time=build_time_context(datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)),
            bodies=[],
            observer={"latitude": 51.5, "longitude": 0.0, "altitude": 0.0},
            backend_name="preview",
        )
    )

    widget._overlay_instruction_count = 0
    widget.request_render()
    Clock.tick()

    assert widget._overlay_instruction_count > 0
    assert widget._overlay_label_count > 0


def test_sky_viewport_drag_updates_planetarium_view():
    class DummyTouch:
        def __init__(self):
            self.pos = (40, 30)
            self.ud = {"sky_anchor": (20, 20)}
            self.modifiers = []
            self.grab_current = object()

    widget = SkyViewportWidget()
    widget.pos = (0, 0)
    widget.size = (200, 120)
    calls = []
    widget.pan = lambda ra_delta, dec_delta: calls.append((ra_delta, dec_delta))

    assert widget.on_touch_move(DummyTouch()) is True
    assert calls
    # "Grab the sky": dragging right (+dx) must turn the view west so the sky
    # follows the finger, which means a negative azimuth/ra delta.
    assert calls[-1][0] < 0.0


def test_sky_viewport_consumes_middle_mouse_drag_without_bubbling():
    class DummyTouch:
        def __init__(self):
            self.pos = (30, 20)
            self.button = "middle"
            self.ud = {}
            self.modifiers = []
            self.grab_current = None

        def grab(self, widget):
            self.grab_current = widget

        def ungrab(self, widget):
            if self.grab_current is widget:
                self.grab_current = None

    widget = SkyViewportWidget()
    widget.pos = (0, 0)
    widget.size = (200, 120)
    touch = DummyTouch()

    assert widget.on_touch_down(touch) is True
    assert touch.grab_current is widget
    touch.pos = (60, 40)
    assert widget.on_touch_move(touch) is True
    assert widget.on_touch_up(touch) is True
    assert touch.grab_current is None


def test_sky_screen_toggle_requests_render():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    calls = []
    sky.sky_panel.request_render = lambda: calls.append("render")

    sky._set_layer("constellations", False)

    assert calls == ["render"]


def test_sky_screen_renderer_toggle_is_retired():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    # The separate immediate-mode OpenGL renderer is retired from the runtime
    # path: there is no renderer toggle, no renderer button, and the viewport
    # always uses the Kivy canvas (GLES2-safe).
    assert not hasattr(sky, "toggle_renderer")
    assert not hasattr(sky, "renderer_button")
    assert sky.sky_panel.using_opengl() is False
    assert sky.sky_panel.viewport._use_gl_callback is False


def test_sky_viewport_never_enables_opengl():
    widget = SkyViewportWidget()
    widget._gl_supported = True

    active = widget.set_use_opengl(True)

    assert active is False
    assert widget.using_opengl is False
    assert widget._gl_fbo is None
    assert widget.last_render_error == ""


def test_sky_screen_can_navigate_home_even_if_render_fails():
    Window.size = (1200, 780)
    app = AstroFlowApp()
    sm = app.build()
    app.root = sm
    app._fix_window_size(0)
    for _ in range(4):
        Clock.tick()

    sky = sm.get_screen("sky")
    sm.current = "sky"
    sky.sky_panel.viewport._use_gl_callback = True

    def boom(_width, _height, viewport_x=0, viewport_y=0):
        raise RuntimeError("render boom")

    sky.sky_panel.viewport.renderer.draw = boom
    sky.sky_panel.viewport._render_gl()

    assert "render boom" in sky.sky_panel.get_last_error()
    sky.go_home()
    assert sm.current == "home"
