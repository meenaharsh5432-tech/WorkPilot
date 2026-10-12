
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Invoice
from app.tools.report_tools import get_overdue_invoice_report


def make_invoice(db, number, company, due_date, amount):
    invoice = Invoice(
        company=company,
        invoice_number=number,
        invoice_date=due_date - timedelta(days=30),
        due_date=due_date,
        amount=Decimal(amount),
        currency="INR",
        payment_approval_status="not_approved",
    )
    db.add(invoice)
    db.commit()


def test_overdue_invoice_detected(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}"
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    try:
        with Session() as db:
            make_invoice(
                db, "TEST-001", "Demo Ltd",
                date.today() - timedelta(days=10),
                "5000.00"
            )

            report = get_overdue_invoice_report(db)

            assert report["overdue_invoice_count"] == 1
            assert report["overdue_invoices"][0]["days_overdue"] == 10
            assert report["overdue_invoices"][0]["amount"] == "5000.00"
    finally:
        engine.dispose()


def test_company_totals(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}"
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    try:
        with Session() as db:
            make_invoice(
                db, "TEST-002", "Demo Ltd",
                date.today() - timedelta(days=5),
                "3000.00"
            )
            make_invoice(
                db, "TEST-003", "Demo Ltd",
                date.today() - timedelta(days=15),
                "7000.00"
            )

            report = get_overdue_invoice_report(db)

            assert report["overdue_invoice_count"] == 2
            assert report["company_summary"][0]["total_amount"] == "10000.00"
            assert report["company_summary"][0]["invoice_count"] == 2
    finally:
        engine.dispose()


def test_future_invoice_excluded(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}"
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    try:
        with Session() as db:
            make_invoice(
                db, "TEST-004", "Future Ltd",
                date.today() + timedelta(days=10),
                "9000.00"
            )

            report = get_overdue_invoice_report(db)

            assert report["overdue_invoice_count"] == 0
            assert report["company_summary"] == []
    finally:
        engine.dispose()
