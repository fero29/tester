"""JSON úložisko: validácia, atómový zápis a záloha každej zmeny.

Čítanie existujúce súbory nikdy neprepisuje. Zámok platí aj medzi procesmi.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import uuid


class StoreError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def validate_tests(data):
    items = data if isinstance(data, list) else [data]
    if not items or len(items) > 1000:
        raise StoreError('Súbor musí obsahovať 1 až 1000 testov.')
    for test in items:
        if not isinstance(test, dict) or not isinstance(test.get('title'), str) or not test['title'].strip():
            raise StoreError('Každý test musí mať názov.')
        for field in ('description', 'category'):
            if field in test and not isinstance(test[field], str):
                raise StoreError(f'Pole {field} musí byť text.')
        if 'year' in test and (isinstance(test['year'], bool) or test['year'] not in (1, 2, '1', '2')):
            raise StoreError('Ročník musí byť 1 alebo 2.')
        if 'previousTitles' in test and (not isinstance(test['previousTitles'], list) or not all(isinstance(t, str) for t in test['previousTitles'])):
            raise StoreError('Predchádzajúce názvy musia byť zoznam textov.')
        if 'sortOrder' in test and (type(test['sortOrder']) not in (int, float) or not math.isfinite(test['sortOrder'])):
            raise StoreError('Poradie testu musí byť konečné číslo.')
        vocab = test.get('testType') == 'vocabulary'
        field = 'vocabulary' if vocab else 'questions'
        entries = test.get(field)
        if not isinstance(entries, list) or not 1 <= len(entries) <= 10000:
            raise StoreError('Test musí obsahovať 1 až 10000 otázok alebo slovíčok.')
        if vocab:
            for word in entries:
                if not isinstance(word, dict) or any(not isinstance(word.get(k), str) or not word[k].strip() for k in ('latin', 'slovak')):
                    raise StoreError('Slovíčko musí obsahovať latinský a slovenský text.')
                if word.get('type') not in ('noun', 'adjective', 'phrase') or any(not isinstance(word.get(k, ''), str) for k in ('genitive', 'gender')):
                    raise StoreError('Neplatný typ alebo gramatika slovíčka.')
        else:
            for question in entries:
                if not isinstance(question, dict) or not isinstance(question.get('question'), str) or not question['question'].strip():
                    raise StoreError('Otázka musí mať text.')
                answers = question.get('answers')
                if not isinstance(answers, list) or not 1 <= len(answers) <= 50 or not all(isinstance(a, str) for a in answers):
                    raise StoreError('Otázka musí obsahovať textové odpovede.')
                correct = question.get('correct')
                correct = correct if isinstance(correct, list) else [correct]
                if any(type(i) is not int or not 0 <= i < len(answers) for i in correct) or len(set(correct)) != len(correct):
                    raise StoreError('Index správnej odpovede je neplatný.')
    return deepcopy(items)


class TestStore:
    def __init__(self, root, data_dir):
        self.root = Path(root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.backups = self.data_dir / 'backups'
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._mutex = threading.RLock()
        self._cache = {}

    @contextmanager
    def locked(self):
        with self._mutex, (self.data_dir / '.tests.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def path(self, filename):
        if (not isinstance(filename, str) or not filename.endswith('.json')
                or filename.startswith('.') or len(filename.encode('utf-8')) > 240
                or any(c in filename for c in '/\\\x00') or any(ord(c) < 32 for c in filename)):
            raise StoreError('Neplatný názov súboru.')
        path = self.root / filename
        if path.is_symlink() or path.resolve().parent != self.root:
            raise StoreError('Prístup mimo adresára testov nie je povolený.')
        return path

    @staticmethod
    def version(raw):
        return hashlib.sha256(raw).hexdigest()

    def _read(self, path):
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise StoreError('Test neexistuje.', 404) from None
        try:
            data = json.loads(raw)
            validate_tests(data)
        except (ValueError, UnicodeError) as exc:
            raise StoreError(f'Neplatný test {path.name}: {exc}') from None
        return data, raw

    def load(self, filename):
        with self.locked():
            data, raw = self._read(self.path(filename))
            return {'success': True, 'filename': filename, 'data': data, 'version': self.version(raw)}

    def catalog(self, include_tests=True):
        with self.locked():
            result, meta = [], []
            paths = sorted(self.root.glob('*.json'))
            self._cache = {p.name: self._cache[p.name] for p in paths if p.name in self._cache}
            for path in paths:
                self.path(path.name)
                stat = path.stat()
                signature = (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino)
                cached = self._cache.get(path.name)
                if cached is None or cached[0] != signature:
                    data, raw = self._read(path)
                    cached = (signature, validate_tests(data), self.version(raw))
                    self._cache[path.name] = cached
                _, items, version = cached
                if include_tests:
                    result.extend({**deepcopy(test), 'filename': path.name, 'version': version} for test in items)
                meta.append({'filename': path.name, 'hash': version, 'size': stat.st_size})
            return result, meta

    def _backup(self, path, raw, action):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        folder = self.backups / f'{stamp}-{action}-{uuid.uuid4().hex[:8]}'
        folder.mkdir(parents=True)
        with (folder / path.name).open('xb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        return str(folder.relative_to(self.data_dir))

    def _write(self, path, data, create=False):
        raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
        fd, tmp = tempfile.mkstemp(prefix='.test-', suffix='.tmp', dir=self.root)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            if create:
                try:
                    os.link(tmp, path)
                except FileExistsError:
                    raise StoreError('Test s týmto názvom už existuje. Vyberte iný názov.', 409) from None
            else:
                os.replace(tmp, path)
            directory = os.open(self.root, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(tmp).unlink(missing_ok=True)
        self._cache.pop(path.name, None)
        return self.version(raw)

    def _check_version(self, raw, version):
        if not version:
            raise StoreError('Chýba verzia testu. Znova otvorte editor.', 428)
        if self.version(raw) != version:
            raise StoreError('Test medzitým zmenil iný používateľ. Znova ho načítajte; vaše zmeny sa neuložili.', 409)

    def import_tests(self, data):
        items = validate_tests(data)
        paths = [self.path(test['title'] + '.json') for test in items]
        if len(set(paths)) != len(paths):
            raise StoreError('Import obsahuje viac testov s rovnakým názvom.', 409)
        with self.locked():
            if any(path.exists() for path in paths):
                raise StoreError('Import by prepísal existujúci test. Zmeňte názov alebo použite editor.', 409)
            created = []
            try:
                for path, item in zip(paths, items):
                    version = self._write(path, [item], create=True)
                    created.append((path, version))
            except Exception:
                # Vrátiť iba súbory vytvorené týmto neúspešným importom.
                for path, version in created:
                    if path.exists() and self.version(path.read_bytes()) == version:
                        path.unlink()
                raise
        return len(items)

    def save(self, name, data, mode='new', version=None):
        items = validate_tests(data)
        if len(items) != 1 or mode not in ('new', 'append'):
            raise StoreError('Neplatný spôsob uloženia testu.')
        path = self.path(name + '.json')
        with self.locked():
            if mode == 'new':
                new_version = self._write(path, items, create=True)
            else:
                existing, raw = self._read(path)
                self._check_version(raw, version)
                existing = validate_tests(existing)
                if len(existing) != 1:
                    raise StoreError('Pridávanie do súboru s viacerými testami nie je podporované.')
                target = existing[0]
                if (target.get('testType') == 'vocabulary') != (items[0].get('testType') == 'vocabulary'):
                    raise StoreError('Otázky a slovíčka nemožno pridať do rovnakého testu.')
                field = 'vocabulary' if target.get('testType') == 'vocabulary' else 'questions'
                target[field].extend(items[0][field])
                validate_tests(existing)
                self._backup(path, raw, 'append')
                new_version = self._write(path, existing)
        return {'success': True, 'filename': path.name, 'version': new_version}

    def update(self, filename, data, version):
        items = validate_tests(data)
        path = self.path(filename)
        new_path = self.path(items[0]['title'] + '.json') if len(items) == 1 else path
        with self.locked():
            existing, raw = self._read(path)
            self._check_version(raw, version)
            if new_path != path and new_path.exists():
                raise StoreError('Test s týmto názvom už existuje. Pôvodný test zostal nezmenený.', 409)
            self._backup(path, raw, 'update')
            new_version = self._write(new_path, items, create=new_path != path)
            if new_path != path:
                path.unlink()
                self._cache.pop(path.name, None)
        return {'success': True, 'filename': new_path.name, 'renamed': new_path != path, 'version': new_version}

    def delete(self, filename, version):
        path = self.path(filename)
        with self.locked():
            _, raw = self._read(path)
            self._check_version(raw, version)
            backup = self._backup(path, raw, 'deleted')
            path.unlink()
            self._cache.pop(path.name, None)
        return {'success': True, 'message': 'Test bol odstránený zo zoznamu. Záloha zostala zachovaná.', 'backup': backup}
