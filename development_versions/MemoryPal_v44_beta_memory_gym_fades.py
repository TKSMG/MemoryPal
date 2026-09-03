import tkinter as tk
from tkinter import ttk


BG = "#101827"
SURFACE = "#182235"
ALT = "#24324b"
INK = "#e8edf7"
MUTED = "#a3b0c8"
PRIMARY = "#5aa8ff"
GREEN = "#37d67a"
ORANGE = "#ffab3d"
PINK = "#ff5c8a"
CYAN = "#4fd1e6"


class MemoryPalV44(tk.Tk):
    """Standalone milestone showing the first Memory Gym and fade direction."""

    def __init__(self):
        super().__init__()
        self.title("MemoryPal v44 - Memory Gym")
        self.geometry("980x680")
        self.minsize(760, 520)
        self.configure(bg=BG)
        self.current_page = None
        self.build_styles()
        self.build_shell()
        self.show_page("gym")

    def build_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Root.TFrame", background=BG)
        self.style.configure("Rail.TFrame", background="#0b1020")
        self.style.configure("Card.TFrame", background=SURFACE, relief="flat")
        self.style.configure("Alt.TFrame", background=ALT, relief="flat")
        self.style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 11))
        self.style.configure("Card.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI", 11))
        self.style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED, font=("Segoe UI", 10))
        self.style.configure("H1.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 22))
        self.style.configure("H2.TLabel", background=SURFACE, foreground=INK, font=("Segoe UI Semibold", 15))
        self.style.configure("TButton", background=ALT, foreground=INK, padding=(14, 10), borderwidth=0)
        self.style.map("TButton", background=[("active", "#314464")])
        self.style.configure("Primary.TButton", background=PRIMARY, foreground="white", padding=(14, 10), borderwidth=0)

    def build_shell(self):
        self.body = ttk.Frame(self, style="Root.TFrame")
        self.body.pack(fill="both", expand=True)
        rail = ttk.Frame(self.body, style="Rail.TFrame", width=180)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        tk.Label(rail, text="MemoryPal", bg="#0b1020", fg="white", font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=18, pady=(24, 14))
        for key, label in [("gym", "Memory Gym"), ("study", "Study Track"), ("everyday", "Everyday Track")]:
            ttk.Button(rail, text=label, command=lambda page=key: self.show_page(page)).pack(fill="x", padx=14, pady=5)
        self.content = ttk.Frame(self.body, style="Root.TFrame")
        self.content.pack(side="left", fill="both", expand=True, padx=28, pady=28)

    def fade_cover(self):
        cover = tk.Toplevel(self)
        cover.overrideredirect(True)
        cover.configure(bg=BG)
        self.update_idletasks()
        cover.geometry(f"{self.winfo_width()}x{self.winfo_height()}+{self.winfo_rootx()}+{self.winfo_rooty()}")
        cover.attributes("-alpha", 1.0)
        cover.lift(self)
        return cover

    def fade_out_cover(self, cover, step=0):
        if not cover.winfo_exists():
            return
        steps = (1.0, 0.82, 0.64, 0.46, 0.30, 0.14, 0.0)
        cover.attributes("-alpha", steps[min(step, len(steps) - 1)])
        if step < len(steps) - 1:
            self.after(18, lambda: self.fade_out_cover(cover, step + 1))
        else:
            cover.destroy()

    def show_page(self, page):
        cover = self.fade_cover()
        for child in self.content.winfo_children():
            child.destroy()
        self.current_page = page
        if page == "gym":
            self.memory_gym()
        elif page == "study":
            self.study_track()
        else:
            self.everyday_track()
        self.after(45, lambda: self.fade_out_cover(cover))

    def card(self, title, body, color):
        frame = ttk.Frame(self.content, style="Card.TFrame", padding=20)
        frame.pack(fill="x", pady=(0, 12))
        tk.Frame(frame, bg=color, width=36, height=4).pack(anchor="w", pady=(0, 12))
        ttk.Label(frame, text=title, style="H2.TLabel").pack(anchor="w")
        ttk.Label(frame, text=body, style="Muted.TLabel", wraplength=660).pack(anchor="w", pady=(6, 0))

    def memory_gym(self):
        self.card("Memory Gym", "A clear hub for student study drills and gentle everyday memory support.", CYAN)
        self.card("Student study track", "Retrieval practice, spaced practice, interleaving, elaboration, concrete examples, and dual coding.", PRIMARY)
        self.card("Everyday memory track", "Spaced retrieval, name recall, routine recall, attention games, and cue-based practice.", GREEN)

    def study_track(self):
        self.card("Retrieval practice", "Answer before revealing. Check the response, then review again later.", PRIMARY)
        self.card("Interleaving", "Mix related material instead of practising one kind of question in a block.", ORANGE)
        self.card("Dual coding", "Pair words with images, sketches, audio, or video cues.", PINK)

    def everyday_track(self):
        self.card("Spaced retrieval", "Practise one important fact, wait a little, then try again.", GREEN)
        self.card("Routine prompts", "Use short step lists for medicine, appointments, places, and daily tasks.", CYAN)
        self.card("Attention warmups", "Use small visual search or missing-item rounds before review.", PRIMARY)


if __name__ == "__main__":
    MemoryPalV44().mainloop()
