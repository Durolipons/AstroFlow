"""Editable interpretation library for AstroFlow.

The engine keeps its interpretation text in a small JSON-backed library so
professional astrologers can rewrite the wording in the UI without touching the
calculation code. The module is UI-agnostic: callers choose the storage path
and can use the same library from Kivy, CLI, or tests.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from . import constants as C


def _default_sign_text() -> Dict[str, str]:
    """Sign character texts grounded in Arroyo's element keywords,
    Forrest's archetypes and Tierney's sign deep-dives."""
    return {
        "Aries": "initiative, courage, directness; the pioneer who acts first and fears nothing - cardinal-fire Aries energy: spring, spark and first-move courage",
        "Taurus": "steadiness, sensuality, patience; the builder who trusts the body and the seasons - fixed earth Taurus energy: steady, sensual and unshakeable",
        "Gemini": "curiosity, adaptability, communication; the messenger who lives through questions and connections - mutable air Gemini energy: quick, curious and ever-adaptable",
        "Cancer": "nurturance, memory, emotional depth; the protector who feels first and shelters fiercely - cardinal water Cancer energy: protective, feeling and home-centred",
        "Leo": "creativity, warmth, self-expression; the performer who shines to give warmth and generous applause - fixed fire Leo energy: radiant, loyal and creatively bold",
        "Virgo": "precision, service, analysis; the refiner who improves everything through useful, careful work - mutable earth Virgo energy: refined, useful and self-improving",
        "Libra": "harmony, fairness, relationship; the diplomat who finds identity through partnership and beauty - cardinal air Libra energy: fair, relational and harmonising",
        "Scorpio": "intensity, transformation, insight; the alchemist who deepens through trust, honesty and rebirth - fixed water Scorpio energy: deep, intense and regenerative",
        "Sagittarius": "philosophy, optimism, exploration; the seeker who expands through travel, learning and contagious faith - mutable fire Sagittarius energy: expansive, hopeful and far-sighted",
        "Capricorn": "ambition, discipline, endurance; the matriarch who climbs patiently through earned authority - cardinal earth Capricorn energy: disciplined, ambitious and enduring",
        "Aquarius": "innovation, independence, ideals; the visionary who breaks the mould for the collective good - fixed air Aquarius energy: original, independent and humanitarian",
        "Pisces": "empathy, imagination, intuition; the mystic who flows between worlds, softens and dissolves - mutable water Pisces energy: empathic, imaginative and boundary-less",
    }


def _default_aspect_text() -> Dict[str, str]:
    return {
        "Conjunction": "intensifies and fuses the two energies",
        "Opposition": "sets up a dynamic tension that needs balancing",
        "Trine": "flows easily and supports smooth expression",
        "Square": "creates friction that pushes for constructive action",
        "Sextile": "offers a helpful opportunity that needs a nudge",
        "Quincunx": "asks for subtle adjustment and re-orientation",
        "Semisextile": "gradually awakens a minor but useful awareness",
        "Semisquare": "produces mild irritation that signals fine-tuning",
        "Sesquiquadrate": "accumulates small frictions that demand review",
    }


def _default_planet_role() -> Dict[str, str]:
    """Planet function descriptions grounded in Forrest's Inner Sky."""
    return {
        "Sun": "core identity & vitality; the conscious self that shines and directs",
        "Moon": "emotional needs & instincts; the felt self that nurtures and remembers",
        "Mercury": "thinking, learning & communication; the mind that connects and trades",
        "Venus": "values, attraction & relating; the heart that loves, beautifies and bonds",
        "Mars": "drive, action & assertion; the will that fights, desires and initiates",
        "Jupiter": "growth, optimism & opportunity; the faith that expands and blesses",
        "Saturn": "structure, responsibility & limits; the discipline that builds and matures",
        "Uranus": "change, freedom & originality; the spark that awakens and liberates",
        "Neptune": "dreams, imagination & transcendence; the vision that dissolves and inspires",
        "Pluto": "power, transformation & regeneration; the depth that destroys and renews",
        "Chiron": "the wounded healer & bridge between personal and collective; the guide who turns pain into wisdom",
    }


def _default_sky_aspect_text() -> Dict[str, str]:
    """Current-sky (general) phrasing for aspects between moving planets."""
    return {
        "Conjunction": "fuses the two energies while they travel together",
        "Opposition": "pulls between two poles that both want airtime today",
        "Trine": "flows easily and keeps the day moving smoothly",
        "Square": "adds productive friction that asks for action",
        "Sextile": "opens a small window of opportunity - take the nudge",
        "Quincunx": "asks for a small adjustment between unlike needs",
        "Semisextile": "quietly shifts the mood a half-step",
        "Semisquare": "sprinkles mild irritation that highlights fine-tuning",
        "Sesquiquadrate": "builds a low hum of tension worth reviewing",
    }


def _default_planet_sky_note() -> Dict[str, str]:
    """Per-planet note about what it rules in the general sky at the moment."""
    return {
        "Sun": "sets the day's vitality and focus",
        "Moon": "the fastest mover - its sign colours the mood of the hours",
        "Mercury": "shapes conversations, plans and errands",
        "Venus": "colours tastes, money and how people get along",
        "Mars": "fuels energy, drive and reactions",
        "Jupiter": "widens opportunities over weeks and months",
        "Saturn": "sets the slower structure and duties of the season",
        "Uranus": "stirs sudden change in the background",
        "Neptune": "dissolves boundaries in dreams and moods",
        "Pluto": "works beneath the surface across years",
        "Chiron": "highlights the healing wound - where it sits matters most",
    }


def _default_sign_sky_note() -> Dict[str, str]:
    return {
        "Aries": "the sky pushes for bold starts and quick decisions",
        "Taurus": "the sky favours steadiness, comfort and tangible results",
        "Gemini": "the sky is curious, chatty and easily distracted",
        "Cancer": "feelings run close to the surface; home matters",
        "Leo": "the sky wants warmth, play and self-expression",
        "Virgo": "details want sorting; useful, precise work flows",
        "Libra": "the sky leans toward balance, beauty and agreement",
        "Scorpio": "undercurrents run deep; truth and trust are themes",
        "Sagittarius": "the sky expands — travel, learning, big pictures",
        "Capricorn": "structure and long-game ambition get rewarded",
        "Aquarius": "ideas spark; the unusual and communal are favoured",
        "Pisces": "imagination and empathy dissolve the edges",
    }


# Shared lookup data used to generate combination libraries
_NATAL_PLANETS: tuple[str, ...] = (
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Chiron",
)

_SIGNS: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

_ASPECT_TYPES: tuple[str, ...] = (
    "Conjunction", "Opposition", "Trine", "Square", "Sextile",
    "Quincunx", "Semisextile", "Semisquare", "Sesquiquadrate",
)

_HOUSE_MEANINGS = C.WESTERN_HOUSE_SIGNIFICATIONS


# Element / modality / single-word frames used by the combination builders
_ELEMENT_OF: dict[str, str] = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

_MODE_OF: dict[str, str] = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}

_SIGN_ONE: dict[str, str] = {
    "Aries": "courage", "Taurus": "steadiness", "Gemini": "curiosity",
    "Cancer": "nurture", "Leo": "warmth", "Virgo": "precision",
    "Libra": "harmony", "Scorpio": "intensity", "Sagittarius": "optimism",
    "Capricorn": "ambition", "Aquarius": "innovation", "Pisces": "empathy",
}

_MOON_OPENERS: dict[str, str] = {
    "Aries": "A wilful Moon leads", "Taurus": "A steady Moon leads",
    "Gemini": "A curious Moon leads", "Cancer": "A tender Moon leads",
    "Leo": "A radiant Moon leads", "Virgo": "A precise Moon leads",
    "Libra": "A graceful Moon leads", "Scorpio": "A deep Moon leads",
    "Sagittarius": "A free Moon leads", "Capricorn": "A composed Moon leads",
    "Aquarius": "A cool Moon leads", "Pisces": "A dreamy Moon leads",
}

# Hand-authored notes for the 55 unordered planet pairs. Each note is shared
# across the nine aspect types; the aspect's own verb is appended by the
# builder so all 495 lines read distinctly.
_PAIR_NOTES: dict[tuple[str, str], str] = {
    ("Sun", "Moon"): "identity and instinct fuse - intensified, inseparable",
    ("Sun", "Mercury"): "two personal drives - the self and the mind share one voice",
    ("Sun", "Venus"): "personal warmth and desire unite",
    ("Sun", "Mars"): "will and drive pair up - action lights the self",
    ("Sun", "Jupiter"): "the larger cycle of growth opens - belief expands the self",
    ("Sun", "Saturn"): "personal will meets structure - discipline shapes identity",
    ("Sun", "Uranus"): "individuality sparks against the unexpected",
    ("Sun", "Neptune"): "self dissolves into dream - vision colours identity",
    ("Sun", "Pluto"): "the larger cycle presses - identity meets regeneration",
    ("Sun", "Chiron"): "identity meets the healing wound - purpose through pain",
    ("Moon", "Mercury"): "instinct and mind converse - feeling informs thought",
    ("Moon", "Venus"): "heart and desire harmonise - love feels safe and sweet",
    ("Moon", "Mars"): "feeling meets drive - passion and courage combine",
    ("Moon", "Jupiter"): "emotional faith expands - feelings seek growth",
    ("Moon", "Saturn"): "emotion meets structure - feeling must be earned and held",
    ("Moon", "Uranus"): "instinct turns restless - feeling craves freedom",
    ("Moon", "Neptune"): "dreams saturate the mood - empathy without edge",
    ("Moon", "Pluto"): "feeling deepens into power - secret currents rule",
    ("Moon", "Chiron"): "the mood carries the old wound - nurturing that hurts and heals",
    ("Mercury", "Venus"): "words and love entwine - the charming mind",
    ("Mercury", "Mars"): "the mind takes aim - sharp words and sharper wit",
    ("Mercury", "Jupiter"): "thoughts widen - big ideas and bold talk",
    ("Mercury", "Saturn"): "the mind matures - careful, tested thought",
    ("Mercury", "Uranus"): "thinking leaps - original, sudden insights",
    ("Mercury", "Neptune"): "mind and dream blend - imagination over logic",
    ("Mercury", "Pluto"): "the mind probes - strategic, penetrating thought",
    ("Mercury", "Chiron"): "words carry the wound - communication as healing",
    ("Venus", "Mars"): "desire and drive embrace - magnetism and heat",
    ("Venus", "Jupiter"): "love expands - generosity and good fortune in relating",
    ("Venus", "Saturn"): "love matures - commitment tested by time",
    ("Venus", "Uranus"): "love electrifies - freedom within relating",
    ("Venus", "Neptune"): "love idealises - romance beyond limits",
    ("Venus", "Pluto"): "love transforms - all-or-nothing passion",
    ("Venus", "Chiron"): "love touches the old wound - healing through intimacy",
    ("Mars", "Jupiter"): "drive expands - bold, lucky action",
    ("Mars", "Saturn"): "drive is disciplined - slow, patient force",
    ("Mars", "Uranus"): "action sparks - sudden, brilliant strikes",
    ("Mars", "Neptune"): "drive blurs - action through intuition and images",
    ("Mars", "Pluto"): "the will to power - intense, regenerative force",
    ("Mars", "Chiron"): "the fight carries the wound - assertion as healing",
    ("Jupiter", "Saturn"): "faith meets structure - earned expansion",
    ("Jupiter", "Uranus"): "growth breaks the pattern - freedom-seeking fortune",
    ("Jupiter", "Neptune"): "belief dissolves into dream - mystical expansion",
    ("Jupiter", "Pluto"): "growth through depth - transformation rewards faith",
    ("Jupiter", "Chiron"): "blessing meets the wound - healing grows through meaning",
    ("Saturn", "Uranus"): "structure meets change - reform born of discipline",
    ("Saturn", "Neptune"): "limits meet dreams - vision disciplined into form",
    ("Saturn", "Pluto"): "structure meets regeneration - great, slow rebuilding",
    ("Saturn", "Chiron"): "duty meets the wound - time as the healer",
    ("Uranus", "Neptune"): "change and dream collide - inspired upheaval",
    ("Uranus", "Pluto"): "a generational current - collective awakening and renewal",
    ("Uranus", "Chiron"): "difference touches the wound - individuality heals",
    ("Neptune", "Pluto"): "dreams engulf transformation - deep spiritual melting",
    ("Neptune", "Chiron"): "vision meets the wound - compassion born of suffering",
    ("Pluto", "Chiron"): "the wound is an initiation - power healed through honesty",
}


_RETRO_NOTES: dict[str, str] = {
    "Sun": "reconsider identity", "Moon": "reprocess feeling",
    "Mercury": "review words", "Venus": "review love", "Mars": "review drive",
    "Jupiter": "review faith", "Saturn": "review structure",
    "Uranus": "review freedom", "Neptune": "review dreams",
    "Pluto": "review power", "Chiron": "review the wound",
}

_RETRO_KEYWORDS: dict[str, str] = {
    "Mercury": "a contemplative, inner-directed mind that is self-analytical and learns through absorption rather than instruction",
    "Venus": "a heart that develops its own unique values, undemonstrative on the surface but seeking the perfect love beneath",
    "Mars": "a will that acts inwardly, noncompetitive, exploring the psyche, with repressed or explosive anger that battles the self",
    "Jupiter": "an inwardly expansive faith, philosophical and meditative, attuned to inner meanings, developing its own belief systems",
    "Saturn": "inner stamina and endurance but resistance to change, self-doubting and self-controlled, preferring solitary work",
    "Uranus": "outwardly conventional but inwardly rebellious, highly intuitive, needing internal freedom, making unexpected changes",
    "Neptune": "vivid imagination but difficulty translating vision into action, dreamy, self-deceiving, psychically oversensitive",
    "Pluto": "suppressed power turned inward, a courageous explorer of the psyche with deep insight but compulsive, withdrawn intensity",
    "Chiron": "the wound examined in solitude, healing comes through private reflection and the maverick own cure",
    "Sun": "the Sun cannot turn retrograde, it is the center of the system",
    "Moon": "the Moon cannot turn retrograde, it orbits the Earth from a steady platform",
}

_PLANET_INGRESS_VERB: dict[str, str] = {
    "Sun": "turns the spotlight of the moment",
    "Moon": "resets the emotional tide",
    "Mercury": "changes the language of the hours",
    "Venus": "reshapes what feels beautiful and worth wanting",
    "Mars": "redirects the drive and the fight",
    "Jupiter": "opens a wider door of possibility",
    "Saturn": "lays down a new set of ground rules",
    "Uranus": "sends a fresh jolt through the pattern",
    "Neptune": "softens the edges around a new dream",
    "Pluto": "turns the wheel of a slow transformation",
    "Chiron": "carries the healing work into new territory",
}

_PLANET_STATION_RETRO: dict[str, str] = {
    "Sun": "steps back to reconsider what identity truly needs",
    "Moon": "turns inward to sit with unprocessed feeling",
    "Mercury": "slows the mind for a quieter, second draft",
    "Venus": "asks love and taste to be reconsidered before deciding",
    "Mars": "banks the fire and reviews where the fight is really needed",
    "Jupiter": "pulls faith inward to test what is truly worth expanding",
    "Saturn": "revisits the structures that were built in too much haste",
    "Uranus": "pauses the break for change so it can become a considered one",
    "Neptune": "lets the dream sit in shadow before it clarifies",
    "Pluto": "turns the transformation inward, out of sight",
    "Chiron": "asks the old wound to be tended quietly before it teaches",
}

_PLANET_STATION_DIRECT: dict[str, str] = {
    "Sun": "steps back into the light with a clearer sense of purpose",
    "Moon": "lets the reconsidered feeling move again",
    "Mercury": "sets the revised plan back into motion",
    "Venus": "lets love and taste move forward, now better understood",
    "Mars": "releases the reviewed drive back into action",
    "Jupiter": "sends the tested faith back out into the world",
    "Saturn": "puts the rebuilt structure to work",
    "Uranus": "lets the considered change finally land",
    "Neptune": "brings the clarified dream back into view",
    "Pluto": "resumes the transformation, now more conscious of itself",
    "Chiron": "carries the tended wound back out again as wisdom",
}

# Traditional ruling planet (+ classical co-ruler) for each house's cusp sign;
# used to compose the on-disk house-ruler templates the editor sees.
_HOUSE_RULERS: dict[int, tuple[str, str]] = {
    1: ("Mars", ""), 2: ("Venus", ""), 3: ("Mercury", ""), 4: ("Moon", ""),
    5: ("Sun", ""), 6: ("Mercury", ""), 7: ("Venus", ""),
    8: ("Pluto", "Mars"), 9: ("Jupiter", ""), 10: ("Saturn", ""),
    11: ("Uranus", "Saturn"), 12: ("Neptune", "Jupiter"),
}


def _default_planet_sign_text() -> Dict[str, str]:
    """Per-planet-in-sign natal texts (11 bodies x 12 signs = 132)."""
    return {
        # --- Sun: identity expressed through the sign ---
        "Sun in Aries": "You meet life head-on; identity is forged through initiative, courage and the thrill of the new start",
        "Sun in Taurus": "You grow by building what lasts; identity settles into patience, sensuality and quiet dependability",
        "Sun in Gemini": "You live through questions; identity brightens with every new idea, conversation and detour",
        "Sun in Cancer": "You lead with feeling; identity is rooted in home, memory and the people you protect",
        "Sun in Leo": "You shine by creating; identity wants centre stage, warm hearts and generous applause",
        "Sun in Virgo": "You refine to belong; identity is polished through useful work, precision and quiet improvement",
        "Sun in Libra": "You become through others; identity finds its balance in fairness, beauty and partnership",
        "Sun in Scorpio": "You transform to be real; identity deepens through trust, intensity and honest rebirth",
        "Sun in Sagittarius": "You outgrow your limits; identity expands through travel, learning and contagious faith",
        "Sun in Capricorn": "You climb patiently; identity matures through discipline, responsibility and earned authority",
        "Sun in Aquarius": "You break the mould; identity thrives on originality, ideals and the freedom to be different",
        "Sun in Pisces": "You flow between worlds; identity softens into imagination, empathy and quiet faith",

        # --- Moon: instinct and emotional needs in the sign ---
        "Moon in Aries": "Feelings arrive instantly and pass quickly; instinct wants action, candour and emotional fresh starts",
        "Moon in Taurus": "Instinct craves calm; emotions settle with comfort, rhythm, good food and unhurried peace",
        "Moon in Gemini": "The mood turns on words; instinct wants talk, novelty and something interesting to chew on",
        "Moon in Cancer": "Feelings run deep and protective; instinct nests, remembers and guards its own",
        "Moon in Leo": "The heart wants warmth and notice; instinct blooms with loyalty, play and affectionate drama",
        "Moon in Virgo": "Emotions find calm in order; instinct analyses, tends and quietly worries until things feel useful",
        "Moon in Libra": "Instinct seeks agreement; moods smooth out with kindness, beauty and someone by your side",
        "Moon in Scorpio": "Feelings pool beneath the surface; instinct bonds intensely, guards fiercely and heals in privacy",
        "Moon in Sagittarius": "The mood lifts with horizons; instinct wants freedom, laughter and something to believe in",
        "Moon in Capricorn": "Emotions stay composed; instinct copes by working, waiting and keeping its dignity",
        "Moon in Aquarius": "Feelings detach to observe; instinct needs space, friendship and a cause worth its loyalty",
        "Moon in Pisces": "Moods absorb everything; instinct dreams, empathises and needs quiet water",
        # --- Mercury: thinking and communication in the sign ---
        "Mercury in Aries": "The mind races ahead; thinking is bold, direct and impatient with anything slow or vague",
        "Mercury in Taurus": "Thoughts take root slowly; thinking is practical, sensual and values what is tangible and real",
        "Mercury in Gemini": "The mind is a live wire; thinking races through ideas, questions, puns and endless connections",
        "Mercury in Cancer": "Memory colours every thought; thinking is intuitive, protective and shaped by emotional history",
        "Mercury in Leo": "The mind performs; thinking wants an audience, a stage and a dramatic, generous way with words",
        "Mercury in Virgo": "The mind dissects; thinking is precise, analytical and finds satisfaction in useful detail",
        "Mercury in Libra": "The mind weighs both sides; thinking seeks fairness, elegance and the right word at the right time",
        "Mercury in Scorpio": "The mind probes beneath the surface; thinking is investigative, strategic and trusts what is hidden",
        "Mercury in Sagittarius": "The mind ranges wide; thinking is philosophical, enthusiastic and wants the big picture",
        "Mercury in Capricorn": "The mind structures; thinking is disciplined, cautious and values what is proven and practical",
        "Mercury in Aquarius": "The mind invents; thinking is original, detached and drawn to novel, futuristic ideas",
        "Mercury in Pisces": "The mind imagines; thinking is intuitive, poetic and flows through images more than logic",
        # --- Venus: values and attraction in the sign ---
        "Venus in Aries": "Desire is direct; you value courage, boldness and the thrill of the chase",
        "Venus in Taurus": "Senses lead; you value comfort, beauty, loyalty and the slow pleasure of having",
        "Venus in Gemini": "Curiosity attracts; you value wit, variety and conversation that sparkles with ideas",
        "Venus in Cancer": "You value emotional safety; affection is nurturing, protective and home-centred",
        "Venus in Leo": "You value being adored; affection is warm, dramatic and wants to be seen and celebrated",
        "Venus in Virgo": "You value useful love; affection shows in service, attention to detail and quiet care",
        "Venus in Libra": "You value harmony and partnership; affection is graceful, fair and aesthetically refined",
        "Venus in Scorpio": "You value depth and surrender; affection is intense, possessive and demands truth",
        "Venus in Sagittarius": "You value freedom and adventure; affection is optimistic, playful and philosophically minded",
        "Venus in Capricorn": "You value commitment and status; affection is loyal, reserved and builds for the long term",
        "Venus in Aquarius": "You value friendship and independence; affection is unconventional, detached and idealistic",
        "Venus in Pisces": "You value compassion and romance; affection is empathic, dreamy and dissolves boundaries",
        # --- Mars: drive and assertion in the sign ---
        "Mars in Aries": "Drive is instantaneous; energy surges into competition, bold starts and the joy of going first",
        "Mars in Taurus": "Energy is a slow burn; drive shows as persistence, steady labour and strength that will not quit",
        "Mars in Gemini": "Energy scatters bright; drive races through errands, debates, curiosity and quick, clever moves",
        "Mars in Cancer": "Drive protects its own; energy surges when the home front or someone dear is at stake",
        "Mars in Leo": "Energy takes the stage; drive runs on pride, play, creation and the will to be seen",
        "Mars in Virgo": "Energy is fine-tuned; drive works precisely, efficiently and best when the task matters",
        "Mars in Libra": "Drive plays the long social game; energy surges for fairness, charm and the cause of others",
        "Mars in Scorpio": "Drive is a held breath; energy concentrates, endures and strikes once, decisively",
        "Mars in Sagittarius": "Energy wants the open road; drive surges on beliefs, adventure and causes worth charging",
        "Mars in Capricorn": "Energy is engineered; drive climbs patiently, works relentlessly and wins by staying the course",
        "Mars in Aquarius": "Drive breaks the pattern; energy surges for reform, experiment and the freedom to do it differently",
        "Mars in Pisces": "Energy flows sideways; drive works through intuition, art and quiet persistence rather than force",
        # --- Jupiter: growth, optimism and opportunity in the sign ---
        "Jupiter in Aries": "Faith burns bright here; you grow through confident, self-assertive activity and single-pointed release of energy toward the new",
        "Jupiter in Taurus": "Growth is practical and patient; blessings build through steady, tangible work and reliance on your own resources",
        "Jupiter in Gemini": "Luck rides on ideas; understanding and connection widen your world through communication and broad learning",
        "Jupiter in Cancer": "Blessings flow through feeling; generosity and intuition open the way through family values and protective empathy",
        "Jupiter in Leo": "You grow through creative activity, freely expressing exuberant vitality and warm encouragement of others",
        "Jupiter in Virgo": "You grow through analytical improvement, practical service and attention to what refines and perfects",
        "Jupiter in Libra": "You grow through fair partnership, aesthetic harmony and relating with grace and balance",
        "Jupiter in Scorpio": "You grow through transmutation of desires and unusually thorough understanding of life's inner workings",
        "Jupiter in Sagittarius": "You grow through aspiration toward far-off goals and following your innate faith in life",
        "Jupiter in Capricorn": "You grow through hard work, discipline and steady progress with an innate sense of authority",
        "Jupiter in Aquarius": "You grow through humanitarian ideals, intellectual development and daring experimentation",
        "Jupiter in Pisces": "You grow through living one's ideals, expanding sympathies and compassion toward all that suffers",
        # --- Saturn: structure, responsibility and limits in the sign ---
        "Saturn in Aries": "Discipline is tested in action; you learn to lead without burning out and cultivate courage through patience",
        "Saturn in Taurus": "Duty fits naturally here; patience turns ambition into real achievement through steady productivity",
        "Saturn in Gemini": "Structure lives in thought; your ideas gain weight through rigour, coherent thinking and mental discipline",
        "Saturn in Cancer": "Duty meets deep feeling; you build emotional security through patient responsibility and family loyalty",
        "Saturn in Leo": "Discipline tests creativity; you build self-worth through loyal, disciplined affection and earned recognition",
        "Saturn in Virgo": "Duty finds purpose in precision; organisation and discipline are aimed toward mastering details and perfecting skills",
        "Saturn in Libra": "You seek to establish self through fair partnership and organizing relationships upon principles of balance",
        "Saturn in Scorpio": "You seek to establish self through control of powerful passions and testing your emotional structure",
        "Saturn in Sagittarius": "You seek to establish self through firm beliefs, philosophical pursuits and clearly formulated ideals",
        "Saturn in Capricorn": "You seek to establish self through ambition, authority and disciplined planning of responsibilities",
        "Saturn in Aquarius": "You seek to establish self through disciplined mental abilities, defined knowledge and commitment to social goals",
        "Saturn in Pisces": "You seek to establish self through transcending personality limitations and uniting with a greater ideal",
        # --- Uranus: change, freedom and originality in the sign ---
        "Uranus in Aries": "Awakening through bold, independent action; freedom is found by breaking trail and daring to be first",
        "Uranus in Taurus": "Awakening through radical rebuilding of security; freedom means redefining stability and liberating the material world",
        "Uranus in Gemini": "Awakening through restless, electric thinking; freedom is found in unfettered curiosity and original ideas",
        "Uranus in Cancer": "Awakening through emotional liberation; freedom means breaking inherited family patterns and feeling authentically",
        "Uranus in Leo": "Awakening through original self-expression; freedom is found by shining on one's own terms",
        "Uranus in Virgo": "Awakening through radical refinement; freedom means rethinking routines, health and daily craft from the ground up",
        "Uranus in Libra": "Awakening through unconventional relating; freedom is found in relationships that honour individuality within partnership",
        "Uranus in Scorpio": "Awakening through deep, transformative insight; freedom means confronting shadow and embracing rebirth on one's own terms",
        "Uranus in Sagittarius": "Awakening through liberated belief; freedom is found by questioning inherited truth and seeking wisdom directly",
        "Uranus in Capricorn": "Awakening through radical restructuring of ambition; freedom means redefining authority and success from within",
        "Uranus in Aquarius": "Awakening through visionary ideals; freedom is found in authentic individuality and collective humanitarian goals",
        "Uranus in Pisces": "Awakening through spiritual dissolution; freedom means transcending boundaries and accessing universal consciousness",
        # --- Neptune: dreams, imagination and transcendence in the sign ---
        "Neptune in Aries": "Idealism ignites; dreams of heroism, art and inspired action",
        "Neptune in Taurus": "The dream wants form; imagination grounds itself in craft and healing work",
        "Neptune in Gemini": "Mysticism meets mind; intuition and thought weave into one fabric",
        "Neptune in Cancer": "The boundary dissolves at home; empathy, dreams and family blur into one tide",
        "Neptune in Leo": "The dream is of divine creativity, inspired performance and radiant love",
        "Neptune in Virgo": "The dream is of perfect healing, sacred craft and devotion to the practical ideal",
        "Neptune in Libra": "The dream is of soul-mate union, perfect harmony and transcendent beauty",
        "Neptune in Scorpio": "The dream is of transformative union, occult insight and complete ego surrender",
        "Neptune in Sagittarius": "The dream is of universal truth, mystical seeking and the dissolution of all borders",
        "Neptune in Capricorn": "The dream is of sacred authority, compassionate leadership and spiritual mastery",
        "Neptune in Aquarius": "The dream is of ideal community, telepathic unity and collective vision",
        "Neptune in Pisces": "The dream is of ultimate compassion, mystical union and return to the source",
        # --- Pluto: power, transformation and regeneration in the sign ---
        "Pluto in Aries": "Power transforms through will; crisis burns away what is not essential and rebirth comes through decisive action",
        "Pluto in Taurus": "Power works through the material; resources, body and security are reborn through patient rebuilding",
        "Pluto in Gemini": "Transformation moves through ideas; truth-telling reshapes your world and uncovers the hidden truth",
        "Pluto in Cancer": "Power runs beneath feeling; the deep psyche is cleaned and rebuilt through emotional catharsis",
        "Pluto in Leo": "Power transforms through creative will; the ego dies and the authentic self is reborn through creative crisis",
        "Pluto in Virgo": "Power works through crisis of craft; the self is perfected through relentless refinement and healing",
        "Pluto in Libra": "Power transforms through relationship intensity; partnership is rebuilt from power games into equality",
        "Pluto in Scorpio": "Power runs deepest here; total surrender to transformation brings complete regeneration",
        "Pluto in Sagittarius": "Power transforms through belief crisis; inherited truth is stripped and conviction forged from experience",
        "Pluto in Capricorn": "Power transforms through structural collapse and rebuild; authority is mastered from the inside out",
        "Pluto in Aquarius": "Power transforms through collective revolution; generational conditioning is broken and the future remade",
        "Pluto in Pisces": "Power transforms through ego death; the separate self dissolves and merges with the infinite",
        # --- Chiron: the wounded healer in the sign ---
        "Chiron in Aries": "The wound is in your courage; healing comes when you act anyway and teach others to begin boldly",
        "Chiron in Taurus": "The wound is in your worth; healing comes when you build anyway and value yourself regardless of what you own",
        "Chiron in Gemini": "The wound is in belonging; healing comes when you speak your difference and teach through words",
        "Chiron in Cancer": "The wound is in your roots; healing comes when you nurture from your own healed foundations",
        "Chiron in Leo": "The wound is in self-expression; healing comes when you create from the heart, not for applause",
        "Chiron in Virgo": "The wound is in competence; healing comes when you accept imperfection and serve from wholeness",
        "Chiron in Libra": "The wound is in relationship; healing comes when you relate authentically rather than to please or fix",
        "Chiron in Scorpio": "The wound is in intimacy; healing comes when you face the deepest pain and transform it into power",
        "Chiron in Sagittarius": "The wound is in meaning; healing comes when you trust your own truth over borrowed conviction",
        "Chiron in Capricorn": "The wound is in authority; healing comes when you lead from inner worth, not external approval",
        "Chiron in Aquarius": "The wound is in individuality; healing comes when you embrace your difference as your gift to the collective",
        "Chiron in Pisces": "The wound is in boundaries; healing comes when you channel empathy without losing yourself in others",
    }


def _default_planet_house_text() -> Dict[str, str]:
    """Per-planet-in-house natal texts (11 bodies x 12 houses = 132).

    Every planet gets its own verb (from _PLANET_HOUSE_VERB) and every
    house its own arena (from _HOUSE_ARENA), so each of the 132 lines is
    distinct. Grounded in Sasportas's The Houses (chapters 3-14) and
    March's The Only Way to Learn Astrology (planet-in-house entries).
    """
    roles = _default_planet_role()
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        verb = _PLANET_HOUSE_VERB.get(planet, "works through")
        role = roles.get(planet, planet)
        for house in range(1, 13):
            arena = _HOUSE_ARENA.get(house, f"house {house}")
            meaning = _HOUSE_MEANINGS.get(house, f"house {house}")
            out[f"{planet} in house {house}"] = (
                f"{planet} {verb} {arena}, colouring your {meaning} "
                f"with {role}")
    return out


def _default_sun_moon_text() -> Dict[str, str]:
    """Sun-sign / Moon-sign blend texts (12 x 12 = 144).

    Each blend opens with a Moon-led phrase (so neighbouring blends never
    echo each other) and names what the pair shares: a doubled sign word,
    a doubled element ("Double fire"), or a doubled modality
    ("Double cardinal"), or a complementary element mingling.
    """
    signs = _default_sign_text()
    out: Dict[str, str] = {}
    for sun in _SIGNS:
        for moon in _SIGNS:
            key = f"Sun {sun} \u00b7 Moon {moon}"
            opener = _MOON_OPENERS.get(moon, "A woven Moon leads")
            if sun == moon:
                note = (f"a double {_SIGN_ONE[sun]} signature - "
                        f"{sun} doubled and unmissable")
            elif _ELEMENT_OF[sun] == _ELEMENT_OF[moon]:
                note = (f"Double {_ELEMENT_OF[sun]} - Sun and Moon "
                        f"share the {_ELEMENT_OF[sun]} element")
            elif _MODE_OF[sun] == _MODE_OF[moon]:
                note = (f"Double {_MODE_OF[sun]} - Sun and Moon "
                        f"share a {_MODE_OF[moon]} modality")
            else:
                note = (f"Mingle of {_ELEMENT_OF[sun]} and {_ELEMENT_OF[moon]} "
                        f"- complementary instincts")
            out[key] = (f"{opener} - the Sun in {sun} holds {signs[sun]}; "
                        f"the Moon in {moon} feels its way by {signs[moon]}. "
                        f"{note}.")
    return out


def _default_aspect_pair_text() -> Dict[str, str]:
    """Per-planet-pair aspect texts (55 pairs x 9 types = 495).

    Each of the 55 unordered planet pairs carries a hand-authored note
    (from _PAIR_NOTES); the note is combined with the aspect's own verb
    so every one of the 495 lines reads as a distinct sentence.
    """
    aspects = _default_aspect_text()
    out: Dict[str, str] = {}
    for i, p1 in enumerate(_NATAL_PLANETS):
        for p2 in _NATAL_PLANETS[i + 1:]:
            note = _PAIR_NOTES.get((p1, p2), "two energies meet and combine")
            for aspect in _ASPECT_TYPES:
                verb = aspects.get(aspect, f"{aspect} contact")
                key = f"{p1} {aspect.lower()} {p2}"
                out[key] = f"{key}: {note}; {verb}"
    return out


def _default_angle_sign_text() -> Dict[str, str]:
    """Angle-in-sign texts (2 angles x 12 signs = 24)."""
    signs = _default_sign_text()
    out: Dict[str, str] = {}
    for sign in _SIGNS:
        out[f"Ascendant in {sign}"] = (
            f"Ascendant in {sign}: you meet the world with "
            f"{sign}'s {signs[sign]}")
        out[f"MC in {sign}"] = (
            f"MC in {sign}: your public standing grows through "
            f"{sign}'s {signs[sign]}")
    return out


def _default_planet_sign_retro_text() -> Dict[str, str]:
    """Sign-specific retrograde texts (11 bodies x 12 signs = 132).

    Grounded in Forrest principle (Inner Sky ch. 7) that retrogradation
    reverses a planet polarity, directing its vitality inward toward the
    unconscious, the wild child in the forest, and in Tracy Marks
    per-planet retrograde keywords (Art of Chart Interpretation ch. 7).
    The sign colours the inward journey with its element/modality quality.
    Sun and Moon are included for grid completeness though they can never
    turn retrograde (Forrest: The sun and moon can never turn retrograde).
    """
    roles = _default_planet_role()
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        keyword = _RETRO_KEYWORDS.get(planet, "turns inward for review")
        role = roles.get(planet, planet)
        for sign in _SIGNS:
            element = _ELEMENT_OF[sign]
            mode = _MODE_OF[sign]
            kw = keyword[0].upper() + keyword[1:]
            out[f"{planet} retrograde in {sign}"] = (
                f"{planet} retrograde in {sign}: {role} turns inward. "
                f"{kw}. The {mode}-{element} nature of {sign} shapes "
                f"this inward journey")
    return out




_HOUSE_ARENA: dict[int, str] = {
    1: "the arena of self-presentation -- how you meet the world",
    2: "the arena of resources -- what you earn, own and value",
    3: "the arena of the near world -- siblings, streets and study",
    4: "the arena of roots -- home, family and the inner base",
    5: "the arena of play -- romance, children and creative risk",
    6: "the arena of craft -- work, health and daily service",
    7: "the arena of partnership -- the one-to-one mirror",
    8: "the arena of merging -- shared goods, debt and deep bonds",
    9: "the arena of horizons -- belief, travel and higher study",
    10: "the arena of standing -- career, duty and public name",
    11: "the arena of allies -- friends, groups and future hopes",
    12: "the arena of retreat -- solitude, dreams and quiet release",
}


_PLANET_HOUSE_VERB: dict[str, str] = {
    "Sun": "shines through",
    "Moon": "feels through",
    "Mercury": "thinks and trades through",
    "Venus": "loves and attracts through",
    "Mars": "fights and drives through",
    "Jupiter": "expands through",
    "Saturn": "tests and builds through",
    "Uranus": "electrifies",
    "Neptune": "dreams through",
    "Pluto": "transforms through",
    "Chiron": "heals through",
}


def sign_ruler(sign: str) -> str:
    """Return the modern ruling planet for a zodiac sign."""
    _RULERS = {
        "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury",
        "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury",
        "Libra": "Venus", "Scorpio": "Pluto", "Sagittarius": "Jupiter",
        "Capricorn": "Saturn", "Aquarius": "Uranus", "Pisces": "Neptune",
    }
    return _RULERS.get(sign, "")


_SIGN_CO_RULERS: dict[str, str] = {
    "Scorpio": "Mars", "Aquarius": "Saturn", "Pisces": "Jupiter",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Gemini": "Mercury",
}


def _house_ruler_sentence(ruled_house: int, ruler: str,
                          placed_house: Optional[int],
                          co_ruler: str = "") -> str:
    """Compose one house-ruler line naming the ruler and where it sits."""
    ruled_meaning = _HOUSE_MEANINGS.get(ruled_house, f"house {ruled_house}")
    role = _default_planet_role().get(ruler, ruler)
    co = f" (classical co-ruler {co_ruler})" if co_ruler else ""
    if placed_house is None:
        return (f"Ruler of house {ruled_house} ({ruler}) has no placed house: "
                f"affairs of {ruled_meaning} unfold without a clear outlet{co}")
    placed_meaning = _HOUSE_MEANINGS.get(placed_house, f"house {placed_house}")
    arena = _HOUSE_ARENA.get(placed_house, f"house {placed_house}")
    verb = _PLANET_HOUSE_VERB.get(ruler, "works through")
    head = f"Ruler of house {ruled_house} ({ruler}) in house {placed_house}"
    if placed_house == ruled_house:
        return (f"{head}: the ruler stays home; affairs of {ruled_meaning} "
                f"are concentrated here and colour your "
                f"{placed_meaning} directly{co}")
    return (f"{head}: {role} {verb} {arena}, steering affairs of "
            f"{ruled_meaning} through your {placed_meaning}{co}")


def _default_house_ruler_text() -> Dict[str, str]:
    """House-ruler template texts (12 ruled x 12 placed = 144).

    Each entry is the fully resolved sentence using the sign's traditional
    ruling planet, so the editor sees exactly the wording a report shows.
    The report path re-composes the sentence with the real ruler for the
    chart, so a chart whose 7th cusp is not Libra still names its own ruler.
    """
    out: Dict[str, str] = {}
    for ruled in range(1, 13):
        ruler, co = _HOUSE_RULERS.get(ruled, (f"Ruler of house {ruled}", ""))
        for placed in range(1, 13):
            out[f"ruler of {ruled} in house {placed}"] = _house_ruler_sentence(
                ruled, ruler, placed, co)
    return out



def previous_default_planet_house_value(planet: str, house: int) -> str:
    """The planet-house default shipped before the arena/verb enrichment."""
    role = _default_planet_role().get(planet, planet)
    role_cap = role[0].upper() + role[1:]
    meaning = _HOUSE_MEANINGS.get(house, f"house {house}")
    return (f"{role_cap} -- its outlet is house {house}, "
            f"colouring your {meaning}")


def previous_default_sun_moon_value(sun_sign: str, moon_sign: str) -> str:
    """The Sun/Moon blend default shipped before the enrichment."""
    return (f"Your Sun in {sun_sign} meets your Moon in {moon_sign}: "
            f"identity and instinct blend across these two signs")


def previous_default_aspect_pair_value(p1: str, p2: str, aspect: str) -> str:
    """The aspect-pair default shipped before enrichment."""
    roles = _default_planet_role()
    return (f"{p1} {aspect.lower()} {p2}: "
            f"{roles.get(p1, p1)} contacts {roles.get(p2, p2)}")

def _default_forecast_ingress_text() -> Dict[str, str]:
    """Sky ingress texts (11 planets x 12 signs = 132).

    Warm, plain-English phrasing: the planet's own poetic verb
    (``_PLANET_INGRESS_VERB``) meets the sign's mood note
    (``_default_sign_sky_note``), so the astrological meaning of "this
    body just changed the tone of the sky" stays intact under new words.
    """
    signs = _default_sign_sky_note()
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        verb = _PLANET_INGRESS_VERB.get(planet, "shifts the tone of the sky")
        for sign in _SIGNS:
            note = signs.get(sign, f"a new {sign} chapter quietly opens")
            out[f"{planet} enters {sign}"] = (
                f"{planet} enters {sign} \u2014 {verb}, and {note}.")
    return out


def _previous_default_forecast_ingress_text() -> Dict[str, str]:
    """The ingress wording shipped before the poetic rewrite (migration only)."""
    signs = _default_sign_sky_note()
    old_verbs = {
        "Sun": "illuminates the hours", "Moon": "shifts the mood",
        "Mercury": "quickens thought and talk", "Venus": "eases harmony and taste",
        "Mars": "fuels energy and drive", "Jupiter": "widens opportunities",
        "Saturn": "tightens structure and duty", "Uranus": "sparks sudden change",
        "Neptune": "deepens dreams and imagination",
        "Pluto": "intensifies hidden transformation",
        "Chiron": "opens a healing doorway",
    }
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        verb = old_verbs.get(planet, "activates")
        for sign in _SIGNS:
            note = signs.get(sign, f"a new {sign} cycle begins")
            out[f"{planet} enters {sign}"] = (
                f"{planet} enters {sign}: {verb} - {note}")
    return out


def _default_forecast_station_text() -> Dict[str, str]:
    """Station texts (11 planets x 2 directions = 22)."""
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        retro = _PLANET_STATION_RETRO.get(
            planet, "pauses to review before moving on")
        direct = _PLANET_STATION_DIRECT.get(
            planet, "lets the reviewed plan move forward again")
        out[f"{planet} stations retrograde"] = (
            f"{planet} stations retrograde \u2014 {retro}; "
            f"give it room before pushing forward.")
        out[f"{planet} stations direct"] = (
            f"{planet} stations direct \u2014 {direct}; "
            f"a considered chapter can now move.")
    return out


def _previous_default_forecast_station_text() -> Dict[str, str]:
    """The station wording shipped before the poetic rewrite (migration only)."""
    old_retro = {
        "Sun": "pause the ego", "Moon": "pause the mood",
        "Mercury": "pause thought", "Venus": "pause love",
        "Mars": "pause drive", "Jupiter": "pause faith",
        "Saturn": "pause structure", "Uranus": "pause rebellion",
        "Neptune": "pause dreams", "Pluto": "pause transformation",
        "Chiron": "pause healing",
    }
    old_direct = {
        "Sun": "the ego brightens", "Moon": "the mood stabilises",
        "Mercury": "move forward again", "Venus": "love flows again",
        "Mars": "drive fires again", "Jupiter": "faith expands again",
        "Saturn": "structure firms again", "Uranus": "change returns",
        "Neptune": "dreams clarify", "Pluto": "transformation resumes",
        "Chiron": "healing advances",
    }
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        retro = old_retro.get(planet, "review and wait")
        direct = old_direct.get(planet, "move forward again")
        out[f"{planet} stations retrograde"] = (
            f"{planet} stations retrograde: {retro} before pushing forward")
        out[f"{planet} stations direct"] = (
            f"{planet} stations direct: {direct}; "
            f"put revised plans into motion")
    return out


def _default_forecast_phase_text() -> Dict[str, str]:
    """Lunation phase texts (8 phases), grounded in the phase's classic
    turning-point meaning but told in warmer, story-like language."""
    return {
        "New Moon": (
            "New Moon \u2014 a fresh page turns; plant a quiet intention "
            "and let it take root in the dark before it needs to prove "
            "itself."),
        "Waxing Crescent Moon": (
            "Waxing Crescent Moon \u2014 the first shoot breaks the soil; "
            "keep tending what you have only just begun."),
        "First Quarter Moon": (
            "First Quarter Moon \u2014 a small wall appears in the path; "
            "push through it and let the friction prove your resolve."),
        "Waxing Gibbous Moon": (
            "Waxing Gibbous Moon \u2014 the shape is almost whole; refine "
            "the details and trust the momentum you have already built."),
        "Full Moon": (
            "Full Moon \u2014 the story reaches its brightest point; "
            "something is revealed, celebrated, or brought to a head."),
        "Waning Gibbous Moon": (
            "Waning Gibbous Moon \u2014 the harvest is in; share what you "
            "have learned and give thanks for how far things have come."),
        "Last Quarter Moon": (
            "Last Quarter Moon \u2014 a crossroads of release; let go of "
            "whatever the cycle no longer needs you to carry."),
        "Waning Crescent Moon": (
            "Waning Crescent Moon \u2014 the light thins to almost "
            "nothing; rest here and let the old cycle empty out before "
            "the new one begins."),
    }


def _previous_default_forecast_phase_text() -> Dict[str, str]:
    """The lunation-phase wording shipped before the rewrite (migration only)."""
    return {
        "New Moon": "New Moon: set intentions and plant seeds for the cycle",
        "First Quarter Moon": "First Quarter Moon: take action and push through obstacles",
        "Full Moon": "Full Moon: culmination, revelation and celebration",
        "Last Quarter Moon": "Last Quarter Moon: release, forgive and let go",
        "Waxing Crescent Moon": "Waxing Crescent Moon: gather momentum and commit",
        "Waxing Gibbous Moon": "Waxing Gibbous Moon: refine and trust the process",
        "Waning Gibbous Moon": "Waning Gibbous Moon: gratitude and sharing",
        "Waning Crescent Moon": "Waning Crescent Moon: surrender, rest and renew",
    }


_SIGN_FORECAST_MOOD: dict[str, str] = {
    "Aries": "your courage is looking for a fresh place to land",
    "Taurus": "your steadiness is quietly gathering its own reward",
    "Gemini": "your curiosity keeps finding one more interesting thread",
    "Cancer": "your care for the people closest to you is asking to be shown",
    "Leo": "your warmth wants an audience worth shining for",
    "Virgo": "your eye for detail is turning small fixes into real progress",
    "Libra": "your sense of fairness is smoothing a path between people",
    "Scorpio": "something honest is working its way up from underneath",
    "Sagittarius": "your hunger to learn is pulling you toward a wider view",
    "Capricorn": "your patience is laying one more brick on something built to last",
    "Aquarius": "your own way of seeing things is proving useful to others",
    "Pisces": "your imagination is quietly weaving the practical and the dreamed-of together",
}

_PERIOD_FORECAST_RHYTHM: dict[str, str] = {
    "Daily": "today",
    "Weekly": "this week",
    "Monthly": "this month",
    "Yearly": "this year",
}


def _default_sign_forecast_text() -> Dict[str, str]:
    """Per-sign evergreen forecasts (12 signs x 4 periods = 48, incl. Weekly)."""
    out: Dict[str, str] = {}
    for sign in _SIGNS:
        mood = _SIGN_FORECAST_MOOD.get(sign, "steady growth is quietly underway")
        for period, rhythm in _PERIOD_FORECAST_RHYTHM.items():
            out[f"{sign} \u00b7 {period}"] = (
                f"{sign} \u2014 {rhythm}: {mood}.")
    return out


def _previous_default_sign_forecast_text() -> Dict[str, str]:
    """The sign-forecast wording shipped before Weekly was added (migration only)."""
    out: Dict[str, str] = {}
    for sign in _SIGNS:
        out[f"{sign} \u00b7 Daily"] = (
            f"{sign} \u2014 daily: small choices shape steady growth")
        out[f"{sign} \u00b7 Monthly"] = (
            f"{sign} \u2014 monthly: deeper currents carry the weeks")
        out[f"{sign} \u00b7 Yearly"] = (
            f"{sign} \u2014 yearly: a turning-point year of growth")
    return out


def _default_forecast_period_intro_text() -> Dict[str, str]:
    """Opening lines that frame each forecast period (4 entries).

    Read by ``interpretation.forecast_introduction_text`` as the first
    paragraph of a sign horoscope; editable so the astrologer can set the
    house style for how a Daily, Weekly, Monthly or Yearly reading opens.
    """
    return {
        "Daily": (
            "Today opens like a page turning \u2014 read what the sky is "
            "writing before the hours run ahead of you."),
        "Weekly": (
            "This week gathers its momentum slowly, then asks you to "
            "follow where it leads."),
        "Monthly": (
            "This month sets down roots that will not show their shape "
            "until later \u2014 watch where the sky settles."),
        "Yearly": (
            "Over the next year, the sky turns like a long season \u2014 "
            "patient, layered and building toward something larger than "
            "any single week."),
    }


def _default_forecast_transition_text() -> Dict[str, str]:
    """Bridging lines for the reading (10 entries).

    Four period keys (``Daily``/``Weekly``/``Monthly``/``Yearly``) carry a
    reading from its overview into its detail sections — this is what
    ``interpretation.forecast_introduction_text`` reads today.  Six
    additional event keys (``lunation``/``ingress``/``station``/
    ``eclipse``/``sign_focus``/``sky_aspect``) bridge into a specific
    report section by name, for integrations that walk the horoscope
    section by section rather than by period. All ten stay editable
    house-style wording.
    """
    return {
        "Daily": (
            "As the hours turn, let the picture above meet the choices "
            "in front of you."),
        "Weekly": (
            "Carry that thread forward \u2014 the week ahead builds on "
            "what the sky has just shown."),
        "Monthly": (
            "From here, the month widens: today's placements are only "
            "the opening note."),
        "Yearly": (
            "Let this settle, then look further out \u2014 the year "
            "keeps unfolding beyond any single moment."),
        "lunation": (
            "The Moon's own chapter comes next \u2014 let its phase set "
            "the emotional weather before you read on."),
        "ingress": (
            "Now the sky itself shifts key \u2014 a planet is changing "
            "signs, and the tone of the coming days changes with it."),
        "station": (
            "Here the sky pauses mid-stride \u2014 a station asks you "
            "to notice what is being reconsidered before it moves "
            "again."),
        "eclipse": (
            "This next moment carries extra weight \u2014 an eclipse "
            "turns an ordinary lunation into a hinge point worth "
            "watching."),
        "sign_focus": (
            "Turning now to what touches your own sign directly \u2014 "
            "this is where the sky's mood becomes personal."),
        "sky_aspect": (
            "And out in the wider sky, two planets are talking to each "
            "other \u2014 here is what that conversation is saying."),
    }


def _previous_default_forecast_transition_text() -> Dict[str, str]:
    """The transition wording shipped before the event keys were added
    (migration only) — covers only the original four period keys, since
    the six event keys are new additions with no prior shipped text."""
    return {
        "Daily": (
            "As the hours turn, let the picture above meet the choices "
            "in front of you."),
        "Weekly": (
            "Carry that thread forward \u2014 the week ahead builds on "
            "what the sky has just shown."),
        "Monthly": (
            "From here, the month widens: today's placements are only "
            "the opening note."),
        "Yearly": (
            "Let this settle, then look further out \u2014 the year "
            "keeps unfolding beyond any single moment."),
    }


def _default_forecast_invitation_text() -> Dict[str, str]:
    """Closing practical nudges, one per period (4 entries).

    Read by ``interpretation.forecast_introduction_text`` as the closing
    paragraph of a sign horoscope.
    """
    return {
        "Daily": (
            "A gentle invitation: pick one small, honest action today "
            "and let the sky support it."),
        "Weekly": (
            "Try this: choose one intention for the week and revisit it "
            "each evening."),
        "Monthly": (
            "A practical nudge: name one goal this month can carry, "
            "then take the first modest step."),
        "Yearly": (
            "For the months ahead: keep a simple record of what shifts, "
            "so the year's pattern reveals itself in hindsight."),
    }


def _default_forecast_quiet_text() -> Dict[str, str]:
    """Wording used when a period carries no notable aspects (4 entries).

    Read by ``interpretation.forecast_introduction_text`` as a fallback
    when no sky facts are available for the window.
    """
    return {
        "Daily": (
            "When the sky stays quiet today, that is not nothing \u2014 "
            "it is room to rest, notice and simply be."),
        "Weekly": (
            "A quiet week is not an empty one; let it be the pause "
            "between one chapter and the next."),
        "Monthly": (
            "If the month feels uneventful, use the stillness \u2014 "
            "quiet seasons often prepare the ground for what comes "
            "after."),
        "Yearly": (
            "A quiet year still moves; the deepest changes are "
            "sometimes the ones that never announce themselves."),
    }


_FORECAST_PLANET_IN_SIGN_NOTE: dict[str, str] = {
    "Sun": "warmth and attention gather naturally around your own path right now",
    "Moon": "feelings run close to home, and instinct becomes an unusually reliable guide",
    "Mercury": "your own thoughts and words carry extra clarity and are worth trusting",
    "Venus": "charm, ease and simple pleasures come looking for you",
    "Mars": "energy and initiative are yours to spend \u2014 use them on purpose",
    "Jupiter": "doors widen and confidence grows almost on its own",
    "Saturn": "effort finally counts for something lasting \u2014 stay steady",
    "Uranus": "the urge to break a pattern and choose differently grows loud",
    "Neptune": "intuition deepens, though the edges of things may blur",
    "Pluto": "an old layer of yourself is quietly being remade",
    "Chiron": "an old wound becomes easier to look at honestly, and easier to heal",
}


def _default_forecast_planet_in_sign_text() -> Dict[str, str]:
    """Per-planet-in-sun-sign meaning (11 bodies)."""
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        note = _FORECAST_PLANET_IN_SIGN_NOTE.get(
            planet, "personal growth and energy gather around your sign")
        out[f"{planet} in your sign"] = f"{planet} in your sign: {note}."
    return out


def _previous_default_forecast_planet_in_sign_text() -> Dict[str, str]:
    """The planet-in-sign wording shipped before the rewrite (migration only)."""
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        out[f"{planet} in your sign"] = f"{planet} in your sign: personal growth and energy"
    return out


# Bodies that can appear retrograde in the forecast sky. Sun and Moon are
# excluded (they can never turn retrograde), matching the natal
# ``planet_sign_retro`` convention.
_FORECAST_RETROGRADE_PLANETS: tuple[str, ...] = (
    "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Chiron",
)


def _default_forecast_retrograde_text() -> Dict[str, str]:
    """Currently-retrograde state texts for the Astro-Clock (9 bodies).

    While ``forecast_station`` covers the *moment* a planet stations,
    this group covers the ongoing *state* ("Mercury is retrograde right
    now, so ..."). Each entry blends the planet's station-retro note
    (``_PLANET_STATION_RETRO``) with its natal retro keyword
    (``_RETRO_KEYWORDS``) and role, so every line reads distinctly and
    stays editable separately from the natal ``planet_sign_retro`` voice.
    """
    roles = _default_planet_role()
    out: Dict[str, str] = {}
    for planet in _FORECAST_RETROGRADE_PLANETS:
        retro = _PLANET_STATION_RETRO.get(
            planet, "pauses to review before moving on")
        keyword = _RETRO_KEYWORDS.get(planet, "turns inward for review")
        role = roles.get(planet, planet)
        kw = keyword[0].upper() + keyword[1:] if keyword else keyword
        out[f"{planet} retrograde forecast"] = (
            f"{planet} retrograde \u2014 {retro}; {kw}. "
            f"With {role}, expect review rather than push: revisit, "
            f"revise and re-check before launching anything new.")
    return out


def _previous_default_forecast_retrograde_text() -> Dict[str, str]:
    """No previously shipped wording: this group is new (migration only)."""
    return {}


def _default_forecast_sign_aspect_text() -> Dict[str, str]:
    """Per-planet-to-sun-sign aspect meaning (11 planets x 4 aspects = 44)."""
    roles = _default_planet_role()
    verbs = _default_sky_aspect_text()
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        role = roles.get(planet, planet)
        for aspect in ("Conjunction", "Trine", "Square", "Opposition"):
            key = f"{planet} {aspect} your sign"
            verb = verbs.get(aspect, aspect)
            out[key] = (
                f"{key}: {role} {verb} right now, quietly shaping "
                f"the feel of your days.")
    return out


def _previous_default_forecast_sign_aspect_text() -> Dict[str, str]:
    """The sign-aspect wording shipped before the rewrite (migration only)."""
    roles = _default_planet_role()
    verbs = _default_sky_aspect_text()
    out: Dict[str, str] = {}
    for planet in _NATAL_PLANETS:
        role = roles.get(planet, planet)
        for aspect in ("Conjunction", "Trine", "Square", "Opposition"):
            key = f"{planet} {aspect} your sign"
            verb = verbs.get(aspect, aspect)
            out[key] = (f"{key}: {role} {verb}; "
                        f"this colours your sign's mood and momentum")
    return out


_LUNATION_PHASE_KEYNOTE: dict[str, str] = {
    "New Moon": "a seed quietly gets planted",
    "First Quarter Moon": "a choice has to be pushed through",
    "Full Moon": "something reaches its bright peak",
    "Last Quarter Moon": "something is released and cleared away",
}


def _default_forecast_lunation_in_sign_text() -> Dict[str, str]:
    """Lunation phase-in-sign meaning (4 phases x 12 signs = 48)."""
    sky_notes = _default_sign_sky_note()
    out: Dict[str, str] = {}
    for phase, keynote in _LUNATION_PHASE_KEYNOTE.items():
        for sign in _SIGNS:
            sky_note = sky_notes.get(sign, f"{sign} colours the moment")
            out[f"{phase} in {sign}"] = (
                f"{phase} in {sign}: {keynote}, coloured by {sign}'s way "
                f"of meeting the moment \u2014 {sky_note}.")
    return out


def _previous_default_forecast_lunation_in_sign_text() -> Dict[str, str]:
    """The lunation-in-sign wording shipped before the rewrite (migration only)."""
    out: Dict[str, str] = {}
    for phase in ("New Moon", "First Quarter Moon", "Full Moon", "Last Quarter Moon"):
        for sign in _SIGNS:
            out[f"{phase} in {sign}"] = f"{phase} in {sign}: emotional turning point"
    return out


def _default_forecast_lunation_area_text() -> Dict[str, str]:
    """Lunation phase-by-life-area meaning (4 phases x 12 areas = 48)."""
    out: Dict[str, str] = {}
    for phase, keynote in _LUNATION_PHASE_KEYNOTE.items():
        for area in range(1, 13):
            arena = _HOUSE_ARENA.get(area, f"house {area}")
            out[f"{phase} in area {area}"] = (
                f"{phase} in area {area}: {keynote}, right in {arena}.")
    return out


def _previous_default_forecast_lunation_area_text() -> Dict[str, str]:
    """The lunation-area wording shipped before the rewrite (migration only)."""
    out: Dict[str, str] = {}
    for phase in ("New Moon", "First Quarter Moon", "Full Moon", "Last Quarter Moon"):
        for area in range(1, 13):
            out[f"{phase} in area {area}"] = f"{phase} in area {area}: life focus"
    return out


def _default_eclipse_layer() -> Dict[str, str]:
    """Generic eclipse context (solar / lunar / none) — mention only.

    Eclipses are amplified New and Full Moons; the Babylonian omen
    tradition recorded eclipses around births as moments of heightened
    weight.  No sign/house meaning is claimed yet, so these stay generic
    and editable.
    """
    return {
        "eclipse.generic.solar": (
            "A solar eclipse lands like a New Moon struck with a bell "
            "\u2014 a beginning arrives carrying more weight than usual, "
            "and the story it opens keeps unfolding for months to come."),
        "eclipse.generic.lunar": (
            "A lunar eclipse lands like a Full Moon turned up loud \u2014 "
            "something long hidden steps into the light, and a chapter "
            "reaches an unusually charged ending."),
        "eclipse.generic.none": (
            "No eclipse falls in this window, so the Sun and Moon keep "
            "to their ordinary, unamplified rhythm."),
    }


def _previous_default_eclipse_layer() -> Dict[str, str]:
    """The eclipse wording shipped before the rewrite (migration only)."""
    return {
        "eclipse.generic.solar": (
            "A solar eclipse is a New Moon with extra weight: a new "
            "beginning arrives with unusual force, and its story unfolds "
            "over the months that follow."),
        "eclipse.generic.lunar": (
            "A lunar eclipse is a Full Moon with extra weight: something "
            "hidden comes to light, and a chapter reaches a charged "
            "culmination."),
        "eclipse.generic.none": (
            "No eclipse passages fall in this window — the lunations run "
            "their ordinary course."),
    }


_TRANSIT_ACTION: dict[str, str] = {
    "Sun": "a warm current of visibility and purpose",
    "Moon": "a moving tide of feeling and instinct",
    "Mercury": "a quickened flow of words, news and small decisions",
    "Venus": "a pull toward warmth, beauty and connection",
    "Mars": "a rise of heat, courage and the will to act",
    "Jupiter": "a widening of horizons and buoyant confidence",
    "Saturn": "a sober, patient test that rewards structure",
    "Uranus": "a sudden spark that breaks an old rut wide open",
    "Neptune": "a soft mist that blurs the edges and stirs imagination",
    "Pluto": "a slow undertow that transforms things from beneath",
    "Chiron": "an old wound reopened gently enough to finally heal",
}


def _default_transit_natal_text() -> Dict[str, str]:
    """Transit-to-natal aspect notes (11 transiting x 11 natal x 9 aspects).

    A transit hands the transiting planet's current sky-energy to the natal
    planet it touches (transits *activate* the natal chart — Tracy Marks,
    ``The Art of Chart Interpretation``); the aspect type sets how that
    energy is delivered.  Composed from per-planet transit actions x
    per-planet natal roles x aspect verbs, so every entry is specific yet
    consistent, and stays editable in the Interpretations screen.
    """
    roles = _default_planet_role()
    verbs = _default_sky_aspect_text()
    out: Dict[str, str] = {}
    for t in _NATAL_PLANETS:
        act = _TRANSIT_ACTION.get(t, t)
        for aspect, verb in verbs.items():
            for n in _NATAL_PLANETS:
                role = roles.get(n, n)
                out[f"{t} {aspect} natal {n}"] = (
                    f"{act[0].upper()}{act[1:]} {verb}, reaching into "
                    f"your natal {n} ({role}).")
    return out


def _previous_default_transit_natal_text() -> Dict[str, str]:
    """The transit-to-natal wording shipped before the rewrite (migration only)."""
    roles = _default_planet_role()
    verbs = _default_sky_aspect_text()
    action = {
        "Sun": "a spotlight of vitality and visible purpose",
        "Moon": "the moving tide of mood and instinct",
        "Mercury": "news, choices and a quickened mind",
        "Venus": "warmth, attraction and the pull to relate",
        "Mars": "drive, heat and the courage to act",
        "Jupiter": "widening horizons and buoyant momentum",
        "Saturn": "a sober test that rewards structure and patience",
        "Uranus": "electric disruption that breaks old ruts",
        "Neptune": "a dissolving mist that blurs lines and inspires",
        "Pluto": "an underworld current that transforms at the roots",
        "Chiron": "a wound-opener that teaches through what hurts",
    }
    out: Dict[str, str] = {}
    for t in _NATAL_PLANETS:
        act = action.get(t, t)
        for aspect, verb in verbs.items():
            for n in _NATAL_PLANETS:
                role = roles.get(n, n)
                out[f"{t} {aspect} natal {n}"] = (
                    f"{act.capitalize()} {verb}, waking the natal "
                    f"{n} ({role}).")
    return out


def _default_synthesis_section_headings() -> Dict[str, str]:
    """Section titles for future full-chart synthesis paragraphs."""
    return {
        "chart_overview": "Your chart at a glance",
        "core_identity": "The heart of your nature",
        "emotional_landscape": "Your inner tides",
        "relationships": "How you meet and receive others",
        "gifts": "Strengths already alive in you",
        "growth_path": "Where life is inviting growth",
        "forecast_bridge": "How the current sky meets your chart",
        "closing": "Bringing the whole story together",
    }


def _default_synthesis_narrative_bridges() -> Dict[str, str]:
    """Warm transition lines for full-chart synthesis sections."""
    return {
        "overview_to_identity": (
            "From the wide pattern, your chart keeps circling back to the "
            "qualities that feel most deeply yours."),
        "identity_to_emotions": (
            "Beneath that visible character, your emotional life tells its "
            "own quieter truth."),
        "emotions_to_relationships": (
            "What you feel inwardly naturally shapes the way you lean toward "
            "connection."),
        "relationships_to_strengths": (
            "Seen together, these patterns also reveal the gifts you bring "
            "without forcing them."),
        "strengths_to_growth": (
            "Every strength carries a next horizon, and your chart points "
            "there gently rather than harshly."),
        "growth_to_forecast": (
            "The current sky does not replace your birth pattern; it simply "
            "shows which themes are ripening now."),
        "forecast_to_closing": (
            "When those present-day currents settle back into the wider "
            "story, the chart reads less like fate and more like a living "
            "conversation."),
    }


def _default_planetary_archetypal_imagery() -> Dict[str, str]:
    """Mythic and archetypal imagery for planetary synthesis."""
    return {
        "Sun": (
            "The Sun is the hearth-fire at the centre of the house — warm, "
            "steady and made to be seen."),
        "Moon": (
            "The Moon is the tide-lit inner room where memory, longing and "
            "belonging keep changing shape."),
        "Mercury": (
            "Mercury is the messenger at the crossroads, quick-footed enough "
            "to carry insight between worlds."),
        "Venus": (
            "Venus is the garden in bloom — attraction, value and tenderness "
            "made visible through beauty."),
        "Mars": (
            "Mars is the bright blade and the drumbeat — courage, appetite "
            "and motion asking for a clear direction."),
        "Jupiter": (
            "Jupiter is the open road and the temple threshold, widening the "
            "story wherever hope is given room."),
        "Saturn": (
            "Saturn is the old mountain path — demanding, faithful and "
            "capable of turning effort into mastery."),
        "Uranus": (
            "Uranus is the lightning strike that wakes the sleeping village "
            "and reminds it life can change quickly."),
        "Neptune": (
            "Neptune is the sea-mist over the horizon, dissolving hard edges "
            "so imagination and compassion can return."),
        "Pluto": (
            "Pluto is the underworld seed — hidden, potent and quietly "
            "transforming life from the roots upward."),
        "Chiron": (
            "Chiron is the healer on the threshold, carrying wisdom born of "
            "what has hurt and what has been mended."),
    }


def _default_synthesis_strengths() -> Dict[str, str]:
    """Affirming strength language for synthesis paragraphs."""
    return {
        "resilience": (
            "You have a way of returning to yourself after change, often with "
            "more wisdom than you had before."),
        "heart": (
            "Warmth is one of your natural resources; people tend to feel it "
            "even before you name it."),
        "discernment": (
            "You notice what matters, and that clarity can become a steady "
            "form of guidance."),
        "adaptability": (
            "When life shifts, you are often more flexible than you first "
            "give yourself credit for."),
        "devotion": (
            "Once something feels meaningful, you know how to stay with it "
            "long enough for depth to grow."),
        "imagination": (
            "Your symbolic and imaginative mind helps you find meaning where "
            "others might only see fragments."),
        "integrity": (
            "There is a part of you that wants to live in a way that feels "
            "clean, honest and internally aligned."),
        "renewal": (
            "Even after hard seasons, your chart suggests a capacity for "
            "renewal rather than finality."),
    }


def _default_synthesis_growth_language() -> Dict[str, str]:
    """Gentle growth framing for non-fatalistic synthesis."""
    return {
        "tender_edge": (
            "Where this chart feels tender, growth asks for patience and "
            "truthfulness, not self-punishment."),
        "becoming": (
            "You do not have to embody every part of this pattern at once; "
            "much of it unfolds through becoming."),
        "integration": (
            "The invitation is not to erase contradiction, but to let "
            "different parts of you learn each other's language."),
        "choice_point": (
            "Astrology names the weather around a choice; it does not remove "
            "your agency inside that weather."),
        "self_trust": (
            "The more gently you listen to your own timing, the more clearly "
            "this chart tends to open."),
        "compassionate_reframe": (
            "A difficult signature can often be read as unused strength "
            "waiting for kinder conditions."),
        "practice": (
            "Small repeated choices matter here more than dramatic gestures."),
        "timing": (
            "Some lessons ripen slowly, and your chart does not ask you to "
            "force what is still growing."),
    }


def _default_forecast_synthesis() -> Dict[str, str]:
    """Language for weaving current transits into the natal synthesis."""
    return {
        "current_weather": (
            "The current sky is best read as weather around your deeper "
            "nature — temporary, meaningful and always moving."),
        "supportive_window": (
            "When the sky opens a supportive window, it becomes easier to act "
            "on qualities your chart already contains."),
        "turning_point": (
            "A louder transit can mark a turning point, but not a verdict; "
            "it is a moment of emphasis, not a fixed ending."),
        "slow_build": (
            "Some forecasts work like seasons rather than events, quietly "
            "building change one layer at a time."),
        "integration_note": (
            "The most useful forecast is the one that helps you respond with "
            "more awareness to the life you are already living."),
        "renewal": (
            "Even intense skies can become chapters of renewal when they are "
            "met with steadiness, support and perspective."),
        "retrograde_window": (
            "A retrograde window asks for review rather than push: revisit, "
            "revise and let the second look do its quiet work."),
    }


def _default_synthesis_conclusions() -> Dict[str, str]:
    """Closing language for a warm, agency-centred chart synthesis."""
    return {
        "affirming_close": (
            "Nothing in this chart is a sentence — it is a living pattern, "
            "and you keep shaping how its gifts are used."),
        "agency_close": (
            "Your birth chart describes tendencies and rhythms, but your "
            "choices remain part of the story every day."),
        "cyclical_close": (
            "What feels unfinished now may simply be in season for a later "
            "chapter; life moves in cycles, not straight lines."),
        "tender_close": (
            "The softest parts of the chart are not flaws to hide — they are "
            "often where meaning, intimacy and healing begin."),
        "next_step_close": (
            "Take from this reading whatever helps you move with more "
            "self-knowledge, warmth and permission to grow."),
    }


# Names follow ``constants.NAKSHATRA_NAMES`` exactly (same order).  The
# briefs follow traditional Jyotish lore (deity, symbol and shakti per
# nakshatra); no Vedic nakshatra text exists in ``Reference/Astrology``.
_NAKSHATRA_DESCRIPTIONS = (
    "Swift healers and initiators — ruled by the Ashvini horsemen, "
    "symbol the horse's head; its shakti brings fast healing and new journeys.",
    "The bearer of burdens — Yama's star, symbol the yoni; its shakti "
    "carries discipline and restraint through to the moment of birth.",
    "The blade of purification — Agni's star, symbol the razor or flame; "
    "its shakti burns away the impure with cutting clarity.",
    "The red, fertile one — Prajapati's star, symbol the ox cart; its "
    "shakti makes things grow: charisma, beauty and steady creation.",
    "The gentle seeker — Soma's star, symbol the deer's head; its shakti "
    "gives a searching curiosity always hunting the fragile bloom.",
    "The storm that cleanses — Rudra's star, symbol the teardrop; its "
    "shakti purifies through upheaval and sharpens a penetrating mind.",
    "The return of the light — Aditi's star, symbol the quiver of "
    "arrows; its shakti renews: what is lost comes back, generous and safe.",
    "The nourisher — Brihaspati's star, symbol the cow's udder; its "
    "shakti feeds and protects, building trust like a nurse at the bedside.",
    "The coiled serpent — the Nagas' star, symbol the serpent; its "
    "shakti embraces with hidden, kundalini wisdom.",
    "The throne of the ancestors — the Pitris' star, symbol the royal "
    "throne; its shakti grants lineage, honour and inherited authority.",
    "The hammock of enjoyment — Bhaga's star, symbol the front legs of "
    "the bed; its shakti gives pleasure, creativity and easy charm.",
    "The patron of unions — Aryaman's star, symbol the back legs of the "
    "bed; its shakti builds lasting friendship, marriage and mutual aid.",
    "The skilled hand — Savitar's star, symbol the hand; its shakti "
    "crafts, heals and jokes with clever dexterity.",
    "The brilliant jewel — Tvashtri's star, symbol the pearl; its "
    "shakti designs beauty with dazzling artistry and charisma.",
    "The wind that bends — Vayu's star, symbol the young shoot swaying; "
    "its shakti gives independence, adaptability and the trader's balance.",
    "The forked goal — Indra-Agni's star, symbol the triumphal gateway; "
    "its shakti focuses ambition relentlessly on the harvest.",
    "The devoted friend — Mitra's star, symbol the lotus; its shakti "
    "organises cooperation and keeps groups in harmony.",
    "The eldest — Indra's star, symbol the umbrella and earring; its "
    "shakti carries seniority, protection and responsible power.",
    "The root — Nirrti's star, symbol the tied bundle of roots; its "
    "shakti digs to the bottom of things, breaking up before regrowth.",
    "The invincible declaration — Apas' star, symbol the winnowing fan; "
    "its shakti stirs emotional tides and bold proclamations.",
    "The undefeated — the Vishvedevas' star, symbol the elephant's "
    "tusk; its shakti wins through quiet, permanent persistence.",
    "The listening ear — Vishnu's star, symbol the three footprints; "
    "its shakti learns and preserves, hearing what tradition teaches.",
    "The drumbeat of wealth — the eight Vasus' star, symbol the drum; "
    "its shakti keeps cosmic timing, music and fortune in rhythm.",
    "The hundred healers — Varuna's star, symbol the empty circle; its "
    "shakti heals from beyond the veil and guards mysterious bounds.",
    "The blazing penance — Aja Ekapada's star, symbol the sword's "
    "edge; its shakti transforms through fire, austerity and intensity.",
    "The deep rain — Ahir Budhnya's star, symbol the serpent of the "
    "deep; its shakti rains compassion from the ocean floor of the mind.",
    "The safe passage — Pushan's star, symbol the fish; its shakti "
    "shepherds travellers to their final nourishment and home.",
)


def _default_nakshatra_text() -> Dict[str, str]:
    """The 27 lunar mansions of Jyotish (keys = NAKSHATRA_NAMES order)."""
    names = (
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
        "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
        "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati",
        "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
        "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
        "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
    )
    return dict(zip(names, _NAKSHATRA_DESCRIPTIONS))


def _default_dasha_text() -> Dict[str, str]:
    """Vimshottari mahadasha themes (9 planets, keys like "Sun Dasha")."""
    themes = {
        "Sun": ("Six years of visibility and authority — father themes, "
                "vitality and recognition step forward; shine without "
                "burning out."),
        "Moon": ("Ten years of feeling and flow — home, mother, the "
                 "public and shifting moods; gentleness carries the period."),
        "Mars": ("Seven years of drive and courage — siblings, property, "
                 "competition and initiative; act with discipline rather "
                 "than impatience."),
        "Rahu": ("Eighteen years of ambition and the unusual — foreign "
                 "connections and sudden rises; ride the whirlwind, watch "
                 "excess."),
        "Jupiter": ("Sixteen years of growth and grace — teaching, "
                    "children, faith and fortune; expansive blessings reward "
                    "generosity."),
        "Saturn": ("Nineteen years of structure and harvest — duty, "
                   "endurance and slow mastery; patient work builds what "
                   "lasts."),
        "Mercury": ("Seventeen years of mind and trade — learning, "
                    "writing, commerce and networks; versatile communication "
                    "opens doors."),
        "Ketu": ("Seven years of release — detachment, purification and "
                 "spiritual turning inward; let go of what is finished."),
        "Venus": ("Twenty years of love and refinement — art, comfort, "
                  "partnership and sweetness; beauty and diplomacy flourish."),
    }
    return {f"{planet} Dasha": text for planet, text in themes.items()}


def _default_vedic_glossary_text() -> Dict[str, str]:
    """Plain-English explanations of the Vedic/Ayurvedic words the
    reports use, so an English-reading audience is never lost.  Includes
    the deities named in the nakshatra texts.  Every entry is editable.
    """
    return {
        # -- core Jyotish terms --
        "Jyotish": ("Vedic astrology, the 'science of light' from ancient "
                    "India. It reads the same sky as Western astrology but "
                    "uses the fixed-star (sidereal) zodiac."),
        "Ayanamsa": ("The slowly growing difference between the season-based "
                     "(tropical) zodiac and the fixed-star (sidereal) zodiac. "
                     "The Lahiri ayanamsa is India's official standard."),
        "Sidereal": ("The fixed-star zodiac: signs measured from the actual "
                     "stars rather than from the seasons."),
        "Nakshatra": ("A nakshatra is one of the 27 lunar mansions - the "
                      "Moon's monthly path is divided into 27 star-clusters, "
                      "each with its own deity, symbol and power."),
        "Pada": ("A pada is one quarter of a nakshatra (each has 4), giving "
                 "a finer flavour to the placement."),
        "Rashi": ("A rashi is a zodiac sign - the same twelve signs as in "
                  "Western astrology, but shifted by the ayanamsa."),
        "Graha": ("A graha is a planet, literally 'that which grasps' - the "
                  "nine grahas include the Sun, Moon, planets and the two "
                  "lunar nodes."),
        "Drishti": ("Drishti means 'sight' or gaze: a graha's aspect onto "
                    "another house or planet."),
        "Vimshottari Dasha": ("The Vimshottari Dasha is the classic 120-year "
                              "cycle of planetary periods. Each life chapter "
                              "is ruled by one graha, starting from the Moon's "
                              "nakshatra at birth."),
        "Dasha": ("A dasha is a planetary period - a chapter of life ruled "
                  "by one graha."),
        "Mahadasha": ("A mahadasha is a major dasha period (years long), as "
                      "opposed to its shorter sub-periods."),
        "Antardasha": ("An antardasha (or bhukti) is a sub-period inside a "
                       "mahadasha - a chapter within the chapter."),
        "Rahu": ("Rahu is the Moon's north node - the 'head of the eclipse "
                 "serpent'. A shadowy graha of ambition, hunger and unusual "
                 "paths; it has no physical body."),
        "Ketu": ("Ketu is the Moon's south node - the 'tail of the eclipse "
                 "serpent'. A shadowy graha of detachment, past-life gifts "
                 "and release."),
        "Lagna": ("The lagna is the ascendant - the sign rising on the "
                  "eastern horizon at birth; the chart's front door."),
        "Gochara": ("Gochara means transit - where the grahas are wandering "
                    "right now, compared to the birth chart."),
        "Benefic": ("A benefic is a favourable graha (Jupiter, Venus, "
                    "Mercury, the waxing Moon) whose gifts flow easily."),
        "Malefic": ("A malefic is a challenging graha (Saturn, Mars, Rahu, "
                    "Ketu) whose lessons come through pressure - and build "
                    "strength."),
        "Guru": ("A guru is a teacher or spiritual guide; in Jyotish the "
                 "word also names Jupiter, the great teacher of the gods."),
        "Dharma": ("Dharma is one's duty or life-purpose - the path that "
                   "fits the soul."),
        "Karma": ("Karma is action and its harvest: the causes we sow and "
                  "the results we reap, carried across the chart."),
        # -- Ayurvedic terms --
        "Ayurveda": ("Ayurveda is Vedic medicine, the 'science of life' - "
                     "India's traditional healing system, sister science to "
                     "Jyotish."),
        "Dosha": ("A dosha is an Ayurvedic constitution type - a blend of "
                  "the elements that shapes body and temperament. The three "
                  "doshas are Vata, Pitta and Kapha."),
        "Vata": ("Vata is the air-and-ether dosha: movement, nerves, "
                 "breath and quick change. Vata types are lively, light and "
                 "easily scattered."),
        "Pitta": ("Pitta is the fire-and-water dosha: transformation, "
                  "metabolism and heat. Pitta types are sharp, driven and "
                  "intense."),
        "Kapha": ("Kapha is the earth-and-water dosha: structure, "
                  "nourishment and endurance. Kapha types are steady, warm "
                  "and build to last."),
        # -- deities named in the nakshatra texts --
        "Ashvini horsemen": ("The Ashvini horsemen are the twin divine "
                             "physicians of the Vedas - healers who ride at "
                             "dawn."),
        "Yama": ("Yama is the lord of death and discipline - the keeper of "
                 "boundaries and just consequences."),
        "Agni": ("Agni is the god of fire - purifier, messenger between "
                 "humanity and the gods."),
        "Prajapati": ("Prajapati is the creator god - the lord of offspring "
                      "and growth."),
        "Soma": ("Soma is the moon-god of nectar - refreshing, poetic and "
                 "gentle."),
        "Rudra": ("Rudra is the howling storm-god - fierce purifier, an "
                  "early form of Shiva."),
        "Aditi": ("Aditi is the boundless mother of the gods - "
                  "limitlessness and safe return."),
        "Brihaspati": ("Brihaspati is the priest of the gods - Jupiter as "
                       "the wise counsellor."),
        "Nagas": ("The Nagas are serpent beings of hidden wisdom - keepers "
                  "of coiled, kundalini power."),
        "Pitris": ("The Pitris are the ancestors - the family line whose "
                   "blessings sit behind the throne."),
        "Bhaga": ("Bhaga is the god of enjoyment, fortune and the good "
                  "things shared at the table."),
        "Aryaman": ("Aryaman is the god of patronage, courtship and lasting "
                    "friendship - the matchmaker of alliances."),
        "Savitar": ("Savitar is the solar inspirer - the rising sun's "
                    "golden hand that sets the mind in motion."),
        "Tvashtri": ("Tvashtri is the celestial craftsman - the divine "
                     "engineer who shapes shining forms."),
        "Vayu": ("Vayu is the god of wind - breath, movement and the "
                 "weather of the mind."),
        "Indra": ("Indra is the king of the gods - thunder-wielding "
                  "champion of seniority and protection."),
        "Mitra": ("Mitra is the god of friendship and contracts - the "
                  "companion who keeps harmony."),
        "Nirrti": ("Nirrti is the goddess of dissolution and decay - the "
                   "necessary fallow before regrowth."),
        "Apas": ("The Apas are the water goddesses - the emotional tides "
                 "that fertilise everything."),
        "Vishvedevas": ("The Vishvedevas are the company of all the gods "
                        "together - universal, all-inclusive victory."),
        "Varuna": ("Varuna is the god of cosmic order and the waters - the "
                   "keeper of bonds and mysterious bounds."),
        "Vasus": ("The Vasus are eight gods of abundance - dwelling, "
                  "radiance and the treasures of the elements."),
        "Aja Ekapada": ("Aja Ekapada is the one-footed goat - a form of "
                        "fire that crosses the sky in a single, purifying "
                        "leap."),
        "Ahir Budhnya": ("Ahir Budhnya is the serpent of the deep - the "
                         "calm ocean floor from which compassion rains."),
        "Pushan": ("Pushan is the shepherd of travellers - the nourisher "
                   "who guides every journey safely home."),
        "Kundalini": ("Kundalini is the coiled serpent-power of yoga - "
                      "dormant energy at the base of the spine that rises "
                      "with practice."),
    }


def _default_planet_dosha_text() -> Dict[str, str]:
    """Each graha's Ayurvedic dosha (traditional correspondences)."""
    return {
        "Sun": ("Pitta dosha (fire + water: transformation) - the Sun carries "
                "vital heat: leadership, digestion and the flame of "
                "identity. In Ayurveda it governs the eyes and the heart's "
                "fire."),
        "Moon": ("Kapha dosha (earth + water: structure) - the Moon rules "
                 "the waters: fluids, nourishment and the tides of feeling. "
                 "In Ayurveda it governs the mind's moisture and rest."),
        "Mars": ("Pitta dosha (fire + water: transformation) - Mars is pure "
                 "heat: drive, blood, muscle and the courage to act. In "
                 "Ayurveda it governs the marrow and the temper."),
        "Mercury": ("Vata dosha (air + ether: movement) - Mercury is the "
                    "nervous quicksilver: speech, trade and connecting "
                    "thought. In Ayurveda it governs the nerves and skin."),
        "Jupiter": ("Kapha dosha (earth + water: structure) - Jupiter "
                    "expands and nourishes: wisdom, fat tissue, growth and "
                    "faith. In Ayurveda it governs the liver and plenty."),
        "Venus": ("Kapha-Vata blend - Venus sweetens and softens: beauty, "
                  "reproduction, comfort and art. In Ayurveda it governs the "
                  "reproductive waters and the palate."),
        "Saturn": ("Vata dosha (air + ether: movement) - Saturn dries and "
                   "slows: bones, longevity and sober time. In Ayurveda it "
                   "governs the joints and the lesson of patience."),
        "Rahu": ("Vata dosha (air + ether: movement) - Rahu is smoke and "
                 "storm: eccentric craving, sudden rises and unquiet nerves. "
                 "In Ayurveda it scatters and intoxicates."),
        "Ketu": ("Vata dosha with a fiery spike - Ketu dissolves: "
                 "detachment, past-life gifts and moksha (liberation). In "
                 "Ayurveda it burns away what is finished."),
    }


# Animal briefs follow the chapter epithets and personality summaries of
# the extracted reference text (\_extracted/Chinese Astrology Exploring
# The Eastern Zodiac.txt), cited by chapter.
def _default_chinese_zodiac_text() -> Dict[str, str]:
    """The 12 Earthly-Branch animals (source-grounded briefs)."""
    return {
        "Rat": ("First sign — the 'Concealed Charmer'. Charm, creativity "
                "and survival: analytical, curious and highly intelligent, "
                "Rat souls live in a rich, private world and use charm to "
                "deflect unpleasantness (Eastern Zodiac, ch. 3)."),
        "Ox": ("Second sign — the 'Head Honcho' (the Durable Ox). The "
               "zodiac's patient 'marathon' personality: steady, "
               "determined and hard to sway, happiest with hands in the "
               "soil (ch. 4)."),
        "Tiger": ("Third sign — the 'Go-Getter' (the Noble Tiger). "
                  "Tempts fate and fights for noble ideals with unwavering "
                  "courage, leadership and visionary plans (ch. 5)."),
        "Rabbit": ("Fourth sign — the 'Artful Dodger'. Compassionate, "
                   "devoted friends and understanding counsellors who "
                   "dissect situations and weigh options (ch. 6)."),
        "Dragon": ("Fifth sign — one of mystery, vitality and the "
                   "universe itself: the zodiac's charismatic showman, "
                   "burning with grand ideals (ch. 7)."),
        "Snake": ("Sixth sign — the 'Learned One'. Gathered strength "
                  "and quiet accumulation of energy: wise, private and "
                  "intuitively deep (ch. 8)."),
        "Horse": ("Seventh sign — the 'Great Debater' (the Decisive "
                  "Horse). Lively, engaging and artistic: loves movement, "
                  "crowds and conversation (ch. 9)."),
        "Goat": ("Eighth sign — the 'Capricious Artist' (the Creative "
                 "Goat). Gentle, creative and compassionate, with artist's "
                 "taste and a longing for harmony (ch. 10)."),
        "Monkey": ("Ninth sign — the 'Merry Mercurial'. Action, "
                   "possibilities and remarkable energy: clever, inventive "
                   "and irrepressibly curious (ch. 11)."),
        "Rooster": ("Tenth sign — the flamboyant, forthright performer: "
                    "precise and orderly beneath the bright plumage, "
                    "speaking plainly and keeping high standards (ch. 12)."),
        "Dog": ("Eleventh sign — the 'Watchful Dog'. Loyal, honest and "
                "fair-minded: guardian of the underdog, trusted with "
                "everyone's secrets (ch. 13)."),
        "Pig": ("Twelfth sign — the 'Tolerant Pig'. Sincere, generous "
                "and unpretentious: enjoys life's pleasures with a trusting "
                "heart (ch. 14)."),
    }


def _default_chinese_element_text() -> Dict[str, str]:
    """The five elements with their creative/destructive cycles (ch. 15)."""
    return {
        "Wood": ("Spring and the east — benevolence, growth and "
                 "expansion. Wood feeds Fire and is fed by Water (creative "
                 "cycle); Metal cuts Wood (destructive cycle) (ch. 15)."),
        "Fire": ("Summer and the south — passion, dynamism and radiance. "
                 "Wood feeds Fire; Fire creates Earth (ash), while Water "
                 "quenches Fire (ch. 15)."),
        "Earth": ("The stable centre — patience, practicality and "
                  "honesty. Fire creates Earth; Earth bears Metal, while "
                  "Wood parts the fields of Earth (ch. 15)."),
        "Metal": ("Autumn and the west — strength, precision and "
                  "righteousness. Earth bears Metal; Metal collects Water, "
                  "while Fire melts Metal (ch. 15)."),
        "Water": ("Winter and the north — wisdom, adaptability and "
                  "reflection. Metal collects Water; Water nourishes Wood, "
                  "while Earth dams Water (ch. 15)."),
    }


def _default_yin_yang_text() -> Dict[str, str]:
    """The two complementary forces (grounded in ch. 15's taiji text)."""
    return {
        "Yin": ("The receptive (negative) force: female, dark, soft, moist, "
                "nighttime and docile — the inward, restful half of the "
                "taiji (Eastern Zodiac, ch. 15)."),
        "Yang": ("The active (positive) force: male, bright, hard, dry, "
                 "daytime and aggressive — the outward, expressive half "
                 "of the taiji (ch. 15)."),
    }


# Maps forecast-only field names to the callable that rebuilds their
# *previously shipped* defaults, so ``InterpretationLibrary.from_dict`` can
# upgrade a saved value that still matches the old wording exactly, while
# leaving any genuine astrologer customisation untouched.
_FORECAST_MIGRATION_DEFAULTS: dict = {
    "forecast_ingress": _previous_default_forecast_ingress_text,
    "forecast_station": _previous_default_forecast_station_text,
    "forecast_phase": _previous_default_forecast_phase_text,
    "sign_forecast": _previous_default_sign_forecast_text,
    "forecast_planet_in_sign": _previous_default_forecast_planet_in_sign_text,
    "forecast_sign_aspect": _previous_default_forecast_sign_aspect_text,
    "forecast_lunation_in_sign": _previous_default_forecast_lunation_in_sign_text,
    "forecast_lunation_area": _previous_default_forecast_lunation_area_text,
    "eclipse_layer": _previous_default_eclipse_layer,
    "transit_natal": _previous_default_transit_natal_text,
    "forecast_transition": _previous_default_forecast_transition_text,
    "forecast_retrograde": _previous_default_forecast_retrograde_text,
}


@dataclass
class InterpretationLibrary:
    """Editable interpretation text grouped by topic."""

    sign_text: Dict[str, str] = field(default_factory=_default_sign_text)
    aspect_text: Dict[str, str] = field(default_factory=_default_aspect_text)
    planet_role: Dict[str, str] = field(default_factory=_default_planet_role)
    planet_sky_note: Dict[str, str] = field(default_factory=_default_planet_sky_note)
    sky_aspect_text: Dict[str, str] = field(default_factory=_default_sky_aspect_text)
    sign_sky_note: Dict[str, str] = field(default_factory=_default_sign_sky_note)
    # --- Natal combination libraries ---
    planet_sign: Dict[str, str] = field(default_factory=_default_planet_sign_text)
    planet_house: Dict[str, str] = field(default_factory=_default_planet_house_text)
    sun_moon: Dict[str, str] = field(default_factory=_default_sun_moon_text)
    aspect_pair: Dict[str, str] = field(default_factory=_default_aspect_pair_text)
    angle_sign: Dict[str, str] = field(default_factory=_default_angle_sign_text)
    planet_sign_retro: Dict[str, str] = field(
        default_factory=_default_planet_sign_retro_text)
    house_ruler: Dict[str, str] = field(
        default_factory=_default_house_ruler_text)
    # --- Astro-Clock forecast libraries ---
    forecast_ingress: Dict[str, str] = field(
        default_factory=_default_forecast_ingress_text)
    forecast_station: Dict[str, str] = field(
        default_factory=_default_forecast_station_text)
    forecast_phase: Dict[str, str] = field(
        default_factory=_default_forecast_phase_text)
    sign_forecast: Dict[str, str] = field(
        default_factory=_default_sign_forecast_text)
    forecast_planet_in_sign: Dict[str, str] = field(
        default_factory=_default_forecast_planet_in_sign_text)
    forecast_sign_aspect: Dict[str, str] = field(
        default_factory=_default_forecast_sign_aspect_text)
    forecast_lunation_in_sign: Dict[str, str] = field(
        default_factory=_default_forecast_lunation_in_sign_text)
    forecast_lunation_area: Dict[str, str] = field(
        default_factory=_default_forecast_lunation_area_text)
    eclipse_layer: Dict[str, str] = field(
        default_factory=_default_eclipse_layer)
    transit_natal: Dict[str, str] = field(
        default_factory=_default_transit_natal_text)
    forecast_retrograde: Dict[str, str] = field(
        default_factory=_default_forecast_retrograde_text)
    # --- Forecast narrative wording (period intro/transition/invitation/quiet) ---
    forecast_period_intro: Dict[str, str] = field(
        default_factory=_default_forecast_period_intro_text)
    forecast_transition: Dict[str, str] = field(
        default_factory=_default_forecast_transition_text)
    forecast_invitation: Dict[str, str] = field(
        default_factory=_default_forecast_invitation_text)
    forecast_quiet: Dict[str, str] = field(
        default_factory=_default_forecast_quiet_text)
    # --- Full-chart poetic synthesis libraries ---
    synthesis_section_headings: Dict[str, str] = field(
        default_factory=_default_synthesis_section_headings)
    synthesis_narrative_bridges: Dict[str, str] = field(
        default_factory=_default_synthesis_narrative_bridges)
    planetary_archetypal_imagery: Dict[str, str] = field(
        default_factory=_default_planetary_archetypal_imagery)
    synthesis_strengths: Dict[str, str] = field(
        default_factory=_default_synthesis_strengths)
    synthesis_growth_language: Dict[str, str] = field(
        default_factory=_default_synthesis_growth_language)
    forecast_synthesis: Dict[str, str] = field(
        default_factory=_default_forecast_synthesis)
    synthesis_conclusions: Dict[str, str] = field(
        default_factory=_default_synthesis_conclusions)
    # --- Vedic astrology libraries ---
    nakshatra_text: Dict[str, str] = field(
        default_factory=_default_nakshatra_text)
    dasha_text: Dict[str, str] = field(
        default_factory=_default_dasha_text)
    # --- Vedic plain-English helpers ---
    vedic_glossary: Dict[str, str] = field(
        default_factory=_default_vedic_glossary_text)
    planet_dosha: Dict[str, str] = field(
        default_factory=_default_planet_dosha_text)
    # --- Chinese astrology libraries ---
    chinese_zodiac: Dict[str, str] = field(
        default_factory=_default_chinese_zodiac_text)
    chinese_element: Dict[str, str] = field(
        default_factory=_default_chinese_element_text)
    yin_yang: Dict[str, str] = field(
        default_factory=_default_yin_yang_text)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "InterpretationLibrary":
        """Create a library from loaded JSON, merging with defaults.

        Forecast-only groups (``_FORECAST_MIGRATION_DEFAULTS``) run through
        a targeted migration: a stored value that exactly matches the
        *previously shipped* default for that key is treated as never
        having been customised, so it is quietly upgraded to the new,
        warmer wording. Anything the astrologer actually changed — any
        value that differs from the old shipped text — is preserved as-is.
        """
        library = cls()
        if not isinstance(data, dict):
            return library

        for field_name in ("sign_text", "aspect_text", "planet_role",
                           "sky_aspect_text", "planet_sky_note",
                           "sign_sky_note", "planet_sign", "planet_house",
                           "sun_moon", "aspect_pair", "angle_sign",
                           "planet_sign_retro", "house_ruler",
                           "forecast_ingress",
                           "forecast_station", "forecast_phase",
                           "sign_forecast", "forecast_planet_in_sign",
                           "forecast_sign_aspect", "forecast_lunation_in_sign",
                           "forecast_lunation_area", "eclipse_layer",
                           "transit_natal", "forecast_retrograde", "forecast_period_intro",
                           "forecast_transition", "forecast_invitation",
                           "forecast_quiet", "synthesis_section_headings",
                           "synthesis_narrative_bridges",
                           "planetary_archetypal_imagery",
                           "synthesis_strengths",
                           "synthesis_growth_language",
                           "forecast_synthesis", "synthesis_conclusions",
                           "nakshatra_text", "dasha_text",
                           "vedic_glossary", "planet_dosha",
                           "chinese_zodiac", "chinese_element",
                           "yin_yang"):
            incoming = data.get(field_name)
            if not isinstance(incoming, dict):
                continue
            target = getattr(library, field_name)
            previous_factory = _FORECAST_MIGRATION_DEFAULTS.get(field_name)
            previous = previous_factory() if previous_factory else None
            for key, value in incoming.items():
                if not (isinstance(key, str) and isinstance(value, str)):
                    continue
                if previous is not None and previous.get(key) == value:
                    # Exact old shipped default: let the new default stand.
                    continue
                target[key] = value
        return library

    def to_dict(self) -> dict:
        """Serialize the library to a JSON-compatible mapping."""
        return {
            "sign_text": dict(self.sign_text),
            "aspect_text": dict(self.aspect_text),
            "planet_role": dict(self.planet_role),
            "sky_aspect_text": dict(self.sky_aspect_text),
            "planet_sky_note": dict(self.planet_sky_note),
            "sign_sky_note": dict(self.sign_sky_note),
            "planet_sign": dict(self.planet_sign),
            "planet_house": dict(self.planet_house),
            "sun_moon": dict(self.sun_moon),
            "aspect_pair": dict(self.aspect_pair),
            "angle_sign": dict(self.angle_sign),
            "planet_sign_retro": dict(self.planet_sign_retro),
            "house_ruler": dict(self.house_ruler),
            "forecast_ingress": dict(self.forecast_ingress),
            "forecast_station": dict(self.forecast_station),
            "forecast_phase": dict(self.forecast_phase),
            "sign_forecast": dict(self.sign_forecast),
            "forecast_planet_in_sign": dict(self.forecast_planet_in_sign),
            "forecast_sign_aspect": dict(self.forecast_sign_aspect),
            "forecast_lunation_in_sign": dict(self.forecast_lunation_in_sign),
            "forecast_lunation_area": dict(self.forecast_lunation_area),
            "eclipse_layer": dict(self.eclipse_layer),
            "transit_natal": dict(self.transit_natal),
            "forecast_retrograde": dict(self.forecast_retrograde),
            "forecast_period_intro": dict(self.forecast_period_intro),
            "forecast_transition": dict(self.forecast_transition),
            "forecast_invitation": dict(self.forecast_invitation),
            "forecast_quiet": dict(self.forecast_quiet),
            "synthesis_section_headings": dict(self.synthesis_section_headings),
            "synthesis_narrative_bridges": dict(
                self.synthesis_narrative_bridges),
            "planetary_archetypal_imagery": dict(
                self.planetary_archetypal_imagery),
            "synthesis_strengths": dict(self.synthesis_strengths),
            "synthesis_growth_language": dict(self.synthesis_growth_language),
            "forecast_synthesis": dict(self.forecast_synthesis),
            "synthesis_conclusions": dict(self.synthesis_conclusions),
            "nakshatra_text": dict(self.nakshatra_text),
            "dasha_text": dict(self.dasha_text),
            "vedic_glossary": dict(self.vedic_glossary),
            "planet_dosha": dict(self.planet_dosha),
            "chinese_zodiac": dict(self.chinese_zodiac),
            "chinese_element": dict(self.chinese_element),
            "yin_yang": dict(self.yin_yang),
        }


_DEFAULT_LIBRARY_PATH = os.path.join(
    os.path.expanduser("~"),
    ".astroflow",
    "interpretations.json",
)
_LIBRARY_PATH = _DEFAULT_LIBRARY_PATH
_LIBRARY_CACHE: Optional[InterpretationLibrary] = None


def configure_interpretation_library(path: Optional[str]) -> None:
    """Set the active interpretation JSON file and clear any cached copy."""
    global _LIBRARY_PATH, _LIBRARY_CACHE
    _LIBRARY_PATH = path or _DEFAULT_LIBRARY_PATH
    _LIBRARY_CACHE = None


def interpretation_library_path() -> str:
    """Return the path currently used for the editable interpretation store."""
    return _LIBRARY_PATH


def default_interpretation_library() -> InterpretationLibrary:
    """Return a fresh library populated with AstroFlow's built-in defaults."""
    return InterpretationLibrary()


def load_interpretation_library(path: Optional[str] = None) -> InterpretationLibrary:
    """Load the editable interpretation library from disk.

    If the file does not exist, the built-in defaults are returned.
    """
    global _LIBRARY_CACHE
    active_path = path or _LIBRARY_PATH
    if _LIBRARY_CACHE is not None and active_path == _LIBRARY_PATH:
        return _LIBRARY_CACHE

    if not os.path.exists(active_path):
        library = default_interpretation_library()
        if active_path == _LIBRARY_PATH:
            _LIBRARY_CACHE = library
        return library

    with open(active_path, encoding="utf-8") as handle:
        raw = json.load(handle)
    library = InterpretationLibrary.from_dict(raw)
    if active_path == _LIBRARY_PATH:
        _LIBRARY_CACHE = library
    return library


def save_interpretation_library(
    library: InterpretationLibrary,
    path: Optional[str] = None,
) -> None:
    """Persist a library to disk and refresh the in-memory cache."""
    global _LIBRARY_CACHE
    active_path = path or _LIBRARY_PATH
    folder = os.path.dirname(active_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(active_path, "w", encoding="utf-8") as handle:
        json.dump(library.to_dict(), handle, indent=2, ensure_ascii=True, sort_keys=True)
        handle.write("\n")
    if active_path == _LIBRARY_PATH:
        _LIBRARY_CACHE = library


def ensure_interpretation_library(path: Optional[str] = None) -> str:
    """Create the interpretation file with defaults if it does not exist."""
    active_path = path or _LIBRARY_PATH
    if not os.path.exists(active_path):
        save_interpretation_library(default_interpretation_library(), active_path)
    return active_path
