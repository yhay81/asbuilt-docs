# Asbuilt Docs

完成したソフトウェアを基に、日本語の要件定義書・設計書・テスト仕様書や引継資料を作るCodex／Claude Codeプラグインです。何が今の動きか、業務上誰が決めたのか、どの試験を実施したのかを、それぞれの根拠に結び付けます。

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

## 手元でサンプルを試す

リポジトリのルートで次を実行すると、同梱した小さな取込処理と台帳から資料を生成できます。必要なものはPython 3.9以降です。

```sh
python3 plugins/asbuilt-docs/skills/reconstruct/scripts/ledger.py render examples/csv/ledger.json --root examples/csv
```

初版はMarkdownの出力、根拠の照合、旧版との差分確認に対応しています。顧客の指定書式があれば、必要な項目を照らし合わせて使えます。[台帳の形式とコマンド](plugins/asbuilt-docs/skills/reconstruct/references/ledger.md)

共通パッケージはAgent Plugins 1.0.0、共有する手順はAgent Skills形式です。CodexとClaude Codeが同じスキルを読み込みます。[Agent Pluginsの公開仕様](https://github.com/agentplugins/agent-plugins-spec/blob/v1.0.0/spec/1.0.0.md) ／ [Agent Skills](https://agentskills.io/specification)
