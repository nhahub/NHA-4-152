"""
Data Agent: flattens the raw Facebook JSON export into a clean, feature-
engineered table (message, reach, clicks, reactions, comments, shares,
total_engagement, engagement_rate, ctr).
"""

import pandas as pd

from state import MarketingState


def data_agent(state: MarketingState) -> dict:
    raw = state["raw_data"]
    posts = raw["data"] if isinstance(raw, dict) else raw

    # -----------------------------
    # 1. Flatten Facebook JSON -> DataFrame
    # -----------------------------
    rows = []
    for post in posts:
        insights_list = post.get("insights", {}).get("data", [])
        insights_map = {item["name"]: item["values"][0]["value"] for item in insights_list}

        reach = insights_map.get("post_impressions_fan", 0)
        clicks = insights_map.get("post_clicks", 0)

        rows.append({
            "message": post.get("message", ""),
            "created_time": post.get("created_time", "Unknown"),
            "reach": reach,
            "clicks": clicks,
            "reactions": post.get("reactions", {}).get("summary", {}).get("total_count", 0),
            "comments": post.get("comments", {}).get("summary", {}).get("total_count", 0),
            "shares": post.get("shares", {}).get("count", 0),
        })

    df = pd.DataFrame(rows).drop_duplicates()

    numeric_columns = df.select_dtypes(include="number").columns
    df[numeric_columns] = df[numeric_columns].fillna(0)
    df = df.fillna("Unknown")

    # -----------------------------
    # 2. Feature Engineering (Engagement Metrics)
    # -----------------------------
    df["total_engagement"] = df["reactions"] + df["comments"] + df["shares"]
    df["engagement_rate"] = df.apply(
        lambda r: round(r["total_engagement"] / r["reach"], 4) if r["reach"] > 0 else 0, axis=1
    )
    df["ctr"] = df.apply(
        lambda r: round(r["clicks"] / r["reach"], 4) if r["reach"] > 0 else 0, axis=1
    )

    # -----------------------------
    # 3. Return Cleaned State
    # -----------------------------
    return {
        # store as list of dict records so LangGraph's checkpointer (msgpack)
        # can serialize the state - reconstruct with pd.DataFrame(...) when needed
        "dataframe": df.to_dict("records")
    }
