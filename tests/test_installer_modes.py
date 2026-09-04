import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
INSTALLER = ROOT / "install.sh"


class InstallerModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = INSTALLER.read_text(encoding="utf-8")

    def test_install_and_format_require_separate_flags(self):
        self.assertIn("CONFIRM=false", self.script)
        self.assertIn("CONFIRM_FORMAT=false", self.script)
        self.assertIn("--confirm-install)", self.script)
        self.assertIn("--confirm-format)", self.script)
        self.assertIn("if $CONFIRM_FORMAT; then", self.script)

    def test_old_explicit_defaults_are_rejected(self):
        self.assertIn("--dry-run was removed", self.script)
        self.assertIn("--skip-format was removed", self.script)

    def test_preserve_mode_requires_ext4(self):
        self.assertIn(
            'if ! $CONFIRM_FORMAT && [ "$sharefs" != "ext4" ]; then',
            self.script,
        )

    def test_all_mutation_follows_install_confirmation(self):
        confirmation_gate = self.script.index("if ! $CONFIRM; then")
        first_remote_mutation = self.script.index(
            'echo "== switching Recalbox to a temporary RAM share =="'
        )
        first_install_mutation = self.script.index(
            'echo "== installing pinned randomizer engine =="'
        )
        self.assertLess(confirmation_gate, first_remote_mutation)
        self.assertLess(confirmation_gate, first_install_mutation)


if __name__ == "__main__":
    unittest.main()
