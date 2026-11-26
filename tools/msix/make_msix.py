"""Package the PyInstaller build (release/MemoryPal) as an MSIX for the Microsoft Store.

The Store signs the package when it is published, so this makes an unsigned
MSIX. Partner Center gives the app an identity; set these repository
variables (Settings > Secrets and variables > Actions > Variables) to match it
before uploading, or the Store refuses the package:

  MSIX_IDENTITY_NAME       Package/Identity/Name, e.g. 12345YourName.MemoryPal
  MSIX_PUBLISHER           Package/Identity/Publisher, e.g. CN=ABCD1234-...
  MSIX_PUBLISHER_DISPLAY   Package/Properties/PublisherDisplayName

Usage: python tools/msix/make_msix.py release/MemoryPal release/MemoryPal-Windows-Store.msix
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "latest_app"))

from memorypal import icon  # noqa: E402

# Windows draws package logos exactly as they are, so they must be the rounded
# tile on a transparent background. (mobile/assets/icon.png is a full-bleed
# square because iOS rounds it itself; on Windows it showed as a square plate.)
SCALES = (100, 125, 150, 200, 400)
TARGET_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)
# (name, width, height, tile share of the short side). Small icons nearly fill
# their square like other Windows 11 app icons; the bigger tiles get the
# margin Windows' tile guidance asks for.
LOGOS = (
    ("StoreLogo", 50, 50, 0.92),
    ("Square44x44Logo", 44, 44, 0.92),
    ("Square150x150Logo", 150, 150, 0.66),
    ("Square310x310Logo", 310, 310, 0.66),
    ("Wide310x150Logo", 310, 150, 0.66),
)

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name="{name}" Publisher="{publisher}" Version="{version}" ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>MemoryPal</DisplayName>
    <PublisherDisplayName>{publisher_display}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  <Applications>
    <Application Id="MemoryPal" Executable="MemoryPal.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="MemoryPal" Description="Flashcards, memory practice and study plans."
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png" Square310x310Logo="Assets\\Square310x310Logo.png" />
      </uap:VisualElements>
    </Application>
  </Applications>
  <Capabilities>
    <Capability Name="internetClient" />
    <rescap:Capability Name="runFullTrust" />
    <DeviceCapability Name="microphone" />
  </Capabilities>
</Package>
"""


def store_version():
    """pyproject's 0.48.3 as 0.48.3.0: the Store wants four parts with the last one 0."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    parts = re.search(r'^version\s*=\s*"([\d.]+)"', text, re.M).group(1).split(".")
    return ".".join((parts + ["0", "0", "0"])[:3] + ["0"])


def tile_image(side, master):
    """The rounded logo tile, side x side, with transparent corners."""
    if side <= 64:
        # Drawn directly at small sizes, which stays crisp where a shrunk copy blurs.
        rows = icon.render_icon_pixels(side)
        return Image.frombytes("RGBA", (side, side), bytes(value for row in rows for pixel in row for value in pixel))
    return master.resize((side, side), Image.LANCZOS)


def logo(width, height, share, master):
    side = min(width, height)
    tile_side = max(1, round(side * share))
    if side - tile_side < 2 and side >= 16:
        tile_side = side - 2  # keep at least a 1px edge so the corners read as rounded
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(tile_image(tile_side, master), ((width - tile_side) // 2, (height - tile_side) // 2))
    return canvas


def write_assets(folder):
    """Every scale and target size Windows asks for, so it never stretches a small image.

    The qualified names (scale-200, targetsize-32_altform-unplated, ...) only
    work through resources.pri, which make_pri() builds from this folder.
    """
    folder.mkdir(parents=True, exist_ok=True)
    rows = icon.render_icon_pixels(1024, scale=1)
    master = Image.frombytes("RGBA", (1024, 1024), bytes(value for row in rows for pixel in row for value in pixel))
    for name, width, height, share in LOGOS:
        for scale in SCALES:
            logo(round(width * scale / 100), round(height * scale / 100), share, master).save(folder / f"{name}.scale-{scale}.png")
    for size in TARGET_SIZES:
        image = logo(size, size, LOGOS[1][3], master)
        # Plain (tile background, which is transparent), dark taskbar and light taskbar.
        for suffix in ("", "_altform-unplated", "_altform-lightunplated"):
            image.save(folder / f"Square44x44Logo.targetsize-{size}{suffix}.png")


def make_pri(sdk_tool, layout):
    """Index Assets/ into resources.pri so Windows can pick the right logo file."""
    makepri = Path(sdk_tool).with_name("makepri.exe")
    makepri = str(makepri) if makepri.exists() else (shutil.which("makepri") or sys.exit("makepri.exe not found; install the Windows 10/11 SDK."))
    with tempfile.TemporaryDirectory() as temp:
        project = Path(temp) / "pri"
        shutil.copytree(layout / "Assets", project / "Assets")
        shutil.copy(layout / "AppxManifest.xml", project / "AppxManifest.xml")
        config = Path(temp) / "priconfig.xml"
        subprocess.run([makepri, "createconfig", "/cf", str(config), "/dq", "en-US", "/pv", "10.0.0", "/o"], check=True)
        subprocess.run([makepri, "new", "/pr", str(project), "/cf", str(config), "/mn", str(project / "AppxManifest.xml"),
                        "/of", str(layout / "resources.pri"), "/o"], check=True)


def find_makeappx():
    found = shutil.which("makeappx")
    if found:
        return found
    kits = sorted(glob.glob(r"C:\Program Files (x86)\Windows Kits\10\bin\10.*\x64\makeappx.exe"))
    if not kits:
        sys.exit("makeappx.exe not found; install the Windows 10/11 SDK.")
    return kits[-1]


def main(app_dir, out_path):
    app_dir, out_path = Path(app_dir), Path(out_path)
    if not (app_dir / "MemoryPal.exe").exists():
        sys.exit(f"{app_dir} has no MemoryPal.exe; build the app first.")
    with tempfile.TemporaryDirectory() as temp:
        layout = Path(temp) / "layout"
        shutil.copytree(app_dir, layout)
        write_assets(layout / "Assets")
        (layout / "AppxManifest.xml").write_text(MANIFEST.format(
            name=escape(os.environ.get("MSIX_IDENTITY_NAME") or "MemoryPal.MemoryPal"),
            publisher=escape(os.environ.get("MSIX_PUBLISHER") or "CN=MemoryPal"),
            publisher_display=escape(os.environ.get("MSIX_PUBLISHER_DISPLAY") or "MemoryPal"),
            version=store_version(),
        ), encoding="utf-8")
        makeappx = find_makeappx()
        make_pri(makeappx, layout)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([makeappx, "pack", "/o", "/d", str(layout), "/p", str(out_path)], check=True)
    print(f"Built {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
