from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import pytest
from storage import StoreError, TestStore as JsonStore, validate_tests


@pytest.fixture
def store(tmp_path):
    return JsonStore(tmp_path / 'testy', tmp_path / 'data')


@pytest.fixture
def classic():
    return {'title': 'Histológia', 'year': 2, 'category': 'Histológia', 'previousTitles': ['Starší názov'],
            'questions': [{'question': 'Otázka?', 'answers': ['A', 'B'], 'correct': [0],
                           'source': {'page': 10}, 'curriculum': {'week': 2}}]}


@pytest.fixture
def vocab():
    return {'title': 'Latinčina', 'testType': 'vocabulary', 'vocabulary': [
        {'latin': 'costa', 'slovak': 'rebro', 'type': 'noun', 'genitive': '-ae', 'gender': 'f'}]}


def test_create_reload_preserves_all_metadata(store, classic):
    store.import_tests([classic])
    assert store.load('Histológia.json')['data'] == [classic]
    tests, meta = store.catalog()
    assert len(tests) == len(meta) == 1
    assert tests[0]['questions'] == classic['questions']
    tests[0]['questions'].clear()
    assert len(store.catalog()[0][0]['questions']) == 1


def test_duplicate_import_is_all_or_nothing(store, classic):
    store.import_tests(classic)
    original = store.path('Histológia.json').read_bytes()
    new = {**classic, 'title': 'Nový'}
    with pytest.raises(StoreError):
        store.import_tests([new, classic])
    assert not store.path('Nový.json').exists()
    assert store.path('Histológia.json').read_bytes() == original


@pytest.mark.parametrize('name', ['../escape', '/tmp/escape', 'dir/file', 'dir\\file', '.hidden', 'bad\x00name'])
def test_reject_paths(store, classic, name):
    with pytest.raises(StoreError):
        store.save(name, classic)
    assert not list(store.root.glob('*.json'))


def test_symlink_cannot_be_read_or_overwritten(store, classic, tmp_path):
    outside = tmp_path / 'outside.json'
    outside.write_text(json.dumps([classic]))
    store.path('link.json').symlink_to(outside)
    with pytest.raises(StoreError):
        store.load('link.json')
    with pytest.raises(StoreError):
        store.save('link', classic)
    assert json.loads(outside.read_text()) == [classic]


def test_rename_collision_does_not_modify_either_file(store, classic):
    store.import_tests([classic, {**classic, 'title': 'Existujúci'}])
    before = {p.name: p.read_bytes() for p in store.root.glob('*.json')}
    loaded = store.load('Histológia.json')
    loaded['data'][0]['title'] = 'Existujúci'
    with pytest.raises(StoreError):
        store.update('Histológia.json', loaded['data'], loaded['version'])
    assert before == {p.name: p.read_bytes() for p in store.root.glob('*.json')}


def test_edit_rename_delete_backups_are_exact(store, classic):
    store.import_tests(classic)
    path = store.path('Histológia.json')
    original = path.read_bytes()
    loaded = store.load(path.name)
    changed = deepcopy(loaded['data'])
    changed[0]['title'] = 'Nový názov'
    updated = store.update(path.name, changed, loaded['version'])
    assert not path.exists()
    assert updated['renamed']
    assert list(store.backups.rglob('Histológia.json'))[0].read_bytes() == original
    new_path = store.path(updated['filename'])
    renamed = new_path.read_bytes()
    store.delete(updated['filename'], updated['version'])
    assert not new_path.exists()
    assert list(store.backups.rglob('Nový názov.json'))[0].read_bytes() == renamed


def test_stale_and_missing_versions_rejected(store, classic):
    created = store.save('Histológia', classic)
    changed = {**classic, 'description': 'Prvá úprava'}
    store.update(created['filename'], changed, created['version'])
    for version in (None, created['version']):
        with pytest.raises(StoreError):
            store.update(created['filename'], classic, version)
        with pytest.raises(StoreError):
            store.delete(created['filename'], version)
    assert store.load(created['filename'])['data'][0]['description'] == 'Prvá úprava'


@pytest.mark.parametrize('fixture', ['classic', 'vocab'])
def test_append_and_metadata_preservation(store, request, fixture):
    test = request.getfixturevalue(fixture)
    created = store.save(test['title'], test)
    store.save(test['title'], test, 'append', created['version'])
    loaded = store.load(created['filename'])['data'][0]
    field = 'vocabulary' if fixture == 'vocab' else 'questions'
    assert loaded[field] == test[field] * 2
    assert {k: v for k, v in loaded.items() if k != field} == {k: v for k, v in test.items() if k != field}


def test_cannot_mix_vocabulary_and_questions(store, classic, vocab):
    created = store.save(classic['title'], classic)
    with pytest.raises(StoreError):
        store.save(classic['title'], vocab, 'append', created['version'])
    assert store.load(created['filename'])['data'] == [classic]


def test_interrupted_atomic_update_preserves_original(store, classic, monkeypatch):
    created = store.save(classic['title'], classic)
    original = store.path(created['filename']).read_bytes()
    def fail(*args):
        raise OSError('Simulovaná chyba disku')
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        store.update(created['filename'], {**classic, 'description': 'Zmena'}, created['version'])
    assert store.path(created['filename']).read_bytes() == original
    assert not list(store.root.glob('*.tmp'))


def test_parallel_reads_have_no_duplicates(store, classic):
    store.import_tests([{**classic, 'title': str(i)} for i in range(8)])
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.catalog()[0], range(32)))
    assert all(len(items) == 8 and len({t['filename'] for t in items}) == 8 for items in results)


@pytest.mark.parametrize('correct', [None, True, -1, 2, [0, 0], ['0'], {}])
def test_invalid_answer_indices(classic, correct):
    classic['questions'][0]['correct'] = correct
    with pytest.raises(StoreError):
        validate_tests(classic)


def test_zero_correct_answers_and_scalar_are_supported(classic):
    for correct in ([], 0, [0, 1]):
        classic['questions'][0]['correct'] = correct
        assert validate_tests(classic)[0] == classic
