"""分析ロジックの単体テスト。"""
from __future__ import annotations

from datetime import date

from src.analyzer.metrics import (
    check_alerts,
    comparison_window,
    compute_ga4_deltas,
    pct_change,
)
from src.collectors.ga4 import GA4Metrics
from src.collectors.search_console import SearchTotals
from src.config import Thresholds


def _ga4(pv: int, uu: int, sess: int, engaged: int, bounce: float, cv: int) -> GA4Metrics:
    return GA4Metrics(
        start=date(2026, 4, 1),
        end=date(2026, 4, 7),
        page_views=pv,
        active_users=uu,
        sessions=sess,
        engaged_sessions=engaged,
        bounce_rate=bounce,
        avg_session_duration=90.0,
        conversions=cv,
        conversion_rate=(cv / sess) if sess else 0.0,
    )


def test_pct_change_zero_previous():
    assert pct_change(10, 0) == 1.0
    assert pct_change(0, 0) == 0.0


def test_pct_change_basic():
    assert abs(pct_change(110, 100) - 0.1) < 1e-9
    assert abs(pct_change(80, 100) + 0.2) < 1e-9


def test_comparison_window_wow():
    cs, ce, ps, pe = comparison_window(date(2026, 4, 14), "week_over_week")
    assert cs == date(2026, 4, 8) and ce == date(2026, 4, 14)
    assert ps == date(2026, 4, 1) and pe == date(2026, 4, 7)


def test_comparison_window_dod():
    cs, ce, ps, pe = comparison_window(date(2026, 4, 14), "day_over_day")
    assert cs == ce == date(2026, 4, 14)
    assert ps == pe == date(2026, 4, 13)


def test_compute_ga4_deltas_includes_cvr():
    cur = _ga4(1000, 500, 600, 420, 0.55, 6)
    prev = _ga4(900, 450, 500, 320, 0.60, 3)
    deltas = compute_ga4_deltas(cur, prev)
    labels = [d.label for d in deltas]
    assert "PV" in labels and "UU" in labels and "CVR" in labels
    cvr = next(d for d in deltas if d.label == "CVR")
    assert cvr.current > cvr.previous


def test_alerts_high_bounce_and_low_cvr():
    thresholds = Thresholds(
        bounce_rate_warning=0.70, conversion_rate_warning=0.005, uu_drop_pct=-0.20
    )
    cur = _ga4(1000, 500, 600, 200, 0.80, 1)  # bounce 80% / CVR ~0.17%
    prev = _ga4(1000, 700, 600, 400, 0.55, 10)
    gsc_cur = SearchTotals(date(2026, 4, 1), date(2026, 4, 7), 100, 5000, 0.02, 12.0)
    gsc_prev = SearchTotals(date(2026, 3, 25), date(2026, 3, 31), 120, 5000, 0.024, 9.0)
    alerts = check_alerts(cur, prev, gsc_cur, gsc_prev, thresholds)
    metrics = {a.metric for a in alerts}
    assert "直帰率" in metrics
    assert "CVR" in metrics
    # UU が 700 → 500 で -28% → 閾値 -20% を下回る
    assert "UU" in metrics
    # 順位 9.0 → 12.0 (+3.0) で警告
    assert "検索順位" in metrics
