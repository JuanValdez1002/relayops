import os
import subprocess
import sys
from pathlib import Path


def test_missing_database_url_raises_error():
    backend_dir = Path(__file__).resolve().parents[1]

    env = os.environ.copy()
    env["DATABASE_URL"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import database"
        ],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True
    )

    assert result.returncode != 0
    assert "DATABASE_URL is missing from .env" in result.stderr

def test_strip_required_strings_preserves_non_string_values():
    from schemas import EventCreate

    result = EventCreate.strip_required_strings(123)

    assert result == 123