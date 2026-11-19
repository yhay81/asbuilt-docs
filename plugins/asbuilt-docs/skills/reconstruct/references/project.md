# 案件ごとに選んで生成する

案件設定と各モジュールの台帳はUTF-8のJSON。Python 3.9以降で、スキルの `scripts/documents.py` を呼ぶ。ソフトウェア・出力・案件設定はそれぞれ別の位置に置ける。

```json
{
  "title": "購買業務",
  "revision": "demo-v1",
  "purpose": "申請と集計を引き継ぐ",
  "scope": "申請サービスと月次集計",
  "activities": ["operations"],
  "selection_reasons": {"operations": "運用部門が申請処理の引継ぎを受ける。"},
  "modules": [
    {"id": "orders", "name": "購買申請", "ledger": "ledgers/orders.json"},
    {"id": "summary", "name": "月次集計", "ledger": "ledgers/summary.json"}
  ],
  "links": [{"from": "summary/R-01", "to": "orders/F-01"}]
}
```

必須は `title`、`revision`、`modules`。各台帳は同じ対象版を持つ。台帳のパスは案件設定の親、根拠のパスは共通の `--root` を基準とする。モジュールIDは英小文字・数字で始め、残りにはハイフンとアンダースコアも使える。各台帳内で一意の項目番号を付ける。複数モジュールで同じ番号を使える。モジュール間の依存は上例のように `links` に書く。

## 成果物の選定

通常は要件定義・基本設計・詳細設計・テスト計画・テスト仕様・テスト結果・対応表の7種。案件の業務条件を `activities` に指定すると対応する資料が加わる。概要と選定理由は毎回「成果物一覧.md」に載る。

| 条件 | 追加資料のID |
|---|---|
| acceptance／業務受入、operations／運用引継ぎ、release／本番導入 | acceptance、operations、release |
| migration／移行、planning／開発計画、procurement／調達 | migration、project-plan、procurement |
| integration／外部連携、quality／非機能、changes／変更管理、retirement／終了 | interfaces、nonfunctional、changes、retirement |

基本7種のIDは `requirements`、`basic-design`、`detailed-design`、`test-plan`、`test-spec`、`test-report`、`trace`。個別の追加と除外には `include`・`exclude` の配列を使う。納品物を指定された場合は `"only":["requirements","test-spec","test-report"]` のように列挙する。

## 資料ごとに埋める欄

通常の[根拠台帳](ledger.md)に次の任意項目を加える。既存の形式1・2の台帳も読み込める。目的や見出しは案件の整理に使い、業務の事実や実績には出典を付ける。

| 場所 | 項目 |
|---|---|
| requirement | `title`、`category`（例　非機能要件）、`actor`、`criteria`（受入条件の文字列配列）。`text` は要件本文。承認は decision 根拠で扱う。 |
| behavior | `inputs`、`outputs`、`exceptions`（文字列配列）は詳細設計の処理別の入力・更新・例外に反映する。 |
| test | `title`、`level`、`preconditions` と `steps`（文字列配列）、`expected`（期待結果）。`depends_on` には関連する要件や設計の番号を置く。 |
| planned の test | 今回実施していないことが確認できた場合だけ `"execution":"not_run"`。情報がなければ省略し「実施状況不明」とする。 |
| test の run 根拠 | 対象版、試験ID、合否、引用範囲に加え、記録にあれば `actual`（観測）、`environment`、`executed_at`、`issue`（不具合や残件）を文字列で記入する。 |

仕様書には操作と期待値、結果報告書には同じ版・試験IDで照合できた実績を載せる。古い形式で試験IDが欠けていれば「照合待ち」として表示する。構造化された実測がなければ観測欄は空く。業務受入の判断者・日付は本人の記録で確定する。

追加資料や組織独自の節には、モジュール台帳の最上位に `"sections":{"operations":{"障害時の一次対応":["F-01","Q-01"]}}` のように書く。指定した台帳項目の内容・状態・根拠をその節に載せる。該当する情報が不足していれば記入欄が残る。テスト仕様書・結果報告書・対応表は上記の構造化欄と関連番号から生成する。同じ試験はモジュール内で1件にし、複数の要件を確かめるときは依存先を列挙する。モジュール共通の試験も一つの台帳に置いて `links` から参照する。

## 実行と大規模案件

```sh
python3 /path/to/skill/scripts/documents.py inventory --root /path/to/repo --revision HEAD --depth 2
python3 /path/to/skill/scripts/documents.py plan project.json
python3 /path/to/skill/scripts/documents.py build project.json --root /path/to/source --module orders --out review-orders
python3 /path/to/skill/scripts/documents.py build project.json --root /path/to/source --out delivery-v1
```

`inventory` はGitの固定コミットからディレクトリ別の追跡ファイル数を集計する。引用するコードは同じ版を展開した作業場所で確認する。`--module` は複数回指定でき、選択した台帳とその根拠だけを開く。関連先が未収録の場合は一覧で件数を示し、全体生成時に両端を照合する。多数の台帳は順に検査・描画し、機能ごとの本文と全体の目次・試験集計を作る。調査の再開には既存のモジュール台帳を使える。

同じ内容は同じ保存先で再実行できる。内容が異なる場合は新しい版の保存先を指定し、手書きの補記や以前の判定を残す。途中で照合に失敗した場合は完成版を配置しない。
