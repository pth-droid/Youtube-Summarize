# Provider connections

Open **Settings → Provider access**, then select **Add connection**.

1. Give the connection a name that you will recognize.
2. Enter the API endpoint and exact model ID from your provider or local server.
3. Choose **OpenAI-compatible chat** or **Anthropic Messages**.
4. Enter an API key if the endpoint needs one. Keys use the operating system credential store. If the endpoint needs no key, open **Connection options** and select that choice.
5. Select **Save connection**. Saving sends no model request.
6. Open the saved connection and select **Use as default**, or choose it in your learning preferences or page options.

There is no fixed provider list or model list. You can save several connections for the same provider, with different model IDs, endpoints, or keys. The API format must match one of the two supported request formats. Codex subscription access stays available. Existing DeepSeek access and saved API connections remain available.

Open a saved connection to edit it, remove its saved key, or remove the connection. Leave the key field blank when editing to keep the existing key. Removing the default connection returns the default to Codex. Saved learning pages stay available and keep the original connection name. Finish or cancel jobs that use a connection before editing or removing it.

## Connection fields

- **Connection name:** your display name. It appears in the hub, default settings, and page options.
- **API endpoint:** the base URL ending in the provider's version path, or its full request URL. The app adds `/chat/completions` or `/messages` if needed.
- **Model ID:** the provider's exact model ID. Enter any model ID supported by that endpoint. There is no automatic model change.
- **API format:** Chat Completions or Anthropic Messages. Other protocols need a separate connector.
- **JSON mode:** request a JSON object. Turn this off if your compatible server does not support `response_format`. Source checks still apply.
- **Output limit field:** use `max_tokens` for most compatible APIs, or `max_completion_tokens` when the model requires it. This field applies to Chat Completions only.

Local servers can use HTTP on localhost, 127.0.0.1, or ::1. Remote endpoints require HTTPS. Any connection can be marked as requiring no API key. API requests need approval unless you enable them as a default in Settings.

Changing a saved connection affects new pages. Retrying a failed page uses the current connection and starts new analysis if that connection changed. A completed page keeps its saved result.

All new API connectors use the shared source checks, checkpoints, and model profiles described in [MODEL_PROFILES.md](MODEL_PROFILES.md). Their default limits are conservative. Configure a model profile when you know the model's limits.

## Library folder

**Browse** opens a Windows folder picker. It fills the folder field. Press **Change library folder** to copy the library and save the location. Canceling Browse changes nothing. The picker is for the local Windows app; a future hosted app needs a different storage selection flow.

## Verification status

These connections have not been checked with live provider accounts. Model support, account access, JSON mode, and output limits depend on the selected service. No paid API request was made during this change.

API formats were implemented from the official [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) and [Claude Messages reference](https://platform.claude.com/docs/en/api/messages/create).
