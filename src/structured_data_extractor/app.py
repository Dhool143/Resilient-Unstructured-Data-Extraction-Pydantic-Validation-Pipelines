import json
from dataclasses import asdict

import streamlit as st

from structured_data_extractor.extractor import (
    SchemaExtractor,
    read_html,
    read_pdf,
)


st.set_page_config(
    page_title="Invoice Extractor",
    page_icon="📄",
    layout="wide",
)

st.title("📄 Invoice Extractor")
st.write("Extract invoice information and check that the totals match.")

SAMPLE_TEXT = """Invoice: INV-1001
Vendor: Seattle Office Supplies
Date: 12th of Oct, 2024
Currency: USD

Notebooks: quantity 2, unit price $10.00, line total $20.00
Pens: quantity 3, unit price $5.00, line total $15.00

Subtotal: $35.00
Tax: $3.50
Total: $38.50
"""

SAMPLE_INVOICE = {
    "invoice_number": "INV-1001",
    "vendor_name": "Seattle Office Supplies",
    "invoice_date": "2024-10-12",
    "line_items": [
        {
            "description": "Notebooks",
            "quantity": 2,
            "unit_price": "10.00",
            "line_total": "20.00",
        },
        {
            "description": "Pens",
            "quantity": 3,
            "unit_price": "5.00",
            "line_total": "15.00",
        },
    ],
    "subtotal": "35.00",
    "tax_amount": "3.50",
    "total_amount": "38.50",
    "currency": "USD",
}


with st.sidebar:
    st.header("Settings")

    reflection_enabled = st.checkbox(
        "Enable reflection self-correction",
        value=True,
    )

    attempt_limit = st.slider(
        "Maximum total attempts",
        min_value=1,
        max_value=5,
        value=3,
    )

    demo_mode = st.selectbox(
        "Run mode",
        [
            "Live AI extraction",
            "Simulated reflection recovery",
        ],
    )

    st.caption(
        "Live extraction requires an OpenAI API key. "
        "Simulations use fixed responses and make no API calls."
    )


input_type = st.radio(
    "Choose your document source",
    ["Paste text", "Paste HTML", "Upload PDF"],
    horizontal=True,
)

document_text = ""
input_error = None

if input_type == "Paste text":
    document_text = st.text_area(
        "Invoice text",
        value=SAMPLE_TEXT,
        height=260,
    )

elif input_type == "Paste HTML":
    html = st.text_area("Paste your invoice HTML", height=260)
    document_text = read_html(html)

else:
    uploaded_file = st.file_uploader(
        "Upload an invoice PDF",
        type=["pdf"],
    )

    if uploaded_file is not None:
        try:
            document_text = read_pdf(uploaded_file)
        except Exception as error:
            input_error = f"Could not read this PDF: {error}"
            st.error(input_error)


extract_clicked = st.button("Extract invoice", type="primary")
failure_clicked = st.button("Simulate Edge Case Failure")

if extract_clicked or failure_clicked:
    result = None
    source_text = document_text

    if failure_clicked:
        st.info(
            "Simulation: fixed invalid responses test the DLQ. "
            "No AI request is made."
        )
        source_text = "Unreadable invoice: ??? no usable information"
        extractor = SchemaExtractor(generate=lambda prompt: "{}")

    elif demo_mode == "Simulated reflection recovery":
        st.info(
            "Simulation: attempt 1 has an incorrect total. "
            "Attempt 2 returns the correct fixed response. "
            "No AI request is made."
        )

        source_text = SAMPLE_TEXT
        bad_invoice = dict(SAMPLE_INVOICE)
        bad_invoice["total_amount"] = "999.00"

        responses = iter(
            [json.dumps(bad_invoice), json.dumps(SAMPLE_INVOICE)]
        )

        extractor = SchemaExtractor(
            generate=lambda prompt: next(
                responses, json.dumps(SAMPLE_INVOICE)
            )
        )

    else:
        extractor = SchemaExtractor()

    if input_error and not failure_clicked and demo_mode == "Live AI extraction":
        st.warning("Fix the PDF input before extracting.")
    elif not source_text.strip():
        st.warning("Please upload a PDF or paste invoice text first.")
    else:
        with st.spinner("Extracting and validating invoice..."):
            try:
                result = extractor.extract_with_retry(
                    raw_text=source_text,
                    max_retries=attempt_limit,
                    enable_reflection=reflection_enabled,
                )
            except Exception as error:
                st.error(f"Extraction could not run: {error}")

    if result is not None:
        st.write(f"**Status:** {result.execution_status}")
        st.write(f"**AI response attempts:** {result.attempts_used}")

        left, right = st.columns(2)

        with left:
            st.subheader("Source document")
            st.text(source_text)

        with right:
            st.subheader("Validated invoice")

            if result.validated_data is not None:
                invoice = result.validated_data

                st.success("✓ Reconciled: invoice totals match within $0.02")
                st.json(invoice.model_dump(mode="json"))

                st.download_button(
                    "Download validated JSON",
                    data=invoice.model_dump_json(indent=2),
                    file_name="validated_invoice.json",
                    mime="application/json",
                )
            else:
                st.error("Validation failed. Human review is required.")

                if result.dlq_path:
                    st.write(f"Saved failure record: `{result.dlq_path}`")
                else:
                    st.warning("The failure record could not be saved.")

        with st.expander("Extraction and validation errors", expanded=bool(result.error_log),
               ):
         if result.error_log:
                for error in result.error_log:
                    st.code(error, language="text")
         else:
                st.write("No validation errors.")

        with st.expander("Exact corrective prompts"):
            for number, prompt in enumerate(result.corrective_prompts, start=1):
                st.write(f"**Correction {number}**")
                st.code(prompt, language="text")

            if not result.corrective_prompts:
                st.write("No corrective prompts were needed.")

        with st.expander("Raw model responses"):
            for number, response in enumerate(result.raw_responses, start=1):
                st.write(f"**Attempt {number}**")
                st.code(response, language="json")