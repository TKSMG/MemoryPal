"""
MemoryPal v66 beta - accessibility and elder support.

This milestone records the pass that made MemoryPal easier to tune for older
adults, people with memory changes, and caregiver-supported use. The live app
keeps the full feature set; this standalone version shows the calmer Everyday
Memory page, accessibility toggles, and large clear controls.
"""

import tkinter as tk
from datetime import date


APP_NAME = "MemoryPal"
BG = "#0f1726"
SURFACE = "#192338"
ALT = "#263a57"
WARM = "#2a2118"
PRIMARY = "#75bdff"
GREEN = "#49d98a"
ORANGE = "#ffb052"
INK = "#f3f7ff"
MUTED = "#d2dced"
LINE = "#6d7d96"


class MemoryPalV66(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v66")
        self.geometry("1080x700")
        self.minsize(820, 560)
        self.configure(bg=BG)
        self.text_size = tk.StringVar(value="Large")
        self.high_contrast = tk.BooleanVar(value=True)
        self.reduce_motion = tk.BooleanVar(value=True)
        self.caregiver_mode = tk.BooleanVar(value=True)
        self.cards = []
        self.shell()

    def shell(self):
        rail = tk.Frame(self, bg="#08111f", width=280)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        tk.Label(rail, text=APP_NAME, bg="#08111f", fg=INK, font=("Segoe UI Semibold", 25)).pack(anchor="w", padx=26, pady=(32, 8))
        tk.Label(rail, text="Senior-friendly layout", bg="#08111f", fg=MUTED, font=("Segoe UI", 13)).pack(anchor="w", padx=26, pady=(0, 24))
        for label, command in (
            ("Everyday Memory", self.show_everyday),
            ("Accessibility", self.show_accessibility),
            ("Gentle Review", self.show_review),
        ):
            tk.Button(rail, text=label, command=command, relief="flat", bg="#10213a", fg=INK, activebackground=ALT, activeforeground=PRIMARY, anchor="w", padx=18, pady=16, font=("Segoe UI Semibold", 13)).pack(fill="x", padx=20, pady=6)

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        self.show_everyday()

    def clear(self, title):
        for child in self.main.winfo_children():
            child.destroy()
        tk.Label(self.main, text=title, bg=BG, fg=INK, font=("Segoe UI Semibold", 30)).pack(anchor="w", padx=34, pady=(32, 14))

    def card(self, title, body, color=PRIMARY):
        frame = tk.Frame(self.main, bg=SURFACE, padx=26, pady=22, highlightthickness=1, highlightbackground=LINE)
        frame.pack(fill="x", padx=34, pady=(0, 14))
        tk.Frame(frame, bg=color, width=42, height=5).pack(anchor="w", pady=(0, 12))
        tk.Label(frame, text=title, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 19)).pack(anchor="w")
        tk.Label(frame, text=body, bg=SURFACE, fg=MUTED, font=("Segoe UI", 14), wraplength=760, justify="left").pack(anchor="w", pady=(7, 0))
        return frame

    def show_everyday(self):
        self.clear("Everyday Memory")
        today = date.today().strftime("%A, %B %d, %Y")
        today_card = self.card("Today board", f"Today is {today}.\nOne small step is enough: review one card, add one reminder, or play one gentle puzzle.", GREEN)
        tk.Button(today_card, text="Start Gentle Review", command=self.show_review, bg=GREEN, fg="white", relief="flat", padx=18, pady=14, font=("Segoe UI Semibold", 13)).pack(fill="x", pady=(18, 0))

        builder = self.card("Caregiver card builder", "Create a short card for a person, place, routine, or reminder. Keep the wording familiar and kind.", PRIMARY)
        self.prompt = tk.Entry(builder, bg="#0f1b2f", fg=INK, insertbackground=PRIMARY, relief="flat", font=("Segoe UI", 14))
        self.prompt.insert(0, "Who is this person?")
        self.prompt.pack(fill="x", pady=(16, 8), ipady=10)
        self.answer = tk.Text(builder, height=4, bg="#0f1b2f", fg=INK, insertbackground=PRIMARY, relief="flat", font=("Segoe UI", 14), wrap="word")
        self.answer.insert("1.0", "This is Maya, your granddaughter. She visits on Sundays.")
        self.answer.pack(fill="x", pady=(0, 12))
        tk.Button(builder, text="Add Everyday Card", command=self.add_card, bg=PRIMARY, fg="white", relief="flat", padx=18, pady=14, font=("Segoe UI Semibold", 13)).pack(fill="x")

        self.card("Care note", "This kind of tool can support memory practice and reminders. It is not a medical device or emergency tool.", ORANGE)

    def add_card(self):
        prompt = self.prompt.get().strip()
        answer = self.answer.get("1.0", "end").strip()
        if prompt and answer:
            self.cards.insert(0, (prompt, answer))
        self.show_review()

    def show_accessibility(self):
        self.clear("Accessibility")
        panel = self.card("Profile accessibility", "These settings make the app calmer: larger text, stronger contrast, reduced motion, and caregiver-supported setup.", PRIMARY)
        for variable, label in (
            (self.high_contrast, "Higher contrast"),
            (self.reduce_motion, "Reduce motion"),
            (self.caregiver_mode, "Caregiver mode"),
        ):
            tk.Checkbutton(panel, text=label, variable=variable, bg=SURFACE, fg=INK, selectcolor="#0f1b2f", activebackground=SURFACE, activeforeground=PRIMARY, font=("Segoe UI", 14)).pack(anchor="w", pady=4)

    def show_review(self):
        self.clear("Gentle Review")
        if not self.cards:
            self.card("No everyday cards yet", "Add a person, routine, place, or reminder card first.", ORANGE)
            return
        prompt, answer = self.cards[0]
        review = self.card(prompt, "Answer from memory, then reveal. Missing something only means the cue needs another calm pass.", GREEN)
        hidden = tk.Label(review, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 14), wraplength=740, justify="left")
        hidden.pack(anchor="w", pady=(14, 0))
        tk.Button(review, text="Reveal Answer", command=lambda: hidden.configure(text=answer), bg=GREEN, fg="white", relief="flat", padx=18, pady=14, font=("Segoe UI Semibold", 13)).pack(fill="x", pady=(16, 0))


if __name__ == "__main__":
    MemoryPalV66().mainloop()
