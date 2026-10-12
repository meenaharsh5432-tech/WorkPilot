from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation

INVOICE_DIR = Path(__file__).resolve().parents[2] / "sample_invoices"


def search_invoices(company_name: str):
    matches = []

    for file_path in INVOICE_DIR.glob("*.txt"):
        content = file_path.read_text(encoding="utf-8")

        fields = {}

        for line in content.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip().lower()] = value.strip()

        company = fields.get("company", "")

        if company_name.casefold() not in company.casefold():
            continue

        try:
            invoice_date = date.fromisoformat(
                fields["invoice date"]
            )
        except (KeyError, ValueError):
            continue

        matches.append({
            "file_name": file_path.name,
            "company": company,
            "invoice_date": invoice_date.isoformat(),
            "invoice_number": fields.get("invoice number")
        })

    matches.sort(
        key=lambda invoice: invoice["invoice_date"],
        reverse=True
    )

    return matches

def extract_invoice_fields(file_name: str):
    file_path = INVOICE_DIR / file_name

    if file_path.name != file_name or file_path.suffix != ".txt":
        raise ValueError("Invalid invoice filename")

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Invoice not found: {file_name}"
        )

    content = file_path.read_text(encoding="utf-8")

    fields = {}

    for line in content.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()

    required_fields = [
        "company",
        "invoice number",
        "invoice date",
        "due date",
        "amount",
        "currency"
    ]

    missing = [
        field for field in required_fields
        if not fields.get(field)
    ]

    if missing:
        raise ValueError(
            f"Missing required fields: {', '.join(missing)}"
        )

    try:
        invoice_date = date.fromisoformat(fields["invoice date"])
        due_date = date.fromisoformat(fields["due date"])
        amount = Decimal(fields["amount"])

        if not amount.is_finite() or amount <= 0:
            raise ValueError("Amount must be positive and finite")

        if due_date < invoice_date:
            raise ValueError("Due date cannot precede invoice date")

    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid invoice data: {exc}") from exc

    return {
        "company": fields["company"],
        "invoice_number": fields["invoice number"],
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "amount": str(amount),
        "currency": fields["currency"].upper()
    }