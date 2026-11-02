"""Crit trade-off explanations are transparent and threshold-aware."""

from game_companion.core.recommendations.crit_compare import (
    compare_crit_builds,
    published_crit_floor,
)


def test_published_floor_reads_the_build_guide_wording():
    assert published_crit_floor("CRIT RATE (Until 75% in stat screen) > CRIT DMG") == 75
    assert published_crit_floor("CRIT RATE = CRIT DMG > ATK%") is None


def test_raw_multiplier_prefers_balanced_high_crit_damage():
    result = compare_crit_builds((95, 105), (65, 155))
    assert result["winner"] == "B"
    assert result["a"]["expected_crit_multiplier"] == 1.9975
    assert result["b"]["expected_crit_multiplier"] == 2.0075


def test_floor_beats_raw_multiplier_when_kit_needs_it():
    result = compare_crit_builds(
        (95, 105),
        (65, 155),
        priority_text="CRIT RATE (Until 75% in stat screen) > CRIT DMG",
    )
    assert result["winner"] == "A"
    assert result["floor"] == 75
    assert "meets that floor" in result["reason"]


def test_crit_rate_is_capped_for_the_multiplier():
    result = compare_crit_builds((110, 100), (100, 100))
    assert result["a"]["effective_crit_rate"] == 100
    assert result["a"]["expected_crit_multiplier"] == result["b"]["expected_crit_multiplier"]
    assert result["winner"] == "tie"
