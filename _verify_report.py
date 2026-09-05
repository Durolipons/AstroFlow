"""One-off verification of the printed natal report for Iain de Somerville
(1976-06-01 17:15 local, -17.8277 +31.0534, tropical, Placidus).

Recomputes everything directly with pyswisseph (Moshier fallback -- the same
math astro.com uses) and diffs every reported value against this independent
computation. Deltas are printed in arcseconds.
"""
import swisseph as swe

LAT, LON = -17.8277, 31.0534

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
         "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGN0 = {s: 30.0 * i for i, s in enumerate(SIGNS)}


def lon(sign, d, m, s):
    return SIGN0[sign] + d + m / 60.0 + s / 3600.0


REPORT_PLANETS = {
    "Sun":       (lon("Gemini", 11, 14, 17.5), False),
    "Moon":      (lon("Cancer", 22, 43, 8.7), False),
    "Mercury":   (lon("Taurus", 24, 57, 22.5), True),
    "Venus":     (lon("Gemini", 6, 43, 55.6), False),
    "Mars":      (lon("Leo", 9, 9, 36.8), False),
    "Jupiter":   (lon("Taurus", 15, 50, 1.0), False),
    "Saturn":    (lon("Cancer", 29, 38, 9.4), False),
    "Uranus":    (lon("Scorpio", 3, 40, 38.1), True),
    "Neptune":   (lon("Sagittarius", 12, 38, 15.1), True),
    "Pluto":     (lon("Libra", 9, 0, 25.4), True),
    "Mean Node": (lon("Scorpio", 11, 11, 3.3), True),
    "True Node": (lon("Scorpio", 12, 14, 47.0), True),
}
REPORT_ANGLES = {
    "Ascendant": lon("Sagittarius", 9, 7, 39.3),
    "MC":        lon("Leo", 27, 51, 13.8),
}
REPORT_HOUSES = [
    lon("Sagittarius", 9, 7, 39.3), lon("Capricorn", 4, 54, 51.7),
    lon("Aquarius", 0, 6, 16.6),    lon("Aquarius", 27, 51, 13.8),
    lon("Aries", 0, 2, 19.5),       lon("Taurus", 5, 13, 17.8),
    lon("Gemini", 9, 7, 39.3),      lon("Cancer", 4, 54, 51.7),
    lon("Leo", 0, 6, 16.6),         lon("Leo", 27, 51, 13.8),
    lon("Libra", 0, 2, 19.5),       lon("Scorpio", 5, 13, 17.8),
]

BODIES = [
    ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY),
    ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
    ("Saturn", swe.SATURN), ("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE),
    ("Pluto", swe.PLUTO), ("Mean Node", swe.MEAN_NODE),
    ("True Node", swe.TRUE_NODE),
]


def compute(jd_ut):
    out = {}
    for name, pid in BODIES:
        res = swe.calc_ut(jd_ut, pid, swe.FLG_SPEED)
        xx = res[0]
        out[name] = (xx[0] % 360.0, xx[3] < 0)
    cusps, ascmc = swe.houses_ex(jd_ut, LAT, LON, b'P', 0)
    out["Ascendant"] = (ascmc[0] % 360.0, None)
    out["MC"] = (ascmc[1] % 360.0, None)
    out["cusps"] = [c % 360.0 for c in cusps]
    return out


def fmt(d):
    return f"{d * 3600:+10.2f}\""


def report(label, jd_ut):
    comp = compute(jd_ut)
    print(f"\n=== {label} (jd {jd_ut:.6f}) ===")
    worst = 0.0
    for name, (rlon, rrx) in REPORT_PLANETS.items():
        clon, crx = comp[name]
        d = ((clon - rlon + 180.0) % 360.0) - 180.0
        worst = max(worst, abs(d))
        flag = "" if (rrx is None or rrx == crx) else "   <-- RETRO MISMATCH"
        print(f"  {name:<10} delta {fmt(d)}{flag}")
    for name, rlon in REPORT_ANGLES.items():
        d = ((comp[name][0] - rlon + 180.0) % 360.0) - 180.0
        worst = max(worst, abs(d))
        print(f"  {name:<10} delta {fmt(d)}")
    for i, (rc, cc) in enumerate(zip(REPORT_HOUSES, comp["cusps"]), 1):
        d = ((cc - rc + 180.0) % 360.0) - 180.0
        worst = max(worst, abs(d))
        if abs(d) > 0.5 / 3600:
            print(f"  H{i:<2} delta {fmt(d)}")
    print(f"  --> worst delta over planets+angles+houses: {fmt(worst)}")
    return worst


jd_1515 = swe.julday(1976, 6, 1, 15.25)
w = report("15:15 UT  (assumes local = UTC+2 / CAT)", jd_1515)
if w > 2.0 / 3600:
    for lbl, off_h in (("16:15 UT (UTC+1)", 1.0), ("14:15 UT (UTC+3)", -1.0),
                       ("17:15 UT (no tz shift)", 2.0)):
        report(lbl, jd_1515 + off_h / 24.0)
