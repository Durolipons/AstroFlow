"""Convenience launcher for the AstroFlow Kivy UI.

Run this from the project root::

    py -3.10 run_app.py

It simply hands control to ``ui.main.AstroFlowApp``.
"""

from __future__ import annotations

import sys


def _runtime_guidance(missing_module: str = "") -> str:
    lines = []
    if sys.version_info >= (3, 14):
        lines.append(
            "This 'python' interpreter is Python 3.14, which is not a supported "
            "AstroFlow runtime."
        )
    if missing_module == "kivy":
        lines.append(
            "Kivy is not installed for the interpreter that launched AstroFlow."
        )
    elif missing_module:
        lines.append(
            f"The required module {missing_module!r} is not installed for the "
            "interpreter that launched AstroFlow."
        )
    lines += [
        "AstroFlow currently expects Python 3.10 or 3.11 with the project "
        "dependencies installed.",
        "Recommended on Windows:",
        "  py -3.10 -m venv .venv",
        "  .venv\\Scripts\\activate",
        "  pip install -r requirements.txt",
        "  py -3.10 run_app.py",
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        import kivy  # noqa: F401  # prove the launcher has the right runtime
        from ui.main import AstroFlowApp
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if missing in {"kivy", "swisseph"}:
            print(_runtime_guidance(missing), file=sys.stderr)
            return 1
        raise

    AstroFlowApp().run()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())