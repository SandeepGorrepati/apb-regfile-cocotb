"""Reject vacuous mutation passes and unrelated compiler/tool failures."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "check_mutations", Path(__file__).resolve().parents[1] / "sim" / "check_mutations.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MutationResultTests(unittest.TestCase):
    def evaluate(self, failures=0, marker="", code=0, expected=None):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "results.xml"
            cases = "".join(
                f'<testcase name="case{i}">' +
                ('<failure message="bad data"/>' if i < failures else '') +
                '</testcase>' for i in range(6))
            file.write_text("<testsuites><testsuite>" + cases +
                            "</testsuite></testsuites>", encoding="utf8")
            return module.check_case("fixture", code, marker, [file], expected)

    def test_healthy_results_accepted(self):
        self.assertEqual(self.evaluate()["result"], "PASS")

    def test_detected_checker_failure_accepted(self):
        result = self.evaluate(1, "READ data mismatch", 1, "READ data mismatch")
        self.assertEqual(result["result"], "DETECTED")

    def test_escaped_mutant_rejected(self):
        with self.assertRaises(RuntimeError):
            self.evaluate(0, "READ data mismatch", 0, "READ data mismatch")

    def test_unrelated_failure_rejected(self):
        with self.assertRaises(RuntimeError):
            self.evaluate(1, "ImportError", 1, "READ data mismatch")

    def test_missing_simulation_results_rejected(self):
        with self.assertRaises(RuntimeError):
            module.check_case("compile failure", 1, "syntax error", [],
                              "READ data mismatch")


if __name__ == "__main__":
    unittest.main()
