"""I Ching casting engine.

Casting methods produce six line values (bottom to top) using the traditional
values:

    6 = old yin (moving)   7 = young yang   8 = young yin   9 = old yang (moving)

Old lines "move": they flip in the secondary (future) hexagram. Randomness
comes from the OS cryptographic noise source (random.SystemRandom), i.e. the
machine's random noise generator.
"""

import json
import random
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "iching.json"

TRIGRAMS = {
    "Ch'ien": ("Heaven", "111"),
    "K'un": ("Earth", "000"),
    "Chen": ("Thunder", "100"),
    "K'an": ("Water", "010"),
    "Ken": ("Mountain", "001"),
    "Sun": ("Wind", "011"),
    "Li": ("Fire", "101"),
    "Tui": ("Lake", "110"),
}

_method_registry = {}


def _method(name):
    def deco(fn):
        _method_registry[name] = fn
        return fn
    return deco


@_method("coins")
def cast_coins(rng):
    """Three-coin toss: heads = 3, tails = 2; the sum gives the line value.

    Probabilities: old yang 1/8, young yang 3/8, young yin 3/8, old yin 1/8.
    """
    total = sum(3 if rng.random() < 0.5 else 2 for _ in range(3))
    return {6: 6, 7: 7, 8: 8, 9: 9}[total]


@_method("yarrow")
def cast_yarrow(rng):
    """Yarrow-stalk casting (simulated; true method probabilities).

    Faithful probabilities of the 50-stalk she method:
    old yang 3/16, young yang 5/16, young yin 7/16, old yin 1/16.
    """
    r = rng.random() * 16
    if r < 3:
        return 9
    if r < 8:
        return 7
    if r < 15:
        return 8
    return 6


def cast(method="coins", rng=None):
    """Cast a full hexagram. Returns a cast dict with line values bottom->top."""
    rng = rng or random.SystemRandom()
    fn = _method_registry.get(method)
    if fn is None:
        raise ValueError(f"unknown casting method: {method!r} "
                         f"(available: {', '.join(sorted(_method_registry))})")
    return {"method": method, "values": [fn(rng) for _ in range(6)]}


def values_to_binary(values):
    """Line values -> 6-bit binary string, bottom line first (1 = yang)."""
    return "".join("1" if v in (7, 9) else "0" for v in values)


def moving_positions(values):
    return [i + 1 for i, v in enumerate(values) if v in (6, 9)]


def transform(binary, positions):
    """Flip the moving lines to get the secondary hexagram's binary."""
    bits = list(binary)
    for pos in positions:
        bits[pos - 1] = "1" if bits[pos - 1] == "0" else "0"
    return "".join(bits)


class Database:
    def __init__(self, path=DATA_PATH):
        self.path = Path(path)
        self.document = json.loads(self.path.read_text(encoding="utf-8"))
        self.hexagrams = {h["number"]: h for h in self.document["hexagrams"]}
        self._by_binary = {h["binary"]: h for h in self.document["hexagrams"]}

    def by_binary(self, binary):
        return self._by_binary[binary]

    def by_number(self, number):
        return self.hexagrams[number]

    def lines_of(self, number):
        return {l["position"]: l for l in self.by_number(number)["lines"]}

    def trigram_pair(self, hexagram):
        low, up = hexagram["trigram_lower"], hexagram["trigram_upper"]
        return low, up


def reading(cast_result, db=None):
    """Resolve a cast into primary/secondary hexagram records + moving lines."""
    db = db or Database()
    primary_binary = values_to_binary(cast_result["values"])
    positions = moving_positions(cast_result["values"])
    secondary_binary = transform(primary_binary, positions)
    return {
        "method": cast_result["method"],
        "values": list(cast_result["values"]),
        "moving": positions,
        "primary": db.by_binary(primary_binary),
        "secondary": db.by_binary(secondary_binary) if positions else None,
    }
