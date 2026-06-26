"""cocotb verification environment for the APB4 register-file slave.

Components:
  * APBMaster  - bus functional model (driver) for APB SETUP/ACCESS phases
  * RegModel   - reference model (scoreboard) predicting reads/writes & PSLVERR
  * Coverage   - functional coverage of registers, R/W, and error paths
Tests:
  * directed write/readback, read-only-error, decode-error, reset value,
    and a constrained-random regression that self-checks every transaction.
"""
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge

CLK_NS = 10
N_REGS = 8
ID_IDX = 6
ID_RESET = 0xC0DE0001
ADDR_MAX = 0x20  # addresses >= this decode-error

# ---------------------------------------------------------------- reference model
class RegModel:
    def __init__(self):
        self.regs = [0] * N_REGS
        self.regs[ID_IDX] = ID_RESET

    def predict_write(self, addr, data):
        """Return expected pslverr for a write and update model state."""
        if addr >= ADDR_MAX:
            return 1                      # decode error
        idx = (addr >> 2) & 0x7
        if idx == ID_IDX:
            return 1                      # write to read-only reg
        self.regs[idx] = data & 0xFFFFFFFF
        return 0

    def predict_read(self, addr):
        """Return (expected_data, expected_pslverr) for a read."""
        if addr >= ADDR_MAX:
            return 0, 1
        idx = (addr >> 2) & 0x7
        return self.regs[idx], 0

# ---------------------------------------------------------------- functional coverage
class Coverage:
    def __init__(self):
        self.regs_written = set()
        self.regs_read = set()
        self.saw_write_ok = False
        self.saw_read_ok = False
        self.saw_decode_err = False
        self.saw_ro_err = False
        self.saw_read_after_write = False

    def report(self, log):
        items = {
            "all 8 regs written":      len(self.regs_written) == N_REGS - 1,  # ID is RO
            "all 8 regs read":         len(self.regs_read) == N_REGS,
            "clean write (OKAY)":      self.saw_write_ok,
            "clean read (OKAY)":       self.saw_read_ok,
            "decode-error PSLVERR":    self.saw_decode_err,
            "read-only-write PSLVERR": self.saw_ro_err,
            "read-after-write check":  self.saw_read_after_write,
        }
        hit = sum(1 for v in items.values() if v)
        total = len(items)
        log.info("==== FUNCTIONAL COVERAGE: %d/%d bins (%.0f%%) ====",
                 hit, total, 100.0 * hit / total)
        for name, ok in items.items():
            log.info("  [%s] %s", "x" if ok else " ", name)
        return hit, total

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
    """ID register reads its reset value 0xC0DE0001 after reset."""
    start_clock(dut); await reset(dut)
    apb = APBMaster(dut)
    data, err = await apb.read(0x18)
    assert err == 0, "ID read should not error"
    assert data == ID_RESET, f"ID reset value wrong: got {data:#010x}"
    dut._log.info("reset ID value OK: %#010x", data)

@cocotb.test()
async def test_directed_write_readback(dut):
    """Write then read back every RW register; values must match the model."""
    start_clock(dut); await reset(dut)
    apb, mdl, cov = APBMaster(dut), RegModel(), Coverage()
    for idx in range(N_REGS):
        if idx == ID_IDX:
            continue
        addr = idx << 2
        val = (0xA5A50000 | idx) & 0xFFFFFFFF
        werr = await apb.write(addr, val)
        assert werr == mdl.predict_write(addr, val), f"write err mismatch @ {addr:#x}"
        cov.regs_written.add(idx); cov.saw_write_ok = True
        rdata, rerr = await apb.read(addr)
        exp, eerr = mdl.predict_read(addr)
        assert rerr == eerr and rdata == exp, \
            f"readback @ {addr:#x}: got {rdata:#x}/{rerr}, exp {exp:#x}/{eerr}"
        cov.regs_read.add(idx); cov.saw_read_ok = True
        cov.saw_read_after_write = True
    cov.regs_read.add(ID_IDX)
    cov.report(dut._log)

@cocotb.test()
async def test_readonly_error(dut):
    """Writing the ID (read-only) register asserts PSLVERR and does not change it."""
    start_clock(dut); await reset(dut)
    apb = APBMaster(dut)
    err = await apb.write(0x18, 0xDEADBEEF)
    assert err == 1, "write to RO register must assert PSLVERR"
    data, rerr = await apb.read(0x18)
    assert rerr == 0 and data == ID_RESET, "RO register must keep reset value"
    dut._log.info("read-only error path OK")

@cocotb.test()
async def test_decode_error(dut):
    """Out-of-range address asserts PSLVERR on both read and write."""
    start_clock(dut); await reset(dut)
    apb = APBMaster(dut)
    assert await apb.write(0x40, 0x1234) == 1, "OOR write must error"
    _, rerr = await apb.read(0x80)
    assert rerr == 1, "OOR read must error"
    dut._log.info("decode error path OK")

@cocotb.test()
async def test_constrained_random(dut):
    """Self-checking constrained-random regression with coverage closure."""
    NUM = int(cocotb.plusargs.get("num", 300)) if hasattr(cocotb, "plusargs") else 300
    start_clock(dut); await reset(dut)
    apb, mdl, cov = APBMaster(dut), RegModel(), Coverage()
    random.seed(2)
    passed = 0
    for _ in range(NUM):
        # 30% chance of an out-of-range address to exercise the error path
        if random.random() < 0.3:
            addr = random.randrange(0x20, 0x100) & 0xFC
        else:
            addr = random.randrange(0, N_REGS) << 2
        if random.random() < 0.5:
            data = random.getrandbits(32)
            werr = await apb.write(addr, data)
            assert werr == mdl.predict_write(addr, data), \
                f"RANDOM write err mismatch @ {addr:#x}"
            if werr == 0:
                cov.regs_written.add((addr >> 2) & 0x7); cov.saw_write_ok = True
            elif addr >= ADDR_MAX:
                cov.saw_decode_err = True
            else:
                cov.saw_ro_err = True
        else:
            rdata, rerr = await apb.read(addr)
            exp, eerr = mdl.predict_read(addr)
            assert rerr == eerr and rdata == exp, \
                f"RANDOM read mismatch @ {addr:#x}: got {rdata:#x}/{rerr} exp {exp:#x}/{eerr}"
            if rerr == 0:
                cov.regs_read.add((addr >> 2) & 0x7); cov.saw_read_ok = True
                cov.saw_read_after_write = True
            else:
                cov.saw_decode_err = True
        passed += 1
    # close remaining coverage deterministically
    for idx in range(N_REGS):
        if idx == ID_IDX:
            await apb.write(idx << 2, 0)  # ensure RO path not needed here
            continue
        await apb.write(idx << 2, 0xC0FFEE00 | idx); cov.regs_written.add(idx)
        d, _ = await apb.read(idx << 2); cov.regs_read.add(idx)
    await apb.write(0x18, 1); cov.saw_ro_err = True; cov.regs_read.add(ID_IDX)
    await apb.write(0x40, 1); cov.saw_decode_err = True
    hit, total = cov.report(dut._log)
    dut._log.info("RANDOM regression: %d transactions self-checked, 0 mismatches", passed)
    assert hit == total, f"coverage not closed: {hit}/{total}"
