"""Real local installer execution using synthetic media; no IBM host or package required."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'roles/ibm_ecm_install/library' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

media_module = load('ibm_install_media')
product = load('ibm_install_product')

class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.state.write_text('old')
        self.media = {'CM87FP5_lnx.zip': {'path': str(self.root), 'archive': str(self.root / 'archive')}}
        self.job = dict(product='content_manager', engine='commands', user=pwd.getpwuid(os.getuid()).pw_name,
                        files=['CM87FP5_lnx.zip'], stop_services=[], start_services=[], before=[], after=[], healthchecks=[],
                        commands=[{'argv': [sys.executable, '-c', f'from pathlib import Path; Path({str(self.state)!r}).write_text("FP5")']}],
                        verify=[{'argv': [sys.executable, '-c', f'from pathlib import Path; print(Path({str(self.state)!r}).read_text())'], 'match': '^FP5$'}])

    def runner(self):
        return product.Installer(self.job, self.media, self.root / 'logs')

    def test_executes_and_second_run_skips(self):
        self.assertEqual(self.runner().execute()['status'], 'installed')
        self.assertEqual(self.state.read_text(), 'FP5')
        self.job['commands'] = [{'argv': [sys.executable, '-c', 'raise RuntimeError("must not execute")']}]
        result = self.runner().execute()
        self.assertEqual(result['status'], 'already_installed')
        self.assertFalse(result['changed'])

    def test_preparation_does_not_install(self):
        self.assertEqual(self.runner().execute(True)['status'], 'validated')
        self.assertEqual(self.state.read_text(), 'old')

    def test_failure_does_not_start_services_or_run_after(self):
        self.job['commands'] = [{'argv': [sys.executable, '-c', 'raise SystemExit(23)']}]
        self.job['after'] = self.job['verify']
        self.job['stop_services'] = ['test.service']
        self.job['start_services'] = ['test.service']
        runner = self.runner()
        original = runner.run
        services = []
        def run(argv, *args, **kw):
            if argv[0] == '/usr/bin/systemctl':
                services.append(argv[1]); return ''
            return original(argv, *args, **kw)
        runner.run = run
        with self.assertRaisesRegex(ValueError, 'rc=23'):
            runner.execute()
        self.assertEqual(services, ['stop'])
        self.assertTrue(runner.changed)

    def test_wrong_postcondition_is_failure(self):
        self.job['commands'] = [{'argv': [sys.executable, '-c', 'print("success without update")']}]
        with self.assertRaisesRegex(ValueError, 'Zielstand nicht nachgewiesen'):
            self.runner().execute()

    def test_relative_command_rejected_before_hooks(self):
        self.job['commands'][0]['argv'][0] = 'installer'
        with self.assertRaisesRegex(ValueError, 'absoluten'):
            self.runner().execute(True)

    def test_imcl_installs_all_requested_fixes_and_correct_offerings(self):
        repo = self.root / 'repository.config'; repo.write_text('synthetic')
        self.job.update(product='websphere', engine='imcl', installation_directory=str(self.root), imcl_path='/fake/imcl',
                        offerings=['com.ibm.websphere.BASE.v90', 'com.ibm.java.jdk.v8'], fix_ids=['FIX_A', 'FIX_B'])
        runner = self.runner()
        calls = []
        def fake(argv, *args, **kw):
            calls.append(argv)
            if argv[1] == 'listAvailablePackages':
                return 'com.ibm.websphere.BASE.v90_9.0.5028.TEST\ncom.ibm.java.jdk.v8_8.0.8071.TEST\n'
            if argv[1] == 'listInstalledPackages':
                return 'com.ibm.websphere.BASE.v90_9.0.5025.OLD\ncom.ibm.java.jdk.v8_8.0.8070.OLD\n'
            return ''
        runner.run = fake
        steps = runner.build('imcl')
        self.assertIn('com.ibm.java.jdk.v8_8.0.8071.TEST', steps[0]['argv'])
        self.assertEqual(steps[0]['argv'][-3:], ['-installFixes', 'none', '-acceptLicense'])
        self.assertEqual([s['argv'][2] for s in steps[1:]], ['FIX_A', 'FIX_B'])
        self.assertIn('-useServiceRepository', steps[0]['argv'])
        self.job['offerings'] = ['com.ibm.java.sdk.v8']
        with self.assertRaisesRegex(ValueError, 'Offering nicht'):
            runner.build('imcl')

    def test_rollback_history_is_not_installed_fix(self):
        self.job.update(imcl_path='/fake/imcl', installation_directory=str(self.root))
        runner = self.runner()
        runner.run = lambda *a, **kw: '[Package]\nFixes:\n FIX_A\nRollback versions:\n FIX_B\n'
        self.assertTrue(runner.has_fix('FIX_A'))
        self.assertFalse(runner.has_fix('FIX_B'))
        self.assertFalse(runner.has_fix('FIX'))

    def test_im_error_with_zero_rc_is_failure(self):
        with self.assertRaisesRegex(ValueError, 'fehlgeschlagen'):
            self.runner().run([sys.executable, '-c', 'print("CRIMA1159E")'])

    def test_db2_build_updates_every_configured_instance(self):
        binary = self.root / 'installFixPack'; binary.write_text('#!/bin/sh\nexit 0\n'); binary.chmod(0o700)
        self.job.update(product='db2', engine='db2', installation_directory=str(self.root), instances=['db2a', 'db2b'])
        steps = self.runner().build('db2')
        self.assertEqual(steps[0]['argv'], [str(binary), '-b', str(self.root), '-y'])
        self.assertEqual([x['argv'] for x in steps[1:]], [[str(self.root / 'instance/db2iupdt'), x] for x in ['db2a', 'db2b']])

    def test_documented_supersedence_removes_active_fix_before_base(self):
        (self.root / 'repository.config').write_text('synthetic')
        self.job.update(product='websphere', engine='imcl', installation_directory=str(self.root), imcl_path='/fake/imcl',
                        offerings=['com.ibm.websphere.BASE.v90'], fix_ids=['NEW'], remove_fix_ids=['OLD'])
        runner = self.runner()
        runner.run = lambda *a, **kw: 'com.ibm.websphere.BASE.v90_9.0.5028.TEST\n'
        runner.has_fix = lambda fix: True
        with self.assertRaisesRegex(ValueError, 'Supersedence'):
            runner.build('imcl')
        self.job['supersedence_source'] = 'IBM package Readme supplied by operator'
        steps = runner.build('imcl')
        self.assertEqual(steps[0]['argv'][1:3], ['uninstall', 'OLD'])
        self.assertEqual(steps[-1]['argv'][1:3], ['install', 'NEW'])

    def test_archive_hash_and_executable_permissions(self):
        archive = self.root / 'archive'
        with zipfile.ZipFile(archive, 'w') as z:
            entry = zipfile.ZipInfo('bin/installUpdate'); entry.external_attr = 0o100755 << 16
            z.writestr(entry, '#!/bin/sh\nexit 0\n')
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        dest = self.root / 'payload'
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            media_module.prepare(str(archive), str(dest), '0' * 64)
        self.assertFalse(dest.exists())
        media_module.prepare(str(archive), str(dest), digest)
        self.assertTrue(os.access(dest / 'bin/installUpdate', os.X_OK))
        with self.assertRaisesRegex(ValueError, 'neu sein'):
            media_module.prepare(str(archive), str(dest), digest)

    def test_archive_traversal_and_escaping_tar_symlink(self):
        for kind in ['zip', 'tar']:
            archive = self.root / ('evil.' + kind)
            if kind == 'zip':
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('../escape', 'bad')
            else:
                with tarfile.open(archive, 'w:gz') as t:
                    entry = tarfile.TarInfo('escape'); entry.type = tarfile.SYMTYPE; entry.linkname = '../outside'
                    t.addfile(entry)
            with self.assertRaises((ValueError, tarfile.TarError)):
                media_module.prepare(str(archive), str(self.root / 'payload'), hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertFalse((self.root / 'payload').exists())

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible required')
    def test_complete_role_installation_and_lock_on_failure(self):
        downloads = self.root / 'downloads'; downloads.mkdir()
        response = self.root / 'install.rsp'; response.write_text('ok')
        self.job.update(engine='cm', response_src=str(response))
        with zipfile.ZipFile(downloads / self.job['files'][0], 'w') as z:
            entry = zipfile.ZipInfo('nested/installUpdate'); entry.external_attr = 0o100755 << 16
            z.writestr(entry, '#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\n'
                       + 'assert sys.argv[1:4] == ["-i", "silent", "-f"]\n'
                       + 'assert Path.cwd().name == "nested"\n'
                       + 'if Path(sys.argv[4]).read_text() == "fail": raise SystemExit(29)\n'
                       + f'Path({str(self.state)!r}).write_text("FP5")\n')
        variables = dict(ansible_python_interpreter=sys.executable, ibm_install_target='localhost',
                         ibm_install_expected_fqdn=socket.getfqdn(), ibm_patch_directory=str(downloads),
                         ibm_install_stage_directory=str(self.root / 'stage'), ibm_install_lock_directory=str(self.root / 'lock'),
                         ibm_install_jobs=[self.job])
        self.job.pop('files')  # The role assigns files from its directory scan.
        play = self.root / 'play.json'
        play.write_text(json.dumps([{'hosts': 'localhost', 'gather_facts': False,
                                    'tasks': [{'ansible.builtin.include_role': {'name': 'ibm_ecm_install'}}]}]))
        args = [shutil.which('ansible-playbook'), '-i', 'localhost,', '-c', 'local', str(play)]
        # CI runners provide passwordless sudo; local root requires no escalation.
        def execute():
            return subprocess.run(args + ['-e', json.dumps(variables)], cwd=ROOT,
                                  capture_output=True, text=True, timeout=100)
        result = execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state.read_text(), 'FP5')
        self.assertFalse((self.root / 'lock').exists())
        repeated = execute()
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertIn('already_installed', repeated.stdout)
        if os.geteuid() == 0:
            self.assertEqual(len(list((self.root / 'stage').glob('*/result.json'))), 2)
        self.state.write_text('old')
        response.write_text('fail')
        result = execute()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.root / 'lock').exists())
        self.assertEqual(self.state.read_text(), 'old')
        response.write_text('ok')
        locked = execute()
        self.assertNotEqual(locked.returncode, 0)
        self.assertEqual(self.state.read_text(), 'old')
        # Remove root-owned private logs for non-root CI TemporaryDirectory cleanup.
        if os.geteuid() != 0:
            subprocess.run(['sudo', 'rm', '-rf', str(self.root / 'stage'), str(self.root / 'lock')], check=True)

if __name__ == '__main__':
    unittest.main()
