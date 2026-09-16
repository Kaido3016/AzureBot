# Microsoft Copilot Studio integration

AzureBot now exposes a dedicated **Copilot Studio gateway** under `/api/copilot`.

The design is:

```text
Microsoft Copilot Studio
        |
        | OAuth 2.0 / custom connector
        v
AzureBot Copilot Gateway
        |
        | On-Behalf-Of (OBO)
        v
Microsoft Graph
   |       |       |
 SharePoint  Outlook  Calendar

AzureBot RAG remains the enterprise evidence layer:
Entra identity -> Azure AI Search -> authorization -> grounded Azure OpenAI
```

## What is implemented

- `GET /api/copilot/health` — connector readiness without exposing secrets.
- `GET /api/copilot/me` — signed-in Microsoft 365 profile through Graph.
- `GET /api/copilot/sharepoint/search?q=...&limit=...` — bounded Graph search for SharePoint/Microsoft 365 content.
- `GET /api/copilot/mail/messages?limit=...` — bounded recent messages.
- `GET /api/copilot/calendar/events?limit=...` — bounded upcoming events.
- OAuth 2.0 On-Behalf-Of token exchange using MSAL.
- No Graph credentials are accepted from the caller; the caller's delegated identity is exchanged server-side.
- Query and result limits are bounded to keep agent actions predictable.

## Required Entra configuration

Create or use an Entra application registration representing the AzureBot API.

Set these application settings in the Azure host:

```text
COPILOT_ENTRA_TENANT_ID=<tenant id>
COPILOT_ENTRA_CLIENT_ID=<API application client id>
COPILOT_ENTRA_CLIENT_SECRET=<confidential client credential>
```

Prefer a certificate-based credential for a production deployment. Never commit a secret to Git.

Expose the API to the Copilot Studio client application and configure the required delegated Microsoft Graph permissions according to the actions actually enabled. A typical least-privilege starting point is:

- `User.Read` for `/me`.
- `Files.Read.All` and/or `Sites.Read.All` for SharePoint search, subject to the organization's consent policy.
- `Mail.Read` for recent messages.
- `Calendars.Read` for calendar events.

Grant admin consent only where the tenant's security policy requires it. Do not request permissions that the agent does not use.

## Copilot Studio custom connector

`docs/openapi/copilot-studio.yaml` is an importable OpenAPI starting point for a custom connector. Configure OAuth 2.0 against the same Entra tenant and API registration used by the gateway.

After importing, expose only the actions required by the agent. For example:

1. `GetMyProfile`
2. `SearchSharePoint`
3. `GetRecentMail`
4. `GetUpcomingCalendarEvents`

The agent can then combine these actions with AzureBot's existing RAG capabilities.

## Important portfolio disclosure

Adding this integration to the repository does **not** by itself prove that a Copilot Studio agent has been deployed in a Microsoft 365 tenant. The final tenant-specific step is to import the connector into Copilot Studio, configure OAuth/permissions, create topics or agent instructions, test the actions with real tenant data, and verify telemetry.

After those steps are completed, the project can truthfully document the actual Copilot Studio hands-on work performed.

## Security boundaries

- Treat Copilot input as untrusted.
- Keep Microsoft Graph authorization delegated to the signed-in user.
- Preserve SharePoint/Microsoft 365 ACL enforcement; do not copy protected content into an unrestricted cache.
- Keep secrets in Azure-managed configuration/Key Vault rather than source control.
- Log action names, latency and status, but do not log Graph access tokens or message/document contents by default.
- Keep the existing AzureBot RAG security model: retrieved content is untrusted and cannot override system policy.
