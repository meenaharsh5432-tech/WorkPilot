from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invoice


def save_invoice(db: Session, fields: dict):
    existing = db.scalar(
        select(Invoice).where(
            Invoice.company == fields["company"],
            Invoice.invoice_number == fields["invoice_number"]
        )
    )

    if existing:
        return {
            "status": "already_exists",
            "invoice_id": existing.id
        }

    invoice = Invoice(
        company=fields["company"],
        invoice_number=fields["invoice_number"],
        invoice_date=date.fromisoformat(fields["invoice_date"]),
        due_date=date.fromisoformat(fields["due_date"]),
        amount=Decimal(fields["amount"]),
        currency=fields["currency"]
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return {
        "status": "saved",
        "invoice_id": invoice.id
    }


def get_invoice(db: Session, invoice_id: int):
    invoice = db.get(Invoice, invoice_id)

    if invoice is None:
        return None

    return {
        "id": invoice.id,
        "company": invoice.company,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
        "amount": str(invoice.amount),
        "currency": invoice.currency
    }