from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from src.pdf_processing.models import KeyState


class NoAvailableGeminiKeyError(Exception):
    """Raised when every Gemini key is cooling down or quota-exhausted."""


class QuotaRepository(Protocol):
    async def get_key_state(self, key_id: str) -> KeyState: ...

    async def save_key_state(self, state: KeyState) -> None: ...

    async def increment_daily_usage(self, key_id: str, date: str) -> None: ...

    async def increment_minute_usage(self, key_id: str, minute: int) -> None: ...

    async def acquire_available_key(
        self,
        api_keys: dict[str, str],
        *,
        requests_per_minute: int,
        requests_per_day: int,
    ) -> tuple[str, str]: ...


def utc_now_ts() -> float:
    return datetime.now(UTC).timestamp()


def utc_today() -> str:
    return datetime.now(UTC).date().isoformat()


def utc_minute_bucket() -> int:
    return int(utc_now_ts() // 60)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteQuotaRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._init_schema_sync)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def _init_schema_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS key_state (
                    key_id TEXT PRIMARY KEY,
                    cooldown_until REAL,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                    key_id TEXT NOT NULL,
                    usage_date TEXT NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (key_id, usage_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS minute_usage (
                    key_id TEXT NOT NULL,
                    minute_bucket INTEGER NOT NULL,
                    request_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (key_id, minute_bucket)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_state (
                    name TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS key_registry (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    env_name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )

    async def get_key_state(self, key_id: str) -> KeyState:
        await self._ensure_schema()
        return await asyncio.to_thread(self._get_key_state_sync, key_id)

    def _get_key_state_sync(self, key_id: str) -> KeyState:
        today = utc_today()
        minute = utc_minute_bucket()
        with self._connect() as conn:
            state_row = conn.execute(
                "SELECT cooldown_until, last_error, updated_at FROM key_state WHERE key_id = ?",
                (key_id,),
            ).fetchone()
            daily_row = conn.execute(
                "SELECT request_count FROM daily_usage WHERE key_id = ? AND usage_date = ?",
                (key_id, today),
            ).fetchone()
            minute_row = conn.execute(
                "SELECT request_count FROM minute_usage WHERE key_id = ? AND minute_bucket = ?",
                (key_id, minute),
            ).fetchone()

        return KeyState(
            key_id=key_id,
            daily_used=int(daily_row[0]) if daily_row else 0,
            minute_used=int(minute_row[0]) if minute_row else 0,
            cooldown_until=float(state_row[0]) if state_row and state_row[0] is not None else None,
            last_error=str(state_row[1]) if state_row and state_row[1] is not None else None,
            updated_at=str(state_row[2]) if state_row else None,
        )

    async def save_key_state(self, state: KeyState) -> None:
        await self._ensure_schema()
        await asyncio.to_thread(self._save_key_state_sync, state)

    def _save_key_state_sync(self, state: KeyState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO key_state (key_id, cooldown_until, last_error, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key_id) DO UPDATE SET
                    cooldown_until = excluded.cooldown_until,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
                (state.key_id, state.cooldown_until, state.last_error, state.updated_at or utc_now_iso()),
            )

    async def increment_daily_usage(self, key_id: str, date: str) -> None:
        await self._ensure_schema()
        await asyncio.to_thread(self._increment_daily_usage_sync, key_id, date)

    def _increment_daily_usage_sync(self, key_id: str, date: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_usage (key_id, usage_date, request_count)
                VALUES (?, ?, 1)
                ON CONFLICT(key_id, usage_date) DO UPDATE SET
                    request_count = request_count + 1
                """,
                (key_id, date),
            )

    async def increment_minute_usage(self, key_id: str, minute: int) -> None:
        await self._ensure_schema()
        await asyncio.to_thread(self._increment_minute_usage_sync, key_id, minute)

    def _increment_minute_usage_sync(self, key_id: str, minute: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO minute_usage (key_id, minute_bucket, request_count)
                VALUES (?, ?, 1)
                ON CONFLICT(key_id, minute_bucket) DO UPDATE SET
                    request_count = request_count + 1
                """,
                (key_id, minute),
            )

    async def acquire_available_key(
        self,
        api_keys: dict[str, str],
        *,
        requests_per_minute: int,
        requests_per_day: int,
    ) -> tuple[str, str]:
        await self._ensure_schema()
        return await asyncio.to_thread(
            self._acquire_available_key_sync,
            api_keys,
            requests_per_minute,
            requests_per_day,
        )

    def _acquire_available_key_sync(
        self,
        api_keys: dict[str, str],
        requests_per_minute: int,
        requests_per_day: int,
    ) -> tuple[str, str]:
        if not api_keys:
            raise NoAvailableGeminiKeyError("No available Gemini API key: no GEMINI API keys configured")

        env_names = sorted(api_keys)
        today = utc_today()
        minute = utc_minute_bucket()
        now = utc_now_ts()
        blocked: list[str] = []

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._sync_key_registry(conn, env_names)
            ordered_keys = self._active_registered_keys(conn, api_keys)
            if not ordered_keys:
                raise NoAvailableGeminiKeyError("No available Gemini API key: no active GEMINI_KEY entries configured")
            state_row = conn.execute(
                "SELECT value FROM scheduler_state WHERE name = ?",
                ("gemini_round_robin_last_key",),
            ).fetchone()
            last_registry_id = _parse_registry_id(state_row[0]) if state_row and state_row[0] else None
            start_index = _next_registry_index([registry_id for registry_id, _key_id, _api_key in ordered_keys], last_registry_id)

            for offset in range(len(ordered_keys)):
                registry_id, key_id, api_key = ordered_keys[(start_index + offset) % len(ordered_keys)]
                key_state = conn.execute(
                    "SELECT cooldown_until FROM key_state WHERE key_id = ?",
                    (key_id,),
                ).fetchone()
                cooldown_until = float(key_state[0]) if key_state and key_state[0] is not None else None
                if cooldown_until and cooldown_until > now:
                    blocked.append(f"{key_id}: cooling down")
                    continue

                daily_row = conn.execute(
                    "SELECT request_count FROM daily_usage WHERE key_id = ? AND usage_date = ?",
                    (key_id, today),
                ).fetchone()
                daily_used = int(daily_row[0]) if daily_row else 0
                if daily_used >= requests_per_day:
                    blocked.append(f"{key_id}: daily quota exhausted")
                    continue

                minute_row = conn.execute(
                    "SELECT request_count FROM minute_usage WHERE key_id = ? AND minute_bucket = ?",
                    (key_id, minute),
                ).fetchone()
                minute_used = int(minute_row[0]) if minute_row else 0
                if minute_used >= requests_per_minute:
                    blocked.append(f"{key_id}: minute quota exhausted")
                    continue

                conn.execute(
                    """
                    INSERT INTO daily_usage (key_id, usage_date, request_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(key_id, usage_date) DO UPDATE SET
                        request_count = request_count + 1
                    """,
                    (key_id, today),
                )
                conn.execute(
                    """
                    INSERT INTO minute_usage (key_id, minute_bucket, request_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(key_id, minute_bucket) DO UPDATE SET
                        request_count = request_count + 1
                    """,
                    (key_id, minute),
                )
                conn.execute(
                    """
                    INSERT INTO scheduler_state (name, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    ("gemini_round_robin_last_key", str(registry_id), utc_now_iso()),
                )
                return key_id, api_key

        detail = "; ".join(blocked) if blocked else "no GEMINI API keys configured"
        raise NoAvailableGeminiKeyError(f"No available Gemini API key: {detail}")

    def _sync_key_registry(self, conn: sqlite3.Connection, env_names: list[str]) -> None:
        now = utc_now_iso()
        conn.execute("UPDATE key_registry SET active = 0, last_seen_at = ?", (now,))
        for env_name in env_names:
            conn.execute(
                """
                INSERT INTO key_registry (env_name, display_name, active, first_seen_at, last_seen_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(env_name) DO UPDATE SET
                    display_name = excluded.display_name,
                    active = 1,
                    last_seen_at = excluded.last_seen_at
                """,
                (env_name, env_name, now, now),
            )

    def _active_registered_keys(
        self,
        conn: sqlite3.Connection,
        api_keys: dict[str, str],
    ) -> list[tuple[int, str, str]]:
        rows = conn.execute(
            """
            SELECT key_id, env_name
            FROM key_registry
            WHERE active = 1
            ORDER BY key_id ASC
            """
        ).fetchall()
        return [
            (int(key_id), str(env_name), api_keys[str(env_name)])
            for key_id, env_name in rows
            if str(env_name) in api_keys
        ]


class GeminiKeyScheduler:
    def __init__(
        self,
        repository: QuotaRepository,
        *,
        requests_per_minute: int,
        requests_per_day: int,
    ) -> None:
        self.repository = repository
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day

    async def acquire_key(self, api_keys: dict[str, str]) -> tuple[str, str]:
        return await self.repository.acquire_available_key(
            api_keys,
            requests_per_minute=self.requests_per_minute,
            requests_per_day=self.requests_per_day,
        )

    async def mark_success(self, key_id: str) -> None:
        state = await self.repository.get_key_state(key_id)
        await self.repository.save_key_state(replace(state, cooldown_until=None, last_error=None, updated_at=utc_now_iso()))

    async def mark_cooldown(self, key_id: str, *, seconds: int, error: str) -> None:
        state = await self.repository.get_key_state(key_id)
        await self.repository.save_key_state(
            replace(
                state,
                cooldown_until=utc_now_ts() + seconds,
                last_error=error,
                updated_at=utc_now_iso(),
            )
        )


def _next_registry_index(registry_ids: list[int], last_registry_id: int | None) -> int:
    if not registry_ids or last_registry_id not in registry_ids:
        return 0
    return (registry_ids.index(last_registry_id) + 1) % len(registry_ids)


def _parse_registry_id(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
