from decimal import Decimal
import json

from app.database import SessionLocal, Base, engine
from app import models
from app.tools.invoice_tools import extract_invoice_fields
from app.tools.finance_tools import save_invoice, get_invoice

Base.metadata.create_all(bind=engine)

fields = extract_invoice_fields("acme_002.txt")

with SessionLocal() as db:
    result = save_invoice(db, fields)

    print("\nSAVE RESULT:")
    print(json.dumps(result, indent=4))

    saved_invoice = get_invoice(db, result["invoice_id"])

    print("\nDATABASE RECORD:")
    print(json.dumps(saved_invoice, indent=4))

    # Independently compare stored values with extracted values.
    verified = saved_invoice is not None and all(
        saved_invoice[key] == (
            f"{Decimal(fields[key]):.2f}" if key == "amount"
            else fields[key]
        )
        for key in (
            "company", "invoice_number", "invoice_date",
            "due_date", "amount", "currency"
        )
    )

    print("\nVERIFICATION:", "PASSED" if verified else "FAILED")