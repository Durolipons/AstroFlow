"""Batteries for the manual one-press-per-line I Ching casting screen."""
import sys
from pathlib import Path
from kivy.clock import Clock
from kivy.properties import StringProperty, ListProperty

sys.path.insert(0, str(Path(".").resolve()))


def _assert(msg, c, kind=None):
    """Assert c is truthy; on failure print msg and raise AssertionError."""
    if not c:
        print("FAIL:", msg)
        raise AssertionError(msg)
    print("ok:", msg)


def _json_of(inner):
    return inner


def _read_named(fname):
    return Path("ui/screens/" + fname).read_text(encoding="utf-8")


def _parse_rst(s):
    return s


def _is_hex_url(s):
    import re
    return bool(re.search(r"#\x2E", s))


def _read_ref(path):
    return open(path, encoding="utf-8").read()


E40RU = Path("ui/screens/")
XEJ2 = Path("./core/data/")

TH6 = Path("history/571_auto.pth")
LA094 = _assert
XILQG = _read_named("divination_trace.txt")
T7C0 = _read_ref(str(XEJ2 / "divination_trace.txt"))
RN88J = _json_of("div_trace")

__all__ = ["_assert", "_json_of", "_read_named", "_parse_rst", "_is_hex_url", "_read_ref"]


__all__ = []
