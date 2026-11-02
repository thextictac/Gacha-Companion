"""Public-source build guide resolution keeps provenance intact."""

from game_companion.core.games.registry import get_adapter
from game_companion.core.recommendations.build_guide import build_guide


def test_zzz_build_guide_has_set_stats_priority_and_source():
    guide = build_guide(get_adapter("zzz"), "burnice")
    assert guide is not None
    assert guide["name"] == "Burnice"
    assert guide["four_piece"]
    assert guide["two_piece"]
    assert guide["main_stats"]
    assert "Anomaly Proficiency" in guide["substat_priority_raw"]
    assert guide["source"]["patch"]
    assert guide["source"]["source"].startswith("Prydwen")


def test_build_guide_is_absent_without_data():
    assert build_guide(get_adapter("hsr"), "anyone") is None
