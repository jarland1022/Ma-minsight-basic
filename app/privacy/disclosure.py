"""Customer-facing data-flow disclosure (P0-06-A). Not a marketing air-gap claim."""

from __future__ import annotations

from typing import Any

from app.privacy.config import POLICY_ID, POLICY_VERSION, PrivacyPolicy


DISCLOSURE_VERSION = "1.0.0"


def build_data_flow_disclosure(policy: PrivacyPolicy | None = None) -> dict[str, Any]:
    """Structured disclosure for admins / API. Safe defaults; no air-gap guarantee."""
    pol = policy
    return {
        "disclosure_version": DISCLOSURE_VERSION,
        "policy_id": (pol.policy_id if pol else POLICY_ID),
        "policy_version": (pol.policy_version if pol else POLICY_VERSION),
        "disclaimer": (
            "On-premises deployment does not mean security data never leaves the environment. "
            "Outbound transmission depends on configured integrations and privacy.* switches. "
            "BYO LLM endpoint is still an external processing destination unless the endpoint "
            "is proven to remain inside the customer trust boundary. "
            "Pseudonymization is not anonymization."
        ),
        "air_gap_claim_supported": False,
        "field_classes": {
            "SECRET_NEVER": {
                "meaning": "API keys, passwords, tokens, private keys — never egress in body",
                "default_action": "redact_or_deny",
            },
            "PII_DEFAULT": {
                "meaning": "usernames, hostnames, private IPs, URL query — default pseudonymize/mask",
                "default_action": "pseudonymize",
            },
            "ANALYTIC_ALLOWED": {
                "meaning": "rule id/name, severity, category, risk scores — may egress for analysis",
                "default_action": "allow",
            },
            "CONSENT_REQUIRED": {
                "meaning": "full URLs, rich HR/SOP text — minimized unless explicitly allowed",
                "default_action": "minimize",
            },
        },
        "channels": [
            {
                "id": "llm",
                "name": "LLM chat completions",
                "enabled": None if pol is None else pol.llm_egress_enabled,
                "destinations": ["DEEPSEEK_BASE_URL / OpenAI-compatible /chat/completions"],
                "may_include": [
                    "derived alert fields (rule, severity, pseudonymized host/user/ip/url)",
                    "SOP guidance (minimized)",
                    "Human Review replies (minimized)",
                    "tool call summaries (protected)",
                ],
                "never_includes": ["API keys in JSON body", "raw password material"],
                "byo_note": "Custom base URL does not bypass EgressGateway protection.",
                "disable": "PRIVACY_LLM_EGRESS_ENABLED=false or privacy.llm_egress_enabled=false or empty API key",
            },
            {
                "id": "ti",
                "name": "Threat intelligence",
                "enabled": None if pol is None else pol.ti_egress_enabled,
                "destinations": ["api.abuseipdb.com", "api.greynoise.io"],
                "may_include": ["public IP indicators only"],
                "never_includes": ["usernames", "hostnames", "full alert JSON"],
                "disable": "PRIVACY_TI_EGRESS_ENABLED=false or omit provider API keys",
            },
            {
                "id": "wecom",
                "name": "WeCom human review",
                "enabled": None if pol is None else pol.wecom_egress_enabled,
                "destinations": ["qyapi.weixin.qq.com", "configured webhook URL"],
                "may_include": [
                    "event title/category/risk",
                    "verdict label",
                    "human_query (minimized)",
                    "host/user only if privacy.wecom.allow_host_user (default false → pseudonymized)",
                ],
                "disable": "PRIVACY_WECOM_EGRESS_ENABLED=false or leave WeCom unset",
            },
            {
                "id": "embed",
                "name": "Embeddings API",
                "enabled": None if pol is None else pol.embed_egress_enabled,
                "destinations": ["OPENAI_BASE_URL /embeddings"],
                "may_include": ["judgment case / query text after protection"],
                "default": "disabled",
                "disable": "privacy.embed_egress_enabled=false (default) or empty embedding keys",
            },
            {
                "id": "webhook",
                "name": "Eval / alert webhooks",
                "enabled": None if pol is None else pol.webhook_egress_enabled,
                "destinations": ["eval.alert_webhook_url"],
                "may_include": ["failure title/detail after protection"],
                "disable": "unset URL or privacy.webhook_egress_enabled=false",
            },
        ],
        "local_only": [
            "PostgreSQL investigation records (authoritative store)",
            "Redis caches/locks",
            "GeoLite2 local mmdb (when configured)",
            "Wazuh Indexer pull (customer infrastructure ingress)",
        ],
        "channel_switches_backend_enforced": True,
        "frontend_cannot_override": True,
    }
