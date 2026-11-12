"""Tests for scripts/unit_diff.py. Synthetic strings only. Run: python -X utf8 -m unittest discover tests"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import unit_diff as ud  # noqa: E402


def kinds(a, b):
    return ud.diff_texts(a, b)["kinds"]


class UnitDiffTests(unittest.TestCase):
    def test_identical_is_clean(self):
        t = "Acme Corp paid $1,200 on Nov 3, 2026 under 38 U.S.C. 5303(a)."
        self.assertTrue(ud.diff_texts(t, t)["clean"])

    def test_reformat_tolerated(self):
        a = "Acme Corp paid $1,000 on Nov 3, citing Art. 133. Growth was 50%."
        b = "Acme Corp paid $1000 on November 3, citing Article 133. Growth was 50 percent."
        self.assertTrue(ud.diff_texts(a, b)["clean"], ud.diff_texts(a, b))

    def test_magnitude_words(self):
        self.assertTrue(ud.diff_texts("It cost $5 million.", "It cost $5000000.")["clean"])

    def test_statute_cite_changed(self):
        k = kinds("See 38 U.S.C. 5303(a) for the rule.", "See 38 U.S.C. 5304(a) for the rule.")
        self.assertIn("cite", k)
        self.assertEqual(len(k["cite"]["changed"]), 1)

    def test_cfr_cite(self):
        k = kinds("Report under 10 CFR 50.73 within 60 days.", "Report within 60 days.")
        self.assertEqual(k["cite"]["dropped"], ["10 CFR 50.73"])

    def test_number_dropped(self):
        k = kinds("We shipped 40 units to 3 sites.", "We shipped units to 3 sites.")
        self.assertEqual(k["number"]["dropped"], ["40"])

    def test_number_added(self):
        k = kinds("Sales grew.", "Sales grew 12 percent.")
        self.assertEqual(k["number"]["added"], ["12 percent"])

    def test_unit_changed(self):
        k = kinds("The dose is 10 mg daily.", "The dose is 10 kg daily.")
        self.assertIn("number", k)

    def test_date_changed(self):
        k = kinds("Filed on March 4, 2026.", "Filed on March 5, 2026.")
        self.assertIn("date", k)

    def test_form_id(self):
        self.assertTrue(ud.diff_texts("Submit VA 21-4142 today.", "Please submit VA Form 21-4142 today.")["clean"])
        k = kinds("Submit VA 21-4142 today.", "Submit VA 21-4143 today.")
        self.assertIn("form", k)

    def test_url_and_email(self):
        a = "Write to contact.a@example.org or see https://example.org/page."
        b = "Write to contact.b@example.org or see https://example.org/other."
        k = kinds(a, b)
        self.assertIn("email", k)
        self.assertIn("url", k)

    def test_quote_changed_and_curly_tolerated(self):
        self.assertTrue(ud.diff_texts('He said "we are on track."', "He said “we are on track.”")["clean"])
        k = kinds('He said "we are on track."', 'He said "we are ahead."')
        self.assertIn("quote", k)

    def test_name_dropped(self):
        k = kinds("Contact A met Acme Corp in Denver.", "Contact A met the firm in Denver.")
        self.assertIn("Acme Corp", k["name"]["dropped"])

    def test_sentence_initial_word_not_a_name(self):
        self.assertTrue(ud.diff_texts("Growth slowed. Costs rose.", "Costs rose. Growth slowed.")["clean"])

    def test_cli_exit_codes(self):
        import subprocess
        import tempfile
        script = str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "unit_diff.py")
        with tempfile.TemporaryDirectory() as d:
            a, b = pathlib.Path(d, "a.txt"), pathlib.Path(d, "b.txt")
            a.write_text("Paid $10.", encoding="utf-8")
            b.write_text("Paid $10.", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, script, str(a), str(b)]).returncode, 0)
            b.write_text("Paid $11.", encoding="utf-8")
            self.assertEqual(subprocess.run([sys.executable, script, str(a), str(b), "--json"],
                                            capture_output=True).returncode, 1)
            self.assertEqual(subprocess.run([sys.executable, script, str(a)], capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
