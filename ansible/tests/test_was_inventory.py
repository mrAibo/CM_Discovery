import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'roles/ibm_was_update/library/ibm_was_inventory.py'
spec = importlib.util.spec_from_file_location('was_inventory', MODULE)
was = importlib.util.module_from_spec(spec)
spec.loader.exec_module(was)

PID = 'com.ibm.websphere.BASE.v90'
VERSION = '9.0.5.25'
INTERNAL = '9.0.5025.20250820_1643'
ROOT = '/opt/IBM/WebSphere/AppServer'
WAS = f'Installed Product\nName IBM WebSphere Application Server\nVersion {VERSION}\nID BASE\n'


def package(root=ROOT, version=VERSION, internal=INTERNAL, german=False):
    group = 'Paketgruppe' if german else 'Package group'
    directory = 'Installationsverzeichnis' if german else 'Installation directory'
    label = 'Paket' if german else 'Package'
    return (f'[{group}]\n{directory}: {root}\n[{label}]\n'
            f'Name: IBM WebSphere Application Server ({PID})\n'
            f'Version: {version} ({internal})\nFixes:\nNone\nRollback versions:\n'
            '9.0.5.22 (9.0.5022.20241118_0055)\n')


class WasIdentityTests(unittest.TestCase):
    def verify(self, im_text, was_text=WAS):
        return was.verify(im_text, was_text, ROOT, PID, INTERNAL, VERSION)

    def test_two_installations_are_selected_by_root(self):
        result = self.verify(package() + package('/opt/IBM/Other', '9.0.5.22', 'older'))
        self.assertEqual(result['internal_version'], INTERNAL)
        self.assertEqual(result['installation_directory'], ROOT)

    def test_duplicate_root_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(package() + package())

    def test_wrong_root_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(package('/opt/IBM/Other'))

    def test_missing_group_path_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(package().replace(f'Installation directory: {ROOT}\n', ''))

    def test_internal_build_drift_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(package(internal='unexpected'))

    def test_binary_version_disagreement_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(package(), WAS.replace(VERSION, '9.0.5.22'))

    def test_wrong_edition_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(package(), WAS.replace('ID BASE', 'ID ND'))

    def test_unparseable_output_is_rejected(self):
        with self.assertRaises(ValueError):
            self.verify('installation succeeded')

    def test_german_output(self):
        result = self.verify(package(german=True), WAS.replace('Installed Product', 'Installiertes Produkt'))
        self.assertTrue(result['version_info_verified'])

    def test_rollback_version_does_not_replace_installed_version(self):
        self.assertEqual(self.verify(package())['display_version'], VERSION)

    def test_failed_command_with_parseable_output_is_rejected(self):
        with patch.object(was.subprocess, 'run', return_value=subprocess.CompletedProcess(['imcl'], 1, package(), 'error')):
            with self.assertRaises(ValueError):
                was.read_command(['/fake/imcl'])

    def test_timeout_is_not_success(self):
        with patch.object(was.subprocess, 'run', side_effect=subprocess.TimeoutExpired('imcl', 90)):
            with self.assertRaises(subprocess.TimeoutExpired):
                was.read_command(['/fake/imcl'])


if __name__ == '__main__':
    unittest.main()
