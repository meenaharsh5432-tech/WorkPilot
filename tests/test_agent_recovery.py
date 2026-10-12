import json
from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from app.agent.executor import execute_tool
from app.models import Task, ExecutionStep
from app.database import Base

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_recovery_during_tool_execution(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recovery.db'}"
    )
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)

    with Session() as db:
        task = Task(user_request="Retrieve and verify invoice")
        db.add(task)
        db.commit()
        db.refresh(task)

        task_id = task.id

        calls = {"count": 0}

        def unreliable_get_invoice(db, invoice_id):
            calls["count"] += 1

            if calls["count"] == 1:
                raise OperationalError(
                    "SELECT invoice",
                    {},
                    Exception("temporary database failure")
                )

            return {
                "id": invoice_id,
                "invoice_number": "TEST-001",
                "amount": "5000.00",
                "currency": "INR"
            }

        with patch(
            "app.agent.executor.get_invoice",
            side_effect=unreliable_get_invoice
        ):
            response = execute_tool(
                db=db,
                task_id=task_id,
                step_number=1,
                tool_name="get_invoice",
                arguments={"invoice_id": 1}
            )

        assert response["success"] is True
        assert calls["count"] == 2

        step = (
            db.query(ExecutionStep)
            .filter_by(task_id=task_id)
            .first()
        )

        assert step.status == "completed"

        output = json.loads(step.output_data)

        assert len(output["retry_events"]) == 1
        assert output["retry_events"][0]["attempt"] == 1
        assert output["result"]["invoice_number"] == "TEST-001"

    engine.dispose()