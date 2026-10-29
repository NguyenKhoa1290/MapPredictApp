"""Portable single-instance Docker Compose startup and local deployment."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROBE = """import json
from urllib.request import urlopen
with urlopen('http://127.0.0.1:8000/api/v1/predictions/model', timeout=10) as r:
    assert json.load(r)['data']['ready']
with urlopen('http://127.0.0.1:8000/portal/', timeout=10) as r:
    assert r.status == 200
import os
if os.environ.get('MAP_PREDICT_ASSISTANT_ENABLED') == '1':
    with urlopen('http://127.0.0.1:8000/api/v1/assistant/status', timeout=10) as r:
        assert json.load(r)['data']['service'] == 'worker'
print('Candidate model and frontend are ready')
"""


def run(*args: str, input: str | None = None, timeout: int = 3600) -> str:
    result = subprocess.run(args, cwd=ROOT, input=input, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stderr[-6000:]}')
    return result.stdout.strip()


def compose(*args: str, **kwargs) -> str:
    return run('docker', 'compose', *args, **kwargs)


@contextmanager
def deployment_lock():
    """Shared by start/deploy and compatible with the former PowerShell lock."""
    (ROOT / '.secrets').mkdir(exist_ok=True)
    with (ROOT / '.secrets/deploy.lock').open('a+b') as handle:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def read_state() -> dict:
    path = ROOT / '.secrets/deployment-state.json'
    if not path.exists():
        return {'mode': 'single'}
    state = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(state, dict):
        raise RuntimeError('Invalid deployment state')
    return state


def write_state(state: dict) -> None:
    path = ROOT / '.secrets/deployment-state.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state), encoding='utf-8')
    temporary.replace(path)


def configuration() -> str:
    upload = '67108864'
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if re.fullmatch(r'MAP_PREDICT_MAX_UPLOAD_BYTES=\d+', line):
            upload = line.split('=', 1)[1]
    return (ROOT / 'deploy/site.template.conf').read_text(encoding='utf-8').replace(
        '__BACKEND__', 'web-portal').replace('__UPLOAD_BYTES__', upload)


def initialize() -> None:
    environment = ROOT / '.env'
    if not environment.exists():
        shutil.copyfile(ROOT / '.env.example', environment)
    (ROOT / 'deploy/local/nginx').mkdir(parents=True, exist_ok=True)
    if not (ROOT / '.secrets/deployment-state.json').exists():
        write_state({'mode': 'single'})
    read_state()
    config = ROOT / 'deploy/local/nginx/active.conf'
    expected = configuration()
    if not config.exists():
        config.write_text(expected, encoding='utf-8')
    key = ROOT / '.secrets/assistant-key'
    if not key.exists():
        descriptor = os.open(str(key), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(secrets.token_hex(32))
    if os.name != 'nt':
        # Compose file-backed secrets preserve host UID, allow container UID 10001
        # to read the mounted file while the private host directory stays closed.
        (ROOT / '.secrets').chmod(0o700)
        key.chmod(0o644)
    admin_password = ROOT / '.secrets/ai-admin-password.hash'
    if not admin_password.exists():
        admin_password.write_text('', encoding='utf-8')
    if os.name != 'nt':
        admin_password.chmod(0o644)


def reload_gateway() -> None:
    compose('exec', '-T', 'web-gateway', 'nginx', '-t')
    compose('exec', '-T', 'web-gateway', 'nginx', '-s', 'reload')


def start(no_build: bool = False) -> None:
    initialize()
    (ROOT / 'deploy/local/nginx/active.conf').write_text(configuration(), encoding='utf-8')
    compose('up', '-d', '--no-build' if no_build else '--build', '--wait', '--wait-timeout', '180')
    reload_gateway()
    print('Started one web, AI, Qdrant, Gemini, gateway and tunnel')


def deploy(pull: bool = False) -> None:
    if pull:
        run('git', 'pull', '--ff-only', 'origin', 'main')
    initialize()
    revision = run('git', 'rev-parse', 'HEAD')
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise RuntimeError('Cannot identify deployed revision')
    # Build before restarting, keep a single container per service.
    compose('build', 'web-portal', 'ai-assistant', 'gemini-session')
    compose('up', '-d', '--no-deps', '--wait', '--wait-timeout', '120', 'qdrant', 'gemini-session', 'ai-embedding')
    compose('up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', 'ai-assistant', 'web-portal')
    compose('exec', '-T', 'web-portal', 'python', '-', input=PROBE)
    (ROOT / 'deploy/local/nginx/active.conf').write_text(configuration(), encoding='utf-8')
    compose('up', '-d', '--no-deps', '--wait', '--wait-timeout', '120', 'web-gateway', 'cloudflare-tunnel')
    reload_gateway()
    write_state({'mode': 'single', 'revision': revision,
                 'updated': datetime.now(timezone.utc).isoformat()})
    print('Deployment complete, one instance per service, no snapshots or standby slots')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('initialize', 'start', 'deploy'))
    parser.add_argument('--pull', action='store_true', help='Fast-forward main before manual deployment')
    parser.add_argument('--no-build', action='store_true', help='Start existing images without rebuilding at boot')
    options = parser.parse_args()
    with deployment_lock():
        if options.action == 'initialize':
            initialize()
        elif options.action == 'start':
            start(options.no_build)
        else:
            deploy(options.pull)


if __name__ == '__main__':
    main()
