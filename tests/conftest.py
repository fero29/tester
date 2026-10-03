from pathlib import Path
import os
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_sandbox = tempfile.TemporaryDirectory(prefix='tester-suite-')
os.environ.update(TESTS_DIR=_sandbox.name + '/testy', DATA_DIR=_sandbox.name + '/data',
                  SECRET_KEY='isolated-test-session-key', ADMIN_SECRET='test-admin-password',
                  ANTHROPIC_API_KEY='', COOKIE_SECURE='false')
