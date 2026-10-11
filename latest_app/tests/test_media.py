import os
import struct
import sys
import tempfile
import time
import unittest
import wave
import zlib
from pathlib import Path

os.environ.setdefault("MEMORYPAL_DATA_DIR", tempfile.mkdtemp(prefix="memorypal-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import media  # noqa: E402

WINDOWS = sys.platform.startswith("win")


def write_bmp(path, width, height, color=(200, 40, 40)):
    stride = ((width * 3 + 3) // 4) * 4
    pixels = (bytes(color[::-1]) * width + b"\0" * (stride - width * 3)) * height
    header = struct.pack("<2sIHHI", b"BM", 54 + len(pixels), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(pixels), 2835, 2835, 0, 0)
    Path(path).write_bytes(header + info + pixels)


def write_png(path, width, height):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + b"\x20\x80\xff" * width for _ in range(height))
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def png_size(path):
    data = Path(path).read_bytes()
    return struct.unpack(">II", data[16:24])


def write_silent_wav(path, seconds=1.0, rate=8000):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\0\0" * int(rate * seconds))


class MediaTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.dir = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()


@unittest.skipUnless(WINDOWS, "uses Windows imaging, voice and MCI")
class WindowsMediaTests(MediaTestCase):
    def test_previews_any_image_type_scaled_to_fit(self):
        write_bmp(self.dir / "photo.bmp", 800, 400)
        write_png(self.dir / "small.png", 50, 30)
        big = media.image_preview(self.dir / "photo.bmp", self.dir / "previews", 200, 200)
        self.assertIsNotNone(big)
        self.assertEqual(png_size(big), (200, 100))
        small = media.image_preview(self.dir / "small.png", self.dir / "previews", 200, 200)
        self.assertEqual(png_size(small), (50, 30))  # never enlarged

    def test_preview_is_cached(self):
        write_bmp(self.dir / "photo.bmp", 300, 300)
        first = media.image_preview(self.dir / "photo.bmp", self.dir / "previews", 100, 100)
        started = time.monotonic()
        again = media.image_preview(self.dir / "photo.bmp", self.dir / "previews", 100, 100)
        self.assertEqual(first, again)
        self.assertLess(time.monotonic() - started, 0.2)

    def test_unreadable_image_gives_none(self):
        (self.dir / "broken.jpg").write_bytes(b"not an image")
        self.assertIsNone(media.image_preview(self.dir / "broken.jpg", self.dir / "previews", 100, 100))

    def test_jpeg_preview_when_windows_ships_one(self):
        sample = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Web" / "Wallpaper" / "Windows" / "img0.jpg"
        if not sample.exists():
            self.skipTest("no sample JPEG on this machine")
        preview = media.image_preview(sample, self.dir / "previews", 320, 320)
        self.assertIsNotNone(preview)
        self.assertLessEqual(max(png_size(preview)), 320)

    def test_spoken_cue_file(self):
        ok, path = media.speech_to_wav("Mitochondria make energy for the cell.", self.dir / "cue.wav")
        self.assertTrue(ok, path)
        self.assertGreater(media.wav_duration(path), 0.8)

    def test_player_plays_and_stops(self):
        clip = self.dir / "silence.wav"
        write_silent_wav(clip, 2.0)
        player = media.AudioPlayer()
        self.assertTrue(player.play(clip))
        self.assertTrue(player.is_playing())
        player.stop()
        self.assertFalse(player.is_playing())

    def test_player_rejects_missing_file(self):
        self.assertFalse(media.AudioPlayer().play(self.dir / "nope.mp3"))


class CameraTests(MediaTestCase):
    def test_finds_only_videos_saved_after_starting(self):
        old = self.dir / "old.mp4"
        old.write_bytes(b"x")
        os.utime(old, (time.time() - 600, time.time() - 600))
        (self.dir / "photo.jpg").write_bytes(b"x")
        started = time.time()
        new = self.dir / "WIN_new.mp4"
        new.write_bytes(b"x")
        original = media.camera_folders
        media.camera_folders = lambda: [self.dir]
        try:
            self.assertEqual(media.newest_video_since(started), new)
            self.assertIsNone(media.newest_video_since(time.time() + 60))
        finally:
            media.camera_folders = original


class AttachmentPathTests(unittest.TestCase):
    """Attachment paths come from backups and sync, so only the profile's own folder is trusted."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="memorypal-attach-"))
        self.folder = self.root / "attachments"
        self.folder.mkdir()
        self.photo = self.folder / "cue.png"
        self.photo.write_bytes(b"png")

    def test_file_inside_the_folder_is_used(self):
        self.assertEqual(media.attachment_file(str(self.photo), self.folder), self.photo.resolve())

    def test_file_outside_the_folder_is_refused(self):
        outside = self.root / "elsewhere.png"
        outside.write_bytes(b"png")
        self.assertIsNone(media.attachment_file(str(outside), self.folder))

    def test_climbing_out_with_dot_dot_is_refused(self):
        (self.root / "secret.txt").write_text("x")
        self.assertIsNone(media.attachment_file(str(self.folder / ".." / "secret.txt"), self.folder))

    def test_network_paths_are_never_touched(self):
        for path in ("\\\\attacker\\share\\cue.png", "//attacker/share/cue.png", "\\\\?\\UNC\\attacker\\share\\cue.png"):
            # A same-named file in the folder is used instead; the share is never looked at.
            self.assertEqual(media.attachment_file(path, self.folder), self.photo.resolve())
            self.assertIsNone(media.attachment_file(path.replace("cue.png", "nothing.png"), self.folder))

    def test_path_from_another_computer_matches_by_name(self):
        moved = "C:\\Users\\someone\\AppData\\Local\\MemoryPal\\profiles\\old\\attachments\\cue.png"
        self.assertEqual(media.attachment_file(moved, self.folder), self.photo.resolve())

    def test_programs_are_never_returned(self):
        for name in ("run.exe", "go.bat", "x.ps1", "link.lnk", "page.hta", "CAPS.EXE"):
            (self.folder / name).write_bytes(b"x")
            self.assertIsNone(media.attachment_file(str(self.folder / name), self.folder), name)
            self.assertTrue(media.is_program(name))
        self.assertFalse(media.is_program("notes.pdf"))

    def test_empty_and_odd_values(self):
        for value in ("", None, "   ", ".", "..", "attachments/"):
            self.assertIsNone(media.attachment_file(value, self.folder))
        self.assertIsNone(media.attachment_file(str(self.photo), None))


if __name__ == "__main__":
    unittest.main()
