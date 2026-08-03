"""
sync.py — Bidirectional sync engine between local SQLite and Turso Cloud.

Push: send local changes to Turso (INSERT OR REPLACE or DELETE)
Pull: fetch remote changes from Turso and apply to local SQLite

All timestamps are UTC ISO-8601 strings (e.g. '2026-01-01T12:00:00').
Conflict resolution: last-write-wins on updated_at.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tgnj_app.core.database import database
    from tgnj_app.core.turso_client import TursoClient

_EPOCH = '1970-01-01 00:00:00'


def _utcnow() -> str:
    """Return current UTC time (matching SQLite datetime format)."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


BATCH_SIZE = 250


def _batch_push_rows(turso: 'TursoClient', rows: list[dict]) -> int:
    """Push a list of row dicts to Turso in batches of 100 using pipeline execution."""
    pushed = 0
    for i in range(0, len(rows), BATCH_SIZE):
        chunk = rows[i:i + BATCH_SIZE]
        statements = []
        for row in chunk:
            statements.append({
                "sql": """
                INSERT OR REPLACE INTO inventory
                    (id, sku_group, sku_id, shape, weight, length, width, depth,
                     created_at, updated_at, is_deleted,
                     status, etsy_listing_id, sold_price, sold_channel, sold_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                "args": [
                    row.get('id'), row.get('sku_group'), row.get('sku_id'),
                    row.get('shape'), row.get('weight'), row.get('length'),
                    row.get('width'), row.get('depth'), row.get('created_at'),
                    row.get('updated_at'), row.get('is_deleted', 0),
                    row.get('status', 'IN_STOCK'), row.get('etsy_listing_id', ''),
                    row.get('sold_price', 0.0), row.get('sold_channel', ''),
                    row.get('sold_at', '')
                ]
            })


        res = turso.execute_batch(statements)
        if res is None:
            print(f"[sync] Batch push failed at offset {i} — Turso unreachable, aborting push")
            return pushed

        pushed += len(chunk)
    return pushed


def sync_push(db: 'database', turso: 'TursoClient', dry_run: bool = False) -> int:
    """
    Push local changes to Turso since last push.
    Returns the number of rows pushed.
    """
    last_push = db.get_sync_meta('last_push_time') or _EPOCH
    changes = db.get_changes_since(last_push)

    if not changes:
        return 0

    if dry_run:
        for row in changes:
            action = 'DELETE' if row.get('is_deleted') else 'UPSERT'
            print(f"  [dry-run push] {action} id={row.get('id')} sku={row.get('sku_group')}/{row.get('sku_id')} updated_at={row.get('updated_at')}")
        return len(changes)

    pushed = _batch_push_rows(turso, changes)

    if pushed == len(changes):
        db.set_sync_meta('last_push_time', _utcnow())

    return pushed


def sync_pull(db: 'database', turso: 'TursoClient', dry_run: bool = False) -> int:
    """
    Pull remote changes from Turso and apply to local SQLite.
    Returns the number of rows pulled.
    """
    last_pull = (db.get_sync_meta('last_pull_time') or _EPOCH).replace('T', ' ').replace('Z', '').strip()
    remote_rows = turso.query_rows(
        "SELECT * FROM inventory WHERE updated_at >= ? ORDER BY updated_at ASC;",
        [last_pull]
    )

    if remote_rows is None:
        print("[sync] Pull failed — Turso unreachable")
        return 0

    if not remote_rows:
        return 0

    pulled = 0
    rows_to_apply = []
    for row in remote_rows:
        if dry_run:
            print(f"  [dry-run pull] id={row.get('id')} sku={row.get('sku_group')}/{row.get('sku_id')} updated_at={row.get('updated_at')}")
            pulled += 1
            continue
        rows_to_apply.append(row)
        pulled += 1

    if rows_to_apply:
        db.apply_remote_changes(rows_to_apply)

    if not dry_run:
        db.set_sync_meta('last_pull_time', _utcnow())

    return pulled


def purge_old_tombstones(db: 'database', turso: 'TursoClient', days: int = 30) -> int:
    """Purge tombstones (is_deleted = 1) older than `days` days from remote Turso and local SQLite."""
    cutoff = f"-{days} days"
    if hasattr(turso, 'execute'):
        turso.execute("DELETE FROM inventory WHERE is_deleted = 1 AND updated_at < datetime('now', ?);", [cutoff])
    return db.purge_old_tombstones(days=days)


def sync(db: 'database', turso: 'TursoClient', dry_run: bool = False) -> dict:
    """
    Run a full push-then-pull sync cycle.
    Returns a result dict: {pushed, pulled, timestamp}.
    """
    if not dry_run and hasattr(turso, 'ensure_schema'):
        turso.ensure_schema()

    pushed = sync_push(db, turso, dry_run=dry_run)
    pulled = sync_pull(db, turso, dry_run=dry_run)
    
    if not dry_run:
        purge_old_tombstones(db, turso, days=30)

    now = _utcnow()
    return {'pushed': pushed, 'pulled': pulled, 'timestamp': now}



def initial_sync(db: 'database', turso: 'TursoClient') -> dict:
    """
    First-time sync logic.
    - Local only → push everything to Turso
    - Remote only → pull everything from Turso
    - Both have data → merge via last-write-wins sync()
    """
    if hasattr(turso, 'ensure_schema'):
        turso.ensure_schema()

    local_count = db.get_count()

    remote_result = turso.query_rows("SELECT COUNT(*) AS c FROM inventory;")
    if remote_result is None:
        print("[sync] initial_sync: Turso unreachable")
        return {'pushed': 0, 'pulled': 0, 'timestamp': _utcnow(), 'error': 'turso_unreachable'}

    remote_count = int(remote_result[0].get('c', 0)) if remote_result else 0

    if local_count == 0 and remote_count > 0:
        # New device — pull everything
        print(f"[sync] initial_sync: pulling {remote_count} rows from Turso (new device)")
        all_remote = turso.query_rows("SELECT * FROM inventory ORDER BY updated_at ASC;")
        if all_remote is None:
            print("[sync] initial_sync: Turso unreachable during full pull — aborting")
            return {'pushed': 0, 'pulled': 0, 'timestamp': _utcnow(), 'error': 'turso_unreachable'}
        if all_remote:
            db.apply_remote_changes(all_remote)
        db.set_sync_meta('last_pull_time', _utcnow())
        db.set_sync_meta('last_push_time', _utcnow())
        return {'pushed': 0, 'pulled': len(all_remote), 'timestamp': _utcnow()}

    elif local_count > 0 and remote_count == 0:
        # First upload — push everything in batches
        print(f"[sync] initial_sync: pushing {local_count} local rows to Turso (first upload)")
        all_local = db.get_all_items()
        pushed = _batch_push_rows(turso, all_local)
        if pushed < len(all_local):
            print(f"[sync] initial_sync: Turso push aborted at {pushed}/{len(all_local)} rows")
            return {'pushed': pushed, 'pulled': 0, 'timestamp': _utcnow(), 'error': 'turso_unreachable'}
        db.set_sync_meta('last_push_time', _utcnow())
        db.set_sync_meta('last_pull_time', _utcnow())
        return {'pushed': pushed, 'pulled': 0, 'timestamp': _utcnow()}

    else:
        # Both have data — merge
        print("[sync] initial_sync: both sides have data, running merge sync")
        return sync(db, turso)



# ——— CLI entry point ———

def _run_dry_run(db_path: str):
    """Dry-run mode: show what would be pushed/pulled without hitting Turso."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from tgnj_app.core.database import database as Database
    from tgnj_app.core.turso_client import TursoClient

    db = Database(Path(db_path))

    # Use a no-op Turso client for dry run
    class _DryRunTurso:
        def execute(self, *a, **kw): return {"results": []}
        def execute_batch(self, *a, **kw): return {"results": []}
        def query_rows(self, *a, **kw): return []

    turso = _DryRunTurso()

    print(f"[dry-run] Checking changes since last push/pull for db: {db_path}")
    last_push = db.get_sync_meta('last_push_time') or _EPOCH
    last_pull = db.get_sync_meta('last_pull_time') or _EPOCH
    print(f"  last_push_time : {last_push}")
    print(f"  last_pull_time : {last_pull}")

    changes = db.get_changes_since(last_push)
    print(f"\n[dry-run] {len(changes)} local row(s) would be pushed:")
    for row in changes:
        action = 'DELETE' if row.get('is_deleted') else 'UPSERT'
        print(f"  {action} id={row.get('id')} sku={row.get('sku_group')}/{row.get('sku_id')} updated_at={row.get('updated_at')}")

    print(f"\n[dry-run] (pull requires live Turso connection — skipped in dry-run)")
    print("\n[dry-run] Done. No changes made.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TGNJ Turso sync engine')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be synced without making changes')
    parser.add_argument('--db', required=True, help='Path to the local SQLite database file')
    args = parser.parse_args()

    if args.dry_run:
        _run_dry_run(args.db)
    else:
        print("[sync] Live sync requires Turso credentials. Use the Flask app or configure via /api/setTursoConfig.")
        sys.exit(1)
