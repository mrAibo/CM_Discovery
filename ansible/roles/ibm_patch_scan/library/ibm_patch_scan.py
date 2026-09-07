#!/usr/bin/python
"""Read-only discovery of downloaded IBM media; names are hints, not applicability."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import sys

DOCUMENTATION = r'''
---
module: ibm_patch_scan
short_description: Inventory previously downloaded IBM archives
version_added: "1.0.0"
description:
  - Scans local archives without extracting, installing or downloading anything.
  - Classifies filenames and computes SHA-256; applicability remains unverified.
options:
  directory:
    description: Absolute existing directory to scan.
    type: path
    required: true
  recursive:
    description: Include subdirectories without following symbolic links.
    type: bool
    default: true
supports_check_mode: true
'''
EXAMPLES = r'''
- ibm_patch_scan:
    directory: /srv/ibm-updates
  register: patches
'''
RETURN = r'''
packages:
  description: Recognized and unknown archives, including hashes and filename hints.
  type: list
  returned: success
rejected:
  description: Symlinks, special files and files changed during hashing.
  type: list
  returned: success
duplicates:
  description: Filenames occurring in multiple directories; selection must be explicit.
  type: dict
  returned: success
'''

PATTERNS = [
    (r'CM(?P<major>\d)(?P<minor>\d)FP(?P<fix_pack>\d+)_lnx\.zip', 'content_manager', 'fix_pack', 'linux'),
    (r'(?P<version>\d+(?:\.\d+){2,3})-IF(?P<interim_fix>\d+)-ICN-Linux\.tar', 'content_navigator', 'interim_fix', 'linux'),
    (r'(?P<version>\d+(?:\.\d+){3})-ICCSAP-Base-JRE-(?P<jre_version>\d+(?:\.\d+){3})-LUX\.zip', 'iccsap', 'jre_update', 'linux_x86_64'),
    (r'4004-ICCSAP-FP4-IF(?P<interim_fix>\d+)-Binaries-LUX\.zip', 'iccsap', 'binary_interim_fix', 'linux_x86_64'),
    (r'(?P<stream>9\.0\.5)-WS-WAS-FP(?P<fix_pack>\d+)\.zip', 'websphere', 'fix_pack', 'readme_required'),
    (r'(?P<filename_baseline>9\.0\.5\.\d+)-WS-WAS-IF(?P<apar>(?:PH|DT)\d+)\.zip', 'websphere', 'interim_fix', 'readme_required'),
    (r'agent\.installer\.linux\.gtk\.x86_64_(?P<internal_version>[\d.]+_\d+)\.zip', 'installation_manager', 'installer_update', 'linux_x86_64'),
    (r'ibm-java-sdk-(?P<java_major>8\.0)-(?P<java_level>\d+\.\d+)-linux-x64-installmgr\.zip', 'ibm_java', 'sdk_update', 'linux_x86_64'),
    (r'special_(?P<special_number>\d+)_v(?P<version>\d+(?:\.\d+){2})_linuxx64_universal_fixpack\.tar\.gz', 'db2', 'published_update', 'linux_x86_64'),
]


def classify(name):
    for pattern, product, kind, platform in PATTERNS:
        match = re.fullmatch(pattern, name, re.I)
        if not match:
            continue
        metadata = match.groupdict()
        for field in ('fix_pack', 'interim_fix'):
            if field in metadata:
                metadata[field] = int(metadata[field])
        if product == 'content_manager':
            metadata['version'] = '{}.{}.00.{:03d}'.format(metadata.pop('major'), metadata.pop('minor'), metadata['fix_pack'] * 100)
        elif product == 'websphere' and kind == 'fix_pack':
            metadata['version'] = '{}.{}'.format(metadata.pop('stream'), metadata['fix_pack'])
        elif product == 'ibm_java':
            metadata['version'] = metadata.pop('java_major') + '.' + metadata.pop('java_level')
        elif product == 'db2':
            metadata['special_build'] = 'special_' + metadata.pop('special_number')
        elif product == 'iccsap' and kind == 'binary_interim_fix':
            metadata['version'] = '4.0.0.4'
        return {'product': product, 'kind': kind, 'platform_hint': platform,
                'filename_metadata': metadata, 'recognition': 'filename_only',
                'applicability': 'not_verified',
                'note': 'Dateiname erkannt; IBM-Metadaten, Voraussetzungen und installierten Stand gesondert prüfen.'}
    return {'product': 'unknown', 'kind': 'unknown', 'recognition': 'unknown',
            'applicability': 'not_verified', 'note': 'Unbekanntes Archiv; keine automatische Auswahl.'}


def signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def scan(directory, recursive=True):
    root = Path(directory)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError('Absolutes vorhandenes Verzeichnis ohne Symlink erforderlich.')
    packages, rejected, names = [], [], {}
    def walk_error(error):
        raise error
    for current, directories, files in os.walk(root, followlinks=False, onerror=walk_error):
        directories.sort()
        for name in directories[:]:
            path = Path(current) / name
            if path.is_symlink():
                rejected.append({'path': str(path), 'reason': 'Symlink-Verzeichnis wird nicht verfolgt.'})
                directories.remove(name)
        if not recursive:
            directories[:] = []
        for name in sorted(files):
            path = Path(current) / name
            if not name.lower().endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.zst', '.tar.xz')):
                continue
            try:
                # O_NOFOLLOW also protects against a replaced final path during open.
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode):
                        raise ValueError('Keine reguläre Datei.')
                    if before.st_size == 0:
                        raise ValueError('Leeres Archiv.')
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if signature(before) != signature(os.fstat(stream.fileno())) or signature(before) != signature(path.lstat()):
                        raise ValueError('Datei wurde während des Scans verändert.')
                record = {'filename': name, 'path': str(path), 'bytes': before.st_size,
                          'sha256': digest, **classify(name)}
                packages.append(record)
                names.setdefault(name, []).append(str(path))
            except (OSError, ValueError) as exc:
                rejected.append({'path': str(path), 'reason': str(exc)})
    return {'directory': str(root), 'packages': packages, 'rejected': rejected,
            'duplicates': {name: paths for name, paths in names.items() if len(paths) > 1},
            'recognized_count': sum(p['recognition'] == 'filename_only' for p in packages),
            'unknown_count': sum(p['recognition'] == 'unknown' for p in packages)}


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={
        'directory': {'type': 'path', 'required': True},
        'recursive': {'type': 'bool', 'default': True},
    }, supports_check_mode=True)
    if sys.version_info[:2] != (3, 12):
        module.fail_json(changed=False, msg="Python 3.12 auf dem Scan-Host erforderlich.")
    try:
        result = scan(module.params['directory'], module.params['recursive'])
    except (OSError, ValueError) as exc:
        module.fail_json(changed=False, msg=str(exc))
    module.exit_json(changed=False, **result)


if __name__ == '__main__':
    main()
