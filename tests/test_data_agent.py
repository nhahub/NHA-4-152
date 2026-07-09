import copy

from agents import data_agent as da


def test_flattening_and_metrics(sample_facebook_json):
    state = {"raw_data": sample_facebook_json}
    out = da.data_agent(state)
    rows = out["dataframe"]
    assert isinstance(rows, list)
    # verify required columns and computed fields exist
    for r in rows:
        assert "message" in r
        assert "created_time" in r
        assert "reach" in r
        assert "clicks" in r
        assert "reactions" in r
        assert "comments" in r
        assert "shares" in r
        assert "total_engagement" in r
        assert "engagement_rate" in r
        assert "ctr" in r
        # numeric consistency
        assert r["total_engagement"] == r["reactions"] + r["comments"] + r["shares"]
        if r["reach"] > 0:
            assert r["engagement_rate"] == round(r["total_engagement"] / r["reach"], 4)
            assert r["ctr"] == round(r["clicks"] / r["reach"], 4)


def test_zero_reach_no_zero_division():
    # synthetic post with zero reach
    post = {"message": "x", "created_time": "2020-01-01", "insights": {"data": [{"name": "post_impressions_fan", "values": [{"value": 0}]}, {"name": "post_clicks", "values": [{"value": 0}]}]}}
    state = {"raw_data": [post]}
    out = da.data_agent(state)
    r = out["dataframe"][0]
    assert r["reach"] == 0
    assert r["engagement_rate"] == 0
    assert r["ctr"] == 0


def test_missing_fields_defaults_and_created_time_unknown():
    post = {"message": "no fields"}
    state = {"raw_data": [post]}
    out = da.data_agent(state)
    r = out["dataframe"][0]
    assert r["reactions"] == 0
    assert r["comments"] == 0
    assert r["shares"] == 0
    assert r["created_time"] == "Unknown"


def test_duplicate_posts_dropped():
    post = {"message": "dup", "created_time": "t"}
    raw = [post, post, copy.deepcopy(post)]
    state = {"raw_data": raw}
    out = da.data_agent(state)
    rows = out["dataframe"]
    assert len(rows) == 1


def test_accepts_bare_list_and_dict_wrapped(sample_facebook_json):
    # wrapped
    out1 = da.data_agent({"raw_data": {"data": sample_facebook_json["data"]}})
    out2 = da.data_agent({"raw_data": sample_facebook_json["data"]})
    assert isinstance(out1["dataframe"], list)
    assert isinstance(out2["dataframe"], list)
