"""Set the private AI admin password using an interactive prompt."""
import getpass
from pathlib import Path
from werkzeug.security import generate_password_hash


def main():
    password = getpass.getpass('AI admin password: ')
    if len(password) < 10 or password != getpass.getpass('Confirm password: '):
        raise SystemExit('Use at least 10 characters and matching confirmation')
    folder = Path(__file__).resolve().parents[1] / '.secrets'
    folder.mkdir(exist_ok=True)
    path = folder / 'ai-admin-password.hash'
    # Keep the inode so an existing Compose bind mount also sees password changes.
    path.write_text(generate_password_hash(password), encoding='utf-8')
    if __import__('os').name != 'nt':
        folder.chmod(0o700)
        path.chmod(0o644)
    print('AI admin password hash updated')


if __name__ == '__main__':
    main()
