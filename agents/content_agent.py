"""
Content Agent: turns marketing insights + campaign details into a full
Facebook content calendar (content_agent), and revises a single post in
that calendar based on reviewer feedback (content_agent_single_post).
"""

from config import get_llm
from prompts import CONTENT_AGENT_PROMPT, SINGLE_POST_PROMPT
from state import CampaignDetails, ContentPlan, MarketingState, PostItem
from utils.errors import call_structured_llm_with_retry


def build_offer_details(campaign: CampaignDetails) -> str:
    return f"""Title: {campaign["title"]}
Description: {campaign["description"]}
Target Audience: {campaign["target_audience"]}
Promotion: {campaign["promotion"]}"""


def content_agent(state: MarketingState) -> dict:
    llm = get_llm("content", temperature=0.8)
    structured_llm = llm.with_structured_output(ContentPlan)

    insights = state["insights"]
    campaign = state["campaign_details"]

    offer_details = build_offer_details(campaign)

    campaign_details = f"""Campaign Length: {campaign["campaign_length"]} {campaign["campaign_unit"]}
Posts Per Week: {campaign["posts_per_week"]}"""
    expected_posts_count = campaign["campaign_length"] * campaign["posts_per_week"]
    post_count_instruction = (
        f"POST COUNT REQUIREMENT:\n"
        f"Generate EXACTLY {expected_posts_count} posts. Not {expected_posts_count - 1}, "
        f"not {expected_posts_count + 1} — exactly {expected_posts_count} posts, no more, "
        f"no less."
    )

    prompt = CONTENT_AGENT_PROMPT.format(
        insights=insights,
        offer_details=offer_details,
        campaign_details=campaign_details,
        post_count_instruction=post_count_instruction,
    )

    # --- Human-in-the-loop: fold in feedback from a previous review round ---
    feedback = state.get("human_feedback", "")
    if feedback:
        prompt += f"""

IMPORTANT - Human Feedback on the Previous Draft (this is a revision round):
{feedback}

Revise the ENTIRE content plan so it fully addresses this feedback. Keep everything
that was already working well; change only what the feedback asks you to change.
"""

    result, error_type, raw_error = call_structured_llm_with_retry(structured_llm, prompt)

    if result is not None:
        content_plan = result.model_dump()
        posts = content_plan.get("posts", [])

        if len(posts) > expected_posts_count:
            content_plan["posts"] = posts[:expected_posts_count]
        elif len(posts) < expected_posts_count:
            retry_prompt = (
                f"{prompt}\n\nPOST COUNT FIX:\n"
                f"Your previous attempt returned {len(posts)} posts instead of the required "
                f"{expected_posts_count}. Generate exactly {expected_posts_count} posts this time."
            )
            retry_result, retry_error_type, retry_raw_error = call_structured_llm_with_retry(
                structured_llm,
                retry_prompt,
            )
            if retry_result is not None:
                content_plan = retry_result.model_dump()
                retry_posts = content_plan.get("posts", [])
                if len(retry_posts) > expected_posts_count:
                    content_plan["posts"] = retry_posts[:expected_posts_count]
                elif len(retry_posts) < expected_posts_count:
                    content_plan["error_type"] = "post_count_mismatch"
                    content_plan["error"] = (
                        f"Expected {expected_posts_count} posts but received {len(retry_posts)}."
                    )
            else:
                content_plan["error_type"] = "post_count_mismatch"
                content_plan["error"] = (
                    f"Expected {expected_posts_count} posts but received {len(posts)}."
                )
    else:
        content_plan = {
            "campaign_summary": "",
            "posts": [],
            "error": raw_error,
            "error_type": error_type,
        }

    for idx, post in enumerate(content_plan["posts"], start=1):
        post["post_id"] = idx
        post["status"] = "draft"

    history = state.get("feedback_history", [])
    if feedback:
        history = history + [{"round": len(history) + 1, "scope": "all", "feedback": feedback}]

    # clear the feedback once it's been applied, so it doesn't leak into
    # a later round where the reviewer didn't say anything new
    return {
        "content_plan": content_plan,
        "human_feedback": "",
        "feedback_history": history,
    }


def content_agent_single_post(state: MarketingState) -> dict:
    campaign = state["campaign_details"]
    content_plan = state["content_plan"]
    target_id = state.get("target_post_id")
    feedback = state.get("human_feedback", "")

    posts = content_plan["posts"]
    target_post = next((p for p in posts if p["post_id"] == target_id), None)

    if target_post is None:
        # nothing to do, target_post_id was invalid - just go back to review
        return {"human_feedback": "", "target_post_id": None}

    llm = get_llm("content", temperature=0.8)
    structured_llm = llm.with_structured_output(PostItem)

    other_posts_summary = "\n".join(
        f"- ({p['objective']}) {p['post_content'][:80]}..."
        for p in posts if p["post_id"] != target_id
    )

    prompt = SINGLE_POST_PROMPT.format(
        insights=state["insights"],
        offer_details=build_offer_details(campaign),
        other_posts_summary=other_posts_summary,
        day=target_post["day"],
        suggested_time=target_post["suggested_time"],
        objective=target_post["objective"],
        current_content=target_post["post_content"],
        feedback=feedback,
    )

    result, error_type, raw_error = call_structured_llm_with_retry(structured_llm, prompt)

    if result is not None:
        updated = result.model_dump()
        updated["post_id"] = target_id
        updated["status"] = "draft"
        posts = [updated if p["post_id"] == target_id else p for p in posts]
        content_plan["posts"] = posts
        content_plan.pop("error", None)
        content_plan.pop("error_type", None)
    else:
        # keep the old post untouched, but surface the error so human_review can warn about it
        content_plan["error"] = raw_error
        content_plan["error_type"] = error_type

    history = state.get("feedback_history", [])
    history = history + [{"round": len(history) + 1, "scope": f"post_{target_id}", "feedback": feedback}]

    return {
        "content_plan": content_plan,
        "human_feedback": "",
        "target_post_id": None,
        "feedback_history": history,
    }
