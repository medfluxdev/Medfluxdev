"""Safety regression for contract-review completion.

Critical material facts may never be waived with a blanket acknowledgement.
"""

import pytest

from app.contracts.review.service import ReviewError, complete_review


def test_complete_review_rejects_unreviewed_critical_facts_before_db_access():
    with pytest.raises(ReviewError, match="kritische ungeprüfte"):
        complete_review(
            None,
            organization_id="org",
            contract_id="contract",
            reviewer_display_name="Reviewer",
            note="I acknowledge everything",
            acknowledge_unreviewed=True,
            relevant_count=3,
            reviewed_count=2,
            critical_unreviewed_count=1,
        )
