"""Export the phone app's icons from the desktop logo geometry (memorypal/icon.py).

    python tools\\mobile_icons.py

Writes mobile/assets/:
- icon.png                      1024 full-bleed square (iOS and stores round the corners)
- android-icon-foreground.png   the card alone, inside Android's adaptive-icon safe zone
- android-icon-background.png   the green tile colour, edge to edge
- android-icon-monochrome.png   white card with the "m" cut out, for Android themed icons
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


def render(size, tile=True, rounded=False, mark_scale=1.0, mono=False, logo=True, supersample=2):
    """The logo with options: square or rounded tile (or none), and the card scaled about the centre.

    Without a tile the card stands alone on transparency (Android's adaptive
    foreground). mono gives the card's silhouette in white with the "m" cut
    out, for Android themed icons, which use only the alpha channel.
    """
    canvas = size * supersample
    edge = float(supersample)
    top, bottom = icon.rgba(icon.LOGO_COLORS["top"]), icon.rgba(icon.LOGO_COLORS["bottom"])
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
                    card_edge = edge / mark_scale
                    if tile:
                        alpha = 255 * (icon.coverage(icon.rounded_square_distance(px, py, canvas, canvas * icon.LOGO_RADIUS), edge) if rounded else 1.0)
                        color = icon.blend(top, bottom, py / canvas)
                        if logo:
                            color = icon.paint_logo(color, mx, my, canvas, card_edge)
                    else:
                        card = icon.coverage(icon.card_distance(mx, my, canvas), card_edge)
                        fold = icon.coverage(icon.fold_distance(mx, my, canvas), card_edge)
                        shape = max(card, fold)
                        if mono:
                            color = [255, 255, 255, 0]
                            alpha = 255 * shape * (1 - icon.coverage(icon.logo_mark_distance(mx, my, canvas), card_edge))
                        else:
                            color = icon.paint_logo(icon.rgba(icon.LOGO_COLORS["card"]), mx, my, canvas, card_edge)
                            alpha = 255 * shape
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
    # Themed icons use only the alpha channel: the card's outline with the "m" cut out.
    png(OUT / "android-icon-monochrome.png", 1024, render(1024, tile=False, mark_scale=0.72, mono=True))
    png(OUT / "splash-icon.png", 512, render(512, tile=True, rounded=True))
    png(OUT / "favicon.png", 48, render(48, tile=True, rounded=True, supersample=4))


if __name__ == "__main__":
    main()
