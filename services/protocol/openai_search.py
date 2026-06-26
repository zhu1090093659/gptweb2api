from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from services.account_service import account_service
from services.config import config
from services.openai_backend_api import OpenAIBackendAPI, SEARCH_MODEL
from services.protocol.openai_v1_chat_complete import completion_response

MODEL = SEARCH_MODEL


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


def handle(body: dict[str, Any]) -> dict[str, Any]:
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail={"error": "prompt is required"})
    model = str(body.get("model") or MODEL).strip() or MODEL
    token = account_service.get_text_access_token(provider="gpt")
    if not token:
        raise HTTPException(status_code=429, detail={"error": "no available text account"})
    account = account_service.get_account(token) or {}
    backend = OpenAIBackendAPI(token, account_proxy=str(account.get("proxy") or ""))
    try:
        result = backend.search(prompt, model=model)
    finally:
        backend.close()
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
