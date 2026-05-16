"""Base agent — shared Anthropic client and call helpers."""
from __future__ import annotations

import threading
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

    def _call_with_web_search(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        max_search_uses: int = 5,
    ) -> str:
        """Call Claude with web search; handles the tool-use loop.

        The web_search_20250305 built-in tool is executed server-side by
        Anthropic — the client drives the loop but does not implement the
        search itself.
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
                return "".join(
                    b.text for b in response.content if hasattr(b, "text")
                )

            if response.stop_reason == "tool_use":
                msgs.append({"role": "assistant", "content": response.content})
                tool_results = [
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "",
                    }
                    for block in response.content
                    if getattr(block, "type", None) == "tool_use"
                ]
                if tool_results:
                    msgs.append({"role": "user", "content": tool_results})
                else:
                    break
            else:
                break

        return ""
