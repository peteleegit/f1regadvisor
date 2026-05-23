"""Base agent — shared Anthropic client and call helpers."""
from __future__ import annotations

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
        """Call Claude with web search; handles the tool-use loop.

        The web_search_20250305 built-in tool runs server-side: searches and
        continuation happen within a single API call, so stop_reason is
        "end_turn" with web_search_tool_use blocks embedded in response.content.
        Progress callbacks are emitted from those blocks before returning.
        """
        tools = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_search_uses,
            "allowed_domains": WEB_SEARCH_DOMAINS,
        }]
        msgs = list(messages)
        m = model or self.model
        mt = max_tokens or self.max_tokens

        while True:
            response = self.client.messages.create(
                model=m,
                max_tokens=mt,
                system=system,
                messages=msgs,
                tools=tools,
            )

            if response.stop_reason in ("end_turn", None):
                if progress_callback:
                    # Diagnostic: report all block types so we can see what
                    # the API actually returns for web_search_20250305.
                    seen = [
                        f"{getattr(b, 'type', '?')}/"
                        f"{getattr(b, 'name', '-')}"
                        for b in response.content
                    ]
                    progress_callback(f"[debug] blocks: {', '.join(seen)}")
                    for block in response.content:
                        btype = getattr(block, "type", "") or ""
                        bname = getattr(block, "name", "") or ""
                        if "search" in btype.lower() or bname == "web_search":
                            query = getattr(block, "input", {}).get("query", "")
                            if query:
                                progress_callback(f"Searched: *{query}*")
                return "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )

            if response.stop_reason == "tool_use":
                msgs.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    btype = getattr(block, "type", "") or ""
                    bname = getattr(block, "name", "") or ""
                    is_search = (btype == "tool_use") or "search" in btype.lower() or bname == "web_search"
                    if not is_search:
                        continue
                    if progress_callback:
                        query = getattr(block, "input", {}).get("query", "")
                        if query:
                            progress_callback(f"Searching: *{query}*")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "",
                    })
                if tool_results:
                    msgs.append({"role": "user", "content": tool_results})
                else:
                    break
            else:
                break

        return ""
