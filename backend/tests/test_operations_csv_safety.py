from app.api.routes.operations import _csv_safe


def test_csv_safe_neutralizes_formula_prefixes() -> None:
    assert _csv_safe("=HYPERLINK(\"https://example.invalid\")") == "'=HYPERLINK(\"https://example.invalid\")"
    assert _csv_safe("+1+1") == "'+1+1"
    assert _csv_safe("-2+3") == "'-2+3"
    assert _csv_safe("@SUM(A1:A2)") == "'@SUM(A1:A2)"


def test_csv_safe_neutralizes_formula_after_leading_whitespace() -> None:
    assert _csv_safe("  =1+1") == "'  =1+1"
    assert _csv_safe("\t@SUM(A1:A2)") == "'\t@SUM(A1:A2)"


def test_csv_safe_preserves_normal_contract_values() -> None:
    assert _csv_safe("MEDTRON AG") == "MEDTRON AG"
    assert _csv_safe("CSV-ACTIVE-1") == "CSV-ACTIVE-1"
    assert _csv_safe(None) == ""
