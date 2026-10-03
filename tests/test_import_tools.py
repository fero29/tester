"""Presunuté ručné nástroje: prenositeľné cesty a zhoda s úložiskom aplikácie."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import Mock

import anthropic
import dotenv
import pytest

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / 'tools' / 'imports'


@pytest.mark.parametrize('script', sorted(IMPORTS.glob('*.py')), ids=lambda p: p.name)
def test_import_from_another_working_directory_has_no_ai_call(script, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    load_env = Mock()
    monkeypatch.setattr(dotenv, 'load_dotenv', load_env)
    client = Mock(side_effect=AssertionError('Import nesmie volať platené API.'))
    monkeypatch.setattr(anthropic, 'Anthropic', client)
    module = runpy.run_path(str(script), run_name='import_check')
    client.assert_not_called()
    if 'ROOT' in module:
        assert module['ROOT'] == ROOT
    if load_env.called:
        load_env.assert_called_once_with(ROOT / '.env')
    if 'MANIFEST' in module:
        assert module['MANIFEST'].parent == IMPORTS
        assert module['MANIFEST'].is_file()
    if 'PDF' in module:
        assert module['PDF'].parent == ROOT / 'sources'


def test_split_output_is_verified_by_current_storage(tmp_path):
    module = runpy.run_path(str(IMPORTS / 'split_biochemia1_weeks.py'))
    files = {Path(f'Test {i}.json'): [{
        'title': f'Test {i}', 'year': 2, 'category': 'Biochémia',
        'questions': [{'question': 'Otázka', 'answers': ['A', 'B'], 'correct': [0]}],
    }] for i in range(13)}
    module['write_outputs'](tmp_path, files)
    module['verify_app_loader'](tmp_path, files)
    path = tmp_path / 'Test 0.json'
    changed = json.loads(path.read_text())
    changed[0]['questions'][0]['correct'] = [1]
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='odlišné dáta'):
        module['verify_app_loader'](tmp_path, files)


def test_manual_ai_help_needs_no_key_or_image(tmp_path):
    result = subprocess.run(
        [sys.executable, str(IMPORTS / 'test_ai.py'), '--help'], cwd=tmp_path,
        env={**os.environ, 'ANTHROPIC_API_KEY': ''}, capture_output=True, text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert 'image' in result.stdout
