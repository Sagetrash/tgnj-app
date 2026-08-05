#!/usr/bin/env python3
"""
turso_cli.py — Run SQL queries against Turso Cloud DB Master directly from the command line.

Usage:
    python scripts/turso_cli.py "SELECT sku_group, sku_id, status, etsy_listing_id FROM inventory WHERE sku_group = 'J7' AND status = 'LISTED_ETSY' ORDER BY sku_id ASC;"
"""
import sys
from pathlib import Path

# Add src/ to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tgnj_app.gui.app import load_turso_config
from tgnj_app.core.turso_client import TursoClient

def main():
    if len(sys.argv) < 2:
        query = "SELECT sku_group, sku_id, shape, weight, status, etsy_listing_id FROM inventory WHERE sku_group = 'J7' AND status = 'LISTED_ETSY' ORDER BY sku_id ASC;"
    else:
        query = sys.argv[1]

    url, token, _ = load_turso_config()
    if not url or not token:
        print("Error: Turso credentials not found in database config.")
        sys.exit(1)

    client = TursoClient(url, token)
    rows = client.query_rows(query)

    print(f"Database: {url}")
    print(f"Query: {query}\n")

    if not rows:
        print("0 rows returned.")
        return

    columns = list(rows[0].keys())
    col_widths = {col: max(len(col), max(len(str(r.get(col, ""))) for r in rows)) for col in columns}

    header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
    divider = "-+-".join("-" * col_widths[col] for col in columns)

    print(header)
    print(divider)
    for r in rows:
        row_str = " | ".join(f"{str(r.get(col, '')):<{col_widths[col]}}" for col in columns)
        print(row_str)

    print(divider)
    print(f"TOTAL ROWS RETURNED: {len(rows)}")

if __name__ == "__main__":
    main()
