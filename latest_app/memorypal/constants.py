APP_NAME = "MemoryPal"
APP_AUTHOR = "MemoryPal"
DEFAULT_PROFILE = "Default"

BASE_DPI = 96
BASE_WINDOW = (1420, 900)
# Small enough to snap to half a laptop screen; pages scroll below it.
BASE_MIN_WINDOW = (760, 500)

SELF_CHECK_ANSWER = "No saved answer. Use this as a self-check prompt, then rate yourself."

# Palette (v96): warm paper and ink in light mode, neutral graphite (not navy)
# in dark mode, one pine-green accent and the logo's amber for streaks. The
# earlier palette was the stock blue / violet / slate set that most generated
# apps share; this one is MemoryPal's own. Rating colours keep their meaning
# (red again, amber hard, green good, blue easy) but are toned to match.
LIGHT_COLORS = {
    "bg": "#f4f2ed",
    "surface": "#fffdf9",
    "surface_soft": "#ece7de",
    "alt": "#e4ded2",
    "ink": "#1e1d1a",
    # Text and filled colours are chosen for WCAG AA (4.5:1): white text on
    # primary/green/danger/violet, and those colours as text on surface.
    "muted": "#5c574e",
    "line": "#e2ddd2",
    "soft_line": "#cfc8ba",
    "primary": "#146b5a",
    "primary_dark": "#0e5547",
    "green": "#2f7323",
    "orange": "#b5541a",
    "pink": "#b8426a",
    "violet": "#7d4a72",
    "cyan": "#1c6f80",
    "rail": "#1e1d1a",
    "rail_hover": "#2c2a26",
    "rail_active": "#1d5a4d",
    "rail_text": "#d9d4c9",
    "rail_muted": "#a8a296",
    "focus": "#a8530c",
    "on_light": "#14130f",
    "white": "#ffffff",
    "danger": "#b42a22",
    "input": "#fffdf9",
    "warm": "#fbf0de",
    "warm_text": "#94500e",
    "mark": "#fae38a",  # highlighted words in notes, under ink text
    "again_bg": "#fbe6e1",
    "again_fg": "#a52a1d",
    "review_bg": "#f9edcf",
    "review_fg": "#7f5100",
    "good_bg": "#e3f1df",
    "good_fg": "#2b6a21",
    "easy_bg": "#e2ecf2",
    "easy_fg": "#2a5c7d",
    "heat_0": "#ebe7de",
    "heat_1": "#c6e3d9",
    "heat_2": "#7dc0ab",
    "heat_3": "#2e8f78",
    "heat_4": "#146b5a",
    "flame": "#d9821f",
    # v100 "taste" pass: the hero panel is the logo's pine tile, with the
    # logo's amber dot; buttons on it are paper-on-pine.
    "hero": "#146b5a",
    "hero_ink": "#ffffff",
    "hero_muted": "#d3e6e0",
    "hero_button": "#fffdf9",
    "hero_button_text": "#0e5547",
    "hero_soft": "#2a7a6a",
    "hero_soft_text": "#ffffff",
    "hero_step": "#1d7564",
    "dot": "#ffb020",
}

DARK_COLORS = {
    "bg": "#141413",
    "surface": "#1d1d1b",
    "surface_soft": "#2d2c29",
    "alt": "#363531",
    "ink": "#eeebe4",
    "muted": "#aaa59b",
    "line": "#34332f",
    "soft_line": "#47453f",
    "primary": "#63c9ae",
    "primary_dark": "#48b496",
    "green": "#86d27a",
    "orange": "#f0a456",
    "pink": "#f08aa8",
    "violet": "#d0a2c6",
    "cyan": "#74c6d6",
    "rail": "#0f0f0e",
    "rail_hover": "#242421",
    "rail_active": "#1f4a40",
    "rail_text": "#d9d4c9",
    "rail_muted": "#a8a296",
    "focus": "#f2c14e",
    # Bright accents (primary, green, violet) carry dark text when filled;
    # see MemoryPalApp.on_color.
    "on_light": "#14130f",
    "white": "#ffffff",
    "danger": "#d0453a",
    "input": "#181816",
    "warm": "#2c2317",
    "warm_text": "#f2b872",
    "mark": "#5c4a12",
    "again_bg": "#3a1d1a",
    "again_fg": "#ff9585",
    "review_bg": "#372b13",
    "review_fg": "#f2c560",
    "good_bg": "#1c3320",
    "good_fg": "#8cdb80",
    "easy_bg": "#1a2a35",
    "easy_fg": "#8fc4e6",
    "heat_0": "#2c2b28",  # empty days must stay visible against surface
    "heat_1": "#1e443b",
    "heat_2": "#26705e",
    "heat_3": "#3ba487",
    "heat_4": "#82dcc3",
    "flame": "#f0a456",
    "hero": "#1d4a40",
    "hero_ink": "#f3f1ec",
    "hero_muted": "#bcd6ce",
    "hero_button": "#63c9ae",
    "hero_button_text": "#14130f",
    "hero_soft": "#2a5b50",
    "hero_soft_text": "#f3f1ec",
    "hero_step": "#245448",
    "dot": "#ffb020",
}

COLORS = dict(DARK_COLORS)

# Each page or study mode keeps one earthy tone everywhere it appears (the
# same in the phone app's TONES): a soft tile behind its line icon, so a list
# reads at a glance instead of as a column of identical green symbols. The
# tones are the palette's own text colours, so they stay calm next to pine.
TONE_KEYS = {
    "pine": "primary",
    "amber": "review_fg",
    "clay": "orange",
    "plum": "violet",
    "slate": "easy_fg",
    "teal": "cyan",
    "moss": "green",
    "rose": "pink",
}

ICON_TONES = {
    "review": "pine", "focus": "amber", "testing": "rose", "capture": "slate",
    "talkback": "plum", "quiz": "teal", "plan": "moss", "dashboard": "moss",
    "study": "plum", "decks": "pine", "library": "slate", "tools": "plum",
    "games": "amber", "elder": "teal", "stats": "moss",
}


# Sets get a tone of their own (picked from the name, so a set keeps its
# colour on every device and in both apps: mobile/src/ui/theme.ts setTone).
SET_TONES = ("pine", "amber", "plum", "slate", "clay", "teal", "moss", "rose")


def set_tone(name):
    value = 0
    for char in str(name or "General"):
        value = (value * 31 + ord(char)) % 4294967296
    return SET_TONES[value % len(SET_TONES)]
