"""Android entry point for AstroFlow.

Buildozer expects main.py at the project root. This thin shim hands
control to the real Kivy App defined in ui.main.
"""

from ui.main import AstroFlowApp


if __name__ == "__main__":
    AstroFlowApp().run()


