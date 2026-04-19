"""前期比較・アラート判定など、定量的な分析ロジック。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from ..collectors.ga4 import GA4Metrics
from ..collectors.search_console import SearchTotals
from ..config import Thresholds


Comparison = Literal["day_over_day", "week_over_week", "month_over_month"]


def comparison_window(end: date, mode: Comparison) -> tuple[date, date, date, date]:
    """(current_start, current_end, previous_start, previous_end) を返す。"""
    if mode == "day_over_day":
        cur_start = end
        cur_end = end
        prev_start = end - timedelta(days=1)
        prev_end = prev_start
    elif mode == "week_over_week":
        cur_end = end
        cur_start = end - timedelta(days=6)
        prev_end = cur_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=6)
    elif mode == "month_over_month":
        cur_end = end
        cur_start = end - timedelta(days=29)
        prev_end = cur_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=29)
    else:
        raise ValueError(f"未知の比較モード: {mode}")
    return cur_start, cur_end, prev_start, prev_end


def pct_change(cur: float, prev: float) -> float:
    if prev == 0:
        return 0.0 if cur == 0 else 1.0
    return (cur - prev) / prev


@dataclass
class Delta:
    label: str
    current: float
    previous: float
    change: float  # 絶対差
    change_pct: float  # 比率 (-0.1 = -10%)


def compute_ga4_deltas(cur: GA4Metrics, prev: GA4Metrics) -> list[Delta]:
    pairs = [
        ("PV", cur.page_views, prev.page_views),
        ("UU", cur.active_users, prev.active_users),
        ("セッション", cur.sessions, prev.sessions),
        ("エンゲージセッション", cur.engaged_sessions, prev.engaged_sessions),
        ("直帰率", cur.bounce_rate, prev.bounce_rate),
        ("平均セッション時間", cur.avg_session_duration, prev.avg_session_duration),
        ("コンバージョン", cur.conversions, prev.conversions),
        ("CVR", cur.conversion_rate, prev.conversion_rate),
    ]
    return [
        Delta(label=l, current=c, previous=p, change=c - p, change_pct=pct_change(c, p))
        for l, c, p in pairs
    ]


def compute_gsc_deltas(cur: SearchTotals, prev: SearchTotals) -> list[Delta]:
    pairs = [
        ("クリック", cur.clicks, prev.clicks),
        ("表示回数", cur.impressions, prev.impressions),
        ("CTR", cur.ctr, prev.ctr),
        ("平均順位", cur.position, prev.position),
    ]
    return [
        Delta(label=l, current=c, previous=p, change=c - p, change_pct=pct_change(c, p))
        for l, c, p in pairs
    ]


@dataclass
class Alert:
    severity: str  # "warning" / "info"
    metric: str
    message: str


def check_alerts(
    ga4_cur: GA4Metrics,
    ga4_prev: GA4Metrics | None,
    gsc_cur: SearchTotals | None,
    gsc_prev: SearchTotals | None,
    thresholds: Thresholds,
) -> list[Alert]:
    alerts: list[Alert] = []

    if ga4_cur.bounce_rate >= thresholds.bounce_rate_warning:
        alerts.append(
            Alert(
                "warning",
                "直帰率",
                f"直帰率が {ga4_cur.bounce_rate:.1%} で警告閾値 {thresholds.bounce_rate_warning:.0%} を超えています。",
            )
        )
    if 0 < ga4_cur.conversion_rate < thresholds.conversion_rate_warning:
        alerts.append(
            Alert(
                "warning",
                "CVR",
                f"CVR が {ga4_cur.conversion_rate:.2%} で警告閾値 {thresholds.conversion_rate_warning:.2%} を下回っています。",
            )
        )
    if ga4_cur.conversions == 0 and ga4_cur.sessions > 0:
        alerts.append(
            Alert(
                "warning",
                "CV",
                f"期間中にコンバージョンが 0 件です (セッション {ga4_cur.sessions}) — 設定されたキーイベントが発火しているか確認してください。",
            )
        )
    if ga4_prev is not None:
        uu_change = pct_change(ga4_cur.active_users, ga4_prev.active_users)
        if uu_change <= thresholds.uu_drop_pct:
            alerts.append(
                Alert(
                    "warning",
                    "UU",
                    f"UU が前期比 {uu_change:.1%} で閾値 {thresholds.uu_drop_pct:.0%} 以下に減少しています。",
                )
            )
    if gsc_cur and gsc_prev and gsc_prev.position > 0:
        pos_change = gsc_cur.position - gsc_prev.position
        if pos_change >= 2.0:
            alerts.append(
                Alert(
                    "warning",
                    "検索順位",
                    f"平均検索順位が {gsc_prev.position:.1f} → {gsc_cur.position:.1f} に悪化しました (+{pos_change:.1f})。",
                )
            )
    return alerts
