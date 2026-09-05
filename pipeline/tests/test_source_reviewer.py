from ai.source_reviewer import SourceReview, build_source_review_agent


def test_source_review_schema_is_bounded():
    review = SourceReview(
        priority=85,
        likely_parcel_source=True,
        likely_authoritative=True,
        verification_focus=["query sample records", "validate APN mapping"],
        rationale="Official-looking parcel layer with an explicit identifier.",
    )
    assert 0 <= review.priority <= 100
    assert review.likely_parcel_source is True
    assert review.verification_focus


def test_agent_construction_does_not_require_api_call():
    agent = build_source_review_agent()
    assert agent.name == "DealScan Source Reviewer"
    assert agent.output_type is SourceReview
