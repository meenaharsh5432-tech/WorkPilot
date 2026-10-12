from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Invoice
from app.tools.finance_tools import save_invoice, get_invoice


@pytest.fixture
def db(tmp_path):
    database_url = (
        f"sqlite:///{tmp_path / 'test_finance.db'}"
    )

    engine = create_engine(database_url)

    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


@pytest.fixture
def invoice_fields():
    return {
        "company": "Acme Corporation",
        "invoice_number": "ACM-002",
        "invoice_date": "2026-10-05",
        "due_date": "2026-11-05",
        "amount": "18750.00",
        "currency": "INR"
    }


def test_save_invoice(db, invoice_fields):
    result = save_invoice(db, invoice_fields)

    assert result["status"] == "saved"
    assert result["invoice_id"] is not None


def test_get_invoice(db, invoice_fields):
    result = save_invoice(db, invoice_fields)

    saved = get_invoice(
        db,
        result["invoice_id"]
    )

    assert saved["company"] == "Acme Corporation"
    assert saved["invoice_number"] == "ACM-002"
    assert Decimal(saved["amount"]) == Decimal("18750.00")


def test_duplicate_invoice_prevention(db, invoice_fields):
    first = save_invoice(db, invoice_fields)
    second = save_invoice(db, invoice_fields)

    assert first["status"] == "saved"
    assert second["status"] == "already_exists"
    assert first["invoice_id"] == second["invoice_id"]

    records = db.scalars(
        select(Invoice)
    ).all()

    assert len(records) == 1


def test_missing_invoice_record(db):
    result = get_invoice(db, 99999)

    assert result is None


def test_invoice_persists_after_commit(
    db, invoice_fields
):
    result = save_invoice(db, invoice_fields)
    invoice_id = result["invoice_id"]

    db.expire_all()

    saved = db.get(Invoice, invoice_id)

    assert saved is not None
    assert saved.invoice_number == "ACM-002"
    assert saved.invoice_date == date(2026, 10, 5)
    assert saved.amount == Decimal("18750.00")


def test_default_payment_status(db, invoice_fields):
    result = save_invoice(db, invoice_fields)

    invoice = db.get(
        Invoice,
        result["invoice_id"]
    )

    assert invoice.payment_approval_status == "not_approved"