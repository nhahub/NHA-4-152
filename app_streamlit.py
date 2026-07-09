import json
import uuid

import streamlit as st
from langgraph.types import Command

from graph import graph
from utils.errors import friendly_error_message

STAGE_LABELS = {
    "data_agent": "Data Agent - cleaning Facebook data",
    "insight_agent": "Insight Agent - extracting marketing insights",
    "content_agent": "Content Agent - drafting the content plan",
    "content_agent_single_post": "Content Agent - revising the selected post",
}

CAMPAIGN_UNITS = ["days", "weeks", "months"]


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_session_state():
    defaults = {
        "stage": "setup",  # setup | review | final | stopped
        "thread_id": None,
        "config": None,
        "state_values": None,  # last known full graph state (dict)
        "interrupt_payload": None,  # payload from the current human_review pause
        "approved_posts": set(),  # post_ids the user has locally marked approved
        "open_regen_box": set(),  # post_ids currently showing a feedback box
        "processing": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_for_new_campaign():
    st.session_state.stage = "setup"
    st.session_state.thread_id = None
    st.session_state.config = None
    st.session_state.state_values = None
    st.session_state.interrupt_payload = None
    st.session_state.approved_posts = set()
    st.session_state.open_regen_box = set()
    st.session_state.processing = False


# ---------------------------------------------------------------------------
# Pipeline execution helper
# ---------------------------------------------------------------------------

def run_pipeline(payload, resume: bool):
    """Runs (or resumes) the graph for the current session's thread, showing
    a live status of which agent is currently running. Returns the graph's
    state values as a dict, with an extra "__interrupt__" key set to the
    pending interrupt payload (or None if the graph reached the end)."""

    config = st.session_state.config
    stream_input = Command(resume=payload) if resume else payload

    with st.status("Running MarketPulse pipeline...", expanded=True) as status:
        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            for node_name in chunk:
                label = STAGE_LABELS.get(node_name, node_name)
                status.write(f"Completed: {label}")
        status.update(label="Pipeline step finished", state="complete")

    snapshot = graph.get_state(config)
    values = dict(snapshot.values)

    interrupt_payload = None
    for task in snapshot.tasks:
        if task.interrupts:
            interrupt_payload = task.interrupts[0].value
            break

    values["__interrupt__"] = interrupt_payload
    return values


def submit_decision(decision: dict):
    """Disables the UI, resumes the graph with the given decision, and
    updates session state with the new result."""
    st.session_state.processing = True
    try:
        result = run_pipeline(decision, resume=True)
    finally:
        st.session_state.processing = False

    st.session_state.state_values = result
    if result["__interrupt__"] is not None:
        st.session_state.interrupt_payload = result["__interrupt__"]
        st.session_state.approved_posts = set()
        st.session_state.open_regen_box = set()
        st.session_state.stage = "review"
    else:
        st.session_state.interrupt_payload = None
        st.session_state.stage = "final"


# ---------------------------------------------------------------------------
# Screen 1: Setup
# ---------------------------------------------------------------------------

def render_setup_screen():
    st.title("MarketPulse")
    st.caption("AI-powered Facebook content planning, grounded in your own page's past performance.")

    st.subheader("1. Upload your Facebook posts export")
    uploaded_file = st.file_uploader(
        "Facebook JSON export for your page",
        type=["json"],
        help="A JSON export of your page's posts, including insights, reactions, comments, and shares.",
    )

    st.subheader("2. Campaign details")
    with st.form("campaign_form"):
        title = st.text_input("Title", placeholder="e.g. Summer Sale Launch")
        description = st.text_area("Description", placeholder="What is this campaign about?")
        target_audience = st.text_area("Target Audience", placeholder="Who is this campaign for?")
        promotion = st.text_input("Promotion", placeholder="e.g. Limited-time discount, giveaway, etc.")

        col1, col2, col3 = st.columns(3)
        with col1:
            campaign_length = st.number_input("Campaign Length", min_value=1, value=2, step=1)
        with col2:
            campaign_unit = st.selectbox("Campaign Unit", CAMPAIGN_UNITS, index=1)
        with col3:
            posts_per_week = st.number_input("Posts Per Week", min_value=1, value=3, step=1)

        submitted = st.form_submit_button(
            "Generate Content Plan",
            disabled=st.session_state.processing,
            use_container_width=True,
        )

    if not submitted:
        return

    if uploaded_file is None:
        st.error("Please upload a Facebook JSON export before generating a content plan.")
        return

    try:
        facebook_json = json.load(uploaded_file)
    except json.JSONDecodeError as e:
        st.error(f"The uploaded file is not valid JSON: {e}")
        return

    if not title.strip():
        st.error("Please give the campaign a title.")
        return

    initial_state = {
        "raw_data": facebook_json,
        "dataframe": [],
        "insights": "",
        "campaign_details": {
            "title": title,
            "description": description,
            "target_audience": target_audience,
            "promotion": promotion,
            "campaign_length": int(campaign_length),
            "campaign_unit": campaign_unit,
            "posts_per_week": int(posts_per_week),
        },
        "content_plan": {
            "campaign_summary": "",
            "posts": [],
        },
        "human_feedback": "",
        "review_action": "",
        "target_post_id": None,
        "feedback_history": [],
    }

    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}
    st.session_state.processing = True

    try:
        result = run_pipeline(initial_state, resume=False)
    except Exception as e:
        st.session_state.processing = False
        st.error(f"The pipeline failed to start: {e}")
        return

    st.session_state.processing = False
    st.session_state.state_values = result

    if result["__interrupt__"] is not None:
        st.session_state.interrupt_payload = result["__interrupt__"]
        st.session_state.stage = "review"
    else:
        st.session_state.stage = "final"

    st.rerun()


# ---------------------------------------------------------------------------
# Screen 3: Human review
# ---------------------------------------------------------------------------

def render_error_banner(payload):
    st.error(friendly_error_message(payload.get("error_type"), payload.get("error") or ""))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Retry", disabled=st.session_state.processing, use_container_width=True):
            submit_decision({"action": "regenerate_all", "feedback": ""})
            st.rerun()
    with col2:
        if st.button("Stop", disabled=st.session_state.processing, use_container_width=True):
            st.session_state.stage = "stopped"
            st.rerun()


def render_post_card(post):
    post_id = post["post_id"]
    is_approved = post_id in st.session_state.approved_posts

    badge = "APPROVED" if is_approved else "DRAFT"

    with st.container(border=True):
        header_col, badge_col = st.columns([5, 1])
        with header_col:
            st.markdown(f"**Post {post_id} - {post['day']} at {post['suggested_time']}**")
            st.caption(f"Objective: {post['objective']}")
        with badge_col:
            if is_approved:
                st.success(badge)
            else:
                st.warning(badge)

        st.write(post["post_content"])

        with st.expander("Why this post?"):
            st.write(post.get("reasoning", ""))

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Approve this post",
                key=f"approve_{post_id}",
                disabled=st.session_state.processing,
                use_container_width=True,
            ):
                st.session_state.approved_posts.add(post_id)
                st.rerun()
        with col2:
            if st.button(
                "Regenerate this post",
                key=f"regen_toggle_{post_id}",
                disabled=st.session_state.processing,
                use_container_width=True,
            ):
                if post_id in st.session_state.open_regen_box:
                    st.session_state.open_regen_box.discard(post_id)
                else:
                    st.session_state.open_regen_box.add(post_id)
                st.rerun()

        if post_id in st.session_state.open_regen_box:
            feedback = st.text_area(
                "What should change in this post?",
                key=f"feedback_{post_id}",
            )
            if st.button(
                "Submit feedback",
                key=f"submit_regen_{post_id}",
                disabled=st.session_state.processing,
            ):
                st.session_state.approved_posts.discard(post_id)
                st.session_state.open_regen_box.discard(post_id)
                submit_decision({
                    "action": "regenerate_post",
                    "post_id": post_id,
                    "feedback": feedback,
                })
                st.rerun()


def render_review_screen():
    st.title("Review Content Plan")

    payload = st.session_state.interrupt_payload

    if payload.get("error"):
        render_error_banner(payload)
        return

    st.subheader("Campaign Summary")
    st.write(payload.get("campaign_summary", ""))

    st.divider()
    st.subheader("Posts")

    for post in payload.get("posts", []):
        render_post_card(post)

    st.divider()
    st.subheader("Actions for the whole plan")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve All", disabled=st.session_state.processing, use_container_width=True):
            submit_decision({"action": "approve"})
            st.rerun()

    with col2:
        if "show_regen_all_box" not in st.session_state:
            st.session_state.show_regen_all_box = False
        if st.button("Regenerate All", disabled=st.session_state.processing, use_container_width=True):
            st.session_state.show_regen_all_box = not st.session_state.show_regen_all_box
            st.rerun()

    if st.session_state.get("show_regen_all_box"):
        feedback = st.text_area("What should change across the whole plan?", key="feedback_all")
        if st.button("Submit feedback for whole plan", disabled=st.session_state.processing):
            st.session_state.show_regen_all_box = False
            submit_decision({"action": "regenerate_all", "feedback": feedback})
            st.rerun()


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def build_user_export(state):
    content_plan = state.get("content_plan", {})
    return {
        "campaign_summary": content_plan.get("campaign_summary", ""),
        "posts": [
            {
                "day": post.get("day"),
                "suggested_time": post.get("suggested_time"),
                "objective": post.get("objective"),
                "post_content": post.get("post_content"),
                "reasoning": post.get("reasoning"),
            }
            for post in content_plan.get("posts", [])
        ],
    }


# ---------------------------------------------------------------------------
# Screen 4: Final approved plan
# ---------------------------------------------------------------------------

def render_final_screen():
    st.title("Approved Content Plan")

    state_values = st.session_state.state_values
    content_plan = state_values.get("content_plan", {})

    st.subheader("Campaign Summary")
    st.write(content_plan.get("campaign_summary", ""))

    st.divider()
    st.subheader("Posts")
    for post in content_plan.get("posts", []):
        with st.container(border=True):
            st.markdown(f"**Post {post['post_id']} - {post['day']} at {post['suggested_time']}**")
            st.caption(f"Objective: {post['objective']}")
            st.write(post["post_content"])
            with st.expander("Why this post?"):
                st.write(post.get("reasoning", ""))

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download JSON",
            data=json.dumps(build_user_export(state_values), ensure_ascii=False, indent=2),
            file_name="marketpulse_content_plan.json",
            mime="application/json",
            use_container_width=True,
        )
    with col2:
        if st.button("Start New Campaign", use_container_width=True):
            reset_for_new_campaign()
            st.rerun()


# ---------------------------------------------------------------------------
# Screen: stopped (after an unrecoverable error the user chose to stop on)
# ---------------------------------------------------------------------------

def render_stopped_screen():
    st.title("Stopped")
    st.warning("The pipeline was stopped before any plan was approved. No changes were saved.")
    if st.button("Start New Campaign", use_container_width=True):
        reset_for_new_campaign()
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="MarketPulse", layout="centered")
    init_session_state()

    if st.session_state.stage == "setup":
        render_setup_screen()
    elif st.session_state.stage == "review":
        render_review_screen()
    elif st.session_state.stage == "final":
        render_final_screen()
    elif st.session_state.stage == "stopped":
        render_stopped_screen()


if __name__ == "__main__":
    main()
