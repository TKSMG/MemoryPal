"""Add a caption and a device frame to the raw captures from capture_phone.js.

python tools/store_shots/frame.py RAW_DIR OUT_DIR

Writes OUT_DIR/google/phone, google/tablet-7, google/tablet-10,
apple/iphone-6.9 and apple/ipad-13 at each store's size, on the logo's pine.
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAW, OUT = sys.argv[1], sys.argv[2]

# raw folder -> (output folder, canvas size)
DEVICES = {
    "phone": ("google/phone", (1080, 1920)),
    "tablet-7": ("google/tablet-7", (1200, 1920)),
    "tablet-10": ("google/tablet-10", (1600, 2560)),
    "iphone-6.9": ("apple/iphone-6.9", (1320, 2868)),
    "ipad-13": ("apple/ipad-13", (2064, 2752)),
}

CAPTIONS = {
    "01-today": "Your day's review\nin one tap",
    "02-review": "Answer from memory,\nthen rate how it went",
    "03-study": "Quick 10, weak cards,\nquizzes and Talk-back",
    "04-progress": "Watch your streak\nand progress grow",
    "05-set": "Each set keeps its notes\nand plans for the exam",
    "06-create": "Make cards in seconds,\nor with AI",
}

PINE_TOP, PINE_BOTTOM = (20, 107, 90), (13, 74, 62)
DOT = (255, 176, 32)
BEZEL = (24, 28, 27)
FONT = next((f for f in ("/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if os.path.exists(f)), None)


def background(size):
    w, h = size
    top = Image.new("RGB", (1, 2), PINE_TOP)
    top.putpixel((0, 1), PINE_BOTTOM)
    return top.resize((w, h), Image.BILINEAR)


def rounded(image, radius):
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height + radius), radius, fill=255)
    return mask


def compose(raw_path, size, caption):
    w, h = size
    canvas = background(size)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, int(w * 0.068)) if FONT else ImageFont.load_default()
    caption_bottom = int(h * 0.19)
    box = draw.multiline_textbbox((0, 0), caption, font=font, spacing=int(w * 0.018), align="center")
    tx = (w - (box[2] - box[0])) // 2
    ty = (caption_bottom - (box[3] - box[1])) // 2 + int(h * 0.01)
    draw.multiline_text((tx, ty), caption, font=font, fill="white", spacing=int(w * 0.018), align="center")
    # The logo's amber dot, after the caption.
    r = int(w * 0.012)
    draw.ellipse((w // 2 - r, ty + box[3] + int(h * 0.018), w // 2 + r, ty + box[3] + int(h * 0.018) + 2 * r), fill=DOT)

    frame_w = int(w * 0.84)
    bezel = max(12, int(w * 0.022))
    frame_x = (w - frame_w) // 2
    frame_y = int(h * 0.235)
    screen_w = frame_w - 2 * bezel
    shot = Image.open(raw_path).convert("RGB")
    shot = shot.resize((screen_w, round(shot.height * screen_w / shot.width)), Image.LANCZOS)
    screen_h = h - frame_y - bezel
    if shot.height < screen_h:
        filled = Image.new("RGB", (screen_w, screen_h), shot.getpixel((2, shot.height - 2)))
        filled.paste(shot, (0, 0))
        shot = filled
    shot = shot.crop((0, 0, screen_w, screen_h))
    outer_r = int(frame_w * 0.09)
    # Soft shadow, then the bezel, then the screen.
    shadow = Image.new("L", size, 0)
    ImageDraw.Draw(shadow).rounded_rectangle((frame_x, frame_y + 12, frame_x + frame_w, h + outer_r), outer_r, fill=110)
    canvas.paste((0, 0, 0), (0, 0), shadow.filter(ImageFilter.GaussianBlur(int(w * 0.02))))
    ImageDraw.Draw(canvas).rounded_rectangle((frame_x, frame_y, frame_x + frame_w, h + outer_r), outer_r, fill=BEZEL)
    canvas.paste(shot, (frame_x + bezel, frame_y + bezel), rounded(shot, outer_r - bezel))
    return canvas


for device, (folder, size) in DEVICES.items():
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    for raw_path in sorted(glob.glob(os.path.join(RAW, device, "*.png"))):
        name = os.path.splitext(os.path.basename(raw_path))[0]
        out = os.path.join(OUT, folder, name + ".png")
        compose(raw_path, size, CAPTIONS[name]).save(out, optimize=True)
        print(out)
