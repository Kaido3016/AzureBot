# Microsoft Copilot Studio Integration

AzureBot is designed to expose its enterprise RAG capabilities to Microsoft Copilot Studio through a secured HTTP/custom-connector boundary.

## Target architecture

```text
Microsoft Copilot Studio agent
          |
          | Custom connector / OpenAPI action
          v
AzureBot API
          |
          +--> Microsoft Entra ID authentication
          +--> authorization / evidence policy
          +--> Azure AI Search
          +--> Azure OpenAI
          +--> citations + abstention
          +--> Application Insights / OpenTelemetry
```

## Copilot Studio action contract

The companion OpenAPI document at `docs/openapi/copilot-studio.yaml` defines a minimal connector contract for sending a user question to AzureBot and receiving an answer with citations.

The contract is intentionally narrow: Copilot Studio should call a dedicated backend action rather than receive direct access to Azure AI Search or Azure OpenAI credentials.

## Microsoft 365 / Microsoft Graph boundary

For enterprise scenarios, a Copilot Studio agent can use Microsoft Graph-backed actions for Microsoft 365 resources such as SharePoint, Teams, and Outlook. Graph permissions and Entra authentication must be configured in the customer's Microsoft tenant; this repository does not claim that tenant configuration has been completed.

A recommended flow is:

```text
Copilot Studio
   |
   +--> Graph action (M365 data, when authorized)
   |
   +--> AzureBot RAG action
           |
           +--> Azure AI Search
           +--> Azure OpenAI
```

## Security requirements

- Use Microsoft Entra ID/OAuth rather than static credentials.
- Apply least-privilege Microsoft Graph permissions.
- Keep Graph and Azure service credentials out of prompts and source code.
- Treat SharePoint/Teams/Outlook content as untrusted retrieved data.
- Preserve AzureBot's authorization and evidence policy before generation.
- Log connector/action latency and failures without logging sensitive document content.

## Validation status

This documentation and connector contract are portfolio integration assets. They are **not** evidence that a Copilot Studio agent has been deployed in a Microsoft tenant. Actual hands-on Copilot Studio experience requires importing/configuring the connector in Copilot Studio and executing an end-to-end test with an Entra-authenticated tenant.
