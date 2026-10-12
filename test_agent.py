import json

from app.database import SessionLocal, Base, engine
from app import models
from app.agent.executor import execute_tool

Base.metadata.create_all(bind=engine)


def pretty_print(label, result):
    print(f"\n{'=' * 55}")
    print(label)
    print('=' * 55)
    print(json.dumps(result, indent=4))


with SessionLocal() as db:

    task = models.Task(
        user_request="Find the latest Acme invoice"
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    result = execute_tool(
        db=db,
        task_id=task.id,
        step_number=1,
        tool_name="search_invoices",
        arguments={"company_name": "Acme"}
    )

    pretty_print("STEP 1 - SEARCH INVOICES", result)

    result = execute_tool(
        db=db,
        task_id=task.id,
        step_number=2,
        tool_name="extract_invoice_fields",
        arguments={"file_name": "acme_002.txt"}
    )

    pretty_print("STEP 2 - EXTRACT INVOICE", result)

    result = execute_tool(
        db=db,
        task_id=task.id,
        step_number=3,
        tool_name="save_invoice",
        arguments={"fields": result["result"]}
    )

    pretty_print("STEP 3 - SAVE INVOICE", result)

    invoice_id = result["result"]["invoice_id"]

    result = execute_tool(
        db=db,
        task_id=task.id,
        step_number=4,
        tool_name="get_invoice",
        arguments={"invoice_id": invoice_id}
    )

    pretty_print("STEP 4 - VERIFY DATABASE RECORD", result)

    task.status = "completed"
    task.result = json.dumps(result["result"])
    db.commit()

    print("\nTask completed successfully.")