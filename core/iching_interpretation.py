"""I Ching divination report generation for AstroFlow.

Generates a human-readable reading from a resolved cast (see core.iching).
"""

from typing import List

from . import iching as IC

VALUE_NAMES = {6: "Six (Old Yin)", 7: "Seven (Young Yang)",
               8: "Eight (Young Yin)", 9: "Nine (Old Yang)"}
METHOD_NAMES = {"coins": "Three-Coin Toss", "yarrow": "Yarrow Stalks"}


def _hexagram_header(h) -> str:
    return (f"#{h['number']} {h['name_en']} "
            f"({h['name_pinyin']}, {h['name_cn']})")


def _section(out: List[str], title: str, body: str):
    out.append(title)
    out.append("-" * 40)
    out.append(body.strip())
    out.append("")


def iching_report(result: dict, question: str = "") -> str:
    """Generate a full I Ching reading report from a resolved cast."""
    db = IC.Database()
    out: List[str] = []

    out.append("=" * 64)
    out.append("* I CHING DIVINATION *")
    out.append("=" * 64)
    out.append(f"Question  : {question or '(no question asked)'}")
    out.append(f"Method    : {METHOD_NAMES.get(result['method'], result['method'])}")
    prim = result["primary"]
    out.append(f"Hexagram  : {_hexagram_header(prim)}")
    out.append("")

    # The cast itself
    out.append("THE CAST")
    out.append("-" * 40)
    for l in prim["lines"]:
        pos = l["position"]
        val = result["values"][pos - 1]
        mark = "  <== MOVING" if pos in result["moving"] else ""
        first = l["text"].splitlines()[0] if l["text"] else ""
        out.append(f"Line {pos}  {VALUE_NAMES[val]:<20} {first}{mark}")
    out.append("")

    # Primary hexagram
    low, up = prim["trigram_lower"], prim["trigram_upper"]
    out.append(f"TRIGRAMS  : {up['name_en']} above / {low['name_en']} below")
    out.append("")

    _section(out, "THE JUDGMENT", prim["judgment"])
    _section(out, "THE JUDGMENT COMMENTARY", prim["judgment_commentary"])
    _section(out, "THE IMAGE", prim["image"])
    _section(out, "THE IMAGE COMMENTARY", prim["image_commentary"])

    # Moving lines of the primary hexagram
    moving = result["moving"]
    if moving:
        lines_by_pos = {l["position"]: l for l in prim["lines"]}
        out.append("MOVING LINES")
        out.append("-" * 40)
        for pos in moving:
            l = lines_by_pos[pos]
            out.append(f"Line {pos} ({VALUE_NAMES[result['values'][pos - 1]]}):")
            out.append(l["text"].strip())
            out.append("")
            if l["commentary"]:
                out.append("  " + l["commentary"].replace("\n", "\n  "))
                out.append("")
        out.append("")

        # Secondary hexagram
        sec = result["secondary"]
        out.append("THE MOVING LINES TRANSFORM INTO")
        out.append("-" * 40)
        out.append(_hexagram_header(sec))
        out.append("")
        _section(out, "FUTURE JUDGMENT", sec["judgment"])
    else:
        out.append("NO MOVING LINES")
        out.append("-" * 40)
        out.append("The hexagram stands as cast; no transformation applies.")
        out.append("")

    out.append("=" * 64)
    return "\n".join(out)
