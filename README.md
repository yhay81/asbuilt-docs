# Asbuilt Docs

完成したソフトウェアを基に、案件に必要な日本語の開発資料を選ぶCodex／Claude Codeプラグインです。要件定義書・テスト仕様書・テスト結果報告書を別々のMarkdownとして生成し、要件・実装・試験・承認の根拠をたどれます。

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

新しいセッションでCodexはAsbuilt Docsを選択し、Claude Codeは `/asbuilt-docs:reconstruct` で呼び出します。調べたいソフトウェアの作業フォルダーで、たとえば次のように依頼してください。

> CSV一括登録を引き継ぎます。正常な9行と入力エラーの1行を渡すと何が起こりますか。現行仕様、業務側に確認すること、受入テスト案をそれぞれ根拠付きでMarkdownにしてください。

> このソフトウェアを運用部門に引き継ぎます。必要な成果物を選び、要件定義書、テスト仕様書、テスト結果報告書と運用手順書を作ってください。実施状況や承認が分からない箇所は記入欄として残してください。

## 手元でサンプルを試す

リポジトリのルートで次を実行すると、同梱した小さな取込処理と台帳から資料を生成できます。必要なものはPython 3.9以降です。

```sh
python3 plugins/asbuilt-docs/skills/reconstruct/scripts/documents.py plan examples/csv/project.json
python3 plugins/asbuilt-docs/skills/reconstruct/scripts/documents.py build examples/csv/project.json --root examples/csv --out delivery-csv
```

例の出力は `成果物一覧.md` と指定した3文書です。案件の条件に応じて設計、試験計画、移行、運用などを加えられます。大きなシステムでは機能別に台帳を作り、部分生成してから全体の目次と結果を集計できます。従来の `ledger.py render`、根拠照合、版間の影響確認も利用できます。[案件設定と生成方法](plugins/asbuilt-docs/skills/reconstruct/references/project.md) ／ [台帳と根拠の照合](plugins/asbuilt-docs/skills/reconstruct/references/ledger.md) ／ [工程ごとの資料](plugins/asbuilt-docs/skills/reconstruct/references/deliverables.md)

共通パッケージはAgent Plugins 1.0.0、共有する手順はAgent Skills形式です。CodexとClaude Codeが同じスキルを読み込みます。[Agent Pluginsの公開仕様](https://github.com/agentplugins/agent-plugins-spec/blob/v1.0.0/spec/1.0.0.md) ／ [Agent Skills](https://agentskills.io/specification)
