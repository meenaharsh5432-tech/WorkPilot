import json
import time
from sqlalchemy.orm import Session
from app.tools.approval_tools import request_invoice_approval
from app.tools.report_tools import get_overdue_invoice_report
from app.models import ExecutionStep
from app.tools.invoice_tools import (
    search_invoices,
    extract_invoice_fields
)
from app.tools.finance_tools import (
    save_invoice,
    get_invoice
)

from app.tools.company_tools import find_similar_companies

from sqlalchemy.exc import OperationalError

def run_with_retry(
    operation,
    tool_name,
    max_attempts=2,
    on_retry=None
):
    safe_retry_tools = {"get_invoice"}

    if tool_name not in safe_retry_tools:
        return operation()

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()

        except OperationalError as exc:
            if attempt == max_attempts:
                raise

            if on_retry:
                on_retry(attempt, str(exc))

            time.sleep(0.3 * attempt)


def execute_tool(
    db: Session,
    task_id: int,
    step_number: int,
    tool_name: str,
    arguments: dict
):
   
    allowed_tools = {
    "search_invoices": search_invoices,
    "extract_invoice_fields": extract_invoice_fields,
    "save_invoice": save_invoice,
    "get_invoice": get_invoice,
    "request_invoice_approval": request_invoice_approval,
    "find_similar_companies": find_similar_companies,
    "get_overdue_invoice_report": get_overdue_invoice_report,
}

    step = ExecutionStep(
        task_id=task_id,
        step_number=step_number,
        tool_name=tool_name,
        input_data=json.dumps(arguments),
        status="running"
    )

    db.add(step)
    db.commit()
    db.refresh(step)

    try:
        if tool_name not in allowed_tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = allowed_tools[tool_name]

        # Database tools need a session
        if tool_name == "request_invoice_approval":
            result = tool(
                db=db,
                task_id=task_id,
                invoice_id=arguments["invoice_id"]
            )

        elif tool_name == "get_invoice":
            retry_events = []

            def record_retry(attempt, error):
                retry_events.append({
                    "attempt": attempt,
                    "error": error,
                    "action": "retry"
                })

            result = run_with_retry(
                operation=lambda: tool(db=db, **arguments),
                tool_name="get_invoice",
                max_attempts=2,
                on_retry=record_retry
            )

        elif tool_name == "save_invoice":
            result = tool(db=db, **arguments)

        elif tool_name == "get_overdue_invoice_report":
            result = tool(db=db)

        else:
            result = tool(**arguments)

        step.status = "completed"
        step.output_data = json.dumps({
    "result": result,
    "retry_events": (
        retry_events if tool_name == "get_invoice" else []
    )
})

        response = {
            "success": True,
            "tool": tool_name,
            "result": result
        }

    except Exception as exc:
        # Clear session error state after a database failure
        db.rollback()

        step.status = "failed"
        step.error_message = str(exc)

        response = {
            "success": False,
            "tool": tool_name,
            "error": str(exc)
        }

    db.add(step)
    db.commit()

    return response
