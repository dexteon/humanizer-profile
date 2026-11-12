"""Tests for scripts/voice_distance.py. Synthetic strings only."""

import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import voice_distance as vd  # noqa: E402

VOICE = ("Honestly I don't mind the long way round. We took the back road, grabbed coffee, and "
         "didn't rush. It's fine, really. You can't plan everything, so I don't.") * 3
CLOSE = "We didn't rush. We took the back road and grabbed coffee, and it's fine. I don't mind the long way."
FAR = ("The organization implemented a comprehensive framework to facilitate stakeholder alignment "
       "and ensure sustainable operational excellence across departments.")


class VoiceDistanceTests(unittest.TestCase):
    def test_identical_is_zero(self):
        self.assertAlmostEqual(vd.distances(VOICE, VOICE)["rewrite_distance"], 0.0, places=3)

    def test_closer_rewrite_wins(self):
        r = vd.distances(VOICE, CLOSE, FAR)
        self.assertTrue(r["moved_closer"])
        self.assertLess(r["rewrite_distance"], r["original_distance"])

    def test_farther_rewrite_loses(self):
        self.assertFalse(vd.distances(VOICE, FAR, CLOSE)["moved_closer"])

    def test_cli(self):
        script = str(SCRIPTS / "voice_distance.py")
        with tempfile.TemporaryDirectory() as d:
            v, o, r = (pathlib.Path(d, n) for n in ("v.txt", "o.txt", "r.txt"))
            v.write_text(VOICE, encoding="utf-8")
            o.write_text(FAR, encoding="utf-8")
            r.write_text(CLOSE, encoding="utf-8")
            p = subprocess.run([sys.executable, "-X", "utf8", script, "--voice", str(v), "--original", str(o),
                                "--rewrite", str(r)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("is closer to", p.stdout)
            self.assertEqual(subprocess.run([sys.executable, script], capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
