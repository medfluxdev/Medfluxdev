"""Small event vocabulary for future workflow orchestration.

This intentionally avoids adding Redis/NATS/Temporal today. The application can
emit these stable events into an outbox now and connect a transport later.
"""

CONTRACT_ACCEPTED = "contract.accepted"
CONTRACT_REANALYZED = "contract.reanalyzed"
DOCUMENT_LINKED = "contract.document_linked"
AMENDMENT_ADDED = "contract.amendment_added"
OBLIGATION_DUE = "obligation.due"
OBLIGATION_BREACHED = "obligation.breached"
INVOICE_RECEIVED = "invoice.received"
DEVICE_UNCOVERED = "equipment.uncovered"
REVIEW_REQUIRED = "review.required"
