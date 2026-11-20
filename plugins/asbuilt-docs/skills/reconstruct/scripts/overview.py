"""Build the evidence-backed product introduction, architectural views and UI plates."""

import hashlib
import json
import shutil
from itertools import islice

from diagrams import render_svg
from document_views import table
from ledger import ID, load, path_within, require, string
from screen_assets import CAPTURES, verify_image

KINDS = {
    "infrastructure": "インフラ構成図",
    "software": "ソフトウェア構成図",
    "data": "データフロー図",
}


def array(value, field):
    require(isinstance(value, list), f"{field} には配列が必要です")
    return value


def mapping(value, field):
    require(isinstance(value, dict), f"{field} にはオブジェクトが必要です")
    return value


def identifiers(values, available, field):
    values = array(values, field)
    require(
        all(isinstance(key, str) and key in available for key in values),
        f"{field} に未知の番号があります",
    )
    require(len(set(values)) == len(values), f"{field} の番号が重複しています")
    return values


def evidence_appendix(sources, root, assets, revision):
    require(sources, "概要に引用する根拠を指定してください")
    lines = ["# 概要と図の根拠", "", f"対象版　{revision}", ""]
    for key, ref in sources.items():
        require(ID.fullmatch(key), f"根拠番号を確認してください: {key}")
        mapping(ref, key)
        name = string(ref, "path")
        first, last = ref.get("start"), ref.get("end")
        require(
            type(first) is int and type(last) is int and 1 <= first <= last,
            f"引用行を確認してください: {key}",
        )
        with path_within(root, name).open(encoding="utf-8-sig") as stream:
            rows = list(islice(stream, first - 1, last))
        require(len(rows) == last - first + 1, f"根拠の行がありません: {key}")
        excerpt = "".join(row.rstrip("\r\n") + "\n" for row in rows)
        require(excerpt.strip(), f"根拠が空です: {key}")
        if "sha256" in ref:
            require(
                hashlib.sha256(excerpt.encode()).hexdigest() == ref["sha256"],
                f"引用内容が変わりました: {key}",
            )
        lines.extend(
            [
                f'<a id="ref-{key}"></a>',
                "",
                f"## {key}　{name} L{first}–{last}",
                "",
                "~~~text",
            ]
        )
        lines.extend(
            f"{number:>4}  {row.rstrip()}" for number, row in enumerate(rows, first)
        )
        lines.extend(["~~~", ""])
    (assets / "sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def citations(entry, sources):
    refs = identifiers(entry.get("evidence"), sources, "evidence")
    require(refs, "説明を裏付ける根拠番号が必要です")
    return " ／ ".join(f"[{key}](figures/sources.md#ref-{key})" for key in refs)


def draw_view(view, entities, assets, index, sources):
    category = string(view, "kind")
    require(category in KINDS, f"図の種類を確認してください: {category}")
    title = string(view, "title")
    refs = citations(view, sources)
    keys = dict.fromkeys(identifiers(view.get("nodes", []), entities, "nodes"))
    edges = []
    for edge in array(view.get("edges", []), "edges"):
        mapping(edge, "edge")
        src, dst = string(edge, "from"), string(edge, "to")
        require(
            src in entities and dst in entities,
            f"図に未定義の要素があります: {src} → {dst}",
        )
        keys.update({src: None, dst: None})
        edges.append((src, dst, string(edge, "label")))
    groups = mapping(view.get("groups", {}), "groups")
    grouped = set()
    for label, members in groups.items():
        ids = identifiers(members, keys, "groups")
        require(
            label.strip() and ids and not grouped.intersection(ids),
            "図の境界名と所属を確認してください",
        )
        grouped.update(ids)
    nodes = {key: entities[key] for key in keys}
    note = string(view, "unknown") if "unknown" in view else ""
    require(
        nodes or note, f"{title} の構成が未確認なら調査範囲と確認先を記載してください"
    )
    require(
        category != "data" or edges or note,
        "データの流れには受渡しの矢印または調査待ちの理由が必要です",
    )
    if not nodes:
        nodes = {"unknown": "未確認\n" + note}
    filename = f"{category}-{index:02}.svg"
    (assets / filename).write_bytes(render_svg(nodes, edges, groups, title))
    result = [
        f"### {title}",
        "",
        string(view, "scope"),
        "",
        f"![{title}](figures/{filename})",
        "",
    ]
    if edges:
        result.extend(
            table(
                ("起点", "渡すもの・関係", "終点"),
                [(entities[src], label, entities[dst]) for src, dst, label in edges],
            )
        )
    if note:
        result.extend(["確認待ち　" + note, ""])
    return [*result, "根拠　" + refs, ""]


def copy_capture(screen, root, assets, index, revision):
    require(
        string(screen, "revision") == revision,
        "スクリーンショットの版が案件と一致しません",
    )
    source = path_within(root, string(screen, "file"))
    ext = source.suffix.lower()
    require(
        ext in (".png", ".jpg", ".jpeg"), "撮影原本にはPNGまたはJPEGを指定してください"
    )
    target = assets / f"screen-{index:02}{ext}"
    shutil.copyfile(source, target)
    verify_image(target, string(screen, "sha256"))
    return "figures/" + target.name


def screens_section(ui, actors, root, assets, revision):
    kind = string(ui, "kind")
    require(
        kind in ("gui", "none", "unknown"),
        "ui.kind は gui、none、unknown のいずれかです",
    )
    captures = array(ui.get("captures", []), "captures")
    result = ['<a id="screens"></a>', "", "## 操作画面", ""]
    if not captures:
        reason = string(ui, "reason")
        label = {
            "gui": "画面採取待ち",
            "none": "画面の対象外",
            "unknown": "画面の有無を確認中",
        }[kind]
        return [*result, f"{label}　{reason}", ""]
    require(kind == "gui", "画面の種別と撮影原本が矛盾しています")
    images = {}
    for idx, screen in enumerate(captures, 1):
        mapping(screen, "capture")
        actor = string(screen, "actor")
        require(actor in actors, f"画面の利用者が未定義です: {actor}")
        src = copy_capture(screen, root, assets, idx, revision)
        images[src.rsplit("/", 1)[1]] = screen["sha256"]
        title = string(screen, "title")
        result.extend(
            [
                f"### {title}",
                "",
                f"{actors[actor]}が行う操作　{string(screen, 'action')}",
                "",
                f"確認できる状態　{string(screen, 'state')}",
                "",
                f"![{title}]({src})",
                "",
                f"撮影　{string(screen, 'captured_at')} ／ {string(screen, 'environment')} ／ 対象版 {revision}",
                "",
            ]
        )
    (assets / CAPTURES).write_text(
        json.dumps(
            {"revision": revision, "images": images}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    result.extend([f"[撮影原本の照合記録](figures/{CAPTURES})", ""])
    if "reason" in ui:
        result.extend(["追加の採取待ち　" + string(ui, "reason"), ""])
    return result


def render_overview(config, root, stage, revision):
    doc = mapping(load(config), "overview")
    require(string(doc, "revision") == revision, "概要の版が案件と一致しません")
    assets = stage / "figures"
    assets.mkdir()
    sources = mapping(doc.get("sources"), "sources")
    evidence_appendix(sources, root, assets, revision)
    intro = [
        string(doc, "product"),
        "",
        string(doc, "purpose"),
        "",
        "根拠　" + citations(doc, sources),
        "",
    ]
    lines = [
        '<a id="system"></a>',
        "",
        "## 製品と目的",
        "",
        *intro,
        "今回扱う範囲　" + string(doc, "scope"),
        "",
    ]
    names, actors = {}, {}
    for field, heading in (
        ("stakeholders", "関係者と利用目的"),
        ("components", "構成要素と責任"),
    ):
        rows = []
        for item in array(doc.get(field), field):
            mapping(item, field)
            key, name = string(item, "id"), string(item, "name")
            require(
                ID.fullmatch(key) and key not in names,
                f"登場要素の番号が不正または重複しています: {key}",
            )
            names[key] = name
            row = [name, string(item, "role")]
            if field == "stakeholders":
                actors[key] = name
                row.append(string(item, "goal"))
            rows.append([*row, citations(item, sources)])
        require(
            rows,
            f"{heading} を記入してください。未確認の担当には確認先を記載してください",
        )
        headers = (
            ("関係者", "業務・判断の責任", "目的・必要な結果", "根拠")
            if field == "stakeholders"
            else ("構成要素", "担当する処理・保有する情報", "根拠")
        )
        lines.extend([f"## {heading}", "", *table(headers, rows)])
    views = [mapping(v, "view") for v in array(doc.get("views"), "views")]
    require(
        {string(v, "kind") for v in views} == set(KINDS),
        "インフラ・ソフトウェア・データフローの3種類の図が必要です",
    )
    scope_type = doc.get("scope_type", "product")
    require(
        scope_type in ("product", "subsystem"), "概要の scope_type を確認してください"
    )
    software = [view for view in views if view["kind"] == "software"]
    for view in software:
        require(
            view.get("level") in (None, "product", "detail"),
            "ソフトウェア図の level を確認してください",
        )
    if scope_type == "subsystem":
        require(
            {"product", "detail"}.issubset(view.get("level") for view in software),
            "部分業務の概要には、製品全体と対象業務を示す2種類のソフトウェア図が必要です",
        )
    for kind, title in KINDS.items():
        lines.extend([f'<a id="view-{kind}"></a>', "", f"## {title}", ""])
        group = [v for v in views if v["kind"] == kind]
        if kind == "software":
            group.sort(key=lambda v: v.get("level") != "product")
        for idx, view in enumerate(group, 1):
            lines.extend(draw_view(view, names, assets, idx, sources))
    lines.extend(
        screens_section(mapping(doc.get("ui"), "ui"), actors, root, assets, revision)
    )
    return intro, lines
