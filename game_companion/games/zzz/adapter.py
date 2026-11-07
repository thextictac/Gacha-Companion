"""The ZZZ GameAdapter: all Zenless Zone Zero specifics live here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import resources
from pathlib import Path
from typing import Any

from game_companion.config import get_settings
from game_companion.core.games.base import (
    LABEL_HEURISTIC,
    EncounterModeDefinition,
    GameAdapter,
    GearEvaluation,
    GearFamily,
    GearSlotDefinition,
    ScoreComponent,
    ScreenshotSpec,
    SkillDefinition,
    SourceDefinition,
    StatDefinition,
    TeamRules,
    Terminology,
)
from game_companion.errors import ValidationError
from game_companion.games.zzz import gear_rules, resource_rules, team_rules
from game_companion.games.zzz import sources as zzz_sources
from game_companion.games.zzz.stats import SKILL_DEFINITIONS, STAT_DEFINITIONS
from game_companion.games.zzz.terminology import ATTRIBUTE_NAMES, SPECIALTY_NAMES
from game_companion.utils import as_list


def _prompt(name: str) -> str:
    return (
        resources.files("game_companion.games.zzz")
        .joinpath("prompts", f"{name}.md")
        .read_text(encoding="utf-8")
    )


class ZZZAdapter(GameAdapter):
    game_id = "zzz"
    display_name = "Zenless Zone Zero"
    version = "1.0.0"

    def __init__(self, data_dir: Path | None = None) -> None:
        base = data_dir or get_settings().resolved_data_dir
        self._overrides_dir = base / "overrides" / "zzz"
        self._requirements = resource_rules.load_data_json(
            "resource_requirements", self._overrides_dir
        )
        self._agents: dict[str, dict] = resource_rules.load_data_json(
            "agents", self._overrides_dir
        ).get("agents", {})
        self._progression = resource_rules.load_data_json("progression", self._overrides_dir)
        self._sets = resource_rules.load_data_json("drive_disc_sets", self._overrides_dir).get(
            "sets", []
        )
        self._gear_families = resource_rules.load_data_json("gear_families", self._overrides_dir).get(
            "families", []
        )
        self._name_index: dict[str, str] = {}
        for key, meta in self._agents.items():
            self._name_index[key] = key
            self._name_index[key.replace("_", " ")] = key
            self._name_index[str(meta.get("name", "")).lower()] = key
        self._team_archetypes: list[dict[str, Any]] | None = None

    # -- identity / terminology ------------------------------------------------

    def terminology(self) -> Terminology:
        return Terminology(
            character="Agent",
            character_plural="Agents",
            equipment="W-Engine",
            equipment_plural="W-Engines",
            gear="Drive Disc",
            gear_plural="Drive Discs",
            duplication="Mindscape",
            special_progression="Core Skill",
        )

    # -- rules -------------------------------------------------------------------

    def team_rules(self) -> TeamRules:
        return team_rules.TEAM_RULES

    def gear_slots(self) -> list[GearSlotDefinition]:
        return gear_rules.GEAR_SLOTS

    def gear_families(self) -> list[GearFamily]:
        families = []
        for family in self._gear_families:
            families.append(
                GearFamily(
                    key=family["key"],
                    display=family.get("display", family["key"]),
                    slot_count=family.get("slot_count", 0),
                    set_rule=family.get("set_rule", "fixed_pieces"),
                    set_sizes=tuple(family.get("set_sizes", ())),
                    rarity_scale=family.get("rarity_scale", "SAB"),
                    max_level=family.get("max_level"),
                    max_substats=family.get("max_substats"),
                    starter_data=family.get("starter_data", False),
                    slots=tuple(
                        GearSlotDefinition(
                            key=slot["key"],
                            name=slot.get("display", slot["key"]),
                            main_stat_pool=tuple(slot.get("main_stat_pool", ())),
                        )
                        for slot in family.get("slots", ())
                    ),
                )
            )
        return families

    def stat_definitions(self) -> list[StatDefinition]:
        return list(STAT_DEFINITIONS)

    def skill_definitions(self) -> list[SkillDefinition]:
        return list(SKILL_DEFINITIONS)

    # -- per-character progression (Mindscape / Potential Vision) -------------

    _CORE_SKILL_KEY = "core_skill"
    _MINDSCAPE_COMBAT_BONUS = {3: 2, 5: 2}  # M3 and M5 each raise combat skills +2
    _CORE_SKILL_LETTERS = "ABCDEF"

    def skill_max_level(
        self,
        definition: SkillDefinition,
        character: Mapping[str, Any] | None = None,
    ) -> int:
        """Combat skills cap at 12, raised to 16 by Mindscape M3 + M5.

        Core Skill keeps its own cap (letters A–F, i.e. six tiers) and is not
        touched by Mindscape.
        """
        base = definition.max_level
        if definition.key == self._CORE_SKILL_KEY or not character:
            return base
        duplication = character.get("duplication_level")
        if duplication is None:
            return base
        try:
            level = int(duplication)
        except (TypeError, ValueError):
            return base
        bonus = sum(add for rank, add in self._MINDSCAPE_COMBAT_BONUS.items() if level >= rank)
        return base + bonus

    def format_skill_level(self, definition: SkillDefinition, level: int | None) -> str:
        if definition.key != self._CORE_SKILL_KEY or level is None:
            return "" if level is None else str(level)
        # Stored 1..6 → A..F. Values outside the band fall back to the number
        # rather than inventing a letter.
        if 1 <= int(level) <= len(self._CORE_SKILL_LETTERS):
            return self._CORE_SKILL_LETTERS[int(level) - 1]
        return str(level)

    def parse_skill_level(self, definition: SkillDefinition, raw: str) -> int | None:
        text = str(raw or "").strip()
        if not text:
            return None
        if definition.key == self._CORE_SKILL_KEY and text.upper() in self._CORE_SKILL_LETTERS:
            return self._CORE_SKILL_LETTERS.index(text.upper()) + 1
        return int(text)

    def character_progression_fields(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "potential_vision",
                "label": "Potential Vision",
                "kind": "int",
                "max_level": 6,
                "help": "1–6; only some Agents support this and it tweaks their kit.",
            },
        ]

    def resource_definitions(self) -> list[resource_rules.ResourceDefinition]:
        return resource_rules.resource_definitions(self._requirements)

    def threshold_config(self) -> resource_rules.ResourceThresholdConfig:
        return resource_rules.THRESHOLD_CONFIG

    def gear_sets(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self._sets]

    # -- gear rules (slots, main stats, grading, shorthand) -------------------

    def substat_stat_keys(self) -> list[str] | None:
        # PEN (flat) is the substat; Pen Ratio is a slot-5 main and must not
        # be offered as a substat choice.
        return [key for key in (stat.key for stat in STAT_DEFINITIONS) if key != "pen_ratio"]

    def fixed_main_stat(self, slot: str | None) -> str | None:
        return gear_rules.FIXED_SLOT_MAINS.get(str(slot)) if slot is not None else None

    def auto_main_stat_value(self, main_key: str | None, level: int | None) -> float | None:
        return gear_rules.main_stat_value(main_key, level)

    def main_stat_max_values(self) -> dict[str, float]:
        return dict(gear_rules.MAIN_STAT_VALUE_AT_15)

    def disc_grade(
        self,
        gear: Mapping[str, Any],
        priority_keys: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        result = gear_rules.priority_grade(gear, priority_keys)
        # The generalized (no-priority) grade also weighs the disc set's
        # intended purpose from its 2-piece bonus, so an on-set-purpose piece
        # ranks above an off-purpose one with the same rolls.
        set_key = gear.get("set_key")
        if not priority_keys and set_key:
            bonus = self._set_piece_two(str(set_key))
            if bonus:
                graded = gear_rules.disc_grade(gear, set_bonus_two=bonus)
                result = {**result, **graded}
        return result

    def _set_piece_two(self, set_key: str) -> str | None:
        for row in self._sets:
            if row.get("key") == set_key:
                return row.get("piece_2")
        return None

    def substat_code(self, substats: Sequence[Mapping[str, Any]] | None) -> str:
        return gear_rules.substat_code([s for s in as_list(substats) if isinstance(s, Mapping)])

    def farm_stages(self) -> list[dict[str, Any]]:
        from game_companion.games.zzz import farm as zzz_farm

        return zzz_farm.load_farm_stages(self._overrides_dir).get("stages", [])

    def gear_meta(self) -> dict[str, Any]:
        from game_companion.games.zzz import farm as zzz_farm

        return zzz_farm.load_drive_meta(self._overrides_dir)

    def grade_gear(self, gear: Mapping[str, Any]) -> dict[str, Any]:
        from game_companion.games.zzz import farm as zzz_farm

        return zzz_farm.grade_disc(gear)

    def build_farm_plan(
        self,
        gear_rows: Sequence[Mapping],
        beta: float = 1.2,
        unit_keys: Sequence[str] | None = None,
    ) -> dict[str, Any] | None:
        from game_companion.games.zzz import farm as zzz_farm

        return zzz_farm.build_farm_plan(self, gear_rows, beta=beta, unit_keys=unit_keys)

    def equipment_rules(self) -> dict[str, Any]:
        return {
            "noun": "W-Engine",
            "refinement_name": "Stars",
            "level_cap": self._progression.get("_wengine_level_cap", {}).get("value", 60),
            "level_cap_verified": self._progression.get("_wengine_level_cap", {}).get(
                "verified", False
            ),
        }

    def progression_rules(self) -> dict[str, Any]:
        return {
            "level_cap": self._progression.get("level_cap", {}),
            "ascension_stages": self._progression.get("ascension_stages", {}),
            "skill_targets": self._progression.get("skill_targets", {}),
            "gear_level_cap": self._progression.get("_drive_disc_level_cap", {}),
        }

    def encounter_modes(self) -> list[EncounterModeDefinition]:
        return [
            EncounterModeDefinition(
                key="shiyu_defense",
                name="Shiyu Defense",
                slot_count=2,
                description="starter data — slot count/constraints may rotate by season",
            ),
            EncounterModeDefinition(
                key="deadly_assault",
                name="Deadly Assault",
                slot_count=3,
                description="starter data — three separate enemy squads, one team per slot",
            ),
        ]

    def source_registry(self) -> list[SourceDefinition]:
        return list(zzz_sources.SOURCES)

    def code_config(self) -> dict[str, Any]:
        return {
            "discovery_source_keys": zzz_sources.CODE_DISCOVERY_SOURCE_KEYS,
            "notes": zzz_sources.CODE_CONFIG_NOTES,
        }

    def theme(self) -> dict[str, str]:
        # palette mirrors the game's menus: near-black neutral + signature red
        # (#ed343e) and stun yellow (#ffc000) as seen in ZZZ's own UI accents
        return {
            "accent": "#ed343e",
            "accent2": "#ffc000",
            "bg": "#0f0f13",
            "bg2": "#1a1a21",
            "card": "#1e1e24",
            "line": "#2d2d35",
            "radius": "10px",
            "mood": "New Eridu after dark",
            "font": "Saira Condensed",
            "logo": "/ui/static/images/logos/zzz.webp",
            "bg_image": "https://cdn.prydwen.gg/images/zenless-zone-zero/website_bg.webp",
            "currency": "Polychrome",
            "currency_colors": "#b16cff,#41d1ff,#e0c8ff,#7a5cff",
            "currency_shape": "image",
            "currency_icon": "/ui/static/images/currency/polychrome.webp",
        }

    def media_url(self, kind: str, key: str, meta: Any = None) -> str | None:
        base = "https://cdn.prydwen.gg/images/zenless-zone-zero"
        slug = key.strip().lower().replace("_", "-")
        if kind == "character":
            return f"{base}/characters/{slug}.webp"
        if kind == "equipment":
            return f"{base}/w-engines/{slug}_image.webp"
        if kind == "gear_set":
            return f"{base}/drives/set_{slug}.webp"
        if kind == "element" and slug in ("physical", "fire", "ice", "electric", "ether"):
            return f"{base}/icons/ele_{slug}.webp"
        return None

    def persona_flavors(self) -> list[dict[str, Any]]:
        return [
            {"id": "hustle_manager", "description": "energetic profit-minded manager vibe"},
            {"id": "calm_tactician", "description": "composed step-by-step instructor vibe"},
        ]

    def tutor_notes(self) -> dict[str, Any]:
        return {
            "controls": (
                "When giving button-by-button ZZZ rotations, use ability names "
                "(Basic Attack, Dodge, Assist/Defensive Assist, Special Attack, "
                "EX Special Attack, Chain Attack, Ultimate, Quick Assist, Switch) "
                "rather than raw platform buttons, and note that inputs vary by platform."
            ),
            "team_size": 3,
        }

    # -- screenshot ingestion ------------------------------------------------------

    def screenshot_specs(self) -> dict[str, ScreenshotSpec]:
        from game_companion.games.zzz import screenshot_schemas as schemas

        return {
            "character_overview": ScreenshotSpec(
                key="character_overview",
                description="Agent overview/attribute screen",
                prompt=_prompt("agent_overview"),
                schema=schemas.AgentOverviewCandidate,
            ),
            "skills": ScreenshotSpec(
                key="skills",
                description="Agent skill levels screen",
                prompt=_prompt("skills"),
                schema=schemas.SkillsCandidate,
            ),
            "equipment": ScreenshotSpec(
                key="equipment",
                description="Equipped W-Engine screen",
                prompt=_prompt("wengine"),
                schema=schemas.WEngineCandidate,
            ),
            "gear_list": ScreenshotSpec(
                key="gear_list",
                description="Drive Disc loadout list screen",
                prompt=_prompt("drive_discs"),
                schema=schemas.DriveDiscListCandidate,
            ),
            "gear_detail": ScreenshotSpec(
                key="gear_detail",
                description="Single Drive Disc detail screen",
                prompt=_prompt("drive_disc_detail"),
                schema=schemas.DriveDiscDetailCandidate,
            ),
            "resources": ScreenshotSpec(
                key="resources",
                description="Inventory/resources screen",
                prompt=_prompt("resources"),
                schema=schemas.ResourcesCandidate,
            ),
        }

    # -- validation / lookup -----------------------------------------------------

    _ALLOWED_DATA_KEYS = {
        "attribute", "specialty", "faction", "nickname", "potential_vision",
    }

    def validate_character_data(self, data: Mapping[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in dict(data).items():
            if key not in self._ALLOWED_DATA_KEYS:
                raise ValidationError(
                    f"unknown ZZZ character data key '{key}' "
                    f"(allowed: {sorted(self._ALLOWED_DATA_KEYS)})"
                )
            if key == "attribute" and value is not None and value not in ATTRIBUTE_NAMES:
                raise ValidationError(
                    f"unknown attribute '{value}' (allowed: {sorted(ATTRIBUTE_NAMES)})"
                )
            if key == "specialty" and value is not None and value not in SPECIALTY_NAMES:
                raise ValidationError(
                    f"unknown specialty '{value}' (allowed: {sorted(SPECIALTY_NAMES)})"
                )
            if key == "potential_vision" and value not in (None, ""):
                try:
                    level = int(value)
                except (TypeError, ValueError):
                    raise ValidationError(
                        f"potential_vision must be a number 1–6 (got '{value}')"
                    ) from None
                if not (1 <= level <= 6):
                    raise ValidationError(f"potential_vision {level} outside 1..6")
                value = str(level)
            cleaned[key] = value
        return cleaned

    def character_field_choices(self) -> dict[str, list[str]]:
        return {
            "attribute": sorted(ATTRIBUTE_NAMES),
            "specialty": sorted(SPECIALTY_NAMES),
        }

    def character_meta(self, key: str) -> dict[str, Any] | None:
        resolved = self._name_index.get(key.lower()) or self._name_index.get(key)
        if resolved is None:
            return None
        meta = self._agents.get(resolved, {})
        return {
            "key": resolved,
            "name": meta.get("name"),
            "rarity": meta.get("rarity"),
            "attribute": meta.get("attribute"),
            "specialty": meta.get("specialty"),
            "faction": meta.get("faction"),
            "starter_data": True,
        }

    def resolve_character_key(self, name: str) -> str | None:
        return self._name_index.get(name.strip().lower())

    # -- scoring hooks (heuristic, explainable) -------------------------------------

    def bootstrap_sources(self) -> dict[str, Any]:
        from game_companion.games.zzz import bootstrap as zzz_bootstrap

        return zzz_bootstrap.BOOTSTRAP_SOURCES

    def bootstrap_transform(self, source_key: str, payload: Any) -> list[dict[str, Any]]:
        from game_companion.games.zzz import bootstrap as zzz_bootstrap

        return zzz_bootstrap.transform(source_key, payload)

    def catalog_sources(self) -> dict[str, Any]:
        from game_companion.games.zzz import catalog as zzz_catalog

        return zzz_catalog.CATALOG_SOURCES

    def catalog_transform(self, source_key: str, payload: Any) -> list[dict[str, Any]]:
        from game_companion.games.zzz import catalog as zzz_catalog

        return zzz_catalog.catalog_transform(source_key, payload)

    def codes_source(self) -> dict[str, Any] | None:
        from game_companion.games.zzz import catalog as zzz_catalog

        return dict(zzz_catalog.CODES_SOURCE)

    def codes_transform(self, payload: Any) -> list[dict[str, Any]]:
        from game_companion.games.zzz import catalog as zzz_catalog

        return zzz_catalog.codes_transform(payload)

    def score_gear(self, gear: Mapping[str, Any], context: Mapping[str, Any]) -> GearEvaluation:
        return gear_rules.score_gear(gear, context, self.character_meta)

    def _meta_teams(self) -> list[dict[str, Any]]:
        if self._team_archetypes is None:
            self._team_archetypes = list(self.gear_meta().get("archetypes") or [])
        return self._team_archetypes

    def score_team(
        self, member_keys: Sequence[str], context: Mapping[str, Any]
    ) -> list[ScoreComponent]:
        return team_rules.score_team(
            member_keys, self.character_meta, context, self._meta_teams()
        )

    def character_slot_fit(
        self, character_key: str, encounter_constraints: Mapping[str, Any]
    ) -> float:
        return team_rules.character_slot_fit(
            character_key, encounter_constraints, self.character_meta
        )


    def score_equipment_for_character(
        self, character_key: str, equipment: Mapping[str, Any]
    ) -> ScoreComponent:
        rarity_score = {"S": 8.0, "A": 5.0, "B": 2.0}.get(str(equipment.get("rarity") or ""), 3.0)
        level_cap = float(self.equipment_rules().get("level_cap") or 60)
        level = equipment.get("level")
        level_score = 1.5 * (float(level) / level_cap) if level else 0.0
        refinement = equipment.get("refinement")
        refinement_score = 0.25 * refinement if refinement else 0.0
        value = min(10.0, rarity_score + level_score + refinement_score)
        detail = (
            f"rarity {equipment.get('rarity') or '?'} base {rarity_score:g}, "
            f"level {level if level is not None else '?'} contributes {level_score:.1f}, "
            f"stars {refinement if refinement is not None else '?'} contributes {refinement_score:.2f}"
        )
        return ScoreComponent("equipment_quality", value, 10, LABEL_HEURISTIC, detail)
