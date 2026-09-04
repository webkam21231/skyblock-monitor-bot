from skyblock_monitor.hypixel import (
    HOTM_XP_COSTS,
    MINING_XP_COSTS,
    extract_snapshot,
    is_skyblock_online,
    level_progress,
)


def test_extracts_stats_without_inventory_or_fuel():
    profile = {
        "leveling": {"experience": 5566},
        "currencies": {"coin_purse": 11_116_978.03},
        "player_data": {"experience": {"SKILL_MINING": 8_008_985.69}},
        "skill_tree": {"experience": {"mining": 77_270}},
        "mining_core": {
            "powder_mithril": 107_628,
            "powder_gemstone": 1_983,
            "powder_glacite": 0,
        },
    }
    player = {"achievements": {"skyblock_hard_working_miner": 130}}

    snapshot = extract_snapshot(4, profile, player)

    assert snapshot.account_id == 4
    assert snapshot.mining_level == 29
    assert snapshot.mining_xp == 8_008_985.69
    assert snapshot.hotm_level == 4
    assert snapshot.hotm_xp == 77_270
    assert snapshot.commissions == 130
    assert snapshot.mithril_powder == 107_628
    assert snapshot.gemstone_powder == 1_983
    assert snapshot.glacite_powder == 0
    assert snapshot.purse == 11_116_978.03
    assert snapshot.skyblock_level == 55


def test_missing_optional_powders_are_zero():
    profile = {
        "leveling": {"experience": 10},
        "currencies": {},
        "player_data": {"experience": {}},
        "skill_tree": {"experience": {}},
        "mining_core": {},
    }
    snapshot = extract_snapshot(1, profile, {"achievements": {}})
    assert snapshot.mithril_powder == 0
    assert snapshot.gemstone_powder == 0
    assert snapshot.glacite_powder == 0


def test_only_skyblock_presence_counts_as_farming_online():
    assert is_skyblock_online({"online": True, "gameType": "SKYBLOCK"}) is True
    assert is_skyblock_online({"online": True, "gameType": "LOBBY"}) is False
    assert is_skyblock_online({"online": False, "gameType": "SKYBLOCK"}) is False


def test_mining_progress_returns_remaining_xp_and_percent():
    progress = level_progress(12_987_654, MINING_XP_COSTS)

    assert progress.level == 33
    assert progress.next_level == 34
    assert progress.remaining == 834_771
    assert progress.percent == 47.8
    assert progress.remaining_percent == 52.2


def test_hotm_progress_returns_remaining_xp_and_percent():
    progress = level_progress(58_765, HOTM_XP_COSTS)

    assert progress.level == 4
    assert progress.next_level == 5
    assert progress.remaining == 38_235
    assert progress.percent == 36.3
