"""
Error handling helpers shared by the content-generation agents.

- classify_llm_error: tells a quota/rate-limit failure apart from any
  other failure (bad JSON, schema mismatch, etc).
- friendly_error_message: turns that classification into a message that
  can be shown directly in the UI.
- call_structured_llm_with_retry: wraps a structured-output LLM call with
  a small retry loop, skipping retries entirely on quota errors.
"""

import time

from langchain_core.messages import HumanMessage

QUOTA_MARKERS = ["429", "rate_limit", "rate limit", "quota", "insufficient_quota", "too many requests"]


def classify_llm_error(e: Exception) -> str:
    """Best-effort read of the exception to tell a real quota/rate-limit
    problem apart from other failures (bad JSON, schema mismatch, etc)."""
    msg = str(e).lower()
    if any(marker in msg for marker in QUOTA_MARKERS):
        return "quota_or_rate_limit"
    return "other"


def friendly_error_message(error_type: str, raw_error: str) -> str:
    if error_type == "quota_or_rate_limit":
        return (
            "It looks like the model's quota or rate limit has been hit or exhausted.\n"
            "Check your usage and limits with your model provider. Retrying automatically "
            "won't help here until the quota resets or you switch models."
        )
    return (
        "The model failed to produce a response in the expected format "
        "(not necessarily a quota issue).\n"
        f"Error details: {raw_error[:300]}"
    )


def call_structured_llm_with_retry(structured_llm, prompt, max_attempts=3, backoff_seconds=2):
    """Tries the structured-output call up to max_attempts times.
    Returns (result, error_type, raw_error) - result is None if every attempt failed."""
    last_error = None
    last_error_type = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = structured_llm.invoke([HumanMessage(content=prompt)])
            return result, None, None
        except Exception as e:
            last_error = str(e)
            last_error_type = classify_llm_error(e)
            print(f"  ...attempt {attempt}/{max_attempts} failed ({last_error_type}): {last_error[:120]}")
            if last_error_type == "quota_or_rate_limit":
                # no point burning through retries against an exhausted quota
                break
            if attempt < max_attempts:
                time.sleep(backoff_seconds)
    return None, last_error_type, last_error
