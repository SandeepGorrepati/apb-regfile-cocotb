"""Compile actual RTL mutants and require checker failures, not build failures.

Each case runs in a temporary repository copy. Production RTL is never edited.
Logs are retained in sim/mutation_logs for CI inspection.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("rtl/apb_regfile.v")
MUTANTS = {
    "corrupt_written_data": (
        "regs[widx] <= pwdata;",
        "regs[widx] <= pwdata ^ 32'h00000001;",
        "READ data mismatch"),
    "suppress_error_response": (
        "assign pslverr = access & ( (!inrange) | (pwrite & is_id) );",
        "assign pslverr = 1'b0;",
        "WRITE error mismatch"),
    "corrupt_reset_id": (
        "regs[6] <= 32'hC0DE_0001;",
        "regs[6] <= 32'hC0DE_0000;",
        "READ data mismatch"),
}


def check_case(label, result_code, console, xml_paths, expected_failure=None):
    cases = []
    for path in xml_paths:
        cases.extend(ET.parse(path).getroot().findall(".//testcase"))
    if len(cases) < 6:
        raise RuntimeError(f"{label}: missing complete RTL test results ({len(cases)} cases)")
    if any(case.find("skipped") is not None for case in cases):
        raise RuntimeError(f"{label}: skipped RTL test is not acceptable evidence")
    failed = sum(case.find("failure") is not None or case.find("error") is not None
                 for case in cases)
    if expected_failure is None:
        if result_code != 0 or failed:
            raise RuntimeError(f"{label}: healthy RTL did not pass ({failed} failures)")
        return {"case": label, "tests": len(cases), "failed": failed, "result": "PASS"}
    if failed == 0 or expected_failure not in console:
        raise RuntimeError(
            f"{label}: mutation escaped or failed for an unrelated reason; "
            f"failures={failed}, expected={expected_failure!r}")
    return {"case": label, "tests": len(cases), "failed": failed,
            "result": "DETECTED", "expected_checker": expected_failure}


def run_case(label, source, expected_failure=None):
    logs = ROOT / "sim" / "mutation_logs"
    logs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="apb-mutation-") as directory:
        copy = Path(directory) / "repo"
        shutil.copytree(
            ROOT, copy,
            ignore=shutil.ignore_patterns(
                ".git", "__pycache__", "sim_build", "mutation_logs",
                "results.xml", "*.fst", "*.vcd"))
        (copy / SOURCE).write_text(source, encoding="utf8")
        completed = subprocess.run(
            [sys.executable, str(copy / "sim" / "runner.py")],
            cwd=copy, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=90)
        (logs / f"{label}.log").write_text(completed.stdout, encoding="utf8")
        xml_paths = sorted(copy.rglob("*.xml"))
        return check_case(label, completed.returncode, completed.stdout,
                          xml_paths, expected_failure)


def main():
    original = (ROOT / SOURCE).read_text(encoding="utf8")
    results = [run_case("healthy_baseline", original)]
    for label, (old, new, message) in MUTANTS.items():
        if original.count(old) != 1:
            raise RuntimeError(f"{label}: mutation anchor must match exactly once")
        results.append(run_case(label, original.replace(old, new), message))
    if (ROOT / SOURCE).read_text(encoding="utf8") != original:
        raise RuntimeError("Production RTL changed during mutation tests")
    summary = {"results": results, "production_rtl_unchanged": True}
    (ROOT / "sim" / "mutation_logs" / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf8")
    for result in results:
        print("MUTATION CHECK:", json.dumps(result))
    print("PASS: healthy RTL passes; all 3 actual-RTL mutants detected")


if __name__ == "__main__":
    main()
