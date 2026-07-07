# MarketPulse

MarketPulse turns a Facebook page's post history into a full, ready-to-publish
content calendar. It reads a JSON export of a page's posts (with their
engagement metrics), extracts marketing insights from what actually performed
well, and then drafts a Facebook posting schedule around a campaign you
describe - with a human-in-the-loop review step before anything is final.

This project is a restructured, Streamlit-based version of the original
`notebooks/MarketPulse_toVS.ipynb` proof of concept. The notebook is kept only
as an optional smoke test; all real usage should go through `app_streamlit.py`.

## How it works

The pipeline is a [LangGraph](https://github.com/langchain-ai/langgraph)
`StateGraph` with five nodes:

1. **Data Agent** (`agents/data_agent.py`) - flattens the raw Facebook JSON
   export into a clean table: message, reach, clicks, reactions, comments,
   shares, total engagement, engagement rate, CTR.
2. **Insight Agent** (`agents/insight_agent.py`) - asks an LLM to read that
   table and produce concrete marketing insights (best posting times, top
   hooks, success characteristics, trends).
3. **Content Agent** (`agents/content_agent.py`) - drafts a full content
   calendar from those insights plus the campaign details you provide, using
   a structured-output schema (`ContentPlan` in `state.py`). It can also
   revise a single post on its own (`content_agent_single_post`).
4. **Human Review** (`agents/review_agent.py`) - pauses the graph
   (`interrupt()`) so a person can approve the plan, regenerate the whole
   plan with feedback, or regenerate a single post with feedback.
5. Loops back to the Content Agent until the plan is approved, then ends.

A `MemorySaver` checkpointer (see `graph.py`) is what allows the graph to
pause at the human-review step and resume later with `Command(resume=...)`.
Each browser session gets its own `thread_id`, so multiple people can use the
same running app without their in-progress campaigns interfering with each
other.

## Project structure

```
marketpulse/
├── .env                    # API keys (OPENAI_API_KEY / GROQ_API_KEY / GEMINI_API_KEY)
├── .gitignore
├── requirements.txt
├── README.md
│
├── data/
│   └── techpulse.json      # sample/demo Facebook export data
│
├── config.py                # MODELS dict + get_llm()
├── state.py                 # TypedDicts + Pydantic schemas
├── prompts.py                # INSIGHT_AGENT_PROMPT, CONTENT_AGENT_PROMPT, SINGLE_POST_PROMPT
│
├── utils/
│   └── errors.py             # classify_llm_error, friendly_error_message, call_structured_llm_with_retry
│
├── agents/
│   ├── data_agent.py
│   ├── insight_agent.py
│   ├── content_agent.py
│   └── review_agent.py
│
├── graph.py                  # StateGraph builder + MemorySaver + compile() -> exports `graph`
├── app_streamlit.py           # the Streamlit UI (see below)
│
└── notebooks/
    └── MarketPulse_toVS.ipynb  # optional smoke test, not required to run the app
```

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # on Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Fill in `.env` with at least the keys your configured models need. By
   default (`config.py` -> `MODELS`), the Insight Agent uses Gemini and the
   Content Agent uses Groq, so at minimum you need:

   ```
   GROQ_API_KEY=...
   GEMINI_API_KEY=...
   ```

   `OPENAI_API_KEY` is only needed if you switch a model's `provider` to
   `"openai"` in `config.py`.

3. Run the app:

   ```bash
   streamlit run app_streamlit.py
   ```

4. In the app, upload a Facebook posts JSON export (or use `data/techpulse.json`
   as a demo file), fill in the campaign form, and click **Generate Content
   Plan**.

## Using the app

- **Setup screen** - upload the Facebook JSON export and fill in the campaign
  form (title, description, target audience, promotion, campaign length/unit,
  posts per week).
- **Pipeline progress** - while the Data, Insight, and Content agents run, the
  app shows which stage is currently active.
- **Review screen** - if generation failed, a warning banner explains why and
  gives you Retry / Stop. Otherwise, you see the campaign summary and each
  post as its own card, with:
  - an "Approve this post" button (marks that post as approved in the UI),
  - a "Regenerate this post" button that opens a feedback box and resends
    just that post to the Content Agent,
  - "Approve All" (finishes the review loop) and "Regenerate All" (with a
    feedback box) for the whole plan.
- **Final screen** - the approved plan, a "Download JSON" button (includes the
  insights and full feedback history), and a "Start New Campaign" button.

## Notes on the sample data

`data/techpulse.json` is a small, synthetic Facebook export used for demos and
local testing. It follows the same shape the Data Agent expects: each post has
`message`, `created_time`, `reactions.summary.total_count`,
`comments.summary.total_count`, `shares.count`, and an `insights.data` array
containing `post_impressions_fan` and `post_clicks` values. Replace it with a
real export, or upload one directly in the app's setup screen.
