"""Portable Docker Compose startup and graceful blue/green deployment."""
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
import time

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
    state = json.loads((ROOT / '.secrets/deployment-state.json').read_text(encoding='utf-8-sig'))
    if state.get('active') not in ('blue', 'green'):
        raise RuntimeError('Invalid active deployment slot')
    return state


def write_state(state: dict) -> None:
    path = ROOT / '.secrets/deployment-state.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state), encoding='utf-8')
    temporary.replace(path)


def configuration(slot: str) -> str:
    upload = '67108864'
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if re.fullmatch(r'MAP_PREDICT_MAX_UPLOAD_BYTES=\d+', line):
            upload = line.split('=', 1)[1]
    return (ROOT / 'deploy/site.template.conf').read_text(encoding='utf-8').replace(
        '__BACKEND__', f'app-{slot}').replace('__UPLOAD_BYTES__', upload)


def initialize() -> None:
    environment = ROOT / '.env'
    if not environment.exists():
        shutil.copyfile(ROOT / '.env.example', environment)
    (ROOT / 'deploy/local/nginx').mkdir(parents=True, exist_ok=True)
    if not (ROOT / '.secrets/deployment-state.json').exists():
        write_state({'active': 'blue'})
    state = read_state()
    config = ROOT / 'deploy/local/nginx/active.conf'
    if not config.exists():
        config.write_text(configuration(state['active']), encoding='utf-8')
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


def setting(name, default=''):
    settings = (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines()
    value = default
    for line in settings:
        if line.startswith(name + '='):
            value = line.split('=', 1)[1].strip().strip('\"\'')
    return os.environ.get(name, value)


def assistant_enabled():
    return setting('MAP_PREDICT_ASSISTANT_ENABLED', '1') == '1'


def start_assistant() -> None:
    if assistant_enabled():
        compose('up', '-d', '--build', '--no-deps', '--wait', '--wait-timeout', '90', 'gemini')
        container = setting('AI_QDRANT_CONTAINER')
        if container:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', container):
                raise RuntimeError('Invalid configured Qdrant container name')
            run('docker', 'start', container)
            networks = json.loads(run('docker', 'inspect', container, '--format', '{{json .NetworkSettings.Networks}}'))
            if 'map-predict_default' not in networks:
                run('docker', 'network', 'connect', '--alias', 'knowledge-qdrant', 'map-predict_default', container)


def wait_for_drain() -> None:
    deadline = time.monotonic() + 190
    while True:
        processes = compose('exec', '-T', 'app', 'ps', '-o', 'args')
        if not any(line.strip().startswith('nginx: worker process is shutting down')
                   for line in processes.splitlines()):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Requests are still draining, previous slot was preserved')
        time.sleep(3)


def start() -> None:
    initialize()
    start_assistant()
    slot = f"app-{read_state()['active']}"
    if assistant_enabled():
        ai = f"ai-{read_state()['active']}"
        compose('up', '-d', '--build', '--no-deps', '--wait', '--wait-timeout', '180', ai)
    compose('up', '-d', '--no-deps', '--wait', '--wait-timeout', '180', slot)
    compose('up', '-d', '--no-deps', '--wait', '--wait-timeout', '120', 'app', 'cloudflared')
    print(f'Started {slot}, gateway and tunnel only')


def deploy(pull: bool = False) -> None:
    if pull:
        run('git', 'pull', '--ff-only', 'origin', 'main')
    initialize()
    start_assistant()
    state = read_state()
    revision = run('git', 'rev-parse', 'HEAD')
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise RuntimeError('Cannot identify deployed revision')
    next_slot = 'green' if state['active'] == 'blue' else 'blue'
    candidate, previous = f'app-{next_slot}', f"app-{state['active']}"
    wait_for_drain()
    if assistant_enabled():
        compose('build', f'ai-{next_slot}', candidate)
        compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '180', f'ai-{next_slot}')
    else:
        compose('build', candidate)
    compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '180', candidate)
    compose('exec', '-T', candidate, 'python', '-', input=PROBE)
    path = ROOT / 'deploy/local/nginx/active.conf'
    old_config = path.read_text(encoding='utf-8')
    try:
        path.write_text(configuration(next_slot), encoding='utf-8')
        compose('exec', '-T', 'app', 'nginx', '-t')
        compose('exec', '-T', 'app', 'nginx', '-s', 'reload')
        write_state({'active': next_slot, 'revision': revision,
                     'updated': datetime.now(timezone.utc).isoformat()})
    except Exception:
        path.write_text(old_config, encoding='utf-8')
        compose('exec', '-T', 'app', 'nginx', '-s', 'reload')
        raise
    wait_for_drain()
    compose('stop', previous)
    compose('rm', '-f', previous)
    previous_ai = f"ai-{state['active']}"
    if assistant_enabled() or compose('ps', '-a', '-q', previous_ai):
        compose('stop', previous_ai)
        compose('rm', '-f', previous_ai)
    print(f'Deployment complete, active slot: {next_slot}, previous slot removed')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('initialize', 'start', 'deploy'))
    parser.add_argument('--pull', action='store_true', help='Fast-forward main before manual deployment')
    options = parser.parse_args()
    with deployment_lock():
        if options.action == 'initialize':
            initialize()
        elif options.action == 'start':
            start()
        else:
            deploy(options.pull)


if __name__ == '__main__':
    main()
