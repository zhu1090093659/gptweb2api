from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any

from fastapi import HTTPException

from services.account_service import account_service
from services.config import config
from services.openai_backend_api import OpenAIBackendAPI, SEARCH_MODEL
from services.protocol.openai_v1_chat_complete import completion_response

logger = logging.getLogger(__name__)

MODEL = SEARCH_MODEL
_SEARCH_ATTEMPT_TIMEOUT = 90
_MAX_RETRIES = 3


def _source_items(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    sources: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url or any(source["url"] == url for source in sources):
            continue
        sources.append({
            "title": str(item.get("title") or "").strip(),
            "url": url,
            "snippet": str(item.get("snippet") or "").strip(),
            "source_type": str(item.get("source_type") or "").strip(),
        })
    return sources


def _do_search(token: str, proxy: str, prompt: str, model: str) -> dict[str, Any]:
    backend = OpenAIBackendAPI(token, account_proxy=proxy)
    try:
        return backend.search(prompt, model=model)
    finally:
        backend.close()


def handle(body: dict[str, Any]) -> dict[str, Any]:
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail={"error": "prompt is required"})
    model = str(body.get("model") or MODEL).strip() or MODEL

    attempted: set[str] = set()
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        token = account_service.get_text_access_token(excluded_tokens=attempted, provider="gpt")
        if not token:
            break
        attempted.add(token)
        account = account_service.get_account(token) or {}
        proxy = str(account.get("proxy") or "")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_search, token, proxy, prompt, model)
            try:
                result = future.result(timeout=_SEARCH_ATTEMPT_TIMEOUT)
            except FutureTimeout:
                logger.warning(
                    "search timeout (%ds) for account %s, retrying with next account (attempt %d/%d)",
                    _SEARCH_ATTEMPT_TIMEOUT,
                    account.get("email", "?"),
                    attempt + 1,
                    _MAX_RETRIES,
                )
                last_error = TimeoutError(f"search timeout after {_SEARCH_ATTEMPT_TIMEOUT}s")
                continue
            except Exception as exc:
                logger.warning(
                    "search error for account %s: %s, retrying (attempt %d/%d)",
                    account.get("email", "?"),
                    exc,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                last_error = exc
                continue

        account_service.mark_text_used(token)
        sources = _source_items(result.get("sources"))
        answer = str(result.get("answer") or "")
        response: dict[str, Any] = {
            "object": "search.result",
            "model": model,
            "conversation_id": str(result.get("conversation_id") or ""),
            "status": str(result.get("status") or ""),
            "answer": answer,
            "sources": sources,
            "assistant_message_id": str(result.get("assistant_message_id") or ""),
            "create_time": result.get("create_time") or 0,
        }
        if config.show_search_sources:
            response["chat_completion"] = completion_response(model, answer, messages=[{"role": "user", "content": prompt}], search_sources=sources)
        return response

    if last_error:
        raise HTTPException(status_code=502, detail={"error": f"search failed after {_MAX_RETRIES} attempts: {last_error}"})
    raise HTTPException(status_code=429, detail={"error": "no available text account"})
