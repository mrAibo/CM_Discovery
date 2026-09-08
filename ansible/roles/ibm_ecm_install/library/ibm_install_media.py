#!/usr/bin/python
"""Verify and extract one archive into a new, isolated directory (Python 3.12)."""
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import zipfile


def prepare(archive, destination, sha256):
    source, dest = Path(archive), Path(destination)
    if not source.is_absolute() or not dest.is_absolute() or source.is_symlink():
        raise ValueError('Absolute Pfade ohne Archiv-Symlink erforderlich.')
    if dest.exists() or dest.is_symlink():
        raise ValueError('Entpackziel muss neu sein; keine überlagerten Repositories.')
    temp = Path(tempfile.mkdtemp(prefix='.extract-', dir=dest.parent))
    try:
        with source.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or hashlib.file_digest(stream, 'sha256').hexdigest() != sha256:
                raise ValueError('Archivtyp oder SHA-256 stimmt nicht.')
            stream.seek(0)
            if zipfile.is_zipfile(stream):
                stream.seek(0)
                with zipfile.ZipFile(stream) as z:
                    seen = set()
                    for item in z.infolist():
                        path = Path(item.filename.replace('\\', '/'))
                        mode = item.external_attr >> 16
                        if path.is_absolute() or '..' in path.parts or ':' in item.filename or str(path) in seen:
                            raise ValueError('Unsicherer oder doppelter ZIP-Pfad.')
                        if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR) or item.flag_bits & 1:
                            raise ValueError('ZIP-Links, Spezialdateien oder Verschlüsselung nicht unterstützt.')
                        seen.add(str(path))
                    needed = sum(i.file_size for i in z.infolist())
                    if shutil.disk_usage(temp).free < needed + 104857600:
                        raise ValueError('Nicht genug Platz zum Entpacken.')
                    for item in z.infolist():
                        output = Path(z.extract(item, temp))
                        if not item.is_dir():
                            output.chmod(0o700 if (item.external_attr >> 16) & 0o111 else 0o600)
            else:
                stream.seek(0)
                with tarfile.open(fileobj=stream, mode='r:*') as t:
                    members = t.getmembers()
                    if shutil.disk_usage(temp).free < sum(m.size for m in members) + 104857600:
                        raise ValueError('Nicht genug Platz zum Entpacken.')
                    # Python's data filter validates link destinations during extraction.
                    t.extractall(temp, members=members, filter='data')
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError('Archiv während des Entpackens verändert.')
        os.rename(temp, dest)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return str(dest)


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={'archive': {'type': 'path', 'required': True}, 'destination': {'type': 'path', 'required': True}, 'sha256': {'type': 'str', 'required': True}}, supports_check_mode=False)
    try:
        path = prepare(**module.params)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as exc:
        module.fail_json(changed=False, msg=str(exc))
    module.exit_json(changed=True, path=path)


if __name__ == '__main__':
    main()
