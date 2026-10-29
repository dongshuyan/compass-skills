"""The portable bundle is explicit, self-contained and safe to inherit."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from title_plugin import Installer, InstallError


class PortableInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        binding = patch('title_runtime.GLOBAL_BINDING', Path(temporary.name) / 'unbound-source.json')
        binding.start()
        self.addCleanup(binding.stop)

    def test_portable_bundle_carries_activation_location_on_internal_home(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'CODEX_HOME': temp}):
            manager = Installer(global_mode=True, portable=True)
            record = manager.configure()
            binding = Path(record['source']) / 'plugins/clarity-session-titles/global-installation.json'
            self.assertEqual(json.loads(binding.read_text()),
                             {'version': 1, 'root': str(Path(temp).resolve() / 'agent-clarity')})
            self.assertIn('plugins/clarity-session-titles/global-installation.json', record['files'])
            self.assertTrue(record['portable'])
            # A later normal update must not silently revert to account-local state.
            record = Installer(global_mode=True).configure()
            self.assertTrue(record['portable'])
            self.assertTrue(binding.is_file())

    def test_project_install_cannot_be_made_portable(self):
        with self.assertRaises(InstallError):
            Installer(Path.cwd(), portable=True)


if __name__ == '__main__':
    unittest.main()
