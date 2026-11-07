"""Unified EgressGateway — sole third-party outbound HTTP path for protected data."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.privacy.config import PrivacyPolicy, load_privacy_policy
from app.privacy.pseudonym import Pseudonymizer
from app.privacy.transform import EgressTransformer, TransformResult
from app.privacy.types import (
    ContentType,
    DestinationClass,
    EgressAuditRecord,
    EgressChannel,
    EgressContext,
    ProtectedPayload,
)

logger = logging.getLogger(__name__)


class EgressDeniedError(RuntimeError):
    """Fail-closed: outbound must not proceed."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class EgressGateway:
    """Protect payloads and optionally send via httpx. Never falls back to raw send."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        audit_sink: list[EgressAuditRecord] | None = None,
    ) -> None:
        self._transport = transport
        self._audit_sink = audit_sink  # tests collect here; production uses logger + optional DB

    async def protect(
        self,
        *,
        channel: EgressChannel | str,
        content_type: ContentType | str,
        payload: Any,
        context: EgressContext | None = None,
        session: AsyncSession | None = None,
        destination_class: DestinationClass | str = DestinationClass.THIRD_PARTY,
        policy: PrivacyPolicy | None = None,
    ) -> ProtectedPayload:
        ctx = context or EgressContext()
        ch = EgressChannel(str(channel))
        ct = ContentType(str(content_type))
        try:
            pol = policy or await load_privacy_policy(session)
        except Exception as exc:
            raise EgressDeniedError(f"policy_load_failed: {exc}") from exc

        if not pol.channel_enabled(ch.value):
            return self._deny(
                pol,
                ch,
                destination="",
                reason=f"channel_disabled:{ch.value}",
                correlation_id=ctx.correlation_id,
            )

        if pol.pseudonym_secret is None:
            return self._deny(
                pol,
                ch,
                destination="",
                reason="pseudonym_secret_missing",
                correlation_id=ctx.correlation_id,
            )

        scope = self._scope(pol, ctx)
        try:
            pseudo = Pseudonymizer(pol.pseudonym_secret, key_version=pol.policy_version)
            transformer = EgressTransformer(
                pseudonymizer=pseudo,
                scope=scope,
                channel=ch.value,
                allow_public_ip_plaintext=pol.allow_public_ip_plaintext,
                allow_username_plaintext=pol.allow_username_plaintext,
                allow_hostname_plaintext=pol.allow_hostname_plaintext,
                allow_full_url=pol.allow_full_url,
                allow_consent_plaintext=pol.allow_consent_plaintext,
                wecom_allow_host_user=pol.wecom_allow_host_user,
                fail_on_unknown=True,
            )
            result = TransformResult()
            if ct == ContentType.CHAT_MESSAGES:
                if not isinstance(payload, list):
                    raise EgressDeniedError("chat_messages payload must be a list")
                protected_body: Any = transformer.transform_messages(payload, result)
            elif ct == ContentType.JSON:
                if isinstance(payload, dict):
                    protected_body = transformer.transform_mapping(payload, result)
                else:
                    protected_body = transformer.transform_value(None, payload, result)
            elif ct in {ContentType.MARKDOWN, ContentType.PLAIN_TEXT}:
                protected_body = transformer.transform_value("content", str(payload), result)
            elif ct == ContentType.QUERY_PARAMS:
                if not isinstance(payload, dict):
                    raise EgressDeniedError("query_params payload must be a dict")
                protected_body = transformer.transform_mapping(payload, result)
            else:
                raise EgressDeniedError(f"unsupported_content_type:{ct}")
        except EgressDeniedError:
            raise
        except Exception as exc:
            raise EgressDeniedError(f"transform_failed: {exc}") from exc

        # SECRET patterns in body after transform → deny (fail-closed on residual secrets in critical paths)
        residual = _find_residual_secrets(protected_body)
        if residual:
            return self._deny(
                pol,
                ch,
                destination="",
                reason=f"secret_residual:{residual[0]}",
                correlation_id=ctx.correlation_id,
                transforms=result.transforms,
                blocked=result.blocked + residual,
            )

        digest = _digest(protected_body)
        protected = ProtectedPayload(
            payload=protected_body,
            policy_id=pol.policy_id,
            policy_version=pol.policy_version,
            transforms_applied=list(dict.fromkeys(result.transforms)),
            blocked_fields=list(dict.fromkeys(result.blocked)),
            content_digest=digest,
            allowed=True,
        )
        self._record_audit(
            EgressAuditRecord(
                channel=ch.value,
                destination="(protect-only)",
                policy_version=pol.policy_version,
                decision="allow",
                transforms_applied=protected.transforms_applied,
                blocked_fields=protected.blocked_fields,
                content_digest=digest,
                correlation_id=ctx.correlation_id,
                field_classes_summary=result.class_counts,
            )
        )
        return protected

    async def send(
        self,
        *,
        channel: EgressChannel | str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        params: dict[str, Any] | None = None,
        content: str | None = None,
        content_type: ContentType | str = ContentType.JSON,
        context: EgressContext | None = None,
        session: AsyncSession | None = None,
        timeout: float = 30.0,
        destination_class: DestinationClass | str = DestinationClass.THIRD_PARTY,
        policy: PrivacyPolicy | None = None,
        protect_json: bool = True,
    ) -> httpx.Response:
        """Protect body/params then send. On any failure, do not send."""
        ctx = context or EgressContext()
        ch = EgressChannel(str(channel))
        try:
            pol = policy or await load_privacy_policy(session)
        except Exception as exc:
            raise EgressDeniedError(f"policy_load_failed: {exc}") from exc

        if not pol.channel_enabled(ch.value):
            self._record_audit(
                EgressAuditRecord(
                    channel=ch.value,
                    destination=_safe_destination(url),
                    policy_version=pol.policy_version,
                    decision="deny",
                    transforms_applied=[],
                    blocked_fields=[],
                    content_digest="",
                    correlation_id=ctx.correlation_id,
                )
            )
            raise EgressDeniedError(f"channel_disabled:{ch.value}")

        if ch == EgressChannel.LLM:
            self._assert_llm_url_allowed(url, pol)

        # Protect request body
        send_json = json_body
        send_content = content
        send_params = params
        transforms: list[str] = []
        blocked: list[str] = []
        digest = ""

        try:
            if protect_json and json_body is not None:
                ct = ContentType.CHAT_MESSAGES if (
                    isinstance(json_body, dict) and isinstance(json_body.get("messages"), list)
                ) else ContentType(str(content_type))
                if ct == ContentType.CHAT_MESSAGES and isinstance(json_body, dict):
                    # Protect messages (+ leave model/tools structure)
                    body = dict(json_body)
                    protected = await self.protect(
                        channel=ch,
                        content_type=ContentType.CHAT_MESSAGES,
                        payload=body.get("messages") or [],
                        context=ctx,
                        session=session,
                        policy=pol,
                        destination_class=destination_class,
                    )
                    if not protected.allowed:
                        raise EgressDeniedError(protected.fail_closed_reason or "protect_denied")
                    body["messages"] = protected.payload
                    # Tool definitions are schemas — scrub any accidental secrets in descriptions
                    if "tools" in body and body["tools"] is not None:
                        scrubbed_tools, t_res = await self._protect_generic(
                            body["tools"], pol, ctx, ch
                        )
                        body["tools"] = scrubbed_tools
                        transforms.extend(t_res.transforms)
                    send_json = body
                    transforms.extend(protected.transforms_applied)
                    blocked.extend(protected.blocked_fields)
                    digest = protected.content_digest
                else:
                    protected = await self.protect(
                        channel=ch,
                        content_type=ct if ct != ContentType.CHAT_MESSAGES else ContentType.JSON,
                        payload=json_body,
                        context=ctx,
                        session=session,
                        policy=pol,
                        destination_class=destination_class,
                    )
                    if not protected.allowed:
                        raise EgressDeniedError(protected.fail_closed_reason or "protect_denied")
                    send_json = protected.payload
                    transforms = protected.transforms_applied
                    blocked = protected.blocked_fields
                    digest = protected.content_digest
            elif content is not None:
                protected = await self.protect(
                    channel=ch,
                    content_type=ContentType.MARKDOWN
                    if content_type == ContentType.MARKDOWN
                    else ContentType.PLAIN_TEXT,
                    payload=content,
                    context=ctx,
                    session=session,
                    policy=pol,
                )
                if not protected.allowed:
                    raise EgressDeniedError(protected.fail_closed_reason or "protect_denied")
                send_content = str(protected.payload)
                transforms = protected.transforms_applied
                blocked = protected.blocked_fields
                digest = protected.content_digest
            elif params is not None:
                protected = await self.protect(
                    channel=ch,
                    content_type=ContentType.QUERY_PARAMS,
                    payload=params,
                    context=ctx,
                    session=session,
                    policy=pol,
                )
                if not protected.allowed:
                    raise EgressDeniedError(protected.fail_closed_reason or "protect_denied")
                send_params = protected.payload
                transforms = protected.transforms_applied
                blocked = protected.blocked_fields
                digest = protected.content_digest
            else:
                # Headers-only / empty body still requires channel enable + URL checks
                if pol.pseudonym_secret is None and ch in {
                    EgressChannel.LLM,
                    EgressChannel.WECOM,
                    EgressChannel.EMBED,
                    EgressChannel.WEBHOOK,
                }:
                    raise EgressDeniedError("pseudonym_secret_missing")
        except EgressDeniedError as exc:
            self._record_audit(
                EgressAuditRecord(
                    channel=ch.value,
                    destination=_safe_destination(url),
                    policy_version=pol.policy_version,
                    decision="deny",
                    transforms_applied=transforms,
                    blocked_fields=blocked,
                    content_digest=digest,
                    correlation_id=ctx.correlation_id,
                )
            )
            raise
        except Exception as exc:
            self._record_audit(
                EgressAuditRecord(
                    channel=ch.value,
                    destination=_safe_destination(url),
                    policy_version=pol.policy_version,
                    decision="failure",
                    transforms_applied=transforms,
                    blocked_fields=blocked,
                    content_digest=digest,
                    correlation_id=ctx.correlation_id,
                )
            )
            raise EgressDeniedError(f"protect_failed: {exc}") from exc

        safe_headers = dict(headers or {})
        # Never log Authorization; ensure we don't copy secrets into audit

        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                response = await client.request(
                    method.upper(),
                    url,
                    headers=safe_headers,
                    json=send_json,
                    params=send_params,
                    content=send_content,
                )
        except EgressDeniedError:
            raise
        except Exception as exc:
            self._record_audit(
                EgressAuditRecord(
                    channel=ch.value,
                    destination=_safe_destination(url),
                    policy_version=pol.policy_version,
                    decision="failure",
                    transforms_applied=transforms,
                    blocked_fields=blocked,
                    content_digest=digest,
                    correlation_id=ctx.correlation_id,
                )
            )
            # Network failure after protect — do not retry with raw payload
            raise EgressDeniedError(f"transport_failed: {exc}") from exc

        self._record_audit(
            EgressAuditRecord(
                channel=ch.value,
                destination=_safe_destination(url),
                policy_version=pol.policy_version,
                decision="allow",
                transforms_applied=transforms,
                blocked_fields=blocked,
                content_digest=digest,
                correlation_id=ctx.correlation_id,
            )
        )
        return response

    async def send_vendor_credential(
        self,
        *,
        channel: EgressChannel | str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
        timeout: float = 30.0,
        policy: PrivacyPolicy | None = None,
        context: EgressContext | None = None,
    ) -> httpx.Response:
        """Channel-gated vendor auth (e.g. WeCom gettoken).

        Credential query params must not pass through PII transformers (would break auth).
        Still fail-closed on disabled channel; audits destination without secret values.
        """
        ctx = context or EgressContext()
        ch = EgressChannel(str(channel))
        try:
            pol = policy or await load_privacy_policy(session)
        except Exception as exc:
            raise EgressDeniedError(f"policy_load_failed: {exc}") from exc
        if not pol.channel_enabled(ch.value):
            self._record_audit(
                EgressAuditRecord(
                    channel=ch.value,
                    destination=_safe_destination(url),
                    policy_version=pol.policy_version,
                    decision="deny",
                    transforms_applied=[],
                    blocked_fields=["vendor_credential"],
                    content_digest="",
                    correlation_id=ctx.correlation_id,
                )
            )
            raise EgressDeniedError(f"channel_disabled:{ch.value}")

        # Audit stub only — never log corpsecret/token values
        self._record_audit(
            EgressAuditRecord(
                channel=ch.value,
                destination=_safe_destination(url),
                policy_version=pol.policy_version,
                decision="allow",
                transforms_applied=["vendor_credential_passthrough"],
                blocked_fields=[],
                content_digest="",
                correlation_id=ctx.correlation_id,
            )
        )
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
                return await client.request(
                    method.upper(),
                    url,
                    headers=dict(headers or {}),
                    params=params,
                )
        except Exception as exc:
            raise EgressDeniedError(f"transport_failed: {exc}") from exc

    async def _protect_generic(
        self,
        payload: Any,
        pol: PrivacyPolicy,
        ctx: EgressContext,
        ch: EgressChannel,
    ) -> tuple[Any, TransformResult]:
        if pol.pseudonym_secret is None:
            raise EgressDeniedError("pseudonym_secret_missing")
        scope = self._scope(pol, ctx)
        pseudo = Pseudonymizer(pol.pseudonym_secret, key_version=pol.policy_version)
        transformer = EgressTransformer(
            pseudonymizer=pseudo,
            scope=scope,
            channel=ch.value,
            allow_public_ip_plaintext=pol.allow_public_ip_plaintext,
            allow_username_plaintext=pol.allow_username_plaintext,
            allow_hostname_plaintext=pol.allow_hostname_plaintext,
            allow_full_url=pol.allow_full_url,
            allow_consent_plaintext=pol.allow_consent_plaintext,
            wecom_allow_host_user=pol.wecom_allow_host_user,
        )
        result = TransformResult()
        out = transformer.transform_value(None, payload, result)
        return out, result

    def _assert_llm_url_allowed(self, url: str, pol: PrivacyPolicy) -> None:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if pol.strict_mode:
            if not pol.allowed_llm_base_urls:
                raise EgressDeniedError("strict_mode_requires_llm_allowlist")
            allowed = {u.rstrip("/") for u in pol.allowed_llm_base_urls}
            if base not in allowed and url.rstrip("/") not in allowed:
                # also allow prefix match of configured bases
                if not any(url.startswith(a) or base == a for a in allowed):
                    raise EgressDeniedError(f"llm_url_not_allowlisted:{base}")
        # BYO still must use gateway — no bypass; non-strict allows any https URL
        if parsed.scheme not in {"http", "https"}:
            raise EgressDeniedError("llm_url_scheme_invalid")

    def _scope(self, pol: PrivacyPolicy, ctx: EgressContext) -> str:
        customer = ctx.scope_id or pol.customer_scope_id or "default"
        if pol.pseudonym_scope_mode == "tenant":
            return customer
        inv = ctx.investigation_id or "no-investigation"
        return f"{customer}|{inv}"

    def _deny(
        self,
        pol: PrivacyPolicy,
        ch: EgressChannel,
        *,
        destination: str,
        reason: str,
        correlation_id: str | None,
        transforms: list[str] | None = None,
        blocked: list[str] | None = None,
    ) -> ProtectedPayload:
        self._record_audit(
            EgressAuditRecord(
                channel=ch.value,
                destination=destination or "(none)",
                policy_version=pol.policy_version,
                decision="deny",
                transforms_applied=transforms or [],
                blocked_fields=blocked or [],
                content_digest="",
                correlation_id=correlation_id,
            )
        )
        return ProtectedPayload(
            payload=None,
            policy_id=pol.policy_id,
            policy_version=pol.policy_version,
            transforms_applied=transforms or [],
            blocked_fields=blocked or [],
            content_digest="",
            fail_closed_reason=reason,
            allowed=False,
        )

    def _record_audit(self, record: EgressAuditRecord) -> None:
        if self._audit_sink is not None:
            self._audit_sink.append(record)
        # Structured log without sensitive payload
        logger.info(
            "egress_audit channel=%s dest=%s decision=%s policy_v=%s digest=%s transforms=%s blocked=%s corr=%s",
            record.channel,
            record.destination,
            record.decision,
            record.policy_version,
            record.content_digest[:16] if record.content_digest else "",
            ",".join(record.transforms_applied[:12]),
            ",".join(record.blocked_fields[:12]),
            record.correlation_id or "",
        )


_gateway: EgressGateway | None = None


def get_egress_gateway() -> EgressGateway:
    global _gateway
    if _gateway is None:
        _gateway = EgressGateway()
    return _gateway


def set_egress_gateway(gateway: EgressGateway | None) -> None:
    """Test helper to inject mock transport gateway."""
    global _gateway
    _gateway = gateway


def _safe_destination(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path}"
    except Exception:
        return "(invalid-url)"


def _digest(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _find_residual_secrets(payload: Any) -> list[str]:
    """Best-effort scan for leaked secrets after transform."""
    text = json.dumps(payload, ensure_ascii=False, default=str)
    hits: list[str] = []
    if re.search(r"Bearer\s+(?!\[REDACTED_SECRET\])\S{8,}", text, re.I):
        hits.append("bearer_token")
    if re.search(
        r"(?i)\b(api[_-]?key|password|secret)\b\s*[:=]\s*(?!\[REDACTED_SECRET\])([^\s,;\"']{8,})",
        text,
    ):
        hits.append("api_key_assignment")
    return hits
