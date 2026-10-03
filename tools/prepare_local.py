"""Vytvorí testovacie dáta a prihlasovanie. Existujúce súbory nikdy neprepíše."""
from pathlib import Path
import hashlib
import json
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / '.local' / 'testy'
    destination.mkdir(parents=True, exist_ok=True)
    (ROOT / '.local' / 'data').mkdir(exist_ok=True)
    copied = 0
    for source in (ROOT / 'testy').glob('*.json'):
        target = destination / source.name
        if source.is_symlink():
            continue
        if not target.exists():
            with target.open('xb') as handle:
                handle.write(source.read_bytes())
            copied += 1
    env = ROOT / '.env.local'
    if not env.exists():
        fd = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(f'SECRET_KEY={secrets.token_hex(32)}\nADMIN_SECRET={secrets.token_urlsafe(24)}\nCOOKIE_SECURE=false\n')
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / 'testy').glob('*.json') if not p.is_symlink()}
    (ROOT / '.local' / 'source-sha256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f'Pridané lokálne kópie: {copied}. Existujúce lokálne testy zostali zachované.')
    print('Heslo lokálneho správcu je ADMIN_SECRET v .env.local. Produkčné dáta sa nepoužijú.')


if __name__ == '__main__':
    main()
