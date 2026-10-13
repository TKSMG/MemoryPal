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
ICON = ROOT / "mobile" / "assets" / "icon.png"

# (file, width, height): the logos the manifest names, plus the unplated
# taskbar sizes Windows looks for next to Square44x44Logo.
ASSETS = [
    ("StoreLogo.png", 50, 50),
    ("Square44x44Logo.png", 44, 44),
    ("Square44x44Logo.targetsize-24_altform-unplated.png", 24, 24),
    ("Square44x44Logo.targetsize-32_altform-unplated.png", 32, 32),
    ("Square44x44Logo.targetsize-48_altform-unplated.png", 48, 48),
    ("Square44x44Logo.targetsize-256_altform-unplated.png", 256, 256),
    ("Square150x150Logo.png", 150, 150),
    ("Square310x310Logo.png", 310, 310),
    ("Wide310x150Logo.png", 310, 150),
]

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


def write_assets(folder):
    folder.mkdir(parents=True, exist_ok=True)
    icon = Image.open(ICON).convert("RGBA")
    for name, width, height in ASSETS:
        side = min(width, height)
        tile = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tile.paste(icon.resize((side, side), Image.LANCZOS), ((width - side) // 2, (height - side) // 2))
        tile.save(folder / name)


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
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([find_makeappx(), "pack", "/o", "/d", str(layout), "/p", str(out_path)], check=True)
    print(f"Built {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
