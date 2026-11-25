"""Check that every desktop page lines up on one left and right edge: the tab
bar's logo, the page title, the cards, and on the right Feedback, the header
icons and the cards (see PAGE_GUTTER in MemoryPalDesktop.py).

    xvfb-run -a -s "-screen 0 1600x1000x24 -dpi 96" python tools/render_check/alignment_audit.py [--pages a b]

Reuses page_review.py's demo library and window. Reads the first screen of
each page as pixels (so a letter's side bearing counts the way the eye sees
it) and prints the first and last painted column in each band. Exits 1 when
a page's edges drift more than TOLERANCE pixels apart.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
source = open(os.path.join(HERE, "page_review.py"), encoding="utf-8").read()
setup = source.split("views = [v for v in app.page_titles()]")[0]
args = sys.argv[1:]
only = args[args.index("--pages") + 1:] if "--pages" in args else []
sys.argv = [sys.argv[0], os.path.join(HERE, "_alignment_out"), "dark", "--no-dialogs"]
namespace = {"__file__": os.path.join(HERE, "page_review.py"), "__name__": "page_review_setup"}
exec(compile(setup, "page_review.py", "exec"), namespace)
app, pump, M = namespace["app"], namespace["pump"], namespace["M"]
from PIL import ImageGrab  # noqa: E402

TOLERANCE = 4


def edges(image, top, bottom, skip_right=0):
    width = image.width
    px = image.load()
    bg = px[2, image.height - 3]

    def painted(x):
        return any(sum(abs(a - b) for a, b in zip(px[x, y][:3], bg[:3])) > 12 for y in range(top, bottom, 2))

    left = next((x for x in range(width // 2) if painted(x)), None)
    right = next((width - 1 - x for x in range(width - 1 - skip_right, width // 2, -1) if painted(x)), None)
    return left, right


views = only or [v for v in app.page_titles() if v not in ("welcome", "signin")]
pump(1.0)
gutter = app.px(app.PAGE_GUTTER)
bar = app.tab_bar_height()
scroll_room = app.px(16)  # the gap and scrollbar inside the right gutter
print(f"ui_scale {getattr(app, 'ui_scale', 1)}, gutter {gutter}px")
print(f"{'page':14} {'logo':>5} {'title':>6} {'cards':>6} | {'feedback':>8} {'icons':>6} {'cards':>6}")
bad = []
for view in views:
    app.show_view(view)
    pump(0.8)
    x0, y0 = app.winfo_rootx(), app.winfo_rooty()
    shot = ImageGrab.grab(bbox=(x0, y0, x0 + app.winfo_width(), y0 + app.winfo_height())).convert("RGB")
    header = app.title_label.winfo_rooty() - y0
    content = app.content.winfo_rooty() - y0
    logo_l, feedback_r = edges(shot, 4, bar - 4)
    title_l, icons_r = edges(shot, header, header + app.title_label.winfo_height())
    cards_l, cards_r = edges(shot, content + 4, shot.height - 8, skip_right=max(0, gutter - scroll_room) + scroll_room + 2)
    print(f"{view:14} {logo_l!s:>5} {title_l!s:>6} {cards_l!s:>6} | {feedback_r!s:>8} {icons_r!s:>6} {cards_r!s:>6}")
    lefts = [v for v in (logo_l, title_l, cards_l) if v is not None]
    rights = [v for v in (feedback_r, icons_r, cards_r) if v is not None]
    if (lefts and max(lefts) - min(lefts) > TOLERANCE) or (rights and max(rights) - min(rights) > TOLERANCE):
        bad.append(view)

print("misaligned:", ", ".join(bad) if bad else "none")
sys.stdout.flush()
os._exit(1 if bad else 0)
