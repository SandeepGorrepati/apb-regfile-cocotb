"""Reference checks and evidence-based coverage for the default APB register map.

No simulator dependency: negative controls can exercise the checker itself.
Coverage is sampled only after expected data and error responses are checked.
"""
N_REGS = 8
ID_IDX = 6
ID_RESET = 0xC0DE0001
ADDR_MAX = 0x20
RW_INDICES = set(range(N_REGS)) - {ID_IDX}


class RegModel:
    def __init__(self):
        self.regs = [0] * N_REGS
        self.regs[ID_IDX] = ID_RESET

    def predict_write(self, addr, data):
        if addr >= ADDR_MAX:
            return 1
        idx = (addr >> 2) & 7
        if idx == ID_IDX:
            return 1
        self.regs[idx] = data & 0xFFFFFFFF
        return 0

    def predict_read(self, addr):
        if addr >= ADDR_MAX:
            return 0, 1
        return self.regs[(addr >> 2) & 7], 0


class Coverage:
    def __init__(self):
        self.regs_written = set()
        self.regs_read = set()
        self.last_written = {}
        self.saw_write_ok = False
        self.saw_read_ok = False
        self.saw_decode_err = False
        self.saw_ro_err = False
        self.saw_read_after_write = False

    def checked_write(self, addr, data, err):
        if err:
            if addr >= ADDR_MAX:
                self.saw_decode_err = True
            elif (addr >> 2) & 7 == ID_IDX:
                self.saw_ro_err = True
            return
        idx = (addr >> 2) & 7
        self.regs_written.add(idx)
        self.last_written[idx] = data & 0xFFFFFFFF
        self.saw_write_ok = True

    def checked_read(self, addr, data, err):
        if err:
            self.saw_decode_err = True
            return
        idx = (addr >> 2) & 7
        self.regs_read.add(idx)
        self.saw_read_ok = True
        if idx in self.last_written and data == self.last_written[idx]:
            self.saw_read_after_write = True

    def bins(self):
        return {
            "all 7 RW registers written": self.regs_written == RW_INDICES,
            "all 8 registers read": self.regs_read == set(range(N_REGS)),
            "clean write (no PSLVERR)": self.saw_write_ok,
            "clean read (no PSLVERR)": self.saw_read_ok,
            "decode-error PSLVERR": self.saw_decode_err,
            "read-only-write PSLVERR": self.saw_ro_err,
            "checked same-register read-after-write": self.saw_read_after_write,
        }

    def report(self, log):
        items = self.bins()
        hit, total = sum(items.values()), len(items)
        log.info("FUNCTIONAL COVERAGE: %d/%d defined bins (%.0f%%)",
                 hit, total, 100.0 * hit / total)
        for name, ok in items.items():
            log.info("  [%s] %s", "x" if ok else " ", name)
        return hit, total


class CheckedAPB:
    """Check every completed transaction before updating coverage."""
    def __init__(self, bus, model=None, coverage=None):
        self.bus = bus
        self.model = model if model is not None else RegModel()
        self.coverage = coverage if coverage is not None else Coverage()
        self.transactions = 0

    async def write(self, addr, data):
        actual_err = await self.bus.write(addr, data)
        expected_err = self.model.predict_write(addr, data)
        assert actual_err == expected_err, (
            f"WRITE error mismatch @ {addr:#x}: got {actual_err}, expected {expected_err}")
        self.coverage.checked_write(addr, data, actual_err)
        self.transactions += 1
        return actual_err

    async def read(self, addr):
        actual_data, actual_err = await self.bus.read(addr)
        expected_data, expected_err = self.model.predict_read(addr)
        assert actual_err == expected_err, (
            f"READ error mismatch @ {addr:#x}: got {actual_err}, expected {expected_err}")
        assert actual_data == expected_data, (
            f"READ data mismatch @ {addr:#x}: got {actual_data:#x}, expected {expected_data:#x}")
        self.coverage.checked_read(addr, actual_data, actual_err)
        self.transactions += 1
        return actual_data, actual_err


async def close_coverage(checked):
    """Deterministic stimulus; every response is checked through CheckedAPB."""
    for idx in sorted(RW_INDICES):
        await checked.write(idx << 2, 0xC0FFEE00 | idx)
        await checked.read(idx << 2)
    await checked.write(ID_IDX << 2, 1)
    await checked.read(ID_IDX << 2)
    await checked.write(0x40, 1)
    await checked.read(0x80)
