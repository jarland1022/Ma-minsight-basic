"""submit_conclusion tool schema (handled by AgentLoop, not SkillRegistry.execute)."""

from __future__ import annotations

from typing import Any

SUBMIT_CONCLUSION_NAME = "submit_conclusion"


def submit_conclusion_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_CONCLUSION_NAME,
            "description": "Submit final structured investigation conclusion. Call when enough evidence is collected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "attack_confirmed",
                            "likely_false_positive",
                            "insufficient_information",
                            "needs_human_review",
                        ],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "risk_level": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                    },
                    "reasoning": {"type": "string"},
                    "recommended_action": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "human_query": {"type": "string"},
                    "missing_info": {"type": "array", "items": {"type": "string"}},
                    "suggested_assets": {"type": "object"},
                    "hypotheses_evaluated": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hypothesis_id": {"type": "string"},
                                "supported": {"type": "boolean"},
                                "note": {"type": "string"},
                            },
                        },
                    },
                    "refutation_summary": {
                        "type": "string",
                        "description": "Summary of counter-evidence considered before concluding",
                    },
                },
                "required": ["verdict", "confidence", "risk_level", "reasoning"],
            },
        },
    }
