# Coverage correction — 27 October 2026

The previous testbench credited read-after-write on any successful read and
manually marked some coverage during unverified closing accesses.

The correction routes every test and closure transaction through CheckedAPB:
status/data assertions precede coverage sampling. The read-after-write bin
requires a successful write followed by matching readback of the same register.
The all-register-write bin is explicitly seven RW registers; the ID read is a
real checked bus access.

Validation consists of ten Python checker unit tests, including data/status
negative controls, and six cocotb tests against the unchanged register-file RTL.
The default random run performs 300 random plus 18 checked closing transactions.

## Executed evidence

[Passing workflow 40496957607](https://github.com/SandeepGorrepati/apb-regfile-cocotb/actions/runs/40496957607)
executed correction commit `7d16790eaa24d1b35ceefbaecb776cd3454d674e` on 27 October 2026.

- Ten checker unit tests passed, including intentionally wrong data/status.
- Six cocotb tests passed against the unchanged RTL: TESTS=6 PASS=6 FAIL=0 SKIP=0.
- The actual-DUT coverage-gate test confirmed that reads before writes and reads
  of unrelated registers do not earn read-after-write credit.
- Random regression: 300 random + 18 closing = 318 checked transactions, zero mismatches.
- All seven explicitly defined bins hit. The directed write/read test alone
  reports 5/7, correctly leaving the error-path bins uncredited.

The source/test correction was validated before promotion to main. This evidence
page records that run; later documentation commits do not introduce new functional
results. See current Actions for subsequent executions and exact tested commits.

## Actual-RTL mutation controls

The follow-up checks compile separate temporary copies with corrupted write data,
suppressed PSLVERR, and a corrupted reset ID. The production RTL file is untouched.
A healthy baseline must pass; each mutant must fail an expected checker and have
complete simulation-result XML. Five result-gate unit tests reject escaped mutants,
missing simulation results and unrelated tool failures.

Execution evidence for these additional mutation controls will be recorded after
the validation branch completes. The earlier ten-unit/six-RTL results above remain
the evidence for the original coverage correction.
