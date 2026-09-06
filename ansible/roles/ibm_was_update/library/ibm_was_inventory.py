#!/usr/bin/python
"""Read-only, installation-scoped WAS verification; independent of Patchwatch."""
from __future__ import annotations

import os
import re
import subprocess

DOCUMENTATION = r'''
---
module: ibm_was_inventory
short_description: Verify one WebSphere installation against IM and versionInfo
version_added: "1.0.0"
description:
  - Reads IM and versionInfo without installing or stopping services.
  - Rejects ambiguous identities, failed commands and version disagreement.
options:
  imcl_path:
    description: Absolute path to imcl.
    type: path
    required: true
  installation_directory:
    description: Absolute WebSphere installation root.
    type: path
    required: true
  package_id:
    description: Exact WebSphere offering ID.
    type: str
    required: true
  expected_internal_version:
    description: Expected full Installation Manager version.
    type: str
    required: true
  expected_display_version:
    description: Expected WebSphere display version.
    type: str
    required: true
supports_check_mode: true
'''
EXAMPLES = r'''
- ibm_was_inventory:
    imcl_path: /opt/IBM/InstallationManager/eclipse/tools/imcl
    installation_directory: /opt/IBM/WebSphere/AppServer
    package_id: com.ibm.websphere.BASE.v90
    expected_internal_version: "9.0.5025.20250820_1643"
    expected_display_version: "9.0.5.25"
'''
RETURN = r'''
installation:
  description: Matched root, package and versions.
  returned: success
  type: dict
'''


def parse_im(text):
    """Preserve each package-group/root occurrence; never merge by product ID."""
    packages, current, root, section = [], None, None, None
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if low in ('[package group]', '[paketgruppe]'):
            if current is not None:
                packages.append(current)
            current, root, section = None, None, 'group'
        elif low in ('[package]', '[paket]'):
            if current is not None:
                packages.append(current)
            current = {'installation_directory': root}
            section = 'package'
        elif line.startswith('[') or low in (
            'fixes:', 'rollback versions:', 'rollbackversionen:',
            'features:', 'komponenten:',
        ):
            section = 'other'
        elif ':' in line:
            key, value = (part.strip() for part in line.split(':', 1))
            key = key.lower()
            if section == 'group' and key in ('installation directory', 'installationsverzeichnis'):
                root = value
            elif section == 'package' and key == 'name':
                match = re.search(r'\(([^()]+)\)\s*$', value)
                if match:
                    current['package_id'] = match.group(1)
            elif section == 'package' and key == 'version':
                match = re.fullmatch(r'(\S+)\s+\(([^()]+)\)', value)
                if match:
                    current['display_version'], current['internal_version'] = match.groups()
    if current is not None:
        packages.append(current)
    return packages


def verify(im_text, was_text, root, package_id, internal, display):
    root = os.path.realpath(root)
    matches = [p for p in parse_im(im_text)
               if p.get('installation_directory')
               and os.path.realpath(p['installation_directory']) == root
               and p.get('package_id') == package_id]
    if len(matches) != 1:
        raise ValueError('IM-Zuordnung fehlt oder ist mehrdeutig: Installationspfad und Paket-ID prüfen.')
    selected = matches[0]
    if selected.get('internal_version') != internal or selected.get('display_version') != display:
        raise ValueError('Installierte IM-Version stimmt nicht mit dem erwarteten Ausgangsstand überein.')
    product_id = {'com.ibm.websphere.BASE.v90': 'BASE', 'com.ibm.websphere.ND.v90': 'ND'}[package_id]
    products = []
    for block in re.split(r'\n\s*\n', was_text.replace('\r', '')):
        if 'Installed Product' not in block and 'Installiertes Produkt' not in block:
            continue
        pid = re.search(r'^\s*ID\s+(\S+)\s*$', block, re.M)
        version = re.search(r'^\s*Version\s+(\S+)\s*$', block, re.M)
        if pid and pid.group(1) == product_id and version:
            products.append(version.group(1))
    if products != [display]:
        raise ValueError('versionInfo und IM widersprechen sich oder das WAS-Produkt ist nicht eindeutig.')
    return {**selected, 'installation_directory': root, 'version_info_verified': True}


def read_command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=90, check=False)
    if result.returncode != 0:
        # Do not mistake parseable partial output for success or expose raw IM metadata.
        raise ValueError('Lesebefehl fehlgeschlagen: {} (rc={}).'.format(argv[0], result.returncode))
    return result.stdout


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={
        'imcl_path': {'type': 'path', 'required': True},
        'installation_directory': {'type': 'path', 'required': True},
        'package_id': {'type': 'str', 'required': True, 'choices': [
            'com.ibm.websphere.BASE.v90', 'com.ibm.websphere.ND.v90']},
        'expected_internal_version': {'type': 'str', 'required': True},
        'expected_display_version': {'type': 'str', 'required': True},
    }, supports_check_mode=True)
    p = module.params
    try:
        root = p['installation_directory']
        if not os.path.isabs(root) or not os.path.isdir(root) or os.path.realpath(root) == '/':
            raise ValueError('WebSphere-Installationsverzeichnis fehlt oder ist ungültig.')
        if not os.path.isabs(p['imcl_path']):
            raise ValueError('imcl benötigt einen absoluten Pfad.')
        im_text = read_command([p['imcl_path'], 'listInstalledPackages', '-verbose'])
        was_text = read_command([os.path.join(root, 'bin', 'versionInfo.sh')])
        result = verify(im_text, was_text, root, p['package_id'],
                        p['expected_internal_version'], p['expected_display_version'])
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        module.fail_json(msg=str(exc), changed=False)
    module.exit_json(changed=False, installation=result)


if __name__ == '__main__':
    main()
