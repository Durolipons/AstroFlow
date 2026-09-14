"""Divination panel: I Ching casting screen.

Lets the user type a question, pick a casting method (three-coin toss or
yarrow stalks), and cast. The cast is performed by ``core.iching`` using the
OS random-noise source; the reading is rendered by
``core.iching_interpretation`` into the scrollable report window.

NOTE: All divination logic lives in ``core/``; this screen only collects
input and displays the report.
"""

from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.screenmanager import Screen

from core import iching as IC
from core import iching_interpretation as IP
from ui.widgets.astro_clock import _copy_to_clipboard  # house copy helper
from ui.widgets import HexagramWindow, IchingCastWidget  # noqa: F401 (KV factory)

# Spinner label -> engine method key.
METHODS = {"Three-Coin Toss": "coins", "Yarrow Stalks": "yarrow"}


class DivinationScreen(Screen):
    """I Ching divination panel (question, cast method, report)."""

    question_input = ObjectProperty(None)
    method_spinner = ObjectProperty(None)
    divination_output = ObjectProperty(None)
    divination_status = ObjectProperty(None)
    cast_widget = ObjectProperty(None)
    hex_window = ObjectProperty(None)

    status_text = StringProperty("Ready. Enter a question and cast.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._db = None
        self._last_result = None

    # -- casting ------------------------------------------------------------
    _pending_method = StringProperty("")
    _pending_result = ObjectProperty(None, allownone=True)
    _armed = ObjectProperty(False, allownone=False)
    _thrown = ObjectProperty(0, allownone=False)

    def throw_next(self):
        """Advance exactly one throw into the Hexagram window (L1 first).

        The first press of Cast arms a fresh reading: a new 6-line cast is
        generated from the chosen method, the Hexagram window is reset, and
        the coins begin flickering for L1. Each subsequent press advances
        exactly one more throw (L2, L3, ... L6). After the sixth line is
        drawn, the hexagram is revealed, a ping sounds, and the full reading
        renders in the text window.

        This is the manual one-press-per-line model: no cast ever auto-plays
        all six throws on a single button press.
        """
        if self.divination_output is None or self.cast_widget is None:
            return
        if not self._armed:
            # Arm a fresh reading.
            method = METHODS.get(getattr(self.method_spinner, "text", ""),
                                 "coins")
            self._pending_method = method
            try:
                if self._db is None:
                    self._db = IC.Database()
                self._pending_result = IC.reading(IC.cast(method), self._db)
            except Exception as exc:  # defensive: never crash the panel
                self.status_text = f"Error: {exc}"
                return
            self._thrown = 0
            values = self._pending_result["values"]
            if self.hex_window is not None:
                self.hex_window.reset()
            # Begin the manual cast: arm the 6-value list, throw line 1,
            # the reading and produces the first line.
            self.cast_widget.begin_cast(values)
            self.cast_widget.throw_next()
            self._armed = True
            self._thrown = 1
            self.status_text = (
                "Line 1 drawn. Press Cast for line 2.")
            return
        # Already armed: advance exactly one throw.
        if self._thrown >= 6:
            # Already complete — start a fresh reading on the next press.
            self._reset_arm()
            return
        self.cast_widget.throw_next()
        self._thrown += 1
        if self._thrown < 6:
            self.status_text = (
                f"Line {self._thrown} drawn. Press Cast for line "
                f"{self._thrown + 1}.")
        else:
            self.status_text = (
                "Line 6 drawn. The hexagram is revealing...")

    def _reset_arm(self):
        self._armed = False
        self._thrown = 0
        self._pending_result = None
        self.status_text = "Ready. Enter a question and cast."

    def cancel_cast(self):
        """Cancel any running cast and reset to a clean state."""
        if self.cast_widget is not None and self.cast_widget.is_running:
            self.cast_widget.stop()
        self._reset_arm()
        if self.hex_window is not None:
            self.hex_window.reset()
        if self.divination_output is not None:
            self.divination_output.text = (
                "Ask your question and press Cast to receive the oracle.")

    def _on_line_landed(self, widget, position, value):
        """One throw landed: draw its line in the hexagram window."""
        if self.hex_window is not None:
            self.hex_window.add_line(value)

    def _on_cast_complete(self, widget, values):
        """All six lines drawn: reveal the hexagram, ping, render report."""
        result = getattr(self, "_pending_result", None)
        if result is None:
            return
        prim = result["primary"]
        if self.hex_window is not None:
            self.hex_window.reveal(prim["number"], prim["name_pinyin"],
                                   prim["name_en"])
        question = ""
        if self.question_input is not None:
            question = self.question_input.text.strip()
        report = IP.iching_report(result, question=question)
        self.divination_output.text = report
        prim = result["primary"]
        moving = result["moving"]
        if moving:
            self.status_text = (f"#{prim['number']} {prim['name_en']} — "
                                f"moving line(s) {', '.join(map(str, moving))}")
        else:
            self.status_text = f"#{prim['number']} {prim['name_en']}"
        self._reset_arm()

    # -- output helpers -----------------------------------------------------
    def copy_output(self):
        if self.divination_output is not None:
            _copy_to_clipboard(self.divination_output.text)

    def scale_font(self, delta: int):
        """Grow/shrink the report font like the other report panels."""
        if self.divination_output is None:
            return
        try:
            size = float(self.divination_output.font_size)
        except (TypeError, ValueError):
            size = 12.0
        self.divination_output.font_size = max(8.0, size + delta)

    # -- navigation ---------------------------------------------------------
    def go_home(self):
        self.manager.current = "home"