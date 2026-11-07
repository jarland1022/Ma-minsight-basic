"""P0-06-E contract tests — real outbound payloads via mock transport."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.privacy.config import PrivacyPolicy
from app.privacy.egress_gateway import EgressDeniedError, EgressGateway, set_egress_gateway
from app.privacy.pseudonym import Pseudonymizer, derive_pseudonym_secret
from app.privacy.transform import EgressTransformer, TransformResult
from app.privacy.types import ContentType, EgressChannel, EgressContext


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, status_code: int = 200, json_body: dict | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.status_code = status_code
        self.json_body = json_body or {
            "choices": [{"message": {"content": "ok", "tool_calls": []}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status_code, json=self.json_body, request=request)


def _policy(**overrides: Any) -> PrivacyPolicy:
    secret = derive_pseudonym_secret(
        explicit_secret="test-pseudonym-secret-not-for-prod",
        jwt_secret="unused",
        insecure_jwt_default="change-me",
        app_env="test",
    )
    p = PrivacyPolicy(
        llm_egress_enabled=True,
        ti_egress_enabled=True,
        wecom_egress_enabled=True,
        embed_egress_enabled=True,
        webhook_egress_enabled=True,
        pseudonym_secret=secret,
        customer_scope_id="tenant-a",
    )
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


@pytest.fixture
def gateway_and_transport():
    transport = RecordingTransport()
    audits: list = []
    gw = EgressGateway(transport=transport, audit_sink=audits)
    set_egress_gateway(gw)
    yield gw, transport, audits
    set_egress_gateway(None)


@pytest.mark.asyncio
async def test_llm_path_goes_through_gateway_and_redacts_secrets(gateway_and_transport):
    gw, transport, audits = gateway_and_transport
    pol = _policy()
    messages = [
        {
            "role": "user",
            "content": "host: srv-internal-01 user: alice api_key=sk-live-SHOULDNOTLEAVE",
        }
    ]
    resp = await gw.send(
        channel=EgressChannel.LLM,
        method="POST",
        url="https://api.deepseek.com/chat/completions",
        headers={"Authorization": "Bearer test-key"},
        json_body={"model": "m", "messages": messages},
        content_type=ContentType.CHAT_MESSAGES,
        context=EgressContext(investigation_id="inv-1", scope_id="tenant-a"),
        policy=pol,
    )
    assert resp.status_code == 200
    assert len(transport.requests) == 1
    body = json.loads(transport.requests[0].content.decode())
    content = body["messages"][0]["content"]
    assert "sk-live-SHOULDNOTLEAVE" not in content
    assert "[REDACTED_SECRET]" in content or "api_key" in content.lower()
    assert "alice" not in content or "user_" in content
    assert audits and audits[-1].decision == "allow"


@pytest.mark.asyncio
async def test_pii_pseudonym_consistent_within_scope(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    pol = _policy()
    ctx = EgressContext(investigation_id="inv-99", scope_id="tenant-a")
    msg = [{"role": "user", "content": "user: bob host: web01"}]
    await gw.send(
        channel=EgressChannel.LLM,
        method="POST",
        url="https://api.deepseek.com/chat/completions",
        json_body={"model": "m", "messages": msg},
        context=ctx,
        policy=pol,
    )
    await gw.send(
        channel=EgressChannel.LLM,
        method="POST",
        url="https://api.deepseek.com/chat/completions",
        json_body={"model": "m", "messages": msg},
        context=ctx,
        policy=pol,
    )
    c1 = json.loads(transport.requests[0].content.decode())["messages"][0]["content"]
    c2 = json.loads(transport.requests[1].content.decode())["messages"][0]["content"]
    assert c1 == c2
    assert "bob" not in c1
    assert "web01" not in c1


@pytest.mark.asyncio
async def test_pseudonym_isolated_across_customer_scopes():
    secret = derive_pseudonym_secret(
        explicit_secret="shared-test-secret",
        jwt_secret="x",
        insecure_jwt_default="y",
        app_env="test",
    )
    assert secret
    p1 = Pseudonymizer(secret)
    a = p1.pseudonymize("alice", field_kind="user", scope="tenant-a|inv1")
    b = p1.pseudonymize("alice", field_kind="user", scope="tenant-b|inv1")
    assert a != b


@pytest.mark.asyncio
async def test_missing_pseudonym_secret_fail_closed(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    pol = _policy(pseudonym_secret=None)
    with pytest.raises(EgressDeniedError) as ei:
        await gw.send(
            channel=EgressChannel.LLM,
            method="POST",
            url="https://api.deepseek.com/chat/completions",
            json_body={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
            policy=pol,
        )
    assert "pseudonym_secret_missing" in ei.value.reason or "secret" in ei.value.reason
    assert transport.requests == []


@pytest.mark.asyncio
async def test_channel_disabled_sends_no_http(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    pol = _policy(llm_egress_enabled=False)
    with pytest.raises(EgressDeniedError):
        await gw.send(
            channel=EgressChannel.LLM,
            method="POST",
            url="https://api.deepseek.com/chat/completions",
            json_body={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
            policy=pol,
        )
    assert transport.requests == []


@pytest.mark.asyncio
async def test_ti_allows_public_ip_and_channel_disable(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    transport.json_body = {"data": {"abuseConfidenceScore": 0}}
    pol = _policy()
    await gw.send(
        channel=EgressChannel.TI,
        method="GET",
        url="https://api.abuseipdb.com/api/v2/check",
        params={"ipAddress": "8.8.8.8", "maxAgeInDays": 90},
        policy=pol,
    )
    assert len(transport.requests) == 1
    assert "8.8.8.8" in str(transport.requests[0].url)

    pol2 = _policy(ti_egress_enabled=False)
    with pytest.raises(EgressDeniedError):
        await gw.send(
            channel=EgressChannel.TI,
            method="GET",
            url="https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": "8.8.8.8"},
            policy=pol2,
        )


@pytest.mark.asyncio
async def test_wecom_markdown_pseudonymizes_host_user(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    transport.json_body = {"errcode": 0, "msgid": "1"}
    pol = _policy(wecom_allow_host_user=False)
    md = "**主机** corp-dc01 | **用户** charlie\napi_key=leakme12345678"
    await gw.send(
        channel=EgressChannel.WECOM,
        method="POST",
        url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send",
        json_body={"msgtype": "markdown", "markdown": {"content": md}},
        policy=pol,
    )
    body = json.loads(transport.requests[0].content.decode())
    content = body["markdown"]["content"]
    assert "corp-dc01" not in content
    assert "charlie" not in content
    assert "leakme12345678" not in content


@pytest.mark.asyncio
async def test_embed_and_webhook_respect_disable(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    transport.json_body = {"data": [{"embedding": [0.1, 0.2]}]}
    with pytest.raises(EgressDeniedError):
        await gw.send(
            channel=EgressChannel.EMBED,
            method="POST",
            url="https://api.openai.com/v1/embeddings",
            json_body={"model": "m", "input": "user: dave"},
            policy=_policy(embed_egress_enabled=False),
        )
    with pytest.raises(EgressDeniedError):
        await gw.send(
            channel=EgressChannel.WEBHOOK,
            method="POST",
            url="https://example.com/hook",
            json_body={"msgtype": "markdown", "markdown": {"content": "x"}},
            policy=_policy(webhook_egress_enabled=False),
        )
    assert transport.requests == []


@pytest.mark.asyncio
async def test_byo_endpoint_still_protects(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    pol = _policy()
    await gw.send(
        channel=EgressChannel.LLM,
        method="POST",
        url="https://llm.customer.local/v1/chat/completions",
        json_body={
            "model": "m",
            "messages": [{"role": "user", "content": "user: eve password=SuperSecret99"}],
        },
        policy=pol,
    )
    content = json.loads(transport.requests[0].content.decode())["messages"][0]["content"]
    assert "SuperSecret99" not in content
    assert "eve" not in content or "user_" in content


@pytest.mark.asyncio
async def test_tool_arguments_and_results_protected(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    pol = _policy()
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "1",
                    "type": "function",
                    "function": {
                        "name": "query_asset",
                        "arguments": json.dumps({"host_name": "db-prod-01", "user_name": "root"}),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "1", "content": "host: db-prod-01 user: root found"},
    ]
    await gw.send(
        channel=EgressChannel.LLM,
        method="POST",
        url="https://api.deepseek.com/chat/completions",
        json_body={"model": "m", "messages": messages},
        policy=pol,
        context=EgressContext(investigation_id="inv-tools"),
    )
    body = json.loads(transport.requests[0].content.decode())
    blob = json.dumps(body)
    assert "db-prod-01" not in blob
    assert "root" not in blob or "user_" in blob


@pytest.mark.asyncio
async def test_gateway_transform_failure_fail_closed(gateway_and_transport):
    gw, transport, _ = gateway_and_transport
    pol = _policy()

    class Boom(EgressGateway):
        async def protect(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    bad = Boom(transport=transport, audit_sink=[])
    with pytest.raises(EgressDeniedError):
        await bad.send(
            channel=EgressChannel.LLM,
            method="POST",
            url="https://api.deepseek.com/chat/completions",
            json_body={"model": "m", "messages": [{"role": "user", "content": "x"}]},
            policy=pol,
        )
    assert transport.requests == []


def test_secret_never_in_structured_json():
    secret = derive_pseudonym_secret(
        explicit_secret="s", jwt_secret="j", insecure_jwt_default="d", app_env="test"
    )
    assert secret
    tr = EgressTransformer(
        pseudonymizer=Pseudonymizer(secret),
        scope="t|i",
        channel="llm",
    )
    result = TransformResult()
    out = tr.transform_mapping({"password": "hunter2", "rule_name": "ssh"}, result)
    assert out["password"] == "[REDACTED_SECRET]"
    assert out["rule_name"] == "ssh"
    assert result.secret_hit


@pytest.mark.asyncio
async def test_vendor_credential_gated_and_disabled(gateway_and_transport):
    gw, transport, audits = gateway_and_transport
    transport.json_body = {"errcode": 0, "access_token": "tok", "expires_in": 7200}
    pol = _policy()
    resp = await gw.send_vendor_credential(
        channel=EgressChannel.WECOM,
        method="GET",
        url="https://qyapi.weixin.qq.com/cgi-bin/gettoken",
        params={"corpid": "c", "corpsecret": "super-secret-corp"},
        policy=pol,
    )
    assert resp.status_code == 200
    assert len(transport.requests) == 1
    # Audit must not contain corpsecret
    for a in audits:
        blob = json.dumps(a.__dict__, default=str)
        assert "super-secret-corp" not in blob

    transport.requests.clear()
    with pytest.raises(EgressDeniedError):
        await gw.send_vendor_credential(
            channel=EgressChannel.WECOM,
            method="GET",
            url="https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": "c", "corpsecret": "x"},
            policy=_policy(wecom_egress_enabled=False),
        )
    assert transport.requests == []


@pytest.mark.asyncio
async def test_audit_record_has_no_raw_prompt(gateway_and_transport):
    gw, transport, audits = gateway_and_transport
    pol = _policy()
    await gw.send(
        channel=EgressChannel.LLM,
        method="POST",
        url="https://api.deepseek.com/chat/completions",
        json_body={
            "model": "m",
            "messages": [{"role": "user", "content": "user: secretuser host: secret-host"}],
        },
        policy=pol,
        context=EgressContext(investigation_id="inv-audit"),
    )
    assert audits
    last = audits[-1]
    blob = json.dumps(last.__dict__, default=str)
    assert "secretuser" not in blob
    assert "secret-host" not in blob
    assert last.content_digest
    assert last.decision == "allow"


@pytest.mark.asyncio
async def test_llm_client_uses_gateway(monkeypatch, gateway_and_transport):
    from app.core import config as cfg
    from app.llm.client import LLMClient

    monkeypatch.setattr(cfg.settings, "deepseek_api_key", "k")
    monkeypatch.setattr(cfg.settings, "deepseek_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(cfg.settings, "privacy_pseudonym_secret", "test-secret")

    # Force policy via monkeypatch load
    async def fake_load(session=None):
        return _policy()

    monkeypatch.setattr("app.privacy.egress_gateway.load_privacy_policy", fake_load)
    monkeypatch.setattr("app.privacy.config.load_privacy_policy", fake_load)

    client = LLMClient()
    result = await client.chat(
        messages=[{"role": "user", "content": "user: frank"}],
        egress_context=EgressContext(investigation_id="i1"),
    )
    assert result.content == "ok"
    gw, transport, _ = gateway_and_transport
    assert transport.requests
    content = json.loads(transport.requests[0].content.decode())["messages"][0]["content"]
    assert "frank" not in content
