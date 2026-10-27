"""Short-lived local deployment check, invoked by Windows Task Scheduler."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REMOTE = 'https://github.com/NguyenKhoa1290/MapPredictApp.git'
LOG = logging.getLogger('auto-deploy')


def eligible_revision(refs: dict[str, str], deployed: str | None) -> str | None:
    """Never deploy an old successful build while a newer main is unverified."""
    revision = refs.get('refs/heads/main', '')
    if (re.fullmatch(r'[0-9a-f]{40}', revision)
            and refs.get('refs/heads/deploy-ready') == revision
            and revision != deployed):
        return revision
    return None


def command(*args: str, timeout: int = 60) -> str:
    result = subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stderr[-2000:]}')
    return result.stdout.strip()


@contextmanager
def exclusive_check():
    path = ROOT / '.secrets' / 'auto-deploy.lock'
    with path.open('a+b') as handle:
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
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def check_once() -> bool:
    if command('git', 'remote', 'get-url', 'origin') != EXPECTED_REMOTE:
        raise RuntimeError('Unexpected origin, deployment skipped')
    if command('git', 'branch', '--show-current') != 'main':
        raise RuntimeError('Local branch is not main, deployment skipped')
    if command('git', 'status', '--porcelain'):
        LOG.info('Local edits found, keeping current application')
        return False
    state = json.loads((ROOT / '.secrets' / 'deployment-state.json').read_text(encoding='utf-8-sig'))
    raw_refs = command('git', 'ls-remote', 'origin', 'refs/heads/main', 'refs/heads/deploy-ready')
    refs = {ref: sha for sha, ref in (line.split() for line in raw_refs.splitlines())}
    revision = eligible_revision(refs, state.get('revision'))
    if not revision:
        LOG.info('No new verified revision')
        return False
    command('docker', 'info', '--format', '{{.ServerVersion}}')
    command('git', 'fetch', '--no-tags', 'origin', 'main', 'deploy-ready')
    # Fetch may race a push. Use the exact revision that was approved above.
    if command('git', 'status', '--porcelain'):
        LOG.info('Local edits found after fetch, deployment skipped')
        return False
    command('git', 'merge-base', '--is-ancestor', 'HEAD', revision)
    command('git', 'merge', '--ff-only', revision)
    if command('git', 'rev-parse', 'HEAD') != revision:
        raise RuntimeError('Checkout differs from verified revision')
    LOG.info('Deploying verified revision %s', revision)
    output = command('powershell.exe', '-NoProfile', '-NonInteractive', '-File',
                     str(ROOT / 'tools' / 'deploy_docker.ps1'), timeout=3600)
    LOG.info('%s', output[-6000:])
    deployed = json.loads((ROOT / '.secrets' / 'deployment-state.json').read_text(encoding='utf-8-sig'))
    if deployed.get('revision') != revision:
        raise RuntimeError('Deployment did not record expected revision')
    LOG.info('Deployment completed at %s', revision)
    return True


def main() -> int:
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    handler = RotatingFileHandler(logs / 'auto-deploy.log', maxBytes=1_048_576,
                                  backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    try:
        with exclusive_check():
            check_once()
        return 0
    except Exception:
        LOG.exception('Update check failed, see error details')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
