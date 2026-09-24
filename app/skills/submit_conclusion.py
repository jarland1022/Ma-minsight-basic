"""submit_conclusion tool schema (handled by AgentLoop, not SkillRegistry.execute)."""

from __future__ import annotations

from typing import Any

SUBMIT_CONCLUSION_NAME = "submit_conclusion"


def submit_conclusion_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_CONCLUSION_NAME,
            "description": (
                "Submit final structured investigation conclusion. "
                "attack_confirmed requires evidence_strength=multi_path (two independent evidence paths). "
                "Disposition actions are suggestions only."
            ),
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
                    "evidence_strength": {
                        "type": "string",
                        "enum": ["none", "single_path", "multi_path"],
                        "description": (
                            "none=no solid path; single_path=one evidence path only; "
                            "multi_path=at least two independent paths (timeline/TI/sample/playbook+alerts)"
                        ),
                    },
                    "disposition_grade": {
                        "type": "string",
                        "enum": [
                            "confirmed_compromise",
                            "suspicious",
                            "false_positive",
                            "needs_more_evidence",
                        ],
                        "description": "Analyst-facing grade aligned with disposition triage table",
                    },
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
