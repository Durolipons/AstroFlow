"""Higher-level Kivy container for the live sky viewport."""

from __future__ import annotations

from kivy.logger import Logger
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout

from .sky_widget import SkyViewportWidget  # noqa: F401 (KV factory)


class SkyPanel(BoxLayout):
    """Toolbar + viewport wrapper with a renderer-facing API."""

    viewport = ObjectProperty(None)
    last_panel_error = ""

    def set_snapshot(self, snapshot):
        if self.viewport is not None:
            try:
                self.viewport.set_snapshot(snapshot)
                self.last_panel_error = ""
            except Exception as exc:
                self.last_panel_error = str(exc)
                Logger.exception("SkyPanel failed to set snapshot")

    def get_scene(self):
        if self.viewport is None:
            return None
        try:
            scene = self.viewport.get_scene()
            self.last_panel_error = ""
            return scene
        except Exception as exc:
            self.last_panel_error = str(exc)
            Logger.exception("SkyPanel failed to build scene")
            return None

    def reset_view(self):
        if self.viewport is not None:
            self.viewport.reset_view()

    def zoom_in(self):
        if self.viewport is not None:
            self.viewport.zoom(1.15)

    def zoom_out(self):
        if self.viewport is not None:
            self.viewport.zoom(0.85)

    def rotate_left(self):
        if self.viewport is not None:
            self.viewport.rotate(-8.0)

    def rotate_right(self):
        if self.viewport is not None:
            self.viewport.rotate(8.0)

    def set_layer_option(self, name: str, enabled: bool):
        if self.viewport is not None:
            self.viewport.set_layer_option(name, enabled)

    def toggle_layer_option(self, name: str) -> bool:
        if self.viewport is None:
            return False
        return self.viewport.toggle_layer_option(name)

    def get_layer_option(self, name: str) -> bool:
        if self.viewport is None:
            return False
        return self.viewport.get_layer_option(name)

    def get_buffers(self):
        if self.viewport is None:
            return {}
        return self.viewport.get_buffers()

    def request_render(self):
        if self.viewport is not None:
            self.viewport.request_render()

    def get_last_error(self) -> str:
        if self.last_panel_error:
            return self.last_panel_error
        if self.viewport is None:
            return ""
        return getattr(self.viewport, "last_render_error", "")

    def using_opengl(self) -> bool:
        if self.viewport is None:
            return False
        return bool(getattr(self.viewport, "using_opengl", False))

    def opengl_available(self) -> bool:
        if self.viewport is None:
            return False
        return bool(getattr(self.viewport, "opengl_available", False))

    def set_use_opengl(self, enabled: bool) -> bool:
        if self.viewport is None:
            return False
        return self.viewport.set_use_opengl(enabled)
