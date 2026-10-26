import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from structured_data_extractor.extractor import SchemaExtractor
from structured_data_extractor.schemas import InvoiceExtraction


def sample_invoice():
    """Return fresh valid invoice data for each test."""
    return {
        "invoice_number": "INV-1001",
        "vendor_name": "Seattle Office Supplies",
        "invoice_date": "2024-10-12",
        "line_items": [
            {
                "description": "Notebooks",
                "quantity": 2,
                "unit_price": "10.00",
                "line_total": "20.00",
            }
        ],
        "subtotal": "20.00",
        "tax_amount": "2.00",
        "total_amount": "22.00",
        "currency": "USD",
    }


def test_golden_text_extraction():
    """A valid mock response succeeds on the first attempt."""
    document = (
        "Invoice INV-1001, Seattle Office Supplies, 2024-10-12. "
        "2 Notebooks at USD 10.00 each. "
        "Subtotal 20.00, tax 2.00, total 22.00."
    )
    prompts = []

    def mock_generate(prompt):
        prompts.append(prompt)
        return json.dumps(sample_invoice())

    extractor = SchemaExtractor(generate=mock_generate)
    result = extractor.extract_with_retry(document)

    assert result.execution_status == "SUCCESS"
    assert result.attempts_used == 1
    assert result.error_log == []
    assert result.validated_data.total_amount == Decimal("22.00")
    assert document in prompts[0]


@pytest.mark.parametrize("quantity", [0, -1])
def test_invalid_quantity_is_rejected(quantity):
    data = sample_invoice()
    data["line_items"][0]["quantity"] = quantity

    with pytest.raises(ValidationError) as caught:
        InvoiceExtraction.model_validate(data)

    assert any(
        error["loc"] == ("line_items", 0, "quantity")
        for error in caught.value.errors()
    )


def test_negative_total_is_rejected():
    data = sample_invoice()
    data["total_amount"] = "-22.00"

    with pytest.raises(ValidationError) as caught:
        InvoiceExtraction.model_validate(data)

    assert any(
        error["loc"] == ("total_amount",)
        for error in caught.value.errors()
    )


def test_mismatched_total_is_rejected():
    data = sample_invoice()
    data["total_amount"] = "999.00"

    with pytest.raises(ValidationError, match="Invoice total should be"):
        InvoiceExtraction.model_validate(data)
        
        
        
        
        
        
def test_golden_pdf_extraction():
    from pathlib import Path
    from structured_data_extractor.extractor import read_pdf

    pdf_path = (
        Path(__file__).resolve().parents[1]
        / "samples"
        / "invoice_messy.pdf"
    )

    with pdf_path.open("rb") as pdf_file:
        document_text = read_pdf(pdf_file)

    assert "INV-1001" in document_text
    assert "Notebooks" in document_text
    assert "22.00" in document_text

    def mock_generate(prompt):
        assert document_text in prompt
        return json.dumps(sample_invoice())

    extractor = SchemaExtractor(generate=mock_generate)
    result = extractor.extract_with_retry(document_text)

    assert result.execution_status == "SUCCESS"
    assert result.attempts_used == 1
    assert result.error_log == []
    assert result.validated_data.total_amount == Decimal("22.00")