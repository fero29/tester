import io
import json
import re
from unittest.mock import patch
import pytest
from PIL import Image
import app as module
from storage import TestStore as JsonStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    module.app.config.update(TESTING=True)
    with module.rate_limiter.lock:
        module.rate_limiter.entries.clear()
    module.app.extensions['test_store'] = JsonStore(tmp_path / 'testy', tmp_path / 'data')
    monkeypatch.setattr(module, 'EVENTS_FILE', tmp_path / 'data' / 'events.jsonl')
    return module.app.test_client()


def token(client):
    html = client.get('/admin/login').get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html)[1]


def login(client):
    response = client.post('/admin/login', data={'password': 'test-admin-password', 'csrf_token': token(client)})
    assert response.status_code == 302
    with client.session_transaction() as session:
        return {'X-CSRF-Token': session['csrf']}


def test_no_api_key_needed_for_startup(client):
    assert client.get('/health').status_code == 200
    assert client.get('/').status_code == 200
    assert client.get('/api/tests').json == []


@pytest.mark.parametrize('path,method', [('/api/import', 'post'), ('/api/save-test', 'post'),
    ('/api/update-test/test.json', 'post'), ('/api/delete-test/test.json', 'delete'),
    ('/api/list-files', 'post'), ('/api/ai-import', 'post'), ('/api/ai-import-vocab', 'post')])
def test_anonymous_writes_are_blocked(client, path, method):
    assert getattr(client, method)(path, json={}).status_code == 401


def test_admin_login_csrf_and_controls(client):
    assert 'data-admin="false"' in client.get('/').get_data(as_text=True)
    assert client.post('/admin/login', data={'password': 'test-admin-password'}).status_code == 403
    headers = login(client)
    assert 'data-admin="true"' in client.get('/').get_data(as_text=True)
    assert client.post('/api/save-test', json={}).status_code == 403
    assert client.post('/api/list-files', json={}, headers=headers).json == {'files': []}
    assert client.post('/api/list-files', json={'folder': '/etc'}, headers=headers).status_code == 400
    assert client.post('/admin/logout', headers=headers).status_code == 302
    assert client.post('/api/save-test', json={}, headers=headers).status_code == 401


def test_login_rate_limit_and_unicode_password(client):
    csrf = token(client)
    for _ in range(10):
        response = client.post('/admin/login', data={'password': 'nesprávne heslo', 'csrf_token': csrf})
        assert response.status_code == 401
    assert client.post('/admin/login', data={'password': 'test-admin-password', 'csrf_token': csrf}).status_code == 429


def test_import_duplicate_protection_and_etag(client):
    headers = login(client)
    test = {'title': 'Test', 'questions': [{'question': 'Otázka', 'answers': ['A', 'B'], 'correct': 0}]}
    def upload():
        return client.post('/api/import', headers=headers, data={'file': (io.BytesIO(json.dumps(test).encode()), 'test.json')})
    assert upload().status_code == 200
    assert upload().status_code == 409
    result = client.get('/api/tests')
    assert len(result.json) == 1
    assert client.get('/api/tests', headers={'If-None-Match': result.headers['ETag']}).status_code == 304


@pytest.mark.parametrize('data', [[], None, {'event': []}, {'event': 'invalid'},
    {'event': 'test_finish', 'percent': 101}, {'event': 'test_finish', 'score': 'bad'},
    {'event': 'page_view', 'test': []}])
def test_bad_analytics_cannot_crash_dashboard(client, data):
    assert client.post('/api/track', json=data).status_code == 400


def test_dashboard_escapes_script_content_and_requires_login(client):
    assert client.get('/admin/stats?key=test-admin-password').status_code == 302
    payload = '</script><script>window.injected=1</script>'
    assert client.post('/api/track', json={'event': 'test_finish', 'test': payload, 'percent': 50}).status_code == 200
    login(client)
    with patch.object(module, 'fetch_cf_analytics', return_value=None):
        response = client.get('/admin/stats')
    assert response.status_code == 200
    assert payload not in response.get_data(as_text=True)
    assert response.headers['Cache-Control'] == 'no-store'


def test_disabled_ai_import_is_explicit(client):
    headers = login(client)
    assert client.post('/api/ai-import', headers=headers).status_code == 503


def test_dashboard_skips_malformed_legacy_events(client):
    module.EVENTS_FILE.write_text('\n'.join(json.dumps(e) for e in [
        {'ts': '2026-10-03T12:00:00', 'event': 'page_view', 'ua': None},
        {'ts': '2026-10-03T12:00:00', 'event': 'test_finish', 'test': {'bad': 'type'}},
        {'ts': 'invalid', 'event': 'page_view'},
    ]))
    login(client)
    with patch.object(module, 'fetch_cf_analytics', return_value=None):
        assert client.get('/admin/stats').status_code == 200


@pytest.mark.parametrize('endpoint,result', [
    ('/api/ai-import', {'questions': [{'question': 'Otázka', 'answers': ['A', 'B'], 'correct': 0}]}),
    ('/api/ai-import-vocab', {'vocabulary': [{'latin': 'costa', 'slovak': 'rebro', 'type': 'noun', 'genitive': '-ae', 'gender': 'f'}]}),
])
def test_ai_endpoints_validate_response_without_external_call(client, monkeypatch, endpoint, result):
    from types import SimpleNamespace
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'mock-key')
    source = io.BytesIO()
    Image.new('RGB', (400, 200), 'white').save(source, format='PNG')
    source.seek(0)
    headers = login(client)
    with patch.object(module, 'anthropic_client') as api:
        api.return_value.messages.create.return_value = SimpleNamespace(content=[
            SimpleNamespace(type='text', text='```json\n' + json.dumps(result) + '\n```')])
        response = client.post(endpoint, headers=headers, data={'image': (source, 'scan.png'), 'rotation': '90'})
    assert response.status_code == 200
    assert response.json['success']
    if endpoint == '/api/ai-import':
        assert response.json['data']['questions'][0]['cropImage'].startswith('data:image/jpeg;base64,')


@pytest.mark.parametrize('advanced', [False, True])
def test_image_preprocessing_and_rotation(advanced):
    source = io.BytesIO()
    Image.new('RGB', (400, 200), 'white').save(source, format='PNG')
    source.seek(0)
    result = Image.open(module.preprocess_image(source, advanced=advanced, rotation=90))
    assert result.format == 'JPEG'
    assert result.height > result.width
