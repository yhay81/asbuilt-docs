"""Japanese delivery documents rendered from one verified module ledger."""

import re
from collections import Counter, defaultdict
from urllib.parse import quote

from ledger import LABELS, require

# name, reader, selection activity (None is part of the default set), editable sections
CATALOG = {
    "requirements": (
        "要件定義書",
        "業務責任者・開発担当",
        None,
        ("業務の目的と対象", "利用者・制約", "非機能要件"),
    ),
    "basic-design": (
        "基本設計書",
        "利用部門・開発担当",
        None,
        ("業務フローと画面", "入出力・権限・例外"),
    ),
    "detailed-design": (
        "詳細設計書",
        "開発・保守担当",
        None,
        ("処理とデータ構造", "更新条件・異常処理"),
    ),
    "test-plan": (
        "テスト計画書",
        "品質担当",
        None,
        ("対象範囲・試験レベル", "環境・体制・日程", "開始・終了条件"),
    ),
    "test-spec": ("テスト仕様書", "試験担当", None, ()),
    "test-report": ("テスト結果報告書", "品質担当・受入担当", None, ()),
    "trace": ("要件・設計・テスト対応表", "レビュー・保守担当", None, ()),
    "acceptance": ("受入判定記録", "受入責任者", "acceptance", ("判断材料・残件",)),
    "operations": (
        "操作・運用保守手順書",
        "利用者・運用担当",
        "operations",
        ("日常の操作", "監視・障害対応", "バックアップ・復旧", "連絡先と引継ぎ"),
    ),
    "release": (
        "リリース・切戻し手順書",
        "リリース担当",
        "release",
        ("対象環境と構成", "配布・切替手順", "切戻し条件と手順", "実施記録"),
    ),
    "migration": (
        "データ移行計画・結果",
        "移行責任者",
        "migration",
        ("移行元と移行先", "変換と照合", "停止・切戻し条件", "実施記録"),
    ),
    "project-plan": (
        "開発計画書",
        "プロジェクト責任者",
        "planning",
        ("目的・体制と範囲", "予算・日程", "品質・リスク管理"),
    ),
    "procurement": (
        "調達・納品仕様書",
        "発注者・受注者",
        "procurement",
        ("調達範囲", "納品一覧・書式", "責任分担と検収条件"),
    ),
    "interfaces": (
        "外部インターフェース仕様書",
        "連携先・開発担当",
        "integration",
        ("連携先・責任分担", "入出力と項目", "異常時の再処理"),
    ),
    "nonfunctional": (
        "非機能要件・検証項目",
        "運用・品質担当",
        "quality",
        ("性能・負荷", "可用性・復旧", "セキュリティ・利用条件", "測定と判定"),
    ),
    "changes": (
        "課題・変更管理表",
        "開発・保守担当",
        "changes",
        ("課題と影響先", "変更判断と再試験"),
    ),
    "retirement": (
        "サービス終了・データ廃棄計画",
        "運用責任者",
        "retirement",
        ("終了条件・通知", "保存・返却・廃棄", "承認と実施記録"),
    ),
}
ACTIVITIES = {
    "acceptance": "利用部門による受入",
    "operations": "運用引継ぎ",
    "release": "本番導入",
    "migration": "データ移行",
    "planning": "開発計画",
    "procurement": "調達・契約",
    "integration": "外部連携",
    "quality": "非機能の重点検証",
    "changes": "変更管理",
    "retirement": "サービス終了",
}
COUNTS = ("合格", "不合格", "未実施", "実施状況不明", "照合待ち")


def cell(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def table(headers, rows):
    def line(values):
        return "| " + " | ".join(cell(x) for x in values) + " |"

    return [line(headers), line(["---"] * len(headers)), *(line(r) for r in rows), ""]


def sources(row, doc, kinds=None):
    result = []
    for ref in row.get("evidence", []):
        if kinds is not None and ref["kind"] not in kinds:
            continue
        name = f"{ref['path']} L{ref['start']}–{ref['end']}"
        if (
            doc.get("repository")
            and ref["kind"] in ("code", "config", "test_code")
            and re.fullmatch(r"[0-9a-f]{40}", doc["revision"])
        ):
            url = f"{doc['repository']}/blob/{doc['revision']}/{quote(ref['path'])}#L{ref['start']}-L{ref['end']}"
            name = f"[{name}]({url})"
        if ref["kind"] == "decision":
            name += f"（{ref['by']}・{ref['date']}）"
        result.append(name)
    return " ／ ".join(result)


def strings(value, what):
    require(
        isinstance(value, list)
        and all(isinstance(x, str) and x.strip() for x in value),
        f"{what} には文字列の配列が必要です",
    )
    return value


def current_runs(row, revision):
    return [
        e
        for e in row.get("evidence", [])
        if e["kind"] == "run"
        and e["revision"] == revision
        and e.get("test_id") == row.get("test_id", row["id"])
    ]


def verdict(row, revision):
    runs = current_runs(row, revision)
    if row["status"] in ("passed", "failed"):
        if not runs:
            return "照合待ち"
        return "合格" if row["status"] == "passed" else "不合格"
    if any(
        e["kind"] == "run" and e["revision"] == revision
        for e in row.get("evidence", [])
    ):
        return "照合待ち"
    return "未実施" if row.get("execution") == "not_run" else "実施状況不明"


def validate_fields(doc, index):
    test_ids = set()
    for row in index.values():
        for key in ("title", "category", "actor", "expected", "level"):
            if key in row:
                require(
                    isinstance(row[key], str) and row[key].strip(),
                    f"{row['id']}: {key} を確認してください",
                )
        for key in (
            "criteria",
            "preconditions",
            "steps",
            "inputs",
            "outputs",
            "exceptions",
        ):
            if key in row:
                strings(row[key], key)
        if row["type"] == "test":
            test_id = row.get("test_id", row["id"])
            require(
                test_id not in test_ids,
                f"{row['id']}: 同じ試験IDが重複しています: {test_id}",
            )
            test_ids.add(test_id)
        if "execution" in row:
            require(
                row["type"] == "test"
                and row["status"] == "planned"
                and row["execution"] == "not_run"
                and verdict(row, doc["revision"]) == "未実施",
                f"{row['id']}: 未実施の記載と試験実績が矛盾しています",
            )
        for ref in row.get("evidence", []):
            if ref["kind"] == "run":
                for key in ("actual", "environment", "executed_at", "issue"):
                    if key in ref:
                        require(
                            isinstance(ref[key], str) and ref[key].strip(),
                            f"run.{key} に文字列が必要です",
                        )
    sections = doc.get("sections", {})
    require(isinstance(sections, dict), "sections には資料別の項目表が必要です")
    for key, fields in sections.items():
        require(
            key in CATALOG and isinstance(fields, dict),
            f"不明な資料または項目表: {key}",
        )
        require(
            key not in ("test-spec", "test-report", "trace"),
            f"{key} は試験項目・実行記録・関連番号から生成します",
        )
        for label, ids in fields.items():
            require(isinstance(label, str) and label.strip(), "見出しは空にできません")
            strings(ids, label)
            require(
                all(x in index for x in ids), f"{key}/{label}: 台帳にない番号があります"
            )


def summary_table(counts):
    return table(
        ("対象ケース", *COUNTS), [(sum(counts.values()), *(counts[k] for k in COUNTS))]
    )


class Module:
    def __init__(self, doc, index, selected):
        self.doc = doc
        self.index = index
        self.selected = set(selected)
        self.by_type = defaultdict(list)
        self.reverse = defaultdict(list)
        for row in index.values():
            self.by_type[row["type"]].append(row)
            for dep in row.get("depends_on", []):
                self.reverse[dep].append(row["id"])
        self.counts = Counter(verdict(t, doc["revision"]) for t in self.by_type["test"])

    def ref(self, ident):
        kind = self.index[ident]["type"]
        destinations = {
            "requirement": "requirements",
            "test": "test-spec",
            "behavior": "detailed-design",
        }
        key = destinations.get(kind)
        if kind == "behavior" and key not in self.selected:
            key = "basic-design"
        if key in self.selected:
            return f"[{ident}]({CATALOG[key][0]}.md#item-{ident})"
        return ident

    def related(self, ids):
        return "、".join(self.ref(ident) for ident in ids)

    def state(self, row):
        if row["type"] == "test":
            return verdict(row, self.doc["revision"])
        return LABELS[row["status"]]

    def sections(self, key, project):
        assigned = self.doc.get("sections", {}).get(key, {})
        result = []
        for label in dict.fromkeys((*CATALOG[key][3], *assigned)):
            if (
                key == "requirements"
                and label == "業務の目的と対象"
                and not assigned.get(label)
                and project.get("purpose")
            ):
                continue
            result.extend([f"## {label}", ""])
            ids = assigned.get(label, [])
            for ident in ids:
                row = self.index[ident]
                result.extend(
                    [f"- {self.ref(ident)}（{self.state(row)}）　{row['text']}"]
                )
                evidence = sources(row, self.doc)
                if evidence:
                    result.append(f"  - 根拠　{evidence}")
            if not ids:
                result.append("記入欄　＿＿＿＿　確認先・根拠　＿＿＿＿")
            result.append("")
        return result

    def questions(self):
        rows = self.by_type["question"] + self.by_type["conflict"]
        if not rows:
            return ["## 未確定事項", "", "追加確認の要否　＿＿＿＿", ""]
        return [
            "## 未確定事項",
            "",
            *table(
                ("番号", "問い・資料間の相違", "確認先", "関係する番号", "回答・日付"),
                [
                    (
                        r["id"],
                        r["text"],
                        r.get("owner", ""),
                        self.related(r.get("depends_on", [])),
                        "",
                    )
                    for r in rows
                ],
            ),
        ]

    def requirements(self):
        lines = ["## 要件と受入条件", ""]
        for row in self.by_type["requirement"]:
            lines.extend(
                [
                    f'<a id="item-{row["id"]}"></a>',
                    "",
                    f"### {row['id']}　{row.get('title', '要件')}",
                    "",
                    row["text"],
                    "",
                    f"- 合意状況　{LABELS[row['status']]}",
                    f"- 種別・利用者　{row.get('category', '要確認')} ／ {row.get('actor', '要確認')}",
                    "- 受入条件",
                    *("  - " + x for x in row.get("criteria", []) or ["記入待ち"]),
                    "- 関連する番号　"
                    + self.related(row.get("depends_on", []) + self.reverse[row["id"]]),
                    "- 根拠　" + (sources(row, self.doc) or "要確認"),
                    "",
                ]
            )
            for dep in row.get("depends_on", []):
                linked = self.index[dep]
                if linked["type"] == "behavior":
                    lines.extend(
                        [
                            f"関連する現行動作の根拠　{dep}　"
                            + sources(linked, self.doc),
                            "",
                        ]
                    )
        if not self.by_type["requirement"]:
            lines.extend(["要件の記録なし。業務担当に目的・受入条件を確認する。", ""])
        return lines + self.questions()

    def specification(self):
        lines = ["## 試験ケース", ""]
        for row in self.by_type["test"]:
            lines.extend(
                [
                    f'<a id="item-{row["id"]}"></a>',
                    "",
                    f"### {row['id']}　{row.get('title', '試験ケース')}",
                    "",
                    "- 試験ID　" + row.get("test_id", row["id"]),
                    "- 対応する要件・設計　" + self.related(row.get("depends_on", [])),
                    "- 試験レベル　" + row.get("level", "要確認"),
                    "",
                    "**前提条件・入力**",
                    "",
                    *("- " + x for x in row.get("preconditions", []) or ["記入待ち"]),
                    "",
                    "**操作**",
                    "",
                    *(
                        f"{i}. {x}"
                        for i, x in enumerate(row.get("steps", []) or ["記入待ち"], 1)
                    ),
                    "",
                    "**期待結果**",
                    "",
                    row.get("expected", "記入待ち"),
                    "",
                ]
            )
            if row["status"] == "planned" and not row.get("expected"):
                lines.extend(["元の試験案　" + row["text"], ""])
            refs = sources(
                row,
                self.doc,
                {"test_code", "document", "code", "config", "observation"},
            )
            if refs:
                lines.extend(["試験設計の根拠　" + refs, ""])
        if not self.by_type["test"]:
            lines += ["試験ケースの記録なし。対象要件から試験を設計する。", ""]
        return lines

    def report(self):
        lines = ["## ケース別集計", "", *summary_table(self.counts), "## 実施結果", ""]
        rows = []
        for test in self.by_type["test"]:
            state = verdict(test, self.doc["revision"])
            runs = (
                current_runs(test, self.doc["revision"])
                if state in ("合格", "不合格")
                else []
            )
            for ref in runs or [{}]:
                evidence = f"{ref['path']} L{ref['start']}–{ref['end']}" if ref else ""
                rows.append(
                    (
                        self.ref(test["id"]),
                        test.get("test_id", test["id"]),
                        state,
                        ref.get("actual", ""),
                        ref.get("executed_at", ""),
                        ref.get("environment", ""),
                        evidence,
                        ref.get("issue", ""),
                    )
                )
        lines.extend(
            table(
                (
                    "番号",
                    "試験ID",
                    "判定",
                    "観測内容",
                    "実施日時",
                    "環境",
                    "実行記録",
                    "不具合・残件",
                ),
                rows,
            )
        )
        lines += [
            "集計は台帳のケース単位。同一ケースの複数の証跡は明細に表示する。空欄は証跡から確認できなかった項目。",
            "",
            "## 残件と業務判断",
            "",
        ]
        for test in self.by_type["test"]:
            state = verdict(test, self.doc["revision"])
            if state != "合格":
                lines.append(f"- {test['id']}　{state}　影響・次の確認担当　＿＿＿＿")
        lines.extend(
            ["", "業務上の受入判断　＿＿＿＿　判断者・日付・根拠　＿＿＿＿", ""]
        )
        return lines

    def render(self, key, project, module, cross_links, chosen, overview_link=None):
        lines = [
            f"# {CATALOG[key][0]}",
            "",
            f"案件　{project['title']}　／　対象版　{self.doc['revision']}",
            "",
            f"範囲　{module['name']}（{module['id']}）",
            "",
        ]
        if overview_link:
            lines.extend([f"[製品の目的・関係者・構成図・画面]({overview_link})", ""])
        for field, label in (("purpose", "目的"), ("scope", "対象範囲")):
            if field in project:
                lines += [f"{label}　{project[field]}", ""]
        lines.extend(self.sections(key, project))
        if key == "requirements":
            lines.extend(self.requirements())
        elif key == "test-spec":
            lines.extend(self.specification())
        elif key == "test-report":
            lines.extend(self.report())
        elif key == "basic-design":
            lines.extend(["## 利用者から見える動作と業務要件", ""])
            for r in self.by_type["behavior"]:
                reqs = [
                    d
                    for d in self.reverse[r["id"]]
                    if self.index[d]["type"] == "requirement"
                ]
                lines.extend(
                    [
                        f'<a id="item-{r["id"]}"></a>',
                        "",
                        f"### {r['id']}",
                        "",
                        r["text"],
                        "",
                        "関連する要件　" + (self.related(reqs) or "要確認"),
                        "",
                        "根拠　" + sources(r, self.doc),
                        "",
                    ]
                )
        elif key == "detailed-design":
            lines.extend(["## 処理ごとの入出力・例外と実装根拠", ""])
            for r in self.by_type["behavior"]:
                lines.extend(
                    [
                        f'<a id="item-{r["id"]}"></a>',
                        "",
                        f"### {r['id']}",
                        "",
                        r["text"],
                        "",
                        *table(
                            ("入力", "出力・更新", "例外"),
                            [
                                tuple(
                                    " ／ ".join(r.get(k, []))
                                    for k in ("inputs", "outputs", "exceptions")
                                )
                            ],
                        ),
                        "実装根拠　" + sources(r, self.doc),
                        "",
                    ]
                )
        elif key == "test-plan":
            lines += [
                "## 試験範囲",
                "",
                *table(
                    ("番号", "試験対象", "レベル", "関連項目"),
                    [
                        (
                            self.ref(r["id"]),
                            r.get("title", r["id"]),
                            r.get("level", "要確認"),
                            self.related(r.get("depends_on", [])),
                        )
                        for r in self.by_type["test"]
                    ],
                ),
            ]
        elif key == "trace":
            lines.extend(
                [
                    "## モジュール内の対応",
                    "",
                    *table(
                        (
                            "番号",
                            "内容",
                            "根拠・依存先の番号",
                            "本項を参照する番号",
                            "出典",
                        ),
                        [
                            (
                                f'<a id="trace-{r["id"]}"></a>' + self.ref(r["id"]),
                                r["text"],
                                self.related(r.get("depends_on", [])),
                                self.related(self.reverse[r["id"]]),
                                sources(r, self.doc),
                            )
                            for r in self.index.values()
                        ],
                    ),
                ]
            )
            if cross_links:

                def address(value):
                    mod, ident = value.split("/", 1)
                    if mod not in chosen:
                        return value + "（今回の範囲外）"
                    target = (
                        ""
                        if mod == module["id"]
                        else f"../{mod}/{CATALOG['trace'][0]}.md"
                    )
                    return f"[{value}]({target}#trace-{ident})"

                lines.extend(
                    [
                        "## モジュールをまたぐ対応",
                        "",
                        *table(
                            ("参照元", "参照先"),
                            [(address(a), address(b)) for a, b in cross_links],
                        ),
                    ]
                )
        elif key == "acceptance":
            lines += [
                "## 受入の記入欄",
                "",
                *summary_table(self.counts),
                *table(
                    ("判断の対象", "判定・条件", "判断者", "日付", "決定記録"),
                    [("", "", "", "", "")],
                ),
            ]
        return "\n".join(lines).rstrip() + "\n"
