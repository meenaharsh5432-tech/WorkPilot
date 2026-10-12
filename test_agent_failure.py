import json

from app.database import SessionLocal
from app.models import Task
from app.agent.reasoning import run_agent

with SessionLocal() as db:
    task = Task(
        user_request=(
            "Find the latest invoice from UnknownCorp, "
            "extract its details and save it to the "
            "finance database."
        )
    )

    db.add(task)
    db.commit()
    db.refresh(task)
    task_id = task.id

print(f"\nTesting failure recovery for task #{task_id}\n")

result = run_agent(task_id)

print(json.dumps(result, indent=4))