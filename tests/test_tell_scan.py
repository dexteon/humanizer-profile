"""Tests for scripts/tell_scan.py. Synthetic strings only."""

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import tell_scan as ts  # noqa: E402


def ids(text, allow=None):
    return {t["id"]: t["count"] for t in ts.scan(text, allow)["tells"] if t["count"]}


class NewTellTests(unittest.TestCase):
    def test_rather_than(self):
        self.assertEqual(ids("The team chose speed rather than polish.").get("39a"), 1)

    def test_associated_with(self):
        self.assertEqual(ids("The fund was associated with several firms, and in connection with the audit.").get("39b"), 2)

    def test_primary_source(self):
        self.assertEqual(ids("Primary sources identify the firm as the buyer.").get("39c"), 1)

    def test_source_availability(self):
        n = ids("I could not access the filing. Sources may be unavailable, and details are not publicly available.")
        self.assertEqual(n.get("39d"), 3)

    def test_clean_text_no_new_tells(self):
        n = ids("The firm bought the plant in May. It cut staff by ten.")
        self.assertFalse([k for k in n if k.startswith("39")])

    def test_era_field_and_order(self):
        res = ts.scan("Smart “quotes” and a vibrant tapestry rather than plain text.")
        eras = [t["era"] for t in res["tells"] if t["count"] and not t["hard"]]
        self.assertEqual(eras, sorted(eras, key=lambda e: ts.ERA_RANK[e]))
        self.assertTrue(all("era" in t for t in res["tells"]))

    def test_paren_and_staccato(self):
        n = ids("We met (twice) and agreed (mostly) on terms. It ended. No deal. Not now. Done.")
        self.assertIn("38", n)
        self.assertIn("31", n)


class AllowlistTests(unittest.TestCase):
    def test_allow_skips_advisory_not_hard(self):
        text = "And so it went. But why? So we left.\n\nIt ended — done."
        self.assertIn("37", ids(text))
        got = ids(text, {"37", "14"})
        self.assertNotIn("37", got)
        self.assertIn("14", got)

    def test_voice_dir_cli(self):
        script = str(SCRIPTS / "tell_scan.py")
        with tempfile.TemporaryDirectory() as d:
            vd = pathlib.Path(d, "voice")
            vd.mkdir()
            (vd / "allow.json").write_text(json.dumps({"allow": ["37", "14"]}), encoding="utf-8")
            f = pathlib.Path(d, "t.txt")
            f.write_text("And so it went. But why? So we left.", encoding="utf-8")
            r = subprocess.run([sys.executable, "-X", "utf8", script, str(f), "--json", "--voice-dir", str(vd)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            data = json.loads(r.stdout)
            self.assertEqual(data["allowlisted"], ["37"])
            self.assertNotIn("37", [t["id"] for t in data["tells"]])


class StatsTests(unittest.TestCase):
    SAMPLE = ("I don't think it's a bad plan. We tested the idea, and it held up.\n\n"
              "- first point\n- second point\n\n## Heading\n\nThe administration of the organization "
              "required careful implementation, quickly and quietly.")

    def test_stats_fields(self):
        st = ts.text_stats(self.SAMPLE)
        for k in ("long_words_7plus", "nominalisations", "ly_adverbs", "commas", "contractions",
                  "first_person", "mattr_50", "paragraphs", "one_line_paragraphs", "bullets", "headings", "bold"):
            self.assertIn(k, st)
        self.assertGreater(st["contractions"], 0)
        self.assertGreater(st["first_person"], 0)
        self.assertGreater(st["nominalisations"], 0)
        self.assertGreater(st["ly_adverbs"], 0)
        self.assertGreater(st["bullets"], 0)
        self.assertEqual(st["headings"], ts._rate(1, st["words"]))

    def test_mattr(self):
        self.assertEqual(ts.mattr(["a"] * 100), 0.02)
        self.assertEqual(ts.mattr(["a", "b", "c", "d"]), 1.0)

    def test_density_repeat_multiplier(self):
        one = ts.scan("A vibrant town.")
        many = ts.scan("A vibrant town. A vibrant city. A vibrant port.")
        d1 = ts.tell_density(one, 3)
        d3 = ts.tell_density(many, 3)
        self.assertGreater(d3, d1 * 3)

    def test_cli_stats_compare_and_exit_codes(self):
        script = str(SCRIPTS / "tell_scan.py")
        with tempfile.TemporaryDirectory() as d:
            a, b = pathlib.Path(d, "a.txt"), pathlib.Path(d, "b.txt")
            a.write_text("One, two, three, four, five, six, seven. It was fine.", encoding="utf-8")
            b.write_text("One two three four five six seven. It was fine.", encoding="utf-8")
            r = subprocess.run([sys.executable, "-X", "utf8", script, str(a), "--stats", "--compare", str(b)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("compare", r.stdout)
            self.assertIn("comma rate rose", r.stdout)
            bad = subprocess.run([sys.executable, "-X", "utf8", script, str(a), "--compare", str(b)],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            hard = pathlib.Path(d, "h.txt")
            hard.write_text("It ended — done.", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, "-X", "utf8", script, str(hard)],
                                            capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
