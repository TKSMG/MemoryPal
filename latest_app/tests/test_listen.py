import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import listen  # noqa: E402


class FakeProcess:
    def __init__(self, stdout=b"", returncode=0, running_polls=0):
        self.stdout = mock.Mock()
        self.stdout.read.return_value = stdout
        self._out = stdout
        self.returncode = returncode
        self._running = running_polls
        self.terminated = False

    def poll(self):
        if self._running > 0:
            self._running -= 1
            return None
        return self.returncode

    def communicate(self, timeout=None):
        return self._out, b""

    def terminate(self):
        self.terminated = True
        self._running = 0


class CommandTests(unittest.TestCase):
    def test_no_command_off_windows(self):
        self.assertIsNone(listen.listen_command(platform="darwin"))
        self.assertIsNone(listen.listen_command(platform="linux"))
        self.assertIsNone(listen.probe_command(platform="linux"))

    def test_windows_command_uses_powershell_and_dictation(self):
        command = listen.listen_command(max_seconds=10, initial_silence=5, end_silence=1.5, platform="win32")
        self.assertTrue(command[0].lower().endswith("powershell.exe") or command[0] == "powershell")
        self.assertEqual(command[1:4], ["-NoProfile", "-NonInteractive", "-Command"])
        script = command[4]
        self.assertIn("System.Speech.Recognition.SpeechRecognitionEngine", script)
        self.assertIn("DictationGrammar", script)
        self.assertIn("SetInputToDefaultAudioDevice", script)
        self.assertIn("FromMilliseconds(5000)", script)
        self.assertIn("FromMilliseconds(10000)", script)
        self.assertIn("FromMilliseconds(1500)", script)

    def test_script_has_no_unfilled_placeholders(self):
        script = listen.listen_command(platform="win32")[4]
        self.assertNotIn("{initial_ms}", script)
        self.assertNotIn("{max_ms}", script)
        self.assertNotIn("{end_ms}", script)

    def test_command_carries_only_numbers_we_format(self):
        # Nothing but the fixed script: there is no way to pass user text in.
        a = listen.listen_command(platform="win32")
        b = listen.listen_command(platform="win32")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)


class ParseTests(unittest.TestCase):
    def test_heard_with_confidence(self):
        result = listen.parse_result("MP-HEARD 0.873 the mitochondria\r\n")
        self.assertEqual((result.status, result.text, result.confidence), ("heard", "the mitochondria", 0.873))
        self.assertTrue(result.heard)

    def test_silence(self):
        self.assertEqual(listen.parse_result("MP-SILENCE\n").status, "silence")
        self.assertEqual(listen.parse_result("").status, "silence")

    def test_error_message(self):
        result = listen.parse_result("MP-ERROR No audio input device is available.\n")
        self.assertEqual(result.status, "error")
        self.assertIn("audio input", result.message)

    def test_crash_without_output_is_an_error(self):
        self.assertEqual(listen.parse_result("", returncode=1).status, "error")

    def test_last_marker_wins_and_noise_is_ignored(self):
        result = listen.parse_result("warning: something\nMP-HEARD 0.5 Paris\n")
        self.assertEqual(result.text, "Paris")

    def test_heard_but_empty_text_is_silence(self):
        self.assertEqual(listen.parse_result("MP-HEARD 0.9 \n").status, "silence")

    def test_probe(self):
        self.assertEqual(listen.parse_probe("MP-RECOGNIZERS 2\r\n"), 2)
        self.assertEqual(listen.parse_probe("garbage"), 0)


class SpokenCommandTests(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(listen.spoken_command("Repeat"), "repeat")
        self.assertEqual(listen.spoken_command("say that again please"), "repeat")
        self.assertEqual(listen.spoken_command("Skip."), "skip")
        self.assertEqual(listen.spoken_command("pause"), "pause")
        self.assertEqual(listen.spoken_command("I don’t know"), "dont_know")

    def test_answers_are_not_commands(self):
        self.assertIsNone(listen.spoken_command("the next step is mitosis"))
        self.assertIsNone(listen.spoken_command("Paris"))
        self.assertIsNone(listen.spoken_command(""))


class ListenerTests(unittest.TestCase):
    def test_off_windows_start_returns_false(self):
        listener = listen.Listener(popen=mock.Mock(), platform="darwin")
        self.assertFalse(listener.supported())
        self.assertFalse(listener.start())
        self.assertFalse(listener.probe())

    def test_start_poll_reads_result_once(self):
        process = FakeProcess(b"MP-HEARD 0.91 Canberra\r\n", running_polls=2)
        popen = mock.Mock(return_value=process)
        listener = listen.Listener(popen=popen, platform="win32")
        self.assertTrue(listener.start(max_seconds=8))
        args, kwargs = popen.call_args
        self.assertEqual(kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIsNone(listener.poll())
        self.assertIsNone(listener.poll())
        result = listener.poll()
        self.assertEqual(result.text, "Canberra")
        self.assertEqual(listener.poll().status, "unavailable")

    def test_stop_terminates(self):
        process = FakeProcess(running_polls=99)
        listener = listen.Listener(popen=mock.Mock(return_value=process), platform="win32")
        listener.start()
        listener.stop()
        self.assertTrue(process.terminated)
        self.assertFalse(listener.listening())

    def test_start_handles_missing_powershell(self):
        listener = listen.Listener(popen=mock.Mock(side_effect=OSError("no such file")), platform="win32")
        self.assertFalse(listener.start())

    def test_probe_counts_and_caches(self):
        popen = mock.Mock(return_value=FakeProcess(b"MP-RECOGNIZERS 1\r\n"))
        listener = listen.Listener(popen=popen, platform="win32")
        self.assertTrue(listener.probe())
        self.assertTrue(listener.probe())
        self.assertEqual(popen.call_count, 1)

    def test_probe_with_none_installed(self):
        listener = listen.Listener(popen=mock.Mock(return_value=FakeProcess(b"MP-RECOGNIZERS 0\r\n")), platform="win32")
        self.assertFalse(listener.probe())


if __name__ == "__main__":
    unittest.main()
