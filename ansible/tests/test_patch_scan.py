import hashlib
import importlib.util
import json
import os
import io
import tarfile
import zipfile
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patch_scan', ROOT / 'roles/ibm_patch_scan/library/ibm_patch_scan.py')
scan_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_module)
FILENAMES = (Path(__file__).parent / 'fixtures/download-filenames.txt').read_text().splitlines()


class PatchScanTests(unittest.TestCase):
    def test_all_operator_packages(self):
        self.assertEqual(len(FILENAMES), 17)
        with tempfile.TemporaryDirectory() as directory:
            for name in FILENAMES:
                (Path(directory) / name).write_bytes(b'synthetic test payload')
            result = scan_module.scan(directory)
        self.assertEqual(result['recognized_count'], 17)
        self.assertEqual(result['unknown_count'], 0)
        self.assertEqual(result['rejected'], [])
        for package in result['packages']:
            self.assertEqual(package['sha256'], hashlib.sha256(b'synthetic test payload').hexdigest())
            self.assertEqual(package['applicability'], 'not_verified')
        cm = scan_module.classify('CM87FP5_lnx.zip')
        self.assertEqual(cm['filename_metadata']['version'], '8.7.00.500')
        was = scan_module.classify('9.0.5.20-WS-WAS-IFPH72166.zip')
        self.assertEqual(was['filename_metadata'], {'filename_baseline': '9.0.5.20', 'apar': 'PH72166'})
        self.assertEqual(scan_module.classify('4004-ICCSAP-FP4-IF21-Binaries-LUX.zip')['filename_metadata']['interim_fix'], 21)

    def test_duplicates_unknown_empty_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'nested').mkdir()
            (root / 'CM87FP5_lnx.zip').write_bytes(b'one')
            (root / 'nested/CM87FP5_lnx.zip').write_bytes(b'two')
            (root / 'unknown.zip').write_bytes(b'unknown')
            (root / 'empty.zip').touch()
            (root / 'link.zip').symlink_to(root / 'CM87FP5_lnx.zip')
            (root / 'loop').symlink_to(root, target_is_directory=True)
            result = scan_module.scan(directory)
            self.assertEqual(result['recognized_count'], 2)
            self.assertEqual(result['unknown_count'], 1)
            self.assertEqual(len(result['duplicates']['CM87FP5_lnx.zip']), 2)
            self.assertEqual(len(result['rejected']), 3)
            self.assertEqual(scan_module.scan(directory, recursive=False)['recognized_count'], 1)
            with self.assertRaises(ValueError):
                scan_module.scan(str(root / 'loop'))

    def test_explicit_selection_keeps_every_non_cumulative_fix(self):
        names = [n for n in FILENAMES if '-WS-WAS-IF' in n]
        with tempfile.TemporaryDirectory() as directory:
            for name in names:
                (Path(directory) / name).write_bytes(b'fixture')
            result = scan_module.scan(directory)
            selected = scan_module.select_packages(result, names)
            self.assertEqual([p['filename'] for p in selected], names)
            self.assertEqual(len(selected), 9)
            self.assertTrue(all(p['cumulative'] is False for p in selected))
            with self.assertRaises(ValueError):
                scan_module.select_packages(result, names + ['missing.zip'])
            with self.assertRaises(ValueError):
                scan_module.select_packages(result, [names[0], names[0]])
            (Path(directory) / 'other').mkdir()
            (Path(directory) / 'other' / names[0]).write_bytes(b'other')
            with self.assertRaises(ValueError):
                scan_module.select_packages(scan_module.scan(directory), names)

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible not installed')
    def test_real_controller_scan_and_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'CM87FP5_lnx.zip').write_bytes(b'fixture, not an IBM archive')
            args = {'ibm_patch_directory': directory, 'ibm_patch_report_directory': str(root / 'reports'), 'ibm_patch_required_filenames': ['CM87FP5_lnx.zip']}
            command = ['ansible-playbook', '-i', 'inventories/example/hosts.yml', 'playbooks/scan_patches.yml', '--limit', 'HB_TEST', '-e', json.dumps(args)]
            result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((root / 'reports/HB_TEST-patches.json').read_text())
            self.assertEqual(report['recognized_count'], 1)
            self.assertFalse(report['changed'])
            self.assertEqual(report['selected_packages'][0]['filename'], 'CM87FP5_lnx.zip')
            listing = subprocess.run(['ansible-inventory', '-i', 'inventories/example/hosts.yml', '--list'], cwd=ROOT, text=True, capture_output=True, check=True)
            inventory = json.loads(listing.stdout)
            self.assertEqual(set(inventory['_meta']['hostvars']), {'HB_TEST', 'HB_PROD', 'NDD_TEST', 'NDD_PROD'})
            self.assertEqual(set(inventory['production']['hosts']), {'HB_PROD', 'NDD_PROD'})

    @unittest.skipUnless(shutil.which('ansible-playbook') and os.environ.get('TEST_YACOMPRESS') == '1', 'optional collection test')
    def test_yacompress_good_and_bad_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with zipfile.ZipFile(root / 'CM87FP5_lnx.zip', 'w') as archive:
                archive.writestr('test.txt', b'fixture')
            for name, mode in [('3.1.0-IF012-ICN-Linux.tar', 'w'), ('special_87984_v11.5.9_linuxx64_universal_fixpack.tar.gz', 'w:gz')]:
                with tarfile.open(root / name, mode) as archive:
                    info = tarfile.TarInfo('test.txt')
                    info.size = 7
                    archive.addfile(info, io.BytesIO(b'fixture'))
            args = {'ibm_patch_directory': directory, 'ibm_patch_verify_with_yacompress': True}
            command = ['ansible-playbook', '-i', 'inventories/example/hosts.yml', 'playbooks/scan_patches.yml', '--limit', 'NDD_TEST', '-e', json.dumps(args)]
            good = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            self.assertIn('changed=0', good.stdout)
            (root / 'CM87FP5_lnx.zip').write_bytes(b'corrupt ZIP')
            bad = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('Archivstruktur mit YaCompress', bad.stdout)


if __name__ == '__main__':
    unittest.main()
