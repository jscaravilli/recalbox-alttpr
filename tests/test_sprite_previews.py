import importlib.util
import json
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

    def test_offline_rebuild_preserves_cached_source_catalog(self):
        entries = [{"name": "Link", "author": "Nintendo",
                    "file": "https://assets/link.zspr",
                    "preview": "https://assets/link.png"}]
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sprite_dir = root / "sprites"
            preview_dir = root / "previews"
            manifest = root / "sprites.json"
            source = root / "sprites.json.src"
            sprite_dir.mkdir()
            preview_dir.mkdir()
            (sprite_dir / "link.zspr").write_bytes(b"sprite")
            (preview_dir / "link.png").write_bytes(b"preview")
            original = json.dumps(entries, indent=2) + "\n"
            source.write_text(original, encoding="utf-8")

            with mock.patch.object(
                    SPRITES.argparse.ArgumentParser, "parse_args",
                    return_value=SPRITES.argparse.Namespace(
                        sprite_dir=str(sprite_dir),
                        manifest=str(manifest),
                        preview_dir=str(preview_dir),
                        list_url=SPRITES.DEF_URL,
                        no_previews=False,
                        refresh_previews=False,
                        offline=True)):
                self.assertEqual(SPRITES.main(), 0)

            self.assertEqual(source.read_text(encoding="utf-8"), original)
            built = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(built[0]["preview"], "link.png")


if __name__ == "__main__":
    unittest.main()
