"""Python test runner (cocotb >= 2.0). Run:  python sim/runner.py
Builds the APB DUT with Icarus Verilog and runs the cocotb test suite."""
import os
from pathlib import Path
from cocotb_tools.runner import get_runner

ROOT = Path(__file__).resolve().parents[1]

def test_apb_regfile():
    sim = os.getenv("SIM", "icarus")
    runner = get_runner(sim)
    runner.build(
        verilog_sources=[ROOT / "rtl" / "apb_regfile.v"],
        hdl_toplevel="apb_regfile",
        build_dir=ROOT / "sim" / "sim_build",
        always=True,
        timescale=("1ns", "1ps"),
        waves=True,
    )
    runner.test(
        hdl_toplevel="apb_regfile",
        test_module="test_apb_regfile",
        test_dir=ROOT / "tb",
        waves=True,
    )

if __name__ == "__main__":
    test_apb_regfile()
