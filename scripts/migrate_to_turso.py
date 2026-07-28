"""
migrate_to_turso.py — One-time migration: push all local inventory rows to Turso.

Usage:
    python scripts/migrate_to_turso.py --db /path/to/inventory.db \
                                       --url https://your-db.turso.io \
                                       --token eyJ...

Safe to run multiple times (INSERT OR REPLACE is idempotent).
"""
import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root without installing package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from tgnj_app.core.turso_client import TursoClient


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def migrate(db_path: str, turso_url: str, turso_token: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 1. Idempotent schema migration — add sync columns if missing
    for col, definition in [
        ('created_at', "TEXT DEFAULT ''"),
        ('updated_at', "TEXT DEFAULT ''"),
        ('is_deleted', 'INTEGER DEFAULT 0'),
    ]:
        try:
            conn.execute(f'ALTER TABLE inventory ADD COLUMN {col} {definition}')
            conn.commit()
            print(f'  Added column: {col}')
        except sqlite3.OperationalError:
            pass  # column already exists

    # 2. Backfill NULL timestamps on existing rows
    now = _utcnow()
    conn.execute(
        "UPDATE inventory SET created_at = ?, updated_at = ? WHERE created_at IS NULL OR created_at = ''",
        (now, now)
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _sync_meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.commit()

    # 3. Fetch all rows
    rows = conn.execute(
        'SELECT * FROM inventory WHERE COALESCE(is_deleted, 0) = 0'
    ).fetchall()
    print(f'\nFound {len(rows)} rows to migrate.')

    if not rows:
        print('Nothing to migrate. Exiting.')
        conn.close()
        return

    # 4. Push each row to Turso
    turso = TursoClient(turso_url, turso_token)
    pushed = 0
    failed = 0
    for row in rows:
        r = dict(row)
        result = turso.execute(
            """
            INSERT OR REPLACE INTO inventory
                (id, sku_group, sku_id, shape, weight, length, width, depth,
                 created_at, updated_at, is_deleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            [
                r.get('id'), r.get('sku_group'), r.get('sku_id'),
                r.get('shape'), r.get('weight'), r.get('length'),
                r.get('width'), r.get('depth'), r.get('created_at'),
                r.get('updated_at'), r.get('is_deleted', 0)
            ]
        )
        if result is None:
            print(f'  FAILED: id={r.get("id")} sku={r.get("sku_group")}/{r.get("sku_id")}')
            failed += 1
        else:
            pushed += 1

    if failed > 0:
        print(f'\n{failed} row(s) failed to push. Do NOT mark migration complete.')
        print('Check your Turso URL and token, then re-run.')
        conn.close()
        sys.exit(1)

    # 5. Mark sync timestamps so the app knows migration is done
    now = _utcnow()
    conn.execute(
        'INSERT OR REPLACE INTO _sync_meta (key, value) VALUES (?, ?)',
        ('last_push_time', now)
    )
    conn.execute(
        'INSERT OR REPLACE INTO _sync_meta (key, value) VALUES (?, ?)',
        ('last_pull_time', now)
    )
    conn.commit()
    conn.close()

    print(f'\nMigrated {pushed}/{len(rows)} rows to Turso successfully.')
    print('last_push_time and last_pull_time set. App is ready for incremental sync.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='One-time migration: push all local inventory rows to Turso.'
    )
    parser.add_argument('--db', required=True, help='Path to local inventory.db')
    parser.add_argument('--url', required=True, help='Turso database URL')
    parser.add_argument('--token', required=True, help='Turso auth token')
    args = parser.parse_args()

    print(f'Migrating {args.db} → {args.url}...')
    migrate(args.db, args.url, args.token)
