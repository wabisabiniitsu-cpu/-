# ハリナビ コラム記事 画像生成ルール（Canva連携・秘書実行）

記事担当が画像のaltテキスト・生成内容を提案し、秘書（このセッション）がCanva連携（`mcp__Canva__generate-image`）を使って実際の画像生成まで行う。
2026-09-29 更新：従来のChatGPT手動生成（社長がプロンプトをコピペして生成・アップロード）から、秘書がセッション内で直接生成する運用に変更した。ログイン不要・数秒〜十数秒で1枚生成できることを実機で確認済み。
生成後、社長が内容を確認しサイトへアップロードする（アップロード作業自体は引き続き社長 or 別途自動化を検討）。

---

## 共通条件

- サイトURL：https://www.harinavi.jp/
- ブランドカラー：ホワイト×ベージュを基調とした空間。アクセントカラーはマゼンタピンク（#c70070）を、小物・花・タオルの刺繍などに「さりげなく1点だけ」配置
- ライティング：窓からの明るい自然光（ハイキー）。透明感・清潔感のあるプロフェッショナルな商業写真スタイル。背景は美しくぼかす
- サイズ：横長。Canvaの`aspectRatio`は元のサイズ仕様（1200×630 ≒ 1.9:1）に最も近い `LANDSCAPE_2_1` を指定する

## 人物の描写ルール

- 登場人物（施術者・クライアント）は全員30代〜40代の日本人女性（実写）
- 人物は毎回別人でよい。手元だけの描写でも女性と分かるようにする
- プロの一眼レフで撮影したような、加工感のないリアルな質感（肌のテクスチャ・光の反射を自然に）

## 日本語表示の厳格ルール（最重要）

- 画像内に看板・ノート・本の表紙・ラベル等の文字を入れることは**原則禁止**とする
- 画像生成AI（Canva含む）は正確な日本語を描写できないため、プロンプトには必ず「No text, no signage, no writing, no labels anywhere in the image.」等、文字を一切入れない旨を明記する
- 万一文字入りの案が必要になった場合は、画像生成では入れず、後工程（Canvaのデザイン編集機能等）でテキストを別途重ねる方法を検討し、社長に確認してから行う

---

## 実行フロー

1. 記事担当が、TOP画像・各H2の画像それぞれについて「日本語のaltテキスト（生成する内容の要約）」を提案する
2. 秘書が、altテキストと下記テンプレートをもとに**英語の生成プロンプト**を組み立てる（Canvaの画像生成は英語プロンプトの方が意図通りの結果になりやすいため、日本語altを英語descriptionに翻訳して使う）
3. 秘書が `mcp__Canva__generate-image` を呼び出す（`aspectRatio: LANDSCAPE_2_1`）
4. `mcp__Canva__get-generate-image-job` でジョブ完了を確認し、生成結果（プレビュー画像＋Canvaで開くリンク）を社長に提示する
5. 社長がOKを出したら、Canvaのリンクからダウンロードしてサイトへアップロードする（この最終アップロード工程は現状まだ社長手動）
6. NGの場合は、プロンプトの表現を調整して2〜4を繰り返す

## TOP画像（記事ごとに1枚）

プロンプトの型（英語・Canva用）：
```
Professional commercial photography, high-key natural window light, white and beige toned
clinic/spa interior background, softly blurred. [記事タイトル・テーマに沿った具体的なシーン描写を
英語で記述]. Realistic DSLR photo quality, natural skin texture, no visible retouching.
A small magenta pink (#c70070) accent color detail on a towel or small flower arrangement
nearby, used sparingly as the only accent color. No text, no signage, no writing, no labels
anywhere in the image. Landscape composition.
```
- 過去に生成した画像がある場合は、その `media_id` を `imageReferences` に渡してテイストを踏襲できる（Canvaの画像編集/参照生成機能）

## 記事内画像（H2ごとに1枚、altテキストの内容に沿って生成）

プロンプトの型（英語・Canva用）：
```
Professional commercial photography, high-key natural window light, white and beige toned
background, softly blurred. [altテキストの内容を具体的な英語のシーン描写に翻訳して記述]. A Japanese
woman in her 30s-40s [場面に応じた動作・表情]. Realistic DSLR photo quality, natural skin
texture, no visible retouching. A small magenta pink (#c70070) accent color detail used
sparingly as the only accent color. No text, no signage, no writing, no labels anywhere in
the image. Landscape composition.
```
- 1枚ずつ `mcp__Canva__generate-image` で生成する
- 生成例（2026-09-29、セルフケア関連記事の記事内画像として実機生成・動作確認済み）：
  「自宅で美容鍼のセルフケアを行う女性のイメージ」相当のaltに対し、施術ベッドでリラックスして鍼を受ける女性のシーンで生成成功
