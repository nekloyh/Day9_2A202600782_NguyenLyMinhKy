"""Shared LLM factory for all agents.

Uses the OpenAI API. The model and base URL can be configured through
OPENAI_MODEL and OPENAI_BASE_URL.
"""

import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client configured for the OpenAI API."""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        temperature=0.3,
    )
    
