import os
os.environ["KIVY_LOG_LEVEL"] = "error"
from kivy.core.window import Window
Window.size = (900, 700)

import math
from ui.main import AstroFlowApp
from ui.presets import get_preset

app = AstroFlowApp()
sm = app.build()
home = sm.get_screen("home")
cs = sm.get_screen("chart")

home._pick_preset(get_preset("marilyn monroe"))
home.generate_chart()

wheel = cs.wheel
wheel.size_hint = (None, None)
wheel.size = (460, 460)
wheel.pos = (20, 60)
wheel.set_chart(cs.wheel.chart)  # re-prepare at real size

L = wheel._layout
print("R", round(L["R"]), "| planets", len(L["planets"]),
      "| aspects", len(L["aspects"]), "| houses", len(L["houses"]),
      "| signs", len(L["signs"]))
print("chart_output type:", type(cs.chart_output).__name__)

# planet tap
wheel._handle_tap(L["planets"][0]["x"], L["planets"][0]["y"])
print("after planet tap detail len:", len(cs.chart_output.text))

# aspect tap (pick one clear of planet glyphs)
target = None
for a in L["aspects"]:
    mx, my = (a["x1"] + a["x2"]) / 2, (a["y1"] + a["y2"]) / 2
    if all(math.hypot(mx - p["x"], my - p["y"]) > 22 for p in L["planets"]):
        target = a
        break
if target:
    mx, my = (target["x1"] + target["x2"]) / 2, (target["y1"] + target["y2"]) / 2
    ok = wheel._handle_tap(mx, my)
    print("aspect tap OK:", ok, "| detail len:", len(cs.chart_output.text))
    print("  ->", target["aspect"].planet1_name,
          target["aspect"].type_name, target["aspect"].planet2_name)

# full report button path
cs.show_full_report()
print("full_report len:", len(cs.chart_output.text))

# forecast nav + back
cs.go_to_forecast()
print("screen now:", sm.current)
cs.go_home()
print("back to:", sm.current)
print("INTEGRATION OK")
