import json

from app.database import SessionLocal
from app.models import Task
from app.agent.reasoning import run_agent


with SessionLocal() as db:
    task = Task(
        user_request=(
            "Find the latest Acme invoice, "
            "extract its details, save it to "
            "the finance database, and verify it."
        )
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    task_id = task.id

print(f"\nRunning autonomous task #{task_id}\n")

result = run_agent(task_id)

print(json.dumps(result, indent=4))