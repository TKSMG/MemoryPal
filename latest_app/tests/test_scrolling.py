import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memorypal import scrolling  # noqa: E402


class WheelMotionTests(unittest.TestCase):
    def test_windows_notch_glides(self):
        pixels, tau = scrolling.wheel_motion(-120, 72)
        self.assertEqual(pixels, 72)
        self.assertGreater(tau, 0)
        pixels, _tau = scrolling.wheel_motion(240, 72)
        self.assertEqual(pixels, -144)

    def test_windows_touchpad_follows_directly(self):
        pixels, tau = scrolling.wheel_motion(-30, 72)
        self.assertAlmostEqual(pixels, 18)
        self.assertEqual(tau, 0)

    def test_whole_notches_right_after_touchpad_stay_direct(self):
        self.assertEqual(scrolling.wheel_motion(-120, 72, since_touchpad_s=0.1)[1], 0)
        self.assertGreater(scrolling.wheel_motion(-120, 72, since_touchpad_s=2.0)[1], 0)

    def test_x11_buttons(self):
        self.assertEqual(scrolling.wheel_motion(0, 72, button=4)[0], -72)
        self.assertEqual(scrolling.wheel_motion(0, 72, button=5)[0], 72)
        self.assertGreater(scrolling.wheel_motion(0, 72, button=5)[1], 0)

    def test_mac_isolated_notch_glides_and_stream_nearly_direct(self):
        pixels, tau = scrolling.wheel_motion(-1, 70, mac=True, gap_s=0.3)
        self.assertAlmostEqual(pixels, 10)
        self.assertEqual(tau, scrolling.NOTCH_TAU_MS)
        _pixels, tau = scrolling.wheel_motion(-3, 70, mac=True, gap_s=0.012)
        self.assertEqual(tau, scrolling.STREAM_TAU_MS)
        self.assertLess(tau, 17)  # about a frame: no visible lag

    def test_mac_large_deltas_use_notches(self):
        self.assertEqual(scrolling.wheel_motion(-120, 72, mac=True)[0], 72)

    def test_reduced_motion_never_glides(self):
        self.assertEqual(scrolling.wheel_motion(-120, 72, reduce_motion=True)[1], 0)
        self.assertEqual(scrolling.wheel_motion(-1, 70, mac=True, gap_s=1, reduce_motion=True)[1], 0)

    def test_no_delta(self):
        self.assertEqual(scrolling.wheel_motion(0, 72), (0.0, 0.0))

    def test_touchpad_detection(self):
        self.assertTrue(scrolling.is_touchpad_delta(-30))
        self.assertFalse(scrolling.is_touchpad_delta(-120))
        self.assertFalse(scrolling.is_touchpad_delta(-3, mac=True))
        self.assertFalse(scrolling.is_touchpad_delta(0, button=4))


class GlideTests(unittest.TestCase):
    def run_glide(self, distance, frame_ms, tau=scrolling.NOTCH_TAU_MS):
        position, frames, steps = 0.0, 0, []
        while True:
            step, done = scrolling.glide_step(distance - position, frame_ms, tau)
            position += step
            steps.append(step)
            frames += 1
            if done or frames > 500:
                return position, frames, steps

    def test_lands_exactly_on_target(self):
        for distance in (72, -72, 300, 3):
            position, _frames, _steps = self.run_glide(distance, 16.7)
            self.assertAlmostEqual(position, distance)

    def test_notch_settles_in_about_120_to_180ms(self):
        _position, frames, _steps = self.run_glide(72, 1000 / 60)
        self.assertTrue(120 <= frames * 1000 / 60 <= 190, frames)
        self.assertTrue(120 <= scrolling.settle_ms(72) <= 180)

    def test_same_duration_at_60_and_144hz(self):
        _p, frames60, _s = self.run_glide(144, 1000 / 60)
        _p, frames144, _s = self.run_glide(144, 1000 / 144)
        self.assertAlmostEqual(frames60 * 1000 / 60, frames144 * 1000 / 144, delta=30)

    def test_ease_out_steps_shrink_and_never_reverse(self):
        _p, _f, steps = self.run_glide(200, 16.7)
        self.assertTrue(all(step > 0 for step in steps))
        self.assertGreater(steps[0], steps[len(steps) // 2])

    def test_zero_tau_is_direct(self):
        self.assertEqual(scrolling.glide_step(50, 16.7, 0), (50, True))

    def test_clamp_target(self):
        self.assertEqual(scrolling.clamp_target(10, -50, 400), 0)
        self.assertEqual(scrolling.clamp_target(390, 50, 400), 400)
        self.assertEqual(scrolling.clamp_target(100, 72, 400), 172)

    def test_take_lines(self):
        self.assertEqual(scrolling.take_lines(0), (0, 0))
        self.assertEqual(scrolling.take_lines(3), (1, 2))
        self.assertEqual(scrolling.take_lines(-3), (-1, -2))
        step, rest = scrolling.take_lines(20)
        self.assertEqual(step + rest, 20)
        self.assertLessEqual(step, 3)

    def test_frames_per_step(self):
        self.assertEqual(scrolling.frames_per_step(None, 16.7), 1)
        self.assertEqual(scrolling.frames_per_step(12, 16.7), 1)
        self.assertEqual(scrolling.frames_per_step(17.5, 16.7), 1)  # within 10%
        self.assertEqual(scrolling.frames_per_step(12, 6.94), 2)  # 144Hz
        self.assertEqual(scrolling.frames_per_step(18, 6.94), 3)
        self.assertEqual(scrolling.frames_per_step(80, 6.94), 3)  # capped


if __name__ == "__main__":
    unittest.main()
