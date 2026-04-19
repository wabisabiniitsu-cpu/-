# ハリナビ マーケティング分析ツール

自社ポータル [ハリナビ](https://www.harinavi.jp/) のマーケターとして、毎日自動で指標を計測し、
改善案・追加コンテンツの提案までを生成する内部ツールです。

- **データソース**: GA4 Data API / Google Search Console API
- **主要指標**: PV / UU / セッション / 直帰率 / コンバージョン率 / 検索クリック / 表示回数 / 平均検索順位
- **出力**: Markdown + HTML レポート (`reports/` 以下)、SMTP メール送信、対話型 Q&A (`chat` サブコマンド)
- **分析エンジン**: Claude Opus 4.7 (`claude-opus-4-7`) + 適応的 thinking + プロンプトキャッシュ
- **スケジュール**: cron で毎日 1 回 `run-daily` を実行 (例: `scripts/cron.example`)

---

## 構成

```
src/
  main.py              # CLI エントリ (report / run-daily / chat)
  pipeline.py          # 収集 → 分析 → レポ生成の一連処理
  config.py            # config.yaml / .env 読み込み
  collectors/
    ga4.py             # GA4 Data API (PV / UU / 直帰率 / CV / ページ / チャネル)
    search_console.py  # Search Console API (クエリ / 順位 / CTR)
  storage/db.py        # 日次 KPI を SQLite に保存して前期比較に使う
  analyzer/
    metrics.py         # 前期比較・アラート判定
    insights.py        # Claude でマーケター視点のコメント / 改善案生成
  report/
    generator.py       # Jinja2 でレポ整形
    templates/         # daily.md.j2 / daily.html.j2
  notifier/email.py    # SMTP で HTML メール送信
  chat/assistant.py    # ターミナルでの対話型アナリスト
tests/test_metrics.py  # 分析ロジック単体テスト
scripts/cron.example   # 日次 cron 例
```

---

## セットアップ

### 1. 依存インストール

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 2. Google API 認証 (サービスアカウント方式)

1. Google Cloud で新しいサービスアカウントを作成し、JSON キーをダウンロード
2. **GA4**: GA4 プロパティ > 管理 > プロパティ アクセス管理 で、上記サービスアカウントのメールアドレスを "閲覧者" として追加
3. **Search Console**: <https://search.google.com/search-console/users> で、対象サイトに同じサービスアカウントを "所有者" または "フル" 権限で追加
4. Google Cloud で以下 API を有効化
   - Google Analytics Data API
   - Search Console API

### 3. GA4 プロパティ ID を確認

`config.yaml.example` の `measurement_id` は gtag 用の `G-XXXXXXXXXX` です。
**GA4 Data API には「数値のプロパティ ID」が必要** です。
GA4 管理画面 > プロパティ設定 で確認できる数値 (例: `123456789`) を
`ga4_property_id` に設定してください。

### 4. 設定ファイル

```bash
cp config.yaml.example config.yaml
cp .env.example .env
# 両方を編集して値を埋める
```

`.env` に設定する主な環境変数:

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service_account.json
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=notify@example.com
SMTP_PASSWORD=...
SMTP_FROM=notify@example.com
```

### 5. 動作確認

```bash
# メール送信なしでレポ生成のみ
python -m src.main report

# 日次フル実行 (レポ生成 + メール送信)
python -m src.main run-daily

# 最新レポートに対して Claude に質問する
python -m src.main chat
```

生成物は `reports/harinavi-YYYY-MM-DD.md` / `.html`、
履歴は `data/metrics.db` に保存されます。
`reports/latest.json` は `chat` サブコマンドがコンテキストとして読み込みます。

---

## 日次自動実行 (cron)

`scripts/cron.example` を参考に `crontab -e` へ登録します。
毎朝 8:00 (JST) に前日分を集計 → HTML メール送信する想定です。

```
0 8 * * * cd /opt/harinavi-marketing && \
  set -a && . ./.env && set +a && \
  /opt/harinavi-marketing/.venv/bin/python -m src.main run-daily \
    >> /var/log/harinavi-marketing.log 2>&1
```

---

## レポート内容

毎回のレポートには以下が含まれます:

1. **サマリ指標** (GA4): PV / UU / セッション / 直帰率 / CVR を当期・前期・増減で
2. **Search Console サマリ**: クリック / 表示 / CTR / 平均順位
3. **アラート**: 直帰率 70% 超え / CVR 0.5% 未満 / UU -20% / 順位悪化 など (閾値は `config.yaml`)
4. **上位ページ** (PV 順)
5. **流入チャネル別 サマリ** (Organic / Direct / Referral / ...)
6. **検索クエリ**: クリック上位 + 「順位が上昇したクエリ」(翌週の狙い候補)
7. **マーケターからの示唆**: Claude Opus 4.7 が「良かった点 / 課題 / 改善案 / 来週のウォッチ項目」を
   根拠となる数値付きで提案

---

## 対話型アナリスト (`chat`)

`python -m src.main chat` で起動すると、直近レポートの JSON を
システムプロンプトに載せた Claude と対話できます。

プロンプトキャッシュを効かせているため、会話を続けるほど 1 問あたりのコストが下がります。

例:
```
あなた > 今週 CVR が下がった一番の要因は?
あなた > 上位クエリで「鍼灸 東京」の順位を上げたい。次に書くべき記事は?
あなた > generate_lead が 0 件なのはなぜ? 確認ポイントを教えて
```

---

## テスト

```bash
pip install pytest
python -m pytest tests/ -q
```

`tests/test_metrics.py` は Google / Anthropic モジュールが
未インストールでも走るよう、コレクタの外部依存はメソッド内で遅延 import しています。

---

## トラブルシュート

- **`ga4_property_id は数値である必要があります`**: 測定 ID (`G-QBB53CDK4P`) をそのまま入れていないか確認
- **`403 PERMISSION_DENIED` (GA4)**: サービスアカウントを GA4 プロパティの閲覧者に追加する
- **Search Console の取得に失敗**: サイトオーナー権限でサービスアカウントを追加、かつ `site_url` は末尾スラッシュ込みで一致させる
- **`budget_tokens` のエラー**: Opus 4.7 は `thinking: {type: "adaptive"}` のみ対応。本ツールは既にそう設定済み
- **CV が 0 件で警告**: GA4 で該当イベントを「キーイベント」としてマークしているか、`conversion_events` が GA4 側の名前と一致しているかを確認
