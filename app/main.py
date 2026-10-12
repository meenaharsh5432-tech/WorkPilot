
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

# Load the .env file from the project root independent of working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=True)

from app import models
from app.agent.reasoning import run_agent
from app.database import Base, engine, get_db
from app.models import ApprovalRequest
from app.schemas import (
    ApprovalDecision,
    ExecutionStepResponse,
    TaskCreate,
    TaskResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="WorkPilot",
    description="Autonomous Company Task Worker",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"message": "WorkPilot API is running", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    request_text = payload.user_request.strip()
    if not request_text:
        raise HTTPException(status_code=400, detail="Task request cannot be empty")

    task = models.Task(user_request=request_text)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(models.Task).order_by(models.Task.id.desc()).all()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/run")
def execute_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Task cannot run from status '{task.status}'",
        )
    # The agent creates its own DB session. The synchronous run endpoint is
    # suitable for local demos, but not safe against concurrent run requests.
    db.close()
    return run_agent(task_id)


@app.get("/tasks/{task_id}/steps", response_model=list[ExecutionStepResponse])
def get_task_steps(task_id: int, db: Session = Depends(get_db)):
    if db.get(models.Task, task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return (
        db.query(models.ExecutionStep)
        .filter(models.ExecutionStep.task_id == task_id)
        .order_by(models.ExecutionStep.step_number, models.ExecutionStep.id)
        .all()
    )


@app.get("/approvals")
def list_approvals(db: Session = Depends(get_db)):
    approvals = (
        db.query(ApprovalRequest)
        .order_by(ApprovalRequest.id.desc())
        .all()
    )
    return [
        {
            "approval_id": approval.id,
            "task_id": approval.task_id,
            "invoice_id": approval.invoice_id,
            "action": approval.action,
            "status": approval.status,
        }
        for approval in approvals
    ]


@app.post("/approvals/{approval_id}/decision")
def decide_approval(
    approval_id: int,
    payload: ApprovalDecision,
    x_approval_token: str = Header(...),
    db: Session = Depends(get_db)
):
    # 1. Authenticate human approval request
    expected_token = os.getenv("WORKPILOT_APPROVAL_TOKEN")

    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="Approval token is not configured"
        )

    if not secrets.compare_digest(
        x_approval_token,
        expected_token
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid approval token"
        )

    # 2. Retrieve approval and associated records
    approval = db.get(ApprovalRequest, approval_id)

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval request not found"
        )

    task = db.get(models.Task, approval.task_id)
    invoice = db.get(models.Invoice, approval.invoice_id)

    if task is None or invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Associated task or invoice not found"
        )

    # 3. Validate workflow state
    if (
        approval.status != "pending"
        or task.status != "awaiting_approval"
        or approval.action != "approve_invoice_payment"
    ):
        raise HTTPException(
            status_code=409,
            detail="Approval request is not actionable"
        )

    try:
        # 4. Consume pending approval once
        decision_result = db.execute(
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.status == "pending"
            )
            .values(
                status=payload.decision,
                decision_note=payload.note
            )
        )

        if decision_result.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Approval already processed"
            )

        # 5. Execute the protected simulated action
        if payload.decision == "approved":

            update_result = db.execute(
                update(models.Invoice)
                .where(
                    models.Invoice.id == invoice.id,
                    models.Invoice.payment_approval_status
                    == "not_approved"
                )
                .values(
                    payment_approval_status="approved"
                )
            )

            if update_result.rowcount != 1:
                db.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Invoice is not in an approvable state"
                    )
                )

            # 6. Read back the updated value
            db.expire(invoice)
            db.refresh(invoice)

            verified = (
                invoice.payment_approval_status == "approved"
            )

            if not verified:
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail="Invoice approval verification failed"
                )

            task.status = "completed"
            message = "Invoice approval executed and verified"

        else:
            # Rejection must not change invoice status
            db.expire(invoice)
            db.refresh(invoice)

            task.status = "rejected"
            verified = (
                invoice.payment_approval_status
                == "not_approved"
            )

            message = "Invoice approval rejected"

        # 7. Store the outcome
        task.result = json.dumps({
            "approval_id": approval.id,
            "invoice_id": invoice.id,
            "decision": payload.decision,
            "payment_approval_status":
                invoice.payment_approval_status,
            "verified": verified,
            "message": message
        })

        # 8. Commit decision, invoice update and task state
        db.commit()

        return {
            "approval_id": approval.id,
            "task_id": task.id,
            "invoice_id": invoice.id,
            "approval_status": payload.decision,
            "invoice_payment_status":
                invoice.payment_approval_status,
            "task_status": task.status,
            "verified": verified,
            "message": message
        }

    except Exception:
        db.rollback()
        raise

@app.get("/invoices/{invoice_id}")
def get_invoice_details(
    invoice_id: int,
    db: Session = Depends(get_db)
):
    invoice = db.get(models.Invoice, invoice_id)

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found"
        )

    return {
        "id": invoice.id,
        "company": invoice.company,
        "invoice_number": invoice.invoice_number,
        "amount": str(invoice.amount),
        "currency": invoice.currency,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "payment_approval_status": invoice.payment_approval_status
    }