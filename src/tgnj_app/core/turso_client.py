"""
Turso HTTP API client — zero external dependencies.
All methods return None on any failure (never raise).
"""
import json
import urllib.request
from urllib.error import URLError, HTTPError


class TursoClient:
    def __init__(self, url: str, token: str):
        self.base_url = url.rstrip('/').replace('libsql://', 'https://')
        self.token = token
        self._pipeline_url = f"{self.base_url}/v2/pipeline"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def execute(self, sql: str, args: list = None) -> dict | None:
        """Execute a single SQL statement. Returns parsed response dict or None."""
        return self.execute_batch([{"sql": sql, "args": args or []}])

    def execute_batch(self, statements: list[dict]) -> dict | None:
        """
        Execute multiple SQL statements in a single pipeline call.
        Each statement: {"sql": "...", "args": [...]}
        Returns the full response dict or None on any failure.
        """
        body = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {
                        "sql": stmt["sql"],
                        "args": [
                            {"type": "null", "value": None} if a is None else
                            ({"type": "float", "value": float(a)} if isinstance(a, float) else
                             ({"type": "integer", "value": str(int(a))} if isinstance(a, int) else
                              {"type": "text", "value": str(a)}))
                            for a in (stmt.get("args") or [])
                        ],
                    },
                }
                for stmt in statements
            ]
            + [{"type": "close"}]
        }
        try:
            data = json.dumps(body).encode()
            req = urllib.request.Request(
                self._pipeline_url,
                data=data,
                headers=self._headers(),
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError) as e:
            print(f"[TursoClient] Warning: {e}")
            return None

    def query_rows(self, sql: str, args: list = None) -> list[dict] | None:
        """
        Convenience: run a SELECT and return list of row dicts.
        Column names are inferred from the response.
        Returns None on failure, empty list if no rows.
        """
        response = self.execute(sql, args)
        if response is None:
            return None
        try:
            result = response["results"][0]
            if result["type"] == "error":
                print(f"[TursoClient] Query error: {result.get('error')}")
                return None
            cols = [c["name"] for c in result["response"]["result"]["cols"]]
            rows = result["response"]["result"]["rows"]
            return [
                {cols[i]: (cell["value"] if cell["type"] != "null" else None)
                 for i, cell in enumerate(row)}
                for row in rows
            ]
        except (KeyError, IndexError, TypeError) as e:
            print(f"[TursoClient] Parse error: {e}")
            return None

    def ensure_schema(self) -> bool:
        """Ensure inventory and _sync_meta tables exist on Turso."""
        schema_stmts = [
            {
                "sql": """
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_group TEXT NOT NULL,
                    sku_id INTEGER NOT NULL,
                    shape TEXT,
                    weight REAL,
                    length INTEGER,
                    width INTEGER,
                    depth INTEGER,
                    created_at TEXT DEFAULT '',
                    updated_at TEXT DEFAULT '',
                    is_deleted INTEGER DEFAULT 0
                );
                """
            },
            {
                "sql": "CREATE TABLE IF NOT EXISTS _sync_meta (key TEXT PRIMARY KEY, value TEXT);"
            },
            {
                "sql": "CREATE INDEX IF NOT EXISTS idx_inventory_updated_at ON inventory(updated_at);"
            }
        ]
        res = self.execute_batch(schema_stmts)
        return res is not None


