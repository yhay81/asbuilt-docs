# Asbuilt Docs

完成したソフトウェアから、日本の開発工程で使う一貫した資料一式を復元するCodex／Claude Codeプラグインです。開発者が資料だけで同じ動きを作り直せること、承認者が合意した仕様と対象版の実測を照合できることを目指しています。

## インストール

**Codex**

```sh
codex plugin marketplace add yhay81/asbuilt-docs
codex plugin add asbuilt-docs@asbuilt-market
```

**Claude Code**

```sh
claude plugin marketplace add yhay81/asbuilt-docs
claude plugin install asbuilt-docs@asbuilt-market
```

新しいセッションでCodexはAsbuilt Docsを選択し、Claude Codeは `/asbuilt-docs:reconstruct` で呼び出します。調べたいソフトウェアの作業フォルダーで依頼します。

> このソフトウェアの開発資料一式を復元してください。

開発者は要件・設計・試験仕様をたどり、入力、操作の順番、正常時と異常時の結果を確認できます。承認者は各要求について、合意した受入条件、対象版で実施した試験、その観測結果を照合します。承認済みの仕様や実行記録が手元にあれば、対象ソフトウェアと一緒に渡してください。資料で確認できた現行動作、仕様との食い違い、人の判断が必要な事項を記録します。

一式の読み始めに、製品の役割と業務目的、関係者とコンポーネントを説明します。インフラ構成・ソフトウェア構成・業務データの流れを別々の図で示し、画面を持つアプリには対象版を操作したスクリーンショットを添えます。図、画像、根拠の抜粋は納品先だけで開けます。[概要と図版の入力・生成方法](plugins/asbuilt-docs/skills/reconstruct/references/overview.md)

再実装の基準は、同じ入力・操作で、利用者や連携先から見える結果が一致することです。実装言語や内部のデータ構造は選べます。仕様と結果の対応を確かめる際は、IPAの要求管理とデジタル庁の受入テストの考え方を参考にしています。[IPA「AI時代の要求管理ハンドブック」第11章](https://www.ipa.go.jp/digital/kaihatsu/rqr7mi000000f5up-att/req-mgmt-hb.pdf#page=96) ／ [デジタル庁 DS-120 第3編第7章](https://www.digital.go.jp/assets/contents/node/basic_page/field_ref_resources/e2a06143-ed29-4f1d-9c31-0f06fca67afc/0af5ce68/20260715_resources_standard_guidelines_guideline_05.pdf#page=358)

復元中に追加で試験した場合は、観測した結果と、その記録を正式な受入に使えるかをそれぞれ示します。原票の該当箇所を資料に収め、納品フォルダー内で参照先のファイルを開けるかを点検します。

## 手元でサンプルを試す

リポジトリのルートで次を実行すると、同梱した小さな取込処理と台帳から資料を生成できます。必要なものはPython 3.9以降です。

```sh
python3 plugins/asbuilt-docs/skills/reconstruct/scripts/documents.py plan examples/csv/project.json
python3 plugins/asbuilt-docs/skills/reconstruct/scripts/documents.py build examples/csv/project.json --root examples/csv --out delivery-csv
```

例の出力は `成果物一覧.md` と指定した3文書です。案件の条件に応じて設計、試験計画、移行、運用などを加えられます。大きなシステムでは機能別に台帳を作り、部分生成してから全体の目次と結果を集計できます。従来の `ledger.py render`、根拠照合、版間の影響確認も利用できます。[案件設定と生成方法](plugins/asbuilt-docs/skills/reconstruct/references/project.md) ／ [台帳と根拠の照合](plugins/asbuilt-docs/skills/reconstruct/references/ledger.md) ／ [工程ごとの資料](plugins/asbuilt-docs/skills/reconstruct/references/deliverables.md)

共通パッケージはAgent Plugins 1.0.0、共有する手順はAgent Skills形式です。CodexとClaude Codeが同じスキルを読み込みます。[Agent Pluginsの公開仕様](https://github.com/agentplugins/agent-plugins-spec/blob/v1.0.0/spec/1.0.0.md) ／ [Agent Skills](https://agentskills.io/specification)
