"""
SQLite storage. Each horse is stored as validated JSON in one row, so the
schema can grow across versions without table migrations. Name, country, and
foaling year are duplicated into columns for listing and lookup.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from .models import Horse

SCHEMA = """
CREATE TABLE IF NOT EXISTS horses (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT,
    foaled      INTEGER,
    data        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS horses_name ON horses (name COLLATE NOCASE);
"""


class HorseStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def upsert(self, horse: Horse) -> None:
        horse.validate()
        self.conn.execute(
            "INSERT INTO horses (id, name, country, foaled, data, updated_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, country=excluded.country, "
            "foaled=excluded.foaled, data=excluded.data, updated_at=excluded.updated_at",
            (horse.id, horse.name, horse.country, horse.foaled,
             json.dumps(horse.to_dict(), ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def get(self, horse_id: str) -> Optional[Horse]:
        row = self.conn.execute("SELECT data FROM horses WHERE id = ?", (horse_id,)).fetchone()
        return Horse.from_dict(json.loads(row[0])) if row else None

    def all(self) -> List[Horse]:
        rows = self.conn.execute("SELECT data FROM horses ORDER BY name COLLATE NOCASE").fetchall()
        return [Horse.from_dict(json.loads(r[0])) for r in rows]

    def find(self, text: str) -> List[Horse]:
        rows = self.conn.execute(
            "SELECT data FROM horses WHERE name LIKE ? OR id LIKE ? ORDER BY name COLLATE NOCASE",
            (f"%{text}%", f"%{text}%"),
        ).fetchall()
        return [Horse.from_dict(json.loads(r[0])) for r in rows]

    def delete(self, horse_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM horses WHERE id = ?", (horse_id,))
        self.conn.commit()
        return cur.rowcount > 0
