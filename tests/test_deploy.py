"""Nasadenie: neplatný vstup alebo nezhoda verzie zastaví skript pred SSH a Dockerom."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def deploy(tmp_path):
    root = tmp_path / 'project'
    (root / 'tools').mkdir(parents=True)
    shutil.copyfile(ROOT / 'tools' / 'deploy.sh', root / 'tools' / 'deploy.sh')
    (root / 'VERSION').write_text('1.2.3\n')
    calls = tmp_path / 'calls'

    def run(*args):
        # Akékoľvek volanie externých nástrojov by sa zapísalo; test ich nesmie dosiahnuť.
        stubs = ''.join(f'{name}() {{ echo {name} >> "{calls}"; return 99; }}; export -f {name}; '
                        for name in ('ssh', 'scp', 'docker', 'git', 'curl'))
        result = subprocess.run(['bash', '-c', stubs + 'exec bash "$@"', 'deploy-test',
                                 str(root / 'tools' / 'deploy.sh'), *args],
                                capture_output=True, text=True, timeout=15)
        return result, calls.read_text().split() if calls.exists() else []

    return run


@pytest.mark.parametrize('args', [(), ('server',), ('server', '1.2.3'), ('server', 'v1.2'),
                                  ('deploy', 'v1.2.3'), ('fetch-data', 'v1.2.3')])
def test_invalid_arguments_show_usage(deploy, args):
    result, calls = deploy(*args)
    assert result.returncode == 2
    assert 'Použitie' in result.stderr
    assert calls == []


@pytest.mark.parametrize('command', ['local', 'server'])
def test_tag_must_match_version_file(deploy, command):
    result, calls = deploy(command, 'v1.2.4')
    assert result.returncode == 1
    assert 'VERSION je 1.2.3' in result.stderr
    assert calls == []
