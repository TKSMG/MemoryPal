"""A small file that keeps the antialiased line icons between runs.

Drawing an icon is pure Python (16 samples a pixel along every edge), which
costs a noticeable part of a second at start and on the first visit to some
pages, most of all on slower computers. The pictures only change when the
icon shapes do, so they are saved once and read back on later starts.

The file holds a key made from the icon shapes; when the shapes change, the
key no longer matches and the old pictures are ignored and replaced.
"""

import hashlib
import os
import struct
import zlib
from pathlib import Path

MAGIC = b"MPIC1"


def shapes_key(*parts):
    """A short key that changes whenever any of the icon definitions do."""
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()[:20].encode("ascii")


def load(path, key):
    """{(name, size): coverage bytes} saved under this key, or {}."""
    try:
        raw = zlib.decompress(Path(path).read_bytes())
    except (OSError, zlib.error):
        return {}
    head = len(MAGIC) + len(key)
    if raw[:head] != MAGIC + key:
        return {}
    found = {}
    offset = head
    try:
        while offset < len(raw):
            name_len, size = struct.unpack_from(">BH", raw, offset)
            offset += 3
            name = raw[offset:offset + name_len].decode("utf-8")
            offset += name_len
            length = size * size
            data = raw[offset:offset + length]
            if len(data) != length:
                break
            offset += length
            found[(name, size)] = bytearray(data)
    except (struct.error, UnicodeDecodeError):
        return {}
    return found


def save(path, key, coverage):
    """Write every icon in coverage under this key; quietly skip on errors."""
    parts = [MAGIC, key]
    for (name, size), data in sorted(coverage.items()):
        encoded = name.encode("utf-8")
        if len(encoded) > 255 or size > 0xFFFF or len(data) != size * size:
            continue
        parts.append(struct.pack(">BH", len(encoded), size))
        parts.append(encoded)
        parts.append(bytes(data))
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(zlib.compress(b"".join(parts), 6))
        os.replace(temp, path)
        return True
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass
        return False
