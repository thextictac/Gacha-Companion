"""ZZZ stat and skill definitions."""

from __future__ import annotations

from game_companion.core.games.base import SkillDefinition, StatDefinition
from game_companion.games.zzz.terminology import SKILL_NAMES

STAT_DEFINITIONS = [
    StatDefinition(key="hp", name="HP", kind="flat"),
    StatDefinition(key="hp_pct", name="HP%", kind="percent"),
    StatDefinition(key="atk", name="ATK", kind="flat"),
    StatDefinition(key="atk_pct", name="ATK%", kind="percent"),
    StatDefinition(key="def", name="DEF", kind="flat"),
    StatDefinition(key="def_pct", name="DEF%", kind="percent"),
    StatDefinition(key="impact", name="Impact", kind="flat"),
    StatDefinition(key="crit_rate", name="CRIT Rate", kind="percent"),
    StatDefinition(key="crit_dmg", name="CRIT DMG", kind="percent"),
    StatDefinition(key="anomaly_proficiency", name="Anomaly Proficiency", kind="flat"),
    StatDefinition(key="anomaly_mastery", name="Anomaly Mastery", kind="percent"),
    # PEN (flat) is the substat ("PEN"), Pen Ratio is the slot-5 percentage
    # main. They are distinct stats in-game; the substat is a flat value.
    StatDefinition(key="pen", name="PEN", kind="flat"),
    StatDefinition(key="pen_ratio", name="Pen Ratio", kind="percent"),
    StatDefinition(key="energy_regen", name="Energy Regen", kind="percent"),
    # Elemental damage mains (slot V only). wind_dmg seen in Prydwen build
    # data (3.2) — UNKNOWN-NEEDS DATA until corroborated in-game.
    StatDefinition(key="physical_dmg", name="Physical DMG", kind="percent"),
    StatDefinition(key="fire_dmg", name="Fire DMG", kind="percent"),
    StatDefinition(key="ice_dmg", name="Ice DMG", kind="percent"),
    StatDefinition(key="electric_dmg", name="Electric DMG", kind="percent"),
    StatDefinition(key="ether_dmg", name="Ether DMG", kind="percent"),
    StatDefinition(key="wind_dmg", name="Wind DMG", kind="percent"),
    StatDefinition(key="lumiflux_dmg", name="Lumiflux DMG", kind="percent"),
]

# Combat skills cap at 12 in-game (Mindscape M3/M5 raise this to 16 per
# character — see ZZZAdapter.skill_max_level). Core Skill is labelled A–F
# in-game, stored here as 1–6 so the letter is a display form, not the value.
SKILL_DEFINITIONS = [
    SkillDefinition(key="basic_attack", name=SKILL_NAMES["basic_attack"], max_level=12),
    SkillDefinition(key="dodge", name=SKILL_NAMES["dodge"], max_level=12),
    SkillDefinition(key="assist", name=SKILL_NAMES["assist"], max_level=12),
    SkillDefinition(key="special_attack", name=SKILL_NAMES["special_attack"], max_level=12),
    SkillDefinition(key="chain_attack", name=SKILL_NAMES["chain_attack"], max_level=12),
    SkillDefinition(
        key="core_skill",
        name=SKILL_NAMES["core_skill"],
        max_level=6,
        max_level_note="Core Skill is displayed A–F; stored as 1–6 (1=A … 6=F)",
    ),
]
