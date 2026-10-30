"""Export the phone app's icons from the desktop logo geometry (memorypal/icon.py).

    python tools\\mobile_icons.py

Writes mobile/assets/:
- icon.png                      1024 full-bleed square (iOS and stores round the corners)
- android-icon-foreground.png   the M alone, inside Android's adaptive-icon safe zone
- android-icon-background.png   the green tile colour, edge to edge
- android-icon-monochrome.png   white M with the folds cut out, for Android themed icons
- splash-icon.png               the rounded tile, for the launch screen
- favicon.png                   48px rounded tile for the web build
"""

import math
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "latest_app"))

from memorypal import icon  # noqa: E402

OUT = ROOT / "mobile" / "assets"


def png(path, size, rows):
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for pixel in row:
            raw.extend(pixel)
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    print("wrote", path)


def render(size, tile=True, rounded=False, mark_scale=1.0, mono=False, logo=True, supersample=4):
    """The logo with options: square or rounded tile (or none), and the M scaled about the centre.

    Without a tile the M stands alone on transparency (Android's adaptive
    foreground). mono gives the M's silhouette in white with the folds cut
    out, for Android themed icons, which use only the alpha channel.
    """
    canvas = size * supersample
    edge = float(supersample)
    top, bottom = icon.rgba(icon.LOGO_COLORS["top"]), icon.rgba(icon.LOGO_COLORS["bottom"])
    mark_rgba, fold_rgba = icon.rgba(icon.LOGO_COLORS["mark"]), icon.rgba(icon.LOGO_COLORS["fold"])
    centre = canvas / 2
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(supersample):
                for sx in range(supersample):
                    px, py = x * supersample + sx + 0.5, y * supersample + sy + 0.5
                    # Map the point back into the unscaled logo's coordinates.
                    mx, my = centre + (px - centre) / mark_scale, centre + (py - centre) / mark_scale
                    mark, fold = icon.mark_samples(mx, my, canvas) if logo else (False, False)
                    if tile:
                        alpha = 255 * (icon.coverage(icon.rounded_square_distance(px, py, canvas, canvas * icon.LOGO_RADIUS), edge) if rounded else 1.0)
                        color = fold_rgba if fold else mark_rgba if mark else icon.blend(top, bottom, py / canvas)
                    elif mono:
                        color, alpha = mark_rgba, 255 if mark and not fold else 0
                    else:
                        color, alpha = (fold_rgba if fold else mark_rgba), 255 if mark else 0
                    acc[0] += color[0] * alpha
                    acc[1] += color[1] * alpha
                    acc[2] += color[2] * alpha
                    acc[3] += alpha
            n = supersample * supersample
            if acc[3]:
                row.append([round(acc[0] / acc[3]), round(acc[1] / acc[3]), round(acc[2] / acc[3]), round(acc[3] / n)])
            else:
                row.append([0, 0, 0, 0])
        rows.append(row)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    png(OUT / "icon.png", 1024, render(1024, tile=True, rounded=False))
    # Android shows the middle ~66% of a foreground layer; keep the mark inside it.
    png(OUT / "android-icon-foreground.png", 1024, render(1024, tile=False, mark_scale=0.72))
    png(OUT / "android-icon-background.png", 1024, render(1024, tile=True, rounded=False, logo=False))
    # Themed icons use only the alpha channel: the M's outline with the folds cut out.
    png(OUT / "android-icon-monochrome.png", 1024, render(1024, tile=False, mark_scale=0.72, mono=True))
    png(OUT / "splash-icon.png", 512, render(512, tile=True, rounded=True))
    png(OUT / "favicon.png", 48, render(48, tile=True, rounded=True, supersample=8))


if __name__ == "__main__":
    main()
