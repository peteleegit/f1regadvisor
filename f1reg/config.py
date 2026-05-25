from __future__ import annotations

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SEASON = "2026"

WEB_SEARCH_DOMAINS = [
    # Authoritative press and official sources
    "fia.com",
    "formula1.com",
    "autosport.com",
    "motorsport.com",
    "the-race.com",
    "racefans.net",
    # Insider commentary (lower reliability — agents instructed to label accordingly)
    "x.com",
]


class Settings(BaseSettings):
    fiaruler_api_url: str = "http://localhost:8000"
    fiaruler_api_key: str = ""

    fast_model:    str = "claude-haiku-4-5-20251001"
    primary_model: str = "claude-sonnet-4-6"
    senior_model:  str = "claude-opus-4-7"
    verdict_model: str = "claude-opus-4-7"

    default_season: str = DEFAULT_SEASON

    regulation_limit: int = 10
    precedent_limit: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="F1REG_",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()


def configure_api_key() -> None:
    """Pull Anthropic key from Streamlit secrets or existing env var."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        import streamlit as st
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["anthropic"]["api_key"]
    except Exception:
        pass


def get_fiaruler_api_url() -> str:
    try:
        import streamlit as st
        url = st.secrets["fiaruler"]["api_url"]
        if url:
            return url
    except Exception:
        pass
    return settings.fiaruler_api_url


def get_fiaruler_api_key() -> str:
    try:
        import streamlit as st
        key = st.secrets["fiaruler"]["api_key"]
        if key:
            return key
    except Exception:
        pass
    return settings.fiaruler_api_key
