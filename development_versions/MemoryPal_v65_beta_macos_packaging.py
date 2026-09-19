"""
MemoryPal v65 beta - macOS packaging.

This milestone records the pass that made the desktop project easier to ship
on Mac as well as Windows. The live app keeps the full feature set, while this
standalone version shows the release idea: native Mac window chrome, packaged
logo assets, and separate Mac artifacts for Intel and Apple Silicon testers.
"""

import sys
import tkinter as tk


APP_NAME = "MemoryPal"
BG = "#101827"
SURFACE = "#182238"
SURFACE_SOFT = "#22304c"
RAIL = "#0c1222"
PRIMARY = "#66b3ff"
GREEN = "#42d58a"
INK = "#edf4ff"
MUTED = "#aeb9cc"
LINE = "#33455f"


class MemoryPalV65(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v65")
        self.geometry("1080x680")
        self.minsize(820, 540)
        self.configure(bg=BG)

        self.native_chrome = sys.platform == "darwin"
        self.shell()

    def shell(self):
        rail = tk.Frame(self, bg=RAIL, width=255)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        mark = tk.Canvas(rail, width=58, height=58, bg=RAIL, highlightthickness=0)
        mark.pack(anchor="w", padx=28, pady=(30, 8))
        self.draw_mark(mark)
        tk.Label(rail, text=APP_NAME, bg=RAIL, fg=INK, font=("Segoe UI Semibold", 24)).pack(anchor="w", padx=28)
        tk.Label(
            rail,
            text="Mac packaging milestone",
            bg=RAIL,
            fg=MUTED,
            font=("Segoe UI", 11),
        ).pack(anchor="w", padx=28, pady=(4, 24))

        for name in ("Dashboard", "Builds", "Testing", "Notes"):
            tk.Button(
                rail,
                text=name,
                bg=RAIL,
                fg=MUTED,
                activebackground=SURFACE_SOFT,
                activeforeground=INK,
                relief="flat",
                anchor="w",
                padx=18,
                pady=12,
                command=lambda page=name: self.show_page(page),
            ).pack(fill="x", padx=20, pady=5)

        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        header = tk.Frame(self.main, bg=SURFACE, padx=26, pady=20, highlightthickness=1, highlightbackground=LINE)
        header.pack(fill="x", padx=36, pady=(32, 18))
        header.columnconfigure(0, weight=1)
        self.title_label = tk.Label(header, text="Dashboard", bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 27))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.status = tk.Label(header, text=self.platform_status(), bg=SURFACE, fg=PRIMARY, font=("Segoe UI Semibold", 10))
        self.status.grid(row=0, column=1, sticky="e")

        self.content = tk.Frame(self.main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=36, pady=(0, 36))
        self.show_page("Dashboard")

    def platform_status(self):
        if self.native_chrome:
            return "Native Mac chrome"
        return "Windows/Linux source preview"

    def draw_mark(self, canvas):
        canvas.create_oval(4, 4, 54, 54, fill="#12223b", outline=LINE, width=2)
        points = [(16, 39), (16, 18), (29, 32), (42, 18), (42, 39)]
        for index in range(len(points) - 1):
            canvas.create_line(*points[index], *points[index + 1], fill=PRIMARY, width=4, capstyle="round", joinstyle="round")
        for x, y in points:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=GREEN, outline=BG, width=1)

    def show_page(self, name):
        self.title_label.configure(text=name)
        for child in self.content.winfo_children():
            child.destroy()

        card = tk.Frame(self.content, bg=SURFACE, padx=30, pady=26, highlightthickness=1, highlightbackground=LINE)
        card.pack(fill="both", expand=True)

        if name == "Dashboard":
            heading = "Mac and Windows release path"
            lines = [
                "Windows remains the local installer path through PyInstaller and Inno Setup.",
                "Mac builds now use a macOS script and GitHub Actions workflow.",
                "The live app avoids custom borderless chrome on Mac so fullscreen and titlebar behavior stay native.",
            ]
        elif name == "Builds":
            heading = "Tester artifacts"
            lines = [
                "Windows: release/MemoryPalSetup.exe and release/MemoryPalTesterPackage.zip.",
                "Mac Intel: MemoryPal-macOS-Intel artifact from GitHub Actions.",
                "Mac Apple Silicon: MemoryPal-macOS-AppleSilicon artifact from GitHub Actions.",
            ]
        elif name == "Testing":
            heading = "Release checks"
            lines = [
                "Confirm app launch, icon display, profile saving, page switching, and fullscreen behavior.",
                "Unsigned Mac beta builds may need right-click Open until Developer ID signing is added.",
                "Keep Mac and Windows packages separate instead of trying to build both from one operating system.",
            ]
        else:
            heading = "Documentation"
            lines = [
                "README and BUILDING_APP explain the Mac packaging flow.",
                "TESTING_CHECKLIST includes Mac-specific launch and artifact checks.",
                "Version history records this as a packaging milestone, not a full feature rewrite.",
            ]

        tk.Label(card, text=heading, bg=SURFACE, fg=INK, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        for line in lines:
            row = tk.Frame(card, bg=SURFACE)
            row.pack(fill="x", pady=(14, 0))
            tk.Label(row, text="*", bg=SURFACE, fg=GREEN, font=("Segoe UI Semibold", 14)).pack(side="left", padx=(0, 10))
            tk.Label(row, text=line, bg=SURFACE, fg=MUTED, font=("Segoe UI", 12), wraplength=720, justify="left").pack(side="left", fill="x", expand=True, anchor="w")


if __name__ == "__main__":
    MemoryPalV65().mainloop()
