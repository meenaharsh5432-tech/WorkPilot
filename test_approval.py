import json

from app.database import SessionLocal
from app.models import Task, Invoice
from app.tools.approval_tools import request_invoice_approval

with SessionLocal() as db:

    invoices = db.query(Invoice).order_by(Invoice.id).all()

    if not invoices:
        raise ValueError("No invoices found in database")

    print("\nAVAILABLE INVOICES")
    print("=" * 50)

    for invoice in invoices:
        print(
            f"ID: {invoice.id} | "
            f"Company: {invoice.company} | "
            f"Invoice: {invoice.invoice_number} | "
            f"Amount: {invoice.amount} {invoice.currency}"
        )

    invoice_id = int(input("\nEnter invoice ID: "))

    invoice = db.get(Invoice, invoice_id)

    if invoice is None:
        raise ValueError("Invalid invoice ID")

    task = Task(
        user_request=(
            f"Approve invoice {invoice.invoice_number} "
            f"from {invoice.company} for payment"
        )
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    result = request_invoice_approval(
        db=db,
        task_id=task.id,
        invoice_id=invoice.id
    )

    print("\nAPPROVAL REQUEST CREATED")
    print(json.dumps(result, indent=4))