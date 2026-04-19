"""Google Search Console API からハリナビの検索パフォーマンスを取得する。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class SearchTotals:
    start: date
    end: date
    clicks: int
    impressions: int
    ctr: float
    position: float


@dataclass
class QueryStats:
    query: str
    clicks: int
    impressions: int
    ctr: float
    position: float


@dataclass
class PageSearchStats:
    page: str
    clicks: int
    impressions: int
    ctr: float
    position: float


@dataclass
class SearchConsoleReport:
    totals: SearchTotals
    top_queries: list[QueryStats] = field(default_factory=list)
    rising_queries: list[QueryStats] = field(default_factory=list)
    top_pages: list[PageSearchStats] = field(default_factory=list)


_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


class SearchConsoleCollector:
    """Search Console Search Analytics API のラッパー。"""

    def __init__(self, site_url: str):
        if not site_url:
            raise ValueError("search_console.site_url を config.yaml に設定してください。")
        from google.auth import default as google_auth_default
        from googleapiclient.discovery import build

        self.site_url = site_url
        credentials, _ = google_auth_default(scopes=_SCOPES)
        self.service = build(
            "searchconsole", "v1", credentials=credentials, cache_discovery=False
        )

    def _query(
        self,
        start: date,
        end: date,
        dimensions: list[str] | None = None,
        row_limit: int = 1000,
    ) -> list[dict]:
        body: dict = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "rowLimit": row_limit,
        }
        if dimensions:
            body["dimensions"] = dimensions
        resp = (
            self.service.searchanalytics()
            .query(siteUrl=self.site_url, body=body)
            .execute()
        )
        return resp.get("rows", [])

    def fetch_totals(self, start: date, end: date) -> SearchTotals:
        rows = self._query(start, end, dimensions=None, row_limit=1)
        if not rows:
            return SearchTotals(start, end, 0, 0, 0.0, 0.0)
        r = rows[0]
        return SearchTotals(
            start=start,
            end=end,
            clicks=int(r.get("clicks", 0)),
            impressions=int(r.get("impressions", 0)),
            ctr=float(r.get("ctr", 0.0)),
            position=float(r.get("position", 0.0)),
        )

    def fetch_top_queries(
        self, start: date, end: date, limit: int = 20
    ) -> list[QueryStats]:
        rows = self._query(start, end, dimensions=["query"], row_limit=limit * 2)
        stats = [
            QueryStats(
                query=r["keys"][0] if r.get("keys") else "",
                clicks=int(r.get("clicks", 0)),
                impressions=int(r.get("impressions", 0)),
                ctr=float(r.get("ctr", 0.0)),
                position=float(r.get("position", 0.0)),
            )
            for r in rows
        ]
        stats.sort(key=lambda q: q.clicks, reverse=True)
        return stats[:limit]

    def fetch_top_pages(
        self, start: date, end: date, limit: int = 20
    ) -> list[PageSearchStats]:
        rows = self._query(start, end, dimensions=["page"], row_limit=limit * 2)
        out = [
            PageSearchStats(
                page=r["keys"][0] if r.get("keys") else "",
                clicks=int(r.get("clicks", 0)),
                impressions=int(r.get("impressions", 0)),
                ctr=float(r.get("ctr", 0.0)),
                position=float(r.get("position", 0.0)),
            )
            for r in rows
        ]
        out.sort(key=lambda p: p.clicks, reverse=True)
        return out[:limit]

    def fetch_rising_queries(
        self,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        limit: int = 10,
    ) -> list[QueryStats]:
        """前期から順位が伸びたクエリを検出する。"""
        current = {
            q.query: q
            for q in self.fetch_top_queries(current_start, current_end, limit=100)
        }
        previous = {
            q.query: q
            for q in self.fetch_top_queries(previous_start, previous_end, limit=100)
        }
        rising: list[tuple[float, QueryStats]] = []
        for key, cur in current.items():
            prev = previous.get(key)
            # 前期順位が無い / 悪い → 今期で上昇したと判定
            prev_pos = prev.position if prev else 100.0
            improvement = prev_pos - cur.position
            if improvement > 1.0 and cur.impressions > 10:
                rising.append((improvement, cur))
        rising.sort(key=lambda t: t[0], reverse=True)
        return [q for _, q in rising[:limit]]

    def fetch_report(self, start: date, end: date) -> SearchConsoleReport:
        totals = self.fetch_totals(start, end)
        top_queries = self.fetch_top_queries(start, end)
        top_pages = self.fetch_top_pages(start, end)
        span = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span - 1)
        rising = self.fetch_rising_queries(start, end, prev_start, prev_end)
        return SearchConsoleReport(
            totals=totals,
            top_queries=top_queries,
            rising_queries=rising,
            top_pages=top_pages,
        )
