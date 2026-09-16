"""Microsoft Copilot Studio integration gateway for AzureBot."""

from __future__ import annotations

import os
from typing import Any

import aiohttp
import msal
from quart import Blueprint, current_app, jsonify, request

from config import CONFIG_CHAT_APPROACH, CONFIG_CHAT_HISTORY_BROWSER_ENABLED, CONFIG_CHAT_HISTORY_COSMOS_ENABLED
from core.sessionhelper import create_session_id
from decorators import authenticated

bp = Blueprint("copilot_studio", __name__, url_prefix="/api/copilot")
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _required_config() -> tuple[str, str, str] | None:
    tenant = os.getenv("COPILOT_ENTRA_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("COPILOT_ENTRA_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("COPILOT_ENTRA_CLIENT_SECRET")
    return (tenant, client_id, client_secret) if tenant and client_id and client_secret else None


def _obo_access_token(user_assertion: str) -> str:
    config = _required_config()
    if config is None:
        raise RuntimeError("Set COPILOT_ENTRA_TENANT_ID, COPILOT_ENTRA_CLIENT_ID and COPILOT_ENTRA_CLIENT_SECRET")
    tenant, client_id, client_secret = config
    client = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"https://login.microsoftonline.com/{tenant}",
    )
    result = client.acquire_token_on_behalf_of(user_assertion=user_assertion, scopes=[GRAPH_SCOPE])
    token = result.get("access_token")
    if not token:
        raise PermissionError(result.get("error_description", "Graph token acquisition failed"))
    return token


async def _graph_get(path: str, token: str, params: dict[str, str] | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        async with session.get(f"{GRAPH_ROOT}{path}", headers=headers, params=params) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise PermissionError(body.get("error", {}).get("message", "Microsoft Graph request failed"))
            return body


async def _graph_post(path: str, token: str, payload: dict[str, Any]) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.post(f"{GRAPH_ROOT}{path}", headers=headers, json=payload) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise PermissionError(body.get("error", {}).get("message", "Microsoft Graph request failed"))
            return body


@bp.get("/health")
async def health():
    return jsonify({"service": "azurebot-copilot-gateway", "configured": _required_config() is not None})


@bp.post("/ask")
@authenticated
async def ask(auth_claims: dict[str, Any]):
    """Expose AzureBot's existing grounded RAG orchestration to Copilot Studio."""
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    payload = await request.get_json()
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    if len(question) > 4000:
        return jsonify({"error": "question must be 4000 characters or fewer"}), 400
    approach = current_app.config[CONFIG_CHAT_APPROACH]
    session_state = payload.get("conversationId") or create_session_id(
        current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED],
        current_app.config[CONFIG_CHAT_HISTORY_BROWSER_ENABLED],
    )
    result = await approach.run(
        [{"role": "user", "content": question}],
        context={"auth_claims": auth_claims, "copilot_studio": True},
        session_state=session_state,
    )
    return jsonify(result)


@bp.get("/me")
async def me():
    incoming = _bearer_token()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    try:
        return jsonify(await _graph_get("/me", _obo_access_token(incoming), {"$select": "id,displayName,mail,userPrincipalName"}))
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.get("/sharepoint/search")
async def sharepoint_search():
    incoming = _bearer_token()
    query = (request.args.get("q") or "").strip()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    if not query:
        return jsonify({"error": "q is required"}), 400
    if len(query) > 300:
        return jsonify({"error": "q must be 300 characters or fewer"}), 400
    try:
        limit = min(max(int(request.args.get("limit", "5")), 1), 10)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    payload = {"requests": [{"entityTypes": ["driveItem", "listItem"], "query": {"queryString": query}, "from": 0, "size": limit}]}
    try:
        return jsonify(await _graph_post("/search/query", _obo_access_token(incoming), payload))
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.get("/mail/messages")
async def mail_messages():
    incoming = _bearer_token()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    try:
        limit = min(max(int(request.args.get("limit", "5")), 1), 10)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    try:
        return jsonify(await _graph_get("/me/messages", _obo_access_token(incoming), {"$top": str(limit), "$select": "id,subject,from,receivedDateTime,webLink", "$orderby": "receivedDateTime DESC"}))
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.get("/calendar/events")
async def calendar_events():
    incoming = _bearer_token()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    try:
        limit = min(max(int(request.args.get("limit", "5")), 1), 10)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    try:
        return jsonify(await _graph_get("/me/events", _obo_access_token(incoming), {"$top": str(limit), "$select": "id,subject,start,end,location,webLink", "$orderby": "start/dateTime"}))
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
