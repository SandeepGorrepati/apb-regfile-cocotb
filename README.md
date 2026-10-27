# APB register-file verification with cocotb

A zero-wait, 8×32-bit register-file slave with an APB SETUP/ACCESS interface,
a Python bus functional model, reference-model checks and scoped coverage.
The default 32-bit implementation does not provide PSTRB byte writes or variable
wait states; it is not a claim of complete APB4 feature coverage.

## Checked behavior

- Reset ID value, all seven writable registers and all eight readable registers.
- Writes to the read-only ID register and out-of-range reads/writes return PSLVERR.
- Six cocotb tests, including a dedicated read-after-write coverage-gate test.
- Seed-2 regression: 300 random transactions plus 18 deterministic closing
  transactions by default; every transaction checks its expected error status,
  and every read checks its expected data, including closing and error-path reads.
- Seven explicitly defined Python coverage bins. A read-after-write hit requires
  a checked successful write and matching checked read of that same register.
  Reads before writes and reads of unrelated registers earn no such credit.

Coverage is evidence for these bins, not exhaustive protocol, RTL code, state-space
or all-parameter verification. Only the default address/data widths are tested.
The ID register is read-only, so the write bin covers seven registers, not eight.

## How the checker is checked

`tb/apb_checks.py` samples coverage only after data/status comparisons pass.
Ten simulator-independent unit tests include deliberately corrupted read data
and incorrect read/write error status, including deterministic coverage-closing
transactions and the ID read. These negative controls must raise checker failures.

CI also compiles temporary copies with three actual RTL defects: corrupted write
data, suppressed PSLVERR and a corrupted reset ID. The healthy baseline must pass;
each mutant must execute the test suite, fail an expected data/status check and
produce test-result XML. Compilation errors, missing tests and unrelated failures
do not count as detected faults. Production RTL remains unchanged.

The cocotb suite separately exercises the coverage gate through actual RTL
transactions. All random and directed accesses use the same checked bus wrapper;
coverage is not closed by directly setting bins.

## Reproduce

Install Python, Icarus Verilog and the Python requirements:

```bash
pip install -r requirements.txt
python -m unittest discover -s tb -p 'test_apb_checks.py' -v
python sim/runner.py
python sim/check_mutations.py
```

The CI workflow runs checker tests, RTL regression and mutation controls on each push and pull request.
Use the workflow for the exact commit being reviewed. The historical
`sim/run_log.txt` predates the coverage correction and is not current evidence.
Results for the correction are linked in [verification evidence](docs/VERIFICATION.md).

## Files

| File | Purpose |
|---|---|
| `rtl/apb_regfile.v` | Default register-file DUT; unchanged by the coverage correction |
| `tb/test_apb_regfile.py` | APB driver and six RTL simulation tests |
| `tb/apb_checks.py` | Reference model, checked transactions and coverage sampling |
| `tb/test_apb_checks.py` | Unit tests and checker negative controls |
| `sim/runner.py` | Icarus/cocotb runner |
| `.github/workflows/ci.yml` | Unit checks and RTL regression |

Potential extensions include wait-state testing, byte strobes and additional
reset/traffic scenarios. They are not claimed as implemented.
