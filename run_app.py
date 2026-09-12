"""Convenience launcher for the AstroFlow Kivy UI.

Run this from the project root::

python run_app.py
 
   

It simply hands control to ``ui.main.AstroFlowApp``.
"""

from ui.main import AstroFlowApp

if __name__ == "__main__":
    AstroFlowApp().run()