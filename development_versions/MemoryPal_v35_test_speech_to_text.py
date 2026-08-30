"""
MemoryPal v35 test - speech-to-text capture

Independent milestone prototype. This version records the point where spoken
input became part of the desktop capture direction. It supports optional
microphone transcription and audio-file transcription when SpeechRecognition
and the right audio dependencies are installed.
"""

import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk


VERSION = "v35 Test"
COLORS = {
    "bg": "#f4f7fb",
    "surface": "#ffffff",
    "soft": "#edf6ff",
    "ink": "#111827",
    "muted": "#64748b",
    "line": "#dbeafe",
    "primary": "#007aff",
    "green": "#34c759",
    "orange": "#ff9500",
}


def enable_dpi_awareness():
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def clean(value):
    return " ".join((value or "").split())


class SpeechStage(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, min(self.winfo_fpixels("1i") / 96, 1.35))
        self.cards = []
        self.title(f"MemoryPal {VERSION} - Speech To Text")
        self.geometry(f"{self.px(1080)}x{self.px(760)}")
        self.minsize(self.px(880), self.px(620))
        self.configure(bg=COLORS["bg"])
        self.configure_styles()
        self.build()

    def px(self, value):
        return int(round(value * self.scale))

    def configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"])
        style.configure("Soft.TFrame", background=COLORS["soft"])
        style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI Semibold", self.px(24)))
        style.configure("H2.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI Semibold", self.px(17)))
        style.configure("Text.TLabel", background=COLORS["surface"], foreground=COLORS["ink"], font=("Segoe UI", self.px(11)))
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", self.px(10)))
        style.configure("Soft.TLabel", background=COLORS["soft"], foreground=COLORS["ink"], font=("Segoe UI", self.px(11)))
        style.configure("TButton", padding=(self.px(14), self.px(10)), font=("Segoe UI Semibold", self.px(10)))
        style.configure("Primary.TButton", padding=(self.px(14), self.px(10)), background=COLORS["primary"], foreground="white", font=("Segoe UI Semibold", self.px(10)))

    def build(self):
        page = ttk.Frame(self, style="Page.TFrame", padding=self.px(26))
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="Speech-to-text capture", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            page,
            text="Speak a prompt or answer, clean it up, then save it as a normal MemoryPal card.",
            style="Title.TLabel",
            font=("Segoe UI", self.px(11)),
        ).pack(anchor="w", pady=(self.px(2), self.px(18)))

        shell = ttk.Frame(page, style="Card.TFrame", padding=self.px(22))
        shell.pack(fill="both", expand=True)
        tk.Frame(shell, bg=COLORS["primary"], height=self.px(4)).pack(fill="x", pady=(0, self.px(18)))

        form = ttk.Frame(shell, style="Card.TFrame")
        form.pack(fill="x")
        ttk.Label(form, text="Question or title", style="H2.TLabel").pack(anchor="w")
        self.question = tk.Text(form, height=3, wrap="word", bg="#fbfdff", fg=COLORS["ink"], insertbackground=COLORS["primary"], relief="flat", padx=self.px(12), pady=self.px(10))
        self.question.pack(fill="x", pady=(self.px(6), self.px(14)))
        ttk.Label(form, text="Answer", style="H2.TLabel").pack(anchor="w")
        self.answer = tk.Text(form, height=5, wrap="word", bg="#fbfdff", fg=COLORS["ink"], insertbackground=COLORS["primary"], relief="flat", padx=self.px(12), pady=self.px(10))
        self.answer.pack(fill="x", pady=(self.px(6), self.px(14)))

        row = ttk.Frame(shell, style="Card.TFrame")
        row.pack(fill="x", pady=(0, self.px(14)))
        ttk.Button(row, text="Dictate Question", style="Primary.TButton", command=lambda: self.dictate_into(self.question)).pack(side="left", padx=(0, self.px(8)))
        ttk.Button(row, text="Dictate Answer", command=lambda: self.dictate_into(self.answer)).pack(side="left", padx=(0, self.px(8)))
        ttk.Button(row, text="Transcribe Audio File", command=self.transcribe_file).pack(side="left", padx=(0, self.px(8)))
        ttk.Button(row, text="Save Card", command=self.save_card).pack(side="right")

        self.status = ttk.Label(shell, text="Ready. Speech recognition is optional, so this version still runs without the package installed. The default recognizer may need an internet connection.", style="Muted.TLabel", wraplength=self.px(900))
        self.status.pack(anchor="w")

        self.list_frame = ttk.Frame(shell, style="Soft.TFrame", padding=self.px(16))
        self.list_frame.pack(fill="both", expand=True, pady=(self.px(16), 0))
        self.render_cards()

    def alert(self, title, body):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg=COLORS["bg"])
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        card = tk.Frame(dialog, bg=COLORS["surface"], padx=self.px(22), pady=self.px(20), highlightthickness=1, highlightbackground=COLORS["line"])
        card.pack(fill="both", expand=True, padx=self.px(14), pady=self.px(14))
        tk.Label(card, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=("Segoe UI Semibold", self.px(17))).pack(anchor="w")
        tk.Label(card, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", self.px(11)), wraplength=self.px(430), justify="left").pack(anchor="w", pady=(self.px(8), self.px(18)))
        ttk.Button(card, text="OK", style="Primary.TButton", command=dialog.destroy).pack(anchor="e")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + self.px(120)}+{self.winfo_rooty() + self.px(120)}")
        self.wait_window(dialog)

    def recognizer(self):
        try:
            import speech_recognition as sr
        except ImportError:
            self.alert("Speech recognition unavailable", "Install SpeechRecognition and PyAudio to use microphone dictation. Audio-file transcription also needs SpeechRecognition.")
            return None
        return sr

    def dictate_into(self, target):
        sr = self.recognizer()
        if not sr:
            return
        self.status.configure(text="Listening for up to 6 seconds...")

        def worker():
            try:
                recognizer = sr.Recognizer()
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    audio = recognizer.listen(source, timeout=4, phrase_time_limit=6)
                text = recognizer.recognize_google(audio)
                self.after(0, lambda: self.insert_transcript(target, text))
            except Exception as exc:
                self.after(0, lambda: self.alert("Dictation failed", str(exc)))
                self.after(0, lambda: self.status.configure(text="Dictation stopped."))

        threading.Thread(target=worker, daemon=True).start()

    def transcribe_file(self):
        sr = self.recognizer()
        if not sr:
            return
        selected = filedialog.askopenfilename(title="Choose audio file", filetypes=[("Audio", "*.wav *.aiff *.aif *.flac"), ("All files", "*.*")])
        if not selected:
            return
        self.status.configure(text=f"Transcribing {Path(selected).name}...")

        def worker():
            try:
                recognizer = sr.Recognizer()
                with sr.AudioFile(selected) as source:
                    audio = recognizer.record(source)
                text = recognizer.recognize_google(audio)
                self.after(0, lambda: self.insert_transcript(self.answer, text))
            except Exception as exc:
                self.after(0, lambda: self.alert("Transcription failed", str(exc)))
                self.after(0, lambda: self.status.configure(text="Audio-file transcription stopped."))

        threading.Thread(target=worker, daemon=True).start()

    def insert_transcript(self, target, text):
        if clean(target.get("1.0", "end")):
            target.insert("end", "\n")
        target.insert("end", clean(text))
        self.status.configure(text="Transcript added. Edit anything that needs cleaning before saving.")

    def save_card(self):
        question = clean(self.question.get("1.0", "end"))
        answer = clean(self.answer.get("1.0", "end"))
        if not question:
            self.alert("Question needed", "Add or dictate a question/title before saving the card.")
            return
        self.cards.insert(0, {"question": question, "answer": answer or "Self-check card"})
        self.question.delete("1.0", "end")
        self.answer.delete("1.0", "end")
        self.status.configure(text="Card saved from speech/text capture.")
        self.render_cards()

    def render_cards(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        ttk.Label(self.list_frame, text="Saved cards", style="Soft.TLabel", font=("Segoe UI Semibold", self.px(14))).pack(anchor="w")
        if not self.cards:
            ttk.Label(self.list_frame, text="No cards saved yet.", style="Soft.TLabel").pack(anchor="w", pady=(self.px(8), 0))
            return
        for card in self.cards[:6]:
            ttk.Label(self.list_frame, text=card["question"], style="Soft.TLabel", wraplength=self.px(880)).pack(anchor="w", pady=(self.px(8), 0))
            ttk.Label(self.list_frame, text=card["answer"], style="Soft.TLabel", wraplength=self.px(880)).pack(anchor="w")


def main():
    enable_dpi_awareness()
    SpeechStage().mainloop()


if __name__ == "__main__":
    main()
