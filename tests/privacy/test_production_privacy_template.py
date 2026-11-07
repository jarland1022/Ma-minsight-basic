"""R3: production env template must document PRIVACY_* without real secrets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "deploy" / "env" / "production.env.example"
DEV = ROOT / ".env.example"

REQUIRED_KEYS = [
    "PRIVACY_PSEUDONYM_SECRET",
    "PRIVACY_STRICT_MODE",
    "PRIVACY_LLM_EGRESS_ENABLED",
    "PRIVACY_TI_EGRESS_ENABLED",
    "PRIVACY_WECOM_EGRESS_ENABLED",
    "PRIVACY_EMBED_EGRESS_ENABLED",
    "PRIVACY_WEBHOOK_EGRESS_ENABLED",
]


def test_production_env_example_has_privacy_keys():
    text = PROD.read_text(encoding="utf-8")
    for key in REQUIRED_KEYS:
        assert key in text, f"missing {key} in production.env.example"
    assert "PRIVACY_EMBED_EGRESS_ENABLED=false" in text
    # No obvious real-looking secrets assigned
    assert "sk-" not in text
    assert "Bearer " not in text


def test_dotenv_example_has_privacy_keys():
    text = DEV.read_text(encoding="utf-8")
    for key in REQUIRED_KEYS:
        assert key in text, f"missing {key} in .env.example"
