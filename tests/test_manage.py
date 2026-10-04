"""Správa prostredí: oddelenie dát, žiadne implicitné verejné spustenie."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deployment(tmp_path):
    root = tmp_path / 'project with spaces'
    (root / 'tools').mkdir(parents=True)
    shutil.copyfile(ROOT / 'tools' / 'manage.sh', root / 'tools' / 'manage.sh')
    docker = tmp_path / 'docker_stub.py'
    docker.write_text('''
import json, os, sys
with open(os.environ['DOCKER_CALLS'], 'a') as file:
    file.write(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(),
        'uid': os.environ.get('APP_UID'), 'gid': os.environ.get('APP_GID'),
        'profiles': os.environ.get('COMPOSE_PROFILES')}) + '\\n')
if 'prepare' in sys.argv and os.environ.get('FAIL_PREPARE'):
    sys.exit(42)
''')
    log = tmp_path / 'calls.jsonl'
    env = {**os.environ, 'DOCKER_STUB': str(docker), 'DOCKER_PYTHON': sys.executable,
           'DOCKER_CALLS': str(log), 'APP_UID': '1234', 'APP_GID': '1235',
           'COMPOSE_PROFILES': 'public'}
    env.pop('TESTER_PROJECT_NAME', None)

    def run(*args, **extra):
        # /tmp je v testovacom kontajneri noexec; mock volá interpreter,
        # bez oslabenia kontajnera alebo potreby skutočného Docker démona.
        command = 'docker() { "$DOCKER_PYTHON" "$DOCKER_STUB" "$@"; }; export -f docker; exec bash "$@"'
        result = subprocess.run(['bash', '-c', command, 'manage-test',
                                 str(root / 'tools' / 'manage.sh'), *args],
                                cwd=tmp_path, env={**env, **extra},
                                capture_output=True, text=True, timeout=15)
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return root, run


def test_local_prepares_before_start_and_ignores_public_environment(deployment):
    root, run = deployment
    result, calls = run('local', 'up')
    assert result.returncode == 0, result.stderr
    assert calls[-2]['args'][-3:] == ['run', '--rm', 'prepare']
    assert calls[-1]['args'][-4:] == ['up', '-d', '--build', '--wait']
    for call in calls[1:]:
        args = call['args']
        assert '--profile' not in args
        assert args[args.index('--env-file') + 1] == '/dev/null'
        assert args[args.index('-p') + 1] == 'tester-local'
        assert 'docker-compose.local.yml' in args
        assert call['cwd'] == str(root)
        assert call['profiles'] is None
        assert (call['uid'], call['gid']) == ('1234', '1235')


def test_failed_local_preparation_does_not_start_web(deployment):
    _, run = deployment
    result, calls = run('local', 'up', FAIL_PREPARE='1')
    assert result.returncode == 42
    assert not any('up' in call['args'] for call in calls)


def test_lan_uses_separate_project_and_override_without_public_profile(deployment):
    _, run = deployment
    result, calls = run('lan', 'up')
    assert result.returncode == 0, result.stderr
    assert calls[-2]['args'][-3:] == ['run', '--rm', 'prepare']
    for call in calls[1:]:
        args = call['args']
        assert args[args.index('-p') + 1] == 'tester-lan'
        assert args[args.index('--env-file') + 1] == '/dev/null'
        assert 'docker-compose.lan.yml' in args
        assert '--profile' not in args
        assert call['profiles'] is None


def test_public_start_requires_migrated_configuration_and_tests(deployment):
    _, run = deployment
    result, calls = run('public', 'up')
    assert result.returncode == 1
    assert not calls
    assert 'Chýba .env alebo testy/' in result.stderr


def test_public_start_uses_explicit_profile_without_executing_or_printing_env(deployment):
    root, run = deployment
    (root / '.env').write_text('ADMIN_SECRET=fixture-private-value\nIGNORE=$(touch injected)\n')
    (root / 'testy').mkdir()
    result, calls = run('public', 'up')
    assert result.returncode == 0, result.stderr
    assert (root / 'data').is_dir()
    assert not (root / 'injected').exists()
    assert 'fixture-private-value' not in result.stdout + result.stderr
    args = calls[-1]['args']
    assert args[args.index('--env-file') + 1] == '.env'
    assert args[args.index('--profile') + 1] == 'public'
    assert args[args.index('-p') + 1] == 'tester'
    assert 'docker-compose.local.yml' not in args
    assert not any('prepare' in call['args'] for call in calls)


@pytest.mark.parametrize('mode', ['local', 'lan', 'public'])
def test_removal_preserves_files_and_works_without_env(deployment, mode):
    root, run = deployment
    for directory in ['testy', 'data', '.local/testy']:
        path = root / directory
        path.mkdir(parents=True, exist_ok=True)
        (path / 'sentinel').write_bytes(b'keep exactly')
    result, calls = run(mode, 'down')
    assert result.returncode == 0, result.stderr
    assert calls[-1]['args'][-1] == 'down'
    assert '--volumes' not in calls[-1]['args'] and '-v' not in calls[-1]['args']
    for directory in ['testy', 'data', '.local/testy']:
        assert (root / directory / 'sentinel').read_bytes() == b'keep exactly'


def test_invalid_mode_never_calls_docker(deployment):
    _, run = deployment
    result, calls = run('production', 'up')
    assert result.returncode == 2
    assert not calls


def test_preparation_keeps_local_and_lan_data_and_secrets_separate(tmp_path):
    (tmp_path / 'tools').mkdir()
    (tmp_path / 'testy').mkdir()
    script = tmp_path / 'tools' / 'prepare_local.py'
    shutil.copyfile(ROOT / 'tools' / 'prepare_local.py', script)
    source = tmp_path / 'testy' / 'example.json'
    source.write_bytes(b'[{"title":"original"}]')
    for mode, folder in [('local', '.local'), ('lan', '.local/lan')]:
        subprocess.run([sys.executable, str(script), '--environment', mode], check=True)
        assert (tmp_path / folder / 'testy' / source.name).read_bytes() == source.read_bytes()
    env_local = (tmp_path / '.env.local').read_bytes()
    env_lan = (tmp_path / '.env.lan').read_bytes()
    assert env_local != env_lan
    for mode in ['local', 'lan']:
        assert (tmp_path / f'.env.{mode}').stat().st_mode & 0o777 == 0o600
    local_test = tmp_path / '.local/testy' / source.name
    local_test.write_bytes(b'keep edited local test')
    source.write_bytes(b'changed source')
    for mode in ['local', 'lan']:
        subprocess.run([sys.executable, str(script), '--environment', mode], check=True)
    assert local_test.read_bytes() == b'keep edited local test'
    assert (tmp_path / '.local/lan/testy' / source.name).read_bytes() == b'[{"title":"original"}]'
    assert (tmp_path / '.env.local').read_bytes() == env_local
    assert (tmp_path / '.env.lan').read_bytes() == env_lan
