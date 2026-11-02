"""Endgame planner, team creation and loadout editing in the standalone UI."""

from __future__ import annotations

from tests.conftest import make_character, make_zzz_roster


def test_team_planner_renders_distinct_endgame_teams(client, ui_player):
    roster = make_zzz_roster(
        client,
        ui_player,
        [
            "burnice", "ellen", "lycaon", "lucy", "anby",
            "soukaku", "koleda", "grace", "qingyi", "rina",
        ],
    )
    page = client.get(
        "/ui/teams?plan=1&encounter=deadly_assault&objective=maximize_total"
    )
    assert page.status_code == 200, page.text
    assert "Deadly Assault" in page.text
    assert "best split" in page.text.lower()
    assert "Team 1" in page.text and "Team 2" in page.text and "Team 3" in page.text
    # The split must use nine distinct names, no character cloned onto two teams.
    team_names = []
    for index in range(3):
        marker = f"Team {index + 1}"
        start = page.text.index(marker)
        section = page.text[start:start + 1600]
        hits = [c["display_name"] for c in roster if c["display_name"] in section]
        team_names.append(set(hits))
    union = set().union(*team_names)
    assert len(union) >= 6
    assert all(len(team) >= 1 for team in team_names)


def test_team_save_and_delete_via_ui(client, ui_player):
    make_zzz_roster(client, ui_player, ["burnice", "ellen", "lycaon"])
    saved = client.post(
        "/ui/teams/save",
        data={
            "name": "UI Team",
            "members": ["burnice", "ellen", "lycaon"],
            "activate": "on",
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    assert "saved" in saved.text.lower()
    teams = client.get("/api/games/zzz/teams").json()["teams"]
    assert len(teams) == 1
    assert teams[0]["name"] == "UI Team"
    assert teams[0]["is_active"] is True

    deleted = client.post(f"/ui/teams/{teams[0]['id']}/delete", follow_redirects=True)
    assert deleted.status_code == 200
    assert client.get("/api/games/zzz/teams").json()["teams"] == []


def test_gear_ui_records_substats_and_edits_them(client, ui_player):
    char = make_character(client, "zzz", "burnice", player_id=ui_player)
    response = client.post(
        "/ui/gear/gear/add",
        data={
            "gear_type": "disc",
            "set_key": "woodpecker_electro",
            "slot": "4",
            "rarity": "S",
            "level": "15",
            "main_stat_key": "crit_rate",
            "main_stat_value": "24%",
            "equipped_character_id": char["id"],
            "substat_key_1": "crit_dmg",
            "substat_value_1": "48%",
            "substat_key_2": "atk_pct",
            "substat_value_2": "9",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Piece added" in response.text
    gear = client.get("/api/games/zzz/gear").json()["gear"]
    assert len(gear) == 1
    item = gear[0]
    assert item["main_stat_value"] == 0.24
    assert {sub["key"] for sub in item["substats"]} == {"crit_dmg", "atk_pct"}
    assert "CRIT DMG" in client.get("/ui/gear").text

    edit = client.get(f"/ui/gear/gear/{item['id']}/edit")
    assert edit.status_code == 200
    assert "Substats" in edit.text and "24" in edit.text

    changed = client.post(
        f"/ui/gear/gear/{item['id']}/edit",
        data={
            "set_key": "woodpecker_electro",
            "slot": "4",
            "rarity": "S",
            "level": "12",
            "main_stat_key": "crit_rate",
            "main_stat_value": "20",
            "substat_key_1": "crit_dmg",
            "substat_value_1": "40",
            "substat_key_2": "",
            "substat_value_2": "",
        },
        follow_redirects=True,
    )
    assert changed.status_code == 200
    updated = client.get(f"/api/games/zzz/gear/{item['id']}").json()
    assert updated["level"] == 12
    assert updated["main_stat_value"] == 0.20
    assert len(updated["substats"]) == 1
    assert updated["equipped_character_id"] is None


def test_character_loadout_creates_active_build(client, ui_player):
    char = make_character(client, "zzz", "burnice", player_id=ui_player)
    equipment = client.post(
        "/api/games/zzz/equipment",
        json={
            "key": "rainforest_gourmet",
            "display_name": "Rainforest Gourmet",
            "rarity": "S",
            "level": 60,
            "character": "burnice",
        },
    ).json()
    disc = client.post(
        "/api/games/zzz/gear",
        json={
            "set_key": "woodpecker_electro",
            "slot": "4",
            "rarity": "S",
            "level": 15,
            "main_stat_key": "crit_rate",
            "main_stat_value": 0.24,
            "substats": [{"key": "crit_dmg", "value": 0.48}],
        },
    ).json()

    equipment_page = client.get(f"/ui/gear/equipment/{equipment['id']}/edit")
    assert equipment_page.status_code == 200
    assert "Rainforest Gourmet" in equipment_page.text
    equipment_saved = client.post(
        f"/ui/gear/equipment/{equipment['id']}/edit",
        data={"display_name": "Rainforest Gourmet", "level": "50", "refinement": "2"},
        follow_redirects=True,
    )
    assert equipment_saved.status_code == 200
    assert client.get(f"/api/games/zzz/equipment/{equipment['id']}").json()["level"] == 50

    guide = client.get("/api/games/zzz/characters/burnice/build-guide").json()
    assert guide["available"] is True
    assert guide["substat_priority_raw"]

    page = client.get("/ui/roster/burnice/edit")
    assert page.status_code == 200
    assert "Current loadout" in page.text
    assert "Build guide" in page.text
    assert "Anomaly Proficiency" in page.text  # Prydwen substat guidance

    saved = client.post(
        "/ui/roster/burnice/loadout",
        data={
            "equipment_item_id": equipment["id"],
            f"slot_{disc['slot']}": disc["id"],
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    assert "Loadout saved" in saved.text

    builds = client.get("/api/games/zzz/characters/burnice/builds").json()["builds"]
    assert len(builds) == 1
    assert builds[0]["is_active"] is True
    assert builds[0]["equipment_item_id"] == equipment["id"]
    assert builds[0]["gear_slots"][disc["slot"]] == disc["id"]
    assert client.get(f"/api/games/zzz/gear/{disc['id']}").json()["equipped_character_id"] == char["id"]


def test_gear_page_compares_crit_builds_with_published_floor(client, ui_player):
    make_character(client, "zzz", "evelyn", player_id=ui_player)
    page = client.get(
        "/ui/gear?cr_a=95&cd_a=105&cr_b=65&cd_b=155&crit_character=evelyn"
    )
    assert page.status_code == 200, page.text
    assert "Build A wins" in page.text
    assert "75%" in page.text
    assert "Published Crit Rate floor" in page.text
