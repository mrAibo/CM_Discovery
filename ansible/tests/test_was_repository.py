import hashlib
import importlib.util
from pathlib import Path
import os
import pwd
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

MODULE = Path(__file__).resolve().parents[1] / 'roles/ibm_was_update/library/ibm_was_repository.py'
spec = importlib.util.spec_from_file_location('was_repository', MODULE)
repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo)
OFFERING = 'com.ibm.websphere.BASE.v90_9.0.5028.20260601_1200'


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'repository.zip'

    def archive(self, names=('repository.config', 'repository.xml')):
        with zipfile.ZipFile(self.path, 'w') as archive:
            for name in names:
                archive.writestr(name, b'fixture')
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_complete_zip_is_inspected_without_extraction(self):
        digest = self.archive()
        result = repo.inspect_archive(str(self.path), digest)
        self.assertEqual(result['sha256'], digest)
        self.assertFalse(result['offering_verified'])
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_hash_mismatch(self):
        self.archive()
        with self.assertRaises(ValueError):
            repo.inspect_archive(str(self.path), '0' * 64)

    def test_plain_file(self):
        self.path.write_bytes(b'not a zip')
        with self.assertRaises(zipfile.BadZipFile):
            repo.inspect_archive(str(self.path), hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_nested_repository_is_not_assumed_complete(self):
        digest = self.archive(('nested/repository.config',))
        with self.assertRaises(ValueError):
            repo.inspect_archive(str(self.path), digest)

    def test_path_traversal(self):
        digest = self.archive(('repository.config', '../outside'))
        with self.assertRaises(ValueError):
            repo.inspect_archive(str(self.path), digest)

    def test_archive_symlink(self):
        digest = self.archive()
        link = self.path.parent / 'link.zip'
        link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            repo.inspect_archive(str(link), digest)

    def test_symlink_entry(self):
        with zipfile.ZipFile(self.path, 'w') as archive:
            archive.writestr('repository.config', b'fixture')
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, '/etc/passwd')
        with self.assertRaises(ValueError):
            repo.inspect_archive(str(self.path), hashlib.sha256(self.path.read_bytes()).hexdigest())

    def probe(self, output, rc=0):
        imcl = self.path.parent / 'imcl'
        imcl.write_text('fixture')
        imcl.chmod(0o700)
        with patch.object(repo.subprocess, 'run', return_value=subprocess.CompletedProcess([], rc, output, '')) as run:
            result = repo.probe_repository(str(self.path), str(imcl), pwd.getpwuid(os.getuid()).pw_name,
                                           OFFERING, '/usr/bin/unshare', '/usr/sbin/runuser')
            args = run.call_args.args[0]
            self.assertEqual(args[:3], ['/usr/bin/unshare', '--net', '--'])
            self.assertIn('listAvailablePackages', args)
            self.assertEqual(args[-2:], ['-repositories', str(self.path)])
            self.assertNotIn('install', args)
            return result

    def test_exact_offering_and_network_isolation(self):
        self.assertEqual(self.probe(OFFERING + '\n'), OFFERING)

    def test_other_offering_is_not_selected(self):
        with self.assertRaises(ValueError):
            self.probe(OFFERING.replace('BASE', 'ND'))

    def test_duplicate_offering(self):
        with self.assertRaises(ValueError):
            self.probe(OFFERING + '\n' + OFFERING)

    def test_failed_namespace_or_im_never_falls_back(self):
        with self.assertRaises(ValueError):
            self.probe(OFFERING, 1)


if __name__ == '__main__':
    unittest.main()
