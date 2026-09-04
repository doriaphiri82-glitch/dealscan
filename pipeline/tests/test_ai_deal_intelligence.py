import json


def test_ai_enrichment_is_noop_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from ai.deal_intelligence import attach_ai_analysis

    deal = {"deal_score": 82, "asking_price": 10000}
    result = attach_ai_analysis(deal.copy(), {"county_id": "test"}, [])

    assert result["deal_score"] == 82
    assert "ai_analysis" not in result


def test_ai_notes_payload_is_json():
    from ai.deal_intelligence import attach_ai_analysis

    class FakeResponse:
        output_text = json.dumps({
            "verdict": "buy",
            "summary": "Promising candidate with valuation evidence.",
            "why_it_stands_out": ["Strong estimated spread"],
            "risks": ["Confirm access"],
            "next_steps": ["Verify title and zoning"],
            "risk_level": "medium",
            "confidence": 0.82,
        })

    class FakeResponses:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        responses = FakeResponses()

    import ai.deal_intelligence as module
    monkeypatch = __import__("pytest").MonkeyPatch()
    try:
        monkeypatch.setenv("OPENAI_API_KEY", "test")
        monkeypatch.setattr(module, "OpenAI", lambda: FakeClient())
        result = attach_ai_analysis({"deal_score": 82}, {"county_id": "test"}, [])
        payload = json.loads(result["notes"])
        assert payload["ai"]["verdict"] == "buy"
        assert result["ai_analysis"]["confidence"] == 0.82
    finally:
        monkeypatch.undo()
