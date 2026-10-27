"""Checker negative controls: passing coverage must represent checked behavior."""
import unittest
from apb_checks import CheckedAPB, Coverage, ID_IDX, ID_RESET, RW_INDICES, close_coverage


class FakeBus:
    def __init__(self):
        self.regs = {i << 2: 0 for i in range(8)}
        self.regs[ID_IDX << 2] = ID_RESET
        self.bad_read_addr = None
        self.bad_write_status_addr = None
        self.bad_read_status_addr = None

    async def write(self, addr, data):
        err = int(addr >= 0x20 or addr == ID_IDX << 2)
        if not err:
            self.regs[addr] = data & 0xFFFFFFFF
        return 1 - err if addr == self.bad_write_status_addr else err

    async def read(self, addr):
        err = int(addr >= 0x20)
        data = self.regs.get(addr, 0)
        if addr == self.bad_read_addr:
            data ^= 1
        if addr == self.bad_read_status_addr:
            err = 1 - err
        return data, err


class CheckerTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_before_write_gets_no_raw_credit(self):
        bus = CheckedAPB(FakeBus())
        await bus.read(0)
        self.assertFalse(bus.coverage.saw_read_after_write)

    async def test_other_register_read_gets_no_raw_credit(self):
        bus = CheckedAPB(FakeBus())
        await bus.write(0, 42)
        await bus.read(4)
        self.assertFalse(bus.coverage.saw_read_after_write)

    async def test_matching_register_read_gets_raw_credit(self):
        bus = CheckedAPB(FakeBus())
        await bus.write(0, 42)
        await bus.read(0)
        self.assertTrue(bus.coverage.saw_read_after_write)

    async def test_bad_data_fails_without_raw_credit(self):
        fake = FakeBus()
        bus = CheckedAPB(fake)
        await bus.write(0, 42)
        fake.bad_read_addr = 0
        with self.assertRaisesRegex(AssertionError, "READ data mismatch"):
            await bus.read(0)
        self.assertFalse(bus.coverage.saw_read_after_write)
        self.assertEqual(bus.coverage.regs_read, set())

    async def test_bad_write_status_fails_without_write_credit(self):
        fake = FakeBus()
        fake.bad_write_status_addr = 0
        bus = CheckedAPB(fake)
        with self.assertRaisesRegex(AssertionError, "WRITE error mismatch"):
            await bus.write(0, 42)
        self.assertEqual(bus.coverage.regs_written, set())

    async def test_bad_read_status_fails_without_read_credit(self):
        fake = FakeBus()
        fake.bad_read_status_addr = 0
        bus = CheckedAPB(fake)
        with self.assertRaisesRegex(AssertionError, "READ error mismatch"):
            await bus.read(0)
        self.assertEqual(bus.coverage.regs_read, set())

    async def test_coverage_closure_rejects_corrupt_readback(self):
        fake = FakeBus()
        fake.bad_read_addr = 4
        with self.assertRaisesRegex(AssertionError, "READ data mismatch"):
            await close_coverage(CheckedAPB(fake))

    async def test_coverage_closure_rejects_bad_write_status(self):
        fake = FakeBus()
        fake.bad_write_status_addr = 4
        with self.assertRaisesRegex(AssertionError, "WRITE error mismatch"):
            await close_coverage(CheckedAPB(fake))

    async def test_coverage_closure_checks_id_read(self):
        fake = FakeBus()
        fake.bad_read_addr = ID_IDX << 2
        with self.assertRaisesRegex(AssertionError, "READ data mismatch"):
            await close_coverage(CheckedAPB(fake))

    async def test_full_closure_is_18_checked_transactions(self):
        bus = CheckedAPB(FakeBus())
        await close_coverage(bus)
        self.assertEqual(bus.transactions, 18)
        self.assertEqual(bus.coverage.regs_written, RW_INDICES)
        self.assertEqual(bus.coverage.regs_read, set(range(8)))
        self.assertTrue(all(bus.coverage.bins().values()))


if __name__ == "__main__":
    unittest.main()
