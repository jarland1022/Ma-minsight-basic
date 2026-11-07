"""Field classification and payload transformation for egress."""

from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.privacy.pseudonym import Pseudonymizer
from app.privacy.types import FieldClass

_SECRET_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "authorization",
    "jwt",
    "bearer",
    "mfa_secret",
    "totp",
    "credential",
    "webhook_secret",
    "encoding_aes_key",
    "deepseek_api_key",
    "openai_api_key",
    "client_secret",
    "refresh_token",
    "session_id",
    "corpsecret",
)

_BEARER_RE = re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE)
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|password|secret|token|authorization)\b(\s*[:=]\s*)([^\s,;\"']+)"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")
_JWT_LIKE_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")

_REDACTED_SECRET = "[REDACTED_SECRET]"

# Structured keys known to the product (safe classification).
_PII_KEYS = {
    "user_name",
    "username",
    "user",
    "dstuser",
    "srcuser",
    "aggregate_user_name",
    "host_name",
    "hostname",
    "host",
    "agent_name",
    "aggregate_host_name",
    "src_ip",
    "dst_ip",
    "ip",
    "ip_address",
    "ipaddress",
    "request_url",
    "url",
    "full_log",
    "email",
}
_ANALYTIC_KEYS = {
    "rule_id",
    "rule_name",
    "severity",
    "category",
    "alert_category",
    "primary_category",
    "risk_score",
    "queue_priority",
    "triage_rule_score",
    "triage_route",
    "event_id",
    "title",
    "occurred_at",
    "alert_count",
    "src_geo",
    "location",
    "verdict",
    "confidence",
    "model",
    "temperature",
    "tool_choice",
}
_CONSENT_KEYS = {
    "guidance_text",
    "reasoning",
    "human_query",
    "raw_content",
    "parsed_content",
    "feature_summary",
    "reference_cases",
    "sop",
}


def classify_key(key: str) -> FieldClass:
    lowered = key.lower().replace("-", "_")
    if any(frag in lowered for frag in _SECRET_KEY_FRAGMENTS):
        return FieldClass.SECRET_NEVER
    if lowered in _PII_KEYS or any(
        lowered.endswith(f"_{k}") or lowered.startswith(f"{k}_") for k in ("user", "host", "ip", "url")
    ):
        # Refine known analytics
        if lowered in _ANALYTIC_KEYS:
            return FieldClass.ANALYTIC_ALLOWED
        return FieldClass.PII_DEFAULT
    if lowered in _ANALYTIC_KEYS:
        return FieldClass.ANALYTIC_ALLOWED
    if lowered in _CONSENT_KEYS:
        return FieldClass.CONSENT_REQUIRED
    return FieldClass.UNKNOWN


def _is_private_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value.strip()).is_private
    except ValueError:
        return False


def _is_public_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value.strip())
        return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)
    except ValueError:
        return False


class TransformResult:
    def __init__(self) -> None:
        self.transforms: list[str] = []
        self.blocked: list[str] = []
        self.class_counts: dict[str, int] = {}
        self.secret_hit = False
        self.unknown_blocked = False

    def note_class(self, fc: FieldClass) -> None:
        self.class_counts[fc.value] = self.class_counts.get(fc.value, 0) + 1


class EgressTransformer:
    def __init__(
        self,
        *,
        pseudonymizer: Pseudonymizer,
        scope: str,
        channel: str,
        allow_public_ip_plaintext: bool = False,
        allow_username_plaintext: bool = False,
        allow_hostname_plaintext: bool = False,
        allow_full_url: bool = False,
        allow_consent_plaintext: bool = False,
        wecom_allow_host_user: bool = False,
        fail_on_unknown: bool = True,
    ) -> None:
        self.pseudo = pseudonymizer
        self.scope = scope or "global"
        self.channel = channel
        self.allow_public_ip_plaintext = allow_public_ip_plaintext
        self.allow_username_plaintext = allow_username_plaintext
        self.allow_hostname_plaintext = allow_hostname_plaintext
        self.allow_full_url = allow_full_url
        self.allow_consent_plaintext = allow_consent_plaintext
        self.wecom_allow_host_user = wecom_allow_host_user
        self.fail_on_unknown = fail_on_unknown

    def transform_value(self, key: str | None, value: Any, result: TransformResult) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return self.transform_mapping(value, result)
        if isinstance(value, list):
            return [self.transform_value(key, item, result) for item in value]
        if isinstance(value, tuple):
            return tuple(self.transform_value(key, item, result) for item in value)
        if not isinstance(value, str):
            if key:
                fc = classify_key(key)
                result.note_class(fc)
                if fc == FieldClass.SECRET_NEVER:
                    result.secret_hit = True
                    result.blocked.append(key)
                    return _REDACTED_SECRET
                if fc == FieldClass.UNKNOWN and self.fail_on_unknown:
                    # Non-string unknown under unknown key: keep numeric analytics only
                    if isinstance(value, (int, float, bool)):
                        result.note_class(FieldClass.ANALYTIC_ALLOWED)
                        return value
                    result.unknown_blocked = True
                    result.blocked.append(key or "<unknown>")
                    return "[BLOCKED_UNKNOWN]"
            return value

        fc = classify_key(key) if key else FieldClass.UNKNOWN
        result.note_class(fc)

        if fc == FieldClass.SECRET_NEVER:
            result.secret_hit = True
            result.blocked.append(key or "secret")
            result.transforms.append("redact:secret_key")
            return _REDACTED_SECRET

        # Channel-specific IP handling for TI: public IP plaintext allowed
        if self.channel == "ti" and key and "ip" in key.lower():
            if _is_public_ip(value):
                result.transforms.append("allow:ti_public_ip")
                return value
            result.transforms.append("block:ti_private_ip")
            result.blocked.append(key)
            return "[PRIVATE_IP]"

        if fc == FieldClass.PII_DEFAULT or (key and key.lower() in _PII_KEYS):
            return self._transform_pii(key or "pii", value, result)

        if fc == FieldClass.CONSENT_REQUIRED:
            if self.allow_consent_plaintext:
                result.transforms.append("allow:consent")
                return self._scrub_secrets_in_text(value, result)
            # Soft-minimize: scrub secrets + PII patterns in free text
            result.transforms.append("minimize:consent_text")
            return self._scrub_free_text(value, result)

        if fc == FieldClass.ANALYTIC_ALLOWED:
            return self._scrub_secrets_in_text(value, result)

        # UNKNOWN
        if self.fail_on_unknown:
            # Free-text content fields (message bodies) — scrub rather than hard-fail entire message
            if key in {None, "content", "arguments", "markdown", "input", "detail", "title", "text"}:
                result.transforms.append("scrub:unknown_text")
                return self._scrub_free_text(value, result)
            result.unknown_blocked = True
            result.blocked.append(key or "<unknown>")
            result.transforms.append("block:unknown_field")
            return "[BLOCKED_UNKNOWN]"

        return self._scrub_free_text(value, result)

    def transform_mapping(self, data: dict[str, Any], result: TransformResult) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in data.items():
            out[str(k)] = self.transform_value(str(k), v, result)
        return out

    def transform_messages(self, messages: list[dict[str, Any]], result: TransformResult) -> list[dict[str, Any]]:
        protected: list[dict[str, Any]] = []
        for msg in messages:
            item = dict(msg)
            if "content" in item and item["content"] is not None:
                item["content"] = self.transform_value("content", item["content"], result)
            if "tool_calls" in item and item["tool_calls"]:
                calls = []
                for call in item["tool_calls"]:
                    c = dict(call)
                    fn = dict(c.get("function") or {})
                    if "arguments" in fn:
                        args = fn["arguments"]
                        if isinstance(args, str):
                            try:
                                parsed = json.loads(args)
                                protected_args = self.transform_value("arguments", parsed, result)
                                fn["arguments"] = json.dumps(protected_args, ensure_ascii=False)
                            except json.JSONDecodeError:
                                fn["arguments"] = self.transform_value("arguments", args, result)
                        else:
                            fn["arguments"] = self.transform_value("arguments", args, result)
                    c["function"] = fn
                    calls.append(c)
                item["tool_calls"] = calls
            protected.append(item)
        return protected

    def _transform_pii(self, key: str, value: str, result: TransformResult) -> str:
        kl = key.lower()
        if self.channel == "wecom" and self.wecom_allow_host_user and (
            "user" in kl or "host" in kl
        ):
            result.transforms.append("allow:wecom_host_user")
            return self._scrub_secrets_in_text(value, result)

        if "url" in kl or kl == "request_url":
            if self.allow_full_url:
                result.transforms.append("allow:full_url")
                return self._scrub_secrets_in_text(value, result)
            result.transforms.append("redact:url_query")
            return self._minimize_url(value)

        if "user" in kl or "email" in kl:
            if self.allow_username_plaintext:
                result.transforms.append("allow:username")
                return value
            result.transforms.append("pseudonym:user")
            kind = "email" if "@" in value else "user"
            return self.pseudo.pseudonymize(value, field_kind=kind, scope=self.scope)

        if "host" in kl:
            if self.allow_hostname_plaintext:
                result.transforms.append("allow:hostname")
                return value
            result.transforms.append("pseudonym:host")
            return self.pseudo.pseudonymize(value, field_kind="host", scope=self.scope)

        if "ip" in kl:
            if _is_private_ip(value) or not _is_public_ip(value):
                result.transforms.append("pseudonym:private_ip")
                return self.pseudo.pseudonymize(value, field_kind="ip", scope=self.scope)
            if self.allow_public_ip_plaintext:
                result.transforms.append("allow:public_ip")
                return value
            result.transforms.append("pseudonym:public_ip")
            return self.pseudo.pseudonymize(value, field_kind="ip", scope=self.scope)

        if "full_log" in kl:
            result.transforms.append("redact:full_log")
            return "[REDACTED_FULL_LOG]"

        result.transforms.append("pseudonym:generic")
        return self.pseudo.pseudonymize(value, field_kind="generic", scope=self.scope)

    def _minimize_url(self, value: str) -> str:
        try:
            parsed = urlparse(value)
            # Drop query/fragment; keep scheme + netloc + path template lightly
            path = parsed.path or "/"
            # Mask path segments that look like tokens
            parts = [
                "[id]" if re.fullmatch(r"[0-9a-fA-F-]{8,}", seg) or "@" in seg else seg
                for seg in path.split("/")
            ]
            safe_path = "/".join(parts)
            return urlunparse((parsed.scheme, parsed.netloc, safe_path, "", "", ""))
        except Exception:
            return "[REDACTED_URL]"

    def _scrub_secrets_in_text(self, value: str, result: TransformResult) -> str:
        out = _BEARER_RE.sub(r"\1" + _REDACTED_SECRET, value)
        out = _KEY_VALUE_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED_SECRET}", out)
        out = _JWT_LIKE_RE.sub(_REDACTED_SECRET, out)
        if out != value:
            result.transforms.append("redact:secret_pattern")
            result.secret_hit = True
        return out

    def _scrub_free_text(self, value: str, result: TransformResult) -> str:
        out = self._scrub_secrets_in_text(value, result)

        def _email_sub(m: re.Match[str]) -> str:
            result.transforms.append("pseudonym:email_in_text")
            return self.pseudo.pseudonymize(m.group(0), field_kind="email", scope=self.scope)

        out = _EMAIL_RE.sub(_email_sub, out)

        def _ip_sub(m: re.Match[str]) -> str:
            ip = m.group(0)
            if self.channel == "ti" and _is_public_ip(ip):
                return ip
            if self.allow_public_ip_plaintext and _is_public_ip(ip):
                return ip
            result.transforms.append("pseudonym:ip_in_text")
            return self.pseudo.pseudonymize(ip, field_kind="ip", scope=self.scope)

        out = _IPV4_RE.sub(_ip_sub, out)

        # Host / user labels common in prompts: "host: X" / "user: Y"
        def _labeled(m: re.Match[str]) -> str:
            label, raw = m.group(1), m.group(2).strip()
            if not raw or raw in {"-", "None", "null"}:
                return m.group(0)
            if self.channel == "wecom" and self.wecom_allow_host_user:
                return m.group(0)
            kind = "host" if label.lower().startswith("host") else "user"
            if kind == "user" and self.allow_username_plaintext:
                return m.group(0)
            if kind == "host" and self.allow_hostname_plaintext:
                return m.group(0)
            result.transforms.append(f"pseudonym:{kind}_label")
            return f"{label}{self.pseudo.pseudonymize(raw, field_kind=kind, scope=self.scope)}"

        out = re.sub(
            r"(?i)\b(host|主机|user|用户)\s*[:=：]\s*([^\s|,;，]+)",
            _labeled,
            out,
        )
        # Markdown WeCom lines: **主机** foo | **用户** bar
        def _md_host_user(m: re.Match[str]) -> str:
            label, raw = m.group(1), m.group(2).strip()
            if self.wecom_allow_host_user:
                return m.group(0)
            kind = "host" if "主机" in label or "host" in label.lower() else "user"
            result.transforms.append(f"pseudonym:md_{kind}")
            return f"{label} {self.pseudo.pseudonymize(raw, field_kind=kind, scope=self.scope)}"

        out = re.sub(r"(\*\*主机\*\*|\*\*Host\*\*)\s+([^\s|]+)", _md_host_user, out, flags=re.I)
        out = re.sub(r"(\*\*用户\*\*|\*\*User\*\*)\s+([^\s|]+)", _md_host_user, out, flags=re.I)
        return out
