"""
Central configuration for MarketPulse.

Holds the MODELS registry (which provider/model each agent uses) and the
get_llm() factory that builds the right LangChain chat model from the
API keys in .env.
"""

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Which provider/model each agent uses. Change here to switch providers
# without touching any agent code.
MODELS = {
    "insight": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
    },
    "content": {
        "provider": "groq",
        "model": "llama-3.1-8b-instant",
    },
}


def get_llm(agent_name: str, temperature: float):
    """Build a LangChain chat model for the given agent (see MODELS)."""

    config = MODELS[agent_name]
    provider = config["provider"]

    if provider == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")
        return ChatGoogleGenerativeAI(
            model=config["model"],
            google_api_key=GEMINI_API_KEY,
            temperature=temperature,
        )

    if provider == "groq":
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        return ChatGroq(
            model=config["model"],
            api_key=GROQ_API_KEY,
            temperature=temperature,
        )

    if provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
        return ChatOpenAI(
            model=config["model"],
            api_key=OPENAI_API_KEY,
            temperature=temperature,
        )

    raise ValueError(f"Unsupported provider: {provider}")
