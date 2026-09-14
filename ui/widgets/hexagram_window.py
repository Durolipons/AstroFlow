"""Hexagram display window for the I Ching panel.

Split horizontally: LEFT = graphical hexagram bars (6 lines, revealed
bottom-to-top as each cast lands, bold, moving lines in amber).
RIGHT = info panel that stays empty until all 6 lines are cast, then
reveals the hexagram number, pinyin name, and English name.
"""

from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

try:  # Windows console beep; harmless no-op elsewhere.
    import winsound
except ImportError:
    winsound = None


def _beep(frequency=880, duration=250):
    try:
        if winsound is not None:
            winsound.Beep(int(frequency), int(duration))
    except Exception:
        pass  # audio is cosmetic; never break the cast


class HexFigure(Widget):
    """Canvas drawing of the six line slots, filled bottom-up.

    Yang = unbroken bar, yin = two broken segments, moving lines (6, 9)
    render in amber.  Slots not yet thrown show as dim placeholders.
    """

    values = ListProperty([])

    SLOT_HEIGHT = 6

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._bg_color = Color(0.05, 0.06, 0.08, 1)
            self._bg_rect = Rectangle()
        self._dynamic = []
        self.bind(values=self._redraw, pos=self._redraw, size=self._redraw)
        self._redraw()

    def _slot_rect(self, index):
        """Geometry of line slot ``index`` (0 = bottom / line 1)."""
        slot_h = self.height / self.SLOT_HEIGHT
        bar_h = slot_h * 0.62  # bolder bars
        y = self.y + index * slot_h + (slot_h - bar_h) / 2.0
        w = self.width * 0.90  # wider bars, more prominent
        x = self.x + (self.width - w) / 2.0
        return x, y, w, bar_h

    def _redraw(self, *_args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        for ins in self._dynamic:
            self.canvas.remove(ins)
        self._dynamic = []

        def add(ins):
            self.canvas.add(ins)
            self._dynamic.append(ins)

        for i in range(self.SLOT_HEIGHT):
            x, y, w, h = self._slot_rect(i)
            if i < len(self.values):
                value = self.values[i]
                yang = value in (7, 9)
                if value in (6, 9):
                    add(Color(1.0, 0.55, 0.15, 1))  # amber for moving lines
                elif yang:
                    add(Color(0.95, 0.97, 1.0, 1))  # bright white-silver for yang
                else:
                    add(Color(0.55, 0.58, 0.68, 1))  # darker slate for yin
                if yang:
                    add(Rectangle(pos=(x, y), size=(w, h)))
                else:
                    gap = w * 0.14
                    seg = (w - gap) / 2.0
                    add(Rectangle(pos=(x, y), size=(seg, h)))
                    add(Rectangle(pos=(x + seg + gap, y), size=(seg, h)))
            else:
                # dim placeholder for a not-yet-thrown line
                add(Color(0.24, 0.26, 0.33, 1))
                add(Rectangle(pos=(x, y + h / 2 - dp(1)), size=(w, dp(2))))


class HexagramWindow(BoxLayout):
    """Split horizontally: LEFT = bars, RIGHT = info (revealed at end).

    The canvas figure occupies the left portion and draws the six lines
    bottom-to-top as each toss lands.  The right portion is initially a
    faint placeholder; when reveal() is called (all 6 lines done) it swaps
    in the hexagram number, pinyin, and English name.
    """

    values = ListProperty([])
    revealed = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", spacing=dp(16), **kwargs)

        self._figure = HexFigure()
        self.add_widget(self._figure)

        self._info_panel = BoxLayout(orientation="vertical",
                                     spacing=dp(4), size_hint_x=0.38)

        self._title = Label(size_hint_y=None, height=dp(30),
                            bold=True, font_size=dp(17),
                            text="", color=(0.9, 0.4, 0.2, 1),
                            halign="center", valign="middle")
        self._title.bind(size=self._title.setter("text_size"))

        self._sep = Label(size_hint_y=None, height=dp(2),
                          color=(0.35, 0.38, 0.45, 1))

        self._pinyin = Label(size_hint_y=None, height=dp(26),
                             font_size=dp(15),
                             text="", color=(0.8, 0.82, 0.88, 1),
                             halign="center", valign="middle")
        self._pinyin.bind(size=self._pinyin.setter("text_size"))

        self._english = Label(size_hint_y=None, height=dp(26),
                              font_size=dp(13),
                              text="", color=(0.7, 0.72, 0.78, 1),
                              halign="center", valign="middle")
        self._english.bind(size=self._english.setter("text_size"))

        self._placeholder = Label(size_hint_y=None, height=dp(88),
                                  text="---",
                                  font_size=dp(28),
                                  color=(0.18, 0.19, 0.24, 1),
                                  halign="center", valign="middle")
        self._placeholder.bind(size=self._placeholder.setter("text_size"))

        self._info_panel.add_widget(self._placeholder)
        self.add_widget(self._info_panel)

    def _swap_placeholder_for_info(self):
        self._info_panel.remove_widget(self._placeholder)
        self._info_panel.add_widget(self._title)
        self._info_panel.add_widget(self._sep)
        self._info_panel.add_widget(self._pinyin)
        self._info_panel.add_widget(self._english)

    def reset(self):
        self.values = []
        self.revealed = False
        self._title.text = ""
        self._pinyin.text = ""
        self._english.text = ""
        if self._placeholder.parent is not self._info_panel:
            for w in (self._title, self._sep, self._pinyin, self._english):
                self._info_panel.remove_widget(w)
            self._info_panel.add_widget(self._placeholder)

    def add_line(self, value):
        self.values = self.values + [value]

    def reveal(self, number, name_pinyin, name_en):
        self.revealed = True
        self._swap_placeholder_for_info()
        self._title.text = f"#{number}"
        self._pinyin.text = name_pinyin
        self._english.text = name_en
        _beep(880, 250)
