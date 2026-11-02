"""Explain a crit-rate / crit-damage trade-off without faking DPS.

The comparison uses the standard expected-crit multiplier
``1 + min(CR, 100%) * CD`` and, when the character's published build guide
states a crit-rate threshold (e.g. "until 75% in stat screen"), treats that
threshold as a kit/set condition the player may need to satisfy. It never
claims to model ATK, buffs, enemy DEF or rotation damage.
"""

from __future__ import annotations

import re
from typing import Any

_FLOOR_PATTERN = re.compile(
    r"CRIT\s*RATE[^0-9]{0,40}([0-9]{1,3}(?:\.[0-9]+)?)\s*%", re.IGNORECASE
)


def _build(cr: float, cd: float) -> dict[str, Any]:
    effective_cr = min(max(float(cr), 0.0), 100.0)
    effective_cd = max(float(cd), 0.0)
    multiplier = 1.0 + (effective_cr / 100.0) * (effective_cd / 100.0)
    return {
        "crit_rate": effective_cr,
        "crit_dmg": effective_cd,
        "effective_crit_rate": effective_cr,
        "expected_crit_multiplier": round(multiplier, 4),
        "crit_value": round(2 * effective_cr + effective_cd, 2),
        "capped": effective_cr < float(cr),
    }


def published_crit_floor(priority_text: str | None) -> float | None:
    """Extract a stated crit-rate goal from a build guide's priority text.

    This is deliberately literal: a number in parentheses after CRIT RATE,
    e.g. 'CRIT RATE (Until 75% in stat screen)'. No threshold is invented
    when the guide does not state one.
    """
    if not priority_text:
        return None
    for match in _FLOOR_PATTERN.finditer(priority_text):
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if 0 < value <= 100:
            return value
    return None


def compare_crit_builds(
    build_a: tuple[float, float],
    build_b: tuple[float, float],
    *,
    character: str | None = None,
    priority_text: str | None = None,
) -> dict[str, Any]:
    """Compare two (crit rate %, crit dmg %) builds.

    The returned winner is selected by:
    1. published crit-rate floor (if one exists): a build that meets it is
       preferred over one that does not;
    2. otherwise the higher expected crit multiplier;
    3. exact ties are flagged as such.
    """
    a = _build(*build_a)
    b = _build(*build_b)
    floor = published_crit_floor(priority_text)
    a_meets = floor is None or a["effective_crit_rate"] >= floor
    b_meets = floor is None or b["effective_crit_rate"] >= floor

    if floor is not None and a_meets != b_meets:
        winner = "A" if a_meets else "B"
        reason = (
            f"the published build guide asks for at least {floor:g}% Crit Rate; "
            f"build {'A' if a_meets else 'B'} meets that floor and the other does not"
        )
    elif abs(a["expected_crit_multiplier"] - b["expected_crit_multiplier"]) < 0.0001:
        winner = "tie"
        reason = "both builds have the same expected crit multiplier"
    else:
        winner = "A" if a["expected_crit_multiplier"] > b["expected_crit_multiplier"] else "B"
        reason = "no published crit-rate floor applies, so the higher expected crit multiplier wins"

    delta = round(
        (b["expected_crit_multiplier"] - a["expected_crit_multiplier"]) * 100.0, 3
    )
    notes = [
        "Expected crit multiplier ignores ATK, damage bonuses, enemy DEF, buffs and rotation — it is a comparison, not DPS.",
        "Crit Rate is capped at 100% for the multiplier; excess Rate is not credited.",
    ]
    if floor is not None:
        notes.append(
            f"Published crit-rate floor: {floor:g}% (from the character's build guide)."
        )
    if a["capped"] or b["capped"]:
        notes.append("One build exceeds 100% Crit Rate, so the excess is ignored here.")
    return {
        "character": character,
        "floor": floor,
        "a": a,
        "b": b,
        "winner": winner,
        "reason": reason,
        "multiplier_delta_percent_b_minus_a": delta,
        "notes": notes,
    }


__all__ = ["compare_crit_builds", "published_crit_floor"]
