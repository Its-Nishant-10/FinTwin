"""Document-to-Portfolio — OWNER: Member 4.

Extracted values are proposals, not facts. Everything comes back with
needs_confirmation=True, and apply_confirmed() writes only the fields the user
has explicitly confirmed.

Three extraction paths, most reliable first:

1. CSV holdings exports: parsed by column name. Deterministic.
2. Free text (and text pulled out of PDFs): the LLM fills a fixed JSON schema.
   Each extracted number is then looked up in the source text; one that is not
   there is marked low-confidence and warned about, because a model can misread
   or invent a figure just as it can in chat.
3. No LLM available: regular expressions for the common statement phrases.

Field names are the profile paths they update:
    cashflow.monthly_income · cashflow.monthly_expenses ·
    cashflow.monthly_contribution · cash_balance · holding
A 'holding' value is a dict with symbol, quantity, current_price and optionally
name, avg_cost, asset_class.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from app.agent import llm
from app.core.logging import get_logger
from app.schemas.agent import DocumentExtraction, ExtractedField
from app.schemas.profile import AssetClass, FinancialProfile, Holding

log = get_logger(__name__)

SCALAR_FIELDS = (
    "cashflow.monthly_income",
    "cashflow.monthly_expenses",
    "cashflow.monthly_contribution",
    "cash_balance",
)

_NUM = r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)"


def _to_float(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, int | float):
        return float(raw)
    cleaned = re.sub(r"[₹,\s]|rs\.?|inr", "", str(raw), flags=re.IGNORECASE)
    try:
        return float(cleaned)
    except ValueError:
        return None


def guess_asset_class(name: str) -> AssetClass:
    text = name.lower()
    if re.search(r"liquid|debt|bond|gilt|money market|overnight|fixed income", text):
        return AssetClass.DEBT
    if "gold" in text:
        return AssetClass.GOLD
    return AssetClass.EQUITY


# ------------------------------------------------------------------------ CSV

_COLUMNS = {
    "symbol": ("symbol", "ticker", "scrip", "instrument", "trading symbol", "scheme code"),
    "name": ("name", "company", "company name", "scheme", "scheme name", "security"),
    "quantity": ("quantity", "qty", "units", "shares", "balance units", "quantity available"),
    "current_price": (
        "ltp",
        "price",
        "current price",
        "nav",
        "market price",
        "last price",
        "close",
    ),
    "value": ("market value", "current value", "value", "present value"),
    "avg_cost": (
        "avg cost",
        "average cost",
        "avg price",
        "average price",
        "buy price",
        "avg. cost",
    ),
    "sector": ("sector", "industry"),
}


def _normalize(header: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-()]", " ", header)).strip().lower()


def _cell(row: dict[str, str], column: str | None) -> str | None:
    return row.get(column) if column else None


def parse_csv(text: str, filename: str) -> DocumentExtraction:
    reader = csv.DictReader(io.StringIO(text))
    headers = {_normalize(h): h for h in (reader.fieldnames or [])}
    columns = {
        key: next((headers[a] for a in aliases if a in headers), None)
        for key, aliases in _COLUMNS.items()
    }
    warnings: list[str] = []
    if not (columns["symbol"] or columns["name"]) or not columns["quantity"]:
        return DocumentExtraction(
            filename=filename,
            doc_type="csv",
            warnings=["Could not find symbol/name and quantity columns in this CSV."],
        )
    if not (columns["current_price"] or columns["value"]):
        warnings.append("No price or value column; prices will need to be entered.")

    fields = []
    for row_number, row in enumerate(reader, start=2):

        def get(key: str, row: dict[str, str] = row) -> str | None:
            return _cell(row, columns[key])

        quantity = _to_float(get("quantity"))
        symbol = (get("symbol") or get("name") or "").strip()
        if not symbol or not quantity:
            continue
        price = _to_float(get("current_price"))
        value = _to_float(get("value"))
        if price is None and value is not None:
            price = value / quantity
        name = (get("name") or symbol).strip()
        holding = {
            "symbol": symbol,
            "name": name,
            "quantity": quantity,
            "current_price": price or 0.0,
            "avg_cost": _to_float(get("avg_cost")) or 0.0,
            "sector": (get("sector") or None),
            "asset_class": guess_asset_class(name).value,
        }
        fields.append(
            ExtractedField(field="holding", value=holding, confidence=0.95, source_page=row_number)
        )

    if not fields:
        warnings.append("No rows with both a symbol and a quantity were found.")
    return DocumentExtraction(filename=filename, doc_type="csv", fields=fields, warnings=warnings)


# ------------------------------------------------------------------ LLM path

_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "enum": ["bank_statement", "cas_statement", "broker_statement", "salary_slip", "other"],
        },
        "monthly_income": {"type": ["number", "null"]},
        "monthly_expenses": {"type": ["number", "null"]},
        "monthly_contribution": {"type": ["number", "null"]},
        "cash_balance": {"type": ["number", "null"]},
        "holdings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "name": {"type": ["string", "null"]},
                    "quantity": {"type": "number"},
                    "current_price": {"type": ["number", "null"]},
                    "avg_cost": {"type": ["number", "null"]},
                },
                "required": ["symbol", "name", "quantity", "current_price", "avg_cost"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "doc_type",
        "monthly_income",
        "monthly_expenses",
        "monthly_contribution",
        "cash_balance",
        "holdings",
    ],
    "additionalProperties": False,
}

_EXTRACTION_SYSTEM = (
    "You extract figures from Indian personal-finance documents: bank statements, "
    "mutual fund CAS statements, broker holdings and salary slips. Copy numbers exactly "
    "as they appear, in rupees, without commas. Use null for anything the document does "
    "not state; never estimate, add up or infer a figure that is not printed. "
    "monthly_income is net monthly salary or take-home pay. monthly_contribution is a "
    "recurring SIP amount. cash_balance is a closing or available bank balance."
)


def _appears_in(value: float, text: str) -> bool:
    """Is this number printed in the source, in any common formatting?"""
    digits = re.sub(r"[,\s]", "", text)
    candidates = {f"{value:.2f}", f"{value:.1f}", f"{value:g}"}
    if value == int(value):
        candidates.add(str(int(value)))
    return any(c in digits for c in candidates)


def _fields_from_llm(data: dict[str, Any], text: str) -> tuple[list[ExtractedField], list[str]]:
    fields, warnings = [], []

    def confidence_for(*values: float | None) -> float:
        printed = all(v is None or _appears_in(v, text) for v in values)
        return 0.85 if printed else 0.4

    scalars = {
        "cashflow.monthly_income": data.get("monthly_income"),
        "cashflow.monthly_expenses": data.get("monthly_expenses"),
        "cashflow.monthly_contribution": data.get("monthly_contribution"),
        "cash_balance": data.get("cash_balance"),
    }
    for field, value in scalars.items():
        if value is None:
            continue
        confidence = confidence_for(value)
        if confidence < 0.5:
            warnings.append(f"{field} = {value:g} does not appear in the document; check it.")
        fields.append(ExtractedField(field=field, value=value, confidence=confidence))

    for h in data.get("holdings", []):
        confidence = confidence_for(h.get("quantity"), h.get("current_price"))
        if confidence < 0.5:
            warnings.append(
                f"Figures for {h['symbol']} do not all appear in the document; check them."
            )
        name = h.get("name") or h["symbol"]
        fields.append(
            ExtractedField(
                field="holding",
                value={
                    "symbol": h["symbol"],
                    "name": name,
                    "quantity": h["quantity"],
                    "current_price": h.get("current_price") or 0.0,
                    "avg_cost": h.get("avg_cost") or 0.0,
                    "asset_class": guess_asset_class(name).value,
                },
                confidence=confidence,
            )
        )
    return fields, warnings


def _extract_with_llm(text: str, filename: str) -> DocumentExtraction:
    response = llm.create(
        system=_EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": f"Document ({filename}):\n\n{text}"}],
        output_format={"type": "json_schema", "schema": _EXTRACTION_SCHEMA},
    )
    try:
        data = json.loads(llm.text_of(response))
    except json.JSONDecodeError as exc:
        raise llm.LLMUnavailable("extraction output was not valid JSON") from exc
    fields, warnings = _fields_from_llm(data, text)
    return DocumentExtraction(
        filename=filename, doc_type=data.get("doc_type", "other"), fields=fields, warnings=warnings
    )


# ---------------------------------------------------------------- regex path

_SCALAR_PATTERNS = {
    "cashflow.monthly_income": (
        r"(?:net\s+(?:salary|pay)|take[- ]home(?:\s+pay)?"
        r"|monthly\s+income|salary\s+credit(?:ed)?)"
    ),
    "cashflow.monthly_expenses": r"(?:monthly\s+expenses|total\s+(?:expenses|spend(?:ing)?))",
    "cashflow.monthly_contribution": r"(?:\bsip\b(?:\s+amount)?|monthly\s+investment)",
    "cash_balance": (
        r"(?:closing\s+balance|available\s+balance|balance\s+as\s+on\s+[\w/\-. ]{1,20}?)"
    ),
}

# SYMBOL  quantity  [units]  [@]  price     e.g. "INFY 60 @ 1600" or "NIFTYBEES  400 units  280.50"
_HOLDING_LINE = re.compile(
    r"^\s*([A-Z][A-Z0-9&\-]{1,19})\s+([\d,]+(?:\.\d+)?)\s*(?:units?|shares?|qty)?\s*(?:@|at)?\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_with_regex(text: str, filename: str) -> DocumentExtraction:
    fields = []
    for field, label in _SCALAR_PATTERNS.items():
        match = re.search(label + r"\s*[:\-]?\s*" + _NUM, text, re.IGNORECASE)
        if match and (value := _to_float(match.group(1))):
            fields.append(ExtractedField(field=field, value=value, confidence=0.6))
    for symbol, quantity, price in _HOLDING_LINE.findall(text):
        fields.append(
            ExtractedField(
                field="holding",
                value={
                    "symbol": symbol.upper(),
                    "name": symbol.upper(),
                    "quantity": _to_float(quantity),
                    "current_price": _to_float(price),
                    "avg_cost": 0.0,
                    "asset_class": guess_asset_class(symbol).value,
                },
                confidence=0.5,
            )
        )
    warnings = ["Extracted with pattern matching (no LLM available); review every value."]
    if not fields:
        warnings.append("No recognisable figures were found.")
    return DocumentExtraction(filename=filename, doc_type="other", fields=fields, warnings=warnings)


# ------------------------------------------------------------------ public API


def extract_text(text: str, filename: str = "document") -> DocumentExtraction:
    """Free text -> proposed fields. Uses the LLM when available, else regexes."""
    if not text.strip():
        return DocumentExtraction(filename=filename, warnings=["The document contains no text."])
    if llm.available():
        try:
            result = _extract_with_llm(text, filename)
        except llm.LLMUnavailable as exc:
            log.warning("LLM extraction failed (%s); falling back to patterns", exc)
        else:
            result.proposed_profile = apply_fields(FinancialProfile(), result.fields)
            return result
    result = _extract_with_regex(text, filename)
    result.proposed_profile = apply_fields(FinancialProfile(), result.fields)
    return result


def _pdf_text(content: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract(filename: str, content: bytes) -> DocumentExtraction:
    """Uploaded file -> proposed fields, every one awaiting user confirmation."""
    lower = filename.lower()
    if lower.endswith(".pdf") or content.startswith(b"%PDF"):
        try:
            text = _pdf_text(content)
        except Exception as exc:  # pdfplumber raises a variety of parser errors
            log.warning("could not read PDF %s: %s", filename, exc)
            return DocumentExtraction(
                filename=filename, doc_type="pdf", warnings=[f"Could not read this PDF: {exc}"]
            )
        if not text.strip():
            return DocumentExtraction(
                filename=filename,
                doc_type="pdf",
                warnings=[
                    "No text layer found; scanned PDFs need OCR, which is not supported yet."
                ],
            )
        return extract_text(text, filename)

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return DocumentExtraction(
            filename=filename, warnings=["Unsupported file: expected PDF, CSV or UTF-8 text."]
        )

    if lower.endswith(".csv"):
        result = parse_csv(text, filename)
        result.proposed_profile = apply_fields(FinancialProfile(), result.fields)
        return result
    return extract_text(text, filename)


def apply_fields(profile: FinancialProfile, fields: list[ExtractedField]) -> FinancialProfile:
    """Write fields onto a copy of `profile`. Holdings replace any with the same symbol."""
    updated = profile.model_copy(deep=True)
    for f in fields:
        if f.field == "holding":
            holding = Holding(**{k: v for k, v in f.value.items() if v is not None})
            updated.holdings = [h for h in updated.holdings if h.symbol != holding.symbol]
            updated.holdings.append(holding)
        elif f.field in SCALAR_FIELDS:
            value = _to_float(f.value)
            if value is None or value < 0:
                raise ValueError(f"{f.field} must be a non-negative number, got {f.value!r}")
            if f.field == "cash_balance":
                updated.cash_balance = value
            else:
                setattr(updated.cashflow, f.field.split(".", 1)[1], value)
        else:
            raise ValueError(f"unknown field {f.field!r}")
    return updated


def apply_confirmed(profile: FinancialProfile, fields: list[ExtractedField]) -> FinancialProfile:
    """Apply only what the user confirmed. Unconfirmed fields never touch the profile."""
    return apply_fields(profile, [f for f in fields if not f.needs_confirmation])
