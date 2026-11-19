# 台帳と検証

`scripts/ledger.py` はPython 3.9以降の標準ライブラリで動く。以下の `ledger.py` には、読み込まれたスキルの `scripts/ledger.py` のパスを使う。

## 記録する内容

新しく作る台帳はUTF-8のJSONで、`schema_version`（整数の2）、`revision`（対象版の文字列）、`records`（項目の配列）を持つ。GitHub上の実装にリンクする場合は `repository` にリポジトリURL、`revision` にコミットの40桁の識別子を指定する。

各項目には `id`、`type`、`status`、日本語の `text` を記録する。根拠は `evidence` の配列、依存先の識別番号は `depends_on` の配列にする。番号は版をまたいで維持する。

| type | status | 記録の条件 |
|---|---|---|
| behavior | observed | 実装・設定・実際の観察のいずれかを行単位で示す。観察には条件を添える。 |
| requirement | proposed / approved | 候補から承認済みに移すには、判断者と日付を持つ意思決定の記録を結ぶ。 |
| test | planned / passed / failed | 案には期待値を書く。合否には、対象版で実施した同じ試験IDの結果記録を結ぶ。報告書の試験IDが台帳の `id` と異なる場合は、項目に `test_id` を指定する。 |
| question | open | `owner` に確認先を記す。未定ならその旨を書く。 |
| conflict | open | 食い違う二つ以上の項目を `depends_on` に指定する。 |

## 根拠を取得する

対象版の資料を一つの作業フォルダーに置く。パスはそのフォルダーからの相対パス、行番号は1から始まり終了行を含む。改行を統一した選択範囲のSHA-256で、以前の引用が今も同じかを確認する。

```sh
python3 ledger.py cite --root . --kind code src/import_rows.py 3 5
python3 ledger.py cite --root . --kind decision --by 運用責任者 --date 2026-11-19 decisions/acceptance.md 6 9
python3 ledger.py cite --root . --kind run --revision v2 --test-id ERR-DISPLAY --result passed reports/run-v2.txt 1 4
```

出力されたJSONを該当項目の `evidence` に追加する。使える根拠の種類は `code`、`config`、`observation`、`document`、`decision`、`run`、`test_code`。画面やPDFの場合は、元の資料の識別子、ページ、日時、観察条件が分かるメモを作り、該当行を引用する。

## 照合して出力する

```sh
python3 ledger.py check ledger.json --root .
python3 ledger.py render ledger.json --root .
python3 ledger.py render ledger.json --root . --section requirement
python3 ledger.py impact old-ledger.json new-ledger.json --root .
```

`check` と `render` は根拠の存在、該当行、承認や合否に必要な記録、参照先を検査する。記述が根拠の意味を正しく表すかは元の箇所を読み合わせる。`render` の出力先は標準出力。保存先を新しいファイルにすれば既存の手書き資料と比較できる。

試験の実行記録は、元の報告書で実際に使われた試験IDを転記する。実施記録との対応が分からなければ、試験は `planned` にして確認事項を残す。旧形式の台帳（整数の1）も読み込める。旧形式で試験IDが未記録の合否には「試験IDは要確認」と表示し、影響一覧の `unlinked_test_results` に含める。形式2への移行時は記録を見直し、対応が確かめられた試験にIDを追記する。

`impact` は項目の追加・削除・変更、根拠の変化、旧版でしか試していない合否、依存関係をたどった影響先をJSONで返す。旧版の台帳と新版の証拠があれば実行できる。運用の変更だけを調べる場合も、意思決定の記録を更新して同じ手順を使う。
