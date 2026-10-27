"""cocotb verification of the default zero-wait APB register-file slave.

All directed, random and coverage-closing transactions use the same checked bus.
"""
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from apb_checks import CheckedAPB, N_REGS, ID_IDX, ID_RESET, RW_INDICES, close_coverage

CLK_NS = 10

# ---------------------------------------------------------------- APB driver (BFM)
class APBMaster:
    def __init__(self, dut):
        self.dut = dut

    async def _idle(self):
        self.dut.psel.value = 0
        self.dut.penable.value = 0
        self.dut.pwrite.value = 0

    async def write(self, addr, data):
        d = self.dut
        await RisingEdge(d.pclk)
        d.psel.value = 1; d.penable.value = 0
        d.pwrite.value = 1; d.paddr.value = addr; d.pwdata.value = data
        await RisingEdge(d.pclk)          # -> ACCESS phase
        d.penable.value = 1
        await RisingEdge(d.pclk)
        while d.pready.value == 0:
            await RisingEdge(d.pclk)
        err = int(d.pslverr.value)
        await FallingEdge(d.pclk)
        await self._idle()
        return err

    async def read(self, addr):
        d = self.dut
        await RisingEdge(d.pclk)
        d.psel.value = 1; d.penable.value = 0
        d.pwrite.value = 0; d.paddr.value = addr
        await RisingEdge(d.pclk)          # -> ACCESS phase
        d.penable.value = 1
        await RisingEdge(d.pclk)
        while d.pready.value == 0:
            await RisingEdge(d.pclk)
        data = int(d.prdata.value)
        err = int(d.pslverr.value)
        await FallingEdge(d.pclk)
        await self._idle()
        return data, err

async def reset(dut):
    dut.presetn.value = 0
    dut.psel.value = 0; dut.penable.value = 0
    dut.pwrite.value = 0; dut.paddr.value = 0; dut.pwdata.value = 0
    for _ in range(5):
        await RisingEdge(dut.pclk)
    dut.presetn.value = 1
    await RisingEdge(dut.pclk)

def start_clock(dut):
    try:
        cocotb.start_soon(Clock(dut.pclk, CLK_NS, unit="ns").start())
    except TypeError:                     # older cocotb used 'units='
        cocotb.start_soon(Clock(dut.pclk, CLK_NS, units="ns").start())

# ---------------------------------------------------------------- tests
@cocotb.test()
async def test_reset_id_value(dut):
    start_clock(dut)
    await reset(dut)
    checked = CheckedAPB(APBMaster(dut))
    data, _ = await checked.read(ID_IDX << 2)
    assert data == ID_RESET


@cocotb.test()
async def test_directed_write_readback(dut):
    start_clock(dut)
    await reset(dut)
    checked = CheckedAPB(APBMaster(dut))
    for idx in sorted(RW_INDICES):
        await checked.write(idx << 2, 0xA5A50000 | idx)
        await checked.read(idx << 2)
    await checked.read(ID_IDX << 2)
    assert checked.coverage.regs_written == RW_INDICES
    assert checked.coverage.regs_read == set(range(N_REGS))
    checked.coverage.report(dut._log)


@cocotb.test()
async def test_readonly_error(dut):
    start_clock(dut)
    await reset(dut)
    checked = CheckedAPB(APBMaster(dut))
    assert await checked.write(ID_IDX << 2, 0xDEADBEEF) == 1
    data, err = await checked.read(ID_IDX << 2)
    assert err == 0 and data == ID_RESET
    assert checked.coverage.saw_ro_err


@cocotb.test()
async def test_decode_error(dut):
    start_clock(dut)
    await reset(dut)
    checked = CheckedAPB(APBMaster(dut))
    assert await checked.write(0x40, 0x1234) == 1
    _, err = await checked.read(0x80)
    assert err == 1
    assert checked.coverage.saw_decode_err


@cocotb.test()
async def test_read_after_write_coverage(dut):
    """Exercise the coverage gate against actual RTL transactions."""
    start_clock(dut)
    await reset(dut)
    checked = CheckedAPB(APBMaster(dut))
    await checked.read(0)
    assert not checked.coverage.saw_read_after_write
    await checked.write(0, 0xA5A55A5A)
    await checked.read(4)
    assert not checked.coverage.saw_read_after_write
    await checked.read(0)
    assert checked.coverage.saw_read_after_write
    dut._log.info("COVERAGE GATE PASS: read-only/unrelated reads earn no RAW credit")


@cocotb.test()
async def test_constrained_random(dut):
    num = int(cocotb.plusargs.get("num", 300)) if hasattr(cocotb, "plusargs") else 300
    assert num >= 0, "num must be nonnegative"
    start_clock(dut)
    await reset(dut)
    checked = CheckedAPB(APBMaster(dut))
    rng = random.Random(2)
    for _ in range(num):
        if rng.random() < 0.3:
            addr = rng.randrange(0x20, 0x100) & 0xFC
        else:
            addr = rng.randrange(N_REGS) << 2
        if rng.random() < 0.5:
            await checked.write(addr, rng.getrandbits(32))
        else:
            await checked.read(addr)
    random_count = checked.transactions
    await close_coverage(checked)
    closure_count = checked.transactions - random_count
    hit, total = checked.coverage.report(dut._log)
    assert hit == total, f"coverage not closed: {hit}/{total}"
    assert closure_count == 18, f"unexpected closure length: {closure_count}"
    dut._log.info(
        "RANDOM regression: %d random + %d closure = %d transactions self-checked, 0 mismatches",
        random_count, closure_count, checked.transactions)
