import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class BroadcastStorage:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.database_path = data_dir / 'broadcasts.sqlite3'

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute('PRAGMA journal_mode = WAL')
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    media_path TEXT,
                    media_kind TEXT,
                    media_original_name TEXT,
                    button_text TEXT,
                    button_url TEXT,
                    status TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    total_count INTEGER NOT NULL DEFAULT 0,
                    valid_count INTEGER NOT NULL DEFAULT 0,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    duplicate_count INTEGER NOT NULL DEFAULT 0,
                    invalid_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                );

                CREATE TABLE IF NOT EXISTS broadcast_recipients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broadcast_id INTEGER NOT NULL,
                    row_number INTEGER NOT NULL,
                    telegram_id INTEGER,
                    raw_telegram_id TEXT,
                    name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    error TEXT,
                    FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_broadcast_status_schedule
                    ON broadcasts(status, scheduled_at);
                CREATE INDEX IF NOT EXISTS idx_recipient_broadcast_status
                    ON broadcast_recipients(broadcast_id, status);
                """
            )

    def create_draft(
        self,
        *,
        message: str,
        source_filename: str,
        media_path: str | None,
        media_kind: str | None,
        media_original_name: str | None,
        button_text: str | None,
        button_url: str | None,
        scheduled_at: datetime,
        recipients: list[dict[str, Any]],
        duplicate_count: int,
        invalid_count: int,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        valid_count = sum(item['status'] == 'pending' for item in recipients)
        skipped_count = sum(item['status'] == 'skipped' for item in recipients)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO broadcasts (
                    message, source_filename, media_path, media_kind,
                    media_original_name, button_text, button_url, status,
                    scheduled_at, created_at, total_count, valid_count,
                    skipped_count, duplicate_count, invalid_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message,
                    source_filename,
                    media_path,
                    media_kind,
                    media_original_name,
                    button_text,
                    button_url,
                    scheduled_at.astimezone(timezone.utc).isoformat(),
                    created_at,
                    len(recipients),
                    valid_count,
                    skipped_count,
                    duplicate_count,
                    invalid_count,
                ),
            )
            broadcast_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO broadcast_recipients (
                    broadcast_id, row_number, telegram_id, raw_telegram_id,
                    name, status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        broadcast_id,
                        item['row_number'],
                        item.get('telegram_id'),
                        item.get('raw_telegram_id'),
                        item.get('name', ''),
                        item['status'],
                        item.get('error'),
                    )
                    for item in recipients
                ],
            )
        return broadcast_id

    def get_broadcast(self, broadcast_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT * FROM broadcasts WHERE id = ?',
                (broadcast_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_broadcasts(self, *, include_drafts: bool = False) -> list[dict[str, Any]]:
        where = '' if include_drafts else "WHERE status != 'draft'"
        with self._connect() as connection:
            rows = connection.execute(
                f'SELECT * FROM broadcasts {where} ORDER BY created_at DESC'  # noqa: S608
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recipients(
        self,
        broadcast_id: int,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        pagination = ''
        parameters: list[Any] = [broadcast_id]
        if limit is not None:
            pagination = ' LIMIT ? OFFSET ?'
            parameters.extend([limit, offset])
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM broadcast_recipients
                WHERE broadcast_id = ? ORDER BY row_number
                {pagination}
                """,  # noqa: S608
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_recipient(self, recipient_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT * FROM broadcast_recipients WHERE id = ?',
                (recipient_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def confirm_draft(self, broadcast_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE broadcasts SET status = 'scheduled' WHERE id = ? AND status = 'draft'",
                (broadcast_id,),
            )
        return cursor.rowcount == 1

    def delete_draft(self, broadcast_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT media_path FROM broadcasts WHERE id = ? AND status = 'draft'",
                (broadcast_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "DELETE FROM broadcasts WHERE id = ? AND status = 'draft'",
                (broadcast_id,),
            )
        return row['media_path']

    def cancel(self, broadcast_id: int) -> tuple[bool, str | None]:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE broadcasts
                SET status = 'cancelled', finished_at = ?
                WHERE id = ? AND status IN ('draft', 'scheduled')
                """,
                (finished_at, broadcast_id),
            )
            if cursor.rowcount != 1:
                return False, None
            row = connection.execute(
                'SELECT media_path FROM broadcasts WHERE id = ?',
                (broadcast_id,),
            ).fetchone()
        return True, row['media_path'] if row is not None else None

    def next_due(self, now: datetime) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM broadcasts
                WHERE status = 'scheduled' AND scheduled_at <= ?
                ORDER BY scheduled_at, id LIMIT 1
                """,
                (now.astimezone(timezone.utc).isoformat(),),
            ).fetchone()
        return dict(row) if row is not None else None

    def mark_running(self, broadcast_id: int) -> bool:
        started_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE broadcasts SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'scheduled'
                """,
                (started_at, broadcast_id),
            )
        return cursor.rowcount == 1

    def pending_recipients(self, broadcast_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM broadcast_recipients
                WHERE broadcast_id = ? AND status = 'pending'
                ORDER BY row_number
                """,
                (broadcast_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_recipient_sending(self, recipient_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE broadcast_recipients SET status = 'sending', error = NULL
                WHERE id = ? AND status = 'pending'
                """,
                (recipient_id,),
            )
        return cursor.rowcount == 1

    def mark_recipient_result(
        self,
        recipient_id: int,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        recipient = self.get_recipient(recipient_id)
        if recipient is None:
            return
        status = 'success' if success else 'error'
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE broadcast_recipients SET status = ?, error = ?
                WHERE id = ? AND status = 'sending'
                """,
                (status, error, recipient_id),
            )
            self._refresh_counts(connection, int(recipient['broadcast_id']))

    def finish_broadcast(self, broadcast_id: int) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._refresh_counts(connection, broadcast_id)
            row = connection.execute(
                'SELECT error_count FROM broadcasts WHERE id = ?',
                (broadcast_id,),
            ).fetchone()
            status = 'completed_with_errors' if row and row['error_count'] else 'completed'
            connection.execute(
                'UPDATE broadcasts SET status = ?, finished_at = ? WHERE id = ?',
                (status, finished_at, broadcast_id),
            )

    def fail_broadcast(self, broadcast_id: int, error: str) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE broadcasts
                SET status = 'completed_with_errors', finished_at = ?, last_error = ?
                WHERE id = ?
                """,
                (finished_at, error, broadcast_id),
            )

    def recover_interrupted(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            interrupted = connection.execute(
                """
                SELECT DISTINCT broadcast_id FROM broadcast_recipients
                WHERE status = 'sending'
                """
            ).fetchall()
            connection.execute(
                """
                UPDATE broadcast_recipients
                SET status = 'error', error = 'Отправка прервана перезапуском сервиса'
                WHERE status = 'sending'
                """
            )
            connection.execute(
                """
                UPDATE broadcasts SET status = 'scheduled', scheduled_at = ?
                WHERE status = 'running'
                """,
                (now,),
            )
            for row in interrupted:
                self._refresh_counts(connection, int(row['broadcast_id']))

    def stale_draft_media(self) -> list[str]:
        threshold = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT media_path FROM broadcasts
                WHERE status = 'draft' AND created_at < ? AND media_path IS NOT NULL
                """,
                (threshold,),
            ).fetchall()
            connection.execute(
                "DELETE FROM broadcasts WHERE status = 'draft' AND created_at < ?",
                (threshold,),
            )
        return [row['media_path'] for row in rows]

    @staticmethod
    def _refresh_counts(connection: sqlite3.Connection, broadcast_id: int) -> None:
        counts = connection.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count
            FROM broadcast_recipients WHERE broadcast_id = ?
            """,
            (broadcast_id,),
        ).fetchone()
        connection.execute(
            """
            UPDATE broadcasts SET success_count = ?, error_count = ?, skipped_count = ?
            WHERE id = ?
            """,
            (
                counts['success_count'] or 0,
                counts['error_count'] or 0,
                counts['skipped_count'] or 0,
                broadcast_id,
            ),
        )
