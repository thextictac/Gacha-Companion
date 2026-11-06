"""ZZZ gear rules: Drive Disc slots, main-stat pools, heuristic scoring."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from game_companion.core.games.base import (
    GEAR_VERDICTS,
    LABEL_HEURISTIC,
    GearEvaluation,
    GearSlotDefinition,
    ScoreComponent,
)

# Slot main-stat pools are a VERIFIED MECHANIC (v3.2): slots 1-3 are fixed
# (flat HP / ATK / DEF); slot 4 can roll CRIT stats; slot 5 carries elemental
# damage bonuses; slot 6 carries utility mains. Elemental list includes
# wind_dmg, seen in Prydwen build data (3.2) — flagged UNKNOWN-NEEDS DATA
# until corroborated in-game.
GEAR_SLOTS = [
    GearSlotDefinition(key="1", name="Slot 1", main_stat_pool=("hp",)),
    GearSlotDefinition(key="2", name="Slot 2", main_stat_pool=("atk",)),
    GearSlotDefinition(key="3", name="Slot 3", main_stat_pool=("def",)),
    GearSlotDefinition(
        key="4",
        name="Slot 4",
        main_stat_pool=(
            "hp_pct", "atk_pct", "def_pct", "crit_rate", "crit_dmg", "anomaly_proficiency",
        ),
    ),
    GearSlotDefinition(
        key="5",
        name="Slot 5",
        main_stat_pool=(
            "hp_pct", "atk_pct", "def_pct", "pen_ratio",
            "physical_dmg", "fire_dmg", "ice_dmg", "electric_dmg", "ether_dmg", "wind_dmg",
            "lumiflux_dmg",
        ),
    ),
    GearSlotDefinition(
        key="6",
        name="Slot 6",
        main_stat_pool=(
            "hp_pct", "atk_pct", "def_pct", "anomaly_mastery", "energy_regen", "impact",
        ),
    ),
]

# Slots 1-3 never roll a different main stat: the main is fixed by the slot.
FIXED_SLOT_MAINS = {"1": "hp", "2": "atk", "3": "def"}

# Main-stat values at +15 (max S-rank). Slots 1-3 are player-confirmed; the
# slot 4/5/6 values are the standard in-game maxes (HEURISTIC for now — edit
# this table if a value is wrong, it drives the auto-fill only).
MAIN_STAT_VALUE_AT_15: dict[str, float] = {
    "hp": 2200.0,  # confirmed
    "atk": 316.0,  # confirmed
    "def": 184.0,  # confirmed
    "hp_pct": 0.30,
    "atk_pct": 0.30,
    "def_pct": 0.48,
    "crit_rate": 0.24,
    "crit_dmg": 0.48,
    "anomaly_proficiency": 92.0,
    "anomaly_mastery": 0.30,
    "pen_ratio": 0.24,
    "energy_regen": 0.60,
    "impact": 0.18,
    "physical_dmg": 0.30,
    "fire_dmg": 0.30,
    "ice_dmg": 0.30,
    "electric_dmg": 0.30,
    "ether_dmg": 0.30,
    "wind_dmg": 0.30,
    "lumiflux_dmg": 0.30,
}
_CONFIRMED_MAIN_KEYS = frozenset({"hp", "atk", "def"})


def main_stat_value(main_key: str | None, level: int | None) -> float | None:
    """Auto-fill a main-stat value for a key at a level.

    Only the +15 values are known; other levels scale linearly from 0 (a
    HEURISTIC, so the UI shows it as a suggestion the player can overwrite).
    """
    if not main_key or main_key not in MAIN_STAT_VALUE_AT_15:
        return None
    at_15 = MAIN_STAT_VALUE_AT_15[main_key]
    if level is None:
        return at_15
    if level <= 0:
        return 0.0
    return round(at_15 * min(level, 15) / 15, 4)


def main_stat_value_verified(main_key: str | None, level: int | None) -> bool:
    """True only for the player-confirmed +15 slots 1-3 values."""
    return level == 15 and main_key in _CONFIRMED_MAIN_KEYS


# -- substat shorthand codes -------------------------------------------------
# Canonical order (fixed so a code is always readable the same way). Percent
# stats come first, then flat/utility: CR CD AK HP DF PEN AP AM IM ER AN HN DN.
# * AK/HP/DF are the % versions; P#/AN/HN/DN are the flat ones.
SUBSTAT_CODE_ORDER: tuple[tuple[str, str], ...] = (
    ("crit_rate", "CR"),
    ("crit_dmg", "CD"),
    ("atk_pct", "AK"),
    ("hp_pct", "HP"),
    ("def_pct", "DF"),
    ("pen", "PEN"),
    ("anomaly_proficiency", "AP"),
    ("anomaly_mastery", "AM"),
    ("impact", "IM"),
    ("energy_regen", "ER"),
    ("atk", "AN"),
    ("hp", "HN"),
    ("def", "DN"),
)
CODE_TO_STAT = {code: key for key, code in SUBSTAT_CODE_ORDER}


def substat_code(substats: Sequence[Mapping[str, Any]] | None) -> str:
    """Short sorting code, e.g. ``CR2CD1``.

    One entry per substat that is present on the disc, in canonical order, with
    its roll count (defaults to 1 when the roll count was not recorded). Stats
    that are not present are omitted, keeping codes short and scannable.
    """
    counts = substat_rolls(substats)
    parts = [f"{code}{counts[key]}" for key, code in SUBSTAT_CODE_ORDER if key in counts]
    return "".join(parts)


def _safe_rolls(rolls: Any) -> int:
    """Coerce a stored roll count to a usable positive int.

    Hand-entered JSON is untrusted: it may hold text, floats, nulls, or
    negatives, and a bad value must never take down the gear page.
    """
    if rolls is None:
        return 1
    try:
        count = int(float(rolls))
    except (TypeError, ValueError, OverflowError):
        return 1
    return max(1, count)


def substat_rolls(substats: Sequence[Mapping[str, Any]] | None) -> dict[str, int]:
    """Roll count per substat key, in the disc's own order."""
    counts: dict[str, int] = {}
    for sub in substats or []:
        if not isinstance(sub, Mapping):
            continue
        key = str(sub.get("key") or "")
        if not key:
            continue
        count = _safe_rolls(sub.get("rolls"))
        counts[key] = counts.get(key, 0) + count
    return counts


def total_rolls(substats: Sequence[Mapping[str, Any]] | None) -> int:
    return sum(substat_rolls(substats).values())


DISC_GRADES = ("ZERO", "GOD", "ZZZ", "S", "A", "B", "C", "D", "F")
# Best-to-worst, i.e. how many matching rolls earn each grade. F=0 and each
# further roll moves one step up: D=1, C=2, B=3, A=4, S=5, ZZZ=6, GOD=7,
# ZERO=8+. (``DISC_GRADES`` stays best-first so it also drives sort order.)
GRADE_BY_ROLLS = ("F", "D", "C", "B", "A", "S", "ZZZ", "GOD", "ZERO")


def _grade_for_rolls(rolls: int) -> str:
    return GRADE_BY_ROLLS[min(max(rolls, 0), len(GRADE_BY_ROLLS) - 1)]


# Requirement: the generalized grade should value each drive set for its
# intended purpose. A 2-piece bonus (e.g. "CRIT Rate +8%", "DEF +16%",
# "Energy Regen +20%") tells us what that set is for; rolls that overlap the
# purpose count in full, unrelated rolls count half. This keeps quantity as the
# base signal while nudging purpose-fit discs up (and off-purpose ones down).
SET_PURPOSE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("crit", ("crit rate", "crit dmg")),
    ("anomaly", ("anomaly proficiency", "anomaly mastery")),
    ("physical", ("physical dmg",)),
    ("fire", ("fire dmg",)),
    ("ice", ("ice dmg",)),
    ("electric", ("electric dmg",)),
    ("ether", ("ether dmg",)),
    ("wind", ("wind dmg",)),
    ("lumiflux", ("lumiflux dmg",)),
    ("impact", ("daze", "impact")),
    ("energy", ("energy regen",)),
    ("pen", ("pen ratio", "pen ")),
    ("defense", ("def ", "def+", "shield")),
    ("hp", ("hp ", "hp+")),
    ("atk", ("atk ", "atk+", "basic attack dmg", "dash attack", "aftershock")),
)

_PURPOSE_WEIGHTS: dict[str, dict[str, float]] = {
    "crit": {"crit_rate": 1.0, "crit_dmg": 1.0, "atk_pct": 0.7},
    "anomaly": {"anomaly_proficiency": 1.0, "anomaly_mastery": 1.0, "atk_pct": 0.7},
    "impact": {"impact": 1.0, "energy_regen": 0.8, "crit_rate": 0.5},
    "energy": {"energy_regen": 1.0, "anomaly_proficiency": 0.6, "hp_pct": 0.5},
    "pen": {"pen": 1.0, "pen_ratio": 1.0, "atk_pct": 0.6},
    "defense": {"def_pct": 1.0, "def": 1.0, "hp_pct": 0.7},
    "hp": {"hp_pct": 1.0, "hp": 1.0, "def_pct": 0.6},
    "atk": {"atk_pct": 1.0, "atk": 1.0, "crit_rate": 0.8, "crit_dmg": 0.8},
}
for _element in ("physical", "fire", "ice", "electric", "ether", "wind", "lumiflux"):
    _PURPOSE_WEIGHTS[_element] = {
        f"{_element}_dmg": 1.0, "atk_pct": 0.6, "pen_ratio": 0.5,
    }
# Off-purpose rolls still count, just at a discount.
_OFF_PURPOSE_WEIGHT = 0.5


def set_purpose(piece_two: str | None) -> str | None:
    """Classify a drive set from its 2-piece bonus text (None when unknown)."""
    text = (piece_two or "").strip().lower()
    if not text:
        return None
    for purpose, keywords in SET_PURPOSE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return purpose
    return None


def purpose_substat_weight(purpose: str | None, stat_key: str) -> float:
    """Multiplier for one substat's rolls given the set's intended purpose."""
    if not purpose:
        return 1.0
    weights = _PURPOSE_WEIGHTS.get(purpose)
    if not weights:
        return 1.0
    return weights.get(stat_key, _OFF_PURPOSE_WEIGHT)


def disc_grade(
    gear: Mapping[str, Any],
    *,
    set_bonus_two: str | None = None,
) -> dict[str, Any]:
    """Grade a disc by how many substat rolls it landed.

    F=0, D=1, C=2, B=3, A=4, S=5, ZZZ=6, GOD=7, ZERO=8+. Uses recorded roll
    counts (each substat defaults to 1 roll when not recorded), so a disc with
    four substats and no upgrade rolls is ``A``.

    When the set's 2-piece bonus is supplied, rolls are weighted by how well
    they match the set's purpose (e.g. CRIT on an Attack set, DEF on a
    Defensive set), so an on-purpose disc grades higher than a mismatched one
    with the same roll count.
    """
    counts = substat_rolls(gear.get("substats"))
    purpose = set_purpose(set_bonus_two)
    if not purpose:
        rolls = sum(counts.values())
        return {"grade": _grade_for_rolls(rolls), "rolls": rolls}
    weighted = sum(
        count * purpose_substat_weight(purpose, key) for key, count in counts.items()
    )
    rolls = int(round(weighted))
    return {"grade": _grade_for_rolls(rolls), "rolls": rolls, "set_purpose": purpose}


def priority_grade(
    gear: Mapping[str, Any],
    priority_keys: Sequence[str] | None,
) -> dict[str, Any]:
    """Build-aware grade: only substats the build wants count, plus the main.

    Requirement: the same disc can be ZERO for one agent and F for another.
    Rolls on substats outside the priority list do not count; a main stat the
    build wants adds one effective roll. With no priority list this degrades to
    the generalized :func:`disc_grade`.
    """
    if not priority_keys:
        return disc_grade(gear)
    wanted = {str(key) for key in priority_keys if key}
    counts = substat_rolls(gear.get("substats"))
    matching = {key: count for key, count in counts.items() if key in wanted}
    rolls = sum(matching.values())
    main_key = gear.get("main_stat_key")
    main_matches = bool(main_key and main_key in wanted)
    if main_matches:
        rolls += 1
    return {
        "grade": _grade_for_rolls(rolls),
        "rolls": rolls,
        "matching_substats": matching,
        "main_matches": main_matches,
    }


# Approximate reference maxima used ONLY to normalize the heuristic score.
# These are not verified game constants; they just scale substat contributions.
SUBSTAT_REFERENCE_MAX: dict[str, float] = {
    "crit_rate": 0.24,
    "crit_dmg": 0.48,
    "atk_pct": 0.30,
    "hp_pct": 0.30,
    "def_pct": 0.48,
    "pen": 9.0,  # flat PEN substat roll value
    "pen_ratio": 0.24,
    "energy_regen": 0.60,
    "anomaly_proficiency": 12.0,
    "anomaly_mastery": 0.30,
    "atk": 30.0,
    "hp": 112.0,
    "def": 15.0,
    "impact": 0.18,
}

# Elemental DMG mains (slot V). They share one usefulness band per archetype;
# listing them keeps a correct element from being scored as "not valued".
_ELEMENTAL_DMG_KEYS = (
    "physical_dmg", "fire_dmg", "ice_dmg", "electric_dmg", "ether_dmg",
    "wind_dmg", "lumiflux_dmg",
)

ARCHETYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "attack": {
        "crit_rate": 0.28, "crit_dmg": 0.28, "atk_pct": 0.22,
        "pen_ratio": 0.12, "pen": 0.10, "atk": 0.10,
        **{key: 0.18 for key in _ELEMENTAL_DMG_KEYS},
    },
    "anomaly": {
        "anomaly_proficiency": 0.35,
        "anomaly_mastery": 0.20,
        "atk_pct": 0.20,
        "pen_ratio": 0.10,
        "pen": 0.08,
        "energy_regen": 0.15,
        **{key: 0.15 for key in _ELEMENTAL_DMG_KEYS},
    },
    "stun": {"impact": 0.40, "energy_regen": 0.20, "crit_rate": 0.15, "def_pct": 0.15, "hp_pct": 0.10},
    "support": {
        "energy_regen": 0.30,
        "anomaly_proficiency": 0.25,
        "hp_pct": 0.15,
        "def_pct": 0.15,
        "atk_pct": 0.10,
        "crit_rate": 0.05,
    },
    "defense": {"hp_pct": 0.30, "def_pct": 0.30, "impact": 0.15, "energy_regen": 0.15, "crit_rate": 0.10},
}


def _iter_substat_values(
    substats: Sequence[Mapping[str, Any]] | None,
) -> Iterator[tuple[str, float]]:
    """Yield ``(key, value)`` for usable substats, skipping malformed entries.

    Stored JSON is player-entered, so entries may be null, non-object, missing a
    key, or carry a non-numeric value. Grading must never 500 the page on such
    a row: unusable entries are simply ignored.
    """
    for sub in substats or []:
        if not isinstance(sub, Mapping):
            continue
        key = sub.get("key")
        if not key:
            continue
        raw = sub.get("value")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        yield str(key), value


def _archetype_score(
    gear: Mapping[str, Any], specialty: str, reasons: list[str]
) -> tuple[float, float, list[str]]:
    """Returns (score_0_100, main_fit, sub_notes) scored against one archetype."""
    weights = ARCHETYPE_WEIGHTS.get(specialty, ARCHETYPE_WEIGHTS["attack"])
    main_stat_key = gear.get("main_stat_key")
    main_fit = 0.0
    local_reasons: list[str] = []
    if main_stat_key:
        if main_stat_key in weights and weights[main_stat_key] >= 0.15:
            main_fit = 1.0
            local_reasons.append(
                f"main stat {main_stat_key} is a top desire for the {specialty} archetype"
            )
        elif main_stat_key in weights:
            main_fit = 0.6
            local_reasons.append(f"main stat {main_stat_key} is usable for the {specialty} archetype")
        else:
            local_reasons.append(f"main stat {main_stat_key} is not valued for the {specialty} archetype")
    else:
        local_reasons.append("main stat unknown")

    sub_score = 0.0
    sub_notes: list[str] = []
    for key, value in _iter_substat_values(gear.get("substats")):
        weight = weights.get(key, 0.0)
        ref_max = SUBSTAT_REFERENCE_MAX.get(key)
        if weight <= 0 or not ref_max:
            sub_notes.append(f"{key} not weighted for {specialty}")
            continue
        sub_score += weight * min(value / ref_max, 1.0)
        sub_notes.append(f"{key} {value:g}")
    score = 100 * (0.45 * main_fit + 0.55 * min(sub_score, 1.0))
    return score, main_fit, local_reasons + (["substats considered: " + ", ".join(sub_notes)] if sub_notes else [])


def score_gear(gear: Mapping[str, Any], context: Mapping[str, Any], meta_lookup) -> GearEvaluation:
    """Heuristic Drive Disc evaluation with explicit reasons (never a black box).

    If the caller names a character/specialty, the disc is scored for that
    archetype. Otherwise it is scored against its BEST-fit archetype; when that
    best fit is an archetype the player does not own, the verdict becomes
    ``speculative`` (good piece, wrong roster).
    """
    gear = dict(gear)
    character_key = context.get("character_key")
    meta = (meta_lookup(character_key) if character_key else None) or {}
    explicit_specialty = context.get("specialty") or meta.get("specialty")
    owned_specialties = context.get("owned_specialties")

    if explicit_specialty:
        score, main_fit, reasons = _archetype_score(gear, explicit_specialty, [])
        specialty = explicit_specialty
    else:
        scored_archetypes = {
            name: _archetype_score(gear, name, [])[0] for name in ARCHETYPE_WEIGHTS
        }
        specialty = max(sorted(scored_archetypes), key=lambda k: scored_archetypes[k])
        score, main_fit, reasons = _archetype_score(gear, specialty, [])
        reasons.append(f"no target character given — scored against best-fit archetype '{specialty}'")

    verdict: str | None = None
    if not explicit_specialty and isinstance(owned_specialties, list) and owned_specialties:
        if specialty not in owned_specialties and score >= 40:
            verdict = "speculative"
            reasons.append(
                f"good rolls for {specialty}, but you own no {specialty}-archetype character yet"
            )
    score = round(score, 1)

    if verdict is None:
        if score >= 75:
            verdict = "strong"
        elif score >= 55:
            verdict = "useful"
        elif score >= 40:
            verdict = "niche"
        elif score <= 18:
            verdict = "likely_safe_to_discard"
        else:
            verdict = "weak"

    components = [
        ScoreComponent("main_stat_fit", main_fit, 1, LABEL_HEURISTIC),
        ScoreComponent("desired_substats", min(_subscore(gear, specialty), 1.0), 1, LABEL_HEURISTIC),
    ]
    return GearEvaluation(
        verdict=verdict if verdict in GEAR_VERDICTS else "useful",
        score=float(score),
        reasons=[r for r in reasons if r],
        components=components,
    )


def _subscore(gear: Mapping[str, Any], specialty: str) -> float:
    weights = ARCHETYPE_WEIGHTS.get(specialty, ARCHETYPE_WEIGHTS["attack"])
    total = 0.0
    for key, value in _iter_substat_values(gear.get("substats")):
        ref_max = SUBSTAT_REFERENCE_MAX.get(key)
        if not ref_max:
            continue
        total += weights.get(key, 0.0) * min(value / ref_max, 1.0)
    return total


def set_bonuses_summary(sets: list[dict], gear: Mapping[str, Any]) -> str:
    """Human hint about which sets a disc belongs to (no fabricated effects)."""
    return gear.get("set_key") or "unknown-set"
