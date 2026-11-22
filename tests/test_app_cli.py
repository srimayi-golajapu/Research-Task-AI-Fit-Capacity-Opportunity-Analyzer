"""
Tests for Application CLI
"""

import os
import subprocess
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON_EXE = str(venv_python) if venv_python.exists() else sys.executable


def _get_env():
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    site_packages = PROJECT_ROOT / ".venv" / "Lib" / "site-packages"
    if site_packages.exists():
        curr_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{site_packages}{os.pathsep}{curr_pythonpath}"
    return env


def test_cli_help():
    res = subprocess.run([PYTHON_EXE, "app/cli.py", "--help"], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=_get_env())
    assert res.returncode == 0
    assert "run-pipeline" in res.stdout
    assert "summary" in res.stdout
    assert "load-org" in res.stdout
    assert "export" in res.stdout
    assert "serve" in res.stdout


def test_cli_summary():
    res = subprocess.run([PYTHON_EXE, "app/cli.py", "summary"], cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=_get_env())
    assert res.returncode == 0
    assert "Capacity Release Scenario Comparison" in res.stdout
    assert "Moderate Scenario" in res.stdout
