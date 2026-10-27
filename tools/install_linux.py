"""Install startup and short-lived automatic deployment units on a systemd VPS."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def quote(value: str, *, command: bool = False) -> str:
    """Quote a literal systemd argument, including specifier and dollar escaping."""
    if any(character in value for character in '\n\r\x00'):
        raise ValueError('Invalid systemd value')
    escaped = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if command:
        escaped = escaped.replace('$', '$$')
    return '"' + escaped + '"'


def units(root: Path, python: str, user: str) -> dict[str, str]:
    # WorkingDirectory takes a literal path, unlike ExecStart's argument parser.
    quote(str(root))  # Reject control characters before writing unit files.
    directory = str(root).replace('%', '%%')
    executable = quote(python, command=True)
    return {
        'map-predict-stack.service': f'''[Unit]
Description=MapPredictApp Docker stack
Wants=network-online.target
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User={user}
WorkingDirectory={directory}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart={executable} -B {quote(str(root / 'tools/docker_stack.py'), command=True)} start
TimeoutStartSec=1800

[Install]
WantedBy=multi-user.target
''',
        'map-predict-update.service': f'''[Unit]
Description=Deploy CI-verified MapPredictApp revision
After=network-online.target map-predict-stack.service
Requires=map-predict-stack.service

[Service]
Type=oneshot
User={user}
WorkingDirectory={directory}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart={executable} -B {quote(str(root / 'tools/auto_deploy.py'), command=True)}
TimeoutStartSec=3700
''',
        'map-predict-update.timer': '''[Unit]
Description=Check verified MapPredictApp updates every five minutes

[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
Unit=map-predict-update.service

[Install]
WantedBy=timers.target
''',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', default=os.environ.get('SUDO_USER'),
                        help='Existing user with Docker access and ownership of the checkout')
    options = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() != 0:
        parser.error('Run with sudo on a Linux VPS using systemd')
    import pwd
    if not options.user or not options.user.replace('_', '').replace('-', '').isalnum():
        parser.error('Provide an existing deployment user via --user')
    pwd.getpwnam(options.user)
    if not Path('/run/systemd/system').exists():
        parser.error('This installer requires systemd')
    for executable in ('docker', 'git', 'runuser', 'systemctl'):
        if not shutil.which(executable):
            parser.error(f'Missing prerequisite: {executable}')
    for arguments in (('docker', 'info', '--format', '{{.ServerVersion}}'),
                      ('docker', 'compose', 'version'),
                      ('git', '-C', str(ROOT), 'status', '--porcelain')):
        subprocess.run(['runuser', '-u', options.user, '--', *arguments], check=True,
                       stdout=subprocess.DEVNULL)
    if not (ROOT / '.secrets/cloudflared-token').is_file():
        parser.error('Copy the tunnel token and private project data before installation')
    for name, content in units(ROOT, sys.executable, options.user).items():
        (Path('/etc/systemd/system') / name).write_text(content, encoding='utf-8')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'map-predict-stack.service',
                    'map-predict-update.timer'], check=True)
    print('Stack startup and five-minute automatic deployment timer installed')


if __name__ == '__main__':
    main()
