import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "portable-core" / "bin" / "alttpr-timerpatch.py"
SPEC = importlib.util.spec_from_file_location("alttpr_timerpatch", SCRIPT)
TIMERPATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TIMERPATCH)


def make_rom(caller=None, reservation=None):
    size = max(
        TIMERPATCH.TIMER_FLAG + 1,
        TIMERPATCH.STOPWATCH_TRAMPOLINE_PC +
        TIMERPATCH.STOPWATCH_TRAMPOLINE_SIZE,
    )
    rom = bytearray(size)
    rom[TIMERPATCH.TIMER_FLAG] = 2
    prefix = TIMERPATCH.FRAME_GATE_PREFIX
    rom[prefix:prefix + len(TIMERPATCH.FRAME_GATE_PREFIX_BYTES)] = (
        TIMERPATCH.FRAME_GATE_PREFIX_BYTES
    )
    caller = caller if caller is not None else TIMERPATCH.CALLER_ORIG
    rom[TIMERPATCH.CALLER:TIMERPATCH.CALLER + len(caller)] = caller
    if reservation is not None:
        start = TIMERPATCH.STOPWATCH_TRAMPOLINE_PC
        rom[start:start + len(reservation)] = reservation
    epilogue = TIMERPATCH.RETURN_EPILOGUE_PC
    rom[epilogue:epilogue + 2] = TIMERPATCH.EXPECTED_RETURN_EPILOGUE
    return rom


class TimerPatchTests(unittest.TestCase):
    def test_timer_disabled_is_no_op(self):
        rom = make_rom()
        rom[TIMERPATCH.TIMER_FLAG] = 0
        original = bytes(rom)
        self.assertEqual(TIMERPATCH.patch_rom(rom), "timer disabled")
        self.assertEqual(bytes(rom), original)

    def test_patches_complete_frame_gate(self):
        rom = make_rom()
        self.assertEqual(
            TIMERPATCH.patch_rom(rom),
            "applied safe trampoline",
        )
        self.assertEqual(
            rom[TIMERPATCH.CALLER:TIMERPATCH.CALLER + 6],
            TIMERPATCH.CALLER_NEW,
        )
        start = TIMERPATCH.STOPWATCH_TRAMPOLINE_PC
        self.assertEqual(
            rom[start:start + TIMERPATCH.STOPWATCH_TRAMPOLINE_SIZE],
            TIMERPATCH.TRAMPOLINE_BYTES,
        )

    def test_skip_branch_lands_on_rtl(self):
        code = TIMERPATCH.TRAMP_CODE
        target = 2 + code[1]
        self.assertEqual(code[target], 0x6B)

    def test_migrates_exact_unsafe_legacy_patch(self):
        legacy = (
            bytes(TIMERPATCH.LEGACY_TRAMPOLINE_PC -
                  TIMERPATCH.STOPWATCH_TRAMPOLINE_PC)
            + TIMERPATCH.LEGACY_TRAMPOLINE
        )
        rom = make_rom(TIMERPATCH.LEGACY_CALLER, legacy)
        self.assertEqual(
            TIMERPATCH.patch_rom(rom),
            "repaired legacy trampoline",
        )
        self.assertEqual(
            rom[TIMERPATCH.CALLER:TIMERPATCH.CALLER + 6],
            TIMERPATCH.CALLER_NEW,
        )

    def test_safe_patch_is_idempotent(self):
        rom = make_rom()
        TIMERPATCH.patch_rom(rom)
        original = bytes(rom)
        self.assertEqual(TIMERPATCH.patch_rom(rom), "already patched")
        self.assertEqual(bytes(rom), original)

    def test_rejects_changed_frame_gate(self):
        rom = make_rom()
        rom[TIMERPATCH.FRAME_GATE_PREFIX] ^= 0xFF
        with self.assertRaisesRegex(RuntimeError, "frame-gate prefix"):
            TIMERPATCH.patch_rom(rom)

    def test_rejects_occupied_reservation(self):
        rom = make_rom(reservation=b"\x01")
        with self.assertRaisesRegex(RuntimeError, "reservation"):
            TIMERPATCH.patch_rom(rom)

    def test_rejects_changed_return_epilogue(self):
        rom = make_rom()
        rom[TIMERPATCH.RETURN_EPILOGUE_PC] ^= 0xFF
        with self.assertRaisesRegex(RuntimeError, "return epilogue"):
            TIMERPATCH.patch_rom(rom)


if __name__ == "__main__":
    unittest.main()
