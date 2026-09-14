"""Extract the 64 hexagram texts of the Wilhelm/Baynes I Ching into JSON.

Source: the machine-readable site-rip of the 1950 Richard Wilhelm / Cary F
Baynes translation kept in Reference/. The file is plain text wrapped in
<PRE>, so this script only needs light regex parsing.

The extractor is authoritative for the *order* (King Wen sequence as
numbered in the Wilhelm edition), the English titles, the trigram pairs, and
the Judgment / Image / line texts. The Chinese characters and Hanyu pinyin
are supplied from a small curated table (verified against the canonical
trigram grid, because the site rip keeps no CJK glyphs).

Usage::

    python scripts/extract_iching.py      # writes core/data/iching.json

Idempotent: re-generates the JSON from scratch on every run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "Reference" / "Divination" / "I Ching" / (
    "Richard Wilhelm - Cary F Baynes"
) / "I Ching - Richard Wilhelm.htm"
OUT = ROOT / "core" / "data" / "iching.json"

# --- Canonical metadata: Chinese characters + Hanyu pinyin per King Wen
# number, verified against the standard upper/lower trigram grid.
CN_TABLE = {
    1: ("乾", "qian"), 2: ("坤", "kun"), 3: ("屯", "zhun"), 4: ("蒙", "meng"),
    5: ("需", "xu"), 6: ("訟", "song"), 7: ("師", "shi"), 8: ("比", "bi"),
    9: ("小畜", "xiaoxu"), 10: ("履", "lu"), 11: ("泰", "tai"),
    12: ("否", "pi"), 13: ("同人", "tongren"), 14: ("大有", "dayou"),
    15: ("謙", "qian"), 16: ("豫", "yu"), 17: ("隨", "sui"), 18: ("蠱", "gu"),
    19: ("臨", "lin"), 20: ("觀", "guan"), 21: ("噬嗑", "shihe"),
    22: ("賁", "bi"), 23: ("剝", "bo"), 24: ("復", "fu"),
    25: ("无妄", "wuwang"), 26: ("大畜", "dachu"), 27: ("頤", "yi"),
    28: ("大過", "daguo"), 29: ("坎", "kan"), 30: ("離", "li"),
    31: ("咸", "xian"), 32: ("恒", "heng"), 33: ("遯", "dun"),
    34: ("大壯", "dazhuang"), 35: ("晉", "jin"), 36: ("明夷", "mingyi"),
    37: ("家人", "jiaren"), 38: ("睽", "kui"), 39: ("蹇", "jian"),
    40: ("解", "jie"), 41: ("損", "sun"), 42: ("益", "yi"),
    43: ("夬", "guai"), 44: ("姤", "gou"), 45: ("萃", "cui"),
    46: ("升", "sheng"), 47: ("困", "kun"), 48: ("井", "jing"),
    49: ("革", "ge"), 50: ("鼎", "ding"), 51: ("震", "zhen"),
    52: ("艮", "gen"), 53: ("漸", "jian"), 54: ("歸妹", "guimei"),
    55: ("豐", "feng"), 56: ("旅", "lu"), 57: ("巽", "xun"),
    58: ("兌", "dui"), 59: ("渙", "huan"), 60: ("節", "jie"),
    61: ("中孚", "zhongfu"), 62: ("小過", "xiaoguo"),
    63: ("既濟", "jiji"), 64: ("未濟", "weiji"),
}

# Trigram canonical data: keyed by canonical Wilhelm pinyin (title case).
TRIGRAMS = {
    "Ch'ien": {"key": "Ch'ien", "name_cn": "乾", "name_en": "The Creative, Heaven"},
    "Tui":    {"key": "Tui",    "name_cn": "兌", "name_en": "The Joyous, Lake"},
    "Li":     {"key": "Li",     "name_cn": "離", "name_en": "The Clinging, Fire"},
    "Chen":   {"key": "Chen",   "name_cn": "震", "name_en": "The Arousing, Thunder"},
    "Sun":    {"key": "Sun",    "name_cn": "巽", "name_en": "The Gentle, Wind"},
    "K'an":   {"key": "K'an",   "name_cn": "坎", "name_en": "The Abysmal, Water"},
    "Ken":    {"key": "Ken",    "name_cn": "艮", "name_en": "Keeping Still, Mountain"},
    "K'un":   {"key": "K'un",   "name_cn": "坤", "name_en": "The Receptive, Earth"},
}

# Trigram -> 3 bits, bottom line first (the conventional reading order).
TRIGRAM_BITS = {
    "Ch'ien": "111", "Tui": "110", "Li": "101", "Chen": "100",
    "Sun": "011", "K'an": "010", "Ken": "001", "K'un": "000",
}

# Canonical King Wen arrangement: hexagram number -> (upper, lower) trigram.
# Verified against the standard upper/lower lookup grid. The site-rip's own
# "above/below" lines are corrupt in a few blocks (e.g. #20, #23), so this
# curated grid is the authoritative source; the rip is only used as a
# cross-check during extraction.
CURATED_GRID = {
    1: ("Ch'ien", "Ch'ien"), 2: ("K'un", "K'un"),
    3: ("K'an", "Chen"), 4: ("Ken", "K'an"),
    5: ("K'an", "Ch'ien"), 6: ("Ch'ien", "K'an"),
    7: ("K'un", "K'an"), 8: ("K'an", "K'un"),
    9: ("Sun", "Ch'ien"), 10: ("Ch'ien", "Tui"),
    11: ("K'un", "Ch'ien"), 12: ("Ch'ien", "K'un"),
    13: ("Ch'ien", "Li"), 14: ("Li", "Ch'ien"),
    15: ("K'un", "Ken"), 16: ("Chen", "K'un"),
    17: ("Tui", "Chen"), 18: ("Ken", "Sun"),
    19: ("K'un", "Tui"), 20: ("Sun", "K'un"),
    21: ("Li", "Chen"), 22: ("Ken", "Li"),
    23: ("Ken", "K'un"), 24: ("K'un", "Chen"),
    25: ("Ch'ien", "Chen"), 26: ("Ken", "Ch'ien"),
    27: ("Ken", "Chen"), 28: ("Tui", "Sun"),
    29: ("K'an", "K'an"), 30: ("Li", "Li"),
    31: ("Tui", "Ken"), 32: ("Chen", "Sun"),
    33: ("Ch'ien", "Ken"), 34: ("Chen", "Ch'ien"),
    35: ("Li", "K'un"), 36: ("K'un", "Li"),
    37: ("Sun", "Li"), 38: ("Li", "Tui"),
    39: ("K'an", "Ken"), 40: ("Chen", "K'an"),
    41: ("Ken", "Tui"), 42: ("Sun", "Chen"),
    43: ("Tui", "Ch'ien"), 44: ("Ch'ien", "Sun"),
    45: ("Tui", "K'un"), 46: ("K'un", "Sun"),
    47: ("Tui", "K'an"), 48: ("K'an", "Sun"),
    49: ("Tui", "Li"), 50: ("Li", "Sun"),
    51: ("Chen", "Chen"), 52: ("Ken", "Ken"),
    53: ("Sun", "Ken"), 54: ("Chen", "Tui"),
    55: ("Chen", "Li"), 56: ("Li", "Ken"),
    57: ("Sun", "Sun"), 58: ("Tui", "Tui"),
    59: ("Sun", "K'an"), 60: ("K'an", "Tui"),
    61: ("Sun", "Tui"), 62: ("Chen", "Ken"),
    63: ("K'an", "Li"), 64: ("Li", "K'an"),
}

# Canonical King Wen sequence as 6-bit strings, bottom line first. Independent
# hard guard: the derived binary from CURATED_GRID must match this exactly for
# every hexagram, so any grid typo fails validation loudly.
CANONICAL_BINARY = {
    1: "111111", 2: "000000", 3: "100010", 4: "010001",
    5: "111010", 6: "010111", 7: "010000", 8: "000010",
    9: "111011", 10: "110111", 11: "111000", 12: "000111",
    13: "101111", 14: "111101", 15: "001000", 16: "000100",
    17: "100110", 18: "011001", 19: "110000", 20: "000011",
    21: "100101", 22: "101001", 23: "000001", 24: "100000",
    25: "100111", 26: "111001", 27: "100001", 28: "011110",
    29: "010010", 30: "101101", 31: "001110", 32: "011100",
    33: "001111", 34: "111100", 35: "000101", 36: "101000",
    37: "101011", 38: "110101", 39: "001010", 40: "010100",
    41: "110001", 42: "100011", 43: "111110", 44: "011111",
    45: "000110", 46: "011000", 47: "010110", 48: "011010",
    49: "101110", 50: "011101", 51: "100100", 52: "001001",
    53: "001011", 54: "110100", 55: "101100", 56: "001101",
    57: "011011", 58: "110110", 59: "010011", 60: "110010",
    61: "110011", 62: "001100", 63: "101010", 64: "010101",
}


# ---------------------------------------------------------------------------
# Gap fills for passages the site rip lost or corrupted.
#
# Text taken from the Bollingen edition extract (the same Wilhelm/Baynes 1950
# translation) kept in Reference/Astrology/_extracted. Verified against the
# derived yin/yang values of the curated trigram grid (20/5 Nine, 21/2 Six,
# 21/3 Six, 26/3 Nine, 32/6 Six). #21 line 2 is a *replacement*: the rip
# carries line 3's verse under the second-place header.
# ---------------------------------------------------------------------------
PATCHES = {
    20: {
        "lines": {
            5: (
                "Contemplation of my life.\n"
                "The superior man is without blame.",
                "A man in an authoritative position to whom others look up must "
                "always be ready for self-examination. The right sort of "
                "self-examination, however, consists not in idle brooding over "
                "oneself but in examining the effects one produces. Only when "
                "these effects are good, and when one's influence on others is "
                "good, will the contemplation of one's own life bring the "
                "satisfaction of knowing oneself to be free of mistakes.",
            ),
        },
    },
    21: {
        "image": (
            "Thunder and lightning:\n"
            "The image of BITING THROUGH.\n"
            "Thus the kings of former times\n"
            "Made firm the laws\n"
            "Through clearly defined penalties.",
            "Penalties are the individual applications of the law. The laws "
            "specify the penalties. Clarity prevails when mild and severe "
            "penalties are clearly differentiated, according to the nature of "
            "the crimes. This is symbolized by the clarity of lightning. The "
            "law is strengthened by a just application of penalties. This is "
            "symbolized by the terror of thunder. This clarity and severity "
            "have the effect of instilling respect; it is not that the "
            "penalties are ends in themselves. The obstructions in the social "
            "life of man increase when there is lack of clarity in the penal "
            "codes and slackness in executing them. The only way to strengthen "
            "the law is to make it clear and to make penalties certain and "
            "swift.",
        ),
        "lines": {
            2: (
                "Bites through tender meat,\n"
                "So that his nose disappears.\n"
                "No blame.",
                "It is easy to discriminate between right and wrong in this "
                "case; it is like biting through tender meat. But one "
                "encounters a hardened sinner, and, aroused by anger, one goes "
                "a little too far. The disappearance of the nose in the course "
                "of the bite signifies that indignation blots out finer "
                "sensibility. However, there is no great harm in this, because "
                "the penalty as such is just.",
            ),
            3: (
                "Bites on old dried meat\n"
                "And strikes on something poisonous.\n"
                "Slight humiliation.  No blame.",
                "Punishment is to be carried out by someone who lacks the power "
                "and authority to do so. Therefore the culprits do not submit. "
                "The matter at issue is an old one-as symbolized by salted "
                "game-and in dealing with it difficulties arise. This old meat "
                "is spoiled: by taking up the problem the punisher arouses "
                "poisonous hatred against himself, and in this way is put in a "
                "somewhat humiliating position. But since punishment was "
                "required by the time, he remains free of blame.",
            ),
        },
    },
    26: {
        "lines": {
            3: (
                "A good horse that follows others.\n"
                "Awareness of danger,\n"
                "With perseverance, furthers.\n"
                "Practice chariot driving and armed defense daily.\n"
                "It furthers one to have somewhere to go.",
                "The way opens; the hindrance has been cleared away. A man is "
                "in contact with a strong will acting in the same direction as "
                "his own, and goes forward like one good horse following "
                "another. But danger still threatens, and he must remain aware "
                "of it, or he will be robbed of his firmness. Thus he must "
                "acquire skill on the one hand in what will take him forward, "
                "and on the other in what will protect him against unforeseen "
                "attacks. It is good in such a pass to have a goal toward which "
                "to strive.",
            ),
        },
    },
    32: {
        "lines": {
            6: (
                "Restlessness as an enduring condition\n"
                "brings misfortune.",
                "There are people who live in a state of perpetual hurry "
                "without ever attaining inner composure. Restlessness not only "
                "prevents all thoroughness but actually becomes a danger if it "
                "is dominant in places of authority.",
            ),
        },
    },
    56: {
        "judgment": (
            "THE WANDERER.\n"
            "Success through smallness.\n"
            "Perseverance brings good fortune\n"
            "To the wanderer.",
            "When a man is a wanderer and stranger, he should not be gruff nor "
            "overbearing. He has no large circle of acquaintances, therefore "
            "he should not give himself airs. He must be cautious and "
            "reserved; in this way he protects himself from evil. If he is "
            "obliging toward others, he wins success.\n\n"
            "A wanderer has no fixed abode; his home is the road. Therefore he "
            "must take care to remain upright and steadfast, so that he "
            "sojourns only in the proper places, associating only with good "
            "people. Then he has good fortune and can go his way unmolested.",
        ),
    },
}
HEADER_RE = re.compile(r"^\s+(\d+)\.\s+(.+?)\s*/\s*(.+?)\s*$")
# Some blocks use the British spelling "JUDGEMENT" (e.g. #56).
SECTION_RE = re.compile(r"^\s*[^\w]*THE\s+(JUDGE?MENT|IMAGE|LINES)\.?\s*$")
MEANS_RE = re.compile(
    r"(Nine|Six) "
    r"(at the beginning|in the second place|in the third place|"
    r"in the fourth place|in the fifth place|at the top) means:\s*$",
    re.IGNORECASE,
)


def means_slot(line):
    """Return the line-slot label for a 'means:' header line, or None.

    The rip mangles headers with stray prefixes ('¡', 'O '), doubled spaces
    and the occasional lost 'th' ('in e second place'), so the line is
    normalised before the canonical pattern is applied.
    """
    norm = re.sub(r"[ \t]+", " ", line).strip()
    norm = norm.replace("in e second", "in the second")
    norm = norm.replace("in the beginning", "at the beginning")
    m = MEANS_RE.search(norm)
    return m.group(2) if m else None
ALL_MOVING_RE = re.compile(
    r"[^\w]*When all the lines\s+are (nines|sixes),? it means:\s*$",
    re.IGNORECASE,
)
TRIGRAM_RE = re.compile(r"^\s*(above|below)\s+([A-Z'][A-Z' ]*?)\s{2,}")

# Map the rip's all-caps trigram tokens onto the canonical title-case keys.
_UPPER_ALIAS = {
    "CH'IEN": "Ch'ien", "TUI": "Tui", "LI": "Li", "CHEN": "Chen",
    "SUN": "Sun", "K'AN": "K'an", "KEN": "Ken", "K'UN": "K'un",
}


# The site rip was saved as a mangled single-byte charset, so the doubled
# trigram tones â / ü come through as raw bytes. Map them back and reduce
# every token to plain ASCII so it can be matched against TRIGRAMS.
_MOJIBYTE_MAP = {"\x90": "E", "\x9f": "U"}


def norm_token(text):
    """Normalise a source token: fix mangled accents, keep ASCII letters/'."""
    text = "".join(_MOJIBYTE_MAP.get(ch, ch) for ch in text)
    return re.sub(r"[^A-Za-z' ]+", "", text).strip()


def clean(text):
    """Normalise a raw source paragraph: collapse spaces, strip edges."""
    return re.sub(r"[ \t]+", " ", text).strip()


def split_verse_commentary(lines):
    """Split a section body into (oracle, commentary).

    Wilhelm layout: the oracular verse occupies the indented lines after the
    header (one or more blank lines may precede the verse); a blank line
    separates verse from the explanatory prose. Returns
    ``(oracle_text, commentary_text)``; either may be empty.
    """
    body = [ln.strip() for ln in lines]
    start = 0
    while start < len(body) and not body[start]:
        start += 1
    idx = start
    while idx < len(body) and body[idx]:
        idx += 1
    oracle = body[start:idx]
    rest = body[idx:]
    paragraphs = []
    cur = []
    for ln in rest:
        if ln:
            cur.append(ln)
        elif cur:
            paragraphs.append(" ".join(cur))
            cur = []
    if cur:
        paragraphs.append(" ".join(cur))
    return "\n".join(oracle), "\n\n".join(paragraphs)


def parse():
    """Parse the source HTML into a list of raw hexagram blocks."""
    raw = SOURCE.read_bytes().decode("latin-1")
    lines = raw.split("\n")

    # Locate the 64 body headings ("         1.  Ch'ien  / The Creative").
    # The TOC entry above it uses a single space after the number; body
    # headings use two+, which lets us skip the one-per-line TOC.
    headers = []
    for i, ln in enumerate(lines):
        # Skip the two-per-line table of contents ("... | ...").
        if "|" in ln:
            continue
        m = HEADER_RE.match(ln)
        if m:
            headers.append((i, int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
    if len(headers) != 64:
        raise SystemExit(f"expected 64 hexagram headings, found {len(headers)}")

    blocks = []
    for k, (i, num, name, en) in enumerate(headers):
        end = headers[k + 1][0] if k + 1 < len(headers) else len(lines)
        if num == 64:
            # hexagram 64 is the last block: stop at the trailing "index" junk.
            stop = next(
                (j for j in range(i, end) if lines[j].strip().lower().startswith("index")),
                end,
            )
            end = stop
        blocks.append({
            "start": i, "end": end, "num": num, "name": name, "en": en,
        })

    hexagrams = []
    for b in blocks:
        text = lines[b["start"] + 1:b["end"]]

        upper = lower = None
        for ln in text:
            m = TRIGRAM_RE.match(ln)
            if m:
                key = _UPPER_ALIAS.get(norm_token(m.group(2)).upper())
                if key is None:
                    continue
                if m.group(1) == "above":
                    upper = key
                else:
                    lower = key

        # Split the block into sections by header line.
        sections = {}
        cur = None
        for ln in text:
            if ln.strip().lower() == "index":
                continue  # page-footer junk of the site rip
            m = SECTION_RE.match(ln)
            if m:
                cur = "THE JUDGMENT" if m.group(1).startswith("JUDG") else (
                    "THE " + m.group(1))
                sections.setdefault(cur, [])
            elif cur is not None:
                sections[cur].append(ln)

        def sect(name):
            return split_verse_commentary(sections.get(name, []))

        judgment, judgment_c = sect("THE JUDGMENT")
        image, image_c = sect("THE IMAGE")

        # Parse the six line texts out of THE LINES section.
        line_order = [
            ("at the beginning", 1), ("in the second place", 2),
            ("in the third place", 3), ("in the fourth place", 4),
            ("in the fifth place", 5), ("at the top", 6),
        ]

        def collect_slots(body):
            slots = {label: [] for label, _ in line_order}
            moving = None
            cur_slot = None
            for ln in body:
                if ln.strip().lower() == "index":
                    continue  # page-footer junk of the site rip
                ma = ALL_MOVING_RE.search(ln)
                if ma:
                    cur_slot = None
                    moving = ma.group(1)
                    continue
                slot = means_slot(ln)
                if slot is not None:
                    cur_slot = slot
                    continue
                if cur_slot is not None:
                    slots[cur_slot].append(ln)
            return slots, moving

        slots, all_moving = collect_slots(sections.get("THE LINES", []))
        if not any(slots.values()):
            # The rip sometimes loses the THE LINES header entirely (e.g. #21,
            # where the line texts follow straight on from THE IMAGE): rescan
            # the whole block for the "means:" headers.
            slots, all_moving = collect_slots(text)

        line_records = []
        for label, pos in line_order:
            oracle, comm = split_verse_commentary(slots[label])
            line_records.append({"position": pos, "text": oracle, "commentary": comm})

        record = {
            "number": b["num"],
            "name": norm_token(b["name"]),
            "name_en": b["en"],
            "judgment": judgment,
            "judgment_commentary": judgment_c,
            "image": image,
            "image_commentary": image_c,
            "lines": line_records,
            "all_moving": all_moving,
        }
        # Keep the rip's own pairing for a cross-check against the curated grid.
        if upper and lower:
            record["parsed_trigrams"] = (upper, lower)
        hexagrams.append(record)

    return hexagrams


def apply_patches(hexagrams):
    """Replace rip-lost/corrupted passages with the curated Bollingen texts."""
    for h in hexagrams:
        patch = PATCHES.get(h["number"])
        if not patch:
            continue
        fills = h.setdefault("gap_fill", [])
        if "judgment" in patch:
            h["judgment"], h["judgment_commentary"] = patch["judgment"]
            fills.append("judgment")
        if "image" in patch:
            h["image"], h["image_commentary"] = patch["image"]
            fills.append("image")
        for pos, (verse, comm) in patch.get("lines", {}).items():
            rec = next(l for l in h["lines"] if l["position"] == pos)
            rec["text"], rec["commentary"] = verse, comm
            fills.append(f"line {pos}")
    return hexagrams


def build_record(h):
    """Add curated CJK names + derived line values to one hexagram block."""
    n = h["number"]
    cn, py = CN_TABLE[n]
    upper_key, lower_key = CURATED_GRID[n]
    upper = TRIGRAMS[upper_key]
    lower = TRIGRAMS[lower_key]
    rec = {
        "number": n,
        "name": h["name"],
        "name_cn": cn,
        "name_pinyin": py,
        "name_en": h["name_en"],
        "binary": TRIGRAM_BITS[lower_key] + TRIGRAM_BITS[upper_key],
        "trigram_upper": dict(upper),
        "trigram_lower": dict(lower),
        "judgment": h["judgment"],
        "judgment_commentary": h["judgment_commentary"],
        "image": h["image"],
        "image_commentary": h["image_commentary"],
        "lines": [],
        "all_moving": h["all_moving"],
        "gap_fill": h.get("gap_fill", []),
        "parsed_trigrams": h.get("parsed_trigrams"),
    }
    for line in sorted(h["lines"], key=lambda d: d["position"]):
        bit = rec["binary"][line["position"] - 1]
        rec["lines"].append({
            "position": line["position"],
            "value": 7 if bit == "1" else 8,
            "text": line["text"],
            "commentary": line["commentary"],
        })
    return rec


def validate(records):
    errors = []
    warnings = []
    if len(records) != 64:
        errors.append(f"expected 64 hexagrams, got {len(records)}")
    bin_set = set()
    for rec in records:
        n = rec["number"]
        if rec["number"] != n:
            errors.append(f"ordering broken at index {n}: #{rec['number']}")
        if len(rec["binary"]) != 6 or not set(rec["binary"]) <= {"0", "1"}:
            errors.append(f"#{n} bad binary {rec['binary']!r}")
        if rec["binary"] != CANONICAL_BINARY[n]:
            errors.append(
                f"#{n} binary {rec['binary']} != canonical {CANONICAL_BINARY[n]}"
            )
        bin_set.add(rec["binary"])
        if not rec["judgment"]:
            errors.append(f"#{n} missing judgment")
        if not rec["image"]:
            errors.append(f"#{n} missing image")
        for ln in rec["lines"]:
            if not ln["text"]:
                errors.append(f"#{n} line {ln['position']} has no text")
            if ln["value"] not in (7, 8):
                errors.append(f"#{n} line {ln['position']} bad value {ln['value']}")
        if not rec["name_cn"] or not rec["name_pinyin"]:
            errors.append(f"#{n} missing curated CJK name")
        if not rec["trigram_upper"] or not rec["trigram_lower"]:
            errors.append(f"#{n} missing trigram pair")
        parsed = rec.get("parsed_trigrams")
        if parsed and tuple(parsed) != CURATED_GRID[n]:
            warnings.append(
                f"#{n} {rec['name']}: rip pairing {parsed} != curated {CURATED_GRID[n]}"
            )
    if len(bin_set) != 64:
        errors.append(f"binary codes not distinct ({len(bin_set)}/64)")
    return errors, warnings


def main():
    records = [build_record(h) for h in apply_patches(parse())]
    errors, warnings = validate(records)
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        raise SystemExit(1)
    if warnings:
        print("CROSS-CHECK WARNINGS (rip pairing disagrees with curated grid):")
        for w in warnings:
            print(" -", w)

    document = {
        "source": (
            "Richard Wilhelm / Cary F. Baynes, THE I CHING OR BOOK OF CHANGES, "
            "1950. Extracted from the site-rip HTML kept in "
            "Reference/Divination/I Ching. Chinese names and pinyin curated per "
            "the canonical King Wen trigram grid."
        ),
        "hexagrams": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    n_lines = sum(len(r["lines"]) for r in records)
    patched = [r for r in records if r["gap_fill"]]
    if patched:
        print("Gap fills applied (source: Bollingen extract):")
        for r in patched:
            print(f" - #{r['number']} {r['name']}: {', '.join(r['gap_fill'])}")
    print(f"OK: wrote {OUT} ({len(records)} hexagrams, {n_lines} line texts)")


if __name__ == "__main__":
    main()