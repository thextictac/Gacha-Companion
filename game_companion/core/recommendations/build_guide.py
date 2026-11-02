"""Public-source build guides, resolved against a game adapter.

The adapter is the trusted-source boundary: ZZZ already ships Prydwen-derived
agent builds (per-agent set usage, main-stat shares, substat priority and a
comment), HSR/NTE expose only what their starter data has. Nothing here
invents weights — an adapter with no build data simply yields ``None``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from game_companion.core.games.base import GameAdapter


def _stat_names(adapter: GameAdapter) -> dict[str, str]:
    return {stat.key: stat.name for stat in adapter.stat_definitions()}


def _slot_names(adapter: GameAdapter) -> dict[str, str]:
    return {slot.key: slot.name for slot in adapter.gear_slots()}


def _set_names(adapter: GameAdapter) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in adapter.gear_sets():
        if isinstance(row, Mapping) and row.get("key"):
            names[str(row["key"])] = str(row.get("name") or row["key"])
    return names


def _priority_tokens(raw: str) -> list[list[str]]:
    """Turn 'CRIT RATE (until 75%) > ATK% = CRIT DMG' into ordered groups."""
    groups: list[list[str]] = []
    for group in raw.split(">"):
        tokens = [token.strip() for token in group.split("=") if token.strip()]
        if tokens:
            groups.append(tokens)
    return groups


def build_guide(adapter: GameAdapter, character_key: str) -> dict[str, Any] | None:
    """Return a source-labeled build guide for one character, or ``None``.

    The result is presentation-ready but keeps provenance in every field so
    the UI/API never presents a heuristic as verified game math.
    """
    meta = adapter.gear_meta()
    if not isinstance(meta, Mapping):
        return None
    rows = meta.get("agents")
    if not isinstance(rows, list):
        return None
    row = next(
        (item for item in rows if isinstance(item, Mapping) and item.get("key") == character_key),
        None,
    )
    if row is None:
        return None

    stat_names = _stat_names(adapter)
    set_names = _set_names(adapter)
    slot_names = _slot_names(adapter)
    raw_source = meta.get("_meta")
    source_meta: Mapping[str, Any] = raw_source if isinstance(raw_source, Mapping) else {}

    four_piece = []
    for option in row.get("four_piece_families", []) or []:
        if not isinstance(option, Mapping):
            continue
        four_piece.append(
            {
                "key": option.get("set"),
                "name": set_names.get(str(option.get("set")), option.get("set")),
                "usage": option.get("usage_pct"),
            }
        )
    four_piece.sort(key=lambda item: (-(item["usage"] or 0), str(item["key"])))

    two_piece: list[dict[str, Any]] = []
    for group in row.get("two_piece_ranked_raw", []) or []:
        if not isinstance(group, list):
            continue
        for rank, key in enumerate(group, start=1):
            two_piece.append(
                {
                    "key": key,
                    "name": set_names.get(str(key), key),
                    "rank": rank,
                }
            )
    # One entry per set: keep the best (lowest) rank across rank groups.
    best_by_key: dict[str, dict[str, Any]] = {}
    for entry in two_piece:
        key = str(entry["key"])
        if key not in best_by_key or (entry["rank"] or 99) < (best_by_key[key]["rank"] or 99):
            best_by_key[key] = entry
    two_piece = sorted(best_by_key.values(), key=lambda item: item["rank"] or 99)

    main_stats: list[dict[str, Any]] = []
    slot_mains = row.get("slot_mains")
    if isinstance(slot_mains, Mapping):
        for slot, options in slot_mains.items():
            flat: list[str] = []
            for option in options or []:
                if isinstance(option, (list, tuple)):
                    flat.extend(str(item) for item in option)
                elif option is not None:
                    flat.append(str(option))
            seen: set[str] = set()
            for key in flat:
                if key in seen:
                    continue
                seen.add(key)
                main_stats.append(
                    {
                        "slot": str(slot),
                        "slot_name": slot_names.get(str(slot), str(slot)),
                        "stat": key,
                        "stat_name": stat_names.get(key, key),
                    }
                )

    variants = []
    for variant in row.get("build_variants", []) or []:
        if not isinstance(variant, Mapping):
            continue
        variants.append(
            {
                "four_piece": variant.get("four_piece"),
                "four_piece_name": set_names.get(str(variant.get("four_piece")), variant.get("four_piece")),
                "two_piece": variant.get("two_piece"),
                "two_piece_name": set_names.get(str(variant.get("two_piece")), variant.get("two_piece")),
                "q": variant.get("q"),
            }
        )
    variants.sort(key=lambda item: -(item["q"] or 0))

    raw_priority = str(row.get("substat_priority_raw") or "").strip()
    priority_keys = [
        key
        for group in _priority_tokens(raw_priority)
        for key in group
        if key in stat_names
    ]
    priority = [{"key": key, "name": stat_names[key]} for key in priority_keys]

    return {
        "key": row.get("key"),
        "name": row.get("name") or row.get("key"),
        "role": row.get("role"),
        "tier": row.get("tier"),
        "rarity": row.get("rarity"),
        "element": row.get("element"),
        "build_patch": row.get("build_patch"),
        "four_piece": four_piece,
        "two_piece": two_piece,
        "main_stats": main_stats,
        "substat_priority_raw": raw_priority,
        "substat_priority": priority,
        "build_variants": variants,
        "comment": row.get("comment"),
        "source": {
            "label": source_meta.get("label"),
            "source": source_meta.get("source"),
            "source_urls": list(source_meta.get("source_urls") or []),
            "patch": source_meta.get("patch"),
            "retrieved": source_meta.get("retrieved"),
        },
        "labels": {
            "four_piece": "CONSENSUS (published usage shares where given)",
            "two_piece": "CONSENSUS rank order",
            "main_stats": "CONSENSUS main-stat options from published builds",
            "substat_priority": "CONSENSUS priority order — not a stat-cap formula",
        },
    }


__all__ = ["build_guide"]
