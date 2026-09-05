"""Are the blit text textures blank, or are the Rectangles not drawing?"""
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("KIVY_LOG_LEVEL", "error")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from kivy.core.window import Window  # noqa: E402
from kivy.clock import Clock  # noqa: E402

from core.chart import calculate_birth_chart  # noqa: E402
from core.models import BirthData, Location  # noqa: E402
from ui.main import AstroFlowApp  # noqa: E402
from ui.widgets.chart_wheel import glyph_font_path  # noqa: E402

Window.size = (900, 700)
app = AstroFlowApp()
sm = app.build()
sm.transition.duration = 0
sm.current = "chart"
wheel = sm.get_screen("chart").wheel
wheel.set_chart(
    calculate_birth_chart(
        BirthData(
            name="Probe",
            birth_datetime=datetime(2000, 1, 1, 12, 0, tzinfo=timezone.utc),
            location=Location(latitude=51.5, longitude=-0.1),
        )
    )
)
for _ in range(3):
    Clock.tick()


def ink_of(tex):
    if tex is None:
        return "None", 0, 0
    buf = tex.pixels
    ink = sum(1 for i in range(0, len(buf), 4) if buf[i + 3] > 30)
    return tex.size, ink, len(buf)


print("glyph font:", glyph_font_path(), flush=True)
tex1 = wheel._text_texture("\u2648", 13, (0.12, 0.12, 0.16, 1), astro=True)
print("aries tex:", ink_of(tex1), flush=True)
tex2 = wheel._text_texture("12", 9, (0.35, 0.35, 0.42, 1), astro=False)
print("'12' tex:", ink_of(tex2), flush=True)
print("cache entries:", len(wheel._text_tex_cache), flush=True)


def phase(dt):
    img = wheel.export_as_image()
    img.save("_wheelshot3.png", flipped=False)
    t = img.texture
    buf = t.pixels
    # count light pixels (white glyph ink on dark ring) and dark ink
    w, h = t.width, t.height
    stride = w * 4
    light = dark = 0
    for y in range(h):
        row = buf[y * stride:(y + 1) * stride]
        for x in range(w):
            i = x * 4
            r, g, b, a = row[i], row[i + 1], row[i + 2], row[i + 3]
            if a > 30:
                if r > 190 and g > 190 and b > 190:
                    light += 1
                elif r < 80 and g < 80 and b < 80:
                    dark += 1
    print("export", t.width, t.height, "light_px:", light, "dark_px:", dark,
          flush=True)
    from kivy.base import stopTouchApp
    stopTouchApp()


Clock.schedule_once(phase, 0.5)
from kivy.base import runTouchApp  # noqa: E402
runTouchApp()
