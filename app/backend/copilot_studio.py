"""Microsoft Copilot Studio integration gateway for AzureBot.

The gateway is intentionally kept separate from the existing RAG routes. Copilot
Studio can call these actions through an OpenAPI custom connector while AzureBot
continues to own retrieval, identity and observability concerns.

Graph calls use OAuth 2.0 On-Behalf-Of (OBO). The incoming access token must be
issued for this API and the API application registration must be configured as a
confidential client with Microsoft Graph delegated permissions.
"""

from __future__ import annotations

import os
from typing import Any

import aiohttp
import msal
from quart import Blueprint, jsonify, request

bp = Blueprint("copilot_studio", __name__, url_prefix="/api/copilot")

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _required_config() -> tuple[str, str, str] | None:
    tenant = os.getenv("COPILOT_ENTRA_TENANT_ID") or os.getenv("AZURE_TENANT_ID")
    client_id = os.getenv("COPILOT_ENTRA_CLIENT_ID") or os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("COPILOT_ENTRA_CLIENT_SECRET")
    if not tenant or not client_id or not client_secret:
        return None
    return tenant, client_id, client_secret


def _obo_access_token(user_assertion: str) -> str:
    config = _required_config()
    if config is None:
        raise RuntimeError(
            "Copilot OBO is not configured. Set COPILOT_ENTRA_TENANT_ID, "
            "COPILOT_ENTRA_CLIENT_ID and COPILOT_ENTRA_CLIENT_SECRET."
        )

    tenant, client_id, client_secret = config
    authority = f"https://login.microsoftonline.com/{tenant}"
    client = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )
    result = client.acquire_token_on_behalf_of(
        user_assertion=user_assertion,
        scopes=[GRAPH_SCOPE],
    )
    access_token = result.get("access_token")
    if not access_token:
        detail = result.get("error_description", "Graph token acquisition failed")
        raise PermissionError(detail)
    return access_token


async def _graph_get(path: str, token: str, params: dict[str, str] | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(f"{GRAPH_ROOT}{path}", headers=headers, params=params) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise PermissionError(body.get("error", {}).get("message", "Microsoft Graph request failed"))
            return body


async def _graph_post(path: str, token: str, payload: dict[str, Any]) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(f"{GRAPH_ROOT}{path}", headers=headers, json=payload) as response:
            body = await response.json(content_type=None)
            if response.status >= 400:
                raise PermissionError(body.get("error", {}).get("message", "Microsoft Graph request failed"))
            return body


@bp.get("/health")
async def health():
    """Non-sensitive readiness endpoint for a Copilot Studio connector."""
    configured = _required_config() is not None
    return jsonify({"service": "azurebot-copilot-gateway", "configured": configured})


@bp.get("/me")
async def me():
    """Return the signed-in Microsoft 365 user's basic profile through Graph."""
    incoming = _bearer_token()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    try:
        graph_token = _obo_access_token(incoming)
        profile = await _graph_get("/me", graph_token, {"$select": "id,displayName,mail,userPrincipalName"})
        return jsonify(profile)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.get("/sharepoint/search")
async def sharepoint_search():
    """Search Microsoft 365/SharePoint content using the caller's delegated identity.

    This uses Graph's search endpoint so SharePoint ACLs remain enforced by
    Microsoft 365. The connector accepts a small query and result limit to keep
    agent actions bounded.
    """
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

    payload = {
        "requests": [
            {
                "entityTypes": ["driveItem", "listItem"],
                "query": {"queryString": query},
                "from": 0,
                "size": limit,
            }
        ]
    }
    try:
        graph_token = _obo_access_token(incoming)
        result = await _graph_post("/search/query", graph_token, payload)
        return jsonify(result)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.get("/mail/messages")
async def mail_messages():
    """Return a bounded set of recent mail messages for an agent action."""
    incoming = _bearer_token()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    try:
        limit = min(max(int(request.args.get("limit", "5")), 1), 10)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    try:
        graph_token = _obo_access_token(incoming)
        result = await _graph_get(
            "/me/messages",
            graph_token,
            {
                "$top": str(limit),
                "$select": "id,subject,from,receivedDateTime,webLink",
                "$orderby": "receivedDateTime DESC",
            },
        )
        return jsonify(result)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@bp.get("/calendar/events")
async def calendar_events():
    """Return a bounded set of upcoming calendar events."""
    incoming = _bearer_token()
    if not incoming:
        return jsonify({"error": "Bearer token required"}), 401
    try:
        limit = min(max(int(request.args.get("limit", "5")), 1), 10)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    try:
        graph_token = _obo_access_token(incoming)
        result = await _graph_get(
            "/me/events",
            graph_token,
            {
                "$top": str(limit),
                "$select": "id,subject,start,end,location,webLink",
                "$orderby": "start/dateTime",
            },
        )
        return jsonify(result)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
