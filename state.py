"""
Shared state definitions for the MarketPulse LangGraph pipeline.

- TypedDicts describe the graph state (MarketingState) and its nested pieces.
- Pydantic models (ContentPlan, PostItem) are used as structured-output
  schemas for the LLM calls in the content agents.
"""

from typing import TypedDict

from pydantic import BaseModel, Field


class CampaignDetails(TypedDict):
    title: str
    description: str
    target_audience: str
    promotion: str
    campaign_length: int
    campaign_unit: str
    posts_per_week: int


class PostItemDict(TypedDict):
    post_id: int
    day: str
    suggested_time: str
    objective: str
    post_content: str
    reasoning: str
    status: str


class ContentPlanDict(TypedDict):
    campaign_summary: str
    posts: list[PostItemDict]


class MarketingState(TypedDict):
    raw_data: dict
    dataframe: list
    insights: str
    campaign_details: CampaignDetails
    content_plan: ContentPlanDict
    # --- Human-in-the-loop fields ---
    human_feedback: str  # free-text feedback from the reviewer
    review_action: str  # "approve" | "regenerate_all" | "regenerate_post"
    target_post_id: int  # which post_id to regenerate (if action == regenerate_post)
    feedback_history: list  # log of every round of feedback, for traceability


class PostItem(BaseModel):
    day: str = Field(description="Day name, e.g. Monday")
    suggested_time: str = Field(description="Suggested posting time, e.g. 7:00 PM")
    objective: str = Field(description="Post objective: Awareness / Engagement / Conversion")
    post_content: str = Field(description="Full post content, ready to publish")
    reasoning: str = Field(description="Reason for choosing this time and content, based on the insights")


class ContentPlan(BaseModel):
    campaign_summary: str = Field(description="Short summary of the campaign strategy")
    posts: list[PostItem]
