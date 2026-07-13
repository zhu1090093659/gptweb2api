from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import Event, Thread

from fastapi import HTTPException, Request

from services.account_service import account_service
from services.auth_service import auth_service
from services.config import config

BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIST_DIR = BASE_DIR / "web_dist"


def extract_bearer_token(authorization: str | None) -> str:
    scheme, _, value = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return ""
    return value.strip()


def _legacy_admin_identity(token: str) -> dict[str, object] | None:
    auth_key = str(config.auth_key or "").strip()
    if auth_key and token == auth_key:
        return {"id": "admin", "name": "管理员", "role": "admin"}
    return None


def require_identity(authorization: str | None) -> dict[str, object]:
    token = extract_bearer_token(authorization)
    identity = _legacy_admin_identity(token) or auth_service.authenticate(token)
    if identity is None:
        raise HTTPException(status_code=401, detail={"error": "密钥无效或已失效，请重新登录"})
    return identity


def require_auth_key(authorization: str | None) -> None:
    require_identity(authorization)


def require_admin(authorization: str | None) -> dict[str, object]:
    identity = require_identity(authorization)
    if identity.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "需要管理员权限才能执行这个操作"})
    return identity


def resolve_image_base_url(request: Request) -> str:
    return config.base_url or f"{request.url.scheme}://{request.headers.get('host', request.url.netloc)}"


def raise_image_quota_error(exc: Exception) -> None:
    message = str(exc)
    if "no available image quota" in message.lower():
        raise HTTPException(status_code=429, detail={"error": "no available image quota"}) from exc
    raise HTTPException(status_code=502, detail={"error": message}) from exc


def sanitize_cpa_pool(pool: dict | None) -> dict | None:
    if not isinstance(pool, dict):
        return None
    return {key: value for key, value in pool.items() if key != "secret_key"}


def sanitize_cpa_pools(pools: list[dict]) -> list[dict]:
    return [sanitized for pool in pools if (sanitized := sanitize_cpa_pool(pool)) is not None]


def sanitize_sub2api_server(server: dict | None) -> dict | None:
    if not isinstance(server, dict):
        return None
    sanitized = {key: value for key, value in server.items() if key not in {"password", "api_key"}}
    sanitized["has_api_key"] = bool(str(server.get("api_key") or "").strip())
    return sanitized


def sanitize_sub2api_servers(servers: list[dict]) -> list[dict]:
    return [sanitized for server in servers if (sanitized := sanitize_sub2api_server(server)) is not None]


def sanitize_remote_account_source(source: dict | None) -> dict | None:
    if not isinstance(source, dict):
        return None
    sanitized = {key: value for key, value in source.items() if key not in {"auth_token", "bearer_token"}}
    sanitized["has_auth_token"] = bool(str(source.get("auth_token") or "").strip())
    sanitized["has_bearer_token"] = bool(str(source.get("bearer_token") or "").strip())
    return sanitized


def sanitize_remote_account_sources(sources: list[dict]) -> list[dict]:
    return [sanitized for source in sources if (sanitized := sanitize_remote_account_source(source)) is not None]


def start_limited_account_watcher(stop_event: Event) -> Thread:
    interval_seconds = config.refresh_account_interval_minute * 60

    def worker() -> None:
        while not stop_event.is_set():
            try:
                limited_tokens = account_service.list_limited_tokens()
                if limited_tokens:
                    print(f"[account-limited-watcher] checking {len(limited_tokens)} limited accounts")
                    account_service.refresh_accounts(limited_tokens)
            except Exception as exc:
                print(f"[account-limited-watcher] fail {exc}")
            stop_event.wait(interval_seconds)

    thread = Thread(target=worker, name="limited-account-watcher", daemon=True)
    thread.start()
    return thread


@lru_cache(maxsize=1)
def web_dist_base_dir() -> Path | None:
    if not WEB_DIST_DIR.is_dir():
        return None
    return WEB_DIST_DIR.resolve()


@lru_cache(maxsize=1)
def web_index_asset() -> Path | None:
    base_dir = web_dist_base_dir()
    if base_dir is None:
        return None
    index = base_dir / "index.html"
    return index if index.is_file() else None


def resolve_web_asset(requested_path: str) -> Path | None:
    clean_path = requested_path.strip("/")
    if clean_path in {"", "index.html"}:
        return web_index_asset()
    requested = Path(clean_path)
    if requested.is_absolute() or ".." in requested.parts:
        return None
    base_dir = web_dist_base_dir()
    if base_dir is None:
        return None
    candidates = [
        base_dir / requested,
        base_dir / requested / "index.html",
        base_dir / f"{clean_path}.html",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
