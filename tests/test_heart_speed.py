import ast
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
MENU = ROOT / "portable-core" / "bin" / "alttpr-menu.py"
GENERATOR = ROOT / "portable-core" / "bin" / "alttpr-generate.sh"
HELP = ROOT / "portable-core" / "bin" / "data" / "option-help.json"


class HeartSpeedTests(unittest.TestCase):
    def test_menu_values_and_default(self):
        tree = ast.parse(MENU.read_text(encoding="utf-8"))
        rows = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Tuple)
            and node.elts
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value == "HEARTBEEP"
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        values = [item.value for item in row.elts[2].elts]
        self.assertEqual(values, ["half", "normal", "double", "quarter", "off"])
        self.assertEqual(row.elts[3].value, 0)

    def test_every_value_has_help(self):
        help_data = json.loads(HELP.read_text(encoding="utf-8"))
        self.assertEqual(
            list(help_data["HEARTBEEP"]),
            ["half", "normal", "double", "quarter", "off"],
        )
        self.assertTrue(all(help_data["HEARTBEEP"].values()))

    def test_generator_defaults_and_forwards_value(self):
        script = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("HEARTBEEP=half HEARTCOLOR=red", script)
        self.assertIn('EXTRA="$EXTRA --heartbeep $HEARTBEEP"', script)


if __name__ == "__main__":
    unittest.main()
