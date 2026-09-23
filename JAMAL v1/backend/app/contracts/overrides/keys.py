"""Stabile Override-Keys für `contract_override` (UAT Defect Batch A).

Diese Keys sind Teil des persistenten Schemas und dürfen nicht beliebig
umbenannt werden. Sie steuern, welche materialen Vertragsfakte manuell
bestätigt/überschrieben werden können.
"""

# Steuer-Basis der wiederkehrenden Kosten ("net" | "gross").
OVERRIDE_KEY_TAX_BASIS = "cost.tax_basis"
# Steuersatz in Prozent (z. B. 19.0).
OVERRIDE_KEY_TAX_RATE_PERCENT = "cost.tax_rate_percent"
# Ereignisbasierter Vertragsbeginn – aufgelöstes (tatsächliches) Ereignis-Datum.
OVERRIDE_KEY_EVENT_START = "date.event_start"
# Generische manuelle Bestätigung eines extrahierten Fakt (fact_ref = Feld).
OVERRIDE_KEY_FACT_CONFIRM = "fact.confirm"

# Keys, die einen wirksamen Override-Wert tragen können (set/void).
OVERRIDE_VALUE_KEYS = frozenset(
    {
        OVERRIDE_KEY_TAX_BASIS,
        OVERRIDE_KEY_TAX_RATE_PERCENT,
        OVERRIDE_KEY_EVENT_START,
    }
)

ALLOWED_KEYS = frozenset(
    {
        OVERRIDE_KEY_TAX_BASIS,
        OVERRIDE_KEY_TAX_RATE_PERCENT,
        OVERRIDE_KEY_EVENT_START,
        OVERRIDE_KEY_FACT_CONFIRM,
    }
)
