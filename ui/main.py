"""AstroFlow Kivy application entry point.

Builds the ``ScreenManager`` with the screens and wires them together.
All astrology logic is delegated to ``core/``; this module only handles
screen management and top-level app configuration.

Run with::

    python -m ui.main
    # or
    python run_app.py
"""

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager

from core.interpretation_store import configure_interpretation_library
from .screens import (
    ChartScreen,
    ForecastScreen,
    HomeScreen,
    InterpretationEditorScreen,
)


# Load the KV layout that defines the look of every screen.
import os
_kv_path = os.path.join(os.path.dirname(__file__), "app.kv")
Builder.load_file(_kv_path)


class AstroFlowApp(App):
    """Top-level Kivy application."""

    title = "AstroFlow"
    _window_size = (1200, 780)

    def build(self) -> ScreenManager:
        if self._window_size:
            Window.size = self._window_size
        configure_interpretation_library(
            os.path.join(self.user_data_dir, "interpretations.json")
        )
        Window.bind(size=self._sync_root_size)
        # NOTE: do NOT set ``Window.size`` here. ``build`` runs before the
        # Window / widget tree are realized, so assigning it this early leaves
        # the root ScreenManager at its default 100x100 and every child
        # (including the chart wheel) collapses -- the wheel then renders at the
        # origin (bottom-left) with a tiny default box instead of filling its
        # area. The size is applied in :meth:`on_start` instead, once the Window
        # exists, which also triggers the layout pass that reflows the root.
        sm = ScreenManager()
        sm.size = Window.size
        sm.pos = (0, 0)
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(ChartScreen(name="chart"))
        sm.add_widget(ForecastScreen(name="forecast"))
        sm.add_widget(InterpretationEditorScreen(name="interpretations"))
        return sm

    def on_start(self):
        # Window is now realized; sizing here reflows the root widget tree so
        # the chart wheel (and all children) get real widths/heights.
        Clock.schedule_once(self._fix_window_size, 0)

    def _fix_window_size(self, dt):
        if self._window_size:
            Window.size = self._window_size
        self._sync_root_size()

    def _sync_root_size(self, *_args):
        if self.root is not None:
            self.root.size = Window.size
            self.root.pos = (0, 0)


if __name__ == "__main__":
    AstroFlowApp().run()