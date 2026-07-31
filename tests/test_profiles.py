import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from capcut_sdk.profiles import ProfileStore, config_from_environment


class ProfileStoreTests(unittest.TestCase):
    def test_default_profile_is_created_with_synthetic_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore(Path(directory))
            config = store.sdk_config()
            self.assertTrue(config.device.device_id.startswith("local-device-"))
            self.assertTrue(config.device.iid.startswith("local-install-"))
            self.assertEqual(config.mode, "offline")
            self.assertEqual(store.default_path.stat().st_mode & 0o777, 0o600)

    def test_environment_values_override_profile(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "CAPCUT_DEVICE_ID": "env-device",
                "CAPCUT_IID": "env-install",
                "CAPCUT_REGION": "US",
                "CAPCUT_LANGUAGE": "en-US",
                "CAPCUT_MODE": "live",
            },
            clear=False,
        ):
            config = config_from_environment(ProfileStore(Path(directory)))
            self.assertEqual(config.device.device_id, "env-device")
            self.assertEqual(config.device.iid, "env-install")
            self.assertEqual((config.region, config.language, config.mode), ("US", "en-US", "live"))
