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
    fiaruler_db_url: str = "sqlite:///./fiaruler.db"

    primary_model: str = "claude-sonnet-4-6"
    senior_model: str = "claude-opus-4-7"

    default_season: str = DEFAULT_SEASON

    regulation_limit: int = 10
    precedent_limit: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="F1REG_",
        case_sensitive=False,
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


def get_fiaruler_db_url() -> str:
    """Return the FIARulerPro DB URL from Streamlit secrets or settings."""
    try:
        import streamlit as st
        url = st.secrets["substrate"]["db_url"]
        if url:
            return url
    except Exception:
        pass
    return settings.fiaruler_db_url
