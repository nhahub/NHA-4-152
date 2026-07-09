import pytest

from pydantic import ValidationError

from state import PostItem, ContentPlan


def test_postitem_validation_requires_fields():
    with pytest.raises(ValidationError):
        PostItem()


def test_contentplan_model_dump_roundtrip():
    posts = [PostItem(day="Mon", suggested_time="7:00", objective="A", post_content="c", reasoning="r")]
    cp = ContentPlan(campaign_summary="s", posts=posts)
    d = cp.model_dump()
    assert isinstance(d, dict)
    assert isinstance(d["posts"], list)
    assert d["posts"][0]["post_content"] == "c"
