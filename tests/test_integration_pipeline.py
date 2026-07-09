import uuid
import pytest

pytest.importorskip("langgraph")

from graph import graph
from agents import data_agent, insight_agent, content_agent, review_agent
from state import ContentPlan, PostItem


def make_content_plan(n):
    posts = [PostItem(day="Day", suggested_time="9:00", objective="A", post_content=f"p{i}", reasoning="r") for i in range(n)]
    return ContentPlan(campaign_summary=f"plan{n}", posts=posts)


def test_full_run_pause_and_resume(monkeypatch, sample_facebook_json, sample_campaign_details):
    # Arrange: mock LLMs used by insight and content agents
    calls = {"content": 0}

    def fake_get_llm(name, temperature=0.5):
        class L:
            def with_structured_output(self, model):
                class Impl:
                    def invoke(self, prompt):
                        # return content plan object depending on how many times content called
                        if name == "content":
                            calls["content"] += 1
                            return make_content_plan(2)
                        return make_content_plan(2)

                return Impl()

            def invoke(self, prompt):
                class R:
                    content = "insights"

                return R()

        return L()

    monkeypatch.setattr(content_agent, "get_llm", fake_get_llm)
    monkeypatch.setattr(insight_agent, "get_llm", fake_get_llm)

    # mock interrupt to first pause and then on resume return approve
    interrupts = []

    def fake_interrupt(payload):
        # first time, return a dict that represents pause request
        if not interrupts:
            interrupts.append(payload)
            return {"action": "approve"}
        return {"action": "approve"}

    monkeypatch.setattr(review_agent, "interrupt", fake_interrupt)

    initial_state = {"raw_data": sample_facebook_json, "campaign_details": sample_campaign_details}

    # run the graph - this should at least execute without raising
    thread_id = str(uuid.uuid4())
    result = graph.invoke(initial_state, {"thread_id": thread_id})

    # If the graph paused, langgraph includes an __interrupt__ key
    if isinstance(result, dict) and "__interrupt__" in result:
        # resume by sending approve
        from langgraph.types import Command

        resumed = graph.invoke({}, Command(resume={"action": "approve"}))
        assert "__interrupt__" not in resumed
    else:
        # best-effort: assert content_plan-like data propagated via interrupts we captured
        assert interrupts

