from datetime import date
from uuid import uuid4

from app.contract_intelligence.models import PortfolioQuestion
from app.contract_intelligence.portfolio import answer_portfolio_question


def test_supplier_text_query_filters_accepted_rows():
    first = uuid4()
    second = uuid4()
    rows = [
        {"contract_id": first, "supplier": "Siemens Healthineers", "end_date": date(2027, 1, 1)},
        {"contract_id": second, "supplier": "GE Healthcare", "end_date": date(2027, 1, 1)},
    ]
    result = answer_portfolio_question(PortfolioQuestion(query="Siemens", as_of_date=date(2026, 9, 13)), rows)
    assert result.contract_ids == [first]


def test_german_expiry_query_uses_contract_end_dates():
    active = uuid4()
    past = uuid4()
    rows = [
        {"contract_id": active, "supplier": "A", "end_date": date(2027, 1, 1)},
        {"contract_id": past, "supplier": "B", "end_date": date(2025, 1, 1)},
    ]
    result = answer_portfolio_question(PortfolioQuestion(query="Welche Verträge enden?", as_of_date=date(2026, 9, 13)), rows)
    assert result.contract_ids == [active]
