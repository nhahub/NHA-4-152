import copy

from agents import content_agent as ca
from state import ContentPlan, PostItem


def test_build_offer_details_minimal():
    campaign = {"title": "T", "description": "D", "target_audience": "A", "promotion": "P"}
    s = ca.build_offer_details(campaign)
    for v in campaign.values():
        assert str(v) in s


def test_content_agent_assigns_ids_and_history(monkeypatch, sample_campaign_details):
    # build a fake content plan result with two posts
    posts = [PostItem(day="Mon", suggested_time="7:00", objective="Awareness", post_content="A", reasoning="r"),
             PostItem(day="Tue", suggested_time="8:00", objective="Engage", post_content="B", reasoning="r2")]
    cp = ContentPlan(campaign_summary="sum", posts=posts)

    def fake_retry(structured_llm, prompt, max_attempts=3, backoff_seconds=2):
        return cp, None, None

    monkeypatch.setattr(ca, "call_structured_llm_with_retry", fake_retry)

    state = {"insights": "x", "campaign_details": sample_campaign_details, "human_feedback": "", "feedback_history": []}
    out = ca.content_agent(state)
    plan = out["content_plan"]
    assert len(plan["posts"]) == 2
    for i, p in enumerate(plan["posts"], start=1):
        assert p["post_id"] == i
        assert p["status"] == "draft"
    assert out["human_feedback"] == ""

    # when human_feedback provided, it's recorded in history
    monkeypatch.setattr(ca, "call_structured_llm_with_retry", fake_retry)
    state2 = {"insights": "x", "campaign_details": sample_campaign_details, "human_feedback": "please change", "feedback_history": []}
    out2 = ca.content_agent(state2)
    assert out2["feedback_history"][0]["scope"] == "all"


def test_content_agent_quota_returns_error(monkeypatch, sample_campaign_details):
    def fake_retry_fail(structured_llm, prompt, max_attempts=3, backoff_seconds=2):
        return None, "quota_or_rate_limit", "quota msg"

    monkeypatch.setattr(ca, "call_structured_llm_with_retry", fake_retry_fail)
    state = {"insights": "x", "campaign_details": sample_campaign_details, "human_feedback": "", "feedback_history": []}
    out = ca.content_agent(state)
    assert out["content_plan"]["posts"] == []
    assert out["content_plan"]["error_type"] == "quota_or_rate_limit"
    assert "error" in out["content_plan"]


def test_content_agent_single_post_replaces_target(monkeypatch, sample_campaign_details):
    # initial plan with two posts
    plan = {"campaign_summary": "s", "posts": [
        {"post_id": 1, "day": "Mon", "suggested_time": "7:00", "objective": "A", "post_content": "old1", "reasoning": "r", "status": "draft"},
        {"post_id": 2, "day": "Tue", "suggested_time": "8:00", "objective": "B", "post_content": "old2", "reasoning": "r2", "status": "draft"},
    ]}

    new_post = PostItem(day="Mon", suggested_time="7:00", objective="A", post_content="new1", reasoning="newr")

    def fake_retry(structured_llm, prompt, max_attempts=3, backoff_seconds=2):
        return new_post, None, None

    monkeypatch.setattr(ca, "call_structured_llm_with_retry", fake_retry)

    state = {"campaign_details": sample_campaign_details, "content_plan": plan, "target_post_id": 1, "human_feedback": "fix this", "insights": "x", "feedback_history": []}
    out = ca.content_agent_single_post(state)
    cp = out["content_plan"]
    assert any(p["post_content"] == "new1" for p in cp["posts"]) 
    assert out["target_post_id"] is None
    assert out["human_feedback"] == ""
    assert out["feedback_history"][0]["scope"] == "post_1"


def test_content_agent_single_post_no_target_noop(monkeypatch):
    # get_llm must be mocked even if target missing
    monkeypatch.setattr(ca, "get_llm", lambda name, temperature: None)
    plan = {"campaign_summary": "s", "posts": []}
    state = {"campaign_details": {}, "content_plan": plan, "target_post_id": 999, "human_feedback": "", "insights": "x", "feedback_history": []}
    out = ca.content_agent_single_post(state)
    assert out == {"human_feedback": "", "target_post_id": None}
    