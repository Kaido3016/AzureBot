import pytest
from quart import Quart

from copilot_studio import bp


def make_client():
    app = Quart(__name__)
    app.register_blueprint(bp)
    return app.test_client()


@pytest.mark.asyncio
async def test_copilot_health_does_not_expose_secrets(monkeypatch):
    monkeypatch.delenv("COPILOT_ENTRA_TENANT_ID", raising=False)
    monkeypatch.delenv("COPILOT_ENTRA_CLIENT_ID", raising=False)
    monkeypatch.delenv("COPILOT_ENTRA_CLIENT_SECRET", raising=False)

    response = await make_client().get("/api/copilot/health")
    assert response.status_code == 200
    payload = await response.get_json()
    assert payload["service"] == "azurebot-copilot-gateway"
    assert payload["configured"] is False
    assert "secret" not in payload


@pytest.mark.asyncio
async def test_graph_actions_require_bearer_token():
    client = make_client()
    for path in ("/api/copilot/me", "/api/copilot/sharepoint/search?q=test", "/api/copilot/mail/messages"):
        response = await client.get(path)
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_sharepoint_query_is_bounded(monkeypatch):
    monkeypatch.setenv("COPILOT_ENTRA_TENANT_ID", "tenant")
    monkeypatch.setenv("COPILOT_ENTRA_CLIENT_ID", "client")
    monkeypatch.setenv("COPILOT_ENTRA_CLIENT_SECRET", "secret")

    response = await make_client().get(
        "/api/copilot/sharepoint/search?q=" + ("x" * 301),
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 400


def test_obo_configuration_is_not_enabled_without_all_values(monkeypatch):
    from copilot_studio import _required_config

    monkeypatch.setenv("COPILOT_ENTRA_TENANT_ID", "tenant")
    monkeypatch.setenv("COPILOT_ENTRA_CLIENT_ID", "client")
    monkeypatch.delenv("COPILOT_ENTRA_CLIENT_SECRET", raising=False)
    assert _required_config() is None
