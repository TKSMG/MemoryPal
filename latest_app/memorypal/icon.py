import math
import struct
import zlib
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


def render_icon_pixels(size, scale=None):
    scale = scale or (4 if size <= 128 else 2)
    canvas_size = size * scale
    radius = canvas_size * 0.24
    top = rgba("#67b7ff")
    middle = rgba("#4f8fff")
    bottom = rgba("#7868ff")
    glow = rgba("#c7fbff")
    mint = rgba("#83ffd8")
    white = rgba("#ffffff")
    shadow = rgba("#101827")
    line_shadow = rgba("#14305a")
    pixels = []

    for y in range(canvas_size):
        row = []
        for x in range(canvas_size):
            if not inside_rounded_square(x, y, canvas_size, radius):
                row.append([0, 0, 0, 0])
                continue

            vertical = y / (canvas_size - 1)
            color = blend(top, middle, min(1, vertical * 1.55))
            if vertical > 0.48:
                color = blend(color, bottom, (vertical - 0.48) / 0.52)
            color = blend(color, glow, dot_alpha(x, y, canvas_size * 0.76, canvas_size * 0.18, canvas_size * 0.34, 0.28) * 0.22)
            color = blend(color, white, dot_alpha(x, y, canvas_size * 0.22, canvas_size * 0.16, canvas_size * 0.34, 0.4) * 0.08)
            shade = 0.95 + 0.06 * (1 - vertical)
            color = [clamp_color(color[0] * shade), clamp_color(color[1] * shade), clamp_color(color[2] * shade), 255]

            path_mark = max(
                line_alpha(x, y, canvas_size * 0.25, canvas_size * 0.70, canvas_size * 0.43, canvas_size * 0.34, canvas_size * 0.085, 0.18),
                line_alpha(x, y, canvas_size * 0.43, canvas_size * 0.34, canvas_size * 0.58, canvas_size * 0.58, canvas_size * 0.085, 0.18),
                line_alpha(x, y, canvas_size * 0.58, canvas_size * 0.58, canvas_size * 0.77, canvas_size * 0.30, canvas_size * 0.085, 0.18),
            )
            color = blend(color, mint, path_mark * 0.24)

            shadow_mark = max(
                line_alpha(x - canvas_size * 0.015, y - canvas_size * 0.025, canvas_size * 0.245, canvas_size * 0.72, canvas_size * 0.245, canvas_size * 0.31, canvas_size * 0.16, 0.14),
                line_alpha(x - canvas_size * 0.015, y - canvas_size * 0.025, canvas_size * 0.245, canvas_size * 0.31, canvas_size * 0.50, canvas_size * 0.62, canvas_size * 0.16, 0.14),
                line_alpha(x - canvas_size * 0.015, y - canvas_size * 0.025, canvas_size * 0.50, canvas_size * 0.62, canvas_size * 0.755, canvas_size * 0.31, canvas_size * 0.16, 0.14),
                line_alpha(x - canvas_size * 0.015, y - canvas_size * 0.025, canvas_size * 0.755, canvas_size * 0.31, canvas_size * 0.755, canvas_size * 0.72, canvas_size * 0.16, 0.14),
            )
            color = blend(color, line_shadow, shadow_mark * 0.18)

            main_mark = max(
                line_alpha(x, y, canvas_size * 0.245, canvas_size * 0.72, canvas_size * 0.245, canvas_size * 0.31, canvas_size * 0.135, 0.10),
                line_alpha(x, y, canvas_size * 0.245, canvas_size * 0.31, canvas_size * 0.50, canvas_size * 0.62, canvas_size * 0.135, 0.10),
                line_alpha(x, y, canvas_size * 0.50, canvas_size * 0.62, canvas_size * 0.755, canvas_size * 0.31, canvas_size * 0.135, 0.10),
                line_alpha(x, y, canvas_size * 0.755, canvas_size * 0.31, canvas_size * 0.755, canvas_size * 0.72, canvas_size * 0.135, 0.10),
            )
            color = blend(color, white, main_mark * 0.96)

            for cx, cy, dot_radius in (
                (canvas_size * 0.245, canvas_size * 0.31, canvas_size * 0.062),
                (canvas_size * 0.50, canvas_size * 0.62, canvas_size * 0.060),
                (canvas_size * 0.755, canvas_size * 0.31, canvas_size * 0.062),
            ):
                dot_shadow = dot_alpha(x - canvas_size * 0.012, y - canvas_size * 0.018, cx, cy, dot_radius * 1.12, 0.12)
                amount = dot_alpha(x, y, cx, cy, dot_radius, 0.08)
                color = blend(color, shadow, dot_shadow * 0.20)
                color = blend(color, white, amount * 0.98)

            row.append(color)
        pixels.append(row)

    sampled = []
    for y in range(size):
        row = []
        for x in range(size):
            total = [0, 0, 0, 0]
            for yy in range(scale):
                for xx in range(scale):
                    source = pixels[y * scale + yy][x * scale + xx]
                    for channel in range(4):
                        total[channel] += source[channel]
            row.append([clamp_color(value / (scale * scale)) for value in total])
        sampled.append(row)
    return sampled


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
    images = [dib_from_pixels(render_icon_pixels(size)) for size in ICON_SIZES]
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


def export_icon_assets(directory, png_size=512):
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
