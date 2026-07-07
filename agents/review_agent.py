"""
Review Agent: pauses the graph at a human-in-the-loop checkpoint
(human_review) and routes to the right next node based on the reviewer's
decision (approve / regenerate_all / regenerate_post).
"""

from langgraph.types import interrupt

from state import MarketingState


def human_review(state: MarketingState) -> dict:
    content_plan = state["content_plan"]

    # This pauses the graph. Whatever dict is passed to interrupt() is what
    # shows up in the interrupt payload on the caller side (see graph.get_state).
    decision = interrupt({
        "review_type": "content_plan",
        "campaign_summary": content_plan.get("campaign_summary", ""),
        "posts": content_plan.get("posts", []),
        "error": content_plan.get("error"),
        "error_type": content_plan.get("error_type"),
    })

    action = decision.get("action", "approve")

    if action == "regenerate_all":
        return {
            "review_action": "regenerate_all",
            "human_feedback": decision.get("feedback", ""),
        }
    elif action == "regenerate_post":
        return {
            "review_action": "regenerate_post",
            "human_feedback": decision.get("feedback", ""),
            "target_post_id": decision.get("post_id"),
        }
    else:
        return {"review_action": "approve"}


def route_after_review(state: MarketingState) -> str:
    action = state.get("review_action", "approve")
    if action == "regenerate_all":
        return "content_agent"
    elif action == "regenerate_post":
        return "content_agent_single_post"
    return "end"
