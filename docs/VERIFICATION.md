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

Validation status: pending the correction branch's GitHub Actions run.
The exact successful run and commit will be recorded after execution.
