"""Claude (Opus 4.7) を使ってマーケター視点の示唆と改善案を生成する。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from anthropic import Anthropic

from ..config import ClaudeConfig


# プロンプトキャッシュを効かせるため、変化しない「役割」を先頭に固定。
_SYSTEM_PROMPT = """あなたはハリナビ (https://www.harinavi.jp/) 専属のシニアグロースマーケターです。
鍼灸・整体・リラクゼーションに関する情報ポータルで、KPI はリード獲得 (contact / generate_lead) です。

入力として直近期間の GA4 / Search Console 指標、前期比、上位ページ、チャネル別サマリ、
検索クエリ、アラートが JSON で与えられます。マーケター視点で以下を日本語で出力してください:

1. **サマリ**: 3〜5 行で、期間中に何が起きたかを事実ベースで要約
2. **良かった点**: 伸びている指標・チャネル・クエリを具体的な数値で
3. **課題・リスク**: 悪化指標、アラート、離脱の多いページ、順位が落ちたクエリ
4. **改善 / 追加アクション案** (優先度付き / 5 件程度):
   - CRO (LP 改修 / CTA / 内部導線)
   - SEO (狙いクエリ・記事リライト・新規コンテンツ)
   - 計測 / キーイベント設定
   - UX / 直帰率対策
   各案には「根拠 (どの数値から判断したか)」と「想定効果」を添えてください
5. **次期のウォッチ項目**: 来週の定点観測ポイントを 3 点

数字は信頼区間・過学習に注意し、サンプル数が小さい指標では断定を避けること。
可能な限り、特定のページパスやクエリ文字列を示し、即実行できる具体性を持たせること。
"""


@dataclass
class InsightResult:
    markdown: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int


def build_payload(
    site_name: str,
    site_url: str,
    comparison: str,
    period: dict,
    ga4_current: dict,
    ga4_previous: dict | None,
    gsc_current: dict | None,
    gsc_previous: dict | None,
    deltas_ga4: list[dict],
    deltas_gsc: list[dict],
    top_pages: list[dict],
    channels: list[dict],
    top_queries: list[dict],
    rising_queries: list[dict],
    alerts: list[dict],
) -> dict[str, Any]:
    return {
        "site": {"name": site_name, "url": site_url},
        "comparison_mode": comparison,
        "period": period,
        "ga4": {"current": ga4_current, "previous": ga4_previous, "deltas": deltas_ga4},
        "search_console": {
            "current": gsc_current,
            "previous": gsc_previous,
            "deltas": deltas_gsc,
        },
        "top_pages": top_pages,
        "channels": channels,
        "search_queries": {"top": top_queries, "rising": rising_queries},
        "alerts": alerts,
    }


def _as_dict(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _as_dict(v) for k, v in obj.items()}
    return obj


def generate_insights(
    client: Anthropic,
    claude_cfg: ClaudeConfig,
    payload: dict[str, Any],
) -> InsightResult:
    """Claude Opus 4.7 で分析コメントを生成する。"""
    user_content = (
        "以下は最新の指標データです。マーケター視点で分析してください。\n\n"
        "```json\n" + json.dumps(_as_dict(payload), ensure_ascii=False, indent=2) + "\n```"
    )

    # 役割 (system) はキャッシュ対象 → 毎日同一プレフィックスを再利用してコスト削減。
    system = [
        {
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    with client.messages.stream(
        model=claude_cfg.model,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        output_config={"effort": claude_cfg.effort},
        system=system,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        final = stream.get_final_message()

    text_parts = [b.text for b in final.content if getattr(b, "type", None) == "text"]
    markdown = "\n\n".join(text_parts).strip()

    usage = final.usage
    return InsightResult(
        markdown=markdown,
        model=final.model,
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
    )
