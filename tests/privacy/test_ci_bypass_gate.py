"""CI egress bypass gate — positive and reverse (must-fail) tests (P0-06 R-B / AUTH-R2)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_egress_bypass.py"


def _load_bypass_module():
    spec = importlib.util.spec_from_file_location("check_egress_bypass", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bypass = _load_bypass_module()
ALLOW_DIRECT_HTTP = _bypass.ALLOW_DIRECT_HTTP
find_violations = _bypass.find_violations


def test_check_egress_bypass_script_passes_on_current_tree():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_allowlist_is_minimal():
    assert ALLOW_DIRECT_HTTP == frozenset(
        {
            "privacy/egress_gateway.py",
            "ingestion/adapters/wazuh/client.py",
        }
    )


def test_find_violations_clean_on_repo_app():
    assert find_violations(ROOT / "app") == []


def _write_tree(tmp: Path, rel: str, body: str) -> Path:
    app = tmp / "app"
    target = app / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return app


@pytest.mark.parametrize(
    "rel,snippet",
    [
        ("evil_httpx.py", "import httpx\nclient = httpx.AsyncClient()\n"),
        ("evil_httpx_sync.py", "import httpx\nclient = httpx.Client()\n"),
        ("evil_httpx_get.py", "import httpx\nhttpx.get('https://example.com')\n"),
        ("evil_requests.py", "import requests\nrequests.get('https://example.com')\n"),
        ("evil_aiohttp.py", "import aiohttp\nsession = aiohttp.ClientSession()\n"),
        (
            "evil_urllib.py",
            "import urllib.request\nurllib.request.urlopen('https://example.com')\n",
        ),
        (
            "evil_http_client.py",
            "import http.client\nhttp.client.HTTPSConnection('example.com')\n",
        ),
    ],
)
def test_reverse_bare_clients_fail(tmp_path: Path, rel: str, snippet: str):
    app = _write_tree(tmp_path, rel, snippet)
    violations = find_violations(app)
    assert violations, f"expected violations for {rel}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(app)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "FAILED" in proc.stdout


def test_reverse_privacy_non_gateway_not_excluded(tmp_path: Path):
    """privacy/ package must not be blanket-excluded — only egress_gateway allowlisted."""
    app = _write_tree(
        tmp_path,
        "privacy/transform.py",
        "import httpx\nhttpx.AsyncClient()\n",
    )
    violations = find_violations(app)
    assert any("privacy/transform.py" in v for v in violations)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(app)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 1


def test_wazuh_allowlist_path_passes_when_only_allowed_file(tmp_path: Path):
    app = _write_tree(
        tmp_path,
        "ingestion/adapters/wazuh/client.py",
        "import httpx\nhttpx.AsyncClient()\n",
    )
    assert find_violations(app) == []
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(app)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
