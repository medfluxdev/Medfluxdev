"""Conservative reconciliation must not invent a contractual unit rate."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.contract_intelligence.invoice import (
    ContractCharge,
    InvoiceLine,
    reconcile_invoice,
    value_leakage,
)


def _charge():
    return ContractCharge(
        label="Maintenance", amount=Decimal("100.00"),
        currency="EUR", charge_type="fixed", applicable=True,
    )


def test_multi_unit_total_cannot_be_compared_to_single_normalized_charge():
    findings = reconcile_invoice(
        [InvoiceLine(
            label="Maintenance", amount=Decimal("200.00"),
            currency="EUR", quantity=Decimal("2"),
        )],
        [_charge()],
    )
    assert len(findings) == 1
    assert findings[0].outcome == "unknown"
    assert findings[0].requires_review is True
    assert value_leakage(findings) == {}


def test_single_unit_explicit_quantity_still_matches():
    findings = reconcile_invoice(
        [InvoiceLine(
            label="Maintenance", amount=Decimal("100.00"),
            currency="EUR", quantity=Decimal("1"),
        )],
        [_charge()],
    )
    assert findings[0].outcome == "matched"
    assert findings[0].requires_review is False


def test_unspecified_quantity_preserves_existing_normalized_comparison():
    findings = reconcile_invoice(
        [InvoiceLine(
            label="Maintenance", amount=Decimal("120.00"),
            currency="EUR",
        )],
        [_charge()],
    )
    assert findings[0].outcome == "overbilled"
    assert value_leakage(findings) == {"EUR": Decimal("20.00")}


@pytest.mark.parametrize("quantity", ["0", "-1", "-0.01"])
def test_invoice_rejects_nonpositive_quantities(quantity):
    with pytest.raises(ValidationError):
        InvoiceLine(
            label="Maintenance", amount=Decimal("100"),
            currency="EUR", quantity=Decimal(quantity),
        )


@pytest.mark.parametrize("quantity", [None, Decimal("1"), Decimal("2")])
def test_invoice_explicit_unit_without_contract_unit_basis_requires_review(quantity):
    findings = reconcile_invoice(
        [InvoiceLine(
            label="Maintenance", amount=Decimal("200.00"),
            currency="EUR", quantity=quantity, unit="per device",
        )],
        [_charge()],
    )
    assert findings[0].outcome == "unknown"
    assert findings[0].requires_review
    assert value_leakage(findings) == {}
