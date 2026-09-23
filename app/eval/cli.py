"""Evaluation CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.db.session import async_session_factory
from app.eval.health_check.runner import HealthCheckRunner
from app.eval.regression.runner import RegressionRunner
from app.models.cache_eval import RegressionTestCase
from app.db.enums import InvestigationVerdict


async def _run_regression(args: argparse.Namespace) -> int:
    async with async_session_factory() as session:
        runner = RegressionRunner(session)
        result = await runner.run(
            trigger="cli",
            tag=args.tag,
            use_real_llm=args.real_llm,
            use_lock=not args.no_lock,
        )
        print(
            json.dumps(
                {
                    "run_id": str(result.run_id) if result.run_id else None,
                    "total": result.total,
                    "passed": result.passed,
                    "failed": result.failed,
                    "errors": result.errors,
                },
                ensure_ascii=False,
            )
        )
        return 0 if result.failed == 0 and not result.errors else 1


async def _run_health_check(args: argparse.Namespace) -> int:
    async with async_session_factory() as session:
        runner = HealthCheckRunner(session)
        result = await runner.run(
            scenario_id=args.scenario_id,
            trigger="cli",
            use_lock=not args.no_lock,
        )
        print(
            json.dumps(
                {
                    "total": result.total,
                    "passed": result.passed,
                    "failed": result.failed,
                    "errors": result.errors,
                },
                ensure_ascii=False,
            )
        )
        return 0 if result.failed == 0 and not result.errors else 1


async def _import_cases(path: str) -> int:
    async with async_session_factory() as session:
        imported = 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                session.add(
                    RegressionTestCase(
                        name=data["name"],
                        alert_payload=data["alert_payload"],
                        expected_verdict=InvestigationVerdict(data["expected_verdict"]),
                        expected_skills=data.get("expected_skills", []),
                        forbidden_skills=data.get("forbidden_skills"),
                        tags=data.get("tags", []),
                        is_active=data.get("is_active", True),
                    )
                )
                imported += 1
        await session.commit()
        print(json.dumps({"imported": imported}))
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.eval.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser("regression")
    reg_sub = reg.add_subparsers(dest="reg_cmd", required=True)
    run_p = reg_sub.add_parser("run")
    run_p.add_argument("--tag")
    run_p.add_argument("--real-llm", action="store_true")
    run_p.add_argument("--no-lock", action="store_true")

    imp_p = reg_sub.add_parser("import")
    imp_p.add_argument("--file", required=True)

    hc = sub.add_parser("health-check")
    hc_sub = hc.add_subparsers(dest="hc_cmd", required=True)
    hc_run = hc_sub.add_parser("run")
    hc_run.add_argument("--all", action="store_true")
    hc_run.add_argument("--scenario-id")
    hc_run.add_argument("--no-lock", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "regression" and args.reg_cmd == "run":
        return asyncio.run(_run_regression(args))
    if args.command == "regression" and args.reg_cmd == "import":
        return asyncio.run(_import_cases(args.file))
    if args.command == "health-check" and args.hc_cmd == "run":
        from uuid import UUID

        args.scenario_id = UUID(args.scenario_id) if args.scenario_id else None
        return asyncio.run(_run_health_check(args))
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
