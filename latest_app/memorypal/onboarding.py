"""Welcome choices: who is using MemoryPal, and what that sets up.

Each persona curates the navigation (its everyday pages first), sets
sensible accessibility defaults, and defines a short guided tour of the
pages that person will use most.
"""

PERSONAS = {
    "student": {
        "title": "I'm studying",
        "body": "School, university, exams, or learning a language. Turn notes into cards and practise on a schedule.",
        "nav": ["dashboard", "plan", "capture", "review", "testing", "quiz", "decks", "tools", "shuffle", "stats"],
        "accessibility": {},
        "tour": [
            ("dashboard", "Your home page", "Each day starts here: your study plan's steps for today, your streak and level, and study modes like Quick 10 or Exam cram."),
            ("capture", "Add what you're learning", "Paste notes or type questions and answers. Each small fact becomes its own card."),
            ("plan", "Plan your study", "Say how long you have and what's coming up. Press Make this my plan and the Dashboard turns it into steps to tick off each day."),
            ("review", "Review cards on time", "Answer first, then check. Cards you know come back later; tricky ones come back sooner."),
            ("tools", "Memory techniques", "Turn lists into acronyms, stories, peg lists, or a memory palace."),
            ("stats", "See your progress", "Charts of your practice, what's coming up, how settled your cards are, and badges to earn."),
        ],
    },
    "everyday": {
        "title": "Help with everyday memory",
        "body": "Names, routines, where things are kept, and gentle daily practice. Larger text and a calmer pace.",
        "nav": ["dashboard", "elder", "review", "testing", "games", "capture", "library", "stats"],
        "accessibility": {"text_size": "Large", "simple_language": True, "more_time": True, "reduce_motion": True},
        "tour": [
            ("dashboard", "Your home page", "Start here each day. Pick Gentle review or Daily puzzles, and watch your streak grow."),
            ("elder", "Everyday Memory", "Make cards for people, routines, and places. Press Start Gentle Review to practise."),
            ("review", "Practise your cards", "Read the question, try to remember, then check. Use Read aloud to hear it."),
            ("games", "Gentle puzzles", "Short, calm memory games. There is no rush and no score to worry about."),
            ("settings", "Make it comfortable", "Change the text size, turn on reading aloud, or give yourself more time."),
        ],
    },
    "caregiver": {
        "title": "I'm helping someone else",
        "body": "Set up cards, photos, and voice notes for a family member or someone you care for.",
        "nav": ["dashboard", "elder", "capture", "library", "review", "games", "stats"],
        "accessibility": {"text_size": "Large", "simple_language": True, "more_time": True, "caregiver_mode": True},
        "tour": [
            ("elder", "Build their cards", "Add people, routines, places, and reminders in plain words. Try Create Starter Set."),
            ("capture", "Add photos and voices", "Attach a real photo or a familiar voice recording. These make strong memory cues."),
            ("library", "Check and tidy", "See every card and note in one place. Reset is hidden in caregiver mode."),
            ("review", "Practise together", "Sit together for a short review. Answers can be read aloud."),
            ("settings", "Adjust for them", "Text size, reading aloud, and more time are all here."),
        ],
    },
    "general": {
        "title": "Just exploring",
        "body": "Curious about memory training. See the main tools and try a few puzzles.",
        "nav": ["dashboard", "training", "capture", "review", "games", "plan", "tools", "stats"],
        "accessibility": {},
        "tour": [
            ("dashboard", "Your home page", "What to do today, your streak and level, and quick study modes. Press Ctrl+K any time to jump to a page."),
            ("training", "Memory Gym", "Every technique MemoryPal offers, with a short explanation of why it works."),
            ("capture", "Add something to learn", "Type or paste anything you want to remember."),
            ("review", "Practise on a schedule", "Answer, check, and rate. MemoryPal decides when to show each card again."),
            ("games", "Quick puzzles", "Short recall games for a warm-up or a break."),
        ],
    },
}

PERSONA_ORDER = ("student", "everyday", "caregiver", "general")

# Settings any persona changes; choosing again resets these before applying.
MANAGED_SETTINGS = sorted({key for data in PERSONAS.values() for key in data["accessibility"]})


def persona(key):
    return PERSONAS.get(key) or PERSONAS["general"]


def tour_steps(key):
    return list(persona(key)["tour"])
