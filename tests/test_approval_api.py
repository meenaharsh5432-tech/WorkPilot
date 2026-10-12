
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Task, Invoice, ApprovalRequest


TEST_TOKEN = "local-test-token-only"


@pytest.fixture
def test_environment(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setenv(
        "WORKPILOT_APPROVAL_TOKEN",
        TEST_TOKEN
    )

    try:
        with TestingSession() as db:
            task = Task(
                user_request="Approve synthetic invoice",
                status="awaiting_approval"
            )
            db.add(task)

            invoice = Invoice(
                company="Test Corporation",
                invoice_number="TEST-100",
                invoice_date=__import__(
                    "datetime"
                ).date(2026, 10, 1),
                due_date=__import__(
                    "datetime"
                ).date(2026, 11, 1),
                amount=__import__(
                    "decimal"
                ).Decimal("5000.00"),
                currency="INR",
                payment_approval_status="not_approved"
            )
            db.add(invoice)
            db.flush()

            approval = ApprovalRequest(
                task_id=task.id,
                invoice_id=invoice.id,
                action="approve_invoice_payment",
                status="pending"
            )
            db.add(approval)
            db.commit()

        # No context manager: avoids running the production
        # application lifespan during these isolated tests.
        client = TestClient(app)

        yield client, TestingSession

    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def make_decision(client, decision, token=TEST_TOKEN):
    return client.post(
        "/approvals/1/decision",
        headers={"x-approval-token": token},
        json={
            "decision": decision,
            "note": "Automated test"
        }
    )


def test_approval_success(test_environment):
    client, SessionLocal = test_environment

    response = make_decision(client, "approved")

    assert response.status_code == 200

    data = response.json()

    assert data["approval_status"] == "approved"
    assert data["invoice_payment_status"] == "approved"
    assert data["task_status"] == "completed"
    assert data["verified"] is True

    # Fresh session checks committed database state
    with SessionLocal() as db:
        invoice = db.get(Invoice, 1)
        assert invoice.payment_approval_status == "approved"


def test_approval_rejection(test_environment):
    client, SessionLocal = test_environment

    response = make_decision(client, "rejected")

    assert response.status_code == 200
    assert response.json()["task_status"] == "rejected"

    with SessionLocal() as db:
        invoice = db.get(Invoice, 1)
        assert invoice.payment_approval_status == "not_approved"


def test_invalid_approval_token(test_environment):
    client, SessionLocal = test_environment

    response = make_decision(
        client,
        "approved",
        token="invalid-token"
    )

    assert response.status_code == 403

    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, 1)
        assert approval.status == "pending"


def test_duplicate_approval_rejected(test_environment):
    client, SessionLocal = test_environment

    first = make_decision(client, "approved")
    second = make_decision(client, "approved")

    assert first.status_code == 200
    assert second.status_code == 409


def test_missing_approval(test_environment):
    client, _ = test_environment

    response = client.post(
        "/approvals/99999/decision",
        headers={"x-approval-token": TEST_TOKEN},
        json={"decision": "approved"}
    )

    assert response.status_code == 404
