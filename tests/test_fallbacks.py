import json
from pathlib import Path

from structured_data_extractor.extractor import SchemaExtractor
from tests.test_extraction import sample_invoice


def test_reflection_recovers_on_second_attempt(monkeypatch):
    # Skip waiting during automated tests.
    monkeypatch.setattr(
        "structured_data_extractor.extractor.time.sleep",
        lambda seconds: None,
    )

    bad_data = sample_invoice()
    del bad_data["currency"]

    responses = iter([
        json.dumps(bad_data),
        json.dumps(sample_invoice()),
    ])
    prompts = []

    def mock_generate(prompt):
        prompts.append(prompt)
        return next(responses)

    extractor = SchemaExtractor(generate=mock_generate)

    result = extractor.extract_with_retry(
        "Invoice INV-1001. Currency USD. Total 22.00.",
        max_retries=3,
    )

    assert result.execution_status == "REPAIRED_VIA_REFLECTION"
    assert result.attempts_used == 2
    assert result.validated_data.currency == "USD"
    assert len(result.error_log) == 1
    assert len(result.corrective_prompts) == 1
    assert "currency" in prompts[1]
    assert "Field required" in prompts[1]
    assert result.dlq_path is None


def test_hard_failure_is_saved_to_dlq(tmp_path, monkeypatch):
    # Save test failures in a temporary folder.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "structured_data_extractor.extractor.time.sleep",
        lambda seconds: None,
    )

    prompts = []

    def mock_generate(prompt):
        prompts.append(prompt)
        return "{}"

    extractor = SchemaExtractor(generate=mock_generate)

    result = extractor.extract_with_retry(
        "Unreadable invoice with no usable information.",
        max_retries=3,
    )

    assert result.execution_status == "DLQ_FAILED"
    assert result.attempts_used == 3
    assert len(prompts) == 3
    assert result.validated_data is None
    assert result.dlq_path is not None

    saved_file = Path(result.dlq_path)
    assert saved_file.exists()

    record = json.loads(saved_file.read_text(encoding="utf-8"))

    assert record["execution_status"] == "DLQ_FAILED"
    assert record["attempts_used"] == 3
    assert record["last_payload"] == "{}"
    assert record["error_log"]