# APB4 Register-File Slave — cocotb Verification

A synthesizable **AMBA APB4** register-file slave (RTL) with a complete
**cocotb (Python)** verification environment: bus functional model, reference-model
scoreboard, self-checking constrained-random regression, error-path validation, and
functional-coverage closure. Runs on free Icarus Verilog (or Verilator).

## Results (reproducible)
- 5 tests, **PASS=5 / FAIL=0**
- **300 constrained-random transactions** self-checked against a reference model, **0 mismatches**
- **100% functional coverage (7/7 bins)** including both PSLVERR error paths
- See `sim/run_log.txt` for the captured run.

## Design (`rtl/apb_regfile.v`)
8×32-bit register file, two-phase SETUP/ACCESS APB4 protocol, zero wait states.
`PSLVERR` is asserted for (a) out-of-range address decode and (b) writes to the
read-only `ID` register. `ID` resets to `0xC0DE0001`.

## Verification env (`tb/test_apb_regfile.py`)
- `APBMaster` — APB driver/BFM (SETUP→ACCESS phasing, PREADY handshake)
- `RegModel`  — reference model predicting read data and PSLVERR
- `Coverage`  — functional coverage: every register R/W, both error paths, read-after-write
- Tests: reset value, directed write/readback, read-only error, decode error,
  and a self-checking constrained-random regression that closes coverage.

## Run it
```bash
# Ubuntu 22.04
sudo apt-get update && sudo apt-get install -y iverilog
pip install -r requirements.txt
python sim/runner.py          # Python runner (recommended)
# or:  cd sim && make          # classic cocotb Makefile flow
```
Waveforms are written to `sim/sim_build/*.fst` (open with GTKWave/Surfer).

## Layout
```
rtl/apb_regfile.v          DUT
tb/test_apb_regfile.py     cocotb testbench (BFM + scoreboard + coverage)
sim/runner.py              python runner
sim/Makefile               classic cocotb make flow
sim/run_log.txt            captured passing run
.github/workflows/ci.yml   CI: runs the full regression on every push
```

## Extend it (ideas)
- Add APB wait states (PREADY deassertion) and randomize them.
- Add byte-strobe (PSTRB) support and partial-write coverage.
- Replace the dict scoreboard with a UVM-RAL-style mirror.
- Swap in a real IP block (UART/SPI/I2C) behind the same APB front-end.
