"""SQLite による日次指標の履歴ストア。前期比較と時系列チャートに使う。"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from ..collectors.ga4 import GA4Metrics
from ..collectors.search_console import SearchTotals


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ga4_daily (
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    page_views INTEGER NOT NULL,
    active_users INTEGER NOT NULL,
    sessions INTEGER NOT NULL,
    engaged_sessions INTEGER NOT NULL,
    bounce_rate REAL NOT NULL,
    avg_session_duration REAL NOT NULL,
    conversions INTEGER NOT NULL,
    conversion_rate REAL NOT NULL,
    PRIMARY KEY (start_date, end_date)
);

CREATE TABLE IF NOT EXISTS gsc_daily (
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    clicks INTEGER NOT NULL,
    impressions INTEGER NOT NULL,
    ctr REAL NOT NULL,
    position REAL NOT NULL,
    PRIMARY KEY (start_date, end_date)
);

CREATE TABLE IF NOT EXISTS report_runs (
    run_at TEXT PRIMARY KEY,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class MetricsDB:
    def __init__(self, path: str | Path = "data/metrics.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def save_ga4(self, m: GA4Metrics) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO ga4_daily VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                m.start.isoformat(),
                m.end.isoformat(),
                m.page_views,
                m.active_users,
                m.sessions,
                m.engaged_sessions,
                m.bounce_rate,
                m.avg_session_duration,
                m.conversions,
                m.conversion_rate,
            ),
        )
        self.conn.commit()

    def save_gsc(self, t: SearchTotals) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO gsc_daily VALUES (?,?,?,?,?,?)""",
            (
                t.start.isoformat(),
                t.end.isoformat(),
                t.clicks,
                t.impressions,
                t.ctr,
                t.position,
            ),
        )
        self.conn.commit()

    def load_ga4(self, start: date, end: date) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM ga4_daily WHERE start_date=? AND end_date=?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()
        return dict(row) if row else None

    def load_gsc(self, start: date, end: date) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM gsc_daily WHERE start_date=? AND end_date=?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()
        return dict(row) if row else None

    def recent_ga4(self, days: int = 30) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM ga4_daily ORDER BY end_date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in rows]

    def recent_gsc(self, days: int = 30) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM gsc_daily ORDER BY end_date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in rows]

    def save_report_run(self, run_at: str, start: date, end: date, payload: Any) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO report_runs VALUES (?,?,?,?)",
            (run_at, start.isoformat(), end.isoformat(), json.dumps(payload, default=str, ensure_ascii=False)),
        )
        self.conn.commit()

    @staticmethod
    def ga4_to_dict(m: GA4Metrics) -> dict:
        d = asdict(m)
        d["start"] = m.start.isoformat()
        d["end"] = m.end.isoformat()
        d["engagement_rate"] = m.engagement_rate
        return d
