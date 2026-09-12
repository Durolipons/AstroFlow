"""Astrological constants shared across the engine.

All planet IDs are plain integers that intentionally match the Swiss
Ephemeris enum values (``swe.SUN == 0`` ... ``swe.TRUE_NODE == 11``).
Keeping this module free of the ``swisseph`` import guarantees the rest of
the engine stays importable even before the C extension loads.
"""

from typing import Dict, List, NamedTuple

# ---------------------------------------------------------------------------
# Planet identifiers (Swiss Ephemeris enum values)
# ---------------------------------------------------------------------------
SUN = 0
MOON = 1
MERCURY = 2
VENUS = 3
MARS = 4
JUPITER = 5
SATURN = 6
URANUS = 7
NEPTUNE = 8
PLUTO = 9
MEAN_NODE = 10
TRUE_NODE = 11
CHIRON = 15

PLANETS: Dict[int, str] = {
    SUN: "Sun",
    MOON: "Moon",
    MERCURY: "Mercury",
    VENUS: "Venus",
    MARS: "Mars",
    JUPITER: "Jupiter",
    SATURN: "Saturn",
    URANUS: "Uranus",
    NEPTUNE: "Neptune",
    PLUTO: "Pluto",
    MEAN_NODE: "Mean Node",
    TRUE_NODE: "True Node",
    CHIRON: "Chiron",
}

# Default selection used for natal / progressed / transit charts.
DEFAULT_PLANET_IDS: List[int] = [
    SUN, MOON, MERCURY, VENUS, MARS,
    JUPITER, SATURN, URANUS, NEPTUNE, PLUTO,
    MEAN_NODE, TRUE_NODE, CHIRON,
]

# ---------------------------------------------------------------------------
# Zodiac signs
# ---------------------------------------------------------------------------
SIGNS: List[str] = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Glyphs (Unicode) to decorate reports (fall back to SIGNS if font lacks them).
SIGNS_SYMBOLS: List[str] = [
    "\u2648", "\u2649", "\u264a", "\u264b", "\u264c", "\u264d",
    "\u264e", "\u264f", "\u2650", "\u2651", "\u2652", "\u2653",
]

# Three-letter abbreviations, handy for compact tables.
SIGNS_SHORT: List[str] = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis",
]

ELEMENTS: Dict[str, str] = {
    "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
    "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
    "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
    "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water",
}

MODALITIES: Dict[str, str] = {
    "Aries": "Cardinal", "Cancer": "Cardinal", "Libra": "Cardinal", "Capricorn": "Cardinal",
    "Taurus": "Fixed", "Leo": "Fixed", "Scorpio": "Fixed", "Aquarius": "Fixed",
    "Gemini": "Mutable", "Virgo": "Mutable", "Sagittarius": "Mutable", "Pisces": "Mutable",
}

# ---------------------------------------------------------------------------
# Detailed Elemental Analysis
# ---------------------------------------------------------------------------
ELEMENT_KEYWORDS: Dict[str, str] = {
    "Fire": "enthusiasm, courage, passion, creativity, willpower, self-expression",
    "Earth": "practicality, stability, materiality, patience, reliability, sensuality",
    "Air": "intellect, communication, social connection, abstract thought, adaptability",
    "Water": "emotion, intuition, empathy, imagination, depth, sensitivity",
}

ELEMENT_QUALITIES: Dict[str, str] = {
    "Fire": "hot and dry — energetic, spontaneous, and driven by inspiration",
    "Earth": "cold and dry — grounded, methodical, and focused on tangible results",
    "Air": "hot and moist — quick-witted, sociable, and drawn to ideas and relationships",
    "Water": "cold and moist — receptive, nurturing, and attuned to the unseen",
}

ELEMENT_STRENGTHS: Dict[str, str] = {
    "Fire": "leadership, boldness, creative vision, and the power to inspire others",
    "Earth": "endurance, craftsmanship, financial sense, and the ability to build lasting structures",
    "Air": "objectivity, articulation, intellectual curiosity, and the gift of seeing all sides",
    "Water": "emotional intelligence, healing presence, artistic sensitivity, and deep empathy",
}

ELEMENT_CHALLENGES: Dict[str, str] = {
    "Fire": "impatience, impulsiveness, burnout, and a tendency to dominate",
    "Earth": "stubbornness, materialism, resistance to change, and over-caution",
    "Air": "detachment, indecision, superficiality, and emotional distance",
    "Water": "over-sensitivity, moodiness, escapism, and difficulty setting boundaries",
}

ELEMENT_GROWTH: Dict[str, str] = {
    "Fire": "learn patience, listen before acting, and channel intensity into sustained purpose",
    "Earth": "embrace flexibility, trust the unfamiliar, and value experience over possession",
    "Air": "ground ideas in feeling, commit to depth over breadth, and honor the heart's wisdom",
    "Water": "cultivate emotional boundaries, express feelings constructively, and anchor dreams in action",
}

ELEMENT_EXPRESSION: Dict[str, Dict[str, str]] = {
    "Fire": {
        "Aries": "pioneering fire — the spark that initiates, leads, and charges ahead",
        "Leo": "radiant fire — the steady flame that creates, performs, and warms others",
        "Sagittarius": "expanding fire — the wildfire of exploration, philosophy, and adventure",
    },
    "Earth": {
        "Taurus": "fertile earth — the rich soil that builds, sustains, and enjoys the senses",
        "Virgo": "refining earth — the cultivated garden of analysis, service, and craft",
        "Capricorn": "mountainous earth — the enduring stone of ambition, structure, and mastery",
    },
    "Air": {
        "Gemini": "breezy air — the quick wind of curiosity, exchange, and mental agility",
        "Libra": "harmonious air — the balanced breeze of partnership, beauty, and fairness",
        "Aquarius": "electric air — the lightning flash of innovation, ideals, and collective vision",
    },
    "Water": {
        "Cancer": "nurturing water — the deep well of care, memory, and emotional security",
        "Scorpio": "transformative water — the underground river of power, depth, and rebirth",
        "Pisces": "boundless water — the vast ocean of compassion, dreams, and transcendence",
    },
}

# ---------------------------------------------------------------------------
# Detailed Modal Analysis
# ---------------------------------------------------------------------------
MODALITY_KEYWORDS: Dict[str, str] = {
    "Cardinal": "initiation, action, leadership, drive, ambition, enterprise",
    "Fixed": "stability, persistence, determination, focus, endurance, will",
    "Mutable": "adaptability, flexibility, transition, versatility, resourcefulness",
}

MODALITY_QUALITIES: Dict[str, str] = {
    "Cardinal": "the power to begin — projects launch, seasons turn, and new directions emerge",
    "Fixed": "the power to sustain — commitments deepen, structures hold, and purpose endures",
    "Mutable": "the power to transform — circumstances shift, skills diversify, and adaptation flows",
}

MODALITY_STRENGTHS: Dict[str, str] = {
    "Cardinal": "courage to take initiative, natural leadership, and the drive to make things happen",
    "Fixed": "loyalty, resilience, deep concentration, and the stamina to see things through",
    "Mutable": "versatility, quick learning, diplomatic skill, and the ability to go with the flow",
}

MODALITY_CHALLENGES: Dict[str, str] = {
    "Cardinal": "impatience with process, starting more than finishing, and competitive tension",
    "Fixed": "rigidity, resistance to change, holding on too long, and power struggles",
    "Mutable": "scattered energy, indecisiveness, inconsistency, and difficulty committing",
}

MODALITY_GROWTH: Dict[str, str] = {
    "Cardinal": "learn to pace yourself, honor the middle of projects, and collaborate rather than compete",
    "Fixed": "practice letting go, welcome necessary change, and share control with others",
    "Mutable": "cultivate focus, commit to a path, and trust that depth brings its own freedom",
}

MODALITY_EXPRESSION: Dict[str, Dict[str, str]] = {
    "Cardinal": {
        "Aries": "cardinal fire — the pioneer who initiates with courage and raw energy",
        "Cancer": "cardinal water — the nurturer who initiates through emotional connection and care",
        "Libra": "cardinal air — the diplomat who initiates through partnership and balanced exchange",
        "Capricorn": "cardinal earth — the builder who initiates through discipline and strategic vision",
    },
    "Fixed": {
        "Taurus": "fixed earth — the anchor who sustains through patience and sensual presence",
        "Leo": "fixed fire — the performer who sustains through creative expression and loyalty",
        "Scorpio": "fixed water — the alchemist who sustains through intensity and transformative depth",
        "Aquarius": "fixed air — the visionary who sustains through originality and unwavering ideals",
    },
    "Mutable": {
        "Gemini": "mutable air — the messenger who adapts through curiosity and mental agility",
        "Virgo": "mutable earth — the craftsman who adapts through analysis and continuous improvement",
        "Sagittarius": "mutable fire — the explorer who adapts through philosophy and boundless optimism",
        "Pisces": "mutable water — the dreamer who adapts through empathy and spiritual fluidity",
    },
}

# ---------------------------------------------------------------------------
# Element Balance Descriptions
# ---------------------------------------------------------------------------
ELEMENT_BALANCE_DESCRIPTIONS: Dict[str, str] = {
    "dominant_fire": "A strong Fire emphasis brings enthusiasm, courage, and creative drive. You are naturally inclined toward leadership and self-expression, with a warm, inspiring presence. Balance comes through cultivating patience and attending to practical details.",
    "dominant_earth": "A strong Earth emphasis brings practicality, reliability, and material skill. You are grounded and dependable, with a gift for building lasting structures. Balance comes through embracing change and honoring emotional and spiritual needs.",
    "dominant_air": "A strong Air emphasis brings intellectual curiosity, social grace, and objectivity. You are a natural communicator who sees all sides of any question. Balance comes through grounding ideas in feeling and committing to depth over breadth.",
    "dominant_water": "A strong Water emphasis brings emotional depth, intuition, and empathy. You are naturally attuned to the unseen currents of life, with a healing presence. Balance comes through cultivating boundaries and expressing feelings constructively.",
    "balanced_elements": "A balanced elemental chart suggests versatility and adaptability across all areas of life. You can draw on fire's inspiration, earth's practicality, air's clarity, and water's empathy as circumstances demand.",
    "missing_fire": "With little or no Fire emphasis, you may find it difficult to assert yourself or access spontaneous joy. Cultivating creative projects, physical play, and healthy self-confidence helps restore the spark.",
    "missing_earth": "With little or no Earth emphasis, practical matters and material security may feel challenging. Developing routines, tending the body, and building tangible skills grounds your energy.",
    "missing_air": "With little or no Air emphasis, communication and social connection may require conscious effort. Reading, writing, and engaging in thoughtful dialogue strengthens your mental agility.",
    "missing_water": "With little or no Water emphasis, accessing emotions and intuition may feel unfamiliar. Time in nature, creative expression, and empathic listening deepen your emotional intelligence.",
}

# ---------------------------------------------------------------------------
# Modality Balance Descriptions
# ---------------------------------------------------------------------------
MODALITY_BALANCE_DESCRIPTIONS: Dict[str, str] = {
    "dominant_cardinal": "A strong Cardinal emphasis makes you a natural initiator and leader. You thrive at the start of new ventures and have the courage to forge ahead. Balance comes through learning to sustain and see things through to completion.",
    "dominant_fixed": "A strong Fixed emphasis gives you remarkable staying power and determination. You are loyal, focused, and capable of deep concentration. Balance comes through cultivating flexibility and welcoming necessary change.",
    "dominant_mutable": "A strong Mutable emphasis makes you adaptable, versatile, and quick to learn. You flow easily between situations and perspectives. Balance comes through committing to a path and developing follow-through.",
    "balanced_modalities": "A balanced modal chart gives you the ability to initiate when needed, sustain through challenges, and adapt to changing circumstances — a rare and valuable combination.",
    "missing_cardinal": "With little or no Cardinal emphasis, taking initiative and asserting your leadership may feel uncomfortable. Practice starting small projects and speaking up for your vision.",
    "missing_fixed": "With little or no Fixed emphasis, staying committed and seeing things through may require conscious effort. Cultivate routines, honor your commitments, and build stamina gradually.",
    "missing_mutable": "With little or no Mutable emphasis, adapting to change and shifting perspectives may feel difficult. Practice trying new approaches, traveling, and embracing the unfamiliar.",
}
class AspectDef(NamedTuple):
    """Definition of one aspect type (name, exact angle, default orb)."""

    name: str
    angle: float      # exact angle in degrees
    orb: float        # default orb in degrees
    symbol: str       # unicode glyph / symbol
    major: bool = True


MAJOR_ASPECTS: List[AspectDef] = [
    AspectDef("Conjunction", 0.0, 8.0, "\u260c"),
    AspectDef("Opposition", 180.0, 8.0, "\u260d"),
    AspectDef("Trine", 120.0, 8.0, "\u25b3"),
    AspectDef("Square", 90.0, 8.0, "\u25a1"),
    AspectDef("Sextile", 60.0, 6.0, "\u26b9"),
]

MINOR_ASPECTS: List[AspectDef] = [
    AspectDef("Quincunx", 150.0, 2.0, "\u2a3f", major=False),
    AspectDef("Semisextile", 30.0, 2.0, "\u26ba", major=False),
    AspectDef("Semisquare", 45.0, 1.0, "\u2220", major=False),
    AspectDef("Sesquiquadrate", 135.0, 1.0, "\u2221", major=False),
]

ALL_ASPECTS: List[AspectDef] = MAJOR_ASPECTS + MINOR_ASPECTS

# ---------------------------------------------------------------------------
# House systems (single-char codes understood by Swiss Ephemeris)
# ---------------------------------------------------------------------------
HOUSE_SYSTEMS: Dict[str, str] = {
    "Placidus": "P",
    "Koch": "K",
    "Whole Sign": "W",
    "Equal (ASC)": "A",
    "Equal (MC)": "X",
    "Regiomontanus": "R",
    "Campanus": "C",
    "Porphyry": "O",
    "Alcabitus": "B",
    "Morinus": "M",
}

# Western tropical house significations used in chart reports and
# interpretation templates.
WESTERN_HOUSE_SIGNIFICATIONS: Dict[int, str] = {
    1: "self, identity and how you meet the world",
    2: "values, money, possessions and self-worth",
    3: "communication, learning, siblings and the local environment",
    4: "home, family, roots and emotional foundations",
    5: "creativity, romance, children and self-expression",
    6: "work, health, service and daily routines",
    7: "partnerships and one-to-one relationships",
    8: "transformation, intimacy and shared resources",
    9: "higher learning, long-distance travel and philosophy",
    10: "career, reputation, authority and public standing",
    11: "friendships, groups, community and aspirations",
    12: "solitude, spirituality, endings and the unconscious",
}

# ---------------------------------------------------------------------------
# Sidereal modes -> Swiss Ephemeris constant names (resolved against swisseph)
# ---------------------------------------------------------------------------
SIDEREAL_MODES: Dict[str, str] = {
    "Fagan/Bradley": "SIDM_FAGAN_BRADLEY",
    "Lahiri": "SIDM_LAHIRI",
    "Raman": "SIDM_RAMAN",
    "Krishnamurti": "SIDM_KRISHNAMURTI",
    "Surya Siddhanta": "SIDM_SURYASIDDHANTA",
    "True Citra": "SIDM_TRUE_CITRA",
    "True Mula": "SIDM_TRUE_MULA",
    "True Revati": "SIDM_TRUE_REVATI",
    "True Pushya": "SIDM_TRUE_PUSHYA",
    "J2000": "SIDM_J2000",
    "Hipparchos": "SIDM_HIPPARCHOS",
    "GalCent 0 Sag": "SIDM_GALCENT_0SAG",
    "Sunrise": "SIDM_GALCENT_RGILBRAND",
}

# ---------------------------------------------------------------------------
# Vedic Astrology Constants
# ---------------------------------------------------------------------------

# 27 Nakshatras (lunar mansions) — each spans 13°20' of the zodiac
NAKSHATRA_NAMES: List[str] = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Nakshatra rulers (Vimshottari Dasha order — 7 planets + 2 nodes)
NAKSHATRA_RULERS: List[str] = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]

# Vimshottari Dasha periods in years
VIMSHOTTARI_DASHA_YEARS: Dict[str, int] = {
    "Sun": 6,
    "Moon": 10,
    "Mars": 7,
    "Rahu": 18,
    "Jupiter": 16,
    "Saturn": 19,
    "Mercury": 17,
    "Ketu": 7,
    "Venus": 20,
}

# Total Vimshottari cycle = 120 years
VIMSHOTTARI_TOTAL_YEARS: int = 120

# Nakshatra symbols
NAKSHATRA_SYMBOLS: Dict[str, str] = {
    "Ashwini": "horse's head",
    "Bharani": "yoni",
    "Krittika": "razor or flame",
    "Rohini": "cart or chariot",
    "Mrigashira": "deer's head",
    "Ardra": "teardrop",
    "Punarvasu": "bow and quiver",
    "Pushya": "cow's udder",
    "Ashlesha": "serpent",
    "Magha": "royal throne",
    "Purva Phalguni": "hammock",
    "Uttara Phalguni": "bed",
    "Hasta": "hand",
    "Chitra": "bright jewel",
    "Swati": "young shoot",
    "Vishakha": "triumphal arch",
    "Anuradha": "lotus",
    "Jyeshtha": "circular amulet",
    "Mula": "roots tied together",
    "Purva Ashadha": "elephant tusk",
    "Uttara Ashadha": "small bed",
    "Shravana": "ear",
    "Dhanishta": "drum",
    "Shatabhisha": "empty circle",
    "Purva Bhadrapada": "sword",
    "Uttara Bhadrapada": "twins",
    "Revati": "fish",
}

# Vedic planetary relationships (natural friends/enemies)
VEDIC_PLANETARY_RELATIONSHIPS: Dict[str, Dict[str, List[str]]] = {
    "Sun": {"friends": ["Moon", "Mars", "Jupiter"], "enemies": ["Venus", "Saturn"], "neutral": ["Mercury"]},
    "Moon": {"friends": ["Sun", "Mercury"], "enemies": [], "neutral": ["Mars", "Jupiter", "Venus", "Saturn"]},
    "Mercury": {"friends": ["Sun", "Venus"], "enemies": ["Moon"], "neutral": ["Mars", "Jupiter", "Saturn"]},
    "Venus": {"friends": ["Mercury", "Saturn"], "enemies": ["Sun", "Moon"], "neutral": ["Mars", "Jupiter"]},
    "Mars": {"friends": ["Sun", "Moon", "Jupiter"], "enemies": ["Mercury"], "neutral": ["Venus", "Saturn"]},
    "Jupiter": {"friends": ["Sun", "Moon", "Mars"], "enemies": ["Mercury", "Venus"], "neutral": ["Saturn"]},
    "Saturn": {"friends": ["Mercury", "Venus"], "enemies": ["Sun", "Moon", "Mars"], "neutral": ["Jupiter"]},
}

# Vedic aspects (Graha Drishti) — planets aspect specific houses from themselves
VEDIC_ASPECT_HOUSES: Dict[str, List[int]] = {
    "Sun": [7],
    "Moon": [7],
    "Mercury": [7],
    "Venus": [7],
    "Mars": [4, 7, 8],
    "Jupiter": [5, 7, 9],
    "Saturn": [3, 7, 10],
    "Rahu": [5, 7, 9],
    "Ketu": [5, 7, 9],
}

# Vedic house significations
VEDIC_HOUSE_SIGNIFICATIONS: Dict[int, str] = {
    1: "self, body, appearance, character, longevity",
    2: "wealth, speech, family, food, face",
    3: "courage, siblings, communication, short journeys",
    4: "mother, home, emotions, vehicles, land",
    5: "children, intelligence, creativity, romance, speculation",
    6: "enemies, disease, service, debt, competition",
    7: "spouse, partnerships, business, foreign travel",
    8: "longevity, transformation, occult, inheritance",
    9: "fortune, guru, dharma, long journeys, higher learning",
    10: "career, status, authority, government, karma",
    11: "gains, income, aspirations, elder siblings",
    12: "loss, expenses, foreign lands, spirituality, liberation",
}

# ---------------------------------------------------------------------------
# Chinese Astrology Constants
# ---------------------------------------------------------------------------

# 12 Chinese Zodiac Animals
CHINESE_ZODIAC_ANIMALS: List[str] = [
    "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig",
]

# Chinese Zodiac animal characters (simplified Chinese)
CHINESE_ZODIAC_CHARACTERS: Dict[str, str] = {
    "Rat": "鼠", "Ox": "牛", "Tiger": "虎", "Rabbit": "兔",
    "Dragon": "龙", "Snake": "蛇", "Horse": "马", "Goat": "羊",
    "Monkey": "猴", "Rooster": "鸡", "Dog": "狗", "Pig": "猪",
}

# Chinese Zodiac animal traits
CHINESE_ZODIAC_TRAITS: Dict[str, str] = {
    "Rat": "quick-witted, resourceful, versatile, kind, curious",
    "Ox": "diligent, dependable, strong, determined, patient",
    "Tiger": "brave, confident, competitive, charismatic, unpredictable",
    "Rabbit": "quiet, elegant, kind, responsible, compassionate",
    "Dragon": "confident, intelligent, enthusiastic, ambitious, charismatic",
    "Snake": "enigmatic, intelligent, wise, intuitive, elegant",
    "Horse": "animated, active, energetic, independent, free-spirited",
    "Goat": "calm, gentle, sympathetic, creative, persistent",
    "Monkey": "sharp, smart, curious, clever, mischievous",
    "Rooster": "observant, hardworking, courageous, talented, confident",
    "Dog": "lovely, honest, prudent, responsible, loyal",
    "Pig": "compassionate, generous, diligent, optimistic, peaceful",
}

# Five Elements (Wu Xing)
CHINESE_ELEMENTS: List[str] = ["Wood", "Fire", "Earth", "Metal", "Water"]

# Chinese element descriptions
CHINESE_ELEMENT_DESCRIPTIONS: Dict[str, str] = {
    "Wood": "growth, creativity, flexibility, vitality, expansion — the energy of spring",
    "Fire": "passion, energy, transformation, dynamism, warmth — the energy of summer",
    "Earth": "stability, nourishment, grounding, balance, centering — the energy of transition",
    "Metal": "structure, precision, clarity, strength, refinement — the energy of autumn",
    "Water": "wisdom, intuition, flow, adaptability, depth — the energy of winter",
}

# Yin-Yang polarities
YIN_YANG: Dict[str, str] = {
    "Yang": "active, outward, masculine, bright, energetic, expansive",
    "Yin": "receptive, inward, feminine, dark, still, contractive",
}

# Heavenly Stems (10 stems — 5 elements × 2 polarities)
HEAVENLY_STEMS: List[str] = [
    "Jia", "Yi", "Bing", "Ding", "Wu",
    "Ji", "Geng", "Xin", "Ren", "Gui",
]

# Heavenly Stem elements and polarities
HEAVENLY_STEM_PROPERTIES: Dict[str, Dict[str, str]] = {
    "Jia": {"element": "Wood", "polarity": "Yang"},
    "Yi": {"element": "Wood", "polarity": "Yin"},
    "Bing": {"element": "Fire", "polarity": "Yang"},
    "Ding": {"element": "Fire", "polarity": "Yin"},
    "Wu": {"element": "Earth", "polarity": "Yang"},
    "Ji": {"element": "Earth", "polarity": "Yin"},
    "Geng": {"element": "Metal", "polarity": "Yang"},
    "Xin": {"element": "Metal", "polarity": "Yin"},
    "Ren": {"element": "Water", "polarity": "Yang"},
    "Gui": {"element": "Water", "polarity": "Yin"},
}

# Earthly Branches (12 branches — correspond to zodiac animals)
EARTHLY_BRANCHES: List[str] = [
    "Zi", "Chou", "Yin", "Mao", "Chen", "Si",
    "Wu", "Wei", "Shen", "You", "Xu", "Hai",
]

# Earthly Branch to animal mapping
EARTHLY_BRANCH_ANIMAL: Dict[str, str] = {
    "Zi": "Rat", "Chou": "Ox", "Yin": "Tiger", "Mao": "Rabbit",
    "Chen": "Dragon", "Si": "Snake", "Wu": "Horse", "Wei": "Goat",
    "Shen": "Monkey", "You": "Rooster", "Xu": "Dog", "Hai": "Pig",
}

# Earthly Branch elements
EARTHLY_BRANCH_ELEMENTS: Dict[str, str] = {
    "Zi": "Water", "Chou": "Earth", "Yin": "Wood", "Mao": "Wood",
    "Chen": "Earth", "Si": "Fire", "Wu": "Fire", "Wei": "Earth",
    "Shen": "Metal", "You": "Metal", "Xu": "Earth", "Hai": "Water",
}

# Chinese Zodiac compatibility (best matches)
CHINESE_ZODIAC_COMPATIBILITY: Dict[str, List[str]] = {
    "Rat": ["Dragon", "Monkey", "Ox"],
    "Ox": ["Rat", "Snake", "Rooster"],
    "Tiger": ["Horse", "Dog", "Pig"],
    "Rabbit": ["Goat", "Pig", "Dog"],
    "Dragon": ["Rat", "Monkey", "Rooster"],
    "Snake": ["Ox", "Rooster", "Monkey"],
    "Horse": ["Tiger", "Dog", "Goat"],
    "Goat": ["Rabbit", "Horse", "Pig"],
    "Monkey": ["Rat", "Dragon", "Snake"],
    "Rooster": ["Ox", "Dragon", "Snake"],
    "Dog": ["Tiger", "Rabbit", "Horse"],
    "Pig": ["Tiger", "Rabbit", "Goat"],
}

# Chinese Zodiac base year (1900 = Year of the Rat)
CHINESE_ZODIAC_BASE_YEAR: int = 1900