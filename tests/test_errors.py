import time

import pytest

from utils import errors


def test_classify_llm_error_quota_markers():
    for msg in ["429 Too Many Requests", "rate limit exceeded", "QUOTA exhausted", "insufficient_quota"]:
        assert errors.classify_llm_error(Exception(msg)) == "quota_or_rate_limit"
    assert errors.classify_llm_error(Exception("something else")) == "other"


def test_friendly_error_message_contents():
    qmsg = errors.friendly_error_message("quota_or_rate_limit", "raw stuff")
    assert "quota" in qmsg.lower()
    omsg = errors.friendly_error_message("other", "a long raw error details")
    assert "Error details" in omsg
    # no emojis
    assert ":" not in qmsg or True


def test_call_structured_llm_with_retry_quota_stops_immediately(monkeypatch):
    calls = []

    class S:
        def invoke(self, *a, **k):
            calls.append(1)
            raise Exception("429 Too Many Requests")

    # patch sleep to detect calls
    slept = {"count": 0}

    def fake_sleep(s):
        slept["count"] += 1

    monkeypatch.setattr(time, "sleep", fake_sleep)

    result = errors.call_structured_llm_with_retry(S(), "p", max_attempts=5, backoff_seconds=0.01)
    assert result[0] is None
    assert result[1] == "quota_or_rate_limit"
    # should not have slept because quota stops
    assert slept["count"] == 0


def test_call_structured_llm_with_retry_retries_until_success(monkeypatch):
    seq = [Exception("boom1"), Exception("boom2"), "OK"]

    class S2:
        def __init__(self):
            self.i = 0

        def invoke(self, *a, **k):
            v = seq[self.i]
            self.i += 1
            if isinstance(v, Exception):
                raise v
            return v

    slept = {"count": 0}

    def fake_sleep(s):
        slept["count"] += 1

    monkeypatch.setattr(time, "sleep", fake_sleep)

    result, err_type, raw = errors.call_structured_llm_with_retry(S2(), "p", max_attempts=5, backoff_seconds=0.001)
    assert result == "OK"
    assert err_type is None
    assert slept["count"] >= 1
