#!/usr/bin/python
"""Inspect a local IM ZIP and optionally probe it in an isolated network namespace."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import zipfile

DOCUMENTATION = r'''
---
module: ibm_was_repository
short_description: Inspect a local repository ZIP and confirm an exact WAS offering
version_added: "1.1.0"
description:
  - Never installs software or extracts the archive.
  - Probe uses Linux network isolation and runs IM as its installation owner.
options:
  archive:
    description: Absolute path to one complete local IM repository ZIP.
    type: path
    required: true
  sha256:
    description: Expected SHA-256 of the archive.
    type: str
    required: true
  probe:
    description: Run a read-only IM repository query with network isolation.
    type: bool
    default: false
  imcl_path:
    description: Absolute IM executable path for probe.
    type: path
  installation_owner:
    description: Existing installation owner used for the IM query.
    type: str
  target_offering:
    description: Exact package ID plus internal version, separated by underscore.
    type: str
supports_check_mode: true
'''
EXAMPLES = r'''
- ibm_was_repository:
    archive: /srv/ibm-stage/repository.zip
    sha256: "{{ ibm_was.artifact_sha256 }}"
'''
RETURN = r'''
repository:
  description: Archive identity and optional exact offering confirmation.
  returned: success
  type: dict
'''


def inspect_archive(archive, expected):
    path = Path(archive)
    if not path.is_absolute() or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
        raise ValueError('Absoluter Archivpfad und SHA-256 mit 64 Hex-Zeichen erforderlich.')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Das Archiv muss eine reguläre Datei sein; Symlinks sind nicht erlaubt.')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected.lower():
            raise ValueError('SHA-256 des Repository-Archivs stimmt nicht.')
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive_file:
            names = archive_file.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Doppelte Einträge im ZIP-Archiv.')
            # IM can open a complete repository ZIP directly; nested/split layouts
            # deliberately need separate package-specific handling.
            if 'repository.config' not in names:
                raise ValueError('Kein vollständiges Repository-ZIP: repository.config fehlt im ZIP-Wurzelverzeichnis.')
            for entry in archive_file.infolist():
                parts = entry.filename.replace('\\', '/').split('/')
                if entry.filename.startswith(('/', '\\')) or '..' in parts or ':' in parts[0]:
                    raise ValueError('Unsicherer Pfad im ZIP-Archiv.')
                mode = entry.external_attr >> 16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                    raise ValueError('Links oder Spezialdateien im ZIP-Archiv werden nicht unterstützt.')
                if entry.flag_bits & 1:
                    raise ValueError('Verschlüsselte ZIP-Einträge werden nicht unterstützt.')
            return {'archive': str(path), 'sha256': digest, 'bytes': os.fstat(stream.fileno()).st_size,
                    'entries': len(names), 'offering_verified': False}


def probe_repository(archive, imcl, owner, offering, unshare, runuser):
    if not re.fullmatch(r'com\.ibm\.websphere\.(?:BASE|ND)\.v90_9\.0\.\d+\.\d{8}_\d{4}', offering):
        raise ValueError('Exakte WAS-9-Offering-ID mit interner Version erforderlich.')
    if not os.path.isabs(imcl) or not os.access(imcl, os.X_OK):
        raise ValueError('imcl fehlt oder ist nicht ausführbar.')
    pwd.getpwnam(owner)
    # No fallback without isolation: even repository metadata cannot cause
    # an external request. IM may write its normal local cache/logs.
    argv = [unshare, '--net', '--', runuser, '-u', owner, '--', imcl,
            'listAvailablePackages', '-repositories', archive]
    result = subprocess.run(argv, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode != 0:
        raise ValueError('Isolierte IM-Abfrage fehlgeschlagen (rc={}); Netzwerk-Namespace, Rechte, IM und Repository prüfen.'.format(result.returncode))
    offerings = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if offerings.count(offering) != 1:
        raise ValueError('Ziel-Offering fehlt oder ist im lokalen Repository nicht eindeutig.')
    return offering


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={
        'archive': {'type': 'path', 'required': True},
        'sha256': {'type': 'str', 'required': True},
        'probe': {'type': 'bool', 'default': False},
        'imcl_path': {'type': 'path'},
        'installation_owner': {'type': 'str'},
        'target_offering': {'type': 'str'},
    }, required_if=[('probe', True, ['imcl_path', 'installation_owner', 'target_offering'])],
       supports_check_mode=True)
    p = module.params
    try:
        result = inspect_archive(p['archive'], p['sha256'])
        if p['probe']:
            if os.geteuid() != 0:
                raise ValueError('Für den isolierten Repository-Test sind root-Rechte erforderlich.')
            result['target_offering'] = probe_repository(
                p['archive'], p['imcl_path'], p['installation_owner'], p['target_offering'],
                module.get_bin_path('unshare', required=True), module.get_bin_path('runuser', required=True))
            result['offering_verified'] = True
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        module.fail_json(changed=False, msg=str(exc))
    module.exit_json(changed=False, repository=result)


if __name__ == '__main__':
    main()
