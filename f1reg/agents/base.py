"""Base agent — shared Anthropic client and call helpers."""
from __future__ import annotations

import json as _json
import threading
from collections.abc import Callable, Generator
from typing import Any

import anthropic

from f1reg.config import WEB_SEARCH_DOMAINS, settings

_client: anthropic.Anthropic | None = None
_client_lock = threading.Lock()


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = anthropic.Anthropic(http_client=_make_http_client())
    return _client


def _make_http_client():
    import ssl
    import httpx
    import truststore
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return httpx.Client(verify=ctx)


class BaseAgent:
    """Shared behaviour for all F1RegAdvisor agents.

    Subclasses set class-level `model` and `max_tokens` to override defaults,
    and implement their logic by calling `_call()` or `_call_with_web_search()`.
    """

    model: str = settings.primary_model
    max_tokens: int = 4000

    @property
    def client(self) -> anthropic.Anthropic:
        return _get_client()

    def _call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        response = self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=messages,
        )
        return "".join(
            b.text for b in response.content if hasattr(b, "text")
        )

    def _stream(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> Generator[str, None, None]:
        """Yield raw text chunks from a streaming API call."""
        with self.client.messages.stream(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=messages,
        ) as stream:
            yield from stream.text_stream

    def _call_with_web_search(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        max_search_uses: int = 5,
        progress_callback: Callable[[str], None] | None = None,
    ) -> str:
        """Call Claude with web search (server-side built-in tool).

        web_search_20250305 completes all searches in a single blocking API
        call.  If progress_callback is provided it is called once per search
        query found in the response, immediately after the call returns.
        """
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_search_uses,
            "allowed_domains": WEB_SEARCH_DOMAINS,
        }]
        response = self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=list(messages),
            tools=tools,
        )
        if progress_callback:
            for block in response.content:
                btype = getattr(block, "type", "") or ""
                bname = getattr(block, "name", "") or ""
                if bname == "web_search" or "search" in btype:
                    query = (getattr(block, "input", None) or {}).get("query", "")
                    if query:
                        progress_callback(f"Searched: *{query}*")
        return "\n".join(b.text for b in response.content if getattr(b, "type", "") == "text")
