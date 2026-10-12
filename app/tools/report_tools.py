from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Invoice


def get_overdue_invoice_report(db):
    today = date.today()

    invoices = db.scalars(
        select(Invoice).where(Invoice.due_date < today)
    ).all()

    grouped = defaultdict(
        lambda: {"count": 0, "total": Decimal("0")}
    )

    overdue = []

    for invoice in invoices:
        # Only payment-approval status is currently recorded.
        # Approval does not prove that payment was made.
        key = (invoice.company, invoice.currency)

        grouped[key]["count"] += 1
        grouped[key]["total"] += invoice.amount

        overdue.append({
            "invoice_id": invoice.id,
            "company": invoice.company,
            "invoice_number": invoice.invoice_number,
            "due_date": invoice.due_date.isoformat(),
            "amount": str(invoice.amount),
            "currency": invoice.currency,
            "days_overdue": (
                today - invoice.due_date
            ).days,
        })

    summary = [
        {
            "company": company,
            "currency": currency,
            "invoice_count": values["count"],
            "total_amount": str(values["total"]),
        }
        for (company, currency), values in sorted(
            grouped.items()
        )
    ]

    return {
        "as_of_date": today.isoformat(),
        "overdue_invoice_count": len(overdue),
        "overdue_invoices": overdue,
        "company_summary": summary,
        "note": (
            "Overdue means the due date has passed. "
            "Payment settlement status is not tracked, "
            "so this report does not establish which "
            "invoices remain unpaid."
        ),
    }