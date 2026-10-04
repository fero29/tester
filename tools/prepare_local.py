"""Vytvorí testovacie dáta a prihlasovanie. Existujúce súbory nikdy neprepíše."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=('local', 'lan'), default='local')
    args = parser.parse_args()
    workspace = ROOT / '.local'
    if args.environment == 'lan':
        workspace = workspace / 'lan'
    destination = workspace / 'testy'
    destination.mkdir(parents=True, exist_ok=True)
    (workspace / 'data').mkdir(exist_ok=True)
    copied = 0
    for source in (ROOT / 'testy').glob('*.json'):
        target = destination / source.name
        if source.is_symlink():
            continue
        if not target.exists():
            with target.open('xb') as handle:
                handle.write(source.read_bytes())
            copied += 1
    env = ROOT / f'.env.{args.environment}'
    if not env.exists():
        fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(f'SECRET_KEY={secrets.token_hex(32)}\nADMIN_SECRET={secrets.token_urlsafe(24)}\nCOOKIE_SECURE=false\n')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'testy').glob('*.json') if not p.is_symlink()}
    (workspace / 'source-sha256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f'Prostredie {args.environment}: pridané kópie {copied}. Existujúce testy zostali zachované.')
    print(f'Heslo správcu je ADMIN_SECRET v {env.name}. Pôvodné testy zostali zachované.')


if __name__ == '__main__':
    main()
