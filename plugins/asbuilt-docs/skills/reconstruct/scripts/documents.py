"""Select and build a Japanese Markdown delivery set, one verified module at a time."""

import argparse
import errno
import filecmp
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from document_views import (
    ACTIVITIES,
    CATALOG,
    COUNTS,
    Module,
    strings,
    table,
    validate_fields,
)
from ledger import ID, load, path_within, require, string, verify_ledger


def choices(project, key, allowed):
    values = strings(project.get(key, []), key)
    unknown = set(values) - set(allowed)
    require(not unknown, f"{key} に未知の値があります: {', '.join(sorted(unknown))}")
    return set(values)


def selection(project):
    activities = choices(project, "activities", ACTIVITIES)
    include = choices(project, "include", CATALOG)
    exclude = choices(project, "exclude", CATALOG)
    only = choices(project, "only", CATALOG)
    require(not include & exclude, "include と exclude の指定が重複しています")
    require(
        "only" not in project or (only and not (include or exclude)),
        "only には1点以上を指定し、include・exclude と分けてください",
    )
    selected, reasons = [], {}
    for key, (_, _, activity, _) in CATALOG.items():
        if "only" in project:
            use = key in only
            reason = "指定された納品物" if use else "納品指定の範囲外"
        elif key in exclude:
            use, reason = False, "案件の指定で対象外"
        elif key in include:
            use, reason = True, "案件の指定で追加"
        elif activity is None:
            use, reason = True, "引継ぎの基本資料"
        else:
            use = activity in activities
            reason = (
                ACTIVITIES[activity] if use else f"{ACTIVITIES[activity]}の指定なし"
            )
        reasons[key] = reason
        if use:
            selected.append(key)
    require(selected, "少なくとも1点の成果物を選択してください")
    overrides = project.get("selection_reasons", {})
    require(
        isinstance(overrides, dict),
        "selection_reasons には資料IDと理由を指定してください",
    )
    for key in overrides:
        require(key in CATALOG, f"選定理由の資料IDが不明です: {key}")
        reasons[key] = string(overrides, key)
    return selected, reasons


def read_project(path):
    project = load(path)
    require(isinstance(project, dict), "案件設定にはJSONオブジェクトが必要です")
    for key in ("title", "revision"):
        string(project, key)
    for key in ("scope", "purpose"):
        if key in project:
            string(project, key)
    require(
        isinstance(project.get("modules"), list) and project["modules"],
        "modules を1件以上指定してください",
    )
    modules = {}
    for module in project["modules"]:
        require(isinstance(module, dict), "module の形式が不正です")
        key = string(module, "id")
        require(
            re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", key) and key not in modules,
            f"モジュール名が不正または重複しています: {key}",
        )
        string(module, "name")
        path_within(path.parent, string(module, "ledger"))
        modules[key] = module
    links = project.get("links", [])
    require(isinstance(links, list), "links には配列が必要です")
    wanted = defaultdict(set)
    by_module = defaultdict(list)
    for link in links:
        require(isinstance(link, dict), "links の項目が不正です")
        ends = []
        for side in ("from", "to"):
            addr = string(link, side)
            mod, _, ident = addr.partition("/")
            require(mod in modules and ID.fullmatch(ident), f"不明な関連先: {addr}")
            wanted[mod].add(ident)
            ends.append(mod)
        require(
            ends[0] != ends[1], "同一モジュール内は台帳の depends_on を使ってください"
        )
        for mod in ends:
            by_module[mod].append((link["from"], link["to"]))
    return project, modules, wanted, by_module


def document_path(module_id, key, split):
    name = CATALOG[key][0] + ".md"
    return Path("modules", module_id, name) if split else Path(name)


def coverage(project, modules, chosen):
    return [
        f"案件　{project['title']}　／　対象版　{project['revision']}",
        "",
        f"収録対象　{len(chosen)} / {len(modules)} モジュール。",
        "",
    ]


def catalog_text(project, modules, chosen, selected, reasons, record_counts=None):
    built = record_counts is not None
    lines = ["# 成果物一覧", "", *coverage(project, modules, chosen)]
    if "purpose" in project:
        lines.extend(["目的　" + project["purpose"], ""])
    if "scope" in project:
        lines.extend(["対象範囲　" + project["scope"], ""])
    lines += table(
        ("資料", "主な読み手", "作成", "選定理由"),
        [
            (
                f"[{name}]({name}.md)" if built and key in selected else name,
                reader,
                "対象" if key in selected else "対象外",
                reasons[key],
            )
            for key, (name, reader, _, _) in CATALOG.items()
        ],
    )
    lines += [
        "## モジュール",
        "",
        *table(
            ("番号", "業務・機能", "今回の範囲", "照合した台帳項目"),
            [
                (
                    key,
                    m["name"],
                    ("収録" if built else "選択") if key in chosen else "範囲外",
                    (record_counts[key] or "0（調査状況を要確認）")
                    if built and key in chosen
                    else "",
                )
                for key, m in modules.items()
            ],
        ),
    ]
    outside = sum(
        1
        for link in project.get("links", [])
        if any(link[k].split("/", 1)[0] not in chosen for k in ("from", "to"))
    )
    if outside:
        lines.extend(
            [
                f"モジュール間の対応のうち、{outside}件は今回の範囲外の端点を含む。全体生成時に両端を照合する。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def same_output(old, new):
    if not (old / "成果物一覧.md").is_file():
        return False
    expected = {f.relative_to(new) for f in new.rglob("*")}
    actual = {f.relative_to(old) for f in old.rglob("*")}
    if expected != actual:
        return False
    for name in expected:
        previous = old / name
        if previous.is_symlink() or previous.is_file() != (new / name).is_file():
            return False
        if previous.is_file() and not filecmp.cmp(previous, new / name, shallow=False):
            return False
    return True


def publish(stage, target):
    # A single rename makes a validated snapshot visible. A concurrent identical build
    # can reuse it; a different build or a handwritten edit is preserved.
    require(not target.is_symlink(), "シンボリックリンクを出力先に指定できません")
    if not target.exists() or (target.is_dir() and not any(target.iterdir())):
        try:
            stage.rename(target)
            return
        except OSError as exc:
            if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY) or not target.is_dir():
                raise
    require(
        target.is_dir() and same_output(target, stage),
        "出力先に別の内容があります。改訂版には新しい出力フォルダーを指定してください",
    )


def build(path, root, target, requested, plan_only=False):
    project, modules, wanted, links = read_project(path)
    selected, reasons = selection(project)
    chosen = set(requested or modules.keys())
    missing = chosen - modules.keys()
    require(not missing, "未知のモジュール: " + ", ".join(sorted(missing)))
    if plan_only:
        print(catalog_text(project, modules, chosen, selected, reasons), end="")
        return
    split = len(modules) > 1
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".asbuilt-", dir=target.parent) as tmp:
        stage = Path(tmp) / "snapshot"
        stage.mkdir()
        totals = Counter()
        counts = {}
        record_counts = {}
        for mod, cfg in modules.items():
            if mod not in chosen:
                continue
            try:
                doc = load(path_within(path.parent, cfg["ledger"]))
                require(
                    isinstance(doc, dict)
                    and doc.get("revision") == project["revision"],
                    "対象版が案件と一致しません",
                )
                index = verify_ledger(doc, root)
                validate_fields(doc, index)
                missing_ids = [ident for ident in wanted[mod] if ident not in index]
                require(
                    not missing_ids,
                    "モジュール間の参照先がありません: "
                    + ", ".join(sorted(missing_ids)),
                )
                data = Module(doc, index, selected)
                counts[mod] = data.counts
                record_counts[mod] = len(index)
                totals.update(data.counts)
                for key in selected:
                    dest = stage / document_path(mod, key, split)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(
                        data.render(key, project, cfg, links[mod], chosen),
                        encoding="utf-8",
                    )
                del data, doc, index
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError(f"{mod}: {exc}") from exc
        if split:
            for key in selected:
                title = CATALOG[key][0]
                lines = ["# " + title, "", *coverage(project, modules, chosen)]
                if key == "test-report":
                    lines += [
                        "## 収録範囲のケース集計",
                        "",
                        *table(
                            ("範囲", "ケース数", *COUNTS),
                            [
                                (label, sum(c.values()), *(c[k] for k in COUNTS))
                                for label, c in [("収録合計", totals), *counts.items()]
                            ],
                        ),
                    ]
                lines += ["## 機能別の本文", ""]
                for mod, cfg in modules.items():
                    if mod in chosen:
                        lines.append(
                            f"- [{cfg['name']}]({document_path(mod, key, True).as_posix()})"
                        )
                (stage / (title + ".md")).write_text(
                    "\n".join(lines) + "\n", encoding="utf-8"
                )
        (stage / "成果物一覧.md").write_text(
            catalog_text(project, modules, chosen, selected, reasons, record_counts),
            encoding="utf-8",
        )
        publish(stage, target)
    print(
        f"{len(chosen)}/{len(modules)} モジュール・{len(selected)}種類の成果物を {target} に生成しました"
    )


def inventory(root, revision, depth):
    require(depth > 0, "depth は1以上が必要です")
    git = ["git", "-C", str(root)]
    commit = subprocess.check_output(
        [*git, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"],
        text=True,
    ).strip()
    counts = Counter()
    with subprocess.Popen(
        [*git, "ls-tree", "-rz", "--name-only", commit], stdout=subprocess.PIPE
    ) as process:
        tail = b""
        for chunk in iter(lambda: process.stdout.read(65536), b""):
            *names, tail = (tail + chunk).split(b"\0")
            for name in names:
                parts = os.fsdecode(name).split("/")[:-1]
                counts["/".join(parts[:depth]) or "."] += 1
        require(
            process.wait() == 0 and not tail, "Gitの一覧を最後まで取得できませんでした"
        )
    print(
        json.dumps(
            {
                "revision": commit,
                "tracked_files": sum(counts.values()),
                "directories": dict(sorted(counts.items())),
            },
            ensure_ascii=True,
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "build"):
        cmd = sub.add_parser(
            name, help="案件の納品一覧" if name == "plan" else "選択された資料を生成"
        )
        cmd.add_argument("project", type=Path)
        cmd.add_argument(
            "--module", action="append", help="収録するモジュールID（複数回指定可）"
        )
        if name == "build":
            cmd.add_argument(
                "--root",
                type=Path,
                default=Path.cwd(),
                help="対象版の根拠ファイルのルート",
            )
            cmd.add_argument(
                "--out", type=Path, required=True, help="出力スナップショット"
            )
    inv = sub.add_parser(
        "inventory", help="固定コミットのディレクトリ別ファイル数を調べる"
    )
    inv.add_argument("--root", type=Path, default=Path.cwd())
    inv.add_argument("--revision", default="HEAD")
    inv.add_argument("--depth", type=int, default=2)
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            inventory(args.root, args.revision, args.depth)
        elif args.command == "plan":
            build(args.project, None, None, args.module, plan_only=True)
        else:
            build(args.project, args.root, args.out, args.module)
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
