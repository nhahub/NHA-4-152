from agents import review_agent as ra


def test_route_after_review_mapping():
    assert ra.route_after_review({"review_action": "approve"}) == "end"
    assert ra.route_after_review({"review_action": "regenerate_all"}) == "content_agent"
    assert ra.route_after_review({"review_action": "regenerate_post"}) == "content_agent_single_post"
    assert ra.route_after_review({}) == "end"


def test_human_review_interrupts_and_returns(monkeypatch):
    captured = {}

    def fake_interrupt(payload):
        captured["payload"] = payload
        return {"action": "approve"}

    monkeypatch.setattr(ra, "interrupt", fake_interrupt)
    state = {"content_plan": {"campaign_summary": "s", "posts": []}}
    out = ra.human_review(state)
    assert out == {"review_action": "approve"}
    assert "campaign_summary" in captured["payload"]


def test_human_review_various_actions(monkeypatch):
    def int_approve(p):
        return {"action": "approve"}

    def int_regen_all(p):
        return {"action": "regenerate_all", "feedback": "please"}

    def int_regen_post(p):
        return {"action": "regenerate_post", "post_id": 5, "feedback": "fix post"}

    monkeypatch.setattr(ra, "interrupt", int_regen_all)
    out = ra.human_review({"content_plan": {}})
    assert out["review_action"] == "regenerate_all"
    assert out["human_feedback"] == "please"

    monkeypatch.setattr(ra, "interrupt", int_regen_post)
    out2 = ra.human_review({"content_plan": {}})
    assert out2["review_action"] == "regenerate_post"
    assert out2["target_post_id"] == 5
