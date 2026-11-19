"""Validate, render and compare an evidence-linked requirements ledger (Python 3.9+)."""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict, deque
from datetime import date
from pathlib import Path
from urllib.parse import quote

STATES = {
    "behavior": {"observed"},
    "requirement": {"proposed", "approved"},
    "test": {"planned", "passed", "failed"},
    "question": {"open"},
    "conflict": {"open"},
}
KINDS = ("code", "config", "observation", "document", "decision", "run", "test_code")
HEADINGS = {
    "behavior": "現行設計",
    "requirement": "要件定義",
    "test": "テスト仕様と結果",
    "question": "確認事項",
    "conflict": "資料間の相違",
}
LABELS = {
    "observed": "現行の根拠あり",
    "proposed": "候補",
    "approved": "承認記録あり",
    "planned": "試験案・実績は未確認",
    "passed": "合格記録あり",
    "failed": "不合格記録あり",
    "open": "要確認",
}
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")


def require(value, message):
    if not value:
        raise ValueError(message)


def string(obj, key):
    value = obj.get(key)
    require(isinstance(value, str) and value.strip(), f"{key} に文字列が必要です")
    return value


def path_within(root, relative):
    path = Path(relative)
    require(
        relative and not path.is_absolute() and ".." not in path.parts,
        f"対象外のパス: {relative}",
    )
    base = root.resolve()
    real = (base / path).resolve()
    require(real.is_relative_to(base), f"対象外のパス: {relative}")
    return real


def digest(root, evidence):
    path = path_within(root, evidence["path"])
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    start, end = evidence["start"], evidence["end"]
    require(
        1 <= start <= end <= len(lines),
        f"行範囲を確認してください: {evidence['path']} {start}–{end}",
    )
    excerpt = "\n".join(lines[start - 1 : end]) + "\n"
    return hashlib.sha256(excerpt.encode()).hexdigest()


def check_evidence(evidence, root):
    require(isinstance(evidence, dict), "根拠にはオブジェクトが必要です")
    kind = string(evidence, "kind")
    require(kind in KINDS, f"未知の根拠の種類: {kind}")
    path = Path(string(evidence, "path"))
    require(not path.is_absolute() and ".." not in path.parts, f"対象外のパス: {path}")
    start, end = evidence.get("start"), evidence.get("end")
    require(
        type(start) is int and type(end) is int and 1 <= start <= end,
        "行範囲が不正です",
    )
    require(
        re.fullmatch(r"[0-9a-f]{64}", string(evidence, "sha256")),
        "行範囲のSHA256が不正です",
    )
    if kind == "decision":
        string(evidence, "by")
        date.fromisoformat(string(evidence, "date"))
    elif kind == "run":
        string(evidence, "revision")
        if "test_id" in evidence:
            string(evidence, "test_id")
        require(
            evidence.get("result") in ("passed", "failed"), "試験記録に合否が必要です"
        )
    if root is not None:
        require(
            digest(root, evidence) == evidence["sha256"],
            f"根拠が変わりました: {path}:{start}-{end}",
        )


def unlinked_result(row, revision):
    return row["status"] in {"passed", "failed"} and not any(
        ref["kind"] == "run" and ref["revision"] == revision and ref.get("test_id")
        for ref in row.get("evidence", [])
    )


def verify_ledger(doc, root=None, *, comparing_versions=False):
    require(
        isinstance(doc, dict)
        and type(doc.get("schema_version")) is int
        and doc["schema_version"] in (1, 2),
        "台帳形式には整数の1または2を指定してください",
    )
    revision = string(doc, "revision")
    if "repository" in doc:
        require(
            re.fullmatch(
                r"https://github\.com/[\w.-]+/[\w.-]+", string(doc, "repository")
            ),
            "repository はGitHubリポジトリのHTTPS URLです",
        )
    rows = doc.get("records")
    require(isinstance(rows, list), "records 配列が必要です")
    index = {}
    for row in rows:
        require(isinstance(row, dict), "各項目にはオブジェクトが必要です")
        key, kind, state = (string(row, f) for f in ("id", "type", "status"))
        require(
            ID.fullmatch(key) and key not in index,
            f"識別番号が不正または重複しています: {key}",
        )
        require(
            kind in STATES and state in STATES[kind],
            f"{key}: 種類と状態の組合せが不正です",
        )
        string(row, "text")
        refs = row.get("evidence", [])
        deps = row.get("depends_on", [])
        require(
            isinstance(refs, list)
            and isinstance(deps, list)
            and all(isinstance(d, str) for d in deps),
            f"{key}: 根拠と関連項目には配列が必要です",
        )
        require(
            key not in deps and len(deps) == len(set(deps)),
            f"{key}: 自己参照または重複する関連項目です",
        )
        for ref in refs:
            check_evidence(ref, root)
        if kind == "test":
            test_id = string(row, "test_id") if "test_id" in row else key
            for ref in refs:
                if ref["kind"] != "run":
                    continue
                if doc["schema_version"] == 2 or "test_id" in ref:
                    require(
                        ref.get("test_id") == test_id,
                        f"{key}: 実行記録の試験IDが {test_id} と一致する必要があります",
                    )
        kinds = {ref["kind"] for ref in refs}
        if kind == "behavior":
            require(
                kinds & {"code", "config", "observation"},
                f"{key}: 現行動作にはコード・設定・観察の根拠が必要です",
            )
        if state == "approved":
            require("decision" in kinds, f"{key}: 承認の根拠が必要です")
        if state in ("passed", "failed"):
            matching = {
                r["result"]
                for r in refs
                if r["kind"] == "run" and r["revision"] == revision
            }
            historical = any(
                r["kind"] == "run" and r["revision"] != revision for r in refs
            )
            require(
                matching == {state}
                or (comparing_versions and historical and not matching),
                f"{key}: 対象版で合否が一致した実行記録が必要です",
            )
        if kind == "question":
            string(row, "owner")
        if kind == "conflict":
            require(
                len(set(deps)) >= 2, f"{key}: 食い違う項目を二つ以上関連付けてください"
            )
        index[key] = row
    for key, row in index.items():
        missing = set(row.get("depends_on", [])) - index.keys()
        require(not missing, f"{key}: 参照先がありません: {', '.join(sorted(missing))}")
    return index


def impact(old, new, root):
    previous = verify_ledger(old)
    current = verify_ledger(new, comparing_versions=True)
    keys = previous.keys() | current.keys()
    changed = {key for key in keys if previous.get(key) != current.get(key)}
    stale = set()
    if root is not None:
        for key, row in current.items():
            for ref in row.get("evidence", []):
                try:
                    check_evidence(ref, root)
                except (OSError, ValueError):
                    stale.add(key)
    previous_runs = {
        key
        for key, row in current.items()
        if row["status"] in {"passed", "failed"}
        and not any(
            r["kind"] == "run" and r["revision"] == new["revision"]
            for r in row.get("evidence", [])
        )
    }
    reverse = defaultdict(set)
    for index in (previous, current):
        for key, row in index.items():
            for dependency in row.get("depends_on", []):
                reverse[dependency].add(key)
    unlinked = {
        key
        for key, row in current.items()
        if key not in previous_runs and unlinked_result(row, new["revision"])
    }
    affected = changed | stale | previous_runs | unlinked
    pending = deque(sorted(affected))
    while pending:
        for key in reverse[pending.popleft()]:
            if key not in affected:
                affected.add(key)
                pending.append(key)
    impacted_areas = {
        HEADINGS[row["type"]]
        for idx in (previous, current)
        for key, row in idx.items()
        if key in affected
    }
    return {
        "changed": sorted(changed),
        "stale_evidence": sorted(stale),
        "prior_revision_tests": sorted(previous_runs),
        "unlinked_test_results": sorted(unlinked),
        "affected": sorted(affected),
        "sections": sorted(impacted_areas),
    }


def render(doc, section):
    lines = ["# 開発資料", "", f"対象版　{doc['revision']}", ""]
    for kind, heading in HEADINGS.items():
        if section and section != kind:
            continue
        lines.extend([f"## {heading}", ""])
        selected = [row for row in doc["records"] if row["type"] == kind]
        if not selected:
            lines.extend(["記録なし（該当の有無は要確認）。", ""])
        for row in selected:
            label = LABELS[row["status"]]
            if unlinked_result(row, doc["revision"]):
                label += "（試験IDは要確認）"
            lines.extend([f"### {row['id']}　{label}", "", row["text"], ""])
            if row.get("owner"):
                lines.append(f"- 確認先　{row['owner']}")
            if row.get("depends_on"):
                lines.append("- 関連項目　" + "、".join(row["depends_on"]))
            for ref in row.get("evidence", []):
                name = f"{ref['path']} L{ref['start']}–{ref['end']}"
                if (
                    ref["kind"] in ("code", "config", "test_code")
                    and doc.get("repository")
                    and re.fullmatch(r"[0-9a-f]{40}", doc["revision"])
                ):
                    url = f"{doc['repository']}/blob/{doc['revision']}/{quote(ref['path'])}#L{ref['start']}-L{ref['end']}"
                    name = f"[{name}]({url})"
                details = (
                    f"　{ref['by']} {ref['date']}" if ref["kind"] == "decision" else ""
                )
                if ref["kind"] == "run":
                    details = f"　{ref['revision']} {ref['result']}"
                    if ref.get("test_id"):
                        details += f"　試験ID {ref['test_id']}"
                lines.append(f"- 根拠　{name}（{ref['kind']}）{details}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load(path):
    if path == Path("-"):
        return json.load(sys.stdin)
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    cite = sub.add_parser("cite", help="根拠の行を指すJSONを作る")
    cite.add_argument("path")
    cite.add_argument("start", type=int)
    cite.add_argument("end", type=int)
    cite.add_argument("--kind", choices=KINDS, required=True)
    for field in ("by", "date", "revision", "result"):
        cite.add_argument("--" + field)
    cite.add_argument("--test-id")
    for name in ("check", "render"):
        cmd = sub.add_parser(name)
        cmd.add_argument("ledger", type=Path)
        cmd.add_argument("--root", type=Path, default=Path.cwd())
        if name == "render":
            cmd.add_argument("--section", choices=list(STATES))
    cite.add_argument("--root", type=Path, default=Path.cwd())
    diff = sub.add_parser("impact", help="新版・旧版の項目とその影響先を求める")
    diff.add_argument("old", type=Path)
    diff.add_argument("new", type=Path)
    diff.add_argument("--root", type=Path)
    a = p.parse_args()
    try:
        if a.command == "cite":
            ref = {
                k: v
                for k, v in vars(a).items()
                if k not in ("command", "root") and v is not None
            }
            ref["sha256"] = digest(a.root, ref)
            check_evidence(ref, a.root)
            print(json.dumps(ref, ensure_ascii=False, indent=2))
        elif a.command == "impact":
            print(
                json.dumps(
                    impact(load(a.old), load(a.new), a.root),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            doc = load(a.ledger)
            rows = verify_ledger(doc, a.root)
            if a.command == "check":
                print(f"{len(rows)} 項目の形式と根拠の参照を確認しました")
                pending = [
                    key
                    for key, row in rows.items()
                    if unlinked_result(row, doc["revision"])
                ]
                if pending:
                    print("試験IDの照合待ち　" + "、".join(pending))
            else:
                print(render(doc, a.section), end="")
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
