import configparser
import importlib
import logging
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class PatchProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Loading patch metadata must not require a monitor/GPU in these tests.
        logger = types.ModuleType("modules.logger")
        logger.log = logger.superlog = logging.getLogger("profile-tests")
        with patch.dict(sys.modules, {"modules.logger": logger}):
            cls.games = importlib.import_module("modules.GameManager.GameManager").Game_Manager
            cls.qt = importlib.import_module("modules.qt_config")

    def setUp(self):
        self.saved = self.games.GamePatches
        self.games.GamePatches = []

    def tearDown(self):
        self.games.GamePatches = self.saved

    def test_versions_have_separate_selection_and_options_but_same_title(self):
        self.games.CreatePatchInfo(ROOT / "src/PatchInfo/Breath Of The Wild")
        base = self.games.GetJsonByID("01007ef00011e000")
        newer = self.games.GetJsonByID("01007ef00011e000@1.9.0-fps")
        self.assertIsNot(base, newer)
        self.assertEqual(base.ID, newer.ID)
        self.assertEqual(base.Versions, ["1.6.0"])
        self.assertEqual(newer.Versions, ["1.9.0"])
        self.assertIsNone(base.ExefsPatch)
        self.assertEqual(newer.ExefsPatch, "FPS-1.9.json")
        self.assertIn("freecam", base.LoadJson()["Keys"])
        self.assertEqual(newer.LoadJson()["NativeFPS"]["fps"]["Values"], [60])
        self.assertFalse(newer.Cheats)
        self.assertFalse(newer.ResolutionScale)
        self.assertFalse(newer.Support_Benchmark)
        self.assertEqual(newer.LoadPresetsJson()["60 FPS (Experimental)"]["fps"], 0)

    def test_repeated_discovery_does_not_duplicate_variants(self):
        folder = ROOT / "src/PatchInfo/Breath Of The Wild"
        first = self.games.CreatePatchInfo(folder)
        self.assertIs(self.games.CreatePatchInfo(folder), first)
        self.assertEqual(len(self.games.GamePatches), 3)

    def test_configurable_profile_exposes_real_native_and_emulator_settings(self):
        self.games.CreatePatchInfo(ROOT / "src/PatchInfo/Breath Of The Wild")
        configurable = self.games.GetJsonByID("01007EF00011E000@1.9.0-native")
        fixed = self.games.GetJsonByID("01007EF00011E000@1.9.0-fps")
        options = configurable.LoadJson()["NativeFPS"]
        self.assertEqual(set(options), {"fps", "fov", "far clip", "emulator scale", "emulator aa", "anisotropy"})
        self.assertEqual(options["fps"]["Values"], [20, 120])
        self.assertEqual(configurable.NativePayload, "NativeFPS-1.9.json")
        self.assertIn(fixed.ModName, configurable.ConflictingMods)
        self.assertIn(configurable.ModName, fixed.ConflictingMods)

    def test_install_can_disable_old_ultracam_and_enable_new_patch(self):
        title = int("01007EF00011E000", 16)
        old, new = "!!!BOTW Optimizer", "!!!BOTW 1.9.0 60 FPS"
        config = configparser.ConfigParser()
        config["DisabledAddOns"] = {
            "1\\title_id": str(title),
            "1\\disabled\\1\\d": new,
            "1\\disabled\\size": "1",
        }
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / old).mkdir()
            (directory / new).mkdir()
            config_file = directory / "qt-config.ini"
            self.qt.add_entry(config_file, directory, config, title, old)
            self.qt.find_and_remove_entry(config_file, directory, config, title, new)
            loaded = configparser.ConfigParser()
            loaded.read(config_file)
            self.assertEqual(self.qt.get_d_values(loaded, "1"), [old])
            self.assertEqual(self.qt.find_title_id_index(loaded, str(title)), "1")


if __name__ == "__main__":
    unittest.main()
