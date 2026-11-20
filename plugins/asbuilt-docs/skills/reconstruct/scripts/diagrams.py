"""Render a labelled directed graph as a portable SVG, with or without Graphviz."""

import json
import shutil
import subprocess
import unicodedata
from html import escape


def wrap(label, columns):
    rows, line, width = [], "", 0
    for ch in label:
        size = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if ch == "\n" or (line and width + size > columns):
            rows.append(line)
            line, width = "", 0
        if ch != "\n":
            line += ch
            width += size
    return [*rows, line]


def relationship_rows(nodes, edges, groups, title):
    """Every relationship keeps its direction and boundary when dot is unavailable."""
    boundary = {key: label for label, members in groups.items() for key in members}

    def name(key):
        return "\n".join(filter(None, [boundary.get(key), nodes[key]]))

    used = {key for src, dst, _ in edges for key in (src, dst)}
    rows = [(name(src), label, name(dst)) for src, dst, label in edges]
    rows.extend((name(key), "", "") for key in nodes if key not in used)
    body = []
    top = 10
    for src, label, dst in rows:
        parts = [wrap(src, 24), wrap(label, 27), wrap(dst, 24)]
        height = max(map(len, parts)) * 20 + 22
        mid = top + height / 2
        for x, lines, color in zip(
            (125, 390, 655), parts, ("#164e63", "#334155", "#164e63")
        ):
            if not any(lines):
                continue
            if x != 390:
                body.append(
                    f'<rect x="{x - 116}" y="{top}" width="232" height="{height}" rx="8" fill="#edf6f8" stroke="#387181"/>'
                )
            for offset, line in enumerate(lines):
                y = mid - (len(lines) - 1) * 10 + offset * 20 + (0 if x == 390 else 5)
                body.append(
                    f'<text x="{x}" y="{y}" fill="{color}">{escape(line)}</text>'
                )
        if dst:
            y = mid + (len(parts[1]) - 1) * 10 + 9
            body.append(
                f'<path d="M244 {y} H532 l-8 -5 m8 5 l-8 5" fill="none" stroke="#347485" stroke-width="2"/>'
            )
        top += height + 14
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 {top}" width="780" height="{top}" role="img">'
        f'<title>{escape(title)}</title><g text-anchor="middle" font-family="sans-serif" font-size="15">'
        + "".join(body)
        + "</g></svg>\n"
    ).encode()


def render_svg(nodes, edges, groups, title):
    dot = shutil.which("dot")
    if not dot:
        return relationship_rows(nodes, edges, groups, title)
    # Internal IDs are generated. User-provided names are quoted plain labels.
    ids = {key: f"n{i}" for i, key in enumerate(nodes)}

    def label(value, columns):
        return json.dumps("\n".join(wrap(value, columns)), ensure_ascii=False)

    lines = [
        'digraph G { graph [rankdir=TB, bgcolor="white", pad=.16, nodesep=.38, ranksep=.48, outputorder=edgesfirst];',
        'node [shape=box, style="rounded,filled", fontname="sans-serif", fontsize=13, margin=".17,.10", color="#337588", fillcolor="#e9f5f7", fontcolor="#153a49"];',
        'edge [fontname="sans-serif", fontsize=11, color="#517383", fontcolor="#263f50", arrowsize=.75];',
    ]
    for key in nodes:
        lines.append(f"{ids[key]} [label={label(nodes[key], 24)}];")
    for i, (group, members) in enumerate(groups.items()):
        lines.append(
            f'subgraph cluster_{i} {{ label={label(group, 42)}; style="rounded"; color="#9caeb9"; fontname="sans-serif"; fontsize=12;'
        )
        lines.extend(f"{ids[key]};" for key in members)
        lines.append("}")
    for src, dst, text in edges:
        lines.append(f"{ids[src]} -> {ids[dst]} [label={label(text, 30)}];")
    lines.append("}")
    result = subprocess.run(
        [dot, "-Tsvg"],
        input="\n".join(lines).encode(),
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            "構成図の描画に失敗しました。関係と図の大きさを確認してください"
        )
    return result.stdout
