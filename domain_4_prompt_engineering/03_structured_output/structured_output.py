"""
Task 4.3 – Structured Output Using Tool Use and JSON Schemas
============================================================
Covers tool_choice options, schema design, and semantic vs syntax errors.

Directly tested in Scenario 6 (Structured Data Extraction).
"""

import anthropic
import json
from typing import Any

client = anthropic.Anthropic()


# ─────────────────────────────────────────────────────────
# SECTION 1: Extraction tool with JSON schema
# ─────────────────────────────────────────────────────────

INVOICE_EXTRACTION_TOOL = {
    "name": "extract_invoice",
    "description": "Extract structured data from an invoice document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_number":   {"type": "string"},
            "vendor_name":      {"type": "string"},
            "invoice_date":     {"type": "string", "description": "ISO 8601 format"},
            "due_date":         {"type": ["string", "null"], "description": "Null if not stated"},
            "currency":         {"type": "string", "enum": ["USD", "EUR", "GBP", "other"]},
            "currency_detail":  {"type": ["string", "null"], "description": "Required when currency=other"},
            "subtotal":         {"type": ["number", "null"]},
            "tax_amount":       {"type": ["number", "null"]},
            "total_amount":     {"type": "number"},
            "calculated_total": {"type": ["number", "null"],
                                 "description": "Sum of line items for semantic validation"},
            "payment_terms":    {
                "type": "string",
                "enum": ["net_30", "net_60", "due_on_receipt", "unclear", "other"],
            },
            "payment_terms_detail": {"type": ["string", "null"],
                                     "description": "Required when payment_terms=other or unclear"},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity":    {"type": ["number", "null"]},
                        "unit_price":  {"type": ["number", "null"]},
                        "amount":      {"type": "number"},
                    },
                    "required": ["description", "amount"],
                },
            },
            "conflict_detected": {
                "type": "boolean",
                "description": "True if stated_total != sum of line items",
            },
        },
        "required": [
            "invoice_number", "vendor_name", "invoice_date",
            "currency", "total_amount", "conflict_detected",
        ],
    },
}


# ─────────────────────────────────────────────────────────
# SECTION 2: tool_choice options
# ─────────────────────────────────────────────────────────

def extract_with_tool_choice_auto(document: str):
    """
    tool_choice: "auto" — model MAY return text instead of calling a tool.
    ❌ Unreliable for guaranteed structured output.
    """
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        tools=[INVOICE_EXTRACTION_TOOL],
        tool_choice={"type": "auto"},           # model decides
        messages=[{"role": "user", "content": f"Extract data:\n{document}"}],
    )
    # May return text or tool_use — not guaranteed
    return response


def extract_with_tool_choice_any(document: str):
    """
    tool_choice: "any" — model MUST call A tool (but chooses which).
    ✅ Use when multiple extraction schemas exist and document type is unknown.
    """
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        tools=[INVOICE_EXTRACTION_TOOL],
        tool_choice={"type": "any"},            # must call a tool
        messages=[{"role": "user", "content": f"Extract data:\n{document}"}],
    )
    return _extract_tool_result(response)


def extract_with_forced_tool(document: str):
    """
    Forced tool selection — model MUST call this specific tool.
    ✅ Use when you need a guaranteed specific extraction schema.
    """
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        tools=[INVOICE_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},   # forced
        messages=[{"role": "user", "content": f"Extract invoice data:\n{document}"}],
    )
    return _extract_tool_result(response)


def _extract_tool_result(response) -> dict | None:
    for block in response.content:
        if block.type == "tool_use":
            return block.input   # Already a dict, schema-compliant
    return None


# ─────────────────────────────────────────────────────────
# SECTION 3: Semantic vs syntax errors
# ─────────────────────────────────────────────────────────

def validate_semantic_correctness(extracted: dict) -> list[str]:
    """
    tool_use with strict JSON schemas eliminates SYNTAX errors.
    But semantic errors still require explicit validation.

    Semantic error examples:
      - line items don't sum to total_amount
      - values placed in wrong fields
      - dates that are logically impossible
    """
    errors = []

    # Check 1: line items sum vs total
    if extracted.get("line_items") and extracted.get("total_amount"):
        calculated = sum(item["amount"] for item in extracted["line_items"])
        stated = extracted["total_amount"]

        if abs(calculated - stated) > 0.01:  # allow for rounding
            errors.append(
                f"Semantic error: line items sum to {calculated:.2f} "
                f"but total_amount states {stated:.2f}"
            )

    # Check 2: subtotal + tax should equal total
    if (extracted.get("subtotal") is not None
            and extracted.get("tax_amount") is not None
            and extracted.get("total_amount") is not None):
        expected = extracted["subtotal"] + extracted["tax_amount"]
        actual = extracted["total_amount"]
        if abs(expected - actual) > 0.01:
            errors.append(
                f"Semantic error: subtotal ({extracted['subtotal']}) + "
                f"tax ({extracted['tax_amount']}) = {expected:.2f} "
                f"!= total ({actual})"
            )

    # Check 3: currency_detail required when currency=other
    if extracted.get("currency") == "other" and not extracted.get("currency_detail"):
        errors.append("Semantic error: currency=other but currency_detail is null")

    return errors


# ─────────────────────────────────────────────────────────
# SECTION 4: Nullable fields prevent fabrication
# ─────────────────────────────────────────────────────────

RECEIPT_TOOL_WITH_OPTIONAL_FIELDS = {
    "name": "extract_receipt",
    "description": "Extract data from a receipt. Many fields may be absent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "merchant_name": {"type": "string"},
            "date":          {"type": "string"},
            "total":         {"type": "number"},
            # These may not appear on every receipt
            "tax":           {"type": ["number", "null"]},   # nullable
            "tip":           {"type": ["number", "null"]},   # nullable
            "receipt_number": {"type": ["string", "null"]},  # nullable
            "cashier_name":  {"type": ["string", "null"]},   # nullable
            "payment_method": {
                "type": ["string", "null"],
                "enum": ["cash", "card", "mobile", "unclear", None],
            },
        },
        "required": ["merchant_name", "date", "total"],
        # Only truly universal fields are required
        # Nullable fields prevent model from fabricating values
    },
}


# ─────────────────────────────────────────────────────────
# SECTION 5: Complete extraction pipeline
# ─────────────────────────────────────────────────────────

def full_extraction_pipeline(document_text: str) -> dict:
    """End-to-end: extract → semantic validate → flag conflicts."""

    # Step 1: Guaranteed structured extraction
    extraction = extract_with_forced_tool(document_text)

    if not extraction:
        return {"error": "No tool call in response"}

    # Step 2: Semantic validation (not handled by JSON schema)
    semantic_errors = validate_semantic_correctness(extraction)

    # Step 3: Build result with validation status
    return {
        "extracted_data": extraction,
        "semantic_valid": len(semantic_errors) == 0,
        "semantic_errors": semantic_errors,
        "conflict_detected": extraction.get("conflict_detected", False),
    }


# ─────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────

SAMPLE_INVOICE = """
INVOICE #INV-2024-0892

From: Acme Corp
To: TechStartup Ltd
Date: 2024-11-01
Due: Net 30

Items:
  - Software License (5 seats) x $200 each = $1,000
  - Setup Fee = $250
  - Training (2 hours) x $100/hr = $200

Subtotal: $1,450
Tax (10%): $145
TOTAL DUE: $1,595

Payment: Bank transfer or credit card accepted.
"""

if __name__ == "__main__":
    result = full_extraction_pipeline(SAMPLE_INVOICE)
    print(json.dumps(result, indent=2, default=str))
