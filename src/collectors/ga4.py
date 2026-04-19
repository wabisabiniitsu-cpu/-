"""GA4 Data API からハリナビの主要指標を取得する。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from google.analytics.data_v1beta.types import RunReportRequest


@dataclass
class GA4Metrics:
    start: date
    end: date
    page_views: int
    active_users: int
    sessions: int
    engaged_sessions: int
    bounce_rate: float
    avg_session_duration: float
    conversions: int
    conversion_rate: float

    @property
    def engagement_rate(self) -> float:
        return (self.engaged_sessions / self.sessions) if self.sessions else 0.0


@dataclass
class PageStats:
    path: str
    title: str
    page_views: int
    users: int
    avg_time_on_page: float


@dataclass
class ChannelStats:
    channel: str
    sessions: int
    users: int
    conversions: int


class GA4Collector:
    """GA4 Data API のラッパー。

    - property_id: 数値の GA4 プロパティ ID (測定 ID G-... ではない)
    - conversion_events: GA4 で "キーイベント" として設定済みのイベント名リスト
    """

    def __init__(self, property_id: str, conversion_events: list[str]):
        if not property_id or not property_id.isdigit():
            raise ValueError(
                f"ga4_property_id は数値である必要があります。受け取った値: {property_id!r}"
            )
        from google.analytics.data_v1beta import BetaAnalyticsDataClient

        self.property_id = property_id
        self.property = f"properties/{property_id}"
        self.conversion_events = conversion_events
        self.client = BetaAnalyticsDataClient()

    def _run(self, request: "RunReportRequest"):
        return self.client.run_report(request=request)

    def fetch_summary(self, start: date, end: date) -> GA4Metrics:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Metric,
            RunReportRequest,
        )
        req = RunReportRequest(
            property=self.property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="engagedSessions"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
            ],
        )
        resp = self._run(req)
        row = resp.rows[0].metric_values if resp.rows else None

        def g(i: int, default: float = 0.0) -> float:
            if row is None:
                return default
            try:
                return float(row[i].value)
            except (ValueError, IndexError):
                return default

        page_views = int(g(0))
        active_users = int(g(1))
        sessions = int(g(2))
        engaged_sessions = int(g(3))
        bounce_rate = g(4)
        avg_session_duration = g(5)

        conversions = self._fetch_conversions(start, end)
        conversion_rate = (conversions / sessions) if sessions else 0.0

        return GA4Metrics(
            start=start,
            end=end,
            page_views=page_views,
            active_users=active_users,
            sessions=sessions,
            engaged_sessions=engaged_sessions,
            bounce_rate=bounce_rate,
            avg_session_duration=avg_session_duration,
            conversions=conversions,
            conversion_rate=conversion_rate,
        )

    def _fetch_conversions(self, start: date, end: date) -> int:
        if not self.conversion_events:
            return 0
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            FilterExpressionList,
            Metric,
            RunReportRequest,
        )
        req = RunReportRequest(
            property=self.property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            dimension_filter=FilterExpression(
                or_group=FilterExpressionList(
                    expressions=[
                        FilterExpression(
                            filter=Filter(
                                field_name="eventName",
                                string_filter=Filter.StringFilter(value=ev),
                            )
                        )
                        for ev in self.conversion_events
                    ]
                )
            ),
        )
        resp = self._run(req)
        total = 0
        for row in resp.rows:
            try:
                total += int(row.metric_values[0].value)
            except (ValueError, IndexError):
                pass
        return total

    def fetch_top_pages(self, start: date, end: date, limit: int = 10) -> list[PageStats]:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
        req = RunReportRequest(
            property=self.property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
                Metric(name="averageSessionDuration"),
            ],
            limit=limit,
        )
        resp = self._run(req)
        pages: list[PageStats] = []
        for row in resp.rows:
            dims = [d.value for d in row.dimension_values]
            mets = [m.value for m in row.metric_values]
            pages.append(
                PageStats(
                    path=dims[0] if len(dims) > 0 else "",
                    title=dims[1] if len(dims) > 1 else "",
                    page_views=int(float(mets[0])) if len(mets) > 0 else 0,
                    users=int(float(mets[1])) if len(mets) > 1 else 0,
                    avg_time_on_page=float(mets[2]) if len(mets) > 2 else 0.0,
                )
            )
        pages.sort(key=lambda p: p.page_views, reverse=True)
        return pages

    def fetch_channels(self, start: date, end: date) -> list[ChannelStats]:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )
        req = RunReportRequest(
            property=self.property,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
                Metric(name="conversions"),
            ],
        )
        resp = self._run(req)
        out: list[ChannelStats] = []
        for row in resp.rows:
            dims = [d.value for d in row.dimension_values]
            mets = [m.value for m in row.metric_values]
            out.append(
                ChannelStats(
                    channel=dims[0] if dims else "(not set)",
                    sessions=int(float(mets[0])) if len(mets) > 0 else 0,
                    users=int(float(mets[1])) if len(mets) > 1 else 0,
                    conversions=int(float(mets[2])) if len(mets) > 2 else 0,
                )
            )
        out.sort(key=lambda c: c.sessions, reverse=True)
        return out


def yesterday_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    y = today - timedelta(days=1)
    return y, y


def period_range(end: date, days: int) -> tuple[date, date]:
    start = end - timedelta(days=days - 1)
    return start, end
