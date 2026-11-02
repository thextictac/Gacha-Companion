"""Recommendations, optimizer and tutor routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from game_companion.api.deps import adapter_for, get_db, resolve_player
from game_companion.api.schemas.requests import (
    EquipmentCompareRequest,
    OptimizeRequest,
    TeamRecommendationRequest,
    TutorRequest,
)
from game_companion.core.coaching.tutor import explain as tutor_explain
from game_companion.core.recommendations.gear_eval import evaluate_inventory
from game_companion.core.recommendations.planner import audit_roster, build_upgrade_plan
from game_companion.core.recommendations.team_recs import compare_equipment, recommend_teams
from game_companion.core.roster.service import RosterService
from game_companion.core.teams.endgame import plan_encounter

router = APIRouter(prefix="/games/{game_id}")


@router.post("/recommendations/teams")
def team_recommendations(
    game_id: str,
    payload: TeamRecommendationRequest | None = None,
    session: Session = Depends(get_db),
    player=Depends(resolve_player),
):
    payload = payload or TeamRecommendationRequest()
    return recommend_teams(
        session, adapter_for(game_id), game_id, player.id,
        encounter=payload.encounter, count=payload.count,
    )


@router.post("/recommendations/gear-inventory")
def gear_inventory_evaluation(game_id: str, session: Session = Depends(get_db), player=Depends(resolve_player)):
    return evaluate_inventory(session, adapter_for(game_id), game_id, player.id)


@router.post("/recommendations/plan")
def upgrade_plan(game_id: str, session: Session = Depends(get_db), player=Depends(resolve_player)):
    return build_upgrade_plan(session, adapter_for(game_id), game_id, player.id)


@router.post("/recommendations/audit")
def run_audit(game_id: str, character: str | None = None, session: Session = Depends(get_db), player=Depends(resolve_player)):
    adapter = adapter_for(game_id)
    service = RosterService(session, adapter)
    char = None
    if character:
        char = service.resolve_character(game_id, player.id, character)
    return audit_roster(session, adapter, game_id, player.id, char)


@router.post("/recommendations/equipment-compare")
def equipment_compare(game_id: str, payload: EquipmentCompareRequest | None = None, session: Session = Depends(get_db), player=Depends(resolve_player)):
    payload = payload or EquipmentCompareRequest(character="")
    if not payload.character:
        from game_companion.errors import ValidationError

        raise ValidationError("provide 'character' (key or name) to compare equipment for")
    service = RosterService(session, adapter_for(game_id))
    char = service.resolve_character(game_id, player.id, payload.character)
    return compare_equipment(
        session, adapter_for(game_id), game_id, player.id, char, payload.item_ids
    )


@router.post("/recommendations/optimize")
def optimize(game_id: str, payload: OptimizeRequest | None = None, session: Session = Depends(get_db), player=Depends(resolve_player)):
    payload = payload or OptimizeRequest()
    return plan_encounter(
        session,
        adapter_for(game_id),
        game_id,
        player.id,
        payload.encounter_key,
        objective=payload.objective,
        comfort_weight=payload.comfort_weight,
    )


@router.post("/tutor/explain")
def tutor(game_id: str, payload: TutorRequest, request: Request, session: Session = Depends(get_db), player=Depends(resolve_player)):
    from game_companion.core.persona.store import PersonaStore

    adapter = adapter_for(game_id)
    store = PersonaStore(request.app.state.settings)
    persona = store.get(payload.persona_id) if payload.persona_id else store.get("companion")
    fragment = persona.system_prompt_fragment(
        terminology_line=(
            f"In this game, characters are called '{adapter.terminology().character}', "
            f"weapon-like equipment '{adapter.terminology().equipment}', and gear pieces "
            f"'{adapter.terminology().gear}'."
        )
    )
    return tutor_explain(
        session, adapter, game_id, player.id,
        character_key=payload.character,
        topic=payload.topic,
        mode=payload.mode,
        persona_fragment=fragment,
        llm=request.app.state.llm,
    )
