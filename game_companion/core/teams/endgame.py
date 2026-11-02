"""Encounter-aware endgame planning shared by the JSON API and the web UI.

Keeps the optimizer call sequence in one place so both surfaces produce the
same explanation, labels and honesty warnings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from game_companion.core.games.base import GameAdapter
from game_companion.core.teams.optimizer import optimize_team_allocation
from game_companion.core.teams.scoring import (
    rank_member_keys,
    score_team_composition,
)
from game_companion.db.repositories import EncounterRepository, PlayerRepository
from game_companion.errors import NotFoundError


@dataclass(frozen=True)
class EncounterPlanSpec:
    key: str
    name: str
    description: str
    slot_count: int
    slot_constraints: list[dict[str, Any]]
    source: str  # "adapter" | "saved"


def resolve_encounter(
    session: Session, adapter: GameAdapter, game_id: str, encounter_key: str
) -> EncounterPlanSpec:
    encounter = EncounterRepository(session).find_by_key(game_id, encounter_key)
    if encounter is not None:
        slot_count = max(len(encounter.slots), 1)
        slot_constraints = [slot.constraints or {} for slot in encounter.slots]
        slot_constraints += [{}] * (slot_count - len(slot_constraints))
        return EncounterPlanSpec(
            key=encounter.key,
            name=encounter.name,
            description=str((encounter.data or {}).get("description") or ""),
            slot_count=slot_count,
            slot_constraints=slot_constraints,
            source="saved",
        )

    known = {mode.key: mode for mode in adapter.encounter_modes()}
    mode = known.get(encounter_key)
    if mode is None:
        raise NotFoundError(
            f"unknown encounter '{encounter_key}' (use a saved encounter or one of: "
            f"{', '.join(sorted(known)) or 'this game has no encounter modes yet'})"
        )
    return EncounterPlanSpec(
        key=mode.key,
        name=mode.name,
        description=mode.description,
        slot_count=mode.slot_count,
        slot_constraints=[{} for _ in range(mode.slot_count)],
        source="adapter",
    )


def _allocation_dict(allocation) -> dict | None:
    if allocation is None:
        return None
    return {"total": allocation.total, "teams": allocation.teams}


def plan_encounter(
    session: Session,
    adapter: GameAdapter,
    game_id: str,
    player_id: str,
    encounter_key: str,
    *,
    objective: str = "maximize_total",
    comfort_weight: float = 0.0,
    max_roster: int = 15,
) -> dict[str, Any]:
    """Optimize distinct teams for every slot in an encounter.

    All scores stay explicitly heuristic. The caller (API/UI) must display the
    ``score_warning`` alongside the teams.
    """
    spec = resolve_encounter(session, adapter, game_id, encounter_key)
    roster = rank_member_keys(
        session, adapter, game_id, player_id, limit=max_roster
    )
    team_size = adapter.team_rules().max_size
    preferences = {
        p.key: p.value
        for p in PlayerRepository(session).list_preferences(player_id)
        if p.scope in ("global", game_id)
    }
    if objective == "maximize_comfort" and comfort_weight == 0.0:
        comfort_weight = 1.5

    def team_score_fn(members, slot_index: int):
        scored = score_team_composition(
            session,
            adapter,
            game_id,
            player_id,
            members,
            encounter_constraints=spec.slot_constraints[slot_index],
            preferences=preferences,
            comfort_weight=comfort_weight,
        )
        total = scored["total"]
        if objective == "maximize_clears":
            # Once a slot is strong enough to likely clear, extra strength there
            # is worth nothing to this objective — push the surplus to weak slots.
            total = min(total, 7.0)
        return total, scored["components"]

    result = optimize_team_allocation(
        roster, spec.slot_count, team_size, team_score_fn, max_roster=min(len(roster), max_roster)
    )
    return {
        "encounter_key": spec.key,
        "encounter_name": spec.name,
        "encounter_description": spec.description,
        "encounter_source": spec.source,
        "slot_count": spec.slot_count,
        "team_size": team_size,
        "objective": objective,
        "feasible": result.feasible,
        "best": _allocation_dict(result.best) if result.best else None,
        "alternatives": [_allocation_dict(allocation) for allocation in result.alternatives],
        "greedy_comparison": _allocation_dict(result.greedy) if result.greedy else None,
        "explanation": result.explanation,
        "score_warning": (
            "All slot scores are labeled HEURISTIC components (synergy, encounter fit, "
            "build readiness, comfort). No DPS simulation exists; totals are relative "
            "only, and never percentages of real damage."
        ),
        "notes": [
            f"evaluated {result.evaluated_team_combos} team-slot combinations",
        ],
    }


__all__ = ["EncounterPlanSpec", "plan_encounter", "resolve_encounter"]
