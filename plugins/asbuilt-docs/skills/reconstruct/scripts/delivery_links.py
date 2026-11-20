"""Check local file destinations in the plugin's Markdown delivery, without fetching URLs."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from screen_assets import verify_captures

LINK_START = re.compile(r"\]\(\s*|^ {0,3}\[[^\]]+\]:[ \t]*")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def destinations(line):
    line = INLINE_CODE.sub("", line)
    for match in LINK_START.finditer(line):
        rest = line[match.end() :]
        if rest.startswith("<"):
            end = rest.find(">")
            if end > 0:
                yield rest[1:end]
            continue
        depth = 0
        value = []
        escaped = False
        for ch in rest:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
                continue
            elif ch.isspace() or (ch == ")" and depth == 0):
                break
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            value.append(ch)
        if value:
            yield "".join(value)


def check_delivery(directory):
    root = directory.resolve()
    cache = {}
    errors = []
    missing = 0
    files = 0
    links = 0

    def report(message):
        nonlocal missing
        missing += 1
        if len(errors) < 20:
            errors.append(message)

    for page in root.rglob("*.md"):
        if not page.resolve().is_relative_to(root):
            report(f"{page.relative_to(root)} は納品先の外を参照しています")
            continue
        files += 1
        fence = ""
        with page.open(encoding="utf-8") as rows:
            for number, line in enumerate(rows, 1):
                mark = FENCE.match(line)
                if fence:
                    if (
                        mark
                        and mark[1].startswith(fence)
                        and not line[mark.end() :].strip()
                    ):
                        fence = ""
                    continue
                if mark:
                    fence = mark[1]
                    continue
                for href in destinations(line):
                    parsed = urlsplit(href)
                    drive = len(parsed.scheme) == 1 and href[1:2] == ":"
                    if (parsed.scheme not in ("", "file") and not drive) or (
                        parsed.netloc and not parsed.scheme
                    ):
                        continue
                    path = unquote(parsed.path)
                    if not path and not parsed.scheme:
                        continue
                    links += 1
                    key = (page.parent, path, parsed.scheme)
                    if key not in cache:
                        dest = (page.parent / path).resolve()
                        cache[key] = (
                            not parsed.scheme
                            and not Path(path).is_absolute()
                            and dest.is_relative_to(root)
                            and dest.is_file()
                        )
                    if not cache[key]:
                        report(f"{page.relative_to(root)} L{number}　{href}")
    if not files:
        raise ValueError("納品先にMarkdown資料がありません")
    if missing:
        raise ValueError(
            f"納品資料から開けないローカル参照が{missing}件あります。\n"
            + "\n".join(errors)
        )
    verify_captures(root)
    return files, links
