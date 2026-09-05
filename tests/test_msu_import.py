import importlib.util
import os
import pathlib
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / "portable-core" / "bin" / "alttpr-msu-import.py"
SPEC = importlib.util.spec_from_file_location("alttpr_msu_import", SCRIPT)
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


class ArchiveListingTests(unittest.TestCase):
    def test_empty_rar_link_fields_are_not_links(self):
        listing = """Header
----------
Path = music-1.pcm
Size = 12
Attributes = A
Symbolic Link = 
Hard Link = 
"""
        self.assertEqual(IMPORTER.inspect_7zz_listing(listing), 12)

    def test_real_symbolic_link_is_rejected(self):
        listing = """Header
----------
Path = music-1.pcm
Size = 12
Symbolic Link = ../outside
"""
        with self.assertRaisesRegex(RuntimeError, "archive contains a link"):
            IMPORTER.inspect_7zz_listing(listing)

    def test_real_hard_link_is_rejected(self):
        listing = """Header
----------
Path = music-1.pcm
Size = 12
Hard Link = other.pcm
"""
        with self.assertRaisesRegex(RuntimeError, "archive contains a link"):
            IMPORTER.inspect_7zz_listing(listing)

    def test_unsafe_path_is_rejected(self):
        listing = """Header
----------
Path = ../music-1.pcm
Size = 12
"""
        with self.assertRaisesRegex(RuntimeError, "unsafe path"):
            IMPORTER.inspect_7zz_listing(listing)

    def test_known_incompatible_rain_track_is_registered(self):
        self.assertEqual(
            IMPORTER.INCOMPATIBLE_PCM[
                "bac4dd42944041d7cc593be0c25a67b46b065486572dd50a4f1853a419e5e5a8"
            ],
            "captured rain/game-sound placeholder",
        )

    def test_pack_link_cleanup_only_removes_matching_targets(self):
        destination = "/packs/user-movie"
        with mock.patch.object(IMPORTER, "SEEDS_DIR", "/seeds"), \
                mock.patch.object(os, "listdir",
                                  return_value=["movie-1.pcm", "other-1.pcm",
                                                "regular.sfc"]), \
                mock.patch.object(os.path, "islink",
                                  side_effect=lambda p: p.endswith(".pcm")), \
                mock.patch.object(
                    os, "readlink",
                    side_effect=lambda p: (
                        "/packs/user-movie/track.pcm"
                        if "movie" in p else "/packs/user-other/track.pcm"
                    ),
                ), mock.patch.object(os, "unlink") as unlink:
            self.assertEqual(IMPORTER.remove_seed_links(destination), 1)
            self.assertEqual(
                os.path.normpath(unlink.call_args.args[0]),
                os.path.normpath("/seeds/movie-1.pcm"),
            )


if __name__ == "__main__":
    unittest.main()
