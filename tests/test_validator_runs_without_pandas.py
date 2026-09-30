"""The standalone validator image has no pandas (Dockerfile / requirements-validator.txt).

Everything on the validator's import path, including the session-map rule reached
through survey_core, must import and work without it. CI's docker smoke test caught
this once; this test catches it in seconds.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

BLOCK_PANDAS = """
import sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name == "pandas" or name.startswith("pandas."):
            raise ImportError("No module named 'pandas'")
sys.meta_path.insert(0, Block())
"""


def run_without_pandas(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", BLOCK_PANDAS + code],
        cwd=REPO,
        env={"PRISM_SKIP_VENV_CHECK": "1", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_validator_entry_point_starts_without_pandas():
    result = run_without_pandas(
        "import runpy\n"
        "sys.argv = ['app/prism.py', '--version']\n"
        "try:\n"
        "    runpy.run_path('app/prism.py', run_name='__main__')\n"
        "except SystemExit as exit_:\n"
        "    sys.exit(exit_.code)\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "prism-validator" in result.stdout


def test_session_rule_works_without_pandas():
    result = run_without_pandas(
        "sys.path[:0] = ['.', 'app']\n"
        "from src.session_map import SessionsNotMappedError, apply_session_map, unmapped_labels\n"
        "assert apply_session_map(1.0, {'1': 'a'}) == 'a'\n"
        "assert apply_session_map(' pre ', {'pre': 'x'}) == 'x'\n"
        "assert unmapped_labels(['', None, float('nan')], {}) == ['']\n"
        "print('ok')\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
