"""Exercise the real Ansible module transport with disposable fake IBM commands."""
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ANSIBLE = shutil.which('ansible-playbook')
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(ANSIBLE, 'ansible-playbook is required for transport tests')
class AnsibleExecutionTests(unittest.TestCase):
    def run_play(self, directory, tasks):
        play = directory / 'play.json'
        play.write_text(json.dumps([{'hosts': 'localhost', 'gather_facts': False,
                                    'tasks': tasks}]))
        env = dict(os.environ, ANSIBLE_LIBRARY=str(ROOT / 'roles/ibm_was_update/library'))
        return subprocess.run([ANSIBLE, '-i', 'localhost,', '-c', 'local',
                               '-e', json.dumps({'ansible_python_interpreter': sys.executable}),
                               str(play)], text=True, capture_output=True, env=env, timeout=60)

    def test_read_only_module_runs_through_ansible(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            installation = directory / 'was'
            (installation / 'bin').mkdir(parents=True)
            imcl = directory / 'imcl'
            im_text = (f'[Package group]\nInstallation directory: {installation}\n'
                       '[Package]\nName: WAS (com.ibm.websphere.BASE.v90)\n'
                       'Version: 9.0.5.25 (9.0.5025.20250820_1643)\n')
            version_text = 'Installed Product\nName WAS\nVersion 9.0.5.25\nID BASE\n'
            for path, text in ((imcl, im_text), (installation / 'bin/versionInfo.sh', version_text)):
                path.write_text('#!' + sys.executable + '\nprint(' + repr(text) + ')\n')
                path.chmod(0o700)
            result = self.run_play(directory, [
                {'ibm_was_inventory': {
                    'imcl_path': str(imcl), 'installation_directory': str(installation),
                    'package_id': 'com.ibm.websphere.BASE.v90',
                    'expected_internal_version': '9.0.5025.20250820_1643',
                    'expected_display_version': '9.0.5.25'}, 'register': 'probe'},
                {'ansible.builtin.assert': {'that': [
                    'not probe.changed', 'probe.installation.version_info_verified']}}
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_role_reaches_and_rejects_wrong_host_facts(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            artifact = directory / 'package.zip'
            artifact.write_bytes(b'local test archive')
            change = {
                'target_inventory_host': 'localhost',
                'expected_fqdn': 'wrong-target.example.invalid',
                'expected_os_version': '15.6', 'expected_architecture': 'x86_64',
                'installation_directory': '/opt/IBM/WebSphere/AppServer',
                'imcl_path': '/opt/IBM/InstallationManager/eclipse/tools/imcl',
                'installation_owner': 'root', 'package_id': 'com.ibm.websphere.BASE.v90',
                'expected_internal_version': '9.0.5025.20250820_1643',
                'expected_display_version': '9.0.5.25',
                'artifact_path': str(artifact),
                'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
            result = self.run_play(directory, [
                {'ansible.builtin.set_fact': {'ibm_was': change}},
                {'ansible.builtin.include_role': {'name': str(ROOT / 'roles/ibm_was_update')}}
            ])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('FQDN, SLES-Version oder Architektur', result.stdout + result.stderr)
            self.assertNotIn('Eindeutige Installation mit IM', result.stdout)

    def test_example_placeholders_fail_before_host_access(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            result = self.run_play(directory, [
                {'ansible.builtin.include_vars': str(ROOT / 'examples/change-was.yml')},
                {'ansible.builtin.include_role': {'name': str(ROOT / 'roles/ibm_was_update')}}
            ])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Platzhalter', result.stdout + result.stderr)
            self.assertNotIn('Zielsystem erfassen', result.stdout)


if __name__ == '__main__':
    unittest.main()
