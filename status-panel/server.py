"""Standalone loopback-only, read-only Hermes status panel.

This service is intentionally outside the Hermes Agent source tree and is
started only by the explicit 9120 launcher. All upstream probes are local,
performed server-side, and credentials are never included in returned state.
"""

from __future__ import annotations

import asyncio
import datetime as _datetime
import json
import os
import re
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_STANDALONE_ROOT = Path(__file__).resolve().parent
_WEB_DIST = _STANDALONE_ROOT / "static"
_STATE_PATH = _STANDALONE_ROOT / "state.json"
_HERMES_HOME = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
_STUDIO_HOME = Path(
    os.environ.get("HERMES_STUDIO_HOME", str(Path.home() / ".hermes-studio-test"))
).expanduser()
_CLIPROXY_HOME = Path(
    os.environ.get("CLIPROXY_HOME", str(Path.home() / ".config" / "cliproxyapi"))
).expanduser()
_HERMES_CONFIG = _HERMES_HOME / "config.yaml"
_STUDIO_CONFIG = _STUDIO_HOME / "config.json"
_CLIPROXY_ENV = _CLIPROXY_HOME / "client.env"
_PROVIDER_KEY = "custom:google-antigravity"
_LEGACY_HIDDEN_MODEL = "antigravity-cpa-smoke"
_LOCAL_TIMEOUT_SECONDS = 2.0
_MAX_JSON_BYTES = 4 * 1024 * 1024
_SNAPSHOT_TTL_SECONDS = 2.0
_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")

_SNAPSHOT_LOCK = threading.RLock()
_STATE_LOCK = threading.RLock()
_SNAPSHOT: dict[str, Any] | None = None
_SNAPSHOT_EXPIRES = 0.0


def _now_iso() -> str:
    return (
        _datetime.datetime.now(_datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_model_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value == _LEGACY_HIDDEN_MODEL or not _MODEL_ID_RE.fullmatch(value):
        return None
    return value


def _safe_text(value: Any, limit: int = 240) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.replace("\x00", "").split())
    return value[:limit] or None


def _humanize_model_id(model_id: str) -> str:
    words = re.split(r"[-_:]+", model_id)
    rendered = " ".join(
        word.upper() if word.lower() in {"gpt", "oss"} else word.title()
        for word in words
    )
    return rendered.replace("Gpt", "GPT").replace("Oss", "OSS")


def _display_name(model_id: str, aliases: dict[str, str]) -> str:
    return aliases.get(model_id) or _humanize_model_id(model_id)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _read_clip_proxy_key() -> str:
    """Read the local key only into memory for one local catalog request."""
    try:
        for line in _CLIPROXY_ENV.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if line.startswith("HERMES_CLIPROXYAPI_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def _local_json_get(url: str, *, bearer: str = "") -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=_LOCAL_TIMEOUT_SECONDS) as response:
            body = response.read(_MAX_JSON_BYTES)
            return int(response.status), json.loads(
                body.decode("utf-8", "replace")
            )
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except Exception:
        return 0, None


def _local_status_get(url: str) -> int:
    """Return only the HTTP status for a local health/page GET."""
    request = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=_LOCAL_TIMEOUT_SECONDS) as response:
            response.read(1024)
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def _gateway_catalog() -> tuple[bool, set[str]]:
    """Read the authenticated local CLIProxyAPI catalog without logging its key."""
    try:
        with socket.create_connection(
            ("127.0.0.1", 8317), timeout=_LOCAL_TIMEOUT_SECONDS
        ):
            pass
    except OSError:
        return False, set()
    status, data = _local_json_get(
        "http://127.0.0.1:8317/v1/models", bearer=_read_clip_proxy_key()
    )
    if status != 200 or not isinstance(data, dict):
        return False, set()
    rows = data.get("data")
    if not isinstance(rows, list):
        rows = data.get("models")
    if not isinstance(rows, list):
        return False, set()
    model_ids = {
        model_id
        for row in rows
        if isinstance(row, dict)
        for model_id in [_safe_model_id(row.get("id"))]
        if model_id
    }
    return True, model_ids


def _provider_models(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            model_id
            for model_id in (_safe_model_id(key) for key in value)
            if model_id
        }
    if isinstance(value, list):
        return {
            model_id
            for model_id in (_safe_model_id(item) for item in value)
            if model_id
        }
    return set()


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _load_provider_state() -> tuple[bool, set[str]]:
    config = _load_yaml(_HERMES_CONFIG)
    found = False
    models: set[str] = set()

    def visit(value: Any) -> None:
        nonlocal found, models
        if isinstance(value, dict):
            if value.get("name") == "google-antigravity":
                found = True
                models.update(_provider_models(value.get("models")))
            for key, child in value.items():
                if key == "google-antigravity" and isinstance(child, dict):
                    found = True
                    models.update(_provider_models(child.get("models")))
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(config)
    return found, models


def _load_studio_metadata() -> dict[str, Any]:
    config = _load_json(_STUDIO_CONFIG)
    if not isinstance(config, dict):
        return {
            "configured": False,
            "known_ids": set(),
            "visible_ids": set(),
            "aliases": {},
        }

    aliases: dict[str, str] = {}
    alias_root = config.get("modelAliases")
    alias_map = alias_root.get(_PROVIDER_KEY) if isinstance(alias_root, dict) else None
    if isinstance(alias_map, dict):
        for raw_id, raw_alias in alias_map.items():
            model_id = _safe_model_id(raw_id)
            if not model_id:
                continue
            alias: Any = raw_alias
            if isinstance(raw_alias, dict):
                alias = next(
                    (
                        raw_alias.get(key)
                        for key in ("displayName", "name", "label")
                        if raw_alias.get(key)
                    ),
                    None,
                )
            label = _safe_text(alias)
            if label:
                aliases[model_id] = label

    custom_ids: set[str] = set()
    custom_root = config.get("customModels")
    custom_value = (
        custom_root.get(_PROVIDER_KEY) if isinstance(custom_root, dict) else None
    )
    if isinstance(custom_value, dict):
        custom_ids.update(
            model_id
            for model_id in (_safe_model_id(key) for key in custom_value)
            if model_id
        )
    elif isinstance(custom_value, list):
        custom_ids.update(
            model_id
            for model_id in (_safe_model_id(value) for value in custom_value)
            if model_id
        )

    visibility_root = config.get("modelVisibility")
    visibility = (
        visibility_root.get(_PROVIDER_KEY)
        if isinstance(visibility_root, dict)
        else None
    )
    visibility_models: set[str] = set()
    visibility_mode = "include"
    if isinstance(visibility, dict):
        visibility_mode = str(visibility.get("mode") or "include").lower()
        raw_models = visibility.get("models")
        if isinstance(raw_models, list):
            visibility_models.update(
                model_id
                for model_id in (_safe_model_id(value) for value in raw_models)
                if model_id
            )

    known_ids = set(aliases) | custom_ids | visibility_models
    if visibility_mode == "exclude":
        visible_ids = known_ids - visibility_models
    else:
        visible_ids = set(visibility_models)
    return {
        "configured": bool(
            alias_map is not None or custom_value is not None or visibility is not None
        ),
        "known_ids": known_ids,
        "visible_ids": visible_ids,
        "aliases": aliases,
    }


def _default_state() -> dict[str, Any]:
    return {
        "last_catalog_ids": [],
        "last_service_status": {},
        "model_first_seen": {},
        "model_last_seen": {},
        "recent_events": [],
    }


def _load_state() -> dict[str, Any]:
    raw = _load_json(_STATE_PATH)
    if not isinstance(raw, dict):
        return _default_state()
    state = _default_state()
    if isinstance(raw.get("last_catalog_ids"), list):
        state["last_catalog_ids"] = sorted(
            {
                model_id
                for model_id in (
                    _safe_model_id(value) for value in raw["last_catalog_ids"]
                )
                if model_id
            }
        )
    if isinstance(raw.get("last_service_status"), dict):
        state["last_service_status"] = {
            str(key): str(value)
            for key, value in raw["last_service_status"].items()
            if isinstance(key, str)
        }
    for field in ("model_first_seen", "model_last_seen"):
        if isinstance(raw.get(field), dict):
            state[field] = {
                model_id: value
                for raw_id, value in raw[field].items()
                for model_id in [_safe_model_id(raw_id)]
                if model_id and isinstance(value, str)
            }
    if isinstance(raw.get("recent_events"), list):
        state["recent_events"] = [
            {
                "type": item.get("type"),
                "title": _safe_text(item.get("title"), 300),
                "time": _safe_text(item.get("time"), 64),
            }
            for item in raw["recent_events"]
            if isinstance(item, dict)
            and isinstance(item.get("type"), str)
            and _safe_text(item.get("title"), 300)
            and _safe_text(item.get("time"), 64)
        ][:50]
    return state


def _save_state(state: dict[str, Any]) -> None:
    payload = {
        "last_catalog_ids": state.get("last_catalog_ids", []),
        "last_service_status": state.get("last_service_status", {}),
        "model_first_seen": state.get("model_first_seen", {}),
        "model_last_seen": state.get("model_last_seen", {}),
        "recent_events": state.get("recent_events", [])[:50],
    }
    parent = _STATE_PATH.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".dashboard-status-", suffix=".tmp", dir=str(parent)
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    payload,
                    handle,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                handle.write("\n")
            os.replace(tmp_name, _STATE_PATH)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
    except Exception:
        return


def _append_event(
    events: list[dict[str, Any]], event_type: str, title: str, when: str
) -> None:
    if (
        events
        and events[0].get("type") == event_type
        and events[0].get("title") == title
    ):
        return
    events.insert(0, {"type": event_type, "title": title, "time": when})


def _service(label: str, status: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "detail": detail}


def _probe_simple(url: str) -> bool:
    return _local_status_get(url) == 200


def _build_model_rows(
    live_ids: set[str],
    studio: dict[str, Any],
    provider_model_ids: set[str],
    state: dict[str, Any],
    checked_at: str,
) -> list[dict[str, Any]]:
    known_ids = set(live_ids) | set(studio["known_ids"]) | provider_model_ids
    known_ids.discard(_LEGACY_HIDDEN_MODEL)
    aliases = studio["aliases"]
    first_seen = state["model_first_seen"]
    last_seen = state["model_last_seen"]
    rows: list[dict[str, Any]] = []
    for model_id in sorted(known_ids, key=lambda value: (value.lower(), value)):
        live = model_id in live_ids
        visible = model_id in studio["visible_ids"]
        if live and visible:
            status = "available"
        elif live:
            status = "new"
        elif visible:
            status = "mismatch"
        else:
            status = "unavailable"
        if live:
            first_seen.setdefault(model_id, checked_at)
            last_seen[model_id] = checked_at
        rows.append(
            {
                "name": _display_name(model_id, aliases),
                "id": model_id,
                "live": live,
                "visible": visible,
                "status": status,
                "studio": (
                    "已显示"
                    if visible
                    else ("已隐藏" if model_id in studio["known_ids"] else "未配置")
                ),
                "liveCatalog": "存在" if live else "不存在",
                "first_seen": first_seen.get(model_id),
                "last_seen": last_seen.get(model_id),
            }
        )
    return rows


def _collect_snapshot() -> dict[str, Any]:
    checked_at = _now_iso()
    catalog_ok, live_ids = _gateway_catalog()
    agent_ok = _probe_simple("http://127.0.0.1:8642/health")
    studio_ok = _probe_simple("http://127.0.0.1:8648/")
    provider_configured, provider_model_ids = _load_provider_state()
    studio = _load_studio_metadata()

    with _STATE_LOCK:
        state = _load_state()
        previous_catalog = set(state["last_catalog_ids"])
        previous_services = dict(state["last_service_status"])
        rows = _build_model_rows(
            live_ids, studio, provider_model_ids, state, checked_at
        )

        antigravity_ok = bool(
            provider_configured
            and catalog_ok
            and live_ids.intersection(set(studio["known_ids"]) | provider_model_ids)
        )
        service_status = {
            "gateway": "healthy" if catalog_ok else "error",
            "agent": "healthy" if agent_ok else "error",
            "studio": "healthy" if studio_ok else "error",
            "antigravity": "healthy" if antigravity_ok else "error",
        }
        events = list(state["recent_events"])

        for row in rows:
            model_id = row["id"]
            if row["live"] and model_id not in previous_catalog:
                event_type = (
                    "model_recovered"
                    if model_id in state["model_last_seen"]
                    else "model_added"
                )
                _append_event(events, event_type, f"发现模型：{row['name']}", checked_at)
            elif not row["live"] and model_id in previous_catalog:
                _append_event(
                    events, "model_removed", f"模型暂不可用：{row['name']}", checked_at
                )
            if row["status"] == "mismatch":
                _append_event(
                    events,
                    "catalog_mismatch",
                    f"模型配置不一致：{row['name']}",
                    checked_at,
                )

        service_labels = {
            "gateway": "网关",
            "agent": "Agent",
            "studio": "Studio",
            "antigravity": "Antigravity",
        }
        for service_name, current in service_status.items():
            previous = previous_services.get(service_name)
            if previous and previous != current and current == "error":
                _append_event(
                    events,
                    "service_down",
                    f"{service_labels[service_name]} 当前不可用",
                    checked_at,
                )
            elif previous and previous != current and current == "healthy":
                _append_event(
                    events,
                    "service_recovered",
                    f"{service_labels[service_name]} 已恢复",
                    checked_at,
                )

        events = events[:50]
        state["last_catalog_ids"] = sorted(live_ids)
        state["last_service_status"] = service_status
        state["recent_events"] = events
        _save_state(state)

    if any(service_status[name] == "error" for name in service_status):
        overall = "error"
    elif any(row["status"] != "available" for row in rows):
        overall = "attention"
    else:
        overall = "healthy"

    summary = {
        "total": len(rows),
        "available": sum(row["status"] == "available" for row in rows),
        "new": sum(row["status"] == "new" for row in rows),
        "unavailable": sum(row["status"] == "unavailable" for row in rows),
        "mismatch": sum(row["status"] == "mismatch" for row in rows),
    }
    return {
        "checked_at": checked_at,
        "overall": overall,
        "services": {
            "gateway": _service(
                "网关",
                service_status["gateway"],
                "本地模型目录可读取" if catalog_ok else "本地模型目录不可读取",
            ),
            "agent": _service(
                "Agent",
                service_status["agent"],
                "健康检查正常" if agent_ok else "健康检查失败",
            ),
            "studio": _service(
                "Studio",
                service_status["studio"],
                "页面可访问" if studio_ok else "页面不可访问",
            ),
            "antigravity": _service(
                "Antigravity",
                service_status["antigravity"],
                "本地模型目录已关联"
                if antigravity_ok
                else "本地 provider 或模型目录不可用",
            ),
        },
        "models": rows,
        "model_summary": summary,
        "events": events[:3],
    }


def _get_snapshot() -> dict[str, Any]:
    global _SNAPSHOT, _SNAPSHOT_EXPIRES
    now = time.monotonic()
    with _SNAPSHOT_LOCK:
        if _SNAPSHOT is not None and now < _SNAPSHOT_EXPIRES:
            return _SNAPSHOT
        _SNAPSHOT = _collect_snapshot()
        _SNAPSHOT_EXPIRES = time.monotonic() + _SNAPSHOT_TTL_SECONDS
        return _SNAPSHOT


def create_readonly_status_panel_app() -> FastAPI:
    application = FastAPI(
        title="Hermes 状态面板",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.readonly_status_panel = True

    if (_WEB_DIST / "assets").exists():
        application.mount(
            "/assets",
            StaticFiles(directory=str(_WEB_DIST / "assets"), check_dir=False),
            name="readonly-assets",
        )
    for directory, name in (
        ("fonts", "readonly-fonts"),
        ("fonts-terminal", "readonly-terminal-fonts"),
    ):
        if (_WEB_DIST / directory).exists():
            application.mount(
                "/" + directory,
                StaticFiles(directory=str(_WEB_DIST / directory), check_dir=False),
                name=name,
            )

    @application.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        path = _WEB_DIST / "favicon.ico"
        if path.is_file():
            return FileResponse(path)
        return JSONResponse({"detail": "not found"}, status_code=404)

    @application.get("/api/health")
    async def health():
        return {"ok": True, "readonly": True, "service": "dashboard"}

    @application.get("/api/status")
    async def status():
        snapshot = await asyncio.to_thread(_get_snapshot)
        return {
            "overall": snapshot["overall"],
            "checked_at": snapshot["checked_at"],
            "services": snapshot["services"],
        }

    @application.get("/api/models")
    async def models():
        snapshot = await asyncio.to_thread(_get_snapshot)
        return {
            "provider": "google-antigravity",
            "checked_at": snapshot["checked_at"],
            "models": snapshot["models"],
            "summary": snapshot["model_summary"],
        }

    @application.get("/api/events")
    async def events():
        snapshot = await asyncio.to_thread(_get_snapshot)
        return {"events": snapshot["events"][:3]}

    @application.get("/")
    async def index():
        path = _WEB_DIST / "index.html"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return JSONResponse(
                {"detail": "Dashboard frontend is not built"}, status_code=503
            )
        return HTMLResponse(
            content,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @application.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(
                {"detail": f"No such API endpoint: /{full_path}"}, status_code=404
            )
        candidate = _WEB_DIST / full_path
        try:
            if (
                full_path
                and candidate.resolve().is_relative_to(_WEB_DIST.resolve())
                and candidate.is_file()
            ):
                return FileResponse(candidate)
        except OSError:
            pass
        return JSONResponse({"detail": "not found"}, status_code=404)

    return application


def start_readonly_status_panel_server(
    host: str = "127.0.0.1",
    port: int = 9120,
    open_browser: bool = False,
    initial_profile: str = "",
) -> None:
    if host not in _LOOPBACK_HOSTS or int(port) != 9120:
        raise SystemExit("Standalone status panel only permits loopback port 9120")
    import uvicorn

    application = create_readonly_status_panel_app()
    config = uvicorn.Config(
        application,
        host=host,
        port=int(port),
        log_level="warning",
        access_log=False,
        proxy_headers=False,
    )
    server = uvicorn.Server(config)

    async def serve() -> None:
        if not config.loaded:
            config.load()
        server.lifespan = config.lifespan_class(config)
        with server.capture_signals():
            await server.startup()
            if server.should_exit:
                return
            application.state.bound_host = host
            application.state.bound_port = int(port)
            print(f"HERMES_STATUS_PANEL_READY port={int(port)}", flush=True)
            print(
                f"  Hermes Standalone Status Panel → http://{host}:{int(port)}",
                flush=True,
            )
            if open_browser:
                url = f"http://{host}:{int(port)}"
                if initial_profile:
                    url += "?profile=" + urllib.parse.quote(initial_profile, safe="")
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            await server.main_loop()
            if server.started:
                await server.shutdown()

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    start_readonly_status_panel_server()
