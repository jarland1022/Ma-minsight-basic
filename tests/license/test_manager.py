"""License manager unit tests."""

from __future__ import annotations

import base64
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.license.edition import read_edition
from app.license.manager import Manager


@pytest.fixture(autouse=True)
def _professional_edition_for_license_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Grace-period tests assume Professional packaging; community disables grace."""
    monkeypatch.setenv("MA_MINSIGHT_EDITION", "professional")
    read_edition.cache_clear()
    yield
    read_edition.cache_clear()


def _gen_keys(lic_dir: Path) -> tuple[Path, Path]:
    priv = lic_dir / "ma-minsight-private.pem"
    pub = lic_dir / "ma-minsight-public.pem"
    pk = ec.generate_private_key(ec.SECP256R1(), default_backend())
    priv.write_bytes(
        pk.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    pub.write_bytes(
        pk.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return priv, pub


def _sign_license(
    priv_path: Path,
    *,
    client: str,
    expiry: str,
    fingerprint: str,
    product: str = "MA-MinSight",
) -> str:
    pk = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
    payload = {
        "client_name": client,
        "issue_date": date.today().isoformat(),
        "expiry_date": expiry,
        "fingerprint": fingerprint.lower(),
        "product": product,
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    sig = pk.sign(body, ec.ECDSA(hashes.SHA256()))
    combined = body + b"." + base64.b64encode(sig)
    return base64.b64encode(combined).decode()


def test_genkeys_sign_verify(tmp_path: Path) -> None:
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    priv, _pub = _gen_keys(lic_dir)
    mgr = Manager(lic_dir, grace_hours=72)

    fp_hash, _ = mgr.hardware_fingerprint()
    expiry = (date.today() + timedelta(days=365)).isoformat()
    lic_text = _sign_license(priv, client="TestCo", expiry=expiry, fingerprint=fp_hash)
    lic_file = lic_dir / "license.lic"
    lic_file.write_text(lic_text, encoding="utf-8")

    payload, days = mgr.verify_full(lic_file)
    assert payload.client_name == "TestCo"
    assert payload.product == "MA-MinSight"
    assert days >= 364

    st = mgr.status()
    assert st.status == "active"
    assert st.activated is True
    assert mgr.allow_operation() is True


def test_grace_when_no_license(tmp_path: Path) -> None:
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    _gen_keys(lic_dir)
    mgr = Manager(lic_dir, grace_hours=72)

    st = mgr.status()
    assert st.status == "grace_period"
    assert mgr.allow_operation() is True
    assert mgr.grace_file.is_file()


def test_expired_license_no_grace(tmp_path: Path) -> None:
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    priv, _pub = _gen_keys(lic_dir)
    mgr = Manager(lic_dir, grace_hours=72)

    fp_hash, _ = mgr.hardware_fingerprint()
    expiry = (date.today() - timedelta(days=1)).isoformat()
    lic_text = _sign_license(priv, client="ExpiredCo", expiry=expiry, fingerprint=fp_hash)
    (lic_dir / "license.lic").write_text(lic_text, encoding="utf-8")

    st = mgr.status()
    assert st.status == "expired"
    assert mgr.allow_operation() is False
    assert not mgr.grace_file.is_file()


def test_fingerprint_mismatch_no_grace(tmp_path: Path) -> None:
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    priv, _pub = _gen_keys(lic_dir)
    mgr = Manager(lic_dir, grace_hours=72)

    expiry = (date.today() + timedelta(days=30)).isoformat()
    lic_text = _sign_license(
        priv,
        client="WrongFP",
        expiry=expiry,
        fingerprint="0" * 64,
    )
    (lic_dir / "license.lic").write_text(lic_text, encoding="utf-8")

    st = mgr.status()
    assert st.status == "fingerprint_mismatch"
    assert mgr.allow_operation() is False


def test_max_nodes_from_max_sites_compat(tmp_path: Path) -> None:
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    priv, _pub = _gen_keys(lic_dir)
    mgr = Manager(lic_dir)

    fp_hash, _ = mgr.hardware_fingerprint()
    pk = serialization.load_pem_private_key(priv.read_bytes(), password=None)
    payload = {
        "client_name": "Compat",
        "issue_date": date.today().isoformat(),
        "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
        "fingerprint": fp_hash,
        "product": "MA-MinSight",
        "max_sites": 5,
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    sig = pk.sign(body, ec.ECDSA(hashes.SHA256()))
    combined = body + b"." + base64.b64encode(sig)
    (lic_dir / "license.lic").write_text(base64.b64encode(combined).decode(), encoding="utf-8")

    st = mgr.status()
    assert st.max_nodes == 5
    assert mgr.allow_nodes(4) is True
    assert mgr.allow_nodes(5) is False


def test_import_file_rollback_on_bad_license(tmp_path: Path) -> None:
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    _gen_keys(lic_dir)
    mgr = Manager(lic_dir)

    bad = tmp_path / "bad.lic"
    bad.write_text("not-a-license", encoding="utf-8")
    with pytest.raises(RuntimeError, match="导入失败"):
        mgr.import_file(bad)
    assert not mgr.license_file.is_file()


def test_community_edition_no_grace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MA_MINSIGHT_EDITION", "community")
    read_edition.cache_clear()
    lic_dir = tmp_path / "license"
    lic_dir.mkdir()
    _gen_keys(lic_dir)
    mgr = Manager(lic_dir, grace_hours=72)
    st = mgr.status()
    assert st.status == "community"
    assert mgr.allow_operation() is False
