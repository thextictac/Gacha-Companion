"""New gear and progression rules: grades, shorthand codes, mains, rolls,
PEN, Lumiflux, Mindscape skill caps, and Core Skill letter I/O."""

from __future__ import annotations

from game_companion.core.games.registry import get_adapter
from game_companion.games.zzz import gear_rules
from game_companion.games.zzz.stats import SKILL_DEFINITIONS


def _by_key(key):
    return next(d for d in SKILL_DEFINITIONS if d.key == key)


# -- PEN / Lumiflux stat coverage -------------------------------------------


def test_pen_is_flat_and_pen_ratio_is_a_separate_percent_stat():
    adapter = get_adapter("zzz")
    stats = {s.key: s for s in adapter.stat_definitions()}
    assert stats["pen"].kind == "flat"
    assert stats["pen_ratio"].kind == "percent"
    substats = adapter.substat_stat_keys() or []
    assert "pen_ratio" not in substats
    assert "pen" in substats


def test_lumiflux_damage_is_a_slot_5_main():
    slot_5 = next(s for s in gear_rules.GEAR_SLOTS if s.key == "5")
    assert "lumiflux_dmg" in slot_5.main_stat_pool


# -- main stats --------------------------------------------------------------


def test_fixed_main_stats_for_slots_1_to_3():
    adapter = get_adapter("zzz")
    assert adapter.fixed_main_stat("1") == "hp"
    assert adapter.fixed_main_stat("2") == "atk"
    assert adapter.fixed_main_stat("3") == "def"
    assert adapter.fixed_main_stat("4") is None


def test_main_stat_value_scales_from_confirmed_plus15_values():
    assert gear_rules.main_stat_value("hp", 15) == 2200.0
    assert gear_rules.main_stat_value("atk", 15) == 316.0
    assert gear_rules.main_stat_value("def", 15) == 184.0
    assert gear_rules.main_stat_value("atk", 0) == 0.0
    at_15 = gear_rules.main_stat_value("atk", 15)
    at_7 = gear_rules.main_stat_value("atk", 7)
    assert at_15 is not None and at_7 is not None and at_15 > at_7
    assert gear_rules.main_stat_value("nope", 15) is None


# -- rolls, codess, grading --------------------------------------------------


def _disc(substats, **extra):
    return {"slot": "5", "main_stat_key": "atk_pct", "substats": substats, **extra}


def test_substat_rolls_default_to_one_and_sum():
    subs: list[dict] = [{"key": "crit_rate", "value": 2.4}, {"key": "crit_rate", "value": 4.8}]
    assert gear_rules.substat_rolls(subs) == {"crit_rate": 2}


def test_substat_code_uses_canonical_order_and_roll_counts():
    subs: list[dict] = [
        {"key": "crit_dmg", "value": 9.6, "rolls": 2},
        {"key": "crit_rate", "value": 4.8, "rolls": 1},
    ]
    assert gear_rules.substat_code(subs) == "CR1CD2"


def test_disc_grade_maps_roll_count_to_band():
    assert gear_rules.disc_grade(_disc([]))["grade"] == "F"
    assert gear_rules.disc_grade(_disc([{"key": "crit_rate", "value": 2.4}]))["grade"] == "D"
    four = [{"key": "atk_pct", "value": 3.0, "rolls": 4}]
    assert gear_rules.disc_grade(_disc(four))["grade"] == "A"
    zero = [{"key": "atk_pct", "value": 9.0, "rolls": 8}]
    assert gear_rules.disc_grade(_disc(zero))["grade"] == "ZERO"


def test_priority_grade_ignores_unwanted_substats():
    subs: list[dict] = [
        {"key": "crit_rate", "value": 4.8, "rolls": 3},
        {"key": "hp", "value": 500, "rolls": 5},
    ]
    # Wants CR only: 3 rolls count, the 5 hp rolls do not. Main (atk_pct) also
    # not wanted, so no main bonus → B.
    result = gear_rules.priority_grade(_disc(subs), ["crit_rate"])
    assert result["matching_substats"] == {"crit_rate": 3}
    assert result["main_matches"] is False
    assert result["grade"] == "B"


def test_priority_grade_counts_matching_main():
    subs: list[dict] = [{"key": "crit_rate", "value": 4.8, "rolls": 2}]
    result = gear_rules.priority_grade(_disc(subs), ["atk_pct"])
    assert result["main_matches"] is True
    assert result["rolls"] == 1  # only the main; the CR was not wanted
    assert result["grade"] == "D"


# -- set-purpose aware generalized grade ------------------------------------


def test_set_purpose_reads_two_piece_bonus():
    assert gear_rules.set_purpose("CRIT Rate +8%.") == "crit"
    assert gear_rules.set_purpose("DEF +16%") == "defense"
    assert gear_rules.set_purpose("Energy Regen +20%.") == "energy"
    assert gear_rules.set_purpose("Ether DMG +10%.") == "ether"
    assert gear_rules.set_purpose("") is None
    assert gear_rules.set_purpose(None) is None


def test_generalized_grade_values_the_sets_intended_purpose():
    # Same rolls, different set purpose: CRIT rolls fit a CRIT set fully but
    # are discounted on a DEF set, so the on-purpose disc grades higher.
    subs: list[dict] = [{"key": "crit_rate", "value": 4.8, "rolls": 4}]
    on_purpose = gear_rules.disc_grade(_disc(subs), set_bonus_two="CRIT Rate +8%.")
    off_purpose = gear_rules.disc_grade(_disc(subs), set_bonus_two="DEF +16%")
    assert on_purpose["grade"] == "A"
    assert on_purpose["rolls"] == 4
    assert off_purpose["rolls"] == 2
    assert off_purpose["set_purpose"] == "defense"


def test_adapter_uses_set_bonus_only_for_generalized_grade():
    # The adapter looks up its data set's 2-piece bonus by set key, and a
    # build-aware (priority) grade stays untouched by set purpose.
    gear = _disc([{"key": "crit_rate", "value": 4.8, "rolls": 4}], set_key="woodpecker_electro")
    adapter = get_adapter("zzz")
    generalized = adapter.disc_grade(gear)
    assert generalized is not None
    assert generalized["rolls"] == 4
    assert generalized.get("set_purpose") == "crit"
    build_aware = adapter.disc_grade(gear, ["crit_rate"])
    assert build_aware is not None
    assert build_aware["matching_substats"] == {"crit_rate": 4}
    assert "set_purpose" not in build_aware


# -- skill progressions -----------------------------------------------------


def test_mindscape_raises_combat_skill_cap_to_16():
    adapter = get_adapter("zzz")
    basic = _by_key("basic_attack")
    assert adapter.skill_max_level(basic, {"duplication_level": 0}) == 12
    assert adapter.skill_max_level(basic, {"duplication_level": 2}) == 12
    assert adapter.skill_max_level(basic, {"duplication_level": 3}) == 14
    assert adapter.skill_max_level(basic, {"duplication_level": 5}) == 16
    assert adapter.skill_max_level(basic, {"duplication_level": 6}) == 16


def test_core_skill_is_untouched_by_mindscape_and_uses_letters():
    adapter = get_adapter("zzz")
    core = _by_key("core_skill")
    assert adapter.skill_max_level(core, {"duplication_level": 6}) == 6
    assert adapter.format_skill_level(core, 1) == "A"
    assert adapter.format_skill_level(core, 6) == "F"
    assert adapter.parse_skill_level(core, "F") == 6
    assert adapter.parse_skill_level(core, "c") == 3
    assert adapter.parse_skill_level(core, "4") == 4
    basic = _by_key("basic_attack")
    assert adapter.parse_skill_level(basic, "12") == 12


# -- data ---------------------------------------------------------------


def test_character_progression_field_lists_potential_vision():
    fields = {f["key"]: f for f in get_adapter("zzz").character_progression_fields()}
    assert "potential_vision" in fields
    assert fields["potential_vision"]["max_level"] == 6
