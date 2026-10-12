import json

from sqlalchemy.orm import Session

from app.models import ExecutionStep
from app.tools.invoice_tools import (
    search_invoices,
    extract_invoice_fields
)
from app.tools.finance_tools import (
    save_invoice,
    get_invoice
)


def execute_tool(
    db: Session,
    task_id: int,
    step_number: int,
    tool_name: str,
    arguments: dict
):
    # Only these tools are allowed
    allowed_tools = {
        "search_invoices": search_invoices,
        "extract_invoice_fields": extract_invoice_fields,
        "save_invoice": save_invoice,
        "get_invoice": get_invoice
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
        if tool_name in ("save_invoice", "get_invoice"):
            result = tool(db=db, **arguments)
        else:
            result = tool(**arguments)

        step.status = "completed"
        step.output_data = json.dumps(result)

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