import math
import os
import struct
import tempfile
import zlib
from functools import lru_cache
from pathlib import Path


ICON_SIZES = (16, 32, 48, 64, 128, 256)


def clamp_color(value):
    return max(0, min(255, int(round(value))))


def rgba(hex_color, alpha=255):
    raw = hex_color.lstrip("#")
    return [int(raw[index:index + 2], 16) for index in (0, 2, 4)] + [alpha]


def blend(first, second, ratio):
    return [clamp_color(first[index] + (second[index] - first[index]) * ratio) for index in range(4)]


def inside_rounded_square(x, y, size, radius):
    center_x = min(max(x, radius), size - radius - 1)
    center_y = min(max(y, radius), size - radius - 1)
    return (x - center_x) ** 2 + (y - center_y) ** 2 <= radius * radius


def line_alpha(px, py, x1, y1, x2, y2, width, softness=0.18):
    vx = x2 - x1
    vy = y2 - y1
    wx = px - x1
    wy = py - y1
    length = vx * vx + vy * vy
    position = 0 if length == 0 else max(0, min(1, (wx * vx + wy * vy) / length))
    dx = px - (x1 + vx * position)
    dy = py - (y1 + vy * position)
    distance = math.hypot(dx, dy)
    edge = max(0.75, width * softness)
    return max(0, min(1, (width / 2 + edge - distance) / edge))


def dot_alpha(px, py, cx, cy, radius, softness=0.16):
    distance = math.hypot(px - cx, py - cy)
    edge = max(0.75, radius * softness)
    return max(0, min(1, (radius + edge - distance) / edge))


# Logo geometry, as fractions of the icon size. assets/memorypal-logo.svg
# uses the same numbers on a 1024 grid, so the SVG and every rendered size
# match. The mark is a lowercase "m" drawn as one unbroken line of two
# arches (one idea leading to the next), with an amber dot for the idea you
# just recalled. Flat colour, no gloss or sparkle, so it stays calm and reads
# cleanly from 16px to 1024px.
LOGO_RADIUS = 0.225                      # tile corner radius
LOGO_LEGS = (0.270, 0.500, 0.730)        # x of the three upright strokes
LOGO_ARCH_Y = 0.430                      # y where the arches meet the legs
LOGO_BOTTOM = 0.710                      # y where the legs end (round caps)
LOGO_STROKE = 0.115
LOGO_DOT = (0.775, 0.235, 0.066)         # amber recall dot: x, y, radius
LOGO_COLORS = {
    "top": "#1f7a66",
    "bottom": "#125c4c",
    "mark": "#ffffff",
    "dot": "#ffb020",
}


def arch_distance(px, py, cx, cy, radius):
    """Distance to the upper half of a circle (an arch)."""
    if py <= cy:
        return abs(math.hypot(px - cx, py - cy) - radius)
    return min(math.hypot(px - (cx - radius), py - cy), math.hypot(px - (cx + radius), py - cy))


def logo_mark_distance(px, py, canvas):
    """Signed distance (in pixels) from a point to the white "m" stroke."""
    x = [value * canvas for value in LOGO_LEGS]
    arch_y, bottom = LOGO_ARCH_Y * canvas, LOGO_BOTTOM * canvas
    radius = (x[1] - x[0]) / 2
    legs = min(segment_distance(px, py, leg, arch_y, leg, bottom) for leg in x)
    arches = min(arch_distance(px, py, x[0] + radius, arch_y, radius), arch_distance(px, py, x[1] + radius, arch_y, radius))
    return min(legs, arches) - canvas * LOGO_STROKE / 2


def segment_distance(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    length = vx * vx + vy * vy
    t = 0 if length == 0 else max(0.0, min(1.0, ((px - x1) * vx + (py - y1) * vy) / length))
    return math.hypot(px - (x1 + vx * t), py - (y1 + vy * t))


def coverage(distance, edge):
    """Anti-aliased coverage for a signed distance (negative = inside)."""
    return max(0.0, min(1.0, 0.5 - distance / edge))


def rounded_square_distance(x, y, size, radius):
    half = size / 2
    qx = abs(x - half) - (half - radius)
    qy = abs(y - half) - (half - radius)
    outside = math.hypot(max(qx, 0), max(qy, 0))
    return outside + min(max(qx, qy), 0) - radius


@lru_cache(maxsize=24)
def render_icon_pixels(size, scale=None):
    """Draw the MemoryPal logo as RGBA rows (pure Python, no Pillow needed).

    The mark is two strokes and a dot on a flat tile, so it needs no
    simplified small-size variant: it stays crisp down to 16px.
    """
    scale = scale or (4 if size <= 64 else 3 if size <= 128 else 2)
    canvas = size * scale
    edge = max(1.0, scale * 1.0)
    top = rgba(LOGO_COLORS["top"])
    bottom = rgba(LOGO_COLORS["bottom"])
    mark = rgba(LOGO_COLORS["mark"])
    dot_color = rgba(LOGO_COLORS["dot"])
    radius = canvas * LOGO_RADIUS
    dot_x, dot_y, dot_r = (value * canvas for value in LOGO_DOT)

    pixels = []
    for y in range(canvas):
        row = []
        py = y + 0.5
        # A gentle top-to-bottom shade keeps the flat tile from looking dull.
        base = blend(top, bottom, py / canvas)
        for x in range(canvas):
            px = x + 0.5
            shape = coverage(rounded_square_distance(px, py, canvas, radius), edge)
            if shape <= 0:
                row.append([0, 0, 0, 0])
                continue
            color = blend(base, mark, coverage(logo_mark_distance(px, py, canvas), edge))
            color = blend(color, dot_color, coverage(math.hypot(px - dot_x, py - dot_y) - dot_r, edge))
            color[3] = clamp_color(255 * shape)
            row.append(color)
        pixels.append(row)

    sampled = []
    area = scale * scale
    for y in range(size):
        row = []
        for x in range(size):
            red = green = blue = alpha = 0
            for yy in range(scale):
                source_row = pixels[y * scale + yy]
                for xx in range(scale):
                    r, g, b, a = source_row[x * scale + xx]
                    red += r * a
                    green += g * a
                    blue += b * a
                    alpha += a
            if alpha:
                row.append([clamp_color(red / alpha), clamp_color(green / alpha), clamp_color(blue / alpha), clamp_color(alpha / area)])
            else:
                row.append([0, 0, 0, 0])
        sampled.append(row)
    return sampled


MASTER_SIZE = 256
MASTER_CACHE_VERSION = 4  # bump whenever the logo artwork changes


def master_cache_path():
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "MemoryPal" / f"icon-master-v{MASTER_CACHE_VERSION}.bin"


@lru_cache(maxsize=1)
def master_pixels():
    """The logo at 256px, drawn once and kept on disk between runs.

    Drawing the logo is pure Python and takes seconds at larger sizes, so
    every other size is shrunk from this copy instead of drawn again.
    """
    expected = MASTER_SIZE * MASTER_SIZE * 4
    path = master_cache_path()
    try:
        raw = zlib.decompress(path.read_bytes())
    except (OSError, zlib.error):
        raw = b""
    if len(raw) != expected:
        pixels = render_icon_pixels(MASTER_SIZE, scale=1)
        raw = bytes(channel for row in pixels for pixel in row for channel in pixel)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(zlib.compress(raw, 6))
        except OSError:
            pass
    return raw


@lru_cache(maxsize=24)
def icon_pixels(size):
    """RGBA rows for the logo at any size up to 256, area-averaged from the master."""
    size = max(1, int(size))
    if size <= 32:
        # Tiny sizes are drawn directly, which stays crisp where a shrunk
        # copy of the master would blur.
        return [list(map(list, row)) for row in render_icon_pixels(size)]
    raw = master_pixels()
    master = MASTER_SIZE
    if size >= master:
        return [[list(raw[(y * master + x) * 4:(y * master + x) * 4 + 4]) for x in range(master)] for y in range(master)]
    step = master / size
    bounds = [(int(round(index * step)), max(int(round(index * step)) + 1, int(round((index + 1) * step)))) for index in range(size)]
    rows = []
    for y0, y1 in bounds:
        row = []
        for x0, x1 in bounds:
            red = green = blue = alpha = 0
            for y in range(y0, y1):
                offset = (y * master + x0) * 4
                for _x in range(x0, x1):
                    a = raw[offset + 3]
                    # Premultiply so transparent corners don't darken the edge.
                    red += raw[offset] * a
                    green += raw[offset + 1] * a
                    blue += raw[offset + 2] * a
                    alpha += a
                    offset += 4
            count = (y1 - y0) * (x1 - x0)
            if alpha:
                row.append([clamp_color(red / alpha), clamp_color(green / alpha), clamp_color(blue / alpha), clamp_color(alpha / count)])
            else:
                row.append([0, 0, 0, 0])
        rows.append(row)
    return rows


def dib_from_pixels(pixels):
    height = len(pixels)
    width = len(pixels[0])
    header = struct.pack("<IIIHHIIIIII", 40, width, height * 2, 1, 32, 0, width * height * 4, 0, 0, 0, 0)
    data = bytearray()
    for row in reversed(pixels):
        for red, green, blue, alpha in row:
            data.extend([blue, green, red, alpha])
    mask_stride = ((width + 31) // 32) * 4
    data.extend(b"\x00" * (mask_stride * height))
    return header + bytes(data)


def build_ico_bytes():
    images = [dib_from_pixels(icon_pixels(size)) for size in ICON_SIZES]
    offset = 6 + 16 * len(images)
    entries = []
    for size, image in zip(ICON_SIZES, images):
        size_byte = 0 if size == 256 else size
        entries.append(struct.pack("<BBBBHHII", size_byte, size_byte, 0, 0, 1, 32, len(image), offset))
        offset += len(image)
    return struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + b"".join(images)


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def build_png_bytes(size=1024):
    pixels = render_icon_pixels(size, scale=2)
    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for red, green, blue, alpha in row:
            raw.extend((red, green, blue, alpha))
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + png_chunk(b"IEND", b"")
    )


def ensure_icon_file(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_ico_bytes()
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return path


def ensure_png_file(path, size=1024):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_png_bytes(size)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return path


def export_icon_assets(directory, png_size=1024):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ico_path = ensure_icon_file(directory / "memorypal.ico")
    png_path = ensure_png_file(directory / "memorypal-logo-preview.png", png_size)
    return ico_path, png_path


if __name__ == "__main__":
    target_dir = Path(__file__).resolve().parents[2] / "assets"
    ico_path, png_path = export_icon_assets(target_dir)
    print(f"Wrote {ico_path}")
    print(f"Wrote {png_path}")
