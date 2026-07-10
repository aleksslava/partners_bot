import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PLATFORMS = ('telegram', 'max')


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
                    last_error TEXT,
                    send_telegram INTEGER NOT NULL DEFAULT 1,
                    send_max INTEGER NOT NULL DEFAULT 0,
                    max_media_token TEXT,
                    max_media_type TEXT,
                    telegram_duplicate_count INTEGER NOT NULL DEFAULT 0,
                    max_duplicate_count INTEGER NOT NULL DEFAULT 0,
                    telegram_invalid_count INTEGER NOT NULL DEFAULT 0,
                    max_invalid_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS broadcast_recipients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broadcast_id INTEGER NOT NULL,
                    row_number INTEGER NOT NULL,
                    telegram_id INTEGER,
                    raw_telegram_id TEXT,
                    max_id INTEGER,
                    raw_max_id TEXT,
                    name TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT,
                    FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id) ON DELETE CASCADE
                );
                """
            )
            self._upgrade_v1_schema(connection)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS broadcast_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broadcast_id INTEGER NOT NULL,
                    recipient_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    target_id INTEGER,
                    raw_target_id TEXT,
                    status TEXT NOT NULL,
                    error TEXT,
                    FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id) ON DELETE CASCADE,
                    FOREIGN KEY (recipient_id) REFERENCES broadcast_recipients(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_broadcast_status_schedule
                    ON broadcasts(status, scheduled_at);
                CREATE INDEX IF NOT EXISTS idx_delivery_broadcast_status
                    ON broadcast_deliveries(broadcast_id, status);
                CREATE INDEX IF NOT EXISTS idx_delivery_platform_status
                    ON broadcast_deliveries(broadcast_id, platform, status);
                """
            )
            self._migrate_legacy_deliveries(connection)
            connection.execute('PRAGMA user_version = 2')

    def _upgrade_v1_schema(self, connection: sqlite3.Connection) -> None:
        broadcast_columns = {
            row['name'] for row in connection.execute('PRAGMA table_info(broadcasts)')
        }
        additions = {
            'send_telegram': 'INTEGER NOT NULL DEFAULT 1',
            'send_max': 'INTEGER NOT NULL DEFAULT 0',
            'max_media_token': 'TEXT',
            'max_media_type': 'TEXT',
            'telegram_duplicate_count': 'INTEGER NOT NULL DEFAULT 0',
            'max_duplicate_count': 'INTEGER NOT NULL DEFAULT 0',
            'telegram_invalid_count': 'INTEGER NOT NULL DEFAULT 0',
            'max_invalid_count': 'INTEGER NOT NULL DEFAULT 0',
        }
        for name, definition in additions.items():
            if name not in broadcast_columns:
                connection.execute(f'ALTER TABLE broadcasts ADD COLUMN {name} {definition}')

        recipient_columns = {
            row['name']
            for row in connection.execute('PRAGMA table_info(broadcast_recipients)')
        }
        if 'max_id' not in recipient_columns:
            connection.execute('ALTER TABLE broadcast_recipients ADD COLUMN max_id INTEGER')
        if 'raw_max_id' not in recipient_columns:
            connection.execute('ALTER TABLE broadcast_recipients ADD COLUMN raw_max_id TEXT')

        connection.execute(
            """
            UPDATE broadcasts
            SET telegram_duplicate_count = duplicate_count,
                telegram_invalid_count = invalid_count
            WHERE send_max = 0
              AND telegram_duplicate_count = 0
              AND telegram_invalid_count = 0
            """
        )

    def _migrate_legacy_deliveries(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            INSERT INTO broadcast_deliveries (
                broadcast_id, recipient_id, platform, target_id,
                raw_target_id, status, error
            )
            SELECT r.broadcast_id, r.id, 'telegram', r.telegram_id,
                   r.raw_telegram_id, r.status, r.error
            FROM broadcast_recipients r
            WHERE NOT EXISTS (
                SELECT 1 FROM broadcast_deliveries d
                WHERE d.recipient_id = r.id
            )
            """
        )
        broadcast_ids = connection.execute('SELECT id FROM broadcasts').fetchall()
        for row in broadcast_ids:
            self._refresh_counts(connection, int(row['id']))

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
        targets: set[str],
        validation_stats: dict[str, dict[str, int]],
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        deliveries = [
            delivery
            for recipient in recipients
            for delivery in recipient.get('deliveries', [])
        ]
        valid_count = sum(item['status'] == 'pending' for item in deliveries)
        skipped_count = sum(item['status'] == 'skipped' for item in deliveries)
        telegram_stats = validation_stats.get('telegram', {})
        max_stats = validation_stats.get('max', {})
        duplicate_count = telegram_stats.get('duplicates', 0) + max_stats.get('duplicates', 0)
        invalid_count = telegram_stats.get('invalid', 0) + max_stats.get('invalid', 0)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO broadcasts (
                    message, source_filename, media_path, media_kind,
                    media_original_name, button_text, button_url, status,
                    scheduled_at, created_at, total_count, valid_count,
                    skipped_count, duplicate_count, invalid_count,
                    send_telegram, send_max, telegram_duplicate_count,
                    max_duplicate_count, telegram_invalid_count, max_invalid_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int('telegram' in targets),
                    int('max' in targets),
                    telegram_stats.get('duplicates', 0),
                    max_stats.get('duplicates', 0),
                    telegram_stats.get('invalid', 0),
                    max_stats.get('invalid', 0),
                ),
            )
            broadcast_id = int(cursor.lastrowid)
            for recipient in recipients:
                recipient_cursor = connection.execute(
                    """
                    INSERT INTO broadcast_recipients (
                        broadcast_id, row_number, telegram_id, raw_telegram_id,
                        max_id, raw_max_id, name, status, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', NULL)
                    """,
                    (
                        broadcast_id,
                        recipient['row_number'],
                        recipient.get('telegram_id'),
                        recipient.get('raw_telegram_id'),
                        recipient.get('max_id'),
                        recipient.get('raw_max_id'),
                        recipient.get('name', ''),
                    ),
                )
                recipient_id = int(recipient_cursor.lastrowid)
                connection.executemany(
                    """
                    INSERT INTO broadcast_deliveries (
                        broadcast_id, recipient_id, platform, target_id,
                        raw_target_id, status, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            broadcast_id,
                            recipient_id,
                            item['platform'],
                            item.get('target_id'),
                            item.get('raw_target_id'),
                            item['status'],
                            item.get('error'),
                        )
                        for item in recipient.get('deliveries', [])
                    ],
                )
        return broadcast_id

    def get_broadcast(self, broadcast_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT * FROM broadcasts WHERE id = ?',
                (broadcast_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['platform_stats'] = self.get_platform_stats(broadcast_id)
        return result

    def list_broadcasts(self, *, include_drafts: bool = False) -> list[dict[str, Any]]:
        where = '' if include_drafts else "WHERE status != 'draft'"
        with self._connect() as connection:
            rows = connection.execute(
                f'SELECT * FROM broadcasts {where} ORDER BY created_at DESC'  # noqa: S608
            ).fetchall()
        results = [dict(row) for row in rows]
        for item in results:
            item['platform_stats'] = self.get_platform_stats(int(item['id']))
        return results

    def get_platform_stats(self, broadcast_id: int) -> dict[str, dict[str, int | bool]]:
        broadcast = None
        with self._connect() as connection:
            broadcast = connection.execute(
                'SELECT send_telegram, send_max FROM broadcasts WHERE id = ?',
                (broadcast_id,),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT platform,
                    SUM(CASE WHEN status != 'skipped' THEN 1 ELSE 0 END) AS valid_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count
                FROM broadcast_deliveries
                WHERE broadcast_id = ? GROUP BY platform
                """,
                (broadcast_id,),
            ).fetchall()
        by_platform = {row['platform']: row for row in rows}
        result: dict[str, dict[str, int | bool]] = {}
        for platform in PLATFORMS:
            row = by_platform.get(platform)
            selected = bool(
                broadcast
                and broadcast['send_telegram' if platform == 'telegram' else 'send_max']
            )
            result[platform] = {
                'selected': selected,
                'valid_count': int(row['valid_count'] or 0) if row else 0,
                'success_count': int(row['success_count'] or 0) if row else 0,
                'error_count': int(row['error_count'] or 0) if row else 0,
                'skipped_count': int(row['skipped_count'] or 0) if row else 0,
            }
        return result

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
                WHERE broadcast_id = ? ORDER BY row_number {pagination}
                """,  # noqa: S608
                parameters,
            ).fetchall()
            recipients = [dict(row) for row in rows]
            recipient_ids = [item['id'] for item in recipients]
            deliveries: list[sqlite3.Row] = []
            if recipient_ids:
                placeholders = ','.join('?' for _ in recipient_ids)
                deliveries = connection.execute(
                    f"""
                    SELECT * FROM broadcast_deliveries
                    WHERE recipient_id IN ({placeholders})
                    """,  # noqa: S608
                    recipient_ids,
                ).fetchall()
        delivery_map = {
            (row['recipient_id'], row['platform']): dict(row)
            for row in deliveries
        }
        for recipient in recipients:
            recipient['telegram_delivery'] = delivery_map.get(
                (recipient['id'], 'telegram')
            )
            recipient['max_delivery'] = delivery_map.get((recipient['id'], 'max'))
        return recipients

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
                UPDATE broadcasts SET status = 'cancelled', finished_at = ?
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

    def pending_deliveries(self, broadcast_id: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT d.*, r.name, r.row_number
                FROM broadcast_deliveries d
                JOIN broadcast_recipients r ON r.id = d.recipient_id
                WHERE d.broadcast_id = ? AND d.status = 'pending'
                ORDER BY r.row_number,
                    CASE d.platform WHEN 'telegram' THEN 0 ELSE 1 END
                """,
                (broadcast_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_delivery_sending(self, delivery_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE broadcast_deliveries SET status = 'sending', error = NULL
                WHERE id = ? AND status = 'pending'
                """,
                (delivery_id,),
            )
        return cursor.rowcount == 1

    def mark_delivery_result(
        self,
        delivery_id: int,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        status = 'success' if success else 'error'
        with self._connect() as connection:
            row = connection.execute(
                'SELECT broadcast_id FROM broadcast_deliveries WHERE id = ?',
                (delivery_id,),
            ).fetchone()
            if row is None:
                return
            connection.execute(
                """
                UPDATE broadcast_deliveries SET status = ?, error = ?
                WHERE id = ? AND status = 'sending'
                """,
                (status, error, delivery_id),
            )
            self._refresh_counts(connection, int(row['broadcast_id']))

    def fail_pending_platform(self, broadcast_id: int, platform: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE broadcast_deliveries SET status = 'error', error = ?
                WHERE broadcast_id = ? AND platform = ? AND status = 'pending'
                """,
                (error, broadcast_id, platform),
            )
            self._refresh_counts(connection, broadcast_id)

    def save_max_media(self, broadcast_id: int, media_type: str, token: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE broadcasts SET max_media_type = ?, max_media_token = ?
                WHERE id = ?
                """,
                (media_type, token, broadcast_id),
            )

    def finish_broadcast(self, broadcast_id: int) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._refresh_counts(connection, broadcast_id)
            row = connection.execute(
                'SELECT error_count FROM broadcasts WHERE id = ?',
                (broadcast_id,),
            ).fetchone()
            result_status = 'completed_with_errors' if row and row['error_count'] else 'completed'
            connection.execute(
                'UPDATE broadcasts SET status = ?, finished_at = ? WHERE id = ?',
                (result_status, finished_at, broadcast_id),
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
            connection.execute(
                """
                UPDATE broadcast_deliveries
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
            for row in connection.execute('SELECT id FROM broadcasts'):
                self._refresh_counts(connection, int(row['id']))

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
                SUM(CASE WHEN status != 'skipped' THEN 1 ELSE 0 END) AS valid_count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_count,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped_count
            FROM broadcast_deliveries WHERE broadcast_id = ?
            """,
            (broadcast_id,),
        ).fetchone()
        connection.execute(
            """
            UPDATE broadcasts
            SET valid_count = ?, success_count = ?, error_count = ?, skipped_count = ?
            WHERE id = ?
            """,
            (
                counts['valid_count'] or 0,
                counts['success_count'] or 0,
                counts['error_count'] or 0,
                counts['skipped_count'] or 0,
                broadcast_id,
            ),
        )
