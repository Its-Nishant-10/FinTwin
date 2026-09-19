"""OWNER: Member 4. Extraction proposes; only the user confirms."""

from __future__ import annotations

import json

import pytest

from app.agent import extraction
from app.schemas.agent import ExtractedField
from app.schemas.profile import AssetClass, FinancialProfile
from tests.agent.fakes import ScriptedLLM, install, response, text_block

HOLDINGS_CSV = """Symbol,Company Name,Qty,Avg Cost,LTP
INFY,Infosys,60,1450,1600
LIQUIDBEES,Nippon India Liquid ETF,150,1000,1000
,Blank row,,,
"""

STATEMENT = """HDFC Bank statement for March
Net salary credited: Rs. 1,20,000
Closing balance: ₹2,50,000
SIP amount: 15,000

NIFTYBEES 400 units @ 280
"""


def test_csv_holdings_parsed_by_column_name():
    result = extraction.extract("holdings.csv", HOLDINGS_CSV.encode())
    assert result.doc_type == "csv"
    holdings = [f.value for f in result.fields]
    assert [h["symbol"] for h in holdings] == ["INFY", "LIQUIDBEES"]
    assert holdings[0]["quantity"] == 60 and holdings[0]["current_price"] == 1600
    assert holdings[1]["asset_class"] == AssetClass.DEBT.value
    assert all(f.needs_confirmation for f in result.fields)


def test_csv_value_column_gives_price():
    csv_text = "Scheme Name,Units,Current Value\nSome Gold Fund,10,5000\n"
    result = extraction.parse_csv(csv_text, "cas.csv")
    assert result.fields[0].value["current_price"] == 500
    assert result.fields[0].value["asset_class"] == AssetClass.GOLD.value


def test_csv_without_quantity_column_warns():
    result = extraction.parse_csv("Symbol,Price\nINFY,1600\n", "x.csv")
    assert not result.fields and result.warnings


def test_regex_fallback_reads_common_statement_phrases():
    result = extraction.extract("statement.txt", STATEMENT.encode())
    values = {f.field: f.value for f in result.fields if f.field != "holding"}
    assert values == {
        "cashflow.monthly_income": 120_000,
        "cash_balance": 250_000,
        "cashflow.monthly_contribution": 15_000,
    }
    holding = next(f.value for f in result.fields if f.field == "holding")
    assert holding == {**holding, "symbol": "NIFTYBEES", "quantity": 400, "current_price": 280}
    assert result.proposed_profile.cash_balance == 250_000


def test_llm_extraction_downgrades_figures_not_in_the_document(monkeypatch):
    data = {
        "doc_type": "bank_statement",
        "monthly_income": 120000,
        "monthly_expenses": None,
        "monthly_contribution": 15000,
        "cash_balance": 999999,
        "holdings": [],
    }
    scripted = install(monkeypatch, ScriptedLLM(response(text_block(json.dumps(data)))))
    result = extraction.extract_text(STATEMENT, "statement.txt")

    by_field = {f.field: f for f in result.fields}
    assert by_field["cashflow.monthly_income"].confidence > 0.8  # printed as 1,20,000
    assert by_field["cash_balance"].confidence < 0.5  # 999999 is not in the text
    assert any("cash_balance" in w for w in result.warnings)
    assert scripted.requests[0]["output_format"]["type"] == "json_schema"


def test_pdf_that_cannot_be_read_warns_instead_of_failing():
    result = extraction.extract("broken.pdf", b"%PDF-1.4 not really a pdf")
    assert not result.fields and result.warnings


def test_only_confirmed_fields_are_applied(profile):
    fields = [
        ExtractedField(
            field="cash_balance", value=500_000, confidence=0.9, needs_confirmation=False
        ),
        ExtractedField(field="cashflow.monthly_income", value=1, confidence=0.9),  # not confirmed
    ]
    updated = extraction.apply_confirmed(profile, fields)
    assert updated.cash_balance == 500_000
    assert updated.cashflow.monthly_income == profile.cashflow.monthly_income
    assert profile.cash_balance == 250_000  # the original is not mutated


def test_confirmed_holding_replaces_same_symbol(profile):
    field = ExtractedField(
        field="holding",
        confidence=0.9,
        needs_confirmation=False,
        value={"symbol": "INFY", "quantity": 100, "current_price": 1700},
    )
    updated = extraction.apply_confirmed(profile, [field])
    infy = [h for h in updated.holdings if h.symbol == "INFY"]
    assert len(infy) == 1 and infy[0].quantity == 100


def test_unknown_field_is_rejected():
    with pytest.raises(ValueError):
        extraction.apply_fields(
            FinancialProfile(), [ExtractedField(field="net_worth", value=1, confidence=1)]
        )


def test_extract_and_confirm_routes(client, profile):
    extracted = client.post(
        "/documents/extract", files={"file": ("holdings.csv", HOLDINGS_CSV, "text/csv")}
    ).json()
    assert len(extracted["fields"]) == 2

    fields = extracted["fields"]
    fields[0]["needs_confirmation"] = False  # the user ticks INFY only
    confirmed = client.post(
        "/documents/confirm", json={"profile": profile.model_dump(mode="json"), "fields": fields}
    )
    assert confirmed.status_code == 200
    symbols = [h["symbol"] for h in confirmed.json()["holdings"]]
    assert symbols.count("INFY") == 1 and "LIQUIDBEES" in symbols  # LIQUIDBEES was already held
