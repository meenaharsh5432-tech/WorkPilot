from pathlib import Path

import pytest

from app.tools import invoice_tools


@pytest.fixture
def invoice_directory(tmp_path, monkeypatch):
    """
    Create an isolated invoice folder for each test.
    The real sample_invoices folder is not modified.
    """

    monkeypatch.setattr(
        invoice_tools,
        "INVOICE_DIR",
        tmp_path
    )

    invoices = {
        "acme_001.txt": """INVOICE
Company: Acme Corporation
Invoice Number: ACM-001
Invoice Date: 2026-09-15
Due Date: 2026-10-15
Amount: 12500.00
Currency: INR
""",
        "acme_002.txt": """INVOICE
Company: Acme Corporation
Invoice Number: ACM-002
Invoice Date: 2026-10-05
Due Date: 2026-11-05
Amount: 18750.00
Currency: INR
""",
        "globex_001.txt": """INVOICE
Company: Globex Corporation
Invoice Number: GLX-001
Invoice Date: 2026-10-01
Due Date: 2026-11-01
Amount: 9200.00
Currency: INR
"""
    }

    for filename, content in invoices.items():
        (tmp_path / filename).write_text(
            content,
            encoding="utf-8"
        )

    return tmp_path


def test_search_returns_latest_invoice_first(invoice_directory):
    results = invoice_tools.search_invoices("Acme")

    assert len(results) == 2
    assert results[0]["file_name"] == "acme_002.txt"
    assert results[0]["invoice_number"] == "ACM-002"


def test_search_is_case_insensitive(invoice_directory):
    results = invoice_tools.search_invoices("aCmE")

    assert len(results) == 2


def test_search_unknown_company(invoice_directory):
    results = invoice_tools.search_invoices("UnknownCorp")

    assert results == []


def test_extract_invoice_fields(invoice_directory):
    result = invoice_tools.extract_invoice_fields(
        "acme_002.txt"
    )

    assert result["company"] == "Acme Corporation"
    assert result["invoice_number"] == "ACM-002"
    assert result["amount"] == "18750.00"
    assert result["currency"] == "INR"


def test_missing_invoice(invoice_directory):
    with pytest.raises(FileNotFoundError):
        invoice_tools.extract_invoice_fields(
            "missing.txt"
        )


def test_negative_invoice_amount(invoice_directory):
    invalid_invoice = invoice_directory / "negative.txt"

    invalid_invoice.write_text(
        """INVOICE
Company: Test Corporation
Invoice Number: TEST-001
Invoice Date: 2026-10-01
Due Date: 2026-11-01
Amount: -500.00
Currency: INR
""",
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        invoice_tools.extract_invoice_fields(
            "negative.txt"
        )


def test_invalid_due_date(invoice_directory):
    invalid_invoice = invoice_directory / "bad_date.txt"

    invalid_invoice.write_text(
        """INVOICE
Company: Test Corporation
Invoice Number: TEST-002
Invoice Date: 2026-10-15
Due Date: 2026-10-01
Amount: 500.00
Currency: INR
""",
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        invoice_tools.extract_invoice_fields(
            "bad_date.txt"
        )


def test_path_traversal_blocked(invoice_directory):
    with pytest.raises(ValueError):
        invoice_tools.extract_invoice_fields(
            "../secret.txt"
        )