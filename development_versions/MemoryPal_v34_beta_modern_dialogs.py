"""
MemoryPal v34 beta - modern dialogs

Independent milestone prototype. This version records the point where old stock
Tk message boxes and simple prompts were replaced with app-styled modal dialogs.
"""

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#0f172a",
    "surface": "#172235",
    "alt": "#22314f",
    "ink": "#eef4ff",
    "muted": "#9fb0cc",
    "primary": "#4d9cff",
    "danger": "#ff5c5c",
}


class DialogDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v34 - Modern Dialogs")
        self.geometry("820x560")
        self.configure(bg=COLORS["bg"])
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TFrame", background=COLORS["bg"])
        self.style.configure("Card.TFrame", background=COLORS["surface"])
        self.style.configure("TButton", padding=(14, 10), background=COLORS["alt"], foreground=COLORS["ink"], borderwidth=0)
        self.style.configure("Primary.TButton", padding=(14, 10), background=COLORS["primary"], foreground="white", borderwidth=0)
        self.build()

    def build(self):
        card = ttk.Frame(self, style="Card.TFrame", padding=28)
        card.pack(fill="both", expand=True, padx=28, pady=28)
        tk.Label(card, text="Modern app dialogs", bg=COLORS["surface"], fg=COLORS["ink"], font=("Segoe UI Semibold", 26)).pack(anchor="w")
        tk.Label(card, text="Profile names, recording lengths, alerts, confirmations, and errors now use MemoryPal-styled modals.", bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 12), wraplength=680, justify="left").pack(anchor="w", pady=(8, 22))
        ttk.Button(card, text="Profile name prompt", style="Primary.TButton", command=lambda: self.text_prompt("New profile", "Profile name")).pack(fill="x", pady=(0, 10))
        ttk.Button(card, text="Recording length prompt", command=lambda: self.number_prompt("Record audio", "How many seconds should be recorded?")).pack(fill="x", pady=(0, 10))
        ttk.Button(card, text="Confirmation dialog", command=lambda: self.confirm("Reset MemoryPal", "Clear local data and restore sample cards?")).pack(fill="x")

    def dialog(self, title, body):
        top = tk.Toplevel(self)
        top.title(title)
        top.configure(bg=COLORS["bg"])
        top.transient(self)
        top.grab_set()
        shell = tk.Frame(top, bg=COLORS["surface"], padx=22, pady=20, highlightthickness=1, highlightbackground="#2a3a5c")
        shell.pack(fill="both", expand=True, padx=14, pady=14)
        tk.Label(shell, text=title, bg=COLORS["surface"], fg=COLORS["ink"], font=("Segoe UI Semibold", 18)).pack(anchor="w")
        tk.Label(shell, text=body, bg=COLORS["surface"], fg=COLORS["muted"], font=("Segoe UI", 11), wraplength=390, justify="left").pack(anchor="w", pady=(6, 14))
        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(fill="x")
        actions = ttk.Frame(shell, style="Card.TFrame")
        actions.pack(fill="x", pady=(18, 0))
        top.minsize(460, 1)
        top.wait_visibility()
        top.geometry(f"+{self.winfo_rootx() + 120}+{self.winfo_rooty() + 100}")
        return top, content, actions

    def text_prompt(self, title, body):
        top, content, actions = self.dialog(title, body)
        entry = ttk.Entry(content)
        entry.pack(fill="x")
        ttk.Button(actions, text="Cancel", command=top.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(actions, text="Save", style="Primary.TButton", command=top.destroy).grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

    def number_prompt(self, title, body):
        top, content, actions = self.dialog(title, body)
        entry = ttk.Entry(content)
        entry.insert(0, "10")
        entry.pack(fill="x")
        tk.Label(content, text="Enter a number from 1 to 120.", bg=COLORS["surface"], fg=COLORS["muted"]).pack(anchor="w", pady=(6, 0))
        ttk.Button(actions, text="Cancel", command=top.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(actions, text="Continue", style="Primary.TButton", command=top.destroy).grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

    def confirm(self, title, body):
        top, _content, actions = self.dialog(title, body)
        ttk.Button(actions, text="Cancel", command=top.destroy).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        tk.Button(actions, text="Reset", command=top.destroy, relief="flat", bd=0, bg=COLORS["danger"], fg="white", padx=14, pady=10).grid(row=0, column=1, sticky="ew")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)


if __name__ == "__main__":
    DialogDemo().mainloop()
