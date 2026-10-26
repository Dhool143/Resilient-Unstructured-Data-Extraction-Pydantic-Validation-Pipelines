# AI Prompt and Code Audit Log

Student: Fathiya Yoosef
Project: Structured Data Extractor
AI assistant: ChatGPT

## Initial Request and Generated Output

I provided the assignment instructions to ChatGPT and worked through
the implementation step by step.

The assignment requested an invoice extractor using Python,
Pydantic v2, constrained structured output, reflection retries,
JSON repair, a dead-letter queue, and an interactive interface.

ChatGPT generated the initial versions of:
- schemas.py
- extractor.py
- fallback.py
- app.py

It later helped generate automated tests and README documentation.
The original prompts and generated code are recorded in the project
conversation.

## My Verification Work

I created the project files, ran the application, inspected errors,
created a sample invoice PDF, and ran the automated tests.

I corrected a test folder naming problem: the folder was named
test, while an import expected tests.

I also corrected indentation when adding the PDF test.

These were setup and editing issues, separate from the code audit
findings below.

## Finding 1: Correction Prompts Could Omit Invoice Totals

File: fallback.py

The initial code included only the first 6,000 source characters
in a reflection prompt.

For a longer document, totals near the end could be excluded.
The model could therefore receive a reconciliation error without
the relevant source evidence.

Correction:
For documents longer than 6,000 characters, include the first
3,000 characters and the last 3,000 characters, with an explicit
marker showing that the middle was omitted.

Remaining limitation:
Important evidence in the middle can still be omitted. A future
improvement would select excerpts based on the failing fields.

## Finding 2: Error Heading Misclassified API Setup Failures

File: app.py

The initial interface labeled the error section "Validation errors."
However, it also displayed API and configuration errors there.

During live testing, missing OpenAI credentials appeared under this
heading. This could make a user think the invoice itself was invalid.

Correction:
Rename the section to "Extraction and validation errors" so the
heading reflects all errors displayed there.

## Additional Audit Checks

- Pydantic v2 field_validator and model_validator are used.
- Model serialization uses model_dump and model_dump_json.
- Decimal is used for monetary calculations.
- Nonpositive quantities are rejected.
- Negative monetary values are rejected.
- Line-item and invoice calculations are checked within 0.02.
- Repaired JSON must pass the full invoice schema again.
- Reflection has a bounded total attempt limit and backoff.
- Simulations are labeled and do not make AI requests.
- The API key is loaded from .env and must stay out of GitHub.

## Verification Results Before These Audit Changes

Command: uv run pytest -v

Result: 8 tests passed.

Coverage:
1. Valid text extraction with a mock response.
2. Zero quantity rejection.
3. Negative quantity rejection.
4. Negative total rejection.
5. Mismatched invoice total rejection.
6. PDF reading and extraction with a mock response.
7. Reflection recovery with mock responses.
8. DLQ routing after repeated invalid responses.

Live PDF extraction was also tested separately:
- Status: SUCCESS
- Attempts: 1
- Subtotal: 20.00 USD
- Tax: 2.00 USD
- Total: 22.00 USD

The simulated reflection and DLQ pathways were demonstrated.
Live AI reflection recovery has not yet been demonstrated.

## Verification After Audit Changes

Pending: rerun the automated tests, inspect the new error heading,
and check the long-document excerpt behavior.