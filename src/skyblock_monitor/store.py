import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Account, PeriodReport, Snapshot


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    telegram_user_id INTEGER NOT NULL,
                    username TEXT NOT NULL COLLATE NOCASE,
                    uuid TEXT NOT NULL,
                    profile_name TEXT NOT NULL COLLATE NOCASE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(telegram_user_id, username, profile_name)
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    observed_at TEXT NOT NULL,
                    mining_xp REAL NOT NULL,
                    mining_level INTEGER NOT NULL,
                    hotm_xp REAL NOT NULL,
                    hotm_level INTEGER NOT NULL,
                    commissions INTEGER NOT NULL,
                    mithril_powder INTEGER NOT NULL,
                    gemstone_powder INTEGER NOT NULL,
                    glacite_powder INTEGER NOT NULL,
                    purse REAL NOT NULL,
                    skyblock_level INTEGER NOT NULL,
                    UNIQUE(account_id, observed_at)
                );
                CREATE INDEX IF NOT EXISTS snapshots_period
                    ON snapshots(account_id, observed_at);
                """
            )

    def add_account(self, telegram_user_id: int, username: str, uuid: str, profile_name: str) -> Account:
        with self._connect() as db:
            db.execute(
                """INSERT INTO accounts(telegram_user_id, username, uuid, profile_name)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(telegram_user_id, username, profile_name)
                   DO UPDATE SET uuid=excluded.uuid, enabled=1""",
                (telegram_user_id, username, uuid, profile_name),
            )
            row = db.execute(
                """SELECT * FROM accounts
                   WHERE telegram_user_id=? AND username=? AND profile_name=?""",
                (telegram_user_id, username, profile_name),
            ).fetchone()
        return self._account(row)

    def list_accounts(self, telegram_user_id: int | None = None) -> list[Account]:
        query = "SELECT * FROM accounts WHERE enabled=1"
        params: tuple[object, ...] = ()
        if telegram_user_id is not None:
            query += " AND telegram_user_id=?"
            params = (telegram_user_id,)
        query += " ORDER BY username COLLATE NOCASE, profile_name COLLATE NOCASE"
        with self._connect() as db:
            return [self._account(row) for row in db.execute(query, params)]

    def get_account(self, account_id: int, telegram_user_id: int) -> Account | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM accounts WHERE id=? AND telegram_user_id=? AND enabled=1",
                (account_id, telegram_user_id),
            ).fetchone()
        return self._account(row) if row else None

    def delete_account(self, account_id: int, telegram_user_id: int) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE accounts SET enabled=0 WHERE id=? AND telegram_user_id=?",
                (account_id, telegram_user_id),
            )

    def save_snapshot(self, snapshot: Snapshot) -> None:
        with self._connect() as db:
            db.execute(
                """INSERT OR REPLACE INTO snapshots(
                    account_id, observed_at, mining_xp, mining_level, hotm_xp, hotm_level,
                    commissions, mithril_powder, gemstone_powder, glacite_powder, purse,
                    skyblock_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot.account_id,
                    snapshot.observed_at.isoformat(),
                    snapshot.mining_xp,
                    snapshot.mining_level,
                    snapshot.hotm_xp,
                    snapshot.hotm_level,
                    snapshot.commissions,
                    snapshot.mithril_powder,
                    snapshot.gemstone_powder,
                    snapshot.glacite_powder,
                    snapshot.purse,
                    snapshot.skyblock_level,
                ),
            )

    def period_report(self, account_id: int, start: datetime, end: datetime) -> PeriodReport | None:
        with self._connect() as db:
            rows = db.execute(
                """SELECT * FROM snapshots
                   WHERE account_id=? AND observed_at BETWEEN ? AND ?
                   ORDER BY observed_at""",
                (account_id, start.isoformat(), end.isoformat()),
            ).fetchall()
        if len(rows) < 2:
            return None
        first, last = self._snapshot(rows[0]), self._snapshot(rows[-1])
        return PeriodReport(
            start=first,
            end=last,
            mining_xp=last.mining_xp - first.mining_xp,
            commissions=last.commissions - first.commissions,
            mithril_powder=last.mithril_powder - first.mithril_powder,
            gemstone_powder=last.gemstone_powder - first.gemstone_powder,
            glacite_powder=last.glacite_powder - first.glacite_powder,
            purse=last.purse - first.purse,
        )

    def latest_snapshot(self, account_id: int) -> Snapshot | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM snapshots WHERE account_id=? ORDER BY observed_at DESC LIMIT 1",
                (account_id,),
            ).fetchone()
        return self._snapshot(row) if row else None

    @staticmethod
    def _account(row: sqlite3.Row) -> Account:
        return Account(row["id"], row["telegram_user_id"], row["username"], row["uuid"], row["profile_name"])

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> Snapshot:
        return Snapshot(
            account_id=row["account_id"],
            observed_at=datetime.fromisoformat(row["observed_at"]),
            mining_xp=row["mining_xp"],
            mining_level=row["mining_level"],
            hotm_xp=row["hotm_xp"],
            hotm_level=row["hotm_level"],
            commissions=row["commissions"],
            mithril_powder=row["mithril_powder"],
            gemstone_powder=row["gemstone_powder"],
            glacite_powder=row["glacite_powder"],
            purse=row["purse"],
            skyblock_level=row["skyblock_level"],
        )
