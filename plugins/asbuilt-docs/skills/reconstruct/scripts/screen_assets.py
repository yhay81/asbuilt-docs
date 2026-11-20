"""Check transport integrity of locally captured PNG/JPEG files without an image library."""

import hashlib
import re
import struct
import zlib

from ledger import load, path_within, require

CAPTURES = "screen-captures.asbuilt.json"


def verify_png(stream):
    if stream.read(8) != b"\x89PNG\r\n\x1a\n":
        return False
    first = True
    has_data = False
    while len(header := stream.read(8)) == 8:
        size, tag = struct.unpack(">I4s", header)
        if first:
            if tag != b"IHDR" or size != 13:
                return False
            first = False
        crc = zlib.crc32(tag)
        remaining = size
        while remaining:
            chunk = stream.read(min(remaining, 1 << 20))
            if not chunk:
                return False
            if tag == b"IHDR" and (
                len(chunk) != 13 or not all(struct.unpack(">II", chunk[:8]))
            ):
                return False
            crc = zlib.crc32(chunk, crc)
            remaining -= len(chunk)
        if stream.read(4) != struct.pack(">I", crc):
            return False
        if tag == b"IDAT" and size:
            has_data = True
        if tag == b"IEND":
            return has_data and size == 0 and not stream.read(1)
    return False


def verify_jpeg(stream):
    if stream.read(2) != b"\xff\xd8":
        return False
    has_frame = False
    while stream.read(1) == b"\xff":
        marker = stream.read(1)
        while marker == b"\xff":
            marker = stream.read(1)
        length = stream.read(2)
        if not marker or len(length) != 2:
            return False
        size = int.from_bytes(length, "big") - 2
        if size < 0:
            return False
        payload = stream.read(size)
        if len(payload) != size:
            return False
        if marker[0] in (
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        ):
            has_frame = len(payload) >= 6 and all(struct.unpack(">HH", payload[1:5]))
        if marker == b"\xda":
            scan = stream.tell()
            stream.seek(0, 2)
            if stream.tell() <= scan + 2:
                return False
            stream.seek(-2, 2)
            return has_frame and stream.read(2) == b"\xff\xd9"
    return False


def verify_image(path, expected):
    require(
        isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
        "撮影原本のSHA-256が必要です",
    )
    with path.open("rb") as stream:
        valid = (
            verify_png(stream) if path.suffix.lower() == ".png" else verify_jpeg(stream)
        )
        require(valid, f"画像の形式を読み取れません: {path.name}")
        stream.seek(0)
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    require(
        digest.hexdigest() == expected, f"撮影原本と画像が一致しません: {path.name}"
    )


def verify_captures(root):
    for index in root.rglob(CAPTURES):
        require(
            index.resolve().is_relative_to(root), "画面記録が納品先の外を参照しています"
        )
        doc = load(index)
        require(
            isinstance(doc, dict)
            and isinstance(doc.get("images"), dict)
            and doc["images"],
            "画面の原本照合記録を確認してください",
        )
        for name, digest in doc["images"].items():
            require(
                re.fullmatch(r"screen-[0-9]+\.(png|jpe?g)", name),
                f"画面ファイル名を確認してください: {name}",
            )
            verify_image(path_within(index.parent, name), digest)
