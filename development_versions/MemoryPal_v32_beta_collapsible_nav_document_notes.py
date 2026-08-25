"""
MemoryPal v32 beta - collapsible navigation and document notes

Independent milestone prototype. This version records the point where the app
added a focus-friendly collapsible navigation rail and note/document importing
for PDFs, Word documents, and plain text notes.
"""

import re
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET


COLORS = {
    "bg": "#0f172a",
    "rail": "#05070d",
    "rail_hover": "#14213a",
    "panel": "#172235",
    "alt": "#22314f",
    "ink": "#eef4ff",
    "muted": "#9fb0cc",
    "primary": "#4d9cff",
    "orange": "#ffb020",
}


def normalize(value):
    return re.sub(r"\s+", " ", value or "").strip()


def split_bits(raw):
    raw = (raw or "").replace("\\n", "\n").replace("/n", "\n")
    return [normalize(re.sub(r"^[-*\d.)\s]+", "", line)) for line in raw.splitlines() if normalize(line)]


def extract_document_text(path):
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        try:
            return source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return source.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        with zipfile.ZipFile(source) as archive:
            xml = archive.read("word/document.xml")
        root = ET.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        pieces = []
        for paragraph in root.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
            if text.strip():
                pieces.append(text.strip())
        return "\n".join(pieces)
    if suffix == ".pdf":
        for module_name in ("pypdf", "PyPDF2"):
            try:
                module = __import__(module_name)
                reader = module.PdfReader(str(source))
                return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
            except Exception:
                continue
        raise RuntimeError("PDF extraction needs pypdf or PyPDF2.")
    raise RuntimeError("This file can be attached, but automatic extraction is not supported.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MemoryPal v32 - Documents and Focus Rail")
        self.geometry("1120x760")
        self.minsize(880, 620)
        self.configure(bg=COLORS["bg"])
        self.rail_collapsed = False
        self.notes = []
        self.cards = []
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("Page.TFrame", background=COLORS["bg"])
        self.style.configure("Rail.TFrame", background=COLORS["rail"])
        self.style.configure("Panel.TFrame", background=COLORS["panel"])
        self.style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        self.style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["ink"], font=("Segoe UI", 12))
        self.style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 10))
        self.style.configure("TButton", padding=(14, 10), background=COLORS["alt"], foreground=COLORS["ink"], borderwidth=0)
        self.style.configure("Primary.TButton", padding=(14, 10), background=COLORS["primary"], foreground="white", borderwidth=0)
        self.build_shell()

    def build_shell(self):
        for child in self.winfo_children():
            child.destroy()
        root = ttk.Frame(self, style="Page.TFrame")
        root.pack(fill="both", expand=True)
        width = 74 if self.rail_collapsed else 250
        rail = ttk.Frame(root, style="Rail.TFrame", width=width)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        tk.Label(rail, text="M", bg=COLORS["primary"], fg="white", font=("Segoe UI Semibold", 22), width=2, pady=10).pack(padx=14, pady=(18, 10))
        toggle = tk.Button(
            rail,
            text=">" if self.rail_collapsed else "<",
            bg=COLORS["orange"] if self.rail_collapsed else COLORS["primary"],
            fg="white",
            relief="flat",
            bd=0,
            command=self.toggle_rail,
            cursor="hand2",
            font=("Segoe UI Semibold", 13),
        )
        toggle.pack(fill="x", padx=12, pady=(0, 12))
        for label, short in [("Capture", "C"), ("Plan", "P"), ("Resources", "R")]:
            ttk.Button(rail, text=short if self.rail_collapsed else label, command=lambda name=label.lower(): self.show(name)).pack(fill="x", padx=12, pady=5)
        self.host = ttk.Frame(root, style="Page.TFrame")
        self.host.pack(side="left", fill="both", expand=True, padx=24, pady=24)
        self.show("capture")

    def toggle_rail(self):
        self.rail_collapsed = not self.rail_collapsed
        self.build_shell()

    def clear(self):
        for child in self.host.winfo_children():
            child.destroy()

    def panel(self):
        frame = ttk.Frame(self.host, style="Panel.TFrame", padding=20)
        frame.pack(fill="x", pady=(0, 14))
        return frame

    def show(self, name):
        self.clear()
        getattr(self, f"view_{name}")()

    def view_capture(self):
        card = self.panel()
        ttk.Label(card, text="Import notes", style="Panel.TLabel", font=("Segoe UI Semibold", 22)).pack(anchor="w")
        ttk.Label(card, text="PDF, DOCX, TXT, MD, and CSV notes can be attached. Extracted text becomes study bits.", style="Muted.TLabel").pack(anchor="w", pady=(4, 12))
        self.text = tk.Text(card, height=10, wrap="word", bg="#0b1220", fg=COLORS["ink"], insertbackground=COLORS["primary"], bd=0, padx=12, pady=10)
        self.text.pack(fill="x")
        row = ttk.Frame(card, style="Panel.TFrame")
        row.pack(fill="x", pady=(12, 0))
        ttk.Button(row, text="Import note/PDF/Word", style="Primary.TButton", command=self.import_note).pack(side="left")
        ttk.Button(row, text="Make cards", command=self.make_cards).pack(side="left", padx=(8, 0))
        self.resources()

    def view_plan(self):
        card = self.panel()
        ttk.Label(card, text="Study Plan", style="Panel.TLabel", font=("Segoe UI Semibold", 22)).pack(anchor="w")
        ttk.Label(card, text=f"{len(self.cards)} cards ready. Notes and audio resources stay visible while planning.", style="Panel.TLabel").pack(anchor="w", pady=(8, 0))
        self.resources()

    def view_resources(self):
        self.resources()

    def resources(self):
        card = self.panel()
        ttk.Label(card, text="Resources", style="Panel.TLabel", font=("Segoe UI Semibold", 18)).pack(anchor="w")
        if not self.notes:
            ttk.Label(card, text="No notes imported yet.", style="Muted.TLabel").pack(anchor="w", pady=(5, 0))
            return
        for note in self.notes:
            ttk.Label(card, text=note["name"], style="Panel.TLabel").pack(anchor="w", pady=(6, 0))
            ttk.Label(card, text=note["preview"], style="Muted.TLabel", wraplength=820).pack(anchor="w")

    def import_note(self):
        path = filedialog.askopenfilename(filetypes=[("Notes and documents", "*.txt *.md *.csv *.pdf *.docx *.doc"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = extract_document_text(path)
        except Exception as exc:
            messagebox.showinfo("Attached only", str(exc))
            text = ""
        if text:
            self.text.delete("1.0", "end")
            self.text.insert("1.0", text)
        self.notes.append({"name": Path(path).name, "preview": (text[:180] + "...") if len(text) > 180 else text or "Attached as a cue."})
        self.show("capture")

    def make_cards(self):
        bits = split_bits(self.text.get("1.0", "end"))
        self.cards.extend({"prompt": f"Study bit {len(self.cards) + index + 1}", "answer": bit} for index, bit in enumerate(bits))
        messagebox.showinfo("Cards", f"Created {len(bits)} cards.")


if __name__ == "__main__":
    App().mainloop()
