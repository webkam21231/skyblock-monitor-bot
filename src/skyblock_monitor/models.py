from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Account:
    id: int
    telegram_user_id: int
    username: str
    uuid: str
    profile_name: str


@dataclass(frozen=True)
class Snapshot:
    account_id: int
    observed_at: datetime
    mining_xp: float
    mining_level: int
    hotm_xp: float
    hotm_level: int
    commissions: int
    mithril_powder: int
    gemstone_powder: int
    glacite_powder: int
    purse: float
    skyblock_level: int


@dataclass(frozen=True)
class PeriodReport:
    start: Snapshot
    end: Snapshot
    mining_xp: float
    commissions: int
    mithril_powder: int
    gemstone_powder: int
    glacite_powder: int
    purse: float


@dataclass(frozen=True)
class MiningSession:
    id: int
    account_id: int
    started_at: datetime
    ended_at: datetime | None
    offline_since: datetime | None


@dataclass(frozen=True)
class LiveView:
    id: int
    telegram_user_id: int
    chat_id: int
    message_id: int
    account_id: int
    started_at: datetime
