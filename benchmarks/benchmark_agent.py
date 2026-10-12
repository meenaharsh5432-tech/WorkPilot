"""WorkPilot's isolated, sequential, real-LLM agent benchmark.

Run from the WorkPilot repository root:
    python -m benchmarks.benchmark_agent
"""

import json
import tempfile
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.agent import executor, reasoning
from app.database import Base
from app.models import ApprovalRequest, ExecutionStep, Invoice, Task
from app.tools import invoice_tools

INVOICE_TEXT = """INVOICE
Company: Acme Corporation
Invoice Number: ACM-002
Invoice Date: 2026-10-05
Due Date: 2026-11-05
Amount: 18750.00
Currency: INR
"""

SCENARIOS = [
    {
        "name": "Normal invoice processing",
        "request": "Find the latest Acme invoice, extract it, save it and verify the database record.",
        "expected_status": "completed",
        "preseed": False,
        "approval": False,
    },
    {
        "name": "Case-insensitive company request",
        "request": "Find the latest aCmE invoice, save its details and verify the result.",
        "expected_status": "completed",
        "preseed": False,
        "approval": False,
    },
    {
        "name": "Duplicate invoice protection",
        "request": "Find the latest Acme invoice, save it without duplication and verify it.",
        "expected_status": "completed",
        "preseed": True,
        "approval": False,
    },
    {
        "name": "Unknown company",
        "request": "Find the latest UnknownCorp invoice, save it and verify the result.",
        "expected_status": "needs_input",
        "preseed": False,
        "approval": False,
    },
    {
        "name": "Human approval gate",
        "request": (
            "Find the latest Acme invoice, save it, and request human approval "
            "for payment. Do not approve it yourself."
        ),
        "expected_status": "awaiting_approval",
        "preseed": False,
        "approval": True,
    },
    {
        "name": "Transient database failure recovery",
        "request": (
            "Find the latest Acme invoice, save its details in the finance "
            "database, and verify that the saved information is correct."
        ),
        "expected_status": "completed",
        "preseed": False,
        "approval": False,
        "inject_read_failure": True,
    },
]


def seed_invoice(db):
    db.add(
        Invoice(
            company="Acme Corporation",
            invoice_number="ACM-002",
            invoice_date=date(2026, 10, 5),
            due_date=date(2026, 11, 5),
            amount=Decimal("18750.00"),
            currency="INR",
            payment_approval_status="not_approved",
        )
    )
    db.commit()


def has_recovery_evidence(steps):
    """Inspect actual persisted retry evidence, not just the final task status."""
    for step in steps:
        if step.tool_name != "get_invoice" or step.status != "completed":
            continue
        try:
            output = json.loads(step.output_data or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(output, dict):
            continue
        events = output.get("retry_events", [])
        if (
            isinstance(events, list)
            and len(events) == 1
            and isinstance(events[0], dict)
            and events[0].get("attempt") == 1
            and events[0].get("action") == "retry"
        ):
            return True
    return False


def run_scenario(scenario, root, scenario_index):
    scenario_dir = root / f"case_{scenario_index}"
    scenario_dir.mkdir()
    invoice_dir = scenario_dir / "invoices"
    invoice_dir.mkdir()
    (invoice_dir / "acme_002.txt").write_text(INVOICE_TEXT, encoding="utf-8")

    engine = create_engine(f"sqlite:///{scenario_dir / 'benchmark.db'}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Run sequentially: temporary patches affect module globals in this process.
    original_session = reasoning.SessionLocal
    original_dir = invoice_tools.INVOICE_DIR
    reasoning.SessionLocal = Session
    invoice_tools.INVOICE_DIR = invoice_dir
    started = time.perf_counter()
    failure_state = {"calls": 0}

    try:
        with Session() as db:
            if scenario["preseed"]:
                seed_invoice(db)
            task = Task(user_request=scenario["request"])
            db.add(task)
            db.commit()
            db.refresh(task)
            task_id = task.id

        original_get_invoice = executor.get_invoice

        def unreliable_get_invoice(db, invoice_id):
            failure_state["calls"] += 1
            if failure_state["calls"] == 1:
                raise OperationalError(
                    "SELECT invoice",
                    {},
                    Exception("Simulated temporary database failure"),
                )
            return original_get_invoice(db=db, invoice_id=invoice_id)

        error = None
        try:
            if scenario.get("inject_read_failure", False):
                with patch.object(executor, "get_invoice", side_effect=unreliable_get_invoice):
                    agent_result = reasoning.run_agent(task_id)
            else:
                agent_result = reasoning.run_agent(task_id)
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
            agent_result = {}

        if not isinstance(agent_result, dict):
            agent_result = {}

        with Session() as db:
            task = db.get(Task, task_id)
            invoice_count = db.scalar(select(func.count()).select_from(Invoice))
            invoices = db.scalars(select(Invoice)).all()
            approvals = db.scalars(select(ApprovalRequest)).all()
            steps = db.scalars(
                select(ExecutionStep)
                .where(ExecutionStep.task_id == task_id)
                .order_by(ExecutionStep.step_number)
            ).all()
            tool_names = [step.tool_name for step in steps]
            status_matches = task.status == scenario["expected_status"]

            if scenario["expected_status"] == "needs_input":
                outcome_valid = (
                    invoice_count == 0
                    and len(approvals) == 0
                    and "search_invoices" in tool_names
                )
            else:
                invoice_valid = (
                    invoice_count == 1
                    and invoices[0].invoice_number == "ACM-002"
                    and invoices[0].amount == Decimal("18750.00")
                    and invoices[0].currency == "INR"
                )
                outcome_valid = invoice_valid and agent_result.get("verified") is True

                # This must apply to ALL cases, not just recovery cases.
                if scenario["approval"]:
                    outcome_valid = (
                        outcome_valid
                        and len(approvals) == 1
                        and approvals[0].status == "pending"
                        and invoices[0].payment_approval_status == "not_approved"
                        and "get_invoice" in tool_names
                        and "request_invoice_approval" in tool_names
                        and tool_names.index("get_invoice")
                        < tool_names.index("request_invoice_approval")
                    )
                else:
                    outcome_valid = outcome_valid and len(approvals) == 0

            recovery_verified = None
            if scenario.get("inject_read_failure", False):
                recovery_verified = has_recovery_evidence(steps)
                outcome_valid = (
                    outcome_valid
                    and recovery_verified
                    and failure_state["calls"] == 2
                )

            passed = error is None and status_matches and outcome_valid
            return {
                "scenario": scenario["name"],
                "passed": bool(passed),
                "expected_status": scenario["expected_status"],
                "actual_status": task.status,
                "invoice_count": invoice_count,
                "tool_calls": len(steps),
                "tools": tool_names,
                "duration_seconds": round(time.perf_counter() - started, 2),
                "error": error,
                "agent_verified": agent_result.get("verified"),
                "approval_count": len(approvals),
                "approval_statuses": [a.status for a in approvals],
                "payment_statuses": [i.payment_approval_status for i in invoices],
                "status_matches": status_matches,
                "outcome_valid": bool(outcome_valid),
                "recovery_verified": recovery_verified,
                "read_attempts": (
                    failure_state["calls"]
                    if scenario.get("inject_read_failure", False)
                    else None
                ),
            }
    finally:
        reasoning.SessionLocal = original_session
        invoice_tools.INVOICE_DIR = original_dir
        engine.dispose()


def main():
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for index, scenario in enumerate(SCENARIOS, start=1):
            print(f"\nRunning: {scenario['name']}", flush=True)
            result = run_scenario(scenario, root, index)
            results.append(result)
            label = "PASS" if result["passed"] else "FAIL"
            print(
                f"{label} | status={result['actual_status']} "
                f"| tools={result['tool_calls']} "
                f"| error={result['error']}",
                flush=True,
            )

    count = len(results)
    passing = sum(result["passed"] for result in results)
    report = {
        "total_scenarios": count,
        "passed": passing,
        "failed": count - passing,
        "pass_rate": round(passing / count * 100, 1) if count else 0.0,
        "results": results,
    }
    report_path = Path("benchmark_report.json")
    report_path.write_text(json.dumps(report, indent=4), encoding="utf-8")
    print("\n" + "=" * 50)
    print("WORKPILOT BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Passed: {passing}/{count}")
    print(f"Pass rate: {report['pass_rate']}%")
    print(f"Report: {report_path.resolve()}")


if __name__ == "__main__":
    main()
