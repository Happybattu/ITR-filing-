"""
form16_parser.py
Extracts key figures from a Form 16 (Part B) PDF using text extraction + regex.

Form 16 layouts vary by employer/payroll software (SAP, ADP, Zoho, in-house),
so this uses flexible label matching rather than fixed coordinates. It will
not be 100% reliable on every template — always show the user what was
extracted and let them correct it before it feeds the tax calculator.
"""

import re
import pdfplumber


FIELD_PATTERNS = {
    "gross_salary": [
        r"Gross\s+Salary.*?(?:Rs\.?|₹)?\s*([\d,]+\.?\d*)",
        r"Total\s+Gross\s+Salary.*?([\d,]+\.?\d*)",
    ],
    "standard_deduction": [
        r"Standard\s+Deduction.*?([\d,]+\.?\d*)",
    ],
    "hra_exemption": [
        r"House\s+Rent\s+Allowance.*?([\d,]+\.?\d*)",
        r"HRA.*?exempt.*?([\d,]+\.?\d*)",
    ],
    "deduction_80c": [
        r"80C.*?([\d,]+\.?\d*)",
        r"Section\s+80C.*?([\d,]+\.?\d*)",
    ],
    "deduction_80d": [
        r"80D.*?([\d,]+\.?\d*)",
    ],
    "tds_paid": [
        r"Total\s+(?:Tax\s+)?(?:Deducted|TDS).*?([\d,]+\.?\d*)",
        r"Tax\s+Deducted\s+at\s+Source.*?([\d,]+\.?\d*)",
    ],
    "pan": [
        r"PAN\s+of\s+the\s+Employee[:\s]*([A-Z]{5}\d{4}[A-Z])",
        r"\b([A-Z]{5}\d{4}[A-Z])\b",
    ],
    "employer_name": [
        r"Name\s+and\s+address\s+of\s+the\s+Employer[:\s]*([A-Za-z0-9 &.,\-]+)",
    ],
    "assessment_year": [
        r"Assessment\s+Year[:\s]*([\d\-]+)",
    ],
}


def _clean_number(raw: str) -> float:
    try:
        return float(raw.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def extract_text(pdf_path: str) -> str:
    text_chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def parse_form16(pdf_path: str) -> dict:
    """
    Returns a dict of extracted fields. Numeric fields default to 0.0 and
    text fields to '' when not found — caller (UI) should surface these as
    editable, not silently trust them.
    """
    text = extract_text(pdf_path)
    result = {}

    for field, patterns in FIELD_PATTERNS.items():
        value = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                break

        if field in ("pan", "employer_name", "assessment_year"):
            result[field] = value or ""
        else:
            result[field] = _clean_number(value) if value else 0.0

    result["_raw_text_preview"] = text[:2000]  # for manual verification in UI
    result["_extraction_warnings"] = _sanity_check(result)
    return result


def _sanity_check(fields: dict) -> list[str]:
    warnings = []
    if fields.get("gross_salary", 0) == 0:
        warnings.append("Gross salary not found — check PDF is Form 16 Part B, or enter manually.")
    if fields.get("tds_paid", 0) == 0:
        warnings.append("TDS amount not found — verify against Part A / Form 26AS.")
    if fields.get("gross_salary", 0) and fields.get("tds_paid", 0):
        if fields["tds_paid"] > fields["gross_salary"] * 0.35:
            warnings.append("TDS looks unusually high relative to gross salary — please verify.")
    return warnings


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 form16_parser.py <path-to-form16.pdf>")
    else:
        import json
        print(json.dumps(parse_form16(sys.argv[1]), indent=2))
