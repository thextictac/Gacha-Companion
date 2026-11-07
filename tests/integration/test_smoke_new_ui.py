def test_gear_page_renders_new_controls(client, ui_player):
    page = client.get("/ui/gear")
    assert page.status_code == 200, page.text
    body = page.text
    assert "Add a" in body
    assert 'name="sort"' in body
    assert 'name="grade_character"' in body
    assert "substat_rolls_1" in body
    assert "GEAR_MAIN_MAX" in body
    assert 'name="need"' in body


def test_gear_page_filters_by_sorting_code(client, ui_player):
    # A token that cannot match any code removes every row from the table.
    page = client.get("/ui/gear", params={"need": "ZZZZ"})
    assert page.status_code == 200, page.text
    assert "likely safe to discard" in page.text
    assert "No drive disc recorded yet" in page.text


def test_character_edit_renders_skill_rows_and_potential(client, ui_player):
    from tests.conftest import make_character
    make_character(client, "zzz", "anby", ui_player)
    characters = client.get("/api/games/zzz/characters").json()["characters"]
    cid = characters[0]["id"]
    page = client.get(f"/ui/roster/{cid}/edit")
    assert page.status_code == 200, page.text
    body = page.text
    assert "Potential Vision" in body
    assert "max 16" in body or "max 12" in body
    assert "Core Skill accepts a letter" in body


def test_character_edit_accepts_core_letter_and_potential(client, ui_player):
    from tests.conftest import make_character
    rec = make_character(client, "zzz", "anby", ui_player)
    cid = rec["id"] if isinstance(rec, dict) and "id" in rec else rec
    page = client.post(
        f"/ui/roster/{cid}/edit",
        data={
            "display_name": "Anby",
            "duplication_level": "5",
            "skill_core_skill": "F",
            "skill_basic_attack": "16",
            "potential_vision": "6",
        },
        follow_redirects=True,
    )
    assert page.status_code == 200, page.text
    chars = client.get("/api/games/zzz/characters").json()["characters"]
    anby = next(c for c in chars if c["id"] == cid)
    assert anby["skills"]["core_skill"] == 6
    assert anby["skills"]["basic_attack"] == 16
    assert anby["data"].get("potential_vision") == "6"


def test_gear_sorts_survive_loosely_typed_rows(client, ui_player):
    """A hand-edited/legacy DB can hold an int where a string belongs (and back).

    Sorting used to raise TypeError from list.sort on the mixed-type key and
    return 500. Every sort option must tolerate it.
    """
    from sqlalchemy import text

    from game_companion.db.session import create_db_engine

    settings = client.app.state.settings
    engine = create_db_engine(settings.resolved_database_url)
    with engine.begin() as session:
        for i, (slot, level, set_key, main_key) in enumerate(
            [
                ("4", 15, "set_a", "crit_rate"),
                (4, "12", 5, 9),
                (None, None, None, None),
            ]
        ):
            session.execute(
                text(
                    "insert or replace into gear_items (id, game_id, player_profile_id,"
                    " set_key, slot, rarity, level, main_stat_key, main_stat_value,"
                    " substats, locked, favorite, data, gear_type, source,"
                    " created_at, updated_at) values (:id, 'zzz', :pid, :set_key,"
                    " :slot, 'S', :level, :main_key, '24', '[]', 0, 0, '{}',"
                    " 'drive_disc', 'manual', datetime('now'), datetime('now'))"
                ),
                {
                    "id": f"mixed{i}",
                    "pid": ui_player,
                    "set_key": set_key,
                    "slot": slot,
                    "level": level,
                    "main_key": main_key,
                },
            )

    for sort in ("slot", "set", "level", "code", "main", "grade"):
        for direction in ("asc", "desc"):
            page = client.get(
                "/ui/gear", params={"sort": sort, "direction": direction}
            )
            assert page.status_code == 200, (sort, direction, page.text[:300])
