from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from .models import Snapshot

MINING_XP_COSTS = [
    50, 125, 200, 300, 500, 750, 1_000, 1_500, 2_000, 3_500,
    5_000, 7_500, 10_000, 15_000, 20_000, 30_000, 50_000, 75_000,
    100_000, 200_000, 300_000, 400_000, 500_000, 600_000, 700_000,
    800_000, 900_000, 1_000_000, 1_100_000, 1_200_000, 1_300_000,
    1_400_000, 1_500_000, 1_600_000, 1_700_000, 1_800_000, 1_900_000,
    2_000_000, 2_100_000, 2_200_000, 2_300_000, 2_400_000, 2_500_000,
    2_600_000, 2_750_000, 2_900_000, 3_100_000, 3_400_000, 3_700_000,
    4_000_000, 4_300_000, 4_600_000, 4_900_000, 5_200_000, 5_500_000,
    5_800_000, 6_100_000, 6_400_000, 6_700_000, 7_000_000,
]
HOTM_XP_COSTS = [0, 3_000, 9_000, 25_000, 60_000, 100_000, 150_000, 210_000, 290_000, 400_000]


@dataclass(frozen=True)
class LevelProgress:
    level: int
    next_level: int | None
    remaining: int
    percent: float

    @property
    def remaining_percent(self) -> float:
        return round(100.0 - self.percent, 1) if self.next_level is not None else 0.0


def level_progress(total_xp: float, costs: list[int]) -> LevelProgress:
    remaining_xp = max(0.0, total_xp)
    level = 0
    for cost in costs:
        if remaining_xp < cost:
            percent = 100.0 if cost == 0 else round(remaining_xp / cost * 100, 1)
            return LevelProgress(level, level + 1, round(cost - remaining_xp), percent)
        remaining_xp -= cost
        level += 1
    return LevelProgress(level, None, 0, 100.0)


def level_from_xp(total_xp: float, costs: list[int]) -> int:
    remaining = total_xp
    level = 0
    for cost in costs:
        if remaining < cost:
            break
        remaining -= cost
        level += 1
    return level


def extract_snapshot(account_id: int, member: dict, player: dict) -> Snapshot:
    mining_xp = float(member.get("player_data", {}).get("experience", {}).get("SKILL_MINING", 0))
    hotm_xp = float(member.get("skill_tree", {}).get("experience", {}).get("mining", 0))
    mining = member.get("mining_core", {})
    return Snapshot(
        account_id=account_id,
        observed_at=datetime.now(UTC),
        mining_xp=mining_xp,
        mining_level=level_from_xp(mining_xp, MINING_XP_COSTS),
        hotm_xp=hotm_xp,
        hotm_level=level_from_xp(hotm_xp, HOTM_XP_COSTS),
        commissions=int(player.get("achievements", {}).get("skyblock_hard_working_miner", 0)),
        mithril_powder=int(mining.get("powder_mithril", 0)),
        gemstone_powder=int(mining.get("powder_gemstone", 0)),
        glacite_powder=int(mining.get("powder_glacite", 0)),
        purse=float(member.get("currencies", {}).get("coin_purse", 0)),
        skyblock_level=int(member.get("leveling", {}).get("experience", 0)) // 100,
    )


def is_skyblock_online(session: dict) -> bool:
    return bool(session.get("online")) and session.get("gameType") == "SKYBLOCK"


class HypixelClient:
    def __init__(self, api_key: str):
        self.headers = {"API-Key": api_key, "User-Agent": "skyblock-monitor-bot/0.1"}

    async def resolve_username(self, username: str) -> tuple[str, str]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"https://api.mojang.com/users/profiles/minecraft/{username}")
            response.raise_for_status()
            data = response.json()
            return data["id"], data["name"]

    async def fetch(self, account_id: int, uuid: str, profile_name: str) -> Snapshot:
        async with httpx.AsyncClient(timeout=30, headers=self.headers) as client:
            profiles_response, player_response = await __import__("asyncio").gather(
                client.get("https://api.hypixel.net/v2/skyblock/profiles", params={"uuid": uuid}),
                client.get("https://api.hypixel.net/v2/player", params={"uuid": uuid}),
            )
        profiles_response.raise_for_status()
        player_response.raise_for_status()
        profiles = profiles_response.json().get("profiles") or []
        profile = next((p for p in profiles if p.get("cute_name", "").casefold() == profile_name.casefold()), None)
        if profile is None:
            raise ValueError(f"Profile {profile_name!r} not found")
        member = profile.get("members", {}).get(uuid)
        if member is None:
            raise ValueError("Player is not a member of this profile")
        return extract_snapshot(account_id, member, player_response.json().get("player") or {})

    async def fetch_status(self, uuid: str) -> dict:
        async with httpx.AsyncClient(timeout=20, headers=self.headers) as client:
            response = await client.get("https://api.hypixel.net/v2/status", params={"uuid": uuid})
        response.raise_for_status()
        return response.json().get("session") or {"online": False}
