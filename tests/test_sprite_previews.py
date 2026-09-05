import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "portable-core" / "bin" / "alttpr-sprites.py"
INSTALL_CONTENT = ROOT / "portable-core" / "install-content.sh"
SPEC = importlib.util.spec_from_file_location("alttpr_sprites", SCRIPT)
SPRITES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SPRITES)


class SpritePreviewTests(unittest.TestCase):
    def test_content_installer_uses_bundled_previews_by_default(self):
        script = INSTALL_CONTENT.read_text(encoding="utf-8")
        self.assertIn('alttpr-sprites.py" --offline', script)
        self.assertIn('if [ "$MODE" = "refresh-sprites" ]', script)

    def test_default_download_skips_cached_preview(self):
        entries = [{"file": "https://assets/sprite.zspr",
                    "preview": "https://assets/sprite.png"}]
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "sprite.png").write_bytes(b"cached")
            with mock.patch.object(SPRITES, "_download_set",
                                   return_value=(0, [])) as download:
                got, failed, missing = SPRITES.download_previews(
                    entries, directory)
            self.assertEqual((got, failed, missing), (0, [], 0))
            download.assert_called_once_with([], workers=16, minbytes=40)

    def test_refresh_downloads_cached_preview_from_official_url(self):
        entries = [{"file": "https://assets/sprite.zspr",
                    "preview": "https://assets/sprite.png"}]
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "sprite.png")
            pathlib.Path(destination).write_bytes(b"cached")
            with mock.patch.object(SPRITES, "_download_set",
                                   return_value=(1, [])) as download:
                got, failed, missing = SPRITES.download_previews(
                    entries, directory, refresh=True)
            self.assertEqual((got, failed, missing), (1, [], 1))
            download.assert_called_once_with(
                [("https://assets/sprite.png", destination)],
                workers=16, minbytes=40)


if __name__ == "__main__":
    unittest.main()
