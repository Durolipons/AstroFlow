"""Animated I Ching coin-toss widget (manual, one throw per press).

The Cast button is pressed six times, once per line (bottom to top). Each
press animates a single three-coin toss: the coins flip through random
faces, settle on the final toss, and the resulting line stacks into the
hexagram column. The widget's ``line_callback`` fires per landed line and
the ``callback`` fires only after the sixth line lands.

Moving lines (6 = old yin, 9 = old yang) render in amber.
"""

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

# Line value -> yang?
_YANG = {6: False, 7: True, 8: False, 9: True}
_MOVING = (6, 9)

FLIP_INTERVAL = 0.07   # seconds between coin-face flickers
FLIPS_PER_THROW = 9    # flicker frames before the coins settle
SETTLE_PAUSE = 0.45    # pause after a line lands


class CoinFace(Label):
    """One coin: a disc with the traditional square hole; shows H/T face."""

    heads = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bold = True
        self.font_size = dp(18)
        self.bind(pos=self._redraw, size=self._redraw, heads=self._redraw)
        with self.canvas:
            self._coin_color = Color(0.78, 0.62, 0.25, 1)
            self._coin = Ellipse()
            self._hole_color = Color(0.08, 0.09, 0.12, 1)
            self._hole = Rectangle()
        self._redraw()

    def _redraw(self, *_args):
        d = min(self.width, self.height)
        cx, cy = self.center_x, self.center_y
        self._coin.pos = (cx - d / 2, cy - d / 2)
        self._coin.size = (d, d)
        hole = d * 0.28
        self._hole.pos = (cx - hole / 2, cy - hole / 2)
        self._hole.size = (hole, hole)
        self.text = "H" if self.heads else "T"
        self.color = (0.1, 0.08, 0.02, 1) if self.heads else (0.95, 0.9, 0.7, 1)


class LineRow(BoxLayout):
    """One hexagram line row: place label + the bar itself."""

    def __init__(self, position, value, **kwargs):
        super().__init__(orientation="horizontal", spacing=dp(6), **kwargs)
        self.position = position
        self.value = value
        self.size_hint_y = None
        self.height = dp(22)

        lbl = Label(text=f"L{position}", size_hint_x=None, width=dp(32),
                    font_size=dp(11), color=(0.7, 0.72, 0.78, 1))
        self.add_widget(lbl)

        bar = Widget()
        self.add_widget(bar)
        self._bar = bar
        with bar.canvas:
            if value in _MOVING:
                Color(1.0, 0.55, 0.15, 1)   # amber for moving lines
            elif _YANG[value]:
                Color(0.85, 0.87, 0.92, 1)
            else:
                Color(0.55, 0.58, 0.66, 1)
            self._bar_rects = []
            for _seg in self._segments():
                self._bar_rects.append(Rectangle())
        self.sync_bar()

    def _segments(self):
        """Rectangle positions for this line's geometry (yang=1, yin=2)."""
        bar = self._bar
        if _YANG[self.value]:
            return [bar.pos]
        seg_gap = dp(14)
        seg = (bar.width - seg_gap) / 2.0
        return [bar.pos, (bar.x + seg + seg_gap, bar.y)]

    def sync_bar(self):
        bar = self._bar
        h = bar.height * 0.35
        seg_gap = dp(14)
        if _YANG[self.value]:
            rects = [(bar.pos, (bar.width, h))]
        else:
            seg = (bar.width - seg_gap) / 2.0
            rects = [(bar.pos, (seg, h)),
                     ((bar.x + seg + seg_gap, bar.y), (seg, h))]
        for rect, (pos, size) in zip(self._bar_rects, rects):
            rect.pos = pos
            rect.size = size


class IchingCastWidget(BoxLayout):
    """Animation window: coin row on top, stacked hexagram lines below.

    Manual operation: ``begin_cast`` arms a cast, then each ``throw_next``
    (one press of the Cast button) animates exactly one throw.
    """

    values = ListProperty([])
    callback = ObjectProperty(None, allownone=True)
    line_callback = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(8),
                         padding=dp(8), **kwargs)
        self._lines_layout = GridLayout(cols=1, size_hint_y=None,
                                        spacing=dp(3))
        self._lines_layout.bind(minimum_height=
                                self._lines_layout.setter("height"))

        self._coins = BoxLayout(size_hint_y=None, height=dp(56),
                                spacing=dp(18))
        self._coin_faces = [CoinFace() for _ in range(3)]
        for c in self._coin_faces:
            self._coins.add_widget(c)

        self._status = Label(size_hint_y=None, height=dp(22),
                             font_size=dp(12), color=(0.9, 0.4, 0.2, 1),
                             text="Press Cast to throw the coins.")

        # Line stack pinned to the bottom: spacer above grows.
        stack = BoxLayout(orientation="vertical")
        stack.add_widget(Widget())
        stack.add_widget(self._lines_layout)

        self.add_widget(self._status)
        self.add_widget(self._coins)
        self.add_widget(stack)

        self._clock_event = None
        self._settle_event = None
        self._watchdog_event = None
        self._completed = False
        self._running = False
        self._generation = 0


    # -- public API ----------------------------------------------------------
    def begin_cast(self, values, method_label=""):
        """Arm a new cast: six values ready, no throws performed yet.

        Each subsequent :meth:`throw_next` call (one press of the Cast
        button) animates exactly one throw; the reading completes on the
        sixth.
        """
        self.stop()
        self.values = list(values)
        self._lines_layout.clear_widgets()
        self._throw_index = 0
        self._completed = False
        self._running = False
        self._generation += 1
        self._method_label = method_label
        self._status.text = "Press Cast to throw line 1."

    def throw_next(self):
        """Animate the next single throw.

        Returns True when a throw was started, False when the cast is
        finished, already mid-throw, or has no values to throw.
        """
        if self._completed or self._running:
            return False
        if not self.values or self._throw_index >= len(self.values):
            self._force_finish()  # safety net; completes the reading
            return False
        self._running = True
        self._generation += 1
        self._status.text = (f"Throwing for line "
                             f"{self._throw_index + 1}...")
        self._start_throw()
        # Per-throw watchdog: even if scheduling goes wrong on some machine,
        # this throw lands shortly after its expected duration.
        expected = FLIPS_PER_THROW * FLIP_INTERVAL + SETTLE_PAUSE
        self._watchdog_event = Clock.schedule_once(
            self._on_watchdog, expected + 2.0)
        return True

    def is_complete(self):
        return self._completed

    def _on_watchdog(self, dt):
        """Belt-and-braces terminator: land the in-flight throw."""
        self._watchdog_event = None
        if self._running and not self._completed:
            self._status.text = "Completing throw..."
            self._land_line()

    def stop(self):
        """Cancel any running animation."""
        self._running = False
        self._cancel_clock()
        if self._settle_event is not None:
            self._settle_event.cancel()
            self._settle_event = None
        if self._watchdog_event is not None:
            self._watchdog_event.cancel()
            self._watchdog_event = None

    # -- animation internals ---------------------------------------------------
    def _start_throw(self, gen=None):
        if gen is None:
            gen = self._generation
        if not self._running or gen != self._generation:
            return  # a newer cast superseded this chain
        # Hard guard: never start beyond the supplied values.
        if self._throw_index >= len(self.values):
            self._force_finish()
            return
        self._flips_left = FLIPS_PER_THROW
        self._cancel_clock()
        self._clock_event = Clock.schedule_interval(
            self._flip_frame, FLIP_INTERVAL)

    def _flip_frame(self, dt):
        if not self._running:
            self._cancel_clock()
            return False  # auto-cancel: cast was stopped/superseded
        # Flicker the coins through changing faces; the final frame shows
        # the true toss (heads count derived from the engine's line value).
        # NOTE: an exception escaping a Kivy interval callback is logged and
        # the interval keeps firing forever, so everything here is guarded:
        # any error force-finishes the cast and renders the reading anyway.
        try:
            final = self._flips_left <= 1
            if final:
                value = self.values[self._throw_index]
                heads = {9: 3, 7: 2, 8: 1, 6: 0}[value]
            else:
                # deterministic pseudo-random flicker across frames
                heads = (self._throw_index * 5 + self._flips_left * 3) % 4
            bits = [i < heads for i in range(3)]
            for face, b in zip(self._coin_faces, bits):
                face.heads = b
            self._flips_left -= 1
            if final:
                self._cancel_clock()
                gen = self._generation
                self._settle_event = Clock.schedule_once(
                    lambda _dt, g=gen: self._land_line(g), SETTLE_PAUSE)
        except Exception as exc:
            self._cancel_clock()
            self._status.text = f"Casting glitch ({exc}); landing the line."
            self._land_line()
        return True  # keep the interval alive until the final frame cancels it

    def _land_line(self, gen=None):
        try:
            if gen is not None and gen != self._generation:
                return  # stale chain from a superseded cast
            if self._throw_index >= len(self.values):
                return  # nothing to land
            idx = self._throw_index
            value = self.values[idx]
            self._lines_layout.add_widget(
                LineRow(position=idx + 1, value=value))
            if self.line_callback is not None:
                self.line_callback(self, idx + 1, value)
            names = {6: "Old Yin (moving)", 7: "Young Yang",
                     8: "Young Yin", 9: "Old Yang (moving)"}
            self._throw_index += 1
            if self._throw_index < len(self.values):
                self._status.text = (
                    f"Line {idx + 1}: {value} — {names[value]}. "
                    f"Press Cast for line {self._throw_index + 1}.")
                self._running = False  # wait for the next button press
                self._cancel_clock()
                if self._watchdog_event is not None:
                    self._watchdog_event.cancel()
                    self._watchdog_event = None
            else:
                self._status.text = (
                    f"Line {idx + 1}: {value} — {names[value]}. "
                    "The hexagram is complete.")
                self._finish()
        except Exception as exc:
            self._status.text = f"Casting glitch ({exc}); completing the cast."
            self._force_finish()

    def _force_finish(self):
        """Land every remaining line immediately and complete the cast."""
        self._cancel_clock()
        if self._settle_event is not None:
            self._settle_event.cancel()
            self._settle_event = None
        while self._throw_index < len(self.values):
            idx = self._throw_index
            value = self.values[idx]
            self._lines_layout.add_widget(
                LineRow(position=idx + 1, value=value))
            if self.line_callback is not None:
                self.line_callback(self, idx + 1, value)
            self._throw_index += 1
        self._status.text = "The hexagram is complete."
        self._finish()

    def _finish(self):
        """Mark the cast complete and stop the watchdog."""
        self._running = False
        if self._watchdog_event is not None:
            self._watchdog_event.cancel()
            self._watchdog_event = None
        self._fire_callback()

    def _fire_callback(self):
        """Invoke the completion callback exactly once per cast."""
        if self._completed:
            return
        self._completed = True
        if self.callback is not None:
            self.callback(self, list(self.values))

    def _cancel_clock(self):
        if self._clock_event is not None:
            self._clock_event.cancel()
            self._clock_event = None
