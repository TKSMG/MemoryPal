"""
MemoryPal_Project_Outline.py

This is a plain-language guide to the current MemoryPal program structure.

The working program itself is:

    ../latest_app/MemoryPalDesktop.py

This file exists so someone reading the project later can understand how the
single-file app is organized without having to read the whole source at once.
It does not replace the app.
"""


SOURCE_FILE = "../latest_app/MemoryPalDesktop.py"


PROGRAM_MAP = [
    (
        "Configuration",
        [
            "App name and data paths.",
            "Default window sizes.",
            "Color palette.",
            "DPI-awareness helper for Windows.",
        ],
    ),
    (
        "Smart-check helpers",
        [
            "normalize_space cleans user text.",
            "split_study_bits turns pasted notes into chunks.",
            "text_tokens extracts comparable words.",
            "answer_assessment scores how close a response is to the expected answer.",
        ],
    ),
    (
        "Data models",
        [
            "Card stores prompt, answer, pathway, association, media, and scheduling data.",
            "Capture stores a title, notes, separated chunks, media, and creation time.",
        ],
    ),
    (
        "Persistence",
        [
            "MemoryStore loads and saves JSON data locally.",
            "Review scheduling updates intervals, repetitions, ease, and lapses.",
        ],
    ),
    (
        "Reusable UI pieces",
        [
            "ScrollFrame gives long screens a vertical scrollbar.",
            "ScrollFrame uses pointer-aware mouse-wheel scrolling across the active page section.",
            "ScrollFrame also supports Page Up, Page Down, Home, and End when focused.",
            "Tooltip gives short hover hints for navigation and important actions.",
            "card_frame creates consistent panels.",
            "button_grid keeps action rows evenly spaced.",
            "media helpers attach, preview, and open image/audio/video files.",
            "media rendering shows text and image previews where possible and play/open buttons for audio/video.",
        ],
    ),
    (
        "Main app shell",
        [
            "MemoryPalApp builds the sidebar, top bar, content area, and toast messages.",
            "The top bar is styled like an app header with a local-save status chip and backup action.",
            "show_view switches between dashboard, capture, review, quiz, repetition, tools, games, and library.",
            "save_current_draft stores in-progress page work before a view is destroyed.",
            "Route changes use a quick reveal animation so page changes feel less abrupt.",
        ],
    ),
    (
        "Dashboard",
        [
            "Shows quick actions.",
            "Recommends the next best study action.",
            "Shows mastery progress and due/learning/mastered chips.",
            "Includes a small daily-action prompt.",
            "Uses hover-highlight dashboard cards and softer filled buttons.",
            "Shows counts for due cards, total cards, captures, and practised items.",
            "Shows weak/new focus counts.",
            "Provides entry points into the main modes.",
        ],
    ),
    (
        "Focus Session",
        [
            "Groups due, weak, and fresh cards.",
            "Lets the user jump directly into practice for a specific card.",
            "Acts like a learner queue with clearer section counts.",
        ],
    ),
    (
        "Capture",
        [
            "Lets the user add study bits one at a time.",
            "Provides separate question and answer fields for exact flashcards.",
            "Can split pasted material into multiple chunks.",
            "Can create direct question-answer cards from question => answer lines.",
            "Can save question-only self-check prompts when no saved answer is wanted.",
            "Can attach image, audio, and video cues.",
            "Audio and video each use one add button, then ask whether to import or record.",
            "Cue controls are compact menu buttons for text, image, audio, and video.",
            "Can create one card per chunk.",
        ],
    ),
    (
        "Review",
        [
            "Shows due cards.",
            "Sends the active card into Test Lab for answering.",
            "Shows a small review start page instead of expanding answer controls inline.",
        ],
    ),
    (
        "Test Lab",
        [
            "Provides a separate test/review page.",
            "Uses a short guide panel so users know to answer first, then check or reveal.",
            "Lets the user return to the previous section.",
            "Supports Smart Check, reveal, and bucket highlighting.",
            "Can schedule review cards from the testing page.",
        ],
    ),
    (
        "Quiz",
        [
            "Self Check mode: user answers, reveals, or smart-checks.",
            "Multiple Choice mode: user chooses from answer options.",
        ],
    ),
    (
        "Repetition Path",
        [
            "Uses separate question/title and answer fields for staged repetition items.",
            "Can still split pasted notes when the user wants bulk entry.",
            "Keeps builder controls and generated practice rounds in one continuous scrollable page.",
            "Shows prompts first.",
            "Uses the start/range pattern.",
            "Example: 5, 5-4, 5-4-3, then 3-2-1.",
        ],
    ),
    (
        "Associations and Games",
        [
            "Associations creates acronyms, auto-generated mini-stories, peg lists, memory palace routes, chunk maps, and link chains.",
            "Puzzles include sequence recall, word recall, pair recall, and missing-item recall.",
        ],
    ),
    (
        "Library",
        [
            "Shows captures as study-bit sets.",
            "Shows cards with paths, hooks, and media.",
            "Supports search and All, Due, Weak, and Captures filters.",
            "Supports import, export, and reset.",
        ],
    ),
]


def print_program_map():
    print("MemoryPal readable program map")
    print("=" * 34)
    print(f"Working source: {SOURCE_FILE}")
    print()
    for section, notes in PROGRAM_MAP:
        print(section)
        print("-" * len(section))
        for note in notes:
            print(f"- {note}")
        print()


if __name__ == "__main__":
    print_program_map()
