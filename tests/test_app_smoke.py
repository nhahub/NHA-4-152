import pytest


def test_streamlit_app_smoke():
    st = pytest.importorskip("streamlit.testing.v1")
    AppTest = st.AppTest
    app_path = "app_streamlit.py"
    tester = AppTest.from_file(app_path)
    result = tester.run()
    # must not have raised
    assert not result.exception
    # try a best-effort check for the button label
    text = ""
    if hasattr(result, "get_all_text"):
        text = result.get_all_text()
    elif hasattr(result, "script_text"):
        text = result.script_text
    else:
        # fallback: ensure no exception and skip label assert
        return
    assert "Generate Content Plan" in text
