#!/usr/bin/python
"""Execute selected local IBM installers and verify the resulting product state."""
import fnmatch
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

PRODUCTS = ('installation_manager', 'db2', 'websphere', 'ibm_java', 'content_manager', 'content_navigator', 'iccsap')
ENGINES = {'installation_manager': 'agent', 'db2': 'db2', 'websphere': 'imcl', 'ibm_java': 'imcl', 'content_manager': 'cm', 'content_navigator': 'icn', 'iccsap': 'commands'}


def validate(job):
    if job.get('product') not in PRODUCTS:
        raise ValueError('Unbekanntes Produkt.')
    if not job.get('user') or not isinstance(job.get('files'), list) or not job['files']:
        raise ValueError('Installationsbenutzer und Dateien angeben.')
    if len(job['files']) != len(set(job['files'])):
        raise ValueError('Dateien doppelt ausgewählt.')
    if not job.get('verify') or not isinstance(job['verify'], list):
        raise ValueError('Mindestens eine produktspezifische Zielprüfung angeben.')
    for check in job['verify']:
        if not check.get('match'):
            raise ValueError('Zielprüfung benötigt einen eindeutigen regulären Ausdruck.')
        re.compile(check['match'])
    for field in ('stop_services', 'start_services', 'before', 'after', 'healthchecks'):
        if field not in job or not isinstance(job[field], list):
            raise ValueError(field + ' explizit als Liste angeben, gegebenenfalls leer.')
    for step in job['verify'] + job['before'] + job['after'] + job['healthchecks'] + job.get('commands', []):
        if not isinstance(step.get('argv'), list) or not step['argv'] or not all(isinstance(x, str) and x for x in step['argv']):
            raise ValueError('Befehle als nicht leere argv-Liste angeben.')
        if 'match' in step:
            re.compile(step['match'])
    if 'UNRESOLVED' in json.dumps(job):
        raise ValueError('Platzhalter in der Produktkonfiguration ersetzen.')
    engine = job.get('engine', ENGINES[job['product']])
    if engine not in ('agent', 'db2', 'imcl', 'cm', 'icn', 'commands'):
        raise ValueError('Unbekannter Installer-Typ.')
    if engine in ('agent', 'db2', 'cm', 'icn') and len(job['files']) != 1:
        raise ValueError('Genau ein eindeutiges Installationsmedium für diesen Produktlauf auswählen.')
    if engine == 'commands' and not job.get('commands'):
        raise ValueError('Für dieses Paket die konkreten Readme-Installationsbefehle angeben.')
    if engine in ('cm', 'icn') and not job.get('response_file'):
        raise ValueError('Vorhandene produktspezifische Response-Datei erforderlich.')
    if engine in ('agent', 'db2', 'imcl') and not str(job.get('installation_directory', '')).startswith('/'):
        raise ValueError('Absolutes Installationsverzeichnis erforderlich.')
    if engine == 'db2' and not job.get('instances'):
        raise ValueError('Alle betroffenen Db2-Instanzen angeben.')
    if engine == 'imcl' and not (job.get('offerings') or job.get('fix_ids')):
        raise ValueError('Offering-IDs und/oder exakte IM-Fix-IDs erforderlich.')
    if engine in ('agent', 'db2', 'imcl') and not Path(job['installation_directory']).is_dir():
        raise ValueError('Vorhandene Produktinstallation erforderlich; keine Neuinstallation.')
    if engine == 'db2' and job['user'] != 'root':
        raise ValueError('Dieser Db2-Offline-Ablauf benötigt root.')
    if engine == 'imcl':
        if not job.get('offerings') and not job.get('offering_id'):
            raise ValueError('Bei reinen iFix-Läufen die vorhandene Offering-ID angeben.')
        for fix in job.get('fix_ids', []) + job.get('remove_fix_ids', []):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', fix):
                raise ValueError('Ungültige IM-Fix-ID.')
        if set(job.get('fix_ids', [])) & set(job.get('remove_fix_ids', [])):
            raise ValueError('Denselben Fix nicht entfernen und installieren.')
    return engine


def expand(value, media):
    for name, data in media.items():
        value = value.replace('{media:' + name + '}', data['path']).replace('{archive:' + name + '}', data['archive'])
    first = next(iter(media.values()))
    value = value.replace('{media}', first['path']).replace('{archive}', first['archive'])
    if '{media' in value or '{archive' in value:
        raise ValueError('Unbekannter Medienplatzhalter.')
    return value


def executable(media, pattern):
    root = Path(next(iter(media.values()))['path'])
    matches = [p for p in root.rglob('*') if p.is_file() and not p.is_symlink() and fnmatch.fnmatch(p.name, pattern)]
    if len(matches) != 1 or not os.access(matches[0], os.X_OK):
        raise ValueError('Installer fehlt, ist mehrdeutig oder nicht ausführbar: ' + pattern)
    return str(matches[0])


class Installer:
    def __init__(self, job, media, log_directory):
        self.job, self.media = job, media
        self.logs = Path(log_directory)
        self.logs.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.number, self.changed = 0, False
        self.targets = []

    def run(self, argv, user=None, mutate=False, acceptable=(0,), env=None, cwd=None):
        self.number += 1
        argv = [expand(a, self.media) for a in argv]
        if not os.path.isabs(argv[0]):
            raise ValueError('Befehle benötigen einen absoluten Programmpfad.')
        user = user or self.job['user']
        account = pwd.getpwnam(user)
        if os.geteuid() != account.pw_uid:
            argv = ['/usr/sbin/runuser', '-u', user, '--'] + argv
        environment = dict(os.environ, **self.job.get('environment', {}), **(env or {}))
        if mutate:
            self.changed = True
        log = self.logs / ('%03d.log' % self.number)
        with log.open('w', encoding='utf-8') as output:
            log.chmod(0o600)
            try:
                p = subprocess.run(argv, stdout=output, stderr=subprocess.STDOUT, text=True, timeout=self.job.get('timeout', 3600), env=environment, cwd=expand(cwd or self.job.get('working_directory', '{media}'), self.media), check=False)
            except subprocess.TimeoutExpired:
                raise ValueError('Zeitüberschreitung; Installerzustand prüfen, Sperre bleibt bestehen. Log: ' + str(log))
        text = log.read_text(errors='replace')
        if p.returncode not in acceptable or re.search(r'\bCRIM[A-Z]\d+E\b', text):
            raise ValueError('Befehl fehlgeschlagen (rc=%s). Log: %s' % (p.returncode, log))
        return text

    def checks(self, checks):
        matches = []
        for check in checks:
            text = self.run(check['argv'], check.get('user'))
            matches.append(not check.get('match') or re.search(check['match'], text, re.M) is not None)
        return all(matches)

    def steps(self, steps):
        for step in steps:
            text = self.run(step['argv'], step.get('user'), True, tuple(step.get('success_rc', [0])), step.get('environment'), step.get('cwd'))
            if step.get('match') and not re.search(step['match'], text, re.M):
                raise ValueError('Erwartete Installerausgabe fehlt; Protokolle prüfen.')

    def repositories(self):
        repositories = []
        for data in self.media.values():
            # Each repository remains isolated; no ZIP overlays.
            matches = list(Path(data['path']).rglob('repository.config'))
            if len(matches) != 1:
                raise ValueError('Genau eine repository.config je IM-Medium erforderlich.')
            if not matches[0].is_file() or not matches[0].resolve().is_relative_to(Path(data['path']).resolve()):
                raise ValueError('Repository liegt außerhalb des Mediums.')
            repositories.append(str(matches[0]))
        return ','.join(repositories)

    def build(self, engine):
        j = self.job
        if engine == 'commands':
            return j['commands']
        if engine == 'imcl':
            imcl = j['imcl_path']
            repos = self.repositories()
            common = ['-installationDirectory', j['installation_directory'], '-repositories', repos, '-useServiceRepository', 'false']
            available = self.run([imcl, 'listAvailablePackages', '-repositories', repos, '-useServiceRepository', 'false'])
            installed = self.run([imcl, 'listInstalledPackages', '-installationDirectory', j['installation_directory']])
            ids = [line.strip() for line in available.splitlines() if re.fullmatch(r'com\.ibm\.[A-Za-z0-9_.-]+', line.strip())]
            if j.get('offering_id') and not any(line.strip().startswith(j['offering_id'] + '_') for line in installed.splitlines()):
                raise ValueError('Erwartetes Offering fehlt in der ausgewählten Installation.')
            targets = []
            for offering in j.get('offerings', []):
                if not re.fullmatch(r'com\.ibm\.[A-Za-z0-9.-]+', offering):
                    raise ValueError('Ungültige Offering-ID.')
                if not any(line.strip().startswith(offering + '_') for line in installed.splitlines()):
                    raise ValueError('Offering nicht in der ausgewählten Installation: ' + offering)
                candidates = [x for x in ids if x.startswith(offering + '_')]
                if len(candidates) != 1:
                    raise ValueError('Ziel-Offering im gewählten Paket nicht eindeutig: ' + offering)
                targets += candidates
            steps = []
            self.targets = targets
            # Exact IBM fix IDs, not inferred from archive prefixes or APAR ordering.
            for fix in j.get('remove_fix_ids', []):
                if not j.get('supersedence_source'):
                    raise ValueError('Entfernung nur mit dokumentierter Supersedence-Quelle.')
                if self.has_fix(fix):
                    steps.append({'argv': [imcl, 'uninstall', fix, '-installationDirectory', j['installation_directory'], '-acceptLicense']})
            if targets:
                steps.append({'argv': [imcl, 'install'] + targets + common + ['-installFixes', 'none', '-acceptLicense']})
            for fix in j.get('fix_ids', []):
                if not re.fullmatch(r'[A-Za-z0-9_.-]+', fix):
                    raise ValueError('Ungültige IM-Fix-ID.')
                steps.append({'argv': [imcl, 'install', fix] + common + ['-acceptLicense']})
            return steps
        if engine == 'agent':
            name = j.get('installer', 'installc' if j['user'] == 'root' else 'userinstc')
            binary = executable(self.media, name)
            return [{'argv': [binary, '-acceptLicense', '-installationDirectory', j['installation_directory']], 'cwd': str(Path(binary).parent)}]
        if engine == 'db2':
            binary = executable(self.media, j.get('installer', 'installFixPack'))
            steps = [{'argv': [binary, '-b', j['installation_directory'], '-y'], 'cwd': str(Path(binary).parent)}]
            # Explicit instance maintenance is part of this selected offline procedure.
            steps += [{'argv': [j['installation_directory'] + '/instance/db2iupdt', instance]} for instance in j['instances']]
            return steps
        if not Path(j['response_file']).is_file():
            raise ValueError('Response-Datei fehlt auf dem Ziel.')
        name = j.get('installer', 'installUpdate' if engine == 'cm' else 'IBM_CONTENT_NAVIGATOR*-LINUX.bin')
        args = ['-i', 'silent', '-f', j['response_file']] if engine == 'cm' else ['-f', j['response_file']]
        binary = executable(self.media, name)
        return [{'argv': [binary] + args, 'cwd': str(Path(binary).parent)}]

    def has_fix(self, fix):
        command = [self.job['imcl_path'], 'listInstalledPackages', '-installationDirectory', self.job['installation_directory'], '-verbose']
        fixes, in_fixes = [], False
        for line in self.run(command).splitlines():
            value = line.strip()
            if value.lower() == 'fixes:':
                in_fixes = True
            elif value.startswith('[') or value.endswith(':'):
                in_fixes = False
            elif in_fixes:
                fixes.append(value)
        return re.search(r'(?<![A-Za-z0-9_.-])' + re.escape(fix) + r'(?![A-Za-z0-9_.-])', '\n'.join(fixes)) is not None

    def validate_commands(self, steps):
        # Prüfen, bevor irgendein Dienst gestoppt wird; spätere Installer-Dateien
        # dürfen erst während des Updates entstehen (beispielsweise db2iupdt).
        for step in steps + self.job['before'] + self.job['after'] + self.job['healthchecks']:
            args = [expand(a, self.media) for a in step['argv']]
            if not os.path.isabs(args[0]):
                raise ValueError('Befehle benötigen einen absoluten Programmpfad.')
            pwd.getpwnam(step.get('user', self.job['user']))

    def desired_state(self):
        good = self.checks(self.job['verify'])
        if self.job.get('engine', ENGINES[self.job['product']]) != 'imcl':
            return good
        command = [self.job['imcl_path'], 'listInstalledPackages', '-installationDirectory', self.job['installation_directory']]
        lines = self.run(command).splitlines()
        good = good and all(target in [x.strip() for x in lines] for target in self.targets)
        good = good and all(self.has_fix(fix) for fix in self.job.get('fix_ids', []))
        good = good and not any(self.has_fix(fix) for fix in self.job.get('remove_fix_ids', []))
        return bool(good)

    def execute(self, validate_only=False):
        engine = validate(self.job)
        steps = self.build(engine)
        self.validate_commands(steps)
        if validate_only:
            # Run version commands to detect access failures before any service stops.
            self.checks(self.job['verify'])
            return {'changed': False, 'status': 'validated', 'log_directory': str(self.logs)}
        if self.desired_state():
            if not self.checks(self.job['healthchecks']):
                raise ValueError('Zielversion vorhanden, aber Funktionstest fehlgeschlagen.')
            return {'changed': False, 'status': 'already_installed', 'log_directory': str(self.logs)}
        self.steps(self.job['before'])
        for service in self.job['stop_services']:
            self.run(['/usr/bin/systemctl', 'stop', service], 'root', True)
        self.steps(steps)
        self.steps(self.job['after'])
        if not self.desired_state():
            raise ValueError('Installer beendet, aber Zielstand nicht nachgewiesen. Kein automatischer Dienststart; Zustand prüfen.')
        for service in self.job['start_services']:
            self.run(['/usr/bin/systemctl', 'start', service], 'root', True)
        if not self.checks(self.job['healthchecks']):
            raise ValueError('Funktionstest nach Installation fehlgeschlagen.')
        return {'changed': self.changed, 'status': 'installed', 'log_directory': str(self.logs)}


def main():
    from ansible.module_utils.basic import AnsibleModule
    m = AnsibleModule(argument_spec={'job': {'type': 'dict', 'required': True, 'no_log': True}, 'media': {'type': 'dict', 'required': True}, 'log_directory': {'type': 'path', 'required': True}, 'validate_only': {'type': 'bool', 'default': False}}, supports_check_mode=False)
    runner = None
    try:
        runner = Installer(m.params['job'], m.params['media'], m.params['log_directory'])
        result = runner.execute(m.params['validate_only'])
    except (OSError, KeyError, ValueError, TypeError, re.error) as exc:
        m.fail_json(changed=bool(runner and runner.changed), msg=str(exc))
    m.exit_json(**result)


if __name__ == '__main__':
    main()
