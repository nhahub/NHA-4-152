import time
import os

import pytest

from agents import data_agent, insight_agent, content_agent
from utils import errors


def make_synthetic_export(n):
    base = {"message": "x", "created_time": "t", "insights": {"data": [{"name": "post_impressions_fan", "values": [{"value": 100}]}, {"name": "post_clicks", "values": [{"value": 5}]}]}, "reactions": {"summary": {"total_count": 1}}, "comments": {"summary": {"total_count": 1}}, "shares": {"count": 0}}
    return [dict(base) for _ in range(n)]


def test_data_agent_500_posts_fast():
    raw = make_synthetic_export(500)
    start = time.perf_counter()
    out = data_agent.data_agent({"raw_data": raw})
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0


def test_call_structured_llm_with_retry_quota_fast(monkeypatch):
    class S:
        def invoke(self, *a, **k):
            raise Exception("429 Too Many Requests")

    start = time.perf_counter()
    res = errors.call_structured_llm_with_retry(S(), "p", max_attempts=5, backoff_seconds=1)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0


@pytest.mark.timeout(2)
def test_full_pipeline_mocked_fast(monkeypatch, sample_facebook_json, sample_campaign_details):
    # Mock LLMs to return instantly
    class L:
        def with_structured_output(self, m):
            class Impl:
                def invoke(self, prompt):
                    from state import ContentPlan, PostItem
                    return ContentPlan(campaign_summary="s", posts=[PostItem(day="d", suggested_time="t", objective="o", post_content="c", reasoning="r")])

            return Impl()

        def invoke(self, prompt):
            class R:
                content = "ins"

            return R()

    monkeypatch.setattr(content_agent, "get_llm", lambda name, temperature=0.5: L())
    monkeypatch.setattr(insight_agent, "get_llm", lambda name, temperature=0.5: L())

    start = time.perf_counter()
    # run the core functions end-to-end (not using graph.invoke for speed/reliability)
    df = data_agent.data_agent({"raw_data": sample_facebook_json})
    insights = insight_agent.insight_agent({"dataframe": df["dataframe"]})
    res = content_agent.content_agent({"insights": insights["insights"], "campaign_details": sample_campaign_details, "human_feedback": "", "feedback_history": []})
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0


def _live_ok():
    return os.environ.get("RUN_LIVE_TESTS") == "1"


@pytest.mark.live
@pytest.mark.skipif(not _live_ok(), reason="Live tests disabled")
def test_live_insight_latency():
    import config, os
    import time
    llm = config.get_llm("insight", temperature=0.3)
    start = time.perf_counter()
    r = llm.invoke(["trivial prompt"])
    assert (time.perf_counter() - start) < int(os.environ.get("LIVE_TEST_TIMEOUT_SECONDS", "20"))


@pytest.mark.live
@pytest.mark.skipif(not _live_ok(), reason="Live tests disabled")
def test_live_content_latency():
    import config, os
    import time
    llm = config.get_llm("content", temperature=0.8)
    start = time.perf_counter()
    r = llm.invoke(["trivial prompt"])
    assert (time.perf_counter() - start) < int(os.environ.get("LIVE_TEST_TIMEOUT_SECONDS", "20"))
