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
        """Call Claude with web search; emit progress callbacks per search query.

        web_search_20250305 runs server-side inside a single streaming call.
        We detect server_tool_use blocks in the stream to surface each search
        query to the caller in real time — before the overall call completes.
        """
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_search_uses,
            "allowed_domains": WEB_SEARCH_DOMAINS,
        }]

        _block_name = ""
        _block_json = ""

        with self.client.messages.stream(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system,
            messages=list(messages),
            tools=tools,
        ) as stream:
            for event in stream:
                etype = getattr(event, "type", "")

                if etype == "content_block_start":
                    cb = getattr(event, "content_block", None)
                    if cb is not None:
                        _block_name = getattr(cb, "name", "") or ""
                        # Some server tools pre-populate input at block start
                        pre = getattr(cb, "input", None)
                        if pre and isinstance(pre, dict) and _block_name == "web_search":
                            query = pre.get("query", "")
                            if query and progress_callback:
                                progress_callback(f"Searching: *{query}*")
                            _block_json = ""
                        else:
                            _block_json = ""
                    else:
                        _block_name = ""
                        _block_json = ""

                elif etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is not None and getattr(delta, "type", "") == "input_json_delta":
                        _block_json += getattr(delta, "partial_json", "") or ""

                elif etype == "content_block_stop":
                    if _block_name == "web_search" and _block_json and progress_callback:
                        try:
                            query = _json.loads(_block_json).get("query", "")
                            if query:
                                progress_callback(f"Searching: *{query}*")
                        except Exception:
                            pass
                    _block_name = ""
                    _block_json = ""

            final = stream.get_final_message()

        return "\n".join(b.text for b in final.content if hasattr(b, "text"))
