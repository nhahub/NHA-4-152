"""
Insight Agent: analyzes the cleaned Facebook data and produces actionable
marketing insights (best posting times, top hooks, success characteristics,
trends) that the Content Agent will later build on.
"""

import pandas as pd
from langchain_core.messages import HumanMessage

from config import get_llm
from prompts import INSIGHT_AGENT_PROMPT
from state import MarketingState


def insight_agent(state: MarketingState) -> dict:
    df = pd.DataFrame(state["dataframe"])

    analysis_df = df[
        [
            "message",
            "created_time",
            "reach",
            "clicks",
            "reactions",
            "comments",
            "shares",
            "total_engagement",
            "engagement_rate",
            "ctr",
        ]
    ]

    llm = get_llm("insight", temperature=0.3)

    prompt = INSIGHT_AGENT_PROMPT.format(
        dataset=analysis_df.to_markdown(index=False)
    )

    response = llm.invoke([HumanMessage(content=prompt)])

    return {
        "insights": response.content
    }
