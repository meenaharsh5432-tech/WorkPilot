from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from sqlalchemy import String, Text, DateTime, ForeignKey


from sqlalchemy import Numeric, UniqueConstraint
from datetime import date

class Task(Base):
    __tablename__="tasks"

    id: Mapped[int]=mapped_column(
        primary_key=True,
        index=True,
    )

    user_request:Mapped[str]=mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str]=mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )
    result: Mapped[str|None]=mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime]=mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        UniqueConstraint("invoice_number", "company", name="uq_invoice_company"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    company: Mapped[str] = mapped_column(String(200), nullable=False)

    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)

    invoice_date: Mapped[date] = mapped_column(nullable=False)

    due_date: Mapped[date] = mapped_column(nullable=False)

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    payment_approval_status: Mapped[str]=mapped_column(
        String(30),
        nullable=False,
        default="not_approved",
        server_onupdate="not_approved"
    )

class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id: Mapped[int] = mapped_column(primary_key=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
        index=True
    )

    step_number: Mapped[int] = mapped_column(
        nullable=False
    )

    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    input_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    output_data: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(primary_key=True)

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
        index=True
    )

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id"),
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        default="approve_invoice_payment",
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False
    )

    decision_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

