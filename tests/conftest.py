import json
from pathlib import Path

import pytest


class FakeStructuredLLM:
    def __init__(self, result):
        self._result = result

    def with_structured_output(self, model):
        return self

    def invoke(self, prompt):
        return self._result


class FakePlainLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, prompt):
        m = type("M", (), {})()
        m.content = self._content
        return m


@pytest.fixture
def sample_facebook_json():
    root = Path(__file__).resolve().parents[1]
    p = root / "data" / "techpulse.json"
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_campaign_details():
    return {
        "title": "Test Campaign",
        "description": "Launch promotion",
        "target_audience": "SMBs",
        "highlights": ["fast", "cheap"],
        "value_proposition": ["saves time"],
        "promotion": "20% off",
        "additional_notes": "None",
        "campaign_length": 1,
        "campaign_unit": "week",
        "posts_per_week": 2,
    }
