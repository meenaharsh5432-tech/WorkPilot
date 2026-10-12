from sqlalchemy.orm import Session

from app.models import ApprovalRequest, Invoice, Task


def request_invoice_approval(
    db: Session,
    task_id: int,
    invoice_id: int
):

    approved_request = (
    db.query(ApprovalRequest)
    .filter_by(
        invoice_id=invoice_id,
        action="approve_invoice_payment",
        status="approved"
    )
    .first()
)

    if approved_request:
        raise ValueError(
        "This invoice already has an approved payment "
        "authorization request"
    )

    
    task = db.get(Task, task_id)
    invoice = db.get(Invoice, invoice_id)

    if task is None:
        raise ValueError("Task not found")

    if invoice is None:
        raise ValueError("Invoice not found")

    if task.status not in ("running", "pending"):
        raise ValueError("Task is not eligible for approval")

    existing = (
        db.query(ApprovalRequest)
        .filter_by(
            task_id=task_id,
            invoice_id=invoice_id,
            action="approve_invoice_payment"
        )
        .first()
    )

    if existing:
        return {
            "approval_id": existing.id,
            "status": existing.status,
            "invoice_id": invoice_id
        }

    approval = ApprovalRequest(
        task_id=task_id,
        invoice_id=invoice_id,
        action="approve_invoice_payment",
        status="pending"
    )

    db.add(approval)
    db.flush()

    task.status = "awaiting_approval"
    db.commit()
    db.refresh(approval)

    return {
        "approval_id": approval.id,
        "invoice_id": invoice_id,
        "status": "pending",
        "message": "Human approval required"
    }