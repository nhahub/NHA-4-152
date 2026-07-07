"""
Builds and compiles the MarketPulse LangGraph pipeline.

Pipeline shape:

    START -> data_agent -> insight_agent -> content_agent -> human_review
                                                 ^                 |
                                                 |                 v
                                    content_agent_single_post <--- (regenerate_post)
                                                 |                 |
                                                 +---------------->+
                                                                   |
                                                          (regenerate_all) -> content_agent
                                                                   |
                                                              (approve) -> END

A MemorySaver checkpointer is required for interrupt()/Command(resume=...)
to work - it's what lets the graph "remember" where it paused between calls.
Each Streamlit session uses its own thread_id, so concurrent users don't
share or collide on paused state.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.content_agent import content_agent, content_agent_single_post
from agents.data_agent import data_agent
from agents.insight_agent import insight_agent
from agents.review_agent import human_review, route_after_review
from state import MarketingState

builder = StateGraph(MarketingState)

builder.add_node("data_agent", data_agent)
builder.add_node("insight_agent", insight_agent)
builder.add_node("content_agent", content_agent)
builder.add_node("content_agent_single_post", content_agent_single_post)
builder.add_node("human_review", human_review)

builder.add_edge(START, "data_agent")
builder.add_edge("data_agent", "insight_agent")
builder.add_edge("insight_agent", "content_agent")
builder.add_edge("content_agent", "human_review")
builder.add_edge("content_agent_single_post", "human_review")

builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {
        "end": END,
        "content_agent": "content_agent",
        "content_agent_single_post": "content_agent_single_post",
    },
)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
